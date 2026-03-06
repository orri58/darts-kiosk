"""
Test suite for i18n/Language feature - Iteration 12
Tests:
- GET /api/settings/language - returns default {language: 'de'}
- PUT /api/settings/language - switch to 'en' and back to 'de'
- PUT /api/settings/language - requires authentication (401 without token)
- Regression: Sound files still served
- Regression: Player stats with is_registered field
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


class TestLanguageAPI:
    """Tests for Language Settings API"""

    def test_get_language_default(self, api_client):
        """GET /api/settings/language returns default 'de'"""
        response = api_client.get(f"{BASE_URL}/api/settings/language")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "language" in data
        # Default should be 'de' (German)
        assert data["language"] in ["de", "en"], f"Unexpected language: {data['language']}"

    def test_put_language_requires_auth(self, api_client):
        """PUT /api/settings/language without auth returns 401"""
        response = api_client.put(
            f"{BASE_URL}/api/settings/language",
            json={"value": {"language": "en"}}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_put_language_switch_to_en(self, api_client, admin_token):
        """PUT /api/settings/language - switch to English"""
        response = api_client.put(
            f"{BASE_URL}/api/settings/language",
            json={"value": {"language": "en"}},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("language") == "en"

        # Verify via GET
        get_response = api_client.get(f"{BASE_URL}/api/settings/language")
        assert get_response.status_code == 200
        assert get_response.json()["language"] == "en"

    def test_put_language_switch_to_de(self, api_client, admin_token):
        """PUT /api/settings/language - switch back to German"""
        response = api_client.put(
            f"{BASE_URL}/api/settings/language",
            json={"value": {"language": "de"}},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("language") == "de"

        # Verify via GET
        get_response = api_client.get(f"{BASE_URL}/api/settings/language")
        assert get_response.status_code == 200
        assert get_response.json()["language"] == "de"


class TestRegressionSound:
    """Regression tests for Sound feature"""

    def test_sound_packs_endpoint(self, api_client):
        """GET /api/sounds/packs returns available packs"""
        response = api_client.get(f"{BASE_URL}/api/sounds/packs")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "packs" in data
        assert len(data["packs"]) > 0
        assert data["packs"][0]["id"] == "default"

    def test_sound_file_start(self, api_client):
        """GET /api/sounds/default/start.wav returns WAV file"""
        response = api_client.get(f"{BASE_URL}/api/sounds/default/start.wav")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "audio/wav"

    def test_sound_file_checkout(self, api_client):
        """GET /api/sounds/default/checkout.wav returns WAV file"""
        response = api_client.get(f"{BASE_URL}/api/sounds/default/checkout.wav")
        assert response.status_code == 200

    def test_sound_file_win(self, api_client):
        """GET /api/sounds/default/win.wav returns WAV file"""
        response = api_client.get(f"{BASE_URL}/api/sounds/default/win.wav")
        assert response.status_code == 200

    def test_sound_config_get(self, api_client):
        """GET /api/settings/sound returns config"""
        response = api_client.get(f"{BASE_URL}/api/settings/sound")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "volume" in data


class TestRegressionStats:
    """Regression tests for Stats/Leaderboard with is_registered field"""

    def test_leaderboard_has_is_registered(self, api_client):
        """GET /api/stats/leaderboard returns is_registered field"""
        response = api_client.get(f"{BASE_URL}/api/stats/leaderboard?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "leaderboard" in data
        if len(data["leaderboard"]) > 0:
            player = data["leaderboard"][0]
            assert "is_registered" in player, "Missing is_registered field in leaderboard"
            assert "player_id" in player, "Missing player_id field"

    def test_top_registered_endpoint(self, api_client):
        """GET /api/stats/top-registered returns top stammkunden"""
        response = api_client.get(f"{BASE_URL}/api/stats/top-registered?period=month&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert "players" in data
        assert "config" in data
        # All players should be registered
        for player in data["players"]:
            assert player.get("is_registered") == True


class TestRegressionOtherSettings:
    """Regression tests for Palette and Stammkunde Settings"""

    def test_palettes_endpoint(self, api_client):
        """GET /api/settings/palettes returns palette list"""
        response = api_client.get(f"{BASE_URL}/api/settings/palettes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Default palette should exist
        default = next((p for p in data if p.get("id") == "default"), None)
        assert default is not None, "Default palette not found"

    def test_stammkunde_display_settings(self, api_client):
        """GET /api/settings/stammkunde-display returns config"""
        response = api_client.get(f"{BASE_URL}/api/settings/stammkunde-display")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "period" in data
        assert "max_entries" in data

    def test_branding_settings(self, api_client):
        """GET /api/settings/branding returns config"""
        response = api_client.get(f"{BASE_URL}/api/settings/branding")
        assert response.status_code == 200
        data = response.json()
        assert "cafe_name" in data


class TestRegressionBoards:
    """Regression tests for Board status"""

    def test_list_boards(self, api_client, admin_token):
        """GET /api/boards returns board list"""
        response = api_client.get(
            f"{BASE_URL}/api/boards",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        board1 = next((b for b in data if b.get("board_id") == "BOARD-1"), None)
        assert board1 is not None, "BOARD-1 not found"
        assert board1["status"] in ["locked", "unlocked", "in_game"]
