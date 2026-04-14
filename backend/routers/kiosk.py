"""
Kiosk Action Routes — local authoritative session lifecycle.

Central finalization via finalize_match(board_id, trigger):
  - Single entry point for ALL match-end scenarios
  - Observer teardown ONLY when session capacity is exhausted
  - Observer stays alive when more local capacity remains
  - Authoritative Autodarts WS finish signals decide billing/finalization
  - Per-game billing happens on authoritative finish/manual stop
  - Per-player billing happens once on authoritative start-of-play
  - Abort/delete never deducts by itself
  - return_to_kiosk_ui() is still guaranteed on true session end
  - Timeout protection prevents hanging finalization
"""
import asyncio
import os
import secrets
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database import get_db, AsyncSessionLocal
from backend.models import Board, Session, MatchResult, Player, User, BoardStatus, SessionStatus, PricingMode, Settings, DEFAULT_AUTODARTS_TRIGGERS
from backend.schemas import StartGameRequest, EndGameRequest
from backend.dependencies import get_active_session_for_board, log_audit, get_or_create_setting, require_admin
from backend.services.ws_manager import board_ws
from backend.services.autodarts_observer import observer_manager, ObserverState
from backend.services.autodarts_triggers import build_trigger_policy
from backend.services.session_pricing import (
    apply_authoritative_start_charge,
    finalize_session_consumption,
    should_record_match_completion,
)

import logging
logger = logging.getLogger(__name__)

AUTODARTS_MODE = os.environ.get('AUTODARTS_MODE', 'observer')
FINALIZE_DELAY_FINISHED = int(os.environ.get('FINALIZE_DELAY_FINISHED', '4'))
FINALIZE_TIMEOUT = int(os.environ.get('FINALIZE_TIMEOUT_SECONDS', '15'))

DEFAULT_MATCH_SHARING = {"enabled": False, "qr_timeout": 60}

router = APIRouter()

# ── Idempotency guards (module-level, per board_id) ──
_finalizing: set = set()          # True WHILE finalize_match is running
_finalized: dict = {}             # True AFTER finalize completed (until next game start)
_last_finalized_match: dict = {}  # board_id -> match_id (prevents duplicate credit deduction)


# =====================================================================
# Centralized credit policy
# =====================================================================

def _should_deduct_credit(trigger: str) -> bool:
    """Compatibility helper for finalize-time credit deductions.

    Authoritative finishes and manual staff ends consume a finalize-time
    credit. Abort/delete only consume here after an already-confirmed match
    start (board already in-game); per-player charging still happens at
    authoritative start-of-play instead.
    """
    return trigger in {"finished", "manual", "match_end_state_finished", "match_end_game_finished"}


# =====================================================================
# return_to_kiosk_ui — ALWAYS called after finalize
# =====================================================================

async def return_to_kiosk_ui(board_id: str, should_lock: bool):
    """
    Bring the local Kiosk UI back to the foreground after a game ends.
    Called ALWAYS — whether locked or unlocked.
    Must be the LAST window operation so DartsKiosk ends up on top.
    """
    logger.info(f"[KIOSK_UI] return_to_kiosk_ui start board={board_id} should_lock={should_lock}")

    # Kill any leftover overlay process
    try:
        from backend.services.window_manager import kill_overlay_process
        await kill_overlay_process()
    except Exception as e:
        logger.warning(f"[KIOSK_UI] overlay kill failed: {e}")

    # First pass: restore/show the kiosk window
    try:
        from backend.services.window_manager import restore_kiosk_window
        await asyncio.sleep(0.3)
        await restore_kiosk_window()
        logger.info("[KIOSK_UI] kiosk window restored (first pass)")
    except Exception as e:
        logger.warning(f"[KIOSK_UI] kiosk window restore failed: {e}")

    # Second pass after 400ms: hard foreground enforcement
    try:
        from backend.services.window_manager import force_kiosk_foreground
        await asyncio.sleep(0.4)
        await force_kiosk_foreground()
        logger.info("[KIOSK_UI] kiosk foreground enforced (second pass)")
    except Exception as e:
        logger.warning(f"[KIOSK_UI] force_kiosk_foreground failed: {e}")

    # Broadcast state refresh to frontend
    try:
        status = "locked" if should_lock else "unlocked"
        await board_ws.broadcast("board_status", {"board_id": board_id, "status": status})
        await board_ws.broadcast("kiosk_refresh", {
            "board_id": board_id,
            "should_lock": should_lock,
            "action": "return_to_kiosk",
        })
        logger.info("[KIOSK_UI] overlay state refreshed")
    except Exception as e:
        logger.warning(f"[KIOSK_UI] broadcast failed: {e}")

    logger.info("[KIOSK_UI] return_to_kiosk_ui done")


