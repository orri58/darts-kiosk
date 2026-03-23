"""
Central License Server — Models
v3.5.2: Added CentralUser model for role-based access control.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid

from central_server.database import Base


def _uuid():
    return str(uuid.uuid4())

def _utcnow():
    return datetime.now(timezone.utc)


class LicenseStatus(str, enum.Enum):
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    TEST = "test"
    DEACTIVATED = "deactivated"
    ARCHIVED = "archived"


class CustomerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class DeviceStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class CentralCustomer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default=CustomerStatus.ACTIVE.value)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    locations = relationship("CentralLocation", back_populates="customer", cascade="all, delete-orphan")
    licenses = relationship("CentralLicense", back_populates="customer", cascade="all, delete-orphan")


class CentralLocation(Base):
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=_uuid)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    address = Column(Text, nullable=True)
    status = Column(String(20), default=CustomerStatus.ACTIVE.value)
    created_at = Column(DateTime, default=_utcnow)

    customer = relationship("CentralCustomer", back_populates="locations")
    devices = relationship("CentralDevice", back_populates="location", cascade="all, delete-orphan")


class CentralDevice(Base):
    """Registered kiosk device. Linked to a location and bound by install_id."""
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=False, index=True)
    install_id = Column(String(64), unique=True, nullable=True, index=True)
    api_key = Column(String(128), unique=True, nullable=False, index=True)
    device_name = Column(String(100), nullable=True)
    status = Column(String(20), default=DeviceStatus.ACTIVE.value)
    binding_status = Column(String(20), default="unbound")
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_ip = Column(String(50), nullable=True)
    sync_count = Column(Integer, default=0)
    registered_via_token_id = Column(String(36), nullable=True)
    license_id = Column(String(36), ForeignKey("licenses.id"), nullable=True, index=True)
    # v3.7.0: Heartbeat / Telemetry fields
    last_heartbeat_at = Column(DateTime, nullable=True)
    reported_version = Column(String(20), nullable=True)
    last_error = Column(Text, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)
    # v3.9.3: Observability — health snapshot + logs from heartbeat
    health_snapshot = Column(Text, nullable=True)  # JSON
    device_logs = Column(Text, nullable=True)  # JSON array
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    location = relationship("CentralLocation", back_populates="devices")


class CentralLicense(Base):
    __tablename__ = "licenses"

    id = Column(String(36), primary_key=True, default=_uuid)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    plan_type = Column(String(50), default="standard")
    max_devices = Column(Integer, default=1)
    status = Column(String(20), default=LicenseStatus.ACTIVE.value)
    starts_at = Column(DateTime, nullable=False, default=_utcnow)
    ends_at = Column(DateTime, nullable=True)
    grace_days = Column(Integer, default=7)
    grace_until = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    customer = relationship("CentralCustomer", back_populates="licenses")


class RegistrationToken(Base):
    """One-time registration token for device onboarding (v3.5.1)."""
    __tablename__ = "registration_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    token_preview = Column(String(12), nullable=False)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True)
    license_id = Column(String(36), ForeignKey("licenses.id"), nullable=True)
    device_name_template = Column(String(100), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by_install_id = Column(String(64), nullable=True)
    used_by_device_id = Column(String(36), nullable=True)
    created_by = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class CentralAuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    timestamp = Column(DateTime, nullable=False, default=_utcnow, index=True)
    action = Column(String(50), nullable=False, index=True)
    device_id = Column(String(36), nullable=True)
    install_id = Column(String(64), nullable=True)
    license_id = Column(String(36), nullable=True)
    actor = Column(String(100), nullable=True)  # username who triggered the action
    details = Column(JSON, nullable=True)
    message = Column(Text, nullable=True)


class CentralUser(Base):
    """Admin/Operator user for the central license server (v3.6.0).
    Roles: superadmin | installer | owner | staff
    """
    __tablename__ = "central_users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default="staff")  # superadmin | installer | owner | staff
    allowed_customer_ids = Column(JSON, nullable=True)  # List of customer IDs for scoped roles
    created_by_user_id = Column(String(36), nullable=True)  # Who created this user (for hierarchy)
    status = Column(String(20), default="active")  # active | disabled
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ═══════════════════════════════════════════════════════════════
# v3.7.0: Telemetry & Revenue Models
# ═══════════════════════════════════════════════════════════════

class TelemetryEvent(Base):
    """Individual telemetry events from devices. Idempotent via event_id."""
    __tablename__ = "telemetry_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_id = Column(String(64), unique=True, nullable=False, index=True)  # Client-generated UUID for idempotency
    device_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)  # heartbeat, game_played, credits_added, session_started, error, restart, etc.
    timestamp = Column(DateTime, nullable=False, index=True)
    data = Column(JSON, nullable=True)  # Flexible payload
    created_at = Column(DateTime, default=_utcnow)


class DeviceDailyStats(Base):
    """Aggregated daily statistics per device. Updated on ingest."""
    __tablename__ = "device_daily_stats"

    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(36), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    revenue_cents = Column(Integer, default=0)
    sessions = Column(Integer, default=0)
    games = Column(Integer, default=0)
    credits_added = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    heartbeats = Column(Integer, default=0)
    first_heartbeat_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        # Unique constraint: one row per device per day
        {"sqlite_autoincrement": False},
    )



# ═══════════════════════════════════════════════════════════════
# v3.8.0: Hierarchical Configuration Profiles
# ═══════════════════════════════════════════════════════════════

class ConfigProfile(Base):
    """
    Hierarchical config: global → customer → location → device.
    The effective config for a device is computed by merging all
    applicable profiles in order (narrower scope wins).
    """
    __tablename__ = "config_profiles"

    id = Column(String(36), primary_key=True, default=_uuid)
    scope_type = Column(String(20), nullable=False, index=True)  # global | customer | location | device
    scope_id = Column(String(36), nullable=True, index=True)     # null for global, FK for others
    config_data = Column(JSON, nullable=False, default=dict)     # The actual config key-values
    version = Column(Integer, default=1)                         # Optimistic locking / sync versioning
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)



class RemoteAction(Base):
    """
    Queued remote actions for devices. Devices poll for pending actions.
    v3.15.0: Added params JSON column for board control parameters.
    """
    __tablename__ = "remote_actions"

    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(36), nullable=False, index=True)
    action_type = Column(String(30), nullable=False)
    params = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")     # pending | acked | failed | expired
    issued_by = Column(String(100), nullable=False)
    issued_at = Column(DateTime, default=_utcnow)
    acked_at = Column(DateTime, nullable=True)
    result_message = Column(Text, nullable=True)


class ConfigHistory(Base):
    """
    v3.9.4: Stores previous versions of config profiles for rollback.
    Created automatically when a profile is updated.
    """
    __tablename__ = "config_history"

    id = Column(String(36), primary_key=True, default=_uuid)
    profile_id = Column(String(36), nullable=False, index=True)
    scope_type = Column(String(20), nullable=False, index=True)
    scope_id = Column(String(36), nullable=True, index=True)
    config_data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False)
    updated_by = Column(String(100), nullable=True)
    saved_at = Column(DateTime, default=_utcnow)
