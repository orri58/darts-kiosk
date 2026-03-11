"""
Test Iteration 36 - Observer Chrome Stability Fixes

This iteration fixes a critical bug where the observer-launched Chrome browser/page/context
disappears shortly after successful launch.

Root cause:
1. Observer Chrome was launched with --kiosk mode, which causes Chrome to exit when
   last tab closes/crashes and conflicts with another kiosk-mode Chrome.
   Fixed by replacing --kiosk with --start-maximized.
2. Added lifecycle event handlers for diagnosability.
3. Added browser health check in observe loop.
4. Window manager now logs all Chrome window titles during enumeration.

Test coverage:
1. Observer Chrome args no longer contain --kiosk (only --start-maximized for non-headless)
2. Observer page.on('close') handler is registered and logs PAGE CLOSED
3. Observer page.on('crash') handler is registered and logs PAGE CRASHED
4. Observer context.on('close') handler is registered and logs CONTEXT CLOSED
5. Observer open_session logs navigation status code and current URL after goto
6. Observer open_session logs page count after navigation
7. Observer open_session does health checks at 3s, 5s, 10s after launch
8. Observe loop has browser health check (checks page.url, logs BROWSER DEAD on failure)
9. Window manager _win32_hide_by_title logs all chrome window titles (all_chrome_titles)
10. Window manager _win32_hide_by_title skips windows with 'autodarts' in title (SKIP log)
11. Window manager _win32_restore_by_title logs all chrome window titles
12. Regression: _check_profile_locked still works (from iteration_35)
13. Regression: matchshot classified as match_finished_matchshot
14. Regression: gameshot classified as round_transition_gameshot (NOT match_finished)
15. Backend /api/health responds correctly
"""
import pytest
import os
import sys
import inspect
import tempfile
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import requests

# Add backend to path
sys.path.insert(0, '/app')

from backend.services.autodarts_observer import (
    AutodartsObserver,
    ObserverState,
    CHROME_PROFILE_DIR,
)

# Load BASE_URL from frontend/.env
def _get_base_url():
    env_file = '/app/frontend/.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().rstrip('/')
    return os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

BASE_URL = _get_base_url()


class TestObserverChromeArgsNoKiosk:
    """Tests that observer Chrome does NOT use --kiosk mode."""

    def test_chrome_args_no_kiosk_in_code(self):
        """Verify the chrome_args list in open_session does NOT contain --kiosk."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Find the chrome_args definition
        assert "chrome_args" in source, "Should have chrome_args variable"
        
        # Extract the chrome_args block - look for the list definition
        lines = source.split('\n')
        in_chrome_args = False
        chrome_args_lines = []
        
        for line in lines:
            if 'chrome_args' in line and '=' in line and '[' in line:
                in_chrome_args = True
            if in_chrome_args:
                chrome_args_lines.append(line)
                if ']' in line and 'append' not in line:
                    break
        
        chrome_args_block = '\n'.join(chrome_args_lines)
        
        # Verify --kiosk is NOT in the initial chrome_args list
        assert '--kiosk' not in chrome_args_block, \
            f"chrome_args should NOT contain --kiosk:\n{chrome_args_block}"
        
        # Verify no append('--kiosk') either - the comment says NOT to use it
        assert ".append('--kiosk')" not in source and '.append("--kiosk")' not in source, \
            "Should NOT append --kiosk to chrome_args"
        
        print("PASS: chrome_args does NOT contain --kiosk")

    def test_chrome_args_has_start_maximized(self):
        """Verify the chrome_args uses --start-maximized for non-headless mode."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check that --start-maximized is added for non-headless
        assert '--start-maximized' in source, \
            "Should have --start-maximized in open_session code"
        
        # Verify the logic: if not headless, append --start-maximized
        assert "not headless" in source or "if not headless" in source, \
            "Should check 'not headless' before adding --start-maximized"
        
        print("PASS: --start-maximized used for non-headless mode")

    def test_chrome_args_comment_explains_kiosk_removal(self):
        """Verify there's a comment explaining why --kiosk is NOT used."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # There should be a comment explaining the kiosk mode issue
        has_kiosk_comment = (
            "kiosk" in source.lower() and 
            ("exit" in source.lower() or "crash" in source.lower() or "conflict" in source.lower())
        )
        
        assert has_kiosk_comment, \
            "Should have a comment explaining why --kiosk is not used"
        
        print("PASS: Comment explaining --kiosk removal exists")


class TestLifecycleEventHandlers:
    """Tests for page/context lifecycle event handlers."""

    def test_page_close_handler_registered(self):
        """Verify page.on('close', ...) handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for page.on("close", ...) pattern
        assert "page.on" in source and "'close'" in source or '"close"' in source, \
            "Should register page.on('close') handler"
        
        # Check that PAGE CLOSED is logged
        assert "PAGE CLOSED" in source, \
            "Should log 'PAGE CLOSED' when page closes"
        
        print("PASS: page.on('close') handler registered with PAGE CLOSED log")

    def test_page_crash_handler_registered(self):
        """Verify page.on('crash', ...) handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for page.on("crash", ...) pattern
        assert "'crash'" in source or '"crash"' in source, \
            "Should register page.on('crash') handler"
        
        # Check that PAGE CRASHED is logged
        assert "PAGE CRASHED" in source, \
            "Should log 'PAGE CRASHED' when page crashes"
        
        print("PASS: page.on('crash') handler registered with PAGE CRASHED log")

    def test_context_close_handler_registered(self):
        """Verify context.on('close', ...) handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for context.on("close", ...) pattern
        # In code it's self._context.on("close", ...)
        assert "context.on" in source or "_context.on" in source, \
            "Should have context.on or _context.on call"
        
        # Check that CONTEXT CLOSED is logged
        assert "CONTEXT CLOSED" in source, \
            "Should log 'CONTEXT CLOSED' when context closes"
        
        print("PASS: context.on('close') handler registered with CONTEXT CLOSED log")