async def _show_pending_credit_gate(board_id: str):
    """Bring the kiosk back on top so the pending-credit overlay is actually visible."""
    logger.info(f"[KIOSK_UI] show_pending_credit_gate start board={board_id}")
    try:
        from backend.services.window_manager import minimize_observer_window, restore_kiosk_window, force_kiosk_foreground
        await minimize_observer_window()
        await asyncio.sleep(0.2)
        await restore_kiosk_window()
        await asyncio.sleep(0.2)
        await force_kiosk_foreground()
    except Exception as e:
        logger.warning(f"[KIOSK_UI] show_pending_credit_gate failed: {e}")


async def run_terminal_session_cleanup(board_id: str, should_lock: bool = True, close_reason: str = "session_end"):
    """Shared terminal session cleanup for non-keep-alive endings.

    Used by central finalize and scheduler-driven terminations so observer teardown,
    kiosk restore, and websocket refresh semantics stay aligned.
    """
    logger.info(
        f"[SESSION] terminal_cleanup start board={board_id} "
        f"should_lock={should_lock} close_reason={close_reason}"
    )
    try:
        logger.info(f"[AUTODARTS] closing observer board={board_id} ({close_reason})")
        observer_manager.set_desired_state(board_id, "stopped")
        await asyncio.wait_for(
            observer_manager.close(board_id, reason=close_reason),
            timeout=10.0,
        )
        logger.info(f"[AUTODARTS] observer closed OK board={board_id} reason={close_reason}")
    except asyncio.TimeoutError:
        logger.error(f"[AUTODARTS] observer close TIMEOUT board={board_id} reason={close_reason}")
    except Exception as e:
        logger.error(f"[AUTODARTS] observer close failed board={board_id} reason={close_reason}: {e}")
    finally:
        try:
            logger.info(f"[KIOSK_UI] terminal_cleanup restore start board={board_id} should_lock={should_lock}")
            await return_to_kiosk_ui(board_id, should_lock)
            logger.info(f"[KIOSK_UI] terminal_cleanup restore done board={board_id}")
        except Exception as e:
            logger.error(f"[KIOSK_UI] terminal_cleanup restore failed board={board_id}: {e}", exc_info=True)


async def _resume_autodarts_after_pending_credit_gate(board_id: str):
    """Once credits are sufficient again, hand control back to Autodarts."""
    logger.info(f"[KIOSK_UI] resume_autodarts_after_pending_credit_gate start board={board_id}")
    try:
        from backend.services.window_manager import ensure_autodarts_foreground
        await ensure_autodarts_foreground()
    except Exception as e:
        logger.warning(f"[KIOSK_UI] resume_autodarts_after_pending_credit_gate failed: {e}")


def _observer_match_context(board_id: str) -> dict:
    obs = observer_manager.get(board_id)
    if obs and hasattr(obs, "export_match_context"):
        try:
            return obs.export_match_context() or {}
        except Exception as exc:
            logger.warning(f"[Observer->Kiosk] export_match_context failed board={board_id}: {exc}")
    return {}


