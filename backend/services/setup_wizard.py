"""
First-Run Setup Wizard
Handles initial system configuration and secure credential setup
"""
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR, DATABASE_PATH, PROJECT_ROOT

SETUP_FLAG_FILE = DATA_DIR / '.setup_complete'
SECRETS_FILE = DATA_DIR / '.secrets'
BACKEND_ENV_FILE = PROJECT_ROOT / 'backend' / '.env'
FRONTEND_ENV_FILE = PROJECT_ROOT / 'frontend' / '.env'
_DEFAULT_PIN_CANDIDATES = (b'1234', b'0000')


class SetupStatus(BaseModel):
    is_complete: bool
    needs_admin_password: bool
    needs_staff_pin: bool
    needs_secrets_generation: bool
    created_at: Optional[str] = None
    database_path: Optional[str] = None
    backend_env_exists: bool = False
    frontend_env_exists: bool = False
    local_urls: Dict[str, str] = Field(default_factory=dict)
    preflight_checks: List[Dict[str, Any]] = Field(default_factory=list)


class SetupConfig(BaseModel):
    admin_password: str
    staff_pin: str
    cafe_name: str = "Dart Zone"
    generate_new_secrets: bool = True


def generate_secure_secret(length: int = 64) -> str:
    """Generate a cryptographically secure secret."""
    return secrets.token_urlsafe(length)


def is_setup_complete() -> bool:
    """Check if first-run setup has been completed."""
    return SETUP_FLAG_FILE.exists()


def get_stored_secrets() -> dict:
    """Get stored secrets from file."""
    if not SECRETS_FILE.exists():
        return {}

    try:
        content = SECRETS_FILE.read_text()
        secrets_dict = {}
        for line in content.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                secrets_dict[key.strip()] = value.strip()
        return secrets_dict
    except Exception as e:
        logger.error(f"Failed to read secrets: {e}")
        return {}


