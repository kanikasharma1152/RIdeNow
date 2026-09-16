from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.revoked_token import RevokedToken


async def revoke_token(
    db: AsyncSession,
    token_jti: str,
    user_id: int,
    expires_at: datetime,
) -> RevokedToken:
    entry = RevokedToken(
        token_jti=token_jti,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def is_token_revoked(
    db: AsyncSession,
    token_jti: str,
) -> bool:
    result = await db.execute(
        select(RevokedToken).where(
            RevokedToken.token_jti == token_jti
        )
    )
    return result.scalar_one_or_none() is not None
