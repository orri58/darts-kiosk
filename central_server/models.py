"""
Central License Server — Models
Mirror of licensing models from the kiosk, but in the central server's own DB.
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


class CentralAuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    timestamp = Column(DateTime, nullable=False, default=_utcnow, index=True)
    action = Column(String(50), nullable=False, index=True)
    device_id = Column(String(36), nullable=True)
    install_id = Column(String(64), nullable=True)
    license_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    message = Column(Text, nullable=True)
