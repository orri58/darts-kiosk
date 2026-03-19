"""
Cyclic License Check Service — v3.4.5

Runs a periodic background task that re-validates the license status
and updates the local cache. Does NOT interrupt running sessions.

Design:
- Uses asyncio.create_task for non-blocking execution
- Fail-safe: on error, keeps last valid cache, logs WARNING
- Configurable interval via settings (default: 6 hours)
- Also runs once on startup
"""
import asyncio
import logging
from datetime import datetime, timezone

from backend.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_HOURS = 6


class CyclicLicenseChecker:
    """Background task for periodic license validation."""

    def __init__(self):
        self._task: asyncio.Task = None
        self._running = False
        self.last_check_at = None
        self.last_check_status = None
        self.last_check_ok = None
        self.check_count = 0

    async def start(self):
        """Start the background checker. Called once from server lifespan."""
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[LICENSE_CHECK] Background checker started")

    async def stop(self):
        """Stop the background checker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[LICENSE_CHECK] Background checker stopped")

    async def _loop(self):
        """Main loop: run check immediately, then every N hours."""
        # Initial check on startup
        await self._run_check()

        while self._running:
            interval = await self._get_interval_seconds()
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            if self._running:
                await self._run_check()

    async def _run_check(self):
        """Execute a single license check cycle."""
        now = datetime.now(timezone.utc)
        logger.info(f"[LICENSE_CHECK] Starting cyclic check #{self.check_count + 1}")

        try:
            from backend.services.license_service import license_service
            from backend.services.device_identity_service import device_identity_service
            from backend.services.audit_log_service import audit_log_service

            install_id = device_identity_service.get_install_id()

            async with AsyncSessionLocal() as db:
                status = await license_service.get_effective_status(
                    db, install_id=install_id, trigger_binding=False
                )
                license_service.save_to_cache(status)

                self.last_check_at = now
                self.last_check_status = status.get("status")
                self.last_check_ok = True
                self.check_count += 1

                await audit_log_service.log(
                    db, "LICENSE_CHECK_SUCCESS",
                    install_id=install_id,
                    new_value={"status": status.get("status"), "binding": status.get("binding_status")},
                    message=f"Cyclic check #{self.check_count}: {status.get('status')}",
                )
                await db.commit()

            logger.info(
                f"[LICENSE_CHECK] Check #{self.check_count} OK: status={status.get('status')} "
                f"binding={status.get('binding_status')}"
            )

        except Exception as e:
            self.last_check_ok = False
            logger.warning(f"[LICENSE_CHECK] Check failed (keeping last valid cache): {e}")

            try:
                async with AsyncSessionLocal() as db:
                    from backend.services.audit_log_service import audit_log_service
                    await audit_log_service.log(
                        db, "LICENSE_CHECK_FAILED",
                        message=str(e),
                    )
                    await db.commit()
            except Exception:
                pass

    async def _get_interval_seconds(self) -> int:
        """Read configurable check interval from settings."""
        try:
            from backend.models import Settings
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                stmt = select(Settings).where(Settings.key == "license_check_interval_hours")
                result = await db.execute(stmt)
                s = result.scalar_one_or_none()
                if s and s.value:
                    return int(s.value) * 3600
        except Exception:
            pass
        return DEFAULT_CHECK_INTERVAL_HOURS * 3600

    def get_status(self) -> dict:
        """Return current checker status for admin display."""
        return {
            "running": self._running,
            "last_check_at": self.last_check_at.isoformat() if self.last_check_at else None,
            "last_check_status": self.last_check_status,
            "last_check_ok": self.last_check_ok,
            "check_count": self.check_count,
        }


cyclic_license_checker = CyclicLicenseChecker()
