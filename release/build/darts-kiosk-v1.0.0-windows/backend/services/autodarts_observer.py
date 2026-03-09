"""
Autodarts Observer Service — MVP Observer Mode
Opens the Autodarts browser and passively observes game state.
Does NOT automate game setup or player entry.

States: idle, in_game, finished, unknown, error, closed
"""
import asyncio
import os
import logging
import time
from typing import Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

AUTODARTS_URL = os.environ.get('AUTODARTS_URL', 'https://play.autodarts.io')
OBSERVER_POLL_INTERVAL = int(os.environ.get('OBSERVER_POLL_INTERVAL', '4'))


class ObserverState(str, Enum):
    CLOSED = "closed"          # No browser open
    IDLE = "idle"              # Browser open, no match running
    IN_GAME = "in_game"        # Match in progress
    FINISHED = "finished"      # Match just finished
    UNKNOWN = "unknown"        # Could not determine state
    ERROR = "error"            # Observer error


@dataclass
class ObserverStatus:
    state: ObserverState = ObserverState.CLOSED
    board_id: str = ""
    autodarts_url: str = ""
    browser_open: bool = False
    games_observed: int = 0
    last_state_change: Optional[str] = None
    last_poll: Optional[str] = None
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "board_id": self.board_id,
            "autodarts_url": self.autodarts_url,
            "browser_open": self.browser_open,
            "games_observed": self.games_observed,
            "last_state_change": self.last_state_change,
            "last_poll": self.last_poll,
            "last_error": self.last_error,
        }


class AutodartsObserver:
    """
    Per-board observer. Opens one Chromium instance to the Autodarts URL,
    then polls the DOM periodically to detect game start/end.
    """

    def __init__(self, board_id: str):
        self.board_id = board_id
        self.status = ObserverStatus(board_id=board_id)
        self._browser = None
        self._context = None
        self._page = None
        self._observe_task: Optional[asyncio.Task] = None
        self._on_game_finished = None  # callback: async def(board_id)
        self._on_game_started = None   # callback: async def(board_id)
        self._stopping = False

    @property
    def is_open(self) -> bool:
        return self._browser is not None and self.status.browser_open

    async def open_session(
        self,
        autodarts_url: str,
        on_game_started=None,
        on_game_finished=None,
        headless: bool = True,
    ):
        """Open the Autodarts browser and start the observer loop."""
        if self.is_open:
            logger.info(f"[Observer:{self.board_id}] Browser already open, skipping duplicate open")
            return

        self._on_game_started = on_game_started
        self._on_game_finished = on_game_finished
        self._stopping = False

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        logger.info(f"[Observer:{self.board_id}] Opening browser → {url} (headless={headless})")

        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-size=1280,800',
                ]
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )
            self._page = await self._context.new_page()
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            self.status.browser_open = True
            self._set_state(ObserverState.IDLE)
            logger.info(f"[Observer:{self.board_id}] Browser opened successfully")

            # Start observe loop as background task
            self._observe_task = asyncio.create_task(self._observe_loop())

        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] Failed to open browser: {e}", exc_info=True)
            self.status.last_error = str(e)
            self._set_state(ObserverState.ERROR)
            await self._cleanup_browser()

    async def close_session(self):
        """Close the browser and stop observing."""
        logger.info(f"[Observer:{self.board_id}] Closing session...")
        self._stopping = True

        if self._observe_task and not self._observe_task.done():
            self._observe_task.cancel()
            try:
                await self._observe_task
            except asyncio.CancelledError:
                pass

        await self._cleanup_browser()
        self._set_state(ObserverState.CLOSED)
        logger.info(f"[Observer:{self.board_id}] Session closed")

    async def _cleanup_browser(self):
        """Safely close all browser resources."""
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if hasattr(self, '_playwright') and self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self.status.browser_open = False

    # ------------------------------------------------------------------
    # Observer loop
    # ------------------------------------------------------------------

    async def _observe_loop(self):
        """Poll the Autodarts page for game state changes."""
        logger.info(f"[Observer:{self.board_id}] Observe loop started (interval={OBSERVER_POLL_INTERVAL}s)")
        prev_state = self.status.state

        while not self._stopping:
            try:
                await asyncio.sleep(OBSERVER_POLL_INTERVAL)

                if not self._page or self._stopping:
                    break

                new_state = await self._detect_state()
                self.status.last_poll = datetime.now(timezone.utc).isoformat()

                if new_state != prev_state:
                    logger.info(f"[Observer:{self.board_id}] State change: {prev_state} → {new_state}")
                    self._set_state(new_state)

                    # Trigger callbacks on transitions
                    if new_state == ObserverState.IN_GAME and prev_state != ObserverState.IN_GAME:
                        if self._on_game_started:
                            try:
                                await self._on_game_started(self.board_id)
                            except Exception as cb_err:
                                logger.error(f"[Observer:{self.board_id}] on_game_started callback error: {cb_err}")

                    elif new_state == ObserverState.FINISHED and prev_state == ObserverState.IN_GAME:
                        self.status.games_observed += 1
                        if self._on_game_finished:
                            try:
                                await self._on_game_finished(self.board_id)
                            except Exception as cb_err:
                                logger.error(f"[Observer:{self.board_id}] on_game_finished callback error: {cb_err}")

                    prev_state = new_state

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Observer:{self.board_id}] Observe loop error: {e}")
                self.status.last_error = str(e)
                self._set_state(ObserverState.ERROR)
                prev_state = ObserverState.ERROR
                await asyncio.sleep(OBSERVER_POLL_INTERVAL * 2)

        logger.info(f"[Observer:{self.board_id}] Observe loop ended")

    async def _detect_state(self) -> ObserverState:
        """
        Detect game state from the Autodarts DOM.
        Uses minimal, stable selectors:
        - Match running: scoreboard / dart-input area visible
        - Match finished: result / winner screen visible
        - Otherwise: idle
        """
        try:
            # Selector 1: Match in progress — the scoring area is visible
            in_game = await self._page.evaluate("""() => {
                // Autodarts shows a match board when a game is running
                const matchBoard = document.querySelector(
                    '[class*="match"], [class*="scoreboard"], [data-testid*="match"], #match'
                );
                // Also check for dart input / throw area
                const dartInput = document.querySelector(
                    '[class*="dart-input"], [class*="throw"], [class*="scoring"], [class*="game-view"]'
                );
                return !!(matchBoard || dartInput);
            }""")

            # Selector 2: Match finished — result/winner screen
            finished = await self._page.evaluate("""() => {
                const winner = document.querySelector(
                    '[class*="winner"], [class*="result"], [class*="game-over"], [class*="match-end"], [class*="finished"]'
                );
                const stats = document.querySelector(
                    '[class*="post-match"], [class*="match-stats"], [class*="game-result"]'
                );
                return !!(winner || stats);
            }""")

            if finished:
                return ObserverState.FINISHED
            elif in_game:
                return ObserverState.IN_GAME
            else:
                return ObserverState.IDLE

        except Exception as e:
            logger.warning(f"[Observer:{self.board_id}] DOM detection error: {e}")
            self.status.last_error = str(e)
            return ObserverState.UNKNOWN

    def _set_state(self, state: ObserverState):
        if self.status.state != state:
            self.status.state = state
            self.status.last_state_change = datetime.now(timezone.utc).isoformat()