def _normalize_game_family(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    compact = raw.lower().replace("-", "").replace("_", "").replace(" ", "")
    if compact == "x01":
        return "x01"
    if compact.isdigit() and compact.endswith("01"):
        return "x01"
    if compact == "cricket":
        return "cricket"
    if compact == "gotcha":
        return "gotcha"
    if compact == "bulloff":
        return "bulloff"
    return compact


def _observer_variant_mismatch(board_id: str, session_game_type: Optional[str]) -> tuple[bool, Optional[str], Optional[str]]:
    observer_context = _observer_match_context(board_id)
    observed_variant = observer_context.get("variant")
    expected_family = _normalize_game_family(session_game_type)
    observed_family = _normalize_game_family(observed_variant)
    preliminary_variant = observed_family in {"gotcha", "bulloff"}
    mismatch = bool(preliminary_variant or (expected_family and observed_family and expected_family != observed_family))
    return mismatch, observed_variant, expected_family


def _preliminary_round_skip_result(board_id: str, reason: str, observed_variant: Optional[str]) -> dict:
    return {
        "should_lock": False,
        "should_teardown": False,
        "credits_remaining": 0,
        "board_status": "unlocked",
        "skipped": True,
        "skip_reason": reason,
        "observed_variant": observed_variant,
        "board_id": board_id,
    }


def _session_state_payload(board_id: str, board_status: str, session, charge=None) -> dict:
    payload = {
        "board_id": board_id,
        "board_status": board_status,
        "pricing_mode": getattr(session, "pricing_mode", None),
        "credits_remaining": int(getattr(session, "credits_remaining", 0) or 0),
        "credits_total": int(getattr(session, "credits_total", 0) or 0),
        "players_count": int(getattr(session, "players_count", 0) or 0),
        "players": list(getattr(session, "players", None) or []),
        "pending_credit_gate": board_status == BoardStatus.BLOCKED_PENDING.value,
    }
    if charge is not None:
        required_units = int(getattr(charge, "required_units", 0) or 0)
        payload.update(
            {
                "required_units": required_units,
                "charged_units": int(getattr(charge, "units", 0) or 0),
                "credits_shortage": max(0, required_units - payload["credits_remaining"]),
                "start_gate_reason": getattr(charge, "reason", None),
            }
        )
    return payload


# =====================================================================
# Central finalization (v2.5.0)
# =====================================================================

async def _finalize_match_inner(board_id: str, trigger: str,
                                winner: str = None, scores: dict = None) -> dict:
    """
    Inner finalize logic. Called via timeout wrapper.

    Steps:
      1.  [GUARD]     Idempotency check
      2.  [CREDIT]    Deduct credit exactly once
      3.  [DELAY]     ONLY for trigger="finished" (player sees result)
      4.  [OBSERVER]  Close browser ONLY if should_teardown (credits=0)
      5.  [LOCK]      Lock board if remaining_credits <= 0
      6.  [KIOSK_UI]  GUARANTEED via finally (even on partial failure)
      7.  [BROADCAST] Notify clients
      8.  [CLEANUP]   Set finalized status
    """
    # ── Step 1: Idempotency guard ──
    if board_id in _finalizing:
        logger.info(f"[SESSION] finalize skipped (already running) board={board_id}")
        return {"should_lock": False, "should_teardown": False,
                "credits_remaining": 0, "board_status": "unknown"}

    if _finalized.get(board_id) and trigger != "manual":
        # v3.3.1-hotfix2: Verify board is ACTUALLY locked before skipping.
        # A stale _finalized flag from a partial failure must not block retry.
        _board_verified_locked = False
        _session_verified_ended = False
        try:
            async with AsyncSessionLocal() as _vdb:
                _vr = await _vdb.execute(select(Board).where(Board.board_id == board_id))
                _vboard = _vr.scalar_one_or_none()
                if _vboard and _vboard.status == BoardStatus.LOCKED.value:
                    _board_verified_locked = True
                if _vboard:
                    _vsession = await get_active_session_for_board(_vdb, _vboard.id)
                    _session_verified_ended = _vsession is None
                else:
                    _session_verified_ended = True
        except Exception as _ve:
            logger.warning(f"[SESSION] finalize verification DB error: {_ve}")

        logger.info(
            f"[SESSION] finalize_state_before_decision board={board_id} trigger={trigger} "
            f"_finalized=True board_locked={_board_verified_locked} "
            f"session_ended={_session_verified_ended}"
        )

        if _board_verified_locked and _session_verified_ended:
            logger.info(
                f"[SESSION] finalize_skip reason=already_committed board={board_id} "
                f"trigger={trigger} board_status=locked session_ended=True"
            )
            return {"should_lock": True, "should_teardown": True,
                    "credits_remaining": 0, "board_status": "locked"}
        else:
            logger.warning(
                f"[SESSION] stale_finalized_flag_cleared board={board_id} trigger={trigger} "
                f"board_locked={_board_verified_locked} session_ended={_session_verified_ended} "
                f"reason=finalize_resume_incomplete_commit"
            )
            _finalized.pop(board_id, None)

    # ── Duplicate match-ID guard (defense-in-depth) ──
    obs = observer_manager.get(board_id)
    current_match_id = obs._ws_state.last_match_id if obs and hasattr(obs, '_ws_state') else None
    if current_match_id and _last_finalized_match.get(board_id) == current_match_id and trigger != "manual":
        logger.info(f"[SESSION] SKIP_DUPLICATE_FINALIZE match_id={current_match_id} board={board_id}")
        return {"should_lock": False, "should_teardown": False,
                "credits_remaining": 0, "board_status": "unknown"}

    _finalizing.add(board_id)
    import time as _t
    _t0 = _t.monotonic()
    logger.info(f"[SESSION] finalize start board={board_id} trigger={trigger}")

    should_lock = False
    should_teardown = False
    credits_remaining = 0
    board_status = "unlocked"
    match_token = None
    db_committed = False

    try:
        # ── Step 2: DB operations (credit + lock decision) ──
        logger.info(f"[SESSION] db_commit_started board={board_id} trigger={trigger}")
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    result = await db.execute(select(Board).where(Board.board_id == board_id))
                    board = result.scalar_one_or_none()
                    if not board:
                        logger.error(f"[SESSION] board_not_found: {board_id}")
                        return {"should_lock": False, "should_teardown": True,
                                "credits_remaining": 0, "board_status": "unknown"}

                    if board.status == BoardStatus.LOCKED.value:
                        logger.info(f"[SESSION] board already locked board={board_id}")
                        should_lock = True
                        should_teardown = True
                        return {"should_lock": True, "should_teardown": True,
                                "credits_remaining": 0, "board_status": "locked"}

                    session = await get_active_session_for_board(db, board.id)
                    if not session:
                        logger.info(f"[SESSION] no active session board={board_id}")
                        should_teardown = True
                        return {"should_lock": False, "should_teardown": True,
                                "credits_remaining": 0, "board_status": board.status}

                    # ── Finalize-time capacity + billing ──
                    finalize_decision = finalize_session_consumption(
                        session,
                        trigger,
                        board_status=board.status,
                    )
                    credits_before = finalize_decision.credits_before
                    credit_after = finalize_decision.credits_after
                    credits_remaining = credit_after
                    should_lock = finalize_decision.should_lock
                    should_teardown = finalize_decision.should_teardown

                    # ── Store match_id for duplicate prevention ──
                    if current_match_id:
                        _last_finalized_match[board_id] = current_match_id

                    obs_for_log = observer_manager.get(board_id)
                    lc_log = obs_for_log.lifecycle_state.value if obs_for_log else "none"
                    desired_log = observer_manager.get_desired_state(board_id)
                    branch = "session_end" if should_lock else "keep_alive"
                    logger.info(
                        f"[SESSION] finalize decision board={board_id} "
                        f"trigger={trigger} pricing_mode={session.pricing_mode} "
                        f"credit_before={credits_before} credit_after={credit_after} "
                        f"charge_applied={finalize_decision.charge_applied} consume_units={finalize_decision.consume_units} "
                        f"has_remaining_capacity={finalize_decision.has_remaining_capacity} "
                        f"should_lock={should_lock} should_teardown={should_teardown} "
                        f"branch={branch} desired_state={desired_log} lifecycle={lc_log}"
                    )
                    if should_lock:
                        logger.info(f"[SESSION] lock_enforced board={board_id} reason=no_remaining_capacity")
                    else:
                        logger.info(f"[SESSION] keep_alive_allowed board={board_id} reason=remaining_capacity")

                    logger.info(
                        f"[SESSION] finalize committed board={board_id} "
                        f"credits={credit_after} should_lock={should_lock} should_teardown={should_teardown}"
                    )

                    # ── Match result + player stats ──
                    if should_record_match_completion(trigger):
                        match_sharing = await get_or_create_setting(db, "match_sharing", DEFAULT_MATCH_SHARING)
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
                        logger.info(
                            f"[STATS] local_match_result_saved board={board.board_id} "
                            f"players={len(session.players or [])} should_lock={should_lock} "
                            f"match_sharing_enabled={bool(match_sharing.get('enabled', False))}"
                        )

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

                    # ── Apply lock or stay unlocked ──
                    if should_lock:
                        session.status = SessionStatus.FINISHED.value
                        session.ended_at = datetime.now(timezone.utc)
                        if trigger in ("aborted", "match_abort_delete"):
                            session.ended_reason = "last_game_aborted"
                        elif trigger == "manual":
                            session.ended_reason = "manual_stop"
                        elif trigger == "crashed":
                            session.ended_reason = "system_crash"
                        elif session.pricing_mode == PricingMode.PER_TIME.value:
                            session.ended_reason = "time_expired"
                        else:
                            session.ended_reason = "credits_exhausted"
                        board.status = BoardStatus.LOCKED.value
                        board_status = "locked"
                        logger.info(f"[SESSION] SESSION_CLOSED reason={session.ended_reason}")
                        logger.info(f"[BOARD] locking board {board_id}")
                    else:
                        board.status = BoardStatus.UNLOCKED.value
                        board_status = "unlocked"

                    await db.flush()
                # Transaction auto-committed after db.begin() exits
                logger.info(
                    f"[SESSION] db_commit_succeeded board={board_id} "
                    f"should_lock={should_lock} credits={credits_remaining} "
                    f"should_teardown={should_teardown}"
                )
                db_committed = True

        except Exception as e:
            logger.error(f"[SESSION] db_commit_failed board={board_id} error={e}", exc_info=True)

        # ── Step 3: Delay ONLY for finished (player sees result) ──
        if trigger == "finished" or trigger.startswith("match_end_"):
            # Read configurable delay from DB (v3.2.0), fallback to env var
            delay_seconds = FINALIZE_DELAY_FINISHED
            try:
                from backend.models import DEFAULT_POST_MATCH_DELAY
                async with AsyncSessionLocal() as delay_db:
                    delay_setting = await get_or_create_setting(delay_db, "post_match_delay", DEFAULT_POST_MATCH_DELAY)
                    delay_ms = delay_setting.get("delay_ms", 5000)
                    delay_seconds = max(0, delay_ms / 1000.0)
                    await delay_db.commit()
            except Exception as e:
                logger.warning(f"[SESSION] failed to read post_match_delay, using default: {e}")
            logger.info(f"[SESSION] post_match_delay start board={board_id} delay_ms={int(delay_seconds*1000)}")
            await asyncio.sleep(delay_seconds)
            logger.info(f"[SESSION] post_match_delay done board={board_id} delay_ms={int(delay_seconds*1000)}")

        # ── Step 4: SESSION-END vs KEEP-ALIVE branch ──
        if should_teardown:
            # ═══ SESSION-END PATH ═══
            logger.info(
                f"[SESSION] finalize branch board={board_id} "
                f"should_lock={should_lock} should_teardown=True branch=session_end"
            )
            await run_terminal_session_cleanup(board_id, should_lock=should_lock, close_reason="session_end")
        else:
            # ═══ KEEP-ALIVE PATH ═══
            logger.info(
                f"[SESSION] finalize branch board={board_id} "
                f"should_lock=False should_teardown=False branch=keep_alive"
            )
            logger.info(f"[AUTODARTS] OBSERVER_KEPT_ALIVE board={board_id} credits={credits_remaining}")
            obs = observer_manager.get(board_id)
            if obs:
                try:
                    match_id = obs._ws_state.last_match_id if hasattr(obs, '_ws_state') else None
                    obs._last_finalized_match_id = match_id
                    logger.info(f"[SESSION] MATCH_FINALIZED_ONCE match_id={match_id}")
                    page_closed = not obs._page_alive()
                    ctx_closed = obs._context is None
                    lc_val = obs.lifecycle_state.value
                    desired_val = observer_manager.get_desired_state(board_id)
                    logger.info(
                        f"[RETURN_HOME] start board={board_id} lifecycle={lc_val} "
                        f"desired={desired_val} page_closed={page_closed} context_closed={ctx_closed}"
                    )
                    nav_ok = await obs._navigate_to_home()
                    if nav_ok:
                        try:
                            final_url = obs._page.url if obs._page_alive() else "page_dead"
                        except Exception:
                            final_url = "url_error"
                        logger.info(
                            f"[RETURN_HOME] success board={board_id} url={final_url} "
                            f"lifecycle={obs.lifecycle_state.value}"
                        )
                    else:
                        logger.warning(f"[RETURN_HOME] failed board={board_id} lifecycle={lc_val}")
                except Exception as e:
                    logger.warning(f"[AUTODARTS] navigate_to_home failed: {e}")

            # ── Clear stale close_reason (TASK 3) ──
            observer_manager.clear_close_reason(board_id)
            obs_inst = observer_manager.get(board_id)
            if obs_inst:
                obs_inst._close_reason = ""
            lc_now = obs_inst.lifecycle_state.value if obs_inst else "none"
            desired_now = observer_manager.get_desired_state(board_id)
            logger.info(
                f"[SESSION] keep_alive_reset board={board_id} "
                f"close_reason_cleared=True desired_state={desired_now} lifecycle={lc_now}"
            )

        # ── Step 7: Sound broadcast ──
        try:
            if should_record_match_completion(trigger):
                await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "checkout"})
            if not should_lock:
                await board_ws.broadcast("credit_update", {
                    "board_id": board_id,
                    "credits_remaining": credits_remaining,
                    "is_last_game": credits_remaining <= 1,
                })
        except Exception as e:
            logger.warning(f"[SESSION] broadcast error: {e}")

        # ── Step 8: Mark finalized (ONLY if DB committed successfully) ──
        if db_committed:
            _finalized[board_id] = True
            logger.info(
                f"[SESSION] finalize_marked_committed board={board_id} "
                f"should_lock={should_lock} credits={credits_remaining} "
                f"db_committed=True"
            )
        else:
            logger.warning(
                f"[SESSION] finalize NOT marked committed board={board_id} "
                f"reason=db_not_committed should_lock={should_lock} "
                f"(retry allowed)"
            )

    finally:
        if should_teardown:
            logger.info(
                f"[KIOSK_UI] session_end_restore already_handled board={board_id} "
                f"should_lock={should_lock}"
            )
        else:
            # ── KEEP-ALIVE: Ensure Autodarts stays foreground ──
            obs_ka = observer_manager.get(board_id)
            lc_ka = obs_ka.lifecycle_state.value if obs_ka else "none"
            desired_ka = observer_manager.get_desired_state(board_id)
            logger.info(
                f"[KEEP_ALIVE_UI] start board={board_id} "
                f"lifecycle={lc_ka} desired={desired_ka}"
            )
            logger.info(f"[KEEP_ALIVE_UI] skip_kiosk_restore board={board_id} reason=observer_kept_alive")
            try:
                from backend.services.window_manager import ensure_autodarts_foreground
                ad_ok = await ensure_autodarts_foreground()
                logger.info(f"[KEEP_ALIVE_UI] done board={board_id} autodarts_foreground={ad_ok}")
            except Exception as e:
                logger.warning(f"[KEEP_ALIVE_UI] ensure_autodarts_foreground failed: {e}")
                logger.info(f"[KEEP_ALIVE_UI] done board={board_id} autodarts_foreground=False")
        _finalizing.discard(board_id)

    total_ms = int((_t.monotonic() - _t0) * 1000)
    logger.info(
        f"[SESSION] finalize end board={board_id} trigger={trigger} "
        f"should_lock={should_lock} credits={credits_remaining}"
    )
    logger.info(f"[FINALIZE_TIMING] total_finalize_ms={total_ms} board={board_id}")

    return {
        "should_lock": should_lock,
        "should_teardown": should_teardown,
        "credits_remaining": credits_remaining,
        "board_status": board_status,
        "match_token": match_token,
    }


