"""
RideNow — WebSocket Endpoint
============================
Endpoint: /ws?token=<jwt_token>

Authenticates the client using JWT token via query parameter.
Maintains continuous bi-directional connection for:
- Real-time ride assignment and status transitions
- Live driver GPS tracking (persisted to DB + broadcast to passenger)
- Instant cancellation notifications
- Ping/pong heartbeat keepalive
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.core.connection_manager import ws_manager
from app.repositories.user import get_user_by_id
from app.repositories.revoked_token import is_token_revoked
from app.repositories.driver import get_driver_by_user_id, update_driver_location
from app.models.ride import Ride

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    if not token:
        logger.warning("[WS] Connection rejected: No token provided.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    payload = decode_access_token(token)
    if not payload:
        logger.warning("[WS] Connection rejected: Invalid token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    user_id_str = payload.get("sub")
    if not user_id_str:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
        return

    try:
        user_id = int(user_id_str)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid user ID")
        return

    # Verify user in DB and ensure token is not revoked
    async with AsyncSessionLocal() as db:
        jti = payload.get("jti")
        if jti and await is_token_revoked(db, jti):
            logger.warning(f"[WS] Connection rejected: Token revoked for user {user_id}.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token revoked")
            return

        user = await get_user_by_id(db, user_id)
        if not user or not user.is_active:
            logger.warning(f"[WS] Connection rejected: User {user_id} inactive or not found.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User inactive")
            return

        user_role = user.role

        # If driver, register driver_id mapping for WS manager routing
        if user_role == "driver":
            driver = await get_driver_by_user_id(db, user.id)
            if driver:
                ws_manager.register_driver_id(driver.id, user.id)

    # Register connection
    await ws_manager.connect(websocket, user_id, user_role)

    # Send initial connection acknowledgment
    try:
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "user_id": user_id,
            "role": user_role,
            "message": "Connected to RideNow Real-Time Gateway",
        })
    except Exception as e:
        logger.warning(f"[WS] Failed to send connection ack: {e}")
        ws_manager.disconnect(websocket, user_id)
        return

    # Event listening loop
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                data = {"raw": raw_text}

            msg_type = data.get("type", "").upper()

            if msg_type == "PING":
                await websocket.send_json({"type": "PONG", "timestamp": data.get("timestamp")})

            elif msg_type == "DRIVER_LOCATION":
                lat = data.get("latitude")
                lon = data.get("longitude")
                if lat is not None and lon is not None and user_role == "driver":
                    try:
                        async with AsyncSessionLocal() as db:
                            # 1. Persist location to DB
                            driver = await get_driver_by_user_id(db, user_id)
                            if driver:
                                await update_driver_location(db, driver, lat, lon)
                                # update_driver_location already commits

                                # 2. Find passengers with active rides assigned to this driver
                                result = await db.execute(
                                    select(Ride).where(
                                        Ride.driver_id == driver.id,
                                        Ride.status.in_(["ACCEPTED", "STARTED"]),
                                    )
                                )
                                active_rides = result.scalars().all()

                                # 3. Broadcast location update to each passenger
                                now_iso = datetime.now(timezone.utc).isoformat()
                                for ride in active_rides:
                                    await ws_manager.send_personal_message(
                                        ride.passenger_id,
                                        {
                                            "type": "DRIVER_LOCATION_UPDATE",
                                            "driver_id": driver.id,
                                            "latitude": lat,
                                            "longitude": lon,
                                            "timestamp": now_iso,
                                            "ride_id": ride.id,
                                        },
                                    )

                                logger.debug(
                                    f"[WS] Driver {user_id} location persisted ({lat}, {lon}); "
                                    f"notified {len(active_rides)} passenger(s)"
                                )
                    except Exception as exc:
                        logger.error(f"[WS] Failed to process DRIVER_LOCATION for user {user_id}: {exc}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as exc:
        logger.error(f"[WS] Unexpected socket error for user {user_id}: {exc}")
        ws_manager.disconnect(websocket, user_id)