# =====================================================================
# Global observer manager — one observer per board
# =====================================================================

class ObserverManager:
    """Manages one AutodartsObserver instance per board."""

    def __init__(self):
        self._observers: Dict[str, AutodartsObserver] = {}

    def get(self, board_id: str) -> Optional[AutodartsObserver]:
        return self._observers.get(board_id)

    def get_status(self, board_id: str) -> dict:
        obs = self._observers.get(board_id)
        if obs:
            return obs.status.to_dict()
        return ObserverStatus(board_id=board_id).to_dict()

    def get_all_statuses(self) -> list:
        return [obs.status.to_dict() for obs in self._observers.values()]

    async def open(
        self,
        board_id: str,
        autodarts_url: str,
        on_game_started=None,
        on_game_finished=None,
        headless: bool = True,
    ):
        """Open observer for a board. No-op if already open."""
        existing = self._observers.get(board_id)
        if existing and existing.is_open:
            logger.info(f"[ObserverMgr] Board {board_id} already has an open observer")
            return existing

        # Create new observer
        obs = AutodartsObserver(board_id)
        self._observers[board_id] = obs
        await obs.open_session(
            autodarts_url=autodarts_url,
            on_game_started=on_game_started,
            on_game_finished=on_game_finished,
            headless=headless,
        )
        return obs

    async def close(self, board_id: str):
        """Close observer for a board."""
        obs = self._observers.get(board_id)
        if obs:
            await obs.close_session()
            logger.info(f"[ObserverMgr] Observer closed for board {board_id}")

    async def close_all(self):
        """Close all observers (on shutdown)."""
        for board_id in list(self._observers.keys()):
            await self.close(board_id)


# Global singleton
observer_manager = ObserverManager()
