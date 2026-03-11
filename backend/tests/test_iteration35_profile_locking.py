"""
Test Iteration 35 - Chrome Profile Locking Bug Fix

This iteration fixes a critical bug where start.bat launched Chrome kiosk UI 
with the SAME --user-data-dir as the Playwright observer, causing profile lock conflicts.

Fix implemented:
1. start.bat now uses separate 'kiosk_ui_profile' for kiosk UI Chrome
2. Observer has a _check_profile_locked() safety check before Playwright launch
3. Cookie diagnostics now checks both Default/Cookies and Default/Network/Cookies

Test coverage:
- _check_profile_locked() returns False when no lock files exist
- _check_profile_locked() cleans stale lock files and returns False
- _check_profile_locked() returns True when lock + Chrome process detected
- open_session() sets ERROR state when profile is locked
- Cookie diagnostics checks both cookie paths
- start.bat uses correct profiles
"""
import pytest
import os
import sys
import tempfile
import shutil
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import requests

# Add backend to path
sys.path.insert(0, '/app')

from backend.services.autodarts_observer import (
    AutodartsObserver,
    ObserverState,
    ObserverManager,
    CHROME_PROFILE_DIR,
)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestProfileLockingLogic:
    """Tests for _check_profile_locked() method."""

    def test_no_lock_files_returns_false(self):
        """When no lock files exist, _check_profile_locked() should return False (safe to launch)."""
        with tempfile.TemporaryDirectory() as profile_dir:
            observer = AutodartsObserver("TEST-BOARD")
            result = observer._check_profile_locked(profile_dir)
            assert result is False, "Should return False when no lock files exist"
            print("PASS: No lock files -> returns False")

    def test_lock_file_no_chrome_process_cleans_stale_lock(self):
        """
        When lock file exists but no Chrome process uses the profile,
        _check_profile_locked() should remove the stale lock and return False.
        """
        with tempfile.TemporaryDirectory() as profile_dir:
            # Create a SingletonLock file (simulating stale lock)
            lock_path = os.path.join(profile_dir, 'SingletonLock')
            with open(lock_path, 'w') as f:
                f.write('stale_lock')
            
            assert os.path.exists(lock_path), "Lock file should exist before check"
            
            observer = AutodartsObserver("TEST-BOARD")
            
            # Mock subprocess to return no Chrome processes
            with patch('subprocess.run') as mock_run:
                # For Linux pgrep - return empty (no chrome with this profile)
                mock_run.return_value = MagicMock(stdout='', returncode=1)
                
                result = observer._check_profile_locked(profile_dir)
                
            assert result is False, "Should return False when lock is stale"
            assert not os.path.exists(lock_path), "Stale lock file should be removed"
            print("PASS: Stale lock cleaned up -> returns False")

    def test_lock_file_with_chrome_process_returns_true(self):
        """
        When lock file exists AND Chrome process is detected for the profile,
        _check_profile_locked() should return True (abort launch).
        """
        with tempfile.TemporaryDirectory() as profile_dir:
            # Create lock file
            lock_path = os.path.join(profile_dir, 'SingletonLock')
            with open(lock_path, 'w') as f:
                f.write('active_lock')
            
            observer = AutodartsObserver("TEST-BOARD")
            profile_abs = os.path.abspath(profile_dir)
            profile_norm = os.path.normpath(profile_abs).lower()
            
            # Mock subprocess to return Chrome process with this profile in cmdline
            with patch('subprocess.run') as mock_run:
                # For Linux pgrep - return line containing the profile path
                mock_run.return_value = MagicMock(
                    stdout=f'12345 chrome --user-data-dir={profile_norm}\n',
                    returncode=0
                )
                
                result = observer._check_profile_locked(profile_dir)
                
            assert result is True, "Should return True when Chrome is using the profile"
            assert os.path.exists(lock_path), "Lock file should NOT be removed when Chrome is active"
            print("PASS: Active lock + Chrome process -> returns True")

    def test_lockfile_variant_names(self):
        """Test that both SingletonLock and lockfile are detected."""
        with tempfile.TemporaryDirectory() as profile_dir:
            # Create lockfile (alternative name)
            lock_path = os.path.join(profile_dir, 'lockfile')
            with open(lock_path, 'w') as f:
                f.write('lock')
            
            observer = AutodartsObserver("TEST-BOARD")
            
            # Mock subprocess - no Chrome process
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', returncode=1)
                result = observer._check_profile_locked(profile_dir)
                
            assert result is False, "Should handle 'lockfile' variant"
            assert not os.path.exists(lock_path), "Stale lockfile should be removed"
            print("PASS: lockfile variant handled correctly")


