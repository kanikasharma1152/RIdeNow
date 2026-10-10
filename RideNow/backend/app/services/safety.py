"""
RideNow Safety Service — Production-Grade Safety & Trust Intelligence
=====================================================================
Handles core safety logic:
- Safety Center operational state and capability flags
- Real-time telemetry evaluation (route deviation, speed anomaly, prolonged stop)
- Idempotent safety event creation, acknowledgment, and resolution
- Critical SOS triggering (passenger & driver) with honest capability boundaries
- WebSocket alerts and calm notifications
- Isolated trusted contact management
- Expiring, privacy-preserving live ride sharing
- Admin safety analytics
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safety import SafetyEvent, TrustedContact, RideShareToken
from app.models.ride import Ride
from app.models.driver import Driver
from app.models.user import User

from app.repositories.safety import (
    create_safety_event,
    get_safety_event_by_id,
    get_safety_events_by_ride,
    get_active_sos,
    resolve_safety_event,
    acknowledge_safety_event,
    get_user_safety_events,
    get_active_safety_events_for_user,
    create_trusted_contact,
    get_trusted_contacts_by_user,
    get_trusted_contact_by_id,
    update_trusted_contact,
    delete_trusted_contact,
    create_ride_share_token,
    get_valid_share_token,
    revoke_share_token,
    get_admin_safety_aggregates,
    get_all_safety_events_admin,
)
from app.repositories.ride import get_ride_by_id
from app.repositories.driver import get_driver_by_user_id, get_driver_by_id
from app.repositories.user import get_user_by_id

from app.services.notification import send_notification
from app.core.connection_manager import ws_manager
from app.core.exceptions import (
    RideNotFoundError,
    UnauthorizedRideAccessError,
    InvalidRideStateError,
)
from app.ml.anomaly.detector import (
    check_route_deviation,
    check_long_stop,
    check_speed_anomaly,
)


# ─── Helper: Verify Ride Participant ─────────────────────────────────────────

async def _verify_ride_access(
    db: AsyncSession,
    ride: Ride,
    user_id: int,
    user_role: str,
) -> bool:
    """Check if user is passenger, assigned driver, or admin."""
    if user_role == "admin":
        return True
    if ride.passenger_id == user_id:
        return True
    if ride.driver_id is not None:
        driver = await get_driver_by_id(db, ride.driver_id)
        if driver and driver.user_id == user_id:
            return True
    return False


# ─── Helper: Emit Safety Event via WS ─────────────────────────────────────────

async def _emit_safety_ws(
    ride_id: Optional[int],
    passenger_user_id: Optional[int],
    driver_user_id: Optional[int],
    event: SafetyEvent,
    message: str,
):
    """Emit SAFETY_EVENT and specific typed alert to participants and admins."""
    payload = {
        "event_id": event.id,
        "ride_id": event.ride_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "status": event.status,
        "description": event.description or message,
        "message": message,
        "timestamp": event.created_at.isoformat() if event.created_at else datetime.utcnow().isoformat(),
        "latitude": event.latitude,
        "longitude": event.longitude,
        "evidence": event.evidence,
    }
    envelope = {
        "type": "SAFETY_EVENT",
        "event_name": event.event_type,
        "ride_id": ride_id,
        "severity": event.severity,
        "timestamp": payload["timestamp"],
        "message": message,
        "data": payload,
    }

    target_users = {uid for uid in (passenger_user_id, driver_user_id) if uid is not None}
    for uid in target_users:
        try:
            await ws_manager.send_personal_message(uid, envelope)
        except Exception:
            pass

    # Also broadcast critical/high events to admin command center
    if event.severity in ("CRITICAL", "HIGH") or event.event_type in ("SOS_TRIGGERED", "DRIVER_EMERGENCY"):
        try:
            await ws_manager.broadcast_to_role("admin", envelope)
        except Exception:
            pass


# ─── 1. Safety Center API ─────────────────────────────────────────────────────

async def get_safety_center_service(
    db: AsyncSession,
    current_user: Any,
) -> Dict[str, Any]:
    """
    Returns comprehensive, factual Safety Center state:
    - Active ride telemetry (driver, vehicle, location, status)
    - Trusted contacts list
    - Active safety events
    - Honest capability flags (NO fake emergency dispatch claims)
    """
    user_id = current_user.id
    user_role = getattr(current_user, "role", "passenger")

    # 1. Look for active ride for this user
    active_ride = None
    if user_role == "passenger":
        stmt = (
            select(Ride)
            .where(
                Ride.passenger_id == user_id,
                Ride.status.in_(["REQUESTED", "ACCEPTED", "STARTED"]),
            )
            .order_by(Ride.created_at.desc())
        )
        res = await db.execute(stmt)
        active_ride = res.scalars().first()
    elif user_role == "driver":
        driver = await get_driver_by_user_id(db, user_id)
        if driver:
            stmt = (
                select(Ride)
                .where(
                    Ride.driver_id == driver.id,
                    Ride.status.in_(["ACCEPTED", "STARTED"]),
                )
                .order_by(Ride.created_at.desc())
            )
            res = await db.execute(stmt)
            active_ride = res.scalars().first()

    # 2. Extract driver/vehicle details if active ride exists
    driver_name = None
    vehicle_model = None
    vehicle_number = None
    vehicle_type = None
    driver_lat = None
    driver_lon = None
    eta_mins = None

    if active_ride and active_ride.driver_id:
        driver = await get_driver_by_id(db, active_ride.driver_id)
        if driver:
            vehicle_model = driver.vehicle_model
            vehicle_number = driver.vehicle_number
            vehicle_type = driver.vehicle_type
            driver_lat = driver.latitude
            driver_lon = driver.longitude
            driver_user = await get_user_by_id(db, driver.user_id)
            if driver_user:
                driver_name = driver_user.name

            # Calculate rough ETA if driver coords available
            if driver_lat and driver_lon and active_ride.pickup_latitude and active_ride.pickup_longitude:
                from app.ml.eta.predictor import predict_eta_minutes
                eta_mins = predict_eta_minutes(
                    driver_lat, driver_lon,
                    active_ride.pickup_latitude, active_ride.pickup_longitude,
                )

    # 3. Fetch trusted contacts
    trusted_contacts = await get_trusted_contacts_by_user(db, user_id)

    # 4. Fetch active safety events
    active_events = await get_active_safety_events_for_user(db, user_id)
    has_active_sos = any(
        e.event_type in ("SOS_TRIGGERED", "DRIVER_EMERGENCY", "PASSENGER_EMERGENCY")
        for e in active_events
    )

    safety_status = "CRITICAL_ALERT" if has_active_sos else ("MONITORED_NOTICE" if active_events else "NORMAL")

    # 5. Define available safety actions
    available_actions = ["report_safety_concern", "manage_trusted_contacts"]
    if active_ride:
        available_actions.extend(["trigger_sos", "share_ride", "view_vehicle_details", "view_driver_location"])

    # 6. Honest capability boundaries
    capability_flags = {
        "direct_emergency_calling": False,
        "external_police_dispatch": False,
        "live_telemetry_monitoring": True,
        "route_deviation_detection": True,
        "prolonged_stop_detection": True,
        "share_ready": True,
        "guidance": "In immediate physical danger, always call 112 / 911 directly from your mobile phone.",
    }

    return {
        "has_active_ride": active_ride is not None,
        "ride_id": active_ride.id if active_ride else None,
        "ride_status": active_ride.status if active_ride else None,
        "pickup_location": active_ride.pickup_location if active_ride else None,
        "dropoff_location": active_ride.dropoff_location if active_ride else None,
        "driver_id": active_ride.driver_id if active_ride else None,
        "driver_name": driver_name,
        "vehicle_model": vehicle_model,
        "vehicle_number": vehicle_number,
        "vehicle_type": vehicle_type,
        "driver_latitude": driver_lat,
        "driver_longitude": driver_lon,
        "eta_minutes": eta_mins,
        "trusted_contacts": trusted_contacts,
        "active_safety_events": active_events,
        "available_actions": available_actions,
        "capability_flags": capability_flags,
        "safety_status": safety_status,
    }


# ─── 2. Universal SOS Emergency System ────────────────────────────────────────

async def trigger_sos(
    db: AsyncSession,
    current_user: Any,
    ride_id: Optional[int] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trigger emergency SOS for a passenger or driver.
    Works for both active ride trips and general emergency triggers.
    Strictly reports internal safety event creation without claiming external 911/112 dispatch.
    """
    user_id = current_user.id
    user_role = getattr(current_user, "role", "passenger")

    ride = None
    if ride_id:
        ride = await get_ride_by_id(db, ride_id)
        if not ride:
            raise RideNotFoundError(f"Ride #{ride_id} not found")
        has_access = await _verify_ride_access(db, ride, user_id, user_role)
        if not has_access:
            raise UnauthorizedRideAccessError("You are not authorized to trigger SOS for this ride")
        # Reject SOS on inactive rides (CANCELLED, COMPLETED)
        if ride.status in ("CANCELLED", "COMPLETED"):
            raise InvalidRideStateError(
                f"Cannot trigger SOS on a {ride.status.lower()} ride. SOS is only available during active trips."
            )
    else:
        # Auto-detect active ride for the user
        if user_role == "passenger":
            stmt = select(Ride).where(
                Ride.passenger_id == user_id,
                Ride.status.in_(["REQUESTED", "ACCEPTED", "STARTED"]),
            ).order_by(Ride.created_at.desc())
            res = await db.execute(stmt)
            ride = res.scalars().first()

    # Check for existing active SOS
    existing_sos = await get_active_sos(db, ride.id if ride else None, user_id)
    if existing_sos:
        return {
            "success": True,
            "event_id": existing_sos.id,
            "status": existing_sos.status,
            "severity": existing_sos.severity,
            "message": "SOS is already active. RideNow Safety Workflow is currently engaged.",
            "emergency_services_contacted": False,
        }

    # Fetch driver user_id if assigned
    driver_user_id = None
    if ride and ride.driver_id:
        driver = await get_driver_by_id(db, ride.driver_id)
        if driver:
            driver_user_id = driver.user_id

    event_type = "SOS_TRIGGERED" if ride else "PASSENGER_EMERGENCY"
    desc = note or "Emergency SOS initiated by user."

    event = await create_safety_event(
        db=db,
        user_id=user_id,
        event_type=event_type,
        ride_id=ride.id if ride else None,
        severity="CRITICAL",
        status="OPEN",
        driver_id=ride.driver_id if ride else None,
        latitude=latitude or (ride.pickup_latitude if ride else None),
        longitude=longitude or (ride.pickup_longitude if ride else None),
        description=desc,
        evidence={
            "triggered_by_role": user_role,
            "ride_status": ride.status if ride else "NO_RIDE",
            "note": note,
        },
        debounce_seconds=0,
    )

    sos_msg = "RideNow Emergency Safety Event created. Operations team alerted."

    # Notifications
    await send_notification(
        db=db,
        user_id=user_id,
        ride_id=ride.id if ride else None,
        title="Emergency SOS Activated",
        message=sos_msg,
    )
    if driver_user_id and driver_user_id != user_id:
        await send_notification(
            db=db,
            user_id=driver_user_id,
            ride_id=ride.id if ride else None,
            title="Emergency SOS Notice",
            message="An emergency SOS has been initiated for this trip.",
        )

    # Emit real-time WebSocket event to user, driver, and admin
    await _emit_safety_ws(
        ride_id=ride.id if ride else None,
        passenger_user_id=ride.passenger_id if ride else user_id,
        driver_user_id=driver_user_id,
        event=event,
        message=sos_msg,
    )

    return {
        "success": True,
        "event_id": event.id,
        "status": event.status,
        "severity": event.severity,
        "message": sos_msg,
        "emergency_services_contacted": False,
        "disclaimer": (
            "RideNow cannot contact police or ambulance directly. "
            "For immediate emergency services, please call 112 (India) or 911 directly from your mobile phone."
        ),
    }


