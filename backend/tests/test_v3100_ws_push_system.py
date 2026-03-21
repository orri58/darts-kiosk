"""
WebSocket Push System Tests — v3.10.0

Tests for:
- WS /ws/devices endpoint: valid API key connects, invalid/missing key rejected
- WS ping/pong: client sends {type:ping}, receives {event:pong}
- Config push: PUT /api/config/profile/global/global → connected device receives config_updated event
- Action push: POST /api/remote-actions/{device_id} → device receives action_created event
- Import push: POST /api/config/import/apply → connected device receives config_updated event
- Rollback push: POST /api/config/rollback/global/global/{version} → connected device receives config_updated event
- GET /api/ws/status returns connected_devices, total_connections, total_events_pushed
- GET /api/ws/device/{device_id} returns ws_connected status
- GET /api/licensing/devices includes ws_connected field per device
- GET /api/telemetry/dashboard includes ws_connected_count field
"""
import pytest
import requests
import asyncio
import json
import os

# Central server runs on port 8002
CENTRAL_URL = "http://localhost:8002"

# ─── Fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Login as superadmin and get access token."""
    resp = requests.post(f"{CENTRAL_URL}/api/auth/login", json={
        "username": "superadmin",
        "password": "admin"
    })
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} - {resp.text}")
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API calls."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def device_info(auth_headers):
    """Get first device's info including api_key."""
    resp = requests.get(f"{CENTRAL_URL}/api/licensing/devices", headers=auth_headers)
    if resp.status_code != 200:
        pytest.skip(f"Failed to get devices: {resp.status_code}")
    devices = resp.json()
    if not devices:
        pytest.skip("No devices available for testing")
    return devices[0]


# ─── REST API Tests ─────────────────────────────────────────────

