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

States: closed, idle, in_game, round_transition, finished, unknown, error

Credit logic:
  Credits are decremented on game START (idle -> in_game), not on finish.
  State guard prevents double-decrement.

Session-end logic:
  Triggered ONLY by confirmed exit from in_game:
    - in_game -> finished  (strong match-end markers: Rematch/Share buttons)
    - in_game -> idle      (game aborted / returned to lobby)
  ROUND_TRANSITION is NOT an exit signal — it indicates a normal turn/round
  change and resets the exit debounce counter.
  On confirmed exit: check credits. If exhausted → lock board, close browser, restore kiosk.

State detection priority:
  1. Strong match-end markers (Rematch/Share/NewGame button TEXT) → FINISHED
     ALWAYS wins, even if in_game markers are still present in DOM.
     (Autodarts keeps scoreboard elements visible on the results screen.)
  2. in_game markers WITHOUT strong end markers → IN_GAME
  3. Generic result CSS classes only → ROUND_TRANSITION
  4. Nothing → IDLE
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

# Debounce: exiting in_game requires N consecutive non-in_game polls
# This prevents false exits from turn changes / brief UI transitions
DEBOUNCE_EXIT_POLLS = int(os.environ.get('OBSERVER_DEBOUNCE_POLLS', '3'))
DEBOUNCE_POLL_INTERVAL = int(os.environ.get('OBSERVER_DEBOUNCE_INTERVAL', '2'))

# Persistent Chrome profile directory — preserves Google login across sessions
_default_profile = str(Path(os.environ.get('DATA_DIR', './data')) / 'chrome_profile')
CHROME_PROFILE_DIR = os.environ.get('CHROME_PROFILE_DIR', _default_profile)


