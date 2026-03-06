"""
Comprehensive API Test Suite for Refactored Darts Kiosk System
Tests all endpoints after server.py was split into routers/, schemas.py, dependencies.py
NO behavior changes expected - this is pure regression testing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
STAFF_PIN = "1234"


class TestHealth:
    """Health check endpoints"""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "mode" in data
        print(f"✓ Health check passed: {data}")
    
    def test_root_endpoint(self):
        """GET /api/ returns API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "mode" in data
        print(f"✓ Root endpoint: {data}")


class TestAuth:
    """Authentication endpoints - /auth/login, /auth/pin-login, /auth/me"""
    
    def test_login_with_admin_credentials(self):
        """POST /api/auth/login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["username"] == ADMIN_USERNAME
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful, token received")
        return data["access_token"]
    
    def test_pin_login_with_1234(self):
        """POST /api/auth/pin-login with PIN 1234"""
        response = requests.post(f"{BASE_URL}/api/auth/pin-login", json={
            "pin": STAFF_PIN
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        print(f"✓ PIN login successful, user: {data['user']['username']}")
        return data["access_token"]
    
    def test_get_current_user(self):
        """GET /api/auth/me returns current user"""
        # First get token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["access_token"]
        
        # Now get current user
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == ADMIN_USERNAME
        assert data["role"] == "admin"
        assert "id" in data
        assert "is_active" in data
        print(f"✓ Get current user: {data['username']} ({data['role']})")
    
    def test_invalid_login(self):
        """POST /api/auth/login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print("✓ Invalid login correctly rejected with 401")
    
    def test_invalid_pin(self):
        """POST /api/auth/pin-login with invalid PIN returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/pin-login", json={
            "pin": "9999"
        })
        assert response.status_code == 401
        print("✓ Invalid PIN correctly rejected with 401")


class TestUsers:
    """User management endpoints - admin only"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_users_list(self):
        """GET /api/users returns user list (admin only)"""
        response = requests.get(f"{BASE_URL}/api/users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least admin exists
        usernames = [u["username"] for u in data]
        assert ADMIN_USERNAME in usernames
        print(f"✓ User list returned {len(data)} users: {usernames}")
    
    def test_get_users_without_auth_fails(self):
        """GET /api/users without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/users")
        assert response.status_code == 401
        print("✓ Users endpoint correctly requires auth")


class TestBoards:
    """Board management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_boards_list(self):
        """GET /api/boards returns board list"""
        response = requests.get(f"{BASE_URL}/api/boards", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least BOARD-1 exists
        board_ids = [b["board_id"] for b in data]
        assert "BOARD-1" in board_ids
        print(f"✓ Boards list returned {len(data)} boards: {board_ids}")
    
    def test_get_board_detail(self):
        """GET /api/boards/BOARD-1 returns board detail with session"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "board" in data
        assert data["board"]["board_id"] == "BOARD-1"
        assert "active_session" in data  # May be None or session object
        print(f"✓ Board detail: {data['board']['name']}, status: {data['board']['status']}")
    
    def test_get_board_not_found(self):
        """GET /api/boards/INVALID returns 404"""
        response = requests.get(f"{BASE_URL}/api/boards/INVALID-BOARD", headers=self.headers)
        assert response.status_code == 404
        print("✓ Invalid board correctly returns 404")


class TestBoardSessions:
    """Board session control: unlock, extend, lock"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        # Ensure board is locked before tests
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_unlock_board_creates_session(self):
        """POST /api/boards/{id}/unlock creates session"""
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "game_type": "501",
                "credits": 5,
                "players_count": 2,
                "price_total": 10.0
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["pricing_mode"] == "per_game"
        assert data["credits_total"] == 5
        assert data["credits_remaining"] == 5
        assert data["status"] == "active"
        print(f"✓ Board unlocked, session created: {data['id']}")
        return data["id"]
    
    def test_extend_session(self):
        """POST /api/boards/{id}/extend extends session"""
        # First unlock if not already
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.0}
        )
        
        # Now extend
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/extend",
            headers=self.headers,
            json={"credits": 2}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["credits_remaining"] == 5  # 3 + 2
        assert data["credits_total"] == 5
        print(f"✓ Session extended, credits: {data['credits_remaining']}")
    
    def test_lock_board_cancels_session(self):
        """POST /api/boards/{id}/lock locks board and cancels session"""
        # Ensure unlocked first
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 1, "price_total": 2.0}
        )
        
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Board locked"
        assert data["board_id"] == "BOARD-1"
        print(f"✓ Board locked successfully")


