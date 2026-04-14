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

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from central_server.database import get_db, init_db, AsyncSessionLocal
from central_server.models import (
    CentralCustomer, CentralLocation, CentralDevice, CentralLicense,
    CentralAuditLog, RegistrationToken, CentralUser, LicenseStatus, CustomerStatus,
    TelemetryEvent, DeviceDailyStats, ConfigProfile, RemoteAction,
    DeviceCredential, DeviceLease, DeviceTrustStatus, DeviceCredentialStatus, DeviceLeaseStatus,
)
from central_server.auth import (
    get_current_user, AuthUser, require_superadmin, require_min_role,
    require_installer_or_above, require_owner_or_above,
    get_allowed_customer_ids, can_access_customer, can_access_location,
    apply_customer_scope, hash_password, verify_password, create_jwt,
    can_create_role, VALID_ROLES, ROLE_HIERARCHY, is_legacy_password_hash,
)
from central_server.ws_hub import device_ws_hub
from central_server.device_trust import (
    attach_lease_key_metadata,
    build_credential_rotation_lineage,
    build_issuer_profile_diagnostics,
    build_placeholder_signed_lease,
    build_reconciliation_summary,
    build_support_diagnostics_compact_summary,
    build_signing_registry_diagnostics,
    build_signing_key_lineage,
    compute_lease_status,
    get_stored_signed_lease_bundle,
    issue_placeholder_credential,
    normalize_enrollment_material,
    reconcile_trust_material,
    revoke_placeholder_credential,
    revoke_placeholder_lease,
    summarize_credential_rotation,
    summarize_lineage,
    sync_device_trust_snapshot,
    verify_placeholder_certificate,
    verify_placeholder_signed_lease,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CENTRAL] %(levelname)s %(message)s")
logger = logging.getLogger("central_server")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_production_env() -> bool:
    env_name = os.environ.get("CENTRAL_ENV", os.environ.get("ENV", "")).strip().lower()
    return env_name in {"prod", "production"}


