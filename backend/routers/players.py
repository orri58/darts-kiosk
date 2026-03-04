"""
Player (Stammkunde) Routes
- Register guest → registered player (nickname + PIN)
- PIN login for returning players
- QR token quick login
- Rate limited PIN attempts
"""
import time
import secrets
import logging
from datetime import datetime, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional

import bcrypt

from database import get_db
from models import Player

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter: 5 PIN attempts per minute per IP
_pin_attempts: dict[str, list[float]] = defaultdict(list)
PIN_RATE_LIMIT = 5
PIN_RATE_WINDOW = 60


def _check_pin_rate(ip: str):
    now = time.time()
    hits = _pin_attempts[ip]
    _pin_attempts[ip] = [t for t in hits if now - t < PIN_RATE_WINDOW]
    if len(_pin_attempts[ip]) >= PIN_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Zu viele Versuche. Bitte warten.")
    _pin_attempts[ip].append(now)


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def _verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


# ===== Schemas =====

class PlayerCheckRequest(BaseModel):
    nickname: str

class PlayerRegisterRequest(BaseModel):
    nickname: str
    pin: str  # 4-6 digits

class PlayerPinLoginRequest(BaseModel):
    nickname: str
    pin: str

class PlayerQrLoginRequest(BaseModel):
    qr_token: str


# ===== Endpoints =====

@router.post("/players/check")
async def check_player(data: PlayerCheckRequest, db: AsyncSession = Depends(get_db)):
    """Check if a nickname is registered (has PIN). Called when player enters name on kiosk."""
    result = await db.execute(
        select(Player).where(Player.nickname_lower == data.nickname.strip().lower())
    )
    player = result.scalar_one_or_none()

    if not player:
        return {"exists": False, "is_registered": False, "nickname": data.nickname.strip()}

    return {
        "exists": True,
        "is_registered": player.is_registered,
        "nickname": player.nickname,
        "player_id": player.id,
    }


@router.post("/players/register")
async def register_player(data: PlayerRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a guest as a Stammkunde with a PIN."""
    nickname = data.nickname.strip()
    pin = data.pin.strip()

    if len(nickname) < 2 or len(nickname) > 30:
        raise HTTPException(status_code=400, detail="Nickname muss 2-30 Zeichen lang sein")
    if not (4 <= len(pin) <= 6) or not pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN muss 4-6 Ziffern sein")

    result = await db.execute(
        select(Player).where(Player.nickname_lower == nickname.lower())
    )
    existing = result.scalar_one_or_none()

    if existing and existing.is_registered:
        raise HTTPException(status_code=409, detail="Nickname bereits registriert")

    qr_token = secrets.token_urlsafe(32)

    if existing:
        # Upgrade guest → registered (keep stats)
        existing.pin_hash = _hash_pin(pin)
        existing.qr_token = qr_token
        existing.is_registered = True
        existing.nickname = nickname  # preserve original casing
        player = existing
    else:
        player = Player(
            nickname=nickname,
            nickname_lower=nickname.lower(),
            pin_hash=_hash_pin(pin),
            qr_token=qr_token,
            is_registered=True,
        )
        db.add(player)

    await db.flush()
    logger.info(f"Player registered: {nickname} (id={player.id})")

    return {
        "success": True,
        "player_id": player.id,
        "nickname": player.nickname,
        "qr_token": qr_token,
        "message": "Registrierung erfolgreich! QR-Code aufbewahren.",
    }


@router.post("/players/pin-login")
async def pin_login(data: PlayerPinLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate a registered player with nickname + PIN."""
    client_ip = request.client.host if request.client else "unknown"
    _check_pin_rate(client_ip)

    result = await db.execute(
        select(Player).where(Player.nickname_lower == data.nickname.strip().lower())
    )
    player = result.scalar_one_or_none()

    if not player or not player.is_registered or not player.pin_hash:
        raise HTTPException(status_code=401, detail="Ungueltige Anmeldedaten")

    if not _verify_pin(data.pin, player.pin_hash):
        raise HTTPException(status_code=401, detail="Falscher PIN")

    return {
        "success": True,
        "player_id": player.id,
        "nickname": player.nickname,
        "is_registered": True,
    }


@router.post("/players/qr-login")
async def qr_login(data: PlayerQrLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a registered player with their QR token."""
    result = await db.execute(
        select(Player).where(Player.qr_token == data.qr_token)
    )
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=401, detail="Ungueltiger QR-Code")

    return {
        "success": True,
        "player_id": player.id,
        "nickname": player.nickname,
        "is_registered": True,
    }


@router.get("/players/registered")
async def list_registered_players(db: AsyncSession = Depends(get_db)):
    """List all registered Stammkunden (no auth – shown on kiosk for selection)."""
    result = await db.execute(
        select(Player)
        .where(Player.is_registered == True)
        .order_by(Player.last_played_at.desc().nullslast())
    )
    players = result.scalars().all()

    return {
        "players": [
            {
                "id": p.id,
                "nickname": p.nickname,
                "games_played": p.games_played,
                "games_won": p.games_won,
                "last_played": p.last_played_at.isoformat() if p.last_played_at else None,
            }
            for p in players
        ]
    }
