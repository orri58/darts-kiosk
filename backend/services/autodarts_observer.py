"""
Autodarts Observer Service — Event-Driven Match Detection
==========================================================

PRIMARY detection: WebSocket/console event capture (injected JS intercepts
Autodarts' own real-time messages and console output).

FALLBACK detection: DOM/UI polling (button text, CSS classes).

Key signals captured from Autodarts:
  - WebSocket messages on autodarts.matches channels (state, game-events)
  - Console output: "Winner Animation", "gameshot", "matchshot"
  - Match state transitions: active -> finished

Credit logic:
  Credits are decremented on game START (idle -> in_game), not on finish.

Session-end logic:
  Triggered ONLY by confirmed exit from in_game:
    - Event-driven: WebSocket match_state="finished" + matchshot event
    - DOM fallback: strong match-end markers (Rematch/Share buttons)
    - Abort: return to lobby (idle)
  On confirmed exit: check credits. If exhausted -> lock board, close browser, restore kiosk.
"""
import asyncio
import os
import sys
import logging
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

AUTODARTS_URL = os.environ.get('AUTODARTS_URL', 'https://play.autodarts.io')
OBSERVER_POLL_INTERVAL = int(os.environ.get('OBSERVER_POLL_INTERVAL', '4'))

# Debounce: exiting in_game requires N consecutive non-in_game polls
DEBOUNCE_EXIT_POLLS = int(os.environ.get('OBSERVER_DEBOUNCE_POLLS', '3'))
DEBOUNCE_POLL_INTERVAL = int(os.environ.get('OBSERVER_DEBOUNCE_INTERVAL', '2'))

# Persistent Chrome profile directory
_default_profile = str(Path(os.environ.get('DATA_DIR', './data')) / 'chrome_profile')
CHROME_PROFILE_DIR = os.environ.get('CHROME_PROFILE_DIR', _default_profile)

