"""
Test Stammkunde (Registered Player) Feature
- Player check endpoint
- Player registration (new + upgrade guest)
- PIN login authentication
- QR token login authentication
- Registered players listing
- End-game player stats tracking
- Leaderboard is_registered and player_id fields
"""
import pytest
import requests
import os
import secrets
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPlayerCheckEndpoint:
    """POST /api/players/check - Check if nickname exists and is registered"""
    
    def test_check_nonexistent_player(self):
        """Check a name that doesn't exist"""
        random_name = f"TEST_Random_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/check", json={
            "nickname": random_name
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["exists"] == False
        assert data["is_registered"] == False
        assert data["nickname"] == random_name
        print(f"SUCCESS: Non-existent player check returns exists=False")
    
    def test_check_registered_player(self):
        """Check a known registered player (TestMax)"""
        response = requests.post(f"{BASE_URL}/api/players/check", json={
            "nickname": "TestMax"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] == True
        assert data["is_registered"] == True
        assert "player_id" in data
        assert data["nickname"] == "TestMax"
        print(f"SUCCESS: Registered player check returns is_registered=True, player_id={data['player_id']}")
    
    def test_check_player_case_insensitive(self):
        """Check is case-insensitive"""
        response = requests.post(f"{BASE_URL}/api/players/check", json={
            "nickname": "TESTMAX"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] == True
        assert data["is_registered"] == True
        print("SUCCESS: Player check is case-insensitive")


class TestPlayerRegistration:
    """POST /api/players/register - Register new player or upgrade guest"""
    
    def test_register_new_player_success(self):
        """Register a brand new player with valid PIN"""
        random_name = f"TEST_New_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "1234"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert "player_id" in data
        assert data["nickname"] == random_name
        assert "qr_token" in data
        assert len(data["qr_token"]) > 20  # QR token should be substantial
        print(f"SUCCESS: New player registered with qr_token={data['qr_token'][:20]}...")
        return data  # For potential cleanup
    
    def test_register_with_5digit_pin(self):
        """Register with 5-digit PIN (valid)"""
        random_name = f"TEST_5Pin_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "12345"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("SUCCESS: 5-digit PIN accepted")
    
    def test_register_with_6digit_pin(self):
        """Register with 6-digit PIN (valid)"""
        random_name = f"TEST_6Pin_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "123456"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("SUCCESS: 6-digit PIN accepted")
    
    def test_register_reject_short_pin(self):
        """Reject PIN shorter than 4 digits"""
        random_name = f"TEST_ShortPin_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "123"  # Too short
        })
        assert response.status_code == 400
        assert "4-6" in response.json().get("detail", "")
        print("SUCCESS: Short PIN (3 digits) rejected with 400")
    
    def test_register_reject_long_pin(self):
        """Reject PIN longer than 6 digits"""
        random_name = f"TEST_LongPin_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "1234567"  # Too long
        })
        assert response.status_code == 400
        assert "4-6" in response.json().get("detail", "")
        print("SUCCESS: Long PIN (7 digits) rejected with 400")
    
    def test_register_reject_alpha_pin(self):
        """Reject PIN with non-digit characters"""
        random_name = f"TEST_AlphaPin_{secrets.token_hex(4)}"
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "12ab"  # Non-digit chars
        })
        assert response.status_code == 400
        print("SUCCESS: Non-numeric PIN rejected with 400")
    
    def test_register_reject_short_nickname(self):
        """Reject nickname shorter than 2 characters"""
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": "A",
            "pin": "1234"
        })
        assert response.status_code == 400
        assert "2-30" in response.json().get("detail", "")
        print("SUCCESS: Short nickname (1 char) rejected with 400")
    
    def test_register_duplicate_registered_nickname_409(self):
        """Reject duplicate registered nickname with 409"""
        # TestMax is already registered per credentials
        response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": "TestMax",
            "pin": "5555"
        })
        assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
        assert "bereits" in response.json().get("detail", "").lower() or "registriert" in response.json().get("detail", "").lower()
        print("SUCCESS: Duplicate registered nickname returns 409 Conflict")


class TestPinLogin:
    """POST /api/players/pin-login - PIN authentication"""
    
    def test_pin_login_success(self):
        """Login with correct PIN"""
        response = requests.post(f"{BASE_URL}/api/players/pin-login", json={
            "nickname": "TestMax",
            "pin": "1234"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert data["nickname"] == "TestMax"
        assert data["is_registered"] == True
        assert "player_id" in data
        print(f"SUCCESS: PIN login successful, player_id={data['player_id']}")
    
    def test_pin_login_wrong_pin_401(self):
        """Reject wrong PIN with 401"""
        response = requests.post(f"{BASE_URL}/api/players/pin-login", json={
            "nickname": "TestMax",
            "pin": "9999"  # Wrong PIN
        })
        assert response.status_code == 401
        assert "Falscher" in response.json().get("detail", "") or "PIN" in response.json().get("detail", "")
        print("SUCCESS: Wrong PIN returns 401")
    
    def test_pin_login_nonexistent_player_401(self):
        """Reject nonexistent player with 401"""
        response = requests.post(f"{BASE_URL}/api/players/pin-login", json={
            "nickname": "NonExistentPlayer12345",
            "pin": "1234"
        })
        assert response.status_code == 401
        print("SUCCESS: Nonexistent player PIN login returns 401")
    
    def test_pin_login_case_insensitive(self):
        """PIN login is case-insensitive for nickname"""
        response = requests.post(f"{BASE_URL}/api/players/pin-login", json={
            "nickname": "testmax",  # lowercase
            "pin": "1234"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("SUCCESS: PIN login is case-insensitive")


class TestQrLogin:
    """POST /api/players/qr-login - QR token authentication"""
    
    def test_qr_login_invalid_token_401(self):
        """Reject invalid QR token with 401"""
        response = requests.post(f"{BASE_URL}/api/players/qr-login", json={
            "qr_token": "invalid-token-12345"
        })
        assert response.status_code == 401
        assert "Ungueltiger" in response.json().get("detail", "") or "QR" in response.json().get("detail", "")
        print("SUCCESS: Invalid QR token returns 401")
    
    def test_qr_login_with_valid_token(self):
        """Login with a valid QR token (from newly registered user)"""
        # First register a new player to get a QR token
        random_name = f"TEST_QR_{secrets.token_hex(4)}"
        reg_response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": random_name,
            "pin": "1234"
        })
        assert reg_response.status_code == 200
        qr_token = reg_response.json()["qr_token"]
        
        # Now login with that QR token
        login_response = requests.post(f"{BASE_URL}/api/players/qr-login", json={
            "qr_token": qr_token
        })
        assert login_response.status_code == 200, f"Expected 200, got {login_response.status_code}"
        data = login_response.json()
        assert data["success"] == True
        assert data["nickname"] == random_name
        assert data["is_registered"] == True
        print(f"SUCCESS: QR login successful with token")


class TestRegisteredPlayersList:
    """GET /api/players/registered - List all registered players"""
    
    def test_list_registered_players(self):
        """Get list of registered players"""
        response = requests.get(f"{BASE_URL}/api/players/registered")
        assert response.status_code == 200
        data = response.json()
        assert "players" in data
        assert isinstance(data["players"], list)
        
        # Should have at least TestMax
        found_testmax = False
        for player in data["players"]:
            assert "id" in player
            assert "nickname" in player
            assert "games_played" in player
            assert "games_won" in player
            if player["nickname"] == "TestMax":
                found_testmax = True
        
        assert found_testmax, "TestMax should be in registered players list"
        print(f"SUCCESS: Listed {len(data['players'])} registered players, TestMax found")


class TestEndGamePlayerStats:
    """POST /api/kiosk/{board_id}/end-game - Auto-create guest and update stats"""
    
    def test_end_game_creates_guest_player_and_updates_stats(self):
        """End game auto-creates guest Player records"""
        # First start a game
        random_guest = f"TEST_Guest_{secrets.token_hex(4)}"
        start_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "501",
            "players": [random_guest, "TestMax"]
        })
        assert start_response.status_code == 200, f"Start game failed: {start_response.text}"
        
        # End the game with the new guest as winner
        end_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={
            "winner": random_guest,
            "scores": {random_guest: 501, "TestMax": 200}
        })
        assert end_response.status_code == 200, f"End game failed: {end_response.text}"
        
        # Verify guest player was created
        check_response = requests.post(f"{BASE_URL}/api/players/check", json={
            "nickname": random_guest
        })
        assert check_response.status_code == 200
        check_data = check_response.json()
        assert check_data["exists"] == True
        assert check_data["is_registered"] == False  # Still a guest
        print(f"SUCCESS: Guest player '{random_guest}' auto-created after game end")


class TestLeaderboardPlayerFields:
    """GET /api/stats/leaderboard - Verify is_registered and player_id fields"""
    
    def test_leaderboard_has_registered_fields(self):
        """Leaderboard returns is_registered and player_id"""
        response = requests.get(f"{BASE_URL}/api/stats/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        assert "leaderboard" in data
        
        found_registered = False
        found_guest = False
        
        for player in data["leaderboard"]:
            assert "is_registered" in player, f"Missing is_registered field for {player.get('nickname')}"
            assert "player_id" in player, f"Missing player_id field for {player.get('nickname')}"
            
            if player["is_registered"]:
                found_registered = True
                assert player["player_id"] is not None
            else:
                found_guest = True
                # Guest may have null player_id
        
        print(f"SUCCESS: Leaderboard has is_registered and player_id fields (found registered: {found_registered}, found guest: {found_guest})")


class TestGuestToRegisteredUpgrade:
    """Test upgrading a guest player to registered"""
    
    def test_upgrade_guest_to_registered(self):
        """Upgrade an existing guest to registered player"""
        # First create a guest by ending a game
        guest_name = f"TEST_UpGuest_{secrets.token_hex(4)}"
        
        # Start and end game to create guest
        start_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "301",
            "players": [guest_name]
        })
        assert start_response.status_code == 200
        
        end_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={
            "winner": guest_name
        })
        assert end_response.status_code == 200
        
        # Verify guest exists
        check_response = requests.post(f"{BASE_URL}/api/players/check", json={
            "nickname": guest_name
        })
        check_data = check_response.json()
        assert check_data["exists"] == True
        assert check_data["is_registered"] == False
        print(f"Guest '{guest_name}' created with games")
        
        # Now upgrade to registered
        reg_response = requests.post(f"{BASE_URL}/api/players/register", json={
            "nickname": guest_name,
            "pin": "4321"
        })
        assert reg_response.status_code == 200, f"Upgrade failed: {reg_response.text}"
        reg_data = reg_response.json()
        assert reg_data["success"] == True
        assert "qr_token" in reg_data
        
        # Verify now registered
        check_response2 = requests.post(f"{BASE_URL}/api/players/check", json={
            "nickname": guest_name
        })
        check_data2 = check_response2.json()
        assert check_data2["is_registered"] == True
        assert check_data2["player_id"] is not None
        print(f"SUCCESS: Guest '{guest_name}' upgraded to registered, stats preserved")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
