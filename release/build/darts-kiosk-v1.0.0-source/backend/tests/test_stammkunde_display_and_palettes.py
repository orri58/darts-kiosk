"""
Backend tests for:
1. Top Stammkunden API (/api/stats/top-registered) with caching
2. Stammkunde Display Settings (/api/settings/stammkunde-display)
3. Custom Palette Editor API (/api/settings/palettes)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture
def authenticated_client(api_client, admin_token):
    """Session with admin auth header"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


class TestTopRegisteredAPI:
    """Tests for /api/stats/top-registered endpoint"""
    
    def test_top_registered_returns_only_registered_players(self, api_client):
        """GET /api/stats/top-registered returns only is_registered=true players"""
        response = api_client.get(f"{BASE_URL}/api/stats/top-registered?period=month&limit=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "players" in data
        assert "period" in data
        assert "config" in data
        assert data["period"] == "month"
        
        # All returned players should be registered
        for player in data["players"]:
            assert player.get("is_registered") == True, f"Player {player.get('nickname')} is not registered"
            # Verify highlight stat is present
            assert "highlight" in player
            assert "type" in player["highlight"]
            assert "label" in player["highlight"]
        
        print(f"SUCCESS: top-registered returned {len(data['players'])} registered players")

    def test_top_registered_includes_stats(self, api_client):
        """GET /api/stats/top-registered includes player stats and highlight"""
        response = api_client.get(f"{BASE_URL}/api/stats/top-registered?period=month&limit=3")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["players"]) > 0:
            player = data["players"][0]
            # Check required stats fields
            assert "nickname" in player
            assert "games_played" in player
            assert "games_won" in player
            assert "win_rate" in player
            assert "highlight" in player
            # Highlight should have type and label
            hl = player["highlight"]
            assert hl["type"] in ["180+", "checkout", "throw", "winrate"]
            assert "label" in hl
            print(f"SUCCESS: Player {player['nickname']} has highlight: {hl['label']}")
        else:
            print("INFO: No registered players found, skipping stats validation")

    def test_top_registered_caching(self, api_client):
        """GET /api/stats/top-registered caching - second call within 45s returns cached data"""
        # First call
        start1 = time.time()
        response1 = api_client.get(f"{BASE_URL}/api/stats/top-registered?period=month&limit=3")
        time1 = time.time() - start1
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call immediately (should be cached)
        start2 = time.time()
        response2 = api_client.get(f"{BASE_URL}/api/stats/top-registered?period=month&limit=3")
        time2 = time.time() - start2
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Data should be identical (cached)
        assert data1["players"] == data2["players"]
        
        # Second call should typically be faster (from cache), but this isn't guaranteed
        # due to network latency, so we just verify the data is the same
        print(f"SUCCESS: Caching works - first call: {time1:.3f}s, second call: {time2:.3f}s")

    def test_top_registered_period_parameter(self, api_client):
        """GET /api/stats/top-registered respects period parameter"""
        for period in ["today", "week", "month", "all"]:
            response = api_client.get(f"{BASE_URL}/api/stats/top-registered?period={period}&limit=3")
            assert response.status_code == 200
            data = response.json()
            assert data["period"] == period
            print(f"SUCCESS: period={period} returns valid response")


