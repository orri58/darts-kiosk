"""
Central License Server — v3.5.0

Separate FastAPI application that serves as the source of truth for license data.
Kiosk devices sync periodically with this server.

Endpoints:
  POST /api/licensing/sync         — Kiosk sync endpoint (API-key authenticated)
  GET  /api/licensing/devices      — List registered devices (admin)
  POST /api/licensing/devices      — Register a new device (admin)
  GET  /api/licensing/customers    — List customers (admin)
  POST /api/licensing/customers    — Create customer (admin)
  GET  /api/licensing/licenses     — List licenses (admin)
  POST /api/licensing/licenses     — Create license (admin)
  GET  /api/licensing/audit-log    — View sync audit log (admin)
  GET  /api/health                 — Health check
"""
import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Request
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db, init_db, AsyncSessionLocal
from central_server.models import (
    CentralCustomer, CentralLocation, CentralDevice, CentralLicense,
    CentralAuditLog, LicenseStatus, CustomerStatus,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CENTRAL] %(levelname)s %(message)s")
logger = logging.getLogger("central_server")

ADMIN_TOKEN = os.environ.get("CENTRAL_ADMIN_TOKEN", "admin-secret-token")


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ═══════════════════════════════════════════════════════════════
# LIFESPAN
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Central License Server started")
    yield
    logger.info("Central License Server shutting down")


