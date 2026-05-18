from __future__ import annotations

import logging
from datetime import datetime, timezone

from central_server.models import CentralAuditLog

logger = logging.getLogger("central_server")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def log_audit(
    db,
    action,
    device_id=None,
    install_id=None,
    license_id=None,
    actor=None,
    message=None,
    details=None,
):
    try:
        entry = CentralAuditLog(
            action=action,
            device_id=device_id,
            install_id=install_id,
            license_id=license_id,
            actor=actor,
            message=message,
            details=details,
            timestamp=utcnow(),
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        logger.error(f"[AUDIT] Failed: {e}")
