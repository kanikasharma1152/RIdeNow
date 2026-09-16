from pydantic import BaseModel, ConfigDict

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class DriverCreate(BaseModel):
    license_number: str
    vehicle_type: str
    vehicle_number: str
    vehicle_model: str


class DriverResponse(BaseModel):
    id: int
    user_id: int
    license_number: str
    vehicle_type: str
    vehicle_number: str
    vehicle_model: str
    is_online: bool
    is_available: bool

    model_config = ConfigDict(from_attributes=True)


class DriverLocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DriverLocationResponse(BaseModel):
    driver_id: int
    latitude: float
    longitude: float
    location_updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriverUpdate(BaseModel):
    """Fields a driver may update about their profile."""
    vehicle_type: str | None = None
    vehicle_number: str | None = None
    vehicle_model: str | None = None
    license_number: str | None = None