from datetime import datetime
from decimal import Decimal

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
    driver_id: int | None
    pickup_location: str
    dropoff_location: str
    distance_km: float

    status: str
    fare: Decimal | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

    pickup_latitude: float | None
    pickup_longitude: float | None


class RideRejectionResponse(BaseModel):
    message: str
    ride_id: int
    next_driver_found: bool