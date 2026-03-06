"""
Match Result Routes – Public QR-code match links
- POST /matches (internal, called by kiosk end-game)
- GET /match/{token} (public, rate-limited, no auth)
"""
import secrets
import time
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import MatchResult, Board

logger = logging.getLogger(__name__)

TOKEN_BYTES = 16  # 128 bit = 16 bytes -> 32 hex chars
TOKEN_EXPIRY_HOURS = 24

router = APIRouter()

# ===== Rate limiter (20 req/min/IP) =====
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 20
RATE_WINDOW = 60  # seconds


def _check_rate_limit(ip: str):
    now = time.time()
    hits = _rate_store[ip]
    # Prune old entries
    _rate_store[ip] = [t for t in hits if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _rate_store[ip].append(now)


# ===== Schemas =====

class CreateMatchRequest(BaseModel):
    board_id: str
    game_type: str
    players: list[str]
    winner: Optional[str] = None
    scores: Optional[dict] = None
    duration_seconds: Optional[int] = None


class MatchResponse(BaseModel):
    game_type: str
    players: list[str]
    winner: Optional[str]
    scores: Optional[dict]
    board_name: Optional[str]
    played_at: str
    duration_seconds: Optional[int]
    expires_at: str


# ===== Internal: create match result =====

@router.post("/matches")
async def create_match_result(data: CreateMatchRequest, db: AsyncSession = Depends(get_db)):
    """Called internally when a game ends. Returns the public token."""
    # Look up board name
    result = await db.execute(select(Board).where(Board.board_id == data.board_id))
    board = result.scalar_one_or_none()
    board_name = board.name if board else data.board_id

    token = secrets.token_hex(TOKEN_BYTES)
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

    match = MatchResult(
        public_token=token,
        board_id=data.board_id,
        board_name=board_name,
        game_type=data.game_type,
        players=data.players,
        winner=data.winner,
        scores=data.scores,
        duration_seconds=data.duration_seconds,
        expires_at=expires,
    )
    db.add(match)
    await db.flush()

    logger.info(f"Match result created: {token[:8]}... board={data.board_id} game={data.game_type}")

    return {
        "token": token,
        "url": f"/match/{token}",
        "expires_at": expires.isoformat(),
    }


# ===== Public: view match result =====

@router.get("/match/{token}", response_model=MatchResponse)
async def get_match_result(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Public endpoint – no auth required. Rate limited to 20 req/min/IP."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    if len(token) < 16:
        raise HTTPException(status_code=400, detail="Invalid token")

    result = await db.execute(
        select(MatchResult).where(MatchResult.public_token == token)
    )
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    expires = match.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=410, detail="Match link expired")

    return MatchResponse(
        game_type=match.game_type,
        players=match.players or [],
        winner=match.winner,
        scores=match.scores,
        board_name=match.board_name,
        played_at=match.played_at.isoformat() if match.played_at else match.created_at.isoformat(),
        duration_seconds=match.duration_seconds,
        expires_at=match.expires_at.isoformat(),
    )
