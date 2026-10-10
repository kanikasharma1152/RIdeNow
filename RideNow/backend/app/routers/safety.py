"""
RideNow Safety Router — Phase 13
=================================
REST API endpoints for:
- Operational Safety Center state & capability flags
- Emergency SOS triggering (Passenger & Driver)
- Active safety events & personal safety history
- Safety concern & anomaly reporting
- Trusted contacts management (/safety/trusted-contacts and /safety/contacts)
- Privacy-preserving live ride sharing
- Real-time route deviation & prolonged stop telemetry
- Admin safety intelligence & command center
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.user import get_current_user, require_role
from app.core.exceptions import (
    RideNowError,
    RideNotFoundError,
    UnauthorizedRideAccessError,
    InvalidRideStateError,
)

from app.schemas.safety import (
    SafetyCenterResponse,
    SafetyEventResponse,
    SafetyEventCreate,
    SOSTriggerRequest,
    SOSTriggerResponse,
    DriverSOSRequest,
    TelemetryCheckRequest,
    TelemetryCheckResponse,
    TrustedContactCreate,
    TrustedContactUpdate,
    TrustedContactResponse,
    RideShareCreateResponse,
    SharedRideStatusResponse,
    AdminSafetyMetricsResponse,
)

from app.services.safety import (
    get_safety_center_service,
    trigger_sos,
    trigger_driver_sos_service,
    create_safety_event_service,
    acknowledge_safety_event_service,
    resolve_safety_event_service,
    get_ride_safety_events_service,
    get_user_safety_history_service,
    evaluate_ride_telemetry,
    check_prolonged_stop_service,
    add_trusted_contact_service,
    get_trusted_contacts_service,
    update_trusted_contact_service,
    delete_trusted_contact_service,
    generate_ride_share_token_service,
    get_shared_ride_status_service,
    revoke_ride_share_token_service,
    get_admin_safety_metrics_service,
    get_admin_safety_events_service,
)
from app.repositories.safety import get_active_safety_events_for_user

router = APIRouter(prefix="/safety", tags=["Safety & Trust"])


def _handle_error(e: Exception):
    if isinstance(e, RideNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    if isinstance(e, UnauthorizedRideAccessError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    if isinstance(e, InvalidRideStateError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    if isinstance(e, RideNowError):
        raise HTTPException(status_code=e.status_code, detail=e.message)
    if isinstance(e, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")


# ─── 1. Safety Center Overview ───────────────────────────────────────────────

@router.get(
    "/center",
    response_model=SafetyCenterResponse,
    summary="Passenger / Driver Safety Command Center",
    description="Returns active ride state, driver telemetry, trusted contacts, and honest platform capability flags.",
)
async def get_safety_center(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_safety_center_service(db, current_user)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/active",
    response_model=List[SafetyEventResponse],
    summary="Get Active Safety Events",
    description="Returns all active, uncompleted safety events involving the authenticated user.",
)
async def get_active_safety_events_endpoint(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_active_safety_events_for_user(db, current_user.id)
    except Exception as e:
        _handle_error(e)


# ─── 2. Universal SOS & Driver Emergency ─────────────────────────────────────

@router.post(
    "/sos",
    response_model=SOSTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Universal SOS",
    description="Initiates internal emergency safety workflow. Strictly states limitation on direct external calling.",
)
async def trigger_universal_sos_api(
    req: SOSTriggerRequest = SOSTriggerRequest(),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await trigger_sos(
            db=db,
            current_user=current_user,
            ride_id=req.ride_id,
            latitude=req.latitude,
            longitude=req.longitude,
            note=req.note,
        )
    except Exception as e:
        _handle_error(e)


@router.post(
    "/rides/{ride_id}/sos",
    response_model=SOSTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Ride SOS",
    description="Backward-compatible ride-specific SOS endpoint.",
)
async def trigger_ride_sos(
    ride_id: int,
    req: SOSTriggerRequest = SOSTriggerRequest(),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await trigger_sos(
            db=db,
            current_user=current_user,
            ride_id=ride_id,
            latitude=req.latitude,
            longitude=req.longitude,
            note=req.note,
        )
    except Exception as e:
        _handle_error(e)


@router.post(
    "/driver/sos",
    response_model=SOSTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Driver Emergency SOS",
    description="Driver-initiated emergency safety workflow.",
)
async def trigger_driver_sos(
    req: DriverSOSRequest = DriverSOSRequest(),
    current_user=Depends(require_role("driver")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await trigger_driver_sos_service(
            db=db,
            current_user=current_user,
            latitude=req.latitude,
            longitude=req.longitude,
            note=req.note,
            ride_id=req.ride_id,
        )
    except Exception as e:
        _handle_error(e)


# ─── 3. Safety Concern & Event Reporting ──────────────────────────────────────

@router.post(
    "/events",
    response_model=SafetyEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report Safety Concern",
    description="Report a structured safety concern (wrong route, vehicle issue, driver behavior).",
)
async def report_safety_concern(
    req: SafetyEventCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_safety_event_service(
            db=db,
            current_user=current_user,
            ride_id=req.ride_id,
            event_type=req.event_type,
            severity=req.severity,
            description=req.description,
            latitude=req.latitude,
            longitude=req.longitude,
            metadata=req.metadata,
        )
    except Exception as e:
        _handle_error(e)


@router.post(
    "/events/{event_id}/acknowledge",
    response_model=SafetyEventResponse,
    summary="Acknowledge Safety Event",
    description="Marks an open safety event as ACKNOWLEDGED.",
)
async def acknowledge_safety_event_api(
    event_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await acknowledge_safety_event_service(db, event_id, current_user)
    except Exception as e:
        _handle_error(e)


@router.post(
    "/events/{event_id}/resolve",
    response_model=SafetyEventResponse,
    summary="Resolve Safety Event",
    description="Marks an active/acknowledged safety event as RESOLVED.",
)
async def resolve_safety_event_post_api(
    event_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await resolve_safety_event_service(db, event_id, current_user)
    except Exception as e:
        _handle_error(e)


@router.patch(
    "/events/{event_id}/resolve",
    response_model=SafetyEventResponse,
    summary="Resolve Safety Event (PATCH)",
    description="Backward-compatible resolve endpoint.",
)
async def resolve_safety_event_patch_api(
    event_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await resolve_safety_event_service(db, event_id, current_user)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/rides/{ride_id}/events",
    response_model=List[SafetyEventResponse],
    summary="Get Ride Safety Events",
    description="Returns all recorded safety events for a given ride (participants only).",
)
async def get_ride_safety_events(
    ride_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_ride_safety_events_service(db, ride_id, current_user)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/history",
    response_model=List[SafetyEventResponse],
    summary="Get Personal Safety History",
    description="Returns safety history strictly isolated to the authenticated user.",
)
async def get_user_safety_history(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_user_safety_history_service(db, current_user)
    except Exception as e:
        _handle_error(e)


# ─── 4. Telemetry, Route Deviation & Prolonged Stops ──────────────────────────

@router.post(
    "/rides/{ride_id}/telemetry",
    response_model=TelemetryCheckResponse,
    summary="Submit Ride GPS Telemetry",
    description="Submits telemetry and evaluates for route deviations and velocity anomalies.",
)
async def check_telemetry(
    ride_id: int,
    req: TelemetryCheckRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await evaluate_ride_telemetry(
            db=db,
            ride_id=ride_id,
            current_user=current_user,
            latitude=req.latitude,
            longitude=req.longitude,
            speed_kmh=req.speed_kmh,
            route_waypoints=req.route_waypoints,
        )
    except Exception as e:
        _handle_error(e)


@router.post(
    "/rides/{ride_id}/prolonged-stop",
    summary="Check Prolonged Stop",
    description="Checks if in-progress ride vehicle has been stationary beyond threshold.",
)
async def check_prolonged_stop_api(
    ride_id: int,
    threshold_minutes: int = Query(5, ge=1, le=30),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await check_prolonged_stop_service(db, ride_id, current_user, threshold_minutes)
    except Exception as e:
        _handle_error(e)


# ─── 5. Trusted Contacts (dual-routed: /trusted-contacts and /contacts) ──────

@router.get(
    "/trusted-contacts",
    response_model=List[TrustedContactResponse],
    summary="List Trusted Contacts",
    description="Returns active trusted emergency contacts for the authenticated user.",
)
@router.get(
    "/contacts",
    response_model=List[TrustedContactResponse],
    include_in_schema=False,
)
async def list_trusted_contacts(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_trusted_contacts_service(db, current_user)
    except Exception as e:
        _handle_error(e)


@router.post(
    "/trusted-contacts",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Trusted Contact",
    description="Adds an emergency contact for the user.",
)
@router.post(
    "/contacts",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def add_trusted_contact(
    req: TrustedContactCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await add_trusted_contact_service(
            db=db,
            current_user=current_user,
            name=req.name,
            phone=req.phone,
            relationship=req.relationship,
        )
    except Exception as e:
        _handle_error(e)


@router.patch(
    "/trusted-contacts/{contact_id}",
    response_model=TrustedContactResponse,
    summary="Update Trusted Contact",
    description="Updates a user's trusted emergency contact.",
)
@router.patch(
    "/contacts/{contact_id}",
    response_model=TrustedContactResponse,
    include_in_schema=False,
)
async def update_trusted_contact_api(
    contact_id: int,
    req: TrustedContactUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_trusted_contact_service(
            db=db,
            contact_id=contact_id,
            current_user=current_user,
            name=req.name,
            phone=req.phone,
            relationship=req.relationship,
            is_active=req.is_active,
        )
    except Exception as e:
        _handle_error(e)


@router.delete(
    "/trusted-contacts/{contact_id}",
    summary="Delete Trusted Contact",
    description="Removes a trusted contact for the user.",
)
@router.delete(
    "/contacts/{contact_id}",
    include_in_schema=False,
)
async def delete_trusted_contact_api(
    contact_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_trusted_contact_service(db, contact_id, current_user)
        return {"success": True, "message": "Trusted contact removed"}
    except Exception as e:
        _handle_error(e)


# ─── 6. Live Ride Safety Sharing ─────────────────────────────────────────────

@router.post(
    "/rides/{ride_id}/share",
    response_model=RideShareCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Live Ride Share Link",
    description="Creates an expiring, secure token and copyable trip information payload.",
)
async def create_share_link(
    ride_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await generate_ride_share_token_service(db, ride_id, current_user)
    except Exception as e:
        _handle_error(e)


@router.delete(
    "/rides/{ride_id}/share/{token}",
    summary="Revoke Live Ride Share Link",
    description="Revokes a previously shared ride tracking token.",
)
async def revoke_share_link(
    ride_id: int,
    token: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await revoke_ride_share_token_service(db, token, current_user)
        return {"success": True, "message": "Share link revoked"}
    except Exception as e:
        _handle_error(e)


@router.get(
    "/share/{token}",
    response_model=SharedRideStatusResponse,
    summary="Public Shared Ride Status",
    description="Public, privacy-preserving endpoint for trusted contacts to monitor trip status.",
)
async def view_shared_ride(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_shared_ride_status_service(db, token)
    except Exception as e:
        _handle_error(e)


# ─── 7. Admin Safety Command Center ──────────────────────────────────────────

@router.get(
    "/admin/metrics",
    response_model=AdminSafetyMetricsResponse,
    summary="Admin Safety Metrics",
    description="Aggregate safety metrics and active emergency counts for the platform.",
)
async def get_admin_safety_metrics(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_admin_safety_metrics_service(db)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/admin/events",
    response_model=List[SafetyEventResponse],
    summary="Admin Safety Events Feed",
    description="Operational list of safety events with status/severity filtering.",
)
async def get_admin_safety_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity_filter: Optional[str] = Query(None, alias="severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_admin_safety_events_service(
            db=db,
            limit=limit,
            offset=offset,
            status_filter=status_filter,
            severity_filter=severity_filter,
        )
    except Exception as e:
        _handle_error(e)
