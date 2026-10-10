from datetime import datetime

from sqlalchemy import (
    Float,
    String,
    ForeignKey,
    Numeric,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
from app.database import Base


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    passenger_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id"),
        nullable=True,
        index=True
    )

    pickup_location: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    pickup_latitude: Mapped[float | None] = mapped_column(
    Float,
    nullable=True
    )

    pickup_longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    dropoff_location: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    distance_km: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="REQUESTED",
        nullable=False,
        index=True
    )

    fare: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )