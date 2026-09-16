from decimal import Decimal
from pydantic import BaseModel


class EarningsResponse(BaseModel):
    total_rides: int
    cancelled_rides: int = 0
    total_earnings: Decimal
    today_earnings: Decimal
    week_earnings: Decimal
    month_earnings: Decimal
    average_fare: Decimal
