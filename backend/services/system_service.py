"""
System Service
Provides system info, disk usage, log access, and management for /admin/system
"""
import os
import platform
import shutil
import gzip
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR
LOGS_DIR = DATA_DIR / 'logs'
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
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
        db_path = DATA_DIR / 'db.sqlite'
        db_size = db_path.stat().st_size if db_path.exists() else 0

        # Count backups
        backup_dir = DATA_DIR / 'backups'
        backup_count = len(list(backup_dir.glob('db_backup_*'))) if backup_dir.exists() else 0

        return {
            "version": APP_VERSION,
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

    def tail_logs(self, lines: int = 100) -> list:
        log_file = LOGS_DIR / 'app.log'
        if not log_file.exists():
            return []

        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
            return [line.rstrip('\n') for line in all_lines[-lines:]]
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            return [f"Error reading logs: {e}"]

    def create_log_bundle(self) -> Optional[io.BytesIO]:
        """Create a gzipped tarball of all log files"""
        import tarfile

        buf = io.BytesIO()
        try:
            with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                # App logs
                if LOGS_DIR.exists():
                    for log_file in LOGS_DIR.glob('*.log*'):
                        tar.add(str(log_file), arcname=f"logs/{log_file.name}")

                # Supervisor logs if present
                sup_dir = Path('/var/log/supervisor')
                if sup_dir.exists():
                    for log_file in sup_dir.glob('*.log'):
                        tar.add(str(log_file), arcname=f"supervisor/{log_file.name}")

            buf.seek(0)
            return buf
        except Exception as e:
            logger.error(f"Failed to create log bundle: {e}")
            return None


system_service = SystemService()