def _load_cors_origins() -> list[str]:
    if _env_flag("CENTRAL_CORS_ALLOW_ALL", False):
        if _is_production_env() and not _env_flag("CENTRAL_ALLOW_INSECURE_CORS_WILDCARD", False):
            raise RuntimeError(
                "CENTRAL_CORS_ALLOW_ALL is blocked in production unless CENTRAL_ALLOW_INSECURE_CORS_WILDCARD=true"
            )
        return ["*"]
    raw = os.environ.get("CENTRAL_CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _load_ws_query_auth_mode() -> str:
    raw = os.environ.get("CENTRAL_WS_QUERY_AUTH_MODE", "").strip().lower()
    if raw in {"allow", "warn", "deny"}:
        return raw

    env_name = os.environ.get("CENTRAL_ENV", os.environ.get("ENV", "")).strip().lower()
    if env_name in {"prod", "production"}:
        return "deny"
    return "warn"


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

    # Ensure bootstrap superadmin exists only when an explicit bootstrap password is provided.
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CentralUser).where(CentralUser.role == "superadmin"))
        if not result.scalar_one_or_none():
            bootstrap_pw = os.environ.get("CENTRAL_BOOTSTRAP_PASSWORD", "").strip() or os.environ.get("CENTRAL_ADMIN_PASSWORD", "").strip()
            if bootstrap_pw:
                sa = CentralUser(
                    username="superadmin",
                    password_hash=hash_password(bootstrap_pw),
                    display_name="Super Administrator",
                    role="superadmin",
                )
                db.add(sa)
                await db.commit()
                logger.info("[INIT] Bootstrap superadmin user created from explicit environment configuration")
            else:
                logger.warning("[INIT] No superadmin exists and no CENTRAL_BOOTSTRAP_PASSWORD/CENTRAL_ADMIN_PASSWORD was provided; skipping insecure default superadmin creation")

    # v3.7.0+: additive device trust / heartbeat scaffolding
    _migrate_cols = [
        ("devices", "last_heartbeat_at", "DATETIME"),
        ("devices", "reported_version", "VARCHAR(20)"),
        ("devices", "last_error", "TEXT"),
        ("devices", "last_activity_at", "DATETIME"),
        ("devices", "license_id", "VARCHAR(36)"),
        ("devices", "trust_status", "VARCHAR(32) DEFAULT 'legacy_unbound'"),
        ("devices", "trust_reason", "TEXT"),
        ("devices", "trust_last_changed_at", "DATETIME"),
        ("devices", "replacement_of_device_id", "VARCHAR(36)"),
        ("devices", "credential_status", "VARCHAR(32) DEFAULT 'none'"),
        ("devices", "credential_fingerprint", "VARCHAR(128)"),
        ("devices", "credential_issued_at", "DATETIME"),
        ("devices", "credential_expires_at", "DATETIME"),
        ("devices", "lease_status", "VARCHAR(32) DEFAULT 'none'"),
        ("devices", "lease_id", "VARCHAR(64)"),
        ("devices", "lease_issued_at", "DATETIME"),
        ("devices", "lease_expires_at", "DATETIME"),
        ("devices", "lease_grace_until", "DATETIME"),
        ("devices", "lease_metadata", "JSON"),
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

    # v3.15.0: Add params column to remote_actions
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(_text("SELECT params FROM remote_actions LIMIT 1"))
    except Exception:
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(_text("ALTER TABLE remote_actions ADD COLUMN params TEXT"))
                await db.commit()
                logger.info("[MIGRATE] Added params column to remote_actions")
            except Exception as e:
                logger.warning(f"[MIGRATE] remote_actions.params: {e}")

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

_CORS_ALLOWED_ORIGINS = _load_cors_origins()
_CORS_ALLOW_ALL = _CORS_ALLOWED_ORIGINS == ["*"]
_WS_QUERY_AUTH_MODE = _load_ws_query_auth_mode()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=not _CORS_ALLOW_ALL,
    allow_origins=_CORS_ALLOWED_ORIGINS,
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

def _ser_device(d, include_api_key: bool = False):
    """Serialize device — v3.15.2: consistent online/degraded/offline status."""
    ws_info = {}
    try:
        ws_info = device_ws_hub.device_ws_status(d.id)
    except Exception:
        pass

    def _safe_dt(val):
        if val is None: return None
        if hasattr(val, 'isoformat'): return val.isoformat()
        return str(val)

    hb = getattr(d, 'last_heartbeat_at', None)
    connectivity = _compute_device_connectivity(hb)

    api_key = getattr(d, 'api_key', None)
    payload = {
        "id": d.id,
        "location_id": getattr(d, 'location_id', None),
        "install_id": getattr(d, 'install_id', None),
        "api_key_preview": f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else ("****" if api_key else None),
        "device_name": getattr(d, 'device_name', None),
        "status": getattr(d, 'status', 'unknown'),
        "binding_status": getattr(d, 'binding_status', 'unknown'),
        "trust_status": getattr(d, 'trust_status', DeviceTrustStatus.LEGACY_UNBOUND.value),
        "trust_reason": getattr(d, 'trust_reason', None),
        "credential_status": getattr(d, 'credential_status', DeviceCredentialStatus.NONE.value),
        "credential_fingerprint": getattr(d, 'credential_fingerprint', None),
        "lease_status": getattr(d, 'lease_status', DeviceLeaseStatus.NONE.value),
        "lease_id": getattr(d, 'lease_id', None),
        "lease_expires_at": _safe_dt(getattr(d, 'lease_expires_at', None)),
        "license_id": getattr(d, 'license_id', None),
        "last_sync_at": _safe_dt(getattr(d, 'last_sync_at', None)),
        "last_heartbeat_at": _safe_dt(hb),
        "reported_version": getattr(d, 'reported_version', None),
        "last_error": getattr(d, 'last_error', None),
        "sync_count": getattr(d, 'sync_count', 0) or 0,
        "created_at": _safe_dt(getattr(d, 'created_at', None)),
        "ws_connected": ws_info.get("ws_connected", False),
        "is_online": connectivity == "online",
        "connectivity": connectivity,
    }
    if include_api_key:
        payload["api_key"] = api_key
    return payload

def _ser_license(lic):
    return {
        "id": lic.id, "customer_id": lic.customer_id, "location_id": lic.location_id,
        "plan_type": lic.plan_type, "max_devices": lic.max_devices, "status": lic.status,
        "starts_at": lic.starts_at.isoformat() if lic.starts_at else None,
        "ends_at": lic.ends_at.isoformat() if lic.ends_at else None,
        "grace_days": lic.grace_days,
        "grace_until": lic.grace_until.isoformat() if lic.grace_until else None,
        "notes": lic.notes,
        "created_by": lic.created_by,
        "created_at": lic.created_at.isoformat() if lic.created_at else None,
        "updated_at": lic.updated_at.isoformat() if lic.updated_at else None,
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

    if is_legacy_password_hash(user.password_hash):
        user.password_hash = hash_password(password)
        await db.flush()

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
            raise HTTPException(400, "Invalid role")
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
    recent_devices = []
    try:
        dev_result = await db.execute(dev_stmt)
        for d in dev_result.scalars().all():
            try:
                connectivity = _compute_device_connectivity(d.last_heartbeat_at)
                recent_devices.append(_finalize_device_summary({
                    "id": d.id, "device_name": d.device_name, "status": d.status,
                    "online": connectivity == "online",
                    "connectivity": connectivity,
                    "binding_status": d.binding_status,
                    "last_sync_at": _safe_raw_dt_static(d.last_sync_at),
                    "last_heartbeat_at": _safe_raw_dt_static(d.last_heartbeat_at),
                    "sync_count": d.sync_count or 0,
                }, user))
            except Exception as e:
                logger.warning(f"[DASHBOARD] Device serialization failed: {e}")
                recent_devices.append(_finalize_device_summary({"id": str(getattr(d, 'id', '?')), "device_name": "?", "status": "error", "online": False, "connectivity": "offline"}, user))
    except Exception as e:
        logger.warning(f"[DASHBOARD] Device query failed: {type(e).__name__}: {e} — skipping recent_devices")
        try:
            await db.rollback()
        except Exception:
            pass

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
    # v3.15.2: Defensive — ORM crash → rollback → fresh-session raw SQL fallback
    devices = []
    try:
        result = await db.execute(stmt)
        all_devs = result.scalars().all()
        for d in all_devs:
            try:
                devices.append(_finalize_device_summary(_ser_device(d), user))
            except Exception as e:
                logger.warning(f"[DEVICES-LIST] Serialization failed for device: {e}")
                devices.append(_finalize_device_summary({"id": str(getattr(d, 'id', '?')), "device_name": str(getattr(d, 'device_name', 'Fehler')), "status": "error", "_error": str(e)}, user))
    except Exception as e:
        # ORM deserialization failed — rollback session, use FRESH session for raw SQL
        logger.warning(f"[DEVICES-LIST] ORM execute failed: {type(e).__name__}: {e} — fresh-session raw SQL fallback")
        try:
            await db.rollback()
        except Exception:
            pass
        from sqlalchemy import text as _t
        try:
            async with AsyncSessionLocal() as fresh_db:
                raw_rows = (await fresh_db.execute(_t(
                    "SELECT id, location_id, install_id, api_key, device_name, status, "
                    "binding_status, license_id, reported_version, sync_count FROM devices"
                ))).mappings().all()
                devices = []
                for r in raw_rows:
                    devices.append(_finalize_device_summary({
                        "id": r["id"], "location_id": r.get("location_id"),
                        "install_id": r.get("install_id"),
                        "api_key_preview": (f"{r.get('api_key')[:8]}...{r.get('api_key')[-4:]}" if r.get("api_key") and len(r.get("api_key")) > 12 else ("****" if r.get("api_key") else None)),
                        "device_name": r.get("device_name"), "status": r.get("status", "unknown"),
                        "binding_status": r.get("binding_status", "unknown"),
                        "license_id": r.get("license_id"), "reported_version": r.get("reported_version"),
                        "sync_count": r.get("sync_count", 0) or 0,
                        "last_sync_at": None, "last_heartbeat_at": None,
                        "created_at": None, "ws_connected": False,
                    }, user))
        except Exception as e2:
            logger.error(f"[DEVICES-LIST] Even fresh-session raw SQL failed: {e2}")
            devices = []
    return devices


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
    return _ser_device(d, include_api_key=True)


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
async def list_licenses(customer_id: str = None, status: str = None, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(CentralLicense).order_by(CentralLicense.created_at.desc())
    if customer_id:
        if not can_access_customer(user, customer_id):
            raise HTTPException(403, "Access denied")
        stmt = stmt.where(CentralLicense.customer_id == customer_id)
    else:
        stmt = apply_customer_scope(stmt, user, CentralLicense.customer_id)
    if status:
        stmt = stmt.where(CentralLicense.status == status)
    result = await db.execute(stmt)
    lics = result.scalars().all()
    # Enrich with customer/location names and device count
    cust_ids = set(l.customer_id for l in lics if l.customer_id)
    cust_map = {}
    if cust_ids:
        cr = await db.execute(select(CentralCustomer).where(CentralCustomer.id.in_(cust_ids)))
        cust_map = {c.id: c.name for c in cr.scalars().all()}
    items = []
    for lic in lics:
        d = _ser_license(lic)
        d["customer_name"] = cust_map.get(lic.customer_id)
        # Count bound devices
        dc = await db.execute(select(func.count()).where(CentralDevice.license_id == lic.id))
        d["device_count"] = dc.scalar() or 0
        items.append(d)
    return items


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


@app.get("/api/licensing/licenses/{license_id}")
async def get_license_detail(license_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Full license detail with bound devices and activation token."""
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")

    # Get bound devices
    dev_result = await db.execute(
        select(CentralDevice).where(CentralDevice.license_id == license_id).order_by(CentralDevice.created_at.desc())
    )
    devices = [_finalize_device_summary(_ser_device(d), user) for d in dev_result.scalars().all()]

    # Get activation token (latest unused for this license)
    tok_result = await db.execute(
        select(RegistrationToken).where(
            RegistrationToken.license_id == license_id
        ).order_by(RegistrationToken.created_at.desc())
    )
    tokens = tok_result.scalars().all()
    active_token = None
    for t in tokens:
        if not t.used_at and not t.is_revoked and (_aware(t.expires_at) > _utcnow() if t.expires_at else True):
            active_token = t
            break

    # Customer/location names
    cust_name = None
    loc_name = None
    if lic.customer_id:
        cr = await db.execute(select(CentralCustomer).where(CentralCustomer.id == lic.customer_id))
        c = cr.scalar_one_or_none()
        if c: cust_name = c.name
    if lic.location_id:
        lr = await db.execute(select(CentralLocation).where(CentralLocation.id == lic.location_id))
        l = lr.scalar_one_or_none()
        if l: loc_name = l.name

    now = _utcnow()
    computed_status = _compute_status(lic, now)

    detail = _ser_license(lic)
    detail["computed_status"] = computed_status
    detail["customer_name"] = cust_name
    detail["location_name"] = loc_name
    detail["devices"] = devices
    detail["device_count"] = len(devices)
    detail["active_token"] = _ser_reg_token_summary(active_token) if active_token else None
    detail["token_history"] = [_ser_reg_token_summary(t) for t in tokens]
    return detail


@app.get("/api/licensing/licenses/{license_id}/token")
async def get_or_create_license_token(license_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get existing active token or create a new one for this license."""
    require_installer_or_above(user)
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")

    # Check for existing active token
    now = _utcnow()
    tok_result = await db.execute(
        select(RegistrationToken).where(
            RegistrationToken.license_id == license_id,
            RegistrationToken.used_at.is_(None),
            RegistrationToken.is_revoked == False,
        ).order_by(RegistrationToken.created_at.desc())
    )
    for t in tok_result.scalars().all():
        if t.expires_at and _aware(t.expires_at) > now:
            return {"exists": True, "token": _ser_reg_token(t), "message": "Aktiver Token vorhanden"}

    # Create new token
    raw_token, token_hash, preview = _generate_reg_token()
    token = RegistrationToken(
        token_hash=token_hash, token_preview=preview,
        customer_id=lic.customer_id, location_id=lic.location_id,
        license_id=lic.id, expires_at=now + timedelta(hours=72),
        created_by=user.username, note=f"Auto-created for license {lic.plan_type}",
    )
    db.add(token)
    await db.flush()
    await _log_audit(db, "REG_TOKEN_CREATED", license_id=lic.id, actor=user.username,
                     message="Activation token created for license (auto)")
    result_data = _ser_reg_token(token)
    result_data["raw_token"] = raw_token
    return {"exists": False, "token": result_data, "raw_token": raw_token, "message": "Neuer Token erstellt"}


@app.post("/api/licensing/licenses/{license_id}/regenerate-token")
async def regenerate_license_token(license_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Revoke all existing tokens and create a fresh one."""
    require_installer_or_above(user)
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")

    # Revoke all existing unused tokens for this license
    now = _utcnow()
    tok_result = await db.execute(
        select(RegistrationToken).where(
            RegistrationToken.license_id == license_id,
            RegistrationToken.used_at.is_(None),
            RegistrationToken.is_revoked == False,
        )
    )
    revoked_count = 0
    for t in tok_result.scalars().all():
        t.is_revoked = True
        t.revoked_at = now
        t.revoked_by = user.username
        revoked_count += 1

    # Create new token
    raw_token, token_hash, preview = _generate_reg_token()
    token = RegistrationToken(
        token_hash=token_hash, token_preview=preview,
        customer_id=lic.customer_id, location_id=lic.location_id,
        license_id=lic.id, expires_at=now + timedelta(hours=72),
        created_by=user.username, note=f"Regenerated (replaced {revoked_count} old tokens)",
    )
    db.add(token)
    await db.flush()
    await _log_audit(db, "REG_TOKEN_REGENERATED", license_id=lic.id, actor=user.username,
                     message=f"Token regenerated for license ({revoked_count} old tokens revoked)")
    result_data = _ser_reg_token(token)
    result_data["raw_token"] = raw_token
    return {"token": result_data, "raw_token": raw_token, "revoked_count": revoked_count}


@app.delete("/api/licensing/licenses/{license_id}")
async def delete_license(license_id: str, action: str = "deactivate", user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Soft-delete a license. action=deactivate|archive"""
    require_installer_or_above(user)
    result = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    if not can_access_customer(user, lic.customer_id):
        raise HTTPException(403, "Access denied")

    if action not in ("deactivate", "archive"):
        raise HTTPException(400, "action must be 'deactivate' or 'archive'")

    old_status = lic.status
    lic.status = "deactivated" if action == "deactivate" else "archived"
    await db.flush()
    await _log_audit(db, f"LICENSE_{action.upper()}D", license_id=lic.id, actor=user.username,
                     message=f"License {action}d (was: {old_status})")
    return {"success": True, "status": lic.status, "license": _ser_license(lic)}


@app.post("/api/licensing/licenses/{license_id}/unbind-device/{device_id}")
async def unbind_device_from_license(license_id: str, device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Unbind a device from a license."""
    require_installer_or_above(user)
    result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id, CentralDevice.license_id == license_id))
    dev = result.scalar_one_or_none()
    if not dev:
        raise HTTPException(404, "Device not bound to this license")
    dev.license_id = None
    dev.binding_status = "unbound"
    await db.flush()
    await _log_audit(db, "DEVICE_UNBOUND", device_id=device_id, license_id=license_id, actor=user.username,
                     message=f"Device {dev.device_name or device_id} unbound from license")
    return {"success": True, "device": _ser_device(dev)}


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


def _ser_reg_token_summary(t: RegistrationToken) -> dict:
    return {
        "id": t.id,
        "token_preview": t.token_preview,
        "license_id": t.license_id,
        "device_name_template": t.device_name_template,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "used_at": t.used_at.isoformat() if t.used_at else None,
        "is_revoked": t.is_revoked,
        "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "status": _token_status(t),
    }

def _token_status(t: RegistrationToken) -> str:
    if t.is_revoked: return "revoked"
    if t.used_at: return "used"
    now = _utcnow()
    if t.expires_at and _aware(t.expires_at) < now: return "expired"
    return "active"


def _safe_iso(dt):
    if not dt:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _ser_device_credential(credential: DeviceCredential, device: CentralDevice = None) -> dict:
    payload = {
        "id": credential.id,
        "device_id": credential.device_id,
        "status": credential.status,
        "credential_kind": credential.credential_kind,
        "fingerprint": credential.fingerprint,
        "issued_at": _safe_iso(credential.issued_at),
        "expires_at": _safe_iso(credential.expires_at),
        "revoked_at": _safe_iso(credential.revoked_at),
        "replacement_for_credential_id": credential.replacement_for_credential_id,
        "metadata": credential.details_json or {},
        "key_id": (credential.details_json or {}).get("key_id"),
        "created_at": _safe_iso(credential.created_at),
        "updated_at": _safe_iso(credential.updated_at),
    }
    payload["verification"] = verify_placeholder_certificate(credential=credential, device=device)
    payload["rotation"] = build_credential_rotation_lineage(credential=credential)
    payload["rotation_summary"] = summarize_credential_rotation(payload["rotation"])
    payload["signing_key_lineage"] = build_signing_key_lineage(key_id=(credential.details_json or {}).get("key_id"))
    payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


def _ser_device_credential_summary(credential: DeviceCredential, device: CentralDevice = None) -> dict:
    payload = {
        "id": credential.id,
        "device_id": credential.device_id,
        "status": credential.status,
        "credential_kind": credential.credential_kind,
        "fingerprint": credential.fingerprint,
        "issued_at": _safe_iso(credential.issued_at),
        "expires_at": _safe_iso(credential.expires_at),
        "revoked_at": _safe_iso(credential.revoked_at),
        "replacement_for_credential_id": credential.replacement_for_credential_id,
        "key_id": (credential.details_json or {}).get("key_id"),
        "created_at": _safe_iso(credential.created_at),
        "updated_at": _safe_iso(credential.updated_at),
    }
    payload["verification"] = verify_placeholder_certificate(credential=credential, device=device)
    payload["rotation"] = build_credential_rotation_lineage(credential=credential)
    payload["rotation_summary"] = summarize_credential_rotation(payload["rotation"])
    payload["signing_key_lineage"] = build_signing_key_lineage(key_id=(credential.details_json or {}).get("key_id"))
    payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


def _ser_device_lease(lease: DeviceLease, device: CentralDevice = None, credential: DeviceCredential = None) -> dict:
    payload = {
        "id": lease.id,
        "device_id": lease.device_id,
        "central_license_id": lease.central_license_id,
        "lease_id": lease.lease_id,
        "status": lease.status,
        "computed_status": compute_lease_status(lease),
        "issued_at": _safe_iso(lease.issued_at),
        "expires_at": _safe_iso(lease.expires_at),
        "grace_until": _safe_iso(lease.grace_until),
        "revoked_at": _safe_iso(lease.revoked_at),
        "signature": lease.signature,
        "metadata": lease.details_json or {},
        "created_at": _safe_iso(lease.created_at),
        "updated_at": _safe_iso(lease.updated_at),
    }
    bundle = get_stored_signed_lease_bundle(lease)
    if bundle is None and device is not None:
        bundle = build_placeholder_signed_lease(device=device, lease=lease, credential=credential)
    if bundle is not None:
        payload["signed_bundle"] = bundle
        payload["signed_bundle_source"] = "stored" if get_stored_signed_lease_bundle(lease) is not None else "rebuilt"
        payload["verification"] = verify_placeholder_signed_lease(bundle=bundle, device=device, lease=lease, credential=credential)
        payload["signing_key_lineage"] = build_signing_key_lineage(key_id=bundle.get("key_id"))
        payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


def _ser_device_lease_summary(lease: DeviceLease, device: CentralDevice = None, credential: DeviceCredential = None) -> dict:
    payload = {
        "id": lease.id,
        "device_id": lease.device_id,
        "central_license_id": lease.central_license_id,
        "lease_id": lease.lease_id,
        "status": lease.status,
        "computed_status": compute_lease_status(lease),
        "issued_at": _safe_iso(lease.issued_at),
        "expires_at": _safe_iso(lease.expires_at),
        "grace_until": _safe_iso(lease.grace_until),
        "revoked_at": _safe_iso(lease.revoked_at),
        "created_at": _safe_iso(lease.created_at),
        "updated_at": _safe_iso(lease.updated_at),
    }
    bundle = get_stored_signed_lease_bundle(lease)
    if bundle is None and device is not None:
        bundle = build_placeholder_signed_lease(device=device, lease=lease, credential=credential)
    if bundle is not None:
        payload["verification"] = verify_placeholder_signed_lease(bundle=bundle, device=device, lease=lease, credential=credential)
        payload["signed_bundle_source"] = "stored" if get_stored_signed_lease_bundle(lease) is not None else "rebuilt"
        payload["signing_key_lineage"] = build_signing_key_lineage(key_id=bundle.get("key_id"))
        payload["signing_key_lineage_summary"] = summarize_lineage(payload["signing_key_lineage"])
    return payload


async def _get_device_with_scope_check(device_id: str, user: AuthUser, db: AsyncSession) -> CentralDevice:
    result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    if not await can_access_location(user, device.location_id, db):
        raise HTTPException(403, "Access denied")
    return device


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
    """Register a new device using a one-time registration token. Public endpoint.
    v3.14.0: Fixed location_id resolution chain + graceful re-registration."""
    raw_token = body.get("token")
    install_id = body.get("install_id")
    device_name = body.get("device_name")

    if not raw_token:
        raise HTTPException(400, "Registrierungs-Token fehlt")
    if not install_id:
        raise HTTPException(400, "install_id fehlt")

    token_hash = _hash_token(raw_token)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.token_hash == token_hash))
    token = result.scalar_one_or_none()

    if not token:
        await _log_audit(db, "DEVICE_REGISTRATION_FAILED", install_id=install_id, message="Invalid token")
        raise HTTPException(403, "Ungueltiger Registrierungs-Token")
    if token.is_revoked:
        raise HTTPException(403, "Token wurde widerrufen")
    if token.used_at:
        raise HTTPException(403, "Token wurde bereits verwendet")
    now = _utcnow()
    if token.expires_at and _aware(token.expires_at) < now:
        raise HTTPException(403, "Token ist abgelaufen")

    # v3.14.0: Graceful re-registration — update existing device instead of 409
    existing_r = await db.execute(select(CentralDevice).where(CentralDevice.install_id == install_id))
    existing_device = existing_r.scalar_one_or_none()

    # ── Resolve location_id: Token → License → Customer default ──
    location_id = token.location_id
    customer_id = token.customer_id

    if location_id and not customer_id:
        loc_r = await db.execute(select(CentralLocation).where(CentralLocation.id == location_id))
        loc = loc_r.scalar_one_or_none()
        if loc:
            customer_id = loc.customer_id

    if not location_id and not customer_id:
        raise HTTPException(400, "Token hat keinen Kunden/Standort")

    # v3.11: Resolve license
    license_id = token.license_id
    resolved_license = None
    if license_id:
        lic_r = await db.execute(select(CentralLicense).where(CentralLicense.id == license_id))
        resolved_license = lic_r.scalar_one_or_none()
    elif customer_id:
        conditions = [CentralLicense.customer_id == customer_id,
                      CentralLicense.status.in_(["active", "test"])]
        if location_id:
            conditions.append((CentralLicense.location_id == location_id) | (CentralLicense.location_id.is_(None)))
        lic_r = await db.execute(select(CentralLicense).where(and_(*conditions)))
        lics = lic_r.scalars().all()
        if lics:
            best, _ = _find_best_license(lics, now)
            if best:
                resolved_license = best
                license_id = best.id

    # v3.14.0: Resolve location_id from license if token didn't have one
    if not location_id and resolved_license and resolved_license.location_id:
        location_id = resolved_license.location_id

    # v3.14.0: Auto-create default location for customer if still no location
    if not location_id and customer_id:
        # Try to find an existing location for this customer
        loc_r = await db.execute(
            select(CentralLocation).where(CentralLocation.customer_id == customer_id).limit(1)
        )
        existing_loc = loc_r.scalar_one_or_none()
        if existing_loc:
            location_id = existing_loc.id
        else:
            # Create a default location
            cust_r = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
            cust = cust_r.scalar_one_or_none()
            cust_name = cust.name if cust else "Kunde"
            new_loc = CentralLocation(
                customer_id=customer_id,
                name=f"{cust_name} - Hauptstandort",
            )
            db.add(new_loc)
            await db.flush()
            location_id = new_loc.id
            logger.info(f"[REG] Auto-created default location {location_id} for customer {customer_id}")

    if not location_id:
        raise HTTPException(400, "Standort konnte nicht aufgeloest werden. Bitte Lizenz-/Token-Konfiguration pruefen.")

    # Enforce max_devices (exclude existing device from count for re-registration)
    if resolved_license:
        exclude_clause = CentralDevice.license_id == resolved_license.id
        count_conditions = [exclude_clause, CentralDevice.status == "active"]
        if existing_device:
            count_conditions.append(CentralDevice.id != existing_device.id)
        bound_count_r = await db.execute(select(func.count()).where(*count_conditions))
        bound_count = bound_count_r.scalar() or 0
        if bound_count >= resolved_license.max_devices:
            await _log_audit(db, "DEVICE_REGISTRATION_REJECTED", install_id=install_id,
                             license_id=resolved_license.id,
                             message=f"max_devices limit reached ({bound_count}/{resolved_license.max_devices})")
            raise HTTPException(403, f"Geraete-Limit erreicht: {bound_count}/{resolved_license.max_devices} Geraete bereits aktiv")

    effective_name = device_name or token.device_name_template or f"Kiosk-{install_id[:8]}"
    trust_status = DeviceTrustStatus.LEGACY_BOUND.value
    trust_changed_at = now

    if existing_device:
        # v3.14.0: Re-registration — update existing device with new binding
        existing_device.location_id = location_id
        existing_device.license_id = license_id
        existing_device.device_name = effective_name
        existing_device.status = "active"
        existing_device.binding_status = "bound"
        existing_device.trust_status = trust_status
        existing_device.trust_reason = "legacy registration flow (install_id/api_key)"
        existing_device.trust_last_changed_at = trust_changed_at
        existing_device.last_sync_at = now
        existing_device.last_sync_ip = request.client.host if request.client else None
        existing_device.registered_via_token_id = token.id
        # Keep the existing api_key so the device doesn't lose auth
        api_key = existing_device.api_key
        device_id = existing_device.id
        await db.flush()
        logger.info(f"[REG] Re-registered existing device {device_id} (install_id={install_id})")
    else:
        # New registration
        api_key = f"dk_{secrets.token_urlsafe(32)}"
        new_device = CentralDevice(
            location_id=location_id, install_id=install_id, api_key=api_key,
            device_name=effective_name, status="active", binding_status="bound",
            trust_status=trust_status,
            trust_reason="legacy registration flow (install_id/api_key)",
            trust_last_changed_at=trust_changed_at,
            credential_status=DeviceCredentialStatus.NONE.value,
            lease_status=DeviceLeaseStatus.NONE.value,
            license_id=license_id,
            last_sync_at=now, last_sync_ip=request.client.host if request.client else None,
            sync_count=0, registered_via_token_id=token.id,
        )
        db.add(new_device)
        await db.flush()
        device_id = new_device.id

    token.used_at = now
    token.used_by_install_id = install_id
    token.used_by_device_id = device_id
    await db.flush()

    # Build response
    license_status = "no_license"
    plan_type = None
    expiry = None
    customer_name = None

    if customer_id:
        cust_r = await db.execute(select(CentralCustomer).where(CentralCustomer.id == customer_id))
        cust = cust_r.scalar_one_or_none()
        if cust:
            customer_name = cust.name

    if resolved_license:
        license_status = _compute_status(resolved_license, now)
        plan_type = resolved_license.plan_type
        expiry = resolved_license.ends_at.isoformat() if resolved_license.ends_at else None

    reg_type = "re-registered" if existing_device else "registered"
    await _log_audit(db, "DEVICE_REGISTERED", device_id=device_id, install_id=install_id,
                     license_id=license_id, actor="registration",
                     message=f"Device {effective_name} {reg_type} via token {token.token_preview}")

    return {
        "success": True, "device_id": device_id, "device_name": effective_name,
        "api_key": api_key, "customer_id": customer_id, "customer_name": customer_name,
        "location_id": location_id, "license_id": license_id, "license_status": license_status,
        "plan_type": plan_type, "expiry": expiry, "binding_status": "bound",
        "re_registered": existing_device is not None,
        "server_timestamp": now.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# DEVICE TRUST / ENROLLMENT SCAFFOLDING — additive only
# ═══════════════════════════════════════════════════════════════

@app.post("/api/device-trust/enroll")
async def enroll_device_trust(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    raw_token = body.get("token")
    install_id = body.get("install_id")
    csr_pem = body.get("csr_pem")
    public_key_pem = body.get("public_key_pem")
    fingerprint = body.get("credential_fingerprint") or body.get("fingerprint")
    device_name = body.get("device_name")
    now = _utcnow()

    if not raw_token:
        raise HTTPException(400, "Enrollment token fehlt")
    if not install_id:
        raise HTTPException(400, "install_id fehlt")
    if not csr_pem and not public_key_pem:
        raise HTTPException(400, "csr_pem oder public_key_pem erforderlich")

    enrollment_material = normalize_enrollment_material(
        csr_pem=csr_pem,
        public_key_pem=public_key_pem,
        fingerprint=fingerprint,
    )

    token_hash = _hash_token(raw_token)
    result = await db.execute(select(RegistrationToken).where(RegistrationToken.token_hash == token_hash))
    token = result.scalar_one_or_none()
    if not token:
        await _log_audit(db, "DEVICE_ENROLLMENT_FAILED", install_id=install_id, message="Invalid enrollment token")
        raise HTTPException(403, "Ungueltiger Enrollment-Token")
    if token.is_revoked:
        raise HTTPException(403, "Token wurde widerrufen")
    if token.expires_at and _aware(token.expires_at) < now:
        raise HTTPException(403, "Token ist abgelaufen")

    existing_r = await db.execute(select(CentralDevice).where(CentralDevice.install_id == install_id))
    device = existing_r.scalar_one_or_none()
    if not device and token.used_by_device_id:
        existing_r = await db.execute(select(CentralDevice).where(CentralDevice.id == token.used_by_device_id))
        device = existing_r.scalar_one_or_none()

    if not device:
        registration_result = await register_device(
            {"token": raw_token, "install_id": install_id, "device_name": device_name},
            request,
            db,
        )
        existing_r = await db.execute(select(CentralDevice).where(CentralDevice.id == registration_result["device_id"]))
        device = existing_r.scalar_one_or_none()

    if not device:
        raise HTTPException(500, "Device could not be resolved for enrollment")

    existing_cred_r = await db.execute(
        select(DeviceCredential)
        .where(
            DeviceCredential.device_id == device.id,
            DeviceCredential.status.in_([
                DeviceCredentialStatus.PENDING.value,
                DeviceCredentialStatus.ACTIVE.value,
                DeviceCredentialStatus.ROTATING.value,
            ]),
        )
        .order_by(DeviceCredential.created_at.desc())
    )
    credential = existing_cred_r.scalars().first()
    metadata = {
        "source": "device_trust_enrollment_placeholder",
        "install_id": install_id,
        "device_name": device_name or device.device_name,
        "requested_at": now.isoformat(),
        "key_id": enrollment_material["key_id"],
        "client_ip": request.client.host if request.client else None,
        "hardware": body.get("hardware") or {},
        "runtime": body.get("runtime") or {},
    }

    if credential:
        credential.status = DeviceCredentialStatus.PENDING.value
        credential.credential_kind = body.get("credential_kind", credential.credential_kind or "x509_csr")
        credential.fingerprint = enrollment_material["fingerprint"]
        credential.csr_pem = enrollment_material["csr_pem"]
        credential.public_key_pem = enrollment_material["public_key_pem"]
        credential.details_json = metadata
    else:
        credential = DeviceCredential(
            device_id=device.id,
            status=DeviceCredentialStatus.PENDING.value,
            credential_kind=body.get("credential_kind", "x509_csr"),
            fingerprint=enrollment_material["fingerprint"],
            csr_pem=enrollment_material["csr_pem"],
            public_key_pem=enrollment_material["public_key_pem"],
            details_json=metadata,
        )
        db.add(credential)

    device.trust_status = DeviceTrustStatus.PENDING_ENROLLMENT.value
    device.trust_reason = "pending device trust enrollment"
    device.trust_last_changed_at = now
    device.credential_status = DeviceCredentialStatus.PENDING.value
    device.credential_fingerprint = enrollment_material["fingerprint"]
    device.registered_via_token_id = token.id
    device.last_sync_at = now
    device.last_sync_ip = request.client.host if request.client else None
    await db.flush()

    await _log_audit(
        db,
        "DEVICE_ENROLLMENT_RECORDED",
        device_id=device.id,
        install_id=install_id,
        license_id=device.license_id,
        actor="device",
        message=f"Pending enrollment credential recorded for device {device.id}",
    )

    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": _ser_device(device),
        "credential": _ser_device_credential(credential, device=device),
        "next_action": "await_central_issuance",
    }


@app.get("/api/device-trust/devices/{device_id}")
async def get_device_trust_detail(device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_owner_or_above(user)
    device = await _get_device_with_scope_check(device_id, user, db)
    now = _utcnow()

    cred_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    lease_result = await db.execute(
        select(DeviceLease)
        .where(DeviceLease.device_id == device.id)
        .order_by(DeviceLease.created_at.desc())
    )

    credentials = cred_result.scalars().all()
    credentials_by_id = {c.id: c for c in credentials}
    active_credential = next((c for c in credentials if c.status == DeviceCredentialStatus.ACTIVE.value), None)
    leases = lease_result.scalars().all()
    current_lease = leases[0] if leases else None
    current_lease_credential = None
    if current_lease is not None:
        current_lease_credential = credentials_by_id.get((current_lease.details_json or {}).get("credential_id")) or active_credential
    effective_credential = current_lease_credential or active_credential
    reconciliation = reconcile_trust_material(
        device=device,
        credential=effective_credential,
        lease=current_lease,
        credentials=credentials,
        leases=leases,
    )
    issuer_profiles = build_issuer_profile_diagnostics(
        credential=effective_credential,
        lease=current_lease,
        device=device,
        credentials=credentials,
    )
    signing_registry = build_signing_registry_diagnostics(
        credential=effective_credential,
        lease=current_lease,
        device=device,
        credentials=credentials,
    )

    return _finalize_device_trust_detail({
        "device": _ser_device(device),
        "diagnostics_timestamp": now.isoformat(),
        "credentials": [_ser_device_credential_summary(c, device=device) for c in credentials],
        "leases": [
            _ser_device_lease_summary(
                l,
                device=device,
                credential=credentials_by_id.get((l.details_json or {}).get("credential_id")) or active_credential,
            )
            for l in leases
        ],
        "reconciliation": reconciliation,
        "reconciliation_summary": reconciliation.get("summary") or build_reconciliation_summary(reconciliation=reconciliation),
        "issuer_profiles": issuer_profiles,
        "signing_registry": signing_registry,
        "endpoint_summary": build_support_diagnostics_compact_summary(
            issuer_profiles=issuer_profiles,
            signing_registry=signing_registry,
            material_history=reconciliation.get("material_history"),
            credential=effective_credential,
            lease=current_lease,
            now=now,
        ),
    }, user)


@app.get("/api/device-trust/devices/{device_id}/support-diagnostics")
async def get_device_trust_support_diagnostics(device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_owner_or_above(user)
    device = await _get_device_with_scope_check(device_id, user, db)
    now = _utcnow()

    cred_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    lease_result = await db.execute(
        select(DeviceLease)
        .where(DeviceLease.device_id == device.id)
        .order_by(DeviceLease.created_at.desc())
    )
    credentials = cred_result.scalars().all()
    active_credential = next((c for c in credentials if c.status == DeviceCredentialStatus.ACTIVE.value), None)
    leases = lease_result.scalars().all()
    current_lease = leases[0] if leases else None
    lease_credential = active_credential
    if current_lease is not None:
        credential_id = (current_lease.details_json or {}).get("credential_id")
        lease_credential = next((c for c in credentials if c.id == credential_id), None) or active_credential

    reconciliation = reconcile_trust_material(
        device=device,
        credential=lease_credential,
        lease=current_lease,
        credentials=credentials,
        leases=leases,
    )
    issuer_profiles = build_issuer_profile_diagnostics(
        credential=lease_credential,
        lease=current_lease,
        device=device,
        credentials=credentials,
    )
    signing_registry = build_signing_registry_diagnostics(
        credential=lease_credential,
        lease=current_lease,
        device=device,
        credentials=credentials,
    )
    payload = {
        "device": _ser_device(device),
        "diagnostics_timestamp": now.isoformat(),
        "reconciliation": reconciliation,
        "reconciliation_summary": reconciliation.get("summary") or build_reconciliation_summary(reconciliation=reconciliation),
        "issuer_profiles": issuer_profiles,
        "signing_registry": signing_registry,
        "endpoint_summary": build_support_diagnostics_compact_summary(
            issuer_profiles=issuer_profiles,
            signing_registry=signing_registry,
            material_history=reconciliation.get("material_history"),
            credential=lease_credential,
            lease=current_lease,
            now=now,
        ),
        "credential": _ser_device_credential(lease_credential, device=device) if lease_credential else None,
        "lease": _ser_device_lease(current_lease, device=device, credential=lease_credential) if current_lease else None,
        "mode": "support_diagnostics_read_only",
        "enforcement": "disabled",
    }
    return _finalize_device_trust_detail(payload, user)


@app.post("/api/device-trust/devices/{device_id}/issue-credential")
async def issue_device_credential_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    device = await _get_device_with_scope_check(device_id, user, db)

    credential_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    existing = credential_result.scalars().all()
    credential = next((c for c in existing if c.status in [DeviceCredentialStatus.PENDING.value, DeviceCredentialStatus.ROTATING.value]), None)
    if credential is None:
        credential = next((c for c in existing if c.status == DeviceCredentialStatus.ACTIVE.value), None)

    if credential is None:
        raise HTTPException(409, "No enrollment material available for credential issuance")

    now = _utcnow()
    if credential.status == DeviceCredentialStatus.ACTIVE.value:
        credential.status = DeviceCredentialStatus.ROTATING.value
        replacement = DeviceCredential(
            device_id=device.id,
            status=DeviceCredentialStatus.PENDING.value,
            credential_kind=credential.credential_kind,
            fingerprint=credential.fingerprint,
            csr_pem=credential.csr_pem,
            public_key_pem=credential.public_key_pem,
            replacement_for_credential_id=credential.id,
            details_json=dict(credential.details_json or {}),
        )
        db.add(replacement)
        await db.flush()
        credential = replacement

    validity_days = int(body.get("validity_days", 30))
    if validity_days < 1 or validity_days > 366:
        raise HTTPException(400, "validity_days out of allowed range")

    issue_placeholder_credential(
        credential=credential,
        device=device,
        issued_by=user.username,
        validity_days=validity_days,
        now=now,
    )
    await db.flush()
    await _log_audit(
        db,
        "DEVICE_CREDENTIAL_ISSUED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder credential issued (key_id={(credential.details_json or {}).get('key_id')})",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": _ser_device(device),
        "credential": _ser_device_credential(credential, device=device),
    }


@app.post("/api/device-trust/devices/{device_id}/issue-lease")
async def issue_device_lease_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    device = await _get_device_with_scope_check(device_id, user, db)
    now = _utcnow()

    duration_hours = int(body.get("duration_hours", 24))
    grace_hours = int(body.get("grace_hours", 24))
    if duration_hours < 1 or duration_hours > 24 * 31:
        raise HTTPException(400, "duration_hours out of allowed range")
    if grace_hours < 0 or grace_hours > 24 * 31:
        raise HTTPException(400, "grace_hours out of allowed range")

    issued_at = now
    expires_at = now + timedelta(hours=duration_hours)
    grace_until = expires_at + timedelta(hours=grace_hours)
    lease_metadata = {
        "mode": "placeholder",
        "issued_by_role": user.role,
        "issued_by": user.username,
        "reason": body.get("reason") or "manual placeholder issuance",
        "capability_overrides": body.get("capability_overrides") or {},
        "lease_policy": {
            "duration_hours": duration_hours,
            "grace_hours": grace_hours,
            "enforcement": "disabled",
        },
    }
    signature = hashlib.sha256(f"{device.id}:{issued_at.isoformat()}:{expires_at.isoformat()}".encode()).hexdigest()

    lease = DeviceLease(
        device_id=device.id,
        central_license_id=device.license_id,
        status=DeviceLeaseStatus.ACTIVE.value,
        issued_at=issued_at,
        expires_at=expires_at,
        grace_until=grace_until,
        signature=signature,
        details_json=lease_metadata,
    )
    db.add(lease)

    credential_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    active_credential = next((c for c in credential_result.scalars().all() if c.status == DeviceCredentialStatus.ACTIVE.value), None)
    attach_lease_key_metadata(lease=lease, credential=active_credential)

    if device.credential_status == DeviceCredentialStatus.NONE.value:
        device.credential_status = DeviceCredentialStatus.PENDING.value
    sync_device_trust_snapshot(device, lease=lease, credential=active_credential, now=now)

    await db.flush()
    await _log_audit(
        db,
        "DEVICE_LEASE_ISSUED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder lease issued until {expires_at.isoformat()}",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": _ser_device(device),
        "lease": _ser_device_lease(lease, device=device, credential=active_credential),
    }


@app.post("/api/device-trust/devices/{device_id}/revoke-credential")
async def revoke_device_credential_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    device = await _get_device_with_scope_check(device_id, user, db)
    credential_id = body.get("credential_id")

    credential_stmt = select(DeviceCredential).where(DeviceCredential.device_id == device.id)
    if credential_id:
        credential_stmt = credential_stmt.where(DeviceCredential.id == credential_id)
    credential_stmt = credential_stmt.order_by(DeviceCredential.created_at.desc())
    credential = (await db.execute(credential_stmt)).scalars().first()
    if credential is None:
        raise HTTPException(404, "Credential not found")

    revoke_placeholder_credential(
        credential=credential,
        device=device,
        reason=body.get("reason"),
        revoked_by=user.username,
        now=_utcnow(),
    )
    await db.flush()
    await _log_audit(
        db,
        "DEVICE_CREDENTIAL_REVOKED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder credential revoked ({credential.id})",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": _ser_device(device),
        "credential": _ser_device_credential(credential, device=device),
    }


@app.post("/api/device-trust/devices/{device_id}/revoke-lease")
async def revoke_device_lease_placeholder(device_id: str, body: dict, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_installer_or_above(user)
    device = await _get_device_with_scope_check(device_id, user, db)
    lease_id = body.get("lease_id")

    lease_stmt = select(DeviceLease).where(DeviceLease.device_id == device.id)
    if lease_id:
        lease_stmt = lease_stmt.where(DeviceLease.id == lease_id)
    lease_stmt = lease_stmt.order_by(DeviceLease.created_at.desc())
    lease = (await db.execute(lease_stmt)).scalars().first()
    if lease is None:
        raise HTTPException(404, "Lease not found")

    credential_stmt = (
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    credential = next((c for c in (await db.execute(credential_stmt)).scalars().all() if c.status == DeviceCredentialStatus.ACTIVE.value), None)

    revoke_placeholder_lease(
        lease=lease,
        device=device,
        credential=credential,
        reason=body.get("reason"),
        revoked_by=user.username,
        now=_utcnow(),
    )
    await db.flush()
    await _log_audit(
        db,
        "DEVICE_LEASE_REVOKED",
        device_id=device.id,
        license_id=device.license_id,
        actor=user.username,
        message=f"Placeholder lease revoked ({lease.lease_id})",
    )
    return {
        "ok": True,
        "mode": "scaffold_only",
        "device": _ser_device(device),
        "lease": _ser_device_lease(lease, device=device, credential=credential),
    }


@app.get("/api/device-trust/lease/current")
async def get_current_device_lease(request: Request, db: AsyncSession = Depends(get_db)):
    device = await _authenticate_device(request, db)
    now = _utcnow()

    lease_result = await db.execute(
        select(DeviceLease)
        .where(DeviceLease.device_id == device.id)
        .order_by(DeviceLease.created_at.desc())
    )
    leases = lease_result.scalars().all()
    lease = leases[0] if leases else None

    if lease:
        sync_device_trust_snapshot(device, lease=lease, now=now)
        await db.flush()

    credential_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id == device.id)
        .order_by(DeviceCredential.created_at.desc())
    )
    credentials = credential_result.scalars().all()
    credentials_by_id = {c.id: c for c in credentials}
    active_credential = next((c for c in credentials if c.status == DeviceCredentialStatus.ACTIVE.value), None)
    lease_credential = active_credential
    if lease is not None:
        credential_id = (lease.details_json or {}).get("credential_id")
        lease_credential = credentials_by_id.get(credential_id) or active_credential

    reconciliation = reconcile_trust_material(
        device=device,
        credential=lease_credential,
        lease=lease,
        credentials=credentials,
        leases=leases,
    )
    issuer_profiles = build_issuer_profile_diagnostics(
        credential=lease_credential,
        lease=lease,
        device=device,
        credentials=credentials,
    )
    signing_registry = build_signing_registry_diagnostics(
        credential=lease_credential,
        lease=lease,
        device=device,
        credentials=credentials,
    )

    return _to_device_safe_current_lease_payload({
        "device_id": device.id,
        "diagnostics_timestamp": now.isoformat(),
        "trust_status": getattr(device, "trust_status", DeviceTrustStatus.LEGACY_UNBOUND.value),
        "credential_status": getattr(device, "credential_status", DeviceCredentialStatus.NONE.value),
        "lease_status": getattr(device, "lease_status", DeviceLeaseStatus.NONE.value),
        "credential": _ser_device_credential(lease_credential, device=device) if lease_credential else None,
        "lease": _ser_device_lease(lease, device=device, credential=lease_credential) if lease else None,
        "reconciliation": reconciliation,
        "reconciliation_summary": reconciliation.get("summary") or build_reconciliation_summary(reconciliation=reconciliation),
        "issuer_profiles": issuer_profiles,
        "signing_registry": signing_registry,
        "endpoint_summary": build_support_diagnostics_compact_summary(
            issuer_profiles=issuer_profiles,
            signing_registry=signing_registry,
            material_history=reconciliation.get("material_history"),
            credential=lease_credential,
            lease=lease,
            now=now,
        ),
        "enforcement": "disabled",
        "mode": "read_only_placeholder",
    })



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
DEGRADED_THRESHOLD_SECONDS = 900  # 15 minutes — online > degraded > offline


def _compute_device_connectivity(last_heartbeat_at) -> str:
    """Compute device connectivity status from a single rule.
    Returns: 'online' | 'degraded' | 'offline'
    Used by ALL endpoints for consistent status display.
    """
    if last_heartbeat_at is None:
        return "offline"
    now = _utcnow()
    try:
        if isinstance(last_heartbeat_at, str):
            try:
                last_heartbeat_at = datetime.fromisoformat(last_heartbeat_at.replace("Z", "+00:00"))
            except Exception:
                return "offline"
        if hasattr(last_heartbeat_at, 'tzinfo') and last_heartbeat_at.tzinfo is None:
            last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
        diff = (now - last_heartbeat_at).total_seconds()
        if diff < ONLINE_THRESHOLD_SECONDS:
            return "online"
        elif diff < DEGRADED_THRESHOLD_SECONDS:
            return "degraded"
        else:
            return "offline"
    except Exception:
        return "offline"


def _extract_device_api_key(headers, *, query_params=None) -> tuple[str, str]:
    """Extract a device API key from preferred transports.

    Returns (api_key, source) where source is one of:
    - x-license-key
    - authorization
    - query
    """
    api_key = (headers.get("X-License-Key") or "").strip()
    if api_key:
        return api_key, "x-license-key"

    auth_header = (headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:].strip()
        if bearer:
            return bearer, "authorization"

    if query_params is not None:
        query_key = (query_params.get("key") or "").strip()
        if query_key:
            return query_key, "query"

    return "", "missing"


async def _authenticate_device(request: Request, db: AsyncSession) -> CentralDevice:
    """Authenticate a device via shared API-key extraction.
    v3.12.0: Also rejects inactive devices (not just blocked)."""
    api_key, _source = _extract_device_api_key(request.headers)
    if not api_key:
        raise HTTPException(401, "Missing device authentication")
    result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(403, "Invalid API key")
    if device.status == "blocked":
        raise HTTPException(403, "Device is blocked")
    if device.status == "inactive":
        raise HTTPException(403, "Device is deactivated — contact your administrator")
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

    return {
        "status": "ok",
        "server_time": now.isoformat(),
        "device_status": device.status,
    }


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

    # Device statuses — v3.15.2: uses _compute_device_connectivity for single-rule consistency
    device_list = []
    warnings = []
    online_count = 0
    degraded_count = 0
    offline_count = 0
    try:
        dev_result = await db.execute(
            select(CentralDevice).where(CentralDevice.id.in_(device_ids))
            .order_by(CentralDevice.last_heartbeat_at.desc().nullslast())
        )
        devices = dev_result.scalars().all()

        for d in devices:
            try:
                connectivity = _compute_device_connectivity(d.last_heartbeat_at)
                if connectivity == "online":
                    online_count += 1
                elif connectivity == "degraded":
                    degraded_count += 1
                else:
                    offline_count += 1

                dev_info = {
                    "id": d.id, "device_name": d.device_name or d.id[:8],
                    "online": connectivity == "online",
                    "connectivity": connectivity,
                    "last_heartbeat_at": _safe_raw_dt_static(d.last_heartbeat_at),
                    "last_activity_at": _safe_raw_dt_static(d.last_activity_at),
                    "last_sync_at": _safe_raw_dt_static(d.last_sync_at),
                    "reported_version": d.reported_version,
                    "last_error": d.last_error,
                    "status": d.status, "binding_status": d.binding_status,
                }
                device_list.append(_finalize_device_summary(dev_info, user))

                # Warnings
                if d.last_error:
                    warnings.append(_to_operator_safe_warning({"type": "error", "device": d.device_name or d.id[:8], "message": d.last_error}) if not _can_view_internal_device_detail(user) else {"type": "error", "device": d.device_name or d.id[:8], "message": d.last_error})
                if connectivity == "offline" and d.last_heartbeat_at:
                    try:
                        mins_ago = int((_utcnow() - _aware(d.last_heartbeat_at)).total_seconds() / 60)
                        warnings.append(_to_operator_safe_warning({"type": "offline", "device": d.device_name or d.id[:8], "message": f"Offline seit {mins_ago} Min."}))
                    except Exception:
                        warnings.append(_to_operator_safe_warning({"type": "offline", "device": d.device_name or d.id[:8], "message": "Offline"}))
                elif connectivity == "degraded":
                    warnings.append(_to_operator_safe_warning({"type": "degraded", "device": d.device_name or d.id[:8], "message": "Verbindung instabil"}))
                elif not d.last_heartbeat_at:
                    warnings.append(_to_operator_safe_warning({"type": "no_heartbeat", "device": d.device_name or d.id[:8], "message": "Noch kein Heartbeat empfangen"}))
            except Exception as e:
                logger.warning(f"[TELEMETRY-DASH] Device serialization failed: {e}")
                offline_count += 1
    except Exception as e:
        logger.warning(f"[TELEMETRY-DASH] Device query failed: {type(e).__name__}: {e}")
        try:
            await db.rollback()
        except Exception:
            pass

    # Daily stats aggregation
    today_stats = await _aggregate_daily_stats(db, device_ids, today, today)
    week_stats = await _aggregate_daily_stats(db, device_ids, week_ago, today)

    return {
        "devices_online": online_count,
        "devices_offline": offline_count,
        "devices_total": len(device_list),
        "ws_connected_count": device_ws_hub.connected_count,
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

    # v3.10.0: Push config_updated to affected devices
    try:
        affected = await _resolve_affected_devices(db, scope_type, scope_id)
        if affected:
            await device_ws_hub.push_to_devices(affected, "config_updated", {"scope_type": scope_type, "scope_id": scope_id, "version": profile.version})
    except Exception as e:
        logger.debug(f"[WS-PUSH] config_updated push error: {e}")

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

    # v3.10.0: Push config_updated to affected devices
    try:
        affected = await _resolve_affected_devices(db, scope_type, scope_id)
        if affected:
            await device_ws_hub.push_to_devices(affected, "config_updated", {"scope_type": scope_type, "scope_id": scope_id, "version": profile.version})
    except Exception as e:
        logger.debug(f"[WS-PUSH] rollback push error: {e}")

    return {
        "success": True,
        "new_version": profile.version,
        "rolled_back_to": version,
        "config_data": profile.config_data,
    }



@app.get("/api/config/effective")
async def get_effective_config(
    request: Request,
    device_id: str = None,
    location_id: str = None,
    customer_id: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute the effective (merged) config for a given device.
    Merge order: global → customer → location → device.
    Can be called by authenticated devices (X-License-Key)
    or authenticated portal users.
    """
    auth_header = request.headers.get("Authorization", "")
    has_user_auth = auth_header.startswith("Bearer ")
    has_device_auth = bool(request.headers.get("X-License-Key"))

    authed_user = None
    authed_device = None

    if has_user_auth:
        authed_user = await get_current_user(request, db)
        require_min_role(authed_user, "owner")
    elif has_device_auth:
        authed_device = await _authenticate_device(request, db)
    else:
        raise HTTPException(401, "Authentication required")

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

    if authed_device:
        if device_id and device_id != authed_device.id:
            raise HTTPException(403, "Authenticated device may only access its own effective config")
        resolved_device_id = authed_device.id
        resolved_location_id = authed_device.location_id
        loc = await db.get(CentralLocation, authed_device.location_id) if authed_device.location_id else None
        resolved_customer_id = loc.customer_id if loc else None
        if location_id and resolved_location_id and location_id != resolved_location_id:
            raise HTTPException(403, "Authenticated device may only access its own location scope")
        if customer_id and resolved_customer_id and customer_id != resolved_customer_id:
            raise HTTPException(403, "Authenticated device may only access its own customer scope")
    else:
        if device_id:
            dev = await db.get(CentralDevice, device_id)
            if not dev:
                raise HTTPException(404, "Device not found")
            if not await can_access_location(authed_user, dev.location_id, db):
                raise HTTPException(403, "No access to this device")
            resolved_device_id = dev.id
            resolved_location_id = resolved_location_id or dev.location_id

        if resolved_location_id:
            if not await can_access_location(authed_user, resolved_location_id, db):
                raise HTTPException(403, "No access to this location")
            loc = await db.get(CentralLocation, resolved_location_id)
            if loc:
                resolved_customer_id = resolved_customer_id or loc.customer_id

        if resolved_customer_id and not can_access_customer(authed_user, resolved_customer_id):
            raise HTTPException(403, "No access to this customer")

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

VALID_ACTIONS = {
    "force_sync", "restart_backend", "reload_ui",
    "unlock_board", "lock_board", "start_session", "stop_session",
}


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

    # v3.10.0: Push config_updated to affected devices
    try:
        affected = await _resolve_affected_devices(db, target_scope_type, target_scope_id or "global")
        if affected:
            await device_ws_hub.push_to_devices(affected, "config_updated", {"scope_type": target_scope_type, "version": profile.version})
    except Exception as e:
        logger.debug(f"[WS-PUSH] import push error: {e}")

    return {
        "success": True,
        "mode": mode,
        "profile": _ser_config_profile(profile),
        "source_meta": meta,
    }


def _ser_action(a):
    d = {
        "id": a.id, "device_id": a.device_id, "action_type": a.action_type,
        "status": a.status, "issued_by": a.issued_by,
        "issued_at": a.issued_at.isoformat() if a.issued_at else None,
        "acked_at": a.acked_at.isoformat() if a.acked_at else None,
        "result_message": a.result_message,
    }
    # v3.15.1: Defensive — params column may not exist in old DBs
    try:
        if getattr(a, 'params', None):
            d["params"] = a.params
    except Exception:
        pass
    return d



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
    action_params = body.get("params")
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

        action = RemoteAction(id=secrets.token_hex(18), device_id=did, action_type=action_type, params=action_params, issued_by=user.username)
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

    # v3.10.0: Push action_created to all devices that got a created action
    try:
        created_device_ids = [r["device_id"] for r in results if r["status"] == "created"]
        if created_device_ids:
            await device_ws_hub.push_to_devices(created_device_ids, "action_created", {"action_type": action_type, "bulk": True})
    except Exception as e:
        logger.debug(f"[WS-PUSH] bulk action push error: {e}")

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

    action_params = body.get("params")

    action = RemoteAction(
        device_id=device_id, action_type=action_type,
        params=action_params if action_params else None,
        issued_by=user.username,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    await _log_audit(db, "remote_action_issued", device_id=device_id, actor=user.username,
                     message=f"Action '{action_type}' issued for device {dev.device_name or device_id}")
    await db.commit()

    # v3.10.0: Push action_created to target device
    try:
        await device_ws_hub.push_to_device(device_id, "action_created", {"action_type": action_type, "action_id": action.id})
    except Exception as e:
        logger.debug(f"[WS-PUSH] action push error: {e}")

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
    await _get_device_with_scope_check(device_id, user, db)
    stmt = select(RemoteAction).where(RemoteAction.device_id == device_id)
    if status:
        stmt = stmt.where(RemoteAction.status == status)
    stmt = stmt.order_by(RemoteAction.issued_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [_finalize_remote_action(_ser_action(a), user) for a in result.scalars().all()]


@app.get("/api/remote-actions/{device_id}/pending")
async def get_pending_actions(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Device-facing endpoint: get pending actions to execute.
    Authenticated via X-License-Key header.
    """
    device = await _authenticate_device(request, db)
    if device.id != device_id:
        raise HTTPException(403, "Authenticated device may only fetch its own actions")

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
    device = await _authenticate_device(request, db)
    if device.id != device_id:
        raise HTTPException(403, "Authenticated device may only ack its own actions")

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
    """
    Get enriched device detail.
    v3.15.2: COMPLETELY hardened — NEVER returns 500.
    Global try/except catches ANY unhandled error and returns partial data.
    Fresh session for raw-SQL fallback to avoid corrupt session state.
    """
    require_min_role(user, "staff")

    try:
        return _finalize_device_detail(await _get_device_detail_inner(device_id, db, user), user)
    except HTTPException:
        raise
    except Exception as e:
        # LAST RESORT: If ANYTHING unexpected crashes, return error detail instead of 500
        logger.error(f"[DEVICE-DETAIL] UNHANDLED ERROR for {device_id}: {type(e).__name__}: {e}", exc_info=True)
        # Try raw-SQL as absolute last resort with a FRESH session
        try:
            return await _get_device_detail_raw_sql(device_id, user)
        except HTTPException:
            raise
        except Exception as e2:
            logger.error(f"[DEVICE-DETAIL] EVEN RAW-SQL FALLBACK FAILED for {device_id}: {e2}", exc_info=True)
            return _finalize_device_detail({
                "id": device_id, "device_name": "Fehler beim Laden",
                "status": "error", "binding_status": "unknown",
                "is_online": False, "last_heartbeat_at": None,
                "reported_version": None, "last_error": None,
                "last_activity_at": None, "license_id": None,
                "location": None, "customer": None,
                "health_snapshot": None, "device_logs": [],
                "recent_events": [], "daily_stats": [], "recent_actions": [],
                "_error": f"{type(e).__name__}: {str(e)[:200]}",
                "_fallback_error": f"{type(e2).__name__}: {str(e2)[:200]}",
                "_data_warning": "Daten konnten nicht geladen werden. Bitte pruefen Sie die Server-Logs.",
            }, user)


async def _get_device_detail_raw_sql(device_id: str, user: AuthUser) -> dict:
    """Load device detail entirely via raw SQL using a FRESH session.
    This avoids any ORM deserialization issues and corrupt session state."""
    from sqlalchemy import text as _t

    async with AsyncSessionLocal() as fresh_db:
        row = (await fresh_db.execute(
            _t("SELECT * FROM devices WHERE id = :did"), {"did": device_id}
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Device not found")
        dev_raw = dict(row)

        loc = None
        cust = None
        try:
            loc_id = dev_raw.get("location_id")
            if loc_id:
                loc_row = (await fresh_db.execute(
                    _t("SELECT id, name, customer_id, status FROM locations WHERE id = :lid"),
                    {"lid": loc_id}
                )).mappings().first()
                if loc_row:
                    cust_id = loc_row["customer_id"]
                    if cust_id and not can_access_customer(user, cust_id):
                        raise HTTPException(403, "No access to this device")
                    loc = {"id": loc_row["id"], "name": loc_row["name"]}
                    if cust_id:
                        cust_row = (await fresh_db.execute(
                            _t("SELECT id, name FROM customers WHERE id = :cid"),
                            {"cid": cust_id}
                        )).mappings().first()
                        if cust_row:
                            cust = {"id": cust_row["id"], "name": cust_row["name"]}
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[DEVICE-DETAIL-RAW] Location/customer lookup failed: {e}")

        # Load related data via raw SQL too
        recent_events = []
        try:
            ev_rows = (await fresh_db.execute(
                _t("SELECT event_type, timestamp, data FROM telemetry_events WHERE device_id = :did ORDER BY timestamp DESC LIMIT 10"),
                {"did": device_id}
            )).mappings().all()
            for ev in ev_rows:
                recent_events.append({
                    "event_type": ev.get("event_type"),
                    "timestamp": _safe_raw_dt_static(ev.get("timestamp")),
                    "data": _safe_json_parse(ev.get("data")),
                })
        except Exception as e:
            logger.warning(f"[DEVICE-DETAIL-RAW] Events query failed: {e}")

        daily_stats = []
        try:
            stats_rows = (await fresh_db.execute(
                _t("SELECT date, revenue_cents, sessions, games, credits_added, errors FROM device_daily_stats WHERE device_id = :did ORDER BY date DESC LIMIT 7"),
                {"did": device_id}
            )).mappings().all()
            for s in stats_rows:
                daily_stats.append({
                    "date": str(s.get("date")) if s.get("date") else None,
                    "revenue_cents": s.get("revenue_cents", 0) or 0,
                    "sessions": s.get("sessions", 0) or 0,
                    "games": s.get("games", 0) or 0,
                    "credits_added": s.get("credits_added", 0) or 0,
                    "errors": s.get("errors", 0) or 0,
                })
        except Exception as e:
            logger.warning(f"[DEVICE-DETAIL-RAW] Stats query failed: {e}")

        recent_actions = []
        try:
            act_rows = (await fresh_db.execute(
                _t("SELECT id, action_type, status, issued_by, issued_at, acked_at, result_message, params FROM remote_actions WHERE device_id = :did ORDER BY issued_at DESC LIMIT 10"),
                {"did": device_id}
            )).mappings().all()
            for a in act_rows:
                recent_actions.append({
                    "id": a.get("id"), "action_type": a.get("action_type"),
                    "status": a.get("status"), "issued_by": a.get("issued_by"),
                    "issued_at": _safe_raw_dt_static(a.get("issued_at")),
                    "acked_at": _safe_raw_dt_static(a.get("acked_at")),
                    "result_message": a.get("result_message"),
                    "params": _safe_json_parse(a.get("params")),
                })
        except Exception as e:
            logger.warning(f"[DEVICE-DETAIL-RAW] Actions query failed: {e}")

        health_snapshot = _safe_json_parse(dev_raw.get("health_snapshot"))
        device_logs = _safe_json_parse(dev_raw.get("device_logs")) or []

        hb_raw = dev_raw.get("last_heartbeat_at")
        connectivity = _compute_device_connectivity(hb_raw) if hb_raw else "offline"

        return _finalize_device_detail({
            "id": dev_raw.get("id"), "device_name": dev_raw.get("device_name"),
            "hardware_id": dev_raw.get("hardware_id"),
            "status": dev_raw.get("status", "unknown"),
            "license_id": dev_raw.get("license_id"),
            "binding_status": dev_raw.get("binding_status", "unknown"),
            "is_online": connectivity == "online",
            "connectivity": connectivity,
            "last_heartbeat_at": _safe_raw_dt_static(hb_raw),
            "reported_version": dev_raw.get("reported_version"),
            "last_error": dev_raw.get("last_error"),
            "last_activity_at": _safe_raw_dt_static(dev_raw.get("last_activity_at")),
            "location": loc, "customer": cust,
            "health_snapshot": health_snapshot, "device_logs": device_logs,
            "recent_events": recent_events, "daily_stats": daily_stats,
            "recent_actions": recent_actions,
            "_data_warning": "Teilweise Daten — ORM-Fallback auf Raw-SQL aktiv",
        }, user)


def _safe_raw_dt_static(val):
    """Safely convert any value to an ISO datetime string or None."""
    if val is None:
        return None
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).isoformat()
    except Exception:
        return None


def _safe_json_parse(val):
    """Safely parse a JSON string, returning None on failure."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        import json as _json
        return _json.loads(str(val))
    except Exception:
        return None


def _can_view_internal_device_detail(user: AuthUser) -> bool:
    return getattr(user, "role", None) in {"installer", "superadmin"}


_OPERATOR_SAFE_DEVICE_SUMMARY_INTERNAL_KEYS = {
    "api_key_preview",
    "install_id",
    "trust_reason",
    "credential_fingerprint",
    "lease_id",
    "last_error",
}


_OPERATOR_SAFE_DEVICE_DETAIL_INTERNAL_KEYS = {
    "health_snapshot",
    "device_logs",
    "lease_metadata",
}


def _apply_operator_safe_device_summary(device_summary: dict) -> dict:
    payload = dict(device_summary)
    for key in _OPERATOR_SAFE_DEVICE_SUMMARY_INTERNAL_KEYS:
        payload.pop(key, None)
    payload["detail_level"] = "operator_safe"
    return payload


def _finalize_device_summary(device_summary: dict, user: AuthUser) -> dict:
    payload = dict(device_summary)
    payload.setdefault("detail_level", "internal" if _can_view_internal_device_detail(user) else "operator_safe")
    if _can_view_internal_device_detail(user):
        return payload
    return _apply_operator_safe_device_summary(payload)


def _to_operator_safe_warning(warning: dict) -> dict:
    payload = dict(warning)
    if payload.get("type") == "error":
        payload["message"] = "Gerät meldet einen Fehler"
    return payload


def _to_operator_safe_recent_event(event: dict) -> dict:
    return {
        "event_type": event.get("event_type"),
        "timestamp": event.get("timestamp"),
        "has_data": bool(event.get("data")),
    }


def _to_operator_safe_recent_action(action: dict) -> dict:
    return {
        "id": action.get("id"),
        "device_id": action.get("device_id"),
        "action_type": action.get("action_type"),
        "status": action.get("status"),
        "issued_at": action.get("issued_at"),
        "acked_at": action.get("acked_at"),
        "has_result_message": action.get("result_message") not in (None, ""),
        "has_params": "params" in action and action.get("params") not in (None, "", {}, []),
        "detail_level": "operator_safe",
    }


def _finalize_remote_action(action: dict, user: AuthUser) -> dict:
    payload = dict(action)
    payload.setdefault("detail_level", "internal" if _can_view_internal_device_detail(user) else "operator_safe")
    if _can_view_internal_device_detail(user):
        return payload
    return _to_operator_safe_recent_action(payload)


def _to_operator_safe_recent_credential(credential: dict) -> dict:
    payload = dict(credential)
    payload.pop("fingerprint", None)
    payload["detail_level"] = "operator_safe"
    return payload



def _to_operator_safe_recent_lease(lease: dict) -> dict:
    payload = dict(lease)
    payload.pop("lease_id", None)
    payload["detail_level"] = "operator_safe"
    return payload



def _apply_operator_safe_device_detail(detail: dict) -> dict:
    payload = dict(detail)
    for key in _OPERATOR_SAFE_DEVICE_DETAIL_INTERNAL_KEYS:
        payload.pop(key, None)
    payload["recent_events"] = [_to_operator_safe_recent_event(event) for event in (detail.get("recent_events") or [])]
    payload["recent_actions"] = [_to_operator_safe_recent_action(action) for action in (detail.get("recent_actions") or [])]
    payload["recent_credentials"] = [_to_operator_safe_recent_credential(item) for item in (detail.get("recent_credentials") or [])]
    payload["recent_leases"] = [_to_operator_safe_recent_lease(item) for item in (detail.get("recent_leases") or [])]
    payload["detail_level"] = "operator_safe"
    return payload


def _finalize_device_detail(detail: dict, user: AuthUser) -> dict:
    payload = dict(detail)
    payload.setdefault("detail_level", "internal" if _can_view_internal_device_detail(user) else "operator_safe")
    if _can_view_internal_device_detail(user):
        return payload
    return _apply_operator_safe_device_detail(payload)


def _to_operator_safe_trust_verification(verification: dict | None) -> dict | None:
    if not verification:
        return verification
    return {
        "valid": verification.get("valid"),
        "errors": list(verification.get("errors") or []),
        "warnings": list(verification.get("warnings") or []),
        "timing_status": verification.get("timing_status"),
        "issuer_status": ((verification.get("issuer_inspection") or {}).get("status")),
    }


def _stamp_detail_level(block, detail_level: str):
    if not isinstance(block, dict):
        return block
    stamped = dict(block)
    stamped["detail_level"] = detail_level
    return stamped


def _to_internal_trust_credential(credential: dict | None) -> dict | None:
    if credential is None:
        return None
    payload = _stamp_detail_level(credential, "internal")
    payload["verification"] = _stamp_detail_level(payload.get("verification"), "internal")
    payload["rotation"] = _stamp_detail_level(payload.get("rotation"), "internal")
    payload["rotation_summary"] = _stamp_detail_level(payload.get("rotation_summary"), "internal")
    payload["signing_key_lineage"] = _stamp_detail_level(payload.get("signing_key_lineage"), "internal")
    payload["signing_key_lineage_summary"] = _stamp_detail_level(payload.get("signing_key_lineage_summary"), "internal")
    return payload


def _to_internal_trust_lease(lease: dict | None) -> dict | None:
    if lease is None:
        return None
    payload = _stamp_detail_level(lease, "internal")
    payload["verification"] = _stamp_detail_level(payload.get("verification"), "internal")
    payload["signing_key_lineage"] = _stamp_detail_level(payload.get("signing_key_lineage"), "internal")
    payload["signing_key_lineage_summary"] = _stamp_detail_level(payload.get("signing_key_lineage_summary"), "internal")
    return payload


def _to_operator_safe_trust_credential(credential: dict) -> dict:
    payload = dict(credential)
    payload.pop("fingerprint", None)
    payload.pop("metadata", None)
    payload["verification"] = _to_operator_safe_trust_verification(payload.get("verification"))
    payload["detail_level"] = "operator_safe"
    return payload


def _to_operator_safe_trust_lease(lease: dict) -> dict:
    payload = dict(lease)
    payload.pop("signature", None)
    payload.pop("metadata", None)
    payload.pop("signed_bundle", None)
    payload["verification"] = _to_operator_safe_trust_verification(payload.get("verification"))
    payload["detail_level"] = "operator_safe"
    return payload


def _to_operator_safe_reconciliation(reconciliation: dict | None) -> dict:
    reconciliation = reconciliation or {}
    return {
        "ok": reconciliation.get("ok"),
        "summary": reconciliation.get("summary") or build_reconciliation_summary(reconciliation=reconciliation),
        "bundle_source": reconciliation.get("bundle_source"),
        "detail_level": "operator_safe",
    }


def _to_operator_safe_signing_registry(signing_registry: dict | None) -> dict:
    signing_registry = signing_registry or {}
    credential_rotation = signing_registry.get("credential_rotation") or {}
    key_lineage = signing_registry.get("key_lineage") or {}
    return {
        "registry_size": signing_registry.get("registry_size"),
        "status_counts": dict(signing_registry.get("status_counts") or {}),
        "consistency": signing_registry.get("consistency") or {},
        "credential_rotation": {
            "credential_id": credential_rotation.get("credential_id"),
            "replacement_for_credential_id": credential_rotation.get("replacement_for_credential_id"),
            "rotation_depth": credential_rotation.get("rotation_depth"),
            "ancestor_count": len(credential_rotation.get("ancestors") or []),
            "descendant_count": len(credential_rotation.get("descendants") or []),
            "detail_level": "operator_safe",
        },
        "key_lineage": {
            name: {
                "key_id": (lineage or {}).get("key_id"),
                "present": (lineage or {}).get("present"),
                "terminal_status": (((lineage or {}).get("status_path") or [{}])[0]).get("status"),
                "rotation_depth": (lineage or {}).get("rotation_depth"),
                "parent_key_id": (lineage or {}).get("parent_key_id"),
                "detail_level": "operator_safe",
            }
            for name, lineage in key_lineage.items()
        },
        "support_summary": {
            **(signing_registry.get("support_summary") or {}),
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }


def _to_operator_safe_issuer_profiles(issuer_profiles: dict | None) -> dict:
    issuer_profiles = issuer_profiles or {}

    def _stamp_profile_block(block: dict | None) -> dict:
        return {
            **(block or {}),
            "detail_level": "operator_safe",
        }

    raw_support_summary = issuer_profiles.get("support_summary") or {}
    support_summary = {
        **raw_support_summary,
        "detail_level": "operator_safe",
    }
    transition = raw_support_summary.get("transition")
    if isinstance(transition, dict):
        support_summary["transition"] = {
            **transition,
            "detail_level": "operator_safe",
        }

    readback_summary = issuer_profiles.get("readback_summary") or {}
    effective_lineage_summary = issuer_profiles.get("effective_lineage_summary") or {}
    lineage_explanation = readback_summary.get("lineage_explanation") or {
        "effective_key_id": ((issuer_profiles.get("effective_profile") or {}).get("key_id")),
        "effective_source": support_summary.get("effective_source"),
        "lineage_state": readback_summary.get("lineage_state"),
        "lineage_note": readback_summary.get("lineage_note"),
        "transition_state": ((support_summary.get("transition") or {}).get("transition_state")),
        "rotation_depth": effective_lineage_summary.get("rotation_depth"),
        "parent_key_id": effective_lineage_summary.get("parent_key_id"),
        "terminal_status": effective_lineage_summary.get("terminal_status"),
    }
    return {
        "active_profile": _stamp_profile_block(issuer_profiles.get("active_profile")),
        "configured_profile": _stamp_profile_block(issuer_profiles.get("configured_profile")),
        "effective_profile": _stamp_profile_block(issuer_profiles.get("effective_profile")),
        "effective_lineage_summary": {
            **effective_lineage_summary,
            "detail_level": "operator_safe",
        },
        "history": [
            {
                "credential_id": item.get("credential_id"),
                "credential_status": item.get("credential_status"),
                "replacement_for_credential_id": item.get("replacement_for_credential_id"),
                "issued_at": item.get("issued_at"),
                "revoked_at": item.get("revoked_at"),
                "key_id": item.get("key_id"),
                "issuer": item.get("issuer"),
                "status": item.get("status"),
                "registry_status": item.get("registry_status"),
                "parent_key_id": item.get("parent_key_id"),
                "detail_level": "operator_safe",
            }
            for item in (issuer_profiles.get("history") or [])
        ],
        "support_summary": support_summary,
        "readback_summary": {
            **readback_summary,
            "lineage_explanation": {
                **lineage_explanation,
                "detail_level": "operator_safe",
            },
            "detail_level": "operator_safe",
        },
        "history_summary": {
            **(issuer_profiles.get("history_summary") or {}),
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }


def _finalize_endpoint_summary(endpoint_summary: dict | None, *, detail_level: str) -> dict | None:
    if endpoint_summary is None:
        return None

    def _stamp(block):
        if not isinstance(block, dict):
            return block
        stamped = dict(block)
        stamped["detail_level"] = detail_level
        for nested_name in (
            "issuer_state",
            "material_state",
            "signing_state",
            "provenance_state",
            "history_state",
            "material_alignment",
            "lineage_explanation",
            "credential_history",
            "lease_history",
            "summary",
            "material_summary",
            "source_contract_summary",
            "state_counts",
            "source_states",
            "status_counts",
        ):
            nested = stamped.get(nested_name)
            if isinstance(nested, dict):
                stamped_nested = {
                    **nested,
                    "detail_level": detail_level,
                }
                nested_status_counts = stamped_nested.get("status_counts")
                if isinstance(nested_status_counts, dict):
                    stamped_nested["status_counts"] = {
                        **nested_status_counts,
                        "detail_level": detail_level,
                    }
                if nested_name == "source_contract_summary":
                    for child_name in ("state_counts", "source_states"):
                        child = stamped_nested.get(child_name)
                        if isinstance(child, dict):
                            stamped_nested[child_name] = {
                                **child,
                                "detail_level": detail_level,
                            }
                elif nested_name == "signing_state":
                    status_counts = stamped_nested.get("status_counts")
                    if isinstance(status_counts, dict):
                        stamped_nested["status_counts"] = {
                            **status_counts,
                            "detail_level": detail_level,
                        }
                if nested_name == "provenance_state":
                    stamped_nested = {
                        key: stamped_nested.get(key)
                        for key in (
                            "overall_state",
                            "missing_expected_count",
                            "observed_extra_count",
                            "present_names",
                            "derived_names",
                            "missing_names",
                            "missing_expected_names",
                            "unexpected_names",
                            "summary",
                            "detail_level",
                        )
                        if key in stamped_nested
                    }
                stamped[nested_name] = stamped_nested
        source_contracts = stamped.get("source_contracts")
        if isinstance(source_contracts, dict):
            stamped["source_contracts"] = {
                name: {
                    **value,
                    "detail_level": detail_level,
                }
                if isinstance(value, dict)
                else value
                for name, value in source_contracts.items()
            }
        return stamped

    payload = dict(endpoint_summary)
    payload["detail_level"] = detail_level
    for block_name in (
        "issuer_state",
        "signing_state",
        "material_timestamps",
        "support_notes",
        "contract_summary",
        "history_state",
        "material_history",
        "material_readback_summary",
    ):
        payload[block_name] = _stamp(payload.get(block_name))
    return payload


def _build_compact_reconciliation_readback_summary(payload: dict) -> dict:
    raw_summary = payload.get("reconciliation_summary") or build_reconciliation_summary(
        reconciliation={
            "summary": payload.get("reconciliation_summary") or payload.get("reconciliation") or {},
            "issuer_profiles": payload.get("issuer_profiles") or {},
            "signing_registry": payload.get("signing_registry") or {},
        }
    )

    issuer_profiles = dict(raw_summary.get("issuer_profiles") or {})
    lineage_explanation = issuer_profiles.get("lineage_explanation")
    if isinstance(lineage_explanation, dict):
        issuer_profiles["lineage_explanation"] = {
            **lineage_explanation,
            "detail_level": "operator_safe",
        }
    transition = issuer_profiles.get("transition")
    if isinstance(transition, dict):
        issuer_profiles["transition"] = {
            **transition,
            "detail_level": "operator_safe",
        }
    readback_summary = issuer_profiles.get("readback_summary")
    if isinstance(readback_summary, dict):
        stamped_readback_summary = {
            **readback_summary,
            "detail_level": "operator_safe",
        }
        nested_lineage_explanation = stamped_readback_summary.get("lineage_explanation")
        if isinstance(nested_lineage_explanation, dict):
            stamped_readback_summary["lineage_explanation"] = {
                **nested_lineage_explanation,
                "detail_level": "operator_safe",
            }
        issuer_profiles["readback_summary"] = stamped_readback_summary
    history_summary = issuer_profiles.get("history_summary")
    if isinstance(history_summary, dict):
        stamped_history_summary = {
            **history_summary,
            "detail_level": "operator_safe",
        }
        if isinstance(stamped_history_summary.get("status_counts"), dict):
            stamped_history_summary["status_counts"] = {
                **(stamped_history_summary.get("status_counts") or {}),
                "detail_level": "operator_safe",
            }
        issuer_profiles["history_summary"] = stamped_history_summary
    source_contracts = issuer_profiles.get("source_contracts")
    if isinstance(source_contracts, dict):
        issuer_profiles["source_contracts"] = {
            name: {
                **value,
                "detail_level": "operator_safe",
            }
            if isinstance(value, dict)
            else value
            for name, value in source_contracts.items()
        }
    source_contract_summary = issuer_profiles.get("source_contract_summary")
    if isinstance(source_contract_summary, dict):
        stamped_source_contract_summary = {
            **source_contract_summary,
            "detail_level": "operator_safe",
        }
        for nested_name in ("state_counts", "source_states"):
            nested = stamped_source_contract_summary.get(nested_name)
            if isinstance(nested, dict):
                stamped_source_contract_summary[nested_name] = {
                    **nested,
                    "detail_level": "operator_safe",
                }
        issuer_profiles["source_contract_summary"] = stamped_source_contract_summary

    material_readback_summary = dict(raw_summary.get("material_readback_summary") or {})
    for nested_name in ("summary", "credential_history", "lease_history"):
        nested = material_readback_summary.get(nested_name)
        if isinstance(nested, dict):
            material_readback_summary[nested_name] = {
                **nested,
                "detail_level": "operator_safe",
            }

    return {
        "ok": raw_summary.get("ok"),
        "status_counts": {
            **(raw_summary.get("status_counts") or {}),
            "detail_level": "operator_safe",
        },
        "bundle_source": (payload.get("reconciliation") or {}).get("bundle_source") or raw_summary.get("bundle_source"),
        "timing": {
            **(raw_summary.get("timing_status") or raw_summary.get("timing") or {}),
            "detail_level": "operator_safe",
        },
        "support_summary": {
            **(raw_summary.get("support_summary") or {}),
            "detail_level": "operator_safe",
        },
        "issuer_profiles": {
            **issuer_profiles,
            "detail_level": "operator_safe",
        },
        "material_readback_summary": {
            **material_readback_summary,
            "detail_level": "operator_safe",
        },
        "detail_level": "operator_safe",
    }


def _to_internal_reconciliation(reconciliation: dict | None) -> dict | None:
    if reconciliation is None:
        return None
    payload = _stamp_detail_level(reconciliation, "internal")
    payload["summary"] = _stamp_detail_level(payload.get("summary"), "internal")
    return payload


def _to_internal_signing_registry(signing_registry: dict | None) -> dict | None:
    if signing_registry is None:
        return None
    payload = _stamp_detail_level(signing_registry, "internal")
    payload["status_counts"] = _stamp_detail_level(payload.get("status_counts"), "internal")
    payload["support_summary"] = _stamp_detail_level(payload.get("support_summary"), "internal")
    payload["consistency"] = _stamp_detail_level(payload.get("consistency"), "internal")
    payload["credential_rotation"] = _stamp_detail_level(payload.get("credential_rotation"), "internal")
    key_lineage = payload.get("key_lineage")
    if isinstance(key_lineage, dict):
        payload["key_lineage"] = {
            name: _stamp_detail_level(lineage, "internal")
            for name, lineage in key_lineage.items()
        }
    return payload


def _to_internal_issuer_profiles(issuer_profiles: dict | None) -> dict | None:
    if issuer_profiles is None:
        return None
    payload = _stamp_detail_level(issuer_profiles, "internal")
    for name in (
        "active_profile",
        "configured_profile",
        "effective_profile",
        "effective_lineage_summary",
        "support_summary",
        "readback_summary",
        "history_summary",
    ):
        value = payload.get(name)
        if name == "support_summary" and not isinstance(value, dict):
            value = {}
        payload[name] = _stamp_detail_level(value, "internal")
    history = payload.get("history")
    if isinstance(history, list):
        payload["history"] = [_stamp_detail_level(item, "internal") for item in history]
    transition = (payload.get("support_summary") or {}).get("transition")
    if isinstance(transition, dict):
        payload["support_summary"] = {
            **payload.get("support_summary"),
            "transition": _stamp_detail_level(transition, "internal"),
        }
    lineage_explanation = (payload.get("readback_summary") or {}).get("lineage_explanation")
    if isinstance(lineage_explanation, dict):
        payload["readback_summary"] = {
            **payload.get("readback_summary"),
            "lineage_explanation": _stamp_detail_level(lineage_explanation, "internal"),
        }
    source_contracts = payload.get("source_contracts")
    if isinstance(source_contracts, dict):
        payload["source_contracts"] = {
            name: _stamp_detail_level(value, "internal")
            for name, value in source_contracts.items()
        }
    source_contract_summary = payload.get("source_contract_summary")
    if isinstance(source_contract_summary, dict):
        payload["source_contract_summary"] = {
            **_stamp_detail_level(source_contract_summary, "internal"),
            "state_counts": _stamp_detail_level(source_contract_summary.get("state_counts"), "internal"),
            "source_states": _stamp_detail_level(source_contract_summary.get("source_states"), "internal"),
        }
    return payload


def _to_internal_material_readback_summary(material_readback_summary: dict | None) -> dict | None:
    if material_readback_summary is None:
        return None
    payload = _stamp_detail_level(material_readback_summary, "internal")
    for name in ("summary", "credential_history", "lease_history"):
        payload[name] = _stamp_detail_level(payload.get(name), "internal")
        nested = payload.get(name)
        if isinstance(nested, dict) and isinstance(nested.get("status_counts"), dict):
            payload[name] = {
                **nested,
                "status_counts": _stamp_detail_level(nested.get("status_counts"), "internal"),
            }
    return payload


def _to_internal_reconciliation_summary(reconciliation_summary: dict | None) -> dict | None:
    if reconciliation_summary is None:
        return None
    payload = _stamp_detail_level(reconciliation_summary, "internal")
    payload["status_counts"] = _stamp_detail_level(
        payload.get("status_counts") or payload.get("severity_counts"),
        "internal",
    )
    payload["severity_counts"] = _stamp_detail_level(
        payload.get("severity_counts") or payload.get("status_counts"),
        "internal",
    )
    payload["source_counts"] = _stamp_detail_level(payload.get("source_counts"), "internal")
    payload["timing"] = _stamp_detail_level(payload.get("timing") or payload.get("timing_status"), "internal")
    payload["timing_status"] = _stamp_detail_level(payload.get("timing_status") or payload.get("timing"), "internal")
    payload["support_summary"] = _stamp_detail_level(payload.get("support_summary"), "internal")
    payload["issuer_profiles"] = _to_internal_issuer_profiles(payload.get("issuer_profiles"))
    payload["material_readback_summary"] = _to_internal_material_readback_summary(payload.get("material_readback_summary"))
    return payload


def _to_device_safe_current_lease_payload(payload: dict | None) -> dict:
    payload = dict(payload or {})
    payload["credential"] = _to_operator_safe_trust_credential(payload.get("credential") or {}) if payload.get("credential") else None
    payload["lease"] = _to_operator_safe_trust_lease(payload.get("lease") or {}) if payload.get("lease") else None
    payload["reconciliation"] = _to_operator_safe_reconciliation(payload.get("reconciliation"))
    payload["reconciliation_summary"] = _build_compact_reconciliation_readback_summary(payload)
    payload["issuer_profiles"] = _to_operator_safe_issuer_profiles(payload.get("issuer_profiles"))
    payload["signing_registry"] = _to_operator_safe_signing_registry(payload.get("signing_registry"))
    payload["endpoint_summary"] = _finalize_endpoint_summary(payload.get("endpoint_summary"), detail_level="operator_safe")
    payload["detail_level"] = "device_safe"
    return payload


def _finalize_device_trust_detail(detail: dict, user: AuthUser) -> dict:
    payload = dict(detail)
    payload.setdefault("detail_level", "internal" if _can_view_internal_device_detail(user) else "operator_safe")
    payload["device"] = _finalize_device_summary(payload.get("device") or {}, user)
    if _can_view_internal_device_detail(user):
        payload["credentials"] = [_to_internal_trust_credential(item) for item in (payload.get("credentials") or [])]
        payload["leases"] = [_to_internal_trust_lease(item) for item in (payload.get("leases") or [])]
        if payload.get("credential"):
            payload["credential"] = _to_internal_trust_credential(payload.get("credential"))
        if payload.get("lease"):
            payload["lease"] = _to_internal_trust_lease(payload.get("lease"))
        payload["reconciliation"] = _to_internal_reconciliation(payload.get("reconciliation"))
        payload["reconciliation_summary"] = _to_internal_reconciliation_summary(payload.get("reconciliation_summary"))
        payload["issuer_profiles"] = _to_internal_issuer_profiles(payload.get("issuer_profiles"))
        payload["signing_registry"] = _to_internal_signing_registry(payload.get("signing_registry"))
        payload["endpoint_summary"] = _finalize_endpoint_summary(payload.get("endpoint_summary"), detail_level="internal")
        return payload
    payload["credentials"] = [_to_operator_safe_trust_credential(item) for item in (payload.get("credentials") or [])]
    payload["leases"] = [_to_operator_safe_trust_lease(item) for item in (payload.get("leases") or [])]
    if payload.get("credential"):
        payload["credential"] = _to_operator_safe_trust_credential(payload.get("credential") or {})
    if payload.get("lease"):
        payload["lease"] = _to_operator_safe_trust_lease(payload.get("lease") or {})
    payload["reconciliation"] = _to_operator_safe_reconciliation(payload.get("reconciliation"))
    if (detail or {}).get("reconciliation") is None and (detail or {}).get("issuer_profiles") is None and (detail or {}).get("signing_registry") is None and (detail or {}).get("reconciliation_summary") is not None:
        payload["reconciliation_summary"] = payload.get("reconciliation_summary")
    else:
        payload["reconciliation_summary"] = _build_compact_reconciliation_readback_summary(payload)
    payload["issuer_profiles"] = _to_operator_safe_issuer_profiles(payload.get("issuer_profiles"))
    payload["signing_registry"] = _to_operator_safe_signing_registry(payload.get("signing_registry"))
    if isinstance((payload.get("signing_registry") or {}).get("status_counts"), dict):
        payload["signing_registry"] = {
            **payload["signing_registry"],
            "status_counts": _stamp_detail_level((payload["signing_registry"] or {}).get("status_counts"), "operator_safe"),
        }
    payload["endpoint_summary"] = _finalize_endpoint_summary(payload.get("endpoint_summary"), detail_level="operator_safe")
    payload["detail_level"] = "operator_safe"
    return payload


async def _get_device_detail_inner(device_id: str, db: AsyncSession, user: AuthUser) -> dict:
    """Inner implementation of device detail — may raise exceptions."""

    # ── Load device (defensive: handle corrupt datetime values in DB) ──
    dev = None
    try:
        dev = await db.get(CentralDevice, device_id)
    except Exception as e:
        # ORM failed — rollback session state, then use fresh-session raw SQL
        logger.warning(f"[DEVICE-DETAIL] ORM load failed for {device_id}: {type(e).__name__}: {e} — raw SQL fallback")
        try:
            await db.rollback()
        except Exception:
            pass
        return await _get_device_detail_raw_sql(device_id, user)

    if not dev:
        raise HTTPException(404, "Device not found")

    # ── Access check (defensive: location_id could be null in legacy data) ──
    loc = None
    cust = None
    try:
        if dev.location_id:
            loc = await db.get(CentralLocation, dev.location_id)
            if loc and not can_access_customer(user, loc.customer_id):
                raise HTTPException(403, "No access to this device")
            if loc and loc.customer_id:
                cust = await db.get(CentralCustomer, loc.customer_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[DEVICE-DETAIL] Access/location check failed for {device_id}: {e}")

    # ── Online status — v3.15.2: single rule via _compute_device_connectivity ──
    connectivity = _compute_device_connectivity(dev.last_heartbeat_at)
    is_online = connectivity == "online"

    # ── Safe datetime serialization helper ──
    def _safe_dt(val):
        if val is None:
            return None
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        return str(val)

    # ── Recent telemetry events (defensive) ──
    recent_events = []
    try:
        events_q = await db.execute(
            select(TelemetryEvent)
            .where(TelemetryEvent.device_id == device_id)
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(10)
        )
        for e in events_q.scalars().all():
            ts = None
            try:
                ts = e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp) if e.timestamp else None
            except Exception:
                ts = str(e.timestamp) if e.timestamp else None
            recent_events.append({
                "event_type": e.event_type,
                "timestamp": ts,
                "data": e.data if isinstance(e.data, (dict, list, type(None))) else str(e.data),
            })
    except Exception as e:
        logger.warning(f"[DEVICE-DETAIL] Events query failed for {device_id}: {e}")

    # ── Daily stats (defensive) ──
    daily_stats = []
    try:
        stats_q = await db.execute(
            select(DeviceDailyStats)
            .where(DeviceDailyStats.device_id == device_id)
            .order_by(DeviceDailyStats.date.desc())
            .limit(7)
        )
        for s in stats_q.scalars().all():
            daily_stats.append({
                "date": str(s.date) if s.date else None,
                "revenue_cents": s.revenue_cents or 0,
                "sessions": s.sessions or 0,
                "games": s.games or 0,
                "credits_added": s.credits_added or 0,
                "errors": s.errors or 0,
            })
    except Exception as e:
        logger.warning(f"[DEVICE-DETAIL] Stats query failed for {device_id}: {e}")

    # ── Recent device trust scaffolding records (defensive / additive only) ──
    recent_credentials = []
    try:
        credentials_q = await db.execute(
            select(DeviceCredential)
            .where(DeviceCredential.device_id == device_id)
            .order_by(DeviceCredential.created_at.desc())
            .limit(5)
        )
        for c in credentials_q.scalars().all():
            recent_credentials.append({
                "id": c.id,
                "status": c.status,
                "credential_kind": c.credential_kind,
                "fingerprint": c.fingerprint,
                "issued_at": _safe_dt(c.issued_at),
                "expires_at": _safe_dt(c.expires_at),
                "revoked_at": _safe_dt(c.revoked_at),
            })
    except Exception as e:
        logger.warning(f"[DEVICE-DETAIL] Credential query failed for {device_id}: {e}")

    recent_leases = []
    try:
        leases_q = await db.execute(
            select(DeviceLease)
            .where(DeviceLease.device_id == device_id)
            .order_by(DeviceLease.created_at.desc())
            .limit(5)
        )
        for l in leases_q.scalars().all():
            recent_leases.append({
                "id": l.id,
                "lease_id": l.lease_id,
                "status": l.status,
                "issued_at": _safe_dt(l.issued_at),
                "expires_at": _safe_dt(l.expires_at),
                "grace_until": _safe_dt(l.grace_until),
                "revoked_at": _safe_dt(l.revoked_at),
            })
    except Exception as e:
        logger.warning(f"[DEVICE-DETAIL] Lease query failed for {device_id}: {e}")

    # ── Recent remote actions (defensive: params column may not exist) ──
    recent_actions = []
    try:
        actions_q = await db.execute(
            select(RemoteAction)
            .where(RemoteAction.device_id == device_id)
            .order_by(RemoteAction.issued_at.desc())
            .limit(10)
        )
        for a in actions_q.scalars().all():
            try:
                recent_actions.append(_ser_action(a))
            except Exception as ae:
                logger.warning(f"[DEVICE-DETAIL] Action serialization failed: {ae}")
                recent_actions.append({
                    "id": str(getattr(a, 'id', '?')),
                    "action_type": str(getattr(a, 'action_type', '?')),
                    "status": str(getattr(a, 'status', '?')),
                    "issued_by": str(getattr(a, 'issued_by', '?')),
                    "issued_at": None, "acked_at": None, "result_message": None,
                })
    except Exception as e:
        logger.warning(f"[DEVICE-DETAIL] Actions query failed for {device_id}: {e}")

    # ── Health snapshot + logs (already defensive) ──
    health_snapshot = None
    stored_logs = []
    try:
        if dev.health_snapshot:
            import json as _json
            health_snapshot = _json.loads(dev.health_snapshot)
    except Exception:
        pass
    try:
        if dev.device_logs:
            import json as _json
            stored_logs = _json.loads(dev.device_logs)
    except Exception:
        pass

    return {
        "id": dev.id,
        "device_name": dev.device_name,
        "hardware_id": getattr(dev, 'hardware_id', None),
        "status": dev.status,
        "license_id": dev.license_id,
        "binding_status": getattr(dev, 'binding_status', None),
        "trust_status": getattr(dev, 'trust_status', DeviceTrustStatus.LEGACY_UNBOUND.value),
        "trust_reason": getattr(dev, 'trust_reason', None),
        "trust_last_changed_at": _safe_dt(getattr(dev, 'trust_last_changed_at', None)),
        "replacement_of_device_id": getattr(dev, 'replacement_of_device_id', None),
        "credential_status": getattr(dev, 'credential_status', DeviceCredentialStatus.NONE.value),
        "credential_fingerprint": getattr(dev, 'credential_fingerprint', None),
        "credential_issued_at": _safe_dt(getattr(dev, 'credential_issued_at', None)),
        "credential_expires_at": _safe_dt(getattr(dev, 'credential_expires_at', None)),
        "lease_status": getattr(dev, 'lease_status', DeviceLeaseStatus.NONE.value),
        "lease_id": getattr(dev, 'lease_id', None),
        "lease_issued_at": _safe_dt(getattr(dev, 'lease_issued_at', None)),
        "lease_expires_at": _safe_dt(getattr(dev, 'lease_expires_at', None)),
        "lease_grace_until": _safe_dt(getattr(dev, 'lease_grace_until', None)),
        "lease_metadata": _safe_json_parse(getattr(dev, 'lease_metadata', None)),
        "is_online": is_online,
        "connectivity": connectivity,
        "last_heartbeat_at": _safe_dt(dev.last_heartbeat_at),
        "reported_version": dev.reported_version,
        "last_error": dev.last_error,
        "last_activity_at": _safe_dt(dev.last_activity_at),
        "location": {"id": loc.id, "name": loc.name} if loc else None,
        "customer": {"id": cust.id, "name": cust.name} if cust else None,
        "health_snapshot": health_snapshot,
        "device_logs": stored_logs,
        "recent_events": recent_events,
        "daily_stats": daily_stats,
        "recent_credentials": recent_credentials,
        "recent_leases": recent_leases,
        "recent_actions": recent_actions,
    }


# ═══════════════════════════════════════════════════════════════
# v3.10.0: WEBSOCKET PUSH SYSTEM
# ═══════════════════════════════════════════════════════════════


@app.websocket("/ws/devices")
async def ws_device_endpoint(ws: WebSocket):
    """
    WebSocket endpoint for device push connections.

    Preferred auth transports:
    - X-License-Key header
    - Authorization: Bearer <device_api_key>

    Compatibility fallback:
    - ?key=<device_api_key> query param
    """
    api_key, api_key_source = _extract_device_api_key(ws.headers, query_params=ws.query_params)
    if not api_key:
        await ws.close(code=4001, reason="Missing device authentication")
        return

    # Resolve device by API key
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(CentralDevice).where(CentralDevice.api_key == api_key))
            device = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"[WS] Auth DB error: {e}")
        await ws.close(code=4003, reason="Server error")
        return

    if not device:
        await ws.close(code=4002, reason="Invalid API key")
        return
    if device.status == "blocked":
        await ws.close(code=4003, reason="Device is blocked")
        return
    if device.status == "inactive":
        await ws.close(code=4003, reason="Device is deactivated")
        return

    if api_key_source == "query":
        if _WS_QUERY_AUTH_MODE == "deny":
            logger.warning("[WS] Rejected deprecated query-parameter auth for device %s", device.id)
            await ws.close(code=4001, reason="Query-parameter auth disabled; use X-License-Key or Authorization header")
            return
        logger.warning("[WS] Device %s authenticated via query parameter; prefer X-License-Key or Authorization header", device.id)

    device_id = device.id
    await ws.accept()
    await device_ws_hub.register(device_id, ws)

    try:
        # Send welcome event
        await ws.send_json({"event": "connected", "device_id": device_id})

        # Keep-alive loop: listen for client messages
        while True:
            try:
                msg = await ws.receive_json()
            except Exception:
                break
            # Handle ping/pong
            if isinstance(msg, dict) and msg.get("type") == "ping":
                try:
                    await ws.send_json({"event": "pong"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[WS] Device {device_id} connection error: {e}")
    finally:
        await device_ws_hub.unregister(device_id)


_OPERATOR_SAFE_WS_DEVICE_STATUS_INTERNAL_KEYS = {
    "connected_at",
    "last_event_at",
    "events_sent",
}


def _apply_operator_safe_ws_device_status(device_status: dict) -> dict:
    payload = dict(device_status)
    for key in _OPERATOR_SAFE_WS_DEVICE_STATUS_INTERNAL_KEYS:
        payload.pop(key, None)
    payload["detail_level"] = "operator_safe"
    return payload



def _finalize_ws_device_status(device_status: dict, user: AuthUser) -> dict:
    payload = dict(device_status)
    payload.setdefault("detail_level", "internal" if _can_view_internal_device_detail(user) else "operator_safe")
    if _can_view_internal_device_detail(user):
        return payload
    return _apply_operator_safe_ws_device_status(payload)


@app.get("/api/ws/status")
async def ws_status(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get WebSocket hub status — scoped to the caller's visible devices."""
    require_min_role(user, "owner")
    hub_status = device_ws_hub.status()
    scoped_device_ids = set(await _resolve_scoped_device_ids(user, db))
    scoped_raw_devices = {
        did: status
        for did, status in (hub_status.get("devices") or {}).items()
        if did in scoped_device_ids
    }
    devices = {
        did: _finalize_ws_device_status(status, user)
        for did, status in scoped_raw_devices.items()
    }
    return {
        "connected_devices": len(devices),
        "total_connections": len(devices),
        "total_events_pushed": sum(int((status or {}).get("events_sent") or 0) for status in scoped_raw_devices.values()),
        "devices": devices,
        "detail_level": "internal" if _can_view_internal_device_detail(user) else "operator_safe",
    }


@app.get("/api/ws/device/{device_id}")
async def ws_device_status(device_id: str, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get WS connection status for a specific device."""
    require_min_role(user, "staff")
    await _get_device_with_scope_check(device_id, user, db)
    return _finalize_ws_device_status(device_ws_hub.device_ws_status(device_id), user)


# ── Data Hygiene / Cleanup — v3.13.0 ──

@app.post("/api/admin/cleanup")
async def data_cleanup(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Clean up stale/inconsistent data. Superadmin only."""
    require_min_role(user, "superadmin")
    results = {}

    # 1. Remove expired registration tokens
    expired_tokens = await db.execute(
        select(RegistrationToken).where(
            RegistrationToken.status == "pending",
            RegistrationToken.expires_at < datetime.now(timezone.utc),
        )
    )
    expired = expired_tokens.scalars().all()
    for t in expired:
        t.status = "expired"
    results["expired_tokens"] = len(expired)

    # 2. Fix devices with mismatched license bindings
    orphaned = await db.execute(
        select(CentralDevice).where(
            CentralDevice.license_id.isnot(None),
            CentralDevice.binding_status != "bound",
        )
    )
    for dev in orphaned.scalars().all():
        dev.binding_status = "bound"
    results["fixed_bindings"] = len(orphaned.scalars().all()) if hasattr(orphaned, 'scalars') else 0

    # 3. Clean up stale heartbeat data (mark devices offline if no heartbeat > 5 min)
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    stale_devs = await db.execute(
        select(CentralDevice).where(
            CentralDevice.status == "active",
            CentralDevice.last_heartbeat_at < stale_cutoff,
        )
    )
    stale_count = 0
    for dev in stale_devs.scalars().all():
        # Don't deactivate, just mark as offline in the online_status
        stale_count += 1
    results["stale_heartbeats"] = stale_count

    await db.commit()
    return {"cleaned": True, "results": results}



# ── Helper: Resolve affected device IDs for a config scope change ──

async def _resolve_affected_devices(db: AsyncSession, scope_type: str, scope_id: str) -> list[str]:
    """Given a config scope, return the list of device IDs that are affected."""
    if scope_type == "device":
        return [scope_id] if scope_id else []

    if scope_type == "location":
        result = await db.execute(
            select(CentralDevice.id).where(CentralDevice.location_id == scope_id, CentralDevice.status == "active")
        )
        return [r[0] for r in result.all()]

    if scope_type == "customer":
        loc_result = await db.execute(
            select(CentralLocation.id).where(CentralLocation.customer_id == scope_id)
        )
        location_ids = [r[0] for r in loc_result.all()]
        if not location_ids:
            return []
        dev_result = await db.execute(
            select(CentralDevice.id).where(CentralDevice.location_id.in_(location_ids), CentralDevice.status == "active")
        )
        return [r[0] for r in dev_result.all()]

    if scope_type == "global":
        result = await db.execute(
            select(CentralDevice.id).where(CentralDevice.status == "active")
        )
        return [r[0] for r in result.all()]

    return []
