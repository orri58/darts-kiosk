"""
Central Server — Auth & Access Policy (v3.5.2)

Role-based access control for the central license server.
- superadmin: full access to all data
- operator: scoped to allowed_customer_ids only

Provides:
- JWT token generation and verification
- User authentication (login)
- Access policy helpers for scope enforcement
"""
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db
from central_server.models import CentralUser, CentralLocation

logger = logging.getLogger("central_server")

JWT_SECRET = os.environ.get("CENTRAL_JWT_SECRET", "central-jwt-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
ADMIN_TOKEN = os.environ.get("CENTRAL_ADMIN_TOKEN", "admin-secret-token")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def create_jwt(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


class AuthUser:
    """Represents the authenticated user context for a request."""
    __slots__ = ("id", "username", "role", "allowed_customer_ids", "is_superadmin")

    def __init__(self, user_id: str, username: str, role: str, allowed_customer_ids: list = None):
        self.id = user_id
        self.username = username
        self.role = role
        self.allowed_customer_ids = allowed_customer_ids or []
        self.is_superadmin = role == "superadmin"


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> AuthUser:
    """Extract and validate the authenticated user from the request.

    Supports:
    1. JWT Bearer token (normal users)
    2. Legacy ADMIN_TOKEN (superadmin bypass for bootstrap)
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if not token:
        raise HTTPException(401, "Missing authorization")

    # Legacy admin token check — always superadmin
    if token == ADMIN_TOKEN:
        return AuthUser("_legacy_", "superadmin", "superadmin")

    # JWT token
    payload = decode_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token payload")

    result = await db.execute(select(CentralUser).where(CentralUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    if user.status != "active":
        raise HTTPException(403, "User account is disabled")

    return AuthUser(
        user_id=user.id,
        username=user.username,
        role=user.role,
        allowed_customer_ids=user.allowed_customer_ids or [],
    )


def require_superadmin(user: AuthUser):
    """Raise 403 if the user is not a superadmin."""
    if not user.is_superadmin:
        raise HTTPException(403, "Superadmin required")


def get_allowed_customer_ids(user: AuthUser) -> Optional[list]:
    """Return the list of customer IDs the user can access, or None if superadmin (= all)."""
    if user.is_superadmin:
        return None  # None means unrestricted
    return user.allowed_customer_ids


def can_access_customer(user: AuthUser, customer_id: str) -> bool:
    if user.is_superadmin:
        return True
    return customer_id in (user.allowed_customer_ids or [])


async def can_access_location(user: AuthUser, location_id: str, db: AsyncSession) -> bool:
    if user.is_superadmin:
        return True
    result = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
    loc = result.scalar_one_or_none()
    if not loc:
        return False
    return loc.customer_id in (user.allowed_customer_ids or [])


async def can_access_device_by_location(user: AuthUser, location_id: str, db: AsyncSession) -> bool:
    return await can_access_location(user, location_id, db)


def apply_customer_scope(stmt, user: AuthUser, customer_id_column):
    """Apply customer scope filtering to a SQLAlchemy query."""
    allowed = get_allowed_customer_ids(user)
    if allowed is not None:
        stmt = stmt.where(customer_id_column.in_(allowed))
    return stmt
