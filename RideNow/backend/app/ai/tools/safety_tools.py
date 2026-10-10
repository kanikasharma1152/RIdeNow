"""
AI Safety Tools — Phase 13
==========================
Tools for the AI agent to orchestrate safety workflows strictly through
the verified service layer without executing direct SQL or faking emergency actions.

Security & Safety Controls:
- All tools enforce authentication & user role ownership
- Real telemetry only; zero hallucinated locations
- Never claims police or ambulance dispatched
- Transparent capability reporting
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.safety import (
    get_safety_center_service,
    get_ride_safety_events_service,
    get_user_safety_history_service,
    get_active_safety_events_for_user,
    trigger_sos,
    create_safety_event_service,
    get_trusted_contacts_service,
    add_trusted_contact_service,
    delete_trusted_contact_service,
    generate_ride_share_token_service,
)
from app.repositories.ride import get_ride_by_id
from app.repositories.driver import get_driver_by_id
from app.repositories.user import get_user_by_id
from app.core.exceptions import RideNotFoundError, UnauthorizedRideAccessError


async def get_safety_center_tool(
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Retrieve current safety status, active ride telemetry (driver, vehicle, location),
    trusted contacts, and platform safety capability flags for the user.
    """
    try:
        center = await get_safety_center_service(db, current_user)
        # Summarize trusted contacts and active events for AI context
        contacts_summary = [
            {"id": c.id, "name": c.name, "phone": c.phone, "relationship": c.relationship}
            for c in center.get("trusted_contacts", [])
        ]
        events_summary = [
            {"id": e.id, "event_type": e.event_type, "severity": e.severity, "status": e.status, "description": e.description}
            for e in center.get("active_safety_events", [])
        ]
        return {
            "success": True,
            "has_active_ride": center["has_active_ride"],
            "ride_id": center["ride_id"],
            "ride_status": center["ride_status"],
            "pickup_location": center["pickup_location"],
            "dropoff_location": center["dropoff_location"],
            "driver_name": center["driver_name"],
            "vehicle_model": center["vehicle_model"],
            "vehicle_number": center["vehicle_number"],
            "vehicle_type": center["vehicle_type"],
            "driver_location": (
                {"latitude": center["driver_latitude"], "longitude": center["driver_longitude"]}
                if center["driver_latitude"] else None
            ),
            "eta_minutes": center["eta_minutes"],
            "trusted_contacts": contacts_summary,
            "active_safety_events": events_summary,
            "safety_status": center["safety_status"],
            "capability_flags": center["capability_flags"],
        }
    except Exception as e:
        return {"error": f"Could not load safety center: {str(e)}"}