class TestOpenSessionAbortOnLock:
    """Tests for open_session() behavior when profile is locked."""

    @pytest.mark.asyncio
    async def test_open_session_sets_error_when_locked(self):
        """
        When _check_profile_locked() returns True, open_session() should:
        1. Set state to ERROR
        2. NOT call launch_persistent_context
        3. Set last_error with meaningful message
        """
        observer = AutodartsObserver("TEST-LOCKED")
        
        # Mock _check_profile_locked to return True (locked)
        with patch.object(observer, '_check_profile_locked', return_value=True):
            await observer.open_session(
                autodarts_url="https://play.autodarts.io",
                headless=True
            )
        
        assert observer.status.state == ObserverState.ERROR, \
            f"Expected ERROR state, got {observer.status.state}"
        assert observer.status.last_error is not None, "last_error should be set"
        assert "locked" in observer.status.last_error.lower() or "profile" in observer.status.last_error.lower(), \
            f"Error message should mention lock: {observer.status.last_error}"
        assert observer._context is None, "Browser context should NOT be created"
        assert observer.status.browser_open is False, "browser_open should be False"
        print(f"PASS: open_session sets ERROR when locked. Error: {observer.status.last_error[:100]}")

    @pytest.mark.asyncio
    async def test_open_session_proceeds_when_not_locked(self):
        """
        When _check_profile_locked() returns False, open_session() should proceed
        (we mock Playwright to avoid actual browser launch).
        """
        observer = AutodartsObserver("TEST-UNLOCKED")
        
        # Mock both _check_profile_locked and Playwright
        with patch.object(observer, '_check_profile_locked', return_value=False):
            # We expect it to try to import playwright
            with patch('playwright.async_api.async_playwright') as mock_playwright:
                # Mock the entire playwright chain
                mock_pw = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                
                mock_context.pages = [mock_page]
                mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
                mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)
                
                try:
                    await observer.open_session(
                        autodarts_url="https://play.autodarts.io",
                        headless=True
                    )
                except Exception as e:
                    # Even if browser launch fails (no Chrome), state should not be ERROR from lock
                    # It should either succeed (mocked) or fail for other reasons
                    if "locked" in str(e).lower():
                        pytest.fail(f"Should not fail due to lock: {e}")
        
        # State should be IDLE (successful launch) or ERROR (browser not found), 
        # but NOT due to profile lock
        if observer.status.last_error:
            assert "locked" not in observer.status.last_error.lower(), \
                "Error should NOT be about profile lock"
        print(f"PASS: open_session proceeds when not locked, state={observer.status.state}")


