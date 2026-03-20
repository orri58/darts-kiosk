"""
Licensing API Router — v3.4.1 MVP

Endpoints for managing customers, locations, devices, and licenses.
All endpoints require admin authentication.
Superadmin-only actions are noted in docstrings.

Prefix: /api/licensing
"""
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import require_admin
from backend.models import User
from backend.models.licensing import (
    LicCustomer, LicLocation, LicDevice, License, UserMembership,
    LicenseStatus, DeviceStatus, CustomerStatus, SystemRole,
)
from backend.services.license_service import license_service
from backend.services.audit_log_service import audit_log_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/licensing", tags=["licensing"])


def _utcnow():
    return datetime.now(timezone.utc)


def _serialize_customer(c):
    return {
        "id": c.id, "name": c.name, "contact_email": c.contact_email,
        "contact_phone": c.contact_phone, "notes": c.notes,
        "status": c.status, "created_at": c.created_at.isoformat() if c.created_at else None,
    }

def _serialize_location(loc):
    return {
        "id": loc.id, "customer_id": loc.customer_id, "name": loc.name,
        "address": loc.address, "status": loc.status,
        "created_at": loc.created_at.isoformat() if loc.created_at else None,
    }

def _serialize_device(d):
    return {
        "id": d.id, "location_id": d.location_id, "board_id": d.board_id,
        "install_id": d.install_id, "device_name": d.device_name,
        "status": d.status, "binding_status": d.binding_status,
        "first_seen_at": d.first_seen_at.isoformat() if d.first_seen_at else None,
        "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
        "mismatch_detected_at": d.mismatch_detected_at.isoformat() if d.mismatch_detected_at else None,
        "previous_install_id": d.previous_install_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }

def _serialize_license(lic):
    return {
        "id": lic.id, "customer_id": lic.customer_id,
        "location_id": lic.location_id, "plan_type": lic.plan_type,
        "max_devices": lic.max_devices, "status": lic.status,
        "starts_at": lic.starts_at.isoformat() if lic.starts_at else None,
        "ends_at": lic.ends_at.isoformat() if lic.ends_at else None,
        "grace_days": lic.grace_days,
        "grace_until": lic.grace_until.isoformat() if lic.grace_until else None,
        "notes": lic.notes,
        "created_at": lic.created_at.isoformat() if lic.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════

@router.get("/customers")
async def list_customers(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LicCustomer).order_by(LicCustomer.name))
    return [_serialize_customer(c) for c in result.scalars().all()]


