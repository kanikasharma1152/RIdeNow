from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db

from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
    GoogleOAuthRequest,
)

from app.services.user import (
    register_user,
    login_user,
    update_user_profile,
)
from app.services.oauth import authenticate_google_user
from app.core.config import settings

from typing import Callable

from app.repositories.user import get_user_by_id
from app.repositories.revoked_token import revoke_token, is_token_revoked
from app.core.security import decode_access_token
from app.core.exceptions import (
    AuthenticationError,
    TokenRevokedError,
    DuplicateResourceError,
    RideNowError,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/users/login"
)


# ==========================================
# GET CURRENT USER (dependency)
# ==========================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Check token revocation
    jti = payload.get("jti")
    if jti:
        if await is_token_revoked(db, jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = await get_user_by_id(db, int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    return user


async def require_passenger(current_user=Depends(get_current_user)):
    if current_user.role != "passenger":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only passengers can perform this action",
        )
    return current_user


async def require_driver(current_user=Depends(get_current_user)):
    if current_user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can perform this action",
        )
    return current_user


def require_role(required_role: str) -> Callable:
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. {required_role} role required.",
            )
        return current_user
    return role_checker


# ==========================================
# REGISTER
# ==========================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new passenger or driver user account.",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await register_user(
            db=db,
            name=user_data.name,
            email=user_data.email,
            phone=user_data.phone,
            password=user_data.password,
            role=user_data.role,
        )

        return user

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except IntegrityError as e:
        # Duplicate phone or email constraint violation from PostgreSQL
        err_str = str(e.orig).lower() if e.orig else str(e).lower()
        if "phone" in err_str:
            detail = "Phone number is already registered"
        elif "email" in err_str:
            detail = "Email address is already registered"
        elif "oauth_sub" in err_str:
            detail = "OAuth account already linked"
        else:
            detail = "An account with this information already exists"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


# ==========================================
# LOGIN
# ==========================================

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with email and password, returns JWT access token.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    try:
        access_token = await login_user(
            db=db,
            email=form_data.username,
            password=form_data.password,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


# ==========================================
# GOOGLE OAUTH
# ==========================================

@router.get(
    "/oauth/google/config",
    summary="Get Google OAuth Client Configuration",
    description="Returns public client_id and configured status without exposing secrets.",
)
async def get_google_oauth_config():
    client_id = settings.GOOGLE_CLIENT_ID
    is_configured = bool(client_id and not client_id.startswith("your-") and len(client_id) > 10)
    return {
        "client_id": client_id if is_configured else None,
        "configured": is_configured,
    }


@router.post(
    "/oauth/google",
    response_model=TokenResponse,
    summary="Authenticate with Google OAuth",
    description="Verifies Google ID token and returns application JWT bearer token.",
)
async def oauth_google(
    payload: GoogleOAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user, access_token = await authenticate_google_user(
            db=db,
            credential=payload.credential,
            requested_role=payload.role,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user,
        }
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}",
        )


# ==========================================
# LOGOUT
# ==========================================

@router.post(
    "/logout",
    summary="Logout",
    description="Revoke the current JWT token so it cannot be used again.",
)
async def logout(
    current_user=Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    # Decode payload directly from the raw token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to revoke token",
        )

    jti = payload.get("jti")
    exp = payload.get("exp")

    if jti and exp:
        # Use naive UTC datetime to match PostgreSQL TIMESTAMP WITHOUT TIME ZONE column
        expires_at = datetime.utcfromtimestamp(exp)
        await revoke_token(
            db=db,
            token_jti=jti,
            user_id=current_user.id,
            expires_at=expires_at,
        )

    return {"message": "Logged out successfully"}


# ==========================================
# CURRENT USER
# ==========================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the authenticated user's profile.",
)
async def get_me(
    current_user=Depends(get_current_user),
):
    return current_user


# ==========================================
# UPDATE PROFILE
# ==========================================

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update profile",
    description="Update name, phone, or email of the authenticated user.",
)
async def update_profile(
    update_data: UserUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_user_profile(
            db=db,
            user=current_user,
            name=update_data.name,
            phone=update_data.phone,
            email=update_data.email,
        )
    except DuplicateResourceError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e.message),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
