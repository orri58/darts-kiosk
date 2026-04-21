from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.models import (
    Settings,
    DEFAULT_ADMIN_THEME,
    DEFAULT_BRANDING,
    DEFAULT_KIOSK_LAYOUT,
    DEFAULT_KIOSK_TEXTS,
    DEFAULT_KIOSK_THEME,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCKSCREEN_QR,
    DEFAULT_OVERLAY_CONFIG,
    DEFAULT_PALETTES,
    DEFAULT_POST_MATCH_DELAY,
    DEFAULT_PWA_CONFIG,
    DEFAULT_PRICING,
)
from backend.runtime_features import sanitize_pricing_settings


Sanitizer = Callable[[Any], Any]

DEFAULT_MATCH_SHARING = {"enabled": False, "qr_timeout": 60}


@dataclass(frozen=True)
class SettingContract:
    key: str
    default: Any
    sanitizer: Sanitizer | None = None
    merge_defaults: bool = True


_ALLOWED_HEADER_ALIGN = {"left", "center"}
_ALLOWED_LOGO_SIZE = {"sm", "md", "lg", "xl", "2xl"}
_ALLOWED_PAIRING_POSITION = {"bottom", "side"}
_ALLOWED_CONTENT_ALIGN = {"left", "center"}
_ALLOWED_LOGO_POSITION = {"header", "hero"}
_ALLOWED_BOOL = {True, False}


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, Mapping):
        merged = {k: deepcopy(v) for k, v in base.items()}
        for key, value in override.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    if isinstance(override, list):
        return deepcopy(override)
    return deepcopy(override)


def _normalized_base(default: Any, value: Any, merge_defaults: bool = True) -> Any:
    if isinstance(default, dict):
        incoming = value if isinstance(value, Mapping) else {}
        return _deep_merge(default, incoming) if merge_defaults else deepcopy(incoming)
    if isinstance(default, list):
        return deepcopy(value) if isinstance(value, list) else deepcopy(default)
    return deepcopy(value) if value is not None else deepcopy(default)


