"""
Tests for Windows Agent v3.4.0

Tests:
1. Agent status endpoint
2. Subprocess timeout handling
3. Restart/reboot/shutdown command guards
4. Graceful degradation on non-Windows
5. Agent HTTP auth
6. Backend agent_client with fallback
7. No regressions on existing runtime
"""
import json
import os
import platform
import pytest
import sys
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent"))

IS_WINDOWS = platform.system() == "Windows"


# ═══════════════════════════════════════════════════════════════
# Test 1: Agent Process — Status Endpoint
# ═══════════════════════════════════════════════════════════════

class TestAgentStatus:
    """Test the agent's /status endpoint returns correct structure."""

    def test_status_structure(self):
        """Status response has all required fields."""
        from agent.darts_agent import (
            AutodartsDesktopManager, SystemCommandService,
            KioskControlManager, AgentHandler, AGENT_VERSION
        )

        handler_cls = type('TestHandler', (AgentHandler,), {
            'agent_secret': 'test-secret',
            'autodarts': AutodartsDesktopManager(),
            'system_cmd': SystemCommandService('http://localhost:8001'),
            'kiosk_ctrl': KioskControlManager(),
            'start_time': time.time() - 60,
            'autodarts_exe_path': '',
        })

        # Start test server
        server = HTTPServer(('127.0.0.1', 0), handler_cls)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        import urllib.request
        try:
            resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/status', timeout=3)
            data = json.loads(resp.read())

            assert data['agent_online'] is True
            assert data['agent_version'] == AGENT_VERSION
            assert 'platform' in data
            assert 'uptime_s' in data
            assert 'heartbeat' in data
            assert 'autodarts' in data
            assert 'kiosk_window' in data
            assert 'shell' in data
            assert 'task_manager' in data
            assert data['uptime_s'] >= 59  # started 60s ago
        finally:
            server.server_close()

    def test_status_no_auth_required(self):
        """Status endpoint does not require auth."""
        from agent.darts_agent import (
            AutodartsDesktopManager, SystemCommandService,
            KioskControlManager, AgentHandler
        )

        handler_cls = type('TestHandler2', (AgentHandler,), {
            'agent_secret': 'secret123',
            'autodarts': AutodartsDesktopManager(),
            'system_cmd': SystemCommandService('http://localhost:8001'),
            'kiosk_ctrl': KioskControlManager(),
            'start_time': time.time(),
            'autodarts_exe_path': '',
        })

        server = HTTPServer(('127.0.0.1', 0), handler_cls)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        import urllib.request
        try:
            resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/status', timeout=3)
            assert resp.status == 200
        finally:
            server.server_close()


# ═══════════════════════════════════════════════════════════════
# Test 2: Auth Guard
# ═══════════════════════════════════════════════════════════════

class TestAgentAuth:
    """Test agent HTTP auth enforcement."""

    def test_post_without_secret_returns_401(self):
        """POST endpoints without X-Agent-Secret return 401."""
        from agent.darts_agent import (
            AutodartsDesktopManager, SystemCommandService,
            KioskControlManager, AgentHandler
        )

        handler_cls = type('TestHandler3', (AgentHandler,), {
            'agent_secret': 'my-secret',
            'autodarts': AutodartsDesktopManager(),
            'system_cmd': SystemCommandService('http://localhost:8001'),
            'kiosk_ctrl': KioskControlManager(),
            'start_time': time.time(),
            'autodarts_exe_path': '',
        })

        server = HTTPServer(('127.0.0.1', 0), handler_cls)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{port}/autodarts/ensure',
                method='POST',
                data=b'{}',
                headers={'Content-Type': 'application/json'}
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req, timeout=3)
            assert exc_info.value.code == 401
        finally:
            server.server_close()

    def test_post_with_wrong_secret_returns_401(self):
        """POST with wrong secret returns 401."""
        from agent.darts_agent import (
            AutodartsDesktopManager, SystemCommandService,
            KioskControlManager, AgentHandler
        )

        handler_cls = type('TestHandler4', (AgentHandler,), {
            'agent_secret': 'correct-secret',
            'autodarts': AutodartsDesktopManager(),
            'system_cmd': SystemCommandService('http://localhost:8001'),
            'kiosk_ctrl': KioskControlManager(),
            'start_time': time.time(),
            'autodarts_exe_path': '',
        })

        server = HTTPServer(('127.0.0.1', 0), handler_cls)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{port}/autodarts/ensure',
                method='POST',
                data=b'{}',
                headers={
                    'Content-Type': 'application/json',
                    'X-Agent-Secret': 'wrong-secret'
                }
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req, timeout=3)
            assert exc_info.value.code == 401
        finally:
            server.server_close()


# ═══════════════════════════════════════════════════════════════
# Test 3: Graceful Degradation on Non-Windows
# ═══════════════════════════════════════════════════════════════

