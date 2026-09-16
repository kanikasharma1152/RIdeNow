from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    ride_id: int
    payment_method: str = "CASH"


class PaymentResponse(BaseModel):
    id: int
    ride_id: int
    passenger_id: int
    amount: Decimal
    status: str
    payment_method: str
    transaction_id: str | None
    created_at: datetime
    paid_at: datetime | None

    model_config = ConfigDict(from_attributes=True)