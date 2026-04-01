"""
Telemetry Sync Client — v3.7.0

Sends heartbeats and telemetry events from local kiosk to Central Server.
Fail-open: network errors NEVER block local game operation.
Events are queued locally in SQLite and retried on next cycle.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("telemetry_sync")


def _utcnow():
    return datetime.now(timezone.utc)


class TelemetrySyncClient:
    def __init__(self):
        self._central_url = None
        self._api_key = None
        self._running = False
        self._pending_events = []  # In-memory queue
        self._version = "unknown"
        self._heartbeat_interval = 60  # seconds
        self._flush_interval = 300  # 5 minutes
        self._max_batch_size = 100
        self._heartbeat_task = None
        self._flush_task = None
        self._last_heartbeat_ok = None
        self._consecutive_heartbeat_failures = 0

    def configure(self, central_url: str, api_key: str, version: str = "unknown"):
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        self._version = version
        if self._central_url and self._api_key:
            logger.info(f"[TELEMETRY] Configured: {self._central_url} (v{self._version})")
        else:
            logger.info("[TELEMETRY] Not configured (no central URL or API key)")

    @property
    def is_configured(self):
        return bool(self._central_url and self._api_key)

    def queue_event(self, event_type: str, data: dict = None):
        """Queue a telemetry event for upload. Non-blocking, fail-safe."""
        try:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "timestamp": _utcnow().isoformat(),
                "data": data or {},
            }
            self._pending_events.append(event)
            # Cap queue size to prevent memory issues
            if len(self._pending_events) > 5000:
                self._pending_events = self._pending_events[-2500:]
                logger.warning("[TELEMETRY] Queue trimmed to 2500 events")
        except Exception as e:
            logger.error(f"[TELEMETRY] Queue error (non-fatal): {e}")

    async def start(self):
        """Start background heartbeat + flush loops. Non-blocking."""
        if not self.is_configured:
            logger.info("[TELEMETRY] Not starting (not configured)")
            return
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("[TELEMETRY] Background sync started")

    async def stop(self):
        self._running = False
        for task in (self._heartbeat_task, self._flush_task):
            if task:
                task.cancel()
        for task in (self._heartbeat_task, self._flush_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._heartbeat_task = None
        self._flush_task = None

    async def _heartbeat_loop(self):
        """Send heartbeat every 60s."""
        while self._running:
            try:
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[TELEMETRY] Heartbeat failed (non-fatal): {e}")
            await asyncio.sleep(self._heartbeat_interval)

    async def _flush_loop(self):
        """Flush pending events every 5 minutes."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
            except asyncio.CancelledError:
                break
            try:
                await self._flush_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[TELEMETRY] Flush failed (non-fatal): {e}")

    async def _send_heartbeat(self):
        """Send heartbeat with health snapshot + recent logs to central server."""
        if not self.is_configured:
            return
        try:
            payload = {
                "version": self._version,
                "timestamp": _utcnow().isoformat(),
            }
            # Append health snapshot (fail-safe)
            try:
                payload["health"] = self._collect_health_snapshot()
            except Exception:
                pass
            # Append recent logs (fail-safe, capped)
            try:
                from backend.services.device_log_buffer import device_logs
                payload["logs"] = device_logs.get_recent(30)
            except Exception:
                pass

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._central_url}/api/telemetry/heartbeat",
                    json=payload,
                    headers={"X-License-Key": self._api_key},
                )
                if resp.status_code == 200:
                    self._consecutive_heartbeat_failures = 0
                    if self._last_heartbeat_ok is not True:
                        logger.info("[TELEMETRY] Heartbeat OK")
                    else:
                        logger.debug("[TELEMETRY] Heartbeat OK")
                    self._last_heartbeat_ok = True
                    # v3.13.0: Clear suspended state if central accepts us again
                    try:
                        from backend.services.central_rejection_handler import handle_central_reactivation
                        await handle_central_reactivation("heartbeat")
                    except Exception:
                        pass
                    # v3.13.0: Process device_status from heartbeat response
                    try:
                        hb_data = resp.json()
                        if hb_data.get("device_status") and hb_data["device_status"] != "active":
                            from backend.services.central_rejection_handler import handle_central_rejection
                            await handle_central_rejection(
                                "heartbeat_status",
                                403,
                                f"device_status={hb_data['device_status']}"
                            )
                    except Exception:
                        pass
                    # v3.9.7: Notify offline queue that central is reachable
                    try:
                        from backend.services.offline_queue import offline_queue
                        offline_queue.notify_online()
                    except Exception:
                        pass
                elif resp.status_code == 403:
                    # v3.13.0: Device deactivated/blocked centrally
                    self._consecutive_heartbeat_failures += 1
                    self._last_heartbeat_ok = False
                    logger.warning(f"[TELEMETRY] Heartbeat REJECTED (403): {resp.text[:200]}")
                    try:
                        from backend.services.central_rejection_handler import handle_central_rejection
                        await handle_central_rejection("heartbeat", 403, resp.text[:200])
                    except Exception:
                        pass
                else:
                    self._consecutive_heartbeat_failures += 1
                    self._last_heartbeat_ok = False
                    logger.warning(f"[TELEMETRY] Heartbeat HTTP {resp.status_code}")
        except Exception as e:
            self._consecutive_heartbeat_failures += 1
            if self._last_heartbeat_ok is not False:
                logger.warning(f"[TELEMETRY] Heartbeat error: {e}")
            else:
                logger.debug(f"[TELEMETRY] Heartbeat error: {e}")
            self._last_heartbeat_ok = False

    @staticmethod
    def _collect_health_snapshot() -> dict:
        """Collect current device health for heartbeat. Never raises."""
        snapshot = {}
        try:
            from backend.services.config_sync_client import config_sync_client
            s = config_sync_client.status
            snapshot["config_sync"] = {
                "config_version": s.get("config_version", 0),
                "last_sync_at": s.get("last_sync_at"),
                "consecutive_errors": s.get("consecutive_errors", 0),
                "last_error": s.get("last_error"),
                "sync_count": s.get("sync_count", 0),
            }
        except Exception:
            snapshot["config_sync"] = None
        try:
            from backend.services.action_poller import action_poller
            a = action_poller.status
            snapshot["action_poller"] = {
                "last_poll_at": a.get("last_poll_at"),
                "last_action_at": a.get("last_action_at"),
                "actions_executed": a.get("actions_executed", 0),
                "actions_failed": a.get("actions_failed", 0),
                "consecutive_poll_errors": a.get("consecutive_poll_errors", 0),
                "last_error": a.get("last_error"),
            }
        except Exception:
            snapshot["action_poller"] = None
        try:
            from backend.services.config_apply import get_applied_version
            snapshot["config_applied_version"] = get_applied_version()
        except Exception:
            snapshot["config_applied_version"] = None
        # v3.9.7: Offline queue status
        try:
            from backend.services.offline_queue import offline_queue
            oq = offline_queue.status
            snapshot["offline_queue"] = {
                "pending": oq.get("pending", 0),
                "drained_total": oq.get("drained_total", 0),
                "dropped_total": oq.get("dropped_total", 0),
                "drain_errors": oq.get("drain_errors", 0),
                "last_drain_at": oq.get("last_drain_at"),
                "last_drain_error": oq.get("last_drain_error"),
            }
        except Exception:
            snapshot["offline_queue"] = None
        try:
            # Determine health status
            ce = snapshot.get("config_sync", {}) or {}
            ae = snapshot.get("action_poller", {}) or {}
            oq = snapshot.get("offline_queue", {}) or {}
            if ce.get("consecutive_errors", 0) >= 3 or ae.get("consecutive_poll_errors", 0) >= 5:
                snapshot["health_status"] = "degraded"
            elif oq.get("pending", 0) > 0:
                snapshot["health_status"] = "degraded"
            else:
                snapshot["health_status"] = "healthy"
        except Exception:
            snapshot["health_status"] = "unknown"
        return snapshot

    async def _flush_events(self):
        """Send pending events in batches."""
        if not self.is_configured or not self._pending_events:
            return

        # Take a batch from the front
        batch = self._pending_events[:self._max_batch_size]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._central_url}/api/telemetry/ingest",
                    json={"events": batch},
                    headers={"X-License-Key": self._api_key},
                )
                if resp.status_code == 200:
                    result = resp.json()
                    accepted = result.get("accepted", 0)
                    dupes = result.get("duplicates", 0)
                    # Remove successfully sent events from queue
                    self._pending_events = self._pending_events[len(batch):]
                    if accepted > 0:
                        logger.info(f"[TELEMETRY] Flushed {accepted} events ({dupes} dupes)")
                else:
                    logger.warning(f"[TELEMETRY] Ingest returned {resp.status_code} — will retry")
                    self._enqueue_batch_to_offline(batch)
        except Exception as e:
            logger.debug(f"[TELEMETRY] Ingest error (will retry): {e}")
            self._enqueue_batch_to_offline(batch)

    def _enqueue_batch_to_offline(self, batch):
        """v3.9.7: Persist failed telemetry events to offline queue."""
        try:
            from backend.services.offline_queue import offline_queue
            for event in batch:
                eid = event.get("event_id", "")
                offline_queue.enqueue(
                    msg_type="telemetry_event",
                    method="POST",
                    url_path="/api/telemetry/ingest",
                    payload={"events": [event]},
                    idempotency_key=f"telem_{eid}",
                )
            # Remove from in-memory queue (now persisted on disk)
            self._pending_events = self._pending_events[len(batch):]
        except Exception as qe:
            logger.warning(f"[TELEMETRY] Offline queue enqueue failed (non-fatal): {qe}")

    async def force_flush(self):
        """Manually trigger a flush (e.g., on shutdown)."""
        await self._flush_events()


# Singleton
telemetry_sync = TelemetrySyncClient()