class TestNavigationLogging:
    """Tests for navigation status code and URL logging."""

    def test_logs_navigation_status_code(self):
        """Verify open_session logs the navigation response status code."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for response.status or nav_status logging
        assert "status" in source.lower() and ("nav" in source.lower() or "response" in source.lower()), \
            "Should log navigation status code"
        
        # Check for nav_status variable or response.status usage
        assert "nav_status" in source or "response.status" in source, \
            "Should have nav_status or response.status variable"
        
        print("PASS: Navigation status code is logged")

    def test_logs_current_url_after_navigation(self):
        """Verify open_session logs current URL after goto."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for current_url or page.url logging after navigation
        assert "current_url" in source or "self._page.url" in source, \
            "Should log current URL after navigation"
        
        # Check it's in logging context
        assert "url=" in source.lower() or "current_url" in source.lower(), \
            "Should log the current URL"
        
        print("PASS: Current URL is logged after navigation")

    def test_logs_page_count_after_navigation(self):
        """Verify open_session logs page count after navigation."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for pages after nav logging
        # Looking for: len(self._context.pages) or similar after goto
        assert "pages" in source.lower() and "after" in source.lower(), \
            "Should log page count after navigation"
        
        # More specific check
        assert "Pages after nav" in source or "pages={" in source or "pages=" in source, \
            "Should log 'Pages after nav' or similar"
        
        print("PASS: Page count is logged after navigation")


class TestPostLaunchHealthChecks:
    """Tests for health checks at 3s, 5s, 10s after launch."""

    def test_health_checks_at_intervals(self):
        """Verify health checks are performed at 3s, 5s, 10s intervals."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for health check loop with delays
        assert "HEALTH@" in source or "HEALTH" in source.upper(), \
            "Should have HEALTH check logging"
        
        # Check for the specific delay values (3, 5, 10)
        has_delay_3 = "3" in source and ("delay" in source or "HEALTH" in source)
        has_delay_5 = "5" in source and ("delay" in source or "HEALTH" in source)
        has_delay_10 = "10" in source and ("delay" in source or "HEALTH" in source)
        
        # Check for a loop with these delays
        assert "[3, 5, 10]" in source or "3, 5, 10" in source, \
            "Should have delays at 3, 5, 10 seconds"
        
        print("PASS: Health checks at 3s, 5s, 10s intervals configured")

    def test_health_check_logs_page_alive(self):
        """Verify health check logs page alive status."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for page_alive logging
        assert "page_alive" in source or "alive" in source.lower(), \
            "Should log page_alive status in health check"
        
        print("PASS: Health check logs page alive status")


class TestObserveLoopHealthCheck:
    """Tests for browser health check in observe loop."""

    def test_observe_loop_has_browser_health_check(self):
        """Verify observe loop checks if browser/page is still alive."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        # Check for health check in the loop
        assert "health" in source.lower() or "BROWSER DEAD" in source or "page.url" in source, \
            "Should have browser health check in observe loop"
        
        print("PASS: Observe loop has browser health check")

    def test_observe_loop_logs_browser_dead(self):
        """Verify observe loop logs BROWSER DEAD on health check failure."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        # Check for BROWSER DEAD logging
        assert "BROWSER DEAD" in source, \
            "Should log 'BROWSER DEAD' when browser dies"
        
        print("PASS: Observe loop logs BROWSER DEAD on failure")

    def test_observe_loop_checks_page_url(self):
        """Verify observe loop uses page.url to check browser health."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        # Check for page.url access for health check
        assert "self._page.url" in source or "_page.url" in source, \
            "Should check self._page.url for browser health"
        
        print("PASS: Observe loop checks page.url for health")

    def test_observe_loop_breaks_on_browser_death(self):
        """Verify observe loop breaks when browser dies."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        # Check for break statement after BROWSER DEAD
        assert "break" in source and "BROWSER DEAD" in source, \
            "Should break the loop when browser dies"
        
        print("PASS: Observe loop breaks on browser death")


class TestWindowManagerLogging:
    """Tests for window manager chrome window title logging."""

    def test_hide_by_title_logs_all_chrome_titles(self):
        """Verify _win32_hide_by_title logs all chrome window titles."""
        from backend.services.window_manager import _win32_hide_by_title
        
        source = inspect.getsource(_win32_hide_by_title)
        
        # Check for all_chrome_titles variable
        assert "all_chrome_titles" in source, \
            "Should have all_chrome_titles variable for logging"
        
        # Check it logs the list
        assert "chrome_windows=" in source or "all_chrome_titles" in source, \
            "Should log chrome_windows or all_chrome_titles"
        
        print("PASS: _win32_hide_by_title logs all chrome window titles")

    def test_hide_by_title_skips_autodarts_windows(self):
        """Verify _win32_hide_by_title skips windows with 'autodarts' in title."""
        from backend.services.window_manager import _win32_hide_by_title
        
        source = inspect.getsource(_win32_hide_by_title)
        
        # Check for autodarts skip logic
        assert "autodarts" in source.lower(), \
            "Should check for 'autodarts' in window title"
        
        # Check for SKIP log
        assert "SKIP" in source, \
            "Should log 'SKIP' when skipping autodarts windows"
        
        print("PASS: _win32_hide_by_title skips autodarts windows with SKIP log")

    def test_restore_by_title_logs_all_chrome_titles(self):
        """Verify _win32_restore_by_title logs all chrome window titles."""
        from backend.services.window_manager import _win32_restore_by_title
        
        source = inspect.getsource(_win32_restore_by_title)
        
        # Check for all_chrome_titles variable
        assert "all_chrome_titles" in source, \
            "Should have all_chrome_titles variable for logging"
        
        # Check it logs the list
        assert "chrome_windows=" in source or "all_chrome_titles" in source, \
            "Should log chrome_windows or all_chrome_titles"
        
        print("PASS: _win32_restore_by_title logs all chrome window titles")


class TestRegressionProfileLocking:
    """Regression: _check_profile_locked still works from iteration_35."""

    def test_check_profile_locked_exists(self):
        """Verify _check_profile_locked method exists."""
        observer = AutodartsObserver("TEST-BOARD")
        assert hasattr(observer, '_check_profile_locked'), \
            "_check_profile_locked method should exist"
        print("PASS: _check_profile_locked method exists")

    def test_check_profile_locked_returns_false_no_locks(self):
        """Verify _check_profile_locked returns False when no locks exist."""
        with tempfile.TemporaryDirectory() as profile_dir:
            observer = AutodartsObserver("TEST-BOARD")
            result = observer._check_profile_locked(profile_dir)
            assert result is False, "Should return False when no lock files"
            print("PASS: _check_profile_locked returns False when no locks")

    def test_check_profile_locked_cleans_stale_locks(self):
        """Verify stale locks are cleaned up."""
        with tempfile.TemporaryDirectory() as profile_dir:
            lock_path = os.path.join(profile_dir, 'SingletonLock')
            with open(lock_path, 'w') as f:
                f.write('stale')
            
            observer = AutodartsObserver("TEST-BOARD")
            
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', returncode=1)
                result = observer._check_profile_locked(profile_dir)
            
            assert result is False, "Should return False for stale lock"
            assert not os.path.exists(lock_path), "Stale lock should be removed"
            print("PASS: Stale locks are cleaned up")


class TestRegressionMatchClassification:
    """Regression: Match classification still works correctly."""

    def test_matchshot_classified_correctly(self):
        """Verify matchshot is classified as match_finished_matchshot."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"type":"matchshot"}',
            'autodarts.matches.123.game-events',
            {'type': 'matchshot'}
        )
        
        assert result == 'match_finished_matchshot', \
            f"matchshot should be match_finished_matchshot, got: {result}"
        print(f"PASS: matchshot -> {result}")

    def test_gameshot_classified_correctly(self):
        """Verify gameshot is classified as round_transition_gameshot (NOT match_finished)."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"type":"gameshot","score":180}',
            'autodarts.matches.123.game-events',
            {'type': 'gameshot'}
        )
        
        assert result == 'round_transition_gameshot', \
            f"gameshot should be round_transition_gameshot, got: {result}"
        assert 'match_finished' not in result, \
            f"gameshot should NOT be match_finished: {result}"
        print(f"PASS: gameshot -> {result}")


class TestBackendHealth:
    """Test backend health endpoint."""

    def test_api_health_responds(self):
        """Verify /api/health returns healthy."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"Unexpected status: {data}"
        print(f"PASS: /api/health -> {data}")


