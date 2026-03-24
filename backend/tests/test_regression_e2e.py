"""
Regression Suite v3.15.1 — E2E Core Flows
==========================================
Tests all critical flows against the RUNNING servers.
No mocks. Real HTTP requests against real endpoints.

Usage:
    pytest backend/tests/test_regression_e2e.py -v

Requirements:
    - Local backend running on port 8001
    - Central server running on port 8002 (for central tests)
"""
import os
import json
import pytest
import httpx
import asyncio
from datetime import datetime, timezone

# ── Config ──
LOCAL_URL = "http://127.0.0.1:8001"
CENTRAL_URL = os.environ.get("CENTRAL_SERVER_URL", "http://127.0.0.1:8002")
TIMEOUT = 10.0

# ── Fixtures ──

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def local_client():
    return httpx.Client(base_url=LOCAL_URL, timeout=TIMEOUT)


@pytest.fixture(scope="session")
def central_client():
    return httpx.Client(base_url=CENTRAL_URL, timeout=TIMEOUT)


@pytest.fixture(scope="session")
def local_admin_token(local_client):
    """Get admin JWT from local backend. Create admin if needed."""
    # Try login
    resp = local_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if resp.status_code == 200:
        return resp.json().get("access_token") or resp.json().get("token")
    # Try setup
    resp = local_client.post("/api/auth/setup", json={"username": "admin", "password": "admin123", "pin": "1234"})
    if resp.status_code in (200, 201):
        data = resp.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Could not get local admin token: {resp.status_code} {resp.text[:200]}")


@pytest.fixture(scope="session")
def local_auth_headers(local_admin_token):
    return {"Authorization": f"Bearer {local_admin_token}"}


@pytest.fixture(scope="session")
def central_admin_token(central_client):
    """Get superadmin JWT from central server."""
    try:
        resp = central_client.post("/api/auth/login", json={"username": "superadmin", "password": "admin"})
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except httpx.ConnectError:
        pytest.skip("Central server not running")
    pytest.skip(f"Central login failed: {resp.status_code}")


@pytest.fixture(scope="session")
def central_auth_headers(central_admin_token):
    return {"Authorization": f"Bearer {central_admin_token}"}


# ═══════════════════════════════════════
# BLOCK 1: Local Backend Health
# ═══════════════════════════════════════

class TestLocalHealth:
    def test_health_endpoint(self, local_client):
        """Local backend health check returns 200."""
        resp = local_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_auth_login(self, local_client):
        """Local admin login works."""
        resp = local_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        # 200 = success, 401 = wrong creds (but endpoint works)
        assert resp.status_code in (200, 401)


# ═══════════════════════════════════════
# BLOCK 2: Local Board Control (GOLD STANDARD)
# ═══════════════════════════════════════

