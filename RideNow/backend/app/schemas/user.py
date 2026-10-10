from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    role: Literal["passenger", "driver"] = "passenger"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleOAuthRequest(BaseModel):
    credential: str
    role: Literal["passenger", "driver"] = "passenger"


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    oauth_provider: Optional[str] = None
    preferred_language: Optional[str] = "en"
    onboarding_complete: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


class UserUpdate(BaseModel):
    """Fields a passenger/driver may update about themselves."""
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    preferred_language: str | None = None
