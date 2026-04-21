"""Settings & Asset Upload Routes"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import User, Settings
from backend.models import DEFAULT_BRANDING, DEFAULT_PRICING, DEFAULT_PALETTES, DEFAULT_STAMMKUNDE_DISPLAY, DEFAULT_SOUND_CONFIG, DEFAULT_LANGUAGE, DEFAULT_KIOSK_TEXTS, DEFAULT_PWA_CONFIG, DEFAULT_LOCKSCREEN_QR, DEFAULT_OVERLAY_CONFIG, DEFAULT_POST_MATCH_DELAY, DEFAULT_AUTODARTS_TRIGGERS, DEFAULT_AUTODARTS_DESKTOP, DEFAULT_KIOSK_THEME, DEFAULT_ADMIN_THEME, DEFAULT_KIOSK_LAYOUT
from backend.schemas import SettingsUpdate
from backend.dependencies import require_admin, log_audit, get_or_create_setting, ASSETS_DIR
from backend.runtime_features import sanitize_pricing_settings
from backend.services.sound_generator import ensure_sound_pack, list_sound_packs, SOUND_EVENTS
from backend.services.autodarts_triggers import sanitize_trigger_policy_config, export_trigger_policy_metadata
from backend.services.settings_contract import build_customization_bundle, get_setting_value, set_setting_value

router = APIRouter()

# Sound files directory
SOUNDS_DIR = ASSETS_DIR.parent / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)


async def _get_contracted_setting(db: AsyncSession, key: str):
    return await get_setting_value(db, key)


async def _put_contracted_setting(db: AsyncSession, admin: User, key: str, value, audit_action: str):
    normalized = await set_setting_value(db, key, value)
    await log_audit(db, admin, audit_action, "settings", key)
    return normalized


@router.get("/settings/customization-bundle")
async def get_customization_bundle(db: AsyncSession = Depends(get_db)):
    return await build_customization_bundle(db)


@router.get("/settings/branding")
async def get_branding(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "branding")


@router.put("/settings/branding")
async def update_branding(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "branding", data.value, "update_branding")


@router.get("/settings/kiosk-theme")
async def get_kiosk_theme(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "kiosk_theme")


@router.put("/settings/kiosk-theme")
async def update_kiosk_theme(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "kiosk_theme", data.value, "update_kiosk_theme")


@router.get("/settings/admin-theme")
async def get_admin_theme(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "admin_theme")


@router.put("/settings/admin-theme")
async def update_admin_theme(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "admin_theme", data.value, "update_admin_theme")


@router.get("/settings/kiosk-layout")
async def get_kiosk_layout(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "kiosk_layout")


@router.put("/settings/kiosk-layout")
async def update_kiosk_layout(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "kiosk_layout", data.value, "update_kiosk_layout")


@router.get("/settings/pricing")
async def get_pricing(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "pricing")


@router.put("/settings/pricing")
async def update_pricing(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "pricing", data.value, "update_pricing")


@router.get("/settings/palettes")
async def get_palettes(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "palettes")


@router.put("/settings/palettes")
async def update_palettes(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "palettes", data.value, "update_palettes")


@router.get("/settings/stammkunde-display")
async def get_stammkunde_display_settings(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "stammkunde_display", DEFAULT_STAMMKUNDE_DISPLAY)


@router.put("/settings/stammkunde-display")
async def update_stammkunde_display(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "stammkunde_display"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="stammkunde_display", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_stammkunde_display", "settings", "stammkunde_display")
    return setting.value


# ===== Asset Upload =====

@router.post("/assets/upload")
async def upload_asset(file: UploadFile = File(...), admin: User = Depends(require_admin)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_types = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    ext = file.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = ASSETS_DIR / filename

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    return {"filename": filename, "url": f"/api/assets/{filename}"}


@router.get("/assets/{filename}")
async def get_asset(filename: str):
    filepath = ASSETS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(filepath)


# ===== Sound Config =====

@router.get("/settings/sound")
async def get_sound_config(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "sound_config", DEFAULT_SOUND_CONFIG)


@router.put("/settings/sound")
async def update_sound_config(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "sound_config"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="sound_config", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_sound_config", "settings", "sound_config")
    return setting.value


@router.get("/sounds/packs")
async def get_sound_packs():
    """List available sound packs."""
    ensure_sound_pack(SOUNDS_DIR, "default")
    return {"packs": list_sound_packs(SOUNDS_DIR)}


# ===== Language Settings =====

@router.get("/settings/language")
async def get_language(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "language")


@router.put("/settings/language")
async def update_language(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "language", data.value, "update_language")


# ===== Match Sharing Settings =====

DEFAULT_MATCH_SHARING = {"enabled": False, "qr_timeout": 60}

@router.get("/settings/match-sharing")
async def get_match_sharing(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "match_sharing")


@router.put("/settings/match-sharing")
async def update_match_sharing(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "match_sharing", data.value, "update_match_sharing")



@router.get("/sounds/{pack}/{event}.wav")
async def get_sound_file(pack: str, event: str):
    """Serve a sound WAV file with strong cache headers."""
    if event not in SOUND_EVENTS:
        raise HTTPException(status_code=404, detail="Unknown sound event")

    # Ensure pack exists (generates on first access)
    ensure_sound_pack(SOUNDS_DIR, pack)

    filepath = SOUNDS_DIR / pack / f"{event}.wav"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Sound file not found")

    return FileResponse(
        filepath,
        media_type="audio/wav",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "Content-Disposition": f"inline; filename={event}.wav",
        },
    )


# ===== Kiosk Text Settings =====

@router.get("/settings/kiosk-texts")
async def get_kiosk_texts(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "kiosk_texts")


@router.put("/settings/kiosk-texts")
async def update_kiosk_texts(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "kiosk_texts", data.value, "update_kiosk_texts")


# ===== PWA Config =====

@router.get("/settings/pwa")
async def get_pwa_config(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "pwa_config")


@router.put("/settings/pwa")
async def update_pwa_config(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "pwa_config", data.value, "update_pwa_config")



# ===== Lock Screen QR Config =====

@router.get("/settings/lockscreen-qr")
async def get_lockscreen_qr(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "lockscreen_qr")


@router.put("/settings/lockscreen-qr")
async def update_lockscreen_qr(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "lockscreen_qr", data.value, "update_lockscreen_qr")



# ===== Credits Overlay Config =====

@router.get("/settings/overlay")
async def get_overlay_config(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "overlay_config")


@router.put("/settings/overlay")
async def update_overlay_config(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "overlay_config", data.value, "update_overlay_config")


# ===== Post-Match Delay Settings =====

@router.get("/settings/post-match-delay")
async def get_post_match_delay(db: AsyncSession = Depends(get_db)):
    return await _get_contracted_setting(db, "post_match_delay")


@router.put("/settings/post-match-delay")
async def update_post_match_delay(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _put_contracted_setting(db, admin, "post_match_delay", data.value, "update_post_match_delay")


# ===== Autodarts Trigger Policy =====

@router.get("/settings/autodarts-triggers")
async def get_autodarts_triggers(db: AsyncSession = Depends(get_db)):
    current = await get_or_create_setting(db, "autodarts_triggers", DEFAULT_AUTODARTS_TRIGGERS)
    return sanitize_trigger_policy_config(current)


@router.get("/settings/autodarts-triggers/metadata")
async def get_autodarts_triggers_metadata(admin: User = Depends(require_admin)):
    return export_trigger_policy_metadata()


@router.put("/settings/autodarts-triggers")
async def update_autodarts_triggers(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        sanitized = sanitize_trigger_policy_config(data.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(select(Settings).where(Settings.key == "autodarts_triggers"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = sanitized
    else:
        setting = Settings(key="autodarts_triggers", value=sanitized)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_autodarts_triggers", "settings", "autodarts_triggers")
    return setting.value


# ===== Autodarts Desktop Settings =====

@router.get("/settings/autodarts-desktop")
async def get_autodarts_desktop_settings(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "autodarts_desktop", DEFAULT_AUTODARTS_DESKTOP)


@router.put("/settings/autodarts-desktop")
async def update_autodarts_desktop_settings(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "autodarts_desktop"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="autodarts_desktop", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_autodarts_desktop", "settings", "autodarts_desktop")
    return setting.value
