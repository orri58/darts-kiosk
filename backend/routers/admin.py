"""Admin Routes: Logs, Revenue, Health Monitoring, Setup Wizard, System Management, Reports, Reset"""
import io
import csv
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from typing import List, Optional
from pathlib import Path
import os

from backend.database import get_db
from backend.models import User, Board, Session, SessionCharge, AuditLog, SessionStatus, MatchResult, Player, Settings
from backend.schemas import AuditLogResponse, SessionResponse
from backend.dependencies import (
    get_current_user, require_admin, log_audit, DATA_DIR,
    get_active_session_for_board, get_or_create_setting
)
from backend.services.health_monitor import health_monitor
from backend.services.setup_wizard import (
    check_setup_status, complete_setup, SetupConfig, is_setup_complete
)
from backend.services.system_service import system_service
from backend.services.autodarts_desktop_service import autodarts_desktop
from backend.services.readiness_service import readiness_service
from backend.services.session_consistency_service import session_consistency_service

router = APIRouter()


async def _session_charge_totals(db: AsyncSession, session_ids: list[str]) -> dict[str, float]:
    if not session_ids:
        return {}
    result = await db.execute(
        select(SessionCharge.session_id, func.sum(SessionCharge.amount))
        .where(SessionCharge.session_id.in_(session_ids))
        .group_by(SessionCharge.session_id)
    )
    return {session_id: float(total or 0.0) for session_id, total in result.all()}


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
    """Get booked revenue for closed sessions in the last N days."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Session)
        .where(Session.started_at >= start_date)
        .where(Session.status.in_([SessionStatus.FINISHED.value, SessionStatus.EXPIRED.value, SessionStatus.CANCELLED.value]))
    )
    sessions = result.scalars().all()
    charge_totals = await _session_charge_totals(db, [s.id for s in sessions])

    boards_result = await db.execute(select(Board))
    boards_map = {board.id: board for board in boards_result.scalars().all()}

    by_date = {}
    by_board = {}
    total_revenue = 0.0
    total_sessions = 0

    for s in sessions:
        date_str = s.started_at.strftime("%Y-%m-%d") if s.started_at else "unknown"
        board = boards_map.get(s.board_id)
        board_name = board.name if board else (getattr(board, "board_id", None) or "Unknown")
        price_total = float(charge_totals.get(s.id, s.price_total or 0) or 0)

        bucket = by_date.setdefault(date_str, {"total": 0.0, "count": 0, "by_board": {}})
        bucket["total"] += price_total
        bucket["count"] += 1
        bucket["by_board"][board_name] = bucket["by_board"].get(board_name, 0.0) + price_total

        by_board[board_name] = by_board.get(board_name, 0.0) + price_total
        total_revenue += price_total
        total_sessions += 1

    return {
        "period_days": days,
        "total_revenue": total_revenue,
        "total_sessions": total_sessions,
        "by_date": by_date,
        "by_board": by_board,
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


@router.get("/system/version")
async def get_system_version():
    """Public version endpoint for update checks and health verification."""
    from backend.services.system_service import APP_VERSION
    return {"installed_version": APP_VERSION}


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
    if await is_setup_complete(db):
        raise HTTPException(status_code=403, detail="Setup already completed")
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


@router.get("/system/readiness")
async def get_system_readiness(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Operator-facing readiness/preflight snapshot for the local board PC."""
    return await readiness_service.build_readiness_snapshot(db)