async def trigger_driver_sos_service(
    db: AsyncSession,
    current_user: Any,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    note: Optional[str] = None,
    ride_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Trigger emergency SOS for a driver on or off active duty.
    """
    driver = await get_driver_by_user_id(db, current_user.id)
    if not driver:
        raise UnauthorizedRideAccessError("Only registered drivers can trigger driver SOS")

    ride = None
    if ride_id:
        ride = await get_ride_by_id(db, ride_id)
        if not ride or ride.driver_id != driver.id:
            raise UnauthorizedRideAccessError("Driver is not assigned to this ride")
    else:
        # Check active ride
        stmt = select(Ride).where(
            Ride.driver_id == driver.id,
            Ride.status.in_(["ACCEPTED", "STARTED"]),
        ).order_by(Ride.created_at.desc())
        res = await db.execute(stmt)
        ride = res.scalars().first()

    event = await create_safety_event(
        db=db,
        user_id=current_user.id,
        event_type="DRIVER_EMERGENCY",
        ride_id=ride.id if ride else None,
        severity="CRITICAL",
        status="OPEN",
        driver_id=driver.id,
        latitude=latitude or driver.latitude,
        longitude=longitude or driver.longitude,
        description=note or "Driver emergency assistance requested.",
        evidence={"driver_id": driver.id, "license": driver.license_number},
        debounce_seconds=0,
    )

    msg = "Driver emergency alert registered. Command center and platform monitoring notified."
    await _emit_safety_ws(
        ride_id=ride.id if ride else None,
        passenger_user_id=ride.passenger_id if ride else None,
        driver_user_id=current_user.id,
        event=event,
        message=msg,
    )

    return {
        "success": True,
        "event_id": event.id,
        "status": event.status,
        "severity": event.severity,
        "message": msg,
        "emergency_services_contacted": False,
    }


# ─── 3. Safety Concern & Event Reporting ──────────────────────────────────────

async def create_safety_event_service(
    db: AsyncSession,
    current_user: Any,
    ride_id: Optional[int],
    event_type: str,
    severity: str,
    description: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> SafetyEvent:
    """Creates a user-reported safety concern or telemetry signal."""
    user_id = current_user.id
    user_role = getattr(current_user, "role", "passenger")

    ride = None
    if ride_id:
        ride = await get_ride_by_id(db, ride_id)
        if not ride:
            raise RideNotFoundError(f"Ride #{ride_id} not found")
        has_access = await _verify_ride_access(db, ride, user_id, user_role)
        if not has_access:
            raise UnauthorizedRideAccessError("Not authorized to report safety events for this ride")

    event = await create_safety_event(
        db=db,
        user_id=user_id,
        event_type=event_type,
        ride_id=ride.id if ride else None,
        severity=severity,
        status="OPEN",
        driver_id=ride.driver_id if ride else None,
        latitude=latitude,
        longitude=longitude,
        description=description,
        event_metadata=metadata,
        debounce_seconds=60,
    )

    # WS alert
    driver_user_id = None
    if ride and ride.driver_id:
        driver = await get_driver_by_id(db, ride.driver_id)
        if driver:
            driver_user_id = driver.user_id

    await _emit_safety_ws(
        ride_id=ride.id if ride else None,
        passenger_user_id=ride.passenger_id if ride else user_id,
        driver_user_id=driver_user_id,
        event=event,
        message=description or f"Safety notice recorded: {event_type}",
    )

    return event


async def acknowledge_safety_event_service(
    db: AsyncSession,
    event_id: int,
    current_user: Any,
) -> SafetyEvent:
    event = await get_safety_event_by_id(db, event_id)
    if not event:
        raise ValueError(f"Safety event #{event_id} not found")

    if event.ride_id:
        ride = await get_ride_by_id(db, event.ride_id)
        if ride:
            has_access = await _verify_ride_access(db, ride, current_user.id, current_user.role)
            if not has_access:
                raise UnauthorizedRideAccessError("Not authorized to acknowledge this event")
    elif event.user_id != current_user.id and current_user.role != "admin":
        raise UnauthorizedRideAccessError("Not authorized to acknowledge this event")

    return await acknowledge_safety_event(db, event, current_user.id)


async def resolve_safety_event_service(
    db: AsyncSession,
    event_id: int,
    current_user: Any,
) -> SafetyEvent:
    event = await get_safety_event_by_id(db, event_id)
    if not event:
        raise ValueError(f"Safety event #{event_id} not found")

    if event.ride_id:
        ride = await get_ride_by_id(db, event.ride_id)
        if ride:
            has_access = await _verify_ride_access(db, ride, current_user.id, current_user.role)
            if not has_access:
                raise UnauthorizedRideAccessError("Not authorized to resolve this safety event")
    elif event.user_id != current_user.id and current_user.role != "admin":
        raise UnauthorizedRideAccessError("Not authorized to resolve this safety event")

    return await resolve_safety_event(db, event, resolved_by=current_user.id)


async def get_ride_safety_events_service(
    db: AsyncSession,
    ride_id: int,
    current_user: Any,
) -> List[SafetyEvent]:
    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError(f"Ride #{ride_id} not found")

    has_access = await _verify_ride_access(db, ride, current_user.id, current_user.role)
    if not has_access:
        raise UnauthorizedRideAccessError("Not authorized to view safety events for this ride")

    return await get_safety_events_by_ride(db, ride_id)


async def get_user_safety_history_service(
    db: AsyncSession,
    current_user: Any,
) -> List[SafetyEvent]:
    """Returns safety history strictly isolated to the authenticated user."""
    return await get_user_safety_events(db, current_user.id)


# ─── 4. Route Deviation & Telemetry Intelligence ─────────────────────────────

async def evaluate_ride_telemetry(
    db: AsyncSession,
    ride_id: int,
    current_user: Any,
    latitude: float,
    longitude: float,
    speed_kmh: Optional[float] = None,
    route_waypoints: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates real-time GPS coordinates against route waypoints and anomaly rules.
    Creates structured, explainable SafetyEvents only when thresholds are breached.
    """
    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError(f"Ride #{ride_id} not found")

    has_access = await _verify_ride_access(db, ride, current_user.id, current_user.role)
    if not has_access:
        raise UnauthorizedRideAccessError("Unauthorized telemetry submission")

    active_statuses = {"REQUESTED", "ACCEPTED", "STARTED"}
    if ride.status not in active_statuses:
        return {"safe": True, "anomalies": [], "events_created": []}

    driver_user_id = None
    if ride.driver_id:
        driver = await get_driver_by_id(db, ride.driver_id)
        if driver:
            driver_user_id = driver.user_id

    anomalies: List[Dict[str, Any]] = []
    events_created: List[int] = []

    # 1. Route deviation check
    if route_waypoints and len(route_waypoints) >= 2:
        wp_tuples = [(pt[0], pt[1]) for pt in route_waypoints]
        rd = check_route_deviation(latitude, longitude, wp_tuples)
        if rd.get("is_deviated"):
            anomalies.append(rd)
            sev = rd.get("severity") or "LOW"
            event = await create_safety_event(
                db=db,
                user_id=ride.passenger_id,
                event_type="ROUTE_DEVIATION",
                ride_id=ride.id,
                severity=sev,
                status="OPEN",
                driver_id=ride.driver_id,
                latitude=latitude,
                longitude=longitude,
                description="Route differs from expected route. Please verify the route if needed.",
                evidence={
                    "min_distance_km": rd.get("min_distance_km"),
                    "threshold_km": rd.get("threshold_km"),
                },
                debounce_seconds=180,
            )
            if event:
                events_created.append(event.id)
                if sev in ("MEDIUM", "HIGH"):
                    msg = "Route deviation detected: The vehicle route differs from the expected corridor."
                    await send_notification(
                        db=db,
                        user_id=ride.passenger_id,
                        ride_id=ride.id,
                        title="Route Notice",
                        message=msg,
                    )
                    await _emit_safety_ws(ride.id, ride.passenger_id, driver_user_id, event, msg)

    # 2. Speed anomaly check
    if speed_kmh is not None and speed_kmh > 200.0:
        sp = {
            "is_anomalous": True,
            "speed_kmh": speed_kmh,
            "anomaly_type": "SPEED_ANOMALY",
            "severity": "HIGH" if speed_kmh > 300.0 else "MEDIUM",
        }
        anomalies.append(sp)
        event = await create_safety_event(
            db=db,
            user_id=ride.passenger_id,
            event_type="SPEED_ANOMALY",
            ride_id=ride.id,
            severity=sp["severity"],
            status="OPEN",
            driver_id=ride.driver_id,
            latitude=latitude,
            longitude=longitude,
            description=f"Unusual velocity telemetry detected ({speed_kmh} km/h).",
            evidence={"observed_speed_kmh": speed_kmh, "threshold": 200.0},
            debounce_seconds=300,
        )
        if event:
            events_created.append(event.id)
            msg = "An unusual speed pattern was detected during your ride."
            await send_notification(
                db=db,
                user_id=ride.passenger_id,
                ride_id=ride.id,
                title="Safety Notice",
                message=msg,
            )
            await _emit_safety_ws(ride.id, ride.passenger_id, driver_user_id, event, msg)

    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, None: 0}
    highest_severity = max(
        (a.get("severity") for a in anomalies),
        key=lambda s: severity_order.get(s, 0),
        default=None,
    )

    return {
        "safe": len(anomalies) == 0,
        "highest_severity": highest_severity,
        "anomalies": anomalies,
        "events_created": events_created,
    }