app = FastAPI(title="Central License Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════

async def verify_device_api_key(request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate a kiosk device by its API key in X-License-Key header."""
    api_key = request.headers.get("X-License-Key")
    if not api_key:
        raise HTTPException(401, "Missing X-License-Key header")

    result = await db.execute(
        select(CentralDevice).where(CentralDevice.api_key == api_key)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(403, "Invalid API key")
    if device.status == "blocked":
        raise HTTPException(403, "Device is blocked")
    return device


async def verify_admin_token(request: Request):
    """Simple admin token auth for management endpoints."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token")


# ═══════════════════════════════════════════════════════════════
# SYNC ENDPOINT (Kiosk → Central)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/licensing/sync")
async def sync_license(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Main sync endpoint. Called by kiosk devices periodically.
    Authenticated by X-License-Key header.

    Request body:
      { "install_id": "uuid", "device_name": "optional" }

    Response:
      { "license_status": "active|grace|expired|blocked|no_license",
        "binding_status": "bound|unbound",
        "expiry": "ISO datetime or null",
        "server_timestamp": "ISO datetime",
        "plan_type": "standard|premium|test",
        "customer_name": "..." }
    """
    api_key = request.headers.get("X-License-Key")
    if not api_key:
        raise HTTPException(401, "Missing X-License-Key header")

    result = await db.execute(
        select(CentralDevice).where(CentralDevice.api_key == api_key)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(403, "Invalid API key")
    if device.status == "blocked":
        raise HTTPException(403, "Device is blocked")

    now = _utcnow()
    install_id = body.get("install_id")
    device_name = body.get("device_name")

    # Update device tracking
    if install_id and not device.install_id:
        device.install_id = install_id
        device.binding_status = "bound"
        logger.info(f"[SYNC] Device {device.id} bound to install_id={install_id}")
    elif install_id and device.install_id == install_id:
        device.binding_status = "bound"
    elif install_id and device.install_id != install_id:
        device.binding_status = "mismatch"
        logger.warning(f"[SYNC] Device {device.id}: install_id mismatch expected={device.install_id} got={install_id}")

    if device_name:
        device.device_name = device_name
    device.last_sync_at = now
    device.last_sync_ip = request.client.host if request.client else None
    device.sync_count = (device.sync_count or 0) + 1
    await db.flush()

    # Resolve license chain: device → location → customer → license
    location = None
    customer = None
    if device.location_id:
        res = await db.execute(select(CentralLocation).where(CentralLocation.id == device.location_id))
        location = res.scalar_one_or_none()

    if location and location.customer_id:
        res = await db.execute(select(CentralCustomer).where(CentralCustomer.id == location.customer_id))
        customer = res.scalar_one_or_none()

    if not customer:
        await _log_sync(db, device, "SYNC_NO_LICENSE", "No customer found in chain")
        return {
            "license_status": "no_license",
            "binding_status": device.binding_status,
            "expiry": None,
            "server_timestamp": now.isoformat(),
            "plan_type": None,
            "customer_name": None,
        }

    if customer.status == CustomerStatus.BLOCKED.value:
        await _log_sync(db, device, "SYNC_BLOCKED", f"Customer {customer.name} is blocked")
        return {
            "license_status": "blocked",
            "binding_status": device.binding_status,
            "expiry": None,
            "server_timestamp": now.isoformat(),
            "plan_type": None,
            "customer_name": customer.name,
        }

    # Find best license for this customer/location
    conditions = [CentralLicense.customer_id == customer.id]
    if location:
        conditions.append(
            (CentralLicense.location_id == location.id) | (CentralLicense.location_id.is_(None))
        )
    res = await db.execute(select(CentralLicense).where(and_(*conditions)))
    licenses = res.scalars().all()

    if not licenses:
        await _log_sync(db, device, "SYNC_NO_LICENSE", f"No licenses for customer {customer.name}")
        return {
            "license_status": "no_license",
            "binding_status": device.binding_status,
            "expiry": None,
            "server_timestamp": now.isoformat(),
            "plan_type": None,
            "customer_name": customer.name,
        }

    # Find best active license
    best_lic = None
    best_status = None
    best_priority = -1
    priority_map = {
        LicenseStatus.ACTIVE.value: 5,
        LicenseStatus.TEST.value: 4,
        LicenseStatus.GRACE.value: 3,
        LicenseStatus.EXPIRED.value: 1,
        LicenseStatus.BLOCKED.value: 0,
    }

    for lic in licenses:
        effective = _compute_status(lic, now)
        p = priority_map.get(effective, 0)
        if p > best_priority:
            best_priority = p
            best_lic = lic
            best_status = effective

    if not best_lic:
        await _log_sync(db, device, "SYNC_NO_LICENSE", "No valid license found")
        return {
            "license_status": "no_license",
            "binding_status": device.binding_status,
            "expiry": None,
            "server_timestamp": now.isoformat(),
            "plan_type": None,
            "customer_name": customer.name,
        }

    expiry = best_lic.ends_at.isoformat() if best_lic.ends_at else None
    grace_until = best_lic.grace_until.isoformat() if best_lic.grace_until else None

    await _log_sync(
        db, device, "SYNC_OK",
        f"status={best_status} plan={best_lic.plan_type} customer={customer.name}",
    )

    return {
        "license_status": best_status,
        "binding_status": device.binding_status,
        "expiry": expiry,
        "grace_until": grace_until,
        "server_timestamp": now.isoformat(),
        "plan_type": best_lic.plan_type,
        "customer_name": customer.name,
        "license_id": best_lic.id,
        "max_devices": best_lic.max_devices,
    }


def _compute_status(lic, now):
    if lic.status == LicenseStatus.BLOCKED.value:
        return LicenseStatus.BLOCKED.value
    if lic.status == LicenseStatus.TEST.value:
        if lic.ends_at and _aware(lic.ends_at) < now:
            return LicenseStatus.EXPIRED.value
        return LicenseStatus.TEST.value
    if lic.starts_at and _aware(lic.starts_at) > now:
        return LicenseStatus.EXPIRED.value
    if not lic.ends_at:
        return LicenseStatus.ACTIVE.value
    ends = _aware(lic.ends_at)
    if ends > now:
        return LicenseStatus.ACTIVE.value
    grace_end = _aware(lic.grace_until) if lic.grace_until else (ends + timedelta(days=lic.grace_days or 0))
    if now <= grace_end:
        return LicenseStatus.GRACE.value
    return LicenseStatus.EXPIRED.value


async def _log_sync(db: AsyncSession, device: CentralDevice, action: str, message: str):
    try:
        entry = CentralAuditLog(
            action=action,
            device_id=device.id,
            install_id=device.install_id,
            message=message,
            timestamp=_utcnow(),
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        logger.error(f"[AUDIT] Failed: {e}")


# ═══════════════════════════════════════════════════════════════
# ADMIN MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

def _ser_customer(c):
    return {
        "id": c.id, "name": c.name, "contact_email": c.contact_email,
        "status": c.status, "created_at": c.created_at.isoformat() if c.created_at else None,
    }

def _ser_location(loc):
    return {
        "id": loc.id, "customer_id": loc.customer_id, "name": loc.name,
        "address": loc.address, "status": loc.status,
    }

def _ser_device(d):
    return {
        "id": d.id, "location_id": d.location_id, "install_id": d.install_id,
        "api_key": d.api_key, "device_name": d.device_name, "status": d.status,
        "binding_status": d.binding_status,
        "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
        "sync_count": d.sync_count,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }

def _ser_license(lic):
    return {
        "id": lic.id, "customer_id": lic.customer_id, "location_id": lic.location_id,
        "plan_type": lic.plan_type, "max_devices": lic.max_devices, "status": lic.status,
        "starts_at": lic.starts_at.isoformat() if lic.starts_at else None,
        "ends_at": lic.ends_at.isoformat() if lic.ends_at else None,
        "grace_days": lic.grace_days,
        "grace_until": lic.grace_until.isoformat() if lic.grace_until else None,
    }


@app.get("/api/licensing/customers")
async def list_customers(_=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CentralCustomer).order_by(CentralCustomer.name))
    return [_ser_customer(c) for c in result.scalars().all()]


@app.post("/api/licensing/customers")
async def create_customer(data: dict, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    c = CentralCustomer(name=data["name"], contact_email=data.get("contact_email"))
    db.add(c)
    await db.flush()
    return _ser_customer(c)


@app.get("/api/licensing/locations")
async def list_locations(customer_id: str = None, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralLocation).order_by(CentralLocation.name)
    if customer_id:
        stmt = stmt.where(CentralLocation.customer_id == customer_id)
    result = await db.execute(stmt)
    return [_ser_location(loc) for loc in result.scalars().all()]


@app.post("/api/licensing/locations")
async def create_location(data: dict, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    loc = CentralLocation(customer_id=data["customer_id"], name=data["name"], address=data.get("address"))
    db.add(loc)
    await db.flush()
    return _ser_location(loc)


@app.get("/api/licensing/devices")
async def list_devices(location_id: str = None, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralDevice).order_by(CentralDevice.created_at.desc())
    if location_id:
        stmt = stmt.where(CentralDevice.location_id == location_id)
    result = await db.execute(stmt)
    return [_ser_device(d) for d in result.scalars().all()]


@app.post("/api/licensing/devices")
async def create_device(data: dict, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    import secrets
    api_key = data.get("api_key") or f"dk_{secrets.token_urlsafe(32)}"
    d = CentralDevice(
        location_id=data["location_id"],
        device_name=data.get("device_name"),
        api_key=api_key,
        install_id=data.get("install_id"),
    )
    db.add(d)
    await db.flush()
    logger.info(f"[ADMIN] Device registered: {d.device_name} api_key={api_key[:12]}...")
    return _ser_device(d)


@app.get("/api/licensing/licenses")
async def list_licenses(customer_id: str = None, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralLicense).order_by(CentralLicense.created_at.desc())
    if customer_id:
        stmt = stmt.where(CentralLicense.customer_id == customer_id)
    result = await db.execute(stmt)
    return [_ser_license(lic) for lic in result.scalars().all()]


@app.post("/api/licensing/licenses")
async def create_license(data: dict, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    ends_at = None
    grace_until = None
    if data.get("ends_at"):
        ends_at = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
        grace_days = data.get("grace_days", 7)
        grace_until = ends_at + timedelta(days=grace_days)

    lic = CentralLicense(
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
    )
    db.add(lic)
    await db.flush()
    return _ser_license(lic)


@app.get("/api/licensing/audit-log")
async def get_audit_log(limit: int = 50, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CentralAuditLog).order_by(CentralAuditLog.timestamp.desc()).limit(limit)
    )
    return [
        {
            "id": e.id, "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "action": e.action, "device_id": e.device_id, "install_id": e.install_id,
            "message": e.message,
        }
        for e in result.scalars().all()
    ]


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "central-license-server", "timestamp": _utcnow().isoformat()}
