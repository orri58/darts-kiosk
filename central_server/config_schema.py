"""
Config Schema Validation — v3.9.4

Validates config_data before saving to config_profiles.
Pragmatic: checks types, ranges, required fields. No meta-engine.
Same validation for Standard-UI and JSON/Advanced mode.
"""
import re

_HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
_URL_PATTERN = re.compile(r'^https?://')


def _err(section, field, msg):
    return f"{section}.{field}: {msg}"


def validate_config(config_data: dict) -> list:
    """
    Validate a config_data dict. Returns a list of error strings.
    Empty list = valid.
    """
    if not isinstance(config_data, dict):
        return ["config_data muss ein JSON-Objekt sein"]

    errors = []

    if "pricing" in config_data:
        errors.extend(_validate_pricing(config_data["pricing"]))
    if "branding" in config_data:
        errors.extend(_validate_branding(config_data["branding"]))
    if "kiosk" in config_data:
        errors.extend(_validate_kiosk(config_data["kiosk"]))
    if "texts" in config_data:
        errors.extend(_validate_texts(config_data["texts"]))
    if "language" in config_data:
        errors.extend(_validate_language(config_data["language"]))
    if "sound" in config_data:
        errors.extend(_validate_sound(config_data["sound"]))
    if "sharing" in config_data:
        errors.extend(_validate_sharing(config_data["sharing"]))
    if "boards" in config_data:
        errors.extend(_validate_boards(config_data["boards"]))

    return errors


def _validate_pricing(p):
    errs = []
    if not isinstance(p, dict):
        return [_err("pricing", "*", "muss ein Objekt sein")]

    if "mode" in p and p["mode"] not in ("per_game", "per_time", "per_player"):
        errs.append(_err("pricing", "mode", "muss per_game, per_time oder per_player sein"))

    if "per_game" in p and isinstance(p["per_game"], dict):
        pg = p["per_game"]
        if "price_per_credit" in pg:
            v = pg["price_per_credit"]
            if not isinstance(v, (int, float)) or v < 0:
                errs.append(_err("pricing", "per_game.price_per_credit", "muss eine Zahl >= 0 sein"))
        if "default_credits" in pg:
            v = pg["default_credits"]
            if not isinstance(v, int) or v < 1:
                errs.append(_err("pricing", "per_game.default_credits", "muss eine ganze Zahl >= 1 sein"))

    if "per_time" in p and isinstance(p["per_time"], dict):
        pt = p["per_time"]
        for k in ("price_per_30_min", "price_per_60_min"):
            if k in pt:
                v = pt[k]
                if not isinstance(v, (int, float)) or v < 0:
                    errs.append(_err("pricing", f"per_time.{k}", "muss eine Zahl >= 0 sein"))

    if "per_player" in p and isinstance(p["per_player"], dict):
        pp = p["per_player"]
        if "price_per_player" in pp:
            v = pp["price_per_player"]
            if not isinstance(v, (int, float)) or v < 0:
                errs.append(_err("pricing", "per_player.price_per_player", "muss eine Zahl >= 0 sein"))

    if "min_amount" in p:
        v = p["min_amount"]
        if not isinstance(v, (int, float)) or v < 0:
            errs.append(_err("pricing", "min_amount", "muss eine Zahl >= 0 sein"))

    return errs


def _validate_branding(b):
    errs = []
    if not isinstance(b, dict):
        return [_err("branding", "*", "muss ein Objekt sein")]

    if "cafe_name" in b:
        v = b["cafe_name"]
        if not isinstance(v, str) or len(v.strip()) == 0:
            errs.append(_err("branding", "cafe_name", "darf nicht leer sein"))
        elif len(v) > 100:
            errs.append(_err("branding", "cafe_name", "maximal 100 Zeichen"))

    if "subtitle" in b:
        v = b["subtitle"]
        if not isinstance(v, str):
            errs.append(_err("branding", "subtitle", "muss ein Text sein"))
        elif len(v) > 200:
            errs.append(_err("branding", "subtitle", "maximal 200 Zeichen"))

    for color_key in ("primary_color", "secondary_color", "accent_color"):
        if color_key in b:
            v = b[color_key]
            if isinstance(v, str) and v and not _HEX_COLOR.match(v):
                errs.append(_err("branding", color_key, "muss ein gueltiger Hex-Farbcode sein (#RRGGBB)"))

    if "logo_url" in b:
        v = b["logo_url"]
        if v is not None and isinstance(v, str) and v.strip() and not _URL_PATTERN.match(v):
            errs.append(_err("branding", "logo_url", "muss eine gueltige URL sein (http/https)"))

    return errs


