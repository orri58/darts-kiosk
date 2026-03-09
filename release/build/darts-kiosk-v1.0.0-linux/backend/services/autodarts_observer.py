"""
Autodarts Observer Service — MVP Observer Mode
Opens the Autodarts browser and passively observes game state.
Does NOT automate game setup or player entry.

MVP SCOPE:
  Observer only tracks browser sessions launched by THIS system.
  Manually opened external browser windows are NOT detected.
  Each board gets its own isolated observer/browser instance.

States: closed, idle, in_game, finished, unknown, error

Credit logic:
  Credits are decremented on game START (idle -> in_game), not on finish.
  State guard prevents double-decrement.
"""
import asyncio
import os
import logging
from typing import Optional, Dict, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

AUTODARTS_URL = os.environ.get('AUTODARTS_URL', 'https://play.autodarts.io')
OBSERVER_POLL_INTERVAL = int(os.environ.get('OBSERVER_POLL_INTERVAL', '4'))


def import_platform() -> str:
    import sys
    import platform
    return f"{sys.platform}/{platform.machine()}"


class ObserverState(str, Enum):
    CLOSED = "closed"
    IDLE = "idle"
    IN_GAME = "in_game"
    FINISHED = "finished"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class ObserverStatus:
    state: ObserverState = ObserverState.CLOSED
    board_id: str = ""
    autodarts_url: str = ""
    browser_open: bool = False
    games_observed: int = 0
    credits_remaining: Optional[int] = None
    is_last_game: bool = False
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
            "credits_remaining": self.credits_remaining,
            "is_last_game": self.is_last_game,
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
        self._on_game_started: Optional[Callable] = None
        self._on_game_finished: Optional[Callable] = None
        self._stopping = False
        self._prev_state: ObserverState = ObserverState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._browser is not None and self.status.browser_open

    async def open_session(
        self,
        autodarts_url: str,
        on_game_started: Optional[Callable] = None,
        on_game_finished: Optional[Callable] = None,
        headless: bool = True,
    ):
        """Open the Autodarts browser and start the observer loop."""
        if self.is_open:
            logger.info(f"[Observer:{self.board_id}] Browser already open, skipping duplicate")
            return

        self._on_game_started = on_game_started
        self._on_game_finished = on_game_finished
        self._stopping = False
        self._prev_state = ObserverState.CLOSED

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH START ===")
        logger.info(f"[Observer:{self.board_id}]   URL: {url}")
        logger.info(f"[Observer:{self.board_id}]   headless: {headless}")
        logger.info(f"[Observer:{self.board_id}]   platform: {import_platform()}")
        logger.info(f"[Observer:{self.board_id}]   event loop: {type(asyncio.get_event_loop_policy()).__name__}")

        try:
            logger.info(f"[Observer:{self.board_id}]   Step 1/6: Importing playwright...")
            from playwright.async_api import async_playwright

            logger.info(f"[Observer:{self.board_id}]   Step 2/6: Starting playwright runtime...")
            self._playwright = await async_playwright().start()

            launch_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
            if not headless:
                launch_args.extend([
                    '--start-fullscreen',
                    '--kiosk',
                ])

            logger.info(f"[Observer:{self.board_id}]   Step 3/6: Launching chromium (args={launch_args})...")
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=launch_args,
            )
            logger.info(f"[Observer:{self.board_id}]   Step 3/6: Browser process created OK")

            logger.info(f"[Observer:{self.board_id}]   Step 4/6: Creating browser context...")
            self._context = await self._browser.new_context(
                viewport=None if not headless else {"width": 1280, "height": 800},
                no_viewport=not headless,
                ignore_https_errors=True,
            )

            logger.info(f"[Observer:{self.board_id}]   Step 5/6: Opening new page...")
            self._page = await self._context.new_page()

            logger.info(f"[Observer:{self.board_id}]   Step 6/6: Navigating to {url}...")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            self.status.browser_open = True
            self._set_state(ObserverState.IDLE)
            self._prev_state = ObserverState.IDLE
            logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH SUCCESS ===")

            self._observe_task = asyncio.create_task(self._observe_loop())

        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED ===")
            logger.error(f"[Observer:{self.board_id}]   Error type: {type(e).__name__}")
            logger.error(f"[Observer:{self.board_id}]   Error: {e}", exc_info=True)
            # Store concise error for frontend display (first line only)
            error_msg = str(e).split('\n')[0][:200]
            self.status.last_error = f"{type(e).__name__}: {error_msg}"
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
        for resource in [self._page, self._context, self._browser]:
            try:
                if resource:
                    await resource.close()
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

    async def _observe_loop(self):
        """Poll the Autodarts page for game state changes."""
        logger.info(f"[Observer:{self.board_id}] Observe loop started (poll={OBSERVER_POLL_INTERVAL}s)")

        while not self._stopping:
            try:
                await asyncio.sleep(OBSERVER_POLL_INTERVAL)
                if not self._page or self._stopping:
                    break

                new_state = await self._detect_state()
                now = datetime.now(timezone.utc).isoformat()
                self.status.last_poll = now

                if new_state == self._prev_state:
                    continue

                logger.info(f"[Observer:{self.board_id}] State: {self._prev_state.value} -> {new_state.value}")
                self._set_state(new_state)

                # idle -> in_game: game STARTED -> decrement credits
                if new_state == ObserverState.IN_GAME and self._prev_state != ObserverState.IN_GAME:
                    self.status.games_observed += 1
                    if self._on_game_started:
                        try:
                            await self._on_game_started(self.board_id)
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_started error: {e}")

                # in_game -> finished: game ENDED
                elif new_state == ObserverState.FINISHED and self._prev_state == ObserverState.IN_GAME:
                    if self._on_game_finished:
                        try:
                            await self._on_game_finished(self.board_id)
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_finished error: {e}")

                self._prev_state = new_state

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Observer:{self.board_id}] Observe loop error: {e}")
                self.status.last_error = str(e)
                self._set_state(ObserverState.ERROR)
                self._prev_state = ObserverState.ERROR
                await asyncio.sleep(OBSERVER_POLL_INTERVAL * 2)

        logger.info(f"[Observer:{self.board_id}] Observe loop ended")

    async def _detect_state(self) -> ObserverState:
        """
        Detect game state from Autodarts DOM using minimal selectors.
        """
        try:
            in_game = await self._page.evaluate("""() => {
                const m = document.querySelector(
                    '[class*="match"], [class*="scoreboard"], [data-testid*="match"], #match'
                );
                const d = document.querySelector(
                    '[class*="dart-input"], [class*="throw"], [class*="scoring"], [class*="game-view"]'
                );
                return !!(m || d);
            }""")

            finished = await self._page.evaluate("""() => {
                const w = document.querySelector(
                    '[class*="winner"], [class*="result"], [class*="game-over"], [class*="match-end"], [class*="finished"]'
                );
                const s = document.querySelector(
                    '[class*="post-match"], [class*="match-stats"], [class*="game-result"]'
                );
                return !!(w || s);
            }""")

            if finished:
                return ObserverState.FINISHED
            if in_game:
                return ObserverState.IN_GAME
            return ObserverState.IDLE

        except Exception as e:
            logger.warning(f"[Observer:{self.board_id}] DOM detection error: {e}")
            self.status.last_error = str(e)
            return ObserverState.UNKNOWN

    def _set_state(self, state: ObserverState):
        if self.status.state != state:
            self.status.state = state
            self.status.last_state_change = datetime.now(timezone.utc).isoformat()


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
        existing = self._observers.get(board_id)
        if existing and existing.is_open:
            logger.info(f"[ObserverMgr] Board {board_id} already open")
            return existing

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
        obs = self._observers.get(board_id)
        if obs:
            await obs.close_session()
            logger.info(f"[ObserverMgr] Observer closed for board {board_id}")

    async def close_all(self):
        for board_id in list(self._observers.keys()):
            await self.close(board_id)


observer_manager = ObserverManager()
