from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.notification import NotificationResponse
from app.services.notification import (
    get_notifications,
    read_notification,
    get_notification_unread_count,
)
from app.routers.user import get_current_user


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="Get notifications",
    description="Returns all notifications for the authenticated user, newest first.",
)
async def get_my_notifications(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_notifications(
        db=db,
        user_id=current_user.id,
    )


@router.get(
    "/unread-count",
    summary="Get unread notification count",
    description="Returns the number of unread notifications for the authenticated user.",
)
async def get_my_unread_count(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await get_notification_unread_count(
        db=db,
        user_id=current_user.id,
    )
    return {"count": count}


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read",
    description="Marks a single notification as read. Only the notification's owner can do this.",
)
async def mark_as_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await read_notification(
            db=db,
            user_id=current_user.id,
            notification_id=notification_id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch(
    "/read-all",
    summary="Mark all notifications as read",
    description="Marks all unread notifications for the authenticated user as read.",
)
async def mark_all_as_read(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.notification import mark_all_read
    count = await mark_all_read(db=db, user_id=current_user.id)
    return {"message": "All notifications marked as read", "updated_count": count}