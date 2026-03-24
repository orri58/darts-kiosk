"""
License Validation Service — v3.4.4 Mismatch Grace + Tracking

Handles:
- License status computation (active/grace/expired/blocked)
- Local license cache for offline resilience
- Device registration and binding (install_id → LicDevice)
- Grace period enforcement
- Device binding check (install_id match/mismatch)
- Mismatch grace period (configurable, default 48h)
- Device tracking (first_seen, last_seen, mismatch_detected, previous_install_id)

Design:
- Does NOT modify existing runtime logic
- All DB operations use existing async session pattern
- Local cache is a signed JSON file for tamper detection
- Binding lives on LicDevice, NOT on License
- Auto-bind ONLY on start_game (trigger_binding=True), not on unlock_board
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

# Cache location — v3.15.1: Fixed path resolution (Path("") is truthy!)
_data_dir_env = os.environ.get("DATA_DIR", "").strip()
_DATA_DIR = Path(_data_dir_env) if _data_dir_env else (Path(__file__).resolve().parent.parent.parent / "data")
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

    # Default binding grace hours (configurable via settings table)
    DEFAULT_BINDING_GRACE_HOURS = 48

    async def _get_binding_grace_hours(self, db: AsyncSession) -> int:
        """Read configurable binding_grace_hours from settings table."""
        try:
            from backend.models import Settings
            stmt = select(Settings).where(Settings.key == "binding_grace_hours")
            result = await db.execute(stmt)
            s = result.scalar_one_or_none()
            if s and s.value is not None:
                return int(s.value)
        except Exception:
            pass
        return self.DEFAULT_BINDING_GRACE_HOURS

    async def get_effective_status(
        self, db: AsyncSession, device_id: Optional[str] = None,
        location_id: Optional[str] = None, customer_id: Optional[str] = None,
        install_id: Optional[str] = None, board_id: Optional[str] = None,
        trigger_binding: bool = False,
    ) -> dict:
        """
        Compute the effective license status for a device, location, or customer.

        v3.15.0: CRITICAL — Check local cache for centrally-enforced suspended/blocked
        state FIRST, before any DB queries. This ensures that a central lock
        (written by central_rejection_handler) cannot be bypassed by local DB state.

        v3.4.4: trigger_binding controls auto-bind behaviour:
        - trigger_binding=True (start_game): auto-binds unbound device to install_id
        - trigger_binding=False (unlock_board, license-status): checks only, no auto-bind

        Mismatch Grace logic:
        - On first mismatch: set mismatch_detected_at, return mismatch_grace
        - Within grace period: return mismatch_grace (sessions allowed)
        - After grace expired: return mismatch_expired (sessions blocked)
        """
        now = _utcnow()

        # ── v3.15.0: Central lock enforcement ──
        # If the central server has suspended this device (via 403 rejection),
        # the cache file contains {status: "suspended", source: "central_rejection"}.
        # This MUST take absolute priority over any local DB state.
        try:
            cached = self.load_from_cache()
            if cached and isinstance(cached, dict):
                cached_status = cached.get("status")
                if cached_status in ("suspended", "blocked", "inactive"):
                    logger.warning(
                        f"[LICENSE] Central lock enforced: status={cached_status} "
                        f"source={cached.get('source', 'cache')} — blocking all operations"
                    )
                    return {
                        "status": cached_status,
                        "checked_at": now.isoformat(),
                        "source": cached.get("source", "cache"),
                        "message": cached.get("message", "Device centrally locked"),
                        "binding_status": "suspended",
                    }
        except Exception as e:
            logger.error(f"[LICENSE] Cache check for central lock failed (continuing): {e}")

        binding_status = None

        # v3.4.3: If install_id provided, try to resolve device by install_id first
        if install_id and not device_id:
            stmt = select(LicDevice).where(LicDevice.install_id == install_id)
            result = await db.execute(stmt)
            bound_device = result.scalar_one_or_none()
            if bound_device:
                device_id = bound_device.id
                binding_status = "bound"
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

                if install_id and not board_device.install_id:
                    # Auto-bind ONLY when trigger_binding=True (start_game)
                    if trigger_binding:
                        board_device.install_id = install_id
                        board_device.binding_status = "bound"
                        board_device.first_seen_at = board_device.first_seen_at or now
                        board_device.last_seen_at = now
                        await db.flush()
                        binding_status = "first_bind"
                        logger.info(
                            f"[BIND_CREATED] board={board_id} install_id={install_id} device={board_device.id}"
                        )
                        try:
                            from backend.services.audit_log_service import audit_log_service
                            await audit_log_service.log(
                                db, "BIND_CREATED", device_id=board_device.id,
                                install_id=install_id,
                                new_value={"board_id": board_id, "binding_status": "bound"},
                                message=f"Auto-bind via board_id={board_id}",
                            )
                        except Exception:
                            pass
                    else:
                        # Not binding yet, just resolving chain
                        binding_status = "unbound"

                elif install_id and board_device.install_id == install_id:
                    binding_status = "bound"
                    board_device.last_seen_at = now
                    await db.flush()

                elif install_id and board_device.install_id != install_id:
                    # v3.4.4: Mismatch with grace period
                    grace_hours = await self._get_binding_grace_hours(db)
                    binding_status = self._evaluate_mismatch_grace(
                        board_device, install_id, now, grace_hours
                    )
                    await db.flush()
                    # v3.4.5: Audit log
                    try:
                        from backend.services.audit_log_service import audit_log_service
                        audit_action = "BIND_MISMATCH_DETECTED" if binding_status == "mismatch_grace" else "BIND_BLOCKED"
                        await audit_log_service.log(
                            db, audit_action, device_id=board_device.id, install_id=install_id,
                            previous_value={"install_id": board_device.install_id, "board_id": board_id},
                            message=f"Board {board_id}: {binding_status}",
                        )
                    except Exception:
                        pass

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

        # v3.4.4: Device binding check via _check_device_binding
        if install_id and binding_status is None and effective_status in (
            LicenseStatus.ACTIVE.value, LicenseStatus.TEST.value, LicenseStatus.GRACE.value
        ):
            grace_hours = await self._get_binding_grace_hours(db)
            binding_status = await self._check_device_binding(
                db, install_id, location_id, now, grace_hours, trigger_binding
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

    def _evaluate_mismatch_grace(
        self, device: LicDevice, new_install_id: str,
        now: datetime, grace_hours: int,
    ) -> str:
        """
        Evaluate mismatch grace period on a device.
        Updates device fields in-place (caller must flush).
        Audit logging is handled by the caller (async context).

        Returns: "mismatch_grace" | "mismatch_expired"
        """
        if not device.mismatch_detected_at:
            # First time mismatch detected
            device.mismatch_detected_at = now
            device.previous_install_id = device.install_id
            device.binding_status = "mismatch_grace"
            logger.warning(
                f"[BIND_MISMATCH_DETECTED] device={device.id} "
                f"expected={device.install_id} got={new_install_id} grace_hours={grace_hours}"
            )
            return "mismatch_grace"

        # Mismatch already detected — check grace window
        detected_at = self._aware(device.mismatch_detected_at)
        grace_end = detected_at + timedelta(hours=grace_hours)

        if now <= grace_end:
            remaining_hours = int((grace_end - now).total_seconds() / 3600)
            device.binding_status = "mismatch_grace"
            logger.info(
                f"[BIND_GRACE_ACTIVE] device={device.id} "
                f"remaining_hours={remaining_hours}"
            )
            return "mismatch_grace"
        else:
            device.binding_status = "mismatch_expired"
            logger.warning(
                f"[BIND_BLOCKED] device={device.id} "
                f"mismatch_detected_at={detected_at.isoformat()} grace expired"
            )
            return "mismatch_expired"

    async def _check_device_binding(
        self, db: AsyncSession, install_id: str,
        location_id: Optional[str], now: datetime,
        grace_hours: int, trigger_binding: bool = False,
    ) -> str:
        """
        Check device binding for a given install_id at a location.

        v3.4.4: Returns "bound" | "first_bind" | "mismatch_grace" | "mismatch_expired" | "unbound" | None
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
                if dev.binding_status not in ("bound",):
                    dev.binding_status = "bound"
                    dev.mismatch_detected_at = None  # Clear any old mismatch
                    await db.flush()
                logger.info(f"[LICENSE] Device binding OK: install_id={install_id} device={dev.id}")
                return "bound"

        # No device with this install_id at this location
        bound_devices = [d for d in existing_devices if d.binding_status in ("bound", "mismatch_grace", "mismatch_expired")]
        if bound_devices:
            # Evaluate mismatch grace on the first bound device
            dev = bound_devices[0]
            binding = self._evaluate_mismatch_grace(dev, install_id, now, grace_hours)
            await db.flush()
            # v3.4.5: Audit log for mismatch events
            try:
                from backend.services.audit_log_service import audit_log_service
                if binding == "mismatch_grace" and not dev.previous_install_id:
                    pass  # Already logged by _evaluate_mismatch_grace logger
                audit_action = "BIND_MISMATCH_DETECTED" if binding == "mismatch_grace" else "BIND_BLOCKED"
                await audit_log_service.log(
                    db, audit_action, device_id=dev.id, install_id=install_id,
                    previous_value={"install_id": dev.install_id},
                    message=f"{binding}: expected={dev.install_id} got={install_id}",
                )
            except Exception:
                pass
            return binding

        # No bound devices yet
        if trigger_binding:
            # First bind (auto-create device record)
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
            logger.info(f"[BIND_CREATED] install_id={install_id} device={new_device.id} location={location_id}")
            try:
                from backend.services.audit_log_service import audit_log_service
                await audit_log_service.log(
                    db, "BIND_CREATED", device_id=new_device.id,
                    install_id=install_id,
                    new_value={"location_id": location_id, "binding_status": "bound"},
                    message=f"First bind at location {location_id}",
                )
            except Exception:
                pass
            return "first_bind"

        return "unbound"

    async def rebind_device(
        self, db: AsyncSession, device_id: str, new_install_id: str,
    ) -> dict:
        """
        Rebind a device record to a new install_id. Superadmin only.
        Clears mismatch state and stores previous_install_id.
        """
        stmt = select(LicDevice).where(LicDevice.id == device_id)
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()
        if not device:
            return {"error": "device_not_found"}

        old_install_id = device.install_id
        device.previous_install_id = old_install_id
        device.install_id = new_install_id
        device.binding_status = "bound"
        device.mismatch_detected_at = None  # v3.4.4: clear mismatch state
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

    # ── v3.15.2: Central BLOCKED_STATES definition ──
    BLOCKED_STATES = frozenset({"suspended", "blocked", "inactive", "expired"})
    BLOCKED_BINDING_STATES = frozenset({"suspended", "mismatch_expired"})
    ALLOWED_STATES = frozenset({"active", "grace", "test", "no_license"})

    def is_session_allowed(self, status: dict) -> bool:
        """Check if a new game session should be allowed based on license status.

        v3.15.2: FAIL-CLOSED policy.
        - Only EXPLICITLY allowed states pass.
        - Everything else (including unknown states) is BLOCKED.
        - suspended, blocked, inactive, expired: HARD BLOCK
        - mismatch_expired, binding=suspended: HARD BLOCK
        - active, grace, test: ALLOWED
        - no_license: ALLOWED (system not configured yet)
        - mismatch_grace: ALLOWED (with warning)
        - unbound: ALLOWED (not yet bound)
        """
        current_status = status.get("status")

        # Hard block on known blocked states
        if current_status in self.BLOCKED_STATES:
            logger.warning(f"[LICENSE] Session BLOCKED: status={current_status}")
            return False

        # Hard block on known blocked binding states
        binding = status.get("binding_status")
        if binding in self.BLOCKED_BINDING_STATES:
            logger.warning(f"[LICENSE] Session BLOCKED: binding={binding}")
            return False

        # Only allow EXPLICITLY known good states
        if current_status in self.ALLOWED_STATES:
            return True

        # mismatch_grace — allowed with warning
        if binding == "mismatch_grace":
            logger.warning(f"[LICENSE] Session allowed under mismatch_grace")
            return True

        # unbound — allowed (not yet bound)
        if binding == "unbound":
            return True

        # UNKNOWN state — FAIL-CLOSED: block
        logger.warning(f"[LICENSE] Session BLOCKED: unknown status={current_status} binding={binding}")
        return False


license_service = LicenseValidationService()
