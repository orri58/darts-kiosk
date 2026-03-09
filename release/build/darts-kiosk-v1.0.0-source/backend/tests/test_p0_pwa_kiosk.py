"""
Test P0 Features: PWA, Kiosk Texts, No Emergent Branding
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and get access token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin12345"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


class TestPWAConfig:
    """P0-2: PWA Configuration API Tests"""
    
    def test_get_pwa_config(self):
        """GET /api/settings/pwa returns PWA config"""
        response = requests.get(f"{BASE_URL}/api/settings/pwa")
        assert response.status_code == 200
        data = response.json()
        # Check all 4 fields exist
        assert "app_name" in data
        assert "short_name" in data
        assert "theme_color" in data
        assert "background_color" in data
    
    def test_update_pwa_config_requires_auth(self):
        """PUT /api/settings/pwa requires authentication"""
        response = requests.put(f"{BASE_URL}/api/settings/pwa", json={
            "value": {"app_name": "Test", "short_name": "T", "theme_color": "#000000", "background_color": "#000000"}
        })
        assert response.status_code == 401
    
    def test_update_pwa_config(self, admin_token):
        """PUT /api/settings/pwa with auth updates config"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        new_config = {
            "app_name": "TEST_PWA_App",
            "short_name": "TEST_PWA",
            "theme_color": "#112233",
            "background_color": "#445566"
        }
        response = requests.put(f"{BASE_URL}/api/settings/pwa", json={"value": new_config}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == "TEST_PWA_App"
        assert data["short_name"] == "TEST_PWA"
        assert data["theme_color"] == "#112233"
        assert data["background_color"] == "#445566"
        
        # Verify GET returns updated value
        get_response = requests.get(f"{BASE_URL}/api/settings/pwa")
        assert get_response.status_code == 200
        assert get_response.json()["app_name"] == "TEST_PWA_App"
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/pwa", json={
            "value": {"app_name": "Darts Kiosk", "short_name": "Darts", "theme_color": "#09090b", "background_color": "#09090b"}
        }, headers=headers)


class TestKioskTexts:
    """P0-3: Kiosk Text Settings API Tests"""
    
    def test_get_kiosk_texts(self):
        """GET /api/settings/kiosk-texts returns all 9 fields"""
        response = requests.get(f"{BASE_URL}/api/settings/kiosk-texts")
        assert response.status_code == 200
        data = response.json()
        # Check all 9 configurable fields
        expected_fields = [
            "locked_title", "locked_subtitle", "pricing_hint",
            "game_running", "game_finished", "call_staff",
            "credits_label", "time_label", "staff_hint"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
    
    def test_update_kiosk_texts_requires_auth(self):
        """PUT /api/settings/kiosk-texts requires authentication"""
        response = requests.put(f"{BASE_URL}/api/settings/kiosk-texts", json={
            "value": {"locked_title": "TEST"}
        })
        assert response.status_code == 401
    
    def test_update_kiosk_texts(self, admin_token):
        """PUT /api/settings/kiosk-texts with auth updates texts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        new_texts = {
            "locked_title": "TEST_LOCKED",
            "locked_subtitle": "Test subtitle",
            "pricing_hint": "Test pricing hint",
            "game_running": "GAME RUNNING TEST",
            "game_finished": "GAME FINISHED TEST",
            "call_staff": "Call Staff Test",
            "credits_label": "Credits Test",
            "time_label": "Time Test",
            "staff_hint": "Staff Hint Test"
        }
        response = requests.put(f"{BASE_URL}/api/settings/kiosk-texts", json={"value": new_texts}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["locked_title"] == "TEST_LOCKED"
        assert data["pricing_hint"] == "Test pricing hint"
        
        # Verify GET returns updated value
        get_response = requests.get(f"{BASE_URL}/api/settings/kiosk-texts")
        assert get_response.status_code == 200
        assert get_response.json()["locked_title"] == "TEST_LOCKED"
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/kiosk-texts", json={
            "value": {
                "locked_title": "GESPERRT",
                "locked_subtitle": "Bitte an der Theke freischalten lassen",
                "pricing_hint": "Happy Hour: 50% Rabatt!",
                "game_running": "SPIEL LÄUFT",
                "game_finished": "SPIEL BEENDET",
                "call_staff": "Personal rufen",
                "credits_label": "Spiele übrig",
                "time_label": "Zeit übrig",
                "staff_hint": ""
            }
        }, headers=headers)


class TestNoEmergentBranding:
    """P0-1: Verify NO Emergent branding anywhere"""
    
    def test_no_emergent_in_html(self):
        """Frontend HTML has no Emergent references"""
        response = requests.get(BASE_URL + "/")
        assert response.status_code == 200
        html_lower = response.text.lower()
        # Check for any Emergent branding
        assert "emergent" not in html_lower, "Found 'emergent' reference in HTML"
        assert "made with" not in html_lower, "Found 'Made with' badge in HTML"
        assert "posthog" not in html_lower, "Found PostHog analytics in HTML"
    
    def test_page_title_is_darts_kiosk(self):
        """Page title is 'Darts Kiosk' not Emergent branded"""
        response = requests.get(BASE_URL + "/")
        assert response.status_code == 200
        assert "<title>Darts Kiosk</title>" in response.text


class TestPWAAssets:
    """P0-2: PWA Manifest and Icons"""
    
    def test_manifest_exists(self):
        """manifest.json is accessible"""
        response = requests.get(f"{BASE_URL}/manifest.json")
        assert response.status_code == 200
        data = response.json()
        assert data["display"] == "standalone"
        assert "icons" in data
        assert len(data["icons"]) >= 2
    
    def test_pwa_icon_192(self):
        """192x192 icon loads successfully"""
        response = requests.get(f"{BASE_URL}/icon-192.png")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "image/png"
    
    def test_pwa_icon_512(self):
        """512x512 icon loads successfully"""
        response = requests.get(f"{BASE_URL}/icon-512.png")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "image/png"
    
    def test_apple_touch_icon_meta(self):
        """HTML has apple-touch-icon link"""
        response = requests.get(BASE_URL + "/")
        assert response.status_code == 200
        assert 'apple-touch-icon' in response.text
    
    def test_theme_color_meta(self):
        """HTML has theme-color meta tag"""
        response = requests.get(BASE_URL + "/")
        assert response.status_code == 200
        assert 'theme-color' in response.text


class TestBrandingAPI:
    """Test branding API for Dart Zone cafe branding"""
    
    def test_get_branding(self):
        """GET /api/settings/branding returns cafe branding"""
        response = requests.get(f"{BASE_URL}/api/settings/branding")
        assert response.status_code == 200
        data = response.json()
        assert "cafe_name" in data
        assert data["cafe_name"] == "Dart Zone"
        # logo_url can be set or null - if set, should NOT contain 'emergent' in the URL
        logo = data.get("logo_url")
        if logo:
            assert "emergent" not in logo.lower() or "preview.emergentagent.com" in logo.lower(), \
                "Logo URL should not reference Emergent branding (except for hosting domain)"