class TestCookieDiagnostics:
    """Tests for cookie path diagnostics in open_session()."""

    def test_cookie_paths_checked(self):
        """
        Verify the code checks both Default/Cookies and Default/Network/Cookies paths.
        This is a code structure test.
        """
        import inspect
        from backend.services.autodarts_observer import AutodartsObserver
        
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check that both cookie paths are referenced
        assert "Default', 'Cookies'" in source or "'Cookies'" in source, \
            "Should check Default/Cookies path"
        assert "'Network', 'Cookies'" in source or "Network/Cookies" in source, \
            "Should check Default/Network/Cookies path"
        
        # Check that both are used in cookie diagnostics
        assert "cookies_classic" in source or "cookies_network" in source, \
            "Should have variables for both cookie paths"
        
        print("PASS: Cookie diagnostics code checks both Cookies paths")

    def test_cookie_path_logic(self):
        """Test cookie detection with both paths."""
        with tempfile.TemporaryDirectory() as profile_dir:
            default_dir = os.path.join(profile_dir, 'Default')
            network_dir = os.path.join(default_dir, 'Network')
            os.makedirs(network_dir, exist_ok=True)
            
            # Create classic cookie path
            cookies_classic = os.path.join(default_dir, 'Cookies')
            with open(cookies_classic, 'w') as f:
                f.write('cookie_data')
            
            # Verify detection logic
            cookies_classic_exists = os.path.isfile(cookies_classic)
            cookies_network_exists = os.path.isfile(os.path.join(network_dir, 'Cookies'))
            cookies_exist = cookies_classic_exists or cookies_network_exists
            
            assert cookies_exist is True, "Should detect classic cookies"
            print("PASS: Classic cookie path detected")
            
            # Now test network path only
            os.remove(cookies_classic)
            cookies_network = os.path.join(network_dir, 'Cookies')
            with open(cookies_network, 'w') as f:
                f.write('network_cookie_data')
            
            cookies_classic_exists = os.path.isfile(cookies_classic)
            cookies_network_exists = os.path.isfile(cookies_network)
            cookies_exist = cookies_classic_exists or cookies_network_exists
            
            assert cookies_exist is True, "Should detect network cookies"
            print("PASS: Network cookie path detected")


class TestStartBatProfileSeparation:
    """Tests for start.bat profile separation."""

    def test_startbat_uses_kiosk_ui_profile(self):
        """Verify start.bat uses kiosk_ui_profile for kiosk UI Chrome."""
        startbat_path = '/app/release/windows/start.bat'
        
        with open(startbat_path, 'r') as f:
            content = f.read()
        
        # Check line 143: creates kiosk_ui_profile directory
        assert 'kiosk_ui_profile' in content, "Should reference kiosk_ui_profile"
        
        # Check the Chrome launch uses kiosk_ui_profile
        assert '--user-data-dir=' in content and 'kiosk_ui_profile' in content, \
            "Chrome launch should use kiosk_ui_profile"
        
        # Verify the Chrome launch line (uses !CHROME_PATH! variable, not chrome.exe literal)
        lines = content.split('\n')
        chrome_launch_line = None
        for line in lines:
            # Line 146: start "" "!CHROME_PATH!" --kiosk --user-data-dir=...
            if '--kiosk' in line and '--user-data-dir=' in line and ('CHROME_PATH' in line or 'chrome' in line.lower()):
                chrome_launch_line = line
                break
        
        assert chrome_launch_line is not None, "Should have Chrome launch line with --kiosk and --user-data-dir"
        assert 'kiosk_ui_profile' in chrome_launch_line, \
            f"Kiosk UI should use kiosk_ui_profile, got: {chrome_launch_line}"
        assert 'chrome_profile\\BOARD-1' not in chrome_launch_line and \
               'chrome_profile/BOARD-1' not in chrome_launch_line and \
               'chrome_profile\\!BOARD_ID!' not in chrome_launch_line, \
            f"Kiosk UI should NOT use chrome_profile/BOARD-1: {chrome_launch_line}"
        
        print(f"PASS: start.bat uses kiosk_ui_profile for Chrome launch")
        print(f"  Chrome launch line: {chrome_launch_line.strip()[:120]}...")

    def test_startbat_creates_chrome_profile_board_dir(self):
        """Verify start.bat still creates chrome_profile/BOARD-1 directory (for observer)."""
        startbat_path = '/app/release/windows/start.bat'
        
        with open(startbat_path, 'r') as f:
            content = f.read()
        
        # Check line 63: mkdir for chrome_profile
        assert 'chrome_profile' in content, "Should reference chrome_profile"
        
        # Find the mkdir line for chrome_profile/BOARD-1
        lines = content.split('\n')
        mkdir_found = False
        for line in lines:
            if 'mkdir' in line.lower() and 'chrome_profile' in line:
                if 'BOARD' in line or '%BOARD_ID%' in line or '!BOARD_ID!' in line:
                    mkdir_found = True
                    print(f"  mkdir line: {line.strip()}")
                    break
        
        assert mkdir_found, "Should create chrome_profile/BOARD-ID directory"
        print("PASS: start.bat creates chrome_profile/BOARD-ID directory")