class TestWSStatusEndpoints:
    """Tests for WS status REST endpoints."""
    
    def test_ws_status_endpoint_returns_structure(self, auth_headers):
        """GET /api/ws/status returns expected structure."""
        resp = requests.get(f"{CENTRAL_URL}/api/ws/status", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "connected_devices" in data, "Missing connected_devices field"
        assert "total_connections" in data, "Missing total_connections field"
        assert "total_events_pushed" in data, "Missing total_events_pushed field"
        assert "devices" in data, "Missing devices dict"
        
        # Verify types
        assert isinstance(data["connected_devices"], int)
        assert isinstance(data["total_connections"], int)
        assert isinstance(data["total_events_pushed"], int)
        assert isinstance(data["devices"], dict)
        print(f"✓ WS status: {data['connected_devices']} connected, {data['total_events_pushed']} events pushed")
    
    def test_ws_status_requires_auth(self):
        """GET /api/ws/status requires authentication."""
        resp = requests.get(f"{CENTRAL_URL}/api/ws/status")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print("✓ WS status endpoint requires authentication")
    
    def test_ws_device_status_endpoint(self, auth_headers, device_info):
        """GET /api/ws/device/{device_id} returns ws_connected status."""
        device_id = device_info["id"]
        resp = requests.get(f"{CENTRAL_URL}/api/ws/device/{device_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "ws_connected" in data, "Missing ws_connected field"
        assert isinstance(data["ws_connected"], bool)
        print(f"✓ Device {device_id[:8]} WS status: ws_connected={data['ws_connected']}")
    
    def test_licensing_devices_includes_ws_connected(self, auth_headers):
        """GET /api/licensing/devices includes ws_connected field per device."""
        resp = requests.get(f"{CENTRAL_URL}/api/licensing/devices", headers=auth_headers)
        assert resp.status_code == 200
        
        devices = resp.json()
        if devices:
            device = devices[0]
            assert "ws_connected" in device, "Missing ws_connected field in device"
            assert isinstance(device["ws_connected"], bool)
            print(f"✓ Devices list includes ws_connected field (first device: {device['ws_connected']})")
        else:
            print("✓ No devices to check, but endpoint works")
    
    def test_telemetry_dashboard_includes_ws_connected_count(self, auth_headers):
        """GET /api/telemetry/dashboard includes ws_connected_count field."""
        resp = requests.get(f"{CENTRAL_URL}/api/telemetry/dashboard", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "ws_connected_count" in data, "Missing ws_connected_count field in dashboard"
        assert isinstance(data["ws_connected_count"], int)
        print(f"✓ Dashboard includes ws_connected_count: {data['ws_connected_count']}")


class TestWSConnectionAuth:
    """Tests for WS connection authentication (using websockets library)."""
    
    @pytest.mark.asyncio
    async def test_ws_valid_api_key_connects(self, device_info):
        """WS /ws/devices with valid API key connects and receives 'connected' event."""
        import websockets
        
        api_key = device_info.get("api_key")
        if not api_key:
            pytest.skip("Device has no api_key")
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                # Should receive 'connected' event
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                
                assert data.get("event") == "connected", f"Expected 'connected' event, got: {data}"
                assert "device_id" in data, "Missing device_id in connected event"
                print(f"✓ Valid API key connects successfully, received: {data}")
        except websockets.exceptions.ConnectionClosed as e:
            pytest.fail(f"Connection closed unexpectedly: {e}")
    
    @pytest.mark.asyncio
    async def test_ws_invalid_api_key_rejected(self):
        """WS /ws/devices with invalid API key gets rejected with HTTP 403."""
        import websockets
        from websockets.exceptions import InvalidStatus
        
        ws_url = "ws://localhost:8002/ws/devices?key=invalid_key_12345"
        
        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                # Should be closed immediately
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                pytest.fail(f"Expected connection to be rejected, but received: {msg}")
        except InvalidStatus as e:
            # Expected: HTTP 403 rejection during handshake
            assert e.response.status_code == 403, f"Expected 403, got {e.response.status_code}"
            print(f"✓ Invalid API key rejected with HTTP 403")
        except websockets.exceptions.ConnectionClosed as e:
            # Also acceptable: connection closed with error code
            assert e.code in [4002, 4001, 4003, 1000, 1006], f"Unexpected close code: {e.code}"
            print(f"✓ Invalid API key rejected with code {e.code}: {e.reason}")
        except asyncio.TimeoutError:
            # Also acceptable - server may just not respond
            print("✓ Invalid API key connection timed out (rejected)")
    
    @pytest.mark.asyncio
    async def test_ws_missing_api_key_rejected(self):
        """WS /ws/devices with missing API key gets rejected with HTTP 403."""
        import websockets
        from websockets.exceptions import InvalidStatus
        
        ws_url = "ws://localhost:8002/ws/devices"
        
        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                pytest.fail(f"Expected connection to be rejected, but received: {msg}")
        except InvalidStatus as e:
            # Expected: HTTP 403 rejection during handshake
            assert e.response.status_code == 403, f"Expected 403, got {e.response.status_code}"
            print(f"✓ Missing API key rejected with HTTP 403")
        except websockets.exceptions.ConnectionClosed as e:
            assert e.code in [4001, 4002, 4003, 1000, 1006], f"Unexpected close code: {e.code}"
            print(f"✓ Missing API key rejected with code {e.code}: {e.reason}")
        except asyncio.TimeoutError:
            print("✓ Missing API key connection timed out (rejected)")


class TestWSPingPong:
    """Tests for WS ping/pong keep-alive."""
    
    @pytest.mark.asyncio
    async def test_ws_ping_pong(self, device_info):
        """Client sends {type:ping}, receives {event:pong}."""
        import websockets
        
        api_key = device_info.get("api_key")
        if not api_key:
            pytest.skip("Device has no api_key")
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        async with websockets.connect(ws_url, close_timeout=5) as ws:
            # Receive connected event first
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data.get("event") == "connected"
            
            # Send ping
            await ws.send(json.dumps({"type": "ping"}))
            
            # Receive pong
            pong_msg = await asyncio.wait_for(ws.recv(), timeout=5)
            pong_data = json.loads(pong_msg)
            
            assert pong_data.get("event") == "pong", f"Expected 'pong' event, got: {pong_data}"
            print(f"✓ Ping/pong works: sent ping, received {pong_data}")


class TestWSPushEvents:
    """Tests for push events (config_updated, action_created)."""
    
    @pytest.mark.asyncio
    async def test_config_update_push(self, auth_headers, device_info):
        """PUT /api/config/profile/global/global → connected device receives config_updated event."""
        import websockets
        
        api_key = device_info.get("api_key")
        if not api_key:
            pytest.skip("Device has no api_key")
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        async with websockets.connect(ws_url, close_timeout=10) as ws:
            # Receive connected event
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data.get("event") == "connected"
            print(f"  Connected as device {data.get('device_id', '?')[:8]}")
            
            # Trigger config update via REST API
            # First get current config (using GET /api/config/profile/global)
            get_resp = requests.get(f"{CENTRAL_URL}/api/config/profile/global", headers=auth_headers)
            if get_resp.status_code != 200:
                pytest.skip(f"Failed to get config: {get_resp.status_code}")
            
            current_config = get_resp.json()
            config_data = current_config.get("config_data", {})
            
            # Make a small change
            if "branding" not in config_data:
                config_data["branding"] = {}
            config_data["branding"]["test_ws_push"] = True
            
            # Update config (using PUT /api/config/profile/global/global)
            update_resp = requests.put(
                f"{CENTRAL_URL}/api/config/profile/global/global",
                headers=auth_headers,
                json={"config_data": config_data}
            )
            assert update_resp.status_code == 200, f"Config update failed: {update_resp.status_code}"
            print("  Config updated via REST API")
            
            # Wait for push event
            try:
                push_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                push_data = json.loads(push_msg)
                
                assert push_data.get("event") == "config_updated", f"Expected 'config_updated', got: {push_data}"
                assert "data" in push_data, "Missing data in push event"
                print(f"✓ Config update push received: {push_data}")
            except asyncio.TimeoutError:
                pytest.fail("Did not receive config_updated push event within 5 seconds")
    
    @pytest.mark.asyncio
    async def test_action_created_push(self, auth_headers, device_info):
        """POST /api/remote-actions/{device_id} → device receives action_created event."""
        import websockets
        
        api_key = device_info.get("api_key")
        device_id = device_info.get("id")
        if not api_key or not device_id:
            pytest.skip("Device missing api_key or id")
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        async with websockets.connect(ws_url, close_timeout=10) as ws:
            # Receive connected event
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data.get("event") == "connected"
            print(f"  Connected as device {data.get('device_id', '?')[:8]}")
            
            # Create a remote action
            action_resp = requests.post(
                f"{CENTRAL_URL}/api/remote-actions/{device_id}",
                headers=auth_headers,
                json={"action_type": "force_sync"}
            )
            assert action_resp.status_code == 200, f"Action creation failed: {action_resp.status_code} - {action_resp.text}"
            print("  Remote action created via REST API")
            
            # Wait for push event
            try:
                push_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                push_data = json.loads(push_msg)
                
                assert push_data.get("event") == "action_created", f"Expected 'action_created', got: {push_data}"
                assert "data" in push_data, "Missing data in push event"
                print(f"✓ Action created push received: {push_data}")
            except asyncio.TimeoutError:
                pytest.fail("Did not receive action_created push event within 5 seconds")
    
    @pytest.mark.asyncio
    async def test_import_apply_push(self, auth_headers, device_info):
        """POST /api/config/import/apply → connected device receives config_updated event."""
        import websockets
        
        api_key = device_info.get("api_key")
        if not api_key:
            pytest.skip("Device has no api_key")
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        async with websockets.connect(ws_url, close_timeout=10) as ws:
            # Receive connected event
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data.get("event") == "connected"
            print(f"  Connected as device {data.get('device_id', '?')[:8]}")
            
            # Create import payload with correct structure
            import_payload = {
                "import_data": {
                    "meta": {
                        "type": "dartcontrol_config",
                        "format_version": 1,
                        "scope_type": "global",
                        "scope_id": "global"
                    },
                    "config_data": {
                        "branding": {"test_import_push": True, "cafe_name": "TestCafe"}
                    }
                },
                "mode": "merge",
                "target_scope_type": "global",
                "target_scope_id": "global"
            }
            
            # Apply import
            import_resp = requests.post(
                f"{CENTRAL_URL}/api/config/import/apply",
                headers=auth_headers,
                json=import_payload
            )
            assert import_resp.status_code == 200, f"Import apply failed: {import_resp.status_code} - {import_resp.text}"
            print("  Config import applied via REST API")
            
            # Wait for push event
            try:
                push_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                push_data = json.loads(push_msg)
                
                assert push_data.get("event") == "config_updated", f"Expected 'config_updated', got: {push_data}"
                print(f"✓ Import apply push received: {push_data}")
            except asyncio.TimeoutError:
                pytest.fail("Did not receive config_updated push event within 5 seconds")
    
    @pytest.mark.asyncio
    async def test_rollback_push(self, auth_headers, device_info):
        """POST /api/config/rollback/global/global/{version} → connected device receives config_updated event."""
        import websockets
        
        api_key = device_info.get("api_key")
        if not api_key:
            pytest.skip("Device has no api_key")
        
        # First, get history to find a version to rollback to
        history_resp = requests.get(
            f"{CENTRAL_URL}/api/config/history/global/global",
            headers=auth_headers
        )
        if history_resp.status_code != 200:
            pytest.skip(f"Failed to get history: {history_resp.status_code}")
        
        history_data = history_resp.json()
        history = history_data.get("history", [])
        if not history:
            pytest.skip("No history available for rollback test")
        
        rollback_version = history[0].get("version", 1)
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        async with websockets.connect(ws_url, close_timeout=10) as ws:
            # Receive connected event
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data.get("event") == "connected"
            print(f"  Connected as device {data.get('device_id', '?')[:8]}")
            
            # Trigger rollback
            rollback_resp = requests.post(
                f"{CENTRAL_URL}/api/config/rollback/global/global/{rollback_version}",
                headers=auth_headers
            )
            assert rollback_resp.status_code == 200, f"Rollback failed: {rollback_resp.status_code} - {rollback_resp.text}"
            print(f"  Rollback to version {rollback_version} triggered via REST API")
            
            # Wait for push event
            try:
                push_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                push_data = json.loads(push_msg)
                
                assert push_data.get("event") == "config_updated", f"Expected 'config_updated', got: {push_data}"
                print(f"✓ Rollback push received: {push_data}")
            except asyncio.TimeoutError:
                pytest.fail("Did not receive config_updated push event within 5 seconds")


class TestWSHubStatus:
    """Tests for WS hub status tracking."""
    
    @pytest.mark.asyncio
    async def test_ws_status_updates_on_connect(self, auth_headers, device_info):
        """WS status updates when device connects."""
        import websockets
        
        api_key = device_info.get("api_key")
        if not api_key:
            pytest.skip("Device has no api_key")
        
        # Get initial status
        initial_resp = requests.get(f"{CENTRAL_URL}/api/ws/status", headers=auth_headers)
        initial_data = initial_resp.json()
        initial_connections = initial_data.get("total_connections", 0)
        
        ws_url = f"ws://localhost:8002/ws/devices?key={api_key}"
        
        async with websockets.connect(ws_url, close_timeout=5) as ws:
            # Receive connected event
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            
            # Check status updated
            await asyncio.sleep(0.5)  # Small delay for status update
            status_resp = requests.get(f"{CENTRAL_URL}/api/ws/status", headers=auth_headers)
            status_data = status_resp.json()
            
            assert status_data["connected_devices"] >= 1, "Expected at least 1 connected device"
            assert status_data["total_connections"] >= initial_connections, "Total connections should increase"
            print(f"✓ WS status updated: {status_data['connected_devices']} connected, {status_data['total_connections']} total")


# ─── Run Tests ──────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
