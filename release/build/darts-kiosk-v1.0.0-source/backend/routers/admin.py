"""Admin Routes: Logs, Revenue, Health Monitoring, Setup Wizard, System Management"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pathlib import Path
import os

from backend.database import get_db
from backend.models import User, Board, Session, AuditLog, SessionStatus
from backend.schemas import AuditLogResponse, SessionResponse
from backend.dependencies import (
    get_current_user, require_admin, log_audit, DATA_DIR,
    get_active_session_for_board
)
from backend.services.health_monitor import health_monitor
from backend.services.setup_wizard import (
    check_setup_status, complete_setup, SetupConfig
)
from backend.services.system_service import system_service

router = APIRouter()


# ===== Audit Logs =====

@router.get("/logs/audit", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        query = query.where(AuditLog.action == action)

    result = await db.execute(query)
    logs = result.scalars().all()
    return [AuditLogResponse(
        id=log.id, username=log.username, action=log.action, entity_type=log.entity_type,
        entity_id=log.entity_id, details=log.details, created_at=log.created_at
    ) for log in logs]


@router.get("/logs/sessions")
async def get_session_logs(
    limit: int = 100,
    board_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Session).order_by(Session.started_at.desc()).limit(limit)
    if board_id:
        result = await db.execute(select(Board).where(Board.board_id == board_id))
        board = result.scalar_one_or_none()
        if board:
            query = query.where(Session.board_id == board.id)

    result = await db.execute(query)
    sessions = result.scalars().all()
    return [SessionResponse(
        id=s.id, board_id=s.board_id, pricing_mode=s.pricing_mode,
        game_type=s.game_type, credits_total=s.credits_total,
        credits_remaining=s.credits_remaining, minutes_total=s.minutes_total,
        price_total=s.price_total, started_at=s.started_at,
        expires_at=s.expires_at, ended_at=s.ended_at,
        players_count=s.players_count, players=s.players or [],
        status=s.status
    ) for s in sessions]


# ===== Revenue =====

@router.get("/revenue/summary")
async def get_revenue_summary(
    days: int = 7,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get revenue summary for the last N days"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Session)
        .where(Session.started_at >= start_date)
        .where(Session.status.in_([SessionStatus.FINISHED.value, SessionStatus.EXPIRED.value, SessionStatus.CANCELLED.value]))
    )
    sessions = result.scalars().all()

    by_date = {}
    for s in sessions:
        date_str = s.started_at.strftime("%Y-%m-%d")
        if date_str not in by_date:
            by_date[date_str] = {"total": 0.0, "count": 0, "by_board": {}}
        by_date[date_str]["total"] += s.price_total
        by_date[date_str]["count"] += 1

    return {
        "period_days": days,
        "total_revenue": sum(d["total"] for d in by_date.values()),
        "total_sessions": sum(d["count"] for d in by_date.values()),
        "by_date": by_date
    }


# ===== Root & Health =====

@router.get("/")
async def root():
    MODE = os.environ.get('MODE', 'MASTER')
    return {"message": "Darts Kiosk System API", "mode": MODE}


@router.get("/health")
async def health():
    MODE = os.environ.get('MODE', 'MASTER')
    return {"status": "healthy", "mode": MODE}


# ===== Health Monitoring =====

@router.get("/health/detailed")
async def get_detailed_health(admin: User = Depends(require_admin)):
    """Get detailed system health status"""
    from dataclasses import asdict
    health_data = health_monitor.get_health()
    return asdict(health_data)


@router.get("/health/screenshot/{filename}")
async def get_error_screenshot(filename: str, admin: User = Depends(require_admin)):
    """Get an error screenshot"""
    screenshots_dir = DATA_DIR / 'autodarts_debug'
    filepath = screenshots_dir / filename

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    if not str(filepath.resolve()).startswith(str(screenshots_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(filepath, media_type="image/png")


@router.get("/health/screenshots")
async def list_error_screenshots(admin: User = Depends(require_admin)):
    """List all error screenshots"""
    return health_monitor.get_error_screenshots()


# ===== Setup Wizard =====

@router.get("/setup/status")
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Check if first-run setup is needed"""
    return await check_setup_status(db)


@router.post("/setup/complete")
async def complete_first_setup(config: SetupConfig, db: AsyncSession = Depends(get_db)):
    """Complete first-run setup with secure credentials"""
    if len(config.admin_password) < 8:
        raise HTTPException(status_code=400, detail="Admin password must be at least 8 characters")
    if len(config.staff_pin) != 4 or not config.staff_pin.isdigit():
        raise HTTPException(status_code=400, detail="Staff PIN must be exactly 4 digits")

    results = await complete_setup(db, config)
    return {
        "success": True,
        "results": results,
        "restart_required": results.get("secrets_generated", False),
        "message": "Setup complete. Please restart the server if new secrets were generated."
    }


# ===== System Management =====

@router.get("/system/info")
async def get_system_info(admin: User = Depends(require_admin)):
    """Get system information: version, uptime, disk, OS"""
    return system_service.get_system_info()


@router.get("/system/logs")
async def get_system_logs(lines: int = 200, admin: User = Depends(require_admin)):
    """Tail recent application logs"""
    return {"lines": system_service.tail_logs(lines)}


@router.get("/system/logs/bundle")
async def download_log_bundle(admin: User = Depends(require_admin)):
    """Download all logs as a gzipped tar archive"""
    bundle = system_service.create_log_bundle()
    if not bundle:
        raise HTTPException(status_code=500, detail="Failed to create log bundle")

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    return StreamingResponse(
        bundle,
        media_type="application/gzip",
        headers={"Content-Disposition": f"attachment; filename=darts-logs_{timestamp}.tar.gz"}
    )
