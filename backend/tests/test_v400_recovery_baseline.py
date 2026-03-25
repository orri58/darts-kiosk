"""
v4.0.0 Recovery Baseline Tests
Tests for the restored v3.3.1-hotfix2 baseline.
All central server / licensing / portal features have been REMOVED.
Only local admin + kiosk + board control + autodarts + settings + revenue remain.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com').rstrip('/')


class TestHealthAndRoot:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["mode"] == "MASTER"
        print(f"✓ Health check passed: {data}")
    
    def test_root_endpoint(self):
        """GET /api/ returns API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "Darts Kiosk System API" in data["message"]
        print(f"✓ Root endpoint passed: {data}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """POST /api/auth/login with admin credentials returns access_token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data, f"Expected 'access_token' in response, got: {data.keys()}"
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        print(f"✓ Login success: token={data['access_token'][:20]}...")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with wrong credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected with 401")
    
    def test_auth_me_with_token(self):
        """GET /api/auth/me with valid token returns user info"""
        # First login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_response.json()["access_token"]
        
        # Then get me
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        print(f"✓ Auth me passed: {data}")


class TestBoardsAPI:
    """Board CRUD and control tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_list_boards(self):
        """GET /api/boards returns list of boards with board_id and status"""
        response = requests.get(f"{BASE_URL}/api/boards", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Expected at least one board"
        
        # Check board structure
        board = data[0]
        assert "board_id" in board
        assert "status" in board
        assert "name" in board
        print(f"✓ List boards passed: {len(data)} boards found")
        for b in data:
            print(f"  - {b['board_id']}: {b['name']} ({b['status']})")
    
    def test_get_board_detail(self):
        """GET /api/boards/BOARD-1 returns board detail with active_session"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "board" in data
        assert data["board"]["board_id"] == "BOARD-1"
        # active_session can be null if board is locked
        assert "active_session" in data
        print(f"✓ Board detail passed: {data['board']['name']}, session={data['active_session']}")
    
    def test_unlock_board(self):
        """POST /api/boards/BOARD-1/unlock with player_count and player_names returns 200"""
        # First ensure board is locked
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        
        # Now unlock
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 2,
            "players_count": 2,
            "player_names": ["P1", "P2"],
            "price_total": 4.0
        }, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["players_count"] == 2
        print(f"✓ Unlock board passed: session_id={data['id']}")
        
        # Verify board status changed
        board_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        board_data = board_response.json()
        assert board_data["board"]["status"] == "unlocked"
        print(f"✓ Board status verified: {board_data['board']['status']}")
    
    def test_lock_board(self):
        """POST /api/boards/BOARD-1/lock returns 200 and board goes back to locked"""
        # First ensure board is unlocked
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 1,
            "players_count": 1,
            "price_total": 2.0
        }, headers=self.headers)
        
        # Now lock
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["board_id"] == "BOARD-1"
        print(f"✓ Lock board passed: {data}")
        
        # Verify board status changed
        board_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        board_data = board_response.json()
        assert board_data["board"]["status"] == "locked"
        print(f"✓ Board status verified: {board_data['board']['status']}")


