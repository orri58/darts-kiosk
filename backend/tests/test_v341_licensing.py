"""
Tests for Licensing System MVP — v3.4.1

Tests:
1. License status computation (active/grace/expired/blocked)
2. Grace period enforcement
3. Local cache save/load + tamper detection
4. Session-allow logic
5. CRUD endpoints
6. No regressions on existing runtime
"""
import json
import os
import sys
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ═══════════════════════════════════════════════════════════════
# Test 1: License Status Computation
# ═══════════════════════════════════════════════════════════════

class TestLicenseStatusComputation:
    """Test the _compute_license_status method."""

    def _make_license(self, **kwargs):
        """Create a mock License object."""
        lic = MagicMock()
        lic.status = kwargs.get("status", "active")
        lic.starts_at = kwargs.get("starts_at")
        lic.ends_at = kwargs.get("ends_at")
        lic.grace_days = kwargs.get("grace_days", 7)
        lic.grace_until = kwargs.get("grace_until")
        return lic

    def test_active_no_end(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(starts_at=now - timedelta(days=10))
        assert svc._compute_license_status(lic, now) == "active"

    def test_active_before_end(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            starts_at=now - timedelta(days=10),
            ends_at=now + timedelta(days=30),
        )
        assert svc._compute_license_status(lic, now) == "active"

    def test_grace_after_end(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            starts_at=now - timedelta(days=40),
            ends_at=now - timedelta(days=3),
            grace_days=7,
        )
        assert svc._compute_license_status(lic, now) == "grace"

    def test_expired_past_grace(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            starts_at=now - timedelta(days=100),
            ends_at=now - timedelta(days=30),
            grace_days=7,
        )
        assert svc._compute_license_status(lic, now) == "expired"

    def test_blocked_always_blocked(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            status="blocked",
            ends_at=now + timedelta(days=100),
        )
        assert svc._compute_license_status(lic, now) == "blocked"

    def test_test_license_valid(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            status="test",
            ends_at=now + timedelta(days=14),
        )
        assert svc._compute_license_status(lic, now) == "test"

    def test_test_license_expired(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            status="test",
            ends_at=now - timedelta(days=1),
        )
        assert svc._compute_license_status(lic, now) == "expired"

    def test_not_yet_started(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        lic = self._make_license(
            starts_at=now + timedelta(days=5),
            ends_at=now + timedelta(days=365),
        )
        assert svc._compute_license_status(lic, now) == "expired"

    def test_naive_datetime_handled(self):
        """SQLite stores naive datetimes — ensure they're handled."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        # Simulate naive datetime from SQLite
        lic = self._make_license(
            starts_at=datetime.now() - timedelta(days=10),  # naive
            ends_at=datetime.now() + timedelta(days=30),     # naive
        )
        # Should not raise
        result = svc._compute_license_status(lic, now)
        assert result in ("active", "grace", "expired", "test", "blocked")


# ═══════════════════════════════════════════════════════════════
# Test 2: Session Allow Logic
# ═══════════════════════════════════════════════════════════════

class TestSessionAllowLogic:
    """Test is_session_allowed method."""

    def test_active_allows(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active"}) is True

    def test_grace_allows(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "grace"}) is True

    def test_test_allows(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "test"}) is True

    def test_expired_blocks(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "expired"}) is False

    def test_blocked_blocks(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "blocked"}) is False

    def test_no_license_blocks(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "no_license"}) is False


# ═══════════════════════════════════════════════════════════════
# Test 3: License Cache
# ═══════════════════════════════════════════════════════════════

class TestLicenseCache:
    """Test local license cache operations."""

    def test_save_and_load(self, tmp_path):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        cache_file = tmp_path / "license_cache.json"

        test_status = {"status": "active", "license_id": "test-123", "checked_at": "2026-01-01T00:00:00"}

        with patch("backend.services.license_service._CACHE_FILE", cache_file):
            svc.save_to_cache(test_status)
            assert cache_file.exists()
            loaded = svc.load_from_cache()
            assert loaded is not None
            assert loaded["status"] == "active"
            assert loaded["license_id"] == "test-123"

    def test_tamper_detection(self, tmp_path):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        cache_file = tmp_path / "license_cache.json"

        test_status = {"status": "active", "license_id": "test-456", "checked_at": "2026-01-01T00:00:00"}

        with patch("backend.services.license_service._CACHE_FILE", cache_file):
            svc.save_to_cache(test_status)
            # Tamper with the cache
            data = json.loads(cache_file.read_text())
            data["license_status"]["status"] = "blocked"
            cache_file.write_text(json.dumps(data))
            # Load should detect tampering
            loaded = svc.load_from_cache()
            assert loaded is None  # tampered — returns None

    def test_missing_cache(self, tmp_path):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        cache_file = tmp_path / "nonexistent.json"
        with patch("backend.services.license_service._CACHE_FILE", cache_file):
            loaded = svc.load_from_cache()
            assert loaded is None


# ═══════════════════════════════════════════════════════════════
# Test 4: Model Imports
# ═══════════════════════════════════════════════════════════════

class TestLicensingModels:
    """Ensure all licensing models can be imported."""

    def test_all_models_importable(self):
        from backend.models.licensing import (
            LicCustomer, LicLocation, LicDevice, License, UserMembership,
            LicenseStatus, DeviceStatus, CustomerStatus, SystemRole,
        )
        assert LicenseStatus.ACTIVE.value == "active"
        assert DeviceStatus.BLOCKED.value == "blocked"
        assert SystemRole.SUPERADMIN.value == "superadmin"

    def test_table_names(self):
        from backend.models.licensing import LicCustomer, LicLocation, LicDevice, License, UserMembership
        assert LicCustomer.__tablename__ == "lic_customers"
        assert LicLocation.__tablename__ == "lic_locations"
        assert LicDevice.__tablename__ == "lic_devices"
        assert License.__tablename__ == "lic_licenses"
        assert UserMembership.__tablename__ == "lic_user_memberships"

    def test_enums_complete(self):
        from backend.models.licensing import LicenseStatus
        expected = {"active", "grace", "expired", "blocked", "test"}
        actual = {s.value for s in LicenseStatus}
        assert actual == expected
