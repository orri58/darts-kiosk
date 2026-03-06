"""Backup Routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import FileResponse

from backend.database import get_db
from backend.models import User
from backend.dependencies import require_admin, log_audit
from backend.services.backup_service import backup_service

router = APIRouter()


@router.get("/backups")
async def list_backups(admin: User = Depends(require_admin)):
    """List all available backups"""
    backups = backup_service.list_backups()
    return {
        "backups": [
            {
                "filename": b.filename,
                "size_bytes": b.size_bytes,
                "size_mb": round(b.size_bytes / (1024 * 1024), 2),
                "created_at": b.created_at.isoformat(),
                "compressed": b.compressed
            }
            for b in backups
        ],
        "stats": backup_service.get_backup_stats()
    }


@router.post("/backups/create")
async def create_backup(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Create a new backup immediately"""
    backup = backup_service.create_backup()
    if not backup:
        raise HTTPException(status_code=500, detail="Backup creation failed")

    await log_audit(db, admin, "create_backup", "backup", backup.filename)

    return {
        "success": True,
        "backup": {
            "filename": backup.filename,
            "size_bytes": backup.size_bytes,
            "created_at": backup.created_at.isoformat()
        }
    }


@router.get("/backups/download/{filename}")
async def download_backup(filename: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Download a backup file"""
    backup_path = backup_service.get_backup_path(filename)

    if not backup_path:
        raise HTTPException(status_code=404, detail="Backup not found")

    await log_audit(db, admin, "download_backup", "backup", filename)

    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename=filename
    )


@router.post("/backups/restore/{filename}")
async def restore_backup(filename: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Restore database from a backup (requires restart)"""
    success = backup_service.restore_backup(filename)

    if not success:
        raise HTTPException(status_code=500, detail="Restore failed")

    await log_audit(db, admin, "restore_backup", "backup", filename)

    return {
        "success": True,
        "message": "Database restored. Please restart the server.",
        "restart_required": True
    }


@router.delete("/backups/{filename}")
async def delete_backup(filename: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Delete a backup file"""
    success = backup_service.delete_backup(filename)

    if not success:
        raise HTTPException(status_code=404, detail="Backup not found")

    await log_audit(db, admin, "delete_backup", "backup", filename)

    return {"success": True, "message": "Backup deleted"}
