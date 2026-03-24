"""
Action Poller Service — v3.9.2 (Hardened)

Polls the Central Server for pending remote actions and executes them locally.

Hardening:
- Persistent executed-action history (survives restarts)
- Status transitions: pending → processing → done/failed (no double-execution)
- Ack retry with exponential backoff (max 3 attempts)
- Per-action execution timeout
- asyncio.Lock to prevent concurrent poll cycles
- Fail-open: central unreachable → local operation unaffected
- Consecutive error tracking for health reporting
"""
import asyncio
import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("action_poller")

try:
    from backend.services.device_log_buffer import device_logs
except ImportError:
    from services.device_log_buffer import device_logs

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_HISTORY_FILE = _DATA_DIR / "action_history.json"

_MAX_HISTORY = 200
_POLL_INTERVAL = 30
_ACTION_TIMEOUT = 30  # seconds per action execution
_ACK_MAX_RETRIES = 3
_ACK_BACKOFF_BASE = 2  # seconds, doubles each retry


def _utcnow():
    return datetime.now(timezone.utc)


class ActionPoller:
    def __init__(self):
        self._central_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._device_id: Optional[str] = None
        self._running = False
        self._poll_lock = asyncio.Lock()
        # OrderedDict: action_id → {"status": "done"/"failed", "at": iso, "type": str}
        self._history: OrderedDict = OrderedDict()
        self._processing: set = set()  # action_ids currently being executed
        self._last_poll_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_action_at: Optional[datetime] = None
        self._poll_count = 0
        self._actions_executed = 0
        self._actions_failed = 0
        self._consecutive_errors = 0

    # ── Configuration ──

    def configure(self, central_url: str, api_key: str, device_id: str):
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        self._device_id = device_id
        self._load_history()
        if self.is_configured:
            logger.info(f"[ACTION-POLL] Configured: url={self._central_url} device={self._device_id} history={len(self._history)}")
        else:
            logger.info("[ACTION-POLL] Not configured (missing URL or device_id)")

    @property
    def is_configured(self):
        return bool(self._central_url and self._api_key and self._device_id)

    @property
    def status(self) -> dict:
        return {
            "configured": self.is_configured,
            "running": self._running,
            "last_poll_at": self._last_poll_at.isoformat() if self._last_poll_at else None,
            "last_action_at": self._last_action_at.isoformat() if self._last_action_at else None,
            "poll_count": self._poll_count,
            "actions_executed": self._actions_executed,
            "actions_failed": self._actions_failed,
            "consecutive_poll_errors": self._consecutive_errors,
            "last_error": self._last_error,
            "processing_count": len(self._processing),
            "history_size": len(self._history),
        }

    # ── Persistence ──

    def _load_history(self):
        """Load executed action IDs from disk. Fail-safe: if corrupt, start fresh."""
        try:
            if _HISTORY_FILE.exists():
                raw = json.loads(_HISTORY_FILE.read_text())
                if isinstance(raw, dict):
                    self._history = OrderedDict(raw)
                elif isinstance(raw, list):
                    # Legacy: list of IDs
                    self._history = OrderedDict((aid, {"status": "done", "at": None, "type": "unknown"}) for aid in raw)
                self._trim_history()
                logger.info(f"[ACTION-POLL] Loaded {len(self._history)} history entries from disk")
        except Exception as e:
            logger.warning(f"[ACTION-POLL] Failed to load history (starting fresh): {e}")
            self._history = OrderedDict()

    def _save_history(self):
        """Persist history to disk. Fail-safe: write errors are logged, not raised."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            _HISTORY_FILE.write_text(json.dumps(dict(self._history), indent=2))
        except Exception as e:
            logger.warning(f"[ACTION-POLL] Failed to save history: {e}")

    def _trim_history(self):
        """Keep history within size limit. Removes oldest entries."""
        while len(self._history) > _MAX_HISTORY:
            self._history.popitem(last=False)

    # ── Lifecycle ──

    async def start(self):
        if self._running or not self.is_configured:
            if not self.is_configured:
                logger.info("[ACTION-POLL] Skipping start — not configured")
            return
        self._running = True
        logger.info(f"[ACTION-POLL] Started (interval={_POLL_INTERVAL}s)")

        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                self._consecutive_errors += 1
                self._last_error = str(e)
                logger.warning(f"[ACTION-POLL] Unexpected poll error #{self._consecutive_errors}: {e}")
            await asyncio.sleep(_POLL_INTERVAL)

    def stop(self):
        self._running = False
        logger.info("[ACTION-POLL] Stopped")

    async def trigger_poll(self):
        """Trigger an immediate poll cycle (called by WS push). Lock-protected against concurrent runs."""
        if not self.is_configured:
            return
        logger.info("[ACTION-POLL] Immediate poll triggered via WS push")
        try:
            await self._poll_once()
        except Exception as e:
            logger.warning(f"[ACTION-POLL] Triggered poll error: {e}")

    # ── Core Poll ──

    async def _poll_once(self):
        """Fetch and execute pending actions. Protected by lock against concurrent runs."""
        if self._poll_lock.locked():
            logger.debug("[ACTION-POLL] Poll skipped — previous cycle still running")
            return

        async with self._poll_lock:
            self._poll_count += 1
            self._last_poll_at = _utcnow()

            # Fetch pending actions
            actions = await self._fetch_pending()
            if actions is None:
                return  # fetch failed, error already logged

            self._consecutive_errors = 0
            self._last_error = None

            # v3.9.7: Notify offline queue that central is reachable
            try:
                from backend.services.offline_queue import offline_queue
                offline_queue.notify_online()
            except Exception:
                pass

            if not actions:
                return

            logger.info(f"[ACTION-POLL] Received {len(actions)} pending action(s)")

            for action in actions:
                if not self._running:
                    break
                await self._handle_action(action)

    async def _fetch_pending(self) -> Optional[list]:
        """Fetch pending actions from central. Returns None on failure."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._central_url}/api/remote-actions/{self._device_id}/pending",
                    headers={"X-License-Key": self._api_key},
                )
                if resp.status_code == 403:
                    # v3.13.0: Device deactivated/blocked centrally
                    self._consecutive_errors += 1
                    self._last_error = "403: Device rejected"
                    logger.warning(f"[ACTION-POLL] REJECTED by central (403): {resp.text[:200]}")
                    try:
                        from backend.services.central_rejection_handler import handle_central_rejection
                        import asyncio
                        await handle_central_rejection("action_poller", 403, resp.text[:200])
                    except Exception:
                        pass
                    return None
                if resp.status_code != 200:
                    self._consecutive_errors += 1
                    self._last_error = f"HTTP {resp.status_code}"
                    if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                        logger.warning(f"[ACTION-POLL] Fetch returned HTTP {resp.status_code} (errors={self._consecutive_errors})")
                    return None
                # v3.13.0: Success — clear any suspended state
                try:
                    from backend.services.central_rejection_handler import handle_central_reactivation
                    await handle_central_reactivation("action_poller")
                except Exception:
                    pass
                return resp.json()
        except httpx.TimeoutException:
            self._consecutive_errors += 1
            self._last_error = "timeout"
            if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                logger.warning(f"[ACTION-POLL] Fetch timeout (errors={self._consecutive_errors})")
            return None
        except Exception as e:
            self._consecutive_errors += 1
            self._last_error = str(e)
            if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                logger.warning(f"[ACTION-POLL] Fetch error: {e} (errors={self._consecutive_errors})")
            return None

    # ── Action Handling ──

    async def _handle_action(self, action: dict):
        """Handle a single action with full lifecycle: check → process → execute → ack."""
        action_id = action.get("id")
        action_type = action.get("action_type")
        action_params = action.get("params")

        if not action_id or not action_type:
            logger.warning(f"[ACTION-POLL] Skipping malformed action: {action}")
            return

        # Idempotency: already executed?
        if action_id in self._history:
            prev = self._history[action_id]
            logger.debug(f"[ACTION-POLL] Action {action_id} already {prev['status']} — re-acking")
            await self._ack_with_retry(action_id, success=(prev["status"] == "done"),
                                       message=f"Already {prev['status']} (idempotent)")
            return

        # Already processing? (guard against concurrent)
        if action_id in self._processing:
            logger.debug(f"[ACTION-POLL] Action {action_id} already processing — skipping")
            return

        # Mark as processing
        self._processing.add(action_id)
        logger.info(f"[ACTION-POLL] Processing action: type={action_type} id={action_id}")

        try:
            # Execute with timeout
            success, message = await asyncio.wait_for(
                self._execute_action(action_type, action_params),
                timeout=_ACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            success = False
            message = f"Action timed out after {_ACTION_TIMEOUT}s"
            logger.error(f"[ACTION-POLL] Action {action_id} ({action_type}) timed out")
        except Exception as e:
            success = False
            message = str(e)
            logger.error(f"[ACTION-POLL] Action {action_id} ({action_type}) exception: {e}")

        # Record result
        status = "done" if success else "failed"
        self._history[action_id] = {
            "status": status,
            "type": action_type,
            "at": _utcnow().isoformat(),
        }
        self._trim_history()
        self._save_history()
        self._processing.discard(action_id)
        self._last_action_at = _utcnow()

        if success:
            self._actions_executed += 1
            logger.info(f"[ACTION-POLL] Action DONE: type={action_type} id={action_id} msg={message}")
            device_logs.info("action_poller", "action_done", f"{action_type}: {message}", {"action_id": action_id, "type": action_type})
        else:
            self._actions_failed += 1
            logger.warning(f"[ACTION-POLL] Action FAILED: type={action_type} id={action_id} msg={message}")
            device_logs.error("action_poller", "action_failed", f"{action_type}: {message}", {"action_id": action_id, "type": action_type})

        # Acknowledge with retry
        await self._ack_with_retry(action_id, success=success, message=message)

    async def _execute_action(self, action_type: str, params: dict = None) -> tuple:
        """Execute a single action. Returns (success, message)."""
        if action_type == "force_sync":
            return await self._do_force_sync()
        elif action_type == "restart_backend":
            return await self._do_restart_backend()
        elif action_type == "reload_ui":
            return await self._do_reload_ui()
        elif action_type in ("unlock_board", "lock_board", "start_session", "stop_session"):
            return await self._do_board_control(action_type, params or {})
        else:
            return False, f"Unknown action_type: {action_type}"

    async def _do_force_sync(self) -> tuple:
        try:
            try:
                from backend.services.config_sync_client import config_sync_client
            except ImportError:
                from services.config_sync_client import config_sync_client
            changed = await config_sync_client.sync_now()
            msg = "Config synced" + (" (changes applied)" if changed else " (no changes)")
            return True, msg
        except Exception as e:
            return False, f"force_sync error: {e}"

    async def _do_restart_backend(self) -> tuple:
        logger.info("[ACTION-POLL] restart_backend requested")
        return True, "Restart signal acknowledged. Requires external process manager."

    async def _do_reload_ui(self) -> tuple:
        try:
            try:
                import backend.services.config_apply as ca
            except ImportError:
                import services.config_apply as ca
            ca._config_applied_version += 1
            return True, f"UI reload signaled (version={ca._config_applied_version})"
        except Exception as e:
            return False, f"reload_ui error: {e}"

    async def _do_board_control(self, action_type: str, params: dict) -> tuple:
        """Execute board control actions locally using the DB directly."""
        logger.info(f"[ACTION-POLL] Board control: {action_type} params={params}")

        try:
            # v3.15.2: Import fix — backend.database (NOT backend.database.database)
            try:
                from backend.database import AsyncSessionLocal
            except ImportError:
                from database import AsyncSessionLocal
            try:
                from backend.models import Board, Session, BoardStatus, SessionStatus, PricingMode
            except ImportError:
                from models import Board, Session, BoardStatus, SessionStatus, PricingMode
            try:
                from backend.dependencies import get_or_create_setting
            except ImportError:
                from dependencies import get_or_create_setting
            from sqlalchemy import select
            from datetime import timedelta

            async with AsyncSessionLocal() as db:
                # Resolve board_id: from params, or discover first board
                target_board_id = params.get("board_id") if params else None
                if target_board_id:
                    result = await db.execute(select(Board).where(Board.board_id == target_board_id))
                    board = result.scalar_one_or_none()
                else:
                    # Auto-discover: pick first board in the local DB
                    result = await db.execute(select(Board).order_by(Board.created_at))
                    board = result.scalars().first()

                if not board:
                    return False, f"No board found (target_board_id={target_board_id})"

                board_id = board.board_id
                logger.info(f"[ACTION-POLL] Resolved board: {board_id} (db_id={board.id})")

                if action_type in ("unlock_board", "start_session"):
                    return await self._do_unlock(db, board, params)
                elif action_type in ("lock_board", "stop_session"):
                    return await self._do_lock(db, board)
                else:
                    return False, f"Unhandled board action: {action_type}"

        except Exception as e:
            logger.error(f"[ACTION-POLL] Board control error: {e}", exc_info=True)
            return False, f"Board control error: {e}"

    async def _do_unlock(self, db, board, params: dict) -> tuple:
        """Unlock a board and create a session."""
        try:
            from backend.models import Session, BoardStatus, SessionStatus, PricingMode
        except ImportError:
            from models import Session, BoardStatus, SessionStatus, PricingMode
        try:
            from backend.dependencies import get_or_create_setting
        except ImportError:
            from dependencies import get_or_create_setting
        try:
            from backend.services.ws_manager import board_ws
        except ImportError:
            from services.ws_manager import board_ws
        from datetime import timedelta

        # Check for existing active session
        from sqlalchemy import select
        existing = await db.execute(
            select(Session).where(
                Session.board_id == board.id,
                Session.status == SessionStatus.ACTIVE.value
            )
        )
        if existing.scalar_one_or_none():
            return False, f"Board {board.board_id} already has an active session"

        # v3.15.2: License check — FAIL-CLOSED. If check fails → BLOCK.
        try:
            try:
                from backend.services.license_service import license_service
            except ImportError:
                from services.license_service import license_service
            try:
                from backend.services.device_identity_service import device_identity_service
            except ImportError:
                from services.device_identity_service import device_identity_service
            _install_id = device_identity_service.get_install_id()
            lic_status = await license_service.get_effective_status(
                db, install_id=_install_id, board_id=board.board_id, trigger_binding=False
            )
            if not license_service.is_session_allowed(lic_status):
                return False, f"License blocked: {lic_status.get('status')} / {lic_status.get('binding_status')}"
        except Exception as e:
            # v3.15.2: FAIL-CLOSED — license check error = BLOCK
            logger.error(f"[ACTION-POLL] License check failed — BLOCKING unlock: {e}")
            return False, f"License check failed (fail-closed): {e}"

        # Resolve pricing from params or local defaults
        pricing_mode = (params.get("pricing_mode") or PricingMode.PER_GAME.value) if params else PricingMode.PER_GAME.value
        game_type = (params.get("game_type") or "501") if params else "501"
        credits = (params.get("credits") or 3) if params else 3
        minutes = (params.get("minutes") or 0) if params else 0
        price_total = (params.get("price_total") or 0) if params else 0
        players_count = (params.get("players_count") or 2) if params else 2

        # Try to read defaults from local settings
        try:
            defaults = await get_or_create_setting(db, "pricing", {})
            if not params or not params.get("pricing_mode"):
                pricing_mode = defaults.get("mode", pricing_mode)
                if pricing_mode == PricingMode.PER_GAME.value:
                    credits = defaults.get("per_game", {}).get("credits", credits)
                    price_total = defaults.get("per_game", {}).get("price", price_total)
                elif pricing_mode == PricingMode.PER_TIME.value:
                    minutes = defaults.get("per_time", {}).get("minutes", minutes)
                    price_total = defaults.get("per_time", {}).get("price", price_total)
        except Exception:
            pass

        expires_at = None
        if pricing_mode == PricingMode.PER_TIME.value and minutes:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

        session = Session(
            board_id=board.id,
            pricing_mode=pricing_mode,
            game_type=game_type,
            credits_total=credits,
            credits_remaining=credits,
            minutes_total=minutes,
            price_total=price_total,
            players_count=players_count,
            expires_at=expires_at,
            status=SessionStatus.ACTIVE.value,
        )
        db.add(session)
        board.status = BoardStatus.UNLOCKED.value
        await db.commit()

        # WebSocket broadcast
        try:
            await board_ws.broadcast("board_status", {"board_id": board.board_id, "status": "unlocked"})
        except Exception:
            pass

        logger.info(f"[ACTION-POLL] Board {board.board_id} unlocked: mode={pricing_mode} credits={credits}")
        return True, f"Board {board.board_id} unlocked (mode={pricing_mode}, credits={credits}, minutes={minutes})"

    async def _do_lock(self, db, board) -> tuple:
        """Lock a board and end any active session."""
        try:
            from backend.models import Session, BoardStatus, SessionStatus
        except ImportError:
            from models import Session, BoardStatus, SessionStatus
        try:
            from backend.services.ws_manager import board_ws
        except ImportError:
            from services.ws_manager import board_ws
        from sqlalchemy import select

        # End active session if exists
        result = await db.execute(
            select(Session).where(
                Session.board_id == board.id,
                Session.status == SessionStatus.ACTIVE.value
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.status = SessionStatus.CANCELLED.value
            session.ended_at = datetime.now(timezone.utc)
            session.ended_reason = "remote_lock"

        board.status = BoardStatus.LOCKED.value
        await db.commit()

        # WebSocket broadcast
        try:
            await board_ws.broadcast("board_status", {"board_id": board.board_id, "status": "locked"})
        except Exception:
            pass

        # Stop Autodarts observer
        try:
            try:
                from backend.routers.boards import observer_manager, stop_observer_for_board
            except ImportError:
                from routers.boards import observer_manager, stop_observer_for_board
            import asyncio
            observer_manager.set_desired_state(board.board_id, "stopped")
            asyncio.create_task(stop_observer_for_board(board.board_id, reason="remote_lock"))
        except Exception:
            pass

        logger.info(f"[ACTION-POLL] Board {board.board_id} locked")
        return True, f"Board {board.board_id} locked"

    # ── Ack with Retry ──

    async def _ack_with_retry(self, action_id: str, success: bool, message: str):
        """Acknowledge action with exponential backoff retry."""
        for attempt in range(_ACK_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{self._central_url}/api/remote-actions/{self._device_id}/ack",
                        headers={"X-License-Key": self._api_key},
                        json={"action_id": action_id, "success": success, "message": message},
                    )
                    if resp.status_code == 200:
                        if attempt > 0:
                            logger.info(f"[ACTION-POLL] Ack succeeded on retry {attempt+1} for {action_id}")
                        else:
                            logger.info(f"[ACTION-POLL] Acked {action_id}: success={success}")
                        return
                    # Non-200 but not a network error — don't retry 4xx
                    if 400 <= resp.status_code < 500:
                        logger.warning(f"[ACTION-POLL] Ack rejected HTTP {resp.status_code} for {action_id} — not retrying")
                        return
                    logger.warning(f"[ACTION-POLL] Ack HTTP {resp.status_code} for {action_id} (attempt {attempt+1})")
            except Exception as e:
                logger.warning(f"[ACTION-POLL] Ack error for {action_id} (attempt {attempt+1}): {e}")

            if attempt < _ACK_MAX_RETRIES - 1:
                backoff = _ACK_BACKOFF_BASE * (2 ** attempt)
                logger.info(f"[ACTION-POLL] Ack retry in {backoff}s for {action_id}")
                await asyncio.sleep(backoff)

        logger.error(f"[ACTION-POLL] Ack FAILED after {_ACK_MAX_RETRIES} attempts for {action_id}")

        # v3.9.7: Enqueue to offline queue for later retry
        try:
            from backend.services.offline_queue import offline_queue
            offline_queue.enqueue(
                msg_type="action_ack",
                method="POST",
                url_path=f"/api/remote-actions/{self._device_id}/ack",
                payload={"action_id": action_id, "success": success, "message": message},
                idempotency_key=f"ack_{action_id}",
            )
        except Exception as qe:
            logger.warning(f"[ACTION-POLL] Offline queue enqueue failed (non-fatal): {qe}")


# Singleton
action_poller = ActionPoller()
