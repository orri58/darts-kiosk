"""
Test Suite: Bulk Device Actions - Retry Failed Actions Feature (v3.9.6)

Tests:
1. Backend: POST /api/central/remote-actions/bulk accepts is_retry and retry_ref fields
2. Backend: Audit log includes [RETRY] prefix when is_retry=true
3. Backend: Dedup correctly returns 'skipped' status for duplicate actions within 30s window
4. Backend: 50 device limit still enforced for retry calls
5. Backend: RBAC still enforced for retry calls (owner+ required)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CENTRAL_API = f"{BASE_URL}/api/central"

class TestBulkRetryBackend:
    """Backend tests for Bulk Device Actions Retry feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as superadmin
        login_resp = self.session.post(f"{CENTRAL_API}/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get available devices
        devices_resp = self.session.get(f"{CENTRAL_API}/licensing/devices")
        assert devices_resp.status_code == 200
        self.devices = devices_resp.json()
        assert len(self.devices) > 0, "No devices available for testing"
        
        yield
        self.session.close()
    
    # ─── Test 1: is_retry and retry_ref fields accepted ───
    def test_bulk_accepts_is_retry_field(self):
        """POST /api/central/remote-actions/bulk accepts is_retry field"""
        device_id = self.devices[0]["id"]
        
        # First call - create action
        resp1 = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "reload_ui",
            "is_retry": False
        })
        assert resp1.status_code == 200, f"First bulk call failed: {resp1.text}"
        data1 = resp1.json()
        assert "is_retry" in data1, "Response should include is_retry field"
        assert data1["is_retry"] == False
        
        # Wait for dedup window to pass
        time.sleep(31)
        
        # Second call - with is_retry=true
        resp2 = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "reload_ui",
            "is_retry": True,
            "retry_ref": "2025-01-01T12:00:00.000Z"
        })
        assert resp2.status_code == 200, f"Retry bulk call failed: {resp2.text}"
        data2 = resp2.json()
        assert data2["is_retry"] == True, "is_retry should be True"
        assert data2["retry_ref"] == "2025-01-01T12:00:00.000Z", "retry_ref should be preserved"
        print("✓ Backend accepts is_retry and retry_ref fields")
    
    # ─── Test 2: Audit log includes [RETRY] prefix ───
    def test_audit_log_retry_prefix(self):
        """Audit log includes [RETRY] prefix when is_retry=true"""
        device_id = self.devices[0]["id"]
        
        # Make a retry call
        resp = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "reload_ui",
            "is_retry": True
        })
        # May be skipped due to dedup, but audit should still log
        assert resp.status_code == 200
        
        # Check audit log
        audit_resp = self.session.get(f"{CENTRAL_API}/licensing/audit-log?limit=10")
        assert audit_resp.status_code == 200
        audit_entries = audit_resp.json()
        
        # Find the retry entry
        retry_entries = [e for e in audit_entries if "[RETRY]" in (e.get("message") or "")]
        assert len(retry_entries) > 0, "Should have at least one [RETRY] audit entry"
        print(f"✓ Audit log contains [RETRY] prefix: {retry_entries[0]['message'][:80]}...")
    
    # ─── Test 3: Dedup returns 'skipped' within 30s window ───
    def test_dedup_returns_skipped_within_30s(self):
        """Dedup correctly returns 'skipped' status for duplicate actions within 30s window"""
        device_id = self.devices[0]["id"]
        
        # First call - should create
        resp1 = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "force_sync"  # Use different action type to avoid conflicts
        })
        assert resp1.status_code == 200
        data1 = resp1.json()
        
        # Immediate second call - should be skipped due to dedup
        resp2 = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "force_sync"
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        
        # Check that second call was skipped
        assert data2["skipped"] >= 1, f"Expected at least 1 skipped, got {data2['skipped']}"
        skipped_results = [r for r in data2["results"] if r["status"] == "skipped"]
        assert len(skipped_results) > 0, "Should have skipped results"
        assert "Bereits ausstehend" in skipped_results[0].get("message", ""), "Should have 'Bereits ausstehend' message"
        print(f"✓ Dedup correctly returns 'skipped' with message: {skipped_results[0]['message']}")
    
    # ─── Test 4: 50 device limit enforced for retry calls ───
    def test_50_device_limit_enforced_for_retry(self):
        """50 device limit still enforced for retry calls"""
        # Create 51 fake device IDs
        fake_ids = [f"fake-device-{i}" for i in range(51)]
        
        resp = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": fake_ids,
            "action_type": "reload_ui",
            "is_retry": True
        })
        assert resp.status_code == 400, f"Expected 400 for >50 devices, got {resp.status_code}"
        assert "50" in resp.text or "Maximal" in resp.text, "Error should mention 50 device limit"
        print("✓ 50 device limit enforced for retry calls")
    
    # ─── Test 5: RBAC enforced for retry calls ───
    def test_rbac_enforced_for_retry(self):
        """RBAC still enforced for retry calls (owner+ required)"""
        # Create a staff user (below owner level)
        staff_user = {
            "username": f"test_staff_{int(time.time())}",
            "password": "testpass123",
            "role": "staff",
            "display_name": "Test Staff"
        }
        create_resp = self.session.post(f"{CENTRAL_API}/users", json=staff_user)
        # May fail if user exists, that's ok
        
        # Login as staff user
        staff_session = requests.Session()
        staff_session.headers.update({"Content-Type": "application/json"})
        login_resp = staff_session.post(f"{CENTRAL_API}/auth/login", json={
            "username": staff_user["username"],
            "password": staff_user["password"]
        })
        
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            staff_session.headers.update({"Authorization": f"Bearer {token}"})
            
            # Try to make a retry call as staff
            device_id = self.devices[0]["id"]
            resp = staff_session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
                "device_ids": [device_id],
                "action_type": "reload_ui",
                "is_retry": True
            })
            assert resp.status_code == 403, f"Expected 403 for staff user, got {resp.status_code}"
            print("✓ RBAC enforced: staff user cannot make retry calls")
        else:
            # If we can't create/login as staff, test with no auth
            no_auth_session = requests.Session()
            no_auth_session.headers.update({"Content-Type": "application/json"})
            resp = no_auth_session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
                "device_ids": [self.devices[0]["id"]],
                "action_type": "reload_ui",
                "is_retry": True
            })
            assert resp.status_code in [401, 403], f"Expected 401/403 for unauthenticated, got {resp.status_code}"
            print("✓ RBAC enforced: unauthenticated user cannot make retry calls")
    
    # ─── Test 6: Empty device list rejected ───
    def test_empty_device_list_rejected(self):
        """Empty device list returns 400 error"""
        resp = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [],
            "action_type": "reload_ui",
            "is_retry": True
        })
        assert resp.status_code == 400, f"Expected 400 for empty device list, got {resp.status_code}"
        print("✓ Empty device list correctly rejected")
    
    # ─── Test 7: Invalid action type rejected ───
    def test_invalid_action_type_rejected(self):
        """Invalid action type returns 400 error"""
        device_id = self.devices[0]["id"]
        resp = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "invalid_action",
            "is_retry": True
        })
        assert resp.status_code == 400, f"Expected 400 for invalid action type, got {resp.status_code}"
        print("✓ Invalid action type correctly rejected")
    
    # ─── Test 8: Response includes all required fields ───
    def test_response_includes_all_fields(self):
        """Response includes action_type, total, created, skipped, denied, is_retry, retry_ref, results"""
        device_id = self.devices[0]["id"]
        
        # Wait for dedup window
        time.sleep(31)
        
        resp = self.session.post(f"{CENTRAL_API}/remote-actions/bulk", json={
            "device_ids": [device_id],
            "action_type": "restart_backend",
            "is_retry": True,
            "retry_ref": "test-ref-123"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        required_fields = ["action_type", "total", "created", "skipped", "denied", "is_retry", "retry_ref", "results"]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"
        
        assert data["action_type"] == "restart_backend"
        assert data["total"] == 1
        assert isinstance(data["results"], list)
        assert data["is_retry"] == True
        assert data["retry_ref"] == "test-ref-123"
        print("✓ Response includes all required fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
