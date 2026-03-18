"""
Watchdog Service v2.9.1 — monitors observer health and triggers recovery.

Lifecycle-aware with strict recovery gating:
  - _should_attempt_recovery() is the single decision point
  - CLOSED is NEVER recovered (intentional end state)
  - Only ERROR with desired_state=running triggers recovery
  - AUTH_REQUIRED is never recovered
  - Bounded recovery: 3 failures in 5 min → block for 10 min
  - All decisions are logged with exact reason
"""
import asyncio
import time
import logging

from backend.services.autodarts_observer import (
    observer_manager,
    LifecycleState,
)

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = 30
RECOVERY_COOLDOWN = 15
LAUNCH_GRACE_PERIOD = 20

# Close reasons that are always intentional — never recover
INTENTIONAL_CLOSE_REASONS = frozenset({
    "manual_lock", "session_end", "admin_stop", "shutdown",
    "desired_state_changed", "auth_required",
})

# Escalation limits
MAX_FAILURES_WINDOW = 3     # max failures within the time window
FAILURE_WINDOW_SECS = 300   # 5 minutes
BLOCK_DURATION_SECS = 600   # block for 10 minutes after escalation

# Per-board state
_recovery_timestamps: dict = {}     # board_id -> [list of failure timestamps]
_blocked_until: dict = {}           # board_id -> timestamp when block expires

_watchdog_task: asyncio.Task = None


async def start_watchdog():
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        return
    _watchdog_task = asyncio.create_task(_watchdog_loop())
    logger.info("[WATCHDOG] started")


async def stop_watchdog():
    global _watchdog_task
    if _watchdog_task:
        _watchdog_task.cancel()
        try:
            await _watchdog_task
        except asyncio.CancelledError:
            pass
        _watchdog_task = None
    logger.info("[WATCHDOG] stopped")


async def _watchdog_loop():
    while True:
        try:
            await asyncio.sleep(WATCHDOG_INTERVAL)
            await _run_health_checks()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[WATCHDOG] loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


def _should_attempt_recovery(board_id: str) -> tuple:
    """
    Single decision point for recovery.
    Returns (should_recover: bool, reason: str).
    """
    obs = observer_manager.get(board_id)
    desired = observer_manager.get_desired_state(board_id)
    close_reason = observer_manager.get_close_reason(board_id)
    now = time.time()

    if obs is None:
        return False, "no_observer_instance"

    lifecycle = obs.lifecycle_state.value
    is_open = obs.is_open
    page_alive = obs._page_alive()

    logger.info(
        f"[WATCHDOG] evaluate board={board_id} desired={desired} lifecycle={lifecycle} "
        f"close_reason={close_reason} is_open={is_open} page_alive={page_alive}"
    )

    # Rule 1: desired_state must be "running"
    if desired != "running":
        return False, f"desired_state_{desired}"

    # v3.2.5: Block recovery if close/finalize is in progress
    if obs._closing or obs._finalize_dispatching:
        return False, "close_or_finalize_in_progress"

    # Rule 2: transitional states — wait
    if lifecycle in ("starting", "stopping"):
        return False, f"lifecycle_{lifecycle}"

    # Rule 3: AUTH_REQUIRED — needs manual intervention
    if lifecycle == "auth_required":
        return False, "auth_required"

    # Rule 4: CLOSED is ALWAYS intentional — NEVER recover
    if lifecycle == "closed":
        return False, "lifecycle_closed"

    # Rule 5: intentional close reason
    if close_reason in INTENTIONAL_CLOSE_REASONS:
        return False, f"close_reason_{close_reason}"

    # Rule 6: grace period after launch
    if obs._last_launch_time and (now - obs._last_launch_time) < LAUNCH_GRACE_PERIOD:
        elapsed = now - obs._last_launch_time
        return False, f"grace_period_{elapsed:.0f}s"

    # Rule 7: escalation block
    blocked = _blocked_until.get(board_id, 0)
    if now < blocked:
        remaining = blocked - now
        return False, f"recovery_blocked_{remaining:.0f}s_remaining"

    # Rule 8: cooldown between attempts
    timestamps = _recovery_timestamps.get(board_id, [])
    if timestamps:
        last = timestamps[-1]
        elapsed = now - last
        # Exponential backoff: base cooldown * 2^(recent_failures-1)
        recent = len([t for t in timestamps if now - t < FAILURE_WINDOW_SECS])
        effective_cooldown = RECOVERY_COOLDOWN * (2 ** min(recent - 1, 4)) if recent > 0 else RECOVERY_COOLDOWN
        if elapsed < effective_cooldown:
            return False, f"cooldown_{elapsed:.0f}s_of_{effective_cooldown:.0f}s"

    # Rule 9: observer must actually be unhealthy
    if is_open and page_alive:
        return False, "healthy"

    # All checks passed — this is a real crash/error that should be recovered
    return True, "unhealthy_running_observer"


async def _run_health_checks():
    from backend.database import AsyncSessionLocal
    from backend.models import Board
    from sqlalchemy import select

    logger.info("[WATCHDOG] active — monitoring observers")

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Board).where(
                    Board.autodarts_target_url.isnot(None),
                    Board.autodarts_target_url != "",
                )
            )
            boards = result.scalars().all()
    except Exception as e:
        logger.error(f"[WATCHDOG] DB error: {e}")
        return

    now = time.time()

    for board in boards:
        board_id = board.board_id

        should_recover, reason = _should_attempt_recovery(board_id)

        if not should_recover:
            if reason != "no_observer_instance" and reason != "healthy":
                logger.info(f"[WATCHDOG] skip {board_id} reason={reason}")
            continue

        # ── Escalation check: too many failures? ──
        timestamps = _recovery_timestamps.get(board_id, [])
        # Clean old timestamps outside the window
        timestamps = [t for t in timestamps if now - t < FAILURE_WINDOW_SECS]
        _recovery_timestamps[board_id] = timestamps

        if len(timestamps) >= MAX_FAILURES_WINDOW:
            _blocked_until[board_id] = now + BLOCK_DURATION_SECS
            logger.error(
                f"[WATCHDOG] recovery blocked {board_id} "
                f"failures={len(timestamps)} window={FAILURE_WINDOW_SECS}s "
                f"blocked_until={time.strftime('%H:%M:%S', time.localtime(now + BLOCK_DURATION_SECS))}"
            )
            continue

        # ── Trigger recovery ──
        logger.info(
            f"[WATCHDOG] recovery starting {board_id} reason={reason} "
            f"failures={len(timestamps)}"
        )
        timestamps.append(now)
        _recovery_timestamps[board_id] = timestamps

        try:
            await _recover_observer(board_id, board.autodarts_target_url)
            logger.info(f"[WATCHDOG] recovery successful for {board_id}")
        except Exception as e:
            logger.error(f"[WATCHDOG] recovery failed for {board_id}: {e}")


async def _recover_observer(board_id: str, autodarts_url: str):
    from backend.routers.kiosk import _on_game_started, _on_game_ended
    import os

    headless = os.environ.get('AUTODARTS_HEADLESS', 'false').lower() == 'true'

    try:
        await asyncio.wait_for(
            observer_manager.close(board_id, reason="watchdog_recovery"),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[WATCHDOG] close timeout for {board_id}, proceeding with open")
    await asyncio.sleep(2)
    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_ended=_on_game_ended,
        headless=headless,
    )
