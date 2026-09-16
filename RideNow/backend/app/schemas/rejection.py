from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RejectionResponse(BaseModel):
    id: int
    ride_id: int
    driver_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
