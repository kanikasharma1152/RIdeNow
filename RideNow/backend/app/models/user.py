from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=True   # nullable to support OAuth users who haven't set phone yet
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=True   # nullable for OAuth-only users
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="passenger",
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # ── OAuth identity fields (Phase 2: Google OAuth) ──────────────────────
    # oauth_provider: "google" | None (email/password)
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        default=None,
        index=True,
    )

    # oauth_sub: Google subject ID ("sub" claim) — globally unique per Google user
    oauth_sub: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        unique=True,
        index=True,
    )

    # avatar_url: profile picture URL from Google OAuth
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        default=None,
    )

    # preferred_language: for Hindi/Hinglish AI adaptation
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )

    # onboarding_complete: used for progressive onboarding flow
    onboarding_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )