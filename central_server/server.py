"""
Central License Server — v3.6.0

4-tier RBAC: superadmin > installer > owner > staff
All endpoints enforce backend scope. No UI-only permissions.
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
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db, init_db, AsyncSessionLocal
from central_server.models import (
    CentralCustomer, CentralLocation, CentralDevice, CentralLicense,
    CentralAuditLog, RegistrationToken, CentralUser, LicenseStatus, CustomerStatus,
    TelemetryEvent, DeviceDailyStats, ConfigProfile, RemoteAction,
)
from central_server.auth import (
    get_current_user, AuthUser, require_superadmin, require_min_role,
    require_installer_or_above, require_owner_or_above,
    get_allowed_customer_ids, can_access_customer, can_access_location,
    apply_customer_scope, hash_password, verify_password, create_jwt,
    can_create_role, VALID_ROLES, ROLE_HIERARCHY,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CENTRAL] %(levelname)s %(message)s")
logger = logging.getLogger("central_server")


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
    # Migrate: add created_by_user_id column if missing
    try:
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT created_by_user_id FROM central_users LIMIT 1"))
    except Exception:
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(text("ALTER TABLE central_users ADD COLUMN created_by_user_id VARCHAR(36)"))
                await db.commit()
                logger.info("[MIGRATE] Added created_by_user_id to central_users")
            except Exception:
                pass

    # Migrate: add actor column to audit_log if missing
    try:
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT actor FROM audit_log LIMIT 1"))
    except Exception:
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(text("ALTER TABLE audit_log ADD COLUMN actor VARCHAR(100)"))
                await db.commit()
                logger.info("[MIGRATE] Added actor to audit_log")
            except Exception:
                pass

    # Migrate: update old 'operator' role to 'installer'
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CentralUser).where(CentralUser.role == "operator"))
        operators = result.scalars().all()
        if operators:
            for u in operators:
                u.role = "installer"
            await db.commit()
            logger.info(f"[MIGRATE] Migrated {len(operators)} 'operator' users to 'installer' role")

    # Ensure default superadmin exists
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CentralUser).where(CentralUser.role == "superadmin"))
        if not result.scalar_one_or_none():
            default_pw = os.environ.get("CENTRAL_ADMIN_PASSWORD", "admin")
            sa = CentralUser(
                username="superadmin",
                password_hash=hash_password(default_pw),
                display_name="Super Administrator",
                role="superadmin",
            )
            db.add(sa)
            await db.commit()
            logger.info("[INIT] Default superadmin user created")

    # v3.7.0: Migrate device heartbeat columns
    _migrate_cols = [
        ("devices", "last_heartbeat_at", "DATETIME"),
        ("devices", "reported_version", "VARCHAR(20)"),
        ("devices", "last_error", "TEXT"),
        ("devices", "last_activity_at", "DATETIME"),
    ]
    from sqlalchemy import text as _text
    for _tbl, _col, _typ in _migrate_cols:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(_text(f"SELECT {_col} FROM {_tbl} LIMIT 1"))
        except Exception:
            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(_text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}"))
                    await db.commit()
                    logger.info(f"[MIGRATE] Added {_col} to {_tbl}")
            except Exception:
                pass

    # v3.8.0: Create config_profiles table if not exists
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(_text("SELECT id FROM config_profiles LIMIT 1"))
    except Exception:
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(_text("""
                    CREATE TABLE IF NOT EXISTS config_profiles (
                        id VARCHAR(36) PRIMARY KEY,
                        scope_type VARCHAR(20) NOT NULL,
                        scope_id VARCHAR(36),
                        config_data JSON NOT NULL DEFAULT '{}',
                        version INTEGER DEFAULT 1,
                        updated_by VARCHAR(100),
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                """))
                await db.commit()
                logger.info("[MIGRATE] Created config_profiles table")
            except Exception as e:
                logger.warning(f"[MIGRATE] config_profiles: {e}")

    # Ensure default global config profile exists
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ConfigProfile).where(ConfigProfile.scope_type == "global")
        )
        if not result.scalar_one_or_none():
            global_config = ConfigProfile(
                scope_type="global",
                scope_id=None,
                config_data={
                    "pricing": {"mode": "per_game", "per_game": {"price_per_credit": 2.0, "default_credits": 3}},
                    "branding": {"cafe_name": "DartControl", "primary_color": "#f59e0b"},
                    "kiosk": {"auto_lock_timeout_min": 5, "idle_timeout_min": 15},
                },
                updated_by="system",
            )
            db.add(global_config)
            await db.commit()
            logger.info("[INIT] Default global config profile created")

    # v3.9.0: Create remote_actions table
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(_text("SELECT id FROM remote_actions LIMIT 1"))
    except Exception:
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(_text("""
                    CREATE TABLE IF NOT EXISTS remote_actions (
                        id VARCHAR(36) PRIMARY KEY,
                        device_id VARCHAR(36) NOT NULL,
                        action_type VARCHAR(30) NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        issued_by VARCHAR(100) NOT NULL,
                        issued_at DATETIME,
                        acked_at DATETIME,
                        result_message TEXT
                    )
                """))
                await db.commit()
                logger.info("[MIGRATE] Created remote_actions table")
            except Exception as e:
                logger.warning(f"[MIGRATE] remote_actions: {e}")

    # v3.9.3: Add observability columns to devices table
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(_text("SELECT health_snapshot FROM devices LIMIT 1"))
    except Exception:
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(_text("ALTER TABLE devices ADD COLUMN health_snapshot TEXT"))
                await db.execute(_text("ALTER TABLE devices ADD COLUMN device_logs TEXT"))
                await db.commit()
                logger.info("[MIGRATE] Added health_snapshot + device_logs columns to devices")
            except Exception as e:
                logger.warning(f"[MIGRATE] observability columns: {e}")

    # v3.9.4: Create config_history table
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(_text("""
                CREATE TABLE IF NOT EXISTS config_history (
                    id VARCHAR(36) PRIMARY KEY,
                    profile_id VARCHAR(36) NOT NULL,
                    scope_type VARCHAR(20) NOT NULL,
                    scope_id VARCHAR(36),
                    config_data JSON NOT NULL,
                    version INTEGER NOT NULL,
                    updated_by VARCHAR(100),
                    saved_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await db.execute(_text("CREATE INDEX IF NOT EXISTS ix_config_history_profile ON config_history(profile_id)"))
            await db.execute(_text("CREATE INDEX IF NOT EXISTS ix_config_history_scope ON config_history(scope_type, scope_id)"))
            await db.commit()
        except Exception as e:
            logger.warning(f"[MIGRATE] config_history: {e}")

    logger.info("Central License Server v3.9.4 started")
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
# SERIALIZERS
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

def _ser_user(u):
    return {
        "id": u.id, "username": u.username, "display_name": u.display_name,
        "role": u.role, "status": u.status,
        "allowed_customer_ids": u.allowed_customer_ids or [],
        "created_by_user_id": u.created_by_user_id,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
async def login(body: dict, db: AsyncSession = Depends(get_db)):
    username = body.get("username", "")
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(400, "Username and password required")

    result = await db.execute(select(CentralUser).where(CentralUser.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if user.status != "active":
        raise HTTPException(403, "Account disabled")

    token = create_jwt(user.id, user.username, user.role)
    return {
        "access_token": token,
        "user": _ser_user(user),
    }


@app.get("/api/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_superadmin": user.is_superadmin,
        "allowed_customer_ids": user.allowed_customer_ids,
    }


# ═══════════════════════════════════════════════════════════════
# USERS — RBAC enforced
# ═══════════════════════════════════════════════════════════════

@app.get("/api/users")
async def list_users(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List users. Superadmin sees all. Installer/Owner see users they created."""
    require_min_role(user, "owner")
    stmt = select(CentralUser).order_by(CentralUser.username)
    if not user.is_superadmin:
        # Non-superadmins see only users they created + themselves
        stmt = stmt.where(
            (CentralUser.created_by_user_id == user.id) | (CentralUser.id == user.id)
        )
    result = await db.execute(stmt)
    return [_ser_user(u) for u in result.scalars().all()]


@app.post("/api/users")
async def create_user(data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a user. RBAC: creator can only create roles below their own level."""
    require_min_role(user, "owner")  # owner+ can create users (limited by can_create_role)

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        raise HTTPException(400, "Username and password required")
    if len(password) < 4:
        raise HTTPException(400, "Password too short (min 4)")

    existing = await db.execute(select(CentralUser).where(CentralUser.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Username already exists")

    role = data.get("role", "staff")
    if role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Valid: {', '.join(sorted(VALID_ROLES))}")
    if not can_create_role(user, role):
        raise HTTPException(403, f"You cannot create users with role '{role}'")

    # Scope: new user can only access customers within creator's scope
    allowed_ids = data.get("allowed_customer_ids", [])
    if not user.is_superadmin:
        creator_scope = set(user.allowed_customer_ids or [])
        requested_scope = set(allowed_ids)
        if not requested_scope.issubset(creator_scope):
            raise HTTPException(403, "Cannot assign customers outside your own scope")

    new_user = CentralUser(
        username=username,
        password_hash=hash_password(password),
        display_name=data.get("display_name", username),
        role=role,
        allowed_customer_ids=allowed_ids,
        created_by_user_id=user.id,
    )
    db.add(new_user)
    await db.flush()

    await _log_audit(db, "USER_CREATED", actor=user.username,
                     message=f"User {username} ({role}) created by {user.username}")

    return _ser_user(new_user)


@app.put("/api/users/{user_id}")
async def update_user(user_id: str, data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update a user. Superadmin can edit anyone. Others can only edit users they created."""
    require_min_role(user, "owner")

    result = await db.execute(select(CentralUser).where(CentralUser.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")

    # Non-superadmin: can only edit users they created
    if not user.is_superadmin and target.created_by_user_id != user.id:
        raise HTTPException(403, "You can only edit users you created")

    changes = []
    if "display_name" in data:
        target.display_name = data["display_name"]
        changes.append("display_name")
    if "role" in data:
        new_role = data["role"]
        if new_role not in VALID_ROLES:
            raise HTTPException(400, f"Invalid role")
        if not user.is_superadmin and not can_create_role(user, new_role):
            raise HTTPException(403, f"Cannot assign role '{new_role}'")
        old_role = target.role
        target.role = new_role
        changes.append(f"role: {old_role} -> {new_role}")
    if "allowed_customer_ids" in data:
        new_scope = data["allowed_customer_ids"]
        if not user.is_superadmin:
            creator_scope = set(user.allowed_customer_ids or [])
            if not set(new_scope).issubset(creator_scope):
                raise HTTPException(403, "Cannot assign customers outside your scope")
        target.allowed_customer_ids = new_scope
        changes.append("allowed_customer_ids")
    if "status" in data and data["status"] in ("active", "disabled"):
        target.status = data["status"]
        changes.append(f"status: {data['status']}")
    if "password" in data and data["password"]:
        target.password_hash = hash_password(data["password"])
        changes.append("password")

    await db.flush()
    await _log_audit(db, "USER_UPDATED", actor=user.username,
                     message=f"User {target.username} updated: {', '.join(changes)}")

    return _ser_user(target)


# ═══════════════════════════════════════════════════════════════
# SCOPE ENDPOINTS — for context switcher
# ═══════════════════════════════════════════════════════════════

@app.get("/api/scope/customers")
async def scope_customers(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return customers within user's scope (for context switcher)."""
    stmt = select(CentralCustomer).where(CentralCustomer.status != "blocked").order_by(CentralCustomer.name)
    stmt = apply_customer_scope(stmt, user, CentralCustomer.id)
    result = await db.execute(stmt)
    return [{"id": c.id, "name": c.name, "status": c.status} for c in result.scalars().all()]


@app.get("/api/scope/locations")
async def scope_locations(customer_id: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return locations within user's scope."""
    stmt = select(CentralLocation).order_by(CentralLocation.name)
    if customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        stmt = stmt.where(CentralLocation.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLocation.customer_id)
    result = await db.execute(stmt)
    return [{"id": l.id, "name": l.name, "customer_id": l.customer_id, "status": l.status} for l in result.scalars().all()]


@app.get("/api/scope/devices")
async def scope_devices(location_id: str = None, customer_id: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return devices within user's scope."""
    if location_id:
        if not await can_access_location(user, location_id, db):
            raise HTTPException(403, "Access denied")
        stmt = select(CentralDevice).where(CentralDevice.location_id == location_id)
    elif customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        loc_ids = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id == customer_id))
        ids = [r[0] for r in loc_ids.fetchall()]
        stmt = select(CentralDevice).where(CentralDevice.location_id.in_(ids)) if ids else select(CentralDevice).where(False)
    else:
        if user.is_superadmin:
            stmt = select(CentralDevice)
        else:
            stmt = select(CentralDevice).join(CentralLocation, CentralDevice.location_id == CentralLocation.id)
            stmt = apply_customer_scope(stmt, user, CentralLocation.customer_id)
    stmt = stmt.order_by(CentralDevice.device_name)
    result = await db.execute(stmt)
    return [{"id": d.id, "device_name": d.device_name, "location_id": d.location_id, "status": d.status} for d in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════
# DASHBOARD — scoped overview
# ═══════════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def dashboard(customer_id: str = None, location_id: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Scoped dashboard stats."""
    # Build filters
    cust_filter = []
    loc_filter = []
    dev_filter = []
    lic_filter = []

    if location_id:
        if not await can_access_location(user, location_id, db):
            raise HTTPException(403, "Access denied")
        loc_filter.append(CentralLocation.id == location_id)
        dev_filter.append(CentralDevice.location_id == location_id)
    elif customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        cust_filter.append(CentralCustomer.id == customer_id)
        loc_filter.append(CentralLocation.customer_id == customer_id)
        lic_filter.append(CentralLicense.customer_id == customer_id)
    elif not user.is_superadmin:
        allowed = user.allowed_customer_ids or []
        cust_filter.append(CentralCustomer.id.in_(allowed))
        loc_filter.append(CentralLocation.customer_id.in_(allowed))
        lic_filter.append(CentralLicense.customer_id.in_(allowed))

    # Counts
    cust_q = select(func.count(CentralCustomer.id))
    for f in cust_filter: cust_q = cust_q.where(f)
    customers = (await db.execute(cust_q)).scalar() or 0

    loc_q = select(func.count(CentralLocation.id))
    for f in loc_filter: loc_q = loc_q.where(f)
    locations = (await db.execute(loc_q)).scalar() or 0

    # Devices: need to filter via location join if not filtering by location_id
    if dev_filter:
        dev_q = select(func.count(CentralDevice.id))
        for f in dev_filter: dev_q = dev_q.where(f)
    elif loc_filter:
        sub = select(CentralLocation.id)
        for f in loc_filter: sub = sub.where(f)
        loc_ids_result = await db.execute(sub)
        loc_ids = [r[0] for r in loc_ids_result.fetchall()]
        dev_q = select(func.count(CentralDevice.id)).where(CentralDevice.location_id.in_(loc_ids)) if loc_ids else select(func.count(CentralDevice.id)).where(False)
    else:
        dev_q = select(func.count(CentralDevice.id))
    devices = (await db.execute(dev_q)).scalar() or 0

    lic_q = select(func.count(CentralLicense.id))
    for f in lic_filter: lic_q = lic_q.where(f)
    total_lic = (await db.execute(lic_q)).scalar() or 0

    lic_active_q = select(func.count(CentralLicense.id)).where(CentralLicense.status == LicenseStatus.ACTIVE.value)
    for f in lic_filter: lic_active_q = lic_active_q.where(f)
    active_lic = (await db.execute(lic_active_q)).scalar() or 0

    # Recent devices for health view
    if dev_filter:
        dev_stmt = select(CentralDevice)
        for f in dev_filter: dev_stmt = dev_stmt.where(f)
    elif loc_filter:
        dev_stmt = select(CentralDevice).where(CentralDevice.location_id.in_(loc_ids)) if loc_ids else select(CentralDevice).where(False)
    else:
        dev_stmt = select(CentralDevice)
    dev_stmt = dev_stmt.order_by(CentralDevice.last_sync_at.desc().nullslast()).limit(20)
    dev_result = await db.execute(dev_stmt)
    recent_devices = []
    now = _utcnow()
    for d in dev_result.scalars().all():
        online = False
        if d.last_sync_at:
            diff = (now - _aware(d.last_sync_at)).total_seconds()
            online = diff < 600  # 10 min
        recent_devices.append({
            "id": d.id, "device_name": d.device_name, "status": d.status,
            "online": online, "binding_status": d.binding_status,
            "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
            "sync_count": d.sync_count,
        })

    return {
        "customers": customers, "locations": locations, "devices": devices,
        "licenses_total": total_lic, "licenses_active": active_lic,
        "recent_devices": recent_devices,
    }


# ═══════════════════════════════════════════════════════════════
# ROLES INFO
# ═══════════════════════════════════════════════════════════════

@app.get("/api/roles")
async def get_roles(user: AuthUser = Depends(get_current_user)):
    """Return role hierarchy and what the current user can create."""
    from central_server.auth import ROLE_CAN_CREATE
    return {
        "current_role": user.role,
        "hierarchy": ROLE_HIERARCHY,
        "can_create": sorted(ROLE_CAN_CREATE.get(user.role, set())),
    }


# ═══════════════════════════════════════════════════════════════
# SYNC ENDPOINT (Kiosk → Central)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/licensing/sync")
async def sync_license(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Main sync endpoint. Called by kiosk devices periodically."""
    api_key = request.headers.get("X-License-Key")
    if not api_key:
        raise HTTPException(401, "Missing X-License-Key header")

    result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(403, "Invalid API key")
    if device.status == "blocked":
        raise HTTPException(403, "Device is blocked")

    now = _utcnow()
    install_id = body.get("install_id")
    device_name = body.get("device_name")

    if install_id and not device.install_id:
        device.install_id = install_id
        device.binding_status = "bound"
    elif install_id and device.install_id == install_id:
        device.binding_status = "bound"
    elif install_id and device.install_id != install_id:
        device.binding_status = "mismatch"

    if device_name:
        device.device_name = device_name
    device.last_sync_at = now
    device.last_sync_ip = request.client.host if request.client else None
    device.sync_count = (device.sync_count or 0) + 1
    await db.flush()

    # Resolve license chain
    location = None
    customer = None
    if device.location_id:
        res = await db.execute(select(CentralLocation).where(CentralLocation.id == device.location_id))
        location = res.scalar_one_or_none()
    if location and location.customer_id:
        res = await db.execute(select(CentralCustomer).where(CentralCustomer.id == location.customer_id))
        customer = res.scalar_one_or_none()

    if not customer:
        return {"license_status": "no_license", "binding_status": device.binding_status,
                "expiry": None, "server_timestamp": now.isoformat(), "plan_type": None, "customer_name": None}

    if customer.status == CustomerStatus.BLOCKED.value:
        return {"license_status": "blocked", "binding_status": device.binding_status,
                "expiry": None, "server_timestamp": now.isoformat(), "plan_type": None, "customer_name": customer.name}

    conditions = [CentralLicense.customer_id == customer.id]
    if location:
        conditions.append((CentralLicense.location_id == location.id) | (CentralLicense.location_id.is_(None)))
    res = await db.execute(select(CentralLicense).where(and_(*conditions)))
    licenses = res.scalars().all()

    if not licenses:
        return {"license_status": "no_license", "binding_status": device.binding_status,
                "expiry": None, "server_timestamp": now.isoformat(), "plan_type": None, "customer_name": customer.name}

    best_lic, best_status = _find_best_license(licenses, now)
    if not best_lic:
        return {"license_status": "no_license", "binding_status": device.binding_status,
                "expiry": None, "server_timestamp": now.isoformat(), "plan_type": None, "customer_name": customer.name}

    return {
        "license_status": best_status, "binding_status": device.binding_status,
        "expiry": best_lic.ends_at.isoformat() if best_lic.ends_at else None,
        "grace_until": best_lic.grace_until.isoformat() if best_lic.grace_until else None,
        "server_timestamp": now.isoformat(), "plan_type": best_lic.plan_type,
        "customer_name": customer.name, "license_id": best_lic.id, "max_devices": best_lic.max_devices,
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


def _find_best_license(licenses, now):
    priority_map = {"active": 5, "test": 4, "grace": 3, "expired": 1, "blocked": 0}
    best_lic = None
    best_status = None
    best_p = -1
    for lic in licenses:
        s = _compute_status(lic, now)
        p = priority_map.get(s, 0)
        if p > best_p:
            best_p = p
            best_lic = lic
            best_status = s
    return best_lic, best_status


# ═══════════════════════════════════════════════════════════════
# CUSTOMERS — installer+ can create, all scoped roles can read
# ═══════════════════════════════════════════════════════════════

@app.get("/api/licensing/customers")
async def list_customers(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralCustomer).order_by(CentralCustomer.name)
    stmt = apply_customer_scope(stmt, user, CentralCustomer.id)
    result = await db.execute(stmt)
    return [_ser_customer(c) for c in result.scalars().all()]


@app.post("/api/licensing/customers")
async def create_customer(data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    c = CentralCustomer(name=data["name"], contact_email=data.get("contact_email"))
    db.add(c)
    await db.flush()
    # Auto-add to creator's scope if not superadmin
    if not user.is_superadmin:
        u_result = await db.execute(select(CentralUser).where(CentralUser.id == user.id))
        u = u_result.scalar_one_or_none()
        if u:
            ids = list(u.allowed_customer_ids or [])
            ids.append(c.id)
            u.allowed_customer_ids = ids
            await db.flush()
    await _log_audit(db, "CUSTOMER_CREATED", actor=user.username, message=f"Customer '{c.name}' created")
    return _ser_customer(c)


@app.put("/api/licensing/customers/{customer_id}")
async def update_customer(customer_id: str, data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    if not can_access_customer(user, customer_id):
        raise HTTPException(403, "Access denied")
    result = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Customer not found")
    old_status = c.status
    for field in ("name", "contact_email", "contact_phone", "notes", "status"):
        if field in data:
            setattr(c, field, data[field])
    await db.flush()
    if "status" in data and data["status"] != old_status:
        await _log_audit(db, "CUSTOMER_STATUS_CHANGED", actor=user.username,
                         message=f"Customer '{c.name}' status: {old_status} -> {data['status']}")
    return _ser_customer(c)


# ═══════════════════════════════════════════════════════════════
# LOCATIONS — installer+ can create within scope
# ═══════════════════════════════════════════════════════════════

@app.get("/api/licensing/locations")
async def list_locations(customer_id: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralLocation).order_by(CentralLocation.name)
    if customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        stmt = stmt.where(CentralLocation.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLocation.customer_id)
    result = await db.execute(stmt)
    return [_ser_location(loc) for loc in result.scalars().all()]


@app.post("/api/licensing/locations")
async def create_location(data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    if not can_access_customer(user, data["customer_id"]):
        raise HTTPException(403, "Access denied to this customer")
    loc = CentralLocation(customer_id=data["customer_id"], name=data["name"], address=data.get("address"))
    db.add(loc)
    await db.flush()
    await _log_audit(db, "LOCATION_CREATED", actor=user.username, message=f"Location '{loc.name}' created")
    return _ser_location(loc)


@app.put("/api/licensing/locations/{location_id}")
async def update_location(location_id: str, data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    if not await can_access_location(user, location_id, db):
        raise HTTPException(403, "Access denied")
    result = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(404, "Location not found")
    for field in ("name", "address", "status"):
        if field in data:
            setattr(loc, field, data[field])
    await db.flush()
    await _log_audit(db, "LOCATION_UPDATED", actor=user.username, message=f"Location '{loc.name}' updated")
    return _ser_location(loc)


# ═══════════════════════════════════════════════════════════════
# DEVICES — installer+ can create, all scoped can read
# ═══════════════════════════════════════════════════════════════

@app.get("/api/licensing/devices")
async def list_devices(location_id: str = None, customer_id: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if location_id:
        if not await can_access_location(user, location_id, db):
            raise HTTPException(403, "Access denied")
        stmt = select(CentralDevice).where(CentralDevice.location_id == location_id)
    elif customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        loc_ids_r = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id == customer_id))
        loc_ids = [r[0] for r in loc_ids_r.fetchall()]
        stmt = select(CentralDevice).where(CentralDevice.location_id.in_(loc_ids)) if loc_ids else select(CentralDevice).where(False)
    else:
        if user.is_superadmin:
            stmt = select(CentralDevice)
        else:
            stmt = select(CentralDevice).join(CentralLocation, CentralDevice.location_id == CentralLocation.id)
            stmt = apply_customer_scope(stmt, user, CentralLocation.customer_id)
    stmt = stmt.order_by(CentralDevice.created_at.desc())
    result = await db.execute(stmt)
    return [_ser_device(d) for d in result.scalars().all()]


@app.post("/api/licensing/devices")
async def create_device(data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    if not await can_access_location(user, data["location_id"], db):
        raise HTTPException(403, "Access denied to this location")
    api_key = data.get("api_key") or f"dk_{secrets.token_urlsafe(32)}"
    d = CentralDevice(location_id=data["location_id"], device_name=data.get("device_name"),
                       api_key=api_key, install_id=data.get("install_id"))
    db.add(d)
    await db.flush()
    await _log_audit(db, "DEVICE_CREATED", device_id=d.id, actor=user.username, message=f"Device '{d.device_name}' created")
    return _ser_device(d)


@app.put("/api/licensing/devices/{device_id}")
async def update_device(device_id: str, data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update device. installer+ within scope."""
    require_installer_or_above(user)
    result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Device not found")
    if not await can_access_location(user, d.location_id, db):
        raise HTTPException(403, "Access denied")
    old_status = d.status
    for field in ("device_name", "status"):
        if field in data:
            setattr(d, field, data[field])
    await db.flush()
    if "status" in data and data["status"] != old_status:
        await _log_audit(db, "DEVICE_STATUS_CHANGED", device_id=d.id, actor=user.username,
                         message=f"Device '{d.device_name}' status: {old_status} -> {data['status']}")
    return _ser_device(d)


# ═══════════════════════════════════════════════════════════════
# LICENSES — superadmin + installer can manage
# ═══════════════════════════════════════════════════════════════

@app.get("/api/licensing/licenses")
async def list_licenses(customer_id: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralLicense).order_by(CentralLicense.created_at.desc())
    if customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        stmt = stmt.where(CentralLicense.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLicense.customer_id)
    result = await db.execute(stmt)
    return [_ser_license(lic) for lic in result.scalars().all()]


@app.post("/api/licensing/licenses")
async def create_license(data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    if not can_access_customer(user, data["customer_id"]):
        raise HTTPException(403, "Access denied to this customer")
    ends_at = None
    grace_until = None
    if data.get("ends_at"):
        ends_at = datetime.fromisoformat(data["ends_at"].replace("Z", "+00:00"))
        grace_days = data.get("grace_days", 7)
        grace_until = ends_at + timedelta(days=grace_days)
    lic = CentralLicense(
        customer_id=data["customer_id"], location_id=data.get("location_id"),
        plan_type=data.get("plan_type", "standard"), max_devices=data.get("max_devices", 1),
        status=data.get("status", LicenseStatus.ACTIVE.value),
        starts_at=datetime.fromisoformat(data["starts_at"].replace("Z", "+00:00")) if data.get("starts_at") else _utcnow(),
        ends_at=ends_at, grace_days=data.get("grace_days", 7), grace_until=grace_until, notes=data.get("notes"),
    )
    db.add(lic)
    await db.flush()
    await _log_audit(db, "LICENSE_CREATED", license_id=lic.id, actor=user.username,
                     message=f"License {lic.plan_type} created for customer {data['customer_id']}")
    return _ser_license(lic)


@app.put("/api/licensing/licenses/{license_id}")
async def update_license(license_id: str, data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")
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
    await db.flush()
    await _log_audit(db, "LICENSE_UPDATED", license_id=lic.id, actor=user.username,
                     message=f"License updated: status={lic.status}")
    return _ser_license(lic)


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG — scoped
# ═══════════════════════════════════════════════════════════════

@app.get("/api/licensing/audit-log")
async def get_audit_log(limit: int = 50, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralAuditLog).order_by(CentralAuditLog.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    if not user.is_superadmin:
        allowed_cids = set(user.allowed_customer_ids or [])
        loc_result = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id.in_(allowed_cids)))
        allowed_lids = {r[0] for r in loc_result.fetchall()}
        dev_result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id.in_(allowed_lids)))
        allowed_dids = {r[0] for r in dev_result.fetchall()}
        lic_result = await db.execute(select(CentralLicense.id).where(CentralLicense.customer_id.in_(allowed_cids)))
        allowed_licids = {r[0] for r in lic_result.fetchall()}

        entries = [
            e for e in entries
            if (not e.device_id or e.device_id in allowed_dids)
            and (not e.license_id or e.license_id in allowed_licids)
        ]

    return [
        {
            "id": e.id, "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "action": e.action, "device_id": e.device_id, "install_id": e.install_id,
            "message": e.message, "actor": e.actor,
        }
        for e in entries
    ]


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "central-license-server", "version": "3.6.0", "timestamp": _utcnow().isoformat()}


# ═══════════════════════════════════════════════════════════════
# REGISTRATION TOKENS — installer+ can manage
# ═══════════════════════════════════════════════════════════════

def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()

def _generate_reg_token() -> tuple:
    raw = f"drt_{secrets.token_urlsafe(32)}"
    hashed = _hash_token(raw)
    preview = f"{raw[:8]}...{raw[-4:]}"
    return raw, hashed, preview

def _ser_reg_token(t: RegistrationToken) -> dict:
    return {
        "id": t.id, "token_preview": t.token_preview,
        "customer_id": t.customer_id, "location_id": t.location_id,
        "license_id": t.license_id, "device_name_template": t.device_name_template,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "used_at": t.used_at.isoformat() if t.used_at else None,
        "used_by_install_id": t.used_by_install_id, "used_by_device_id": t.used_by_device_id,
        "created_by": t.created_by, "note": t.note,
        "is_revoked": t.is_revoked,
        "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None,
        "revoked_by": t.revoked_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "status": _token_status(t),
    }

def _token_status(t: RegistrationToken) -> str:
    if t.is_revoked: return "revoked"
    if t.used_at: return "used"
    now = _utcnow()
    if t.expires_at and _aware(t.expires_at) < now: return "expired"
    return "active"


@app.post("/api/registration-tokens")
async def create_registration_token(data: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    if data.get("customer_id") and not can_access_customer(user, data["customer_id"]):
        raise HTTPException(403, "Access denied to this customer")
    raw_token, token_hash, preview = _generate_reg_token()
    expires_in = int(data.get("expires_in_hours", 72))
    token = RegistrationToken(
        token_hash=token_hash, token_preview=preview,
        customer_id=data.get("customer_id"), location_id=data.get("location_id"),
        license_id=data.get("license_id"), device_name_template=data.get("device_name_template"),
        expires_at=_utcnow() + timedelta(hours=expires_in), created_by=user.username, note=data.get("note"),
    )
    db.add(token)
    await db.flush()
    await _log_audit(db, "REG_TOKEN_CREATED", actor=user.username, message=f"Token {preview} created, expires in {expires_in}h")
    result = _ser_reg_token(token)
    result["raw_token"] = raw_token
    return result


@app.get("/api/registration-tokens")
async def list_registration_tokens(status: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(RegistrationToken).order_by(RegistrationToken.created_at.desc())
    if not user.is_superadmin:
        allowed = user.allowed_customer_ids or []
        stmt = stmt.where(RegistrationToken.customer_id.in_(allowed))
    result = await db.execute(stmt)
    tokens = [_ser_reg_token(t) for t in result.scalars().all()]
    if status:
        tokens = [t for t in tokens if t["status"] == status]
    return tokens


@app.post("/api/registration-tokens/{token_id}/revoke")
async def revoke_registration_token(token_id: str, data: dict = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.id == token_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(404, "Token not found")
    if token.customer_id and not can_access_customer(user, token.customer_id):
        raise HTTPException(403, "Access denied")
    if token.is_revoked:
        raise HTTPException(400, "Token already revoked")
    if token.used_at:
        raise HTTPException(400, "Token already used")
    token.is_revoked = True
    token.revoked_at = _utcnow()
    token.revoked_by = user.username
    await db.flush()
    await _log_audit(db, "REG_TOKEN_REVOKED", actor=user.username, message=f"Token {token.token_preview} revoked")
    return _ser_reg_token(token)


# ═══════════════════════════════════════════════════════════════
# DEVICE REGISTRATION (Public/Controlled)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/register-device")
async def register_device(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new device using a one-time registration token. Public endpoint."""
    raw_token = body.get("token")
    install_id = body.get("install_id")
    device_name = body.get("device_name")

    if not raw_token:
        raise HTTPException(400, "Missing registration token")
    if not install_id:
        raise HTTPException(400, "Missing install_id")

    token_hash = _hash_token(raw_token)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.token_hash == token_hash))
    token = result.scalar_one_or_none()

    if not token:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id, message="Invalid token")
        raise HTTPException(403, "Invalid registration token")
    if token.is_revoked:
        raise HTTPException(403, "Token has been revoked")
    if token.used_at:
        raise HTTPException(403, "Token already used")
    now = _utcnow()
    if token.expires_at and _aware(token.expires_at) < now:
        raise HTTPException(403, "Token expired")

    existing = await db.execute(select(CentralDevice).where(CentralDevice.install_id == install_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "install_id already registered")

    location_id = token.location_id
    customer_id = token.customer_id
    if location_id and not customer_id:
        loc_r = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
        loc = loc_r.scalar_one_or_none()
        if loc: customer_id = loc.customer_id
    if not location_id and not customer_id:
        raise HTTPException(400, "Token has no customer/location")

    api_key = f"dk_{secrets.token_urlsafe(32)}"
    effective_name = device_name or token.device_name_template or f"Kiosk-{install_id[:8]}"

    new_device = CentralDevice(
        location_id=location_id, install_id=install_id, api_key=api_key,
        device_name=effective_name, status="active", binding_status="bound",
        last_sync_at=now, last_sync_ip=request.client.host if request.client else None,
        sync_count=0, registered_via_token_id=token.id,
    )
    db.add(new_device)
    await db.flush()

    token.used_at = now
    token.used_by_install_id = install_id
    token.used_by_device_id = new_device.id
    await db.flush()

    # Resolve license
    license_status = "no_license"
    license_id = token.license_id
    plan_type = None
    expiry = None
    customer_name = None

    if customer_id:
        cust_r = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
        cust = cust_r.scalar_one_or_none()
        if cust: customer_name = cust.name

    if license_id:
        lic_r = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
        lic = lic_r.scalar_one_or_none()
        if lic:
            license_status = _compute_status(lic, now)
            plan_type = lic.plan_type
            expiry = lic.ends_at.isoformat() if lic.ends_at else None
    elif customer_id:
        conditions = [CentralLicense.customer_id == customer_id]
        if location_id:
            conditions.append((CentralLicense.location_id == location_id) | (CentralLicense.location_id.is_(None)))
        lic_r = await db.execute(select(CentralLicense).where(and_(*conditions)))
        lics = lic_r.scalars().all()
        if lics:
            best, best_s = _find_best_license(lics, now)
            if best:
                license_status = best_s
                plan_type = best.plan_type
                license_id = best.id
                expiry = best.ends_at.isoformat() if best.ends_at else None

    await _log_audit(db, "DEVICE_REGISTERED", device_id=new_device.id, install_id=install_id,
                     license_id=license_id, actor="registration",
                     message=f"Device {effective_name} registered via token {token.token_preview}")

    return {
        "success": True, "device_id": new_device.id, "device_name": effective_name,
        "api_key": api_key, "customer_id": customer_id, "customer_name": customer_name,
        "location_id": location_id, "license_id": license_id, "license_status": license_status,
        "plan_type": plan_type, "expiry": expiry, "binding_status": "bound",
        "server_timestamp": now.isoformat(),
    }



# ═══════════════════════════════════════════════════════════════
# DEVICE IDENTITY RESOLUTION — v3.9.4
# ═══════════════════════════════════════════════════════════════

@app.get("/api/device/resolve")
async def resolve_device_id(request: Request, db: AsyncSession = Depends(get_db)):
    """Resolve a device_id from an API key. Used by kiosk at startup to learn its own central ID."""
    api_key = request.headers.get("X-License-Key")
    if not api_key:
        raise HTTPException(401, "Missing X-License-Key header")
    result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "No device found for this API key")
    return {
        "device_id": device.id,
        "device_name": device.device_name,
        "location_id": device.location_id,
        "status": device.status,
    }


# ═══════════════════════════════════════════════════════════════
# TELEMETRY — v3.7.0
# ═══════════════════════════════════════════════════════════════

ONLINE_THRESHOLD_SECONDS = 300  # 5 minutes


async def _authenticate_device(request: Request, db: AsyncSession) -> CentralDevice:
    """Authenticate a device via X-License-Key header."""
    api_key = request.headers.get("X-License-Key")
    if not api_key:
        raise HTTPException(401, "Missing X-License-Key header")
    result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(403, "Invalid API key")
    if device.status == "blocked":
        raise HTTPException(403, "Device is blocked")
    return device


async def _resolve_device_customer_id(device: CentralDevice, db: AsyncSession) -> str:
    """Resolve customer_id from device → location → customer chain."""
    if not device.location_id:
        return None
    result = await db.execute(select(CentralLocation.customer_id).where(CentralLocation.id == device.location_id))
    row = result.first()
    return row[0] if row else None


@app.post("/api/telemetry/heartbeat")
async def telemetry_heartbeat(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Lightweight heartbeat from device. Updates online status + version."""
    device = await _authenticate_device(request, db)
    now = _utcnow()

    was_offline = not device.last_heartbeat_at or (now - _aware(device.last_heartbeat_at)).total_seconds() > ONLINE_THRESHOLD_SECONDS

    device.last_heartbeat_at = now
    if body.get("version"):
        device.reported_version = body["version"]
    if body.get("error"):
        device.last_error = body["error"]
    elif device.last_error and body.get("clear_error"):
        device.last_error = None

    # v3.9.3: Store health snapshot + device logs
    if body.get("health"):
        import json as _json
        device.health_snapshot = _json.dumps(body["health"])
    if body.get("logs"):
        import json as _json
        device.device_logs = _json.dumps(body["logs"])

    # Update daily stats heartbeat count
    date_str = now.strftime("%Y-%m-%d")
    stats = await _get_or_create_daily_stats(db, device.id, date_str)
    stats.heartbeats = (stats.heartbeats or 0) + 1
    if not stats.first_heartbeat_at:
        stats.first_heartbeat_at = now
    stats.last_heartbeat_at = now

    await db.flush()

    # Log state transition (online/offline) — not every heartbeat
    if was_offline:
        await _log_audit(db, "DEVICE_ONLINE", device_id=device.id,
                         message=f"Device '{device.device_name}' came online (v{body.get('version', '?')})")

    return {"status": "ok", "server_time": now.isoformat()}


@app.post("/api/telemetry/ingest")
async def telemetry_ingest(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Bulk ingest telemetry events from a device. Idempotent via event_id."""
    device = await _authenticate_device(request, db)
    now = _utcnow()

    events = body.get("events", [])
    if not events:
        return {"accepted": 0, "duplicates": 0}

    accepted = 0
    duplicates = 0

    for ev in events:
        event_id = ev.get("event_id")
        if not event_id:
            continue

        # Idempotency: skip if event_id already exists
        existing = await db.execute(select(TelemetryEvent.id).where(TelemetryEvent.event_id == event_id))
        if existing.scalar_one_or_none():
            duplicates += 1
            continue

        event_type = ev.get("event_type", "unknown")
        timestamp_str = ev.get("timestamp")
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else now
        except (ValueError, AttributeError):
            ts = now

        te = TelemetryEvent(
            event_id=event_id,
            device_id=device.id,
            event_type=event_type,
            timestamp=ts,
            data=ev.get("data"),
        )
        db.add(te)

        # Update daily aggregation
        date_str = ts.strftime("%Y-%m-%d")
        stats = await _get_or_create_daily_stats(db, device.id, date_str)
        data = ev.get("data") or {}

        if event_type == "credits_added":
            stats.credits_added = (stats.credits_added or 0) + int(data.get("amount", 0))
            stats.revenue_cents = (stats.revenue_cents or 0) + int(data.get("revenue_cents", 0))
        elif event_type == "session_started":
            stats.sessions = (stats.sessions or 0) + 1
        elif event_type == "game_played":
            stats.games = (stats.games or 0) + 1
        elif event_type == "error":
            stats.errors = (stats.errors or 0) + 1
            device.last_error = data.get("message", "Unknown error")

        # Update last activity
        if event_type in ("session_started", "game_played", "credits_added"):
            device.last_activity_at = ts

        accepted += 1

    await db.flush()
    return {"accepted": accepted, "duplicates": duplicates, "server_time": now.isoformat()}


@app.get("/api/telemetry/dashboard")
async def telemetry_dashboard(
    customer_id: str = None, location_id: str = None, device_id: str = None,
    user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Scoped telemetry dashboard stats."""
    now = _utcnow()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    # Resolve device IDs within scope
    device_ids = await _resolve_scoped_device_ids(user, db, customer_id, location_id, device_id)

    if not device_ids:
        return {
            "devices_online": 0, "devices_offline": 0, "devices_total": 0,
            "revenue_today_cents": 0, "revenue_7d_cents": 0,
            "sessions_today": 0, "sessions_7d": 0, "games_today": 0, "games_7d": 0,
            "devices": [], "warnings": [],
        }

    # Device statuses
    dev_result = await db.execute(
        select(CentralDevice).where(CentralDevice.id.in_(device_ids))
        .order_by(CentralDevice.last_heartbeat_at.desc().nullslast())
    )
    devices = dev_result.scalars().all()

    online_count = 0
    offline_count = 0
    device_list = []
    warnings = []

    for d in devices:
        is_online = d.last_heartbeat_at and (now - _aware(d.last_heartbeat_at)).total_seconds() < ONLINE_THRESHOLD_SECONDS
        if is_online:
            online_count += 1
        else:
            offline_count += 1

        dev_info = {
            "id": d.id, "device_name": d.device_name or d.id[:8],
            "online": is_online,
            "last_heartbeat_at": d.last_heartbeat_at.isoformat() if d.last_heartbeat_at else None,
            "last_activity_at": d.last_activity_at.isoformat() if d.last_activity_at else None,
            "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
            "reported_version": d.reported_version,
            "last_error": d.last_error,
            "status": d.status, "binding_status": d.binding_status,
        }
        device_list.append(dev_info)

        # Warnings
        if d.last_error:
            warnings.append({"type": "error", "device": d.device_name or d.id[:8], "message": d.last_error})
        if not is_online and d.last_heartbeat_at:
            mins_ago = int((now - _aware(d.last_heartbeat_at)).total_seconds() / 60)
            warnings.append({"type": "offline", "device": d.device_name or d.id[:8], "message": f"Offline seit {mins_ago} Min."})
        elif not d.last_heartbeat_at:
            warnings.append({"type": "no_heartbeat", "device": d.device_name or d.id[:8], "message": "Noch kein Heartbeat empfangen"})

    # Daily stats aggregation
    today_stats = await _aggregate_daily_stats(db, device_ids, today, today)
    week_stats = await _aggregate_daily_stats(db, device_ids, week_ago, today)

    return {
        "devices_online": online_count,
        "devices_offline": offline_count,
        "devices_total": len(devices),
        "revenue_today_cents": today_stats["revenue_cents"],
        "revenue_7d_cents": week_stats["revenue_cents"],
        "sessions_today": today_stats["sessions"],
        "sessions_7d": week_stats["sessions"],
        "games_today": today_stats["games"],
        "games_7d": week_stats["games"],
        "credits_today": today_stats["credits_added"],
        "errors_today": today_stats["errors"],
        "devices": device_list,
        "warnings": warnings,
    }


@app.get("/api/telemetry/device-stats")
async def telemetry_device_stats(
    device_id: str, days: int = 7,
    user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Detailed stats for a single device over N days."""
    # Scope check
    result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    if not await can_access_location(user, device.location_id, db):
        raise HTTPException(403, "Access denied")

    now = _utcnow()
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    stmt = select(DeviceDailyStats).where(
        DeviceDailyStats.device_id == device_id,
        DeviceDailyStats.date >= start_date,
        DeviceDailyStats.date <= end_date,
    ).order_by(DeviceDailyStats.date)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "device_id": device_id,
        "device_name": device.device_name,
        "days": [
            {
                "date": r.date,
                "revenue_cents": r.revenue_cents or 0,
                "sessions": r.sessions or 0,
                "games": r.games or 0,
                "credits_added": r.credits_added or 0,
                "errors": r.errors or 0,
                "heartbeats": r.heartbeats or 0,
            }
            for r in rows
        ],
    }


async def _resolve_scoped_device_ids(user: AuthUser, db: AsyncSession, customer_id=None, location_id=None, device_id=None):
    """Resolve device IDs respecting user scope."""
    if device_id:
        # Check scope
        result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
        d = result.scalar_one_or_none()
        if not d:
            return []
        if not await can_access_location(user, d.location_id, db):
            return []
        return [device_id]

    if location_id:
        if not await can_access_location(user, location_id, db):
            return []
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id == location_id))
        return [r[0] for r in result.fetchall()]

    if customer_id:
        if not can_access_customer(user, customer_id):
            return []
        loc_r = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id == customer_id))
        loc_ids = [r[0] for r in loc_r.fetchall()]
        if not loc_ids:
            return []
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id.in_(loc_ids)))
        return [r[0] for r in result.fetchall()]

    # No specific filter — use user scope
    if user.is_superadmin:
        result = await db.execute(select(CentralDevice.id))
        return [r[0] for r in result.fetchall()]
    else:
        allowed = user.allowed_customer_ids or []
        if not allowed:
            return []
        loc_r = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id.in_(allowed)))
        loc_ids = [r[0] for r in loc_r.fetchall()]
        if not loc_ids:
            return []
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.location_id.in_(loc_ids)))
        return [r[0] for r in result.fetchall()]


async def _get_or_create_daily_stats(db: AsyncSession, device_id: str, date_str: str) -> DeviceDailyStats:
    """Get or create a daily stats row for device+date."""
    result = await db.execute(
        select(DeviceDailyStats).where(
            DeviceDailyStats.device_id == device_id,
            DeviceDailyStats.date == date_str,
        )
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = DeviceDailyStats(device_id=device_id, date=date_str)
        db.add(stats)
        await db.flush()
    return stats


async def _aggregate_daily_stats(db: AsyncSession, device_ids: list, start_date: str, end_date: str) -> dict:
    """Aggregate daily stats across devices and date range."""
    if not device_ids:
        return {"revenue_cents": 0, "sessions": 0, "games": 0, "credits_added": 0, "errors": 0}

    result = await db.execute(
        select(
            func.coalesce(func.sum(DeviceDailyStats.revenue_cents), 0),
            func.coalesce(func.sum(DeviceDailyStats.sessions), 0),
            func.coalesce(func.sum(DeviceDailyStats.games), 0),
            func.coalesce(func.sum(DeviceDailyStats.credits_added), 0),
            func.coalesce(func.sum(DeviceDailyStats.errors), 0),
        ).where(
            DeviceDailyStats.device_id.in_(device_ids),
            DeviceDailyStats.date >= start_date,
            DeviceDailyStats.date <= end_date,
        )
    )
    row = result.first()
    return {
        "revenue_cents": row[0] or 0,
        "sessions": row[1] or 0,
        "games": row[2] or 0,
        "credits_added": row[3] or 0,
        "errors": row[4] or 0,
    }


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG HELPER
# ═══════════════════════════════════════════════════════════════

async def _log_audit(db, action, device_id=None, install_id=None, license_id=None, actor=None, message=None):
    try:
        entry = CentralAuditLog(
            action=action, device_id=device_id, install_id=install_id,
            license_id=license_id, actor=actor, message=message, timestamp=_utcnow(),
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        logger.error(f"[AUDIT] Failed: {e}")


# ═══════════════════════════════════════════════════════════════
# v3.8.0: CENTRALIZED CONFIGURATION
# ═══════════════════════════════════════════════════════════════

def _ser_config_profile(cp):
    return {
        "id": cp.id, "scope_type": cp.scope_type, "scope_id": cp.scope_id,
        "config_data": cp.config_data or {}, "version": cp.version,
        "updated_by": cp.updated_by,
        "updated_at": cp.updated_at.isoformat() if cp.updated_at else None,
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts. override wins on conflict."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


@app.get("/api/config/profiles")
async def list_config_profiles(
    scope_type: str = None,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """List all config profiles, optionally filtered by scope_type."""
    require_min_role(user, "owner")
    stmt = select(ConfigProfile)
    if scope_type:
        stmt = stmt.where(ConfigProfile.scope_type == scope_type)
    stmt = stmt.order_by(ConfigProfile.scope_type, ConfigProfile.updated_at.desc())
    result = await db.execute(stmt)
    profiles = result.scalars().all()
    return [_ser_config_profile(p) for p in profiles]


@app.get("/api/config/profile/{scope_type}/{scope_id}")
async def get_config_profile(
    scope_type: str,
    scope_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Get a single config profile by scope."""
    require_min_role(user, "owner")
    result = await db.execute(
        select(ConfigProfile).where(
            ConfigProfile.scope_type == scope_type,
            ConfigProfile.scope_id == scope_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, f"No config for {scope_type}/{scope_id}")
    return _ser_config_profile(profile)


@app.get("/api/config/profile/global")
async def get_global_config(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Get the global config profile."""
    require_min_role(user, "owner")
    result = await db.execute(
        select(ConfigProfile).where(ConfigProfile.scope_type == "global")
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "No global config found")
    return _ser_config_profile(profile)


@app.put("/api/config/profile/{scope_type}/{scope_id}")
async def upsert_config_profile(
    scope_type: str,
    scope_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Create or update a config profile for the given scope."""
    require_min_role(user, "owner")
    if scope_type not in ("global", "customer", "location", "device"):
        raise HTTPException(400, "scope_type must be global|customer|location|device")

    body = await request.json()
    config_data = body.get("config_data", {})
    if not isinstance(config_data, dict):
        raise HTTPException(400, "config_data must be a JSON object")

    # v3.9.4: Schema validation before save
    from central_server.config_schema import validate_config
    validation_errors = validate_config(config_data)
    if validation_errors:
        raise HTTPException(422, detail={"validation_errors": validation_errors})

    # Scope access check
    if scope_type == "global" and user.role != "superadmin":
        raise HTTPException(403, "Only superadmin can modify global config")
    elif scope_type == "customer":
        if not can_access_customer(user, scope_id):
            raise HTTPException(403, "No access to this customer")
    elif scope_type == "location":
        loc = await db.get(CentralLocation, scope_id)
        if not loc or not can_access_customer(user, loc.customer_id):
            raise HTTPException(403, "No access to this location")
    elif scope_type == "device":
        dev = await db.get(CentralDevice, scope_id)
        if dev:
            loc = await db.get(CentralLocation, dev.location_id)
            if not loc or not can_access_customer(user, loc.customer_id):
                raise HTTPException(403, "No access to this device")

    # Upsert
    sid = None if scope_type == "global" else scope_id
    result = await db.execute(
        select(ConfigProfile).where(
            ConfigProfile.scope_type == scope_type,
            ConfigProfile.scope_id == sid,
        )
    )
    profile = result.scalar_one_or_none()
    if profile:
        # v3.9.4: Save current version to history BEFORE overwriting
        from central_server.models import ConfigHistory
        history_entry = ConfigHistory(
            profile_id=profile.id,
            scope_type=profile.scope_type,
            scope_id=profile.scope_id,
            config_data=profile.config_data or {},
            version=profile.version or 1,
            updated_by=profile.updated_by,
        )
        db.add(history_entry)

        profile.config_data = config_data
        profile.version = (profile.version or 0) + 1
        profile.updated_by = user.username
        profile.updated_at = _utcnow()
    else:
        profile = ConfigProfile(
            scope_type=scope_type, scope_id=sid,
            config_data=config_data, updated_by=user.username,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    await _log_audit(db, "config_updated", actor=user.username,
                     message=f"Config {scope_type}/{sid} updated (v{profile.version})")
    await db.commit()
    return _ser_config_profile(profile)


# ── Config History & Rollback — v3.9.4 ──

@app.get("/api/config/history/{scope_type}/{scope_id}")
async def get_config_history(
    scope_type: str,
    scope_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """List version history for a config scope."""
    require_min_role(user, "owner")
    sid = None if scope_type == "global" else scope_id
    from central_server.models import ConfigHistory
    result = await db.execute(
        select(ConfigHistory).where(
            ConfigHistory.scope_type == scope_type,
            ConfigHistory.scope_id == sid,
        ).order_by(ConfigHistory.version.desc()).limit(50)
    )
    entries = result.scalars().all()

    # Also fetch the current active profile
    active_result = await db.execute(
        select(ConfigProfile).where(
            ConfigProfile.scope_type == scope_type,
            ConfigProfile.scope_id == sid,
        )
    )
    active = active_result.scalar_one_or_none()

    return {
        "scope_type": scope_type,
        "scope_id": sid,
        "active_version": active.version if active else None,
        "active_updated_by": active.updated_by if active else None,
        "active_updated_at": active.updated_at.isoformat() if active and active.updated_at else None,
        "history": [
            {
                "id": h.id,
                "version": h.version,
                "updated_by": h.updated_by,
                "saved_at": h.saved_at.isoformat() if h.saved_at else None,
                "config_data": h.config_data,
            }
            for h in entries
        ],
    }


@app.post("/api/config/rollback/{scope_type}/{scope_id}/{version}")
async def rollback_config(
    scope_type: str,
    scope_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Rollback a config scope to a previous version."""
    require_min_role(user, "owner")
    sid = None if scope_type == "global" else scope_id

    # Find the history entry
    from central_server.models import ConfigHistory
    result = await db.execute(
        select(ConfigHistory).where(
            ConfigHistory.scope_type == scope_type,
            ConfigHistory.scope_id == sid,
            ConfigHistory.version == version,
        )
    )
    history_entry = result.scalar_one_or_none()
    if not history_entry:
        raise HTTPException(404, f"Version {version} nicht gefunden fuer {scope_type}/{scope_id}")

    # Find current active profile
    profile_result = await db.execute(
        select(ConfigProfile).where(
            ConfigProfile.scope_type == scope_type,
            ConfigProfile.scope_id == sid,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, f"Kein aktives Profil fuer {scope_type}/{scope_id}")

    # Save current version to history before rollback
    current_history = ConfigHistory(
        profile_id=profile.id,
        scope_type=profile.scope_type,
        scope_id=profile.scope_id,
        config_data=profile.config_data or {},
        version=profile.version or 1,
        updated_by=profile.updated_by,
    )
    db.add(current_history)

    # Apply the rollback
    profile.config_data = history_entry.config_data
    profile.version = (profile.version or 0) + 1
    profile.updated_by = f"{user.username} (rollback v{version})"
    profile.updated_at = _utcnow()

    await db.commit()

    # Audit log (separate commit, non-critical)
    try:
        await _log_audit(db, "config_rollback", actor=user.username,
                         message=f"Config {scope_type}/{sid} rolled back to v{version} (now v{profile.version})")
        await db.commit()
    except Exception:
        pass

    return {
        "success": True,
        "new_version": profile.version,
        "rolled_back_to": version,
        "config_data": profile.config_data,
    }



@app.get("/api/config/effective")
async def get_effective_config(
    device_id: str = None,
    location_id: str = None,
    customer_id: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute the effective (merged) config for a given device.
    Merge order: global → customer → location → device.
    Can be called by devices (unauthenticated, identified by device_id)
    or by portal users.
    """
    layers = {}

    # 1. Global
    result = await db.execute(
        select(ConfigProfile).where(ConfigProfile.scope_type == "global")
    )
    global_p = result.scalar_one_or_none()
    if global_p:
        layers["global"] = global_p.config_data or {}

    # Resolve hierarchy: device → location → customer
    resolved_customer_id = customer_id
    resolved_location_id = location_id
    resolved_device_id = device_id

    if device_id:
        dev = await db.get(CentralDevice, device_id)
        if dev:
            resolved_location_id = resolved_location_id or dev.location_id

    if resolved_location_id:
        loc = await db.get(CentralLocation, resolved_location_id)
        if loc:
            resolved_customer_id = resolved_customer_id or loc.customer_id

    # 2. Customer layer
    if resolved_customer_id:
        result = await db.execute(
            select(ConfigProfile).where(
                ConfigProfile.scope_type == "customer",
                ConfigProfile.scope_id == resolved_customer_id,
            )
        )
        cp = result.scalar_one_or_none()
        if cp:
            layers["customer"] = cp.config_data or {}

    # 3. Location layer
    if resolved_location_id:
        result = await db.execute(
            select(ConfigProfile).where(
                ConfigProfile.scope_type == "location",
                ConfigProfile.scope_id == resolved_location_id,
            )
        )
        lp = result.scalar_one_or_none()
        if lp:
            layers["location"] = lp.config_data or {}

    # 4. Device layer
    if resolved_device_id:
        result = await db.execute(
            select(ConfigProfile).where(
                ConfigProfile.scope_type == "device",
                ConfigProfile.scope_id == resolved_device_id,
            )
        )
        dp = result.scalar_one_or_none()
        if dp:
            layers["device"] = dp.config_data or {}

    # Merge: global → customer → location → device
    merged = {}
    for scope in ("global", "customer", "location", "device"):
        if scope in layers:
            merged = _deep_merge(merged, layers[scope])

    # Compute a composite version (max of all layer versions)
    all_versions = []
    for scope in ("global", "customer", "location", "device"):
        if scope in layers:
            # Re-query for version
            if scope == "global":
                r = await db.execute(select(ConfigProfile.version).where(ConfigProfile.scope_type == "global"))
            else:
                scope_id_val = {"customer": resolved_customer_id, "location": resolved_location_id, "device": resolved_device_id}.get(scope)
                r = await db.execute(select(ConfigProfile.version).where(ConfigProfile.scope_type == scope, ConfigProfile.scope_id == scope_id_val))
            v = r.scalar_one_or_none()
            if v:
                all_versions.append(v)

    return {
        "config": merged,
        "version": max(all_versions) if all_versions else 0,
        "layers_applied": list(layers.keys()),
        "scope": {
            "customer_id": resolved_customer_id,
            "location_id": resolved_location_id,
            "device_id": resolved_device_id,
        },
    }


# ── Config Diff — v3.9.5 ──

def _flatten_dict(d, prefix=""):
    """Flatten a nested dict into dot-notation keys."""
    items = {}
    if not isinstance(d, dict):
        return {prefix: d} if prefix else {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, key))
        else:
            items[key] = v
    return items


@app.get("/api/config/diff/{scope_type}/{scope_id}")
async def get_config_diff(
    scope_type: str,
    scope_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Compare a history version against the active config for a scope. Returns flat field-level diff."""
    require_min_role(user, "owner")
    sid = None if scope_type == "global" else scope_id

    # Get active profile
    active_result = await db.execute(
        select(ConfigProfile).where(ConfigProfile.scope_type == scope_type, ConfigProfile.scope_id == sid)
    )
    active = active_result.scalar_one_or_none()
    if not active:
        raise HTTPException(404, f"Kein aktives Profil fuer {scope_type}/{scope_id}")

    # Get history version
    from central_server.models import ConfigHistory
    hist_result = await db.execute(
        select(ConfigHistory).where(
            ConfigHistory.scope_type == scope_type,
            ConfigHistory.scope_id == sid,
            ConfigHistory.version == version,
        )
    )
    hist = hist_result.scalar_one_or_none()
    if not hist:
        raise HTTPException(404, f"Version {version} nicht gefunden")

    old_flat = _flatten_dict(hist.config_data or {})
    new_flat = _flatten_dict(active.config_data or {})
    all_keys = sorted(set(old_flat.keys()) | set(new_flat.keys()))

    changes = []
    for key in all_keys:
        old_val = old_flat.get(key)
        new_val = new_flat.get(key)
        if key not in old_flat:
            changes.append({"key": key, "status": "added", "old": None, "new": new_val})
        elif key not in new_flat:
            changes.append({"key": key, "status": "removed", "old": old_val, "new": None})
        elif old_val != new_val:
            changes.append({"key": key, "status": "changed", "old": old_val, "new": new_val})
        else:
            changes.append({"key": key, "status": "unchanged", "old": old_val, "new": new_val})

    actual_changes = [c for c in changes if c["status"] != "unchanged"]
    return {
        "scope_type": scope_type,
        "scope_id": sid,
        "old_version": version,
        "new_version": active.version,
        "total_changes": len(actual_changes),
        "changes": changes,
    }




# ═══════════════════════════════════════════════════════════════
# v3.9.0: REMOTE ACTIONS
# ═══════════════════════════════════════════════════════════════

VALID_ACTIONS = {"force_sync", "restart_backend", "reload_ui"}


# ── Config Export / Import — v3.9.8 ──

@app.get("/api/config/export/{scope_type}/{scope_id}")
async def export_config(
    scope_type: str,
    scope_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Export the override config_data for a scope as downloadable JSON with metadata."""
    require_min_role(user, "owner")
    if scope_type not in ("global", "customer", "location", "device"):
        raise HTTPException(400, "scope_type must be global|customer|location|device")

    sid = None if scope_type == "global" else scope_id
    result = await db.execute(
        select(ConfigProfile).where(ConfigProfile.scope_type == scope_type, ConfigProfile.scope_id == sid)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, f"No config for {scope_type}/{scope_id}")

    # Scope access check
    if scope_type == "customer" and not can_access_customer(user, scope_id):
        raise HTTPException(403, "No access")
    elif scope_type in ("location", "device"):
        if scope_type == "location":
            loc = await db.get(CentralLocation, scope_id)
            if not loc or not can_access_customer(user, loc.customer_id):
                raise HTTPException(403, "No access")
        else:
            dev = await db.get(CentralDevice, scope_id)
            if dev:
                loc = await db.get(CentralLocation, dev.location_id)
                if not loc or not can_access_customer(user, loc.customer_id):
                    raise HTTPException(403, "No access")

    export_data = {
        "meta": {
            "type": "darts_kiosk_config_export",
            "format_version": 1,
            "scope_type": scope_type,
            "scope_id": scope_id if scope_type != "global" else "global",
            "version": profile.version,
            "exported_at": _utcnow().isoformat(),
            "exported_by": user.username,
        },
        "config_data": profile.config_data or {},
    }

    try:
        await _log_audit(db, "config_export", actor=user.username,
                         message=f"Config exported: {scope_type}/{sid} v{profile.version}")
        await db.commit()
    except Exception:
        pass

    return export_data


@app.post("/api/config/import/validate")
async def validate_import(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """
    Validate an import file and return preview/diff.
    Body: { import_data: {...exported JSON...}, target_scope_type, target_scope_id, mode: "replace"|"merge" }
    """
    require_min_role(user, "owner")
    body = await request.json()

    import_data = body.get("import_data", {})
    target_scope_type = body.get("target_scope_type")
    target_scope_id = body.get("target_scope_id")
    mode = body.get("mode", "merge")

    errors = []

    # Structure validation
    if not isinstance(import_data, dict):
        return {"valid": False, "errors": ["Datei muss ein JSON-Objekt sein"], "diff": None}

    meta = import_data.get("meta", {})
    config_data = import_data.get("config_data", {})

    if not isinstance(meta, dict) or meta.get("type") != "darts_kiosk_config_export":
        errors.append("Keine gueltige Config-Export-Datei (meta.type fehlt oder ungueltig)")
    if not isinstance(config_data, dict) or not config_data:
        errors.append("config_data fehlt oder ist leer")

    if errors:
        return {"valid": False, "errors": errors, "diff": None}

    # Config schema validation
    from central_server.config_schema import validate_config
    schema_errors = validate_config(config_data)
    if schema_errors:
        return {"valid": False, "errors": [f"Schema: {e}" for e in schema_errors], "diff": None}

    # Target scope
    tst = target_scope_type or meta.get("scope_type", "global")
    tsi = target_scope_id or meta.get("scope_id")
    if tst not in ("global", "customer", "location", "device"):
        errors.append(f"Ungueltiger Ziel-Scope: {tst}")
        return {"valid": False, "errors": errors, "diff": None}

    sid = None if tst == "global" else tsi

    # Scope access
    if tst == "customer" and not can_access_customer(user, tsi):
        return {"valid": False, "errors": ["Kein Zugriff auf diesen Scope"], "diff": None}
    elif tst == "global" and user.role != "superadmin":
        return {"valid": False, "errors": ["Nur Superadmin kann globale Config importieren"], "diff": None}

    # Get current config for diff
    result = await db.execute(
        select(ConfigProfile).where(ConfigProfile.scope_type == tst, ConfigProfile.scope_id == sid)
    )
    current = result.scalar_one_or_none()
    current_data = current.config_data if current else {}

    # Compute what will be applied
    if mode == "replace":
        new_data = config_data
    else:
        new_data = _deep_merge(current_data or {}, config_data)

    # Compute diff
    old_flat = _flatten_dict(current_data or {})
    new_flat = _flatten_dict(new_data)
    all_keys = sorted(set(old_flat.keys()) | set(new_flat.keys()))

    changes = []
    for key in all_keys:
        old_val = old_flat.get(key)
        new_val = new_flat.get(key)
        if key not in old_flat:
            changes.append({"key": key, "status": "added", "old": None, "new": new_val})
        elif key not in new_flat:
            changes.append({"key": key, "status": "removed", "old": old_val, "new": None})
        elif old_val != new_val:
            changes.append({"key": key, "status": "changed", "old": old_val, "new": new_val})
        else:
            changes.append({"key": key, "status": "unchanged", "old": old_val, "new": new_val})

    actual_changes = [c for c in changes if c["status"] != "unchanged"]

    warnings = []
    if mode == "replace" and current_data:
        removed = [c for c in actual_changes if c["status"] == "removed"]
        if removed:
            warnings.append(f"Replace-Modus: {len(removed)} bestehende Felder werden entfernt")
    if meta.get("scope_type") and meta["scope_type"] != tst:
        warnings.append(f"Originaler Scope war '{meta['scope_type']}', Ziel ist '{tst}'")

    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "mode": mode,
        "target_scope_type": tst,
        "target_scope_id": tsi or "global",
        "source_meta": meta,
        "diff": {
            "total_changes": len(actual_changes),
            "changes": changes,
        },
    }


@app.post("/api/config/import/apply")
async def apply_import(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """
    Apply a validated import. Creates history, validates, saves.
    Body: { import_data, target_scope_type, target_scope_id, mode }
    """
    require_min_role(user, "owner")
    body = await request.json()

    import_data = body.get("import_data", {})
    target_scope_type = body.get("target_scope_type", "global")
    target_scope_id = body.get("target_scope_id")
    mode = body.get("mode", "merge")

    config_data = import_data.get("config_data", {})
    meta = import_data.get("meta", {})

    if not isinstance(config_data, dict) or not config_data:
        raise HTTPException(400, "config_data fehlt oder ist leer")
    if target_scope_type not in ("global", "customer", "location", "device"):
        raise HTTPException(400, "Ungueltiger scope_type")

    # Re-validate schema
    from central_server.config_schema import validate_config
    schema_errors = validate_config(config_data)
    if schema_errors:
        raise HTTPException(422, detail={"validation_errors": schema_errors})

    # Scope access (same checks as upsert_config_profile)
    if target_scope_type == "global" and user.role != "superadmin":
        raise HTTPException(403, "Only superadmin can modify global config")
    elif target_scope_type == "customer":
        if not can_access_customer(user, target_scope_id):
            raise HTTPException(403, "No access to this customer")
    elif target_scope_type == "location":
        loc = await db.get(CentralLocation, target_scope_id)
        if not loc or not can_access_customer(user, loc.customer_id):
            raise HTTPException(403, "No access to this location")
    elif target_scope_type == "device":
        dev = await db.get(CentralDevice, target_scope_id)
        if dev:
            loc = await db.get(CentralLocation, dev.location_id)
            if not loc or not can_access_customer(user, loc.customer_id):
                raise HTTPException(403, "No access to this device")

    sid = None if target_scope_type == "global" else target_scope_id

    # Upsert with history (reusing existing pattern)
    result = await db.execute(
        select(ConfigProfile).where(
            ConfigProfile.scope_type == target_scope_type, ConfigProfile.scope_id == sid,
        )
    )
    profile = result.scalar_one_or_none()

    if profile:
        # Save current to history
        from central_server.models import ConfigHistory
        db.add(ConfigHistory(
            profile_id=profile.id, scope_type=profile.scope_type, scope_id=profile.scope_id,
            config_data=profile.config_data or {}, version=profile.version or 1,
            updated_by=profile.updated_by,
        ))

        if mode == "merge":
            profile.config_data = _deep_merge(profile.config_data or {}, config_data)
        else:
            profile.config_data = config_data

        profile.version = (profile.version or 0) + 1
        profile.updated_by = f"{user.username} (import-{mode})"
        profile.updated_at = _utcnow()
    else:
        profile = ConfigProfile(
            scope_type=target_scope_type, scope_id=sid,
            config_data=config_data,
            updated_by=f"{user.username} (import-{mode})",
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)

    source_info = f"from {meta.get('scope_type','?')}/{meta.get('scope_id','?')} v{meta.get('version','?')}"
    await _log_audit(db, "config_import", actor=user.username,
                     message=f"Config imported ({mode}) to {target_scope_type}/{sid} v{profile.version} {source_info}")
    await db.commit()

    return {
        "success": True,
        "mode": mode,
        "profile": _ser_config_profile(profile),
        "source_meta": meta,
    }


def _ser_action(a):
    return {
        "id": a.id, "device_id": a.device_id, "action_type": a.action_type,
        "status": a.status, "issued_by": a.issued_by,
        "issued_at": a.issued_at.isoformat() if a.issued_at else None,
        "acked_at": a.acked_at.isoformat() if a.acked_at else None,
        "result_message": a.result_message,
    }



# ── Bulk Device Actions — v3.9.5 (MUST be before {device_id} routes) ──

_BULK_MAX_DEVICES = 50
_BULK_DEDUP_SECONDS = 30


@app.post("/api/remote-actions/bulk")
async def bulk_remote_actions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Issue a remote action to multiple devices at once. Owner+ role required."""
    require_min_role(user, "owner")
    body = await request.json()
    device_ids = body.get("device_ids", [])
    action_type = body.get("action_type", "")
    is_retry = body.get("is_retry", False)
    retry_ref = body.get("retry_ref")  # optional: reference to original run timestamp

    if not isinstance(device_ids, list) or len(device_ids) == 0:
        raise HTTPException(400, "device_ids must be a non-empty list")
    if len(device_ids) > _BULK_MAX_DEVICES:
        raise HTTPException(400, f"Maximal {_BULK_MAX_DEVICES} Geraete pro Bulk-Aktion")
    if action_type not in VALID_ACTIONS:
        raise HTTPException(400, f"action_type must be one of: {', '.join(sorted(VALID_ACTIONS))}")

    unique_ids = list(dict.fromkeys(device_ids))
    results = []
    created_count = skipped_count = denied_count = 0

    for did in unique_ids:
        dev = await db.get(CentralDevice, did)
        if not dev:
            results.append({"device_id": did, "status": "error", "message": "Geraet nicht gefunden"})
            continue
        if dev.location_id:
            loc = await db.get(CentralLocation, dev.location_id)
            if loc and not can_access_customer(user, loc.customer_id):
                results.append({"device_id": did, "device_name": dev.device_name, "status": "denied", "message": "Kein Zugriff"})
                denied_count += 1
                continue

        dedup_cutoff = _utcnow() - timedelta(seconds=_BULK_DEDUP_SECONDS)
        dedup_q = await db.execute(
            select(RemoteAction).where(
                RemoteAction.device_id == did, RemoteAction.action_type == action_type,
                RemoteAction.issued_at >= dedup_cutoff, RemoteAction.status == "pending",
            ).limit(1)
        )
        if dedup_q.scalar_one_or_none():
            results.append({"device_id": did, "device_name": dev.device_name, "status": "skipped", "message": "Bereits ausstehend"})
            skipped_count += 1
            continue

        action = RemoteAction(id=secrets.token_hex(18), device_id=did, action_type=action_type, issued_by=user.username)
        db.add(action)
        results.append({"device_id": did, "device_name": dev.device_name, "status": "created", "action_id": action.id})
        created_count += 1

    await db.commit()
    audit_msg = f"Bulk '{action_type}': {created_count} erstellt, {skipped_count} uebersprungen, {denied_count} verweigert von {len(unique_ids)} Geraeten"
    if is_retry:
        audit_msg = f"[RETRY] {audit_msg}"
    try:
        await _log_audit(db, "bulk_remote_action", actor=user.username,
                         message=audit_msg)
        await db.commit()
    except Exception:
        pass

    return {
        "action_type": action_type, "total": len(unique_ids),
        "created": created_count, "skipped": skipped_count, "denied": denied_count,
        "is_retry": is_retry, "retry_ref": retry_ref,
        "results": results,
    }


@app.post("/api/remote-actions/{device_id}")
async def issue_remote_action(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Issue a remote action to a device. Requires owner+ role."""
    require_min_role(user, "owner")

    # Verify device exists and user has access
    dev = await db.get(CentralDevice, device_id)
    if not dev:
        raise HTTPException(404, "Device not found")
    if dev.location_id:
        loc = await db.get(CentralLocation, dev.location_id)
        if loc and not can_access_customer(user, loc.customer_id):
            raise HTTPException(403, "No access to this device")

    body = await request.json()
    action_type = body.get("action_type", "")
    if action_type not in VALID_ACTIONS:
        raise HTTPException(400, f"action_type must be one of: {', '.join(sorted(VALID_ACTIONS))}")

    action = RemoteAction(
        device_id=device_id, action_type=action_type,
        issued_by=user.username,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    await _log_audit(db, "remote_action_issued", device_id=device_id, actor=user.username,
                     message=f"Action '{action_type}' issued for device {dev.device_name or device_id}")
    await db.commit()

    return _ser_action(action)




@app.get("/api/remote-actions/{device_id}")
async def list_device_actions(
    device_id: str,
    status: str = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """List recent remote actions for a device."""
    require_min_role(user, "staff")
    stmt = select(RemoteAction).where(RemoteAction.device_id == device_id)
    if status:
        stmt = stmt.where(RemoteAction.status == status)
    stmt = stmt.order_by(RemoteAction.issued_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [_ser_action(a) for a in result.scalars().all()]


@app.get("/api/remote-actions/{device_id}/pending")
async def get_pending_actions(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Device-facing endpoint: get pending actions to execute.
    Authenticated via X-License-Key header.
    """
    stmt = (
        select(RemoteAction)
        .where(RemoteAction.device_id == device_id, RemoteAction.status == "pending")
        .order_by(RemoteAction.issued_at.asc())
    )
    result = await db.execute(stmt)
    return [_ser_action(a) for a in result.scalars().all()]


@app.post("/api/remote-actions/{device_id}/ack")
async def ack_remote_action(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Device acknowledges completion of a remote action."""
    body = await request.json()
    action_id = body.get("action_id")
    success = body.get("success", True)
    message = body.get("message", "")

    action = await db.get(RemoteAction, action_id)
    if not action or action.device_id != device_id:
        raise HTTPException(404, "Action not found")

    action.status = "acked" if success else "failed"
    action.acked_at = _utcnow()
    action.result_message = message
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# v3.9.0: ENHANCED DEVICE DETAIL
# ═══════════════════════════════════════════════════════════════

@app.get("/api/telemetry/device/{device_id}")
async def get_device_detail(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Get enriched device detail: status, version, last activity, recent events, daily stats."""
    require_min_role(user, "staff")

    dev = await db.get(CentralDevice, device_id)
    if not dev:
        raise HTTPException(404, "Device not found")

    # Check access
    if dev.location_id:
        loc = await db.get(CentralLocation, dev.location_id)
        if loc and not can_access_customer(user, loc.customer_id):
            raise HTTPException(403, "No access to this device")
    else:
        loc = None

    # Location + customer names
    cust = None
    if loc and loc.customer_id:
        cust = await db.get(CentralCustomer, loc.customer_id)

    # Online status (handle naive datetimes from SQLite)
    is_online = False
    if dev.last_heartbeat_at:
        hb = dev.last_heartbeat_at
        now = _utcnow()
        # Make both aware or both naive for comparison
        if hb.tzinfo is None:
            from datetime import timezone as _tz
            hb = hb.replace(tzinfo=_tz.utc)
        diff = (now - hb).total_seconds()
        is_online = diff < 300  # 5min threshold

    # Last 10 telemetry events
    events_q = await db.execute(
        select(TelemetryEvent)
        .where(TelemetryEvent.device_id == device_id)
        .order_by(TelemetryEvent.timestamp.desc())
        .limit(10)
    )
    recent_events = [
        {"event_type": e.event_type, "timestamp": e.timestamp.isoformat() if e.timestamp else None,
         "data": e.data}
        for e in events_q.scalars().all()
    ]

    # Last 7 days of daily stats
    stats_q = await db.execute(
        select(DeviceDailyStats)
        .where(DeviceDailyStats.device_id == device_id)
        .order_by(DeviceDailyStats.date.desc())
        .limit(7)
    )
    daily_stats = [
        {"date": s.date, "revenue_cents": s.revenue_cents, "sessions": s.sessions,
         "games": s.games, "credits_added": s.credits_added, "errors": s.errors}
        for s in stats_q.scalars().all()
    ]

    # Pending remote actions
    actions_q = await db.execute(
        select(RemoteAction)
        .where(RemoteAction.device_id == device_id)
        .order_by(RemoteAction.issued_at.desc())
        .limit(10)
    )
    recent_actions = [_ser_action(a) for a in actions_q.scalars().all()]

    # Parse stored health snapshot + logs
    health_snapshot = None
    stored_logs = []
    if dev.health_snapshot:
        try:
            import json as _json
            health_snapshot = _json.loads(dev.health_snapshot)
        except Exception:
            pass
    if dev.device_logs:
        try:
            import json as _json
            stored_logs = _json.loads(dev.device_logs)
        except Exception:
            pass

    return {
        "id": dev.id, "device_name": dev.device_name, "hardware_id": getattr(dev, 'hardware_id', None),
        "status": dev.status,
        "is_online": is_online,
        "last_heartbeat_at": dev.last_heartbeat_at.isoformat() if dev.last_heartbeat_at else None,
        "reported_version": dev.reported_version,
        "last_error": dev.last_error,
        "last_activity_at": dev.last_activity_at.isoformat() if dev.last_activity_at else None,
        "location": {"id": loc.id, "name": loc.name} if loc else None,
        "customer": {"id": cust.id, "name": cust.name} if cust else None,
        "health_snapshot": health_snapshot,
        "device_logs": stored_logs,
        "recent_events": recent_events,
        "daily_stats": daily_stats,
        "recent_actions": recent_actions,
    }
