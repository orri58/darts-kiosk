"""
Licensing Models for Darts Kiosk System — v3.4.1 MVP

Additive models for multi-tenant licensing. Does NOT modify existing models.
All tables use the 'lic_' prefix to clearly separate from core runtime tables.

Entities:
- LicCustomer: Business entity (cafe, bar, operator)
- LicLocation: Physical location of a customer
- LicDevice: Individual kiosk device at a location
- License: License record linking customer/location to entitlements
- UserMembership: Maps existing users to customers/locations with system roles
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid

from backend.database import Base


def _uuid():
    return str(uuid.uuid4())

def _utcnow():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════

class LicenseStatus(str, enum.Enum):
    ACTIVE = "active"
    GRACE = "grace"          # past end date, within grace period
    EXPIRED = "expired"      # past grace period
    BLOCKED = "blocked"      # manually blocked by superadmin
    TEST = "test"            # trial license

class DeviceStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"

class CustomerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"

class SystemRole(str, enum.Enum):
    SUPERADMIN = "superadmin"      # full system access
    OPERATOR = "operator"          # manages own customers
    LOCATION_ADMIN = "loc_admin"   # manages own location only
    VIEWER = "viewer"              # read-only


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════

class LicCustomer(Base):
    """Business entity — a cafe, bar, or operator."""
    __tablename__ = "lic_customers"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default=CustomerStatus.ACTIVE.value)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    locations = relationship("LicLocation", back_populates="customer", cascade="all, delete-orphan")
    licenses = relationship("License", back_populates="customer", cascade="all, delete-orphan")


class LicLocation(Base):
    """Physical location belonging to a customer."""
    __tablename__ = "lic_locations"

    id = Column(String(36), primary_key=True, default=_uuid)
    customer_id = Column(String(36), ForeignKey("lic_customers.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    address = Column(Text, nullable=True)
    status = Column(String(20), default=CustomerStatus.ACTIVE.value)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    customer = relationship("LicCustomer", back_populates="locations")
    devices = relationship("LicDevice", back_populates="location", cascade="all, delete-orphan")


class LicDevice(Base):
    """Individual kiosk device at a location, linked to a board."""
    __tablename__ = "lic_devices"

    id = Column(String(36), primary_key=True, default=_uuid)
    location_id = Column(String(36), ForeignKey("lic_locations.id"), nullable=False, index=True)
    board_id = Column(String(50), nullable=True, index=True)  # links to boards.board_id
    install_id = Column(String(64), unique=True, nullable=True, index=True)  # generated on first start
    hardware_fingerprint = Column(String(128), nullable=True)
    device_name = Column(String(100), nullable=True)
    status = Column(String(20), default=DeviceStatus.ACTIVE.value)
    binding_status = Column(String(20), default="unbound")  # unbound, bound, mismatch
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_license_check_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    location = relationship("LicLocation", back_populates="devices")


class License(Base):
    """License record — ties a customer to entitlements with time bounds."""
    __tablename__ = "lic_licenses"

    id = Column(String(36), primary_key=True, default=_uuid)
    customer_id = Column(String(36), ForeignKey("lic_customers.id"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("lic_locations.id"), nullable=True, index=True)

    # Plan
    plan_type = Column(String(50), default="standard")  # standard, premium, test
    max_devices = Column(Integer, default=1)

    # Status & Dates
    status = Column(String(20), default=LicenseStatus.ACTIVE.value)
    starts_at = Column(DateTime, nullable=False, default=_utcnow)
    ends_at = Column(DateTime, nullable=True)  # None = unlimited
    grace_days = Column(Integer, default=7)  # days after ends_at where system still works
    grace_until = Column(DateTime, nullable=True)  # computed: ends_at + grace_days

    # Metadata
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    customer = relationship("LicCustomer", back_populates="licenses")


class UserMembership(Base):
    """Maps existing users to customers/locations with system roles.

    This is a separate table to avoid modifying the existing User model.
    A user can have multiple memberships (e.g., operator for multiple customers).
    """
    __tablename__ = "lic_user_memberships"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("lic_customers.id"), nullable=True, index=True)
    location_id = Column(String(36), ForeignKey("lic_locations.id"), nullable=True, index=True)
    system_role = Column(String(20), nullable=False, default=SystemRole.VIEWER.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
