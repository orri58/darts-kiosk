"""
First-Run Setup Wizard
Handles initial system configuration and secure credential setup
"""
import os
import secrets
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.database import DATA_DIR
SETUP_FLAG_FILE = DATA_DIR / '.setup_complete'
SECRETS_FILE = DATA_DIR / '.secrets'


class SetupStatus(BaseModel):
    is_complete: bool
    needs_admin_password: bool
    needs_staff_pin: bool
    needs_secrets_generation: bool
    created_at: Optional[str] = None


class SetupConfig(BaseModel):
    admin_password: str
    staff_pin: str
    cafe_name: str = "Dart Zone"
    generate_new_secrets: bool = True


def generate_secure_secret(length: int = 64) -> str:
    """Generate a cryptographically secure secret"""
    return secrets.token_urlsafe(length)


def is_setup_complete() -> bool:
    """Check if first-run setup has been completed"""
    return SETUP_FLAG_FILE.exists()


def get_stored_secrets() -> dict:
    """Get stored secrets from file"""
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
    """Save secrets to file with restricted permissions"""
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
    except:
        pass
    
    logger.info("Secrets saved securely")


def mark_setup_complete():
    """Mark first-run setup as complete"""
    SETUP_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETUP_FLAG_FILE.write_text(datetime.now(timezone.utc).isoformat())
    logger.info("Setup marked as complete")


def get_setup_timestamp() -> Optional[str]:
    """Get when setup was completed"""
    if SETUP_FLAG_FILE.exists():
        return SETUP_FLAG_FILE.read_text().strip()
    return None


async def check_setup_status(db: AsyncSession) -> SetupStatus:
    """Check current setup status"""
    from backend.models import User, UserRole
    import bcrypt
    
    is_complete = is_setup_complete()
    
    # Check if admin still has default password
    needs_admin_password = False
    needs_staff_pin = False
    
    if not is_complete:
        # Check admin user
        result = await db.execute(
            select(User).where(User.username == "admin")
        )
        admin = result.scalar_one_or_none()
        if admin:
            # Check if password is still default
            try:
                if bcrypt.checkpw(b"admin123", admin.password_hash.encode()):
                    needs_admin_password = True
            except:
                pass
        else:
            needs_admin_password = True
        
        # Check staff PIN
        result = await db.execute(
            select(User).where(User.role == UserRole.STAFF.value)
        )
        staff_users = result.scalars().all()
        for staff in staff_users:
            if staff.pin_hash:
                try:
                    if bcrypt.checkpw(b"0000", staff.pin_hash.encode()):
                        needs_staff_pin = True
                        break
                except:
                    pass
    
    # Check if secrets need generation
    stored_secrets = get_stored_secrets()
    needs_secrets = not stored_secrets.get('JWT_SECRET') or not stored_secrets.get('AGENT_SECRET')
    
    return SetupStatus(
        is_complete=is_complete,
        needs_admin_password=needs_admin_password,
        needs_staff_pin=needs_staff_pin,
        needs_secrets_generation=needs_secrets,
        created_at=get_setup_timestamp()
    )


async def complete_setup(db: AsyncSession, config: SetupConfig) -> dict:
    """Complete the first-run setup"""
    from backend.models import User, Settings, UserRole
    import bcrypt
    
    results = {
        "admin_updated": False,
        "staff_updated": False,
        "secrets_generated": False,
        "branding_updated": False
    }
    
    # Update admin password
    if config.admin_password:
        result = await db.execute(
            select(User).where(User.username == "admin")
        )
        admin = result.scalar_one_or_none()
        if admin:
            admin.password_hash = bcrypt.hashpw(
                config.admin_password.encode(), 
                bcrypt.gensalt()
            ).decode()
            results["admin_updated"] = True
            logger.info("Admin password updated")
    
    # Update staff PIN
    if config.staff_pin:
        result = await db.execute(
            select(User).where(User.role == UserRole.STAFF.value)
        )
        staff_users = result.scalars().all()
        for staff in staff_users:
            staff.pin_hash = bcrypt.hashpw(
                config.staff_pin.encode(),
                bcrypt.gensalt()
            ).decode()
        results["staff_updated"] = True
        logger.info("Staff PINs updated")
    
    # Generate and save new secrets
    if config.generate_new_secrets:
        jwt_secret = generate_secure_secret(64)
        agent_secret = generate_secure_secret(32)
        save_secrets(jwt_secret, agent_secret)
        results["secrets_generated"] = True
        
        # Note: The server needs to be restarted to use new secrets
        logger.warning("New secrets generated - server restart required!")
    
    # Update branding
    if config.cafe_name:
        result = await db.execute(
            select(Settings).where(Settings.key == "branding")
        )
        branding = result.scalar_one_or_none()
        if branding and branding.value:
            branding.value = {**branding.value, "cafe_name": config.cafe_name}
            results["branding_updated"] = True
    
    await db.commit()
    
    # Mark setup as complete
    mark_setup_complete()
    
    return results


def load_secrets_to_env():
    """Load secrets from file into environment (called at startup)"""
    secrets = get_stored_secrets()
    
    if secrets.get('JWT_SECRET'):
        os.environ.setdefault('JWT_SECRET', secrets['JWT_SECRET'])
        logger.info("Loaded JWT_SECRET from secrets file")
    
    if secrets.get('AGENT_SECRET'):
        os.environ.setdefault('AGENT_SECRET', secrets['AGENT_SECRET'])
        logger.info("Loaded AGENT_SECRET from secrets file")
