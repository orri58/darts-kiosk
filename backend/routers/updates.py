"""Update & Rollback Routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, Board
from dependencies import require_admin, log_audit
from services.update_service import update_service

router = APIRouter()


@router.get("/updates/status")
async def get_update_status(admin: User = Depends(require_admin)):
    """Get current version and available updates"""
    return {
        "current_version": update_service.get_current_version(),
        "available_versions": [
            {
                "version": v.version,
                "tag": v.tag,
                "is_current": v.is_current,
                "is_stable": v.is_stable
            }
            for v in update_service.get_available_versions()
        ],
        "update_history": update_service.get_update_history(10)
    }


@router.post("/updates/agent/{board_id}")
async def update_agent(board_id: str, target_version: str = "latest", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Update a specific agent to a new version"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()

    if not board or not board.agent_api_base_url:
        raise HTTPException(status_code=404, detail="Board or agent URL not found")

    update_result = await update_service.update_agent(board_id, board.agent_api_base_url, target_version)

    await log_audit(db, admin, "update_agent", "board", board_id, {
        "target_version": target_version,
        "success": update_result.success
    })

    return {
        "success": update_result.success,
        "message": update_result.message,
        "details": {
            "board_id": update_result.board_id,
            "old_version": update_result.old_version,
            "new_version": update_result.new_version
        }
    }


@router.post("/updates/all-agents")
async def update_all_agents(target_version: str = "latest", admin: User = Depends(require_admin)):
    """Update all registered agents"""
    results = await update_service.update_all_agents(target_version)

    return {
        "total": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [
            {
                "board_id": r.board_id,
                "success": r.success,
                "message": r.message
            }
            for r in results
        ]
    }


@router.post("/updates/local")
async def update_local(target_version: str = "latest", admin: User = Depends(require_admin)):
    """Get instructions for local update"""
    return update_service.trigger_local_update(target_version)


@router.post("/updates/rollback/{board_id}")
async def rollback_agent(board_id: str, target_version: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Rollback an agent to a previous version"""
    result = await db.execute(select(Board).where(Board.board_id == board_id))
    board = result.scalar_one_or_none()

    if not board or not board.agent_api_base_url:
        raise HTTPException(status_code=404, detail="Board or agent URL not found")

    rollback_result = await update_service.rollback_agent(board_id, board.agent_api_base_url, target_version)

    return {
        "success": rollback_result.success,
        "message": rollback_result.message
    }
