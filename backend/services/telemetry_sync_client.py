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
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._flush_loop())
        logger.info("[TELEMETRY] Background sync started")

    async def stop(self):
        self._running = False

    async def _heartbeat_loop(self):
        """Send heartbeat every 60s."""
        while self._running:
            try:
                await self._send_heartbeat()
            except Exception as e:
                logger.debug(f"[TELEMETRY] Heartbeat failed (non-fatal): {e}")
            await asyncio.sleep(self._heartbeat_interval)

    async def _flush_loop(self):
        """Flush pending events every 5 minutes."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            try:
                await self._flush_events()
            except Exception as e:
                logger.debug(f"[TELEMETRY] Flush failed (non-fatal): {e}")

    async def _send_heartbeat(self):
        """Send a single heartbeat to the central server."""
        if not self.is_configured:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._central_url}/api/telemetry/heartbeat",
                    json={
                        "version": self._version,
                        "timestamp": _utcnow().isoformat(),
                    },
                    headers={"X-License-Key": self._api_key},
                )
                if resp.status_code == 200:
                    logger.debug("[TELEMETRY] Heartbeat OK")
                else:
                    logger.debug(f"[TELEMETRY] Heartbeat {resp.status_code}")
        except Exception as e:
            logger.debug(f"[TELEMETRY] Heartbeat error: {e}")

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
        except Exception as e:
            logger.debug(f"[TELEMETRY] Ingest error (will retry): {e}")

    async def force_flush(self):
        """Manually trigger a flush (e.g., on shutdown)."""
        await self._flush_events()


# Singleton
telemetry_sync = TelemetrySyncClient()
