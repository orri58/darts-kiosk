"""
License Validation Service — v3.4.1 MVP

Handles:
- License status computation (active/grace/expired/blocked)
- Local license cache for offline resilience
- Device registration and binding
- Grace period enforcement

Design:
- Does NOT modify existing runtime logic
- All DB operations use existing async session pattern
- Local cache is a signed JSON file for tamper detection
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
    """Validates license status for a device/location/customer."""

    async def get_effective_status(
        self, db: AsyncSession, device_id: Optional[str] = None,
        location_id: Optional[str] = None, customer_id: Optional[str] = None,
    ) -> dict:
        """
        Compute the effective license status for a device, location, or customer.

        Resolution order:
        1. Find device → get location → get customer
        2. Find all licenses for customer (and optionally location)
        3. Pick the most permissive active license
        4. Compute effective status considering grace period

        Returns:
            {
                "status": "active" | "grace" | "expired" | "blocked" | "no_license",
                "license_id": str | None,
                "customer_name": str | None,
                "ends_at": str | None,
                "grace_until": str | None,
                "days_remaining": int | None,
                "grace_days_remaining": int | None,
                "max_devices": int | None,
                "checked_at": str,
            }
        """
        now = _utcnow()

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
        )

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
        return {
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
        """Check if a new game session should be allowed based on license status."""
        allowed = {"active", "grace", "test"}
        return status.get("status") in allowed


license_service = LicenseValidationService()
