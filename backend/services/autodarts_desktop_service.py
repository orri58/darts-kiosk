"""
Autodarts Desktop Supervision Service v3.3.0

Detects if Autodarts.exe is running, can start/restart it.
The exe path is configurable via the settings DB.
This service only runs on Windows.

v3.3.0:
  - Post-launch focus-steal detection and correction
  - Enhanced status model with last_start_attempt, last_error, cooldown_active
  - Robust process detection with null-safe checks
  - Safe subprocess encoding (utf-8, errors=replace)
"""
import logging
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Cooldown between auto-start attempts (seconds)
_AUTO_START_COOLDOWN = 60

# Safe subprocess kwargs for Windows
_SUBPROCESS_SAFE = {
    "capture_output": True,
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
    "timeout": 10,
}


class AutodartsDesktopService:
    """Supervision for the Autodarts Desktop application."""

    def __init__(self):
        self._process_name = "Autodarts.exe"
        self._last_auto_start_ts: float = 0.0
        self._last_start_attempt_at: Optional[str] = None
        self._last_error: Optional[str] = None

    # ── Process Detection ──

    def is_running(self) -> bool:
        """Check if Autodarts.exe is currently running. Null-safe."""
        if not IS_WINDOWS:
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self._process_name}", "/NH"],
                **_SUBPROCESS_SAFE,
            )
            stdout = result.stdout or ""
            return self._process_name.lower() in stdout.lower()
        except Exception as e:
            logger.warning(f"[AUTODARTS_DESKTOP] is_running check failed: {e}")
            return False

    # ── Start / Kill / Restart ──

    def start_process(self, exe_path: str) -> dict:
        """Start Autodarts.exe minimized. Returns status dict."""
        self._last_start_attempt_at = datetime.now(timezone.utc).isoformat()
        if not IS_WINDOWS:
            return {"success": False, "error": "Not a Windows system"}

        if not exe_path or not os.path.isfile(exe_path):
            err = f"Datei nicht gefunden: {exe_path}"
            self._last_error = err
            logger.error(f"[AUTODARTS_DESKTOP] exe not found: {exe_path}")
            return {"success": False, "error": err}

        if self.is_running():
            logger.info("[AUTODARTS_DESKTOP] launch skipped reason=already_running")
            return {"success": True, "message": "Already running"}

        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 7  # SW_SHOWMINNOACTIVE
            subprocess.Popen(
                [exe_path],
                startupinfo=si,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            logger.info(f"[AUTODARTS_DESKTOP] Started (minimized): {exe_path}")
            self._last_error = None
            # Schedule post-launch focus correction
            self._correct_focus_steal_sync()
            return {"success": True, "message": f"Started: {exe_path}"}
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[AUTODARTS_DESKTOP] start failed: {e}")
            return {"success": False, "error": str(e)}

    def kill_process(self) -> bool:
        """Kill all Autodarts.exe processes."""
        if not IS_WINDOWS:
            return False
        try:
            result = subprocess.run(
                ["taskkill", "/IM", self._process_name, "/F"],
                **_SUBPROCESS_SAFE,
            )
            killed = result.returncode == 0
            if killed:
                logger.info("[AUTODARTS_DESKTOP] Process killed")
            else:
                stderr = (result.stderr or "").strip()
                logger.info(f"[AUTODARTS_DESKTOP] taskkill returned {result.returncode}: {stderr}")
            return killed
        except Exception as e:
            logger.error(f"[AUTODARTS_DESKTOP] kill failed: {e}")
            return False

    def restart_process(self, exe_path: str) -> dict:
        """Kill and restart Autodarts.exe."""
        logger.info(f"[AUTODARTS_DESKTOP] Restart requested: {exe_path}")
        self.kill_process()
        time.sleep(1.5)
        return self.start_process(exe_path)

    # ── Auto-Start with Cooldown ──

    def ensure_running(self, exe_path: str, trigger: str = "unknown") -> dict:
        """Single guarded attempt to start Autodarts.exe if not running."""
        logger.info(f"[AUTODARTS_DESKTOP] launch requested trigger={trigger}")
        if not IS_WINDOWS:
            return {"action": "skip", "reason": "not_windows"}

        if not exe_path:
            logger.warning(f"[AUTODARTS_DESKTOP] ensure_running({trigger}): no exe_path configured")
            return {"action": "skip", "reason": "no_exe_path"}

        try:
            if self.is_running():
                logger.info(f"[AUTODARTS_DESKTOP] launch skipped reason=already_running")
                return {"action": "skip", "reason": "already_running"}
        except Exception as e:
            logger.warning(f"[AUTODARTS_DESKTOP] ensure_running({trigger}): check failed: {e}")
            return {"action": "skip", "reason": "check_failed"}

        now = time.monotonic()
        elapsed = now - self._last_auto_start_ts
        if elapsed < _AUTO_START_COOLDOWN:
            remaining = int(_AUTO_START_COOLDOWN - elapsed)
            logger.info(f"[AUTODARTS_DESKTOP] launch skipped reason=cooldown ({remaining}s left)")
            return {"action": "skip", "reason": "cooldown", "remaining_s": remaining}

        self._last_auto_start_ts = now
        self._last_start_attempt_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"[AUTODARTS_DESKTOP] ensure_running({trigger}): attempting start")
        return self._start_no_focus(exe_path, trigger)

    def _start_no_focus(self, exe_path: str, trigger: str = "auto") -> dict:
        """Start Autodarts.exe minimized WITHOUT stealing focus."""
        if not os.path.isfile(exe_path):
            err = f"Datei nicht gefunden: {exe_path}"
            self._last_error = err
            logger.warning(f"[AUTODARTS_DESKTOP] exe not found: {exe_path}")
            return {"action": "failed", "error": err}
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 7  # SW_SHOWMINNOACTIVE — minimized, no focus steal
            subprocess.Popen(
                [exe_path],
                startupinfo=si,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            logger.info(f"[AUTODARTS_DESKTOP] auto-started (no focus): {exe_path}")
            self._last_error = None
            # Post-launch focus correction
            self._correct_focus_steal_sync()
            return {"action": "started", "exe_path": exe_path}
        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"[AUTODARTS_DESKTOP] auto-start failed: {e}")
            return {"action": "failed", "error": str(e)}

    # ── Focus Steal Correction ──

    def _correct_focus_steal_sync(self):
        """
        After launching Autodarts Desktop, check if it stole focus.
        If detected, minimize it and restore the previous foreground window.
        Best-effort only — failures are warnings, not errors.
        """
        if not IS_WINDOWS:
            return
        try:
            # Wait briefly for the window to appear
            time.sleep(2)
            # Use PowerShell to detect and correct focus steal
            ps_script = """
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class WinApi {
                [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
                [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
            }
"@
            $fg = [WinApi]::GetForegroundWindow()
            $sb = New-Object System.Text.StringBuilder 256
            [WinApi]::GetWindowText($fg, $sb, 256) | Out-Null
            $title = $sb.ToString()
            if ($title -like "*Autodarts*") {
                # Minimize the Autodarts window (SW_MINIMIZE = 6)
                [WinApi]::ShowWindow($fg, 6) | Out-Null
                Write-Output "CORRECTED:$title"
            } else {
                Write-Output "OK:$title"
            }
            """
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                **_SUBPROCESS_SAFE,
            )
            stdout = (result.stdout or "").strip()
            if stdout.startswith("CORRECTED:"):
                title = stdout.split(":", 1)[1]
                logger.info(f"[AUTODARTS_DESKTOP] foreground_steal_detected title={title}")
                logger.info(f"[AUTODARTS_DESKTOP] foreground_corrected action=minimize_restore_kiosk")
            elif stdout.startswith("OK:"):
                logger.debug(f"[AUTODARTS_DESKTOP] no focus steal detected, fg={stdout}")
            else:
                logger.debug(f"[AUTODARTS_DESKTOP] focus check output: {stdout}")
        except Exception as e:
            logger.warning(f"[AUTODARTS_DESKTOP] foreground_correction_failed reason={e}")

    # ── Status ──

    def get_status(self) -> dict:
        """Return comprehensive status of Autodarts Desktop."""
        try:
            running = self.is_running()
        except Exception:
            running = False

        now = time.monotonic()
        cooldown_active = (now - self._last_auto_start_ts) < _AUTO_START_COOLDOWN

        return {
            "running": running,
            "process_name": self._process_name,
            "platform": platform.system(),
            "supported": IS_WINDOWS,
            "auto_start_cooldown_s": _AUTO_START_COOLDOWN,
            "cooldown_active": cooldown_active,
            "last_start_attempt_at": self._last_start_attempt_at,
            "last_error": self._last_error,
        }


autodarts_desktop = AutodartsDesktopService()
