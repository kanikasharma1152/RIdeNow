from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RatingCreate(BaseModel):
    ride_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)
    feedback: str | None = Field(default=None, max_length=500)


class RatingResponse(BaseModel):
    id: int
    ride_id: int
    passenger_id: int
    driver_id: int
    rating: int
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)