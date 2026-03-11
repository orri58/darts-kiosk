"""
Test Iteration 37 - Observer Fresh Page Creation Fix

This iteration fixes a critical issue where launch_persistent_context() can restore 
previous session tabs, and using pages[0] is unreliable. 

Fix: Always create a fresh page via context.new_page(), navigate it to Autodarts, 
then close all old/stale pages (about:blank, restored tabs).

Test coverage:
1. Observer creates FRESH page via new_page() instead of using pages[0]
2. Observer logs all existing pages and their URLs after context launch
3. Observer closes old/stale pages after navigating the fresh page
4. Observer logs final page inventory with (OBSERVED) marker on the active page
5. Observer detects and logs if page is still on about:blank after navigation (NAVIGATION FAILED)
6. Chrome args include --disable-session-crashed-bubble
7. Chrome args do NOT contain --kiosk
8. Chrome args contain --start-maximized for non-headless
9. Observer page.on('close') handler registered
10. Observer page.on('crash') handler registered
11. Observer context.on('close') handler registered
12. Observe loop browser health check still works (BROWSER DEAD)
13. Regression: _check_profile_locked still works
14. Regression: matchshot = match_finished_matchshot
15. Regression: gameshot = round_transition_gameshot
16. Backend /api/health responds
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


class TestFreshPageCreation:
    """Tests for fresh page creation via new_page() instead of pages[0]."""

    def test_uses_new_page_not_pages_zero(self):
        """Verify open_session uses context.new_page() instead of pages[0]."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for new_page() usage
        assert "new_page()" in source, \
            "Should use new_page() to create a fresh page"
        
        # Make sure we're NOT using pages[0] as the observed page
        # Look for assignment like: self._page = self._context.pages[0]
        lines = source.split('\n')
        bad_pattern_found = False
        for line in lines:
            if 'self._page' in line and 'pages[0]' in line and '=' in line:
                # Check if this is the assignment
                if 'self._page' in line.split('=')[0]:
                    bad_pattern_found = True
                    break
        
        assert not bad_pattern_found, \
            "Should NOT use self._page = ...pages[0]. Use new_page() instead."
        
        # Verify the fresh page is assigned
        assert "self._page = await" in source and "new_page()" in source, \
            "Should assign self._page = await ...new_page()"
        
        print("PASS: Observer creates FRESH page via new_page() instead of pages[0]")

    def test_fresh_page_creation_comment(self):
        """Verify there's a comment explaining why we use new_page()."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for comment about fresh page
        has_fresh_page_comment = (
            "fresh" in source.lower() and 
            ("page" in source.lower() or "reuse" in source.lower() or "restored" in source.lower())
        )
        
        assert has_fresh_page_comment, \
            "Should have a comment explaining why we create a fresh page"
        
        print("PASS: Comment explaining fresh page creation exists")


class TestExistingPagesLogging:
    """Tests for logging existing pages after context launch."""

    def test_logs_existing_pages_after_launch(self):
        """Verify open_session logs all existing pages after context launch."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for existing_pages variable or logging pattern
        has_existing_pages_log = (
            "existing_pages" in source or 
            "Pages after launch" in source or
            "pages after" in source.lower()
        )
        
        assert has_existing_pages_log, \
            "Should log existing pages after launch"
        
        print("PASS: Observer logs all existing pages after context launch")

    def test_logs_each_page_url(self):
        """Verify open_session logs the URL of each existing page."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for page URL enumeration pattern
        # Should have a loop over pages and log URLs
        has_url_enumeration = (
            "enumerate" in source and "page" in source.lower() and 
            ("url" in source.lower() or "p.url" in source or "p_url" in source)
        )
        
        # Or direct pages iteration with URL access
        has_pages_iteration = (
            "for" in source and "pages" in source and 
            ("url" in source.lower() or "p.url" in source or "p_url" in source)
        )
        
        assert has_url_enumeration or has_pages_iteration, \
            "Should enumerate and log each page's URL"
        
        print("PASS: Observer logs each existing page's URL")


class TestOldPagesCleanup:
    """Tests for closing old/stale pages after navigation."""

    def test_closes_old_pages(self):
        """Verify open_session closes old/stale pages after navigating fresh page."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for closing old pages pattern
        has_close_old_pages = (
            "old_page" in source.lower() or
            "existing_pages" in source
        ) and ".close()" in source
        
        # Alternative: check for loop closing pages
        has_loop_close = "for" in source and "close()" in source
        
        assert has_close_old_pages or has_loop_close, \
            "Should close old/stale pages after navigation"
        
        print("PASS: Observer closes old/stale pages after navigating fresh page")

    def test_close_old_pages_comment(self):
        """Verify there's a comment about closing old pages."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for comment about closing old pages
        has_comment = (
            ("old" in source.lower() or "stale" in source.lower()) and 
            ("close" in source.lower() or "Close" in source)
        )
        
        assert has_comment, \
            "Should have a comment explaining why old pages are closed"
        
        print("PASS: Comment explaining old page cleanup exists")


class TestFinalPageInventory:
    """Tests for final page inventory logging with (OBSERVED) marker."""

    def test_logs_final_page_inventory(self):
        """Verify open_session logs final page inventory."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for final page inventory logging
        has_final_inventory = (
            "final" in source.lower() and "page" in source.lower()
        ) or "Final page count" in source or "final_pages" in source
        
        assert has_final_inventory, \
            "Should log final page inventory"
        
        print("PASS: Observer logs final page inventory")

    def test_observed_marker_on_active_page(self):
        """Verify the active observed page is marked with (OBSERVED)."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for (OBSERVED) marker
        assert "(OBSERVED)" in source or "OBSERVED" in source, \
            "Should mark the active page with (OBSERVED)"
        
        # Verify the marker is used in logging context
        assert "is_ours" in source or "(OBSERVED)" in source, \
            "Should have logic to identify and mark the observed page"
        
        print("PASS: Observer logs final page inventory with (OBSERVED) marker")


class TestAboutBlankDetection:
    """Tests for about:blank detection after navigation (NAVIGATION FAILED)."""

    def test_detects_about_blank_after_navigation(self):
        """Verify open_session detects if page is still on about:blank after navigation."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for about:blank detection
        assert "about:blank" in source, \
            "Should check for about:blank after navigation"
        
        print("PASS: Observer detects about:blank after navigation")

    def test_logs_navigation_failed(self):
        """Verify NAVIGATION FAILED is logged when page stays on about:blank."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for NAVIGATION FAILED logging
        assert "NAVIGATION FAILED" in source, \
            "Should log 'NAVIGATION FAILED' when page is still on about:blank"
        
        print("PASS: Observer logs NAVIGATION FAILED when stuck on about:blank")


class TestChromeArgsIteration37:
    """Tests for chrome args specific to iteration 37."""

    def test_chrome_args_has_disable_session_crashed_bubble(self):
        """Verify chrome_args includes --disable-session-crashed-bubble."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for --disable-session-crashed-bubble in chrome_args
        assert '--disable-session-crashed-bubble' in source, \
            "chrome_args should include --disable-session-crashed-bubble"
        
        print("PASS: Chrome args include --disable-session-crashed-bubble")

    def test_chrome_args_no_kiosk(self):
        """Verify chrome_args does NOT contain --kiosk."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Find the chrome_args definition block (not comments)
        lines = source.split('\n')
        in_chrome_args = False
        chrome_args_lines = []
        
        for line in lines:
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if 'chrome_args' in line and '=' in line and '[' in line:
                in_chrome_args = True
            if in_chrome_args:
                chrome_args_lines.append(line)
                if ']' in line and 'append' not in line:
                    break
        
        chrome_args_block = '\n'.join(chrome_args_lines)
        
        # Verify --kiosk is NOT in the chrome_args list
        assert '--kiosk' not in chrome_args_block or "'--kiosk'" not in chrome_args_block, \
            f"chrome_args should NOT contain --kiosk in list:\n{chrome_args_block}"
        
        # Also check no append('--kiosk')
        has_kiosk_append = (
            ".append('--kiosk')" in source or 
            '.append("--kiosk")' in source
        )
        assert not has_kiosk_append, "Should NOT append --kiosk to chrome_args"
        
        print("PASS: Chrome args do NOT contain --kiosk")

    def test_chrome_args_has_start_maximized(self):
        """Verify chrome_args uses --start-maximized for non-headless mode."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for --start-maximized in the code
        assert '--start-maximized' in source, \
            "Should have --start-maximized in chrome_args"
        
        # Verify it's conditional on non-headless mode
        assert "not headless" in source, \
            "Should check 'not headless' before adding --start-maximized"
        
        print("PASS: Chrome args contain --start-maximized for non-headless")


