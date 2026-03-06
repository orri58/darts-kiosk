"""
WebSocket Real-Time Board Status Tests (P1)
============================================
Tests for the WebSocket endpoint /api/ws/boards which replaces HTTP polling.
Features tested:
  - WebSocket connection
  - board_status broadcast on unlock/lock/start-game/end-game
  - session_extended broadcast on extend
  - Existing API regression
"""
import pytest
import requests
import json
import asyncio
import websockets
import os
import time
from datetime import datetime, timezone

# Use external URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://darts-kiosk.preview.emergentagent.com').rstrip('/')
WS_URL = BASE_URL.replace('https:', 'wss:').replace('http:', 'ws:') + '/api/ws/boards'

# Test credentials
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
STAFF_PIN = "1234"


# ============================================================
# Helper Fixtures
# ============================================================

@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USER,
        "password": ADMIN_PASS
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code}")


@pytest.fixture
def api_client(admin_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    })
    return session


# ============================================================
# Existing API Regression Tests
# ============================================================

class TestExistingAPIsRegression:
    """Ensure existing APIs still work after WebSocket addition"""

    def test_health_endpoint(self):
        """GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["mode"] == "MASTER"
        print(f"✓ Health endpoint OK: {data}")

    def test_auth_login_success(self, api_client):
        """POST /api/auth/login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["username"] == ADMIN_USER
        print(f"✓ Login OK: user={data['user']['username']}")

    def test_auth_pin_login(self):
        """POST /api/auth/pin-login works with staff PIN"""
        response = requests.post(f"{BASE_URL}/api/auth/pin-login", json={
            "pin": STAFF_PIN
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ PIN login OK: user={data['user']['username']}")

    def test_boards_list(self, api_client):
        """GET /api/boards returns board list"""
        response = api_client.get(f"{BASE_URL}/api/boards")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # BOARD-1 and BOARD-2
        board_ids = [b["board_id"] for b in data]
        assert "BOARD-1" in board_ids
        print(f"✓ Boards list OK: {len(data)} boards ({board_ids})")

    def test_system_info(self, api_client):
        """GET /api/system/info returns system info"""
        response = api_client.get(f"{BASE_URL}/api/system/info")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "hostname" in data
        assert "disk" in data
        print(f"✓ System info OK: version={data['version']}, hostname={data['hostname']}")


# ============================================================
# WebSocket Connection Tests
# ============================================================

class TestWebSocketConnection:
    """Test WebSocket endpoint /api/ws/boards connection"""

    @pytest.mark.asyncio
    async def test_websocket_connects(self):
        """WS endpoint accepts connection"""
        try:
            async with websockets.connect(WS_URL, close_timeout=5) as ws:
                # websockets 14.x uses ws.state instead of ws.open
                from websockets.protocol import State
                assert ws.state == State.OPEN
                print(f"✓ WebSocket connected to {WS_URL}")
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")

    @pytest.mark.asyncio
    async def test_websocket_stays_open(self):
        """WS connection stays open for at least 2 seconds"""
        try:
            async with websockets.connect(WS_URL, close_timeout=5) as ws:
                await asyncio.sleep(2)
                from websockets.protocol import State
                assert ws.state == State.OPEN
                print("✓ WebSocket stayed open for 2s")
        except Exception as e:
            pytest.fail(f"WebSocket connection dropped: {e}")


# ============================================================
# WebSocket Broadcast Tests
# ============================================================

class TestWebSocketBroadcasts:
    """Test WebSocket broadcasts on board actions"""

    @pytest.mark.asyncio
    async def test_broadcast_on_unlock(self, admin_token):
        """WS broadcasts board_status on unlock"""
        # First ensure board is locked
        lock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        try:
            async with websockets.connect(WS_URL, close_timeout=10) as ws:
                # Trigger unlock
                unlock_resp = requests.post(
                    f"{BASE_URL}/api/boards/BOARD-1/unlock",
                    json={
                        "pricing_mode": "per_game",
                        "credits": 3,
                        "players_count": 1,
                        "price_total": 6.0
                    },
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
                assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.text}"
                
                # Wait for broadcast
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    assert data["event"] == "board_status"
                    assert data["data"]["board_id"] == "BOARD-1"
                    assert data["data"]["status"] == "unlocked"
                    print(f"✓ Received board_status broadcast on unlock: {data}")
                except asyncio.TimeoutError:
                    pytest.fail("No WS broadcast received on unlock within 5s")
        finally:
            # Cleanup - lock board
            requests.post(
                f"{BASE_URL}/api/boards/BOARD-1/lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )

    @pytest.mark.asyncio
    async def test_broadcast_on_lock(self, admin_token):
        """WS broadcasts board_status on lock"""
        # First unlock the board
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "players_count": 1,
                "price_total": 6.0
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        try:
            async with websockets.connect(WS_URL, close_timeout=10) as ws:
                # Trigger lock
                lock_resp = requests.post(
                    f"{BASE_URL}/api/boards/BOARD-1/lock",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
                assert lock_resp.status_code == 200, f"Lock failed: {lock_resp.text}"
                
                # Wait for broadcast
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    assert data["event"] == "board_status"
                    assert data["data"]["board_id"] == "BOARD-1"
                    assert data["data"]["status"] == "locked"
                    print(f"✓ Received board_status broadcast on lock: {data}")
                except asyncio.TimeoutError:
                    pytest.fail("No WS broadcast received on lock within 5s")
        finally:
            # Cleanup
            requests.post(
                f"{BASE_URL}/api/boards/BOARD-1/lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )

    @pytest.mark.asyncio
    async def test_broadcast_on_extend(self, admin_token):
        """WS broadcasts session_extended on extend"""
        # First unlock the board
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "players_count": 1,
                "price_total": 6.0
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert unlock_resp.status_code == 200
        
        try:
            async with websockets.connect(WS_URL, close_timeout=10) as ws:
                # Trigger extend
                extend_resp = requests.post(
                    f"{BASE_URL}/api/boards/BOARD-1/extend",
                    json={"credits": 2, "minutes": 15},
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
                assert extend_resp.status_code == 200, f"Extend failed: {extend_resp.text}"
                
                # Wait for broadcast
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    assert data["event"] == "session_extended"
                    assert data["data"]["board_id"] == "BOARD-1"
                    assert data["data"]["credits"] == 2
                    assert data["data"]["minutes"] == 15
                    print(f"✓ Received session_extended broadcast: {data}")
                except asyncio.TimeoutError:
                    pytest.fail("No WS broadcast received on extend within 5s")
        finally:
            # Cleanup
            requests.post(
                f"{BASE_URL}/api/boards/BOARD-1/lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )

    @pytest.mark.asyncio
    async def test_broadcast_on_start_game(self, admin_token):
        """WS broadcasts board_status on start-game"""
        # First unlock the board
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "players_count": 1,
                "price_total": 6.0
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert unlock_resp.status_code == 200
        
        try:
            async with websockets.connect(WS_URL, close_timeout=10) as ws:
                # Trigger start-game (kiosk endpoint - no auth needed)
                start_resp = requests.post(
                    f"{BASE_URL}/api/kiosk/BOARD-1/start-game",
                    json={"game_type": "501", "players": ["Player1"]}
                )
                assert start_resp.status_code == 200, f"Start-game failed: {start_resp.text}"
                
                # Wait for broadcast
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    assert data["event"] == "board_status"
                    assert data["data"]["board_id"] == "BOARD-1"
                    assert data["data"]["status"] == "in_game"
                    assert data["data"]["game_type"] == "501"
                    print(f"✓ Received board_status broadcast on start-game: {data}")
                except asyncio.TimeoutError:
                    pytest.fail("No WS broadcast received on start-game within 5s")
        finally:
            # Cleanup
            requests.post(
                f"{BASE_URL}/api/boards/BOARD-1/lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )

    @pytest.mark.asyncio
    async def test_broadcast_on_end_game(self, admin_token):
        """WS broadcasts board_status on end-game"""
        # First unlock and start a game
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "players_count": 1,
                "price_total": 6.0
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert unlock_resp.status_code == 200
        
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/start-game",
            json={"game_type": "501", "players": ["Player1"]}
        )
        assert start_resp.status_code == 200
        
        try:
            async with websockets.connect(WS_URL, close_timeout=10) as ws:
                # Trigger end-game
                end_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game")
                assert end_resp.status_code == 200, f"End-game failed: {end_resp.text}"
                
                # Wait for broadcast
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    assert data["event"] == "board_status"
                    assert data["data"]["board_id"] == "BOARD-1"
                    # Status should be 'unlocked' (still has credits) or 'locked' (no credits)
                    assert data["data"]["status"] in ["unlocked", "locked"]
                    print(f"✓ Received board_status broadcast on end-game: {data}")
                except asyncio.TimeoutError:
                    pytest.fail("No WS broadcast received on end-game within 5s")
        finally:
            # Cleanup
            requests.post(
                f"{BASE_URL}/api/boards/BOARD-1/lock",
                headers={"Authorization": f"Bearer {admin_token}"}
            )


# ============================================================
# Autodarts Soak Report Validation
# ============================================================

class TestAutodartsReport:
    """Validate the autodarts soak test report"""

    def test_soak_report_exists(self):
        """Soak report file exists"""
        report_path = "/app/test_reports/autodarts_soak_report.json"
        assert os.path.exists(report_path), f"Report not found at {report_path}"
        print(f"✓ Soak report exists at {report_path}")

    def test_soak_report_has_200_cycles(self):
        """Soak report shows 200 cycles completed"""
        with open("/app/test_reports/autodarts_soak_report.json") as f:
            report = json.load(f)
        
        assert report["total_cycles"] == 200
        assert report["success"] == 200
        assert report["fail"] == 0
        print(f"✓ Soak report: {report['total_cycles']} cycles, {report['success']} success, {report['fail']} fail")

    def test_soak_report_100_percent_success(self):
        """Soak report shows 100% success rate"""
        with open("/app/test_reports/autodarts_soak_report.json") as f:
            report = json.load(f)
        
        assert report["success_rate"] == 100.0
        print(f"✓ Soak success rate: {report['success_rate']}%")

    def test_soak_report_all_modes_tested(self):
        """Soak report shows all 4 game modes tested"""
        with open("/app/test_reports/autodarts_soak_report.json") as f:
            report = json.load(f)
        
        modes = ["301", "501", "Cricket", "Training"]
        for mode in modes:
            assert mode in report["by_mode"]
            assert report["by_mode"][mode]["success"] == 50
            assert report["by_mode"][mode]["fail"] == 0
        print(f"✓ All modes tested: {list(report['by_mode'].keys())}")

    def test_soak_report_acceptance_criteria(self):
        """Soak report passes all acceptance criteria"""
        with open("/app/test_reports/autodarts_soak_report.json") as f:
            report = json.load(f)
        
        ac = report["acceptance_criteria"]
        assert ac["AC-1_200_cycles"] is True, "AC-1 failed: 200 cycles not completed"
        assert ac["AC-2_all_modes"] is True, "AC-2 failed: Not all modes tested"
        assert ac["AC-6_95pct"] is True, "AC-6 failed: Success rate < 95%"
        print(f"✓ Acceptance criteria passed: AC-1={ac['AC-1_200_cycles']}, AC-2={ac['AC-2_all_modes']}, AC-6={ac['AC-6_95pct']}")


# ============================================================
# Kiosk Page API Test
# ============================================================

class TestKioskAPI:
    """Test kiosk-related APIs"""

    def test_kiosk_session_endpoint(self):
        """GET /api/boards/{board_id}/session works without auth"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        data = response.json()
        assert "board_status" in data
        assert data["board_status"] in ["locked", "unlocked", "in_game", "offline"]
        print(f"✓ Kiosk session endpoint OK: status={data['board_status']}")

    def test_kiosk_call_staff(self):
        """POST /api/kiosk/{board_id}/call-staff works"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/call-staff")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Staff notified"
        print(f"✓ Call staff endpoint OK")
