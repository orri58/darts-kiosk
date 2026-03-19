"""
Central License Server — v3.5.1

Separate FastAPI application that serves as the source of truth for license data.
Kiosk devices sync periodically with this server.

v3.5.0 Endpoints:
  POST /api/licensing/sync         — Kiosk sync endpoint (API-key authenticated)
  GET/POST /api/licensing/customers, locations, devices, licenses — Admin CRUD
  GET  /api/licensing/audit-log    — View audit log (admin)
  GET  /api/health                 — Health check

v3.5.1 Endpoints (Registration Flow):
  POST /api/registration-tokens           — Create registration token (admin)
  GET  /api/registration-tokens           — List tokens (admin)
  POST /api/registration-tokens/{id}/revoke — Revoke token (admin)
  POST /api/register-device               — Register device with token (public/controlled)
"""
import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import hashlib
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Request
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db, init_db, AsyncSessionLocal
from central_server.models import (
    CentralCustomer, CentralLocation, CentralDevice, CentralLicense,
    CentralAuditLog, RegistrationToken, LicenseStatus, CustomerStatus,
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
        await _log_audit(db, "SYNC_NO_LICENSE", device_id=device.id, install_id=device.install_id,
                         message="No customer found in chain")
        return {
            "license_status": "no_license",
            "binding_status": device.binding_status,
            "expiry": None,
            "server_timestamp": now.isoformat(),
            "plan_type": None,
            "customer_name": None,
        }

    if customer.status == CustomerStatus.BLOCKED.value:
        await _log_audit(db, "SYNC_BLOCKED", device_id=device.id, install_id=device.install_id,
                         message=f"Customer {customer.name} is blocked")
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
        await _log_audit(db, "SYNC_NO_LICENSE", device_id=device.id, install_id=device.install_id,
                         message=f"No licenses for customer {customer.name}")
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
        await _log_audit(db, "SYNC_NO_LICENSE", device_id=device.id, install_id=device.install_id,
                         message="No valid license found")
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

    await _log_audit(
        db, "SYNC_OK",
        device_id=device.id, install_id=device.install_id,
        message=f"status={best_status} plan={best_lic.plan_type} customer={customer.name}",
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
    return {"status": "ok", "service": "central-license-server", "version": "3.5.1", "timestamp": _utcnow().isoformat()}


# ═══════════════════════════════════════════════════════════════
# REGISTRATION TOKEN HELPERS (v3.5.1)
# ═══════════════════════════════════════════════════════════════

def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of a registration token. Never store raw token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _generate_reg_token() -> tuple:
    """Generate a cryptographically secure registration token.
    Returns (raw_token, token_hash, token_preview)."""
    raw = f"drt_{secrets.token_urlsafe(32)}"
    hashed = _hash_token(raw)
    preview = f"{raw[:8]}...{raw[-4:]}"
    return raw, hashed, preview


def _ser_reg_token(t: RegistrationToken) -> dict:
    return {
        "id": t.id,
        "token_preview": t.token_preview,
        "customer_id": t.customer_id,
        "location_id": t.location_id,
        "license_id": t.license_id,
        "device_name_template": t.device_name_template,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "used_at": t.used_at.isoformat() if t.used_at else None,
        "used_by_install_id": t.used_by_install_id,
        "used_by_device_id": t.used_by_device_id,
        "created_by": t.created_by,
        "note": t.note,
        "is_revoked": t.is_revoked,
        "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None,
        "revoked_by": t.revoked_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "status": _token_status(t),
    }


def _token_status(t: RegistrationToken) -> str:
    """Compute effective token status."""
    if t.is_revoked:
        return "revoked"
    if t.used_at:
        return "used"
    now = _utcnow()
    if t.expires_at and _aware(t.expires_at) < now:
        return "expired"
    return "active"


# ═══════════════════════════════════════════════════════════════
# REGISTRATION TOKEN CRUD (Admin)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/registration-tokens")
async def create_registration_token(
    data: dict,
    _=Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Create a one-time registration token.
    Body: {
        "customer_id": "...",          (optional but recommended)
        "location_id": "...",          (optional but recommended)
        "license_id": "...",           (optional)
        "device_name_template": "...", (optional)
        "expires_in_hours": 72,        (default: 72h)
        "note": "..."                  (optional)
    }
    Returns the raw token ONCE. It will never be shown again.
    """
    raw_token, token_hash, preview = _generate_reg_token()
    expires_in = int(data.get("expires_in_hours", 72))
    expires_at = _utcnow() + timedelta(hours=expires_in)

    token = RegistrationToken(
        token_hash=token_hash,
        token_preview=preview,
        customer_id=data.get("customer_id"),
        location_id=data.get("location_id"),
        license_id=data.get("license_id"),
        device_name_template=data.get("device_name_template"),
        expires_at=expires_at,
        created_by=data.get("created_by", "superadmin"),
        note=data.get("note"),
    )
    db.add(token)
    await db.flush()

    await _log_audit(db, "REG_TOKEN_CREATED", message=f"Token {preview} created, expires {expires_at.isoformat()}")

    logger.info(f"[REG] Token created: {preview} expires={expires_at.isoformat()}")

    result = _ser_reg_token(token)
    result["raw_token"] = raw_token  # Only returned ONCE at creation
    return result


@app.get("/api/registration-tokens")
async def list_registration_tokens(
    status: str = None,
    _=Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List registration tokens. Optional filter by status: active, used, expired, revoked."""
    stmt = select(RegistrationToken).order_by(RegistrationToken.created_at.desc())
    result = await db.execute(stmt)
    tokens = result.scalars().all()

    serialized = [_ser_reg_token(t) for t in tokens]
    if status:
        serialized = [t for t in serialized if t["status"] == status]
    return serialized


@app.post("/api/registration-tokens/{token_id}/revoke")
async def revoke_registration_token(
    token_id: str,
    data: dict = None,
    _=Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a registration token. Cannot be undone."""
    result = await db.execute(
        select(RegistrationToken).where(RegistrationToken.id == token_id)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(404, "Token not found")
    if token.is_revoked:
        raise HTTPException(400, "Token already revoked")
    if token.used_at:
        raise HTTPException(400, "Token already used — cannot revoke")

    token.is_revoked = True
    token.revoked_at = _utcnow()
    token.revoked_by = (data or {}).get("revoked_by", "superadmin")
    await db.flush()

    await _log_audit(db, "REG_TOKEN_REVOKED", message=f"Token {token.token_preview} revoked")

    logger.info(f"[REG] Token revoked: {token.token_preview}")
    return _ser_reg_token(token)


# ═══════════════════════════════════════════════════════════════
# DEVICE REGISTRATION (Public/Controlled)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/register-device")
async def register_device(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new device using a one-time registration token.

    Body: {
        "token": "drt_...",           (required — raw token)
        "install_id": "...",          (required)
        "device_name": "...",         (optional)
        "hostname": "...",            (optional)
        "app_version": "...",         (optional)
    }

    Security:
    - Token must be valid, unused, not expired, not revoked
    - install_id must not already be bound to another device
    - No silent overwrites — hard errors on conflicts
    """
    raw_token = body.get("token")
    install_id = body.get("install_id")
    device_name = body.get("device_name")

    if not raw_token:
        raise HTTPException(400, "Missing registration token")
    if not install_id:
        raise HTTPException(400, "Missing install_id")

    # Step 1: Find and validate token
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RegistrationToken).where(RegistrationToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if not token:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id,
                         message="Invalid registration token")
        raise HTTPException(403, "Invalid registration token")

    if token.is_revoked:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id,
                         message=f"Token {token.token_preview} is revoked")
        raise HTTPException(403, "Registration token has been revoked")

    if token.used_at:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id,
                         message=f"Token {token.token_preview} already used")
        raise HTTPException(403, "Registration token has already been used")

    now = _utcnow()
    if token.expires_at and _aware(token.expires_at) < now:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id,
                         message=f"Token {token.token_preview} expired at {token.expires_at.isoformat()}")
        raise HTTPException(403, "Registration token has expired")

    # Step 2: Check for install_id conflicts
    existing = await db.execute(
        select(CentralDevice).where(CentralDevice.install_id == install_id)
    )
    existing_device = existing.scalar_one_or_none()
    if existing_device:
        await _log_audit(db, "DEVICE_REGISTERED_BIND_CONFLICT", install_id=install_id,
                         device_id=existing_device.id,
                         message=f"install_id {install_id} already bound to device {existing_device.id}")
        raise HTTPException(409, f"install_id already bound to device {existing_device.id}. Rebind requires Superadmin.")

    # Step 3: Resolve customer/location from token
    location_id = token.location_id
    customer_id = token.customer_id

    if location_id and not customer_id:
        loc_result = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
        loc = loc_result.scalar_one_or_none()
        if loc:
            customer_id = loc.customer_id

    if not location_id and not customer_id:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id,
                         message="Token has no customer/location assignment")
        raise HTTPException(400, "Token has no customer or location assigned — cannot register device")

    # Step 4: Create device with API key + bind install_id
    api_key = f"dk_{secrets.token_urlsafe(32)}"
    effective_name = device_name or token.device_name_template or f"Kiosk-{install_id[:8]}"

    new_device = CentralDevice(
        location_id=location_id,
        install_id=install_id,
        api_key=api_key,
        device_name=effective_name,
        status="active",
        binding_status="bound",
        last_sync_at=now,
        last_sync_ip=request.client.host if request.client else None,
        sync_count=0,
        registered_via_token_id=token.id,
    )
    db.add(new_device)
    await db.flush()

    # Step 5: Mark token as used
    token.used_at = now
    token.used_by_install_id = install_id
    token.used_by_device_id = new_device.id
    await db.flush()

    # Step 6: Resolve license info for response
    license_status = "no_license"
    license_id = token.license_id
    plan_type = None
    expiry = None
    customer_name = None

    if customer_id:
        cust_result = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
        cust = cust_result.scalar_one_or_none()
        if cust:
            customer_name = cust.name

    if license_id:
        lic_result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
        lic = lic_result.scalar_one_or_none()
        if lic:
            license_status = _compute_status(lic, now)
            plan_type = lic.plan_type
            expiry = lic.ends_at.isoformat() if lic.ends_at else None
    elif customer_id:
        # Find best license for customer/location
        conditions = [CentralLicense.customer_id == customer_id]
        if location_id:
            conditions.append(
                (CentralLicense.location_id == location_id) | (CentralLicense.location_id.is_(None))
            )
        lic_result = await db.execute(select(CentralLicense).where(and_(*conditions)))
        lics = lic_result.scalars().all()
        if lics:
            best = max(lics, key=lambda x: {"active": 5, "test": 4, "grace": 3, "expired": 1, "blocked": 0}.get(_compute_status(x, now), 0))
            license_status = _compute_status(best, now)
            plan_type = best.plan_type
            license_id = best.id
            expiry = best.ends_at.isoformat() if best.ends_at else None

    await _log_audit(
        db, "DEVICE_REGISTERED",
        device_id=new_device.id,
        install_id=install_id,
        license_id=license_id,
        message=f"Device {effective_name} registered via token {token.token_preview}. "
                f"Customer={customer_name} License={license_status}",
    )
    await _log_audit(db, "REG_TOKEN_USED", message=f"Token {token.token_preview} used by {install_id}")

    logger.info(f"[REG] Device registered: {effective_name} install_id={install_id[:12]}... api_key={api_key[:12]}...")

    return {
        "success": True,
        "device_id": new_device.id,
        "device_name": effective_name,
        "api_key": api_key,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "location_id": location_id,
        "license_id": license_id,
        "license_status": license_status,
        "plan_type": plan_type,
        "expiry": expiry,
        "binding_status": "bound",
        "server_timestamp": now.isoformat(),
    }


async def _log_audit(
    db: AsyncSession,
    action: str,
    device_id: str = None,
    install_id: str = None,
    license_id: str = None,
    message: str = None,
):
    """Write to central audit log."""
    try:
        entry = CentralAuditLog(
            action=action,
            device_id=device_id,
            install_id=install_id,
            license_id=license_id,
            message=message,
            timestamp=_utcnow(),
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        logger.error(f"[AUDIT] Failed: {e}")