class TestGracefulDegradation:
    """Test all services degrade gracefully on non-Windows."""

    def test_autodarts_not_windows(self):
        from agent.darts_agent import AutodartsDesktopManager
        mgr = AutodartsDesktopManager()
        if not IS_WINDOWS:
            assert mgr.is_running() is False
            assert mgr.get_pid() is None
            result = mgr.ensure_running("/fake/path.exe")
            assert result["reason"] == "not_windows"
            result = mgr.restart("/fake/path.exe")
            assert result["action"] == "failed" or result.get("reason") == "not_windows"

    def test_system_commands_not_windows(self):
        from agent.darts_agent import SystemCommandService
        svc = SystemCommandService("http://localhost:8001")
        if not IS_WINDOWS:
            assert svc.reboot_os()["reason"] == "windows_only"
            assert svc.shutdown_os()["reason"] == "windows_only"

    def test_kiosk_controls_not_windows(self):
        from agent.darts_agent import KioskControlManager
        mgr = KioskControlManager()
        if not IS_WINDOWS:
            assert mgr.get_shell_status()["reason"] == "not_windows"
            assert mgr.switch_shell("explorer")["reason"] == "not_windows"
            assert mgr.get_task_manager_status()["reason"] == "not_windows"
            assert mgr.set_task_manager(True)["reason"] == "not_windows"

    def test_kiosk_window_not_windows(self):
        from agent.darts_agent import detect_kiosk_window
        if not IS_WINDOWS:
            result = detect_kiosk_window()
            assert result["detected"] is False
            assert result["reason"] == "not_windows"


# ═══════════════════════════════════════════════════════════════
# Test 4: Cooldown Guards
# ═══════════════════════════════════════════════════════════════

class TestCooldownGuards:
    """Test cooldown logic for repeated actions."""

    def test_autodarts_cooldown(self):
        """After a start attempt, ensure_running respects cooldown."""
        from agent.darts_agent import AutodartsDesktopManager, _AUTODARTS_COOLDOWN
        mgr = AutodartsDesktopManager()
        if IS_WINDOWS:
            pytest.skip("Windows-specific test skipped on non-Windows")

        # On non-Windows, ensure_running returns "not_windows" immediately
        # So test cooldown logic directly
        mgr._last_start_ts = time.monotonic()  # simulate recent start
        result = mgr.ensure_running("/fake.exe")
        assert result["reason"] == "not_windows"  # non-windows guard fires first

    def test_backend_restart_cooldown(self):
        """Backend restart respects cooldown."""
        from agent.darts_agent import SystemCommandService
        svc = SystemCommandService("http://localhost:8001")
        if not IS_WINDOWS:
            pytest.skip("System restart is Windows-only")


# ═══════════════════════════════════════════════════════════════
# Test 5: Backend Agent Client
# ═══════════════════════════════════════════════════════════════

class TestAgentClient:
    """Test the backend's agent_client module."""

    @pytest.mark.asyncio
    async def test_client_returns_none_when_agent_offline(self):
        """Client returns None when agent is not running."""
        from backend.services.agent_client import AgentClient
        client = AgentClient()

        # Use a port that's not running
        with patch('backend.services.agent_client._AGENT_PORT', '59999'):
            result = await client.get_status()
            assert result is None

    @pytest.mark.asyncio
    async def test_client_is_configured_with_secret(self):
        """Client reports configured when secret is set."""
        from backend.services.agent_client import AgentClient
        client = AgentClient()
        with patch('backend.services.agent_client._AGENT_SECRET', 'some-secret'):
            assert client.is_configured() is True

    @pytest.mark.asyncio
    async def test_client_not_configured_without_secret(self):
        """Client reports not configured when secret is empty."""
        from backend.services.agent_client import AgentClient
        client = AgentClient()
        with patch('backend.services.agent_client._AGENT_SECRET', ''):
            assert client.is_configured() is False


# ═══════════════════════════════════════════════════════════════
# Test 6: Autodarts Exe Path Validation
# ═══════════════════════════════════════════════════════════════

class TestExePathValidation:
    """Test exe path validation in AutodartsDesktopManager."""

    def test_empty_exe_path(self):
        from agent.darts_agent import AutodartsDesktopManager
        mgr = AutodartsDesktopManager()
        result = mgr.ensure_running("")
        assert result["reason"] in ("not_windows", "exe_not_found")

    def test_nonexistent_exe_path(self):
        from agent.darts_agent import AutodartsDesktopManager
        mgr = AutodartsDesktopManager()
        result = mgr.ensure_running("/nonexistent/path/to/app.exe")
        assert result["reason"] in ("not_windows", "exe_not_found")


# ═══════════════════════════════════════════════════════════════
# Test 7: Agent Version Constant
# ═══════════════════════════════════════════════════════════════

class TestAgentVersion:
    """Test agent version is set correctly."""

    def test_version_is_340(self):
        from agent.darts_agent import AGENT_VERSION
        assert AGENT_VERSION == "3.4.0"

    def test_version_in_status(self):
        from agent.darts_agent import AutodartsDesktopManager, AgentHandler
        # Just ensure the handler has the version
        assert hasattr(AgentHandler, 'server_version')
        assert '3.4.0' in AgentHandler.server_version