class TestSettingsAPI:
    """Settings endpoints tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_branding(self):
        """GET /api/settings/branding returns cafe_name and subtitle"""
        response = requests.get(f"{BASE_URL}/api/settings/branding")
        assert response.status_code == 200
        data = response.json()
        assert "cafe_name" in data
        assert "subtitle" in data
        print(f"✓ Get branding passed: cafe_name={data.get('cafe_name')}, subtitle={data.get('subtitle')}")
    
    def test_update_branding(self):
        """PUT /api/settings/branding with {value:{cafe_name:'Test'}} updates branding"""
        # First get current branding
        get_response = requests.get(f"{BASE_URL}/api/settings/branding")
        original = get_response.json()
        
        # Update branding
        new_branding = {
            "cafe_name": "Test Cafe",
            "subtitle": "Test Subtitle",
            "welcome_text": original.get("welcome_text", "Willkommen!")
        }
        response = requests.put(f"{BASE_URL}/api/settings/branding", json={
            "value": new_branding
        }, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["cafe_name"] == "Test Cafe"
        print(f"✓ Update branding passed: {data}")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/branding", json={
            "value": original
        }, headers=self.headers)
        print("✓ Branding restored to original")
    
    def test_get_pricing(self):
        """GET /api/settings/pricing returns pricing config"""
        response = requests.get(f"{BASE_URL}/api/settings/pricing")
        assert response.status_code == 200
        data = response.json()
        # Pricing should have mode and pricing options
        print(f"✓ Get pricing passed: {data}")


class TestRevenueAPI:
    """Revenue endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_revenue_summary(self):
        """GET /api/revenue/summary?days=30 returns total_revenue and total_sessions as numbers"""
        response = requests.get(f"{BASE_URL}/api/revenue/summary?days=30", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_revenue" in data
        assert "total_sessions" in data
        assert isinstance(data["total_revenue"], (int, float))
        assert isinstance(data["total_sessions"], int)
        print(f"✓ Revenue summary passed: revenue={data['total_revenue']}, sessions={data['total_sessions']}")


class TestKioskAPI:
    """Kiosk endpoint tests"""
    
    def test_observer_status(self):
        """GET /api/kiosk/BOARD-1/observer-status returns state and browser_open fields"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/observer-status")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "browser_open" in data
        assert "autodarts_mode" in data
        print(f"✓ Observer status passed: state={data['state']}, browser_open={data['browser_open']}")
    
    def test_board_session_endpoint(self):
        """GET /api/boards/BOARD-1/session returns board status and session info"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        data = response.json()
        assert "board_status" in data
        assert "autodarts_mode" in data
        print(f"✓ Board session passed: status={data['board_status']}, mode={data['autodarts_mode']}")


class TestNoLicensingEndpoints:
    """Verify licensing/central endpoints are removed"""
    
    def test_no_central_endpoints(self):
        """Verify /api/central/* endpoints return 404"""
        response = requests.get(f"{BASE_URL}/api/central/health")
        # Should be 404 since central endpoints are removed
        assert response.status_code == 404, f"Expected 404 for removed endpoint, got {response.status_code}"
        print("✓ Central endpoints correctly removed (404)")
    
    def test_no_licensing_endpoints(self):
        """Verify /api/licensing/* endpoints return 404"""
        response = requests.get(f"{BASE_URL}/api/licensing/status")
        # Should be 404 since licensing endpoints are removed
        assert response.status_code == 404, f"Expected 404 for removed endpoint, got {response.status_code}"
        print("✓ Licensing endpoints correctly removed (404)")


class TestFullUnlockLockCycle:
    """End-to-end test of unlock/lock cycle"""
    
    def test_full_cycle(self):
        """Test complete unlock -> verify -> lock -> verify cycle"""
        # Login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure board is locked first
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=headers)
        
        # Verify locked
        board_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=headers)
        assert board_response.json()["board"]["status"] == "locked"
        print("✓ Step 1: Board is locked")
        
        # Unlock with 2 players
        unlock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "players_count": 2,
            "player_names": ["Player1", "Player2"],
            "price_total": 6.0
        }, headers=headers)
        assert unlock_response.status_code == 200
        session = unlock_response.json()
        assert session["players_count"] == 2
        assert session["credits_total"] == 3
        print(f"✓ Step 2: Board unlocked with session {session['id']}")
        
        # Verify unlocked
        board_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=headers)
        board_data = board_response.json()
        assert board_data["board"]["status"] == "unlocked"
        assert board_data["active_session"] is not None
        print("✓ Step 3: Board status verified as unlocked with active session")
        
        # Lock board
        lock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=headers)
        assert lock_response.status_code == 200
        print("✓ Step 4: Board locked")
        
        # Verify locked again
        board_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=headers)
        board_data = board_response.json()
        assert board_data["board"]["status"] == "locked"
        assert board_data["active_session"] is None
        print("✓ Step 5: Board status verified as locked with no active session")
        
        print("\n✓ Full unlock/lock cycle completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
