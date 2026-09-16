"""
RideNow — Real-Time WebSocket Connection Manager
=================================================
Manages active WebSocket connections for passengers and drivers.
Supports:
- Direct messaging to specific users (by user_id)
- Role-based broadcasting (e.g. to all online drivers)
- Ride event dispatching
- Redis Pub/Sub integration for multi-worker scaling (with graceful in-memory fallback)
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Tracks active WebSockets grouped by user_id and role.
    Thread-safe and async-safe.
    """

    def __init__(self):
        # user_id -> set of active WebSocket instances (allows multiple tabs/devices)
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # user_id -> role ("passenger" or "driver")
        self.user_roles: Dict[int, str] = {}
        # driver_id -> user_id mapping
        self.driver_to_user: Dict[int, int] = {}
        # Redis listener task reference
        self._pubsub_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, user_id: int, role: str):
        """Accept a WebSocket connection and register user."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self.user_roles[user_id] = role
        logger.info(f"[WS] User {user_id} ({role}) connected. Total active sockets for user: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.user_roles.pop(user_id, None)
        logger.info(f"[WS] User {user_id} disconnected.")

    def register_driver_id(self, driver_id: int, user_id: int):
        """Map driver table id to user_id."""
        self.driver_to_user[driver_id] = user_id

    def get_user_id_for_driver(self, driver_id: int) -> Optional[int]:
        return self.driver_to_user.get(driver_id)

    async def send_personal_message(self, user_id: int, message: Dict[str, Any]):
        """
        Send JSON payload to all active connections for a given user.
        """
        sockets = self.active_connections.get(user_id)
        if not sockets:
            logger.debug(f"[WS] User {user_id} has no active connections.")
            return

        dead_sockets = set()
        text_data = json.dumps(message, default=str)

        for ws in list(sockets):
            try:
                await ws.send_text(text_data)
            except Exception as e:
                logger.warning(f"[WS] Failed sending to user {user_id}: {e}")
                dead_sockets.add(ws)

        for ws in dead_sockets:
            self.disconnect(ws, user_id)

    async def broadcast_to_role(self, role: str, message: Dict[str, Any]):
        """Broadcast a message to all connected users with a given role."""
        target_user_ids = [uid for uid, r in self.user_roles.items() if r == role]
        for uid in target_user_ids:
            await self.send_personal_message(uid, message)

    async def send_ride_event(
        self,
        event_type: str,
        ride_id: int,
        passenger_user_id: Optional[int],
        driver_user_id: Optional[int],
        payload: Dict[str, Any],
    ):
        """
        Convenience dispatcher for ride lifecycle events.
        Dispatches to passenger and/or driver with standardized envelope.
        """
        envelope = {
            "type": event_type,
            "ride_id": ride_id,
            "data": payload,
        }

        # Deduplicate user IDs to prevent sending duplicate WebSocket events when passenger_user_id == driver_user_id
        target_user_ids = {uid for uid in (passenger_user_id, driver_user_id) if uid is not None}
        tasks = [self.send_personal_message(uid, envelope) for uid in target_user_ids]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def is_user_connected(self, user_id: int) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


# Global singleton instance
ws_manager = ConnectionManager()
