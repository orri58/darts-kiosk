import asyncio
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, PROJECT_ROOT
from backend.dependencies import get_or_create_setting, log_audit, require_admin
from backend.models import DEFAULT_AUTODARTS_DESKTOP, User
from backend.services.agent_client import agent_client
from backend.services.autodarts_desktop_service import autodarts_desktop
from backend.services.system_control_service import system_control
from backend.services.windows_kiosk_control_service import windows_kiosk_control

router = APIRouter()

IS_WINDOWS = platform.system() == "Windows"
_AGENT_SETUP_SCRIPT = PROJECT_ROOT / "agent" / "setup_autostart.py"
_DEFAULT_KIOSK_SHELL = PROJECT_ROOT / "kiosk" / "kiosk_shell.vbs"


class ShellSwitchRequest(BaseModel):
    target: str


class TaskManagerRequest(BaseModel):
    enabled: bool


async def _autodarts_config(db: AsyncSession) -> dict:
    return await get_or_create_setting(db, "autodarts_desktop", DEFAULT_AUTODARTS_DESKTOP)


def _normalize_task_manager_status(status: dict) -> dict:
    disabled = status.get("disabled")
    if disabled is None:
        disabled = status.get("task_manager_disabled", False)
    status["disabled"] = disabled
    status.setdefault("task_manager_disabled", disabled)
    return status


def _detect_kiosk_shell_path() -> str:
    env_path = os.environ.get("KIOSK_SHELL_PATH", "")
    for candidate in (
        env_path,
        str(_DEFAULT_KIOSK_SHELL),
    ):
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return str(_DEFAULT_KIOSK_SHELL)


async def _fallback_status(db: AsyncSession) -> dict:
    config = await _autodarts_config(db)

    try:
        from agent.darts_agent import detect_kiosk_window, get_autostart_status
        kiosk_window = detect_kiosk_window()
        autostart = get_autostart_status()
    except Exception as exc:
        kiosk_window = {"detected": False, "error": str(exc), "reason": "fallback_import_failed"}
        autostart = {"supported": IS_WINDOWS, "registered": False, "error": str(exc)}

    shell = windows_kiosk_control.get_shell_status(_detect_kiosk_shell_path())
    task_manager = _normalize_task_manager_status(windows_kiosk_control.get_task_manager_status())

    return {
        "agent_online": False,
        "agent_version": None,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "is_windows": IS_WINDOWS,
        "autodarts": autodarts_desktop.get_status(config=config),
        "kiosk_window": kiosk_window,
        "shell": shell,
        "task_manager": task_manager,
        "autostart": autostart,
        "source": "fallback",
        "configured": agent_client.is_configured(),
    }


async def _agent_status_or_fallback(db: AsyncSession) -> dict:
    status = await agent_client.get_status() if agent_client.is_configured() else None
    if status:
        status["source"] = "agent"
        if "task_manager" in status:
            status["task_manager"] = _normalize_task_manager_status(status["task_manager"])
        return status
    return await _fallback_status(db)


async def _local_autodarts_ensure(db: AsyncSession) -> dict:
    config = await _autodarts_config(db)
    exe_path = config.get("exe_path", "")
    if not exe_path:
        return {
            "action_taken": "skipped",
            "running_after": False,
            "pid_after": None,
            "message": "Autodarts exe_path nicht konfiguriert",
            "via": "fallback",
        }
    result = await asyncio.to_thread(autodarts_desktop.ensure_desktop_ready, exe_path)
    result["via"] = "fallback"
    return result


async def _local_autodarts_restart(db: AsyncSession) -> dict:
    config = await _autodarts_config(db)
    exe_path = config.get("exe_path", "")
    if not exe_path:
        raise HTTPException(status_code=400, detail="Autodarts exe_path not configured")
    result = await asyncio.to_thread(autodarts_desktop.restart_process, exe_path)
    result["via"] = "fallback"
    return result


def _task_manager_action(enabled: bool) -> dict:
    result = windows_kiosk_control.enable_task_manager() if enabled else windows_kiosk_control.disable_task_manager()
    result["via"] = "fallback"
    return result