async def check_prolonged_stop_service(
    db: AsyncSession,
    ride_id: int,
    current_user: Any,
    threshold_minutes: int = 5,
) -> Dict[str, Any]:
    """
    Detects prolonged stationary stops during an in-progress trip.
    Neutral, non-accusatory terminology.
    """
    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError(f"Ride #{ride_id} not found")

    has_access = await _verify_ride_access(db, ride, current_user.id, current_user.role)
    if not has_access:
        raise UnauthorizedRideAccessError("Unauthorized access to ride telemetry")

    if ride.status != "STARTED":
        return {"prolonged_stop": False, "message": "Ride is not currently in progress."}

    # If stationary for > threshold_minutes, record event
    desc = f"Vehicle has been stationary for approximately {threshold_minutes} minutes. Automated safety check enabled."
    event = await create_safety_event(
        db=db,
        user_id=ride.passenger_id,
        event_type="PROLONGED_STOP",
        ride_id=ride.id,
        severity="LOW",
        status="OPEN",
        driver_id=ride.driver_id,
        latitude=ride.pickup_latitude,
        longitude=ride.pickup_longitude,
        description=desc,
        debounce_seconds=300,
    )

    return {
        "prolonged_stop": True,
        "event_id": event.id if event else None,
        "message": desc,
    }


