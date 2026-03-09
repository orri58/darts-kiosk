"""
Kiosk Action Routes — Observer MVP

Credit logic: credits decrement on game START (idle->in_game), not on finish.
Match sharing: conditional based on admin setting match_sharing.enabled.
"""
import asyncio
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database import get_db, AsyncSessionLocal
from backend.models import Board, Session, MatchResult, Player, User, BoardStatus, SessionStatus, PricingMode, Settings
from backend.schemas import StartGameRequest, EndGameRequest
from backend.dependencies import get_active_session_for_board, log_audit, get_or_create_setting, require_admin
from backend.services.ws_manager import board_ws
from backend.services.autodarts_observer import observer_manager, ObserverState

import logging
logger = logging.getLogger(__name__)

AUTODARTS_MODE = os.environ.get('AUTODARTS_MODE', 'observer')

DEFAULT_MATCH_SHARING = {"enabled": False, "qr_timeout": 60}

router = APIRouter()


# =====================================================================
# Observer callbacks
# =====================================================================

async def _on_game_started(board_id: str):
    """
    Observer detected idle -> in_game.
    Decrement credits NOW (not on finish).
    """
    logger.info(f"[Observer->Kiosk] Game STARTED on board {board_id}")

    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(select(Board).where(Board.board_id == board_id))
                board = result.scalar_one_or_none()
                if not board:
                    logger.error(f"[Observer->Kiosk] Board {board_id} not found")
                    return

                session = await get_active_session_for_board(db, board.id)
                if not session:
                    logger.warning(f"[Observer->Kiosk] No active session for {board_id}")
                    return

                board.status = BoardStatus.IN_GAME.value
                is_last_game = False

                if session.pricing_mode == PricingMode.PER_GAME.value:
                    session.credits_remaining = max(0, session.credits_remaining - 1)
                    logger.info(f"[Observer->Kiosk] Credits decremented: {session.credits_remaining} remaining")
                    if session.credits_remaining <= 0:
                        is_last_game = True
                        logger.info("[Observer->Kiosk] Last game! Credits exhausted after this game.")

                if session.pricing_mode == PricingMode.PER_TIME.value:
                    if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
                        is_last_game = True

                await db.flush()

                # Update observer status with credit info
                obs = observer_manager.get(board_id)
                if obs:
                    obs.status.credits_remaining = session.credits_remaining
                    obs.status.is_last_game = is_last_game

        # Broadcast updates
        await board_ws.broadcast("board_status", {
            "board_id": board_id,
            "status": "in_game",
            "source": "observer",
        })
        await board_ws.broadcast("credit_update", {
            "board_id": board_id,
            "credits_remaining": session.credits_remaining,
            "is_last_game": is_last_game,
        })
        await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "start"})

    except Exception as e:
        logger.error(f"[Observer->Kiosk] Error on game start for {board_id}: {e}", exc_info=True)


async def _on_game_finished(board_id: str):
    """
    Observer detected in_game -> finished.
    Credits already decremented at start. Now check if we should lock.
    """
    logger.info(f"[Observer->Kiosk] Game FINISHED on board {board_id}")

    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(select(Board).where(Board.board_id == board_id))
                board = result.scalar_one_or_none()
                if not board:
                    return

                session = await get_active_session_for_board(db, board.id)
                if not session:
                    return

                should_lock = False

                if session.pricing_mode == PricingMode.PER_GAME.value:
                    if session.credits_remaining <= 0:
                        should_lock = True

                if session.pricing_mode == PricingMode.PER_TIME.value:
                    if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
                        should_lock = True

                # Conditional match result creation
                match_sharing = await get_or_create_setting(db, "match_sharing", DEFAULT_MATCH_SHARING)
                token = None
                if match_sharing.get("enabled", False):
                    token = secrets.token_hex(16)
                    duration = None
                    if session.started_at:
                        started = session.started_at
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=timezone.utc)
                        duration = int((datetime.now(timezone.utc) - started).total_seconds())
                    match = MatchResult(
                        public_token=token,
                        board_id=board.board_id,
                        board_name=board.name,
                        game_type=session.game_type or "Dart",
                        players=session.players or [],
                        winner=session.players[0] if session.players else None,
                        duration_seconds=duration,
                        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                    )
                    db.add(match)

                # Update player stats
                for name in (session.players or []):
                    result_p = await db.execute(
                        select(Player).where(Player.nickname_lower == name.strip().lower())
                    )
                    player = result_p.scalar_one_or_none()
                    if not player:
                        player = Player(
                            nickname=name.strip(),
                            nickname_lower=name.strip().lower(),
                            is_registered=False,
                        )
                        db.add(player)
                    player.games_played = (player.games_played or 0) + 1
                    player.last_played_at = datetime.now(timezone.utc)

                if should_lock:
                    session.status = SessionStatus.FINISHED.value
                    session.ended_at = datetime.now(timezone.utc)
                    session.ended_reason = (
                        "credits_exhausted" if session.pricing_mode == PricingMode.PER_GAME.value
                        else "time_expired"
                    )
                    board.status = BoardStatus.LOCKED.value
                else:
                    board.status = BoardStatus.UNLOCKED.value

                await db.flush()

        # Broadcast
        await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "checkout"})
        if should_lock:
            await board_ws.broadcast("board_status", {"board_id": board_id, "status": "locked"})
            logger.info(f"[Observer->Kiosk] Auto-locking board {board_id}")
            asyncio.create_task(observer_manager.close(board_id))
        else:
            await board_ws.broadcast("board_status", {"board_id": board_id, "status": "unlocked"})
            await board_ws.broadcast("credit_update", {
                "board_id": board_id,
                "credits_remaining": session.credits_remaining,
                "is_last_game": False,
            })

    except Exception as e:
        logger.error(f"[Observer->Kiosk] Error on game finish for {board_id}: {e}", exc_info=True)


