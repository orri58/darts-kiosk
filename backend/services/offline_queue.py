"""
Offline Queue Service — v3.9.7

Persistent FIFO queue for outbound messages that couldn't reach Central Server.
Stored in data/offline_queue.json, drained when connectivity returns.

Guarantees:
- Fail-safe: NEVER blocks game operation, NEVER crashes
- Persistent: Survives restarts (JSON on disk)
- Idempotent: Unique keys prevent duplicate sends
- FIFO: Messages processed in order
- Bounded: Max 100 entries, oldest dropped on overflow (logged as WARN)
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("offline_queue")

from backend.services.device_log_buffer import device_logs

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_QUEUE_FILE = _DATA_DIR / "offline_queue.json"

_MAX_ENTRIES = 100
_MAX_RETRIES = 10
_DRAIN_INTERVAL = 60       # seconds between periodic drain attempts
_DRAIN_TIMEOUT = 10        # HTTP timeout for drain requests
_BACKOFF_BASE = 5          # base backoff seconds, doubles each retry


def _utcnow():
    return datetime.now(timezone.utc)


class OfflineQueue:
    def __init__(self):
        self._central_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._queue: list = []
        self._seen_keys: set = set()   # for fast dedup lookups
        self._running = False
        self._drain_lock = asyncio.Lock()
        self._drain_event = asyncio.Event()
        # stats
        self._enqueued_total = 0
        self._drained_total = 0
        self._dropped_total = 0
        self._drain_errors = 0
        self._last_drain_at: Optional[datetime] = None
        self._last_drain_error: Optional[str] = None

    def configure(self, central_url: str, api_key: str):
        self._central_url = central_url.rstrip("/") if central_url else None
        self._api_key = api_key
        self._load()
        if self._central_url:
            logger.info(f"[OFFLINE-Q] Configured: url={self._central_url}, pending={len(self._queue)}")
        else:
            logger.info("[OFFLINE-Q] Not configured (no central URL)")

    @property
    def is_configured(self):
        return bool(self._central_url and self._api_key)

    @property
    def pending_count(self):
        return len(self._queue)

    @property
    def status(self) -> dict:
        return {
            "configured": self.is_configured,
            "running": self._running,
            "pending": len(self._queue),
            "enqueued_total": self._enqueued_total,
            "drained_total": self._drained_total,
            "dropped_total": self._dropped_total,
            "drain_errors": self._drain_errors,
            "last_drain_at": self._last_drain_at.isoformat() if self._last_drain_at else None,
            "last_drain_error": self._last_drain_error,
        }

    # ── Persistence ──────────────────────────────────────────

    def _load(self):
        """Load queue from disk. Fail-safe: corrupt file → start fresh."""
        try:
            if _QUEUE_FILE.exists():
                data = json.loads(_QUEUE_FILE.read_text())
                if isinstance(data, list):
                    self._queue = data
                    self._seen_keys = {e.get("idempotency_key") for e in self._queue if e.get("idempotency_key")}
                    logger.info(f"[OFFLINE-Q] Loaded {len(self._queue)} pending entries from disk")
                else:
                    logger.warning("[OFFLINE-Q] Invalid queue file format, starting fresh")
                    self._queue = []
                    self._seen_keys = set()
        except Exception as e:
            logger.warning(f"[OFFLINE-Q] Failed to load queue (starting fresh): {e}")
            self._queue = []
            self._seen_keys = set()

    def _save(self):
        """Persist queue to disk. Fail-safe: write errors logged, not raised."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            _QUEUE_FILE.write_text(json.dumps(self._queue, indent=2))
        except Exception as e:
            logger.warning(f"[OFFLINE-Q] Failed to save queue: {e}")

    # ── Enqueue ──────────────────────────────────────────────

    def enqueue(self, msg_type: str, method: str, url_path: str,
                payload: dict, idempotency_key: str):
        """
        Add an outbound message to the offline queue.
        Thread-safe via GIL for the synchronous parts.
        NEVER raises — all errors are caught and logged.
        """
        try:
            # Idempotency: skip if already queued
            if idempotency_key in self._seen_keys:
                logger.debug(f"[OFFLINE-Q] Skipped duplicate: {idempotency_key}")
                return

            entry = {
                "idempotency_key": idempotency_key,
                "msg_type": msg_type,
                "method": method,
                "url_path": url_path,
                "payload": payload,
                "created_at": _utcnow().isoformat(),
                "retries": 0,
                "last_retry_at": None,
            }

            # Overflow: drop oldest entries
            while len(self._queue) >= _MAX_ENTRIES:
                dropped = self._queue.pop(0)
                dropped_key = dropped.get("idempotency_key")
                if dropped_key:
                    self._seen_keys.discard(dropped_key)
                self._dropped_total += 1
                logger.warning(f"[OFFLINE-Q] OVERFLOW: Dropped oldest entry: type={dropped.get('msg_type')} key={dropped_key}")
                device_logs.warn("offline_queue", "overflow",
                                 f"Dropped: {dropped.get('msg_type')} key={dropped_key}",
                                 {"dropped_total": self._dropped_total})

            self._queue.append(entry)
            self._seen_keys.add(idempotency_key)
            self._enqueued_total += 1
            self._save()

            logger.info(f"[OFFLINE-Q] Enqueued: type={msg_type} key={idempotency_key} (pending={len(self._queue)})")
            device_logs.info("offline_queue", "enqueued",
                             f"{msg_type}: {idempotency_key}",
                             {"pending": len(self._queue)})

        except Exception as e:
            logger.error(f"[OFFLINE-Q] Enqueue FAILED (non-fatal): {e}")

    # ── Drain ────────────────────────────────────────────────

    def notify_online(self):
        """Signal that central is reachable. Triggers immediate drain attempt."""
        if self._queue and self._running:
            self._drain_event.set()

    async def drain(self):
        """
        Process pending queue entries. Lock-protected against concurrent drains.
        NEVER raises — all errors are caught.
        """
        if not self.is_configured or not self._queue:
            return

        if self._drain_lock.locked():
            logger.debug("[OFFLINE-Q] Drain skipped — already running")
            return

        async with self._drain_lock:
            await self._do_drain()

    async def _do_drain(self):
        """Internal drain — must be called within _drain_lock."""
        drained = 0
        dead = 0
        errors = 0
        to_remove = []

        for idx, entry in enumerate(self._queue):
            key = entry.get("idempotency_key", "?")
            retries = entry.get("retries", 0)

            # Max retries exceeded → mark for removal (dead letter)
            if retries >= _MAX_RETRIES:
                to_remove.append(idx)
                dead += 1
                logger.error(f"[OFFLINE-Q] DEAD LETTER: key={key} after {retries} retries — removing")
                device_logs.error("offline_queue", "dead_letter",
                                  f"Dropped after {retries} retries: {key}",
                                  {"msg_type": entry.get("msg_type")})
                continue

            # Backoff check: skip if too soon
            last_retry = entry.get("last_retry_at")
            if last_retry and retries > 0:
                backoff = min(_BACKOFF_BASE * (2 ** (retries - 1)), 300)
                elapsed = (_utcnow() - datetime.fromisoformat(last_retry)).total_seconds()
                if elapsed < backoff:
                    continue  # Not yet time to retry

            # Try sending
            success = await self._send_entry(entry)
            entry["retries"] = retries + 1
            entry["last_retry_at"] = _utcnow().isoformat()

            if success:
                to_remove.append(idx)
                drained += 1
            else:
                errors += 1
                # Stop draining on first error (central likely still down)
                break

        # Remove drained/dead entries (reverse order to preserve indices)
        for idx in sorted(to_remove, reverse=True):
            removed = self._queue.pop(idx)
            self._seen_keys.discard(removed.get("idempotency_key"))

        if drained > 0 or dead > 0:
            self._drained_total += drained
            self._dropped_total += dead
            self._last_drain_at = _utcnow()
            self._save()
            logger.info(f"[OFFLINE-Q] Drain complete: {drained} sent, {dead} dead, {errors} errors, {len(self._queue)} remaining")
            device_logs.info("offline_queue", "drain_complete",
                             f"{drained} sent, {dead} dead, {len(self._queue)} remaining")

        if errors > 0:
            self._drain_errors += errors
            self._last_drain_error = f"{errors} errors at {_utcnow().isoformat()}"

    async def _send_entry(self, entry: dict) -> bool:
        """Send a single queue entry to central. Returns True on success."""
        try:
            url = f"{self._central_url}{entry['url_path']}"
            headers = {"X-License-Key": self._api_key, "Content-Type": "application/json"}

            async with httpx.AsyncClient(timeout=_DRAIN_TIMEOUT) as client:
                if entry.get("method", "POST").upper() == "POST":
                    resp = await client.post(url, json=entry.get("payload", {}), headers=headers)
                else:
                    resp = await client.put(url, json=entry.get("payload", {}), headers=headers)

            if resp.status_code < 400:
                logger.debug(f"[OFFLINE-Q] Sent OK: key={entry.get('idempotency_key')} → HTTP {resp.status_code}")
                return True
            elif 400 <= resp.status_code < 500:
                # Client error — don't retry (likely rejected by server)
                logger.warning(f"[OFFLINE-Q] Rejected (HTTP {resp.status_code}): key={entry.get('idempotency_key')} — removing")
                return True  # Remove from queue, retrying won't help
            else:
                logger.warning(f"[OFFLINE-Q] Server error (HTTP {resp.status_code}): key={entry.get('idempotency_key')}")
                return False
        except httpx.TimeoutException:
            logger.debug(f"[OFFLINE-Q] Timeout: key={entry.get('idempotency_key')}")
            return False
        except Exception as e:
            logger.debug(f"[OFFLINE-Q] Send error: key={entry.get('idempotency_key')}: {e}")
            return False

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self):
        """Start background drain loop. Non-blocking, fail-safe."""
        if self._running or not self.is_configured:
            return
        self._running = True
        asyncio.create_task(self._drain_loop())
        logger.info(f"[OFFLINE-Q] Started (interval={_DRAIN_INTERVAL}s, pending={len(self._queue)})")

    async def _drain_loop(self):
        """Background loop: drain periodically or on notify_online signal."""
        while self._running:
            try:
                # Wait for either the periodic interval or an explicit signal
                try:
                    await asyncio.wait_for(self._drain_event.wait(), timeout=_DRAIN_INTERVAL)
                    self._drain_event.clear()
                except asyncio.TimeoutError:
                    pass  # Periodic drain

                if self._queue:
                    await self.drain()
            except Exception as e:
                logger.error(f"[OFFLINE-Q] Drain loop error (non-fatal): {e}")
                await asyncio.sleep(10)  # Brief pause on unexpected error

    def stop(self):
        self._running = False
        self._drain_event.set()  # Wake up loop to exit
        self._save()  # Final persist
        logger.info(f"[OFFLINE-Q] Stopped (pending={len(self._queue)})")

    async def force_drain(self):
        """Manual drain trigger (e.g. before shutdown)."""
        if self._queue:
            await self.drain()


# Singleton
offline_queue = OfflineQueue()
