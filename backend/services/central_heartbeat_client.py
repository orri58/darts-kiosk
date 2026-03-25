"""
Layer A: Central Heartbeat Client

Sends periodic heartbeat to the central server.
Completely non-blocking. Fails silently if central is unreachable.
Device continues normal operation regardless of central server status.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger("central_heartbeat")


class CentralHeartbeatClient:
    def __init__(self):
        self._task = None
        self._running = False
        self._base_interval = 60
        self._max_interval = 300
        self._current_interval = self._base_interval
        self._consecutive_failures = 0

    @property
    def central_url(self):
        return os.environ.get("CENTRAL_SERVER_URL", "").rstrip("/")

    @property
    def api_key(self):
        return os.environ.get("CENTRAL_API_KEY", "")

    @property
    def enabled(self):
        return bool(self.central_url and self.api_key)

    def _get_version(self):
        try:
            vf = Path(__file__).resolve().parent.parent.parent / "VERSION"
            return vf.read_text().strip()
        except Exception:
            return "unknown"

    def _get_health(self):
        try:
            from backend.services.health_monitor import health_monitor
            status = health_monitor.get_status()
            return {
                "scheduler": status.get("scheduler_running"),
                "backup": status.get("backup_running"),
                "boards_total": status.get("boards_total", 0),
                "boards_active": status.get("boards_active", 0),
            }
        except Exception:
            return {}

    async def start(self):
        if not self.enabled:
            logger.info("[HEARTBEAT] Disabled — CENTRAL_SERVER_URL or CENTRAL_API_KEY not set")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[HEARTBEAT] Started -> {self.central_url} (interval={self._base_interval}s)")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[HEARTBEAT] Stopped")

    async def _send_heartbeat(self):
        url = f"{self.central_url}/api/telemetry/heartbeat"
        payload = {
            "version": self._get_version(),
            "health": self._get_health(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        headers = {"X-License-Key": self.api_key}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def _loop(self):
        await asyncio.sleep(5)  # let app fully start
        while self._running:
            try:
                result = await self._send_heartbeat()
                self._consecutive_failures = 0
                self._current_interval = self._base_interval
                logger.info(f"[HEARTBEAT] OK -> device_status={result.get('device_status', '?')}")
            except Exception as e:
                self._consecutive_failures += 1
                self._current_interval = min(
                    self._base_interval * (2 ** min(self._consecutive_failures, 5)),
                    self._max_interval,
                )
                logger.warning(
                    f"[HEARTBEAT] Failed ({self._consecutive_failures}x): {type(e).__name__}: {e} "
                    f"-> retry in {self._current_interval}s"
                )
            await asyncio.sleep(self._current_interval)


heartbeat_client = CentralHeartbeatClient()
