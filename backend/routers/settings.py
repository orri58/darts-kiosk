"""Settings & Asset Upload Routes"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, Settings
from models import DEFAULT_BRANDING, DEFAULT_PRICING, DEFAULT_PALETTES, DEFAULT_STAMMKUNDE_DISPLAY
from schemas import SettingsUpdate
from dependencies import require_admin, log_audit, get_or_create_setting, ASSETS_DIR

router = APIRouter()


@router.get("/settings/branding")
async def get_branding(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "branding", DEFAULT_BRANDING)


@router.put("/settings/branding")
async def update_branding(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "branding"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="branding", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_branding", "settings", "branding")
    return setting.value


@router.get("/settings/pricing")
async def get_pricing(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "pricing", DEFAULT_PRICING)


@router.put("/settings/pricing")
async def update_pricing(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "pricing"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="pricing", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_pricing", "settings", "pricing")
    return setting.value


@router.get("/settings/palettes")
async def get_palettes(db: AsyncSession = Depends(get_db)):
    return await get_or_create_setting(db, "palettes", DEFAULT_PALETTES)


@router.put("/settings/palettes")
async def update_palettes(data: SettingsUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Settings).where(Settings.key == "palettes"))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = data.value
    else:
        setting = Settings(key="palettes", value=data.value)
        db.add(setting)
    await db.flush()
    await log_audit(db, admin, "update_palettes", "settings", "palettes")
    return setting.value


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