async def get_active_safety_events_tool(
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Retrieve all currently open or active safety notices and alerts for the user.
    """
    try:
        events = await get_active_safety_events_for_user(db, current_user.id)
        return {
            "active_events_count": len(events),
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "status": e.status,
                    "description": e.description,
                    "detected_at": e.detected_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
                for e in events
            ],
        }
    except Exception as e:
        return {"error": f"Could not retrieve active events: {str(e)}"}


async def create_safety_event_tool(
    event_type: str,
    severity: str = "MEDIUM",
    description: Optional[str] = None,
    ride_id: Optional[int] = None,
    current_user: Any = None,
    db: AsyncSession = None,
) -> Dict[str, Any]:
    """
    Report a structured safety concern (e.g. ROUTE_DEVIATION, DRIVER_BEHAVIOR, VEHICLE_ISSUE).
    """
    try:
        event = await create_safety_event_service(
            db=db,
            current_user=current_user,
            ride_id=ride_id,
            event_type=event_type,
            severity=severity,
            description=description,
        )
        return {
            "success": True,
            "event_id": event.id,
            "event_type": event.event_type,
            "severity": event.severity,
            "status": event.status,
            "message": f"Safety concern registered (ID #{event.id}). Our monitoring system is updated.",
        }
    except Exception as e:
        return {"error": f"Could not record safety concern: {str(e)}"}


async def trigger_sos_tool(
    note: Optional[str] = None,
    ride_id: Optional[int] = None,
    current_user: Any = None,
    db: AsyncSession = None,
) -> Dict[str, Any]:
    """
    Activate internal emergency SOS workflow.
    Creates a critical safety incident. Note: Does not replace direct 112/911 calls.
    """
    try:
        res = await trigger_sos(
            db=db,
            current_user=current_user,
            ride_id=ride_id,
            note=note or "Emergency SOS activated via AI Assistant.",
        )
        return res
    except Exception as e:
        return {"error": f"Failed to activate SOS: {str(e)}"}


async def get_trusted_contacts_tool(
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    """List user's configured emergency trusted contacts."""
    try:
        contacts = await get_trusted_contacts_service(db, current_user)
        return {
            "count": len(contacts),
            "contacts": [
                {"id": c.id, "name": c.name, "phone": c.phone, "relationship": c.relationship}
                for c in contacts
            ],
        }
    except Exception as e:
        return {"error": f"Could not retrieve trusted contacts: {str(e)}"}


async def create_trusted_contact_tool(
    name: str,
    phone: str,
    relationship: Optional[str] = None,
    current_user: Any = None,
    db: AsyncSession = None,
) -> Dict[str, Any]:
    """Add a new trusted contact for emergency trip sharing and alerts."""
    try:
        contact = await add_trusted_contact_service(
            db=db,
            current_user=current_user,
            name=name,
            phone=phone,
            relationship=relationship,
        )
        return {
            "success": True,
            "contact_id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "relationship": contact.relationship,
            "message": f"Trusted contact '{contact.name}' added successfully.",
        }
    except Exception as e:
        return {"error": f"Could not add trusted contact: {str(e)}"}


async def delete_trusted_contact_tool(
    contact_id: int,
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Remove a trusted contact by ID."""
    try:
        await delete_trusted_contact_service(db, contact_id, current_user)
        return {"success": True, "message": f"Trusted contact #{contact_id} removed."}
    except Exception as e:
        return {"error": f"Could not delete trusted contact: {str(e)}"}


async def prepare_ride_share_tool(
    ride_id: Optional[int] = None,
    current_user: Any = None,
    db: AsyncSession = None,
) -> Dict[str, Any]:
    """
    Generate an expiring privacy-preserving tracking link and formatted trip text for sharing with family.
    """
    try:
        # If ride_id not given, auto-resolve active ride
        if not ride_id:
            center = await get_safety_center_service(db, current_user)
            ride_id = center.get("ride_id")
            if not ride_id:
                return {"error": "You do not have an active ride to share right now."}

        res = await generate_ride_share_token_service(db, ride_id, current_user)
        return {
            "success": True,
            "ride_id": ride_id,
            "share_url": res["share_url"],
            "share_text": res["share_text"],
            "expires_at": res["expires_at"].strftime("%Y-%m-%d %H:%M:%S UTC"),
            "message": "Trip details prepared for sharing. You can copy the link or share it with your contacts.",
        }
    except Exception as e:
        return {"error": f"Could not prepare ride share: {str(e)}"}


async def get_driver_live_location_tool(
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Fetch the real-time GPS coordinates of the assigned driver for user's active trip.
    """
    try:
        center = await get_safety_center_service(db, current_user)
        if not center["has_active_ride"]:
            return {"error": "No active ride in progress."}
        if not center["driver_id"]:
            return {"message": "A driver is currently being matched to your pickup corridor."}

        lat = center["driver_latitude"]
        lon = center["driver_longitude"]
        if lat is None or lon is None:
            return {
                "driver_name": center["driver_name"],
                "message": "Driver is assigned, but GPS telemetry is temporarily updating. Please check again in a few seconds.",
            }

        return {
            "driver_name": center["driver_name"],
            "vehicle_model": center["vehicle_model"],
            "vehicle_number": center["vehicle_number"],
            "latitude": lat,
            "longitude": lon,
            "eta_minutes": center["eta_minutes"],
        }
    except Exception as e:
        return {"error": f"Could not get driver location: {str(e)}"}


async def get_vehicle_details_tool(
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Fetch exact vehicle model, license plate, and driver identity for user's active ride.
    """
    try:
        center = await get_safety_center_service(db, current_user)
        if not center["has_active_ride"]:
            return {"error": "You do not have an active ride right now."}
        if not center["driver_id"]:
            return {"message": "Driver matching is currently in progress."}

        return {
            "driver_name": center["driver_name"],
            "vehicle_model": center["vehicle_model"],
            "vehicle_number": center["vehicle_number"],
            "vehicle_type": center["vehicle_type"],
            "pickup_location": center["pickup_location"],
            "dropoff_location": center["dropoff_location"],
        }
    except Exception as e:
        return {"error": f"Could not retrieve vehicle details: {str(e)}"}


async def get_route_deviation_status_tool(
    ride_id: Optional[int] = None,
    current_user: Any = None,
    db: AsyncSession = None,
) -> Dict[str, Any]:
    """
    Check if any route deviation or stop anomaly has been flagged for the trip.
    """
    try:
        center = await get_safety_center_service(db, current_user)
        target_ride_id = ride_id or center.get("ride_id")
        if not target_ride_id:
            return {"error": "No active ride to check route status for."}

        events = await get_ride_safety_events_service(db, target_ride_id, current_user)
        deviation_events = [e for e in events if e.event_type == "ROUTE_DEVIATION" and e.status in ("ACTIVE", "OPEN", "ACKNOWLEDGED")]

        if deviation_events:
            latest = deviation_events[0]
            return {
                "route_deviated": True,
                "severity": latest.severity,
                "message": "Route deviation detected. The vehicle route differs from the expected corridor.",
                "event_id": latest.id,
            }
        return {
            "route_deviated": False,
            "message": "Vehicle is on the planned travel corridor. No deviations detected.",
        }
    except Exception as e:
        return {"error": f"Could not check route deviation: {str(e)}"}


# ─── Preserved Existing Tools ────────────────────────────────────────────────

async def get_ride_safety_events_tool(
    ride_id: int,
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    try:
        events = await get_ride_safety_events_service(db, ride_id, current_user)
        has_active_sos = any(e.event_type in ("SOS_TRIGGERED", "DRIVER_EMERGENCY", "PASSENGER_EMERGENCY") and e.status in ("ACTIVE", "OPEN", "ACKNOWLEDGED") for e in events)

        summarized = []
        for e in events:
            summarized.append({
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "status": e.status,
                "description": e.description,
                "detected_at": e.detected_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "resolved": e.status == "RESOLVED",
            })

        return {
            "ride_id": ride_id,
            "has_active_sos": has_active_sos,
            "total_safety_events": len(events),
            "safety_status": "CRITICAL_SOS_ACTIVE" if has_active_sos else ("NOTICES_RECORDED" if events else "ALL_NORMAL"),
            "events": summarized,
        }
    except RideNotFoundError:
        return {"error": f"Ride #{ride_id} not found."}
    except UnauthorizedRideAccessError:
        return {"error": "You are not authorized to view safety records for this trip."}
    except Exception as e:
        return {"error": f"Could not retrieve safety records: {str(e)}"}


async def get_my_safety_summary_tool(
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    try:
        events = await get_user_safety_history_service(db, current_user)
        active_count = sum(1 for e in events if e.status in ("ACTIVE", "OPEN", "ACKNOWLEDGED"))
        return {
            "user_id": current_user.id,
            "total_historical_events": len(events),
            "active_events_count": active_count,
            "recent_events": [
                {
                    "ride_id": e.ride_id,
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "status": e.status,
                    "description": e.description,
                    "detected_at": e.detected_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
                for e in events[:5]
            ],
        }
    except Exception as e:
        return {"error": f"Could not retrieve safety summary: {str(e)}"}
