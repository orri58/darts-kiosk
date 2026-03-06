"""Kiosk Action Routes (called from kiosk UI, no auth)"""
import asyncio
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
from backend.services.autodarts_integration import (
    get_autodarts_integration, GameConfig, AutodartsError
)

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Global autodarts integration instance (lazy-initialized per board)
_autodarts_instances: dict = {}


def _get_autodarts(board_id: str):
    """Get or create an autodarts integration instance for a board."""
    if board_id not in _autodarts_instances:
        _autodarts_instances[board_id] = get_autodarts_integration()
        logger.info(f"[Autodarts] Created integration instance for board {board_id}")
    return _autodarts_instances[board_id]


async def _run_autodarts_game(board_id: str, config: GameConfig):
    """
    Background task: Start autodarts automation and wait for game end.
    When the game finishes, automatically call end-game logic.
    """
    logger.info(f"[Autodarts] Background task started for board {board_id}")
    logger.info(f"[Autodarts] Config: game_type={config.game_type}, players={config.players}")

    integration = _get_autodarts(board_id)

    # Check circuit breaker
    if hasattr(integration, '_circuit_breaker') and not integration._circuit_breaker.can_execute():
        logger.warning(f"[Autodarts] Circuit breaker OPEN for board {board_id} — skipping automation")
        await board_ws.broadcast("autodarts_status", {
            "board_id": board_id,
            "status": "circuit_open",
            "message": "Autodarts automation temporarily disabled due to repeated failures"
        })
        return

    # Check manual mode
    if hasattr(integration, '_manual_mode') and integration._manual_mode:
        logger.info(f"[Autodarts] Manual mode active for board {board_id} — skipping automation")
        return

    try:
        # Step 1: Start the game
        logger.info(f"[Autodarts] Starting game via Playwright for board {board_id}...")
        result = await integration.start_game(config)

        if not result.success:
            logger.error(f"[Autodarts] start_game FAILED for board {board_id}: {result.message}")
            if hasattr(integration, '_circuit_breaker'):
                integration._circuit_breaker.record_failure()
            await board_ws.broadcast("autodarts_status", {
                "board_id": board_id,
                "status": "error",
                "message": result.message,
                "screenshot": result.screenshot_path
            })
            return

        logger.info(f"[Autodarts] Game started successfully for board {board_id}")
        if hasattr(integration, '_circuit_breaker'):
            integration._circuit_breaker.record_success()

        await board_ws.broadcast("autodarts_status", {
            "board_id": board_id,
            "status": "running",
            "message": "Autodarts game automation active"
        })

        # Step 2: Wait for game end (polls Autodarts page)
        logger.info(f"[Autodarts] Waiting for game end on board {board_id}...")

        async def on_status(status):
            logger.info(f"[Autodarts] Status update for board {board_id}: running={status.is_running}, finished={status.is_finished}")

        game_status = await integration.wait_for_game_end(
            timeout_seconds=7200,
            on_status_update=on_status
        )

        logger.info(f"[Autodarts] Game ended for board {board_id}: winner={game_status.winner}, error={game_status.error}")

        # Step 3: Auto-end the game in the database
        if game_status.is_finished:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    res = await db.execute(select(Board).where(Board.board_id == board_id))
                    board = res.scalar_one_or_none()
                    if board:
                        session = await get_active_session_for_board(db, board.id)
                        if session:
                            logger.info(f"[Autodarts] Auto-ending game for board {board_id} via DB update")
                            await _end_game_internal(
                                db, board, session, board_id,
                                winner=game_status.winner,
                                scores=game_status.scores
                            )

    except AutodartsError as e:
        logger.error(f"[Autodarts] AutodartsError for board {board_id}: {e} (screenshot={e.screenshot_path})")
        if hasattr(integration, '_circuit_breaker'):
            integration._circuit_breaker.record_failure()
        await board_ws.broadcast("autodarts_status", {
            "board_id": board_id,
            "status": "error",
            "message": str(e)
        })
    except Exception as e:
        logger.error(f"[Autodarts] Unexpected error for board {board_id}: {e}", exc_info=True)
        if hasattr(integration, '_circuit_breaker'):
            integration._circuit_breaker.record_failure()
        await board_ws.broadcast("autodarts_status", {
            "board_id": board_id,
            "status": "error",
            "message": f"Unexpected error: {e}"
        })