@router.get("/admin/agent/status")
async def get_agent_status(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _agent_status_or_fallback(db)


@router.post("/admin/agent/autodarts/ensure")
async def ensure_autodarts(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await agent_client.ensure_autodarts() if agent_client.is_configured() else None
    if result is not None:
        result["via"] = "agent"
    else:
        result = await _local_autodarts_ensure(db)
    await log_audit(db, admin, "ensure_autodarts_desktop", "system", "autodarts_desktop", details=result)
    return result


@router.post("/admin/agent/autodarts/restart")
async def restart_autodarts(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await agent_client.restart_autodarts() if agent_client.is_configured() else None
    if result is not None:
        result["via"] = "agent"
    else:
        result = await _local_autodarts_restart(db)
    await log_audit(db, admin, "restart_autodarts_desktop", "system", "autodarts_desktop", details=result)
    if not result.get("success", True) and not result.get("running_after"):
        raise HTTPException(status_code=500, detail=result.get("error") or result.get("message") or "Autodarts restart failed")
    return result


@router.post("/admin/agent/system/restart-backend")
async def restart_backend(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await agent_client.restart_backend() if agent_client.is_configured() else None
    if result is not None:
        result["via"] = "agent"
    else:
        result = await system_control.restart_backend()
        result["via"] = "fallback"
    await log_audit(db, admin, "restart_backend", "system", "backend", details=result)
    return result


@router.post("/admin/agent/system/reboot")
async def reboot_os(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await agent_client.reboot_os() if agent_client.is_configured() else None
    if result is not None:
        result["via"] = "agent"
    else:
        result = await system_control.reboot_os()
        result["via"] = "fallback"
    await log_audit(db, admin, "reboot_os", "system", "os", details=result)
    if not result.get("accepted") and not result.get("success") and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/admin/agent/system/shutdown")
async def shutdown_os(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await agent_client.shutdown_os() if agent_client.is_configured() else None
    if result is not None:
        result["via"] = "agent"
    else:
        result = await system_control.shutdown_os()
        result["via"] = "fallback"
    await log_audit(db, admin, "shutdown_os", "system", "os", details=result)
    if not result.get("accepted") and not result.get("success") and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/admin/agent/kiosk/shell/switch")
async def switch_shell(payload: ShellSwitchRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target = (payload.target or "").strip().lower()
    if target not in {"explorer", "kiosk"}:
        raise HTTPException(status_code=400, detail="target must be explorer or kiosk")

    if agent_client.is_configured():
        agent_target = "explorer" if target == "explorer" else _detect_kiosk_shell_path()
        result = await agent_client.switch_shell(agent_target)
        if result is not None:
            result["via"] = "agent"
            await log_audit(db, admin, "switch_shell", "system", "windows_shell", details={"target": target, **result})
            return result

    if target == "explorer":
        result = windows_kiosk_control.switch_to_explorer()
    else:
        kiosk_shell_path = _detect_kiosk_shell_path()
        if not Path(kiosk_shell_path).exists():
            raise HTTPException(status_code=400, detail=f"Kiosk shell not found: {kiosk_shell_path}")
        result = windows_kiosk_control.switch_to_kiosk(kiosk_shell_path)

    result["via"] = "fallback"
    await log_audit(db, admin, "switch_shell", "system", "windows_shell", details={"target": target, **result})
    if not result.get("success") and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/admin/agent/kiosk/taskmanager/set")
async def set_task_manager(payload: TaskManagerRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await agent_client.set_task_manager(payload.enabled) if agent_client.is_configured() else None
    if result is not None:
        result["via"] = "agent"
    else:
        result = _task_manager_action(payload.enabled)

    await log_audit(db, admin, "set_task_manager", "system", "task_manager", details={"enabled": payload.enabled, **result})
    if not result.get("success") and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


async def _run_autostart_setup(remove: bool) -> dict:
    if not IS_WINDOWS:
        return {"success": False, "supported": False, "error": "Nur auf Windows verfügbar"}
    if not _AGENT_SETUP_SCRIPT.exists():
        return {"success": False, "supported": True, "error": f"Script nicht gefunden: {_AGENT_SETUP_SCRIPT}"}

    cmd = [sys.executable, str(_AGENT_SETUP_SCRIPT)]
    if remove:
        cmd.append("--remove")

    proc = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_AGENT_SETUP_SCRIPT.parent),
    )
    return {
        "success": proc.returncode == 0,
        "supported": True,
        "removed": remove,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "command": cmd,
        "via": "fallback",
    }


@router.post("/admin/agent/autostart/register")
async def register_autostart(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await _run_autostart_setup(remove=False)
    await log_audit(db, admin, "register_agent_autostart", "system", "agent_autostart", details=result)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("stderr") or result.get("error") or "Autostart registration failed")
    return result


@router.post("/admin/agent/autostart/remove")
async def remove_autostart(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await _run_autostart_setup(remove=True)
    await log_audit(db, admin, "remove_agent_autostart", "system", "agent_autostart", details=result)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("stderr") or result.get("error") or "Autostart removal failed")
    return result