class TestKiosk:
    """Kiosk action endpoints - no auth required"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token and ensure board is unlocked"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        # Unlock board for kiosk tests
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 10, "price_total": 20.0}
        )
    
    def test_start_game(self):
        """POST /api/kiosk/{id}/start-game changes status to in_game"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "501",
            "players": ["Player1", "Player2"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Game started"
        assert data["game_type"] == "501"
        assert data["players"] == ["Player1", "Player2"]
        print(f"✓ Game started: {data['game_type']} with {len(data['players'])} players")
    
    def test_end_game(self):
        """POST /api/kiosk/{id}/end-game decrements credits and updates status"""
        # Start a game first
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "Cricket",
            "players": ["P1"]
        })
        
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Game ended"
        assert "credits_remaining" in data
        assert "board_status" in data
        print(f"✓ Game ended, credits remaining: {data['credits_remaining']}")
    
    def test_call_staff(self):
        """POST /api/kiosk/{id}/call-staff returns success"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/call-staff")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Staff notified"
        assert data["board_id"] == "BOARD-1"
        print(f"✓ Staff call success")


class TestSettings:
    """Settings endpoints - branding, pricing, palettes"""
    
    def test_get_branding(self):
        """GET /api/settings/branding returns branding settings"""
        response = requests.get(f"{BASE_URL}/api/settings/branding")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Check expected keys in branding
        assert "venue_name" in data or "primary_color" in data or len(data) > 0
        print(f"✓ Branding settings returned: {list(data.keys())[:5]}...")
    
    def test_get_pricing(self):
        """GET /api/settings/pricing returns pricing settings"""
        response = requests.get(f"{BASE_URL}/api/settings/pricing")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        print(f"✓ Pricing settings returned: {list(data.keys())[:5]}...")
    
    def test_get_palettes(self):
        """GET /api/settings/palettes returns palettes"""
        response = requests.get(f"{BASE_URL}/api/settings/palettes")
        assert response.status_code == 200
        data = response.json()
        # Palettes can be a list of palette objects or a dict
        assert isinstance(data, (dict, list))
        if isinstance(data, list):
            assert len(data) > 0
            print(f"✓ Palettes returned: {len(data)} palette themes")
        else:
            print(f"✓ Palettes returned: {list(data.keys())[:3]}...")


class TestAdminEndpoints:
    """Admin-only endpoints: logs, revenue, health, setup, system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_audit_logs(self):
        """GET /api/logs/audit returns audit logs (admin)"""
        response = requests.get(f"{BASE_URL}/api/logs/audit", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            log = data[0]
            assert "action" in log
            assert "created_at" in log
        print(f"✓ Audit logs returned {len(data)} entries")
    
    def test_get_revenue_summary(self):
        """GET /api/revenue/summary returns revenue data"""
        response = requests.get(f"{BASE_URL}/api/revenue/summary", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "period_days" in data
        assert "total_revenue" in data
        assert "total_sessions" in data
        assert "by_date" in data
        print(f"✓ Revenue summary: {data['total_sessions']} sessions, ${data['total_revenue']}")
    
    def test_get_detailed_health(self):
        """GET /api/health/detailed returns detailed health (admin)"""
        response = requests.get(f"{BASE_URL}/api/health/detailed", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "database_ok" in data
        assert "scheduler_running" in data
        print(f"✓ Detailed health: DB={data['database_ok']}, Scheduler={data['scheduler_running']}")
    
    def test_get_setup_status(self):
        """GET /api/setup/status returns setup status"""
        response = requests.get(f"{BASE_URL}/api/setup/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_complete" in data or "setup_complete" in data or "needs_setup" in data
        print(f"✓ Setup status returned: {data}")
    
    def test_get_system_info(self):
        """GET /api/system/info returns system info"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data or "uptime" in data
        print(f"✓ System info returned: {list(data.keys())}")
    
    def test_get_system_logs(self):
        """GET /api/system/logs returns log lines"""
        response = requests.get(f"{BASE_URL}/api/system/logs?lines=50", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "lines" in data
        assert isinstance(data["lines"], list)
        print(f"✓ System logs returned {len(data['lines'])} lines")


class TestBackups:
    """Backup management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_backups_list(self):
        """GET /api/backups returns backup list"""
        response = requests.get(f"{BASE_URL}/api/backups", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "backups" in data
        assert "stats" in data
        assert isinstance(data["backups"], list)
        print(f"✓ Backups list: {len(data['backups'])} backups")
    
    def test_create_backup(self):
        """POST /api/backups/create creates backup"""
        response = requests.post(f"{BASE_URL}/api/backups/create", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "backup" in data
        assert "filename" in data["backup"]
        print(f"✓ Backup created: {data['backup']['filename']}")


class TestUpdates:
    """Update management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_updates_status(self):
        """GET /api/updates/status returns version info"""
        response = requests.get(f"{BASE_URL}/api/updates/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        assert "available_versions" in data
        print(f"✓ Updates status: current version {data['current_version']}")


class TestAgent:
    """Agent API endpoints"""
    
    def test_agent_health(self):
        """GET /api/agent/health returns agent health"""
        response = requests.get(f"{BASE_URL}/api/agent/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "mode" in data
        assert "timestamp" in data
        print(f"✓ Agent health: {data['status']}, mode: {data['mode']}")


class TestCleanup:
    """Cleanup after tests"""
    
    def test_cleanup_lock_board(self):
        """Ensure board is locked after tests"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=headers)
        print(f"✓ Cleanup: Board locked, status {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