async def finalize_match(board_id: str, trigger: str,
                         winner: str = None, scores: dict = None) -> dict:
    """
    Timeout-protected wrapper around _finalize_match_inner.
    If finalize hangs for >15s, force cleanup.
    """
    try:
        return await asyncio.wait_for(
            _finalize_match_inner(board_id, trigger, winner=winner, scores=scores),
            timeout=FINALIZE_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[SESSION] FINALIZE_TIMEOUT board={board_id} trigger={trigger} (>{FINALIZE_TIMEOUT}s)")
        _finalizing.discard(board_id)

        # v3.3.1-hotfix2: Minimal recovery — attempt DB lock before giving up.
        # Do NOT blindly set _finalized — verify commit first.
        _timeout_db_ok = False
        try:
            logger.info(f"[SESSION] timeout_recovery db_commit_started board={board_id}")
            async with AsyncSessionLocal() as _tdb:
                async with _tdb.begin():
                    _tr = await _tdb.execute(select(Board).where(Board.board_id == board_id))
                    _tboard = _tr.scalar_one_or_none()
                    if _tboard and _tboard.status != BoardStatus.LOCKED.value:
                        _tboard.status = BoardStatus.LOCKED.value
                        _tsession = await get_active_session_for_board(_tdb, _tboard.id)
                        if _tsession:
                            _tsession.status = SessionStatus.FINISHED.value
                            _tsession.ended_at = datetime.now(timezone.utc)
                            _tsession.ended_reason = "finalize_timeout"
                        await _tdb.flush()
                    elif _tboard and _tboard.status == BoardStatus.LOCKED.value:
                        logger.info(f"[SESSION] timeout_recovery board_already_locked board={board_id}")
            logger.info(f"[SESSION] timeout_recovery db_commit_succeeded board={board_id}")
            _timeout_db_ok = True
        except Exception as _te:
            logger.error(f"[SESSION] timeout_recovery db_commit_failed board={board_id} error={_te}")

        if _timeout_db_ok:
            _finalized[board_id] = True
            logger.info(
                f"[SESSION] finalize_marked_committed board={board_id} "
                f"reason=timeout_recovery db_committed=True"
            )
        else:
            # Do NOT mark finalized — allow retry
            logger.warning(
                f"[SESSION] finalize NOT marked committed board={board_id} "
                f"reason=timeout_recovery_failed (retry allowed)"
            )

        # Try to close observer
        try:
            observer_manager.set_desired_state(board_id, "stopped")
            await asyncio.wait_for(observer_manager.close(board_id, reason="finalize_timeout"), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            pass

        # Broadcast lock state
        try:
            await board_ws.broadcast("board_status", {"board_id": board_id, "status": "locked"})
            await board_ws.broadcast("kiosk_refresh", {
                "board_id": board_id, "should_lock": True, "action": "return_to_kiosk",
            })
        except Exception:
            pass

        return {
            "should_lock": True, "should_teardown": True,
            "credits_remaining": 0, "board_status": "locked",
            "error": "finalize_timeout",
        }


# =====================================================================
# Observer callbacks — SYNCHRONOUS (no create_task)
# =====================================================================

async def _on_game_started(board_id: str, trigger: str = "observer_start"):
    """Observer detected authoritative start-of-play.

    Per-player sessions bill exactly once here. Per-game and per-time sessions only
    transition the board into in-game state.
    """
    logger.info(f"[Observer->Kiosk] === GAME STARTED === board={board_id} trigger={trigger}")
    _finalized.pop(board_id, None)
    _last_finalized_match.pop(board_id, None)
    try:
        charge = None
        board_status = BoardStatus.IN_GAME.value
        session_state_payload = None
        observer_context = _observer_match_context(board_id)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(select(Board).where(Board.board_id == board_id))
                board = result.scalar_one_or_none()
                if not board:
                    return
                session = await get_active_session_for_board(db, board.id)
                if not session:
                    return

                variant_mismatch, observed_variant, expected_family = _observer_variant_mismatch(board_id, session.game_type)
                if variant_mismatch:
                    logger.warning(
                        f"[Observer->Kiosk] start_ignored_preliminary_round board={board_id} "
                        f"trigger={trigger} session_game_type={session.game_type} "
                        f"expected_family={expected_family} observed_variant={observed_variant}"
                    )
                    return

                charge = apply_authoritative_start_charge(
                    session,
                    board.status,
                    players_count=observer_context.get("players_count"),
                    players=observer_context.get("players") or None,
                )
                board.status = BoardStatus.BLOCKED_PENDING.value if charge.blocked else BoardStatus.IN_GAME.value
                board_status = board.status
                session_state_payload = _session_state_payload(board_id, board.status, session, charge)

                logger.info(
                    f"[Observer->Kiosk] start_charge board={board_id} trigger={trigger} "
                    f"pricing_mode={session.pricing_mode} charged={charge.charged} blocked={charge.blocked} "
                    f"units={charge.units}/{charge.required_units} players_count={charge.players_count} "
                    f"credits_before={charge.credits_before} credits_after={charge.credits_after} "
                    f"reason={charge.reason}"
                )
        await board_ws.broadcast("board_status", {"board_id": board_id, "status": board_status})
        if session_state_payload:
            await board_ws.broadcast("session_state", session_state_payload)

        if charge and charge.blocked:
            await _show_pending_credit_gate(board_id)
            return

        await board_ws.broadcast("sound_event", {"board_id": board_id, "event": "start"})
    except Exception as e:
        logger.error(f"[Observer->Kiosk] Error on game start: {e}", exc_info=True)


async def _on_game_ended(board_id: str, reason: str) -> dict:
    """
    Observer detected match end. Execute finalize DIRECTLY (synchronous).
    Returns finalize result so observer knows whether to exit or continue.
    """
    observed_variant = None
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Board).where(Board.board_id == board_id))
            board = result.scalar_one_or_none()
            session = await get_active_session_for_board(db, board.id) if board else None
            if session:
                variant_mismatch, observed_variant, expected_family = _observer_variant_mismatch(board_id, session.game_type)
                if variant_mismatch:
                    logger.warning(
                        f"[SESSION] finalize skipped board={board_id} trigger={reason} "
                        f"reason=preliminary_variant_mismatch match_id={_get_observer_match_id(board_id)} "
                        f"session_game_type={session.game_type} expected_family={expected_family} "
                        f"observed_variant={observed_variant}"
                    )
                    return _preliminary_round_skip_result(
                        board_id,
                        reason="preliminary_variant_mismatch",
                        observed_variant=observed_variant,
                    )
    except Exception as exc:
        logger.warning(f"[SESSION] finalize variant precheck failed board={board_id}: {exc}")

    logger.info(
        f"[SESSION] finalize dispatch accepted board={board_id} trigger={reason} "
        f"match_id={_get_observer_match_id(board_id)} observed_variant={observed_variant or 'unknown'}"
    )
    try:
        result = await finalize_match(board_id, reason)
        logger.info(
            f"[Observer->Kiosk] finalize result: should_lock={result.get('should_lock')}, "
            f"credits={result.get('credits_remaining')}"
        )
        return result
    except Exception as e:
        logger.error(
            f"[SESSION] finalize dispatch failed board={board_id} trigger={reason} error={e}",
            exc_info=True,
        )
        raise


