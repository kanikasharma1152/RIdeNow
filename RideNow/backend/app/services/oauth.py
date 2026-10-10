"""
RideNow — Google OAuth Authentication Service
=============================================
Provides production-grade Google OAuth token verification and account linking.
Requirements:
1. Validates ID tokens via Google's OAuth2 tokeninfo service or google-auth.
2. Checks client_id matching if GOOGLE_CLIENT_ID is configured.
3. Automatically links existing accounts with matching email (no duplicates).
4. Creates new user with role and avatar if no account exists.
5. Returns standard RideNow JWT bearer token for unified auth.
6. Graceful error handling if credentials or token are invalid.
"""

import logging
from typing import Dict, Any, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.repositories.user import (
    get_user_by_email,
    get_user_by_oauth_sub,
    create_oauth_user,
    link_google_oauth,
)

logger = logging.getLogger(__name__)

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google_credential(credential: str) -> Dict[str, Any]:
    """
    Verifies a Google ID token by calling Google's secure tokeninfo endpoint.
    Returns token claims dictionary or raises AuthenticationError.
    """
    if not credential:
        raise AuthenticationError("Missing Google OAuth credential token.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": credential})

        if resp.status_code != 200:
            logger.warning(f"Google tokeninfo error: {resp.status_code} - {resp.text}")
            raise AuthenticationError("Invalid or expired Google OAuth credential token.")

        data = resp.json()

        # If GOOGLE_CLIENT_ID is configured, verify the audience matches
        client_id = settings.GOOGLE_CLIENT_ID
        if client_id and not client_id.startswith("your-"):
            aud = data.get("aud")
            if aud != client_id:
                logger.error(f"Google token audience mismatch: expected {client_id}, got {aud}")
                raise AuthenticationError("Google client ID mismatch.")

        # Ensure required claims exist
        sub = data.get("sub")
        email = data.get("email")
        if not sub or not email:
            raise AuthenticationError("Google token missing required subject or email claims.")

        return data

    except AuthenticationError:
        raise
    except Exception as exc:
        logger.error(f"Failed to communicate with Google OAuth service: {exc}")
        raise AuthenticationError(f"Google OAuth verification failed: {exc}")


async def authenticate_google_user(
    db: AsyncSession,
    credential: str,
    requested_role: str = "passenger",
) -> Tuple[User, str]:
    """
    Completes Google authentication:
    1. Verifies token
    2. Finds or creates/links user
    3. Issues RideNow access JWT
    """
    claims = await verify_google_credential(credential)

    sub = str(claims["sub"])
    email = str(claims["email"]).lower().strip()
    name = str(claims.get("name") or email.split("@")[0])
    avatar_url = claims.get("picture")

    # 1. Check if user already exists by Google sub
    user = await get_user_by_oauth_sub(db, oauth_sub=sub, provider="google")

    if not user:
        # 2. Check if an account exists with the same email (from password registration)
        existing_email_user = await get_user_by_email(db, email=email)
        if existing_email_user:
            logger.info(f"Linking existing user {existing_email_user.id} ({email}) to Google OAuth sub {sub}")
            user = await link_google_oauth(
                db=db,
                user=existing_email_user,
                oauth_sub=sub,
                avatar_url=avatar_url,
            )
        else:
            # 3. Create brand-new user
            logger.info(f"Creating new Google OAuth user for {email} with role {requested_role}")
            user = await create_oauth_user(
                db=db,
                name=name,
                email=email,
                oauth_sub=sub,
                provider="google",
                avatar_url=avatar_url,
                role=requested_role,
            )

    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.")

    # Generate standard application JWT
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
            "email": user.email,
        }
    )

    return user, access_token
