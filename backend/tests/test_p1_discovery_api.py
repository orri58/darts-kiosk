"""
P1 Discovery + Pairing API Tests
Tests for:
- GET /api/discovery/agents - discovered agents list
- GET /api/discovery/peers - paired peers list
- GET /api/agent/pair/code - 6-digit pairing code
- POST /api/agent/pair/verify - code verification
- POST /api/agent/pair/complete - challenge completion
- DELETE /api/discovery/peers/{id} - unpair
- Existing APIs: /api/health, /api/auth/login, /api/boards, /api/system/info
"""
import os
import pytest
import requests
import hmac
import hashlib

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealth:
    """Health check and basic API tests"""
    
    def test_health_returns_healthy_master(self):
        """GET /api/health returns status healthy with mode MASTER"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["mode"] == "MASTER"


class TestAuth:
    """Authentication tests"""
    
    def test_login_admin(self):
        """POST /api/auth/login with valid admin credentials"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
    
    def test_login_invalid_returns_401(self):
        """POST /api/auth/login with invalid credentials"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "invalid",
            "password": "wrong"
        })
        assert resp.status_code == 401


class TestPairingCode:
    """Pairing code endpoint tests (no auth required)"""
    
    def test_get_pairing_code(self):
        """GET /api/agent/pair/code returns 6-digit code with expires_in"""
        resp = requests.get(f"{BASE_URL}/api/agent/pair/code")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify code structure
        assert "code" in data
        assert "expires_in" in data
        
        # Code is 6 digits
        code = data["code"]
        assert len(code) == 6
        assert code.isdigit()
        
        # Expires in is reasonable (0-60 seconds)
        assert 0 <= data["expires_in"] <= 60
    
    def test_pairing_code_is_stable(self):
        """Pairing code should remain stable within rotation window"""
        resp1 = requests.get(f"{BASE_URL}/api/agent/pair/code")
        resp2 = requests.get(f"{BASE_URL}/api/agent/pair/code")
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        
        # Within 60-second window, code should be same
        assert resp1.json()["code"] == resp2.json()["code"]


class TestPairingVerify:
    """Pairing code verification tests"""
    
    def test_verify_wrong_code_403(self):
        """POST /api/agent/pair/verify rejects wrong code with 403"""
        resp = requests.post(f"{BASE_URL}/api/agent/pair/verify", json={
            "code": "000000",
            "master_fingerprint": "testfp",
            "master_ip": "127.0.0.1",
            "master_board_id": "TEST-MASTER"
        })
        assert resp.status_code == 403
        assert "invalid" in resp.json()["detail"].lower() or "expired" in resp.json()["detail"].lower()
    
    def test_verify_correct_code_returns_nonce(self):
        """POST /api/agent/pair/verify accepts correct code and returns nonce"""
        # Get current code
        code_resp = requests.get(f"{BASE_URL}/api/agent/pair/code")
        assert code_resp.status_code == 200
        code = code_resp.json()["code"]
        
        # Verify with correct code
        resp = requests.post(f"{BASE_URL}/api/agent/pair/verify", json={
            "code": code,
            "master_fingerprint": "testfp123",
            "master_ip": "127.0.0.1",
            "master_board_id": "TEST-MASTER"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Should return nonce for challenge
        assert "nonce" in data
        assert len(data["nonce"]) == 64  # hex encoded 32 bytes


class TestPairingComplete:
    """Pairing challenge completion tests"""
    
    def test_complete_invalid_challenge_403(self):
        """POST /api/agent/pair/complete rejects invalid challenge with 403"""
        resp = requests.post(f"{BASE_URL}/api/agent/pair/complete", json={
            "nonce": "invalid_nonce",
            "signature": "bad_signature",
            "master_fingerprint": "testfp",
            "master_board_id": "TEST-MASTER"
        })
        assert resp.status_code == 403
        assert "failed" in resp.json()["detail"].lower()
    
    def test_complete_with_wrong_signature_403(self):
        """POST /api/agent/pair/complete rejects wrong signature"""
        # First get a valid nonce
        code_resp = requests.get(f"{BASE_URL}/api/agent/pair/code")
        code = code_resp.json()["code"]
        
        verify_resp = requests.post(f"{BASE_URL}/api/agent/pair/verify", json={
            "code": code,
            "master_fingerprint": "testfp_sig",
            "master_ip": "127.0.0.1",
            "master_board_id": "TEST-MASTER-SIG"
        })
        
        if verify_resp.status_code != 200:
            pytest.skip("Code verification failed")
        
        nonce = verify_resp.json()["nonce"]
        
        # Try with wrong signature
        complete_resp = requests.post(f"{BASE_URL}/api/agent/pair/complete", json={
            "nonce": nonce,
            "signature": "wrong_signature",
            "master_fingerprint": "testfp_sig",
            "master_board_id": "TEST-MASTER-SIG"
        })
        assert complete_resp.status_code == 403


class TestDiscoveryAgents:
    """Discovery agents endpoint tests (requires admin auth)"""
    
    @pytest.fixture
    def admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        return resp.json()["access_token"]
    
    def test_discovery_agents_requires_auth(self):
        """GET /api/discovery/agents without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/discovery/agents")
        assert resp.status_code == 401
    
    def test_discovery_agents_returns_list(self, admin_token):
        """GET /api/discovery/agents returns agents list with discovery_active flag"""
        resp = requests.get(
            f"{BASE_URL}/api/discovery/agents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check structure
        assert "agents" in data
        assert "count" in data
        assert "discovery_active" in data
        
        # Agents is a list
        assert isinstance(data["agents"], list)
        assert data["count"] == len(data["agents"])
        
        # Discovery should be active in MASTER mode
        assert data["discovery_active"] is True


class TestDiscoveryPeers:
    """Discovery peers endpoint tests (requires admin auth)"""
    
    @pytest.fixture
    def admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        return resp.json()["access_token"]
    
    def test_discovery_peers_requires_auth(self):
        """GET /api/discovery/peers without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/discovery/peers")
        assert resp.status_code == 401
    
    def test_discovery_peers_returns_list(self, admin_token):
        """GET /api/discovery/peers returns paired peers list"""
        resp = requests.get(
            f"{BASE_URL}/api/discovery/peers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check structure
        assert "peers" in data
        assert isinstance(data["peers"], list)


class TestUnpairPeer:
    """Unpair peer endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        return resp.json()["access_token"]
    
    def test_unpair_nonexistent_peer_404(self, admin_token):
        """DELETE /api/discovery/peers/{id} with invalid id returns 404"""
        resp = requests.delete(
            f"{BASE_URL}/api/discovery/peers/nonexistent-id",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 404


class TestExistingAPIs:
    """Verify existing APIs still work"""
    
    @pytest.fixture
    def admin_token(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        return resp.json()["access_token"]
    
    def test_boards_endpoint(self, admin_token):
        """GET /api/boards returns board list"""
        resp = requests.get(
            f"{BASE_URL}/api/boards",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check board structure
        board = data[0]
        assert "board_id" in board
        assert "status" in board
    
    def test_system_info_endpoint(self, admin_token):
        """GET /api/system/info returns system info"""
        resp = requests.get(
            f"{BASE_URL}/api/system/info",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "version" in data
        assert "mode" in data
        assert data["mode"] == "MASTER"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
