from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    ride_id: int | None = None,
):
    if ride_id is not None:
        # Check if an identical notification was already recorded for this ride to prevent duplicates
        existing = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.ride_id == ride_id,
                Notification.title == title,
            )
        )
        found = existing.scalars().first()
        if found:
            return found

    notification = Notification(
        user_id=user_id,
        ride_id=ride_id,
        title=title,
        message=message,
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    return notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )

    return result.scalars().all()


async def mark_notification_read(
    db: AsyncSession,
    notification: Notification,
):
    notification.is_read = True

    await db.commit()
    await db.refresh(notification)

    return notification


async def mark_all_notifications_read(
    db: AsyncSession,
    user_id: int,
) -> int:
    from sqlalchemy import update
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount


async def get_notification_by_id(
    db: AsyncSession,
    notification_id: int,
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id
        )
    )

    return result.scalar_one_or_none()


async def get_unread_count(
    db: AsyncSession,
    user_id: int,
) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    return result.scalar_one()