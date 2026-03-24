"""
Config Sync Client — v3.9.2 (Hardened)

Pulls effective configuration from the Central Server at startup and periodically.
Fail-open: if the central server is unreachable, the last known config is used.

Hardening:
- asyncio.Lock prevents concurrent sync_now() calls (periodic + force_sync)
- Exponential backoff on consecutive failures (30s → 60s → 120s → cap 300s)
- Consecutive error counter for health reporting
- Sync count and error stats for diagnostics
- Disk cache survives restarts
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("config_sync")

from backend.services.device_log_buffer import device_logs

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_CACHE_FILE = _DATA_DIR / "config_cache.json"

_BASE_INTERVAL = 300          # 5 minutes normal
_MIN_BACKOFF = 30             # minimum retry interval on error
_MAX_BACKOFF = 300            # cap backoff at 5 minutes
_HTTP_TIMEOUT = 15


def _utcnow():
    return datetime.now(timezone.utc)


class ConfigSyncClient:
    def __init__(self):
        self._central_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._device_id: Optional[str] = None
        self._running = False
        self._sync_lock = asyncio.Lock()
        self._current_config: dict = {}
        self._config_version: int = 0
        self._last_sync_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._callbacks: list = []
        self._sync_count: int = 0
        self._sync_errors: int = 0
        self._consecutive_errors: int = 0

    def configure(self, central_url: str, api_key: str, device_id: str = None):
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        self._device_id = device_id
        if self._central_url:
            logger.info(f"[CONFIG-SYNC] Configured: {self._central_url} device={self._device_id}")
        else:
            logger.info("[CONFIG-SYNC] Not configured (no central URL)")
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
            "running": self._running,
            "last_sync_at": self._last_sync_at.isoformat() if self._last_sync_at else None,
            "config_version": self._config_version,
            "last_error": self._last_error,
            "sync_count": self._sync_count,
            "sync_errors": self._sync_errors,
            "consecutive_errors": self._consecutive_errors,
        }

    def on_config_change(self, callback):
        """Register callback for config changes. Prevents duplicate registrations."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            logger.debug(f"[CONFIG-SYNC] Callback registered: {callback.__name__}")
        else:
            logger.debug(f"[CONFIG-SYNC] Callback already registered (skipped): {callback.__name__}")

    # ── Cache ──

    def _load_cache(self):
        try:
            if _CACHE_FILE.exists():
                data = json.loads(_CACHE_FILE.read_text())
                self._current_config = data.get("config", {})
                self._config_version = data.get("version", 0)
                logger.info(f"[CONFIG-SYNC] Loaded cached config v{self._config_version}")
        except Exception as e:
            logger.warning(f"[CONFIG-SYNC] Failed to load cache: {e}")

    def _save_cache(self):
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(json.dumps({
                "config": self._current_config,
                "version": self._config_version,
                "synced_at": _utcnow().isoformat(),
            }, indent=2))
        except Exception as e:
            logger.warning(f"[CONFIG-SYNC] Failed to save cache: {e}")

    # ── Sync ──

    async def sync_now(self) -> bool:
        """Pull effective config. Lock-protected against concurrent calls.
        Returns True if config changed."""
        if not self.is_configured:
            return False

        # Non-blocking lock check: if already syncing, skip
        if self._sync_lock.locked():
            logger.debug("[CONFIG-SYNC] Sync skipped — already in progress")
            return False

        async with self._sync_lock:
            return await self._do_sync()

    async def _do_sync(self) -> bool:
        """Internal sync — must be called within _sync_lock."""
        self._sync_count += 1
        try:
            params = {}
            if self._device_id:
                params["device_id"] = self._device_id

            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._central_url}/api/config/effective",
                    params=params,
                    headers={"X-License-Key": self._api_key},
                )
                # v3.13.0: Handle 403 — device deactivated/blocked centrally
                if resp.status_code == 403:
                    logger.warning(f"[CONFIG-SYNC] REJECTED by central (403): {resp.text[:200]}")
                    try:
                        from backend.services.central_rejection_handler import handle_central_rejection
                        await handle_central_rejection("config_sync", 403, resp.text[:200])
                    except Exception:
                        pass
                    self._sync_errors += 1
                    self._consecutive_errors += 1
                    self._last_error = "403: Device rejected"
                    return False
                resp.raise_for_status()
                data = resp.json()

            # v3.15.3: Central accepted us — log only, NO auto-reactivation
            try:
                from backend.services.central_rejection_handler import handle_central_reactivation
                await handle_central_reactivation("config_sync")
            except Exception:
                pass

            new_config = data.get("config", {})
            new_version = data.get("version", 0)

            logger.info(f"[CONFIG-SYNC] CONFIG RECEIVED: version={new_version}, keys={list(new_config.keys())[:10]}")

            changed = new_version != self._config_version or new_config != self._current_config
            self._current_config = new_config
            self._config_version = new_version
            self._last_sync_at = _utcnow()
            self._last_error = None
            self._consecutive_errors = 0
            self._save_cache()

            if changed:
                layers = data.get("layers_applied", [])
                logger.info(f"[CONFIG-SYNC] CONFIG APPLIED: v{new_version}, layers={layers}")
                device_logs.info("config_sync", "config_applied", f"Config v{new_version} applied", {"layers": layers, "version": new_version})
                await self._run_callbacks(new_config)
            else:
                logger.info(f"[CONFIG-SYNC] CONFIG SKIPPED: no changes (v{new_version})")

            return changed

        except httpx.TimeoutException:
            self._sync_errors += 1
            self._consecutive_errors += 1
            self._last_error = "timeout"
            if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                logger.warning(f"[CONFIG-SYNC] Sync timeout (consecutive={self._consecutive_errors}, using cache)")
                device_logs.warn("config_sync", "sync_timeout", f"Timeout (consecutive={self._consecutive_errors})")
            return False

        except Exception as e:
            self._sync_errors += 1
            self._consecutive_errors += 1
            self._last_error = str(e)
            if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                logger.warning(f"[CONFIG-SYNC] Sync failed (consecutive={self._consecutive_errors}, using cache): {e}")
                device_logs.warn("config_sync", "sync_failed", str(e), {"consecutive": self._consecutive_errors})
            return False

    async def _run_callbacks(self, config: dict):
        """Run all registered callbacks. Errors are isolated per callback."""
        for cb in self._callbacks:
            try:
                await cb(config)
            except Exception as e:
                logger.error(f"[CONFIG-SYNC] Callback {cb.__name__} error: {e}", exc_info=True)

    # ── Lifecycle ──

    def _compute_interval(self) -> float:
        """Compute next sleep interval with exponential backoff on errors."""
        if self._consecutive_errors == 0:
            return _BASE_INTERVAL
        # Backoff: 30, 60, 120, 240, capped at 300
        backoff = _MIN_BACKOFF * (2 ** min(self._consecutive_errors - 1, 4))
        return min(backoff, _MAX_BACKOFF)

    async def start(self):
        if self._running or not self.is_configured:
            return
        self._running = True
        logger.info(f"[CONFIG-SYNC] Starting sync loop (base_interval={_BASE_INTERVAL}s)")

        # Initial sync
        await self.sync_now()

        while self._running:
            interval = self._compute_interval()
            if self._consecutive_errors > 0:
                logger.debug(f"[CONFIG-SYNC] Next sync in {interval}s (backoff, errors={self._consecutive_errors})")
            await asyncio.sleep(interval)
            if not self._running:
                break
            await self.sync_now()

    def stop(self):
        self._running = False
        logger.info("[CONFIG-SYNC] Stopped")


# Singleton
config_sync_client = ConfigSyncClient()
