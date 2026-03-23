"""
Cyclic License Check Service — v3.5.0 Hybrid Sync

Runs a periodic background task that:
1. First attempts a remote sync with the central license server
2. On remote success: updates local cache with server data
3. On remote failure: falls back to local license validation (existing logic)

Design:
- Uses asyncio.create_task for non-blocking execution
- Fail-safe: on error, keeps last valid cache, logs WARNING
- Configurable interval via settings (default: 6 hours, range: 1-24h)
- Runs once on startup + cyclically
- NEVER blocks gameplay due to network errors
"""
import asyncio
import logging
from datetime import datetime, timezone

from backend.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_HOURS = 6


class CyclicLicenseChecker:
    """Background task for periodic license validation with hybrid sync."""

    def __init__(self):
        self._task: asyncio.Task = None
        self._running = False
        self.last_check_at = None
        self.last_check_status = None
        self.last_check_ok = None
        self.last_check_source = None  # "remote" or "local"
        self.check_count = 0

    async def start(self):
        """Start the background checker. Called once from server lifespan."""
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[LICENSE_CHECK] Background checker started (v3.5.0 hybrid)")

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
        """Execute a single hybrid license check cycle."""
        now = datetime.now(timezone.utc)
        logger.info(f"[LICENSE_CHECK] Starting hybrid check #{self.check_count + 1}")

        try:
            from backend.services.license_service import license_service
            from backend.services.device_identity_service import device_identity_service
            from backend.services.audit_log_service import audit_log_service
            from backend.services.license_sync_client import license_sync_client

            install_id = device_identity_service.get_install_id()

            # Step 1: Try remote sync
            sync_config = await self._get_sync_config()

            if sync_config.get("enabled") and sync_config.get("server_url") and sync_config.get("api_key"):
                logger.info(f"[LICENSE_CHECK] Attempting remote sync to {sync_config['server_url']}")
                remote_data = await license_sync_client.sync(
                    server_url=sync_config["server_url"],
                    api_key=sync_config["api_key"],
                    install_id=install_id,
                    device_name=sync_config.get("device_name"),
                )

                if remote_data:
                    # Remote sync succeeded — build cache-compatible status
                    status = {
                        "status": remote_data.get("license_status", "no_license"),
                        "binding_status": remote_data.get("binding_status"),
                        "license_id": remote_data.get("license_id"),
                        "customer_name": remote_data.get("customer_name"),
                        "plan_type": remote_data.get("plan_type"),
                        "ends_at": remote_data.get("expiry"),
                        "grace_until": remote_data.get("grace_until"),
                        "max_devices": remote_data.get("max_devices"),
                        "checked_at": now.isoformat(),
                        "source": "remote",
                        "server_timestamp": remote_data.get("server_timestamp"),
                    }
                    license_service.save_to_cache(status)

                    self.last_check_at = now
                    self.last_check_status = status.get("status")
                    self.last_check_ok = True
                    self.last_check_source = "remote"
                    self.check_count += 1

                    async with AsyncSessionLocal() as db:
                        await audit_log_service.log(
                            db, "REMOTE_SYNC_OK",
                            install_id=install_id,
                            new_value={"status": status.get("status"), "binding": status.get("binding_status")},
                            message=f"Remote sync #{self.check_count}: {status.get('status')} from {sync_config['server_url']}",
                        )
                        await db.commit()

                    logger.info(
                        f"[LICENSE_CHECK] Remote sync #{self.check_count} OK: "
                        f"status={status.get('status')} binding={status.get('binding_status')}"
                    )
                    return
                else:
                    logger.warning("[LICENSE_CHECK] Remote sync failed — falling back to local check")
                    async with AsyncSessionLocal() as db:
                        await audit_log_service.log(
                            db, "REMOTE_SYNC_FAILED",
                            install_id=install_id,
                            message=f"Remote sync failed: {license_sync_client.last_error}. Falling back to local.",
                        )
                        await db.commit()

            # Step 2: Fallback to local check (existing v3.4.5 logic)
            # v3.11.2: If device is registered, don't overwrite a valid cache with
            # local no_license (the local DB has no licensing data for SaaS devices).
            logger.info("[LICENSE_CHECK] Running local license check")
            async with AsyncSessionLocal() as db:
                status = await license_service.get_effective_status(
                    db, install_id=install_id, trigger_binding=False
                )
                status["source"] = "local"

                # Fail-safe: if local returns no_license but device is registered
                # and we already have a valid cache (from registration or prior sync),
                # preserve the existing cache instead of overwriting it.
                # Also check registration data as authoritative source.
                if status.get("status") == "no_license":
                    from backend.services.device_registration_client import device_registration_client
                    if device_registration_client.is_registered:
                        existing_cache = license_service.load_from_cache()
                        if existing_cache and existing_cache.get("status") not in (None, "no_license"):
                            logger.info(
                                f"[LICENSE_CHECK] Local=no_license but device is registered. "
                                f"Preserving cache: status={existing_cache.get('status')} "
                                f"(source={existing_cache.get('source')})"
                            )
                            self.last_check_at = now
                            self.last_check_status = existing_cache.get("status")
                            self.last_check_ok = True
                            self.last_check_source = "cache_preserved"
                            self.check_count += 1
                            return

                        # No valid cache — use registration data as authoritative source
                        reg_data = device_registration_client.get_status()
                        reg_license = reg_data.get("license_status")
                        if reg_license and reg_license != "no_license":
                            reg_status = {
                                "status": reg_license,
                                "license_id": reg_data.get("license_id"),
                                "customer_name": reg_data.get("customer_name"),
                                "binding_status": "bound",
                                "checked_at": now.isoformat(),
                                "source": "registration_data",
                                "registration_status": "registered",
                            }
                            license_service.save_to_cache(reg_status)
                            logger.info(
                                f"[LICENSE_CHECK] Local=no_license, cache stale. "
                                f"Restored from registration data: status={reg_license}"
                            )
                            self.last_check_at = now
                            self.last_check_status = reg_license
                            self.last_check_ok = True
                            self.last_check_source = "registration_data"
                            self.check_count += 1
                            return

                license_service.save_to_cache(status)

                self.last_check_at = now
                self.last_check_status = status.get("status")
                self.last_check_ok = True
                self.last_check_source = "local"
                self.check_count += 1

                await audit_log_service.log(
                    db, "LICENSE_CHECK_SUCCESS",
                    install_id=install_id,
                    new_value={"status": status.get("status"), "binding": status.get("binding_status"), "source": "local"},
                    message=f"Local check #{self.check_count}: {status.get('status')}",
                )
                await db.commit()

            logger.info(
                f"[LICENSE_CHECK] Local check #{self.check_count} OK: "
                f"status={status.get('status')} binding={status.get('binding_status')}"
            )

        except Exception as e:
            self.last_check_ok = False
            self.last_check_source = "error"
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

    async def _get_sync_config(self) -> dict:
        """Read sync configuration from settings table."""
        try:
            from backend.models import Settings
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                stmt = select(Settings).where(Settings.key == "license_sync_config")
                result = await db.execute(stmt)
                s = result.scalar_one_or_none()
                if s and s.value:
                    return s.value if isinstance(s.value, dict) else {}
        except Exception as e:
            logger.warning(f"[LICENSE_CHECK] Failed to read sync config: {e}")
        return {}

    async def _get_interval_seconds(self) -> int:
        """Read configurable check interval from settings."""
        try:
            # First check sync config for interval
            sync_config = await self._get_sync_config()
            if sync_config.get("interval_hours"):
                hours = max(1, min(24, int(sync_config["interval_hours"])))
                return hours * 3600

            # Fallback to legacy setting
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
        from backend.services.license_sync_client import license_sync_client
        return {
            "running": self._running,
            "last_check_at": self.last_check_at.isoformat() if self.last_check_at else None,
            "last_check_status": self.last_check_status,
            "last_check_ok": self.last_check_ok,
            "last_check_source": self.last_check_source,
            "check_count": self.check_count,
            "sync": license_sync_client.get_status(),
        }


cyclic_license_checker = CyclicLicenseChecker()
