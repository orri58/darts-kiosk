"""
License Audit Log Service — v3.4.5

Central service for recording all licensing events.
Write-only, append-only design. No updates or deletes.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.licensing import LicAuditLog

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


class AuditLogService:
    """Append-only audit logger for licensing events."""

    async def log(
        self, db: AsyncSession,
        action: str,
        *,
        license_id: Optional[str] = None,
        device_id: Optional[str] = None,
        install_id: Optional[str] = None,
        previous_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
        actor: str = "system",
        message: Optional[str] = None,
    ):
        """Write a single audit event. Never raises — failures are logged."""
        try:
            entry = LicAuditLog(
                timestamp=_utcnow(),
                action=action,
                license_id=license_id,
                device_id=device_id,
                install_id=install_id,
                previous_value=previous_value,
                new_value=new_value,
                actor=actor,
                message=message,
            )
            db.add(entry)
            await db.flush()
            logger.debug(f"[AUDIT] {action} actor={actor} lic={license_id} dev={device_id}")
        except Exception as e:
            logger.error(f"[AUDIT] Failed to write audit log: {action} — {e}")


audit_log_service = AuditLogService()
