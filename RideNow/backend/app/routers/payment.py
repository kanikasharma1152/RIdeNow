from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment import (
    create_ride_payment,
    complete_payment
)
from app.routers.user import require_passenger


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_payment_api(
    payment_data: PaymentCreate,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await create_ride_payment(
            db=db,
            passenger_id=current_user.id,
            ride_id=payment_data.ride_id,
            payment_method=payment_data.payment_method
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/{ride_id}/pay",
    response_model=PaymentResponse
)
async def pay_for_ride_api(
    ride_id: int,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await complete_payment(
            db=db,
            passenger_id=current_user.id,
            ride_id=ride_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )