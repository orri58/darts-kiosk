#!/usr/bin/env python3
"""
Backend API Tests for Darts Kiosk + Admin Control System
Testing all authentication, board management, and kiosk functionality
"""

import requests
import sys
import json
from datetime import datetime

class DartsKioskAPITester:
    def __init__(self, base_url="https://board-control-hub.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.staff_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if token:
            test_headers['Authorization'] = f'Bearer {token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.text}")
                except:
                    pass
                self.failed_tests.append({
                    'test': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'endpoint': endpoint
                })
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'test': name,
                'error': str(e),
                'endpoint': endpoint
            })
            return False, {}

    def test_health_endpoints(self):
        """Test basic health endpoints"""
        print("\n=== HEALTH & BASIC ENDPOINTS ===")
        
        # Test root endpoint
        self.run_test("Root API endpoint", "GET", "", 200)
        
        # Test health endpoint
        self.run_test("Health endpoint", "GET", "health", 200)

    def test_admin_authentication(self):
        """Test admin login with username/password and PIN"""
        print("\n=== ADMIN AUTHENTICATION ===")
        
        # Test admin login with username/password
        success, response = self.run_test(
            "Admin login (admin/admin123)",
            "POST",
            "auth/login",
            200,
            data={"username": "admin", "password": "admin123"}
        )
        
        if success and 'access_token' in response:
            self.admin_token = response['access_token']
            print(f"   ✓ Admin token obtained: {self.admin_token[:20]}...")
            
            # Verify user info
            user_info = response.get('user', {})
            if user_info.get('role') == 'admin':
                print(f"   ✓ Admin role confirmed")
            else:
                print(f"   ⚠ Expected admin role, got: {user_info.get('role')}")
        
        # Test admin PIN login
        success, response = self.run_test(
            "Admin PIN login (1234)",
            "POST",
            "auth/pin-login",
            200,
            data={"pin": "1234"}
        )
        
        if success and response.get('user', {}).get('role') == 'admin':
            print(f"   ✓ Admin PIN login successful")

    def test_staff_authentication(self):
        """Test staff PIN login"""
        print("\n=== STAFF AUTHENTICATION ===")
        
        # Test staff PIN login
        success, response = self.run_test(
            "Staff PIN login (0000)",
            "POST",
            "auth/pin-login",
            200,
            data={"pin": "0000"}
        )
        
        if success and 'access_token' in response:
            self.staff_token = response['access_token']
            print(f"   ✓ Staff token obtained: {self.staff_token[:20]}...")
            
            user_info = response.get('user', {})
            if user_info.get('username') == 'wirt':
                print(f"   ✓ Wirt user confirmed")

    def test_board_management(self):
        """Test board listing and management"""
        print("\n=== BOARD MANAGEMENT ===")
        
        if not self.admin_token:
            print("❌ No admin token available - skipping board management tests")
            return

        # Test boards listing
        success, response = self.run_test(
            "List boards",
            "GET",
            "boards",
            200,
            token=self.admin_token
        )
        
        if success and isinstance(response, list):
            board_count = len(response)
            print(f"   ✓ Found {board_count} boards")
            
            if board_count >= 2:
                # Check for default boards
                board_ids = [b.get('board_id') for b in response]
                if 'BOARD-1' in board_ids and 'BOARD-2' in board_ids:
                    print(f"   ✓ Default boards BOARD-1 and BOARD-2 found")
                else:
                    print(f"   ⚠ Expected BOARD-1 and BOARD-2, found: {board_ids}")

        # Test individual board details
        success, response = self.run_test(
            "Get BOARD-1 details",
            "GET",
            "boards/BOARD-1",
            200,
            token=self.admin_token
        )
        
        if success:
            board_info = response.get('board', {})
            print(f"   ✓ BOARD-1 status: {board_info.get('status')}")

    def test_board_unlock_lock_workflow(self):
        """Test complete unlock/lock workflow"""
        print("\n=== BOARD UNLOCK/LOCK WORKFLOW ===")
        
        if not self.admin_token:
            print("❌ No admin token available - skipping unlock/lock tests")
            return

        # Test unlock board (per_game mode with 3 credits)
        success, response = self.run_test(
            "Unlock BOARD-1 (per_game, 3 credits)",
            "POST",
            "boards/BOARD-1/unlock",
            200,
            data={
                "pricing_mode": "per_game",
                "credits": 3,
                "players_count": 1,
                "price_total": 6.0
            },
            token=self.admin_token
        )
        
        if success:
            session_id = response.get('id')
            print(f"   ✓ Session created: {session_id}")
            print(f"   ✓ Credits: {response.get('credits_total')}")
            print(f"   ✓ Price: {response.get('price_total')} €")

        # Check kiosk session status (no auth required)
        success, response = self.run_test(
            "Check kiosk session for BOARD-1",
            "GET",
            "boards/BOARD-1/session",
            200
        )
        
        if success:
            board_status = response.get('board_status')
            session = response.get('session')
            print(f"   ✓ Board status: {board_status}")
            if session:
                print(f"   ✓ Active session found with {session.get('credits_remaining')} credits")

        # Test lock board
        success, response = self.run_test(
            "Lock BOARD-1",
            "POST",
            "boards/BOARD-1/lock",
            200,
            token=self.admin_token
        )
        
        if success:
            print(f"   ✓ Board locked successfully")

    def test_kiosk_game_workflow(self):
        """Test kiosk game start/end workflow"""
        print("\n=== KIOSK GAME WORKFLOW ===")
        
        if not self.admin_token:
            print("❌ No admin token available - skipping kiosk workflow tests")
            return

        # First unlock the board
        success, response = self.run_test(
            "Unlock BOARD-2 for game testing",
            "POST",
            "boards/BOARD-2/unlock",
            200,
            data={
                "pricing_mode": "per_game",
                "credits": 2,
                "players_count": 2,
                "price_total": 4.0
            },
            token=self.admin_token
        )
        
        if not success:
            print("❌ Could not unlock board for kiosk testing")
            return

        # Test game start
        success, response = self.run_test(
            "Start game on BOARD-2 (kiosk)",
            "POST",
            "kiosk/BOARD-2/start-game",
            200,
            data={
                "game_type": "501",
                "players": ["Player1", "Player2"]
            }
        )
        
        if success:
            print(f"   ✓ Game started: {response.get('game_type')}")
            print(f"   ✓ Players: {response.get('players')}")

        # Test game end
        success, response = self.run_test(
            "End game on BOARD-2 (kiosk)",
            "POST",
            "kiosk/BOARD-2/end-game",
            200
        )
        
        if success:
            print(f"   ✓ Game ended")
            print(f"   ✓ Credits remaining: {response.get('credits_remaining')}")
            print(f"   ✓ Should lock: {response.get('should_lock')}")

        # Test call staff
        success, response = self.run_test(
            "Call staff from BOARD-2",
            "POST",
            "kiosk/BOARD-2/call-staff",
            200
        )
        
        if success:
            print(f"   ✓ Staff call registered")

    def test_settings_and_configuration(self):
        """Test settings endpoints"""
        print("\n=== SETTINGS & CONFIGURATION ===")
        
        # Test branding settings (no auth required for read)
        success, response = self.run_test(
            "Get branding settings",
            "GET",
            "settings/branding",
            200
        )
        
        if success:
            print(f"   ✓ Branding loaded: {response.get('cafe_name', 'N/A')}")

        # Test pricing settings
        success, response = self.run_test(
            "Get pricing settings",
            "GET",
            "settings/pricing",
            200
        )
        
        if success:
            per_game = response.get('per_game', {})
            print(f"   ✓ Per-game price: {per_game.get('price_per_credit', 'N/A')} €")

        # Test palettes
        success, response = self.run_test(
            "Get color palettes",
            "GET",
            "settings/palettes",
            200
        )
        
        if success and isinstance(response, dict):
            palette_count = len(response.get('available', []))
            print(f"   ✓ Available palettes: {palette_count}")

    def test_user_management(self):
        """Test user management (admin only)"""
        print("\n=== USER MANAGEMENT ===")
        
        if not self.admin_token:
            print("❌ No admin token available - skipping user management tests")
            return

        # Test list users
        success, response = self.run_test(
            "List users (admin)",
            "GET",
            "users",
            200,
            token=self.admin_token
        )
        
        if success and isinstance(response, list):
            user_count = len(response)
            print(f"   ✓ Found {user_count} users")
            
            # Check for default users
            usernames = [u.get('username') for u in response]
            if 'admin' in usernames and 'wirt' in usernames:
                print(f"   ✓ Default users found: {usernames}")

    def test_logs_and_audit(self):
        """Test audit logs and session logs"""
        print("\n=== LOGS & AUDIT ===")
        
        if not self.admin_token:
            print("❌ No admin token available - skipping logs tests")
            return

        # Test audit logs
        success, response = self.run_test(
            "Get audit logs",
            "GET",
            "logs/audit?limit=10",
            200,
            token=self.admin_token
        )
        
        if success and isinstance(response, list):
            print(f"   ✓ Audit logs count: {len(response)}")

        # Test session logs
        success, response = self.run_test(
            "Get session logs",
            "GET",
            "logs/sessions?limit=10",
            200,
            token=self.admin_token
        )
        
        if success and isinstance(response, list):
            print(f"   ✓ Session logs count: {len(response)}")

    def test_revenue_summary(self):
        """Test revenue reporting"""
        print("\n=== REVENUE SUMMARY ===")
        
        if not self.admin_token:
            print("❌ No admin token available - skipping revenue tests")
            return

        success, response = self.run_test(
            "Get revenue summary",
            "GET",
            "revenue/summary?days=7",
            200,
            token=self.admin_token
        )
        
        if success:
            total_revenue = response.get('total_revenue', 0)
            total_sessions = response.get('total_sessions', 0)
            print(f"   ✓ Total revenue (7 days): {total_revenue} €")
            print(f"   ✓ Total sessions: {total_sessions}")

    def test_enterprise_hardening_features(self):
        """Test enterprise hardening features - setup, backups, detailed health"""
        print("\n=== ENTERPRISE HARDENING FEATURES ===")
        
        # Test setup status (no auth required)
        success, response = self.run_test(
            "Get setup status",
            "GET",
            "setup/status",
            200
        )
        
        if success:
            is_complete = response.get('is_complete', False)
            needs_admin_password = response.get('needs_admin_password', False)
            needs_staff_pin = response.get('needs_staff_pin', False)
            print(f"   ✓ Setup complete: {is_complete}")
            print(f"   ✓ Needs admin password: {needs_admin_password}")
            print(f"   ✓ Needs staff PIN: {needs_staff_pin}")

        # Test detailed health endpoint (admin only)
        if not self.admin_token:
            print("❌ No admin token available - skipping detailed health tests")
        else:
            success, response = self.run_test(
                "Get detailed health status",
                "GET",
                "health/detailed",
                200,
                token=self.admin_token
            )
            
            if success:
                status = response.get('status', 'unknown')
                uptime = response.get('uptime_seconds', 0)
                scheduler_running = response.get('scheduler_running', False)
                backup_running = response.get('backup_service_running', False)
                print(f"   ✓ System status: {status}")
                print(f"   ✓ Uptime: {uptime} seconds")
                print(f"   ✓ Scheduler running: {scheduler_running}")
                print(f"   ✓ Backup service running: {backup_running}")

            # Test backup listing
            success, response = self.run_test(
                "List backups",
                "GET",
                "backups",
                200,
                token=self.admin_token
            )
            
            if success:
                backup_count = len(response.get('backups', []))
                stats = response.get('stats', {})
                print(f"   ✓ Available backups: {backup_count}")
                print(f"   ✓ Retention policy: {stats.get('retention_policy', 'N/A')} backups")
                print(f"   ✓ Backup interval: {stats.get('backup_interval_hours', 'N/A')} hours")

            # Test backup creation
            success, response = self.run_test(
                "Create new backup",
                "POST",
                "backups/create",
                200,
                token=self.admin_token
            )
            
            if success:
                backup_info = response.get('backup', {})
                filename = backup_info.get('filename', 'unknown')
                size_bytes = backup_info.get('size_bytes', 0)
                print(f"   ✓ Backup created: {filename}")
                print(f"   ✓ Backup size: {size_bytes} bytes")

    def test_error_conditions(self):
        """Test various error conditions"""
        print("\n=== ERROR CONDITIONS ===")
        
        # Test invalid login
        self.run_test(
            "Invalid login credentials",
            "POST",
            "auth/login",
            401,
            data={"username": "invalid", "password": "wrong"}
        )
        
        # Test invalid PIN
        self.run_test(
            "Invalid PIN login",
            "POST",
            "auth/pin-login",
            401,
            data={"pin": "9999"}
        )
        
        # Test unauthorized access
        self.run_test(
            "Unauthorized user management access",
            "GET",
            "users",
            401
        )
        
        # Test nonexistent board
        self.run_test(
            "Nonexistent board access",
            "GET",
            "boards/NONEXISTENT",
            404,
            token=self.admin_token if self.admin_token else None
        )

def main():
    """Run all tests"""
    print("🎯 DARTS KIOSK SYSTEM - BACKEND API TESTS")
    print("=" * 50)
    
    tester = DartsKioskAPITester()
    
    try:
        # Run all test suites
        tester.test_health_endpoints()
        tester.test_admin_authentication()
        tester.test_staff_authentication()
        tester.test_board_management()
        tester.test_board_unlock_lock_workflow()
        tester.test_kiosk_game_workflow()
        tester.test_settings_and_configuration()
        tester.test_user_management()
        tester.test_logs_and_audit()
        tester.test_revenue_summary()
        tester.test_enterprise_hardening_features()  # New enterprise features test
        tester.test_error_conditions()
        
    except Exception as e:
        print(f"\n💥 Test execution error: {e}")
        return 1
    
    # Print results
    print(f"\n" + "=" * 50)
    print(f"📊 TEST RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if tester.failed_tests:
        print(f"\n❌ FAILED TESTS:")
        for failure in tester.failed_tests:
            if 'error' in failure:
                print(f"  - {failure['test']}: {failure['error']}")
            else:
                print(f"  - {failure['test']}: Expected {failure['expected']}, got {failure['actual']}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())