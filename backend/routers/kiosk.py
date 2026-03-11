"""
Kiosk Action Routes — Observer MVP (v2.2.0)

Central finalization via finalize_match(board_id, trigger):
  - Single entry point for ALL match-end scenarios (WS, manual, abort)
  - Strict order: guard → credit → lock decision → close observer → restore kiosk
  - Observer/kiosk cleanup ONLY when session ends (should_lock or manual)
  - Credit deduction via _should_deduct_credit (centralized policy)
  - Kiosk window (WindowManager) and Autodarts browser (Playwright) are SEPARATE
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

# Guard against concurrent finalize_match calls per board
_finalizing: set = set()


# =====================================================================
# Centralized credit policy
# =====================================================================

def _should_deduct_credit(trigger: str) -> bool:
    """
    Central credit deduction policy.
    Returns True if a credit should be consumed for this trigger.

    - "finished": Game completed normally → deduct
    - "manual":   Staff stopped the game  → deduct
    - "aborted":  Game cancelled/left     → FREE (no deduction)
    - anything else (e.g. stale triggers) → no deduction
    """
    return trigger in ("finished", "manual")


# =====================================================================
# Central finalization
# =====================================================================

async def finalize_match(board_id: str, trigger: str,
                         winner: str = None, scores: dict = None) -> dict:
    """
    Central match finalization. Called for ALL end scenarios.

    trigger: "finished" | "aborted" | "manual"

    Steps (strict order):
      1. [GUARD]    Idempotency — skip if already finalizing this board
      2. [CREDIT]   Deduct credit (only if _should_deduct_credit)
      3. [LOCK]     Lock board if credits exhausted or time expired
      4. [OBSERVER] Close Autodarts browser — ONLY if session ends (should_lock or manual)
      5. [KIOSK]    Restore kiosk window  — ONLY if session ends (should_lock or manual)
      6. [BROADCAST] Notify all clients
      7. [CLEANUP]  Release finalizing guard
    """
    # ── Step 1: Idempotency guard ──
    if board_id in _finalizing:
        logger.info(f"[FINALIZE] SKIPPED board={board_id} (already finalizing)")
        return {"should_lock": False, "credits_remaining": -1, "board_status": "unknown"}
    _finalizing.add(board_id)

    logger.info(f"[FINALIZE] ===== START board={board_id} trigger={trigger} =====")

    should_lock = False
    credits_remaining = 0
    board_status = "unlocked"
    match_token = None
    # Whether to tear down the observer + kiosk (only on session end)
    should_teardown = (trigger == "manual")

    try:
        # ── Steps 2-3: DB operations (credit + lock decision) ──
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    result = await db.execute(select(Board).where(Board.board_id == board_id))
                    board = result.scalar_one_or_none()
                    if not board:
                        logger.error(f"[FINALIZE] board_not_found: {board_id}")
                        return {"should_lock": False, "credits_remaining": 0, "board_status": "unknown"}

                    if board.status == BoardStatus.LOCKED.value:
                        logger.info(f"[FINALIZE] board already locked, nothing to do board={board_id}")
                        return {"should_lock": True, "credits_remaining": 0, "board_status": "locked"}

                    session = await get_active_session_for_board(db, board.id)
                    if not session:
                        logger.info(f"[FINALIZE] no active session board={board_id}")
                        return {"should_lock": False, "credits_remaining": 0, "board_status": board.status}

                    # ── Step 2: Credit deduction ──
                    credits_before = session.credits_remaining
                    if _should_deduct_credit(trigger):
                        if session.pricing_mode == PricingMode.PER_GAME.value:
                            session.credits_remaining = max(0, session.credits_remaining - 1)
                            logger.info(
                                f"[FINALIZE] CREDIT_DEDUCTED: {credits_before} -> "
                                f"{session.credits_remaining} (trigger={trigger}, mode=per_game)"
                            )
                        else:
                            logger.info(
                                f"[FINALIZE] CREDIT_SKIP: mode={session.pricing_mode} "
                                f"(only per_game deducts on match end)"
                            )
                    else:
                        logger.info(
                            f"[FINALIZE] CREDIT_FREE: trigger={trigger} "
                            f"(no deduction for this trigger)"
                        )
                    credits_remaining = session.credits_remaining

                    # ── Step 3: Lock decision ──
                    if session.pricing_mode == PricingMode.PER_GAME.value:
                        should_lock = session.credits_remaining <= 0
                    if session.pricing_mode == PricingMode.PER_TIME.value:
                        if session.expires_at and datetime.now(timezone.utc) >= session.expires_at:
                            should_lock = True

                    # Manual stop always tears down, lock additionally if no credits
                    if should_lock:
                        should_teardown = True

                    logger.info(
                        f"[FINALIZE] LOCK_DECISION: should_lock={should_lock}, "
                        f"should_teardown={should_teardown}, "
                        f"credits={credits_remaining}, trigger={trigger}"
                    )

                    # ── Match result (finished/manual only) ──
                    if _should_deduct_credit(trigger):
                        match_sharing = await get_or_create_setting(db, "match_sharing", DEFAULT_MATCH_SHARING)
                        if match_sharing.get("enabled", False):
                            match_token = secrets.token_hex(16)
                            duration = None
                            if session.started_at:
                                started = session.started_at
                                if started.tzinfo is None:
                                    started = started.replace(tzinfo=timezone.utc)
                                duration = int((datetime.now(timezone.utc) - started).total_seconds())
                            match = MatchResult(
                                public_token=match_token,
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

                        # Player stats
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

                    # ── Apply lock or return to unlocked ──
                    if should_lock:
                        session.status = SessionStatus.FINISHED.value
                        session.ended_at = datetime.now(timezone.utc)
                        if trigger == "aborted":
                            session.ended_reason = "last_game_aborted"
                        elif trigger == "manual":
                            session.ended_reason = "manual_stop"
                        elif session.pricing_mode == PricingMode.PER_TIME.value:
                            session.ended_reason = "time_expired"
                        else:
                            session.ended_reason = "credits_exhausted"
                        board.status = BoardStatus.LOCKED.value
                        board_status = "locked"
                        logger.info(f"[FINALIZE] SESSION_CLOSED: reason={session.ended_reason}")
                    elif trigger == "manual":
                        # Manual stop without lock: end session but keep board unlocked
                        session.status = SessionStatus.FINISHED.value
                        session.ended_at = datetime.now(timezone.utc)
                        session.ended_reason = "manual_stop"
                        board.status = BoardStatus.LOCKED.value
                        board_status = "locked"
                        should_lock = True
                        logger.info(f"[FINALIZE] SESSION_CLOSED: manual stop (board locked)")
                    else:
                        board.status = BoardStatus.UNLOCKED.value
                        board_status = "unlocked"
                        logger.info(f"[FINALIZE] BOARD_STAYS_UNLOCKED: credits={credits_remaining}")

                    await db.flush()

        except Exception as e:
            logger.error(f"[FINALIZE] DB_ERROR: {e}", exc_info=True)

        # ── Step 4: Close Autodarts observer (ONLY on session teardown) ──
        if should_teardown:
            try:
                logger.info(f"[FINALIZE] OBSERVER_CLOSE: board={board_id} (teardown=True)")
                await observer_manager.close(board_id)
                logger.info(f"[FINALIZE] OBSERVER_CLOSED_OK: board={board_id}")
            except Exception as e:
                logger.error(f"[FINALIZE] OBSERVER_CLOSE_FAILED: {e}")
        else:
            logger.info(
                f"[FINALIZE] OBSERVER_KEPT_ALIVE: board={board_id} "
                f"(credits={credits_remaining}, awaiting next game)"
            )

        # ── Step 5: Restore kiosk window (ONLY on session teardown) ──
        if should_teardown:
            try:
                from backend.services.window_manager import kill_overlay_process
                await kill_overlay_process()
                logger.info(f"[FINALIZE] OVERLAY_KILLED: board={board_id}")
            except Exception as e:
                logger.warning(f"[FINALIZE] OVERLAY_KILL_FAILED: {e}")

            try:
                from backend.services.window_manager import restore_kiosk_window
                await asyncio.sleep(0.5)
                await restore_kiosk_window()
                logger.info(f"[FINALIZE] KIOSK_RESTORED: board={board_id}")
            except Exception as e:
                logger.warning(f"[FINALIZE] KIOSK_RESTORE_FAILED: {e}")

        # ── Step 6: Broadcasts ──
        try:
            if _should_deduct_credit(trigger):
                await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "checkout"})

            await board_ws.broadcast("board_status", {"board_id": board_id, "status": board_status})

            if not should_lock:
                await board_ws.broadcast("credit_update", {
                    "board_id": board_id,
                    "credits_remaining": credits_remaining,
                    "is_last_game": credits_remaining <= 1,
                })
        except Exception as e:
            logger.warning(f"[FINALIZE] BROADCAST_ERROR: {e}")

    finally:
        # ── Step 7: ALWAYS release the guard ──
        _finalizing.discard(board_id)

    logger.info(
        f"[FINALIZE] ===== END board={board_id} trigger={trigger} "
        f"should_lock={should_lock} should_teardown={should_teardown} "
        f"credits={credits_remaining} ====="
    )

    return {
        "should_lock": should_lock,
        "credits_remaining": credits_remaining,
        "board_status": board_status,
        "match_token": match_token,
    }


# =====================================================================
# Observer callbacks (thin wrappers around finalize_match)
# =====================================================================

async def _on_game_started(board_id: str):
    """Observer detected match start. Set board to IN_GAME."""
    logger.info(f"[Observer->Kiosk] === GAME STARTED === board={board_id}")
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(select(Board).where(Board.board_id == board_id))
                board = result.scalar_one_or_none()
                if board:
                    board.status = BoardStatus.IN_GAME.value
        await board_ws.broadcast("board_status", {"board_id": board_id, "status": "in_game"})
        await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "start"})
    except Exception as e:
        logger.error(f"[Observer->Kiosk] Error on game start: {e}", exc_info=True)


async def _on_game_ended(board_id: str, reason: str):
    """
    Observer detected match end. Schedule centralized finalization.
    Uses create_task so the observe loop can continue shutting down cleanly.
    """
    logger.info(f"[Observer->Kiosk] === GAME ENDED === trigger={reason}, scheduling finalize_match")
    asyncio.create_task(finalize_match(board_id, reason))


# =====================================================================
# Observer lifecycle
# =====================================================================

async def start_observer_for_board(board_id: str, autodarts_url: str):
    if AUTODARTS_MODE != 'observer':
        logger.info(f"[Kiosk] AUTODARTS_MODE={AUTODARTS_MODE}, skipping observer")
        return
    if not autodarts_url:
        logger.warning(f"[Kiosk] No autodarts_url for {board_id}, skipping observer start")
        return

    headless = os.environ.get('AUTODARTS_HEADLESS', 'false').lower() == 'true'
    logger.info("[Kiosk] === Observer Start Request ===")
    logger.info(f"[Kiosk]   board_id: {board_id}")
    logger.info(f"[Kiosk]   autodarts_url: {autodarts_url}")
    logger.info(f"[Kiosk]   headless: {headless}")
    logger.info(f"[Kiosk]   AUTODARTS_MODE: {AUTODARTS_MODE}")

    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_ended=_on_game_ended,
        headless=headless,
    )

    status = observer_manager.get_status(board_id)
    logger.info(f"[Kiosk] Observer post-start status: state={status['state']}, browser_open={status['browser_open']}")


async def stop_observer_for_board(board_id: str):
    logger.info(f"[Kiosk] Stopping observer for {board_id} (closing Autodarts browser)")
    await observer_manager.close(board_id)
    logger.info(f"[Kiosk] Observer stopped for {board_id}")


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
    """Manual end-game trigger (staff action). Uses central finalize_match path."""
    logger.info(f"[EndGame] Manual trigger: board={board_id}")

    result_db = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result_db.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    session = await get_active_session_for_board(db, board.id)
    if not session:
        return {"message": "No active session"}

    # Central finalization — same path as observer match-end
    winner = data.winner if data and data.winner else None
    scores = data.scores if data and data.scores else None
    result = await finalize_match(board_id, "manual", winner=winner, scores=scores)

    return {
        "message": "Game ended",
        **result,
        "match_sharing_enabled": (await get_or_create_setting(db, "match_sharing", DEFAULT_MATCH_SHARING)).get("enabled", False),
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


@router.get("/kiosk/{board_id}/ws-diagnostic")
async def get_ws_diagnostic(board_id: str):
    """
    Diagnostic endpoint: returns captured WebSocket frames and event state
    for debugging match-end detection. Shows the raw event stream that
    the observer uses to determine game state.
    """
    obs = observer_manager.get(board_id)
    if not obs:
        return {
            "board_id": board_id,
            "observer_active": False,
            "ws_state": None,
            "captured_frames": [],
            "note": "No active observer for this board",
        }

    ws = obs._ws_state
    frames = list(obs._ws_frames)

    return {
        "board_id": board_id,
        "observer_active": obs.is_open,
        "stable_state": obs._stable_state.value,
        "debounce": {
            "exit_polls": obs._exit_polls,
            "saw_finished": obs._exit_saw_finished,
        },
        "ws_state": {
            "match_active": ws.match_active,
            "match_finished": ws.match_finished,
            "winner_detected": ws.winner_detected,
            "last_match_state": ws.last_match_state,
            "last_game_event": ws.last_game_event,
            "last_match_id": ws.last_match_id,
            "frames_received": ws.frames_received,
            "match_relevant_frames": ws.match_relevant_frames,
            "finish_trigger": ws.finish_trigger,
        },
        "captured_frames_count": len(frames),
        "captured_frames": [f.to_dict() for f in frames[-30:]],  # Last 30 frames
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

    is_last = False
    if session.pricing_mode == PricingMode.PER_GAME.value:
        is_last = (session.credits_remaining or 0) <= 0

    # Include upsell texts for last-game display (credit mode only)
    upsell_message = ""
    upsell_pricing = ""
    if is_last and session.pricing_mode != PricingMode.PER_TIME.value:
        from backend.models import DEFAULT_KIOSK_TEXTS
        kiosk_texts = await get_or_create_setting(db, "kiosk_texts", DEFAULT_KIOSK_TEXTS)
        upsell_message = kiosk_texts.get("upsell_message", "")
        upsell_pricing = kiosk_texts.get("upsell_pricing", "")

    return {
        "visible": True,
        "board_name": board.name,
        "board_status": board.status,
        "pricing_mode": session.pricing_mode,
        "credits_remaining": session.credits_remaining,
        "time_remaining_seconds": time_remaining,
        "observer_state": observer_manager.get_status(board_id).get("state"),
        "is_last_game": is_last,
        "session_id": session.id,
        "upsell_message": upsell_message,
        "upsell_pricing": upsell_pricing,
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
    """Simulate observer detecting idle->in_game (for testing only)."""
    await _on_game_started(board_id)
    return {"message": f"Simulated game start on {board_id}"}


@router.post("/kiosk/{board_id}/simulate-game-end")
async def simulate_game_end(board_id: str, admin: User = Depends(require_admin)):
    """Simulate observer detecting in_game->finished (for testing only)."""
    await _on_game_ended(board_id, "finished")
    return {"message": f"Simulated game end on {board_id}"}


@router.post("/kiosk/{board_id}/simulate-game-abort")
async def simulate_game_abort(board_id: str, admin: User = Depends(require_admin)):
    """Simulate observer detecting in_game->idle (game aborted, for testing only)."""
    await _on_game_ended(board_id, "aborted")
    return {"message": f"Simulated game abort on {board_id}"}
