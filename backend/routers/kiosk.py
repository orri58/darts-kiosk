"""Kiosk Action Routes (called from kiosk UI, no auth)"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Board, Session, MatchResult, BoardStatus, SessionStatus, PricingMode
from schemas import StartGameRequest, EndGameRequest
from dependencies import get_active_session_for_board, log_audit
from services.ws_manager import board_ws

router = APIRouter()


@router.post("/kiosk/{board_id}/start-game")
async def kiosk_start_game(board_id: str, data: StartGameRequest, db: AsyncSession = Depends(get_db)):
    """Called when customer starts a game on kiosk"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session - board must be unlocked first")

    if session.pricing_mode == PricingMode.PER_GAME.value:
        if session.credits_remaining <= 0:
            raise HTTPException(status_code=400, detail="No credits remaining")

    if session.pricing_mode == PricingMode.PER_TIME.value:
        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
            raise HTTPException(status_code=400, detail="Session time expired")

    session.game_type = data.game_type
    session.players = data.players
    session.players_count = len(data.players)
    board.status = BoardStatus.IN_GAME.value

    await db.flush()

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": "in_game", "game_type": data.game_type})

    return {
        "message": "Game started",
        "game_type": data.game_type,
        "players": data.players,
        "session_id": session.id
    }


@router.post("/kiosk/{board_id}/end-game")
async def kiosk_end_game(board_id: str, data: Optional[EndGameRequest] = None, db: AsyncSession = Depends(get_db)):
    """Called when a game ends (from autodarts integration or manual)"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        return {"message": "No active session"}

    should_lock = False

    if session.pricing_mode == PricingMode.PER_GAME.value:
        session.credits_remaining = max(0, session.credits_remaining - 1)
        if session.credits_remaining <= 0:
            should_lock = True

    if session.pricing_mode == PricingMode.PER_TIME.value:
        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
            should_lock = True

    if should_lock:
        session.status = SessionStatus.FINISHED.value
        session.ended_at = datetime.now(timezone.utc)
        session.ended_reason = "credits_exhausted" if session.pricing_mode == PricingMode.PER_GAME.value else "time_expired"
        board.status = BoardStatus.LOCKED.value
    else:
        board.status = BoardStatus.UNLOCKED.value

    # Create match result with public token
    duration = None
    if session.started_at:
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration = int((datetime.now(timezone.utc) - started).total_seconds())

    token = secrets.token_hex(16)
    winner = (data.winner if data and data.winner else
              session.players[0] if session.players else None)
    scores = data.scores if data and data.scores else None

    match = MatchResult(
        public_token=token,
        board_id=board.board_id,
        board_name=board.name,
        game_type=session.game_type or "Dart",
        players=session.players or [],
        winner=winner,
        scores=scores,
        duration_seconds=duration,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(match)

    await db.flush()

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": board.status})

    return {
        "message": "Game ended",
        "should_lock": should_lock,
        "credits_remaining": session.credits_remaining,
        "board_status": board.status,
        "match_token": token,
        "match_url": f"/match/{token}",
    }


@router.post("/kiosk/{board_id}/call-staff")
async def kiosk_call_staff(board_id: str, db: AsyncSession = Depends(get_db)):
    """Customer requests staff assistance"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    await log_audit(db, None, "call_staff", "board", board.id, {"board_id": board_id})
    return {"message": "Staff notified", "board_id": board_id}