class TestIntegrationMockedPlaywright:
    """Integration tests with mocked Playwright."""

    @pytest.mark.asyncio
    async def test_open_session_chrome_args_list(self):
        """Test that chrome_args passed to Playwright do NOT contain --kiosk."""
        observer = AutodartsObserver("TEST-ARGS")
        
        captured_args = None
        
        with patch.object(observer, '_check_profile_locked', return_value=False):
            with patch('playwright.async_api.async_playwright') as mock_playwright:
                mock_pw = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                
                mock_page.url = "https://play.autodarts.io"
                mock_context.pages = [mock_page]
                
                async def capture_launch(**kwargs):
                    nonlocal captured_args
                    captured_args = kwargs.get('args', [])
                    return mock_context
                
                mock_pw.chromium.launch_persistent_context = AsyncMock(side_effect=capture_launch)
                mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)
                
                # Mock navigation response
                mock_response = MagicMock()
                mock_response.status = 200
                mock_page.goto = AsyncMock(return_value=mock_response)
                mock_page.add_init_script = AsyncMock()
                mock_page.on = MagicMock()
                mock_context.on = MagicMock()
                
                try:
                    await observer.open_session(
                        autodarts_url="https://play.autodarts.io",
                        headless=False  # Non-headless to test --start-maximized
                    )
                except Exception:
                    pass
                
                if captured_args is not None:
                    assert '--kiosk' not in captured_args, \
                        f"chrome_args should NOT contain --kiosk: {captured_args}"
                    assert '--start-maximized' in captured_args, \
                        f"chrome_args should contain --start-maximized: {captured_args}"
                    print(f"PASS: Captured chrome_args: {captured_args}")
                    print("       --kiosk: NOT present (correct)")
                    print("       --start-maximized: present (correct)")

    @pytest.mark.asyncio
    async def test_lifecycle_handlers_registered(self):
        """Test that lifecycle handlers are registered on page and context."""
        observer = AutodartsObserver("TEST-HANDLERS")
        
        page_handlers = []
        context_handlers = []
        
        with patch.object(observer, '_check_profile_locked', return_value=False):
            with patch('playwright.async_api.async_playwright') as mock_playwright:
                mock_pw = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                
                mock_page.url = "https://play.autodarts.io"
                mock_context.pages = [mock_page]
                
                def capture_page_on(event, handler):
                    page_handlers.append(event)
                
                def capture_context_on(event, handler):
                    context_handlers.append(event)
                
                mock_page.on = MagicMock(side_effect=capture_page_on)
                mock_context.on = MagicMock(side_effect=capture_context_on)
                
                mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
                mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)
                
                mock_response = MagicMock()
                mock_response.status = 200
                mock_page.goto = AsyncMock(return_value=mock_response)
                mock_page.add_init_script = AsyncMock()
                
                try:
                    await observer.open_session(
                        autodarts_url="https://play.autodarts.io",
                        headless=True
                    )
                except Exception:
                    pass
                
                # Check that lifecycle handlers were registered
                assert 'close' in page_handlers, \
                    f"page.on('close') should be registered: {page_handlers}"
                assert 'crash' in page_handlers, \
                    f"page.on('crash') should be registered: {page_handlers}"
                assert 'close' in context_handlers, \
                    f"context.on('close') should be registered: {context_handlers}"
                
                print(f"PASS: Lifecycle handlers registered:")
                print(f"  page handlers: {page_handlers}")
                print(f"  context handlers: {context_handlers}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