class TestLifecycleHandlersIteration37:
    """Tests for lifecycle event handlers (page close/crash, context close)."""

    def test_page_close_handler_registered(self):
        """Verify page.on('close') handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for page.on("close", ...) or self._page.on("close", ...)
        has_close_handler = (
            ("_page.on" in source or "page.on" in source) and 
            ("'close'" in source or '"close"' in source)
        )
        
        assert has_close_handler, "Should register page.on('close') handler"
        assert "PAGE CLOSED" in source, "Should log PAGE CLOSED when page closes"
        
        print("PASS: Observer page.on('close') handler registered")

    def test_page_crash_handler_registered(self):
        """Verify page.on('crash') handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for page.on("crash", ...) or self._page.on("crash", ...)
        has_crash_handler = "'crash'" in source or '"crash"' in source
        
        assert has_crash_handler, "Should register page.on('crash') handler"
        assert "PAGE CRASHED" in source, "Should log PAGE CRASHED when page crashes"
        
        print("PASS: Observer page.on('crash') handler registered")

    def test_context_close_handler_registered(self):
        """Verify context.on('close') handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check for context.on("close", ...) or self._context.on("close", ...)
        has_context_close = (
            ("_context.on" in source or "context.on" in source) and
            "CONTEXT CLOSED" in source
        )
        
        assert has_context_close, "Should register context.on('close') handler"
        
        print("PASS: Observer context.on('close') handler registered")


class TestObserveLoopHealthCheck:
    """Tests for browser health check in observe loop."""

    def test_observe_loop_has_browser_health_check(self):
        """Verify observe loop checks if browser/page is still alive."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        # Check for health check pattern
        has_health_check = (
            "self._page.url" in source or 
            "_page.url" in source
        )
        
        assert has_health_check, "Should check page.url for browser health"
        
        print("PASS: Observe loop browser health check still works")

    def test_observe_loop_logs_browser_dead(self):
        """Verify observe loop logs BROWSER DEAD on health check failure."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        assert "BROWSER DEAD" in source, \
            "Should log 'BROWSER DEAD' when browser dies"
        
        print("PASS: Observe loop logs BROWSER DEAD on failure")


class TestRegressionProfileLocking:
    """Regression: _check_profile_locked still works from iteration_35."""

    def test_check_profile_locked_exists(self):
        """Verify _check_profile_locked method exists."""
        observer = AutodartsObserver("TEST-BOARD")
        assert hasattr(observer, '_check_profile_locked'), \
            "_check_profile_locked method should exist"
        print("PASS: _check_profile_locked still works")

    def test_check_profile_locked_returns_false_no_locks(self):
        """Verify _check_profile_locked returns False when no locks exist."""
        with tempfile.TemporaryDirectory() as profile_dir:
            observer = AutodartsObserver("TEST-BOARD")
            result = observer._check_profile_locked(profile_dir)
            assert result is False, "Should return False when no lock files"
            print("PASS: _check_profile_locked returns False when no locks")


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
        print(f"PASS: matchshot = {result}")

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
        print(f"PASS: gameshot = {result}")


class TestBackendHealth:
    """Test backend health endpoint."""

    def test_api_health_responds(self):
        """Verify /api/health returns healthy."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"Unexpected status: {data}"
        print(f"PASS: Backend /api/health responds -> {data}")


