"""
Tests for Device Binding — v3.4.3

Tests:
1. DeviceIdentityService: generate, persist, reload install_id
2. First bind: new install_id auto-creates device
3. Same device: bound install_id matches → OK
4. Different device: mismatch detected
5. Rebind: superadmin can reassign device
6. is_session_allowed: mismatch blocks sessions
7. Existing enforcement tests remain green (no_license = allowed)
"""
import json
import os
import sys
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ═══════════════════════════════════════════════════════════════
# Test 1: DeviceIdentityService
# ═══════════════════════════════════════════════════════════════

class TestDeviceIdentityService:
    """Test install_id generation and persistence."""

    def test_generate_install_id(self, tmp_path):
        """New service generates a valid UUID install_id."""
        with patch("backend.services.device_identity_service._IDENTITY_FILE", tmp_path / "identity.json"):
            from backend.services.device_identity_service import DeviceIdentityService
            svc = DeviceIdentityService()
            iid = svc.get_install_id()
            assert iid is not None
            # Valid UUID format
            uuid.UUID(iid)  # raises if invalid

    def test_persist_and_reload(self, tmp_path):
        """install_id is persisted and reloaded across instances."""
        identity_file = tmp_path / "identity.json"
        with patch("backend.services.device_identity_service._IDENTITY_FILE", identity_file):
            from backend.services.device_identity_service import DeviceIdentityService
            svc1 = DeviceIdentityService()
            iid1 = svc1.get_install_id()

            # New instance should load the same id
            svc2 = DeviceIdentityService()
            iid2 = svc2.get_install_id()
            assert iid1 == iid2

    def test_file_contents(self, tmp_path):
        """Identity file contains install_id and fingerprints."""
        identity_file = tmp_path / "identity.json"
        with patch("backend.services.device_identity_service._IDENTITY_FILE", identity_file):
            from backend.services.device_identity_service import DeviceIdentityService
            svc = DeviceIdentityService()
            svc.get_install_id()

            data = json.loads(identity_file.read_text())
            assert "install_id" in data
            assert "fingerprints" in data
            assert "created_hostname" in data

    def test_get_identity_returns_full_info(self, tmp_path):
        """get_identity() returns install_id and fingerprints dict."""
        with patch("backend.services.device_identity_service._IDENTITY_FILE", tmp_path / "identity.json"):
            from backend.services.device_identity_service import DeviceIdentityService
            svc = DeviceIdentityService()
            identity = svc.get_identity()
            assert "install_id" in identity
            assert "fingerprints" in identity
            assert isinstance(identity["fingerprints"], dict)

    def test_corrupted_file_regenerates(self, tmp_path):
        """Corrupted identity file triggers regeneration."""
        identity_file = tmp_path / "identity.json"
        identity_file.write_text("not-json!!!", encoding="utf-8")
        with patch("backend.services.device_identity_service._IDENTITY_FILE", identity_file):
            from backend.services.device_identity_service import DeviceIdentityService
            svc = DeviceIdentityService()
            iid = svc.get_install_id()
            assert iid is not None
            uuid.UUID(iid)


# ═══════════════════════════════════════════════════════════════
# Test 2: Device Binding Logic in LicenseValidationService
# ═══════════════════════════════════════════════════════════════

class TestDeviceBinding:
    """Test the _check_device_binding method."""

    @pytest.mark.asyncio
    async def test_first_bind_creates_device(self):
        """First bind auto-creates a device record with binding_status=bound."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        install_id = str(uuid.uuid4())
        location_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Mock DB: no existing devices at location
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await svc._check_device_binding(mock_db, install_id, location_id, now)
        assert result == "first_bind"
        # Verify device was added
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_same_device_returns_bound(self):
        """Same install_id at location returns 'bound'."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        install_id = str(uuid.uuid4())
        location_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Mock existing device with matching install_id
        mock_device = MagicMock()
        mock_device.install_id = install_id
        mock_device.binding_status = "bound"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_device]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await svc._check_device_binding(mock_db, install_id, location_id, now)
        assert result == "bound"

    @pytest.mark.asyncio
    async def test_different_device_returns_mismatch(self):
        """Different install_id when another device is already bound → mismatch."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        bound_id = str(uuid.uuid4())
        new_id = str(uuid.uuid4())
        location_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Mock existing device with DIFFERENT install_id
        mock_device = MagicMock()
        mock_device.install_id = bound_id
        mock_device.binding_status = "bound"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_device]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await svc._check_device_binding(mock_db, new_id, location_id, now)
        assert result == "mismatch"

    @pytest.mark.asyncio
    async def test_no_location_returns_none(self):
        """No location_id → binding check skipped (returns None)."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        install_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        mock_db = AsyncMock()

        result = await svc._check_device_binding(mock_db, install_id, None, now)
        assert result is None


# ═══════════════════════════════════════════════════════════════
# Test 3: Rebind
# ═══════════════════════════════════════════════════════════════

class TestRebind:
    """Test the rebind_device method."""

    @pytest.mark.asyncio
    async def test_rebind_updates_install_id(self):
        """Rebind updates install_id and sets binding_status=bound."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        device_id = str(uuid.uuid4())
        old_id = str(uuid.uuid4())
        new_id = str(uuid.uuid4())

        mock_device = MagicMock()
        mock_device.id = device_id
        mock_device.install_id = old_id
        mock_device.binding_status = "mismatch"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_device
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await svc.rebind_device(mock_db, device_id, new_id)
        assert result["old_install_id"] == old_id
        assert result["new_install_id"] == new_id
        assert result["binding_status"] == "bound"
        assert mock_device.install_id == new_id
        assert mock_device.binding_status == "bound"

    @pytest.mark.asyncio
    async def test_rebind_nonexistent_device(self):
        """Rebind on nonexistent device returns error."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await svc.rebind_device(mock_db, "nonexistent", "new-id")
        assert "error" in result


# ═══════════════════════════════════════════════════════════════
# Test 4: is_session_allowed with binding
# ═══════════════════════════════════════════════════════════════

class TestSessionAllowedWithBinding:
    """Test is_session_allowed considers binding_status."""

    def test_active_no_binding(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active"}) is True

    def test_active_bound(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "bound"}) is True

    def test_active_first_bind(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "first_bind"}) is True

    def test_active_mismatch_blocked(self):
        """Binding mismatch blocks session even if license is active."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch"}) is False

    def test_no_license_allowed(self):
        """No license configured → fail-open."""
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
# Test 5: build_status includes binding
# ═══════════════════════════════════════════════════════════════

class TestBuildStatusBinding:
    """Test that _build_status correctly includes binding_status."""

    def test_binding_included(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        result = svc._build_status("active", now, binding_status="bound")
        assert result["binding_status"] == "bound"

    def test_no_binding(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        result = svc._build_status("active", now)
        assert "binding_status" not in result

    def test_mismatch_binding(self):
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        now = datetime.now(timezone.utc)
        result = svc._build_status("active", now, binding_status="mismatch")
        assert result["binding_status"] == "mismatch"
