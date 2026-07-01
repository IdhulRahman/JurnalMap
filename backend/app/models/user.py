"""User models for JurnalMap authentication."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from pydantic import BaseModel, Field, ConfigDict, EmailStr


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uid() -> str:
    return str(uuid.uuid4())


class UserCreate(BaseModel):
    """Payload for POST /api/auth/register."""
    username: str
    password: str
    email: Optional[str] = None


class UserLogin(BaseModel):
    """Payload for POST /api/auth/login."""
    username: str
    password: str


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
