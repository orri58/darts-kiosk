"""Update Routes — GitHub-based update system"""
from fastapi import APIRouter, Depends, HTTPException, Query
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
async def get_update_status(admin: User = Depends(require_admin)):
    """Get current version and cached release info."""
    return {
        "current_version": update_service.get_current_version(),
        "github_repo": update_service.get_github_repo(),
        "update_history": update_service.get_update_history(10),
    }


@router.post("/updates/prepare")
async def prepare_update(
    target_version: str = Query(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create backup and prepare update instructions for a target version."""
    result = await update_service.prepare_update(target_version)
    await log_audit(db, admin, "prepare_update", "system", "update", {"target_version": target_version})
    return result
