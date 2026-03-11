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
        self._ws_state = WSEventState()
        self._ws_frames.clear()

        url = autodarts_url or AUTODARTS_URL
        self.status.autodarts_url = url

        # Persistent Chrome profile per board
        profile_dir = os.path.join(CHROME_PROFILE_DIR, self.board_id)
        profile_dir_abs = os.path.abspath(profile_dir)
        profile_default = os.path.join(profile_dir, 'Default')
        profile_exists = os.path.isdir(profile_default)
        os.makedirs(profile_dir, exist_ok=True)
        self.status.chrome_profile = profile_dir_abs

        # ── Profile diagnostics ──
        cookies_exist = os.path.isfile(os.path.join(profile_default, 'Cookies'))
        extensions_exist = os.path.isdir(os.path.join(profile_dir, 'Default', 'Extensions'))
        logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH START ===")
        logger.info(f"[Observer:{self.board_id}]   URL: {url}")
        logger.info(f"[Observer:{self.board_id}]   headless: {headless}")
        logger.info(f"[Observer:{self.board_id}]   platform: {sys.platform}")
        logger.info(f"[Observer:{self.board_id}]   Using Chrome profile: {profile_dir_abs}")
        logger.info(f"[Observer:{self.board_id}]   profile_exists: {os.path.isdir(profile_dir)}")
        logger.info(f"[Observer:{self.board_id}]   Default_exists: {profile_exists}")
        logger.info(f"[Observer:{self.board_id}]   Cookies_exists: {cookies_exist}")
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

            # ── Inject console capture BEFORE page loads ──
            await self._page.add_init_script(CONSOLE_CAPTURE_SCRIPT)
            logger.info(f"[Observer:{self.board_id}]   Console capture script registered (add_init_script)")

            # ── Register WebSocket frame observer (network-level) ──
            self._page.on("websocket", self._on_ws_created)
            logger.info(f"[Observer:{self.board_id}]   WebSocket frame observer registered")

            logger.info(f"[Observer:{self.board_id}]   Navigating to {url}...")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

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
                                        'legs', 'sets', 'status', 'isFinished', 'data')}
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

    def _classify_frame(self, raw: str, channel: str, payload) -> str:
        """
        Classify a WS frame. CONSERVATIVE: only true match-level signals
        trigger match_finished. Leg/round/turn signals are NEVER match_finished.

        Match-finished (definitive):
          - matchshot (only sent for the final winning double of the MATCH)
          - matchWinner field explicitly set

        NOT match-finished (must not trigger lock):
          - gameshot (leg end, match continues)
          - gameWinner (leg winner, match continues)
          - state: finished (could be a leg, NOT necessarily the match)
          - isFinished (ambiguous — could be leg-level)
          - next / turn change / round transition
        """
        raw_lower = raw.lower()
        chan_lower = channel.lower()

        # ── DEFINITIVE match end: only matchshot ──
        # matchshot is ONLY sent when the entire match is won (not a leg)
        if 'matchshot' in raw_lower and 'gameshot' not in raw_lower:
            return "match_finished_matchshot"

        # ── Check payload for match-level winner ──
        if payload and isinstance(payload, dict):
            # ONLY matchWinner counts as match end (NOT gameWinner)
            match_winner = (
                payload.get('matchWinner') or
                (payload.get('data', {}) or {}).get('matchWinner')
            )
            if match_winner and match_winner is not False:
                return "match_finished_winner_field"

            # state field — log but do NOT treat as match_finished
            # (state: finished can mean a leg/game finished, not the match)
            state = self._deep_get_state(payload)
            if state in ('active', 'running', 'started', 'playing'):
                return "match_started"
            if state in ('finished', 'completed', 'ended'):
                # This might be a leg finish — classify as game_state_finished,
                # NOT match_finished. The difference matters.
                return "game_state_finished"

        # ── Gameshot = leg end, NEVER match end ──
        if 'gameshot' in raw_lower:
            return "round_transition_gameshot"

        # ── Channel-based classification ──
        if 'autodarts.matches' in chan_lower and '.state' in chan_lower:
            return "match_state"
        if '.game-events' in chan_lower or 'game-event' in chan_lower:
            return "game_event"
        if 'autodarts.boards' in chan_lower and '.matches' in chan_lower:
            return "board_matches"
        if 'autodarts.boards' in chan_lower and '.state' in chan_lower:
            return "board_state"

        # ── Content-based classification (conservative) ──
        if 'autodarts' in raw_lower or 'match' in raw_lower:
            if any(kw in raw_lower for kw in ('throw', 'score', 'turn', 'dart', 'next')):
                return "turn_transition"
            return "match_related"

        if 'subscribe' in raw_lower or 'attach' in raw_lower:
            return "subscription"

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
        Update the accumulated WS event state based on frame classification.
        CONSERVATIVE: only definitive match-level signals set match_finished.
        """
        ws = self._ws_state

        if interpretation in ("match_finished_matchshot", "match_finished_winner_field"):
            # TRUE match end signals — only these trigger finalization
            ws.match_finished = True
            ws.winner_detected = True
            ws.finish_trigger = f"{interpretation}:{channel}"
            logger.info(
                f"[Observer:{self.board_id}] *** MATCH_END_SIGNAL: {interpretation} ***  "
                f"channel={channel} | finish_trigger={ws.finish_trigger}"
            )

        elif interpretation == "game_state_finished":
            # state: finished — could be leg OR match. Log but do NOT set match_finished.
            # This prevents false locks on leg finishes.
            logger.info(
                f"[Observer:{self.board_id}] WS_EVENT: game_state_finished "
                f"(leg or match — NOT triggering match_finished) channel={channel}"
            )

        elif interpretation == "match_started":
            ws.match_active = True
            ws.match_finished = False
            ws.winner_detected = False
            ws.finish_trigger = None
            logger.info(f"[Observer:{self.board_id}] WS_EVENT: match_started channel={channel}")

        elif interpretation == "round_transition_gameshot":
            ws.last_game_event = "gameshot"
            logger.info(f"[Observer:{self.board_id}] WS_EVENT: gameshot (leg end, NOT match end)")

        elif interpretation == "turn_transition":
            ws.last_game_event = "turn"

        elif interpretation in ("game_event", "match_state", "board_state", "board_matches"):
            if payload and isinstance(payload, dict):
                state = self._deep_get_state(payload)
                if state:
                    ws.last_match_state = state
                evt = (payload.get('type') or payload.get('event') or
                       (payload.get('data', {}) or {}).get('type') or '')
                if evt:
                    ws.last_game_event = str(evt)

    # ═══════════════════════════════════════════════════════════════
    # SESSION LIFECYCLE
    # ═══════════════════════════════════════════════════════════════

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

        while not self._stopping:
            try:
                interval = DEBOUNCE_POLL_INTERVAL if self._exit_polls > 0 else OBSERVER_POLL_INTERVAL
                await asyncio.sleep(interval)
                if not self._page or self._stopping:
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
                    self._exit_polls += 1
                    if raw == ObserverState.FINISHED:
                        self._exit_saw_finished = True

                    logger.info(f"[Observer:{self.board_id}] debounce: exit poll "
                                f"{self._exit_polls}/{DEBOUNCE_EXIT_POLLS} "
                                f"(merged={raw.value}, saw_finished={self._exit_saw_finished}, "
                                f"ws_trigger={ws.finish_trigger})")

                    if self._exit_polls < DEBOUNCE_EXIT_POLLS:
                        continue

                    # ─── CONFIRMED: match is really over ──────────
                    reason = "finished" if self._exit_saw_finished else "aborted"
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

                    if self._on_game_ended:
                        try:
                            await self._on_game_ended(self.board_id, reason)
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended({reason}) ERROR: {e}",
                                         exc_info=True)
                    self._credit_consumed = False

                    # Reset WS state for next game
                    self._ws_state.reset()

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
    # STATE READERS
    # ═══════════════════════════════════════════════════════════════

    def _read_ws_event_state(self) -> Optional[ObserverState]:
        """
        Read the accumulated WS event state. This data is populated in real-time
        by the _on_ws_frame_received callback (network-level Playwright hook).
        """
        ws = self._ws_state

        if ws.match_finished and ws.winner_detected:
            logger.info(f"[Observer:{self.board_id}] WS_STATE: final_match_end_detected "
                        f"(trigger={ws.finish_trigger})")
            return ObserverState.FINISHED

        if ws.match_finished:
            logger.info(f"[Observer:{self.board_id}] WS_STATE: match_finished_detected "
                        f"(no explicit winner yet, trigger={ws.finish_trigger})")
            return ObserverState.FINISHED

        if ws.match_active and not ws.match_finished:
            return ObserverState.IN_GAME

        if ws.last_game_event == "gameshot" and not ws.match_finished:
            return ObserverState.ROUND_TRANSITION

        return None  # No definitive WS data

    async def _read_console_state(self) -> Optional[ObserverState]:
        """Read console capture data (injected via add_init_script)."""
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
          4. WS ROUND_TRANSITION → if DOM says IN_GAME, keep IN_GAME (leg change)
          5. DOM result → fallback
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

        # WS says round transition → check DOM
        if ws_state == ObserverState.ROUND_TRANSITION:
            if dom_state == ObserverState.IN_GAME:
                return ObserverState.IN_GAME
            return ObserverState.ROUND_TRANSITION

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
