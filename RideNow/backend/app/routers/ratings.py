from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ratings import RatingCreate, RatingResponse
from app.services.ratings import (
    submit_rating,
    get_driver_rating_list
)
from app.routers.user import require_passenger, require_driver
from app.repositories.driver import get_driver_by_user_id


router = APIRouter(
    prefix="/ratings",
    tags=["Ratings"]
)


@router.post(
    "",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_rating_api(
    rating_data: RatingCreate,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await submit_rating(
            db=db,
            passenger_id=current_user.id,
            ride_id=rating_data.ride_id,
            rating=rating_data.rating,
            comment=rating_data.comment,
            feedback=rating_data.feedback,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/ride/{ride_id}",
    response_model=RatingResponse | None,
)
async def get_ride_rating_api(
    ride_id: int,
    current_user=Depends(require_passenger),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.ratings import get_rating_by_ride
    rating = await get_rating_by_ride(db, ride_id)
    if not rating:
        return None
    if rating.passenger_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view ratings for your own rides"
        )
    return rating


@router.get(
    "/driver/{driver_id}",
    response_model=list[RatingResponse]
)
async def driver_ratings_api(
    driver_id: int,
    current_user=Depends(require_driver),
    db: AsyncSession = Depends(get_db)
):
    driver = await get_driver_by_user_id(db, current_user.id)
    if not driver or driver.id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own ratings"
        )
    return await get_driver_rating_list(
        db=db,
        driver_id=driver_id
    )