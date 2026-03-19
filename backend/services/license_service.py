"""
License Validation Service — v3.4.3 Device Binding

Handles:
- License status computation (active/grace/expired/blocked)
- Local license cache for offline resilience
- Device registration and binding (install_id → LicDevice)
- Grace period enforcement
- Device binding check (install_id match/mismatch)

Design:
- Does NOT modify existing runtime logic
- All DB operations use existing async session pattern
- Local cache is a signed JSON file for tamper detection
- Binding lives on LicDevice, NOT on License
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.licensing import (
    License, LicenseStatus, LicDevice, DeviceStatus,
    LicCustomer, LicLocation, CustomerStatus,
)

logger = logging.getLogger(__name__)

# Cache location
_DATA_DIR = Path(os.environ.get("DATA_DIR", "")) or (Path(__file__).resolve().parent.parent.parent / "data")
_CACHE_FILE = _DATA_DIR / "license_cache.json"
_CACHE_SECRET = os.environ.get("AGENT_SECRET", "license-cache-key")


def _sign_cache(data: dict) -> str:
    """Simple HMAC-like signature for cache tamper detection."""
    payload = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(f"{_CACHE_SECRET}:{payload}".encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LicenseValidationService:
    """Validates license status for a device/location/customer with device binding."""

    async def get_effective_status(
        self, db: AsyncSession, device_id: Optional[str] = None,
        location_id: Optional[str] = None, customer_id: Optional[str] = None,
        install_id: Optional[str] = None, board_id: Optional[str] = None,
    ) -> dict:
        """
        Compute the effective license status for a device, location, or customer.

        v3.4.3: When install_id is provided, also checks device binding:
        - If no device with that install_id exists → first-bind (auto-create)
        - If device bound with same install_id → OK
        - If device bound with different install_id → binding_mismatch

        Resolution order:
        1. Find device by install_id → get location → get customer
        2. If not found by install_id, try board_id lookup
        3. Find all licenses for customer (and optionally location)
        4. Pick the most permissive active license
        5. Compute effective status considering grace period
        6. Check device binding (if install_id provided)
        """
        now = _utcnow()
        binding_status = None
        bound_device = None

        # v3.4.3: If install_id provided, try to resolve device by install_id first
        if install_id and not device_id:
            stmt = select(LicDevice).where(LicDevice.install_id == install_id)
            result = await db.execute(stmt)
            bound_device = result.scalar_one_or_none()
            if bound_device:
                device_id = bound_device.id
                binding_status = "bound"
                # Update last_seen
                bound_device.last_seen_at = now
                await db.flush()

        # v3.4.3: Fallback — look up by board_id if no device found by install_id
        if not device_id and board_id:
            stmt = select(LicDevice).where(LicDevice.board_id == board_id).order_by(LicDevice.created_at.desc())
            result = await db.execute(stmt)
            board_device = result.scalars().first()
            if board_device:
                device_id = board_device.id
                location_id = board_device.location_id
                # Auto-bind: if device has no install_id yet, bind it now
                if install_id and not board_device.install_id:
                    board_device.install_id = install_id
                    board_device.binding_status = "bound"
                    board_device.first_seen_at = board_device.first_seen_at or now
                    board_device.last_seen_at = now
                    await db.flush()
                    binding_status = "first_bind"
                    logger.info(
                        f"[LICENSE] Auto-bind via board_id: board={board_id} "
                        f"install_id={install_id} device={board_device.id}"
                    )
                elif install_id and board_device.install_id == install_id:
                    binding_status = "bound"
                    board_device.last_seen_at = now
                    await db.flush()
                elif install_id and board_device.install_id != install_id:
                    binding_status = "mismatch"
                    logger.warning(
                        f"[LICENSE] Board device binding MISMATCH: board={board_id} "
                        f"install_id={install_id} expected={board_device.install_id}"
                    )

        # Resolve device → location → customer chain
        if device_id and not location_id:
            stmt = select(LicDevice).where(LicDevice.id == device_id)
            result = await db.execute(stmt)
            device = result.scalar_one_or_none()
            if device:
                location_id = device.location_id

        if location_id and not customer_id:
            stmt = select(LicLocation).where(LicLocation.id == location_id)
            result = await db.execute(stmt)
            loc = result.scalar_one_or_none()
            if loc:
                customer_id = loc.customer_id

        if not customer_id:
            return self._build_status("no_license", now)

        # Check customer status
        stmt = select(LicCustomer).where(LicCustomer.id == customer_id)
        result = await db.execute(stmt)
        customer = result.scalar_one_or_none()
        if not customer:
            return self._build_status("no_license", now)
        if customer.status == CustomerStatus.BLOCKED.value:
            return self._build_status("blocked", now, customer_name=customer.name)

        # Find all licenses for this customer
        conditions = [License.customer_id == customer_id]
        if location_id:
            conditions.append(
                (License.location_id == location_id) | (License.location_id.is_(None))
            )
        stmt = select(License).where(and_(*conditions))
        result = await db.execute(stmt)
        licenses = result.scalars().all()

        if not licenses:
            return self._build_status("no_license", now, customer_name=customer.name)

        # Find the best license (active > grace > test > expired > blocked)
        best = None
        best_priority = -1
        priority_map = {
            LicenseStatus.ACTIVE.value: 5,
            LicenseStatus.TEST.value: 4,
            LicenseStatus.GRACE.value: 3,
            LicenseStatus.EXPIRED.value: 1,
            LicenseStatus.BLOCKED.value: 0,
        }

        for lic in licenses:
            effective = self._compute_license_status(lic, now)
            p = priority_map.get(effective, 0)
            if p > best_priority:
                best_priority = p
                best = (lic, effective)

        if not best:
            return self._build_status("no_license", now, customer_name=customer.name)

        lic, effective_status = best
        grace_until = None
        days_remaining = None
        grace_days_remaining = None

        if lic.ends_at:
            ends = self._aware(lic.ends_at)
            if ends > now:
                days_remaining = (ends - now).days
            grace_until = self._aware(lic.grace_until) if lic.grace_until else (ends + timedelta(days=lic.grace_days or 0))
            if effective_status == LicenseStatus.GRACE.value and grace_until > now:
                grace_days_remaining = (grace_until - now).days

        # v3.4.3: Device binding check
        if install_id and effective_status in (
            LicenseStatus.ACTIVE.value, LicenseStatus.TEST.value, LicenseStatus.GRACE.value
        ):
            binding_status = await self._check_device_binding(
                db, install_id, location_id, now
            )

        return self._build_status(
            effective_status, now,
            license_id=lic.id,
            customer_name=customer.name,
            ends_at=lic.ends_at,
            grace_until=grace_until,
            days_remaining=days_remaining,
            grace_days_remaining=grace_days_remaining,
            max_devices=lic.max_devices,
            plan_type=lic.plan_type,
            binding_status=binding_status,
        )

    async def _check_device_binding(
        self, db: AsyncSession, install_id: str,
        location_id: Optional[str], now: datetime,
    ) -> str:
        """
        Check device binding for a given install_id.

        Returns: "bound" | "first_bind" | "mismatch" | None
        """
        if not location_id:
            return None

        # Look for any device at this location with a bound install_id
        stmt = select(LicDevice).where(
            LicDevice.location_id == location_id,
            LicDevice.install_id.isnot(None),
        )
        result = await db.execute(stmt)
        existing_devices = result.scalars().all()

        # Check if this install_id is already bound at this location
        for dev in existing_devices:
            if dev.install_id == install_id:
                if dev.binding_status != "bound":
                    dev.binding_status = "bound"
                    await db.flush()
                logger.info(f"[LICENSE] Device binding OK: install_id={install_id} device={dev.id}")
                return "bound"

        # No device with this install_id at this location
        # Check if there are ANY bound devices → this is a mismatch
        bound_devices = [d for d in existing_devices if d.binding_status == "bound"]
        if bound_devices:
            logger.warning(
                f"[LICENSE] Device binding MISMATCH: install_id={install_id} "
                f"expected={bound_devices[0].install_id} location={location_id}"
            )
            return "mismatch"

        # No bound devices yet → first bind (auto-create device record)
        new_device = LicDevice(
            location_id=location_id,
            install_id=install_id,
            binding_status="bound",
            device_name=f"Auto-bound {install_id[:8]}",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(new_device)
        await db.flush()
        logger.info(f"[LICENSE] First device bind: install_id={install_id} device={new_device.id} location={location_id}")
        return "first_bind"

    async def rebind_device(
        self, db: AsyncSession, device_id: str, new_install_id: str,
    ) -> dict:
        """
        Rebind a device record to a new install_id. Superadmin only.
        Clears mismatch status on all devices at that location.
        """
        stmt = select(LicDevice).where(LicDevice.id == device_id)
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()
        if not device:
            return {"error": "device_not_found"}

        old_install_id = device.install_id
        device.install_id = new_install_id
        device.binding_status = "bound"
        device.last_seen_at = _utcnow()
        await db.flush()

        logger.info(
            f"[LICENSE] Device REBOUND: device={device_id} "
            f"old_install_id={old_install_id} new_install_id={new_install_id}"
        )
        return {
            "device_id": device_id,
            "old_install_id": old_install_id,
            "new_install_id": new_install_id,
            "binding_status": "bound",
        }

    def _compute_license_status(self, lic: License, now: datetime) -> str:
        """Compute the real-time status of a license based on dates."""
        if lic.status == LicenseStatus.BLOCKED.value:
            return LicenseStatus.BLOCKED.value
        if lic.status == LicenseStatus.TEST.value:
            if lic.ends_at and self._aware(lic.ends_at) < now:
                return LicenseStatus.EXPIRED.value
            return LicenseStatus.TEST.value

        # Check time bounds
        if lic.starts_at and self._aware(lic.starts_at) > now:
            return LicenseStatus.EXPIRED.value  # not yet started
        if not lic.ends_at:
            return LicenseStatus.ACTIVE.value  # unlimited

        ends = self._aware(lic.ends_at)
        if ends > now:
            return LicenseStatus.ACTIVE.value

        # Past end date — check grace
        grace_end = self._aware(lic.grace_until) if lic.grace_until else (ends + timedelta(days=lic.grace_days or 0))
        if now <= grace_end:
            return LicenseStatus.GRACE.value

        return LicenseStatus.EXPIRED.value

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (SQLite stores naive)."""
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _build_status(self, status: str, now: datetime, **kwargs) -> dict:
        result = {
            "status": status,
            "license_id": kwargs.get("license_id"),
            "customer_name": kwargs.get("customer_name"),
            "plan_type": kwargs.get("plan_type"),
            "ends_at": kwargs.get("ends_at", "").isoformat() if kwargs.get("ends_at") else None,
            "grace_until": kwargs.get("grace_until", "").isoformat() if kwargs.get("grace_until") else None,
            "days_remaining": kwargs.get("days_remaining"),
            "grace_days_remaining": kwargs.get("grace_days_remaining"),
            "max_devices": kwargs.get("max_devices"),
            "checked_at": now.isoformat(),
        }
        # v3.4.3: include binding_status if present
        binding = kwargs.get("binding_status")
        if binding is not None:
            result["binding_status"] = binding
        return result

    # ── Local Cache ──────────────────────────────────────────

    def save_to_cache(self, status: dict):
        """Save license status to local cache file with signature."""
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "license_status": status,
                "cached_at": _utcnow().isoformat(),
            }
            payload["signature"] = _sign_cache({"license_status": status, "cached_at": payload["cached_at"]})
            _CACHE_FILE.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            logger.info(f"[LICENSE] Cache saved: status={status.get('status')}")
        except Exception as e:
            logger.error(f"[LICENSE] Cache save failed: {e}")

    def load_from_cache(self) -> Optional[dict]:
        """Load and verify license status from local cache."""
        try:
            if not _CACHE_FILE.exists():
                return None
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            stored_sig = data.pop("signature", "")
            expected_sig = _sign_cache(data)
            if stored_sig != expected_sig:
                logger.warning("[LICENSE] Cache signature mismatch — tampered or corrupted")
                return None
            return data.get("license_status")
        except Exception as e:
            logger.error(f"[LICENSE] Cache load failed: {e}")
            return None

    def is_session_allowed(self, status: dict) -> bool:
        """Check if a new game session should be allowed based on license status.

        Policy: fail-open when no license system is configured.
        - active, grace, test: allowed (if binding OK or no binding check)
        - no_license: allowed (system not configured yet)
        - expired, blocked: BLOCKED
        - binding_mismatch: BLOCKED (device not authorized)

        v3.4.3: binding_mismatch blocks sessions.
        """
        # Check binding first
        binding = status.get("binding_status")
        if binding == "mismatch":
            return False

        allowed = {"active", "grace", "test", "no_license"}
        return status.get("status") in allowed


license_service = LicenseValidationService()