@router.post("/kiosk/{board_id}/start-game")
async def kiosk_start_game(board_id: str, data: StartGameRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Called when customer starts a game on kiosk"""
    logger.info(f"[StartGame] Endpoint called: board={board_id}, game_type={data.game_type}, players={data.players}")

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        logger.warning(f"[StartGame] Board not found: {board_id}")
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        logger.warning(f"[StartGame] No active session for board {board_id}")
        raise HTTPException(status_code=400, detail="No active session - board must be unlocked first")

    if session.pricing_mode == PricingMode.PER_GAME.value:
        if session.credits_remaining <= 0:
            logger.warning(f"[StartGame] No credits remaining for board {board_id}")
            raise HTTPException(status_code=400, detail="No credits remaining")

    if session.pricing_mode == PricingMode.PER_TIME.value:
        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
            logger.warning(f"[StartGame] Session time expired for board {board_id}")
            raise HTTPException(status_code=400, detail="Session time expired")

    session.game_type = data.game_type
    session.players = data.players
    session.players_count = len(data.players)
    board.status = BoardStatus.IN_GAME.value

    await db.flush()

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": "in_game", "game_type": data.game_type})
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "start"})

    # Trigger Autodarts automation if board has a target URL configured
    autodarts_triggered = False
    if board.autodarts_target_url:
        logger.info(f"[StartGame] Board {board_id} has autodarts_target_url: {board.autodarts_target_url}")
        config = GameConfig(
            game_type=data.game_type,
            players=data.players,
            board_id=board_id,
            session_id=session.id,
            autodarts_url=board.autodarts_target_url
        )
        background_tasks.add_task(_run_autodarts_game, board_id, config)
        autodarts_triggered = True
        logger.info(f"[StartGame] Autodarts background task queued for board {board_id}")
    else:
        logger.info(f"[StartGame] No autodarts_target_url for board {board_id} — manual game mode")

    return {
        "message": "Game started",
        "game_type": data.game_type,
        "players": data.players,
        "session_id": session.id,
        "autodarts_triggered": autodarts_triggered
    }


async def _end_game_internal(
    db: AsyncSession, board: Board, session: Session, board_id: str,
    winner: Optional[str] = None, scores: Optional[dict] = None
):
    """Internal end-game logic shared by the endpoint and Autodarts background task."""
    logger.info(f"[EndGame] Internal end-game: board={board_id}, winner={winner}")

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
    final_winner = (winner if winner else
                    session.players[0] if session.players else None)

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

    # Update Player stats (guest + registered)
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

    await board_ws.broadcast("board_status", {"board_id": board_id, "status": board.status})
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "win" if final_winner else "checkout"})

    return {
        "message": "Game ended",
        "should_lock": should_lock,
        "credits_remaining": session.credits_remaining,
        "board_status": board.status,
        "match_token": token,
        "match_url": f"/match/{token}",
    }


@router.post("/kiosk/{board_id}/end-game")
async def kiosk_end_game(board_id: str, data: Optional[EndGameRequest] = None, db: AsyncSession = Depends(get_db)):
    """Called when a game ends (from autodarts integration or manual)"""
    logger.info(f"[EndGame] Endpoint called: board={board_id}, data={data}")

    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        logger.warning(f"[EndGame] Board not found: {board_id}")
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        logger.info(f"[EndGame] No active session for board {board_id}")
        return {"message": "No active session"}

    winner = data.winner if data and data.winner else None
    scores = data.scores if data and data.scores else None

    return await _end_game_internal(db, board, session, board_id, winner=winner, scores=scores)


@router.post("/kiosk/{board_id}/call-staff")
async def kiosk_call_staff(board_id: str, db: AsyncSession = Depends(get_db)):
    """Customer requests staff assistance"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    await log_audit(db, None, "call_staff", "board", board.id, {"board_id": board_id})
    return {"message": "Staff notified", "board_id": board_id}


class SoundTrigger(BaseModel):
    event: str  # start, one_eighty, checkout, bust, win

@router.post("/kiosk/{board_id}/sound")
async def kiosk_trigger_sound(board_id: str, data: SoundTrigger):
    """Trigger a sound event on a kiosk (e.g. from Autodarts integration)."""
    valid_events = {"start", "one_eighty", "checkout", "bust", "win"}
    if data.event not in valid_events:
        raise HTTPException(status_code=400, detail=f"Invalid event. Must be one of: {valid_events}")
    await board_ws.broadcast("sound_event", {"board_id": board_id, "event": data.event})
    return {"message": f"Sound '{data.event}' triggered", "board_id": board_id}



@router.get("/kiosk/{board_id}/autodarts-status")
async def get_autodarts_status(board_id: str):
    """Get the current Autodarts integration status for a board."""
    if board_id not in _autodarts_instances:
        return {
            "board_id": board_id,
            "integration_active": False,
            "circuit_state": "unknown",
            "manual_mode": False,
            "message": "No integration instance (not yet triggered)"
        }
    integration = _autodarts_instances[board_id]
    circuit_state = "unknown"
    manual_mode = False
    if hasattr(integration, 'circuit_state'):
        circuit_state = integration.circuit_state.value
    if hasattr(integration, 'is_manual_mode'):
        manual_mode = integration.is_manual_mode
    return {
        "board_id": board_id,
        "integration_active": True,
        "circuit_state": circuit_state,
        "manual_mode": manual_mode,
    }


@router.post("/kiosk/{board_id}/autodarts-reset")
async def reset_autodarts(board_id: str):
    """Reset the Autodarts circuit breaker and manual mode for a board."""
    if board_id in _autodarts_instances:
        integration = _autodarts_instances[board_id]
        if hasattr(integration, 'disable_manual_mode'):
            integration.disable_manual_mode()
        if hasattr(integration, '_circuit_breaker'):
            integration._circuit_breaker.reset()
        logger.info(f"[Autodarts] Reset circuit breaker and manual mode for board {board_id}")
    return {"message": "Autodarts integration reset", "board_id": board_id}
