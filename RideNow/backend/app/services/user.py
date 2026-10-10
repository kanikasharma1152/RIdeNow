from sqlalchemy.ext.asyncio import AsyncSession
from pwdlib import PasswordHash

from app.repositories.user import (
    get_user_by_email,
    get_user_by_phone,
    create_user,
    update_user,
)

from app.core.security import create_access_token
from app.core.exceptions import DuplicateResourceError


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password
    )


async def register_user(
    db: AsyncSession,
    name: str,
    email: str,
    phone: str,
    password: str,
    role: str = "passenger"
):
    existing_user = await get_user_by_email(
        db,
        email
    )

    if existing_user:
        raise ValueError("Email already registered")

    if phone:
        existing_phone = await get_user_by_phone(
            db,
            phone
        )
        if existing_phone:
            raise ValueError("Phone number already registered")

    password_hash_value = hash_password(password)

    user = await create_user(
        db=db,
        name=name,
        email=email,
        phone=phone,
        password_hash=password_hash_value,
        role=role
    )

    if role == "driver":
        from app.services.driver import get_or_create_driver
        await get_or_create_driver(db, user.id)

    return user


async def login_user(
    db: AsyncSession,
    email: str,
    password: str
):
    user = await get_user_by_email(
        db,
        email
    )

    if not user:
        raise ValueError("Invalid email or password")

    if not verify_password(
        password,
        user.password_hash
    ):
        raise ValueError("Invalid email or password")

    if not user.is_active:
        raise ValueError("User account is inactive")

    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role
    })

    return access_token


async def update_user_profile(
    db: AsyncSession,
    user,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
):
    """Update user profile fields with uniqueness checks."""
    if email is not None and email != user.email:
        existing = await get_user_by_email(db, email)
        if existing:
            raise DuplicateResourceError("Email is already in use")

    if phone is not None and phone != user.phone:
        existing = await get_user_by_phone(db, phone)
        if existing:
            raise DuplicateResourceError("Phone number is already in use")

    return await update_user(
        db=db,
        user=user,
        name=name,
        phone=phone,
        email=email,
    )