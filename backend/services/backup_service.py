import asyncio
import gzip
import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from backend.database import DATABASE_PATH

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("data/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(DATABASE_PATH)


@dataclass
class BackupInfo:
    filename: str
    path: str
    size: int
    created_at: datetime
    compressed: bool
    validated: bool = True
    integrity_check: Optional[str] = None

    @property
    def size_bytes(self) -> int:
        return self.size


class BackupService:
    def __init__(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def _open_sqlite(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    def _validate_sqlite_file(self, path: Path) -> str:
        conn = self._open_sqlite(path)
        try:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            result = row[0] if row else "unknown"
            if result != "ok":
                raise RuntimeError(f"SQLite integrity_check failed: {result}")
            return result
        finally:
            conn.close()

    def _create_snapshot(self, temp_sqlite: Path) -> str:
        source = self._open_sqlite(DB_PATH)
        target = self._open_sqlite(temp_sqlite)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return self._validate_sqlite_file(temp_sqlite)

    def create_backup(self, compress: bool = True) -> BackupInfo:
        if not DB_PATH.exists():
            raise FileNotFoundError(f"Database not found: {DB_PATH}")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        temp_sqlite = BACKUP_DIR / f"darts-kiosk-{timestamp}.tmp.sqlite"
        final_sqlite = BACKUP_DIR / f"darts-kiosk-{timestamp}.sqlite"
        final_gz = BACKUP_DIR / f"darts-kiosk-{timestamp}.sqlite.gz"

        integrity = None
        try:
            integrity = self._create_snapshot(temp_sqlite)

            if compress:
                with open(temp_sqlite, "rb") as src, gzip.open(final_gz, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                temp_sqlite.unlink(missing_ok=True)
                target = final_gz
                compressed = True
            else:
                temp_sqlite.replace(final_sqlite)
                target = final_sqlite
                compressed = False

            info = BackupInfo(
                filename=target.name,
                path=str(target),
                size=target.stat().st_size,
                created_at=datetime.now(timezone.utc),
                compressed=compressed,
                validated=True,
                integrity_check=integrity,
            )
            logger.info("[Backup] created backup=%s size=%s integrity=%s", info.filename, info.size, integrity)
            return info
        except Exception:
            temp_sqlite.unlink(missing_ok=True)
            final_sqlite.unlink(missing_ok=True)
            raise

    def list_backups(self) -> List[BackupInfo]:
        backups: List[BackupInfo] = []
        for path in sorted(BACKUP_DIR.glob("darts-kiosk-*.sqlite*"), reverse=True):
            backups.append(
                BackupInfo(
                    filename=path.name,
                    path=str(path),
                    size=path.stat().st_size,
                    created_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                    compressed=path.suffix == ".gz",
                    validated=True,
                    integrity_check=None,
                )
            )
        return backups

    def restore_backup(self, filename: str, create_pre_restore_backup: bool = True) -> BackupInfo:
        backup_path = BACKUP_DIR / filename
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {filename}")

        if create_pre_restore_backup and DB_PATH.exists():
            try:
                self.create_backup(compress=True)
            except Exception as e:
                logger.warning("[Backup] pre-restore backup failed: %s", e)

        restore_tmp = BACKUP_DIR / f"restore-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.tmp.sqlite"
        target_tmp = BACKUP_DIR / f"target-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.tmp.sqlite"
        original_backup = DB_PATH.with_suffix(DB_PATH.suffix + ".pre-restore.bak")
        try:
            if backup_path.suffix == ".gz":
                with gzip.open(backup_path, "rb") as src, open(restore_tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                shutil.copy2(backup_path, restore_tmp)

            integrity = self._validate_sqlite_file(restore_tmp)

            source = self._open_sqlite(restore_tmp)
            target = self._open_sqlite(target_tmp)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()

            self._validate_sqlite_file(target_tmp)

            if DB_PATH.exists():
                shutil.copy2(DB_PATH, original_backup)
            target_tmp.replace(DB_PATH)

            info = BackupInfo(
                filename=backup_path.name,
                path=str(backup_path),
                size=backup_path.stat().st_size,
                created_at=datetime.now(timezone.utc),
                compressed=backup_path.suffix == ".gz",
                validated=True,
                integrity_check=integrity,
            )
            logger.info("[Backup] restored backup=%s integrity=%s", backup_path.name, integrity)
            return info
        finally:
            restore_tmp.unlink(missing_ok=True)
            target_tmp.unlink(missing_ok=True)

    def get_backup_path(self, filename: str) -> Optional[str]:
        backup_path = BACKUP_DIR / filename
        if backup_path.exists() and backup_path.is_file():
            return str(backup_path)
        return None

    def delete_backup(self, filename: str) -> bool:
        backup_path = BACKUP_DIR / filename
        if not backup_path.exists() or not backup_path.is_file():
            return False
        backup_path.unlink()
        logger.info("[Backup] deleted backup=%s", filename)
        return True

    def get_backup_stats(self) -> dict:
        backups = self.list_backups()
        total_size = sum(item.size for item in backups)
        return {
            "count": len(backups),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_backup": backups[0].created_at.isoformat() if backups else None,
        }

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("[Backup] backup service started")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[Backup] backup service stopped")


backup_service = BackupService()


async def start_backup_service():
    await backup_service.start()


async def stop_backup_service():
    await backup_service.stop()
