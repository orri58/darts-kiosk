"""
Autodarts Desktop Supervision Service (v3.2.0 — Minimal, v3.2.1 — Auto-Start)

Detects if Autodarts.exe is running, can start/restart it.
The exe path is configurable via the settings DB.
This service only runs on Windows.

v3.2.1: Added ensure_running() with cooldown to safely auto-start on
         server boot and board unlock without focus-stealing or loops.
"""
import logging
import platform
import subprocess
import time

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Cooldown between auto-start attempts (seconds)
_AUTO_START_COOLDOWN = 60


class AutodartsDesktopService:
    """Minimal supervision for the Autodarts Desktop application."""

    def __init__(self):
        self._process_name = "Autodarts.exe"
        self._last_auto_start_ts: float = 0.0

    def is_running(self) -> bool:
        """Check if Autodarts.exe is currently running."""
        if not IS_WINDOWS:
            logger.debug("[AUTODARTS_DESKTOP] Not Windows, skipping process check")
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self._process_name}", "/NH"],
                capture_output=True, text=True, timeout=10,
            )
            return self._process_name.lower() in result.stdout.lower()
        except Exception as e:
            logger.warning(f"[AUTODARTS_DESKTOP] is_running check failed: {e}")
            return False

    def start_process(self, exe_path: str) -> dict:
        """Start Autodarts.exe minimized. Returns status dict."""
        if not IS_WINDOWS:
            return {"success": False, "error": "Not a Windows system"}

        import os
        if not os.path.isfile(exe_path):
            logger.error(f"[AUTODARTS_DESKTOP] exe not found: {exe_path}")
            return {"success": False, "error": f"Datei nicht gefunden: {exe_path}"}

        if self.is_running():
            logger.info("[AUTODARTS_DESKTOP] Already running, skipping start")
            return {"success": True, "message": "Already running"}

        try:
            # Start minimized using SW_SHOWMINIMIZED (6)
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 6  # SW_SHOWMINIMIZED
            subprocess.Popen(
                [exe_path],
                startupinfo=si,
                creationflags=subprocess.DETACHED_PROCESS,
            )
            logger.info(f"[AUTODARTS_DESKTOP] Started: {exe_path}")
            return {"success": True, "message": f"Started: {exe_path}"}
        except Exception as e:
            logger.error(f"[AUTODARTS_DESKTOP] start failed: {e}")
            return {"success": False, "error": str(e)}

    def kill_process(self) -> bool:
        """Kill all Autodarts.exe processes."""
        if not IS_WINDOWS:
            return False
        try:
            result = subprocess.run(
                ["taskkill", "/IM", self._process_name, "/F"],
                capture_output=True, text=True, timeout=10,
            )
            killed = result.returncode == 0
            if killed:
                logger.info("[AUTODARTS_DESKTOP] Process killed")
            else:
                logger.info(f"[AUTODARTS_DESKTOP] taskkill returned {result.returncode}: {result.stderr.strip()}")
            return killed
        except Exception as e:
            logger.error(f"[AUTODARTS_DESKTOP] kill failed: {e}")
            return False

    def restart_process(self, exe_path: str) -> dict:
        """Kill and restart Autodarts.exe."""
        logger.info(f"[AUTODARTS_DESKTOP] Restart requested: {exe_path}")
        self.kill_process()
        # Brief pause to allow process to fully exit
        import time
        time.sleep(1)
        return self.start_process(exe_path)

    def ensure_running(self, exe_path: str, trigger: str = "unknown") -> dict:
        """Single guarded attempt to start Autodarts.exe if not running.

        - Returns immediately if already running.
        - Respects a 60-second cooldown between attempts.
        - Never steals focus (SW_SHOWMINNOACTIVE = 7).
        - Logs outcome; never raises.
        """
        if not IS_WINDOWS:
            return {"action": "skip", "reason": "not_windows"}

        if not exe_path:
            logger.warning(f"[AUTODARTS_DESKTOP] ensure_running({trigger}): no exe_path configured")
            return {"action": "skip", "reason": "no_exe_path"}

        if self.is_running():
            return {"action": "skip", "reason": "already_running"}

        now = time.monotonic()
        elapsed = now - self._last_auto_start_ts
        if elapsed < _AUTO_START_COOLDOWN:
            remaining = int(_AUTO_START_COOLDOWN - elapsed)
            logger.info(f"[AUTODARTS_DESKTOP] ensure_running({trigger}): cooldown active ({remaining}s left)")
            return {"action": "skip", "reason": "cooldown", "remaining_s": remaining}

        self._last_auto_start_ts = now
        logger.info(f"[AUTODARTS_DESKTOP] ensure_running({trigger}): attempting start")
        return self._start_no_focus(exe_path)

    def _start_no_focus(self, exe_path: str) -> dict:
        """Start Autodarts.exe minimized WITHOUT stealing focus."""
        import os
        if not os.path.isfile(exe_path):
            logger.warning(f"[AUTODARTS_DESKTOP] exe not found: {exe_path}")
            return {"action": "failed", "error": f"Datei nicht gefunden: {exe_path}"}
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
            return {"action": "started", "exe_path": exe_path}
        except Exception as e:
            logger.warning(f"[AUTODARTS_DESKTOP] auto-start failed: {e}")
            return {"action": "failed", "error": str(e)}

    def get_status(self) -> dict:
        """Return current status of Autodarts Desktop."""
        running = self.is_running()
        return {
            "running": running,
            "process_name": self._process_name,
            "platform": platform.system(),
            "supported": IS_WINDOWS,
            "auto_start_cooldown_s": _AUTO_START_COOLDOWN,
        }


autodarts_desktop = AutodartsDesktopService()