def _validate_kiosk(k):
    errs = []
    if not isinstance(k, dict):
        return [_err("kiosk", "*", "muss ein Objekt sein")]

    for timeout_key in ("auto_lock_timeout_min", "idle_timeout_min"):
        if timeout_key in k:
            v = k[timeout_key]
            if not isinstance(v, (int, float)) or v <= 0:
                errs.append(_err("kiosk", timeout_key, "muss eine Zahl > 0 sein"))

    for bool_key in ("auto_start", "fullscreen"):
        if bool_key in k:
            v = k[bool_key]
            if not isinstance(v, bool):
                errs.append(_err("kiosk", bool_key, "muss true oder false sein"))

    return errs


def _validate_texts(t):
    errs = []
    if not isinstance(t, dict):
        return [_err("texts", "*", "muss ein Objekt sein")]

    for key, val in t.items():
        if not isinstance(val, str):
            errs.append(_err("texts", key, "muss ein Text sein"))
        elif len(val) > 200:
            errs.append(_err("texts", key, "maximal 200 Zeichen"))

    return errs


def _validate_language(l):
    errs = []
    if not isinstance(l, dict):
        return [_err("language", "*", "muss ein Objekt sein")]

    if "default" in l and l["default"] not in ("de", "en"):
        errs.append(_err("language", "default", "muss 'de' oder 'en' sein"))

    if "allow_switch" in l and not isinstance(l["allow_switch"], bool):
        errs.append(_err("language", "allow_switch", "muss true oder false sein"))

    return errs


def _validate_sound(s):
    errs = []
    if not isinstance(s, dict):
        return [_err("sound", "*", "muss ein Objekt sein")]

    if "enabled" in s and not isinstance(s["enabled"], bool):
        errs.append(_err("sound", "enabled", "muss true oder false sein"))

    if "volume" in s:
        v = s["volume"]
        if not isinstance(v, (int, float)) or v < 0 or v > 100:
            errs.append(_err("sound", "volume", "muss zwischen 0 und 100 liegen"))

    for hour_key in ("quiet_hours_start", "quiet_hours_end"):
        if hour_key in s:
            v = s[hour_key]
            if not isinstance(v, (int, float)) or v < 0 or v > 23:
                errs.append(_err("sound", hour_key, "muss zwischen 0 und 23 liegen"))

    return errs


def _validate_sharing(sh):
    errs = []
    if not isinstance(sh, dict):
        return [_err("sharing", "*", "muss ein Objekt sein")]

    for bool_key in ("qr_enabled", "public_results", "leaderboard_public"):
        if bool_key in sh:
            v = sh[bool_key]
            if not isinstance(v, bool):
                errs.append(_err("sharing", bool_key, "muss true oder false sein"))

    return errs



def _validate_boards(b):
    """Validate boards configuration section — v3.13.0."""
    errs = []
    if not isinstance(b, dict):
        return [_err("boards", "*", "muss ein Objekt sein")]

    if "autodarts_url" in b:
        v = b["autodarts_url"]
        if not isinstance(v, str):
            errs.append(_err("boards", "autodarts_url", "muss ein String sein"))
        elif v and not _URL_PATTERN.match(v):
            errs.append(_err("boards", "autodarts_url", "muss eine gueltige URL sein"))

    if "board_name" in b:
        v = b["board_name"]
        if not isinstance(v, str) or len(v) > 100:
            errs.append(_err("boards", "board_name", "muss ein String <= 100 Zeichen sein"))

    if "auto_start" in b:
        v = b["auto_start"]
        if not isinstance(v, bool):
            errs.append(_err("boards", "auto_start", "muss true oder false sein"))

    return errs
