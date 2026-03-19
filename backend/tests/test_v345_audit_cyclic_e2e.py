"""
E2E Tests for v3.4.5 — Cyclic License Check + Audit Log APIs

Tests:
1. GET /api/licensing/check-status - returns cyclic checker status
2. POST /api/licensing/check-now - triggers manual license check
3. GET /api/licensing/audit-log - returns paginated audit entries
4. GET /api/licensing/audit-log?action=X - filters by action type
5. Audit events written on license actions (create/block/activate/extend/rebind)
6. Cyclic checker runs on startup (check_count >= 1)
7. Regression: existing license CRUD still works
8. Regression: binding settings endpoint still works
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://boardgame-repair.preview.emergentagent.com"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if resp.status_code == 200:
        return resp.json().get("access_token")
    pytest.skip("Auth failed - cannot run tests")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers."""
    return {"Authorization": f"Bearer {auth_token}"}


# ═══════════════════════════════════════════════════════════════
# Test 1: GET /api/licensing/check-status
# ═══════════════════════════════════════════════════════════════

class TestCheckStatusEndpoint:
    
    def test_requires_auth(self):
        """GET /api/licensing/check-status requires auth."""
        resp = requests.get(f"{BASE_URL}/api/licensing/check-status")
        assert resp.status_code == 401
    
    def test_returns_checker_status(self, headers):
        """GET /api/licensing/check-status returns checker status fields."""
        resp = requests.get(f"{BASE_URL}/api/licensing/check-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "last_check_at" in data
        assert "last_check_status" in data
        assert "last_check_ok" in data
        assert "check_count" in data
        # Should be running after server startup
        assert data["running"] is True
    
    def test_checker_ran_on_startup(self, headers):
        """Cyclic checker runs on server start (check_count >= 1)."""
        resp = requests.get(f"{BASE_URL}/api/licensing/check-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["check_count"] >= 1, "Cyclic checker should have run at least once on startup"
        assert data["last_check_at"] is not None, "last_check_at should be set after startup check"


# ═══════════════════════════════════════════════════════════════
# Test 2: POST /api/licensing/check-now
# ═══════════════════════════════════════════════════════════════

class TestCheckNowEndpoint:
    
    def test_requires_auth(self):
        """POST /api/licensing/check-now requires auth."""
        resp = requests.post(f"{BASE_URL}/api/licensing/check-now")
        assert resp.status_code == 401
    
    def test_triggers_manual_check(self, headers):
        """POST /api/licensing/check-now returns {triggered: true}."""
        resp = requests.post(f"{BASE_URL}/api/licensing/check-now", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["triggered"] is True
        assert "message" in data


# ═══════════════════════════════════════════════════════════════
# Test 3: GET /api/licensing/audit-log
# ═══════════════════════════════════════════════════════════════

class TestAuditLogEndpoint:
    
    def test_requires_auth(self):
        """GET /api/licensing/audit-log requires auth."""
        resp = requests.get(f"{BASE_URL}/api/licensing/audit-log")
        assert resp.status_code == 401
    
    def test_returns_paginated_entries(self, headers):
        """GET /api/licensing/audit-log returns entries with total count."""
        resp = requests.get(f"{BASE_URL}/api/licensing/audit-log", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert isinstance(data["total"], int)
    
    def test_entries_have_correct_fields(self, headers):
        """Audit entries contain required fields."""
        resp = requests.get(f"{BASE_URL}/api/licensing/audit-log?limit=10", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        if data["entries"]:
            entry = data["entries"][0]
            assert "id" in entry
            assert "timestamp" in entry
            assert "action" in entry
            assert "actor" in entry
            # Optional fields
            assert "license_id" in entry
            assert "device_id" in entry
            assert "install_id" in entry
            assert "message" in entry
    
    def test_filter_by_action(self, headers):
        """GET /api/licensing/audit-log?action=X filters by action type."""
        resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=LICENSE_CHECK_SUCCESS",
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        # All returned entries should have the filtered action
        for entry in data["entries"]:
            assert entry["action"] == "LICENSE_CHECK_SUCCESS"
    
    def test_pagination_limit_offset(self, headers):
        """Audit log supports limit and offset params."""
        resp1 = requests.get(f"{BASE_URL}/api/licensing/audit-log?limit=5&offset=0", headers=headers)
        resp2 = requests.get(f"{BASE_URL}/api/licensing/audit-log?limit=5&offset=5", headers=headers)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        data1 = resp1.json()
        data2 = resp2.json()
        # Total should be same
        assert data1["total"] == data2["total"]
        # Entries should be different (if enough data)
        if data1["total"] > 5:
            ids1 = [e["id"] for e in data1["entries"]]
            ids2 = [e["id"] for e in data2["entries"]]
            # Should not overlap
            assert set(ids1).isdisjoint(set(ids2))


# ═══════════════════════════════════════════════════════════════
# Test 4: Audit Events Written on License Actions
# ═══════════════════════════════════════════════════════════════

class TestAuditEventsOnLicenseActions:
    
    def test_license_created_audit_event(self, headers):
        """LICENSE_CREATED audit event written when creating a license."""
        # First create a customer
        cust_resp = requests.post(f"{BASE_URL}/api/licensing/customers", headers=headers, json={
            "name": f"AuditTest Customer"
        })
        assert cust_resp.status_code == 200
        customer_id = cust_resp.json()["id"]
        
        # Create a license
        lic_resp = requests.post(f"{BASE_URL}/api/licensing/licenses", headers=headers, json={
            "customer_id": customer_id,
            "plan_type": "test"
        })
        assert lic_resp.status_code == 200
        license_id = lic_resp.json()["id"]
        
        # Check audit log for LICENSE_CREATED event
        audit_resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=LICENSE_CREATED&limit=5",
            headers=headers
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json()["entries"]
        # Should have at least one entry for our new license
        matching = [e for e in entries if e.get("license_id") == license_id]
        assert len(matching) >= 1, f"Expected LICENSE_CREATED audit for license {license_id}"
        assert matching[0]["action"] == "LICENSE_CREATED"
    
    def test_license_blocked_audit_event(self, headers):
        """LICENSE_BLOCKED audit event written when blocking a license."""
        # Get existing licenses
        lic_resp = requests.get(f"{BASE_URL}/api/licensing/licenses", headers=headers)
        licenses = lic_resp.json()
        
        # Find an active license to block
        active_lic = next((l for l in licenses if l["status"] == "active"), None)
        if not active_lic:
            pytest.skip("No active license to block")
        
        license_id = active_lic["id"]
        
        # Block the license
        block_resp = requests.post(
            f"{BASE_URL}/api/licensing/licenses/{license_id}/block",
            headers=headers
        )
        assert block_resp.status_code == 200
        
        # Check audit log for LICENSE_BLOCKED event
        audit_resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=LICENSE_BLOCKED&limit=5",
            headers=headers
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json()["entries"]
        matching = [e for e in entries if e.get("license_id") == license_id]
        assert len(matching) >= 1, f"Expected LICENSE_BLOCKED audit for license {license_id}"
        
        # Reactivate the license for cleanup
        requests.post(
            f"{BASE_URL}/api/licensing/licenses/{license_id}/activate",
            headers=headers
        )
    
    def test_license_activated_audit_event(self, headers):
        """LICENSE_ACTIVATED audit event written when activating a license."""
        # Get licenses
        lic_resp = requests.get(f"{BASE_URL}/api/licensing/licenses", headers=headers)
        licenses = lic_resp.json()
        
        # Find an active license to block then reactivate
        active_lic = next((l for l in licenses if l["status"] == "active"), None)
        if not active_lic:
            pytest.skip("No active license to test activate")
        
        license_id = active_lic["id"]
        
        # Block then activate
        requests.post(f"{BASE_URL}/api/licensing/licenses/{license_id}/block", headers=headers)
        activate_resp = requests.post(
            f"{BASE_URL}/api/licensing/licenses/{license_id}/activate",
            headers=headers
        )
        assert activate_resp.status_code == 200
        
        # Check audit log
        audit_resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=LICENSE_ACTIVATED&limit=5",
            headers=headers
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json()["entries"]
        matching = [e for e in entries if e.get("license_id") == license_id]
        assert len(matching) >= 1, f"Expected LICENSE_ACTIVATED audit for license {license_id}"
    
    def test_license_extended_audit_event(self, headers):
        """LICENSE_EXTENDED audit event written when extending a license."""
        # Get licenses
        lic_resp = requests.get(f"{BASE_URL}/api/licensing/licenses", headers=headers)
        licenses = lic_resp.json()
        
        if not licenses:
            pytest.skip("No licenses to extend")
        
        license_id = licenses[0]["id"]
        
        # Extend the license
        extend_resp = requests.post(
            f"{BASE_URL}/api/licensing/licenses/{license_id}/extend",
            headers=headers,
            json={"days": 7}
        )
        assert extend_resp.status_code == 200
        
        # Check audit log
        audit_resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=LICENSE_EXTENDED&limit=5",
            headers=headers
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json()["entries"]
        matching = [e for e in entries if e.get("license_id") == license_id]
        assert len(matching) >= 1, f"Expected LICENSE_EXTENDED audit for license {license_id}"


# ═══════════════════════════════════════════════════════════════
# Test 5: DEVICE_REBOUND Audit Event
# ═══════════════════════════════════════════════════════════════

class TestDeviceReboundAuditEvent:
    
    def test_device_rebound_audit_event(self, headers):
        """DEVICE_REBOUND audit event written when rebinding a device."""
        # Get devices
        dev_resp = requests.get(f"{BASE_URL}/api/licensing/devices", headers=headers)
        devices = dev_resp.json()
        
        if not devices:
            pytest.skip("No devices to rebind")
        
        # Find a bound device
        bound_device = next((d for d in devices if d.get("binding_status") == "bound"), None)
        if not bound_device:
            pytest.skip("No bound device to rebind")
        
        device_id = bound_device["id"]
        new_install_id = "test-rebind-" + device_id[:8]
        
        # Rebind the device
        rebind_resp = requests.post(
            f"{BASE_URL}/api/licensing/devices/{device_id}/rebind",
            headers=headers,
            json={"new_install_id": new_install_id}
        )
        assert rebind_resp.status_code == 200
        
        # Check audit log
        audit_resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=DEVICE_REBOUND&limit=5",
            headers=headers
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json()["entries"]
        matching = [e for e in entries if e.get("device_id") == device_id]
        assert len(matching) >= 1, f"Expected DEVICE_REBOUND audit for device {device_id}"


# ═══════════════════════════════════════════════════════════════
# Test 6: LICENSE_CHECK_SUCCESS from Cyclic Checker
# ═══════════════════════════════════════════════════════════════

class TestLicenseCheckAuditEvents:
    
    def test_license_check_success_on_startup(self, headers):
        """LICENSE_CHECK_SUCCESS written by cyclic checker on startup."""
        audit_resp = requests.get(
            f"{BASE_URL}/api/licensing/audit-log?action=LICENSE_CHECK_SUCCESS&limit=10",
            headers=headers
        )
        assert audit_resp.status_code == 200
        data = audit_resp.json()
        # Should have at least one check from startup
        assert data["total"] >= 1, "Expected at least one LICENSE_CHECK_SUCCESS from startup"
        
        # Verify entry has expected fields
        if data["entries"]:
            entry = data["entries"][0]
            assert entry["action"] == "LICENSE_CHECK_SUCCESS"
            assert "Cyclic check" in (entry.get("message") or "")


# ═══════════════════════════════════════════════════════════════
# Test 7: Regression — Existing License CRUD
# ═══════════════════════════════════════════════════════════════

class TestRegressionLicenseCRUD:
    
    def test_get_customers(self, headers):
        """GET /api/licensing/customers still works."""
        resp = requests.get(f"{BASE_URL}/api/licensing/customers", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    
    def test_get_locations(self, headers):
        """GET /api/licensing/locations still works."""
        resp = requests.get(f"{BASE_URL}/api/licensing/locations", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    
    def test_get_devices(self, headers):
        """GET /api/licensing/devices still works."""
        resp = requests.get(f"{BASE_URL}/api/licensing/devices", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    
    def test_get_licenses(self, headers):
        """GET /api/licensing/licenses still works."""
        resp = requests.get(f"{BASE_URL}/api/licensing/licenses", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    
    def test_get_dashboard(self, headers):
        """GET /api/licensing/dashboard still works."""
        resp = requests.get(f"{BASE_URL}/api/licensing/dashboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        assert "locations" in data
        assert "devices" in data
        assert "licenses_total" in data


# ═══════════════════════════════════════════════════════════════
# Test 8: Regression — Binding Settings Endpoint
# ═══════════════════════════════════════════════════════════════

class TestRegressionBindingSettings:
    
    def test_get_binding_settings(self, headers):
        """GET /api/licensing/binding-settings still works."""
        resp = requests.get(f"{BASE_URL}/api/licensing/binding-settings", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "binding_grace_hours" in data
    
    def test_post_binding_settings(self, headers):
        """POST /api/licensing/binding-settings still works."""
        # Get current value
        get_resp = requests.get(f"{BASE_URL}/api/licensing/binding-settings", headers=headers)
        current = get_resp.json()["binding_grace_hours"]
        
        # Update
        resp = requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=headers,
            json={"binding_grace_hours": 72}
        )
        assert resp.status_code == 200
        assert resp.json()["binding_grace_hours"] == 72
        
        # Restore
        requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=headers,
            json={"binding_grace_hours": current}
        )


# ═══════════════════════════════════════════════════════════════
# Test 9: Public Kiosk License Status (Regression)
# ═══════════════════════════════════════════════════════════════

class TestRegressionKioskLicenseStatus:
    
    def test_kiosk_license_status_public(self):
        """GET /api/kiosk/license-status is public (no auth required)."""
        resp = requests.get(f"{BASE_URL}/api/kiosk/license-status")
        # Should not be 401
        assert resp.status_code in [200, 400, 404, 500]
        # If 200, should have status field
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data
