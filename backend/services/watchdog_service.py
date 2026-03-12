"""
Watchdog Service — monitors observer health and triggers recovery.

Lifecycle-aware:
  - Skips boards in STARTING or STOPPING state (transitional)
  - Enforces cooldown between recovery attempts (RECOVERY_COOLDOWN)
  - Tracks consecutive failures per board for backoff
  - Only recovers when lifecycle=RUNNING but page/context is dead
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

# Per-board recovery state
_last_recovery_time: dict = {}      # board_id -> timestamp of last recovery attempt
_consecutive_failures: dict = {}    # board_id -> count of consecutive failures

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

        if obs is None:
            # No observer created yet — not our responsibility
            continue

        lifecycle = obs.lifecycle_state

        # ── Skip transitional states ──
        if lifecycle in (LifecycleState.STARTING, LifecycleState.STOPPING):
            logger.info(
                f"[WATCHDOG] skipped {board_id} — lifecycle={lifecycle.value} "
                f"(transitional, waiting)"
            )
            continue

        # ── Skip if recently launched (grace period) ──
        if obs._last_launch_time and (now - obs._last_launch_time) < LAUNCH_GRACE_PERIOD:
            elapsed = now - obs._last_launch_time
            logger.info(
                f"[WATCHDOG] skipped {board_id} — launched {elapsed:.0f}s ago "
                f"(grace period {LAUNCH_GRACE_PERIOD}s)"
            )
            continue

        # ── Check if observer is healthy ──
        is_healthy = obs.is_open and obs._page_alive()

        if is_healthy:
            # Reset consecutive failure counter on healthy check
            _consecutive_failures.pop(board_id, None)
            continue

        # ── Observer unhealthy — should we recover? ──
        logger.warning(
            f"[WATCHDOG] UNHEALTHY {board_id}: lifecycle={lifecycle.value} "
            f"is_open={obs.is_open} page_alive={obs._page_alive()}"
        )

        # Cooldown check
        last_recovery = _last_recovery_time.get(board_id, 0)
        cooldown_elapsed = now - last_recovery

        # Backoff: consecutive failures increase cooldown
        failures = _consecutive_failures.get(board_id, 0)
        effective_cooldown = RECOVERY_COOLDOWN * (2 ** min(failures, 4))  # max 16x

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
            f"(failures={failures}, cooldown={effective_cooldown:.0f}s)"
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

    # Close existing (this acquires the lifecycle lock)
    await observer_manager.close(board_id)

    # Small pause before relaunch
    await asyncio.sleep(2)

    # Reopen (this also acquires the lifecycle lock)
    await observer_manager.open(
        board_id=board_id,
        autodarts_url=autodarts_url,
        on_game_started=_on_game_started,
        on_game_ended=_on_game_ended,
        headless=headless,
    )
