"""Update Routes — GitHub-based update system with download, history, rollback"""
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import User
from backend.dependencies import require_admin, log_audit
from backend.services.update_service import update_service
from backend.services.updater_service import updater_service

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
    """Permanently dismiss the update notification for a specific version."""
    await update_service.dismiss_notification(db, version)
    return {"message": f"Benachrichtigung fuer v{version} ausgeblendet"}


@router.post("/updates/notification/snooze")
async def snooze_update_notification(
    version: str = Query(...),
    hours: int = Query(default=48),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Snooze the update notification for a number of hours (default 48)."""
    await update_service.snooze_notification(db, version, hours)
    return {"message": f"Erinnerung fuer v{version} in {hours}h", "snooze_hours": hours}



# ═══════════════════════════════════════════════════════════════
# App Backup Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/updates/backups")
async def list_app_backups(admin: User = Depends(require_admin)):
    """List all full application backups."""
    return {"backups": updater_service.list_app_backups()}


@router.post("/updates/backups/create")
async def create_app_backup(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a full application backup (backend + frontend + scripts + VERSION)."""
    result = updater_service.create_app_backup()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Backup fehlgeschlagen"))

    await update_service.record_update_event(db, {
        "action": "app_backup_created",
        "filename": result["filename"],
        "size_bytes": result["size_bytes"],
    })
    await log_audit(db, admin, "create_app_backup", "system", "backup", {"filename": result["filename"]})
    return result


@router.delete("/updates/backups/{filename}")
async def delete_app_backup(filename: str, admin: User = Depends(require_admin)):
    """Delete a specific application backup."""
    if updater_service.delete_app_backup(filename):
        return {"message": f"Backup {filename} geloescht"}
    raise HTTPException(status_code=404, detail="Backup nicht gefunden")


# ═══════════════════════════════════════════════════════════════
# Install & Rollback Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/updates/install")
async def install_update(
    asset_filename: str = Query(..., description="Downloaded zip filename"),
    target_version: str = Query(..., description="Version to install"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Full install pipeline:
    1. Create app backup
    2. Extract & validate the downloaded asset
    3. Write update manifest
    4. Launch external updater process
    """
    # Step 1: Create backup
    backup_result = updater_service.create_app_backup()
    if not backup_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Backup fehlgeschlagen: {backup_result.get('error')}")

    # Step 2: Find the downloaded asset
    downloads = update_service.list_downloaded_assets()
    asset = next((a for a in downloads if a["filename"] == asset_filename), None)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Download nicht gefunden: {asset_filename}")

    # Step 3: Extract & validate
    validation = updater_service.extract_and_validate(asset["path"], target_version)
    if not validation.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=f"Paket ungueltig: {', '.join(validation.get('errors', []))}",
        )

    # Step 4: Write manifest
    manifest_result = updater_service.write_manifest(
        staging_dir=validation["staging_dir"],
        backup_path=backup_result["path"],
        target_version=target_version,
    )

    # Step 5: Record event
    await update_service.record_update_event(db, {
        "action": "install_started",
        "target_version": target_version,
        "backup_filename": backup_result["filename"],
        "asset_filename": asset_filename,
    })
    await log_audit(db, admin, "install_update", "system", "update", {"target_version": target_version})

    # Step 6: Launch updater
    launch_result = updater_service.launch_updater()

    return {
        "status": "update_started",
        "message": f"Update auf v{target_version} gestartet",
        "backup": backup_result["filename"],
        "updater_launched": launch_result.get("launched", False),
        "manifest": manifest_result["manifest"],
        "note": "Das System wird jetzt aktualisiert. Die Seite laedt automatisch neu, wenn das Update abgeschlossen ist.",
    }


@router.post("/updates/rollback")
async def rollback_update(
    backup_filename: str = Query(..., description="Backup filename to restore from"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Rollback to a previous version using an app backup.
    Writes a rollback manifest and launches the external updater.
    """
    # Find the backup
    backups = updater_service.list_app_backups()
    backup = next((b for b in backups if b["filename"] == backup_filename), None)
    if not backup:
        raise HTTPException(status_code=404, detail=f"Backup nicht gefunden: {backup_filename}")

    from backend.services.updater_service import APP_BACKUPS_DIR
    backup_path = str(APP_BACKUPS_DIR / backup_filename)

    # Write rollback manifest
    updater_service.write_rollback_manifest(backup_path=backup_path)

    await update_service.record_update_event(db, {
        "action": "rollback_started",
        "backup_filename": backup_filename,
    })
    await log_audit(db, admin, "rollback", "system", "update", {"backup": backup_filename})

    # Launch updater
    launch_result = updater_service.launch_updater()

    return {
        "status": "rollback_started",
        "message": f"Rollback gestartet mit Backup: {backup_filename}",
        "updater_launched": launch_result.get("launched", False),
    }


@router.get("/updates/result")
async def get_update_result(admin: User = Depends(require_admin)):
    """
    Get the result of the last update/rollback operation.
    Written by the external updater.py after completion.
    """
    result = updater_service.get_update_result()
    if not result:
        return {"has_result": False}
    return {"has_result": True, "result": result}


@router.post("/updates/result/clear")
async def clear_update_result(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Clear the update result (acknowledge it was seen)."""
    result = updater_service.get_update_result()
    if result:
        await update_service.record_update_event(db, {
            "action": "update_result_acknowledged",
            "success": result.get("success"),
            "target_version": result.get("target_version"),
            "rolled_back": result.get("rolled_back"),
        })
    updater_service.clear_update_result()
    updater_service.cleanup_staging()
    return {"message": "Update-Ergebnis bestaetigt"}