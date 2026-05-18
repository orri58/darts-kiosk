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
import math
import os
import secrets
from collections import defaultdict
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
    build_advisory_device_posture,
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
from central_server.remote_action_policy import get_remote_action_policy
from central_server.routes.config_profiles import build_config_profiles_router
from central_server.routes.admin_crud import build_admin_crud_router
from central_server.routes.device_details import build_device_details_router
from central_server.routes.device_remote_actions import build_device_remote_actions_router
from central_server.routes.device_trust import build_device_trust_router
from central_server.routes.effective_config import build_effective_config_router
from central_server.routes.licensing_tokens import build_licensing_tokens_router
from central_server.routes.remote_actions import build_remote_actions_router
from central_server.services.licensing_tokens import register_device_with_token_payload
from central_server.routes.ws_devices import build_device_ws_router
from central_server.routes.ws_status import build_ws_status_router
from central_server.services.config_profiles import deep_merge as _deep_merge
from central_server.services.device_auth import (
    authenticate_device as _authenticate_device,
    extract_device_api_key as _extract_device_api_key,
)
from central_server.services.device_details import (
    get_device_detail_inner as _get_device_detail_inner_service,
    get_device_detail_raw_sql as _get_device_detail_raw_sql_service,
    safe_raw_dt as _safe_raw_dt_static,
)
from central_server.services.device_trust_details import (
    _build_compact_reconciliation_readback_summary,
    can_view_internal_device_detail as _can_view_internal_device_detail,
    finalize_device_detail as _finalize_device_detail,
    finalize_device_summary as _finalize_device_summary,
    finalize_device_trust_detail as _finalize_device_trust_detail,
    finalize_endpoint_summary as _finalize_endpoint_summary,
    serialize_device_credential as _ser_device_credential,
    serialize_device_credential_summary as _ser_device_credential_summary,
    serialize_device_lease as _ser_device_lease,
    serialize_device_lease_summary as _ser_device_lease_summary,
    stamp_detail_level as _stamp_detail_level,
    to_device_safe_current_lease_payload as _to_device_safe_current_lease_payload,
    to_operator_safe_issuer_profiles as _to_operator_safe_issuer_profiles,
    to_operator_safe_recent_action as _to_operator_safe_recent_action,
    to_operator_safe_signing_registry as _to_operator_safe_signing_registry,
    to_operator_safe_warning as _to_operator_safe_warning,
)
from central_server.services.licensing import (
    build_license_commercial_readiness as _build_license_commercial_readiness,
    build_license_portfolio_summary as _build_license_portfolio_summary,
    compute_license_status as _compute_status,
    refine_license_detail_suggested_actions as _refine_license_detail_suggested_actions,
    serialize_registration_token_summary as _ser_reg_token_summary,
    summarize_license_token_state as _summarize_license_token_state,
    token_status as _token_status,
)
from central_server.services.remote_actions import (
    derive_remote_action_outcome as _derive_remote_action_outcome,
    normalize_remote_action_request_state as _normalize_remote_action_request_state,
    remote_action_lifecycle_details as _remote_action_lifecycle_details,
    remote_action_problem_scope_payload as _remote_action_problem_scope_payload,
    remote_action_queue_metrics as _remote_action_queue_metrics,
    remote_action_scope_snapshot as _remote_action_scope_snapshot,
    remote_action_summary_payload as _remote_action_summary_payload,
    remote_action_triage_priority as _remote_action_triage_priority,
)
from central_server.services.ws_status import (
    apply_operator_safe_ws_device_status as _apply_operator_safe_ws_device_status,
    finalize_ws_device_status as _finalize_ws_device_status,
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

    # v3.15.x: Add approval/audit maturity columns to remote_actions
    _remote_action_cols = [
        ("request_state", "VARCHAR(24) DEFAULT 'queued'"),
        ("approval_state", "VARCHAR(24) DEFAULT 'not_required'"),
        ("outcome_code", "VARCHAR(32)"),
        ("outcome_detail", "VARCHAR(64)"),
        ("request_note", "TEXT"),
        ("requested_at", "DATETIME"),
        ("reviewed_at", "DATETIME"),
        ("reviewed_by", "VARCHAR(100)"),
        ("review_note", "TEXT"),
        ("delivered_at", "DATETIME"),
        ("finalized_at", "DATETIME"),
        ("finalized_by", "VARCHAR(100)"),
    ]
    for _col, _typ in _remote_action_cols:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(_text(f"SELECT {_col} FROM remote_actions LIMIT 1"))
        except Exception:
            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(_text(f"ALTER TABLE remote_actions ADD COLUMN {_col} {_typ}"))
                    await db.commit()
                    logger.info(f"[MIGRATE] Added {_col} to remote_actions")
            except Exception as e:
                logger.warning(f"[MIGRATE] remote_actions.{_col}: {e}")

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
    users = result.scalars().all()
    payload = []
    now = _utcnow()
    for target in users:
        item = _ser_user(target)
        scoped_customer_ids = list(target.allowed_customer_ids or [])
        device_stmt = select(CentralDevice)
        target_is_superadmin = getattr(target, "role", None) == "superadmin"
        if not target_is_superadmin:
            if scoped_customer_ids:
                device_stmt = device_stmt.join(CentralLocation, CentralDevice.location_id == CentralLocation.id).where(
                    CentralLocation.customer_id.in_(scoped_customer_ids)
                )
            else:
                device_stmt = device_stmt.where(False)
        device_result = await db.execute(device_stmt)
        scoped_devices = device_result.scalars().all()
        posture_map = await _build_device_advisory_posture_map(db, scoped_devices, now=now)
        item["scope_summary"] = {
            "customer_count": len(scoped_customer_ids) if not target_is_superadmin else None,
            "has_global_scope": bool(target_is_superadmin),
            "fleet_advisory_summary": _summarize_posture_collection(list(posture_map.values())),
            "detail_level": "operator_safe",
        }
        payload.append(item)
    return payload


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
    devices = result.scalars().all()
    posture_map = await _build_device_advisory_posture_map(db, devices)
    return [{
        "id": d.id,
        "device_name": d.device_name,
        "location_id": d.location_id,
        "status": d.status,
        "advisory_posture": _compact_advisory_posture(posture_map.get(d.id)),
    } for d in devices]


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

    license_stmt = select(CentralLicense).order_by(CentralLicense.created_at.desc())
    for f in lic_filter:
        license_stmt = license_stmt.where(f)
    scoped_licenses = (await db.execute(license_stmt)).scalars().all()
    scoped_license_ids = [lic.id for lic in scoped_licenses]
    portfolio_posture_summary_by_license = {}
    if scoped_license_ids:
        scoped_license_devices = (await db.execute(select(CentralDevice).where(CentralDevice.license_id.in_(scoped_license_ids)))).scalars().all()
        scoped_device_postures = await _build_device_advisory_posture_map(db, scoped_license_devices)
        scoped_devices_by_license: dict[str, list[dict]] = defaultdict(list)
        for device in scoped_license_devices:
            scoped_devices_by_license[device.license_id].append(scoped_device_postures.get(device.id))
        for lic_id, postures in scoped_devices_by_license.items():
            portfolio_posture_summary_by_license[lic_id] = _summarize_posture_collection(postures)
    license_portfolio_summary = _build_license_portfolio_summary(scoped_licenses, portfolio_posture_summary_by_license, _utcnow())

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
        dashboard_devices = dev_result.scalars().all()
        dashboard_postures = await _build_device_advisory_posture_map(db, dashboard_devices)
        for d in dashboard_devices:
            try:
                connectivity = _compute_device_connectivity(d.last_heartbeat_at)
                recent_devices.append(_finalize_device_summary({
                    "id": d.id, "device_name": d.device_name, "status": d.status,
                    "online": connectivity == "online",
                    "connectivity": connectivity,
                    "binding_status": d.binding_status,
                    "advisory_posture": _compact_advisory_posture(dashboard_postures.get(d.id), detail_level="internal" if _can_view_internal_device_detail(user) else "operator_safe"),
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

    remote_action_stmt = select(RemoteAction).join(CentralDevice, RemoteAction.device_id == CentralDevice.id)
    if location_id:
        remote_action_stmt = remote_action_stmt.where(CentralDevice.location_id == location_id)
    elif customer_id:
        remote_action_stmt = remote_action_stmt.join(CentralLocation, CentralDevice.location_id == CentralLocation.id).where(CentralLocation.customer_id == customer_id)
    elif not user.is_superadmin:
        allowed = user.allowed_customer_ids or []
        remote_action_stmt = remote_action_stmt.join(CentralLocation, CentralDevice.location_id == CentralLocation.id).where(CentralLocation.customer_id.in_(allowed) if allowed else False)
    remote_action_stmt = remote_action_stmt.order_by(RemoteAction.issued_at.desc()).limit(250)
    remote_actions = (await db.execute(remote_action_stmt)).scalars().all()
    remote_action_metrics = _remote_action_queue_metrics(remote_actions)

    return {
        "customers": customers, "locations": locations, "devices": devices,
        "licenses_total": total_lic, "licenses_active": active_lic,
        "license_portfolio_summary": license_portfolio_summary,
        "fleet_advisory_summary": _summarize_posture_collection(list(dashboard_postures.values()) if 'dashboard_postures' in locals() else []),
        "remote_action_queue": remote_action_metrics,
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
async def get_audit_log(
    limit: int = 50,
    action: str = None,
    action_prefix: str = None,
    actor: str = None,
    device_id: str = None,
    license_id: str = None,
    customer_id: str = None,
    location_id: str = None,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CentralAuditLog).order_by(CentralAuditLog.timestamp.desc())
    if action:
        stmt = stmt.where(CentralAuditLog.action == action)
    if action_prefix:
        stmt = stmt.where(CentralAuditLog.action.like(f"{action_prefix}%"))
    if actor:
        stmt = stmt.where(CentralAuditLog.actor == actor)
    if device_id:
        stmt = stmt.where(CentralAuditLog.device_id == device_id)
    if license_id:
        stmt = stmt.where(CentralAuditLog.license_id == license_id)
    stmt = stmt.limit(max(1, min(limit, 250)))
    result = await db.execute(stmt)
    entries = result.scalars().all()

    devices_by_id = {}
    locations_by_id = {}
    customers_by_id = {}
    licenses_by_id = {}

    scoped_entries = entries
    if not user.is_superadmin or customer_id or location_id:
        allowed_cids = set(user.allowed_customer_ids or []) if not user.is_superadmin else None
        loc_stmt = select(CentralLocation)
        if customer_id:
            if not can_access_customer(user, customer_id):
                raise HTTPException(403, "Access denied")
            loc_stmt = loc_stmt.where(CentralLocation.customer_id == customer_id)
        elif location_id:
            if not await can_access_location(user, location_id, db):
                raise HTTPException(403, "Access denied")
            loc_stmt = loc_stmt.where(CentralLocation.id == location_id)
        elif not user.is_superadmin:
            loc_stmt = loc_stmt.where(CentralLocation.customer_id.in_(allowed_cids) if allowed_cids else False)
        loc_result = await db.execute(loc_stmt)
        allowed_locations = loc_result.scalars().all()
        locations_by_id = {loc.id: loc for loc in allowed_locations}
        allowed_lids = set(locations_by_id.keys())
        customer_ids = {loc.customer_id for loc in allowed_locations}
        if customer_ids:
            customer_result = await db.execute(select(CentralCustomer).where(CentralCustomer.id.in_(customer_ids)))
            customers_by_id = {customer.id: customer for customer in customer_result.scalars().all()}
        dev_result = await db.execute(select(CentralDevice).where(CentralDevice.location_id.in_(allowed_lids) if allowed_lids else False))
        devices = dev_result.scalars().all()
        devices_by_id = {device.id: device for device in devices}
        lic_stmt = select(CentralLicense)
        if customer_id:
            lic_stmt = lic_stmt.where(CentralLicense.customer_id == customer_id)
        elif location_id:
            lic_stmt = lic_stmt.where(CentralLicense.location_id == location_id)
        elif not user.is_superadmin:
            lic_stmt = lic_stmt.where(CentralLicense.customer_id.in_(allowed_cids) if allowed_cids else False)
        lic_result = await db.execute(lic_stmt)
        licenses_by_id = {lic.id: lic for lic in lic_result.scalars().all()}

        scoped_entries = [
            e for e in entries
            if (not e.device_id or e.device_id in devices_by_id)
            and (not e.license_id or e.license_id in licenses_by_id)
        ]
    else:
        device_ids = {e.device_id for e in entries if e.device_id}
        if device_ids:
            dev_result = await db.execute(select(CentralDevice).where(CentralDevice.id.in_(device_ids)))
            devices = dev_result.scalars().all()
            devices_by_id = {device.id: device for device in devices}
            location_ids = {device.location_id for device in devices if device.location_id}
            if location_ids:
                loc_result = await db.execute(select(CentralLocation).where(CentralLocation.id.in_(location_ids)))
                locations = loc_result.scalars().all()
                locations_by_id = {loc.id: loc for loc in locations}
                customer_ids = {loc.customer_id for loc in locations if loc.customer_id}
                if customer_ids:
                    customer_result = await db.execute(select(CentralCustomer).where(CentralCustomer.id.in_(customer_ids)))
                    customers_by_id = {customer.id: customer for customer in customer_result.scalars().all()}
        license_ids = {e.license_id for e in entries if e.license_id}
        if license_ids:
            lic_result = await db.execute(select(CentralLicense).where(CentralLicense.id.in_(license_ids)))
            licenses_by_id = {lic.id: lic for lic in lic_result.scalars().all()}

    payload = []
    for e in scoped_entries:
        device = devices_by_id.get(e.device_id)
        location = locations_by_id.get(device.location_id) if device is not None else None
        customer = customers_by_id.get(location.customer_id) if location is not None else None
        license_row = licenses_by_id.get(e.license_id) or (licenses_by_id.get(device.license_id) if device is not None and getattr(device, "license_id", None) else None)
        payload.append({
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "action": e.action,
            "device_id": e.device_id,
            "install_id": e.install_id,
            "license_id": e.license_id,
            "message": e.message,
            "actor": e.actor,
            "details": e.details or None,
            "scope": _remote_action_scope_snapshot({}, device=device, location=location, customer=customer, license_row=license_row),
        })
    return payload


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


def _finalize_reg_token_summary(token_summary: dict | None, user: AuthUser) -> dict | None:
    if token_summary is None:
        return None
    payload = dict(token_summary)
    if _can_view_internal_device_detail(user):
        payload["detail_level"] = "internal"
        return payload
    payload.pop("token_preview", None)
    payload.pop("device_name_template", None)
    payload["has_token_preview"] = bool(token_summary.get("token_preview"))
    payload["has_device_name_template"] = bool(token_summary.get("device_name_template"))
    payload["detail_level"] = "operator_safe"
    return payload

async def _get_device_with_scope_check(device_id: str, user: AuthUser, db: AsyncSession) -> CentralDevice:
    result = await db.execute(select(CentralDevice).where(CentralDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(404, "Device not found")
    if not await can_access_location(user, device.location_id, db):
        raise HTTPException(403, "Access denied")
    return device


async def _build_device_advisory_posture(
    db: AsyncSession,
    *,
    device: CentralDevice,
    credential: DeviceCredential | None = None,
    lease: DeviceLease | None = None,
    now: datetime | None = None,
) -> dict:
    license_row = None
    if getattr(device, "license_id", None):
        license_row = await db.get(CentralLicense, device.license_id)

    duplicate_devices: list[CentralDevice] = []
    fingerprint = getattr(credential, "fingerprint", None) or getattr(device, "credential_fingerprint", None)
    if fingerprint:
        dup_result = await db.execute(
            select(CentralDevice).where(
                CentralDevice.credential_fingerprint == fingerprint,
                CentralDevice.id != device.id,
            )
        )
        duplicate_devices = dup_result.scalars().all()

    replacement_target = None
    if getattr(device, "replacement_of_device_id", None):
        replacement_target = await db.get(CentralDevice, device.replacement_of_device_id)

    replacement_children_result = await db.execute(
        select(CentralDevice).where(CentralDevice.replacement_of_device_id == device.id)
    )
    replacement_children = replacement_children_result.scalars().all()

    return build_advisory_device_posture(
        device=device,
        license_row=license_row,
        credential=credential,
        lease=lease,
        duplicate_fingerprint_devices=duplicate_devices,
        replacement_target=replacement_target,
        replacement_children=replacement_children,
        now=now,
    )


async def _build_device_advisory_posture_map(
    db: AsyncSession,
    devices: list[CentralDevice],
    *,
    now: datetime | None = None,
) -> dict[str, dict]:
    now = now or _utcnow()
    if not devices:
        return {}

    device_ids = [device.id for device in devices if getattr(device, "id", None)]
    license_ids = sorted({device.license_id for device in devices if getattr(device, "license_id", None)})
    replacement_target_ids = sorted({device.replacement_of_device_id for device in devices if getattr(device, "replacement_of_device_id", None)})
    fingerprints = sorted({
        getattr(device, "credential_fingerprint", None)
        for device in devices
        if getattr(device, "credential_fingerprint", None)
    })

    credentials_result = await db.execute(
        select(DeviceCredential)
        .where(DeviceCredential.device_id.in_(device_ids))
        .order_by(DeviceCredential.device_id.asc(), DeviceCredential.created_at.desc())
    )
    credentials_by_device: dict[str, list[DeviceCredential]] = defaultdict(list)
    for credential in credentials_result.scalars().all():
        credentials_by_device[credential.device_id].append(credential)

    leases_result = await db.execute(
        select(DeviceLease)
        .where(DeviceLease.device_id.in_(device_ids))
        .order_by(DeviceLease.device_id.asc(), DeviceLease.created_at.desc())
    )
    leases_by_device: dict[str, list[DeviceLease]] = defaultdict(list)
    for lease in leases_result.scalars().all():
        leases_by_device[lease.device_id].append(lease)

    licenses_by_id = {}
    if license_ids:
        license_result = await db.execute(select(CentralLicense).where(CentralLicense.id.in_(license_ids)))
        licenses_by_id = {license_row.id: license_row for license_row in license_result.scalars().all()}

    replacement_targets_by_id = {}
    if replacement_target_ids:
        target_result = await db.execute(select(CentralDevice).where(CentralDevice.id.in_(replacement_target_ids)))
        replacement_targets_by_id = {row.id: row for row in target_result.scalars().all()}

    replacement_children_result = await db.execute(
        select(CentralDevice).where(CentralDevice.replacement_of_device_id.in_(device_ids))
    )
    replacement_children_by_parent: dict[str, list[CentralDevice]] = defaultdict(list)
    for child in replacement_children_result.scalars().all():
        replacement_children_by_parent[child.replacement_of_device_id].append(child)

    fingerprint_candidates_by_value: dict[str, list[CentralDevice]] = defaultdict(list)
    if fingerprints:
        fingerprint_result = await db.execute(
            select(CentralDevice).where(CentralDevice.credential_fingerprint.in_(fingerprints))
        )
        for row in fingerprint_result.scalars().all():
            if getattr(row, "credential_fingerprint", None):
                fingerprint_candidates_by_value[row.credential_fingerprint].append(row)

    posture_map: dict[str, dict] = {}
    for device in devices:
        credentials = credentials_by_device.get(device.id, [])
        credentials_by_id = {c.id: c for c in credentials}
        active_credential = next((c for c in credentials if c.status == DeviceCredentialStatus.ACTIVE.value), None)
        leases = leases_by_device.get(device.id, [])
        current_lease = leases[0] if leases else None
        lease_credential = None
        if current_lease is not None:
            lease_credential = credentials_by_id.get((current_lease.details_json or {}).get("credential_id")) or active_credential
        effective_credential = lease_credential or active_credential

        device_fingerprint = getattr(effective_credential, "fingerprint", None) or getattr(device, "credential_fingerprint", None)
        duplicate_devices = [
            row for row in fingerprint_candidates_by_value.get(device_fingerprint, [])
            if row.id != device.id
        ] if device_fingerprint else []

        posture_map[device.id] = build_advisory_device_posture(
            device=device,
            license_row=licenses_by_id.get(getattr(device, "license_id", None)),
            credential=effective_credential,
            lease=current_lease,
            duplicate_fingerprint_devices=duplicate_devices,
            replacement_target=replacement_targets_by_id.get(getattr(device, "replacement_of_device_id", None)),
            replacement_children=replacement_children_by_parent.get(device.id, []),
            now=now,
        )

    return posture_map


def _compact_advisory_posture(posture: dict | None, *, detail_level: str = "operator_safe") -> dict | None:
    if not posture:
        return None
    compact = {
        "schema": posture.get("schema"),
        "mode": posture.get("mode"),
        "advisory_only": posture.get("advisory_only"),
        "enforcement": posture.get("enforcement"),
        "generated_at": posture.get("generated_at"),
        "overall_posture": posture.get("overall_posture"),
        "trust_posture": posture.get("trust_posture"),
        "commercial_posture": posture.get("commercial_posture"),
        "lifecycle_posture": posture.get("lifecycle_posture"),
        "summary": posture.get("summary"),
        "recommendation": posture.get("recommendation"),
        "finding_summary": posture.get("finding_summary"),
        "finding_codes": [item.get("code") for item in (posture.get("findings") or []) if item.get("code")],
        "detail_level": detail_level,
    }
    return compact


def _summarize_posture_collection(postures: list[dict] | None, *, detail_level: str = "operator_safe") -> dict:
    postures = [item for item in (postures or []) if item]
    counts = {"ready": 0, "degraded": 0, "review_required": 0, "blocked": 0}
    finding_counts: dict[str, int] = defaultdict(int)
    highest = "ready"
    order = {"ready": 0, "degraded": 1, "review_required": 2, "blocked": 3}

    for posture in postures:
        overall = posture.get("overall_posture") or "ready"
        if overall not in counts:
            counts[overall] = 0
        counts[overall] += 1
        if order.get(overall, -1) > order.get(highest, -1):
            highest = overall
        for item in posture.get("findings") or []:
            code = item.get("code")
            if code:
                finding_counts[code] += 1

    top_findings = [
        {"code": code, "count": count}
        for code, count in sorted(finding_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    return {
        "schema": "darts.fleet_advisory_summary.v1",
        "mode": "central_advisory_read_only",
        "advisory_only": True,
        "enforcement": "disabled",
        "device_count": len(postures),
        "overall_posture": highest,
        "counts": counts,
        "top_findings": top_findings,
        "detail_level": detail_level,
    }


# ═══════════════════════════════════════════════════════════════
# DEVICE REGISTRATION (Public/Controlled)
# ═══════════════════════════════════════════════════════════════


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


# ── Telemetry utilities – extracted to central_server.telemetry
from central_server.telemetry import compute_device_connectivity as _compute_device_connectivity


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


# Telemetry helper functions moved to central_server.telemetry_stats
from central_server.telemetry_stats import (
    _resolve_scoped_device_ids,
    _get_or_create_daily_stats,
    _aggregate_daily_stats,
)


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG HELPER
# ═══════════════════════════════════════════════════════════════

async def _log_audit(db, action, device_id=None, install_id=None, license_id=None, actor=None, message=None, details=None):
    try:
        entry = CentralAuditLog(
            action=action, device_id=device_id, install_id=install_id,
            license_id=license_id, actor=actor, message=message, details=details, timestamp=_utcnow(),
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        logger.error(f"[AUDIT] Failed: {e}")


# ═══════════════════════════════════════════════════════════════
# v3.8.0: CENTRALIZED CONFIGURATION
# ═══════════════════════════════════════════════════════════════

def _ser_action(a):
    request_state = _normalize_remote_action_request_state(a)
    outcome_code, outcome_detail = _derive_remote_action_outcome(a)
    d = {
        "id": a.id, "device_id": a.device_id, "action_type": a.action_type,
        "status": a.status, "issued_by": a.issued_by,
        "issued_at": a.issued_at.isoformat() if a.issued_at else None,
        "acked_at": a.acked_at.isoformat() if a.acked_at else None,
        "result_message": a.result_message,
        "request_state": request_state,
        "approval_state": getattr(a, "approval_state", None) or ("pending" if request_state == "pending_approval" else "not_required"),
        "outcome_code": outcome_code,
        "outcome_detail": outcome_detail,
        "request_note": getattr(a, "request_note", None),
        "requested_at": a.requested_at.isoformat() if getattr(a, "requested_at", None) else (a.issued_at.isoformat() if a.issued_at else None),
        "reviewed_at": a.reviewed_at.isoformat() if getattr(a, "reviewed_at", None) else None,
        "reviewed_by": getattr(a, "reviewed_by", None),
        "review_note": getattr(a, "review_note", None),
        "delivered_at": a.delivered_at.isoformat() if getattr(a, "delivered_at", None) else None,
        "finalized_at": a.finalized_at.isoformat() if getattr(a, "finalized_at", None) else (a.acked_at.isoformat() if a.acked_at else None),
        "finalized_by": getattr(a, "finalized_by", None),
    }
    # v3.15.1: Defensive — params column may not exist in old DBs
    try:
        if getattr(a, 'params', None) is not None:
            d["params"] = a.params
    except Exception:
        pass
    try:
        policy = get_remote_action_policy(a.action_type)
        expires_at = policy.expires_at(a.issued_at)
        d.update({
            "category": policy.category,
            "risk_level": policy.risk_level,
            "approval_required": policy.approval_required,
            "expires_at": expires_at.isoformat() if expires_at else None,
        })
    except Exception:
        pass
    return d


# ═══════════════════════════════════════════════════════════════
# v3.9.0: ENHANCED DEVICE DETAIL
# ═══════════════════════════════════════════════════════════════


async def _get_device_detail_raw_sql(device_id: str, user: AuthUser) -> dict:
    return await _get_device_detail_raw_sql_service(
        device_id,
        user,
        session_factory=AsyncSessionLocal,
        compute_device_connectivity=_compute_device_connectivity,
    )


async def _get_device_detail_inner(device_id: str, db: AsyncSession, user: AuthUser) -> dict:
    return await _get_device_detail_inner_service(
        device_id,
        db,
        user,
        get_device_detail_raw_sql_fallback=_get_device_detail_raw_sql,
        compute_device_connectivity=_compute_device_connectivity,
        serialize_action=_ser_action,
    )


def _finalize_remote_action(action: dict, user: AuthUser) -> dict:
    payload = dict(action)
    payload.setdefault("detail_level", "internal" if _can_view_internal_device_detail(user) else "operator_safe")
    if _can_view_internal_device_detail(user):
        return payload
    return _to_operator_safe_recent_action(payload)


async def register_device(body: dict, request: Request, db: AsyncSession):
    return await register_device_with_token_payload(
        body=body,
        request=request,
        db=db,
        logger=logger,
        utcnow=_utcnow,
        aware=_aware,
        hash_token=_hash_token,
        log_audit=_log_audit,
        find_best_license=_find_best_license,
        compute_status=_compute_status,
    )


async def _resolve_affected_devices(db: AsyncSession, scope_type: str, scope_id: str) -> list[str]:
    """Given a config scope, return the list of affected active device IDs."""
    if scope_type == "device":
        return [scope_id] if scope_id else []

    if scope_type == "location":
        result = await db.execute(
            select(CentralDevice.id).where(CentralDevice.location_id == scope_id, CentralDevice.status == "active")
        )
        return [row[0] for row in result.all()]

    if scope_type == "customer":
        loc_result = await db.execute(select(CentralLocation.id).where(CentralLocation.customer_id == scope_id))
        location_ids = [row[0] for row in loc_result.all()]
        if not location_ids:
            return []
        dev_result = await db.execute(
            select(CentralDevice.id).where(CentralDevice.location_id.in_(location_ids), CentralDevice.status == "active")
        )
        return [row[0] for row in dev_result.all()]

    if scope_type == "global":
        result = await db.execute(select(CentralDevice.id).where(CentralDevice.status == "active"))
        return [row[0] for row in result.all()]

    return []


app.include_router(build_remote_actions_router(
    get_device_with_scope_check=_get_device_with_scope_check,
    serialize_action=_ser_action,
    finalize_remote_action=_finalize_remote_action,
    device_ws_hub=device_ws_hub,
))

app.include_router(build_device_remote_actions_router(
    utcnow=_utcnow,
    authenticate_device=_authenticate_device,
    log_audit=_log_audit,
    serialize_action=_ser_action,
    remote_action_lifecycle_details=_remote_action_lifecycle_details,
))

app.include_router(build_device_details_router(
    get_device_detail_inner=_get_device_detail_inner,
    get_device_detail_raw_sql=_get_device_detail_raw_sql,
    finalize_device_detail=_finalize_device_detail,
))

app.include_router(build_device_trust_router(
    utcnow=_utcnow,
    aware=_aware,
    authenticate_device=_authenticate_device,
    get_device_with_scope_check=_get_device_with_scope_check,
    build_device_advisory_posture=_build_device_advisory_posture,
    serialize_device=_ser_device,
    serialize_device_credential=_ser_device_credential,
    serialize_device_credential_summary=_ser_device_credential_summary,
    serialize_device_lease=_ser_device_lease,
    serialize_device_lease_summary=_ser_device_lease_summary,
    hash_token=_hash_token,
    normalize_enrollment_material=normalize_enrollment_material,
    log_audit=_log_audit,
    register_device=register_device,
    require_installer_or_above=require_installer_or_above,
    attach_lease_key_metadata=attach_lease_key_metadata,
    issue_placeholder_credential=issue_placeholder_credential,
    revoke_placeholder_credential=revoke_placeholder_credential,
    revoke_placeholder_lease=revoke_placeholder_lease,
))

app.include_router(build_effective_config_router(
    get_current_user=get_current_user,
    require_min_role=require_min_role,
    authenticate_device=_authenticate_device,
    can_access_location=can_access_location,
    can_access_customer=can_access_customer,
    deep_merge=_deep_merge,
))

app.include_router(build_config_profiles_router(
    get_current_user=get_current_user,
    require_min_role=require_min_role,
    can_access_customer=can_access_customer,
    utcnow=_utcnow,
    log_audit=_log_audit,
    resolve_affected_devices=_resolve_affected_devices,
    device_ws_hub=device_ws_hub,
))

app.include_router(build_admin_crud_router(
    logger=logger,
    utcnow=_utcnow,
    aware=_aware,
    log_audit=_log_audit,
    require_installer_or_above=require_installer_or_above,
    can_access_customer=can_access_customer,
    can_access_location=can_access_location,
    apply_customer_scope=apply_customer_scope,
    serialize_customer=_ser_customer,
    serialize_location=_ser_location,
    serialize_device=_ser_device,
    serialize_license=_ser_license,
    build_device_advisory_posture_map=_build_device_advisory_posture_map,
    compact_advisory_posture=_compact_advisory_posture,
    can_view_internal_device_detail=_can_view_internal_device_detail,
    finalize_device_summary=_finalize_device_summary,
    summarize_posture_collection=_summarize_posture_collection,
    summarize_license_token_state=_summarize_license_token_state,
    compute_status=_compute_status,
    build_license_commercial_readiness=_build_license_commercial_readiness,
    build_license_portfolio_summary=_build_license_portfolio_summary,
    refine_license_detail_suggested_actions=_refine_license_detail_suggested_actions,
    serialize_reg_token_summary=_ser_reg_token_summary,
    finalize_reg_token_summary=_finalize_reg_token_summary,
))

app.include_router(build_licensing_tokens_router(
    logger=logger,
    utcnow=_utcnow,
    aware=_aware,
    log_audit=_log_audit,
    require_installer_or_above=require_installer_or_above,
    can_access_customer=can_access_customer,
    hash_token=_hash_token,
    generate_reg_token=_generate_reg_token,
    serialize_reg_token=_ser_reg_token,
    find_best_license=_find_best_license,
    compute_status=_compute_status,
))

app.include_router(build_ws_status_router(
    device_ws_hub=device_ws_hub,
    resolve_scoped_device_ids=_resolve_scoped_device_ids,
    get_device_with_scope_check=_get_device_with_scope_check,
    finalize_ws_device_status=_finalize_ws_device_status,
    can_view_internal_device_detail=_can_view_internal_device_detail,
))

app.include_router(build_device_ws_router(
    async_session_local=AsyncSessionLocal,
    extract_device_api_key=_extract_device_api_key,
    device_ws_hub=device_ws_hub,
    logger=logger,
    ws_query_auth_mode=_WS_QUERY_AUTH_MODE,
))

for _route in app.routes:
    if not hasattr(_route, "methods"):
        _route.methods = set()

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


