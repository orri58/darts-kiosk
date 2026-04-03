"""Operator-facing readiness and support snapshot helpers.

These helpers intentionally stay local-first and practical:
- summarize whether a board PC is actually ready to operate
- expose the checks an operator/support person will ask about first
- reuse existing setup/health/update services instead of inventing new flows
"""
from __future__ import annotations

import os
import platform
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import DATA_DIR, DATABASE_PATH, PROJECT_ROOT
from backend.models import Board, DEFAULT_AUTODARTS_DESKTOP, Settings
from backend.runtime_features import AUTODARTS_MODE, observer_mode_requires_target
from backend.services.health_monitor import SCREENSHOTS_DIR, health_monitor
from backend.services.setup_wizard import (
    BACKEND_ENV_FILE,
    FRONTEND_ENV_FILE,
    SECRETS_FILE,
    SETUP_FLAG_FILE,
    check_setup_status,
    get_stored_secrets,
)
from backend.services.system_service import LOGS_DIR, system_service
from backend.services.update_service import update_service
from backend.services.updater_service import updater_service

_FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "build"
_VERSION_FILE = PROJECT_ROOT / "VERSION"


class ReadinessService:
    def _add_check(
        self,
        checks: List[Dict[str, Any]],
        *,
        group: str,
        key: str,
        label: str,
        status: str,
        detail: str,
        remediation: str | None = None,
    ) -> None:
        checks.append(
            {
                "group": group,
                "key": key,
                "label": label,
                "status": status,
                "detail": detail,
                "remediation": remediation,
            }
        )

    async def _autodarts_desktop_config(self, db: AsyncSession) -> dict:
        result = await db.execute(select(Settings).where(Settings.key == "autodarts_desktop"))
        row = result.scalar_one_or_none()
        value = row.value if row and isinstance(row.value, dict) else {}
        return {**DEFAULT_AUTODARTS_DESKTOP, **value}

    async def build_readiness_snapshot(self, db: AsyncSession) -> dict:
        setup = await check_setup_status(db)
        stored_secrets = get_stored_secrets()
        local_board_id = (os.environ.get("BOARD_ID") or os.environ.get("LOCAL_BOARD_ID") or "BOARD-1").strip()

        boards_result = await db.execute(select(Board).order_by(Board.is_master.desc(), Board.created_at.asc()))
        boards = boards_result.scalars().all()
        board = next((item for item in boards if item.board_id == local_board_id), None)

        desktop_cfg = await self._autodarts_desktop_config(db)
        desktop_exe = (desktop_cfg.get("exe_path") or "").strip()
        desktop_exe_exists = Path(desktop_exe).exists() if desktop_exe else False
        is_windows = platform.system() == "Windows"

        db_exists = DATABASE_PATH.exists()
        db_size_bytes = DATABASE_PATH.stat().st_size if db_exists else 0
        frontend_build_exists = (_FRONTEND_BUILD_DIR / "index.html").exists()
        version_exists = _VERSION_FILE.exists()
        logs_dir_exists = LOGS_DIR.exists()
        screenshots_dir_exists = SCREENSHOTS_DIR.exists()
        backup_dir = DATA_DIR / "backups"
        backup_dir_exists = backup_dir.exists()

        checks: List[Dict[str, Any]] = []

        # Setup & secrets
        self._add_check(
            checks,
            group="Setup & access",
            key="setup_complete",
            label="Ersteinrichtung abgeschlossen",
            status="ok" if setup.is_complete else "fail",
            detail=setup.created_at or str(SETUP_FLAG_FILE),
            remediation="/setup abschließen und Standard-Zugangsdaten ersetzen",
        )
        self._add_check(
            checks,
            group="Setup & access",
            key="admin_password",
            label="Admin-Standardpasswort ersetzt",
            status="ok" if not setup.needs_admin_password else "fail",
            detail="Admin-Login ist nicht mehr auf admin123" if not setup.needs_admin_password else "Seed-Passwort noch aktiv oder Admin fehlt",
            remediation="Im Setup oder über Benutzerverwaltung ein echtes Admin-Passwort setzen",
        )
        self._add_check(
            checks,
            group="Setup & access",
            key="staff_pin",
            label="Quick-PIN ersetzt",
            status="ok" if not setup.needs_staff_pin else "fail",
            detail="Quick-PIN für Admin/Staff wirkt nicht mehr wie Seed-PIN" if not setup.needs_staff_pin else "1234/0000 scheint noch aktiv oder fehlt",
            remediation="Im Setup einen echten 4-stelligen Staff-PIN setzen",
        )
        self._add_check(
            checks,
            group="Setup & access",
            key="secrets_file",
            label="JWT/Agent-Secrets vorhanden",
            status="ok" if stored_secrets.get("JWT_SECRET") and stored_secrets.get("AGENT_SECRET") else "fail",
            detail=str(SECRETS_FILE),
            remediation="Secrets neu generieren oder data/.secrets aus Backup wiederherstellen",
        )
        self._add_check(
            checks,
            group="Setup & access",
            key="secrets_loaded",
            label="Secrets in Prozess geladen",
            status="ok" if os.environ.get("JWT_SECRET") and os.environ.get("AGENT_SECRET") else "warn",
            detail="JWT_SECRET/AGENT_SECRET im laufenden Prozess" if os.environ.get("JWT_SECRET") and os.environ.get("AGENT_SECRET") else "Secrets-Datei existiert evtl., aber Prozess wurde noch nicht mit ihnen gestartet",
            remediation="Backend nach Secret-Rotation neu starten",
        )
        self._add_check(
            checks,
            group="Setup & access",
            key="backend_env",
            label="backend/.env auffindbar",
            status="ok" if BACKEND_ENV_FILE.exists() else "warn",
            detail=str(BACKEND_ENV_FILE),
            remediation="Nur prüfen, wenn env-Dateien lokal erwartet werden",
        )
        self._add_check(
            checks,
            group="Setup & access",
            key="frontend_env",
            label="frontend/.env auffindbar",
            status="ok" if FRONTEND_ENV_FILE.exists() else "warn",
            detail=str(FRONTEND_ENV_FILE),
            remediation="Nur prüfen, wenn Frontend-Locals genutzt werden",
        )

        # Runtime paths / build
        self._add_check(
            checks,
            group="Runtime & artifacts",
            key="data_dir",
            label="Data-Verzeichnis vorhanden",
            status="ok" if DATA_DIR.exists() else "fail",
            detail=str(DATA_DIR),
            remediation="Install/Reinstall ausführen oder DATA_DIR korrigieren",
        )
        self._add_check(
            checks,
            group="Runtime & artifacts",
            key="database",
            label="SQLite-Datenbank vorhanden",
            status="ok" if db_exists else "fail",
            detail=f"{DATABASE_PATH} ({db_size_bytes} Bytes)" if db_exists else str(DATABASE_PATH),
            remediation="DB-Backup wiederherstellen oder Installation reparieren",
        )
        self._add_check(
            checks,
            group="Runtime & artifacts",
            key="frontend_build",
            label="Frontend-Build vorhanden",
            status="ok" if frontend_build_exists else "fail",
            detail=str(_FRONTEND_BUILD_DIR / 'index.html'),
            remediation="Frontend bauen oder Windows-Paket sauber neu installieren",
        )
        self._add_check(
            checks,
            group="Runtime & artifacts",
            key="version_file",
            label="VERSION-Datei vorhanden",
            status="ok" if version_exists else "fail",
            detail=str(_VERSION_FILE),
            remediation="Installationspaket unvollständig – Build/Update prüfen",
        )
        self._add_check(
            checks,
            group="Runtime & artifacts",
            key="logs_dir",
            label="Log-Verzeichnis vorhanden",
            status="ok" if logs_dir_exists else "warn",
            detail=str(LOGS_DIR),
            remediation="Nach Backend-Start prüfen; ohne Logs wird Support unnötig blind",
        )
        self._add_check(
            checks,
            group="Runtime & artifacts",
            key="backup_dir",
            label="Backup-Verzeichnis vorhanden",
            status="ok" if backup_dir_exists else "warn",
            detail=str(backup_dir),
            remediation="Spätestens vor Updates ein erstes Backup erzeugen",
        )

        # Local board config
        has_explicit_board_id = bool((os.environ.get("BOARD_ID") or os.environ.get("LOCAL_BOARD_ID") or "").strip())
        self._add_check(
            checks,
            group="Local board",
            key="board_id_env",
            label="Board-ID konfiguriert",
            status="ok" if has_explicit_board_id else "warn",
            detail=local_board_id,
            remediation="BOARD_ID bzw. LOCAL_BOARD_ID bewusst setzen, statt implizit auf BOARD-1 zu fallen",
        )
        self._add_check(
            checks,
            group="Local board",
            key="board_row",
            label="Board in DB vorhanden",
            status="ok" if board else "fail",
            detail=board.name if board else f"Kein DB-Eintrag für {local_board_id}",
            remediation="Board-ID in backend/.env gegen Admin > Boards abgleichen",
        )
        if board:
            self._add_check(
                checks,
                group="Local board",
                key="board_status",
                label="Board-Konfiguration geladen",
                status="ok",
                detail=f"{board.board_id} · {board.name} · Status {board.status}",
            )
            self._add_check(
                checks,
                group="Local board",
                key="agent_url",
                label="Agent-API-URL gepflegt",
                status="ok" if board.agent_api_base_url else "warn",
                detail=board.agent_api_base_url or "Nicht gesetzt – Device Ops läuft nur lokal/fallback-basiert",
                remediation="Für Remote-Status/Pairing eine agent_api_base_url hinterlegen",
            )
        else:
            self._add_check(
                checks,
                group="Local board",
                key="agent_url",
                label="Agent-API-URL gepflegt",
                status="warn",
                detail="Kann ohne lokales Board nicht geprüft werden",
            )

        # Observer / device prerequisites
        requires_target = observer_mode_requires_target()
        board_target = (board.autodarts_target_url or "").strip() if board else ""
        self._add_check(
            checks,
            group="Observer & device",
            key="autodarts_mode",
            label="Autodarts-Modus",
            status="ok",
            detail=AUTODARTS_MODE,
        )
        self._add_check(
            checks,
            group="Observer & device",
            key="observer_target",
            label="Observer-Ziel-URL gesetzt",
            status="ok" if (not requires_target or bool(board_target)) else "fail",
            detail=board_target or ("Im aktuellen Modus nicht erforderlich" if not requires_target else "Fehlt"),
            remediation="Board-Konfiguration öffnen und autodarts_target_url setzen",
        )
        mock_mode = (os.environ.get("AUTODARTS_MOCK", "") or "").strip().lower() in {"1", "true", "yes", "on"}
        self._add_check(
            checks,
            group="Observer & device",
            key="autodarts_mock",
            label="Mock-Modus deaktiviert",
            status="warn" if mock_mode else "ok",
            detail="AUTODARTS_MOCK=true" if mock_mode else "Produktiver Observer-Modus",
            remediation="Auf echten Board-PCs Mock-Modus deaktivieren",
        )
        headless_mode = (os.environ.get("AUTODARTS_HEADLESS", "false") or "false").strip().lower() in {"1", "true", "yes", "on"}
        self._add_check(
            checks,
            group="Observer & device",
            key="autodarts_headless",
            label="Observer-Headless-Modus",
            status="warn" if headless_mode else "ok",
            detail="headless=true" if headless_mode else "UI-/Board-PC-Modus",
            remediation="Für echte Board-PC-Diagnose Headless nur bewusst aktivieren",
        )
        if is_windows:
            exe_status = "ok" if desktop_exe and desktop_exe_exists else "warn"
            exe_detail = desktop_exe or "Nicht konfiguriert"
            if desktop_exe and not desktop_exe_exists:
                exe_detail = f"Nicht gefunden: {desktop_exe}"
            self._add_check(
                checks,
                group="Observer & device",
                key="autodarts_desktop_exe",
                label="Autodarts Desktop EXE erreichbar",
                status=exe_status,
                detail=exe_detail,
                remediation="Pfad in Settings > Autodarts Desktop oder Setup korrigieren",
            )
        else:
            self._add_check(
                checks,
                group="Observer & device",
                key="autodarts_desktop_exe",
                label="Autodarts Desktop EXE",
                status="warn",
                detail="Nur auf Windows-Board-PCs relevant",
            )

        fail_count = sum(1 for check in checks if check["status"] == "fail")
        warn_count = sum(1 for check in checks if check["status"] == "warn")
        ok_count = sum(1 for check in checks if check["status"] == "ok")
        overall_status = "blocked" if fail_count else "warning" if warn_count else "ready"

        recommended_actions: List[str] = []
        if not setup.is_complete:
            recommended_actions.append("/setup abschließen, damit Standardzugänge und Secrets sauber ersetzt sind.")
        if not board:
            recommended_actions.append(f"BOARD_ID/LOCAL_BOARD_ID gegen die Boards-Tabelle abgleichen (gesucht: {local_board_id}).")
        if requires_target and not board_target:
            recommended_actions.append("In Admin > Boards die Autodarts-Ziel-URL für das lokale Board setzen.")
        if not frontend_build_exists:
            recommended_actions.append("Frontend-Build prüfen – ohne frontend/build/index.html fühlt sich die Installation halb tot an.")
        if not (os.environ.get("JWT_SECRET") and os.environ.get("AGENT_SECRET")):
            recommended_actions.append("Nach Secret-Änderungen Backend neu starten, damit JWT/Agent-Secret wirklich aktiv sind.")
        if not backup_dir_exists:
            recommended_actions.append("Vor dem nächsten Update einmal ein App- oder DB-Backup erzeugen.")
        if not recommended_actions:
            recommended_actions.append("Keine offensichtlichen Blocker – wenn es trotzdem hakt, Support-Snapshot/Bundle exportieren und Logs prüfen.")

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": overall_status,
            "summary": {
                "status": overall_status,
                "fail_count": fail_count,
                "warn_count": warn_count,
                "ok_count": ok_count,
                "check_count": len(checks),
            },
            "local_board_id": local_board_id,
            "local_urls": setup.local_urls,
            "recommended_actions": recommended_actions,
            "setup": setup.model_dump(),
            "board": {
                "exists": bool(board),
                "count": len(boards),
                "board_id": board.board_id if board else local_board_id,
                "name": board.name if board else None,
                "status": board.status if board else None,
                "is_master": bool(board.is_master) if board else False,
                "autodarts_target_url": board.autodarts_target_url if board else None,
                "agent_api_base_url": board.agent_api_base_url if board else None,
            },
            "observer": {
                "mode": AUTODARTS_MODE,
                "requires_target": requires_target,
                "headless": headless_mode,
                "mock": mock_mode,
            },
            "runtime": {
                "os": f"{platform.system()} {platform.release()}",
                "data_dir": str(DATA_DIR),
                "database_path": str(DATABASE_PATH),
                "database_exists": db_exists,
                "database_size_bytes": db_size_bytes,
                "frontend_build_path": str(_FRONTEND_BUILD_DIR / 'index.html'),
                "frontend_build_exists": frontend_build_exists,
                "version_path": str(_VERSION_FILE),
                "version_exists": version_exists,
                "logs_dir": str(LOGS_DIR),
                "logs_dir_exists": logs_dir_exists,
                "screenshot_dir": str(SCREENSHOTS_DIR),
                "screenshot_dir_exists": screenshots_dir_exists,
                "backup_dir": str(backup_dir),
                "backup_dir_exists": backup_dir_exists,
            },
            "device": {
                "is_windows": is_windows,
                "autodarts_desktop": {
                    "exe_path": desktop_exe,
                    "exe_exists": desktop_exe_exists,
                    "auto_start": bool(desktop_cfg.get("auto_start")),
                },
            },
            "checks": checks,
        }

    async def build_support_snapshot(self, db: AsyncSession, agent_status: dict) -> dict:
        readiness = await self.build_readiness_snapshot(db)
        setup = readiness["setup"]
        health = asdict(health_monitor.get_health())
        downloads = update_service.list_downloaded_assets()
        app_backups = updater_service.list_app_backups()
        update_result = updater_service.get_update_result()
        screenshots = health_monitor.get_error_screenshots()
        log_files = []
        if LOGS_DIR.exists():
            for file in sorted(LOGS_DIR.glob("*.log*")):
                stat = file.stat()
                log_files.append(
                    {
                        "name": file.name,
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    }
                )

        support_bundle_includes = [
            "logs/*.log*",
            "supervisor/*.log (wenn vorhanden)",
            "snapshot/system_info.json",
            "snapshot/health.json",
            "snapshot/setup_status.json",
            "snapshot/readiness.json",
            "snapshot/agent_status.json",
            "snapshot/downloaded_assets.json",
            "snapshot/app_backups.json",
            "snapshot/update_result.json",
            "snapshot/secrets_status.json",
        ]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "support_bundle": {
                "download_endpoint": "/api/system/logs/bundle",
                "filename_pattern": "darts-support_YYYYMMDD_HHMMSS.tar.gz",
                "includes": support_bundle_includes,
            },
            "system_info": system_service.get_system_info(),
            "health": health,
            "setup_status": setup,
            "readiness": readiness,
            "agent_status": agent_status,
            "downloaded_assets": {"assets": downloads, "count": len(downloads)},
            "app_backups": {"backups": app_backups, "count": len(app_backups)},
            "update_result": {"has_result": bool(update_result), "result": update_result},
            "secrets_status": {
                "file_path": str(SECRETS_FILE),
                "has_jwt_secret": bool(get_stored_secrets().get("JWT_SECRET")),
                "has_agent_secret": bool(get_stored_secrets().get("AGENT_SECRET")),
                "loaded_in_env": bool(os.environ.get("JWT_SECRET") and os.environ.get("AGENT_SECRET")),
            },
            "logs": {
                "dir": str(LOGS_DIR),
                "files": log_files,
                "tail_lines": system_service.tail_logs(120),
            },
            "screenshots": {
                "dir": str(SCREENSHOTS_DIR),
                "count": len(screenshots),
                "items": screenshots[:8],
            },
        }


readiness_service = ReadinessService()
