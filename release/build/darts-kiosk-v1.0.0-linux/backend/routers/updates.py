"""Update Routes — GitHub-based update system with download, history, rollback"""
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import User
from backend.dependencies import require_admin, log_audit
from backend.services.update_service import update_service

router = APIRouter()


@router.get("/updates/check")
async def check_for_updates(admin: User = Depends(require_admin)):
    """Check GitHub for new releases."""
    return await update_service.check_for_updates()


@router.get("/updates/status")
async def get_update_status(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get current version, repo config, and persisted update history."""
    history = await update_service.get_update_history(db)
    return {
        "current_version": update_service.get_current_version(),
        "github_repo": update_service.get_github_repo(),
        "update_history": history,
    }


@router.post("/updates/prepare")
async def prepare_update(
    target_version: str = Query(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create backup and prepare update instructions for a target version."""
    result = await update_service.prepare_update(target_version)

    await update_service.record_update_event(db, {
        "action": "prepare_update",
        "target_version": target_version,
        "backup_created": result["backup_created"],
        "backup_filename": result.get("backup_filename"),
    })

    await log_audit(db, admin, "prepare_update", "system", "update", {"target_version": target_version})
    return result


@router.post("/updates/download")
async def download_release_asset(
    asset_url: str = Query(...),
    asset_name: str = Query(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Start downloading a release asset in the background."""
    download_id = str(uuid.uuid4())[:8]

    async def _do_download():
        await update_service.download_asset(asset_url, asset_name, download_id)

    background_tasks.add_task(_do_download)

    await update_service.record_update_event(db, {
        "action": "download_started",
        "asset_name": asset_name,
        "download_id": download_id,
    })

    return {
        "download_id": download_id,
        "asset_name": asset_name,
        "message": "Download gestartet",
    }


@router.get("/updates/download/{download_id}")
async def get_download_progress(download_id: str, admin: User = Depends(require_admin)):
    """Get the progress of a running download."""
    progress = update_service.get_download_progress(download_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Download nicht gefunden")
    return progress


@router.get("/updates/downloads")
async def list_downloads(admin: User = Depends(require_admin)):
    """List all downloaded release assets."""
    return {"assets": update_service.list_downloaded_assets()}


@router.delete("/updates/downloads/{filename}")
async def delete_download(filename: str, admin: User = Depends(require_admin)):
    """Delete a downloaded asset."""
    if update_service.delete_downloaded_asset(filename):
        return {"message": f"{filename} geloescht"}
    raise HTTPException(status_code=404, detail="Datei nicht gefunden")


@router.get("/updates/history")
async def get_update_history(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get the persisted update history."""
    history = await update_service.get_update_history(db)
    return {"history": history}


@router.get("/updates/notification")
async def get_update_notification(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get the cached background update check result for dashboard banner."""
    notification = await update_service.get_notification(db)
    if not notification:
        return {"update_available": False, "configured": bool(update_service.get_github_repo())}
    return notification


@router.post("/updates/notification/dismiss")
async def dismiss_update_notification(
    version: str = Query(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss the update notification for a specific version."""
    await update_service.dismiss_notification(db, version)
    return {"message": f"Benachrichtigung fuer v{version} ausgeblendet"}
