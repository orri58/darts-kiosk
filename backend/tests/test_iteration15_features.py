"""
Iteration 15 Backend Tests:
Tests for the three improvements implemented:
1. Enhanced GitHub-based update system with download progress, changelog, persistent history, rollback info
2. Legacy code removal (health_monitor.py refactored from 'automation' to 'observer' terminology)
3. mDNS discovery improvements with periodic stale cleanup, re-scan, and stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUpdateEndpoints:
    """Tests for the enhanced GitHub-based update system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for admin endpoints"""
        # Login as admin
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip("Admin login failed - skipping authenticated tests")
    
    def test_updates_check_structure(self):
        """GET /api/updates/check returns correct structure with configured=false when no GITHUB_REPO is set"""
        response = requests.get(f"{BASE_URL}/api/updates/check", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have 'configured' key set to False when GITHUB_REPO not set
        assert "configured" in data, "Response should contain 'configured' field"
        assert data["configured"] == False, "configured should be False when GITHUB_REPO not set"
        assert "current_version" in data, "Response should contain 'current_version' field"
        assert "message" in data, "Response should contain 'message' field"
        assert "releases" in data, "Response should contain 'releases' field"
        assert isinstance(data["releases"], list), "releases should be a list"
        print(f"Update check response: configured={data['configured']}, version={data['current_version']}")
    
    def test_updates_status_returns_correct_structure(self):
        """GET /api/updates/status returns current_version, github_repo, and update_history array"""
        response = requests.get(f"{BASE_URL}/api/updates/status", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "current_version" in data, "Response should contain 'current_version'"
        assert "github_repo" in data, "Response should contain 'github_repo'"
        assert "update_history" in data, "Response should contain 'update_history'"
        assert isinstance(data["update_history"], list), "update_history should be a list"
        print(f"Update status: version={data['current_version']}, repo={data['github_repo']}, history_count={len(data['update_history'])}")
    
    def test_updates_history_returns_persisted_history(self):
        """GET /api/updates/history returns persisted history from DB"""
        response = requests.get(f"{BASE_URL}/api/updates/history", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "history" in data, "Response should contain 'history'"
        assert isinstance(data["history"], list), "history should be a list"
        print(f"Update history: {len(data['history'])} entries")
    
    def test_updates_downloads_returns_assets_list(self):
        """GET /api/updates/downloads returns empty assets list"""
        response = requests.get(f"{BASE_URL}/api/updates/downloads", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "assets" in data, "Response should contain 'assets'"
        assert isinstance(data["assets"], list), "assets should be a list"
        print(f"Downloaded assets: {len(data['assets'])} files")
    
    def test_updates_prepare_creates_backup_and_returns_correct_structure(self):
        """POST /api/updates/prepare?target_version=2.0.0 creates backup and returns correct structure"""
        response = requests.post(
            f"{BASE_URL}/api/updates/prepare?target_version=2.0.0",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Check required fields in response
        assert "backup_created" in data, "Response should contain 'backup_created'"
        assert "target_version" in data, "Response should contain 'target_version'"
        assert data["target_version"] == "2.0.0", "target_version should match request"
        assert "changelog" in data, "Response should contain 'changelog'"
        assert "download_links" in data, "Response should contain 'download_links'"
        assert isinstance(data["download_links"], list), "download_links should be a list"
        assert "rollback_info" in data, "Response should contain 'rollback_info'"
        assert isinstance(data["rollback_info"], dict), "rollback_info should be a dict"
        assert "instruction" in data["rollback_info"], "rollback_info should contain 'instruction'"
        assert "manual_steps" in data, "Response should contain 'manual_steps'"
        assert isinstance(data["manual_steps"], list), "manual_steps should be a list"
        assert len(data["manual_steps"]) > 0, "manual_steps should not be empty"
        
        print(f"Prepare update: backup_created={data['backup_created']}, target={data['target_version']}")
        print(f"Rollback info: {data['rollback_info']}")
        print(f"Manual steps: {len(data['manual_steps'])} steps")


class TestHealthMonitorRefactored:
    """Tests for health_monitor refactored terminology (automation -> observer)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for admin endpoints"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip("Admin login failed - skipping authenticated tests")
    
    def test_health_detailed_returns_observer_metrics(self):
        """GET /api/health/detailed returns observer_metrics (not automation_metrics)"""
        response = requests.get(f"{BASE_URL}/api/health/detailed", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check that we have observer_metrics, NOT automation_metrics
        assert "observer_metrics" in data, "Response should contain 'observer_metrics' (refactored from automation_metrics)"
        assert "automation_metrics" not in data, "Response should NOT contain 'automation_metrics' (legacy name)"
        
        # Validate observer_metrics structure
        obs_metrics = data["observer_metrics"]
        assert "total_events" in obs_metrics, "observer_metrics should contain 'total_events'"
        assert "successful" in obs_metrics, "observer_metrics should contain 'successful'"
        assert "failed" in obs_metrics, "observer_metrics should contain 'failed'"
        assert "success_rate" in obs_metrics, "observer_metrics should contain 'success_rate'"
        
        # Validate other health fields
        assert "status" in data, "Response should contain 'status'"
        assert "uptime_seconds" in data, "Response should contain 'uptime_seconds'"
        assert "agent_status" in data, "Response should contain 'agent_status'"
        
        print(f"Health status: {data['status']}")
        print(f"Observer metrics: total={obs_metrics['total_events']}, success_rate={obs_metrics['success_rate']}%")


class TestDiscoveryEnhancements:
    """Tests for mDNS discovery improvements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for admin endpoints"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip("Admin login failed - skipping authenticated tests")
    
    def test_discovery_agents_returns_stats(self):
        """GET /api/discovery/agents returns agents, count, discovery_active, and new stats object"""
        response = requests.get(f"{BASE_URL}/api/discovery/agents", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "agents" in data, "Response should contain 'agents'"
        assert isinstance(data["agents"], list), "agents should be a list"
        assert "count" in data, "Response should contain 'count'"
        assert "discovery_active" in data, "Response should contain 'discovery_active'"
        assert "stats" in data, "Response should contain 'stats'"
        assert isinstance(data["stats"], dict), "stats should be a dict"
        
        # Validate stats structure
        stats = data["stats"]
        assert "active_agents" in stats, "stats should contain 'active_agents'"
        assert "paired_agents" in stats, "stats should contain 'paired_agents'"
        assert "scan_count" in stats, "stats should contain 'scan_count'"
        
        print(f"Discovery: {data['count']} agents, active={data['discovery_active']}")
        print(f"Stats: active={stats['active_agents']}, paired={stats['paired_agents']}, scans={stats['scan_count']}")
    
    def test_discovery_stats_returns_detailed_stats(self):
        """GET /api/discovery/stats returns detailed mDNS discovery statistics"""
        response = requests.get(f"{BASE_URL}/api/discovery/stats", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Check all expected fields in stats
        assert "active_agents" in data, "Response should contain 'active_agents'"
        assert "paired_agents" in data, "Response should contain 'paired_agents'"
        assert "scan_count" in data, "Response should contain 'scan_count'"
        assert "stale_timeout_seconds" in data, "Response should contain 'stale_timeout_seconds'"
        assert "total_discovered" in data, "Response should contain 'total_discovered'"
        assert "total_removed" in data, "Response should contain 'total_removed'"
        
        print(f"Discovery stats: active={data['active_agents']}, paired={data['paired_agents']}")
        print(f"Scan count: {data['scan_count']}, stale_timeout: {data['stale_timeout_seconds']}s")
    
    def test_discovery_rescan_increments_scan_count(self):
        """POST /api/discovery/rescan triggers re-scan and returns stats with incremented scan_count"""
        # First get current scan count
        stats_before = requests.get(f"{BASE_URL}/api/discovery/stats", headers=self.headers)
        assert stats_before.status_code == 200
        scan_count_before = stats_before.json()["scan_count"]
        
        # Trigger rescan
        response = requests.post(f"{BASE_URL}/api/discovery/rescan", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Response should contain 'message'"
        assert "stats" in data, "Response should contain 'stats'"
        
        # Verify scan_count was incremented
        stats = data["stats"]
        assert "scan_count" in stats, "stats should contain 'scan_count'"
        assert stats["scan_count"] == scan_count_before + 1, f"scan_count should be {scan_count_before + 1}, got {stats['scan_count']}"
        
        print(f"Rescan complete: message={data['message']}")
        print(f"Scan count: before={scan_count_before}, after={stats['scan_count']}")


class TestAuthRequirements:
    """Tests that endpoints require proper authentication"""
    
    def test_updates_check_requires_auth(self):
        """GET /api/updates/check requires admin auth"""
        response = requests.get(f"{BASE_URL}/api/updates/check")
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_updates_status_requires_auth(self):
        """GET /api/updates/status requires admin auth"""
        response = requests.get(f"{BASE_URL}/api/updates/status")
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_health_detailed_requires_auth(self):
        """GET /api/health/detailed requires admin auth"""
        response = requests.get(f"{BASE_URL}/api/health/detailed")
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_discovery_agents_requires_auth(self):
        """GET /api/discovery/agents requires admin auth"""
        response = requests.get(f"{BASE_URL}/api/discovery/agents")
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_discovery_stats_requires_auth(self):
        """GET /api/discovery/stats requires admin auth"""
        response = requests.get(f"{BASE_URL}/api/discovery/stats")
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_discovery_rescan_requires_auth(self):
        """POST /api/discovery/rescan requires admin auth"""
        response = requests.post(f"{BASE_URL}/api/discovery/rescan")
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
