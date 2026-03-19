"""
Device Registration Client — v3.5.1

Handles the one-time registration of a kiosk device with the central server
using a registration token.

Design:
- Sends registration request to the central server
- On success: saves API key and registration data to local config
- On failure: returns clear error with reason
- NEVER fail-open — registration MUST succeed online
- Uses the sync server URL from the existing sync config
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 20  # seconds
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_REG_FILE = _DATA_DIR / "device_registration.json"


class DeviceRegistrationClient:
    """Client for registering a kiosk device with the central license server."""

    def __init__(self):
        self._registration_data: Optional[dict] = None
        self._load_local()

    def _load_local(self):
        """Load saved registration data from disk."""
        try:
            if _REG_FILE.exists():
                with open(_REG_FILE) as f:
                    self._registration_data = json.load(f)
                logger.info(f"[REG] Loaded registration data: device_id={self._registration_data.get('device_id', '?')}")
        except Exception as e:
            logger.warning(f"[REG] Failed to load registration data: {e}")
            self._registration_data = None

    def _save_local(self, data: dict):
        """Save registration data to disk."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(_REG_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self._registration_data = data
            logger.info(f"[REG] Saved registration data: device_id={data.get('device_id', '?')}")
        except Exception as e:
            logger.error(f"[REG] Failed to save registration data: {e}")

    @property
    def is_registered(self) -> bool:
        """Check if this device is registered."""
        return bool(
            self._registration_data
            and self._registration_data.get("device_id")
            and self._registration_data.get("api_key")
        )

    @property
    def registration_status(self) -> str:
        """Return registration status: registered | unregistered."""
        return "registered" if self.is_registered else "unregistered"

    def get_api_key(self) -> Optional[str]:
        """Return the device's API key from registration."""
        if self._registration_data:
            return self._registration_data.get("api_key")
        return None

    def get_status(self) -> dict:
        """Return registration status for admin UI."""
        if self.is_registered:
            return {
                "status": "registered",
                "device_id": self._registration_data.get("device_id"),
                "device_name": self._registration_data.get("device_name"),
                "customer_name": self._registration_data.get("customer_name"),
                "customer_id": self._registration_data.get("customer_id"),
                "location_id": self._registration_data.get("location_id"),
                "license_status": self._registration_data.get("license_status"),
                "registered_at": self._registration_data.get("registered_at"),
            }
        return {"status": "unregistered"}

    async def register(
        self,
        server_url: str,
        token: str,
        install_id: str,
        device_name: Optional[str] = None,
        hostname: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> dict:
        """
        Register this device with the central server using a one-time token.

        Returns dict with:
            success: bool
            error: str (on failure)
            ... device/license data (on success)
        """
        if not server_url:
            return {"success": False, "error": "Keine Server-URL konfiguriert"}
        if not token:
            return {"success": False, "error": "Kein Registrierungstoken angegeben"}
        if not install_id:
            return {"success": False, "error": "Keine Install-ID vorhanden"}

        url = f"{server_url.rstrip('/')}/api/register-device"
        body = {
            "token": token,
            "install_id": install_id,
            "device_name": device_name,
            "hostname": hostname,
            "app_version": app_version,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=body)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    # Save registration data locally
                    reg_data = {
                        "device_id": data.get("device_id"),
                        "device_name": data.get("device_name"),
                        "api_key": data.get("api_key"),
                        "customer_id": data.get("customer_id"),
                        "customer_name": data.get("customer_name"),
                        "location_id": data.get("location_id"),
                        "license_id": data.get("license_id"),
                        "license_status": data.get("license_status"),
                        "plan_type": data.get("plan_type"),
                        "binding_status": data.get("binding_status"),
                        "registered_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self._save_local(reg_data)

                    # Also update sync config with the new API key
                    await self._update_sync_config_api_key(data.get("api_key"), server_url)

                    logger.info(f"[REG] Device registered successfully: {data.get('device_name')}")
                    return {"success": True, **data}
                return {"success": False, "error": data.get("detail", "Unbekannter Fehler")}

            # Parse error response
            try:
                err = resp.json()
                detail = err.get("detail", resp.text[:200])
            except Exception:
                detail = resp.text[:200]

            logger.warning(f"[REG] Registration failed HTTP {resp.status_code}: {detail}")
            return {"success": False, "error": detail, "status_code": resp.status_code}

        except httpx.ConnectError:
            return {"success": False, "error": "Server nicht erreichbar. Registrierung erfordert Online-Verbindung."}
        except httpx.TimeoutException:
            return {"success": False, "error": "Server-Timeout. Bitte erneut versuchen."}
        except Exception as e:
            logger.error(f"[REG] Unexpected error: {e}")
            return {"success": False, "error": str(e)}

    async def _update_sync_config_api_key(self, api_key: str, server_url: str):
        """After successful registration, update the local sync config with the new API key."""
        try:
            from backend.models import Settings
            from sqlalchemy import select
            from backend.database import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                stmt = select(Settings).where(Settings.key == "license_sync_config")
                result = await db.execute(stmt)
                s = result.scalar_one_or_none()
                existing = s.value if s and s.value and isinstance(s.value, dict) else {}

                existing["api_key"] = api_key
                existing["server_url"] = server_url
                existing["enabled"] = True

                if s:
                    s.value = existing
                else:
                    db.add(Settings(key="license_sync_config", value=existing))
                await db.commit()
                logger.info("[REG] Sync config updated with registration API key")
        except Exception as e:
            logger.warning(f"[REG] Failed to update sync config: {e}")

    def clear_registration(self):
        """Clear local registration data (for testing/debug only)."""
        self._registration_data = None
        try:
            if _REG_FILE.exists():
                _REG_FILE.unlink()
        except Exception:
            pass


# Module-level singleton
device_registration_client = DeviceRegistrationClient()
