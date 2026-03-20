"""
Config Sync Client — v3.8.0

Pulls effective configuration from the Central Server at startup and periodically.
The local kiosk uses this as its source of truth for pricing, branding, and kiosk behavior.
Fail-open: if the central server is unreachable, the last known config is used.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger("config_sync")


def _utcnow():
    return datetime.now(timezone.utc)


# Resolve data dir for caching
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_CACHE_FILE = _DATA_DIR / "config_cache.json"


class ConfigSyncClient:
    def __init__(self):
        self._central_url = None
        self._api_key = None
        self._device_id = None
        self._running = False
        self._sync_interval = 300  # 5 minutes
        self._current_config = {}
        self._config_version = 0
        self._last_sync_at = None
        self._last_error = None
        self._callbacks = []  # list of async callables invoked on config change

    def configure(self, central_url: str, api_key: str, device_id: str = None):
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        self._device_id = device_id
        if self._central_url:
            logger.info(f"[CONFIG-SYNC] Configured: {self._central_url} device={self._device_id}")
        else:
            logger.info("[CONFIG-SYNC] Not configured (no central URL)")
        # Load cached config on startup
        self._load_cache()

    @property
    def is_configured(self):
        return bool(self._central_url and self._api_key)

    @property
    def config(self) -> dict:
        return self._current_config

    @property
    def version(self) -> int:
        return self._config_version

    @property
    def status(self) -> dict:
        return {
            "configured": self.is_configured,
            "last_sync_at": self._last_sync_at.isoformat() if self._last_sync_at else None,
            "config_version": self._config_version,
            "last_error": self._last_error,
            "running": self._running,
        }

    def on_config_change(self, callback):
        """Register an async callback for config changes."""
        self._callbacks.append(callback)

    def _load_cache(self):
        """Load last-known config from disk cache."""
        try:
            if _CACHE_FILE.exists():
                data = json.loads(_CACHE_FILE.read_text())
                self._current_config = data.get("config", {})
                self._config_version = data.get("version", 0)
                logger.info(f"[CONFIG-SYNC] Loaded cached config v{self._config_version}")
        except Exception as e:
            logger.warning(f"[CONFIG-SYNC] Failed to load cache: {e}")

    def _save_cache(self):
        """Save current config to disk for offline fallback."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(json.dumps({
                "config": self._current_config,
                "version": self._config_version,
                "synced_at": _utcnow().isoformat(),
            }, indent=2))
        except Exception as e:
            logger.warning(f"[CONFIG-SYNC] Failed to save cache: {e}")

    async def sync_now(self) -> bool:
        """Pull effective config from central server. Returns True if config changed."""
        if not self.is_configured:
            return False
        try:
            params = {}
            if self._device_id:
                params["device_id"] = self._device_id
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self._central_url}/api/config/effective",
                    params=params,
                    headers={"X-License-Key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            new_config = data.get("config", {})
            new_version = data.get("version", 0)

            changed = new_version != self._config_version or new_config != self._current_config
            self._current_config = new_config
            self._config_version = new_version
            self._last_sync_at = _utcnow()
            self._last_error = None
            self._save_cache()

            if changed:
                logger.info(f"[CONFIG-SYNC] Config updated to v{new_version}, layers: {data.get('layers_applied', [])}")
                for cb in self._callbacks:
                    try:
                        await cb(new_config)
                    except Exception as e:
                        logger.error(f"[CONFIG-SYNC] Callback error: {e}")
            return changed

        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"[CONFIG-SYNC] Sync failed (using cache): {e}")
            return False

    async def start(self):
        """Start periodic config sync loop."""
        if self._running or not self.is_configured:
            return
        self._running = True
        logger.info(f"[CONFIG-SYNC] Starting sync loop (interval={self._sync_interval}s)")

        # Initial sync
        await self.sync_now()

        while self._running:
            await asyncio.sleep(self._sync_interval)
            if not self._running:
                break
            await self.sync_now()

    def stop(self):
        self._running = False
        logger.info("[CONFIG-SYNC] Stopped")


# Singleton
config_sync_client = ConfigSyncClient()
