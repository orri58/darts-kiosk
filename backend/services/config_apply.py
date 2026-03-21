"""
Config Apply Service — v3.9.2 (Hardened)

Takes the effective central config and writes it into the local Settings table.
Bridges central config → local DB → existing Kiosk UI.

Hardening:
- Per-section try/except: one corrupt section cannot block others
- Deep copy to avoid SQLAlchemy mutation tracking issues
- flag_modified for JSON column change detection
- Persistent applied-version counter (survives restarts)
- Atomic: all-or-nothing commit per apply call
"""
import copy
import json
import logging
from pathlib import Path

from backend.database import AsyncSessionLocal
from backend.models import Settings
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger("config_apply")

from backend.services.device_log_buffer import device_logs

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_VERSION_FILE = _DATA_DIR / "config_applied_version.json"


# ── Config Mapping ──

CONFIG_TO_SETTINGS_MAP = {
    "pricing": {
        "settings_key": "pricing",
        "fields": {
            "mode": "mode",
            "per_game.price_per_credit": "per_game.price_per_credit",
            "per_game.default_credits": "per_game.default_credits",
            "min_amount": "min_amount",
        }
    },
    "branding": {
        "settings_key": "branding",
        "fields": {
            "cafe_name": "cafe_name",
            "subtitle": "subtitle",
            "logo_url": "logo_url",
            "primary_color": "primary_color",
            "secondary_color": "secondary_color",
            "accent_color": "accent_color",
        }
    },
    "kiosk": {
        "settings_key": "kiosk_behavior",
        "fields": {
            "auto_lock_timeout_min": "auto_lock_timeout_min",
            "idle_timeout_min": "idle_timeout_min",
            "auto_start": "auto_start",
            "fullscreen": "fullscreen",
        }
    },
    "texts": {
        "settings_key": "kiosk_texts",
        "fields": {
            "welcome_title": "locked_title",
            "welcome_subtitle": "locked_subtitle",
            "locked_message": "game_running",
            "game_over": "game_finished",
        }
    },
    "language": {
        "settings_key": "language",
        "fields": {
            "default": "current",
            "allow_switch": "allow_switch",
        }
    },
    "sound": {
        "settings_key": "sound_config",
        "fields": {
            "enabled": "enabled",
            "volume": "volume",
            "quiet_hours_start": "quiet_hours_start",
            "quiet_hours_end": "quiet_hours_end",
        }
    },
    "sharing": {
        "settings_key": "match_sharing",
        "fields": {
            "qr_enabled": "enabled",
            "public_results": "public_results",
            "leaderboard_public": "leaderboard_public",
        }
    },
}


# ── Helpers ──

def _get_nested(obj, path):
    keys = path.split(".")
    current = obj
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return None
        current = current[k]
    return current


def _set_nested(obj, path, value):
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


# ── Version Persistence ──

_config_applied_version = 0


def _load_version():
    global _config_applied_version
    try:
        if _VERSION_FILE.exists():
            data = json.loads(_VERSION_FILE.read_text())
            _config_applied_version = data.get("version", 0)
            logger.info(f"[CONFIG-APPLY] Loaded persisted version: {_config_applied_version}")
    except Exception as e:
        logger.warning(f"[CONFIG-APPLY] Failed to load version (starting at 0): {e}")


def _save_version():
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _VERSION_FILE.write_text(json.dumps({"version": _config_applied_version}))
    except Exception as e:
        logger.warning(f"[CONFIG-APPLY] Failed to save version: {e}")


# Load on module import
_load_version()


def get_applied_version() -> int:
    return _config_applied_version


# ── Core Apply ──

async def apply_config(config: dict) -> dict:
    """
    Apply central config to local settings table.
    Per-section isolation: one failing section cannot block others.
    Returns dict of changed settings keys → new values.
    """
    if not config:
        logger.debug("[CONFIG-APPLY] No config to apply")
        return {}

    changes = {}
    errors = []

    async with AsyncSessionLocal() as db:
        for section_key, mapping in CONFIG_TO_SETTINGS_MAP.items():
            try:
                section_data = config.get(section_key)
                if not section_data:
                    continue

                settings_key = mapping["settings_key"]

                result = await db.execute(
                    select(Settings).where(Settings.key == settings_key)
                )
                setting = result.scalar_one_or_none()
                current_value = copy.deepcopy(setting.value) if setting and isinstance(setting.value, dict) else {}

                changed = False
                for central_path, local_path in mapping["fields"].items():
                    central_val = _get_nested(section_data, central_path)
                    if central_val is not None:
                        existing_val = _get_nested(current_value, local_path)
                        if existing_val != central_val:
                            _set_nested(current_value, local_path, central_val)
                            changed = True
                            logger.debug(f"[CONFIG-APPLY] {settings_key}.{local_path}: {existing_val!r} -> {central_val!r}")

                if changed:
                    if setting:
                        setting.value = current_value
                        flag_modified(setting, "value")
                    else:
                        setting = Settings(key=settings_key, value=current_value)
                        db.add(setting)
                    changes[settings_key] = current_value

            except Exception as e:
                errors.append(f"{section_key}: {e}")
                logger.error(f"[CONFIG-APPLY] Section '{section_key}' failed: {e}", exc_info=True)

        if changes:
            try:
                await db.commit()
                logger.info(f"[CONFIG-APPLY] Applied {len(changes)} setting(s): {list(changes.keys())}")
                device_logs.info("config_apply", "settings_applied", f"Applied: {list(changes.keys())}", {"count": len(changes)})
            except Exception as e:
                logger.error(f"[CONFIG-APPLY] DB commit failed: {e}", exc_info=True)
                device_logs.error("config_apply", "commit_failed", str(e))
                changes = {}

    if errors:
        logger.warning(f"[CONFIG-APPLY] {len(errors)} section(s) had errors: {errors}")
        device_logs.warn("config_apply", "section_errors", f"{len(errors)} sections failed", {"errors": errors})

    return changes


# ── Callback ──

async def on_config_synced(config: dict):
    """Callback invoked by config_sync_client after each successful sync with changes."""
    global _config_applied_version
    changes = await apply_config(config)
    if changes:
        _config_applied_version += 1
        _save_version()
        logger.info(f"[CONFIG-APPLY] Version bumped to {_config_applied_version} (changed: {list(changes.keys())})")