@router.post("/customers")
async def create_customer(data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    customer = LicCustomer(
        name=data["name"],
        contact_email=data.get("contact_email"),
        contact_phone=data.get("contact_phone"),
        notes=data.get("notes"),
    )
    db.add(customer)
    await db.flush()
    logger.info(f"[LICENSE] Customer created: {customer.name} (id={customer.id})")
    return _serialize_customer(customer)


@router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LicCustomer).where(LicCustomer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")
    for field in ("name", "contact_email", "contact_phone", "notes", "status"):
        if field in data:
            setattr(customer, field, data[field])
    await db.flush()
    return _serialize_customer(customer)


# ═══════════════════════════════════════════════════════════════
# LOCATIONS
# ═══════════════════════════════════════════════════════════════

@router.get("/locations")
async def list_locations(customer_id: Optional[str] = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(LicLocation).order_by(LicLocation.name)
    if customer_id:
        stmt = stmt.where(LicLocation.customer_id == customer_id)
    result = await db.execute(stmt)
    return [_serialize_location(loc) for loc in result.scalars().all()]


@router.post("/locations")
async def create_location(data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    loc = LicLocation(
        customer_id=data["customer_id"],
        name=data["name"],
        address=data.get("address"),
    )
    db.add(loc)
    await db.flush()
    logger.info(f"[LICENSE] Location created: {loc.name} (customer={data['customer_id']})")
    return _serialize_location(loc)


# ═══════════════════════════════════════════════════════════════
# DEVICES
# ═══════════════════════════════════════════════════════════════

@router.get("/devices")
async def list_devices(location_id: Optional[str] = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(LicDevice).order_by(LicDevice.created_at.desc())
    if location_id:
        stmt = stmt.where(LicDevice.location_id == location_id)
    result = await db.execute(stmt)
    return [_serialize_device(d) for d in result.scalars().all()]


@router.post("/devices")
async def create_device(data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    device = LicDevice(
        location_id=data["location_id"],
        board_id=data.get("board_id"),
        device_name=data.get("device_name"),
        install_id=data.get("install_id"),
    )
    db.add(device)
    await db.flush()
    logger.info(f"[LICENSE] Device created: {device.device_name} at location={data['location_id']}")
    return _serialize_device(device)


@router.put("/devices/{device_id}")
async def update_device(device_id: str, data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LicDevice).where(LicDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    for field in ("board_id", "device_name", "install_id", "status"):
        if field in data:
            setattr(device, field, data[field])
    await db.flush()
    return _serialize_device(device)


# ═══════════════════════════════════════════════════════════════
# LICENSES
# ═══════════════════════════════════════════════════════════════

@router.get("/licenses")
async def list_licenses(customer_id: Optional[str] = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(License).order_by(License.created_at.desc())
    if customer_id:
        stmt = stmt.where(License.customer_id == customer_id)
    result = await db.execute(stmt)
    return [_serialize_license(lic) for lic in result.scalars().all()]


@router.post("/licenses")
async def create_license(data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    ends_at = None
    grace_until = None
    if data.get("ends_at"):
        ends_at = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
        grace_days = data.get("grace_days", 7)
        grace_until = ends_at + timedelta(days=grace_days)

    lic = License(
        customer_id=data["customer_id"],
        location_id=data.get("location_id"),
        plan_type=data.get("plan_type", "standard"),
        max_devices=data.get("max_devices", 1),
        status=data.get("status", LicenseStatus.ACTIVE.value),
        starts_at=datetime.fromisoformat(data["starts_at"].replace("Z", "+00:00")) if data.get("starts_at") else _utcnow(),
        ends_at=ends_at,
        grace_days=data.get("grace_days", 7),
        grace_until=grace_until,
        notes=data.get("notes"),
        created_by=admin.id,
    )
    db.add(lic)
    await db.flush()
    logger.info(f"[LICENSE] License created: plan={lic.plan_type} customer={data['customer_id']} status={lic.status}")
    await audit_log_service.log(
        db, "LICENSE_CREATED", license_id=lic.id, actor=admin.username,
        new_value={"plan_type": lic.plan_type, "status": lic.status, "customer_id": data["customer_id"]},
        message=f"License created: {lic.plan_type} for customer {data['customer_id']}",
    )
    return _serialize_license(lic)


@router.put("/licenses/{license_id}")
async def update_license(license_id: str, data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")

    for field in ("plan_type", "max_devices", "status", "notes", "grace_days"):
        if field in data:
            setattr(lic, field, data[field])

    if "ends_at" in data:
        if data["ends_at"]:
            lic.ends_at = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
            lic.grace_until = lic.ends_at + timedelta(days=lic.grace_days or 7)
        else:
            lic.ends_at = None
            lic.grace_until = None

    if "status" in data:
        lic.status = data["status"]

    await db.flush()
    logger.info(f"[LICENSE] License updated: id={license_id} status={lic.status}")
    return _serialize_license(lic)


@router.post("/licenses/{license_id}/block")
async def block_license(license_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    lic.status = LicenseStatus.BLOCKED.value
    await db.flush()
    logger.info(f"[LICENSE] License BLOCKED: id={license_id}")
    await audit_log_service.log(
        db, "LICENSE_BLOCKED", license_id=license_id, actor=admin.username,
        previous_value={"status": "active"}, new_value={"status": "blocked"},
    )
    return _serialize_license(lic)


@router.post("/licenses/{license_id}/activate")
async def activate_license(license_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    lic.status = LicenseStatus.ACTIVE.value
    await db.flush()
    logger.info(f"[LICENSE] License ACTIVATED: id={license_id}")
    await audit_log_service.log(
        db, "LICENSE_ACTIVATED", license_id=license_id, actor=admin.username,
        previous_value={"status": "blocked"}, new_value={"status": "active"},
    )
    return _serialize_license(lic)


@router.post("/licenses/{license_id}/extend")
async def extend_license(license_id: str, data: dict, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Extend a license by adding days to its end date."""
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")

    days = data.get("days", 30)
    now = _utcnow()
    base = lic.ends_at or now
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if base < now:
        base = now
    lic.ends_at = base + timedelta(days=days)
    lic.grace_until = lic.ends_at + timedelta(days=lic.grace_days or 7)
    if lic.status in (LicenseStatus.EXPIRED.value, LicenseStatus.GRACE.value):
        lic.status = LicenseStatus.ACTIVE.value
    await db.flush()
    logger.info(f"[LICENSE] License EXTENDED: id={license_id} +{days}d → ends_at={lic.ends_at.isoformat()}")
    await audit_log_service.log(
        db, "LICENSE_EXTENDED", license_id=license_id, actor=admin.username,
        new_value={"days": days, "ends_at": lic.ends_at.isoformat(), "status": lic.status},
        message=f"+{days}d → {lic.ends_at.isoformat()}",
    )
    return _serialize_license(lic)


# ═══════════════════════════════════════════════════════════════
# LICENSE STATUS CHECK
# ═══════════════════════════════════════════════════════════════

@router.get("/status")
async def get_license_status(
    device_id: Optional[str] = None,
    location_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get effective license status for a device/location/customer."""
    status = await license_service.get_effective_status(
        db, device_id=device_id, location_id=location_id, customer_id=customer_id,
    )
    # Save to local cache
    license_service.save_to_cache(status)
    return status


@router.get("/status/cached")
async def get_cached_license_status(admin: User = Depends(require_admin)):
    """Get the locally cached license status (for offline resilience check)."""
    cached = license_service.load_from_cache()
    if cached is None:
        return {"status": "no_cache", "message": "No cached license status available"}
    return {"status": "cached", "license_status": cached}


# ═══════════════════════════════════════════════════════════════
# DASHBOARD / OVERVIEW
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def licensing_dashboard(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Overview counts for the licensing admin UI."""
    customers = (await db.execute(select(func.count(LicCustomer.id)))).scalar() or 0
    locations = (await db.execute(select(func.count(LicLocation.id)))).scalar() or 0
    devices = (await db.execute(select(func.count(LicDevice.id)))).scalar() or 0
    licenses = (await db.execute(select(func.count(License.id)))).scalar() or 0
    active_licenses = (await db.execute(
        select(func.count(License.id)).where(License.status == LicenseStatus.ACTIVE.value)
    )).scalar() or 0
    blocked_licenses = (await db.execute(
        select(func.count(License.id)).where(License.status == LicenseStatus.BLOCKED.value)
    )).scalar() or 0

    return {
        "customers": customers,
        "locations": locations,
        "devices": devices,
        "licenses_total": licenses,
        "licenses_active": active_licenses,
        "licenses_blocked": blocked_licenses,
    }



# ═══════════════════════════════════════════════════════════════
# DEVICE IDENTITY (v3.4.3)
# ═══════════════════════════════════════════════════════════════

@router.get("/device-identity")
async def get_device_identity(admin: User = Depends(require_admin)):
    """Return the current device's install_id and fingerprints."""
    from backend.services.device_identity_service import device_identity_service
    identity = device_identity_service.get_identity()
    return identity


# ═══════════════════════════════════════════════════════════════
# DEVICE REBIND (v3.4.3 — Superadmin only)
# ═══════════════════════════════════════════════════════════════

@router.post("/devices/{device_id}/rebind")
async def rebind_device(
    device_id: str,
    data: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Rebind a device to a new install_id. Superadmin only.
    Body: { "new_install_id": "uuid-string" }
    """
    new_install_id = data.get("new_install_id")
    if not new_install_id:
        raise HTTPException(400, "new_install_id is required")

    result = await license_service.rebind_device(db, device_id, new_install_id)
    if "error" in result:
        raise HTTPException(404, result["error"])

    await audit_log_service.log(
        db, "DEVICE_REBOUND", device_id=device_id, install_id=new_install_id,
        actor=admin.username,
        previous_value={"install_id": result.get("old_install_id")},
        new_value={"install_id": new_install_id},
        message=f"Rebound: {result.get('old_install_id')} → {new_install_id}",
    )

    logger.info(
        f"[LICENSE] Device REBIND by {admin.username}: device={device_id} "
        f"old={result.get('old_install_id')} new={new_install_id}"
    )
    return result


# ═══════════════════════════════════════════════════════════════
# BINDING SETTINGS (v3.4.4)
# ═══════════════════════════════════════════════════════════════

@router.get("/binding-settings")
async def get_binding_settings(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Return current binding configuration."""
    from backend.models import Settings
    stmt = select(Settings).where(Settings.key == "binding_grace_hours")
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()
    return {
        "binding_grace_hours": int(s.value) if s and s.value is not None else 48,
    }


@router.post("/binding-settings")
async def update_binding_settings(
    data: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update binding configuration. Body: { "binding_grace_hours": 48 }"""
    hours = data.get("binding_grace_hours")
    if hours is None or not isinstance(hours, (int, float)) or hours < 0:
        raise HTTPException(400, "binding_grace_hours must be a non-negative number")

    from backend.models import Settings
    stmt = select(Settings).where(Settings.key == "binding_grace_hours")
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()
    if s:
        s.value = int(hours)
    else:
        db.add(Settings(key="binding_grace_hours", value=int(hours)))
    await db.flush()

    logger.info(f"[LICENSE] Binding grace hours updated to {hours} by {admin.username}")
    return {"binding_grace_hours": int(hours)}


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG (v3.4.5)
# ═══════════════════════════════════════════════════════════════

@router.get("/audit-log")
async def get_audit_log(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    action: str = None,
    license_id: str = None,
    device_id: str = None,
):
    """Return audit log entries with optional filters."""
    from backend.models.licensing import LicAuditLog
    stmt = select(LicAuditLog).order_by(LicAuditLog.timestamp.desc())

    if action:
        stmt = stmt.where(LicAuditLog.action == action)
    if license_id:
        stmt = stmt.where(LicAuditLog.license_id == license_id)
    if device_id:
        stmt = stmt.where(LicAuditLog.device_id == device_id)

    # Total count (with same filters)
    from sqlalchemy import func
    count_stmt = select(func.count(LicAuditLog.id))
    if action:
        count_stmt = count_stmt.where(LicAuditLog.action == action)
    if license_id:
        count_stmt = count_stmt.where(LicAuditLog.license_id == license_id)
    if device_id:
        count_stmt = count_stmt.where(LicAuditLog.device_id == device_id)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return {
        "total": total,
        "entries": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "action": e.action,
                "license_id": e.license_id,
                "device_id": e.device_id,
                "install_id": e.install_id,
                "previous_value": e.previous_value,
                "new_value": e.new_value,
                "actor": e.actor,
                "message": e.message,
            }
            for e in entries
        ],
    }


# ═══════════════════════════════════════════════════════════════
# LICENSE CHECK STATUS (v3.4.5)
# ═══════════════════════════════════════════════════════════════

@router.get("/check-status")
async def get_license_check_status(admin: User = Depends(require_admin)):
    """Return the status of the cyclic license checker."""
    from backend.services.cyclic_license_checker import cyclic_license_checker
    return cyclic_license_checker.get_status()


@router.post("/check-now")
async def trigger_license_check(admin: User = Depends(require_admin)):
    """Manually trigger a license check cycle."""
    from backend.services.cyclic_license_checker import cyclic_license_checker
    import asyncio
    asyncio.create_task(cyclic_license_checker._run_check())
    return {"triggered": True, "message": "License check triggered"}



# ═══════════════════════════════════════════════════════════════
# SYNC CONFIGURATION (v3.5.0)
# ═══════════════════════════════════════════════════════════════

@router.get("/sync-config")
async def get_sync_config(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Return the remote sync configuration."""
    from backend.models import Settings
    stmt = select(Settings).where(Settings.key == "license_sync_config")
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()
    config = s.value if s and s.value else {}
    # Never return the full API key — mask it
    masked_config = {**config}
    if masked_config.get("api_key"):
        key = masked_config["api_key"]
        masked_config["api_key_masked"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "****"
        del masked_config["api_key"]
    return {
        "enabled": config.get("enabled", False),
        "server_url": config.get("server_url", ""),
        "api_key_masked": masked_config.get("api_key_masked", ""),
        "api_key_set": bool(config.get("api_key")),
        "interval_hours": config.get("interval_hours", 6),
        "device_name": config.get("device_name", ""),
    }


@router.post("/sync-config")
async def update_sync_config(
    data: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update the remote sync configuration.
    Body: {
        "enabled": true/false,
        "server_url": "https://central.example.com",
        "api_key": "dk_...",        (optional — only update if provided)
        "interval_hours": 6,        (1-24)
        "device_name": "Kiosk 1"
    }
    """
    from backend.models import Settings

    # Load existing config
    stmt = select(Settings).where(Settings.key == "license_sync_config")
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()
    existing = s.value if s and s.value and isinstance(s.value, dict) else {}

    # Merge new values
    if "enabled" in data:
        existing["enabled"] = bool(data["enabled"])
    if "server_url" in data:
        existing["server_url"] = data["server_url"].rstrip("/") if data["server_url"] else ""
    if "api_key" in data and data["api_key"]:
        existing["api_key"] = data["api_key"]
    if "interval_hours" in data:
        existing["interval_hours"] = max(1, min(24, int(data["interval_hours"])))
    if "device_name" in data:
        existing["device_name"] = data["device_name"]

    if s:
        s.value = existing
    else:
        db.add(Settings(key="license_sync_config", value=existing))
    await db.flush()

    logger.info(f"[SYNC] Config updated by {admin.username}: enabled={existing.get('enabled')} url={existing.get('server_url')}")

    await audit_log_service.log(
        db, "SYNC_CONFIG_UPDATED",
        actor=admin.username,
        new_value={"enabled": existing.get("enabled"), "server_url": existing.get("server_url"), "interval_hours": existing.get("interval_hours")},
        message=f"Sync config updated by {admin.username}",
    )

    return {"ok": True, "config": {
        "enabled": existing.get("enabled", False),
        "server_url": existing.get("server_url", ""),
        "interval_hours": existing.get("interval_hours", 6),
        "device_name": existing.get("device_name", ""),
    }}


@router.get("/sync-status")
async def get_sync_status(admin: User = Depends(require_admin)):
    """Return the current sync client status (connected/offline, last sync, etc.)."""
    from backend.services.license_sync_client import license_sync_client
    from backend.services.cyclic_license_checker import cyclic_license_checker
    return {
        "sync": license_sync_client.get_status(),
        "checker": cyclic_license_checker.get_status(),
    }


@router.post("/sync-now")
async def trigger_sync_now(admin: User = Depends(require_admin)):
    """Manually trigger a sync cycle (remote + local fallback)."""
    from backend.services.cyclic_license_checker import cyclic_license_checker
    import asyncio
    asyncio.create_task(cyclic_license_checker._run_check())
    return {"triggered": True, "message": "Hybrid sync triggered"}



@router.get("/central-server-url")
async def get_central_server_url():
    """Return the configured central server URL (for kiosk registration overlay).
    Public endpoint — needed before registration."""
    import os
    # 1. Check env var (set in .env or build)
    url = os.environ.get("CENTRAL_SERVER_URL", "").strip()
    if url:
        return {"url": url, "source": "env", "configured": True}
    # 2. Check sync config in DB
    try:
        from backend.database import AsyncSessionLocal
        from backend.models import Settings
        async with AsyncSessionLocal() as db:
            stmt = select(Settings).where(Settings.key == "license_sync_config")
            result = await db.execute(stmt)
            s = result.scalar_one_or_none()
            if s and s.value and s.value.get("server_url"):
                return {"url": s.value["server_url"], "source": "sync_config", "configured": True}
    except Exception:
        pass
    return {"url": "", "source": "none", "configured": False}



# ═══════════════════════════════════════════════════════════════
# DEVICE REGISTRATION (v3.5.1)
# ═══════════════════════════════════════════════════════════════

@router.get("/registration-status")
async def get_registration_status():
    """Return device registration status. Public endpoint (no auth needed for kiosk UI)."""
    from backend.services.device_registration_client import device_registration_client
    from backend.services.device_identity_service import device_identity_service
    status = device_registration_client.get_status()
    status["install_id"] = device_identity_service.get_install_id()
    return status


@router.post("/register-device")
async def register_device_via_token(data: dict):
    """Register this kiosk device using a one-time registration token.
    Body: { "token": "drt_...", "device_name": "Kiosk 1" }
    This is a public endpoint — the token itself provides authorization.
    Registration MUST succeed online. No offline fallback.
    """
    from backend.services.device_registration_client import device_registration_client
    from backend.services.device_identity_service import device_identity_service
    from backend.models import Settings

    install_id = device_identity_service.get_install_id()
    token = data.get("token", "").strip()
    device_name = data.get("device_name", "").strip() or None

    if not token:
        raise HTTPException(status_code=400, detail="Kein Registrierungstoken angegeben")

    # Get server URL from sync config
    try:
        async with AsyncSession(bind=None) as _:
            pass
    except Exception:
        pass

    server_url = None
    # 1. Check env var CENTRAL_SERVER_URL
    import os
    server_url = os.environ.get("CENTRAL_SERVER_URL", "").strip() or None
    # 2. Check sync config in DB
    if not server_url:
        try:
            from backend.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                stmt = select(Settings).where(Settings.key == "license_sync_config")
                result = await db.execute(stmt)
                s = result.scalar_one_or_none()
                if s and s.value:
                    server_url = s.value.get("server_url")
        except Exception:
            pass
    # 3. Check request body
    if not server_url:
        server_url = data.get("server_url", "").strip() or None

    if not server_url:
        raise HTTPException(status_code=400, detail="Keine Server-URL konfiguriert. Bitte zuerst unter Sync-Konfiguration eintragen.")

    import platform
    hostname = platform.node()
    app_version = None
    try:
        version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"
        if version_file.exists():
            app_version = version_file.read_text().strip()
    except Exception:
        pass

    result = await device_registration_client.register(
        server_url=server_url,
        token=token,
        install_id=install_id,
        device_name=device_name,
        hostname=hostname,
        app_version=app_version,
    )

    if result.get("success"):
        # Log locally
        try:
            from backend.database import AsyncSessionLocal as ASL
            async with ASL() as db:
                await audit_log_service.log(
                    db, "DEVICE_REGISTERED",
                    install_id=install_id,
                    new_value={"device_id": result.get("device_id"), "customer": result.get("customer_name")},
                    message=f"Device registered via token. Customer={result.get('customer_name')}",
                )
                await db.commit()
        except Exception:
            pass
        return result
    else:
        status_code = result.get("status_code", 400)
        if status_code >= 500:
            status_code = 502
        raise HTTPException(status_code=status_code, detail=result.get("error", "Registrierung fehlgeschlagen"))
