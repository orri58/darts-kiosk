"""
Kiosk Action Routes (called from kiosk UI, no auth)

AUTODARTS_MODE=observer (default MVP):
  - Unlock opens Autodarts browser, observer watches game state
  - start-game is a no-op (customer starts game directly in Autodarts)
  - Observer auto-detects game end → decrements credits → auto-locks if exhausted

AUTODARTS_MODE=automation (legacy):
  - Full Playwright automation for game setup (fragile, not recommended for MVP)
"""
import asyncio
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database import get_db, AsyncSessionLocal
from backend.models import Board, Session, MatchResult, Player, BoardStatus, SessionStatus, PricingMode
from backend.schemas import StartGameRequest, EndGameRequest
from backend.dependencies import get_active_session_for_board, log_audit
from backend.services.ws_manager import board_ws
from backend.services.autodarts_observer import observer_manager, ObserverState

import logging
logger = logging.getLogger(__name__)

# Feature flag
AUTODARTS_MODE = os.environ.get('AUTODARTS_MODE', 'observer')

router = APIRouter()


# =====================================================================
# Observer callbacks — triggered when observer detects game transitions
# =====================================================================

async def _on_game_started(board_id: str):
    """Called by observer when a match starts in Autodarts."""
    logger.info(f"[Observer→Kiosk] Game STARTED on board {board_id}")
    await board_ws.broadcast("board_status", {
        "board_id": board_id,
        "status": "in_game",
        "source": "observer",
    })
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "start"})


async def _on_game_finished(board_id: str):
    """
    Called by observer when a match ends in Autodarts.
    Decrements credits or checks time, auto-locks if exhausted.
    """
    logger.info(f"[Observer→Kiosk] Game FINISHED on board {board_id}")

    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(select(Board).where(Board.board_id == board_id))
                board = result.scalar_one_or_none()
                if not board:
                    logger.error(f"[Observer→Kiosk] Board {board_id} not found")
                    return

                session = await get_active_session_for_board(db, board.id)
                if not session:
                    logger.warning(f"[Observer→Kiosk] No active session for {board_id}")
                    return

                # Run the end-game business logic
                end_result = await _end_game_internal(db, board, session, board_id)

                # If board got locked, close the observer
                if end_result.get("should_lock"):
                    logger.info(f"[Observer→Kiosk] Credits/time exhausted → closing observer for {board_id}")
                    asyncio.create_task(observer_manager.close(board_id))

    except Exception as e:
        logger.error(f"[Observer→Kiosk] Error processing game end for {board_id}: {e}", exc_info=True)


# =====================================================================
# Observer lifecycle — called from boards.py on unlock/lock
# =====================================================================

async def start_observer_for_board(board_id: str, autodarts_url: str):
    """Open the Autodarts browser for a board (called on unlock)."""
    if AUTODARTS_MODE != 'observer':
        logger.info(f"[Kiosk] AUTODARTS_MODE={AUTODARTS_MODE}, skipping observer for {board_id}")
        return

    if not autodarts_url:
        logger.info(f"[Kiosk] No autodarts_url for {board_id}, skipping observer")
        return

    logger.info(f"[Kiosk] Starting observer for {board_id} → {autodarts_url}")
    headless = os.environ.get('AUTODARTS_HEADLESS', 'true').lower() == 'true'
    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_finished=_on_game_finished,
        headless=headless,
    )


async def stop_observer_for_board(board_id: str):
    """Close the Autodarts browser for a board (called on lock)."""
    await observer_manager.close(board_id)


# =====================================================================
# Endpoints
# =====================================================================

@router.post("/kiosk/{board_id}/start-game")
async def kiosk_start_game(board_id: str, data: StartGameRequest, db: AsyncSession = Depends(get_db)):
    """
    In observer mode: No-op for Autodarts automation.
    Records player names and game type for stats, but the customer
    starts the actual game directly inside the native Autodarts UI.
    """
    logger.info(f"[StartGame] Endpoint called: board={board_id}, game_type={data.game_type}, players={data.players}")

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

    # Record player names / game type (for stats tracking)
    session.game_type = data.game_type
    session.players = data.players
    session.players_count = len(data.players)
    board.status = BoardStatus.IN_GAME.value
    await db.flush()

    await board_ws.broadcast("board_status", {
        "board_id": board_id,
        "status": "in_game",
        "game_type": data.game_type,
    })

    # In observer mode, Autodarts browser is already open from unlock.
    # Customer starts the game directly in Autodarts.
    observer_status = observer_manager.get_status(board_id)

    return {
        "message": "Game registered — start the game directly in Autodarts",
        "game_type": data.game_type,
        "players": data.players,
        "session_id": session.id,
        "autodarts_mode": AUTODARTS_MODE,
        "observer_state": observer_status.get("state"),
    }


