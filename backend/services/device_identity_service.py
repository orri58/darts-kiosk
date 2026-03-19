"""
Device Identity Service — v3.4.3

Generates and persists a unique install_id for this kiosk device.
The install_id is stored in data/device_identity.json and remains
constant across restarts. It is used for license-to-device binding.

Optionally collects machine fingerprints (Windows Machine GUID, hostname)
for diagnostics and recovery — these are NOT used for enforcement.
"""
import json
import logging
import os
import platform
import socket
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Use the same DATA_DIR as database.py for consistency
try:
    from backend.database import DATA_DIR as _DATA_DIR
except ImportError:
    _DATA_DIR = Path(os.environ.get("DATA_DIR", "")) or (Path(__file__).resolve().parent.parent.parent / "data")

_IDENTITY_FILE = _DATA_DIR / "device_identity.json"


class DeviceIdentityService:
    """Manages a persistent, unique install_id for this device."""

    def __init__(self):
        self._install_id: Optional[str] = None
        self._fingerprints: dict = {}

    def get_install_id(self) -> str:
        """Return the device's install_id, creating one if it doesn't exist."""
        if self._install_id:
            return self._install_id

        # Try loading from file
        loaded = self._load_from_file()
        if loaded:
            self._install_id = loaded
            logger.info(f"[DEVICE_ID] Loaded install_id={self._install_id}")
            return self._install_id

        # Generate new
        self._install_id = str(uuid.uuid4())
        self._fingerprints = self._collect_fingerprints()
        self._save_to_file()
        logger.info(f"[DEVICE_ID] Generated new install_id={self._install_id}")
        return self._install_id

    def get_identity(self) -> dict:
        """Return full identity info (install_id + fingerprints)."""
        install_id = self.get_install_id()
        return {
            "install_id": install_id,
            "fingerprints": self._fingerprints,
        }

    def _load_from_file(self) -> Optional[str]:
        """Load install_id from persistent file."""
        try:
            if not _IDENTITY_FILE.exists():
                return None
            data = json.loads(_IDENTITY_FILE.read_text(encoding="utf-8"))
            iid = data.get("install_id")
            if iid:
                self._fingerprints = data.get("fingerprints", {})
                return iid
            return None
        except Exception as e:
            logger.error(f"[DEVICE_ID] Failed to load identity file: {e}")
            return None

    def _save_to_file(self):
        """Save install_id and fingerprints to persistent file."""
        try:
            _IDENTITY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "install_id": self._install_id,
                "fingerprints": self._fingerprints,
                "created_hostname": socket.gethostname(),
                "created_platform": platform.system(),
            }
            _IDENTITY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info(f"[DEVICE_ID] Saved identity to {_IDENTITY_FILE}")
        except Exception as e:
            logger.error(f"[DEVICE_ID] Failed to save identity file: {e}")

    @staticmethod
    def _collect_fingerprints() -> dict:
        """Collect optional machine fingerprints for diagnostics."""
        fp = {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
        }
        # Windows Machine GUID (read-only, non-enforced)
        if platform.system() == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                )
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                fp["machine_guid"] = machine_guid
            except Exception:
                fp["machine_guid"] = None
        return fp


# Module-level singleton
device_identity_service = DeviceIdentityService()
