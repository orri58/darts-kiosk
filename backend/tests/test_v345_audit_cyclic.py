"""
Tests for v3.4.5 — Cyclic License Check + Audit Log

Tests:
1. AuditLogService: writes entries, handles failures gracefully
2. CyclicLicenseChecker: runs on start, status tracking
3. is_session_allowed unchanged (regression)
4. Audit events from license actions
5. Audit log API filtering
"""
import sys
import pytest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _utcnow():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# Test 1: AuditLogService
# ═══════════════════════════════════════════════════════════════

class TestAuditLogService:

    @pytest.mark.asyncio
    async def test_log_creates_entry(self):
        """audit_log_service.log() adds a record to the session."""
        from backend.services.audit_log_service import AuditLogService
        svc = AuditLogService()

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        await svc.log(
            mock_db, "LICENSE_CREATED",
            license_id="lic-1", actor="admin",
            new_value={"plan": "standard"},
            message="Test license created",
        )
        mock_db.add.assert_called_once()
        entry = mock_db.add.call_args[0][0]
        assert entry.action == "LICENSE_CREATED"
        assert entry.license_id == "lic-1"
        assert entry.actor == "admin"

    @pytest.mark.asyncio
    async def test_log_handles_failure_gracefully(self):
        """Audit log failure does not raise."""
        from backend.services.audit_log_service import AuditLogService
        svc = AuditLogService()

        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=Exception("DB error"))

        # Should NOT raise
        await svc.log(mock_db, "BIND_CREATED")

    @pytest.mark.asyncio
    async def test_log_all_fields(self):
        """All optional fields are stored correctly."""
        from backend.services.audit_log_service import AuditLogService
        svc = AuditLogService()

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        await svc.log(
            mock_db, "DEVICE_REBOUND",
            license_id="lic-1", device_id="dev-1",
            install_id="iid-1",
            previous_value={"old": "val"}, new_value={"new": "val"},
            actor="superadmin", message="Rebound test",
        )
        entry = mock_db.add.call_args[0][0]
        assert entry.device_id == "dev-1"
        assert entry.install_id == "iid-1"
        assert entry.previous_value == {"old": "val"}
        assert entry.new_value == {"new": "val"}


# ═══════════════════════════════════════════════════════════════
# Test 2: CyclicLicenseChecker
# ═══════════════════════════════════════════════════════════════

class TestCyclicLicenseChecker:

    def test_initial_status(self):
        """New checker has clean initial state."""
        from backend.services.cyclic_license_checker import CyclicLicenseChecker
        checker = CyclicLicenseChecker()
        status = checker.get_status()
        assert status["running"] is False
        assert status["check_count"] == 0
        assert status["last_check_at"] is None
        assert status["last_check_ok"] is None

    def test_get_status_returns_dict(self):
        """get_status() returns required keys."""
        from backend.services.cyclic_license_checker import CyclicLicenseChecker
        checker = CyclicLicenseChecker()
        status = checker.get_status()
        assert "running" in status
        assert "last_check_at" in status
        assert "last_check_status" in status
        assert "last_check_ok" in status
        assert "check_count" in status


# ═══════════════════════════════════════════════════════════════
# Test 3: Regression — is_session_allowed still works
# ═══════════════════════════════════════════════════════════════

class TestSessionAllowedRegression:

    def test_active_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active"}) is True

    def test_mismatch_grace_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch_grace"}) is True

    def test_mismatch_expired_blocked(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch_expired"}) is False

    def test_no_license_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "no_license"}) is True

    def test_expired_blocked(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "expired"}) is False

    def test_blocked_blocked(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "blocked"}) is False
