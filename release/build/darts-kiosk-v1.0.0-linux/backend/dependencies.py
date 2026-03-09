"""
Shared Dependencies: auth, password hashing, token management, DB helpers
"""
import os
import hmac
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

import jwt
import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db, DATA_DIR
from backend.models import User, Session, Settings, AuditLog, UserRole, SessionStatus

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get('JWT_SECRET', 'darts-kiosk-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
MODE = os.environ.get('MODE', 'MASTER')
AGENT_SECRET = os.environ.get('AGENT_SECRET', 'agent-secret-key')
ASSETS_DIR = DATA_DIR / 'assets'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_agent_secret(request: Request) -> bool:
    auth_header = request.headers.get("X-Agent-Secret", "")
    return hmac.compare_digest(auth_header, AGENT_SECRET)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Fallback: accept token as query parameter (needed for window.open downloads)
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def log_audit(db: AsyncSession, user: Optional[User], action: str,
                    entity_type: str = None, entity_id: str = None,
                    details: dict = None, ip: str = None):
    log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip
    )
    db.add(log)
    await db.flush()


async def get_or_create_setting(db: AsyncSession, key: str, default_value: dict) -> dict:
    result = await db.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = Settings(key=key, value=default_value)
        db.add(setting)
        await db.flush()
    return setting.value


async def get_active_session_for_board(db: AsyncSession, board_db_id: str) -> Optional[Session]:
    result = await db.execute(
        select(Session)
        .where(Session.board_id == board_db_id)
        .where(Session.status == SessionStatus.ACTIVE.value)
        .order_by(Session.started_at.desc())
    )
    return result.scalar_one_or_none()
