"""
System Control Service v3.3.1

Admin-triggered system operations:
- Backend restart (graceful, async)
- OS reboot (Windows only)
- OS shutdown (Windows only)

All operations are safe, logged, and degrade gracefully on unsupported platforms.
"""
import asyncio
import logging
import os
import platform
import subprocess

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


class SystemControlService:
    """Admin-triggered system control operations."""

    async def restart_backend(self) -> dict:
        """Schedule graceful backend restart. Returns immediately, restart happens async."""
        logger.info("[SYSTEM] backend restart requested by admin")
        try:
            loop = asyncio.get_running_loop()
            loop.call_later(2.0, self._do_restart)
            logger.info("[SYSTEM] backend restart scheduled (2s delay)")
            return {
                "accepted": True,
                "message": "Backend-Neustart in 2 Sekunden geplant",
            }
        except Exception as e:
            logger.error(f"[SYSTEM] backend restart scheduling failed: {e}")
            return {"accepted": False, "error": str(e)}

    def _do_restart(self):
        """Execute backend restart.
        - Windows: os._exit(1) — watchdog script handles restart.
        - Linux/--reload: touch own source file to trigger uvicorn file-watcher restart.
        - Fallback: os._exit(1) — supervisor/systemd handles restart.
        """
        logger.info("[SYSTEM] backend restart executing")
        if IS_WINDOWS:
            os._exit(1)
        else:
            # Touch own source to trigger uvicorn --reload file watcher
            try:
                import pathlib
                pathlib.Path(__file__).touch()
                logger.info("[SYSTEM] backend restart triggered via file touch (reload)")
            except Exception as e:
                logger.warning(f"[SYSTEM] file touch failed ({e}), falling back to os._exit")
                os._exit(1)

    async def reboot_os(self) -> dict:
        """Trigger OS reboot. Windows only."""
        if not IS_WINDOWS:
            return {"accepted": False, "error": "Nur auf Windows verfuegbar", "supported": False}

        logger.info("[SYSTEM] reboot requested by admin")
        try:
            subprocess.Popen(
                ["shutdown", "/r", "/t", "5", "/c", "Darts Kiosk: Neustart durch Admin"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"accepted": True, "message": "System-Neustart in 5 Sekunden"}
        except Exception as e:
            logger.error(f"[SYSTEM] reboot command failed: {e}")
            return {"accepted": False, "error": str(e)}

    async def shutdown_os(self) -> dict:
        """Trigger OS shutdown. Windows only."""
        if not IS_WINDOWS:
            return {"accepted": False, "error": "Nur auf Windows verfuegbar", "supported": False}

        logger.info("[SYSTEM] shutdown requested by admin")
        try:
            subprocess.Popen(
                ["shutdown", "/s", "/t", "5", "/c", "Darts Kiosk: Herunterfahren durch Admin"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"accepted": True, "message": "System wird in 5 Sekunden heruntergefahren"}
        except Exception as e:
            logger.error(f"[SYSTEM] shutdown command failed: {e}")
            return {"accepted": False, "error": str(e)}


system_control = SystemControlService()
