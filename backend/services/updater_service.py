"""
Updater Service — Prepares and validates update packages.

Responsibilities:
  1. Create FULL application backups (not just DB — backend, frontend, scripts, VERSION)
  2. Extract downloaded release zips to a staging directory
  3. Validate the staging directory structure
  4. Write an update manifest (JSON) for the external updater.py to consume
  5. Trigger the external updater process (Windows only)

The actual file replacement is NEVER done inside this running process.
A separate updater.py script handles: stop → replace → restart → health check → rollback.

Protected directories (NEVER overwritten by the updater):
  - data/           (database, assets, downloads, backups)
  - logs/
  - chrome_profile/ (or data/kiosk_chrome_profile/)
  - backend/.env
  - frontend/.env
"""
import json
import os
import shutil
import zipfile
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR

# Directories
APP_BACKUPS_DIR = DATA_DIR / 'app_backups'
STAGING_DIR = DATA_DIR / 'update_staging'
MANIFEST_PATH = DATA_DIR / 'update_manifest.json'
RESULT_PATH = DATA_DIR / 'update_result.json'
APP_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

# Project root (where VERSION, backend/, frontend/ live)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Maximum number of app backups to keep
MAX_APP_BACKUPS = 5


class UpdaterService:
    """Manages the update preparation and handoff to the external updater."""

    def create_app_backup(self) -> Dict:
        """
        Create a full application backup (backend + frontend + scripts + VERSION).
        Excludes: data/, logs/, .env, __pycache__, node_modules, chrome_profile/
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_name = f"app_backup_{timestamp}"
        backup_zip = APP_BACKUPS_DIR / f"{backup_name}.zip"

        logger.info(f"[Updater] Creating full app backup: {backup_zip}")

        # Directories to back up (relative to PROJECT_ROOT)
        include_dirs = ['backend', 'frontend']

        # Also backup .bat/.py scripts at root level
        root_scripts = [f for f in PROJECT_ROOT.iterdir()
                        if f.is_file() and f.suffix in ('.bat', '.py', '.sh', '.md')]

        # Exclude patterns
        exclude_dirs = {'__pycache__', 'node_modules', '.git', '.emergent',
                        'data', 'logs', 'chrome_profile', 'test_reports',
                        'memory', '.venv', 'venv', 'build'}
        exclude_files = {'.env'}

        try:
            with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Backup VERSION
                version_file = PROJECT_ROOT / 'VERSION'
                if version_file.exists():
                    zf.write(version_file, 'VERSION')

                # Backup directories
                for dir_name in include_dirs:
                    dir_path = PROJECT_ROOT / dir_name
                    if not dir_path.exists():
                        continue
                    for root, dirs, files in os.walk(dir_path):
                        # Filter out excluded dirs
                        dirs[:] = [d for d in dirs if d not in exclude_dirs]
                        for file in files:
                            if file in exclude_files:
                                continue
                            filepath = Path(root) / file
                            arcname = filepath.relative_to(PROJECT_ROOT)
                            zf.write(filepath, str(arcname))

                # Backup root scripts
                for script in root_scripts:
                    if script.name not in exclude_files:
                        zf.write(script, script.name)

            size = backup_zip.stat().st_size
            logger.info(f"[Updater] App backup created: {backup_zip.name} ({size / 1024 / 1024:.1f} MB)")

            # Cleanup old backups
            self._cleanup_old_backups()

            return {
                "success": True,
                "filename": backup_zip.name,
                "path": str(backup_zip),
                "size_bytes": size,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"[Updater] App backup failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _cleanup_old_backups(self):
        """Remove old app backups exceeding MAX_APP_BACKUPS."""
        backups = sorted(
            APP_BACKUPS_DIR.glob('app_backup_*.zip'),
            key=lambda f: f.stat().st_mtime
        )
        while len(backups) > MAX_APP_BACKUPS:
            old = backups.pop(0)
            old.unlink()
            logger.info(f"[Updater] Removed old app backup: {old.name}")

    def list_app_backups(self) -> list:
        """List all application backups."""
        backups = []
        for f in sorted(APP_BACKUPS_DIR.glob('app_backup_*.zip'),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        return backups

    def extract_and_validate(self, zip_path: str, target_version: str) -> Dict:
        """
        Extract a downloaded release asset to a staging directory.
        Validate that it contains the expected structure.

        Expected zip structure:
          darts-kiosk-v{version}-windows/
            backend/
            frontend/
            VERSION
            ...

        Returns: { valid: bool, staging_dir: str, errors: [...] }
        """
        zip_file = Path(zip_path)
        if not zip_file.exists():
            return {"valid": False, "errors": [f"Zip-Datei nicht gefunden: {zip_path}"]}

        # Clean staging directory
        if STAGING_DIR.exists():
            shutil.rmtree(STAGING_DIR)
        STAGING_DIR.mkdir(parents=True)

        logger.info(f"[Updater] Extracting {zip_file.name} to staging...")

        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(STAGING_DIR)
        except zipfile.BadZipFile:
            return {"valid": False, "errors": ["Ungueltige ZIP-Datei"]}

        # Find the root directory inside the zip
        # Could be darts-kiosk-v1.7.0-windows/ or just the files directly
        staging_contents = list(STAGING_DIR.iterdir())
        staging_root = STAGING_DIR

        if len(staging_contents) == 1 and staging_contents[0].is_dir():
            # Zip has a single root folder (standard convention)
            staging_root = staging_contents[0]

        # Validate structure
        errors = []
        required = ['backend']
        for req in required:
            if not (staging_root / req).is_dir():
                errors.append(f"Fehlender Ordner: {req}/")

        # Check for VERSION file
        has_version = (staging_root / 'VERSION').exists()
        if not has_version:
            errors.append("Fehlende VERSION-Datei")

        # Verify no data/ directory in the package (safety)
        if (staging_root / 'data').exists():
            errors.append("WARNUNG: Paket enthaelt data/ — wird nicht ueberschrieben")

        # Check version matches
        if has_version:
            pkg_version = (staging_root / 'VERSION').read_text().strip()
            if pkg_version != target_version:
                errors.append(f"Version mismatch: Paket={pkg_version}, erwartet={target_version}")

        result = {
            "valid": len([e for e in errors if not e.startswith("WARNUNG")]) == 0,
            "staging_dir": str(staging_root),
            "staging_root_name": staging_root.name,
            "errors": errors,
            "contents": {
                "has_backend": (staging_root / 'backend').is_dir(),
                "has_frontend": (staging_root / 'frontend').is_dir(),
                "has_version": has_version,
                "has_scripts": any(staging_root.glob('*.bat')) or any(staging_root.glob('*.py')),
            },
        }

        logger.info(f"[Updater] Validation result: valid={result['valid']}, errors={errors}")
        return result

    def write_manifest(self, staging_dir: str, backup_path: str,
                       target_version: str) -> Dict:
        """
        Write the update manifest that the external updater.py will consume.
        """
        manifest = {
            "action": "install_update",
            "target_version": target_version,
            "current_version": self._read_current_version(),
            "staging_dir": staging_dir,
            "backup_path": backup_path,
            "project_root": str(PROJECT_ROOT),
            "health_check_url": "http://localhost:8001/api/health",
            "version_check_url": "http://localhost:8001/api/system/version",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "protected_paths": [
                "data",
                "logs",
                "chrome_profile",
                "data/kiosk_chrome_profile",
                "backend/.env",
                "frontend/.env",
            ],
        }

        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
        logger.info(f"[Updater] Manifest written: {MANIFEST_PATH}")
        return {"manifest_path": str(MANIFEST_PATH), "manifest": manifest}

    def write_rollback_manifest(self, backup_path: str) -> Dict:
        """Write a manifest for rollback operation."""
        manifest = {
            "action": "rollback",
            "current_version": self._read_current_version(),
            "backup_path": backup_path,
            "project_root": str(PROJECT_ROOT),
            "health_check_url": "http://localhost:8001/api/health",
            "version_check_url": "http://localhost:8001/api/system/version",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "protected_paths": [
                "data",
                "logs",
                "chrome_profile",
                "data/kiosk_chrome_profile",
                "backend/.env",
                "frontend/.env",
            ],
        }
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
        logger.info(f"[Updater] Rollback manifest written: {MANIFEST_PATH}")
        return {"manifest_path": str(MANIFEST_PATH), "manifest": manifest}

    def launch_updater(self) -> Dict:
        """
        Launch the external updater.py as a detached process.
        On Windows, this spawns a new console window that runs updater.py.
        The updater reads the manifest, stops services, replaces files, restarts.
        """
        updater_script = PROJECT_ROOT / 'updater.py'
        if not updater_script.exists():
            return {"launched": False, "error": "updater.py nicht gefunden"}

        if not MANIFEST_PATH.exists():
            return {"launched": False, "error": "Kein Update-Manifest vorhanden"}

        logger.info(f"[Updater] Launching external updater: {updater_script}")

        try:
            if sys.platform == 'win32':
                # On Windows: launch in a new console window, detached
                subprocess.Popen(
                    [sys.executable, str(updater_script), str(MANIFEST_PATH)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                    close_fds=True,
                )
            else:
                # On Linux: launch as background process
                subprocess.Popen(
                    [sys.executable, str(updater_script), str(MANIFEST_PATH)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            logger.info("[Updater] External updater launched successfully")
            return {"launched": True, "message": "Updater gestartet — System wird aktualisiert"}

        except Exception as e:
            logger.error(f"[Updater] Failed to launch updater: {e}", exc_info=True)
            return {"launched": False, "error": str(e)}

    def get_update_result(self) -> Optional[Dict]:
        """Read the result file written by the external updater after completion."""
        if not RESULT_PATH.exists():
            return None
        try:
            result = json.loads(RESULT_PATH.read_text())
            return result
        except Exception:
            return None

    def clear_update_result(self):
        """Clear the result file after it has been read by the admin."""
        if RESULT_PATH.exists():
            RESULT_PATH.unlink()

    def cleanup_staging(self):
        """Remove the staging directory after a successful update."""
        if STAGING_DIR.exists():
            shutil.rmtree(STAGING_DIR, ignore_errors=True)
            logger.info("[Updater] Staging directory cleaned up")

    def delete_app_backup(self, filename: str) -> bool:
        """Delete a specific app backup."""
        path = APP_BACKUPS_DIR / filename
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    @staticmethod
    def _read_current_version() -> str:
        version_file = PROJECT_ROOT / 'VERSION'
        try:
            return version_file.read_text().strip()
        except FileNotFoundError:
            return '0.0.0'


updater_service = UpdaterService()