def _get_observer_match_id(board_id: str) -> str:
    """Helper to extract current match_id from observer's WS state."""
    obs = observer_manager.get(board_id)
    if obs and hasattr(obs, '_ws_state'):
        return obs._ws_state.last_match_id or "unknown"
    return "unknown"


# =====================================================================
# Observer lifecycle
# =====================================================================

async def _load_autodarts_trigger_policy() -> dict:
    try:
        async with AsyncSessionLocal() as db:
            policy = await get_or_create_setting(db, "autodarts_triggers", DEFAULT_AUTODARTS_TRIGGERS)
            await db.commit()
            return build_trigger_policy(policy).export()
    except Exception as exc:
        logger.warning(f"[Kiosk] Failed to load autodarts trigger policy, using defaults: {exc}")
        return build_trigger_policy(DEFAULT_AUTODARTS_TRIGGERS).export()


async def start_observer_for_board(board_id: str, autodarts_url: str):
    if AUTODARTS_MODE != 'observer':
        logger.info(f"[Kiosk] AUTODARTS_MODE={AUTODARTS_MODE}, skipping observer")
        return
    if not autodarts_url:
        logger.warning(f"[Kiosk] No autodarts_url for {board_id}, skipping observer start")
        return

    _finalized.pop(board_id, None)

    env_headless = os.environ.get('AUTODARTS_HEADLESS', 'false').lower() == 'true'
    display_missing = sys.platform.startswith('linux') and not os.environ.get('DISPLAY')
    headless = env_headless or display_missing
    trigger_policy = await _load_autodarts_trigger_policy()
    logger.info(
        f"[Kiosk] === Observer Start === board={board_id} url={autodarts_url} headless={headless} "
        f"authoritative_finish={trigger_policy.get('authoritative_finish')}"
    )

    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_ended=_on_game_ended,
        headless=headless,
        trigger_config=trigger_policy,
    )

    status = observer_manager.get_status(board_id)
    logger.info(f"[Kiosk] Observer post-start: state={status['state']} browser_open={status['browser_open']}")

    if status.get("browser_open") and status.get("state") not in {"auth_required", "error", "closed"}:
        try:
            from backend.services.window_manager import hide_kiosk_window, ensure_autodarts_foreground
            await asyncio.sleep(0.3)
            await hide_kiosk_window()
            await asyncio.sleep(0.2)
            await ensure_autodarts_foreground()
            logger.info(f"[Kiosk] Observer foreground handoff completed board={board_id}")
        except Exception as exc:
            logger.warning(f"[Kiosk] Observer foreground handoff failed board={board_id}: {exc}")


