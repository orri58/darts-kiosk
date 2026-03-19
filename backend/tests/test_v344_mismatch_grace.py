"""
Tests for v3.4.4 — Mismatch Grace + Tracking

Tests:
1. _evaluate_mismatch_grace: first detection, within grace, expired
2. is_session_allowed with new binding states
3. _check_device_binding with grace logic
4. rebind clears mismatch state
5. trigger_binding=False does NOT auto-bind
6. trigger_binding=True DOES auto-bind
7. Binding grace hours setting
8. Regression: existing license/enforcement tests still green
"""
import json
import sys
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _utcnow():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# Test 1: _evaluate_mismatch_grace
# ═══════════════════════════════════════════════════════════════

class TestEvaluateMismatchGrace:
    """Test the mismatch grace evaluation logic."""

    def test_first_detection_returns_mismatch_grace(self):
        """First time mismatch: set mismatch_detected_at, return mismatch_grace."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        device = MagicMock()
        device.id = "dev-1"
        device.install_id = "original-id"
        device.mismatch_detected_at = None
        device.previous_install_id = None
        device.binding_status = "bound"

        result = svc._evaluate_mismatch_grace(device, "new-id", _utcnow(), 48)
        assert result == "mismatch_grace"
        assert device.mismatch_detected_at is not None
        assert device.previous_install_id == "original-id"
        assert device.binding_status == "mismatch_grace"

    def test_within_grace_returns_mismatch_grace(self):
        """Within grace period: return mismatch_grace."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        now = _utcnow()
        device = MagicMock()
        device.id = "dev-1"
        device.install_id = "original-id"
        device.mismatch_detected_at = now - timedelta(hours=12)  # 12h ago
        device.binding_status = "mismatch_grace"

        result = svc._evaluate_mismatch_grace(device, "new-id", now, 48)
        assert result == "mismatch_grace"
        assert device.binding_status == "mismatch_grace"

    def test_expired_grace_returns_mismatch_expired(self):
        """Past grace period: return mismatch_expired."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        now = _utcnow()
        device = MagicMock()
        device.id = "dev-1"
        device.install_id = "original-id"
        device.mismatch_detected_at = now - timedelta(hours=72)  # 72h ago, > 48h grace
        device.binding_status = "mismatch_grace"

        result = svc._evaluate_mismatch_grace(device, "new-id", now, 48)
        assert result == "mismatch_expired"
        assert device.binding_status == "mismatch_expired"

    def test_custom_grace_hours(self):
        """Custom grace hours (24h): 25h past → expired."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        now = _utcnow()
        device = MagicMock()
        device.id = "dev-1"
        device.install_id = "original-id"
        device.mismatch_detected_at = now - timedelta(hours=25)

        result = svc._evaluate_mismatch_grace(device, "new-id", now, 24)
        assert result == "mismatch_expired"

    def test_custom_grace_hours_within(self):
        """Custom grace hours (72h): 48h past → still in grace."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        now = _utcnow()
        device = MagicMock()
        device.id = "dev-1"
        device.install_id = "original-id"
        device.mismatch_detected_at = now - timedelta(hours=48)

        result = svc._evaluate_mismatch_grace(device, "new-id", now, 72)
        assert result == "mismatch_grace"


# ═══════════════════════════════════════════════════════════════
# Test 2: is_session_allowed with new binding states
# ═══════════════════════════════════════════════════════════════

class TestSessionAllowedV344:
    """Test is_session_allowed with v3.4.4 binding states."""

    def test_mismatch_grace_allowed(self):
        """mismatch_grace allows sessions."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch_grace"}) is True

    def test_mismatch_expired_blocked(self):
        """mismatch_expired blocks sessions."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch_expired"}) is False

    def test_unbound_allowed(self):
        """unbound status allows sessions."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "unbound"}) is True

    def test_bound_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "bound"}) is True

    def test_first_bind_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "first_bind"}) is True

    def test_no_binding_active_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active"}) is True

    def test_no_license_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "no_license"}) is True

    def test_expired_blocked(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "expired"}) is False

    def test_grace_allowed(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "grace"}) is True


# ═══════════════════════════════════════════════════════════════
# Test 3: Rebind clears mismatch state
# ═══════════════════════════════════════════════════════════════

class TestRebindV344:
    """Test rebind clears mismatch state and stores previous_install_id."""

    @pytest.mark.asyncio
    async def test_rebind_clears_mismatch(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        device = MagicMock()
        device.id = "dev-1"
        device.install_id = "old-id"
        device.binding_status = "mismatch_grace"
        device.mismatch_detected_at = _utcnow()
        device.previous_install_id = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = device
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await svc.rebind_device(mock_db, "dev-1", "new-id")
        assert result["binding_status"] == "bound"
        assert result["old_install_id"] == "old-id"
        assert device.mismatch_detected_at is None
        assert device.previous_install_id == "old-id"
        assert device.install_id == "new-id"
        assert device.binding_status == "bound"


# ═══════════════════════════════════════════════════════════════
# Test 4: trigger_binding flag
# ═══════════════════════════════════════════════════════════════

class TestTriggerBinding:
    """Test that trigger_binding controls auto-bind."""

    @pytest.mark.asyncio
    async def test_no_trigger_no_autobind(self):
        """trigger_binding=False should NOT auto-bind unbound device."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        install_id = str(uuid.uuid4())
        now = _utcnow()

        # Mock: no existing devices at location
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await svc._check_device_binding(mock_db, install_id, "loc-1", now, 48, trigger_binding=False)
        assert result == "unbound"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_autobinds(self):
        """trigger_binding=True should auto-bind when no devices exist."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        install_id = str(uuid.uuid4())
        now = _utcnow()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await svc._check_device_binding(mock_db, install_id, "loc-1", now, 48, trigger_binding=True)
        assert result == "first_bind"
        mock_db.add.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Test 5: Mismatch grace in _check_device_binding
# ═══════════════════════════════════════════════════════════════

class TestCheckDeviceBindingGrace:
    """Test mismatch grace logic inside _check_device_binding."""

    @pytest.mark.asyncio
    async def test_mismatch_with_grace(self):
        """Different install_id on bound device → mismatch_grace (first detection)."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        existing_device = MagicMock()
        existing_device.install_id = "bound-id"
        existing_device.binding_status = "bound"
        existing_device.mismatch_detected_at = None
        existing_device.previous_install_id = None
        existing_device.id = "dev-1"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_device]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await svc._check_device_binding(mock_db, "new-id", "loc-1", _utcnow(), 48)
        assert result == "mismatch_grace"

    @pytest.mark.asyncio
    async def test_mismatch_grace_expired_in_check(self):
        """Mismatch detected 72h ago with 48h grace → mismatch_expired."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        now = _utcnow()
        existing_device = MagicMock()
        existing_device.install_id = "bound-id"
        existing_device.binding_status = "mismatch_grace"
        existing_device.mismatch_detected_at = now - timedelta(hours=72)
        existing_device.id = "dev-1"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_device]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await svc._check_device_binding(mock_db, "new-id", "loc-1", now, 48)
        assert result == "mismatch_expired"


# ═══════════════════════════════════════════════════════════════
# Test 6: Build status includes new binding states
# ═══════════════════════════════════════════════════════════════

class TestBuildStatusV344:

    def test_mismatch_grace_in_build(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        result = svc._build_status("active", _utcnow(), binding_status="mismatch_grace")
        assert result["binding_status"] == "mismatch_grace"

    def test_mismatch_expired_in_build(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        result = svc._build_status("active", _utcnow(), binding_status="mismatch_expired")
        assert result["binding_status"] == "mismatch_expired"
