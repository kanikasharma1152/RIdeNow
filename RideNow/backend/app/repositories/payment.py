from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


async def create_payment(
    db: AsyncSession,
    ride_id: int,
    passenger_id: int,
    amount,
    payment_method: str
):
    payment = Payment(
        ride_id=ride_id,
        passenger_id=passenger_id,
        amount=amount,
        payment_method=payment_method,
        status="PENDING"
    )

    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return payment


async def get_payment_by_ride(
    db: AsyncSession,
    ride_id: int
):
    result = await db.execute(
        select(Payment).where(Payment.ride_id == ride_id)
    )
    return result.scalar_one_or_none()


async def mark_payment_paid(
    db: AsyncSession,
    payment: Payment,
    transaction_id: str
):
    payment.status = "PAID"
    payment.transaction_id = transaction_id
    payment.paid_at = datetime.utcnow()

    await db.commit()
    await db.refresh(payment)

    return payment