async def _end_game_internal(
    db: AsyncSession, board: Board, session: Session, board_id: str,
    winner: Optional[str] = None, scores: Optional[dict] = None
):
    """Internal end-game logic shared by the endpoint and the observer callback."""
    logger.info(f"[EndGame] Internal: board={board_id}, winner={winner}")

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
        session.ended_reason = (
            "credits_exhausted" if session.pricing_mode == PricingMode.PER_GAME.value
            else "time_expired"
        )
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
    final_winner = winner or (session.players[0] if session.players else None)

    match = MatchResult(
        public_token=token,
        board_id=board.board_id,
        board_name=board.name,
        game_type=session.game_type or "Dart",
        players=session.players or [],
        winner=final_winner,
        scores=scores,
        duration_seconds=duration,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(match)

    # Update Player stats
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
        if final_winner and final_winner.strip().lower() == name.strip().lower():
            player.games_won = (player.games_won or 0) + 1
        player.last_played_at = datetime.now(timezone.utc)

    await db.flush()

    status_str = board.status
    event = "win" if final_winner else "checkout"
    await board_ws.broadcast("board_status", {"board_id": board_id, "status": status_str})
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": event})
    if should_lock:
        await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "checkout"})

    logger.info(f"[EndGame] Done: board={board_id}, locked={should_lock}, credits_left={session.credits_remaining}")

    return {
        "message": "Game ended",
        "should_lock": should_lock,
        "credits_remaining": session.credits_remaining,
        "board_status": status_str,
        "match_token": token,
        "match_url": f"/match/{token}",
    }


@router.post("/kiosk/{board_id}/end-game")
async def kiosk_end_game(board_id: str, data: Optional[EndGameRequest] = None, db: AsyncSession = Depends(get_db)):
    """Called when a game ends (from observer callback or manual trigger)."""
    logger.info(f"[EndGame] Endpoint called: board={board_id}")

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        return {"message": "No active session"}

    winner = data.winner if data and data.winner else None
    scores = data.scores if data and data.scores else None

    end_result = await _end_game_internal(db, board, session, board_id, winner=winner, scores=scores)

    # If locked, close observer
    if end_result.get("should_lock"):
        asyncio.create_task(observer_manager.close(board_id))

    return end_result


# =====================================================================
# Observer status & control endpoints
# =====================================================================

@router.get("/kiosk/{board_id}/observer-status")
async def get_observer_status(board_id: str):
    """Get the current Autodarts observer status for a board."""
    return {
        "autodarts_mode": AUTODARTS_MODE,
        **observer_manager.get_status(board_id),
    }


@router.get("/kiosk/observers/all")
async def get_all_observer_statuses():
    """Get observer status for all boards (admin overview)."""
    return {
        "autodarts_mode": AUTODARTS_MODE,
        "observers": observer_manager.get_all_statuses(),
    }


@router.post("/kiosk/{board_id}/observer-reset")
async def reset_observer(board_id: str):
    """Close and reopen the observer for a board."""
    logger.info(f"[Observer] Reset requested for board {board_id}")
    await observer_manager.close(board_id)

    # Reopen if board has autodarts URL and active session
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Board).where(Board.board_id == board_id))
        board = result.scalar_one_or_none()
        if board and board.autodarts_target_url:
            session = await get_active_session_for_board(db, board.id)
            if session:
                await start_observer_for_board(board_id, board.autodarts_target_url)
                return {"message": "Observer reset and reopened", "board_id": board_id}

    return {"message": "Observer closed (no active session to reopen)", "board_id": board_id}


# =====================================================================
# Sound trigger (unchanged)
# =====================================================================

class SoundTrigger(BaseModel):
    event: str

@router.post("/kiosk/{board_id}/sound")
async def trigger_sound(board_id: str, data: SoundTrigger):
    """Trigger a sound event for a board (used by kiosk UI)."""
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": data.event})
    return {"message": f"Sound '{data.event}' triggered", "board_id": board_id}
