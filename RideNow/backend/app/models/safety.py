from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    Float,
    DateTime,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    ride_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rides.id"),
        nullable=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    driver_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("drivers.id"),
        nullable=True,
        index=True
    )

    # Event types: SOS_TRIGGERED, SAFETY_CONCERN, ROUTE_DEVIATION, PROLONGED_STOP, PICKUP_MISMATCH, DESTINATION_MISMATCH, RIDE_INTERRUPTED, DRIVER_EMERGENCY, PASSENGER_EMERGENCY, RIDE_SHARED, SAFETY_CHECK, MANUAL_SAFETY_REPORT
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    # Severity: INFO, LOW, MEDIUM, HIGH, CRITICAL
    severity: Mapped[str] = mapped_column(
        String(20),
        default="INFO",
        nullable=False
    )

    # Status: OPEN, ACKNOWLEDGED, RESOLVED, CANCELLED, ACTIVE, DISMISSED
    status: Mapped[str] = mapped_column(
        String(20),
        default="OPEN",
        nullable=False
    )

    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )

    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    resolved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    # Evidence details, e.g. observed_speed, distance_deviated, time_stationary
    evidence: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True
    )

    # Event metadata (note: attribute is event_metadata to avoid collision with Declarative Base.metadata)
    event_metadata: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    relationship: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class RideShareToken(Base):
    __tablename__ = "ride_share_tokens"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    ride_id: Mapped[int] = mapped_column(
        ForeignKey("rides.id"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