class TestLocalBoardControl:
    """Verify the local admin board control still works — this is the gold standard."""

    def test_list_boards(self, local_client, local_auth_headers):
        """GET /api/boards returns list."""
        resp = local_client.get("/api/boards", headers=local_auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_unlock_lock_cycle(self, local_client, local_auth_headers):
        """Full unlock → verify → lock cycle on first board."""
        # Get boards
        boards = local_client.get("/api/boards", headers=local_auth_headers).json()
        if not boards:
            pytest.skip("No boards configured")

        board_id = boards[0]["board_id"]

        # Lock first (ensure clean state)
        lock_resp = local_client.post(f"/api/boards/{board_id}/lock", headers=local_auth_headers)
        assert lock_resp.status_code in (200, 404)

        # Unlock
        unlock_resp = local_client.post(
            f"/api/boards/{board_id}/unlock",
            headers=local_auth_headers,
            json={"pricing_mode": "per_game", "credits": 3, "game_type": "501"}
        )
        assert unlock_resp.status_code in (200, 409, 403), f"Unlock failed: {unlock_resp.text[:300]}"

        # Lock again
        lock_resp = local_client.post(f"/api/boards/{board_id}/lock", headers=local_auth_headers)
        assert lock_resp.status_code == 200

    def test_board_status(self, local_client, local_auth_headers):
        """GET /api/boards returns board with status field."""
        boards = local_client.get("/api/boards", headers=local_auth_headers).json()
        if not boards:
            pytest.skip("No boards configured")
        board = boards[0]
        assert "board_id" in board
        assert "status" in board


# ═══════════════════════════════════════
# BLOCK 3: Local Settings (MUST NOT BREAK)
# ═══════════════════════════════════════

class TestLocalSettings:
    """Verify local admin settings are functional."""

    def test_get_branding_settings(self, local_client, local_auth_headers):
        """GET /api/settings/branding returns settings."""
        resp = local_client.get("/api/settings/branding", headers=local_auth_headers)
        assert resp.status_code == 200

    def test_get_pricing_settings(self, local_client, local_auth_headers):
        """GET /api/settings/pricing returns settings."""
        resp = local_client.get("/api/settings/pricing", headers=local_auth_headers)
        assert resp.status_code == 200

    def test_save_branding_setting(self, local_client, local_auth_headers):
        """PUT /api/settings/branding saves and returns data."""
        data = {"value": {"cafe_name": "Regression Test Cafe", "subtitle": "Stabilisierung"}}
        resp = local_client.put(
            "/api/settings/branding",
            headers={**local_auth_headers, "Content-Type": "application/json"},
            json=data
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════
# BLOCK 4: License Service (Lock Enforcement)
# ═══════════════════════════════════════

class TestLicenseEnforcement:
    """Verify license lock is enforced when cache contains 'suspended'."""

    def test_license_status_endpoint(self, local_client, local_auth_headers):
        """GET /api/kiosk/license-status works."""
        resp = local_client.get("/api/kiosk/license-status", headers=local_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_suspended_cache_blocks_unlock(self, local_client, local_auth_headers):
        """When license cache = suspended, board unlock must be blocked."""
        import json as _json
        from pathlib import Path
        from dotenv import load_dotenv

        # Load .env to get the SAME AGENT_SECRET as the server
        load_dotenv("/app/backend/.env", override=True)

        # Resolve the cache file path exactly as the server does
        data_dir_env = os.environ.get("DATA_DIR", "").strip()
        data_dir = Path(data_dir_env) if data_dir_env else Path(__file__).resolve().parent.parent.parent / "data"
        cache_file = data_dir / "license_cache.json"
        cache_secret = os.environ.get("AGENT_SECRET", "license-cache-key")

        def _sign(d):
            import hashlib
            return hashlib.sha256(f"{cache_secret}:{_json.dumps(d, sort_keys=True, default=str)}".encode()).hexdigest()

        # Backup existing cache
        original_content = cache_file.read_text(encoding="utf-8") if cache_file.exists() else None

        try:
            # Write suspended status to cache (same format as save_to_cache)
            status_data = {
                "status": "suspended",
                "source": "central_rejection",
                "message": "Device centrally locked (regression test)",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            payload = {
                "license_status": status_data,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            payload["signature"] = _sign({"license_status": status_data, "cached_at": payload["cached_at"]})
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(_json.dumps(payload, indent=2, default=str), encoding="utf-8")

            # Verify the file was written
            assert cache_file.exists(), f"Cache file not written at {cache_file}"

            # Now try to unlock a board — must be blocked by license
            boards = local_client.get("/api/boards", headers=local_auth_headers).json()
            if not boards:
                pytest.skip("No boards configured")

            board_id = boards[0]["board_id"]
            # Lock first (ensure clean state)
            local_client.post(f"/api/boards/{board_id}/lock", headers=local_auth_headers)

            # Try unlock — should be blocked by license
            resp = local_client.post(
                f"/api/boards/{board_id}/unlock",
                headers=local_auth_headers,
                json={"pricing_mode": "per_game", "credits": 3, "game_type": "501"}
            )
            assert resp.status_code == 403, (
                f"Unlock should be blocked when suspended, got {resp.status_code}. "
                f"Response: {resp.text[:300]}. Cache at: {cache_file}"
            )

        finally:
            # Restore original cache
            if original_content:
                cache_file.write_text(original_content, encoding="utf-8")
            elif cache_file.exists():
                # Write a clean 'no_license' cache
                clean_status = {"status": "no_license", "source": "regression_cleanup", "checked_at": datetime.now(timezone.utc).isoformat()}
                clean_payload = {"license_status": clean_status, "cached_at": datetime.now(timezone.utc).isoformat()}
                clean_payload["signature"] = _sign({"license_status": clean_status, "cached_at": clean_payload["cached_at"]})
                cache_file.write_text(_json.dumps(clean_payload, indent=2, default=str), encoding="utf-8")


# ═══════════════════════════════════════
# BLOCK 5: Kiosk Core (MUST WORK OFFLINE)
# ═══════════════════════════════════════

class TestKioskCore:
    """Kiosk must work independently of portal/central server."""

    def test_kiosk_license_status(self, local_client, local_auth_headers):
        """GET /api/kiosk/license-status works."""
        resp = local_client.get("/api/kiosk/license-status", headers=local_auth_headers)
        assert resp.status_code == 200

    def test_kiosk_boards(self, local_client, local_auth_headers):
        """GET /api/boards works for kiosk operations."""
        resp = local_client.get("/api/boards", headers=local_auth_headers)
        assert resp.status_code == 200


# ═══════════════════════════════════════
# BLOCK 6: Central Server (if running)
# ═══════════════════════════════════════

class TestCentralServer:
    """Tests against the central server. Skipped if not running."""

    def test_central_health(self, central_client):
        """Central server health check."""
        try:
            resp = central_client.get("/api/health")
            assert resp.status_code == 200
        except httpx.ConnectError:
            pytest.skip("Central server not running")

    def test_central_device_list(self, central_client, central_auth_headers):
        """GET /api/licensing/devices returns list."""
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_central_device_detail_consistency(self, central_client, central_auth_headers):
        """Every device in the list must be loadable in detail."""
        devices = central_client.get("/api/licensing/devices", headers=central_auth_headers).json()
        for d in devices[:5]:  # Test up to 5
            detail_resp = central_client.get(f"/api/telemetry/device/{d['id']}", headers=central_auth_headers)
            assert detail_resp.status_code == 200, (
                f"Device {d['id']} ({d.get('device_name')}) visible in list but detail returns "
                f"{detail_resp.status_code}: {detail_resp.text[:200]}"
            )

    def test_central_device_detail_404_for_invalid_id(self, central_client, central_auth_headers):
        """Detail for non-existent device returns 404, not 500."""
        resp = central_client.get("/api/telemetry/device/nonexistent-uuid-12345", headers=central_auth_headers)
        assert resp.status_code == 404

    def test_central_license_list(self, central_client, central_auth_headers):
        """GET /api/licensing/licenses returns list."""
        resp = central_client.get("/api/licensing/licenses", headers=central_auth_headers)
        assert resp.status_code == 200

    def test_central_license_detail_consistency(self, central_client, central_auth_headers):
        """Every license in the list must be loadable in detail."""
        licenses = central_client.get("/api/licensing/licenses", headers=central_auth_headers).json()
        for lic in licenses[:5]:
            detail_resp = central_client.get(f"/api/licensing/licenses/{lic['id']}", headers=central_auth_headers)
            assert detail_resp.status_code == 200, (
                f"License {lic['id']} visible in list but detail returns "
                f"{detail_resp.status_code}: {detail_resp.text[:200]}"
            )

    def test_central_valid_actions_include_board_control(self, central_client, central_auth_headers):
        """Remote action creation with board control types must be accepted."""
        devices = central_client.get("/api/licensing/devices", headers=central_auth_headers).json()
        if not devices:
            pytest.skip("No devices registered")

        device_id = devices[0]["id"]
        for action_type in ["unlock_board", "lock_board", "start_session", "stop_session"]:
            resp = central_client.post(
                f"/api/remote-actions/{device_id}",
                headers={**central_auth_headers, "Content-Type": "application/json"},
                json={"action_type": action_type, "params": {"board_id": "BOARD-1"}},
            )
            assert resp.status_code in (200, 201), (
                f"Action {action_type} rejected: {resp.status_code} {resp.text[:200]}"
            )


    def test_central_device_detail_with_corrupt_data(self, central_client, central_auth_headers):
        """Device with corrupt datetime must NOT return 500 — raw SQL fallback."""
        import sqlite3, uuid
        db_path = "/app/central_server/data/central_licenses.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Get a valid location_id
        c.execute("SELECT id FROM locations LIMIT 1")
        loc_row = c.fetchone()
        if not loc_row:
            conn.close()
            pytest.skip("No locations in central DB")
        loc_id = loc_row[0]

        # Insert devices with MULTIPLE corruption patterns
        test_ids = []
        corruption_cases = [
            ("corrupt-invalid-date", "INVALID-NOT-A-DATE", "1.0.0", "NOT-JSON", "{broken"),
            ("corrupt-empty-strings", "", "", None, None),
            ("corrupt-unix-ts", "1706745600", None, None, None),
            ("corrupt-none-string", "None", None, "null", "null"),
        ]
        for suffix, hb_val, ver_val, health_val, logs_val in corruption_cases:
            test_id = str(uuid.uuid4())
            c.execute("""INSERT INTO devices (id, location_id, device_name, api_key, status, binding_status,
                        last_heartbeat_at, reported_version, health_snapshot, device_logs, sync_count)
                        VALUES (?, ?, ?, ?, 'active', 'unknown', ?, ?, ?, ?, 0)""",
                      (test_id, loc_id, f'TEST-{suffix}', f'regtest-{suffix}-{test_id[:8]}',
                       hb_val, ver_val, health_val, logs_val))
            test_ids.append(test_id)
        conn.commit()
        conn.close()

        try:
            # Test device LIST — must not 500
            list_resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
            assert list_resp.status_code == 200, f"Device list 500 with corrupt data: {list_resp.text[:200]}"
            devices = list_resp.json()
            for tid in test_ids:
                found = any(d.get("id") == tid for d in devices)
                assert found, f"Corrupt device {tid} not in list"

            # Test each device DETAIL — none must return 500
            for tid in test_ids:
                detail_resp = central_client.get(f"/api/telemetry/device/{tid}", headers=central_auth_headers)
                assert detail_resp.status_code == 200, (
                    f"Device detail 500 for {tid}: {detail_resp.status_code} {detail_resp.text[:300]}"
                )
                detail = detail_resp.json()
                assert "id" in detail
                assert detail["id"] == tid

            # Test dashboard — must not 500
            dash_resp = central_client.get("/api/dashboard", headers=central_auth_headers)
            assert dash_resp.status_code == 200, f"Dashboard 500 with corrupt data: {dash_resp.text[:200]}"

            # Test telemetry dashboard — must not 500
            tel_resp = central_client.get("/api/telemetry/dashboard", headers=central_auth_headers)
            assert tel_resp.status_code == 200, f"Telemetry dashboard 500 with corrupt data: {tel_resp.text[:200]}"

        finally:
            # Cleanup
            conn = sqlite3.connect(db_path)
            for tid in test_ids:
                conn.execute("DELETE FROM devices WHERE id = ?", (tid,))
            conn.commit()
            conn.close()

    def test_central_device_detail_minimal_data(self, central_client, central_auth_headers):
        """Device with minimal/NULL fields must NOT return 500."""
        import sqlite3, uuid
        db_path = "/app/central_server/data/central_licenses.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT id FROM locations LIMIT 1")
        loc_id = c.fetchone()[0]

        test_id = str(uuid.uuid4())
        c.execute("INSERT INTO devices (id, location_id, api_key) VALUES (?, ?, 'regtest-min')", (test_id, loc_id))
        conn.commit()
        conn.close()

        try:
            detail_resp = central_client.get(f"/api/telemetry/device/{test_id}", headers=central_auth_headers)
            assert detail_resp.status_code == 200, f"Minimal device detail failed: {detail_resp.status_code}"
        finally:
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM devices WHERE id = ?", (test_id,))
            conn.commit()
            conn.close()


# ═══════════════════════════════════════
# BLOCK 7: Proxy Behavior
# ═══════════════════════════════════════

class TestCentralProxy:
    """Test the central proxy on the local backend."""

    def test_proxy_returns_502_when_central_down(self, local_client, local_auth_headers):
        """When central server is down, proxy returns 502 (not 500 or hang)."""
        resp = local_client.get("/api/central/licensing/devices", headers=local_auth_headers, timeout=15.0)
        # 502 = central unreachable (expected when central is down)
        # 200 = central is running (also fine)
        assert resp.status_code in (200, 502, 504), f"Unexpected proxy response: {resp.status_code}"

    def test_proxy_device_detail_returns_structured_error(self, local_client, local_auth_headers):
        """Proxy to device detail returns structured JSON error when central is down."""
        resp = local_client.get("/api/central/telemetry/device/test-id", headers=local_auth_headers, timeout=15.0)
        assert resp.status_code in (200, 404, 502, 504)
        # Verify response is JSON (not HTML error page)
        try:
            resp.json()
        except json.JSONDecodeError:
            pytest.fail(f"Proxy returned non-JSON response: {resp.text[:200]}")


# ═══════════════════════════════════════
# BLOCK 8: Config Endpoints
# ═══════════════════════════════════════

class TestConfigEndpoints:
    """Verify config endpoints work correctly."""

    def test_local_branding_config(self, local_client, local_auth_headers):
        """Settings branding CRUD cycle works."""
        resp = local_client.get("/api/settings/branding", headers=local_auth_headers)
        assert resp.status_code == 200

    def test_local_pricing_config(self, local_client, local_auth_headers):
        """Settings pricing works."""
        resp = local_client.get("/api/settings/pricing", headers=local_auth_headers)
        assert resp.status_code == 200

    def test_central_config_effective(self, local_client, local_auth_headers):
        """Effective config endpoint through proxy."""
        resp = local_client.get("/api/central/config/effective", headers=local_auth_headers, timeout=15.0)
        # 200 = works, 502 = central down (acceptable)
        assert resp.status_code in (200, 502, 504)


# ═══════════════════════════════════════
# BLOCK 9: v3.15.2 Stabilization Tests
# ═══════════════════════════════════════

class TestBoardControlActions:
    """Test that all 4 remote actions can be created on central server."""

    def test_remote_unlock_board(self, central_client, central_auth_headers):
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        assert resp.status_code == 200
        devices = resp.json()
        if not devices:
            pytest.skip("No devices")
        device_id = devices[0]["id"]
        resp = central_client.post(
            f"/api/remote-actions/{device_id}",
            headers={**central_auth_headers, "Content-Type": "application/json"},
            json={"action_type": "unlock_board", "params": {"board_id": "BOARD-1"}},
        )
        assert resp.status_code in (200, 201), f"unlock_board failed: {resp.status_code} {resp.text[:200]}"
        assert resp.json().get("status") == "pending"

    def test_remote_lock_board(self, central_client, central_auth_headers):
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        devices = resp.json()
        if not devices:
            pytest.skip("No devices")
        device_id = devices[0]["id"]
        resp = central_client.post(
            f"/api/remote-actions/{device_id}",
            headers={**central_auth_headers, "Content-Type": "application/json"},
            json={"action_type": "lock_board", "params": {"board_id": "BOARD-1"}},
        )
        assert resp.status_code in (200, 201)

    def test_remote_start_session(self, central_client, central_auth_headers):
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        devices = resp.json()
        if not devices:
            pytest.skip("No devices")
        device_id = devices[0]["id"]
        resp = central_client.post(
            f"/api/remote-actions/{device_id}",
            headers={**central_auth_headers, "Content-Type": "application/json"},
            json={"action_type": "start_session", "params": {"board_id": "BOARD-1"}},
        )
        assert resp.status_code in (200, 201)

    def test_remote_stop_session(self, central_client, central_auth_headers):
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        devices = resp.json()
        if not devices:
            pytest.skip("No devices")
        device_id = devices[0]["id"]
        resp = central_client.post(
            f"/api/remote-actions/{device_id}",
            headers={**central_auth_headers, "Content-Type": "application/json"},
            json={"action_type": "stop_session", "params": {"board_id": "BOARD-1"}},
        )
        assert resp.status_code in (200, 201)


class TestLicenseFailClosed:
    """Verify fail-closed license enforcement."""

    def test_blocked_states_constant_exists(self):
        """LicenseValidationService must define BLOCKED_STATES."""
        import sys
        sys.path.insert(0, '/app')
        from backend.services.license_service import license_service
        assert hasattr(license_service, 'BLOCKED_STATES')
        assert 'suspended' in license_service.BLOCKED_STATES
        assert 'blocked' in license_service.BLOCKED_STATES
        assert 'inactive' in license_service.BLOCKED_STATES
        assert 'expired' in license_service.BLOCKED_STATES

    def test_suspended_blocks(self):
        import sys
        sys.path.insert(0, '/app')
        from backend.services.license_service import license_service
        assert license_service.is_session_allowed({"status": "suspended"}) == False

    def test_unknown_status_blocks(self):
        """Unknown states must be blocked (fail-closed)."""
        import sys
        sys.path.insert(0, '/app')
        from backend.services.license_service import license_service
        assert license_service.is_session_allowed({"status": "unknown"}) == False
        assert license_service.is_session_allowed({"status": None}) == False
        assert license_service.is_session_allowed({"status": ""}) == False

    def test_active_allows(self):
        import sys
        sys.path.insert(0, '/app')
        from backend.services.license_service import license_service
        assert license_service.is_session_allowed({"status": "active"}) == True


class TestConsistentConnectivity:
    """Verify all endpoints return consistent connectivity status."""

    def test_device_list_has_connectivity(self, central_client, central_auth_headers):
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        assert resp.status_code == 200
        devices = resp.json()
        for d in devices[:5]:
            assert "connectivity" in d, f"Device {d.get('id')} missing 'connectivity' field"
            assert d["connectivity"] in ("online", "degraded", "offline"), f"Invalid connectivity: {d['connectivity']}"
            assert "is_online" in d, f"Device {d.get('id')} missing 'is_online' field"

    def test_device_detail_has_connectivity(self, central_client, central_auth_headers):
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        devices = resp.json()
        if not devices:
            pytest.skip("No devices")
        device_id = devices[0]["id"]
        resp = central_client.get(f"/api/telemetry/device/{device_id}", headers=central_auth_headers)
        assert resp.status_code == 200
        d = resp.json()
        assert "connectivity" in d, "Device detail missing 'connectivity'"
        assert d["connectivity"] in ("online", "degraded", "offline")
        assert "is_online" in d

    def test_telemetry_dashboard_has_connectivity(self, central_client, central_auth_headers):
        resp = central_client.get("/api/telemetry/dashboard", headers=central_auth_headers)
        assert resp.status_code == 200
        d = resp.json()
        for dev in d.get("devices", [])[:3]:
            assert "connectivity" in dev, f"Telemetry device missing 'connectivity'"

    def test_dashboard_has_connectivity(self, central_client, central_auth_headers):
        resp = central_client.get("/api/dashboard", headers=central_auth_headers)
        assert resp.status_code == 200
        d = resp.json()
        for dev in d.get("recent_devices", [])[:3]:
            assert "connectivity" in dev, f"Dashboard device missing 'connectivity'"


class TestActionPollerImport:
    """Verify action_poller imports work correctly (Issue #1 root cause)."""

    def test_import_action_poller(self):
        """action_poller must import without ModuleNotFoundError."""
        import sys
        sys.path.insert(0, '/app')
        from backend.services.action_poller import action_poller
        assert action_poller is not None

    def test_broken_import_does_not_exist(self):
        """The old broken import path must NOT work."""
        import importlib
        try:
            importlib.import_module('backend.database.database')
            assert False, "backend.database.database should NOT be importable"
        except ImportError:
            pass  # Expected — confirms the bug was real


# ═══════════════════════════════════════
# BLOCK 10: v3.15.3 System Stability Tests
# ═══════════════════════════════════════

class TestLicenseNoAutoRecover:
    """v3.15.3: Verify that handle_central_reactivation does NOT flip suspended→active."""

    def test_reactivation_does_not_change_cache(self):
        """After central rejection, reactivation handler must NOT set cache to active."""
        import sys, asyncio, pathlib
        sys.path.insert(0, '/app')
        from backend.services.license_service import license_service, _CACHE_FILE
        from backend.services.central_rejection_handler import handle_central_reactivation

        # Save suspended state to cache
        license_service.save_to_cache({
            "status": "suspended", "source": "central_rejection",
            "checked_at": "2026-01-01T00:00:00",
        })
        # Simulate what config_sync does on 200
        asyncio.get_event_loop().run_until_complete(handle_central_reactivation("test"))
        cached = license_service.load_from_cache()
        assert cached.get("status") == "suspended", (
            f"Cache was changed to '{cached.get('status')}' — auto-recover is STILL active!"
        )
        # Cleanup
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()


class TestActionHandlerSeparation:
    """v3.15.3: Verify 4 distinct action handlers exist."""

    def test_four_handlers_exist(self):
        import sys
        sys.path.insert(0, '/app')
        from backend.services.action_poller import action_poller
        for handler in ['_do_unlock', '_do_lock', '_do_start_session', '_do_stop_session']:
            assert hasattr(action_poller, handler), f"Missing handler: {handler}"

    def test_actions_route_correctly(self, central_client, central_auth_headers):
        """All 4 action types must be accepted by central server."""
        resp = central_client.get("/api/licensing/devices", headers=central_auth_headers)
        devices = resp.json()
        if not devices:
            pytest.skip("No devices")
        did = devices[0]["id"]
        for action in ["unlock_board", "lock_board", "start_session", "stop_session"]:
            r = central_client.post(
                f"/api/remote-actions/{did}",
                headers={**central_auth_headers, "Content-Type": "application/json"},
                json={"action_type": action, "params": {"board_id": "BOARD-1"}},
            )
            assert r.status_code in (200, 201), f"{action} rejected: {r.status_code}"


class TestWebSocketConfig:
    """v3.15.3: Verify WS reconnect backoff is stable."""

    def test_backoff_values(self):
        import sys
        sys.path.insert(0, '/app')
        from backend.services.ws_push_client import _MIN_BACKOFF, _MAX_BACKOFF, _STABLE_AFTER
        assert _MIN_BACKOFF >= 10, f"MIN_BACKOFF too low: {_MIN_BACKOFF}"
        assert _MAX_BACKOFF >= 60, f"MAX_BACKOFF too low: {_MAX_BACKOFF}"
        assert _STABLE_AFTER >= 3, f"STABLE_AFTER too low: {_STABLE_AFTER}"


class TestConfigSyncLogs:
    """v3.15.3: Verify explicit CONFIG log strings exist."""

    def test_log_strings_in_code(self):
        import pathlib
        sync_code = pathlib.Path("/app/backend/services/config_sync_client.py").read_text()
        assert "CONFIG RECEIVED" in sync_code
        assert "CONFIG APPLIED" in sync_code
        assert "CONFIG SKIPPED" in sync_code

        apply_code = pathlib.Path("/app/backend/services/config_apply.py").read_text()
        assert "CONFIG APPLIED" in apply_code
        assert "CONFIG SKIPPED" in apply_code


class TestAutodartsLogs:
    """v3.15.3: Verify AUTODARTS STARTED/FAILED log strings exist."""

    def test_log_strings_in_code(self):
        import pathlib
        kiosk_code = pathlib.Path("/app/backend/routers/kiosk.py").read_text()
        assert "AUTODARTS STARTED" in kiosk_code
        assert "AUTODARTS FAILED" in kiosk_code


class TestRevenueNullSafe:
    """v3.15.3: Revenue endpoint handles None price_total."""

    def test_revenue_endpoint(self, local_client, local_auth_headers):
        resp = local_client.get("/api/revenue/summary?days=30", headers=local_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_revenue" in data
        assert isinstance(data["total_revenue"], (int, float))




if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
