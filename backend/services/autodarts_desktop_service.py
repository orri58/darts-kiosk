"""
Autodarts Desktop Supervision Service v3.3.0

Detects if Autodarts.exe is running, can start/restart it.
The exe path is configurable via the settings DB.
This service only runs on Windows.

v3.3.0:
  - Post-launch focus-steal detection and correction (non-blocking, threaded)
  - Two-stage: SW_SHOWMINNOACTIVE launch + active foreground check/correction
  - Debounced correction (min 10s between attempts, no flicker loops)
  - Enhanced status model with last_start_attempt, last_error, cooldown_active
  - Robust process detection with null-safe checks
  - Safe subprocess encoding (utf-8, errors=replace)
"""
import logging
import os
import platform
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Cooldown between auto-start attempts (seconds)
_AUTO_START_COOLDOWN = 60

# Minimum interval between focus corrections (debounce)
_FOCUS_CORRECTION_DEBOUNCE = 10

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
        self._last_focus_correction_ts: float = 0.0

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

    def _get_pid(self) -> Optional[int]:
        """Get PID of running Autodarts.exe via tasklist CSV. Returns None if not found."""
        if not IS_WINDOWS:
            return None
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self._process_name}", "/NH", "/FO", "CSV"],
                **_SUBPROCESS_SAFE,
            )
            stdout = result.stdout or ""
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if not line or self._process_name.lower() not in line.lower():
                    continue
                # CSV format: "Autodarts.exe","1234","Console","1","45,678 K"
                parts = line.replace('"', "").split(",")
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except (ValueError, IndexError):
                        pass
            return None
        except Exception as e:
            logger.debug(f"[AUTODARTS_DESKTOP] _get_pid failed: {e}")
            return None

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
            # Stage 2: Schedule non-blocking focus correction in background thread
            self._schedule_focus_correction()
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
                logger.info("[AUTODARTS_DESKTOP] launch skipped reason=already_running")
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
        """Start Autodarts.exe minimized WITHOUT stealing focus. Two-stage approach:
        Stage 1: Launch with SW_SHOWMINNOACTIVE + CREATE_NO_WINDOW
        Stage 2: Background thread checks foreground and corrects if stolen (debounced)
        """
        if not os.path.isfile(exe_path):
            err = f"Datei nicht gefunden: {exe_path}"
            self._last_error = err
            logger.warning(f"[AUTODARTS_DESKTOP] exe not found: {exe_path}")
            return {"action": "failed", "error": err}
        try:
            # Stage 1: Launch minimized, no focus steal
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
            # Stage 2: Non-blocking focus correction in background thread
            self._schedule_focus_correction()
            return {"action": "started", "exe_path": exe_path}
        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"[AUTODARTS_DESKTOP] auto-start failed: {e}")
            return {"action": "failed", "error": str(e)}

    # ── Focus Steal Correction (Non-blocking, Debounced) ──

    def _schedule_focus_correction(self):
        """
        Schedule a focus correction check in a background daemon thread.
        Debounced: will not run more than once per _FOCUS_CORRECTION_DEBOUNCE seconds.
        This ensures the asyncio event loop is never blocked.
        """
        if not IS_WINDOWS:
            return
        now = time.monotonic()
        elapsed = now - self._last_focus_correction_ts
        if elapsed < _FOCUS_CORRECTION_DEBOUNCE:
            logger.debug(f"[AUTODARTS_DESKTOP] focus correction debounced ({int(_FOCUS_CORRECTION_DEBOUNCE - elapsed)}s remaining)")
            return
        self._last_focus_correction_ts = now
        thread = threading.Thread(target=self._do_focus_correction, daemon=True, name="autodarts-focus-fix")
        thread.start()
        logger.info("[AUTODARTS_DESKTOP] focus correction scheduled (background thread)")

    def _do_focus_correction(self):
        """
        Stage 2 of focus-steal prevention. Runs in a BACKGROUND THREAD.
        After launching Autodarts Desktop, wait briefly for its window to appear,
        then check if it stole focus. If detected, minimize it and restore the
        previous foreground window.
        Best-effort only — failures are warnings, not errors.
        """
        try:
            # Wait for the Autodarts window to appear (2s is enough for most launches)
            time.sleep(2)
            # Use PowerShell to detect and correct focus steal via Win32 API
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
                logger.info("[AUTODARTS_DESKTOP] foreground_corrected action=minimize")
            elif stdout.startswith("OK:"):
                logger.debug(f"[AUTODARTS_DESKTOP] no focus steal detected, fg={stdout}")
            else:
                logger.debug(f"[AUTODARTS_DESKTOP] focus check output: {stdout}")
        except Exception as e:
            logger.warning(f"[AUTODARTS_DESKTOP] foreground_correction_failed reason={e}")

    # ── Status ──

    def get_status(self, config: Optional[dict] = None) -> dict:
        """Return comprehensive status of Autodarts Desktop.
        Accepts optional config dict to include enabled/configured fields.
        """
        logger.debug("[AUTODARTS_DESKTOP] status check start")
        last_check_ok = True
        try:
            running = self.is_running()
            pid = self._get_pid() if running else None
        except Exception as e:
            running = False
            pid = None
            last_check_ok = False
            logger.warning(f"[AUTODARTS_DESKTOP] status error={e}")

        if running:
            logger.debug(f"[AUTODARTS_DESKTOP] status running pid={pid}")
        else:
            logger.debug("[AUTODARTS_DESKTOP] status not_running")

        now = time.monotonic()
        cooldown_active = (now - self._last_auto_start_ts) < _AUTO_START_COOLDOWN

        cfg = config or {}
        exe_path = cfg.get("exe_path", "")
        enabled = cfg.get("auto_start", False)
        configured = bool(exe_path)

        return {
            "running": running,
            "pid": pid,
            "process_name": self._process_name,
            "platform": platform.system(),
            "supported": IS_WINDOWS,
            "enabled": enabled,
            "configured": configured,
            "exe_path": exe_path,
            "auto_start_cooldown_s": _AUTO_START_COOLDOWN,
            "cooldown_active": cooldown_active,
            "last_start_attempt_at": self._last_start_attempt_at,
            "last_error": self._last_error,
            "last_check_ok": last_check_ok,
        }

    # ── Ensure Desktop Ready (Admin Wake/Recovery) ──

    def ensure_desktop_ready(self, exe_path: str) -> dict:
        """One-shot check and start if needed. For admin wake/recovery endpoint.
        Synchronous — caller should wrap in asyncio.to_thread if needed.
        """
        logger.info("[AUTODARTS_DESKTOP] ensure_desktop_ready requested")
        was_running = False
        try:
            was_running = self.is_running()
        except Exception:
            pass

        result = {"was_running_before": was_running}

        if was_running:
            pid = self._get_pid()
            result.update({
                "action_taken": "none",
                "running_after": True,
                "pid_after": pid,
                "message": "Autodarts Desktop laeuft bereits",
            })
            logger.info(f"[AUTODARTS_DESKTOP] ensure_desktop_ready: already running pid={pid}")
        else:
            if not exe_path:
                result.update({
                    "action_taken": "skipped",
                    "running_after": False,
                    "pid_after": None,
                    "message": "Kein exe_path konfiguriert",
                })
                logger.info("[AUTODARTS_DESKTOP] ensure_desktop_ready: no exe_path configured")
                return result

            start_result = self._start_no_focus(exe_path, trigger="admin_ensure")
            # Brief wait for process to appear
            time.sleep(2)
            try:
                running_after = self.is_running()
            except Exception:
                running_after = False
            pid_after = self._get_pid() if running_after else None
            action = "started" if running_after else "start_failed"
            msg = start_result.get("exe_path", start_result.get("error", "Unbekannt"))
            result.update({
                "action_taken": action,
                "running_after": running_after,
                "pid_after": pid_after,
                "message": f"Start {'erfolgreich' if running_after else 'fehlgeschlagen'}: {msg}",
            })
            logger.info(f"[AUTODARTS_DESKTOP] ensure_desktop_ready: {action} running_after={running_after} pid={pid_after}")

        return result


autodarts_desktop = AutodartsDesktopService()