# =====================================================================
# Observer lifecycle
# =====================================================================

async def start_observer_for_board(board_id: str, autodarts_url: str):
    if AUTODARTS_MODE != 'observer':
        logger.info(f"[Kiosk] AUTODARTS_MODE={AUTODARTS_MODE}, skipping observer")
        return
    if not autodarts_url:
        logger.info(f"[Kiosk] No autodarts_url for {board_id}, skipping observer")
        return

    logger.info(f"[Kiosk] Starting observer for {board_id} -> {autodarts_url}")
    headless = os.environ.get('AUTODARTS_HEADLESS', 'true').lower() == 'true'
    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_finished=_on_game_finished,
        headless=headless,
    )


async def stop_observer_for_board(board_id: str):
    await observer_manager.close(board_id)


# =====================================================================
# Endpoints
# =====================================================================

@router.post("/kiosk/{board_id}/start-game")
async def kiosk_start_game(board_id: str, data: StartGameRequest, db: AsyncSession = Depends(get_db)):
    """
    Observer mode: records player names/game type only.
    Customer starts the game directly in native Autodarts.
    """
    logger.info(f"[StartGame] board={board_id}, game_type={data.game_type}, players={data.players}")

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session")

    session.game_type = data.game_type
    session.players = data.players
    session.players_count = len(data.players)
    await db.flush()

    observer_status = observer_manager.get_status(board_id)
    return {
        "message": "Game registered - start directly in Autodarts",
        "session_id": session.id,
        "autodarts_mode": AUTODARTS_MODE,
        "observer_state": observer_status.get("state"),
    }