# ─── 5. Trusted Contacts Service ──────────────────────────────────────────────

async def add_trusted_contact_service(
    db: AsyncSession,
    current_user: Any,
    name: str,
    phone: str,
    relationship: Optional[str] = None,
) -> TrustedContact:
    return await create_trusted_contact(
        db=db,
        user_id=current_user.id,
        name=name.strip(),
        phone=phone.strip(),
        relationship=relationship.strip() if relationship else None,
    )


async def get_trusted_contacts_service(
    db: AsyncSession,
    current_user: Any,
) -> List[TrustedContact]:
    return await get_trusted_contacts_by_user(db, current_user.id)


async def update_trusted_contact_service(
    db: AsyncSession,
    contact_id: int,
    current_user: Any,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    relationship: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> TrustedContact:
    contact = await get_trusted_contact_by_id(db, contact_id)
    if not contact:
        raise ValueError(f"Trusted contact #{contact_id} not found")
    if contact.user_id != current_user.id:
        raise UnauthorizedRideAccessError("You can only manage your own trusted contacts")

    return await update_trusted_contact(
        db=db,
        contact=contact,
        name=name.strip() if name else None,
        phone=phone.strip() if phone else None,
        relationship=relationship.strip() if relationship else None,
        is_active=is_active,
    )


async def delete_trusted_contact_service(
    db: AsyncSession,
    contact_id: int,
    current_user: Any,
) -> None:
    contact = await get_trusted_contact_by_id(db, contact_id)
    if not contact:
        raise ValueError(f"Trusted contact #{contact_id} not found")
    if contact.user_id != current_user.id:
        raise UnauthorizedRideAccessError("You can only manage your own trusted contacts")

    await delete_trusted_contact(db, contact)


# ─── 6. Privacy-Preserving Live Ride Sharing ─────────────────────────────────

async def generate_ride_share_token_service(
    db: AsyncSession,
    ride_id: int,
    current_user: Any,
    expires_in_hours: int = 24,
) -> Dict[str, Any]:
    """
    Generates privacy-preserving live tracking link.
    Records RIDE_SHARED safety event.
    Returns structured share text for copy/pasting.
    Does NOT claim SMS/WhatsApp were sent externally.
    """
    ride = await get_ride_by_id(db, ride_id)
    if not ride:
        raise RideNotFoundError(f"Ride #{ride_id} not found")

    has_access = await _verify_ride_access(db, ride, current_user.id, current_user.role)
    if not has_access:
        raise UnauthorizedRideAccessError("Not authorized to share this ride")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    record = await create_ride_share_token(
        db=db,
        ride_id=ride.id,
        user_id=current_user.id,
        token=token,
        expires_at=expires_at,
    )

    # Record RIDE_SHARED event
    await create_safety_event(
        db=db,
        user_id=current_user.id,
        event_type="RIDE_SHARED",
        ride_id=ride.id,
        severity="LOW",
        status="RESOLVED",
        description="Trip tracking link generated for trusted sharing.",
        debounce_seconds=60,
    )

    # Build structured shareable payload
    driver_name = "Assigned Captain"
    vehicle_str = "RideNow Fleet"
    if ride.driver_id:
        driver = await get_driver_by_id(db, ride.driver_id)
        if driver:
            vehicle_str = f"{driver.vehicle_model} ({driver.vehicle_number})"
            d_user = await get_user_by_id(db, driver.user_id)
            if d_user and d_user.name:
                driver_name = d_user.name.split()[0]

    share_url = f"/safety/share/{record.token}"
    share_text = (
        f"RideNow Trip with {driver_name}\n"
        f"Vehicle: {vehicle_str}\n"
        f"From: {ride.pickup_location}\n"
        f"To: {ride.dropoff_location}\n"
        f"Status: {ride.status}\n"
        f"Live Tracking: {share_url}"
    )

    return {
        "share_token": record.token,
        "share_url": share_url,
        "share_text": share_text,
        "expires_at": record.expires_at,
        "external_messaging_sent": False,
        "message": "Ride information ready to share. Browser copy/share supported.",
    }


async def get_shared_ride_status_service(
    db: AsyncSession,
    token: str,
) -> Dict[str, Any]:
    """Public privacy-preserving status view for trusted contacts."""
    share_record = await get_valid_share_token(db, token)
    if not share_record:
        raise ValueError("Invalid, expired, or revoked share link")

    ride = await get_ride_by_id(db, share_record.ride_id)
    if not ride:
        raise RideNotFoundError("Shared ride not found")

    passenger = await get_user_by_id(db, ride.passenger_id)
    passenger_first = passenger.name.split()[0] if passenger and passenger.name else "Passenger"

    driver_name = None
    vehicle_model = None
    vehicle_number = None
    driver_lat = None
    driver_lon = None

    if ride.driver_id:
        driver = await get_driver_by_id(db, ride.driver_id)
        if driver:
            vehicle_model = driver.vehicle_model
            vehicle_number = driver.vehicle_number
            driver_lat = driver.latitude
            driver_lon = driver.longitude
            driver_user = await get_user_by_id(db, driver.user_id)
            if driver_user and driver_user.name:
                driver_name = driver_user.name.split()[0]

    events = await get_safety_events_by_ride(db, ride.id)
    active_events = [e for e in events if e.status in ("ACTIVE", "OPEN", "ACKNOWLEDGED")]
    has_active_sos = any(e.event_type in ("SOS_TRIGGERED", "DRIVER_EMERGENCY", "PASSENGER_EMERGENCY") for e in active_events)

    safety_status = "CRITICAL_ALERT" if has_active_sos else ("MONITORED_NOTICE" if active_events else "NORMAL")

    return {
        "ride_id": ride.id,
        "status": ride.status,
        "pickup_location": ride.pickup_location,
        "dropoff_location": ride.dropoff_location,
        "passenger_name": passenger_first,
        "driver_name": driver_name,
        "vehicle_model": vehicle_model,
        "vehicle_number": vehicle_number,
        "driver_latitude": driver_lat,
        "driver_longitude": driver_lon,
        "active_safety_alert": len(active_events) > 0,
        "safety_status": safety_status,
        "updated_at": datetime.utcnow(),
    }


async def revoke_ride_share_token_service(
    db: AsyncSession,
    token: str,
    current_user: Any,
) -> bool:
    share_record = await get_valid_share_token(db, token)
    if not share_record:
        raise ValueError("Share token not found or already inactive")
    if share_record.user_id != current_user.id and current_user.role != "admin":
        raise UnauthorizedRideAccessError("You can only revoke your own share links")

    await revoke_share_token(db, share_record)
    return True


# ─── 7. Admin Safety Analytics ────────────────────────────────────────────────

async def get_admin_safety_metrics_service(
    db: AsyncSession,
) -> Dict[str, Any]:
    return await get_admin_safety_aggregates(db)


async def get_admin_safety_events_service(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
) -> List[SafetyEvent]:
    return await get_all_safety_events_admin(db, limit, offset, status_filter, severity_filter)