def save_secrets(jwt_secret: str, agent_secret: str):
    """Save secrets to file with restricted permissions."""
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Generated secrets - DO NOT SHARE
# Generated at: {datetime.now(timezone.utc).isoformat()}
JWT_SECRET={jwt_secret}
AGENT_SECRET={agent_secret}
"""
    SECRETS_FILE.write_text(content)

    # Set restrictive permissions (owner read only)
    try:
        os.chmod(SECRETS_FILE, 0o600)
    except Exception:
        pass

    logger.info("Secrets saved securely")


def mark_setup_complete():
    """Mark first-run setup as complete."""
    SETUP_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETUP_FLAG_FILE.write_text(datetime.now(timezone.utc).isoformat())
    logger.info("Setup marked as complete")


def get_setup_timestamp() -> Optional[str]:
    """Get when setup was completed."""
    if SETUP_FLAG_FILE.exists():
        return SETUP_FLAG_FILE.read_text().strip()
    return None


def _build_local_urls() -> Dict[str, str]:
    backend_port = os.environ.get('PORT', '8001')
    frontend_port = os.environ.get('FRONTEND_PORT', '3000')
    board_id = os.environ.get('BOARD_ID') or os.environ.get('LOCAL_BOARD_ID') or 'BOARD-1'
    return {
        "backend": f"http://localhost:{backend_port}",
        "admin_login": f"http://localhost:{frontend_port}/admin/login",
        "setup": f"http://localhost:{frontend_port}/setup",
        "kiosk": f"http://localhost:{frontend_port}/kiosk/{board_id}",
    }


def _build_preflight_checks(setup_complete: bool, secrets: Dict[str, str]) -> List[Dict[str, Any]]:
    db_exists = DATABASE_PATH.exists()
    db_size_bytes = DATABASE_PATH.stat().st_size if db_exists else 0

    checks = [
        {
            "key": "backend_env",
            "label": "Backend .env",
            "ok": BACKEND_ENV_FILE.exists(),
            "detail": str(BACKEND_ENV_FILE),
        },
        {
            "key": "frontend_env",
            "label": "Frontend .env",
            "ok": FRONTEND_ENV_FILE.exists(),
            "detail": str(FRONTEND_ENV_FILE),
        },
        {
            "key": "data_dir",
            "label": "Data-Verzeichnis",
            "ok": DATA_DIR.exists(),
            "detail": str(DATA_DIR),
        },
        {
            "key": "database",
            "label": "SQLite-Datenbank",
            "ok": db_exists,
            "detail": f"{DATABASE_PATH} ({db_size_bytes} Bytes)" if db_exists else str(DATABASE_PATH),
        },
        {
            "key": "secrets",
            "label": "JWT/Agent-Secrets",
            "ok": bool(secrets.get('JWT_SECRET') and secrets.get('AGENT_SECRET')),
            "detail": str(SECRETS_FILE),
        },
        {
            "key": "setup_complete",
            "label": "Ersteinrichtung abgeschlossen",
            "ok": setup_complete,
            "detail": get_setup_timestamp() or "Noch nicht abgeschlossen",
        },
    ]
    return checks


def _matches_any_pin(pin_hash: Optional[str], candidates: tuple[bytes, ...]) -> bool:
    if not pin_hash:
        return True

    import bcrypt

    for candidate in candidates:
        try:
            if bcrypt.checkpw(candidate, pin_hash.encode()):
                return True
        except Exception:
            continue
    return False


async def check_setup_status(db: AsyncSession) -> SetupStatus:
    """Check current setup status and surface lightweight preflight data."""
    from backend.models import User, UserRole
    import bcrypt

    is_complete = is_setup_complete()

    needs_admin_password = False
    needs_staff_pin = False

    result = await db.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one_or_none()
    if admin:
        try:
            if bcrypt.checkpw(b"admin123", admin.password_hash.encode()):
                needs_admin_password = True
        except Exception:
            needs_admin_password = True
    else:
        needs_admin_password = True

    result = await db.execute(
        select(User).where(User.role.in_([UserRole.ADMIN.value, UserRole.STAFF.value]))
    )
    quick_pin_users = result.scalars().all()
    if not quick_pin_users:
        needs_staff_pin = True
    else:
        needs_staff_pin = any(_matches_any_pin(user.pin_hash, _DEFAULT_PIN_CANDIDATES) for user in quick_pin_users)

    stored_secrets = get_stored_secrets()
    needs_secrets = not stored_secrets.get('JWT_SECRET') or not stored_secrets.get('AGENT_SECRET')

    return SetupStatus(
        is_complete=is_complete,
        needs_admin_password=(needs_admin_password and not is_complete),
        needs_staff_pin=(needs_staff_pin and not is_complete),
        needs_secrets_generation=needs_secrets,
        created_at=get_setup_timestamp(),
        database_path=str(DATABASE_PATH),
        backend_env_exists=BACKEND_ENV_FILE.exists(),
        frontend_env_exists=FRONTEND_ENV_FILE.exists(),
        local_urls=_build_local_urls(),
        preflight_checks=_build_preflight_checks(is_complete, stored_secrets),
    )


async def complete_setup(db: AsyncSession, config: SetupConfig) -> dict:
    """Complete the first-run setup."""
    from backend.models import Settings, User, UserRole
    import bcrypt

    results = {
        "admin_updated": False,
        "staff_updated": False,
        "quick_pin_updated": False,
        "quick_pin_users": [],
        "secrets_generated": False,
        "branding_updated": False,
    }

    if config.admin_password:
        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if admin:
            admin.password_hash = bcrypt.hashpw(
                config.admin_password.encode(),
                bcrypt.gensalt(),
            ).decode()
            results["admin_updated"] = True
            logger.info("Admin password updated")

    if config.staff_pin:
        result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN.value, UserRole.STAFF.value]))
        )
        quick_pin_users = result.scalars().all()
        for user in quick_pin_users:
            user.pin_hash = bcrypt.hashpw(
                config.staff_pin.encode(),
                bcrypt.gensalt(),
            ).decode()
            results["quick_pin_users"].append(user.username)

        if quick_pin_users:
            results["quick_pin_updated"] = True
            results["staff_updated"] = True
            logger.info("Quick PIN updated for admin/staff users")

    if config.generate_new_secrets:
        jwt_secret = generate_secure_secret(64)
        agent_secret = generate_secure_secret(32)
        save_secrets(jwt_secret, agent_secret)
        results["secrets_generated"] = True

        # Note: The server needs to be restarted to use new secrets
        logger.warning("New secrets generated - server restart required!")

    if config.cafe_name:
        result = await db.execute(select(Settings).where(Settings.key == "branding"))
        branding = result.scalar_one_or_none()
        if branding and branding.value:
            branding.value = {**branding.value, "cafe_name": config.cafe_name}
            results["branding_updated"] = True

    await db.commit()

    mark_setup_complete()

    return results


def load_secrets_to_env():
    """Load secrets from file into environment (called at startup)."""
    secrets = get_stored_secrets()

    if secrets.get('JWT_SECRET'):
        os.environ.setdefault('JWT_SECRET', secrets['JWT_SECRET'])
        logger.info("Loaded JWT_SECRET from secrets file")

    if secrets.get('AGENT_SECRET'):
        os.environ.setdefault('AGENT_SECRET', secrets['AGENT_SECRET'])
        logger.info("Loaded AGENT_SECRET from secrets file")