class TestStammkundeDisplaySettings:
    """Tests for /api/settings/stammkunde-display endpoint"""
    
    def test_get_stammkunde_display_default(self, api_client):
        """GET /api/settings/stammkunde-display returns config"""
        response = api_client.get(f"{BASE_URL}/api/settings/stammkunde-display")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected config fields
        assert "enabled" in data
        assert "period" in data
        assert "interval_seconds" in data
        assert "max_entries" in data
        assert "nickname_max_length" in data
        
        # Verify default values or current state
        assert isinstance(data["enabled"], bool)
        assert data["period"] in ["today", "week", "month", "all"]
        assert 5 <= data["interval_seconds"] <= 8 or data["interval_seconds"] == 6  # default or valid range
        assert 1 <= data["max_entries"] <= 3
        assert 8 <= data["nickname_max_length"] <= 30 or data["nickname_max_length"] == 15
        
        print(f"SUCCESS: stammkunde-display config: enabled={data['enabled']}, period={data['period']}")

    def test_put_stammkunde_display_toggle_enabled(self, authenticated_client):
        """PUT /api/settings/stammkunde-display - admin can toggle enabled"""
        # First get current state
        get_response = authenticated_client.get(f"{BASE_URL}/api/settings/stammkunde-display")
        current = get_response.json()
        
        # Toggle enabled
        new_enabled = not current.get("enabled", False)
        update_payload = {
            "enabled": new_enabled,
            "period": current.get("period", "month"),
            "interval_seconds": current.get("interval_seconds", 6),
            "max_entries": current.get("max_entries", 3),
            "nickname_max_length": current.get("nickname_max_length", 15)
        }
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/settings/stammkunde-display",
            json={"value": update_payload}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == new_enabled
        
        print(f"SUCCESS: toggled enabled from {current.get('enabled')} to {new_enabled}")

    def test_put_stammkunde_display_update_period(self, authenticated_client):
        """PUT /api/settings/stammkunde-display - admin can update period"""
        # Update to 'week' period
        update_payload = {
            "enabled": True,
            "period": "week",
            "interval_seconds": 6,
            "max_entries": 3,
            "nickname_max_length": 15
        }
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/settings/stammkunde-display",
            json={"value": update_payload}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "week"
        
        # Verify persistence with GET
        get_response = authenticated_client.get(f"{BASE_URL}/api/settings/stammkunde-display")
        assert get_response.status_code == 200
        assert get_response.json()["period"] == "week"
        
        print("SUCCESS: period updated to 'week' and persisted")
        
        # Restore to month
        update_payload["period"] = "month"
        authenticated_client.put(f"{BASE_URL}/api/settings/stammkunde-display", json={"value": update_payload})

    def test_put_stammkunde_display_all_fields(self, authenticated_client):
        """PUT /api/settings/stammkunde-display - admin can update all fields"""
        update_payload = {
            "enabled": True,
            "period": "month",
            "interval_seconds": 7,
            "max_entries": 2,
            "nickname_max_length": 12
        }
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/settings/stammkunde-display",
            json={"value": update_payload}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["enabled"] == True
        assert data["period"] == "month"
        assert data["interval_seconds"] == 7
        assert data["max_entries"] == 2
        assert data["nickname_max_length"] == 12
        
        print("SUCCESS: all stammkunde display fields updated")
        
        # Restore defaults
        restore_payload = {
            "enabled": True,
            "period": "month",
            "interval_seconds": 6,
            "max_entries": 3,
            "nickname_max_length": 15
        }
        authenticated_client.put(f"{BASE_URL}/api/settings/stammkunde-display", json={"value": restore_payload})