# ── JavaScript injected into the Autodarts page ──
# Intercepts WebSocket messages and console.log output to capture
# match state changes, game events, and winner signals.
WS_INTERCEPT_SCRIPT = """
(() => {
    if (window.__dartsKioskCapture) return; // Already injected

    window.__dartsKioskCapture = {
        matchState: null,          // Latest match state string
        matchFinished: false,      // Definitive match-end detected
        matchStarted: false,       // Match currently active
        winnerDetected: false,     // Winner animation / matchshot
        lastGameEvent: null,       // Last game event type
        lastMatchId: null,         // Last seen match ID
        events: [],                // Ring buffer of last 50 events
        wsMessageCount: 0,         // Total WS messages captured
        consoleCaptures: 0,        // Total console captures
        lastUpdate: null,          // ISO timestamp of last event

        _pushEvent: function(type, data) {
            var entry = {
                type: type,
                data: data,
                ts: new Date().toISOString()
            };
            this.events.push(entry);
            if (this.events.length > 50) this.events.shift();
            this.lastUpdate = entry.ts;
        },

        reset: function() {
            this.matchState = null;
            this.matchFinished = false;
            this.matchStarted = false;
            this.winnerDetected = false;
            this.lastGameEvent = null;
            this.events = [];
        }
    };

    // ── 1. WebSocket message interception ──
    var OrigWebSocket = window.WebSocket;
    var origSend = OrigWebSocket.prototype.send;

    // Patch each new WebSocket instance
    var origAddEventListener = OrigWebSocket.prototype.addEventListener;
    var patchWs = function(ws) {
        if (ws.__dartsPatched) return;
        ws.__dartsPatched = true;

        var origOnMessage = null;
        var descriptor = Object.getOwnPropertyDescriptor(ws, 'onmessage') ||
                         Object.getOwnPropertyDescriptor(OrigWebSocket.prototype, 'onmessage');

        ws.addEventListener('message', function(evt) {
            try {
                var raw = typeof evt.data === 'string' ? evt.data : '';
                if (!raw) return;

                window.__dartsKioskCapture.wsMessageCount++;

                // Autodarts uses patterns like:
                //   autodarts.matches.{id}.state
                //   autodarts.matches.{id}.game-events
                var isMatchMsg = raw.indexOf('autodarts.matches') !== -1 ||
                                 raw.indexOf('match') !== -1;
                if (!isMatchMsg) return;

                // Try to extract JSON payload
                var payload = null;
                try {
                    // Messages may be JSON or JSON inside a wrapper
                    payload = JSON.parse(raw);
                } catch(e) {
                    // Try extracting JSON from mixed format (e.g. "42[event,{...}]")
                    var jsonStart = raw.indexOf('{');
                    var jsonEnd = raw.lastIndexOf('}');
                    if (jsonStart !== -1 && jsonEnd > jsonStart) {
                        try {
                            payload = JSON.parse(raw.substring(jsonStart, jsonEnd + 1));
                        } catch(e2) {}
                    }
                }

                // ── Match state messages ──
                if (raw.indexOf('.state') !== -1 || raw.indexOf('state') !== -1) {
                    var state = null;
                    if (payload) {
                        state = payload.state || payload.matchState ||
                                (payload.data && payload.data.state) ||
                                (payload.match && payload.match.state);
                    }
                    if (state) {
                        window.__dartsKioskCapture.matchState = state;
                        window.__dartsKioskCapture._pushEvent('ws_match_state', { state: state, raw_length: raw.length });

                        if (state === 'finished' || state === 'completed' || state === 'ended') {
                            window.__dartsKioskCapture.matchFinished = true;
                        }
                        if (state === 'active' || state === 'running' || state === 'started') {
                            window.__dartsKioskCapture.matchStarted = true;
                            window.__dartsKioskCapture.matchFinished = false;
                            window.__dartsKioskCapture.winnerDetected = false;
                        }
                    }
                }

                // ── Game event messages ──
                if (raw.indexOf('game-event') !== -1 || raw.indexOf('gameEvent') !== -1 ||
                    raw.indexOf('matchshot') !== -1 || raw.indexOf('gameshot') !== -1) {
                    var eventType = null;
                    if (payload) {
                        eventType = payload.type || payload.event || payload.eventType ||
                                    (payload.data && (payload.data.type || payload.data.event));
                    }
                    // Also check raw string for key signals
                    if (!eventType) {
                        if (raw.indexOf('matchshot') !== -1) eventType = 'matchshot';
                        else if (raw.indexOf('gameshot') !== -1) eventType = 'gameshot';
                    }
                    if (eventType) {
                        window.__dartsKioskCapture.lastGameEvent = eventType;
                        window.__dartsKioskCapture._pushEvent('ws_game_event', { event: eventType });

                        var lower = eventType.toLowerCase();
                        if (lower === 'matchshot' || lower === 'match_won' || lower === 'match_finished') {
                            window.__dartsKioskCapture.matchFinished = true;
                            window.__dartsKioskCapture.winnerDetected = true;
                        }
                    }
                }

                // ── Match ID tracking ──
                if (payload) {
                    var matchId = payload.matchId || payload.match_id ||
                                  (payload.data && (payload.data.matchId || payload.data.match_id)) ||
                                  (payload.match && payload.match.id);
                    if (matchId) {
                        window.__dartsKioskCapture.lastMatchId = matchId;
                    }
                }

            } catch(err) {
                // Silent - don't break Autodarts
            }
        });
    };

    // Patch existing WebSocket instances and new ones
    var OrigWsConstruct = window.WebSocket;
    window.WebSocket = function(url, protocols) {
        var ws = protocols ? new OrigWsConstruct(url, protocols) : new OrigWsConstruct(url);
        setTimeout(function() { patchWs(ws); }, 0);
        return ws;
    };
    window.WebSocket.prototype = OrigWsConstruct.prototype;
    window.WebSocket.CONNECTING = OrigWsConstruct.CONNECTING;
    window.WebSocket.OPEN = OrigWsConstruct.OPEN;
    window.WebSocket.CLOSING = OrigWsConstruct.CLOSING;
    window.WebSocket.CLOSED = OrigWsConstruct.CLOSED;

    // ── 2. Console.log interception ──
    // Autodarts logs "Winner Animation - Initializing", "gameshot", "matchshot"
    var origLog = console.log;
    console.log = function() {
        origLog.apply(console, arguments);
        try {
            var msg = Array.prototype.join.call(arguments, ' ');
            var cap = window.__dartsKioskCapture;

            if (/winner.?animation/i.test(msg)) {
                cap.winnerDetected = true;
                cap.matchFinished = true;
                cap._pushEvent('console_winner_animation', { msg: msg.substring(0, 200) });
                cap.consoleCaptures++;
            }
            else if (/matchshot/i.test(msg)) {
                cap.matchFinished = true;
                cap.winnerDetected = true;
                cap.lastGameEvent = 'matchshot';
                cap._pushEvent('console_matchshot', { msg: msg.substring(0, 200) });
                cap.consoleCaptures++;
            }
            else if (/gameshot/i.test(msg)) {
                cap.lastGameEvent = 'gameshot';
                cap._pushEvent('console_gameshot', { msg: msg.substring(0, 200) });
                cap.consoleCaptures++;
            }
            else if (/match.*finish|match.*end|match.*complet/i.test(msg)) {
                cap.matchFinished = true;
                cap._pushEvent('console_match_end', { msg: msg.substring(0, 200) });
                cap.consoleCaptures++;
            }
        } catch(e) {}
    };

    console.log('[DartsKiosk] WebSocket + console capture injected');
})();
"""


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
    Per-board observer. Opens Chrome to Autodarts using a persistent profile,
    injects WebSocket/console interceptors, and detects match state primarily
    from captured events with DOM polling as fallback.
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
        self._exit_polls: int = 0
        self._exit_saw_finished: bool = False

        # Per-game tracking
        self._credit_consumed = False

        # Event-driven tracking
        self._ws_interceptor_injected = False

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
        self._ws_interceptor_injected = False

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        # Persistent Chrome profile per board
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
        logger.info(f"[Observer:{self.board_id}]   profile: {profile_dir_abs} (exists={profile_exists})")

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            chrome_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-background-timer-throttling',
                '--no-first-run',
                '--no-default-browser-check',
                '--autoplay-policy=no-user-gesture-required',
            ]
            if not headless:
                chrome_args.extend(['--start-fullscreen', '--kiosk'])

            ignore_args = [
                "--enable-automation",
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
            ]

            logger.info(f"[Observer:{self.board_id}]   Launching Chrome (persistent context, channel=chrome)...")
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
            logger.info(f"[Observer:{self.board_id}]   Chrome launched OK")

            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()

            logger.info(f"[Observer:{self.board_id}]   Navigating to {url}...")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Inject WebSocket/console interceptor BEFORE any match events
            await self._inject_ws_interceptor()

            self.status.browser_open = True
            self._set_state(ObserverState.IDLE)
            self._stable_state = ObserverState.IDLE

            # OS-level window management
            try:
                from backend.services.window_manager import hide_kiosk_window
                await asyncio.sleep(1.5)
                await hide_kiosk_window()
                logger.info(f"[Observer:{self.board_id}]   Kiosk window hidden")
            except Exception as wm_err:
                logger.warning(f"[Observer:{self.board_id}]   Window management skipped: {wm_err}")

            logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH SUCCESS ===")
            self._observe_task = asyncio.create_task(self._observe_loop())

        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED === {e}", exc_info=True)
            self.status.last_error = f"{type(e).__name__}: {str(e)[:200]}"
            self._set_state(ObserverState.ERROR)
            await self._cleanup()

    async def _inject_ws_interceptor(self):
        """Inject the WebSocket/console capture script into the Autodarts page."""
        if self._ws_interceptor_injected or not self._page:
            return
        try:
            await self._page.evaluate(WS_INTERCEPT_SCRIPT)
            self._ws_interceptor_injected = True
            logger.info(f"[Observer:{self.board_id}] WebSocket/console interceptor injected")
        except Exception as e:
            logger.warning(f"[Observer:{self.board_id}] Interceptor injection failed: {e}")

    async def close_session(self):
        """Close Chrome and stop observing. Restore kiosk window."""
        logger.info(f"[Observer:{self.board_id}] === CLOSE SESSION START ===")
        self._stopping = True

        if self._observe_task and not self._observe_task.done():
            logger.info(f"[Observer:{self.board_id}]   cancelling observe_task...")
            self._observe_task.cancel()
            try:
                await self._observe_task
            except asyncio.CancelledError:
                pass

        await self._cleanup()
        self._set_state(ObserverState.CLOSED)

        # Restore kiosk window
        try:
            from backend.services.window_manager import restore_kiosk_window
            logger.info(f"[Observer:{self.board_id}]   restoring kiosk window...")
            await asyncio.sleep(0.5)
            await restore_kiosk_window()
            logger.info(f"[Observer:{self.board_id}]   kiosk window restored OK")
        except Exception as wm_err:
            logger.warning(f"[Observer:{self.board_id}]   kiosk window restore FAILED: {wm_err}")

        logger.info(f"[Observer:{self.board_id}] === CLOSE SESSION COMPLETE ===")

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
        self._ws_interceptor_injected = False

    # ═══════════════════════════════════════════════════════════════
    # OBSERVE LOOP
    # ═══════════════════════════════════════════════════════════════

    async def _observe_loop(self):
        """
        Main observation loop. Each cycle:
          1. Read captured WebSocket/console events (primary source)
          2. Fall back to DOM detection if no event data
          3. Apply debounce logic for state transitions

        Priority: WS events > DOM signals > fallback
        """
        logger.info(f"[Observer:{self.board_id}] Observe loop started (event-driven + DOM fallback)")
        logger.info(f"[Observer:{self.board_id}]   poll_interval={OBSERVER_POLL_INTERVAL}s, "
                     f"debounce_polls={DEBOUNCE_EXIT_POLLS}, debounce_interval={DEBOUNCE_POLL_INTERVAL}s")

        while not self._stopping:
            try:
                interval = DEBOUNCE_POLL_INTERVAL if self._exit_polls > 0 else OBSERVER_POLL_INTERVAL
                await asyncio.sleep(interval)
                if not self._page or self._stopping:
                    break

                # Re-inject interceptor if page navigated
                if not self._ws_interceptor_injected:
                    await self._inject_ws_interceptor()

                # ── PRIMARY: Read captured events ──
                event_state = await self._read_captured_events()

                # ── FALLBACK: DOM detection ──
                dom_state = await self._detect_state_dom()

                # ── MERGE: Events take priority ──
                raw = self._merge_detection(event_state, dom_state)

                now = datetime.now(timezone.utc).isoformat()
                self.status.last_poll = now
                stable = self._stable_state

                # ═══════════════════════════════════════════
                # CASE A: Currently IN_GAME
                # ═══════════════════════════════════════════
                if stable == ObserverState.IN_GAME:
                    if raw == ObserverState.IN_GAME:
                        if self._exit_polls > 0:
                            logger.info(f"[Observer:{self.board_id}] debounce: RECOVERED to IN_GAME "
                                        f"after {self._exit_polls} exit polls")
                            self._exit_polls = 0
                            self._exit_saw_finished = False
                        continue

                    if raw == ObserverState.ROUND_TRANSITION:
                        if self._exit_polls > 0:
                            logger.info(f"[Observer:{self.board_id}] debounce: RESET by ROUND_TRANSITION "
                                        f"({self._exit_polls}/{DEBOUNCE_EXIT_POLLS}) — turn change")
                            self._exit_polls = 0
                            self._exit_saw_finished = False
                        continue

                    # ─── IDLE or FINISHED: exit candidate ─────
                    self._exit_polls += 1
                    if raw == ObserverState.FINISHED:
                        self._exit_saw_finished = True

                    logger.info(f"[Observer:{self.board_id}] debounce: exit poll "
                                f"{self._exit_polls}/{DEBOUNCE_EXIT_POLLS} "
                                f"(raw={raw.value}, saw_finished={self._exit_saw_finished})")

                    if self._exit_polls < DEBOUNCE_EXIT_POLLS:
                        continue

                    # ─── CONFIRMED: match is really over ──────────
                    reason = "finished" if self._exit_saw_finished else "aborted"
                    confirmed_state = ObserverState.FINISHED if self._exit_saw_finished else raw

                    logger.info(f"[Observer:{self.board_id}] === DEBOUNCE CONFIRMED: "
                                f"in_game -> {confirmed_state.value} (reason={reason}) ===")

                    self._stable_state = confirmed_state
                    self._set_state(confirmed_state)
                    self._exit_polls = 0
                    self._exit_saw_finished = False

                    if self._on_game_ended:
                        try:
                            await self._on_game_ended(self.board_id, reason)
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended({reason}) ERROR: {e}",
                                         exc_info=True)
                    self._credit_consumed = False

                    # Reset captured events for next game
                    await self._reset_captured_events()

                # ═══════════════════════════════════════════
                # CASE B: NOT in_game
                # ═══════════════════════════════════════════
                else:
                    if raw == stable:
                        continue

                    effective_raw = raw
                    if raw == ObserverState.ROUND_TRANSITION:
                        effective_raw = ObserverState.IDLE

                    if effective_raw == stable:
                        continue

                    # ─── Entering IN_GAME ──
                    if effective_raw == ObserverState.IN_GAME:
                        logger.info(f"[Observer:{self.board_id}] === TRANSITION: "
                                    f"{stable.value} -> in_game (immediate) ===")
                        self._stable_state = ObserverState.IN_GAME
                        self._set_state(ObserverState.IN_GAME)
                        self._credit_consumed = True
                        self._exit_polls = 0
                        self._exit_saw_finished = False
                        self.status.games_observed += 1

                        # Reset captured events for fresh game tracking
                        await self._reset_captured_events()

                        logger.info(f"[Observer:{self.board_id}] GAME STARTED — "
                                    f"games_observed={self.status.games_observed}")
                        if self._on_game_started:
                            try:
                                await self._on_game_started(self.board_id)
                            except Exception as e:
                                logger.error(f"[Observer:{self.board_id}] on_game_started ERROR: {e}",
                                             exc_info=True)

                    elif stable == ObserverState.FINISHED and effective_raw == ObserverState.IDLE:
                        logger.info(f"[Observer:{self.board_id}] === TRANSITION: "
                                    f"finished -> idle (result dismissed) ===")
                        self._stable_state = ObserverState.IDLE
                        self._set_state(ObserverState.IDLE)

                        if self._on_game_ended:
                            try:
                                await self._on_game_ended(self.board_id, "post_finish_check")
                            except Exception as e:
                                logger.error(f"[Observer:{self.board_id}] "
                                             f"on_game_ended(post_finish_check) ERROR: {e}", exc_info=True)
                    else:
                        logger.info(f"[Observer:{self.board_id}] === TRANSITION: "
                                    f"{stable.value} -> {effective_raw.value} ===")
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

    # ═══════════════════════════════════════════════════════════════
    # EVENT CAPTURE (PRIMARY)
    # ═══════════════════════════════════════════════════════════════

    async def _read_captured_events(self) -> Optional[ObserverState]:
        """
        Read the captured WebSocket/console data from the injected script.
        Returns a definitive ObserverState if event data is available,
        or None if no event data captured.
        """
        try:
            data = await self._page.evaluate("""() => {
                var cap = window.__dartsKioskCapture;
                if (!cap) return null;
                return {
                    matchState: cap.matchState,
                    matchFinished: cap.matchFinished,
                    matchStarted: cap.matchStarted,
                    winnerDetected: cap.winnerDetected,
                    lastGameEvent: cap.lastGameEvent,
                    lastMatchId: cap.lastMatchId,
                    wsMessageCount: cap.wsMessageCount,
                    consoleCaptures: cap.consoleCaptures,
                    recentEvents: cap.events.slice(-5)
                };
            }""")
        except Exception as e:
            logger.warning(f"[Observer:{self.board_id}] event_capture_read_error: {e}")
            self._ws_interceptor_injected = False
            return None

        if not data:
            return None

        match_state = data.get('matchState')
        match_finished = data.get('matchFinished', False)
        winner_detected = data.get('winnerDetected', False)
        match_started = data.get('matchStarted', False)
        last_game_event = data.get('lastGameEvent')
        ws_count = data.get('wsMessageCount', 0)
        console_count = data.get('consoleCaptures', 0)
        recent = data.get('recentEvents', [])

        # Log captured data
        if ws_count > 0 or console_count > 0:
            logger.info(
                f"[Observer:{self.board_id}] event_capture: "
                f"match_state={match_state}, finished={match_finished}, "
                f"winner={winner_detected}, started={match_started}, "
                f"last_event={last_game_event}, ws_msgs={ws_count}, "
                f"console_caps={console_count}"
            )
            if recent:
                for ev in recent:
                    logger.info(f"[Observer:{self.board_id}]   recent_event: "
                                f"type={ev.get('type')}, data={ev.get('data')}, ts={ev.get('ts')}")

        # ── Definitive match end from events ──
        if match_finished and winner_detected:
            logger.info(f"[Observer:{self.board_id}] EVENT_SIGNAL: final_match_end_detected "
                        f"(matchFinished=True, winnerDetected=True, event={last_game_event})")
            return ObserverState.FINISHED

        if match_finished and last_game_event and 'matchshot' in str(last_game_event).lower():
            logger.info(f"[Observer:{self.board_id}] EVENT_SIGNAL: matchshot_detected "
                        f"(matchFinished=True, lastGameEvent={last_game_event})")
            return ObserverState.FINISHED

        if match_state in ('finished', 'completed', 'ended'):
            logger.info(f"[Observer:{self.board_id}] EVENT_SIGNAL: ws_match_state_finished "
                        f"(matchState={match_state})")
            return ObserverState.FINISHED

        # ── Match active from events ──
        if match_started and not match_finished:
            if match_state in ('active', 'running', 'started', None):
                # Only return IN_GAME from events if we also have WS data
                if ws_count > 0:
                    return ObserverState.IN_GAME

        # ── Gameshot (leg won, NOT match won) — NOT a match end ──
        if last_game_event and 'gameshot' in str(last_game_event).lower() and not match_finished:
            # Gameshot = leg end, match continues. This is a round transition.
            logger.info(f"[Observer:{self.board_id}] EVENT_SIGNAL: gameshot_only (leg end, match continues)")
            return ObserverState.ROUND_TRANSITION

        return None  # No definitive event data — fall back to DOM

    async def _reset_captured_events(self):
        """Reset the captured event data for a new game."""
        try:
            await self._page.evaluate("""() => {
                if (window.__dartsKioskCapture) {
                    window.__dartsKioskCapture.reset();
                }
            }""")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # DOM DETECTION (FALLBACK)
    # ═══════════════════════════════════════════════════════════════

    async def _detect_state_dom(self) -> ObserverState:
        """
        DOM-based state detection (fallback).
        Three-tier: in_game > match_finished > round_transition > idle.
        """
        try:
            signals = await self._page.evaluate("""() => {
                var inGame = !!(
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

                var allButtons = Array.from(document.querySelectorAll('button, a[role="button"], [class*="btn"]'));
                var buttonTexts = allButtons.map(function(b) { return (b.textContent || '').trim().toLowerCase(); });

                var hasRematchBtn = buttonTexts.some(function(t) {
                    return /rematch|nochmal spielen|play again|erneut spielen/i.test(t);
                });
                var hasShareBtn = buttonTexts.some(function(t) {
                    return /share|teilen|share result|ergebnis teilen/i.test(t);
                });
                var hasNewGameBtn = buttonTexts.some(function(t) {
                    return /new game|neues spiel|new match|neues match/i.test(t);
                });
                var hasPostMatchUI = !!(
                    document.querySelector('[class*="post-match"]') ||
                    document.querySelector('[class*="match-summary"]') ||
                    document.querySelector('[class*="match-end"]') ||
                    document.querySelector('[class*="game-over"]')
                );
                var strongMatchEnd = hasRematchBtn || hasShareBtn || hasNewGameBtn || hasPostMatchUI;

                var hasGenericResult = !!(
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
                    hasRematchBtn: hasRematchBtn,
                    hasShareBtn: hasShareBtn,
                    hasNewGameBtn: hasNewGameBtn,
                    hasPostMatchUI: hasPostMatchUI
                };
            }""")

            in_game = signals.get('inGame', False)
            strong_match_end = signals.get('strongMatchEnd', False)
            has_generic_result = signals.get('hasGenericResult', False)

            logger.info(f"[Observer:{self.board_id}] dom_fallback: "
                        f"in_game={in_game}, strong_end={strong_match_end}, "
                        f"generic_result={has_generic_result}")

            if strong_match_end:
                logger.info(f"[Observer:{self.board_id}] DOM_SIGNAL: FINISHED (strong end markers)")
                return ObserverState.FINISHED
            if in_game:
                return ObserverState.IN_GAME
            if has_generic_result:
                return ObserverState.ROUND_TRANSITION
            return ObserverState.IDLE

        except Exception as e:
            logger.warning(f"[Observer:{self.board_id}] DOM detection error: {e}")
            self.status.last_error = str(e)[:200]
            return ObserverState.UNKNOWN

    # ═══════════════════════════════════════════════════════════════
    # MERGE: Events > DOM
    # ═══════════════════════════════════════════════════════════════

    def _merge_detection(self, event_state: Optional[ObserverState], dom_state: ObserverState) -> ObserverState:
        """
        Merge event-based and DOM-based detection.
        Events take priority when they provide a definitive signal.
        DOM is used as fallback.

        Priority:
          1. Event says FINISHED → FINISHED (strongest signal)
          2. Event says IN_GAME  → IN_GAME
          3. Event says ROUND_TRANSITION → DOM decides between ROUND_TRANSITION and IN_GAME
          4. No event data       → DOM result
        """
        if event_state == ObserverState.FINISHED:
            # Events say match is over — always trust this
            if dom_state != ObserverState.FINISHED:
                logger.info(f"[Observer:{self.board_id}] merge: EVENT=FINISHED overrides DOM={dom_state.value}")
            return ObserverState.FINISHED

        if event_state == ObserverState.IN_GAME:
            return ObserverState.IN_GAME

        if event_state == ObserverState.ROUND_TRANSITION:
            # Gameshot detected — if DOM still shows in_game, keep it (leg change during match)
            if dom_state == ObserverState.IN_GAME:
                return ObserverState.IN_GAME
            return ObserverState.ROUND_TRANSITION

        # No event data — use DOM
        return dom_state

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