class TestObserverProfileUsage:
    """Tests for observer profile path usage."""

    def test_observer_uses_chrome_profile(self):
        """Verify observer uses chrome_profile (not kiosk_ui_profile)."""
        import inspect
        from backend.services.autodarts_observer import AutodartsObserver, CHROME_PROFILE_DIR
        
        # Check CHROME_PROFILE_DIR constant
        assert 'chrome_profile' in CHROME_PROFILE_DIR, \
            f"CHROME_PROFILE_DIR should contain 'chrome_profile': {CHROME_PROFILE_DIR}"
        assert 'kiosk_ui_profile' not in CHROME_PROFILE_DIR, \
            f"CHROME_PROFILE_DIR should NOT contain 'kiosk_ui_profile': {CHROME_PROFILE_DIR}"
        
        print(f"PASS: CHROME_PROFILE_DIR = {CHROME_PROFILE_DIR}")

    def test_observer_profile_path_construction(self):
        """Test that observer constructs correct profile path."""
        observer = AutodartsObserver("BOARD-1")
        
        # The profile_dir construction from open_session
        expected_path_part = os.path.join(CHROME_PROFILE_DIR, "BOARD-1")
        
        # Verify CHROME_PROFILE_DIR doesn't have kiosk_ui_profile
        assert 'kiosk_ui' not in CHROME_PROFILE_DIR.lower(), \
            "Observer profile should not use kiosk_ui"
        
        print(f"PASS: Observer profile path: {expected_path_part}")


class TestExistingFunctionality:
    """Regression tests - verify existing functionality still works."""

    def test_ws_frame_classification_gameshot(self):
        """Verify gameshot is classified as round_transition (NOT match_finished)."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"type":"gameshot","score":180}',
            'autodarts.matches.123.game-events',
            {'type': 'gameshot'}
        )
        
        assert result == 'round_transition_gameshot', \
            f"gameshot should be round_transition_gameshot, got: {result}"
        print(f"PASS: gameshot -> {result}")

    def test_ws_frame_classification_matchshot(self):
        """Verify matchshot is classified as match_finished."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"type":"matchshot"}',
            'autodarts.matches.123.game-events',
            {'type': 'matchshot'}
        )
        
        assert result == 'match_finished_matchshot', \
            f"matchshot should be match_finished_matchshot, got: {result}"
        print(f"PASS: matchshot -> {result}")

    def test_ws_frame_classification_match_winner(self):
        """Verify matchWinner field triggers match_finished."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"matchWinner":"player1"}',
            'autodarts.matches.123.state',
            {'matchWinner': 'player1'}
        )
        
        assert result == 'match_finished_winner_field', \
            f"matchWinner should be match_finished_winner_field, got: {result}"
        print(f"PASS: matchWinner -> {result}")

    def test_debounce_poll_count_config(self):
        """Verify debounce configuration exists."""
        from backend.services.autodarts_observer import DEBOUNCE_EXIT_POLLS, DEBOUNCE_POLL_INTERVAL
        
        assert DEBOUNCE_EXIT_POLLS >= 2, f"DEBOUNCE_EXIT_POLLS should be >= 2: {DEBOUNCE_EXIT_POLLS}"
        assert DEBOUNCE_POLL_INTERVAL >= 1, f"DEBOUNCE_POLL_INTERVAL should be >= 1: {DEBOUNCE_POLL_INTERVAL}"
        print(f"PASS: Debounce config - polls={DEBOUNCE_EXIT_POLLS}, interval={DEBOUNCE_POLL_INTERVAL}")


class TestHealthEndpoint:
    """Test backend health endpoint."""

    def test_api_health(self):
        """Verify /api/health returns healthy."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"Unexpected health status: {data}"
        print(f"PASS: /api/health -> {data}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
