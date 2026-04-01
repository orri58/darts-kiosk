"""
Layer A: Central Heartbeat Client

Sends periodic heartbeat to the central server.
Completely non-blocking. Fails silently if central is unreachable.
Device continues normal operation regardless of central server status.
"""
import asyncio
from dataclasses import asdict, is_dataclass
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
        self._last_result_ok = None

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
            status = health_monitor.get_health()
            if is_dataclass(status):
                status = asdict(status)
            observer = status.get("observer_metrics") or {}
            agent_status = status.get("agent_status") or {}
            return {
                "status": status.get("status"),
                "uptime_seconds": status.get("uptime_seconds"),
                "scheduler_running": status.get("scheduler_running"),
                "backup_service_running": status.get("backup_service_running"),
                "observer_total_events": observer.get("total_events", 0),
                "observer_success_rate": observer.get("success_rate", 0),
                "agents_total": len(agent_status),
                "agents_online": sum(1 for item in agent_status.values() if item.get("is_online")),
            }
        except Exception:
            return {}

    async def start(self):
        if self._running:
            return
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
                if self._last_result_ok is not True:
                    logger.info(f"[HEARTBEAT] OK -> device_status={result.get('device_status', '?')}")
                else:
                    logger.debug(f"[HEARTBEAT] OK -> device_status={result.get('device_status', '?')}")
                self._last_result_ok = True
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_failures += 1
                self._current_interval = min(
                    self._base_interval * (2 ** min(self._consecutive_failures, 5)),
                    self._max_interval,
                )
                if self._last_result_ok is not False or self._consecutive_failures <= 3 or self._consecutive_failures % 5 == 0:
                    logger.warning(
                        f"[HEARTBEAT] Failed ({self._consecutive_failures}x): {type(e).__name__}: {e} "
                        f"-> retry in {self._current_interval}s"
                    )
                self._last_result_ok = False
            await asyncio.sleep(self._current_interval)


heartbeat_client = CentralHeartbeatClient()
