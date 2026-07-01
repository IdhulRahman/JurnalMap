"""User models for JurnalMap authentication."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
import uuid

from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uid() -> str:
    return str(uuid.uuid4())


# ── Password strength rules ────────────────────────────────────────────────
_PASSWORD_MIN = 8
_UPPER_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"[0-9]")
_SYMBOL_RE = re.compile(r"[^A-Za-z0-9]")


def validate_strong_password(pwd: str) -> str:
    """Return the password if it satisfies the strong-password policy.

    Rules: length >= 8, contains upper case, digit, and symbol.
    """
    if not isinstance(pwd, str) or len(pwd) < _PASSWORD_MIN:
        raise ValueError("Password must be at least 8 characters long")
    if not _UPPER_RE.search(pwd):
        raise ValueError("Password must contain at least one uppercase letter")
    if not _DIGIT_RE.search(pwd):
        raise ValueError("Password must contain at least one digit")
    if not _SYMBOL_RE.search(pwd):
        raise ValueError("Password must contain at least one symbol")
    return pwd


class UserCreate(BaseModel):
    """Payload for POST /api/auth/register."""
    username: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return validate_strong_password(v)


class UserLogin(BaseModel):
    """Payload for POST /api/auth/login."""
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    """Payload for POST /api/auth/forgot-password."""
    username: str
    email: EmailStr
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return validate_strong_password(v)


class ChangePasswordRequest(BaseModel):
    """Payload for POST /api/auth/change-password (requires JWT)."""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return validate_strong_password(v)


class User(BaseModel):
    """User document stored in MongoDB (no password field exposed)."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_uid)
    username: str
    email: Optional[str] = None
    is_admin: bool = False
    created_at: str = Field(default_factory=utcnow_iso)


class TokenResponse(BaseModel):
    """Response from login / register endpoints."""
    access_token: str
    token_type: str = "bearer"
    user: User
