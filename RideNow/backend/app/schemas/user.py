from typing import Literal

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


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdate(BaseModel):
    """Fields a passenger/driver may update about themselves."""
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
