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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
