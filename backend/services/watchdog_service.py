"""
Observer Watchdog Service — Crash Recovery & Zombie Cleanup (v2.4.0)

Background task that monitors observer health for all active boards.
Runs every 5 seconds and handles:
  - Observer dead but session active → auto-restart
  - Page/context crashed → recovery
  - Zombie observers (no active session) → cleanup
  - Stale WS connection (no frames for 60s during game) → restart
"""
import asyncio
import time
import logging
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import Board, Session, BoardStatus, SessionStatus
from backend.dependencies import get_active_session_for_board
from backend.services.autodarts_observer import observer_manager

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = 5  # seconds between checks
WS_STALE_THRESHOLD = 60  # seconds without WS frame during active game

_watchdog_task: asyncio.Task = None


async def start_watchdog():
    """Start the watchdog background task. Call from app startup."""
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        logger.info("[WATCHDOG] already running")
        return
    _watchdog_task = asyncio.create_task(_watchdog_loop())
    logger.info("[WATCHDOG] started")


async def stop_watchdog():
    """Stop the watchdog. Call from app shutdown."""
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        _watchdog_task.cancel()
        try:
            await _watchdog_task
        except asyncio.CancelledError:
            pass
    _watchdog_task = None
    logger.info("[WATCHDOG] stopped")


async def _watchdog_loop():
    """Main watchdog loop. Runs indefinitely."""
    # Wait for app to fully start
    await asyncio.sleep(10)
    logger.info("[WATCHDOG] active — monitoring observers")

    while True:
        try:
            await _run_health_checks()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[WATCHDOG] error in health check: {e}", exc_info=True)
        await asyncio.sleep(WATCHDOG_INTERVAL)


async def _run_health_checks():
    """Check all boards and recover unhealthy observers."""
    # Collect active boards from DB
    active_boards = {}
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Board).where(
                    Board.status.in_([
                        BoardStatus.UNLOCKED.value,
                        BoardStatus.IN_GAME.value,
                    ])
                )
            )
            for board in result.scalars():
                session = await get_active_session_for_board(db, board.id)
                if session:
                    active_boards[board.board_id] = {
                        "autodarts_url": board.autodarts_target_url,
                        "board_name": board.name,
                    }
    except Exception as e:
        logger.error(f"[WATCHDOG] DB error: {e}")
        return

    # Check 1: Active session but no/dead observer → restart
    for board_id, info in active_boards.items():
        obs = observer_manager.get(board_id)
        autodarts_url = info.get("autodarts_url")

        if obs is None or not obs.is_open:
            if autodarts_url:
                logger.warning(f"[WATCHDOG] observer unhealthy for {board_id} (missing/closed)")
                logger.info(f"[WATCHDOG] attempting recovery for {board_id}")
                await _recover_observer(board_id, autodarts_url)
            continue

        # Check 2: Observer exists but page/context is dead
        if not obs._page_alive():
            logger.warning(f"[WATCHDOG] page dead for {board_id}")
            if autodarts_url:
                logger.info(f"[WATCHDOG] relaunching observer/browser for {board_id}")
                await _recover_observer(board_id, autodarts_url)
            continue

    # Check 3: Zombie observers (observer open but no active session)
    for board_id in list(observer_manager._observers.keys()):
        if board_id not in active_boards:
            obs = observer_manager.get(board_id)
            if obs and obs.is_open:
                logger.warning(f"[WATCHDOG] zombie observer {board_id} (no active session)")
                logger.info(f"[WATCHDOG] cleaning up zombie for {board_id}")
                try:
                    await observer_manager.close(board_id)
                    logger.info(f"[WATCHDOG] orphan context cleaned {board_id}")
                except Exception as e:
                    logger.error(f"[WATCHDOG] zombie cleanup failed {board_id}: {e}")


async def _recover_observer(board_id: str, autodarts_url: str):
    """Close existing observer and start fresh."""
    try:
        await observer_manager.close(board_id)
        logger.info(f"[WATCHDOG] old observer closed for {board_id}")
    except Exception as e:
        logger.warning(f"[WATCHDOG] close failed during recovery {board_id}: {e}")

    try:
        # Late import to avoid circular dependency
        from backend.routers.kiosk import start_observer_for_board
        await start_observer_for_board(board_id, autodarts_url)
        logger.info(f"[WATCHDOG] recovery successful for {board_id}")
    except Exception as e:
        logger.error(f"[WATCHDOG] recovery failed for {board_id}: {e}")
