"""
Backup Service
Automatic SQLite backups with retention policy
"""
import os
import shutil
import gzip
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get('DATA_DIR', '/app/data'))
BACKUP_DIR = DATA_DIR / 'backups'
DB_PATH = DATA_DIR / 'db.sqlite'

# Configuration
MAX_BACKUPS = int(os.environ.get('MAX_BACKUPS', 30))  # Keep last 30 backups
BACKUP_INTERVAL_HOURS = int(os.environ.get('BACKUP_INTERVAL_HOURS', 6))  # Every 6 hours


@dataclass
class BackupInfo:
    filename: str
    path: str
    size_bytes: int
    created_at: datetime
    compressed: bool


class BackupService:
    """Handles automatic database backups with retention"""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start automatic backup scheduler"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._backup_loop())
        logger.info(f"Backup service started (interval: {BACKUP_INTERVAL_HOURS}h, retention: {MAX_BACKUPS})")
    
    async def stop(self):
        """Stop backup scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Backup service stopped")
    
    async def _backup_loop(self):
        """Background loop for scheduled backups"""
        while self._running:
            try:
                self.create_backup()
                self.cleanup_old_backups()
            except Exception as e:
                logger.error(f"Backup error: {e}")
            
            # Wait for next backup interval
            await asyncio.sleep(BACKUP_INTERVAL_HOURS * 3600)
    
    def create_backup(self, compress: bool = True) -> Optional[BackupInfo]:
        """Create a new backup of the database"""
        if not DB_PATH.exists():
            logger.warning("Database file not found, skipping backup")
            return None
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        
        if compress:
            backup_filename = f"db_backup_{timestamp}.sqlite.gz"
            backup_path = BACKUP_DIR / backup_filename
            
            # Create compressed backup
            with open(DB_PATH, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            backup_filename = f"db_backup_{timestamp}.sqlite"
            backup_path = BACKUP_DIR / backup_filename
            shutil.copy2(DB_PATH, backup_path)
        
        size = backup_path.stat().st_size
        logger.info(f"Backup created: {backup_filename} ({size / 1024:.1f} KB)")
        
        return BackupInfo(
            filename=backup_filename,
            path=str(backup_path),
            size_bytes=size,
            created_at=datetime.now(timezone.utc),
            compressed=compress
        )
    
    def cleanup_old_backups(self):
        """Remove old backups exceeding retention limit"""
        backups = self.list_backups()
        
        if len(backups) > MAX_BACKUPS:
            # Sort by date (oldest first)
            backups.sort(key=lambda b: b.created_at)
            
            # Remove oldest backups
            to_remove = backups[:-MAX_BACKUPS]
            for backup in to_remove:
                try:
                    Path(backup.path).unlink()
                    logger.info(f"Removed old backup: {backup.filename}")
                except Exception as e:
                    logger.error(f"Failed to remove backup {backup.filename}: {e}")
    
    def list_backups(self) -> List[BackupInfo]:
        """List all available backups"""
        backups = []
        
        if not BACKUP_DIR.exists():
            return backups
        
        for file in BACKUP_DIR.glob("db_backup_*.sqlite*"):
            try:
                stat = file.stat()
                
                # Parse timestamp from filename
                parts = file.stem.replace('.sqlite', '').split('_')
                if len(parts) >= 3:
                    date_str = f"{parts[2]}_{parts[3]}" if len(parts) > 3 else parts[2]
                    try:
                        created = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                        created = created.replace(tzinfo=timezone.utc)
                    except:
                        created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                else:
                    created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                
                backups.append(BackupInfo(
                    filename=file.name,
                    path=str(file),
                    size_bytes=stat.st_size,
                    created_at=created,
                    compressed=file.suffix == '.gz'
                ))
            except Exception as e:
                logger.warning(f"Error reading backup {file}: {e}")
        
        # Sort by date (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups
    
    def get_backup_path(self, filename: str) -> Optional[Path]:
        """Get path to a specific backup file"""
        path = BACKUP_DIR / filename
        if path.exists() and path.is_file():
            return path
        return None
    
    def restore_backup(self, filename: str) -> bool:
        """Restore database from a backup"""
        backup_path = self.get_backup_path(filename)
        if not backup_path:
            logger.error(f"Backup not found: {filename}")
            return False
        
        try:
            # Create a backup of current database first
            if DB_PATH.exists():
                current_backup = DB_PATH.with_suffix('.sqlite.pre_restore')
                shutil.copy2(DB_PATH, current_backup)
                logger.info(f"Created pre-restore backup: {current_backup}")
            
            # Restore
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(DB_PATH, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_path, DB_PATH)
            
            logger.info(f"Database restored from: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def delete_backup(self, filename: str) -> bool:
        """Delete a specific backup"""
        backup_path = self.get_backup_path(filename)
        if not backup_path:
            return False
        
        try:
            backup_path.unlink()
            logger.info(f"Deleted backup: {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False
    
    def get_backup_stats(self) -> dict:
        """Get backup statistics"""
        backups = self.list_backups()
        total_size = sum(b.size_bytes for b in backups)
        
        return {
            "total_backups": len(backups),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_backup": backups[-1].created_at.isoformat() if backups else None,
            "newest_backup": backups[0].created_at.isoformat() if backups else None,
            "retention_policy": MAX_BACKUPS,
            "backup_interval_hours": BACKUP_INTERVAL_HOURS
        }


# Global instance
backup_service = BackupService()


async def start_backup_service():
    await backup_service.start()


async def stop_backup_service():
    await backup_service.stop()
