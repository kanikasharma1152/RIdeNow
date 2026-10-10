from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True
    )

    license_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    vehicle_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    vehicle_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )

    vehicle_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    is_online: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    latitude: Mapped[float | None] = mapped_column(
    Float,
    nullable=True
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    location_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )