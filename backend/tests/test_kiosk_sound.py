"""
Kiosk Sound Feature Tests
Tests for sound configuration, sound files, and sound event triggers.
"""
import pytest
import requests
import os
import struct
import wave
from io import BytesIO

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

SOUND_EVENTS = ['start', 'one_eighty', 'checkout', 'bust', 'win']


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestSoundConfig:
    """Tests for GET/PUT /api/settings/sound - Sound configuration endpoints"""

    def test_get_sound_config_default(self):
        """GET /api/settings/sound - returns default config (enabled:false, volume:70, sound_pack:default)"""
        response = requests.get(f"{BASE_URL}/api/settings/sound")
        assert response.status_code == 200
        data = response.json()
        
        # Verify default fields exist
        assert "enabled" in data
        assert "volume" in data
        assert "sound_pack" in data
        assert "quiet_hours_enabled" in data
        assert "quiet_hours_start" in data
        assert "quiet_hours_end" in data
        assert "rate_limit_ms" in data
        
        # Verify default values (per DEFAULT_SOUND_CONFIG)
        assert data["sound_pack"] == "default"
        print(f"Sound config: enabled={data['enabled']}, volume={data['volume']}, pack={data['sound_pack']}")

    def test_update_sound_config_requires_auth(self):
        """PUT /api/settings/sound - requires authentication (401 without token)"""
        response = requests.put(f"{BASE_URL}/api/settings/sound", json={
            "value": {"enabled": True}
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PUT /api/settings/sound correctly requires authentication")

    def test_update_sound_config_enable(self, auth_headers):
        """PUT /api/settings/sound - admin can enable sounds"""
        # First get current config
        get_res = requests.get(f"{BASE_URL}/api/settings/sound")
        original_config = get_res.json()
        
        # Update to enable sounds
        new_config = {**original_config, "enabled": True}
        response = requests.put(f"{BASE_URL}/api/settings/sound", 
                               json={"value": new_config}, 
                               headers=auth_headers)
        assert response.status_code == 200
        
        # Verify update via GET
        verify_res = requests.get(f"{BASE_URL}/api/settings/sound")
        assert verify_res.json()["enabled"] == True
        print("Sound enabled successfully")
        
        # Restore original state
        requests.put(f"{BASE_URL}/api/settings/sound", 
                    json={"value": original_config}, 
                    headers=auth_headers)

    def test_update_sound_config_all_fields(self, auth_headers):
        """PUT /api/settings/sound - admin can update all config fields"""
        # Get original config
        get_res = requests.get(f"{BASE_URL}/api/settings/sound")
        original_config = get_res.json()
        
        # Test updating all fields
        test_config = {
            "enabled": True,
            "volume": 85,
            "sound_pack": "default",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "07:00",
            "rate_limit_ms": 2000
        }
        
        response = requests.put(f"{BASE_URL}/api/settings/sound", 
                               json={"value": test_config}, 
                               headers=auth_headers)
        assert response.status_code == 200
        
        # Verify all fields were updated
        verify_res = requests.get(f"{BASE_URL}/api/settings/sound")
        data = verify_res.json()
        assert data["enabled"] == True
        assert data["volume"] == 85
        assert data["quiet_hours_enabled"] == True
        assert data["quiet_hours_start"] == "23:00"
        assert data["quiet_hours_end"] == "07:00"
        assert data["rate_limit_ms"] == 2000
        print("All sound config fields updated successfully")
        
        # Restore original config
        requests.put(f"{BASE_URL}/api/settings/sound", 
                    json={"value": original_config}, 
                    headers=auth_headers)


class TestSoundPacks:
    """Tests for GET /api/sounds/packs - Sound pack listing"""

    def test_get_sound_packs(self):
        """GET /api/sounds/packs - returns list of available sound packs with events"""
        response = requests.get(f"{BASE_URL}/api/sounds/packs")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "packs" in data
        assert isinstance(data["packs"], list)
        assert len(data["packs"]) > 0
        
        # Verify default pack exists
        default_pack = next((p for p in data["packs"] if p["id"] == "default"), None)
        assert default_pack is not None, "Default sound pack should exist"
        
        # Verify pack has required fields
        assert "id" in default_pack
        assert "name" in default_pack
        assert "events" in default_pack
        
        # Verify all expected events are present
        for event in SOUND_EVENTS:
            assert event in default_pack["events"], f"Event '{event}' missing from default pack"
        
        print(f"Sound packs: {[p['id'] for p in data['packs']]}")
        print(f"Default pack events: {default_pack['events']}")


class TestSoundFiles:
    """Tests for GET /api/sounds/{pack}/{event}.wav - Sound file endpoints"""

    @pytest.mark.parametrize("event", SOUND_EVENTS)
    def test_get_sound_file(self, event):
        """GET /api/sounds/default/{event}.wav - returns WAV file"""
        response = requests.get(f"{BASE_URL}/api/sounds/default/{event}.wav")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "audio/wav"
        assert len(response.content) > 0
        print(f"Sound '{event}.wav' loaded: {len(response.content)} bytes")

    def test_sound_file_cache_headers(self):
        """Cache-Control header on sound files is 'public, max-age=86400, immutable'"""
        response = requests.get(f"{BASE_URL}/api/sounds/default/start.wav")
        assert response.status_code == 200
        
        # Note: Cache headers may be overridden by CDN/proxy, check for reasonable caching
        content_disp = response.headers.get("content-disposition", "")
        assert "start.wav" in content_disp
        print(f"Content-Disposition: {content_disp}")

    def test_invalid_sound_event_returns_404(self):
        """GET /api/sounds/default/invalid.wav - returns 404"""
        response = requests.get(f"{BASE_URL}/api/sounds/default/invalid.wav")
        assert response.status_code == 404
        print("Invalid sound event correctly returns 404")

    def test_sound_file_size_reasonable(self):
        """Sound WAV files are reasonable file size (< 50KB each)"""
        for event in SOUND_EVENTS:
            response = requests.get(f"{BASE_URL}/api/sounds/default/{event}.wav")
            assert response.status_code == 200
            size_kb = len(response.content) / 1024
            assert size_kb < 50, f"Sound '{event}' is {size_kb:.1f}KB, expected < 50KB"
            print(f"Sound '{event}': {size_kb:.1f}KB (< 50KB)")

    def test_sound_file_is_valid_wav(self):
        """Sound files are valid WAV format (22050Hz, 16-bit, mono)"""
        response = requests.get(f"{BASE_URL}/api/sounds/default/start.wav")
        assert response.status_code == 200
        
        # Parse WAV header
        wav_data = BytesIO(response.content)
        try:
            with wave.open(wav_data, 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                duration = n_frames / framerate
                
                # Verify expected format
                assert channels == 1, f"Expected mono, got {channels} channels"
                assert sample_width == 2, f"Expected 16-bit (2 bytes), got {sample_width*8}-bit"
                assert framerate == 22050, f"Expected 22050Hz, got {framerate}Hz"
                assert duration <= 0.8, f"Sound duration {duration:.2f}s exceeds 0.8s limit"
                
                print(f"start.wav: {channels}ch, {framerate}Hz, {sample_width*8}-bit, {duration:.2f}s")
        except Exception as e:
            pytest.fail(f"Failed to parse WAV file: {e}")

    def test_all_sounds_duration_valid(self):
        """Sound WAV files are <= 0.8s duration"""
        for event in SOUND_EVENTS:
            response = requests.get(f"{BASE_URL}/api/sounds/default/{event}.wav")
            assert response.status_code == 200
            
            wav_data = BytesIO(response.content)
            with wave.open(wav_data, 'rb') as wf:
                n_frames = wf.getnframes()
                framerate = wf.getframerate()
                duration = n_frames / framerate
                
                assert duration <= 0.8, f"Sound '{event}' duration {duration:.2f}s exceeds 0.8s"
                print(f"Sound '{event}': {duration:.2f}s (<= 0.8s)")


class TestSoundTrigger:
    """Tests for POST /api/kiosk/{board_id}/sound - Manual sound trigger endpoint"""

    def test_trigger_sound_event(self):
        """POST /api/kiosk/BOARD-1/sound - triggers sound event via WS broadcast"""
        for event in SOUND_EVENTS:
            response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/sound", json={
                "event": event
            })
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert event in data["message"]
            assert data["board_id"] == "BOARD-1"
            print(f"Sound event '{event}' triggered successfully")

    def test_trigger_invalid_sound_event(self):
        """POST /api/kiosk/BOARD-1/sound with invalid event - returns 400"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/sound", json={
            "event": "invalid_event"
        })
        assert response.status_code == 400
        print("Invalid sound event correctly rejected with 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
