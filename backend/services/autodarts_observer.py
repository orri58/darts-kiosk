"""
Autodarts Observer Service — Event-Driven Match Detection
==========================================================

Detection architecture (priority order):
  1. Playwright WebSocket frame observation (network-level, most reliable)
  2. Console.log capture via add_init_script (catches Winner Animation, matchshot logs)
  3. DOM/UI polling (button text, CSS classes) — fallback only

The WebSocket observation uses Playwright's page.on('websocket') API which
intercepts ALL frames at the network level, regardless of when the connection
was created. This solves the fundamental flaw of the previous JS-injection
approach where the interceptor ran AFTER the WS connection was already open.

Autodarts messaging patterns observed:
  - autodarts.matches.{id}.state      → match lifecycle (active, finished)
  - autodarts.matches.{id}.game-events → throw, gameshot, matchshot
  - autodarts.boards.{id}.matches     → board-level match events
  - autodarts.boards.{id}.state       → board state changes

Credit logic:
  Credits are decremented on game START (idle -> in_game), not on finish.

Session-end logic:
  Triggered ONLY by confirmed exit from in_game:
    - Event-driven: WS match finished / matchshot / winner
    - DOM fallback: strong match-end markers (Rematch/Share buttons)
    - Abort: return to lobby (idle)
  On confirmed exit: check credits → lock board, close browser, restore kiosk.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import logging
import threading
from collections import deque
from typing import Optional, Dict, Callable
from dataclasses import dataclass, field
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


# ── Console capture script (injected BEFORE page loads) ──
# add_init_script ensures this runs before any Autodarts JS.
CONSOLE_CAPTURE_SCRIPT = """
(() => {
    if (window.__dartsKioskConsole) return;
    window.__dartsKioskConsole = {
        entries: [],
        matchFinished: false,
        winnerDetected: false,
        _push: function(msg) {
            this.entries.push({ msg: msg.substring(0, 500), ts: new Date().toISOString() });
            if (this.entries.length > 30) this.entries.shift();
        }
    };

    var origLog = console.log;
    var origWarn = console.warn;
    var origInfo = console.info;

    function capture(args) {
        try {
            var msg = Array.prototype.join.call(args, ' ');
            var cap = window.__dartsKioskConsole;
            var dominated = false;

            if (/winner.?animation/i.test(msg)) {
                cap.winnerDetected = true;
                cap.matchFinished = true;
                cap._push('[WINNER_ANIM] ' + msg);
                dominated = true;
            }
            if (/matchshot/i.test(msg)) {
                cap.matchFinished = true;
                cap.winnerDetected = true;
                cap._push('[MATCHSHOT] ' + msg);
                dominated = true;
            }
            if (/gameshot/i.test(msg)) {
                cap._push('[GAMESHOT] ' + msg);
                dominated = true;
            }
            if (/match.*finish|match.*end|match.*complet/i.test(msg)) {
                cap.matchFinished = true;
                cap._push('[MATCH_END] ' + msg);
                dominated = true;
            }
            // Log any autodarts-related console output
            if (!dominated && /autodarts|match|game|dart|score|winner|finish|throw/i.test(msg)) {
                cap._push('[AUTODARTS] ' + msg);
            }
        } catch(e) {}
    }

    console.log = function() { origLog.apply(console, arguments); capture(arguments); };
    console.warn = function() { origWarn.apply(console, arguments); capture(arguments); };
    console.info = function() { origInfo.apply(console, arguments); capture(arguments); };
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
class CapturedWSFrame:
    """A single captured WebSocket frame with classification."""
    timestamp: str
    url: str
    direction: str  # 'received' or 'sent'
    raw_preview: str  # First 500 chars of raw data
    channel: str  # Extracted channel/topic (e.g. autodarts.matches.{id}.state)
    payload_type: str  # 'json', 'text', 'binary'
    interpretation: str  # Our classification of this frame
    payload_data: dict  # Parsed payload (if JSON)

    def to_dict(self):
        return {
            "ts": self.timestamp,
            "dir": self.direction,
            "channel": self.channel,
            "interp": self.interpretation,
            "raw": self.raw_preview[:200],
            "payload": self.payload_data,
        }


@dataclass
class WSEventState:
    """Accumulated state from WebSocket events."""
    match_active: bool = False
    match_finished: bool = False
    winner_detected: bool = False
    last_match_state: Optional[str] = None
    last_game_event: Optional[str] = None
    last_match_id: Optional[str] = None
    frames_received: int = 0
    match_relevant_frames: int = 0
    finish_trigger: Optional[str] = None  # What triggered the finish detection

    def reset(self):
        self.match_active = False
        self.match_finished = False
        self.winner_detected = False
        self.last_match_state = None
        self.last_game_event = None
        self.last_match_id = None
        self.finish_trigger = None


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
    Per-board observer. Opens Chrome to Autodarts, observes WebSocket frames
    at network level via Playwright, and detects match state primarily from
    captured events with DOM polling as fallback.
    """

    def __init__(self, board_id: str):
        self.board_id = board_id
        self.status = ObserverStatus(board_id=board_id)
        self._context = None
        self._page = None
        self._playwright = None
        self._observe_task: Optional[asyncio.Task] = None
        self._stopping = False
        self._closing = False  # Guard against concurrent close_session calls
        self._finalized = False  # True after finalize_match completed for this game
        self._abort_detected = False  # Set by WS delete handler, triggers immediate finalize

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

        # ── WebSocket event capture (network-level) ──
        self._ws_state = WSEventState()
        self._ws_frames: deque = deque(maxlen=100)  # Ring buffer of captured frames
        self._ws_lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self._context is not None and self.status.browser_open

    def _page_alive(self) -> bool:
        """Check if the page is still alive and usable. Null-safe."""
        if self._page is None or self._context is None:
            return False
        try:
            return not self._page.is_closed()
        except Exception:
            return False

    def _check_profile_locked(self, profile_dir: str) -> bool:
        """
        Safety check: detect if another Chrome instance is already using this
        user-data-dir. Returns True if locked (caller must abort), False if safe.
        """
        profile_abs = os.path.abspath(profile_dir)
        profile_norm = os.path.normpath(profile_abs).lower()

        # ── Check for Chrome lock files ──
        lock_names = ['SingletonLock', 'lockfile']
        found_locks = [
            name for name in lock_names
            if os.path.exists(os.path.join(profile_dir, name))
        ]

        if not found_locks:
            return False

        logger.warning(
            f"[Observer:{self.board_id}] Chrome lock indicators found: {found_locks} "
            f"in {profile_abs}"
        )

        # ── Verify Chrome is actually running with this profile ──
        chrome_using_profile = False

        if sys.platform == 'win32':
            # Try PowerShell (precise: checks command-line args)
            try:
                ps_cmd = (
                    "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" "
                    "| Select-Object ProcessId,CommandLine "
                    "| Format-List"
                )
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command', ps_cmd],
                    capture_output=True, text=True, timeout=10,
                )
                for line in result.stdout.splitlines():
                    if 'commandline' in line.lower():
                        cmdline = line.split(':', 1)[1].strip().lower().replace('/', '\\')
                        if profile_norm in cmdline:
                            chrome_using_profile = True
                            break
            except Exception as e:
                logger.debug(f"[Observer:{self.board_id}] PowerShell check failed: {e}")
                # Fallback: any chrome.exe running + lock file = likely conflict
                try:
                    result = subprocess.run(
                        ['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/NH'],
                        capture_output=True, text=True, timeout=5,
                    )
                    if 'chrome.exe' in result.stdout.lower():
                        chrome_using_profile = True
                except Exception:
                    pass
        else:
            # Linux/Mac: pgrep with full command line
            try:
                result = subprocess.run(
                    ['pgrep', '-af', 'chrome'],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.splitlines():
                    if profile_norm in line.lower():
                        chrome_using_profile = True
                        break
            except Exception:
                pass

        if chrome_using_profile:
            logger.error(
                f"[Observer:{self.board_id}] *** PROFILE LOCKED *** "
                f"Another Chrome instance is already using: {profile_abs}  "
                f"Playwright cannot launch a second persistent context with the same "
                f"user-data-dir. Aborting observer launch. "
                f"Ensure start.bat does NOT use --user-data-dir pointing to this path."
            )
            return True

        # Lock files exist but no Chrome process found → stale locks, clean up
        for name in found_locks:
            lock_path = os.path.join(profile_dir, name)
            try:
                os.remove(lock_path)
                logger.info(f"[Observer:{self.board_id}] Removed stale lock: {lock_path}")
            except Exception as e:
                logger.warning(f"[Observer:{self.board_id}] Could not remove stale lock {lock_path}: {e}")

        return False

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

        # ── HARD RESET of all runtime flags for clean start ──
        self._stopping = False
        self._closing = False
        self._finalized = False
        self._abort_detected = False
        self._stable_state = ObserverState.CLOSED
        self._exit_polls = 0
        self._exit_saw_finished = False
        self._credit_consumed = False
        self._ws_state = WSEventState()
        self._ws_frames.clear()

        logger.info(f"[Observer:{self.board_id}] ALL_FLAGS_RESET: "
                    f"stopping=False closing=False finalized=False abort_detected=False")

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        # Persistent Chrome profile per board
        profile_dir = os.path.join(CHROME_PROFILE_DIR, self.board_id)
        profile_dir_abs = os.path.abspath(profile_dir)
        profile_default = os.path.join(profile_dir, 'Default')
        profile_exists = os.path.isdir(profile_default)
        os.makedirs(profile_dir, exist_ok=True)
        self.status.chrome_profile = profile_dir_abs

        # ── Safety check: abort if another Chrome already owns this profile ──
        if self._check_profile_locked(profile_dir):
            err_msg = (
                f"Chrome profile is locked by another process: {profile_dir_abs}. "
                f"Cannot launch observer. Ensure no other Chrome instance uses this "
                f"user-data-dir (check start.bat)."
            )
            logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH ABORTED === {err_msg}")
            self.status.last_error = err_msg
            self._set_state(ObserverState.ERROR)
            return

        # ── Profile diagnostics ──
        cookies_classic = os.path.isfile(os.path.join(profile_default, 'Cookies'))
        cookies_network = os.path.isfile(os.path.join(profile_default, 'Network', 'Cookies'))
        cookies_exist = cookies_classic or cookies_network
        extensions_exist = os.path.isdir(os.path.join(profile_default, 'Extensions'))
        logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH START ===")
        logger.info(f"[Observer:{self.board_id}]   URL: {url}")
        logger.info(f"[Observer:{self.board_id}]   headless: {headless}")
        logger.info(f"[Observer:{self.board_id}]   platform: {sys.platform}")
        logger.info(f"[Observer:{self.board_id}]   Using Chrome profile: {profile_dir_abs}")
        logger.info(f"[Observer:{self.board_id}]   profile_exists: {os.path.isdir(profile_dir)}")
        logger.info(f"[Observer:{self.board_id}]   Default_exists: {profile_exists}")
        logger.info(f"[Observer:{self.board_id}]   Cookies_exists: {cookies_exist} (classic={cookies_classic}, network={cookies_network})")
        logger.info(f"[Observer:{self.board_id}]   Extensions_exists: {extensions_exist}")

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
                '--disable-session-crashed-bubble',
            ]
            if not headless:
                # NOTE: Do NOT use --kiosk here. Kiosk mode is only for the
                # user-facing kiosk UI Chrome (start.bat). The observer Chrome
                # uses --start-fullscreen (F11-style) which fills the screen
                # but does NOT auto-exit on tab close like --kiosk does.
                chrome_args.append('--start-fullscreen')

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

            # ── Log ALL existing pages (restored tabs, extensions, about:blank) ──
            existing_pages = list(self._context.pages)
            logger.info(f"[Observer:{self.board_id}]   Pages after launch: {len(existing_pages)}")
            for i, p in enumerate(existing_pages):
                try:
                    p_url = p.url
                except Exception:
                    p_url = "<inaccessible>"
                logger.info(f"[Observer:{self.board_id}]     page[{i}]: {p_url}")

            # ── Create a FRESH page (never reuse restored/blank pages) ──
            # Persistent contexts may restore previous session tabs, extension
            # popups, or have stale about:blank pages. Using pages[0] is unreliable.
            logger.info(f"[Observer:{self.board_id}]   Creating fresh page for observation...")
            self._page = await self._context.new_page()
            logger.info(f"[Observer:{self.board_id}]   Fresh page created. Total pages: {len(self._context.pages)}")

            # ── Lifecycle event handlers (detect premature close/crash) ──
            self._page.on("close", lambda: logger.error(
                f"[Observer:{self.board_id}] *** PAGE CLOSED *** "
                f"The observer page was closed unexpectedly!"
            ))
            self._page.on("crash", lambda: logger.error(
                f"[Observer:{self.board_id}] *** PAGE CRASHED *** "
                f"The observer page has crashed!"
            ))
            self._context.on("close", lambda: logger.error(
                f"[Observer:{self.board_id}] *** CONTEXT CLOSED *** "
                f"The browser context was closed unexpectedly!"
            ))

            # ── Inject console capture BEFORE page loads ──
            await self._page.add_init_script(CONSOLE_CAPTURE_SCRIPT)
            logger.info(f"[Observer:{self.board_id}]   Console capture script registered (add_init_script)")

            # ── Register WebSocket frame observer (network-level) ──
            self._page.on("websocket", self._on_ws_created)
            logger.info(f"[Observer:{self.board_id}]   WebSocket frame observer registered")

            # ── Navigate our fresh page to Autodarts ──
            logger.info(f"[Observer:{self.board_id}]   Navigating to {url}...")
            response = await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            nav_status = response.status if response else "no_response"
            current_url = self._page.url
            logger.info(f"[Observer:{self.board_id}]   Navigation complete: status={nav_status}, url={current_url}")

            # ── Close old/stale pages (about:blank, restored tabs) ──
            # Keep ONLY our Autodarts page. Old pages waste resources and can
            # confuse Chrome's tab focus on Windows.
            for old_page in existing_pages:
                try:
                    if not old_page.is_closed():
                        old_url = old_page.url
                        logger.info(f"[Observer:{self.board_id}]   Closing old page: {old_url}")
                        await old_page.close()
                except Exception as close_err:
                    logger.debug(f"[Observer:{self.board_id}]   Old page close skipped: {close_err}")

            # ── Final page inventory ──
            final_pages = self._context.pages
            logger.info(f"[Observer:{self.board_id}]   Final page count: {len(final_pages)}")
            for i, p in enumerate(final_pages):
                try:
                    p_url = p.url
                except Exception:
                    p_url = "<inaccessible>"
                is_ours = " (OBSERVED)" if p == self._page else ""
                logger.info(f"[Observer:{self.board_id}]     page[{i}]: {p_url}{is_ours}")

            # ── Verify we're on Autodarts, not about:blank ──
            if 'about:blank' in self._page.url:
                logger.error(
                    f"[Observer:{self.board_id}] *** NAVIGATION FAILED *** "
                    f"Page is still on about:blank after goto({url}). "
                    f"Autodarts may be unreachable."
                )

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

            # ── Post-launch health check: verify page is still alive ──
            for check_at in [3, 7, 12]:
                await asyncio.sleep(check_at - (0 if check_at == 3 else (3 if check_at == 7 else 7)))
                if not self._page_alive():
                    logger.error(
                        f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                        f"page_alive=False (page or context is None/closed)"
                    )
                    break
                try:
                    alive_url = self._page.url
                    page_count = len(self._context.pages) if self._context else 0
                    logger.info(
                        f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                        f"page_alive=True, url={alive_url}, pages={page_count}"
                    )
                except Exception as health_err:
                    logger.error(
                        f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                        f"page_alive=False, error={health_err}"
                    )
                    break

            logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH SUCCESS ===")
            self._observe_task = asyncio.create_task(self._observe_loop())

        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED === {e}", exc_info=True)
            self.status.last_error = f"{type(e).__name__}: {str(e)[:200]}"
            self._set_state(ObserverState.ERROR)
            await self._cleanup()

    # ═══════════════════════════════════════════════════════════════
    # PLAYWRIGHT WEBSOCKET OBSERVATION (NETWORK-LEVEL)
    # ═══════════════════════════════════════════════════════════════

    def _on_ws_created(self, ws):
        """Called when a new WebSocket connection is detected by Playwright."""
        ws_url = ws.url
        logger.info(f"[Observer:{self.board_id}] WS_CONNECTION_OPENED: {ws_url}")

        ws.on("framereceived", lambda payload: self._on_ws_frame_received(ws_url, payload))
        ws.on("framesent", lambda payload: self._on_ws_frame_sent(ws_url, payload))
        ws.on("close", lambda: logger.info(f"[Observer:{self.board_id}] WS_CONNECTION_CLOSED: {ws_url}"))

    def _on_ws_frame_received(self, ws_url: str, payload: str):
        """Process a received WebSocket frame at network level."""
        self._process_ws_frame(ws_url, payload, "received")

    def _on_ws_frame_sent(self, ws_url: str, payload: str):
        """Process a sent WebSocket frame (for subscribe/unsubscribe tracking)."""
        # Only log sent frames if they contain match-related subscriptions
        if isinstance(payload, str) and ('autodarts' in payload or 'subscribe' in payload.lower()):
            self._process_ws_frame(ws_url, payload, "sent")

    def _process_ws_frame(self, ws_url: str, raw_data, direction: str):
        """Parse, classify, and log a WebSocket frame."""
        now = datetime.now(timezone.utc).isoformat()

        # Convert to string for analysis
        if isinstance(raw_data, bytes):
            try:
                raw_str = raw_data.decode('utf-8', errors='replace')
            except Exception:
                raw_str = f"<binary {len(raw_data)} bytes>"
        else:
            raw_str = str(raw_data)

        # ── Extract channel/topic ──
        channel = self._extract_channel(raw_str)

        # ── Parse payload ──
        payload_data, payload_type = self._parse_payload(raw_str)

        # ── Classify the frame ──
        interpretation = self._classify_frame(raw_str, channel, payload_data)

        frame = CapturedWSFrame(
            timestamp=now,
            url=ws_url,
            direction=direction,
            raw_preview=raw_str[:500],
            channel=channel,
            payload_type=payload_type,
            interpretation=interpretation,
            payload_data=payload_data if payload_data else {},
        )

        with self._ws_lock:
            self._ws_frames.append(frame)
            self._ws_state.frames_received += 1

        # ── Update event state based on classification ──
        self._update_ws_state(interpretation, channel, payload_data, raw_str)

        # ── LOG: Every match-relevant frame ──
        if interpretation != "irrelevant":
            self._ws_state.match_relevant_frames += 1
            logger.info(
                f"[Observer:{self.board_id}] WS_FRAME_{direction.upper()}: "
                f"channel={channel} | interp={interpretation} | "
                f"payload_type={payload_type} | "
                f"raw_preview={raw_str[:300]}"
            )
            if payload_data:
                # Log key fields from payload
                interesting = {k: v for k, v in payload_data.items()
                               if k in ('state', 'type', 'event', 'matchState', 'winner',
                                        'finished', 'variant', 'gameWinner', 'matchWinner',
                                        'legs', 'sets', 'status', 'isFinished', 'data',
                                        'throwNumber', 'turnScore', 'gameScores', 'error',
                                        'message')}
                if interesting:
                    logger.info(f"[Observer:{self.board_id}]   payload_fields: {interesting}")

    def _extract_channel(self, raw: str) -> str:
        """Extract the Autodarts channel/topic from a raw WS message."""
        # Pattern 1: autodarts.matches.{uuid}.{subtopic}
        m = re.search(r'(autodarts\.\w+\.[a-f0-9-]+\.\S+)', raw, re.IGNORECASE)
        if m:
            return m.group(1)

        # Pattern 2: autodarts.boards.{id}.{subtopic}
        m = re.search(r'(autodarts\.boards\.\S+)', raw, re.IGNORECASE)
        if m:
            return m.group(1)

        # Pattern 3: Just look for known channel prefixes
        m = re.search(r'(autodarts\.\S+)', raw, re.IGNORECASE)
        if m:
            return m.group(1)

        # Pattern 4: Ably/Centrifugo/Pusher channel format [channel, data]
        if raw.startswith('[') or raw.startswith('42['):
            try:
                arr_str = raw.lstrip('0123456789')
                arr = json.loads(arr_str)
                if isinstance(arr, list) and len(arr) >= 1 and isinstance(arr[0], str):
                    return arr[0]
            except Exception:
                pass

        return "unknown"

    def _parse_payload(self, raw: str):
        """Try to parse the payload as JSON."""
        # Direct JSON
        try:
            data = json.loads(raw)
            return data, "json"
        except Exception:
            pass

        # Socket.IO format: "42[event_name, {...}]"
        m = re.match(r'^\d+(.+)$', raw)
        if m:
            try:
                data = json.loads(m.group(1))
                return data, "socketio"
            except Exception:
                pass

        # Extract embedded JSON
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
                return data, "embedded_json"
            except Exception:
                pass

        # Look for JSON array
        start = raw.find('[')
        end = raw.rfind(']')
        if start != -1 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
                return data, "json_array"
            except Exception:
                pass

        return None, "text"

    def _extract_match_id(self, channel: str) -> Optional[str]:
        """Extract match UUID from an Autodarts channel name."""
        m = re.search(r'autodarts\.matches\.([a-f0-9-]+)', channel, re.IGNORECASE)
        return m.group(1) if m else None

    def _extract_event(self, payload) -> str:
        """Extract event name from payload (checks nested levels)."""
        if not payload:
            return ""
        if isinstance(payload, dict):
            for key in ('event', 'type'):
                val = payload.get(key)
                if isinstance(val, str):
                    return val.lower()
            data = payload.get('data')
            if isinstance(data, dict):
                for key in ('event', 'type'):
                    val = data.get(key)
                    if isinstance(val, str):
                        return val.lower()
        if isinstance(payload, list) and len(payload) >= 2:
            if isinstance(payload[1], dict):
                return self._extract_event(payload[1])
        return ""

    def _extract_body_type(self, payload) -> str:
        """Extract body.type from payload (for game_shot match detection)."""
        if not payload or not isinstance(payload, dict):
            return ""
        for container_key in ('body', 'data'):
            container = payload.get(container_key)
            if isinstance(container, dict):
                t = container.get('type')
                if isinstance(t, str):
                    return t.lower()
                if container_key == 'data':
                    body = container.get('body')
                    if isinstance(body, dict):
                        t = body.get('type')
                        if isinstance(t, str):
                            return t.lower()
        return ""

    def _extract_bool_field(self, payload, field_name: str) -> bool:
        """Check if a boolean field is True in payload (checks nested levels)."""
        if not isinstance(payload, dict):
            return False
        if payload.get(field_name) is True:
            return True
        data = payload.get('data')
        if isinstance(data, dict) and data.get(field_name) is True:
            return True
        match_data = payload.get('match')
        if isinstance(match_data, dict) and match_data.get(field_name) is True:
            return True
        return False

    def _classify_frame(self, raw: str, channel: str, payload) -> str:
        """
        Classify a WS frame based on Autodarts lifecycle signals.

        Match START signals (authoritative):
          - event = "turn_start"
          - event = "throw"

        Match END signals (authoritative):
          - game-event: event = "game_shot" AND body.type = "match"
          - state frame: finished = true  (boolean)
          - state frame: gameFinished = true  (boolean)
          - matchshot keyword (backward compat)

        Post-match cleanup:
          - event = "delete" → reset (match removed from server)

        IGNORED for lifecycle: round changes, turn_end, score updates
        """
        raw_lower = raw.lower()
        chan_lower = channel.lower()
        event = self._extract_event(payload)

        # ── MATCH START ──
        if event == 'turn_start':
            return "match_start_turn_start"
        if event == 'throw':
            return "match_start_throw"

        # ── MATCH END: game_shot + body.type = "match" ──
        if event in ('game_shot', 'gameshot', 'game-shot'):
            body_type = self._extract_body_type(payload)
            if body_type == 'match':
                return "match_end_gameshot_match"
            return "round_transition_gameshot"

        # ── MATCH END: finished=true or gameFinished=true (state frames) ──
        if payload and isinstance(payload, dict):
            if self._extract_bool_field(payload, 'finished'):
                return "match_end_state_finished"
            if self._extract_bool_field(payload, 'gameFinished'):
                return "match_end_game_finished"

        # ── MATCH END: matchshot keyword (backward compat) ──
        if 'matchshot' in raw_lower and 'gameshot' not in raw_lower:
            return "match_finished_matchshot"

        # ── POST-MATCH: delete event ──
        if event == 'delete':
            return "match_reset_delete"

        # ── NON-LIFECYCLE (diagnostic only) ──
        if 'autodarts' in chan_lower or 'autodarts' in raw_lower:
            if 'subscribe' in raw_lower or 'attach' in raw_lower:
                return "subscription"
            return "match_other"

        return "irrelevant"

    def _deep_get_state(self, payload) -> Optional[str]:
        """Recursively look for a 'state' field in a payload dict."""
        if not isinstance(payload, dict):
            return None

        # Direct fields
        for key in ('state', 'matchState', 'status'):
            val = payload.get(key)
            if isinstance(val, str):
                return val.lower()

        # Nested data
        data = payload.get('data')
        if isinstance(data, dict):
            for key in ('state', 'matchState', 'status'):
                val = data.get(key)
                if isinstance(val, str):
                    return val.lower()

        # Nested match
        match = payload.get('match')
        if isinstance(match, dict):
            for key in ('state', 'status'):
                val = match.get(key)
                if isinstance(val, str):
                    return val.lower()

        return None

    def _update_ws_state(self, interpretation: str, channel: str, payload, raw: str):
        """
        Update ws_state based on the Autodarts lifecycle state machine.

        State machine:
          turn_start / throw           → match_active = True
          game_shot+match / finished   → match_finished = True, match_active = False
          delete                       → full reset

        Ignored: round changes, turn_end, score updates, generic match events
        """
        ws = self._ws_state

        # ── Track match ID from channel ──
        match_id = self._extract_match_id(channel)
        if match_id:
            ws.last_match_id = match_id

        # ═══ MATCH START ═══
        if interpretation in ("match_start_turn_start", "match_start_throw"):
            if not ws.match_active and not ws.match_finished:
                ws.match_active = True
                logger.info(
                    f"[Observer:{self.board_id}] *** MATCH START DETECTED *** "
                    f"reason={interpretation} | match_id={ws.last_match_id}"
                )

        # ═══ MATCH END (authoritative) ═══
        elif interpretation in ("match_end_gameshot_match", "match_end_state_finished",
                                "match_end_game_finished", "match_finished_matchshot"):
            ws.match_finished = True
            ws.match_active = False
            ws.winner_detected = True
            ws.finish_trigger = interpretation
            logger.info(
                f"[Observer:{self.board_id}] *** MATCH FINISH DETECTED *** "
                f"trigger={interpretation} | match_id={ws.last_match_id}"
            )

        # ═══ POST-MATCH RESET (delete = match removed) ═══
        elif interpretation == "match_reset_delete":
            was_active = ws.match_active
            was_finished = ws.match_finished
            old_match_id = ws.last_match_id

            if was_active and not was_finished:
                # ── DELETE during active match = ABORT ──
                # Match was manually cancelled in Autodarts UI.
                # Set abort_detected for IMMEDIATE finalize (bypass debounce).
                ws.match_active = False
                ws.finish_trigger = "match_abort_delete"
                self._abort_detected = True
                logger.info(
                    f"[Observer:{self.board_id}] *** MATCH ABORT DETECTED *** "
                    f"(delete event during active match) | match_id={old_match_id} | "
                    f"abort_detected=True (IMMEDIATE finalize)"
                )
            else:
                # Post-match cleanup or delete without active game → full reset
                ws.reset()
                logger.info(
                    f"[Observer:{self.board_id}] *** MATCH RESET DETECTED *** "
                    f"(delete event) | was_active={was_active} | was_finished={was_finished} "
                    f"| match_id={old_match_id}"
                )

        # ═══ LEG-LEVEL gameshot (ignored for lifecycle) ═══
        elif interpretation == "round_transition_gameshot":
            ws.last_game_event = "gameshot"
            logger.info(
                f"[Observer:{self.board_id}] WS_EVENT: gameshot "
                f"(leg-level, ignored for match lifecycle)"
            )

    # ═══════════════════════════════════════════════════════════════
    # SESSION LIFECYCLE
    # ═══════════════════════════════════════════════════════════════

    async def close_session(self):
        """
        Close Playwright browser ONLY. Idempotent.
        Detects self-call (from within observe_task) to avoid deadlock.
        Does NOT handle kiosk window management — that is finalize_match's job.
        """
        if self._closing:
            logger.info(f"[Observer:{self.board_id}] CLOSE_SESSION_SKIPPED (already closing)")
            return
        self._closing = True
        self._stopping = True
        logger.info(f"[Observer:{self.board_id}] === CLOSE_SESSION_START ===")

        # Detect self-call: if we're being called from within the observe_task,
        # do NOT cancel/await ourselves (would deadlock).
        current_task = asyncio.current_task()
        is_self_call = (self._observe_task is not None
                        and self._observe_task is current_task)

        if is_self_call:
            logger.info(f"[Observer:{self.board_id}]   self-call detected, skipping task cancel")
        else:
            if self._observe_task and not self._observe_task.done():
                logger.info(f"[Observer:{self.board_id}]   cancelling observe_task (external call)...")
                self._observe_task.cancel()
                try:
                    await self._observe_task
                except asyncio.CancelledError:
                    pass
        self._observe_task = None

        await self._cleanup()
        self._set_state(ObserverState.CLOSED)
        logger.info(f"[Observer:{self.board_id}] === CLOSE_SESSION_DONE ===")

    async def _cleanup(self):
        """Close Playwright objects step-by-step with detailed logging."""
        # Step 1: Close page
        if self._page:
            try:
                await self._page.close()
                logger.info(f"[AUTODARTS] PAGE_CLOSE_DONE board={self.board_id}")
            except Exception as e:
                logger.debug(f"[AUTODARTS] page close error: {e}")
        self._page = None

        # Step 2: Close context
        if self._context:
            try:
                await self._context.close()
                logger.info(f"[AUTODARTS] CONTEXT_CLOSE_DONE board={self.board_id}")
            except Exception as e:
                logger.debug(f"[AUTODARTS] context close error: {e}")
        self._context = None

        # Step 3: Stop Playwright
        if self._playwright:
            try:
                await self._playwright.stop()
                logger.info(f"[AUTODARTS] PLAYWRIGHT_STOP_DONE board={self.board_id}")
            except Exception as e:
                logger.debug(f"[AUTODARTS] playwright stop error: {e}")
        self._playwright = None

        self.status.browser_open = False
        logger.info(f"[AUTODARTS] CLEANUP_COMPLETE board={self.board_id}")

    # ═══════════════════════════════════════════════════════════════
    # OBSERVE LOOP
    # ═══════════════════════════════════════════════════════════════

    async def _observe_loop(self):
        """
        Main observation loop. Each cycle:
          1. Read WS event state (accumulated from network-level capture)
          2. Read console capture state (from injected script)
          3. Fall back to DOM detection if no event data
          4. Apply debounce logic for state transitions

        Priority: WS events > console signals > DOM signals > fallback
        """
        logger.info(f"[Observer:{self.board_id}] Observe loop started")
        logger.info(f"[Observer:{self.board_id}]   poll_interval={OBSERVER_POLL_INTERVAL}s, "
                     f"debounce_polls={DEBOUNCE_EXIT_POLLS}, debounce_interval={DEBOUNCE_POLL_INTERVAL}s")

        stop_reason = "unknown"

        while not self._stopping:
            try:
                interval = DEBOUNCE_POLL_INTERVAL if self._exit_polls > 0 else OBSERVER_POLL_INTERVAL
                await asyncio.sleep(interval)

                # ── Null-safe page check ──
                if self._stopping:
                    stop_reason = "stopping_flag"
                    break
                if not self._page_alive():
                    stop_reason = "page_not_alive"
                    logger.warning(
                        f"[Observer:{self.board_id}] OBSERVE_LOOP_STOP_REASON: {stop_reason} "
                        f"(page={self._page is not None}, context={self._context is not None})"
                    )
                    break

                # ── IMMEDIATE ABORT: delete event detected, bypass all debounce ──
                if self._abort_detected and not self._finalized:
                    logger.info(f"[Observer:{self.board_id}] ABORT DETECTED IMMEDIATE — "
                                f"bypassing debounce, calling finalize_match(aborted)")
                    self._finalized = True
                    self._abort_detected = False
                    self._stable_state = ObserverState.IDLE
                    self._set_state(ObserverState.IDLE)
                    self._exit_polls = 0
                    self._exit_saw_finished = False

                    if self._on_game_ended:
                        try:
                            result = await self._on_game_ended(self.board_id, "aborted")
                            logger.info(f"[Observer:{self.board_id}] abort finalize returned: "
                                        f"teardown={result.get('should_teardown') if result else '?'}")
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended(aborted) ERROR: {e}",
                                         exc_info=True)

                    if self._stopping:
                        logger.info(f"[Observer:{self.board_id}] _stopping=True after abort finalize")
                        break

                    self._finalized = False
                    self._credit_consumed = False
                    self._ws_state.reset()
                    logger.info(f"[Observer:{self.board_id}] READY_FOR_NEXT_GAME after abort")
                    continue

                # ── Browser health check ──
                try:
                    _ = self._page.url
                except Exception as health_err:
                    stop_reason = f"browser_dead:{health_err}"
                    logger.error(
                        f"[Observer:{self.board_id}] *** BROWSER DEAD *** "
                        f"Page no longer accessible: {health_err}. "
                        f"Breaking observe loop."
                    )
                    self.status.last_error = f"Browser died: {str(health_err)[:200]}"
                    self._set_state(ObserverState.ERROR)
                    break

                # ── PRIMARY: WS event state (already accumulated) ──
                event_state = self._read_ws_event_state()

                # ── SECONDARY: Console capture ──
                console_state = await self._read_console_state()

                # ── TERTIARY: DOM detection ──
                dom_state = await self._detect_state_dom()

                # ── MERGE: Events > Console > DOM ──
                raw = self._merge_detection(event_state, console_state, dom_state)

                now = datetime.now(timezone.utc).isoformat()
                self.status.last_poll = now
                stable = self._stable_state

                # Log poll summary
                ws = self._ws_state
                logger.info(
                    f"[Observer:{self.board_id}] POLL: stable={stable.value} | merged={raw.value} | "
                    f"ws_finished={ws.match_finished} ws_winner={ws.winner_detected} "
                    f"ws_trigger={ws.finish_trigger} | "
                    f"ws_frames={ws.frames_received} ws_match_frames={ws.match_relevant_frames} | "
                    f"dom={dom_state.value}"
                )

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
                    # Skip if already finalized/aborted (prevent double finalize)
                    if self._finalized or self._abort_detected:
                        logger.info(f"[Observer:{self.board_id}] exit debounce skipped "
                                    f"(finalized={self._finalized} abort_detected={self._abort_detected})")
                        continue

                    self._exit_polls += 1
                    if raw == ObserverState.FINISHED:
                        self._exit_saw_finished = True

                    logger.info(f"[Observer:{self.board_id}] debounce: exit poll "
                                f"{self._exit_polls}/{DEBOUNCE_EXIT_POLLS} "
                                f"(merged={raw.value}, saw_finished={self._exit_saw_finished}, "
                                f"ws_trigger={ws.finish_trigger})")

                    # Fast-track: authoritative finish trigger skips debounce
                    debounce_needed = 1 if ws.finish_trigger else DEBOUNCE_EXIT_POLLS
                    if self._exit_polls < debounce_needed:
                        continue

                    # ─── CONFIRMED: match is really over ──────────
                    # Use WS finish_trigger as specific reason when available
                    if self._exit_saw_finished and ws.finish_trigger:
                        reason = ws.finish_trigger
                    elif self._exit_saw_finished:
                        reason = "finished"
                    else:
                        reason = "aborted"
                    confirmed_state = ObserverState.FINISHED if self._exit_saw_finished else raw

                    logger.info(
                        f"[Observer:{self.board_id}] === DEBOUNCE CONFIRMED: "
                        f"in_game -> {confirmed_state.value} (reason={reason}, "
                        f"trigger={ws.finish_trigger}) ==="
                    )

                    self._stable_state = confirmed_state
                    self._set_state(confirmed_state)
                    self._exit_polls = 0
                    self._exit_saw_finished = False

                    # ── Call finalize DIRECTLY (synchronous, no create_task) ──
                    # _finalized guard prevents double finalization
                    if self._on_game_ended and not self._finalized:
                        self._finalized = True
                        try:
                            result = await self._on_game_ended(self.board_id, reason)
                            logger.info(f"[Observer:{self.board_id}] finalize returned: "
                                        f"teardown={result.get('should_teardown') if result else '?'}")
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended({reason}) ERROR: {e}",
                                         exc_info=True)
                    elif self._finalized:
                        logger.info(f"[Observer:{self.board_id}] FINALIZE_SKIPPED (already finalized)")

                    # If finalize_match closed the observer (_stopping set by close_session),
                    # break immediately — no more polls needed
                    if self._stopping:
                        logger.info(f"[Observer:{self.board_id}] _stopping=True after finalize, exiting loop")
                        break

                    # Credits remain — reset for next game
                    self._finalized = False
                    self._credit_consumed = False
                    self._ws_state.reset()
                    logger.info(f"[Observer:{self.board_id}] READY_FOR_NEXT_GAME (observer stays alive)")

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
                        self._finalized = False  # Reset for new game
                        self._abort_detected = False  # Reset for new game
                        self._exit_polls = 0
                        self._exit_saw_finished = False
                        self.status.games_observed += 1

                        # Reset WS state for fresh game tracking
                        self._ws_state.reset()

                        logger.info(f"[Observer:{self.board_id}] GAME STARTED — "
                                    f"games_observed={self.status.games_observed}")
                        if self._on_game_started:
                            try:
                                await self._on_game_started(self.board_id)
                            except Exception as e:
                                logger.error(f"[Observer:{self.board_id}] on_game_started ERROR: {e}",
                                             exc_info=True)

                    elif stable == ObserverState.FINISHED and effective_raw == ObserverState.IDLE:
                        # Player dismissed results and returned to lobby.
                        # Do NOT trigger finalize_match again — that was already done
                        # when the match finished. Just transition the state.
                        logger.info(f"[Observer:{self.board_id}] === TRANSITION: "
                                    f"finished -> idle (result dismissed, NO re-finalize) ===")
                        self._stable_state = ObserverState.IDLE
                        self._set_state(ObserverState.IDLE)
                    else:
                        logger.info(f"[Observer:{self.board_id}] === TRANSITION: "
                                    f"{stable.value} -> {effective_raw.value} ===")
                        self._stable_state = effective_raw
                        self._set_state(effective_raw)

            except asyncio.CancelledError:
                stop_reason = "cancelled"
                break
            except Exception as e:
                logger.error(f"[Observer:{self.board_id}] Observe loop error: {e}")
                self.status.last_error = str(e)[:200]
                self._set_state(ObserverState.ERROR)
                self._stable_state = ObserverState.ERROR
                await asyncio.sleep(OBSERVER_POLL_INTERVAL * 2)

        if self._stopping:
            stop_reason = "finalize_teardown" if self._finalized else "stopping_flag"
        logger.info(f"[Observer:{self.board_id}] OBSERVE_LOOP_STOP_REASON: {stop_reason}")
        logger.info(f"[Observer:{self.board_id}] Observe loop ended")

    # ═══════════════════════════════════════════════════════════════
    # STATE READERS
    # ═══════════════════════════════════════════════════════════════

    def _read_ws_event_state(self) -> Optional[ObserverState]:
        """
        Read the accumulated WS event state. This data is populated in real-time
        by the _on_ws_frame_received callback (network-level Playwright hook).

        Returns:
          FINISHED  — if match_finished is True
          IN_GAME   — if match_active is True (and not finished)
          None      — no definitive WS data
        """
        ws = self._ws_state

        if ws.match_finished:
            logger.info(f"[Observer:{self.board_id}] WS_STATE: FINISHED "
                        f"(trigger={ws.finish_trigger})")
            return ObserverState.FINISHED

        if ws.match_active:
            return ObserverState.IN_GAME

        return None  # No definitive WS data

    async def _read_console_state(self) -> Optional[ObserverState]:
        """Read console capture data (injected via add_init_script)."""
        if not self._page_alive():
            return None
        try:
            data = await self._page.evaluate("""() => {
                var c = window.__dartsKioskConsole;
                if (!c) return null;
                return {
                    matchFinished: c.matchFinished,
                    winnerDetected: c.winnerDetected,
                    recent: c.entries.slice(-5)
                };
            }""")
        except Exception:
            return None

        if not data:
            return None

        if data.get('winnerDetected') or data.get('matchFinished'):
            recent = data.get('recent', [])
            for entry in recent:
                logger.info(f"[Observer:{self.board_id}] CONSOLE_CAPTURE: {entry.get('msg', '')[:200]}")
            if data.get('winnerDetected'):
                logger.info(f"[Observer:{self.board_id}] CONSOLE_STATE: winner_detected")
                return ObserverState.FINISHED
            if data.get('matchFinished'):
                logger.info(f"[Observer:{self.board_id}] CONSOLE_STATE: match_finished")
                return ObserverState.FINISHED

        return None

    # ═══════════════════════════════════════════════════════════════
    # DOM DETECTION (FALLBACK)
    # ═══════════════════════════════════════════════════════════════

    async def _detect_state_dom(self) -> ObserverState:
        """DOM-based state detection (fallback). Three-tier detection."""
        if not self._page_alive():
            return ObserverState.UNKNOWN
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

            if strong_match_end:
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
    # MERGE: WS Events > Console > DOM
    # ═══════════════════════════════════════════════════════════════

    def _merge_detection(
        self,
        ws_state: Optional[ObserverState],
        console_state: Optional[ObserverState],
        dom_state: ObserverState,
    ) -> ObserverState:
        """
        Merge three detection sources. Priority:
          1. WS FINISHED → always trust (strongest signal)
          2. Console FINISHED → trust (Winner Animation, matchshot logs)
          3. WS IN_GAME → trust
          4. DOM result → fallback
        """
        # WS says finished → done
        if ws_state == ObserverState.FINISHED:
            if dom_state != ObserverState.FINISHED:
                logger.info(f"[Observer:{self.board_id}] merge: WS=FINISHED overrides DOM={dom_state.value}")
            return ObserverState.FINISHED

        # Console says finished → done
        if console_state == ObserverState.FINISHED:
            if dom_state != ObserverState.FINISHED:
                logger.info(f"[Observer:{self.board_id}] merge: CONSOLE=FINISHED overrides DOM={dom_state.value}")
            return ObserverState.FINISHED

        # WS says in_game → trust
        if ws_state == ObserverState.IN_GAME:
            return ObserverState.IN_GAME

        # No WS/console data → DOM fallback
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
        # ── Single observer per board: cleanup existing first ──
        existing = self._observers.get(board_id)
        if existing:
            if existing.is_open:
                logger.info(f"[ObserverMgr] Board {board_id} already open, returning existing")
                return existing
            # Dead/closed observer → cleanup before creating new
            logger.info(f"[ObserverMgr] Cleaning up dead observer for {board_id}")
            try:
                await existing.close_session()
            except Exception as e:
                logger.debug(f"[ObserverMgr] cleanup error (ignored): {e}")

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