@router.get("/system/support-snapshot")
async def get_support_snapshot(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Human-readable support snapshot that mirrors the support bundle contents."""
    from backend.routers.admin_agent import _agent_status_or_fallback

    agent_status = await _agent_status_or_fallback(db)
    return await readiness_service.build_support_snapshot(db, agent_status)


@router.get("/system/session-consistency")
async def get_session_consistency(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Runtime consistency diagnostics for board/session lifecycle mismatches."""
    return await session_consistency_service.build_snapshot(db)


@router.post("/system/session-consistency/repair/{board_id}")
async def repair_session_consistency(board_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Safe repair for common board/session lifecycle mismatches."""
    try:
        result = await session_consistency_service.repair_board(db, board_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Board not found")

    await log_audit(
        db,
        admin,
        action="session_consistency_repair",
        entity_type="board",
        entity_id=board_id,
        details={
            "board_id": board_id,
            "actions": result.get("actions", []),
            "cleanup_triggered": result.get("cleanup_triggered", False),
        },
    )
    return result


@router.get("/system/logs")
async def get_system_logs(lines: int = 200, admin: User = Depends(require_admin)):
    """Tail recent application logs"""
    return {"lines": system_service.tail_logs(lines)}


@router.get("/system/logs/bundle")
async def download_log_bundle(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Download a support bundle with logs plus core runtime snapshots."""
    from backend.routers.admin_agent import _agent_status_or_fallback
    agent_status = await _agent_status_or_fallback(db)
    snapshot = await readiness_service.build_support_snapshot(db, agent_status)
    extras = {
        "snapshot/system_info.json": snapshot["system_info"],
        "snapshot/health.json": snapshot["health"],
        "snapshot/setup_status.json": snapshot["setup_status"],
        "snapshot/readiness.json": snapshot["readiness"],
        "snapshot/agent_status.json": snapshot["agent_status"],
        "snapshot/downloaded_assets.json": snapshot["downloaded_assets"],
        "snapshot/app_backups.json": snapshot["app_backups"],
        "snapshot/update_result.json": snapshot["update_result"],
        "snapshot/secrets_status.json": snapshot["secrets_status"],
    }

    bundle = system_service.create_log_bundle(extras)
    if not bundle:
        raise HTTPException(status_code=500, detail="Failed to create support bundle")

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    return StreamingResponse(
        bundle,
        media_type="application/gzip",
        headers={"Content-Disposition": f"attachment; filename=darts-support_{timestamp}.tar.gz"}
    )


# ===================================================================
# Reports / Accounting Export
# ===================================================================

@router.get("/reports/sessions")
async def get_sessions_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    board_id: Optional[str] = Query(None),
    pricing_mode: Optional[str] = Query(None),
    preset: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get session report with filters. Returns JSON."""
    query = select(Session).order_by(Session.started_at.desc())

    now = datetime.now(timezone.utc)
    if preset == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.where(Session.started_at >= start)
    elif preset == "week":
        query = query.where(Session.started_at >= now - timedelta(days=7))
    elif preset == "month":
        query = query.where(Session.started_at >= now - timedelta(days=30))
    else:
        if date_from:
            try:
                dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
                query = query.where(Session.started_at >= dt)
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                query = query.where(Session.started_at <= dt)
            except ValueError:
                pass

    if pricing_mode:
        query = query.where(Session.pricing_mode == pricing_mode)

    result = await db.execute(query)
    sessions = result.scalars().all()
    charge_totals = await _session_charge_totals(db, [s.id for s in sessions])

    # Load boards for name lookup
    boards_result = await db.execute(select(Board))
    boards_map = {b.id: b for b in boards_result.scalars().all()}

    if board_id:
        board_obj = next((b for b in boards_map.values() if b.board_id == board_id), None)
        if board_obj:
            sessions = [s for s in sessions if s.board_id == board_obj.id]

    # Load user lookup
    users_result = await db.execute(select(User))
    users_map = {u.id: u.username for u in users_result.scalars().all()}

    rows = []
    total_revenue = 0.0
    revenue_by_board = {}

    for s in sessions:
        board = boards_map.get(s.board_id)
        board_name = board.name if board else "?"
        board_bid = board.board_id if board else "?"
        created_by = users_map.get(s.unlocked_by_user_id, "-")

        booked_total = float(charge_totals.get(s.id, s.price_total or 0) or 0)
        revenue_by_board[board_name] = revenue_by_board.get(board_name, 0) + booked_total
        total_revenue += booked_total

        rows.append({
            "date": s.started_at.isoformat() if s.started_at else "",
            "board": board_name,
            "board_id": board_bid,
            "session_id": s.id,
            "pricing_mode": s.pricing_mode,
            "price_total": booked_total,
            "credits_total": s.credits_total,
            "credits_remaining": s.credits_remaining,
            "minutes_total": s.minutes_total,
            "players_count": s.players_count,
            "status": s.status,
            "ended_reason": s.ended_reason or "",
            "created_by": created_by,
        })

    count = len(rows)
    avg = round(total_revenue / count, 2) if count > 0 else 0

    return {
        "sessions": rows,
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "session_count": count,
            "average_per_session": avg,
            "revenue_by_board": revenue_by_board,
        },
    }


@router.get("/reports/sessions/csv")
async def export_sessions_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    board_id: Optional[str] = Query(None),
    pricing_mode: Optional[str] = Query(None),
    preset: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Export sessions as CSV for bookkeeping."""
    report = await get_sessions_report(date_from, date_to, board_id, pricing_mode, preset, admin, db)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow(["Datum", "Board", "Board-ID", "Session-ID", "Modus", "Preis", "Credits", "Credits Rest", "Minuten", "Spieler", "Status", "Beendet Grund", "Erstellt von"])
    for row in report["sessions"]:
        writer.writerow([
            row["date"], row["board"], row["board_id"], row["session_id"],
            row["pricing_mode"], row["price_total"], row["credits_total"],
            row["credits_remaining"], row["minutes_total"], row["players_count"],
            row["status"], row["ended_reason"], row["created_by"],
        ])

    writer.writerow([])
    writer.writerow(["Zusammenfassung"])
    s = report["summary"]
    writer.writerow(["Umsatz gesamt", s["total_revenue"]])
    writer.writerow(["Anzahl Sessions", s["session_count"]])
    writer.writerow(["Durchschnitt/Session", s["average_per_session"]])
    for board_name, rev in s["revenue_by_board"].items():
        writer.writerow([f"Umsatz {board_name}", round(rev, 2)])

    output.seek(0)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=darts-report-{timestamp}.csv"},
    )


# ===================================================================
# Reset / Delete Controls
# ===================================================================

@router.delete("/admin/player/{player_id}/stats")
async def reset_player_stats(player_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Reset stats for a single player."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    player.games_played = 0
    player.games_won = 0
    player.last_played_at = None
    await db.flush()
    await log_audit(db, admin, "reset_player_stats", "player", player_id)
    return {"message": f"Stats reset for {player.nickname}", "player_id": player_id}


@router.delete("/admin/players/guests")
async def reset_all_guest_stats(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Delete all guest (non-registered) players."""
    result = await db.execute(select(Player).where(Player.is_registered.is_(False)))
    guests = result.scalars().all()
    count = len(guests)
    for g in guests:
        await db.delete(g)
    await db.flush()
    await log_audit(db, admin, "reset_all_guest_stats", "players", f"deleted {count} guests")
    return {"message": f"{count} guest players deleted", "count": count}


@router.delete("/admin/players/all-stats")
async def reset_all_player_stats(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Reset stats for ALL players (guests + registered). Does not delete registered players."""
    result = await db.execute(select(Player))
    players = result.scalars().all()
    count = 0
    for p in players:
        p.games_played = 0
        p.games_won = 0
        p.last_played_at = None
        count += 1
    await db.flush()
    await log_audit(db, admin, "reset_all_player_stats", "players", f"reset {count} players")
    return {"message": f"Stats reset for {count} players", "count": count}


@router.delete("/admin/matches")
async def delete_match_history(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete match history by date range. If no range, deletes ALL."""
    query = select(MatchResult)
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            query = query.where(MatchResult.played_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
            query = query.where(MatchResult.played_at <= dt)
        except ValueError:
            pass

    result = await db.execute(query)
    matches = result.scalars().all()
    count = len(matches)
    for m in matches:
        await db.delete(m)
    await db.flush()
    await log_audit(db, admin, "delete_match_history", "matches", f"deleted {count} matches")
    return {"message": f"{count} match results deleted", "count": count}


# ===================================================================
# Branding: Remove Logo
# ===================================================================

@router.delete("/settings/branding/logo")
async def remove_branding_logo(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Remove the uploaded logo and clear logo_url in branding settings."""
    from backend.dependencies import ASSETS_DIR

    result = await db.execute(select(Settings).where(Settings.key == "branding"))
    setting = result.scalar_one_or_none()
    if not setting:
        return {"message": "No branding settings found"}

    branding = dict(setting.value or {})  # copy the dict to break the reference
    logo_url = branding.get("logo_url", "")

    if logo_url:
        filename = logo_url.split("/")[-1]
        filepath = ASSETS_DIR / filename
        if filepath.exists():
            filepath.unlink()

    branding["logo_url"] = None
    setting.value = branding
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(setting, "value")
    await db.flush()
    await log_audit(db, admin, "remove_logo", "settings", "branding")
    return {"message": "Logo removed", "branding": branding}


# ===================================================================
# Autodarts Desktop Supervision (v3.2.0, enhanced v3.3.1)
# ===================================================================

@router.get("/admin/system/autodarts-desktop-status")
async def get_autodarts_desktop_status(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Get current status of Autodarts Desktop application (enhanced v3.3.1)."""
    from backend.models import DEFAULT_AUTODARTS_DESKTOP
    config = await get_or_create_setting(db, "autodarts_desktop", DEFAULT_AUTODARTS_DESKTOP)
    return autodarts_desktop.get_status(config=config)


@router.post("/admin/system/restart-autodarts-desktop")
async def restart_autodarts_desktop(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Restart the Autodarts Desktop application."""
    import asyncio
    from backend.models import DEFAULT_AUTODARTS_DESKTOP
    setting = await get_or_create_setting(db, "autodarts_desktop", DEFAULT_AUTODARTS_DESKTOP)
    exe_path = setting.get("exe_path", "")
    if not exe_path:
        raise HTTPException(status_code=400, detail="Autodarts exe_path not configured")
    result = await asyncio.to_thread(autodarts_desktop.restart_process, exe_path)
    await log_audit(db, admin, "restart_autodarts_desktop", "system", "autodarts_desktop",
                    details={"exe_path": exe_path, "result": result})
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result


@router.post("/admin/system/ensure-autodarts-desktop")
async def ensure_autodarts_desktop(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """One-shot ensure Autodarts Desktop is running. For wake/recovery."""
    import asyncio
    from backend.models import DEFAULT_AUTODARTS_DESKTOP
    setting = await get_or_create_setting(db, "autodarts_desktop", DEFAULT_AUTODARTS_DESKTOP)
    exe_path = setting.get("exe_path", "")
    if not exe_path:
        return {"action_taken": "skipped", "was_running_before": False,
                "running_after": False, "pid_after": None,
                "message": "Autodarts exe_path nicht konfiguriert"}
    result = await asyncio.to_thread(autodarts_desktop.ensure_desktop_ready, exe_path)
    await log_audit(db, admin, "ensure_autodarts_desktop", "system", "autodarts_desktop",
                    details={"result": result})
    return result


# ===================================================================
# System Controls (v3.3.1)
# ===================================================================

@router.post("/admin/system/restart-backend")
async def restart_backend(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Schedule graceful backend restart. Returns immediately."""
    from backend.services.system_control_service import system_control
    result = await system_control.restart_backend()
    await log_audit(db, admin, "restart_backend", "system", "backend", details=result)
    return result


@router.post("/admin/system/reboot-os")
async def reboot_os(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Trigger OS reboot. Windows only."""
    from backend.services.system_control_service import system_control
    result = await system_control.reboot_os()
    await log_audit(db, admin, "reboot_os", "system", "os", details=result)
    if not result.get("accepted") and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/admin/system/shutdown-os")
async def shutdown_os(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Trigger OS shutdown. Windows only."""
    from backend.services.system_control_service import system_control
    result = await system_control.shutdown_os()
    await log_audit(db, admin, "shutdown_os", "system", "os", details=result)
    if not result.get("accepted") and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
