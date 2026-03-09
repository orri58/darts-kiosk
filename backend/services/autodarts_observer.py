"""
Autodarts Observer Service — MVP Observer Mode
Opens the installed Chrome browser with a persistent profile and observes game state.
Does NOT automate game setup or player entry.

MVP SCOPE:
  Observer only tracks browser sessions launched by THIS system.
  Manually opened external browser windows are NOT detected.
  Each board gets its own isolated observer/browser instance.

CHROME PROFILE:
  Uses launch_persistent_context with channel="chrome" to reuse
  the installed Chrome and its user profile. This preserves:
    - Google login sessions
    - Cookies and storage
    - Browser extensions
  Profile directory: data/chrome_profile/{board_id}/
  Profile is NEVER recreated — operator logs in once and it persists.

AUTOMATION DETECTION:
  ignore_default_args=["--enable-automation"] prevents the
  "Chrome is being controlled by automated test software" banner.
  Additional flags disable automation fingerprinting.

WINDOW MANAGEMENT:
  On Windows, after launching Chrome, the kiosk window is hidden via
  Win32 API (SW_HIDE). On close, the kiosk window is restored to
  fullscreen via SW_SHOW + SW_SHOWMAXIMIZED + SetForegroundWindow.

States: closed, idle, in_game, finished, unknown, error

Credit logic:
  Credits are decremented on game START (idle -> in_game), not on finish.
  State guard prevents double-decrement.

Session-end logic:
  Triggered by ANY exit from in_game:
    - in_game -> finished  (normal finish)
    - in_game -> idle      (game aborted / returned to lobby)
  On each: check credits. If exhausted → lock board, close browser, restore kiosk.
"""
import asyncio
import os
import sys
import logging
from typing import Optional, Dict, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

AUTODARTS_URL = os.environ.get('AUTODARTS_URL', 'https://play.autodarts.io')
OBSERVER_POLL_INTERVAL = int(os.environ.get('OBSERVER_POLL_INTERVAL', '4'))

# Persistent Chrome profile directory — preserves Google login across sessions
_default_profile = str(Path(os.environ.get('DATA_DIR', './data')) / 'chrome_profile')
CHROME_PROFILE_DIR = os.environ.get('CHROME_PROFILE_DIR', _default_profile)


class ObserverState(str, Enum):
    CLOSED = "closed"
    IDLE = "idle"
    IN_GAME = "in_game"
    FINISHED = "finished"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class ObserverStatus:
    board_id: str
    state: ObserverState = ObserverState.CLOSED
    browser_open: bool = False
    autodarts_url: str = ""
    games_observed: int = 0
    last_state_change: Optional[str] = None
    last_poll: Optional[str] = None
    last_error: Optional[str] = None
    chrome_profile: str = ""

    def to_dict(self) -> dict:
        return {
            "board_id": self.board_id,
            "state": self.state.value if isinstance(self.state, ObserverState) else self.state,
            "browser_open": self.browser_open,
            "autodarts_url": self.autodarts_url,
            "games_observed": self.games_observed,
            "last_state_change": self.last_state_change,
            "last_poll": self.last_poll,
            "last_error": self.last_error,
            "chrome_profile": self.chrome_profile,
        }