async def stop_observer_for_board(board_id: str, reason: str = "unknown"):
    logger.info(f"[Kiosk] Stopping observer for {board_id} reason={reason}")
    await observer_manager.close(board_id, reason=reason)
    logger.info(f"[Kiosk] Observer stopped for {board_id}")


# =====================================================================
# Endpoints
# =====================================================================

@router.post("/kiosk/{board_id}/start-game")
async def kiosk_start_game(board_id: str, data: StartGameRequest, db: AsyncSession = Depends(get_db)):
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
        "finalized": obs._finalized,
        "abort_detected": obs._abort_detected,
        "debounce": {
            "exit_polls": obs._exit_polls,
            "saw_finished": obs._exit_saw_finished,
        },
        "ws_state": {
            "match_active": ws.match_active,
            "match_finished": ws.match_finished,
            "finish_pending": ws.finish_pending,
            "winner_detected": ws.winner_detected,
            "last_match_state": ws.last_match_state,
            "last_game_event": ws.last_game_event,
            "last_match_id": ws.last_match_id,
            "last_start_trigger": ws.last_start_trigger,
            "pending_finish_trigger": ws.pending_finish_trigger,
            "frames_received": ws.frames_received,
            "match_relevant_frames": ws.match_relevant_frames,
            "finish_trigger": ws.finish_trigger,
        },
        "trigger_policy": obs.export_trigger_policy(),
        "captured_frames_count": len(frames),
        "captured_frames": [f.to_dict() for f in frames[-30:]],
    }


