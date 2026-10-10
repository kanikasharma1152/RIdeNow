from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RideCreate(BaseModel):
    pickup_location: str
    dropoff_location: str
    distance_km: float | None = Field(default=None, gt=0)
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None


class RideResponse(BaseModel):
    id: int
    passenger_id: int
    driver_id: Optional[int] = None
    pickup_location: str
    dropoff_location: str
    distance_km: float

    status: str
    fare: Optional[Decimal] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    pickup_latitude: Optional[float] = None
    pickup_longitude: Optional[float] = None

    # Enriched driver info populated by service layer when driver is assigned
    driver_info: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RideRejectionResponse(BaseModel):
    message: str
    ride_id: int
    next_driver_found: bool