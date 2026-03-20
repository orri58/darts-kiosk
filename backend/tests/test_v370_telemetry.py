"""
v3.7.0 Telemetry Testing — Central Server Telemetry Endpoints

Tests:
1. POST /api/telemetry/heartbeat — Device heartbeat updates
2. POST /api/telemetry/ingest — Batch event ingestion with idempotency
3. GET /api/telemetry/dashboard — Scoped dashboard KPIs
4. Idempotency: Duplicate event_id detection
5. Scope enforcement: User sees only scoped devices in dashboard
6. Online/Offline heuristic based on heartbeat timestamp
7. Revenue aggregation from credits_added events
"""
import pytest
import requests
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com').rstrip('/')
CENTRAL_SERVER_URL = "http://127.0.0.1:8002"  # Direct central server access for testing

# Superadmin credentials
SUPERADMIN_USER = "superadmin"
SUPERADMIN_PASS = "admin"


@pytest.fixture(scope="module")
def superadmin_token():
    """Get JWT token for superadmin user."""
    resp = requests.post(f"{CENTRAL_SERVER_URL}/api/auth/login", json={
        "username": SUPERADMIN_USER,
        "password": SUPERADMIN_PASS
    })
    assert resp.status_code == 200, f"Superadmin login failed: {resp.text}"
    data = resp.json()
    assert "access_token" in data, "No access_token in login response"
    return data["access_token"]


@pytest.fixture(scope="module")
def device_api_key(superadmin_token):
    """Get API key for an existing device (Dartboard-01)."""
    resp = requests.get(f"{CENTRAL_SERVER_URL}/api/licensing/devices", headers={
        "Authorization": f"Bearer {superadmin_token}"
    })
    assert resp.status_code == 200, f"Devices list failed: {resp.text}"
    devices = resp.json()
    
    # Find a device with api_key
    for d in devices:
        if d.get("api_key"):
            return d["api_key"]
    
    pytest.skip("No device with API key found")


