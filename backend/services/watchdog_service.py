"""
Watchdog Service — monitors observer health and triggers recovery.

Lifecycle-aware:
  - Skips boards in STARTING or STOPPING state (transitional)
  - Only recovers when desired_state == "running"
  - Suppresses recovery for manual_lock / session_end / admin_stop
  - Enforces cooldown between recovery attempts (RECOVERY_COOLDOWN)
  - Tracks consecutive failures per board for exponential backoff
  - AUTH_REQUIRED is NOT recovered (needs manual login)
"""
import asyncio
import time
import logging

from backend.services.autodarts_observer import (
    observer_manager,
    LifecycleState,
)

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = 30      # seconds between health checks
RECOVERY_COOLDOWN = 15      # min seconds between recovery attempts per board
LAUNCH_GRACE_PERIOD = 20    # seconds after launch before watchdog may intervene

# Close reasons that suppress automatic recovery
INTENTIONAL_CLOSE_REASONS = {"manual_lock", "session_end", "admin_stop", "shutdown"}

# Per-board recovery state
_last_recovery_time: dict = {}
_consecutive_failures: dict = {}

_watchdog_task: asyncio.Task = None


async def start_watchdog():
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        logger.info("[WATCHDOG] already running")
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
    """Main watchdog loop — runs periodically to check observer health."""
    while True:
        try:
            await asyncio.sleep(WATCHDOG_INTERVAL)
            await _run_health_checks()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[WATCHDOG] loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


async def _run_health_checks():
    """Check all known observers and recover if needed."""
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
        obs = observer_manager.get(board_id)
        desired = observer_manager.get_desired_state(board_id)
        close_reason = observer_manager.get_close_reason(board_id)

        # ── Check 1: desired_state must be "running" ──
        if desired != "running":
            if obs and obs.lifecycle_state not in (LifecycleState.CLOSED, LifecycleState.STOPPING):
                logger.info(
                    f"[WATCHDOG] recovery suppressed {board_id} — "
                    f"desired_state={desired} (intentionally stopped)"
                )
            continue

        if obs is None:
            continue

        lifecycle = obs.lifecycle_state

        # ── Check 2: Skip transitional states ──
        if lifecycle in (LifecycleState.STARTING, LifecycleState.STOPPING):
            logger.info(
                f"[WATCHDOG] skipped {board_id} — lifecycle={lifecycle.value} "
                f"(transitional, waiting)"
            )
            continue

        # ── Check 3: AUTH_REQUIRED is NOT recoverable ──
        if lifecycle == LifecycleState.AUTH_REQUIRED:
            logger.info(
                f"[WATCHDOG] auth_required detected {board_id} — "
                f"recovery suppressed (needs manual login in Chrome profile)"
            )
            continue

        # ── Check 4: Skip if intentional close reason ──
        if close_reason in INTENTIONAL_CLOSE_REASONS:
            if lifecycle in (LifecycleState.CLOSED, LifecycleState.ERROR):
                logger.info(
                    f"[WATCHDOG] recovery suppressed {board_id} — "
                    f"close_reason={close_reason} (intentional stop)"
                )
                continue

        # ── Check 5: Skip if recently launched (grace period) ──
        if obs._last_launch_time and (now - obs._last_launch_time) < LAUNCH_GRACE_PERIOD:
            elapsed = now - obs._last_launch_time
            logger.info(
                f"[WATCHDOG] skipped {board_id} — launched {elapsed:.0f}s ago "
                f"(grace period {LAUNCH_GRACE_PERIOD}s)"
            )
            continue

        # ── Check 6: Is observer actually unhealthy? ──
        is_healthy = obs.is_open and obs._page_alive()

        if is_healthy:
            _consecutive_failures.pop(board_id, None)
            continue

        # ── Observer unhealthy — should we recover? ──
        logger.warning(
            f"[WATCHDOG] UNHEALTHY {board_id}: lifecycle={lifecycle.value} "
            f"is_open={obs.is_open} page_alive={obs._page_alive()} "
            f"desired_state={desired} close_reason={close_reason}"
        )

        # Cooldown + backoff check
        last_recovery = _last_recovery_time.get(board_id, 0)
        cooldown_elapsed = now - last_recovery
        failures = _consecutive_failures.get(board_id, 0)
        effective_cooldown = RECOVERY_COOLDOWN * (2 ** min(failures, 4))

        if cooldown_elapsed < effective_cooldown:
            logger.info(
                f"[WATCHDOG] recovery throttled {board_id} — "
                f"last attempt {cooldown_elapsed:.0f}s ago, "
                f"cooldown={effective_cooldown:.0f}s (failures={failures})"
            )
            continue

        # ── Trigger recovery ──
        logger.info(
            f"[WATCHDOG] recovery starting {board_id} "
            f"(failures={failures}, cooldown={effective_cooldown:.0f}s, "
            f"desired_state={desired})"
        )
        _last_recovery_time[board_id] = now
        _consecutive_failures[board_id] = failures + 1

        try:
            await _recover_observer(board_id, board.autodarts_target_url)
            logger.info(f"[WATCHDOG] recovery successful for {board_id}")
        except Exception as e:
            logger.error(f"[WATCHDOG] recovery failed for {board_id}: {e}")


async def _recover_observer(board_id: str, autodarts_url: str):
    """Close and reopen an unhealthy observer."""
    from backend.routers.kiosk import _on_game_started, _on_game_ended
    import os

    headless = os.environ.get('AUTODARTS_HEADLESS', 'false').lower() == 'true'

    # Close existing (acquires lifecycle lock, records reason)
    await observer_manager.close(board_id, reason="watchdog_recovery")

    await asyncio.sleep(2)

    # Reopen (acquires lifecycle lock)
    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_ended=_on_game_ended,
        headless=headless,
    )