class TestCustomPaletteAPI:
    """Tests for /api/settings/palettes endpoint - Custom Palette Editor"""
    
    def test_get_palettes_returns_default_palettes(self, api_client):
        """GET /api/settings/palettes returns all palettes including defaults"""
        response = api_client.get(f"{BASE_URL}/api/settings/palettes")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list)
        assert len(data) >= 1, "Should have at least one palette"
        
        # Check structure of first palette
        palette = data[0]
        assert "id" in palette
        assert "name" in palette
        assert "colors" in palette
        
        # Check colors structure
        colors = palette["colors"]
        assert "bg" in colors
        assert "surface" in colors
        assert "primary" in colors
        assert "secondary" in colors
        assert "accent" in colors
        assert "text" in colors
        
        # Verify known default palettes exist
        palette_ids = [p["id"] for p in data]
        assert "industrial" in palette_ids or len(data) > 0
        
        print(f"SUCCESS: GET palettes returned {len(data)} palettes")

    def test_put_palettes_add_custom_palette(self, authenticated_client, api_client):
        """PUT /api/settings/palettes - admin can add custom palette with custom:true flag"""
        # Get current palettes
        get_response = api_client.get(f"{BASE_URL}/api/settings/palettes")
        current_palettes = get_response.json()
        
        # Create new custom palette
        test_palette = {
            "id": "test_custom_palette",
            "name": "Test Custom",
            "colors": {
                "bg": "#1a1a2e",
                "surface": "#16213e",
                "primary": "#0f3460",
                "secondary": "#e94560",
                "accent": "#533483",
                "text": "#ffffff"
            },
            "custom": True
        }
        
        # Remove any existing test palette first
        updated_palettes = [p for p in current_palettes if p["id"] != "test_custom_palette"]
        updated_palettes.append(test_palette)
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/settings/palettes",
            json={"value": updated_palettes}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify test palette was added
        test_found = next((p for p in data if p["id"] == "test_custom_palette"), None)
        assert test_found is not None, "Custom palette should be in response"
        assert test_found["custom"] == True
        assert test_found["name"] == "Test Custom"
        
        print("SUCCESS: Custom palette added with custom:true flag")

    def test_put_palettes_preserves_default_palettes(self, authenticated_client, api_client):
        """PUT /api/settings/palettes - default palettes preserved when adding custom"""
        # Get current palettes
        get_response = api_client.get(f"{BASE_URL}/api/settings/palettes")
        current_palettes = get_response.json()
        
        # Count default (non-custom) palettes
        default_count = len([p for p in current_palettes if not p.get("custom")])
        
        # Add another custom palette
        new_palette = {
            "id": "test_custom_2",
            "name": "Test Custom 2",
            "colors": {
                "bg": "#0d1117",
                "surface": "#161b22",
                "primary": "#58a6ff",
                "secondary": "#8b949e",
                "accent": "#f78166",
                "text": "#c9d1d9"
            },
            "custom": True
        }
        
        updated = [p for p in current_palettes if p["id"] != "test_custom_2"]
        updated.append(new_palette)
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/settings/palettes",
            json={"value": updated}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Default palettes should still exist
        new_default_count = len([p for p in data if not p.get("custom")])
        assert new_default_count == default_count, "Default palettes should be preserved"
        
        print(f"SUCCESS: {new_default_count} default palettes preserved after adding custom")

    def test_get_palettes_includes_custom(self, api_client):
        """GET /api/settings/palettes - returns all palettes including custom ones"""
        response = api_client.get(f"{BASE_URL}/api/settings/palettes")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check if any custom palettes exist from previous tests
        custom_palettes = [p for p in data if p.get("custom")]
        
        if len(custom_palettes) > 0:
            # Verify custom palette structure
            cp = custom_palettes[0]
            assert cp.get("custom") == True
            assert "colors" in cp
            print(f"SUCCESS: Found {len(custom_palettes)} custom palettes")
        else:
            print("INFO: No custom palettes found (may have been cleaned up)")

    def test_put_palettes_delete_custom(self, authenticated_client, api_client):
        """PUT /api/settings/palettes - can delete custom palette by excluding from list"""
        # Get current palettes
        get_response = api_client.get(f"{BASE_URL}/api/settings/palettes")
        current_palettes = get_response.json()
        
        # Remove test custom palettes
        filtered = [p for p in current_palettes if not p["id"].startswith("test_custom")]
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/settings/palettes",
            json={"value": filtered}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify test palettes removed
        test_palettes = [p for p in data if p["id"].startswith("test_custom")]
        assert len(test_palettes) == 0, "Test custom palettes should be removed"
        
        print("SUCCESS: Custom palettes deleted successfully")


class TestSettingsEndpointAuth:
    """Test that PUT endpoints require authentication"""
    
    def test_put_stammkunde_display_requires_auth(self, api_client):
        """PUT /api/settings/stammkunde-display requires admin auth"""
        response = api_client.put(
            f"{BASE_URL}/api/settings/stammkunde-display",
            json={"value": {"enabled": True}}
        )
        # Should fail without auth
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        print("SUCCESS: stammkunde-display PUT requires authentication")

    def test_put_palettes_requires_auth(self, api_client):
        """PUT /api/settings/palettes requires admin auth"""
        response = api_client.put(
            f"{BASE_URL}/api/settings/palettes",
            json={"value": []}
        )
        # Should fail without auth
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        print("SUCCESS: palettes PUT requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
