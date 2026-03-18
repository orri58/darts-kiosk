"""
Autodarts Desktop Supervision Service (v3.2.0 — Minimal)

Detects if Autodarts.exe is running, can start/restart it.
The exe path is configurable via the settings DB.
This service only runs on Windows.
"""
import asyncio
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


class AutodartsDesktopService:
    """Minimal supervision for the Autodarts Desktop application."""

    def __init__(self):
        self._process_name = "Autodarts.exe"

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

    def get_status(self) -> dict:
        """Return current status of Autodarts Desktop."""
        running = self.is_running()
        return {
            "running": running,
            "process_name": self._process_name,
            "platform": platform.system(),
            "supported": IS_WINDOWS,
        }


autodarts_desktop = AutodartsDesktopService()
