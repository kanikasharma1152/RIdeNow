import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.payment import (
    create_payment,
    get_payment_by_ride,
    mark_payment_paid
)
from app.repositories.ride import get_ride_by_id


async def create_ride_payment(
    db: AsyncSession,
    passenger_id: int,
    ride_id: int,
    payment_method: str
):
    ride = await get_ride_by_id(db, ride_id)

    if not ride:
        raise ValueError("Ride not found")

    if ride.passenger_id != passenger_id:
        raise ValueError("You can only pay for your own ride")

    if ride.status != "COMPLETED":
        raise ValueError("Payment is allowed only for completed rides")

    if ride.fare is None:
        raise ValueError("Ride fare is not available")

    existing_payment = await get_payment_by_ride(db, ride_id)

    if existing_payment:
        return existing_payment

    return await create_payment(
        db=db,
        ride_id=ride_id,
        passenger_id=passenger_id,
        amount=ride.fare,
        payment_method=payment_method
    )


async def complete_payment(
    db: AsyncSession,
    passenger_id: int,
    ride_id: int
):
    payment = await get_payment_by_ride(db, ride_id)

    if not payment:
        raise ValueError("Payment not found")

    if payment.passenger_id != passenger_id:
        raise ValueError("You can only pay for your own ride")

    if payment.status == "PAID":
        return payment

    transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    return await mark_payment_paid(
        db=db,
        payment=payment,
        transaction_id=transaction_id
    )