def _safe_str(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return fallback
    return str(value)


def _safe_bool(value: Any, fallback: bool) -> bool:
    return value if value in _ALLOWED_BOOL else fallback


def _safe_enum(value: Any, allowed: set[str], fallback: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return fallback


def _sanitize_branding(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_BRANDING)
    cfg = _normalized_base(default, value)
    for key in ("cafe_name", "subtitle", "palette_id", "font_preset", "background_style"):
        cfg[key] = _safe_str(cfg.get(key), default[key])
    logo_url = cfg.get("logo_url")
    cfg["logo_url"] = None if logo_url in (None, "") else str(logo_url)
    return cfg


def _sanitize_kiosk_theme(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_KIOSK_THEME)
    cfg = _normalized_base(default, value)
    for key in ("palette_id", "font_preset", "background_style"):
        cfg[key] = _safe_str(cfg.get(key), default[key])
    return cfg


def _sanitize_admin_theme(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_ADMIN_THEME)
    cfg = _normalized_base(default, value)
    cfg["palette_id"] = _safe_str(cfg.get("palette_id"), default["palette_id"])
    return cfg


def _sanitize_kiosk_layout(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_KIOSK_LAYOUT)
    cfg = _normalized_base(default, value)
    cfg["preset"] = _safe_str(cfg.get("preset"), default["preset"])

    header = cfg.setdefault("header", deepcopy(default["header"]))
    header["show_logo"] = _safe_bool(header.get("show_logo"), default["header"]["show_logo"])
    header["show_title"] = _safe_bool(header.get("show_title"), default["header"]["show_title"])
    header["show_subtitle"] = _safe_bool(header.get("show_subtitle"), default["header"]["show_subtitle"])
    header["align"] = _safe_enum(header.get("align"), _ALLOWED_HEADER_ALIGN, default["header"]["align"])
    header["logo_size"] = _safe_enum(header.get("logo_size"), _ALLOWED_LOGO_SIZE, default["header"]["logo_size"])

    locked = cfg.setdefault("locked_screen", deepcopy(default["locked_screen"]))
    locked["pairing_position"] = _safe_enum(
        locked.get("pairing_position"), _ALLOWED_PAIRING_POSITION, default["locked_screen"]["pairing_position"]
    )
    locked["show_community_widgets"] = _safe_bool(
        locked.get("show_community_widgets"), default["locked_screen"]["show_community_widgets"]
    )
    locked["panel_emphasis"] = _safe_str(locked.get("panel_emphasis"), default["locked_screen"]["panel_emphasis"])
    locked["content_align"] = _safe_enum(
        locked.get("content_align"), _ALLOWED_CONTENT_ALIGN, default["locked_screen"]["content_align"]
    )
    locked["logo_position"] = _safe_enum(
        locked.get("logo_position"), _ALLOWED_LOGO_POSITION, default["locked_screen"]["logo_position"]
    )
    locked["hero_logo_size"] = _safe_enum(
        locked.get("hero_logo_size"), _ALLOWED_LOGO_SIZE, default["locked_screen"]["hero_logo_size"]
    )
    return cfg


def _sanitize_card(card_value: Any, default_card: Mapping[str, Any]) -> dict[str, Any]:
    card = _normalized_base(default_card, card_value)
    card["enabled"] = _safe_bool(card.get("enabled"), bool(default_card.get("enabled", True)))
    for key in ("label", "value", "hint"):
        card[key] = _safe_str(card.get(key), str(default_card.get(key, "")))
    return card


def _sanitize_kiosk_texts(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_KIOSK_TEXTS)
    cfg = _normalized_base(default, value)
    scalar_keys = (
        "locked_title",
        "locked_subtitle",
        "pricing_hint",
        "game_running",
        "game_finished",
        "call_staff",
        "credits_label",
        "time_label",
        "staff_hint",
        "upsell_message",
        "upsell_pricing",
    )
    for key in scalar_keys:
        cfg[key] = _safe_str(cfg.get(key), default[key])
    locked_cards = cfg.setdefault("locked_cards", deepcopy(default["locked_cards"]))
    for card_key, default_card in default["locked_cards"].items():
        locked_cards[card_key] = _sanitize_card(locked_cards.get(card_key), default_card)
    return cfg


def _sanitize_pwa_config(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_PWA_CONFIG)
    cfg = _normalized_base(default, value)
    for key in ("app_name", "short_name", "theme_color", "background_color"):
        cfg[key] = _safe_str(cfg.get(key), default[key])
    return cfg


def _sanitize_lockscreen_qr(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_LOCKSCREEN_QR)
    cfg = _normalized_base(default, value)
    cfg["enabled"] = _safe_bool(cfg.get("enabled"), default["enabled"])
    cfg["label"] = _safe_str(cfg.get("label"), default["label"])
    path = _safe_str(cfg.get("path"), default["path"])
    if not path.startswith("/"):
        path = default["path"]
    cfg["path"] = path
    return cfg


def _sanitize_overlay_config(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_OVERLAY_CONFIG)
    cfg = _normalized_base(default, value)
    cfg["enabled"] = _safe_bool(cfg.get("enabled"), default["enabled"])
    cfg["position"] = _safe_str(cfg.get("position"), default["position"])
    return cfg


def _sanitize_post_match_delay(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_POST_MATCH_DELAY)
    cfg = _normalized_base(default, value)
    try:
        delay_ms = int(cfg.get("delay_ms", default["delay_ms"]))
    except (TypeError, ValueError):
        delay_ms = default["delay_ms"]
    cfg["delay_ms"] = max(0, min(delay_ms, 60_000))
    return cfg


def _sanitize_language(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_LANGUAGE)
    cfg = _normalized_base(default, value)
    cfg["language"] = _safe_str(cfg.get("language"), default["language"])
    return cfg


def _sanitize_match_sharing(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_MATCH_SHARING)
    cfg = _normalized_base(default, value)
    cfg["enabled"] = _safe_bool(cfg.get("enabled"), default["enabled"])
    try:
        qr_timeout = int(cfg.get("qr_timeout", default["qr_timeout"]))
    except (TypeError, ValueError):
        qr_timeout = default["qr_timeout"]
    cfg["qr_timeout"] = max(5, min(qr_timeout, 600))
    return cfg


SETTINGS_CONTRACTS: dict[str, SettingContract] = {
    "branding": SettingContract("branding", DEFAULT_BRANDING, _sanitize_branding),
    "pricing": SettingContract("pricing", DEFAULT_PRICING, sanitize_pricing_settings),
    "palettes": SettingContract("palettes", DEFAULT_PALETTES, merge_defaults=False),
    "kiosk_theme": SettingContract("kiosk_theme", DEFAULT_KIOSK_THEME, _sanitize_kiosk_theme),
    "admin_theme": SettingContract("admin_theme", DEFAULT_ADMIN_THEME, _sanitize_admin_theme),
    "kiosk_layout": SettingContract("kiosk_layout", DEFAULT_KIOSK_LAYOUT, _sanitize_kiosk_layout),
    "kiosk_texts": SettingContract("kiosk_texts", DEFAULT_KIOSK_TEXTS, _sanitize_kiosk_texts),
    "pwa_config": SettingContract("pwa_config", DEFAULT_PWA_CONFIG, _sanitize_pwa_config),
    "lockscreen_qr": SettingContract("lockscreen_qr", DEFAULT_LOCKSCREEN_QR, _sanitize_lockscreen_qr),
    "overlay_config": SettingContract("overlay_config", DEFAULT_OVERLAY_CONFIG, _sanitize_overlay_config),
    "post_match_delay": SettingContract("post_match_delay", DEFAULT_POST_MATCH_DELAY, _sanitize_post_match_delay),
    "language": SettingContract("language", DEFAULT_LANGUAGE, _sanitize_language),
    "match_sharing": SettingContract("match_sharing", DEFAULT_MATCH_SHARING, _sanitize_match_sharing),
}


def has_setting_contract(key: str) -> bool:
    return key in SETTINGS_CONTRACTS


def get_contract(key: str) -> SettingContract:
    return SETTINGS_CONTRACTS[key]


def normalize_setting_value(key: str, value: Any) -> Any:
    contract = get_contract(key)
    normalized = _normalized_base(contract.default, value, merge_defaults=contract.merge_defaults)
    if contract.sanitizer is not None:
        normalized = contract.sanitizer(normalized)
    if contract.merge_defaults and isinstance(contract.default, dict):
        normalized = _deep_merge(contract.default, normalized)
    return normalized


async def get_setting_value(db: AsyncSession, key: str) -> Any:
    contract = get_contract(key)
    result = await db.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    value = setting.value if setting else deepcopy(contract.default)
    return normalize_setting_value(key, value)


async def set_setting_value(db: AsyncSession, key: str, value: Any) -> Any:
    normalized = normalize_setting_value(key, value)
    result = await db.execute(select(Settings).where(Settings.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = normalized
        flag_modified(setting, "value")
    else:
        setting = Settings(key=key, value=normalized)
        db.add(setting)
    await db.flush()
    return normalized


def build_customization_bundle_from_values(values: Mapping[str, Any] | None = None) -> dict[str, Any]:
    values = values or {}
    return {
        "branding": normalize_setting_value("branding", values.get("branding")),
        "pricing": normalize_setting_value("pricing", values.get("pricing")),
        "palettes": normalize_setting_value("palettes", values.get("palettes")),
        "kioskTheme": normalize_setting_value("kiosk_theme", values.get("kiosk_theme")),
        "adminTheme": normalize_setting_value("admin_theme", values.get("admin_theme")),
        "kioskLayout": normalize_setting_value("kiosk_layout", values.get("kiosk_layout")),
        "kioskTexts": normalize_setting_value("kiosk_texts", values.get("kiosk_texts")),
        "pwaConfig": normalize_setting_value("pwa_config", values.get("pwa_config")),
        "lockscreenQr": normalize_setting_value("lockscreen_qr", values.get("lockscreen_qr")),
        "overlayConfig": normalize_setting_value("overlay_config", values.get("overlay_config")),
        "postMatchDelay": normalize_setting_value("post_match_delay", values.get("post_match_delay")),
        "language": normalize_setting_value("language", values.get("language")),
        "matchSharing": normalize_setting_value("match_sharing", values.get("match_sharing")),
    }


async def build_customization_bundle(db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(select(Settings).where(Settings.key.in_(list(SETTINGS_CONTRACTS.keys()))))
    settings = {row.key: row.value for row in result.scalars().all()}
    return build_customization_bundle_from_values(settings)