class ObserverState(str, Enum):
    CLOSED = "closed"
    IDLE = "idle"
    IN_GAME = "in_game"
    ROUND_TRANSITION = "round_transition"
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

        # Stable confirmed state (only changes after debounce)
        self._stable_state: ObserverState = ObserverState.CLOSED

        # Callbacks
        self._on_game_started: Optional[Callable] = None
        self._on_game_ended: Optional[Callable] = None

        # Debounce tracking for exiting in_game
        self._exit_polls: int = 0          # Consecutive non-in_game polls
        self._exit_saw_finished: bool = False  # Any exit poll returned FINISHED?

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
        self._stable_state = ObserverState.CLOSED
        self._exit_polls = 0
        self._exit_saw_finished = False
        self._credit_consumed = False

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        # Persistent Chrome profile per board — NEVER recreated
        profile_dir = os.path.join(CHROME_PROFILE_DIR, self.board_id)
        profile_dir_abs = os.path.abspath(profile_dir)
        profile_default = os.path.join(profile_dir, 'Default')
        profile_exists = os.path.isdir(profile_default)
        os.makedirs(profile_dir, exist_ok=True)
        self.status.chrome_profile = profile_dir_abs

        logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH START ===")
        logger.info(f"[Observer:{self.board_id}]   URL: {url}")
        logger.info(f"[Observer:{self.board_id}]   headless: {headless}")
        logger.info(f"[Observer:{self.board_id}]   platform: {sys.platform}")
        logger.info(f"[Observer:{self.board_id}]   event_loop: {type(asyncio.get_event_loop_policy()).__name__}")
        logger.info(f"[Observer:{self.board_id}]   Using kiosk Chrome profile: {profile_dir_abs}")
        logger.info(f"[Observer:{self.board_id}]   profile_directory_exists: {os.path.isdir(profile_dir)}")
        logger.info(f"[Observer:{self.board_id}]   profile_has_data (Default/): {profile_exists}")
        if profile_exists:
            # Log evidence of existing profile content
            try:
                default_contents = os.listdir(profile_default)
                has_cookies = 'Cookies' in default_contents
                has_extensions = os.path.isdir(os.path.join(profile_default, 'Extensions'))
                ext_count = len(os.listdir(os.path.join(profile_default, 'Extensions'))) if has_extensions else 0
                logger.info(f"[Observer:{self.board_id}]   profile_status: REUSING EXISTING PROFILE")
                logger.info(f"[Observer:{self.board_id}]     cookies_present: {has_cookies}")
                logger.info(f"[Observer:{self.board_id}]     extensions_dir: {has_extensions} ({ext_count} entries)")
                logger.info(f"[Observer:{self.board_id}]     → Google login + extensions will be preserved")
            except Exception:
                logger.info(f"[Observer:{self.board_id}]   profile_status: REUSING (could not inspect contents)")
        else:
            logger.info(f"[Observer:{self.board_id}]   profile_status: NEW PROFILE (first launch)")
            logger.info(f"[Observer:{self.board_id}]     → Run setup_profile.bat first to log in and install extensions")

        try:
            logger.info(f"[Observer:{self.board_id}]   Step 1/5: Importing playwright...")
            from playwright.async_api import async_playwright

            logger.info(f"[Observer:{self.board_id}]   Step 2/5: Starting playwright runtime...")
            self._playwright = await async_playwright().start()

            # Chrome launch args — clean, preserve extensions, no automation fingerprint
            chrome_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
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

            # Playwright default args to EXCLUDE so extensions + login work:
            #   --enable-automation          → causes "controlled by automation" banner
            #   --disable-extensions         → prevents operator-installed extensions
            #   --disable-component-extensions-with-background-pages → breaks some extensions
            ignore_args = [
                "--enable-automation",
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
            ]

            logger.info(f"[Observer:{self.board_id}]   Step 3/5: Launching Chrome (persistent context, channel=chrome)...")
            logger.info(f"[Observer:{self.board_id}]   ignore_default_args: {ignore_args}")
            logger.info(f"[Observer:{self.board_id}]   custom args: {chrome_args}")

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",
                headless=headless,
                ignore_default_args=ignore_args,
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
            self._stable_state = ObserverState.IDLE
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
        """
        Poll the Autodarts page for game state changes.

        STATE MAPPING HIERARCHY (from _detect_state):
          IN_GAME          — active match markers (scoreboard, dart-input, etc.)
          FINISHED         — strong end-of-match markers (Rematch/Share/NewGame buttons)
          ROUND_TRANSITION — generic result/winner CSS classes only (turn/round change)
          IDLE             — no game markers (lobby/setup)

        DEBOUNCE LOGIC for exiting IN_GAME:
          ROUND_TRANSITION → does NOT count as exit. Normal turn change.
          FINISHED         → counts as exit poll (saw_finished=True).
          IDLE             → counts as exit poll (abort scenario).
          IN_GAME          → resets exit counter (still playing).

          Only DEBOUNCE_EXIT_POLLS consecutive FINISHED/IDLE polls confirm an exit.
          ROUND_TRANSITION polls reset the counter because they indicate the
          match is still active (just between turns).

        Credit logic: credits consumed on first IN_GAME detection (immediate).
        """
        logger.info(f"[Observer:{self.board_id}] Observe loop started")
        logger.info(f"[Observer:{self.board_id}]   normal_poll: {OBSERVER_POLL_INTERVAL}s")
        logger.info(f"[Observer:{self.board_id}]   debounce_exit_polls: {DEBOUNCE_EXIT_POLLS}")
        logger.info(f"[Observer:{self.board_id}]   debounce_poll: {DEBOUNCE_POLL_INTERVAL}s")

        while not self._stopping:
            try:
                # Use faster polling during debounce confirmation
                interval = DEBOUNCE_POLL_INTERVAL if self._exit_polls > 0 else OBSERVER_POLL_INTERVAL
                await asyncio.sleep(interval)
                if not self._page or self._stopping:
                    break

                raw = await self._detect_state()
                now = datetime.now(timezone.utc).isoformat()
                self.status.last_poll = now

                stable = self._stable_state

                # ═══════════════════════════════════════════════
                # CASE A: Stable state is IN_GAME (match active)
                # ═══════════════════════════════════════════════
                if stable == ObserverState.IN_GAME:
                    if raw == ObserverState.IN_GAME:
                        # Still in game — clear any pending exit
                        if self._exit_polls > 0:
                            logger.info(
                                f"[Observer:{self.board_id}] debounce: RECOVERED to IN_GAME "
                                f"after {self._exit_polls} exit polls (turn change / UI flicker)"
                            )
                            self._exit_polls = 0
                            self._exit_saw_finished = False
                        continue

                    if raw == ObserverState.ROUND_TRANSITION:
                        # Normal turn/round change — NOT an exit signal.
                        # Reset exit counter: the match is clearly still active.
                        if self._exit_polls > 0:
                            logger.info(
                                f"[Observer:{self.board_id}] debounce: RESET by ROUND_TRANSITION "
                                f"(was at {self._exit_polls}/{DEBOUNCE_EXIT_POLLS} exit polls) — "
                                f"turn change detected, match still active"
                            )
                            self._exit_polls = 0
                            self._exit_saw_finished = False
                        else:
                            logger.info(
                                f"[Observer:{self.board_id}] ROUND_TRANSITION detected — "
                                f"normal turn/round change, session continues"
                            )
                        continue

                    # ─── IDLE or FINISHED: real exit candidate ─────
                    self._exit_polls += 1
                    if raw == ObserverState.FINISHED:
                        self._exit_saw_finished = True

                    logger.info(
                        f"[Observer:{self.board_id}] debounce: exit poll "
                        f"{self._exit_polls}/{DEBOUNCE_EXIT_POLLS} "
                        f"(raw={raw.value}, saw_finished={self._exit_saw_finished})"
                    )

                    if self._exit_polls < DEBOUNCE_EXIT_POLLS:
                        # Not yet confirmed — continue polling faster
                        continue

                    # ─── CONFIRMED: match is really over ──────────
                    reason = "finished" if self._exit_saw_finished else "aborted"
                    confirmed_state = ObserverState.FINISHED if self._exit_saw_finished else raw

                    logger.info(
                        f"[Observer:{self.board_id}] === DEBOUNCE CONFIRMED: "
                        f"in_game -> {confirmed_state.value} (reason={reason}) ==="
                    )
                    logger.info(
                        f"[Observer:{self.board_id}]   exit polls needed: {DEBOUNCE_EXIT_POLLS}, "
                        f"saw_finished: {self._exit_saw_finished}"
                    )

                    self._stable_state = confirmed_state
                    self._set_state(confirmed_state)
                    self._exit_polls = 0
                    self._exit_saw_finished = False

                    # Fire callback
                    if self._on_game_ended:
                        try:
                            await self._on_game_ended(self.board_id, reason)
                        except Exception as e:
                            logger.error(
                                f"[Observer:{self.board_id}] on_game_ended({reason}) ERROR: {e}",
                                exc_info=True,
                            )
                    self._credit_consumed = False

                # ═══════════════════════════════════════════════
                # CASE B: Stable state is NOT in_game
                # ═══════════════════════════════════════════════
                else:
                    if raw == stable:
                        continue  # No change

                    # Normalize ROUND_TRANSITION to IDLE for non-in_game stable states
                    # (round_transition only matters when we're actively in a game)
                    effective_raw = raw
                    if raw == ObserverState.ROUND_TRANSITION:
                        effective_raw = ObserverState.IDLE
                        logger.info(
                            f"[Observer:{self.board_id}] ROUND_TRANSITION outside IN_GAME "
                            f"→ treating as IDLE (stable={stable.value})"
                        )

                    if effective_raw == stable:
                        continue

                    # ─── Entering IN_GAME: immediate (credit consumed) ──
                    if effective_raw == ObserverState.IN_GAME:
                        logger.info(
                            f"[Observer:{self.board_id}] === TRANSITION: "
                            f"{stable.value} -> in_game (immediate) ==="
                        )
                        self._stable_state = ObserverState.IN_GAME
                        self._set_state(ObserverState.IN_GAME)
                        self._credit_consumed = True
                        self._exit_polls = 0
                        self._exit_saw_finished = False
                        self.status.games_observed += 1

                        logger.info(
                            f"[Observer:{self.board_id}] GAME STARTED — "
                            f"credit_consumed=True, games_observed={self.status.games_observed}"
                        )
                        if self._on_game_started:
                            try:
                                await self._on_game_started(self.board_id)
                            except Exception as e:
                                logger.error(
                                    f"[Observer:{self.board_id}] on_game_started ERROR: {e}",
                                    exc_info=True,
                                )

                    # ─── Post-game: finished → idle (result dismissed) ──
                    elif stable == ObserverState.FINISHED and effective_raw == ObserverState.IDLE:
                        logger.info(
                            f"[Observer:{self.board_id}] === TRANSITION: "
                            f"finished -> idle (result dismissed) ==="
                        )
                        self._stable_state = ObserverState.IDLE
                        self._set_state(ObserverState.IDLE)

                        if self._on_game_ended:
                            try:
                                await self._on_game_ended(self.board_id, "post_finish_check")
                            except Exception as e:
                                logger.error(
                                    f"[Observer:{self.board_id}] "
                                    f"on_game_ended(post_finish_check) ERROR: {e}",
                                    exc_info=True,
                                )

                    # ─── Other transitions (idle ↔ unknown, etc.) ──
                    else:
                        logger.info(
                            f"[Observer:{self.board_id}] === TRANSITION: "
                            f"{stable.value} -> {effective_raw.value} ==="
                        )
                        self._stable_state = effective_raw
                        self._set_state(effective_raw)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Observer:{self.board_id}] Observe loop error: {e}")
                self.status.last_error = str(e)[:200]
                self._set_state(ObserverState.ERROR)
                self._stable_state = ObserverState.ERROR
                await asyncio.sleep(OBSERVER_POLL_INTERVAL * 2)

        logger.info(f"[Observer:{self.board_id}] Observe loop ended")

    async def _detect_state(self) -> ObserverState:
        """
        Three-tier DOM detection: in_game > match_finished > round_transition > idle.

        Tier 1 — IN_GAME: Active match markers (scoreboard, dart input, etc.).
                 If present, state is always IN_GAME regardless of other signals.

        Tier 2 — FINISHED (match_finished): Definitive end-of-match markers.
                 ONLY button text matching (Rematch, Play again, Share, New Game)
                 qualifies. CSS class-based markers alone are NOT sufficient
                 because Autodarts reuses generic classes during round transitions.

        Tier 3 — ROUND_TRANSITION: Generic result/winner/finished CSS classes
                 WITHOUT the strong button-text markers. This is the normal
                 state between turns/rounds/legs. Must NOT trigger session end.

        Tier 4 — IDLE: No game-related markers at all (lobby/setup screen).
        """
        try:
            signals = await self._page.evaluate("""() => {
                // === Tier 1: Active match indicators ===
                const inGame = !!(
                    document.querySelector('[class*="scoreboard"]') ||
                    document.querySelector('[class*="dart-input"]') ||
                    document.querySelector('[class*="throw"]') ||
                    document.querySelector('[class*="scoring"]') ||
                    document.querySelector('[class*="game-view"]') ||
                    document.querySelector('[class*="match-view"]') ||
                    document.querySelector('[class*="player-score"]') ||
                    document.querySelector('[class*="turn"]') ||
                    document.querySelector('[class*="match"][class*="running"]') ||
                    document.querySelector('[data-testid*="match"]') ||
                    document.querySelector('#match')
                );

                // === Tier 2: Strong end-of-match markers (button text ONLY) ===
                // These buttons ONLY appear after the ENTIRE match is over.
                const allButtons = Array.from(document.querySelectorAll('button, a[role="button"], [class*="btn"]'));
                const buttonTexts = allButtons.map(function(b) { return (b.textContent || '').trim().toLowerCase(); });

                const hasRematchBtn = buttonTexts.some(function(t) {
                    return /rematch|nochmal spielen|play again|erneut spielen/i.test(t);
                });
                const hasShareBtn = buttonTexts.some(function(t) {
                    return /share|teilen|share result|ergebnis teilen/i.test(t);
                });
                const hasNewGameBtn = buttonTexts.some(function(t) {
                    return /new game|neues spiel|new match|neues match/i.test(t);
                });

                // Also check for post-match summary containers
                const hasPostMatchUI = !!(
                    document.querySelector('[class*="post-match"]') ||
                    document.querySelector('[class*="match-summary"]') ||
                    document.querySelector('[class*="match-end"]') ||
                    document.querySelector('[class*="game-over"]')
                );

                const strongMatchEnd = hasRematchBtn || hasShareBtn || hasNewGameBtn || hasPostMatchUI;

                // === Tier 3: Generic result markers (round/turn transitions) ===
                const hasGenericResult = !!(
                    document.querySelector('[class*="result"]') ||
                    document.querySelector('[class*="winner"]') ||
                    document.querySelector('[class*="finished"]') ||
                    document.querySelector('[class*="match-result"]') ||
                    document.querySelector('[class*="leg-result"]')
                );

                return {
                    inGame: inGame,
                    strongMatchEnd: strongMatchEnd,
                    hasGenericResult: hasGenericResult,
                    // Debug detail
                    _detail: {
                        hasRematchBtn: hasRematchBtn,
                        hasShareBtn: hasShareBtn,
                        hasNewGameBtn: hasNewGameBtn,
                        hasPostMatchUI: hasPostMatchUI,
                        buttonSample: buttonTexts.slice(0, 5)
                    }
                };
            }""")

            in_game = signals.get('inGame', False)
            strong_match_end = signals.get('strongMatchEnd', False)
            has_generic_result = signals.get('hasGenericResult', False)
            detail = signals.get('_detail', {})

            # Always log raw detection for traceability
            logger.info(
                f"[Observer:{self.board_id}] raw_detected_state: "
                f"in_game={in_game}, strong_match_end={strong_match_end}, "
                f"generic_result={has_generic_result}, "
                f"detail={detail}"
            )

            # === State mapping ===
            # PRIORITY ORDER:
            #   1. Strong match-end markers → FINISHED (ALWAYS, even with in_game present)
            #   2. in_game WITHOUT strong markers → IN_GAME
            #   3. Generic result only → ROUND_TRANSITION
            #   4. Nothing → IDLE
            #
            # WHY strong markers override in_game:
            # On the Autodarts match-end screen, scoreboard/match-view elements
            # remain in the DOM alongside Rematch/Share buttons. If we let in_game
            # markers take priority, FINISHED is never detected and the last-credit
            # lock never fires.

            # Tier 1: Strong end-of-match markers ALWAYS win
            if strong_match_end:
                logger.info(
                    f"[Observer:{self.board_id}] mapped_state: FINISHED | "
                    f"reason: match_finished — strong end markers detected "
                    f"(rematch={detail.get('hasRematchBtn')}, "
                    f"share={detail.get('hasShareBtn')}, "
                    f"newgame={detail.get('hasNewGameBtn')}, "
                    f"postmatch_ui={detail.get('hasPostMatchUI')}), "
                    f"in_game_markers_also_present={in_game}"
                )
                return ObserverState.FINISHED

            # Tier 2: in_game markers WITHOUT strong end markers → active match
            if in_game:
                reason = "active match markers present, no strong end markers"
                if has_generic_result:
                    reason += " + round result overlay (normal turn change)"
                logger.info(f"[Observer:{self.board_id}] mapped_state: IN_GAME | reason: {reason}")
                return ObserverState.IN_GAME

            # Tier 3: Generic result markers WITHOUT strong markers → round transition
            if has_generic_result:
                logger.info(
                    f"[Observer:{self.board_id}] mapped_state: ROUND_TRANSITION | "
                    f"reason: generic result/winner/finished CSS classes detected "
                    f"but NO strong match-end buttons — interpreting as turn/round change"
                )
                return ObserverState.ROUND_TRANSITION

            # Tier 4: Nothing game-related → lobby/setup
            logger.info(f"[Observer:{self.board_id}] mapped_state: IDLE | reason: no game markers detected")
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