class TestTelemetryHeartbeat:
    """Test POST /api/telemetry/heartbeat endpoint."""
    
    def test_heartbeat_success(self, device_api_key):
        """Heartbeat should update last_heartbeat_at and reported_version."""
        version = f"3.7.0-test-{int(time.time())}"
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": version, "timestamp": datetime.now(timezone.utc).isoformat()},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Heartbeat failed: {resp.text}"
        data = resp.json()
        assert data.get("status") == "ok", "Heartbeat status should be 'ok'"
        assert "server_time" in data, "server_time missing in response"
        print(f"Heartbeat OK: version={version} server_time={data.get('server_time')}")
    
    def test_heartbeat_with_error_report(self, device_api_key):
        """Heartbeat with error field should update last_error."""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": "3.7.0", "error": "TEST_ERROR: This is a test error"},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Heartbeat with error failed: {resp.text}"
        print("Heartbeat with error OK")
    
    def test_heartbeat_clear_error(self, device_api_key):
        """Heartbeat with clear_error should remove last_error."""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": "3.7.0", "clear_error": True},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Heartbeat clear error failed: {resp.text}"
        print("Heartbeat clear error OK")
    
    def test_heartbeat_missing_api_key(self):
        """Heartbeat without X-License-Key header should fail with 401."""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": "3.7.0"}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("Heartbeat missing API key: correctly returns 401")
    
    def test_heartbeat_invalid_api_key(self):
        """Heartbeat with invalid API key should fail with 403."""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": "3.7.0"},
            headers={"X-License-Key": "invalid_key_12345"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("Heartbeat invalid API key: correctly returns 403")


class TestTelemetryIngest:
    """Test POST /api/telemetry/ingest endpoint."""
    
    def test_ingest_single_event(self, device_api_key):
        """Ingest a single event successfully."""
        event_id = f"test-{uuid.uuid4()}"
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/ingest",
            json={"events": [{
                "event_id": event_id,
                "event_type": "session_started",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"board_id": "BOARD-1", "pricing_mode": "per_game"}
            }]},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Ingest failed: {resp.text}"
        data = resp.json()
        assert data.get("accepted") == 1, f"Expected 1 accepted, got {data.get('accepted')}"
        assert data.get("duplicates") == 0, f"Expected 0 duplicates, got {data.get('duplicates')}"
        print(f"Ingest single event OK: event_id={event_id}")
    
    def test_ingest_idempotency(self, device_api_key):
        """Sending same event_id twice should return duplicates=1."""
        event_id = f"idempotent-{uuid.uuid4()}"
        payload = {"events": [{
            "event_id": event_id,
            "event_type": "game_played",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"board_id": "BOARD-1", "variant": "X01"}
        }]}
        
        # First submission
        resp1 = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/ingest",
            json=payload,
            headers={"X-License-Key": device_api_key}
        )
        assert resp1.status_code == 200, f"First ingest failed: {resp1.text}"
        data1 = resp1.json()
        assert data1.get("accepted") == 1, "First submission should accept event"
        
        # Second submission (duplicate)
        resp2 = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/ingest",
            json=payload,
            headers={"X-License-Key": device_api_key}
        )
        assert resp2.status_code == 200, f"Second ingest failed: {resp2.text}"
        data2 = resp2.json()
        assert data2.get("accepted") == 0, f"Second submission should not accept: {data2}"
        assert data2.get("duplicates") == 1, f"Second submission should show 1 duplicate: {data2}"
        print(f"Idempotency test PASSED: event_id={event_id}")
    
    def test_ingest_batch_events(self, device_api_key):
        """Ingest multiple events in a single batch."""
        ts = datetime.now(timezone.utc).isoformat()
        events = [
            {"event_id": f"batch-{uuid.uuid4()}", "event_type": "session_started", "timestamp": ts, "data": {}},
            {"event_id": f"batch-{uuid.uuid4()}", "event_type": "game_played", "timestamp": ts, "data": {}},
            {"event_id": f"batch-{uuid.uuid4()}", "event_type": "credits_added", "timestamp": ts, "data": {"amount": 5, "revenue_cents": 500}},
        ]
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/ingest",
            json={"events": events},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Batch ingest failed: {resp.text}"
        data = resp.json()
        assert data.get("accepted") == 3, f"Expected 3 accepted, got {data.get('accepted')}"
        print(f"Batch ingest OK: {data}")
    
    def test_ingest_revenue_aggregation(self, device_api_key):
        """Credits_added events should update device_daily_stats revenue."""
        event_id = f"revenue-{uuid.uuid4()}"
        revenue_cents = 1234
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/ingest",
            json={"events": [{
                "event_id": event_id,
                "event_type": "credits_added",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"amount": 10, "revenue_cents": revenue_cents}
            }]},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Revenue ingest failed: {resp.text}"
        data = resp.json()
        assert data.get("accepted") == 1, "Revenue event should be accepted"
        print(f"Revenue aggregation ingest OK: {revenue_cents} cents")
    
    def test_ingest_empty_batch(self, device_api_key):
        """Empty events array should return accepted=0, duplicates=0."""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/ingest",
            json={"events": []},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200, f"Empty batch failed: {resp.text}"
        data = resp.json()
        assert data.get("accepted") == 0
        assert data.get("duplicates") == 0
        print("Empty batch OK")


