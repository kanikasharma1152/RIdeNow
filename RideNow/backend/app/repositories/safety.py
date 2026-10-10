from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safety import SafetyEvent, TrustedContact, RideShareToken
from app.models.ride import Ride


# ─── Safety Events ─────────────────────────────────────────────────────────────

async def get_active_event_in_window(
    db: AsyncSession,
    ride_id: Optional[int],
    user_id: int,
    event_type: str,
    window_seconds: int = 180,
) -> Optional[SafetyEvent]:
    """
    Find if an event of the same type was already recorded recently for this ride/user,
    or is currently OPEN/ACTIVE, to prevent database spamming / duplicates.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    conditions = [
        SafetyEvent.event_type == event_type,
        or_(
            SafetyEvent.status.in_(["ACTIVE", "OPEN", "ACKNOWLEDGED"]),
            SafetyEvent.created_at >= cutoff,
        ),
    ]
    if ride_id is not None:
        conditions.append(SafetyEvent.ride_id == ride_id)
    else:
        conditions.append(SafetyEvent.user_id == user_id)

    stmt = select(SafetyEvent).where(and_(*conditions)).order_by(SafetyEvent.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_active_sos(
    db: AsyncSession,
    ride_id: Optional[int],
    user_id: Optional[int] = None,
) -> Optional[SafetyEvent]:
    """Check if an active SOS already exists for this ride or user."""
    conditions = [
        SafetyEvent.event_type.in_(["SOS_TRIGGERED", "DRIVER_EMERGENCY", "PASSENGER_EMERGENCY"]),
        SafetyEvent.status.in_(["ACTIVE", "OPEN", "ACKNOWLEDGED"]),
    ]
    if ride_id is not None:
        conditions.append(SafetyEvent.ride_id == ride_id)
    elif user_id is not None:
        conditions.append(SafetyEvent.user_id == user_id)
    else:
        return None

    stmt = select(SafetyEvent).where(and_(*conditions)).order_by(SafetyEvent.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_safety_event(
    db: AsyncSession,
    user_id: int,
    event_type: str,
    ride_id: Optional[int] = None,
    severity: str = "INFO",
    status: str = "OPEN",
    driver_id: Optional[int] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    description: Optional[str] = None,
    evidence: Optional[Any] = None,
    event_metadata: Optional[Any] = None,
    debounce_seconds: int = 180,
) -> SafetyEvent:
    """
    Creates a new SafetyEvent with deterministic deduplication.
    If an active event of the same type exists within debounce_seconds,
    returns the existing event instead of creating a duplicate.
    """
    if event_type in ("SOS_TRIGGERED", "DRIVER_EMERGENCY", "PASSENGER_EMERGENCY"):
        existing_sos = await get_active_sos(db, ride_id, user_id)
        if existing_sos:
            return existing_sos
    elif debounce_seconds > 0:
        existing = await get_active_event_in_window(db, ride_id, user_id, event_type, debounce_seconds)
        if existing:
            return existing

    event = SafetyEvent(
        ride_id=ride_id,
        user_id=user_id,
        driver_id=driver_id,
        event_type=event_type,
        severity=severity,
        status=status,
        latitude=latitude,
        longitude=longitude,
        description=description,
        detected_at=datetime.utcnow(),
        evidence=evidence,
        event_metadata=event_metadata,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_safety_event_by_id(
    db: AsyncSession,
    event_id: int,
) -> Optional[SafetyEvent]:
    stmt = select(SafetyEvent).where(SafetyEvent.id == event_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_safety_events_by_ride(
    db: AsyncSession,
    ride_id: int,
) -> List[SafetyEvent]:
    stmt = select(SafetyEvent).where(
        SafetyEvent.ride_id == ride_id
    ).order_by(SafetyEvent.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def acknowledge_safety_event(
    db: AsyncSession,
    event: SafetyEvent,
    user_id: Optional[int] = None,
) -> SafetyEvent:
    event.status = "ACKNOWLEDGED"
    event.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(event)
    return event


async def resolve_safety_event(
    db: AsyncSession,
    event: SafetyEvent,
    resolved_by: Optional[int] = None,
) -> SafetyEvent:
    event.status = "RESOLVED"
    event.resolved_at = datetime.utcnow()
    event.resolved_by = resolved_by
    event.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(event)
    return event


async def get_active_safety_events_for_user(
    db: AsyncSession,
    user_id: int,
) -> List[SafetyEvent]:
    """Retrieve all open/active safety events involving the user."""
    stmt = (
        select(SafetyEvent)
        .outerjoin(Ride, SafetyEvent.ride_id == Ride.id)
        .where(
            and_(
                SafetyEvent.status.in_(["ACTIVE", "OPEN", "ACKNOWLEDGED"]),
                or_(
                    SafetyEvent.user_id == user_id,
                    Ride.passenger_id == user_id,
                ),
            )
        )
        .order_by(SafetyEvent.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_user_safety_events(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> List[SafetyEvent]:
    """Retrieve safety events where user is the initiator, passenger, or driver."""
    stmt = (
        select(SafetyEvent)
        .outerjoin(Ride, SafetyEvent.ride_id == Ride.id)
        .where(
            or_(
                SafetyEvent.user_id == user_id,
                Ride.passenger_id == user_id,
            )
        )
        .order_by(SafetyEvent.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_all_safety_events_admin(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
) -> List[SafetyEvent]:
    """Admin operational list of safety events."""
    query = select(SafetyEvent)
    if status_filter:
        query = query.where(SafetyEvent.status == status_filter)
    if severity_filter:
        query = query.where(SafetyEvent.severity == severity_filter)
    query = query.order_by(SafetyEvent.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


# ─── Trusted Contacts ─────────────────────────────────────────────────────────

async def create_trusted_contact(
    db: AsyncSession,
    user_id: int,
    name: str,
    phone: str,
    relationship: Optional[str] = None,
) -> TrustedContact:
    contact = TrustedContact(
        user_id=user_id,
        name=name,
        phone=phone,
        relationship=relationship,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def get_trusted_contacts_by_user(
    db: AsyncSession,
    user_id: int,
) -> List[TrustedContact]:
    stmt = (
        select(TrustedContact)
        .where(
            TrustedContact.user_id == user_id,
            TrustedContact.is_active == True,
        )
        .order_by(TrustedContact.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_trusted_contact_by_id(
    db: AsyncSession,
    contact_id: int,
) -> Optional[TrustedContact]:
    stmt = select(TrustedContact).where(TrustedContact.id == contact_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_trusted_contact(
    db: AsyncSession,
    contact: TrustedContact,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    relationship: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> TrustedContact:
    if name is not None:
        contact.name = name
    if phone is not None:
        contact.phone = phone
    if relationship is not None:
        contact.relationship = relationship
    if is_active is not None:
        contact.is_active = is_active
    contact.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(contact)
    return contact


async def delete_trusted_contact(
    db: AsyncSession,
    contact: TrustedContact,
) -> None:
    await db.delete(contact)
    await db.commit()


# ─── Ride Share Tokens ────────────────────────────────────────────────────────

async def create_ride_share_token(
    db: AsyncSession,
    ride_id: int,
    user_id: int,
    token: str,
    expires_at: datetime,
) -> RideShareToken:
    share_record = RideShareToken(
        ride_id=ride_id,
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_revoked=False,
        created_at=datetime.utcnow(),
    )
    db.add(share_record)
    await db.commit()
    await db.refresh(share_record)
    return share_record


async def get_valid_share_token(
    db: AsyncSession,
    token: str,
) -> Optional[RideShareToken]:
    stmt = select(RideShareToken).where(
        RideShareToken.token == token,
        RideShareToken.is_revoked == False,
        RideShareToken.expires_at > datetime.utcnow(),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_share_token(
    db: AsyncSession,
    share_record: RideShareToken,
) -> RideShareToken:
    share_record.is_revoked = True
    await db.commit()
    await db.refresh(share_record)
    return share_record


# ─── Admin Aggregates ─────────────────────────────────────────────────────────

async def get_admin_safety_aggregates(
    db: AsyncSession,
) -> Dict[str, Any]:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Active SOS
    active_sos_res = await db.execute(
        select(func.count(SafetyEvent.id)).where(
            SafetyEvent.event_type.in_(["SOS_TRIGGERED", "DRIVER_EMERGENCY", "PASSENGER_EMERGENCY"]),
            SafetyEvent.status.in_(["ACTIVE", "OPEN", "ACKNOWLEDGED"]),
        )
    )
    active_sos = active_sos_res.scalar() or 0

    # Events today
    events_today_res = await db.execute(
        select(func.count(SafetyEvent.id)).where(
            SafetyEvent.created_at >= today_start
        )
    )
    events_today = events_today_res.scalar() or 0

    # Route deviations count
    deviations_res = await db.execute(
        select(func.count(SafetyEvent.id)).where(
            SafetyEvent.event_type == "ROUTE_DEVIATION"
        )
    )
    deviations = deviations_res.scalar() or 0

    # Speed anomalies count
    speed_res = await db.execute(
        select(func.count(SafetyEvent.id)).where(
            SafetyEvent.event_type == "SPEED_ANOMALY"
        )
    )
    speed_count = speed_res.scalar() or 0

    # Long stops count
    stops_res = await db.execute(
        select(func.count(SafetyEvent.id)).where(
            SafetyEvent.event_type.in_(["LONG_STOP", "PROLONGED_STOP"])
        )
    )
    stops_count = stops_res.scalar() or 0

    # Unresolved critical events
    crit_res = await db.execute(
        select(func.count(SafetyEvent.id)).where(
            SafetyEvent.severity.in_(["HIGH", "CRITICAL"]),
            SafetyEvent.status.in_(["ACTIVE", "OPEN", "ACKNOWLEDGED"]),
        )
    )
    unresolved_critical = crit_res.scalar() or 0

    # Recent critical events
    recent_crit_stmt = (
        select(SafetyEvent)
        .where(SafetyEvent.severity.in_(["HIGH", "CRITICAL"]))
        .order_by(SafetyEvent.created_at.desc())
        .limit(10)
    )
    recent_res = await db.execute(recent_crit_stmt)
    recent_critical = list(recent_res.scalars().all())

    return {
        "active_sos_count": int(active_sos),
        "events_today_count": int(events_today),
        "route_deviations_count": int(deviations),
        "speed_anomalies_count": int(speed_count),
        "long_stops_count": int(stops_count),
        "unresolved_critical_count": int(unresolved_critical),
        "recent_critical_events": recent_critical,
    }