@router.post("/kiosk/{board_id}/observer-reset")
async def reset_observer(board_id: str):
    logger.info(f"[Observer] Reset: {board_id}")
    _finalized.pop(board_id, None)
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


@router.get("/kiosk/{board_id}/overlay")
async def get_overlay_data(board_id: str, db: AsyncSession = Depends(get_db)):
    overlay_config = await get_or_create_setting(db, "overlay_config", {"enabled": True})
    if not overlay_config.get("enabled", True):
        return {"visible": False, "reason": "disabled"}
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        return {"visible": False}
    if board.status not in (BoardStatus.UNLOCKED.value, BoardStatus.IN_GAME.value, BoardStatus.BLOCKED_PENDING.value):
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
    pending_credit_gate = board.status == BoardStatus.BLOCKED_PENDING.value and session.pricing_mode == PricingMode.PER_PLAYER.value
    required_units = int(session.players_count or 0)
    credits_shortage = max(0, required_units - int(session.credits_remaining or 0)) if pending_credit_gate else 0
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
        "pending_credit_gate": pending_credit_gate,
        "required_units": required_units if pending_credit_gate else None,
        "credits_shortage": credits_shortage,
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
# Simulation endpoints (testing without real Autodarts)
# =====================================================================

@router.post("/kiosk/{board_id}/simulate-game-start")
async def simulate_game_start(board_id: str, admin: User = Depends(require_admin)):
    await _on_game_started(board_id)
    return {"message": f"Simulated game start on {board_id}"}


@router.post("/kiosk/{board_id}/simulate-game-end")
async def simulate_game_end(board_id: str, admin: User = Depends(require_admin)):
    result = await _on_game_ended(board_id, "finished")
    return {"message": f"Simulated game end on {board_id}", **result}


@router.post("/kiosk/{board_id}/simulate-game-abort")
async def simulate_game_abort(board_id: str, admin: User = Depends(require_admin)):
    result = await _on_game_ended(board_id, "aborted")
    return {"message": f"Simulated game abort on {board_id}", **result}
