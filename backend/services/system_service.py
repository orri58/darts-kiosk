"""
System Service
Provides system info, disk usage, log access, and management for /admin/system
"""
import io
import json
import logging
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR, DATABASE_PATH, PROJECT_ROOT
from backend.services.version_service import read_app_version

LOGS_DIR = DATA_DIR / 'logs'
ROOT_LOGS_DIR = PROJECT_ROOT / 'logs'

DOCKER_IMAGE = os.environ.get('DOCKER_IMAGE', 'darts-kiosk')


class SystemService:
    """System information and management"""

    def __init__(self):
        self._start_time = datetime.now(timezone.utc)

    def get_system_info(self) -> dict:
        uptime_s = int((datetime.now(timezone.utc) - self._start_time).total_seconds())

        # Disk usage for data directory
        disk = shutil.disk_usage(str(DATA_DIR))

        # DB file size
        db_path = DATABASE_PATH
        db_size = db_path.stat().st_size if db_path.exists() else 0

        # Count backups
        backup_dir = DATA_DIR / 'backups'
        backup_count = len(list(backup_dir.glob('db_backup_*'))) if backup_dir.exists() else 0

        return {
            "version": read_app_version(),
            "image_tag": os.environ.get('IMAGE_TAG', 'latest'),
            "mode": os.environ.get('MODE', 'MASTER'),
            "uptime_seconds": uptime_s,
            "start_time": self._start_time.isoformat(),
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "hostname": platform.node(),
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "usage_percent": round(disk.used / disk.total * 100, 1),
            },
            "database": {
                "path": str(db_path),
                "size_mb": round(db_size / (1024**2), 2),
            },
            "backups": {
                "count": backup_count,
            },
            "data_dir": str(DATA_DIR),
        }

    def get_log_directories(self) -> list[Path]:
        dirs: list[Path] = []
        for candidate in (ROOT_LOGS_DIR, LOGS_DIR):
            if candidate not in dirs:
                dirs.append(candidate)
        return dirs

    def list_log_files(self) -> list[dict]:
        files: list[dict] = []
        seen: set[Path] = set()
        for log_dir in self.get_log_directories():
            if not log_dir.exists():
                continue
            for log_file in sorted(log_dir.glob('*.log*')):
                resolved = log_file.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                stat = log_file.stat()
                files.append({
                    'dir': str(log_dir),
                    'name': log_file.name,
                    'path': str(log_file),
                    'size_bytes': stat.st_size,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
        files.sort(key=lambda item: item['modified_at'], reverse=True)
        return files

    def tail_logs(self, lines: int = 100) -> list:
        candidates: list[Path] = []
        for log_dir in self.get_log_directories():
            candidates.extend([
                log_dir / 'app.log',
                log_dir / 'backend.log',
                log_dir / 'updater.log',
            ])
            candidates.extend(sorted(log_dir.glob('*.log*')))

        seen: set[Path] = set()
        existing: list[Path] = []
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if path.exists() and path.is_file():
                existing.append(path)

        if not existing:
            return []

        log_file = max(existing, key=lambda item: item.stat().st_mtime)

        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
            return [line.rstrip('\n') for line in all_lines[-lines:]]
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            return [f"Error reading logs: {e}"]

    def create_log_bundle(self, extra_json_files: Optional[Dict[str, dict]] = None) -> Optional[io.BytesIO]:
        """Create a gzipped support bundle with logs plus optional JSON snapshots."""
        import tarfile

        buf = io.BytesIO()
        try:
            with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                # App logs
                for log_dir in self.get_log_directories():
                    if log_dir.exists():
                        for log_file in log_dir.glob('*.log*'):
                            tar.add(str(log_file), arcname=f"logs/{log_file.name}")

                # Supervisor logs if present
                sup_dir = Path('/var/log/supervisor')
                if sup_dir.exists():
                    for log_file in sup_dir.glob('*.log'):
                        tar.add(str(log_file), arcname=f"supervisor/{log_file.name}")

                for relative_name, payload in (extra_json_files or {}).items():
                    body = json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode('utf-8')
                    info = tarfile.TarInfo(name=relative_name)
                    info.size = len(body)
                    info.mtime = datetime.now(timezone.utc).timestamp()
                    tar.addfile(info, io.BytesIO(body))

            buf.seek(0)
            return buf
        except Exception as e:
            logger.error(f"Failed to create log bundle: {e}")
            return None


system_service = SystemService()