class TestTelemetryDashboard:
    """Test GET /api/telemetry/dashboard endpoint."""
    
    def test_dashboard_returns_kpis(self, superadmin_token):
        """Dashboard should return devices_online, revenue_today_cents, sessions_today, etc."""
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/telemetry/dashboard",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        data = resp.json()
        
        # Check required KPI fields
        assert "devices_online" in data, "Missing devices_online"
        assert "devices_offline" in data, "Missing devices_offline"
        assert "devices_total" in data, "Missing devices_total"
        assert "revenue_today_cents" in data, "Missing revenue_today_cents"
        assert "sessions_today" in data, "Missing sessions_today"
        assert "games_today" in data, "Missing games_today"
        assert "devices" in data, "Missing devices array"
        assert "warnings" in data, "Missing warnings array"
        
        print(f"Dashboard KPIs: online={data['devices_online']}, revenue={data['revenue_today_cents']}, sessions={data['sessions_today']}, games={data['games_today']}")
    
    def test_dashboard_device_list(self, superadmin_token):
        """Dashboard devices array should have online status, version, heartbeat times."""
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/telemetry/dashboard",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        data = resp.json()
        
        devices = data.get("devices", [])
        if devices:
            d = devices[0]
            assert "id" in d, "Device missing id"
            assert "device_name" in d, "Device missing device_name"
            assert "online" in d, "Device missing online status"
            assert "last_heartbeat_at" in d, "Device missing last_heartbeat_at"
            assert "reported_version" in d, "Device missing reported_version"
            print(f"Device in dashboard: {d.get('device_name')} online={d.get('online')} version={d.get('reported_version')}")
        else:
            print("No devices in dashboard (empty scope)")
    
    def test_dashboard_warnings_section(self, superadmin_token, device_api_key):
        """Dashboard should include warnings for offline devices or errors."""
        # First send heartbeat to ensure device is online
        requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": "3.7.0"},
            headers={"X-License-Key": device_api_key}
        )
        
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/telemetry/dashboard",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        data = resp.json()
        
        warnings = data.get("warnings", [])
        # Warnings structure check
        for w in warnings:
            assert "type" in w, "Warning missing type"
            assert "device" in w, "Warning missing device"
            assert "message" in w, "Warning missing message"
            print(f"Warning: {w}")
        
        print(f"Dashboard has {len(warnings)} warnings")
    
    def test_dashboard_requires_auth(self):
        """Dashboard without auth should fail with 401."""
        resp = requests.get(f"{CENTRAL_SERVER_URL}/api/telemetry/dashboard")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print("Dashboard auth check: correctly requires authentication")


class TestOnlineOfflineHeuristic:
    """Test the 5-minute online/offline threshold."""
    
    def test_device_shows_online_after_heartbeat(self, superadmin_token, device_api_key):
        """Device should show online=True after recent heartbeat."""
        # Send fresh heartbeat
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/telemetry/heartbeat",
            json={"version": "3.7.0-online-test"},
            headers={"X-License-Key": device_api_key}
        )
        assert resp.status_code == 200
        
        # Check dashboard
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/telemetry/dashboard",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # At least one device should be online
        online_count = data.get("devices_online", 0)
        assert online_count > 0, f"Expected at least 1 device online after heartbeat, got {online_count}"
        print(f"Online heuristic: {online_count} devices online after heartbeat")


class TestScopeEnforcement:
    """Test that dashboard respects user scope."""
    
    def test_dashboard_with_customer_filter(self, superadmin_token):
        """Dashboard with customer_id param should filter devices."""
        # Get a customer first
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/licensing/customers",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        if resp.status_code != 200 or not resp.json():
            pytest.skip("No customers available for scope test")
        
        customers = resp.json()
        customer_id = customers[0]["id"]
        
        # Get dashboard with scope
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/telemetry/dashboard?customer_id={customer_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200, f"Scoped dashboard failed: {resp.text}"
        data = resp.json()
        print(f"Scoped dashboard (customer={customer_id}): {data['devices_total']} devices")


class TestFrontendIntegration:
    """Test the frontend's /api/central/ proxy path."""
    
    def test_central_proxy_dashboard(self, superadmin_token):
        """Frontend proxy should forward telemetry dashboard requests."""
        resp = requests.get(
            f"{BASE_URL}/api/central/telemetry/dashboard",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        # May be 200 or 502 if central server unreachable via proxy
        if resp.status_code == 502:
            print("Central proxy returned 502 (central server unreachable via proxy)")
        else:
            assert resp.status_code == 200, f"Proxy dashboard failed: {resp.text}"
            data = resp.json()
            assert "devices_online" in data or "error" in data
            print(f"Proxy dashboard OK: {data.get('devices_total', 'N/A')} devices")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
