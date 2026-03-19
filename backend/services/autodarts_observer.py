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
import time
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


class LifecycleState(str, Enum):
    """Observer lifecycle state — controls what operations are allowed."""
    CLOSED = "closed"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    AUTH_REQUIRED = "auth_required"


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
    variant: Optional[str] = None  # v3.3.2: Game variant (e.g., "Gotcha", "501")

    def reset(self):
        self.match_active = False
        self.match_finished = False
        self.winner_detected = False
        self.last_match_state = None
        self.last_game_event = None
        self.last_match_id = None
        self.finish_trigger = None
        # variant NOT reset — persists for the session


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
        self._last_finalized_match_id: Optional[str] = None  # Prevents double-finalize for same match
        self._finalize_dispatching = False  # v3.2.3: single-flight guard for finalize dispatch

        # ── Lifecycle state (serializes start/stop/recovery) ──
        self._lifecycle_state: LifecycleState = LifecycleState.CLOSED
        self._session_generation: int = 0
        self._last_launch_time: float = 0
        self._close_reason: str = ""
        self._close_requested_gen: int = -1  # v3.2.2: generation when close was requested

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

    @property
    def lifecycle_state(self) -> LifecycleState:
        return self._lifecycle_state

    @property
    def is_transitioning(self) -> bool:
        return self._lifecycle_state in (LifecycleState.STARTING, LifecycleState.STOPPING)

    def _set_lifecycle(self, new_state: LifecycleState):
        old = self._lifecycle_state
        if old != new_state:
            self._lifecycle_state = new_state
            logger.info(
                f"[Observer:{self.board_id}] lifecycle_state: {old.value} → {new_state.value} "
                f"(gen={self._session_generation})"
            )

    def _page_alive(self) -> bool:
        """Check if the page is still alive and usable. Null-safe."""
        if self._page is None or self._context is None:
            return False
        try:
            return not self._page.is_closed()
        except Exception:
            return False

    async def _dispatch_finalize(self, trigger: str, source: str) -> Optional[dict]:
        """
        v3.2.3: Single-flight finalize dispatch. Exactly-once guarantee.

        Guards:
          - _finalize_dispatching: prevents concurrent dispatch
          - _finalized: prevents re-dispatch after completion
          - match_id dedup: prevents double-finalize for same match

        Called from: observe_loop debounce, WS match-end safety net, loop exit safety net
        """
        ws = self._ws_state
        match_id = ws.last_match_id
        finalize_key = match_id or f"synthetic_{trigger}_{int(time.time())}"

        # ── Guard: already dispatching ──
        if self._finalize_dispatching:
            logger.info(
                f"[Observer:{self.board_id}] FINALIZE_DISPATCH duplicate ignored "
                f"trigger={trigger} match_id={match_id} finalize_key={finalize_key} "
                f"source={source} reason=already_dispatching"
            )
            return None

        # ── Guard: already finalized for this game cycle ──
        if self._finalized:
            logger.info(
                f"[Observer:{self.board_id}] FINALIZE_DISPATCH duplicate ignored "
                f"trigger={trigger} match_id={match_id} finalize_key={finalize_key} "
                f"source={source} reason=already_finalized"
            )
            return None

        # ── Guard: match_id already finalized (cross-cycle dedup) ──
        if match_id and match_id == self._last_finalized_match_id:
            logger.info(
                f"[Observer:{self.board_id}] FINALIZE_DISPATCH duplicate ignored "
                f"trigger={trigger} match_id={match_id} finalize_key={finalize_key} "
                f"source={source} reason=match_already_finalized"
            )
            return None

        # ── Guard: no callback ──
        if not self._on_game_ended:
            logger.warning(
                f"[Observer:{self.board_id}] FINALIZE_DISPATCH skipped "
                f"trigger={trigger} source={source} reason=no_callback"
            )
            return None

        # ── Dispatch ──
        self._finalize_dispatching = True
        self._finalized = True
        logger.info(
            f"[Observer:{self.board_id}] FINALIZE_DISPATCH start "
            f"trigger={trigger} match_id={match_id} finalize_key={finalize_key} source={source}"
        )

        result = None
        try:
            result = await self._on_game_ended(self.board_id, trigger)
            logger.info(
                f"[Observer:{self.board_id}] FINALIZE_DISPATCH complete "
                f"trigger={trigger} match_id={match_id} finalize_key={finalize_key} "
                f"lock={result.get('should_lock') if result else '?'} "
                f"teardown={result.get('should_teardown') if result else '?'}"
            )
        except Exception as e:
            logger.error(
                f"[Observer:{self.board_id}] FINALIZE_DISPATCH failed "
                f"trigger={trigger} match_id={match_id} error={e}",
                exc_info=True,
            )
        finally:
            self._finalize_dispatching = False

        return result

    def _schedule_finalize_safety(self, trigger: str, match_id: str):
        """
        v3.2.3: Deferred finalize safety net. Runs after poll interval + margin.
        If the observe loop already dispatched finalize, _dispatch_finalize's guards
        will silently skip. If not, this ensures finalize is not lost.
        """
        delay = OBSERVER_POLL_INTERVAL + 3  # poll interval + margin

        async def _safety_check():
            await asyncio.sleep(delay)
            if self._finalized or self._finalize_dispatching or self._stopping:
                logger.info(
                    f"[Observer:{self.board_id}] WS_FINALIZE_SAFETY_NET skipped "
                    f"reason=already_reserved finalized={self._finalized} "
                    f"dispatching={self._finalize_dispatching} stopping={self._stopping}"
                )
                return  # Already handled — all good
            if not self._ws_state.match_finished:
                return  # State was reset (new game started) — no finalize needed
            logger.warning(
                f"[Observer:{self.board_id}] WS_FINALIZE_SAFETY_NET: "
                f"finalize not dispatched after {delay}s, dispatching now. "
                f"trigger={trigger} match_id={match_id}"
            )
            try:
                await self._dispatch_finalize(trigger, source="ws_safety_net")
            except Exception as e:
                logger.error(
                    f"[Observer:{self.board_id}] WS_FINALIZE_SAFETY_NET failed: {e}",
                    exc_info=True,
                )

        try:
            asyncio.get_event_loop().create_task(_safety_check())
        except RuntimeError:
            pass  # No event loop — can't schedule (e.g., during shutdown)


    def _schedule_immediate_finalize(self, trigger: str, match_id: str):
        """
        v3.2.5: Immediate finalize dispatch via asyncio task.
        Fires within the current event loop tick (no sleep).
        Single-flight guard in _dispatch_finalize ensures exactly-once.
        """
        async def _immediate():
            # Tiny yield to allow both WS signals to land (gameshot + state_finished)
            await asyncio.sleep(0.05)
            if self._finalized or self._finalize_dispatching:
                logger.info(
                    f"[Observer:{self.board_id}] FINALIZE_PRIMARY_SKIPPED "
                    f"reason={'already_finalized' if self._finalized else 'already_dispatching'} "
                    f"trigger={trigger}"
                )
                return
            logger.info(
                f"[Observer:{self.board_id}] FINALIZE_PRIMARY_DISPATCH "
                f"trigger={trigger} match_id={match_id} source=ws_primary"
            )
            try:
                await self._dispatch_finalize(trigger, source="ws_primary")
            except Exception as e:
                logger.error(
                    f"[Observer:{self.board_id}] FINALIZE_PRIMARY_DISPATCH failed: {e}",
                    exc_info=True,
                )

        try:
            asyncio.get_event_loop().create_task(_immediate())
        except RuntimeError:
            pass

    def _check_profile_locked(self, profile_dir: str) -> bool:
        """
        Safety check: detect if another Chrome instance is already using this
        user-data-dir. If found, attempts to kill it and clean up.
        Returns True if STILL locked (caller must abort), False if safe.
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

        # ── Find Chrome processes using this profile ──
        chrome_pids = self._find_chrome_pids_for_profile(profile_norm)

        if chrome_pids:
            logger.warning(
                f"[Observer:{self.board_id}] Chrome processes holding profile: "
                f"pids={chrome_pids} profile={profile_abs}"
            )
            # ── Kill them ──
            killed = self._kill_pids(chrome_pids)
            if killed:
                logger.info(
                    f"[Observer:{self.board_id}] Killed {len(killed)} Chrome processes, "
                    f"waiting for exit..."
                )
                time.sleep(2)  # Wait for process exit

                # ── Re-check: are lock files still there? ──
                remaining_locks = [
                    name for name in lock_names
                    if os.path.exists(os.path.join(profile_dir, name))
                ]
                if remaining_locks:
                    # Processes killed but locks remain → stale, clean up
                    still_running = self._find_chrome_pids_for_profile(profile_norm)
                    if still_running:
                        logger.error(
                            f"[Observer:{self.board_id}] *** PROFILE STILL LOCKED *** "
                            f"Chrome pids={still_running} survived kill. "
                            f"Cannot launch observer. Profile: {profile_abs}"
                        )
                        return True
                    # Processes gone, stale locks remain → clean up
                    for name in remaining_locks:
                        lock_path = os.path.join(profile_dir, name)
                        try:
                            os.remove(lock_path)
                            logger.info(f"[Observer:{self.board_id}] Removed stale lock after kill: {lock_path}")
                        except Exception as e:
                            logger.warning(f"[Observer:{self.board_id}] Could not remove lock {lock_path}: {e}")
                return False  # Profile is now free
            else:
                logger.error(
                    f"[Observer:{self.board_id}] *** PROFILE LOCKED *** "
                    f"Could not kill Chrome processes. Profile: {profile_abs}"
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

    def _find_chrome_pids_for_profile(self, profile_norm: str) -> list:
        """Find Chrome process PIDs using the given profile directory."""
        pids = []
        if sys.platform == 'win32':
            try:
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" "
                     "| Select-Object ProcessId,CommandLine | Format-List"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                )
                current_pid = None
                for line in result.stdout.splitlines():
                    s = line.strip()
                    if s.lower().startswith('processid'):
                        current_pid = s.split(':', 1)[1].strip()
                    elif s.lower().startswith('commandline') and current_pid:
                        cmdline = s.split(':', 1)[1].strip().lower().replace('/', '\\')
                        if profile_norm in cmdline:
                            pids.append(current_pid)
                            logger.info(
                                f"[Observer:{self.board_id}] chrome_pid={current_pid} "
                                f"matched user-data-dir={profile_norm}"
                            )
                        current_pid = None
            except Exception as e:
                logger.debug(f"[Observer:{self.board_id}] PowerShell PID scan failed: {e}")
        else:
            try:
                result = subprocess.run(
                    ['pgrep', '-af', 'chrome'],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                )
                for line in result.stdout.splitlines():
                    if profile_norm in line.lower():
                        pid = line.split()[0]
                        pids.append(pid)
                        logger.info(
                            f"[Observer:{self.board_id}] chrome_pid={pid} "
                            f"matched user-data-dir={profile_norm}"
                        )
            except Exception:
                pass
        return pids

    def _kill_pids(self, pids: list) -> list:
        """Kill processes by PID. Returns list of successfully killed PIDs."""
        killed = []
        for pid in pids:
            try:
                if sys.platform == 'win32':
                    r = subprocess.run(
                        ['taskkill', '/F', '/PID', str(pid)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                    )
                else:
                    r = subprocess.run(
                        ['kill', '-9', str(pid)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                    )
                if r.returncode == 0:
                    logger.info(f"[Observer:{self.board_id}] CHROME_KILL: pid={pid} success")
                    killed.append(pid)
                else:
                    logger.warning(f"[Observer:{self.board_id}] CHROME_KILL: pid={pid} failed rc={r.returncode}")
            except Exception as e:
                logger.warning(f"[Observer:{self.board_id}] CHROME_KILL: pid={pid} error: {e}")
        return killed

    async def open_session(
        self,
        autodarts_url: str,
        on_game_started: Optional[Callable] = None,
        on_game_ended: Optional[Callable] = None,
        headless: bool = False,
    ):
        """Open Chrome with persistent profile and start the observer loop."""
        # ═══ v3.2.5: COMPREHENSIVE START GUARD ═══
        # Abort if ANY close/finalize path is active or reserved
        if self._lifecycle_state in (LifecycleState.STARTING, LifecycleState.STOPPING, LifecycleState.CLOSED):
            if self._closing or self._stopping or self._finalize_dispatching:
                logger.warning(
                    f"[Observer:{self.board_id}] START_ABORTED reason=close_in_progress "
                    f"lifecycle={self._lifecycle_state.value} closing={self._closing} "
                    f"stopping={self._stopping} dispatching={self._finalize_dispatching} "
                    f"gen={self._session_generation}"
                )
                return
            if self._lifecycle_state in (LifecycleState.STARTING, LifecycleState.STOPPING):
                logger.warning(
                    f"[Observer:{self.board_id}] open_session BLOCKED — "
                    f"lifecycle={self._lifecycle_state.value} (gen={self._session_generation})"
                )
                return

        if self._closing or self._stopping:
            logger.warning(
                f"[Observer:{self.board_id}] START_ABORTED reason=close_in_progress "
                f"lifecycle={self._lifecycle_state.value} gen={self._session_generation}"
            )
            return

        if self._finalize_dispatching:
            logger.warning(
                f"[Observer:{self.board_id}] START_ABORTED reason=finalize_in_progress "
                f"gen={self._session_generation}"
            )
            return

        if self.is_open:
            logger.info(f"[Observer:{self.board_id}] Browser already open, skipping")
            return

        # ── Transition to STARTING ──
        self._session_generation += 1
        gen = self._session_generation
        self._set_lifecycle(LifecycleState.STARTING)
        self._last_launch_time = time.time()

        self._on_game_started = on_game_started
        self._on_game_ended = on_game_ended

        # ── HARD RESET of all runtime flags for clean start ──
        self._stopping = False
        self._closing = False
        self._finalized = False
        self._finalize_dispatching = False
        self._abort_detected = False
        self._last_finalized_match_id = None
        self._stable_state = ObserverState.CLOSED
        self._exit_polls = 0
        self._exit_saw_finished = False
        self._credit_consumed = False
        self._ws_state = WSEventState()
        self._ws_frames.clear()

        logger.info(f"[Observer:{self.board_id}] ALL_FLAGS_RESET: "
                    f"stopping=False closing=False finalized=False abort_detected=False "
                    f"last_finalized_match_id=None gen={self._session_generation}")

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
            self._set_lifecycle(LifecycleState.ERROR)
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
            def _make_page_close_handler(obs_ref):
                def handler():
                    lc = obs_ref._lifecycle_state.value
                    gen = obs_ref._session_generation
                    close_requested = (obs_ref._stopping or obs_ref._closing
                                       or obs_ref._close_requested_gen == gen
                                       or lc in ("stopping", "closed", "auth_required"))
                    if close_requested:
                        logger.info(
                            f"[Observer:{obs_ref.board_id}] PAGE_CLOSED_EXPECTED "
                            f"lifecycle={lc} gen={gen}"
                        )
                    else:
                        logger.error(
                            f"[Observer:{obs_ref.board_id}] PAGE_CLOSED_UNEXPECTED "
                            f"lifecycle={lc} gen={gen}"
                        )
                return handler

            def _make_page_crash_handler(obs_ref):
                def handler():
                    lc = obs_ref._lifecycle_state.value
                    gen = obs_ref._session_generation
                    logger.error(
                        f"[Observer:{obs_ref.board_id}] *** PAGE_CRASHED *** "
                        f"lifecycle={lc} gen={gen}"
                    )
                return handler

            def _make_context_close_handler(obs_ref):
                def handler():
                    lc = obs_ref._lifecycle_state.value
                    gen = obs_ref._session_generation
                    close_requested = (obs_ref._stopping or obs_ref._closing
                                       or obs_ref._close_requested_gen == gen
                                       or lc in ("stopping", "closed", "auth_required"))
                    if close_requested:
                        logger.info(
                            f"[Observer:{obs_ref.board_id}] CONTEXT_CLOSED_EXPECTED "
                            f"lifecycle={lc} gen={gen}"
                        )
                    else:
                        logger.error(
                            f"[Observer:{obs_ref.board_id}] CONTEXT_CLOSED_UNEXPECTED "
                            f"lifecycle={lc} gen={gen}"
                        )
                return handler

            self._page.on("close", _make_page_close_handler(self))
            self._page.on("crash", _make_page_crash_handler(self))
            self._context.on("close", _make_context_close_handler(self))

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
            current_url = self._page.url if self._page else "page_none"
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
            _current_url = self._page.url if self._page else ""
            if 'about:blank' in _current_url:
                logger.error(
                    f"[Observer:{self.board_id}] *** NAVIGATION FAILED *** "
                    f"Page is still on about:blank after goto({url}). "
                    f"Autodarts may be unreachable."
                )

            # ── Auth redirect detection ──
            final_url = _current_url.lower()
            is_auth_redirect = (
                'login.autodarts.io' in final_url
                or '/login' in final_url
                or '/auth' in final_url
                or 'signin' in final_url
            )
            if is_auth_redirect:
                logger.error(
                    f"[Observer:{self.board_id}] *** AUTH_REQUIRED *** "
                    f"Browser landed on login page: {_current_url}  "
                    f"Session/cookies for profile {profile_dir_abs} are invalid or expired. "
                    f"Please log in manually once, then restart the observer."
                )
                self.status.last_error = f"auth_required: {_current_url}"
                self._close_reason = "auth_required"
                self._set_state(ObserverState.ERROR)
                self._set_lifecycle(LifecycleState.AUTH_REQUIRED)
                self.status.browser_open = False
                await self._cleanup()
                # Do NOT start observe loop, do NOT hide kiosk
                return

            self.status.browser_open = True
            self._set_state(ObserverState.IDLE)
            self._stable_state = ObserverState.IDLE

            # NOTE: Kiosk hide is deferred until AFTER health check confirms valid session

            # ── Post-launch health check: verify page is still alive ──
            health_ok = True
            for check_at in [3, 7, 12]:
                # Stale generation check: abort if a newer session superseded this one
                if self._session_generation != gen:
                    logger.warning(
                        f"[Observer:{self.board_id}]   HEALTH stale gen={gen} "
                        f"current={self._session_generation}, aborting"
                    )
                    health_ok = False
                    break
                # v3.2.2: If close was requested for this generation, abort health checks
                if self._close_requested_gen == gen:
                    logger.info(
                        f"[Observer:{self.board_id}] stale launch callback ignored because close requested "
                        f"gen={gen} close_reason={self._close_reason}"
                    )
                    health_ok = False
                    break
                await asyncio.sleep(check_at - (0 if check_at == 3 else (3 if check_at == 7 else 7)))
                if not self._page_alive():
                    logger.error(
                        f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                        f"page_alive=False (page or context is None/closed)"
                    )
                    health_ok = False
                    break
                try:
                    if not self._page:
                        raise RuntimeError("page is None")
                    alive_url = self._page.url
                    page_count = len(self._context.pages) if self._context else 0
                    # Auth redirect detection during health check
                    alive_lower = alive_url.lower()
                    if 'login.autodarts.io' in alive_lower or '/login' in alive_lower:
                        logger.error(
                            f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                            f"AUTH_REDIRECT_DETECTED url={alive_url}"
                        )
                        health_ok = False
                        self.status.last_error = f"auth_required: {alive_url}"
                        self._close_reason = "auth_required"
                        self._set_state(ObserverState.ERROR)
                        self.status.browser_open = False
                        self._set_lifecycle(LifecycleState.AUTH_REQUIRED)
                        break
                    logger.info(
                        f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                        f"page_alive=True, url={alive_url}, pages={page_count}"
                    )
                except Exception as health_err:
                    logger.error(
                        f"[Observer:{self.board_id}]   HEALTH@{check_at}s: "
                        f"page_alive=False, error={health_err}"
                    )
                    health_ok = False
                    break

            if health_ok:
                # v3.2.2: Final close-intent check before transitioning to RUNNING
                if self._close_requested_gen == gen or self._closing:
                    logger.info(
                        f"[Observer:{self.board_id}] stale launch callback ignored because close requested "
                        f"gen={gen}"
                    )
                    await self._cleanup()
                else:
                    logger.info(f"[Observer:{self.board_id}] === BROWSER LAUNCH SUCCESS === (gen={gen})")
                    self._set_lifecycle(LifecycleState.RUNNING)
                    # Only hide kiosk AFTER health confirms valid authenticated session
                    try:
                        from backend.services.window_manager import hide_kiosk_window
                        await hide_kiosk_window()
                        logger.info(f"[Observer:{self.board_id}]   Kiosk window hidden (session confirmed)")
                    except Exception as wm_err:
                        logger.warning(f"[Observer:{self.board_id}]   Window management skipped: {wm_err}")
                    self._observe_task = asyncio.create_task(self._observe_loop())
            else:
                # Preserve AUTH_REQUIRED — do NOT overwrite with ERROR
                if self._lifecycle_state != LifecycleState.AUTH_REQUIRED:
                    logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED (health) === (gen={gen})")
                    self._set_lifecycle(LifecycleState.ERROR)
                    self.status.last_error = "Post-launch health check failed"
                else:
                    logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED (auth_required) === (gen={gen})")
                await self._cleanup()

        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] === BROWSER LAUNCH FAILED === {e}", exc_info=True)
            self.status.last_error = f"{type(e).__name__}: {str(e)[:200]}"
            self._set_state(ObserverState.ERROR)
            self._set_lifecycle(LifecycleState.ERROR)
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

    def _extract_variant(self, payload) -> Optional[str]:
        """Extract game variant from WS payload (e.g., 'gotcha', 'x01', 'cricket')."""
        if not isinstance(payload, dict):
            return None
        for key in ('variant', 'gameMode', 'mode', 'gameType'):
            val = payload.get(key)
            if isinstance(val, str) and val:
                return val
        for container in ('data', 'body', 'match'):
            nested = payload.get(container)
            if isinstance(nested, dict):
                for key in ('variant', 'gameMode', 'mode', 'gameType'):
                    val = nested.get(key)
                    if isinstance(val, str) and val:
                        return val
        return None

    def _is_gotcha(self) -> bool:
        """Check if current match is a Gotcha variant."""
        variant = (self._ws_state.variant or "").lower()
        return "gotcha" in variant

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
            # v3.3.1: Revoke false finish if in-game signal arrives after premature match_finished
            if ws.match_finished:
                old_trigger = ws.finish_trigger
                logger.warning(
                    f"[Observer:{self.board_id}] *** FALSE_FINISH_REVOKED *** "
                    f"reason={interpretation} after premature trigger={old_trigger} "
                    f"match_id={ws.last_match_id} — match is still active"
                )
                ws.match_finished = False
                ws.winner_detected = False
                ws.finish_trigger = None
                ws.match_active = True
                self._finalized = False
                self._finalize_dispatching = False
            elif not ws.match_active:
                ws.match_active = True
                logger.info(
                    f"[Observer:{self.board_id}] *** MATCH START DETECTED *** "
                    f"reason={interpretation} | match_id={ws.last_match_id}"
                )

        # ═══ MATCH END (authoritative) ═══
        elif interpretation in ("match_end_gameshot_match", "match_end_state_finished",
                                "match_end_game_finished", "match_finished_matchshot"):
            # v3.3.2: Extract variant from payload if available
            if payload:
                _ev = self._extract_variant(payload)
                if _ev and not ws.variant:
                    ws.variant = _ev
                    logger.info(
                        f"[Observer:{self.board_id}] VARIANT_DETECTED "
                        f"variant={_ev} source={interpretation}")

            # Duplicate match-ID guard: ignore repeat finish signals for already-finalized match
            current_mid = ws.last_match_id
            if current_mid and current_mid == self._last_finalized_match_id:
                logger.info(
                    f"[Observer:{self.board_id}] MATCH_FINISH_DUPLICATE_IGNORED "
                    f"trigger={interpretation} match_id={current_mid} reason=match_already_finalized")
                return

            # v3.3.1: Separate confirmed (state frame) from pending (gameshot) signals
            is_confirmed = interpretation in ("match_end_state_finished", "match_end_game_finished")
            is_gameshot_trigger = interpretation in ("match_end_gameshot_match", "match_finished_matchshot")

            # v3.3.2: Gotcha variant guard — game_shot/matchshot are NOT reliable for Gotcha
            # In Gotcha, opponent score resets and intermediate states can trigger game_shot
            # with body.type=match, which is NOT a real match end.
            if self._is_gotcha() and is_gameshot_trigger:
                logger.info(
                    f"[Observer:{self.board_id}] MATCH_FINISH_CANDIDATE variant=Gotcha "
                    f"trigger={interpretation} confirmed=False "
                    f"match_id={current_mid}")
                logger.info(
                    f"[Observer:{self.board_id}] MATCH_FINISH_REJECTED variant=Gotcha "
                    f"reason=game_shot_without_confirmed_finished_state "
                    f"trigger={interpretation} match_id={current_mid}")
                return  # Do NOT set match_finished, do NOT schedule finalize

            if ws.match_finished:
                if is_confirmed and ws.finish_trigger not in ("match_end_state_finished", "match_end_game_finished"):
                    # State frame CONFIRMS a pending gameshot finish — upgrade trigger and dispatch
                    logger.info(
                        f"[Observer:{self.board_id}] MATCH_FINISH_CONFIRMED "
                        f"trigger={interpretation} match_id={current_mid} "
                        f"variant={ws.variant or 'standard'} "
                        f"(upgrades pending trigger={ws.finish_trigger})")
                    ws.finish_trigger = interpretation
                    self._schedule_immediate_finalize(interpretation, ws.last_match_id)
                else:
                    logger.info(
                        f"[Observer:{self.board_id}] MATCH_FINISH_DUPLICATE_IGNORED "
                        f"trigger={interpretation} match_id={current_mid} reason=already_marked_finished "
                        f"first_trigger={ws.finish_trigger}")
                return

            ws.match_finished = True
            ws.match_active = False
            ws.winner_detected = True
            ws.finish_trigger = interpretation
            logger.info(
                f"[Observer:{self.board_id}] *** MATCH FINISH DETECTED *** "
                f"trigger={interpretation} | match_id={ws.last_match_id} | "
                f"confirmed={is_confirmed} | variant={ws.variant or 'unknown'}"
            )

            # v3.3.2: Log ACCEPTED with variant and confirmation details
            if self._is_gotcha():
                logger.info(
                    f"[Observer:{self.board_id}] MATCH_FINISH_ACCEPTED variant=Gotcha "
                    f"trigger={interpretation} confirmed={is_confirmed} "
                    f"match_id={ws.last_match_id}")
            else:
                logger.info(
                    f"[Observer:{self.board_id}] MATCH_FINISH_ACCEPTED "
                    f"trigger={interpretation} match_id={ws.last_match_id} "
                    f"variant={ws.variant or 'standard'}")

            if is_confirmed:
                # State frame (finished=true) = authoritative → immediate finalize
                self._schedule_immediate_finalize(interpretation, ws.last_match_id)
            else:
                # gameshot_match/matchshot = may be premature for multi-leg matches
                # Let debounce or state frame confirm; safety net as backup
                logger.info(
                    f"[Observer:{self.board_id}] MATCH_FINISH_PENDING "
                    f"trigger={interpretation} match_id={ws.last_match_id} "
                    f"variant={ws.variant or 'standard'} "
                    f"(awaiting state frame confirmation or debounce)")

            # Always schedule safety net as backup
            self._schedule_finalize_safety(interpretation, ws.last_match_id)

        # ═══ POST-MATCH RESET (delete = match removed) ═══
        elif interpretation == "match_reset_delete":
            was_active = ws.match_active
            was_finished = ws.match_finished
            old_match_id = ws.last_match_id

            if was_active and not was_finished:
                # Duplicate match-ID guard: ignore abort for already-finalized match
                if old_match_id and old_match_id == self._last_finalized_match_id:
                    logger.info(
                        f"[Observer:{self.board_id}] SKIP_DUPLICATE_FINALIZE "
                        f"match_id={old_match_id} (abort signal for already-finalized match)")
                    ws.reset()
                    return
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

    async def close_session(self, reason: str = "unknown"):
        """
        Close Playwright browser ONLY. Idempotent.
        Detects self-call (from within observe_task) to avoid deadlock.
        Does NOT handle kiosk window management — that is finalize_match's job.
        reason: manual_lock | session_end | watchdog_recovery | crash_cleanup | admin_stop
        """
        import time as _t
        t0 = _t.monotonic()

        if self._lifecycle_state == LifecycleState.CLOSED:
            logger.info(f"[Observer:{self.board_id}] CLOSE_SESSION_SKIPPED (lifecycle=closed)")
            return
        if self._closing:
            logger.info(f"[Observer:{self.board_id}] CLOSE_SESSION_SKIPPED (already closing)")
            return
        self._closing = True
        self._stopping = True
        # v3.2.4: Preserve committed close_reason — never degrade to "unknown"
        if not self._close_reason or self._close_reason == "unknown":
            self._close_reason = reason
        else:
            logger.info(
                f"[Observer:{self.board_id}] close_reason preserved={self._close_reason} "
                f"(incoming={reason} ignored)"
            )
        # Mark close-requested generation so stale callbacks can detect it
        self._close_requested_gen = self._session_generation
        self._set_lifecycle(LifecycleState.STOPPING)
        logger.info(
            f"[Observer:{self.board_id}] === CLOSE_SESSION_START === "
            f"(gen={self._session_generation}, reason={self._close_reason})"
        )
        logger.info(f"[Observer:{self.board_id}] CLOSE_PATH_RESERVED gen={self._session_generation}")

        ms = int((_t.monotonic() - t0) * 1000)
        logger.info(f"[FINALIZE_TIMING] close_lock_acquired ms={ms} board={self.board_id}")

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
                    await asyncio.wait_for(
                        asyncio.shield(self._observe_task),
                        timeout=5.0,
                    )
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        self._observe_task = None

        ms = int((_t.monotonic() - t0) * 1000)
        logger.info(f"[FINALIZE_TIMING] observe_cancel_done ms={ms} board={self.board_id}")

        await self._cleanup()
        self._set_state(ObserverState.CLOSED)
        self._set_lifecycle(LifecycleState.CLOSED)

        ms = int((_t.monotonic() - t0) * 1000)
        logger.info(f"[FINALIZE_TIMING] lifecycle_closed ms={ms} board={self.board_id}")

        # v3.3.1: Reset guard flags after close is FULLY COMPLETE
        # This prevents START_PATH_BLOCKED deadlock in watchdog recovery
        self._closing = False
        self._stopping = False
        self._finalize_dispatching = False

        logger.info(
            f"[Observer:{self.board_id}] === CLOSE_SESSION_DONE === "
            f"reason={self._close_reason} guards_reset=True"
        )

    async def _cleanup(self):
        """Close Playwright objects step-by-step with detailed logging and timeouts."""
        import time as _t
        t0 = _t.monotonic()

        # Step 1: Close page (3s timeout)
        if self._page:
            try:
                await asyncio.wait_for(self._page.close(), timeout=3.0)
                ms = int((_t.monotonic() - t0) * 1000)
                logger.info(f"[FINALIZE_TIMING] page_close_done ms={ms} board={self.board_id}")
            except asyncio.TimeoutError:
                ms = int((_t.monotonic() - t0) * 1000)
                logger.warning(f"[FINALIZE_TIMING] page_close_timeout ms={ms} board={self.board_id}")
            except Exception as e:
                logger.debug(f"[AUTODARTS] page close error: {e}")
        self._page = None

        # Step 2: Close context (3s timeout)
        if self._context:
            try:
                await asyncio.wait_for(self._context.close(), timeout=3.0)
                ms = int((_t.monotonic() - t0) * 1000)
                logger.info(f"[FINALIZE_TIMING] context_close_done ms={ms} board={self.board_id}")
            except asyncio.TimeoutError:
                ms = int((_t.monotonic() - t0) * 1000)
                logger.warning(f"[FINALIZE_TIMING] context_close_timeout ms={ms} board={self.board_id}")
            except Exception as e:
                logger.debug(f"[AUTODARTS] context close error: {e}")
        self._context = None

        # Step 3: Stop Playwright (5s timeout)
        if self._playwright:
            try:
                await asyncio.wait_for(self._playwright.stop(), timeout=5.0)
                ms = int((_t.monotonic() - t0) * 1000)
                logger.info(f"[FINALIZE_TIMING] playwright_stop_done ms={ms} board={self.board_id}")
            except asyncio.TimeoutError:
                ms = int((_t.monotonic() - t0) * 1000)
                logger.warning(f"[FINALIZE_TIMING] playwright_stop_timeout ms={ms} board={self.board_id}")
            except Exception as e:
                logger.debug(f"[AUTODARTS] playwright stop error: {e}")
        self._playwright = None

        self.status.browser_open = False
        total_ms = int((_t.monotonic() - t0) * 1000)
        logger.info(f"[FINALIZE_TIMING] cleanup_complete ms={total_ms} board={self.board_id}")

    # ═══════════════════════════════════════════════════════════════
    # NAVIGATE BACK TO HOME/LOBBY (after game ends, credits remain)
    # ═══════════════════════════════════════════════════════════════

    async def _navigate_to_home(self):
        """
        Navigate the Autodarts page back to home/lobby after a game ends.
        Prevents the browser from staying on the finished match result page.
        Returns True on success, False on failure.
        """
        logger.info(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME start")
        if not self._page_alive():
            logger.warning(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME skip (page not alive)")
            return False

        home_url = self.status.autodarts_url or AUTODARTS_URL

        # Primary: navigate to the configured Autodarts URL (home/lobby)
        try:
            await self._page.goto(home_url, wait_until="domcontentloaded", timeout=10000)
            current_url = self._page.url if self._page else "page_gone"
            logger.info(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME success url={current_url}")
            return True
        except Exception as e:
            logger.error(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME failed: {e}")

        # Fallback 1: try base Autodarts URL
        try:
            await self._page.goto(AUTODARTS_URL, wait_until="domcontentloaded", timeout=10000)
            logger.info(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME fallback success")
            return True
        except Exception as e2:
            logger.error(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME fallback failed: {e2}")

        # Fallback 2: force reload current page
        try:
            await self._page.reload(wait_until="domcontentloaded", timeout=10000)
            logger.info(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME reload-fallback success")
            return True
        except Exception as e3:
            logger.error(f"[Observer:{self.board_id}] AUTODARTS_RETURN_TO_HOME reload-fallback failed: {e3}")

        return False

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
                # ── FAST PATH: Abort → immediate finalize, NO sleep ──
                if self._abort_detected and not self._finalized:
                    logger.info(f"[Observer:{self.board_id}] ABORT_FAST_PATH — "
                                f"immediate finalize, zero delay (before sleep/poll)")
                    self._finalized = True
                    self._abort_detected = False
                    self._stable_state = ObserverState.IDLE
                    self._set_state(ObserverState.IDLE)
                    self._exit_polls = 0
                    self._exit_saw_finished = False

                    if self._on_game_ended:
                        try:
                            result = await self._dispatch_finalize("aborted", source="abort_fast_path")
                            logger.info(f"[Observer:{self.board_id}] abort finalize returned: "
                                        f"lock={result.get('should_lock') if result else '?'} "
                                        f"teardown={result.get('should_teardown') if result else '?'}")
                        except Exception as e:
                            logger.error(f"[Observer:{self.board_id}] on_game_ended(aborted) ERROR: {e}",
                                         exc_info=True)

                    if self._stopping:
                        logger.info(f"[Observer:{self.board_id}] _stopping=True after abort finalize")
                        break

                    # Credits remain — state reset only (navigation done by finalize_match)
                    self._finalized = False
                    self._credit_consumed = False
                    self._abort_detected = False
                    self._exit_polls = 0
                    self._exit_saw_finished = False
                    self._ws_state.reset()
                    self._stable_state = ObserverState.IDLE
                    self._set_state(ObserverState.IDLE)
                    logger.info(f"[Observer:{self.board_id}] OBSERVER_RESET_FOR_NEXT_GAME done")
                    logger.info(f"[Observer:{self.board_id}] READY_FOR_NEXT_GAME (abort path)")
                    continue

                interval = DEBOUNCE_POLL_INTERVAL if self._exit_polls > 0 else OBSERVER_POLL_INTERVAL
                await asyncio.sleep(interval)

                # ═══ v3.2.4+v3.3.1: PRIORITY CHECK — finalize before page-alive ═══
                # Only dispatch for STATE-FRAME-CONFIRMED finishes (not pending gameshot)
                # Pending gameshot triggers go through debounce for false-finish protection
                ws_pre = self._ws_state
                _confirmed_triggers = ("match_end_state_finished", "match_end_game_finished")
                if (ws_pre.match_finished and ws_pre.finish_trigger in _confirmed_triggers
                        and not self._finalized and not self._finalize_dispatching):
                    trigger = ws_pre.finish_trigger or "finished"
                    logger.info(
                        f"[Observer:{self.board_id}] FINALIZE_PRIMARY_DISPATCH "
                        f"trigger={trigger} match_id={ws_pre.last_match_id} "
                        f"source=observe_loop_priority_check"
                    )
                    result = await self._dispatch_finalize(trigger, source="observe_loop_priority")
                    if result is not None:
                        if result.get("should_teardown"):
                            stop_reason = "finalize_teardown"
                            break
                        else:
                            # keep_alive: reset for next game
                            self._finalized = False
                            self._finalize_dispatching = False
                            self._credit_consumed = False
                            self._exit_polls = 0
                            self._exit_saw_finished = False
                            self._ws_state.reset()
                            self._stable_state = ObserverState.IDLE
                            self._set_state(ObserverState.IDLE)
                            logger.info(f"[Observer:{self.board_id}] OBSERVER_RESET_FOR_NEXT_GAME done")
                            logger.info(f"[Observer:{self.board_id}] READY_FOR_NEXT_GAME (primary dispatch, keep_alive)")
                            continue

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

                # ── Browser health check (null-safe) ──
                if not self._page:
                    stop_reason = "page_is_none"
                    logger.warning(f"[Observer:{self.board_id}] page is None during health check, breaking")
                    break
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

                    # Fast-track: only state-frame confirmed triggers skip debounce
                    # v3.3.1: gameshot_match needs full debounce (false-finish protection)
                    _confirmed_debounce = ("match_end_state_finished", "match_end_game_finished")
                    debounce_needed = 1 if ws.finish_trigger in _confirmed_debounce else DEBOUNCE_EXIT_POLLS
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

                    # ── Call finalize DIRECTLY via single-flight dispatcher ──
                    if not self._finalized:
                        result = await self._dispatch_finalize(reason, source="debounce_confirmed")
                    else:
                        logger.info(f"[Observer:{self.board_id}] FINALIZE_SKIPPED (already finalized)")

                    if self._stopping:
                        logger.info(f"[Observer:{self.board_id}] _stopping=True after finalize, exiting loop")
                        break

                    # Credits remain — state reset only (navigation done by finalize_match)
                    self._finalized = False
                    self._credit_consumed = False
                    self._abort_detected = False
                    self._exit_polls = 0
                    self._exit_saw_finished = False
                    self._ws_state.reset()
                    self._stable_state = ObserverState.IDLE
                    self._set_state(ObserverState.IDLE)
                    logger.info(f"[Observer:{self.board_id}] OBSERVER_RESET_FOR_NEXT_GAME done")
                    logger.info(f"[Observer:{self.board_id}] READY_FOR_NEXT_GAME (debounce path)")

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

        # ═══ v3.2.3: LOOP-EXIT SAFETY NET ═══
        # If the loop exited (page died, crash, etc.) but a match finish was detected
        # and finalize never ran, dispatch it now. This prevents lost finalizes.
        # v3.2.4: Removed `not self._stopping` condition — finalize must run regardless
        ws = self._ws_state
        if ws.match_finished and not self._finalized and not self._finalize_dispatching:
            trigger = ws.finish_trigger or "finished"
            logger.warning(
                f"[Observer:{self.board_id}] LOOP_EXIT_SAFETY_NET: "
                f"match_finished=True but finalize never ran! "
                f"trigger={trigger} match_id={ws.last_match_id} stop_reason={stop_reason}"
            )
            try:
                result = await self._dispatch_finalize(trigger, source="loop_exit_safety_net")
                logger.info(
                    f"[Observer:{self.board_id}] LOOP_EXIT_SAFETY_NET complete: "
                    f"lock={result.get('should_lock') if result else '?'}"
                )
            except Exception as e:
                logger.error(
                    f"[Observer:{self.board_id}] LOOP_EXIT_SAFETY_NET failed: {e}",
                    exc_info=True,
                )

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
    """Manages one AutodartsObserver instance per board with lifecycle serialization."""

    def __init__(self):
        self._observers: Dict[str, AutodartsObserver] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._desired_state: Dict[str, str] = {}      # board_id -> "running" | "stopped"
        self._close_reasons: Dict[str, str] = {}       # board_id -> last close reason

    def _get_lock(self, board_id: str) -> asyncio.Lock:
        if board_id not in self._locks:
            self._locks[board_id] = asyncio.Lock()
        return self._locks[board_id]

    # ── Desired state management ──

    def set_desired_state(self, board_id: str, state: str):
        old = self._desired_state.get(board_id, "stopped")
        self._desired_state[board_id] = state
        if old != state:
            logger.info(f"[ObserverMgr] desired_state: {board_id} {old} → {state}")

    def get_desired_state(self, board_id: str) -> str:
        return self._desired_state.get(board_id, "stopped")

    def get_close_reason(self, board_id: str) -> str:
        return self._close_reasons.get(board_id, "")

    def clear_close_reason(self, board_id: str):
        """Clear stale close_reason after keep-alive path. Only call when observer stays alive."""
        old = self._close_reasons.get(board_id, "")
        if old:
            self._close_reasons[board_id] = ""
            logger.info(f"[ObserverMgr] close_reason cleared: {board_id} was={old}")
        obs = self._observers.get(board_id)
        if obs and obs._close_reason:
            obs._close_reason = ""

    def get(self, board_id: str) -> Optional[AutodartsObserver]:
        return self._observers.get(board_id)

    def get_status(self, board_id: str) -> dict:
        obs = self._observers.get(board_id)
        if obs:
            d = obs.status.to_dict()
            d["lifecycle"] = obs.lifecycle_state.value
            d["session_generation"] = obs._session_generation
            d["desired_state"] = self.get_desired_state(board_id)
            d["close_reason"] = self._close_reasons.get(board_id, "")
            return d
        d = ObserverStatus(board_id=board_id).to_dict()
        d["lifecycle"] = "closed"
        d["session_generation"] = 0
        d["desired_state"] = self.get_desired_state(board_id)
        d["close_reason"] = self._close_reasons.get(board_id, "")
        return d

    def get_all_statuses(self) -> list:
        return [self.get_status(bid) for bid in self._observers]

    async def open(
        self,
        board_id: str,
        autodarts_url: str,
        on_game_started=None,
        on_game_ended=None,
        headless: bool = False,
    ):
        # v3.2.4: Block open if a close is in progress for this board
        obs_existing = self._observers.get(board_id)
        if obs_existing and (obs_existing._closing or obs_existing._finalize_dispatching):
            logger.warning(
                f"[ObserverMgr] START_PATH_BLOCKED reason=close_in_progress "
                f"board={board_id} gen={obs_existing._session_generation}"
            )
            return obs_existing

        lock = self._get_lock(board_id)
        logger.info(f"[ObserverMgr] lifecycle_lock acquiring board={board_id}")
        async with lock:
            logger.info(f"[ObserverMgr] lifecycle_lock acquired board={board_id}")
            try:
                existing = self._observers.get(board_id)
                if existing:
                    if existing.is_open:
                        logger.info(f"[ObserverMgr] Board {board_id} already open, returning existing")
                        return existing
                    logger.info(f"[ObserverMgr] Cleaning up dead observer for {board_id}")
                    try:
                        await existing.close_session(reason="cleanup_before_reopen")
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
                # Propagate close_reason from observer to manager
                # (auth_required sets close_reason on the instance, not via close())
                if obs._close_reason:
                    self._close_reasons[board_id] = obs._close_reason
                return obs
            finally:
                logger.info(f"[ObserverMgr] lifecycle_lock released board={board_id}")

    async def close(self, board_id: str, reason: str = "unknown"):
        lock = self._get_lock(board_id)
        logger.info(f"[ObserverMgr] lifecycle_lock acquiring (close) board={board_id} reason={reason}")
        try:
            # v3.2.4: Bounded lock acquisition — don't hang forever if watchdog holds lock
            await asyncio.wait_for(lock.acquire(), timeout=8.0)
        except asyncio.TimeoutError:
            logger.error(
                f"[ObserverMgr] lifecycle_lock TIMEOUT (close) board={board_id} reason={reason} "
                f"— forcing close without lock"
            )
            # Force close without lock to prevent finalize deadlock
            obs = self._observers.get(board_id)
            self._close_reasons[board_id] = reason
            if obs:
                try:
                    await asyncio.wait_for(obs.close_session(reason=reason), timeout=8.0)
                except (asyncio.TimeoutError, Exception) as e:
                    logger.error(f"[ObserverMgr] forced close failed: {e}")
            return
        try:
            logger.info(f"[ObserverMgr] lifecycle_lock acquired (close) board={board_id}")
            self._close_reasons[board_id] = reason
            obs = self._observers.get(board_id)
            if obs:
                await obs.close_session(reason=reason)
                logger.info(f"[ObserverMgr] Observer closed for board {board_id} reason={reason}")
        finally:
            lock.release()
            logger.info(f"[ObserverMgr] lifecycle_lock released (close) board={board_id}")

    async def close_all(self):
        for board_id in list(self._observers.keys()):
            await self.close(board_id, reason="shutdown")


observer_manager = ObserverManager()
