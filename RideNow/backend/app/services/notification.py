from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.notification import (
    create_notification,
    get_user_notifications,
    get_notification_by_id,
    mark_notification_read,
    get_unread_count,
)


async def send_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    ride_id: int | None = None,
):
    return await create_notification(
        db=db,
        user_id=user_id,
        title=title,
        message=message,
        ride_id=ride_id,
    )


async def get_notifications(
    db: AsyncSession,
    user_id: int,
):
    return await get_user_notifications(
        db=db,
        user_id=user_id,
    )


async def read_notification(
    db: AsyncSession,
    user_id: int,
    notification_id: int,
):
    notification = await get_notification_by_id(
        db=db,
        notification_id=notification_id,
    )

    if not notification:
        raise ValueError("Notification not found")

    if notification.user_id != user_id:
        raise ValueError("You cannot access this notification")

    if not notification.is_read:
        return await mark_notification_read(
            db=db,
            notification=notification,
        )

    return notification


async def mark_all_read(
    db: AsyncSession,
    user_id: int,
) -> int:
    from app.repositories.notification import mark_all_notifications_read
    return await mark_all_notifications_read(db=db, user_id=user_id)


async def get_notification_unread_count(
    db: AsyncSession,
    user_id: int,
) -> int:
    return await get_unread_count(
        db=db,
        user_id=user_id,
    )