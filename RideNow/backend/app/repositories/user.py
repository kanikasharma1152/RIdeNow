from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(
    db: AsyncSession,
    email: str
):
    result = await db.execute(
        select(User).where(User.email == email)
    )

    return result.scalar_one_or_none()


async def get_user_by_id(
    db: AsyncSession,
    user_id: int
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    return result.scalar_one_or_none()


async def get_user_by_phone(
    db: AsyncSession,
    phone: str,
):
    result = await db.execute(
        select(User).where(User.phone == phone)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    name: str,
    email: str,
    phone: str,
    password_hash: str,
    role: str = "passenger"
):
    user = User(
        name=name,
        email=email,
        phone=phone,
        password_hash=password_hash,
        role=role
    )

    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


async def update_user(
    db: AsyncSession,
    user: User,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> User:
    if name is not None:
        user.name = name
    if phone is not None:
        user.phone = phone
    if email is not None:
        user.email = email

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_oauth_sub(
    db: AsyncSession,
    oauth_sub: str,
    provider: str = "google",
) -> User | None:
    result = await db.execute(
        select(User).where(
            User.oauth_sub == oauth_sub,
            User.oauth_provider == provider,
        )
    )
    return result.scalar_one_or_none()


async def create_oauth_user(
    db: AsyncSession,
    name: str,
    email: str,
    oauth_sub: str,
    provider: str = "google",
    avatar_url: str | None = None,
    role: str = "passenger",
) -> User:
    user = User(
        name=name,
        email=email,
        phone=None,
        password_hash=None,
        role=role,
        oauth_provider=provider,
        oauth_sub=oauth_sub,
        avatar_url=avatar_url,
        preferred_language="en",
        onboarding_complete=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def link_google_oauth(
    db: AsyncSession,
    user: User,
    oauth_sub: str,
    avatar_url: str | None = None,
) -> User:
    user.oauth_provider = "google"
    user.oauth_sub = oauth_sub
    if avatar_url and not user.avatar_url:
        user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return user
