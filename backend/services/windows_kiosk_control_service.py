"""
Windows Kiosk Control Service v3.3.3

Admin-triggered Windows kiosk operations:
- Shell Switch: Toggle between Explorer and Kiosk shell (registry)
- Task Manager Toggle: Enable/disable via Group Policy registry key

All operations are safe, reversible, audit-logged, and degrade gracefully
on non-Windows platforms.
"""
import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Registry paths
_WINLOGON_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
_TASKMGR_POLICY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
_SHELL_VALUE_NAME = "Shell"
_TASKMGR_VALUE_NAME = "DisableTaskMgr"

EXPLORER_SHELL = "explorer.exe"


def _not_windows_response(feature: str) -> dict:
    return {
        "supported": False,
        "reason": "windows_only",
        "message": f"{feature} ist nur auf Windows verfuegbar",
    }


class WindowsKioskControlService:
    """Admin-triggered Windows kiosk control operations."""

    # ── Shell Switch ──

    def get_current_shell(self) -> Optional[str]:
        """Read the current Windows shell from registry. Returns None on non-Windows."""
        if not IS_WINDOWS:
            return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _WINLOGON_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, _SHELL_VALUE_NAME)
                return value
        except Exception as e:
            logger.error(f"[KIOSK_CTRL] Failed to read shell: {e}")
            return None

    def classify_shell(self, shell_value: Optional[str]) -> str:
        """Classify a shell value: 'explorer' | 'kiosk' | 'custom' | 'unknown'."""
        if shell_value is None:
            return "unknown"
        lower = shell_value.lower().strip()
        if lower == "explorer.exe" or lower.endswith("\\explorer.exe"):
            return "explorer"
        # Check for common kiosk patterns
        if "kiosk" in lower or "autostart" in lower or "start_kiosk" in lower:
            return "kiosk"
        if lower:
            return "custom"
        return "unknown"

    def get_shell_status(self, kiosk_shell_configured: str = "") -> dict:
        """Get current shell status."""
        if not IS_WINDOWS:
            return {
                **_not_windows_response("Shell Switch"),
                "is_windows": False,
                "current_shell": None,
                "shell_mode": "unknown",
                "kiosk_shell_configured": kiosk_shell_configured,
                "kiosk_controls_available": False,
            }

        current = self.get_current_shell()
        mode = self.classify_shell(current)
        return {
            "supported": True,
            "is_windows": True,
            "current_shell": current,
            "shell_mode": mode,
            "kiosk_shell_configured": kiosk_shell_configured,
            "kiosk_controls_available": True,
        }

    def switch_to_explorer(self) -> dict:
        """Set Windows shell to explorer.exe."""
        if not IS_WINDOWS:
            return _not_windows_response("Shell Switch")

        current = self.get_current_shell()
        if current and current.lower().strip() in ("explorer.exe",):
            return {
                "success": True,
                "changed": False,
                "previous_shell": current,
                "new_shell": EXPLORER_SHELL,
                "reboot_required": False,
                "message": "Explorer-Shell ist bereits aktiv",
            }

        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _WINLOGON_KEY, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                winreg.SetValueEx(key, _SHELL_VALUE_NAME, 0, winreg.REG_SZ, EXPLORER_SHELL)

            logger.info(
                f"[KIOSK_CTRL] shell_switch_to_explorer "
                f"previous_shell={current} new_shell={EXPLORER_SHELL}")
            return {
                "success": True,
                "changed": True,
                "previous_shell": current,
                "new_shell": EXPLORER_SHELL,
                "reboot_required": True,
                "message": "Shell auf Explorer umgestellt. Aenderung wird nach Neustart/Neuanmeldung wirksam.",
            }
        except PermissionError:
            logger.error("[KIOSK_CTRL] shell_switch_to_explorer FAILED: PermissionError (admin required)")
            return {
                "success": False,
                "error": "Keine Berechtigung. Backend muss als Administrator laufen.",
                "previous_shell": current,
            }
        except Exception as e:
            logger.error(f"[KIOSK_CTRL] shell_switch_to_explorer FAILED: {e}")
            return {"success": False, "error": str(e), "previous_shell": current}

    def switch_to_kiosk(self, kiosk_shell_path: str) -> dict:
        """Set Windows shell to kiosk shell."""
        if not IS_WINDOWS:
            return _not_windows_response("Shell Switch")

        if not kiosk_shell_path or not kiosk_shell_path.strip():
            return {
                "success": False,
                "error": "Kein Kiosk-Shell-Pfad konfiguriert. Bitte zuerst in den Einstellungen festlegen.",
            }

        current = self.get_current_shell()
        target = kiosk_shell_path.strip()

        if current and current.strip() == target:
            return {
                "success": True,
                "changed": False,
                "previous_shell": current,
                "new_shell": target,
                "reboot_required": False,
                "message": "Kiosk-Shell ist bereits aktiv",
            }

        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _WINLOGON_KEY, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                winreg.SetValueEx(key, _SHELL_VALUE_NAME, 0, winreg.REG_SZ, target)

            logger.info(
                f"[KIOSK_CTRL] shell_switch_to_kiosk "
                f"previous_shell={current} new_shell={target}")
            return {
                "success": True,
                "changed": True,
                "previous_shell": current,
                "new_shell": target,
                "reboot_required": True,
                "message": "Shell auf Kiosk-Modus umgestellt. Aenderung wird nach Neustart/Neuanmeldung wirksam.",
            }
        except PermissionError:
            logger.error("[KIOSK_CTRL] shell_switch_to_kiosk FAILED: PermissionError")
            return {
                "success": False,
                "error": "Keine Berechtigung. Backend muss als Administrator laufen.",
                "previous_shell": current,
            }
        except Exception as e:
            logger.error(f"[KIOSK_CTRL] shell_switch_to_kiosk FAILED: {e}")
            return {"success": False, "error": str(e), "previous_shell": current}

    # ── Task Manager Toggle ──

    def get_task_manager_status(self) -> dict:
        """Check if Task Manager is disabled via Group Policy registry."""
        if not IS_WINDOWS:
            return {
                **_not_windows_response("Task Manager Toggle"),
                "is_windows": False,
                "task_manager_disabled": False,
                "configured": False,
                "scope": None,
            }

        disabled = False
        scope = None
        try:
            import winreg
            # Check HKCU first (user-level policy)
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TASKMGR_POLICY_KEY, 0,
                                    winreg.KEY_READ) as key:
                    value, _ = winreg.QueryValueEx(key, _TASKMGR_VALUE_NAME)
                    if value == 1:
                        disabled = True
                        scope = "user"
            except FileNotFoundError:
                pass
            except OSError:
                pass

            # Check HKLM as fallback (machine-level)
            if not disabled:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _TASKMGR_POLICY_KEY, 0,
                                        winreg.KEY_READ) as key:
                        value, _ = winreg.QueryValueEx(key, _TASKMGR_VALUE_NAME)
                        if value == 1:
                            disabled = True
                            scope = "machine"
                except FileNotFoundError:
                    pass
                except OSError:
                    pass

        except Exception as e:
            logger.error(f"[KIOSK_CTRL] Failed to read TaskMgr status: {e}")

        return {
            "supported": True,
            "is_windows": True,
            "task_manager_disabled": disabled,
            "configured": disabled,
            "scope": scope,
        }

    def disable_task_manager(self) -> dict:
        """Disable Task Manager via HKCU Group Policy registry."""
        if not IS_WINDOWS:
            return _not_windows_response("Task Manager Toggle")

        try:
            import winreg
            # Use HKCU (user-level, no admin required)
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _TASKMGR_POLICY_KEY, 0,
                                     winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, _TASKMGR_VALUE_NAME, 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)

            logger.info("[KIOSK_CTRL] task_manager_disable scope=user")
            return {
                "success": True,
                "task_manager_disabled": True,
                "scope": "user",
                "message": "Task-Manager deaktiviert (Benutzer-Policy). Sofort wirksam.",
            }
        except Exception as e:
            logger.error(f"[KIOSK_CTRL] disable_task_manager FAILED: {e}")
            return {"success": False, "error": str(e)}

    def enable_task_manager(self) -> dict:
        """Enable Task Manager by removing HKCU Group Policy registry value."""
        if not IS_WINDOWS:
            return _not_windows_response("Task Manager Toggle")

        try:
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TASKMGR_POLICY_KEY, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, _TASKMGR_VALUE_NAME)
            except FileNotFoundError:
                pass  # Already enabled (value doesn't exist)

            logger.info("[KIOSK_CTRL] task_manager_enable scope=user")
            return {
                "success": True,
                "task_manager_disabled": False,
                "scope": "user",
                "message": "Task-Manager aktiviert. Sofort wirksam.",
            }
        except Exception as e:
            logger.error(f"[KIOSK_CTRL] enable_task_manager FAILED: {e}")
            return {"success": False, "error": str(e)}

    # ── Combined Status ──

    def get_full_status(self, kiosk_shell_configured: str = "") -> dict:
        """Get combined kiosk control status."""
        shell = self.get_shell_status(kiosk_shell_configured)
        taskmgr = self.get_task_manager_status()
        return {
            "is_windows": IS_WINDOWS,
            "kiosk_controls_available": IS_WINDOWS,
            "shell": shell,
            "task_manager": taskmgr,
        }


windows_kiosk_control = WindowsKioskControlService()