@router.post("/kiosk/{board_id}/end-game")
async def kiosk_end_game(board_id: str, data: Optional[EndGameRequest] = None, db: AsyncSession = Depends(get_db)):
    """Manual end-game trigger (staff action). Credits already decremented at start."""
    logger.info(f"[EndGame] Manual trigger: board={board_id}")

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        return {"message": "No active session"}

    should_lock = False
    if session.pricing_mode == PricingMode.PER_GAME.value and session.credits_remaining <= 0:
        should_lock = True
    if session.pricing_mode == PricingMode.PER_TIME.value:
        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
            should_lock = True

    # Conditional match result
    match_sharing = await get_or_create_setting(db, "match_sharing", DEFAULT_MATCH_SHARING)
    token = None
    if match_sharing.get("enabled", False):
        token = secrets.token_hex(16)
        winner = data.winner if data and data.winner else None
        scores = data.scores if data and data.scores else None
        duration = None
        if session.started_at:
            started = session.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            duration = int((datetime.now(timezone.utc) - started).total_seconds())
        match = MatchResult(
            public_token=token,
            board_id=board.board_id,
            board_name=board.name,
            game_type=session.game_type or "Dart",
            players=session.players or [],
            winner=winner or (session.players[0] if session.players else None),
            scores=scores,
            duration_seconds=duration,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(match)

    if should_lock:
        session.status = SessionStatus.FINISHED.value
        session.ended_at = datetime.now(timezone.utc)
        session.ended_reason = "manual_or_exhausted"
        board.status = BoardStatus.LOCKED.value
    else:
        board.status = BoardStatus.UNLOCKED.value

    await db.flush()
    await board_ws.broadcast("board_status", {"board_id": board_id, "status": board.status})

    if should_lock:
        asyncio.create_task(observer_manager.close(board_id))

    return {
        "message": "Game ended",
        "should_lock": should_lock,
        "credits_remaining": session.credits_remaining,
        "board_status": board.status,
        "match_token": token,
        "match_sharing_enabled": match_sharing.get("enabled", False),
    }


# =====================================================================
# Observer status & control
# =====================================================================

@router.get("/kiosk/{board_id}/observer-status")
async def get_observer_status(board_id: str, db: AsyncSession = Depends(get_db)):
    """Observer status with credits info."""
    obs_status = observer_manager.get_status(board_id)

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    credits_remaining = None
    pricing_mode = None
    expires_at = None
    if board:
        session = await get_active_session_for_board(db, board.id)
        if session:
            credits_remaining = session.credits_remaining
            pricing_mode = session.pricing_mode
            expires_at = session.expires_at.isoformat() if session.expires_at else None

    return {
        "autodarts_mode": AUTODARTS_MODE,
        **obs_status,
        "credits_remaining": credits_remaining,
        "pricing_mode": pricing_mode,
        "session_expires_at": expires_at,
    }


@router.get("/kiosk/observers/all")
async def get_all_observer_statuses():
    return {
        "autodarts_mode": AUTODARTS_MODE,
        "observers": observer_manager.get_all_statuses(),
    }


@router.post("/kiosk/{board_id}/observer-reset")
async def reset_observer(board_id: str):
    logger.info(f"[Observer] Reset: {board_id}")
    await observer_manager.close(board_id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Board).where(Board.board_id == board_id))
        board = result.scalar_one_or_none()
        if board and board.autodarts_target_url:
            session = await get_active_session_for_board(db, board.id)
            if session:
                await start_observer_for_board(board_id, board.autodarts_target_url)
                return {"message": "Observer reset and reopened", "board_id": board_id}

    return {"message": "Observer closed", "board_id": board_id}


# =====================================================================
# Overlay data endpoint (lightweight, polled by overlay window)
# =====================================================================

@router.get("/kiosk/{board_id}/overlay")
async def get_overlay_data(board_id: str, db: AsyncSession = Depends(get_db)):
    """Returns minimal data for the credits overlay display."""
    # Check if overlay is enabled in settings
    overlay_config = await get_or_create_setting(db, "overlay_config", {"enabled": True})
    if not overlay_config.get("enabled", True):
        return {"visible": False, "reason": "disabled"}

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        return {"visible": False}

    # Only show overlay when board is unlocked or in_game
    if board.status not in (BoardStatus.UNLOCKED.value, BoardStatus.IN_GAME.value):
        return {"visible": False, "board_status": board.status}

    session = await get_active_session_for_board(db, board.id)
    if not session:
        return {"visible": False}

    time_remaining = None
    if session.pricing_mode == PricingMode.PER_TIME.value and session.expires_at:
        delta = session.expires_at - datetime.now(timezone.utc)
        time_remaining = max(0, int(delta.total_seconds()))

    obs_status = observer_manager.get_status(board_id)
    is_last = obs_status.get("is_last_game", False)
    if not is_last and session.pricing_mode == PricingMode.PER_GAME.value:
        is_last = (session.credits_remaining or 0) <= 0

    return {
        "visible": True,
        "board_name": board.name,
        "board_status": board.status,
        "pricing_mode": session.pricing_mode,
        "credits_remaining": session.credits_remaining,
        "time_remaining_seconds": time_remaining,
        "observer_state": obs_status.get("state"),
        "is_last_game": is_last,
        "session_id": session.id,
    }


# =====================================================================
# Sound trigger
# =====================================================================

class SoundTrigger(BaseModel):
    event: str

@router.post("/kiosk/{board_id}/sound")
async def trigger_sound(board_id: str, data: SoundTrigger):
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": data.event})
    return {"message": f"Sound '{data.event}' triggered", "board_id": board_id}



# =====================================================================
# Observer simulation (for testing without real Autodarts)
# =====================================================================

@router.post("/kiosk/{board_id}/simulate-game-start")
async def simulate_game_start(board_id: str, admin: User = Depends(require_admin)):
    """Simulate observer detecting idle→in_game (for testing only)."""
    await _on_game_started(board_id)
    return {"message": f"Simulated game start on {board_id}"}


@router.post("/kiosk/{board_id}/simulate-game-end")
async def simulate_game_end(board_id: str, admin: User = Depends(require_admin)):
    """Simulate observer detecting in_game→finished (for testing only)."""
    await _on_game_finished(board_id)
    return {"message": f"Simulated game end on {board_id}"}
