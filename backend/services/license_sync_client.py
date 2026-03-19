"""
License Sync Client — v3.5.0

HTTP client that syncs license status with a central license server.
Used by the CyclicLicenseChecker for hybrid operation.

Design:
- Non-blocking async HTTP via httpx
- Simple API-key authentication
- Returns license status dict or None on failure
- Never raises — all errors are caught and logged
- Tracks connection state for UI display
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 15  # seconds


class LicenseSyncClient:
    """Sync client for communicating with a central license server."""

    def __init__(self):
        self.connected = False
        self.last_sync_at: Optional[datetime] = None
        self.last_sync_ok: Optional[bool] = None
        self.last_error: Optional[str] = None
        self.sync_count = 0

    async def sync(
        self,
        server_url: str,
        api_key: str,
        install_id: str,
        device_name: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Sync with central server. Returns license status dict or None.

        POST {server_url}/api/licensing/sync
        Body: { install_id, device_name }
        Headers: X-License-Key: {api_key}
        """
        url = f"{server_url.rstrip('/')}/api/licensing/sync"
        headers = {}
        if api_key:
            headers["X-License-Key"] = api_key

        body = {
            "install_id": install_id,
        }
        if device_name:
            body["device_name"] = device_name

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=body, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                self.connected = True
                self.last_sync_at = datetime.now(timezone.utc)
                self.last_sync_ok = True
                self.last_error = None
                self.sync_count += 1
                logger.info(
                    f"[SYNC] OK: status={data.get('status')} "
                    f"binding={data.get('binding_status')} server={server_url}"
                )
                return data
            else:
                self.connected = False
                self.last_sync_ok = False
                self.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(f"[SYNC] Server returned {resp.status_code}: {resp.text[:200]}")
                return None

        except httpx.ConnectError:
            self._mark_offline("Connection refused")
            return None
        except httpx.TimeoutException:
            self._mark_offline("Timeout")
            return None
        except Exception as e:
            self._mark_offline(str(e))
            return None

    def _mark_offline(self, reason: str):
        self.connected = False
        self.last_sync_ok = False
        self.last_error = reason
        logger.warning(f"[SYNC] Server unreachable: {reason} — using local cache")

    def get_status(self) -> dict:
        """Return sync client status for admin/UI display."""
        return {
            "connected": self.connected,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_sync_ok": self.last_sync_ok,
            "last_error": self.last_error,
            "sync_count": self.sync_count,
            "mode": "remote" if self.connected else "local",
        }


license_sync_client = LicenseSyncClient()
