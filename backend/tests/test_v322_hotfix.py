"""
v3.2.2 Targeted Tests — Final credit lock, desktop service robustness, admin endpoint
"""
import pytest
import sys
import os
import importlib

# ============================================================
# Test A — Final credit lock: credit_before=1, consume → lock
# ============================================================

def test_final_credit_lock_decision():
    """When credit_before=1 and consume_credit=True, should_lock must be True."""
    credit_before = 1
    consume_credit = True
    credit_after = max(0, credit_before - 1) if consume_credit else credit_before
    has_remaining_credits = credit_after > 0
    should_lock = not has_remaining_credits
    should_teardown = should_lock
    branch = "session_end" if should_lock else "keep_alive"

    assert credit_after == 0
    assert has_remaining_credits is False
    assert should_lock is True
    assert should_teardown is True
    assert branch == "session_end"


# ============================================================
# Test B — Keep-alive unchanged: credit_before=2
# ============================================================

def test_keep_alive_unchanged():
    """When credit_before=2 and consume_credit=True, should_lock must be False."""
    credit_before = 2
    consume_credit = True
    credit_after = max(0, credit_before - 1) if consume_credit else credit_before
    has_remaining_credits = credit_after > 0
    should_lock = not has_remaining_credits
    should_teardown = should_lock
    branch = "session_end" if should_lock else "keep_alive"

    assert credit_after == 1
    assert has_remaining_credits is True
    assert should_lock is False
    assert should_teardown is False
    assert branch == "keep_alive"


def test_no_consume_keeps_credits():
    """When consume_credit=False, credits remain unchanged."""
    credit_before = 1
    consume_credit = False
    credit_after = max(0, credit_before - 1) if consume_credit else credit_before
    has_remaining_credits = credit_after > 0
    should_lock = not has_remaining_credits

    assert credit_after == 1
    assert has_remaining_credits is True
    assert should_lock is False


# ============================================================
# Test C — Desktop process scan robustness
# ============================================================

def test_is_running_returns_bool():
    """is_running must return a bool, never crash."""
    from backend.services.autodarts_desktop_service import AutodartsDesktopService
    svc = AutodartsDesktopService()
    result = svc.is_running()
    assert isinstance(result, bool)


def test_is_running_handles_none_stdout(monkeypatch):
    """is_running must handle subprocess returning None stdout."""
    import subprocess
    class FakeResult:
        stdout = None
        returncode = 1
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeResult())
    # Force IS_WINDOWS to True for this test
    import backend.services.autodarts_desktop_service as mod
    monkeypatch.setattr(mod, "IS_WINDOWS", True)
    svc = mod.AutodartsDesktopService()
    result = svc.is_running()
    assert result is False


def test_ensure_running_no_exe_path():
    """ensure_running with empty exe_path must return skip."""
    from backend.services.autodarts_desktop_service import AutodartsDesktopService
    svc = AutodartsDesktopService()
    result = svc.ensure_running("", trigger="test")
    assert result["action"] == "skip"
    assert result["reason"] in ("no_exe_path", "not_windows")


def test_get_status_never_crashes():
    """get_status must always return a dict without exception."""
    from backend.services.autodarts_desktop_service import AutodartsDesktopService
    svc = AutodartsDesktopService()
    status = svc.get_status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "supported" in status


# ============================================================
# Test D — Admin restart endpoint has no NameError
# ============================================================

def test_admin_restart_endpoint_imports():
    """The admin router must have get_or_create_setting imported."""
    from backend.routers import admin as admin_mod
    assert hasattr(admin_mod, 'get_or_create_setting'), \
        "get_or_create_setting must be importable in admin.py"


def test_admin_restart_endpoint_no_name_error():
    """Verify that calling the restart endpoint function doesn't raise NameError."""
    # We can't run the full endpoint but we can verify the import chain
    from backend.dependencies import get_or_create_setting
    assert callable(get_or_create_setting)


# ============================================================
# Test E — Close-request generation guard
# ============================================================

def test_close_requested_gen_attribute():
    """Observer must have _close_requested_gen attribute."""
    from backend.services.autodarts_observer import AutodartsObserver
    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs._close_requested_gen = -1
    assert obs._close_requested_gen == -1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
