"""
Action Poller Service — v3.9.1

Polls the Central Server for pending remote actions (force_sync, restart_backend, reload_ui)
and executes them locally. Fail-open: if central is unreachable, nothing breaks.

Design:
- Polls every 30s for pending actions
- Acknowledges each action after execution
- Idempotent: tracks executed action IDs to prevent double-execution
- Never raises — all errors are caught and logged
- Graceful shutdown via stop()
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("action_poller")


def _utcnow():
    return datetime.now(timezone.utc)


class ActionPoller:
    def __init__(self):
        self._central_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._device_id: Optional[str] = None
        self._running = False
        self._poll_interval = 30  # seconds
        self._executed_ids: set = set()  # prevent double-execution
        self._max_history = 500  # cap memory for executed IDs
        self._last_poll_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._poll_count = 0

    def configure(self, central_url: str, api_key: str, device_id: str):
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        self._device_id = device_id
        if self._central_url and self._device_id:
            logger.info(f"[ACTION-POLL] Configured: {self._central_url} device={self._device_id}")
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
            "poll_count": self._poll_count,
            "last_error": self._last_error,
        }

    async def start(self):
        """Start the polling loop. Fail-open: errors are logged, never raised."""
        if self._running or not self.is_configured:
            if not self.is_configured:
                logger.info("[ACTION-POLL] Skipping start — not configured")
            return
        self._running = True
        logger.info(f"[ACTION-POLL] Started (interval={self._poll_interval}s)")

        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                self._last_error = str(e)
                logger.warning(f"[ACTION-POLL] Poll error (non-critical): {e}")
            await asyncio.sleep(self._poll_interval)

    def stop(self):
        self._running = False
        logger.info("[ACTION-POLL] Stopped")

    async def _poll_once(self):
        """Fetch pending actions and execute them."""
        self._poll_count += 1
        self._last_poll_at = _utcnow()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._central_url}/api/remote-actions/{self._device_id}/pending",
                    headers={"X-License-Key": self._api_key},
                )
                if resp.status_code != 200:
                    self._last_error = f"HTTP {resp.status_code}"
                    return
                actions = resp.json()
        except Exception as e:
            self._last_error = str(e)
            logger.debug(f"[ACTION-POLL] Fetch failed: {e}")
            return

        self._last_error = None

        if not actions:
            return

        logger.info(f"[ACTION-POLL] Received {len(actions)} pending action(s)")

        for action in actions:
            action_id = action.get("id")
            action_type = action.get("action_type")

            if not action_id or not action_type:
                continue

            # Idempotency: skip already executed
            if action_id in self._executed_ids:
                logger.debug(f"[ACTION-POLL] Skipping already executed: {action_id}")
                await self._ack_action(action_id, success=True, message="Already executed (idempotent)")
                continue

            logger.info(f"[ACTION-POLL] Executing action: {action_type} (id={action_id})")

            success, message = await self._execute_action(action_type)

            # Track execution
            self._executed_ids.add(action_id)
            if len(self._executed_ids) > self._max_history:
                # Trim oldest entries (set doesn't preserve order, but that's fine for idempotency)
                self._executed_ids = set(list(self._executed_ids)[-self._max_history:])

            # Acknowledge
            await self._ack_action(action_id, success=success, message=message)

    async def _execute_action(self, action_type: str) -> tuple:
        """Execute a single action. Returns (success: bool, message: str)."""
        try:
            if action_type == "force_sync":
                return await self._do_force_sync()
            elif action_type == "restart_backend":
                return await self._do_restart_backend()
            elif action_type == "reload_ui":
                return await self._do_reload_ui()
            else:
                logger.warning(f"[ACTION-POLL] Unknown action_type: {action_type}")
                return False, f"Unknown action_type: {action_type}"
        except Exception as e:
            logger.error(f"[ACTION-POLL] Action '{action_type}' failed: {e}")
            return False, str(e)

    async def _do_force_sync(self) -> tuple:
        """Trigger an immediate config sync."""
        try:
            from backend.services.config_sync_client import config_sync_client
            changed = await config_sync_client.sync_now()
            msg = "Config synced" + (" (changes applied)" if changed else " (no changes)")
            logger.info(f"[ACTION-POLL] force_sync: {msg}")
            return True, msg
        except Exception as e:
            logger.error(f"[ACTION-POLL] force_sync failed: {e}")
            return False, str(e)

    async def _do_restart_backend(self) -> tuple:
        """Signal a backend restart. In practice, we log and let the watchdog handle it."""
        logger.info("[ACTION-POLL] restart_backend requested — signaling for restart")
        # We can't restart ourselves mid-request. Signal it for external handling.
        return True, "Restart signal acknowledged. Requires external process manager."

    async def _do_reload_ui(self) -> tuple:
        """Bump the config version to trigger frontend re-fetch."""
        try:
            from backend.services.config_apply import _config_applied_version
            import backend.services.config_apply as ca
            ca._config_applied_version += 1
            logger.info(f"[ACTION-POLL] reload_ui: version bumped to {ca._config_applied_version}")
            return True, f"UI reload signaled (config version={ca._config_applied_version})"
        except Exception as e:
            logger.error(f"[ACTION-POLL] reload_ui failed: {e}")
            return False, str(e)

    async def _ack_action(self, action_id: str, success: bool, message: str):
        """Acknowledge action completion to central server."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._central_url}/api/remote-actions/{self._device_id}/ack",
                    headers={"X-License-Key": self._api_key},
                    json={"action_id": action_id, "success": success, "message": message},
                )
                if resp.status_code == 200:
                    logger.info(f"[ACTION-POLL] Acked action {action_id}: success={success}")
                else:
                    logger.warning(f"[ACTION-POLL] Ack failed HTTP {resp.status_code} for {action_id}")
        except Exception as e:
            logger.warning(f"[ACTION-POLL] Ack failed for {action_id}: {e}")


# Singleton
action_poller = ActionPoller()
