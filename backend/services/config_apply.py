"""
Config Apply Service — v3.9.1

Takes the effective central config and writes it into the local Settings table.
This bridges the gap between central config and the existing kiosk UI which
reads from local settings endpoints.

Flow: Central Config → config_apply → Local SQLite Settings → SettingsContext → UI
"""
import logging
from backend.database import AsyncSessionLocal
from backend.models import Settings
from sqlalchemy import select

logger = logging.getLogger("config_apply")

# Map central config keys → local settings keys + merge strategy
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


def _get_nested(obj, path):
    """Get nested value from dict using dot notation."""
    keys = path.split(".")
    current = obj
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return None
        current = current[k]
    return current


def _set_nested(obj, path, value):
    """Set nested value in dict using dot notation."""
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


async def apply_config(config: dict) -> dict:
    """
    Apply central config to local settings.
    Returns dict of what was changed.
    """
    if not config:
        logger.debug("[CONFIG-APPLY] No config to apply")
        return {}

    changes = {}

    async with AsyncSessionLocal() as db:
        for section_key, mapping in CONFIG_TO_SETTINGS_MAP.items():
            section_data = config.get(section_key)
            if not section_data:
                continue

            settings_key = mapping["settings_key"]

            # Get current local setting
            result = await db.execute(
                select(Settings).where(Settings.key == settings_key)
            )
            setting = result.scalar_one_or_none()
            current_value = setting.value if setting else {}
            if not isinstance(current_value, dict):
                current_value = {}

            # Apply each mapped field
            changed = False
            for central_path, local_path in mapping["fields"].items():
                central_val = _get_nested(section_data, central_path)
                if central_val is not None:
                    existing_val = _get_nested(current_value, local_path)
                    if existing_val != central_val:
                        _set_nested(current_value, local_path, central_val)
                        changed = True

            if changed:
                if setting:
                    setting.value = current_value
                else:
                    setting = Settings(key=settings_key, value=current_value)
                    db.add(setting)
                changes[settings_key] = current_value

        if changes:
            await db.commit()
            logger.info(f"[CONFIG-APPLY] Applied {len(changes)} settings: {list(changes.keys())}")
        else:
            logger.debug("[CONFIG-APPLY] No changes to apply")

    return changes


# Increment-based version tracking for frontend polling
_config_applied_version = 0


def get_applied_version():
    return _config_applied_version


async def on_config_synced(config: dict):
    """Callback for config_sync_client — runs after each successful sync."""
    global _config_applied_version
    changes = await apply_config(config)
    if changes:
        _config_applied_version += 1
        logger.info(f"[CONFIG-APPLY] Version bumped to {_config_applied_version}")