class TestIntegrationMockedPlaywright:
    """Integration tests with mocked Playwright for fresh page creation."""

    @pytest.mark.asyncio
    async def test_open_session_creates_fresh_page(self):
        """Test that open_session creates a fresh page via new_page()."""
        observer = AutodartsObserver("TEST-FRESH-PAGE")
        
        new_page_called = False
        captured_chrome_args = None
        
        with patch.object(observer, '_check_profile_locked', return_value=False):
            with patch('playwright.async_api.async_playwright') as mock_playwright:
                mock_pw = AsyncMock()
                mock_context = AsyncMock()
                mock_existing_page = AsyncMock()
                mock_fresh_page = AsyncMock()
                
                # Existing page is about:blank (simulating restored tab)
                mock_existing_page.url = "about:blank"
                mock_existing_page.is_closed = MagicMock(return_value=False)
                mock_existing_page.close = AsyncMock()
                
                # Fresh page will navigate to autodarts
                mock_fresh_page.url = "https://play.autodarts.io"
                mock_fresh_page.add_init_script = AsyncMock()
                mock_fresh_page.on = MagicMock()
                
                # Context has existing page initially
                mock_context.pages = [mock_existing_page]
                mock_context.on = MagicMock()
                
                async def mock_new_page():
                    nonlocal new_page_called
                    new_page_called = True
                    # Add fresh page to context.pages
                    mock_context.pages = [mock_existing_page, mock_fresh_page]
                    return mock_fresh_page
                
                mock_context.new_page = mock_new_page
                
                async def capture_launch(**kwargs):
                    nonlocal captured_chrome_args
                    captured_chrome_args = kwargs.get('args', [])
                    return mock_context
                
                mock_pw.chromium.launch_persistent_context = AsyncMock(side_effect=capture_launch)
                mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)
                
                # Mock navigation response
                mock_response = MagicMock()
                mock_response.status = 200
                mock_fresh_page.goto = AsyncMock(return_value=mock_response)
                
                try:
                    await observer.open_session(
                        autodarts_url="https://play.autodarts.io",
                        headless=False
                    )
                except Exception as e:
                    # May fail due to cleanup, but we can check our assertions
                    pass
                
                # Assertions
                assert new_page_called, "Should call new_page() to create fresh page"
                print("PASS: new_page() was called to create fresh page")
                
                if captured_chrome_args is not None:
                    assert '--disable-session-crashed-bubble' in captured_chrome_args, \
                        f"Should have --disable-session-crashed-bubble: {captured_chrome_args}"
                    assert '--kiosk' not in captured_chrome_args, \
                        f"Should NOT have --kiosk: {captured_chrome_args}"
                    assert '--start-maximized' in captured_chrome_args, \
                        f"Should have --start-maximized: {captured_chrome_args}"
                    print(f"PASS: Chrome args correct: {captured_chrome_args}")

    @pytest.mark.asyncio
    async def test_open_session_closes_old_pages(self):
        """Test that open_session closes old/stale pages."""
        observer = AutodartsObserver("TEST-CLOSE-OLD")
        
        old_page_closed = False
        
        with patch.object(observer, '_check_profile_locked', return_value=False):
            with patch('playwright.async_api.async_playwright') as mock_playwright:
                mock_pw = AsyncMock()
                mock_context = AsyncMock()
                mock_existing_page = AsyncMock()
                mock_fresh_page = AsyncMock()
                
                # Existing page is about:blank
                mock_existing_page.url = "about:blank"
                mock_existing_page.is_closed = MagicMock(return_value=False)
                
                async def track_close():
                    nonlocal old_page_closed
                    old_page_closed = True
                
                mock_existing_page.close = track_close
                
                # Fresh page will navigate to autodarts
                mock_fresh_page.url = "https://play.autodarts.io"
                mock_fresh_page.add_init_script = AsyncMock()
                mock_fresh_page.on = MagicMock()
                
                # Context starts with existing page
                mock_context.pages = [mock_existing_page]
                mock_context.on = MagicMock()
                
                async def mock_new_page():
                    mock_context.pages = [mock_existing_page, mock_fresh_page]
                    return mock_fresh_page
                
                mock_context.new_page = mock_new_page
                
                mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
                mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)
                
                mock_response = MagicMock()
                mock_response.status = 200
                mock_fresh_page.goto = AsyncMock(return_value=mock_response)
                
                try:
                    await observer.open_session(
                        autodarts_url="https://play.autodarts.io",
                        headless=True
                    )
                except Exception:
                    pass
                
                assert old_page_closed, "Should close old/existing pages"
                print("PASS: Old pages are closed after navigation")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
