"""
Central Server — Auth & Access Policy (v3.6.0)

4-tier role-based access control:
- superadmin: full access to all data, can manage installers
- installer:  scoped to assigned customers, can manage owners
- owner:      scoped to own business, can manage staff
- staff:      read-only operational view within scope

Provides:
- JWT token generation and verification
- User authentication (login)
- Access policy helpers for scope enforcement
- Role hierarchy checks
"""
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db
from central_server.models import CentralUser, CentralLocation

logger = logging.getLogger("central_server")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_production_env() -> bool:
    env_name = os.environ.get("CENTRAL_ENV", os.environ.get("ENV", "")).strip().lower()
    return env_name in {"prod", "production"}


def _load_jwt_secret() -> str:
    value = os.environ.get("CENTRAL_JWT_SECRET", "").strip()
    if value:
        return value
    if _is_production_env():
        raise RuntimeError("CENTRAL_JWT_SECRET is required in production")
    generated = secrets.token_urlsafe(48)
    logger.warning("CENTRAL_JWT_SECRET missing; using ephemeral runtime secret. Configure a persistent secret before production use.")
    return generated


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
ADMIN_TOKEN = os.environ.get("CENTRAL_ADMIN_TOKEN", "").strip()
LEGACY_ADMIN_TOKEN_ENABLED = _env_flag("CENTRAL_ENABLE_LEGACY_ADMIN_TOKEN", False)

# Role hierarchy — higher number = more privileges
ROLE_HIERARCHY = {
    "staff": 1,
    "owner": 2,
    "installer": 3,
    "superadmin": 4,
}

VALID_ROLES = set(ROLE_HIERARCHY.keys())

# Which roles can each role create?
ROLE_CAN_CREATE = {
    "superadmin": {"superadmin", "installer", "owner", "staff"},
    "installer": {"owner", "staff"},
    "owner": {"staff"},
    "staff": set(),
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _legacy_hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def is_legacy_password_hash(hashed: str) -> bool:
    return bool(hashed) and not hashed.startswith("$2")


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    if hashed.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except ValueError:
            return False
    return hmac.compare_digest(_legacy_hash_password(password), hashed)


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
    __slots__ = ("id", "username", "role", "allowed_customer_ids", "is_superadmin", "created_by_user_id")

    def __init__(self, user_id: str, username: str, role: str, allowed_customer_ids: list = None, created_by_user_id: str = None):
        self.id = user_id
        self.username = username
        self.role = role
        self.allowed_customer_ids = allowed_customer_ids or []
        self.is_superadmin = role == "superadmin"
        self.created_by_user_id = created_by_user_id

    @property
    def role_level(self) -> int:
        return ROLE_HIERARCHY.get(self.role, 0)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> AuthUser:
    """Extract and validate the authenticated user from the request."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if not token:
        raise HTTPException(401, "Missing authorization")

    # Legacy admin token check — disabled by default; opt-in only.
    if LEGACY_ADMIN_TOKEN_ENABLED and ADMIN_TOKEN and hmac.compare_digest(token, ADMIN_TOKEN):
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
        created_by_user_id=user.created_by_user_id,
    )


# ═══════════════════════════════════════════════════════════════
# ROLE CHECKS
# ═══════════════════════════════════════════════════════════════

def require_superadmin(user: AuthUser):
    """Raise 403 if the user is not a superadmin."""
    if not user.is_superadmin:
        raise HTTPException(403, "Superadmin required")


def require_min_role(user: AuthUser, min_role: str):
    """Raise 403 if user's role is below the minimum required level."""
    min_level = ROLE_HIERARCHY.get(min_role, 99)
    if user.role_level < min_level:
        raise HTTPException(403, f"Insufficient permissions. Required: {min_role}")


def require_installer_or_above(user: AuthUser):
    require_min_role(user, "installer")


def require_owner_or_above(user: AuthUser):
    require_min_role(user, "owner")


def can_create_role(creator: AuthUser, target_role: str) -> bool:
    """Check if creator can create users with the target role."""
    allowed = ROLE_CAN_CREATE.get(creator.role, set())
    return target_role in allowed


# ═══════════════════════════════════════════════════════════════
# SCOPE / ACCESS CHECKS
# ═══════════════════════════════════════════════════════════════

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