class AutodartsObserver:
    """
    Per-board observer. Opens the installed Chrome to the Autodarts URL
    using a persistent profile (login survives restarts), then polls
    the DOM periodically to detect game start/end.
    """

    def __init__(self, board_id: str):
        self.board_id = board_id
        self.status = ObserverStatus(board_id=board_id)
        self._context = None
        self._page = None
        self._playwright = None
        self._observe_task: Optional[asyncio.Task] = None
        self._stopping = False
        self._prev_state: ObserverState = ObserverState.CLOSED

        # Callbacks
        self._on_game_started: Optional[Callable] = None
        self._on_game_ended: Optional[Callable] = None

        # Per-game tracking
        self._credit_consumed = False

    @property
    def is_open(self) -> bool:
        return self._context is not None and self.status.browser_open

    async def open_session(
        self,
        autodarts_url: str,
        on_game_started: Optional[Callable] = None,
        on_game_ended: Optional[Callable] = None,
        headless: bool = False,
    ):
        """Open Chrome with persistent profile and start the observer loop."""
        if self.is_open:
            logger.info(f"[Observer:{self.board_id}] Browser already open, skipping")
            return

        self._on_game_started = on_game_started
        self._on_game_ended = on_game_ended
        self._stopping = False
        self._prev_state = ObserverState.CLOSED
        self._credit_consumed = False

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        # Persistent Chrome profile per board — NEVER recreated
        profile_dir = os.path.join(CHROME_PROFILE_DIR, self.board_id)
        profile_exists = os.path.exists(os.path.join(profile_dir, 'Default'))
        os.makedirs(profile_dir, exist_ok=True)
        self.status.chrome_profile = profile_dir

        logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH START ===")
        logger.info(f"[Observer:{self.board_id}]   URL: {url}")
        logger.info(f"[Observer:{self.board_id}]   headless: {headless}")
        logger.info(f"[Observer:{self.board_id}]   platform: {sys.platform}")
        logger.info(f"[Observer:{self.board_id}]   event_loop: {type(asyncio.get_event_loop_policy()).__name__}")
        logger.info(f"[Observer:{self.board_id}]   chrome_profile: {profile_dir}")
        if profile_exists:
            logger.info(f"[Observer:{self.board_id}]   profile_status: REUSING (Google login preserved)")
        else:
            logger.info(f"[Observer:{self.board_id}]   profile_status: NEW (first launch — login required)")

        try:
            logger.info(f"[Observer:{self.board_id}]   Step 1/5: Importing playwright...")
            from playwright.async_api import async_playwright

            logger.info(f"[Observer:{self.board_id}]   Step 2/5: Starting playwright runtime...")
            self._playwright = await async_playwright().start()

            # Chrome launch args — clean, no automation fingerprinting
            chrome_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-default-apps',
                '--disable-translate',
                '--disable-sync',
                '--disable-background-timer-throttling',
                '--no-first-run',
                '--no-default-browser-check',
                '--autoplay-policy=no-user-gesture-required',
            ]
            if not headless:
                chrome_args.extend([
                    '--start-fullscreen',
                    '--kiosk',
                ])

            logger.info(f"[Observer:{self.board_id}]   Step 3/5: Launching Chrome (persistent context, channel=chrome)...")

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",
                headless=headless,
                ignore_default_args=["--enable-automation"],
                args=chrome_args,
                viewport=None if not headless else {"width": 1280, "height": 800},
                no_viewport=not headless,
                ignore_https_errors=True,
                accept_downloads=False,
            )
            logger.info(f"[Observer:{self.board_id}]   Step 3/5: Chrome launched OK (no automation banner)")

            # Use existing page or create new one
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()

            logger.info(f"[Observer:{self.board_id}]   Step 4/5: Navigating to {url}...")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            self.status.browser_open = True
            self._set_state(ObserverState.IDLE)
            self._prev_state = ObserverState.IDLE
            logger.info(f"[Observer:{self.board_id}]   Step 5/5: Window management...")

            # OS-level window management: hide kiosk, Autodarts takes foreground
            try:
                from backend.services.window_manager import hide_kiosk_window
                await asyncio.sleep(1.5)  # Let Chrome window fully render
                await hide_kiosk_window()
                logger.info(f"[Observer:{self.board_id}]   Kiosk window hidden (Autodarts visible)")
            except Exception as wm_err:
                logger.warning(f"[Observer:{self.board_id}]   Window management skipped: {wm_err}")

            logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH SUCCESS ===")
            logger.info(f"[Observer:{self.board_id}]   Autodarts fullscreen, kiosk hidden")
            logger.info(f"[Observer:{self.board_id}]   Profile: {profile_dir}")

            self._observe_task = asyncio.create_task(self._observe_loop())

        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED ===")
            logger.error(f"[Observer:{self.board_id}]   Error type: {type(e).__name__}")
            logger.error(f"[Observer:{self.board_id}]   Error: {e}", exc_info=True)
            error_msg = str(e).split('\n')[0][:200]
            self.status.last_error = f"{type(e).__name__}: {error_msg}"
            self._set_state(ObserverState.ERROR)
            await self._cleanup()

    async def close_session(self):
        """Close Chrome and stop observing. Restore kiosk window."""
        logger.info(f"[Observer:{self.board_id}] Closing session...")
        self._stopping = True

        if self._observe_task and not self._observe_task.done():
            self._observe_task.cancel()
            try:
                await self._observe_task
            except asyncio.CancelledError:
                pass

        await self._cleanup()
        self._set_state(ObserverState.CLOSED)

        # Restore kiosk window to fullscreen foreground
        try:
            from backend.services.window_manager import restore_kiosk_window
            await asyncio.sleep(0.5)  # Brief pause after Chrome closes
            await restore_kiosk_window()
            logger.info(f"[Observer:{self.board_id}] Kiosk window restored to foreground")
        except Exception as wm_err:
            logger.warning(f"[Observer:{self.board_id}] Window restore skipped: {wm_err}")

        logger.info(f"[Observer:{self.board_id}] Session closed")

    async def _cleanup(self):
        """Close context and playwright. Profile data is preserved on disk."""
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
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

                logger.info(f"[Observer:{self.board_id}] === TRANSITION: {self._prev_state.value} -> {new_state.value} ===")
                self._set_state(new_state)

                # ─── GAME STARTED: * → in_game ─────────────────────
                if new_state == ObserverState.IN_GAME and self._prev_state != ObserverState.IN_GAME:
                    self._credit_consumed = True
                    self.status.games_observed += 1
                    logger.info(f"[Observer:{self.board_id}] GAME STARTED — credit_consumed=True, games_observed={self.status.games_observed}")
                    if self._on_game_started:
                        try:
                            await self._on_game_started(self.board_id)
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_started callback ERROR: {e}", exc_info=True)

                # ─── GAME FINISHED: in_game → finished ──────────────
                elif new_state == ObserverState.FINISHED and self._prev_state == ObserverState.IN_GAME:
                    logger.info(f"[Observer:{self.board_id}] GAME FINISHED — calling on_game_ended(reason='finished')")
                    if self._on_game_ended:
                        try:
                            await self._on_game_ended(self.board_id, "finished")
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended(finished) callback ERROR: {e}", exc_info=True)
                    self._credit_consumed = False

                # ─── GAME ABORTED: in_game → idle ──────────────────
                elif self._prev_state == ObserverState.IN_GAME and new_state in (ObserverState.IDLE, ObserverState.UNKNOWN):
                    logger.info(f"[Observer:{self.board_id}] GAME ABORTED — credit already consumed, calling on_game_ended(reason='aborted')")
                    if self._on_game_ended:
                        try:
                            await self._on_game_ended(self.board_id, "aborted")
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended(aborted) callback ERROR: {e}", exc_info=True)
                    self._credit_consumed = False

                # ─── POST-GAME: finished → idle (result dismissed) ──
                elif self._prev_state == ObserverState.FINISHED and new_state == ObserverState.IDLE:
                    logger.info(f"[Observer:{self.board_id}] POST-GAME: finished → idle (result screen dismissed)")
                    # Safety net: if session should have ended but didn't, check now
                    if self._on_game_ended:
                        try:
                            await self._on_game_ended(self.board_id, "post_finish_check")
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended(post_finish_check) ERROR: {e}", exc_info=True)

                self._prev_state = new_state

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Observer:{self.board_id}] Observe loop error: {e}")
                self.status.last_error = str(e)[:200]
                self._set_state(ObserverState.ERROR)
                self._prev_state = ObserverState.ERROR
                await asyncio.sleep(OBSERVER_POLL_INTERVAL * 2)

        logger.info(f"[Observer:{self.board_id}] Observe loop ended")

    async def _detect_state(self) -> ObserverState:
        """Detect game state from Autodarts DOM using minimal selectors."""
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
            self.status.last_error = str(e)[:200]
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
        on_game_ended=None,
        headless: bool = False,
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
            on_game_ended=on_game_ended,
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
