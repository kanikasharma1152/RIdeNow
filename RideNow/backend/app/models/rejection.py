from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RideDriverRejection(Base):
    """
    Tracks which drivers have rejected which rides.
    Used to prevent re-assigning the same driver to a rejected ride.
    """
    __tablename__ = "ride_driver_rejections"
    __table_args__ = (
        UniqueConstraint("ride_id", "driver_id", name="uq_ride_driver_rejection"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    ride_id: Mapped[int] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )
