"""
Darts Kiosk — Windows Agent v3.4.0
====================================

Separate local process for OS-level kiosk management.
Runs on the kiosk PC alongside the FastAPI backend.

Responsibilities:
  - Process supervision (Autodarts Desktop, Chrome, Backend)
  - System commands (restart backend, reboot, shutdown)
  - Kiosk controls (shell switch, task manager toggle)
  - Heartbeat / status reporting

Design:
  - HTTP server on 127.0.0.1 ONLY (no external access)
  - Authenticated via shared secret (AGENT_SECRET)
  - All subprocess calls have strict timeouts
  - Graceful degradation on non-Windows
  - Does NOT replace any existing backend logic
"""
import argparse
import json
import logging
import logging.handlers
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

AGENT_VERSION = "3.4.0"
IS_WINDOWS = platform.system() == "Windows"

# Defaults (overridable via CLI args or env)
DEFAULT_PORT = 8002
DEFAULT_HOST = "127.0.0.1"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8001"

# Subprocess safety
_SUBPROCESS_TIMEOUT = 10
_SUBPROCESS_SAFE = {
    "capture_output": True,
    "text": True,
    "timeout": _SUBPROCESS_TIMEOUT,
}
if IS_WINDOWS:
    _SUBPROCESS_SAFE["encoding"] = "utf-8"
    _SUBPROCESS_SAFE["errors"] = "replace"

# Cooldowns
_AUTODARTS_COOLDOWN = 60        # seconds between auto-start attempts
_FOCUS_CORRECTION_DEBOUNCE = 10  # seconds between focus corrections
_BACKEND_RESTART_COOLDOWN = 30   # seconds between backend restart attempts


# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

def setup_logging(log_dir: str):
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "agent.log"

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

logger = logging.getLogger("darts_agent")


# ═══════════════════════════════════════════════════════════════
# AUTODARTS DESKTOP SERVICE
# ═══════════════════════════════════════════════════════════════

class AutodartsDesktopManager:
    """Manages Autodarts Desktop process lifecycle."""

    def __init__(self):
        self._process_name = "Autodarts.exe"
        self._last_start_ts: float = 0.0
        self._last_focus_correction_ts: float = 0.0
        self._last_error: Optional[str] = None
        self._last_start_attempt: Optional[str] = None

    def is_running(self) -> bool:
        if not IS_WINDOWS:
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self._process_name}", "/NH"],
                **_SUBPROCESS_SAFE,
            )
            return self._process_name.lower() in (result.stdout or "").lower()
        except Exception as e:
            logger.warning(f"[AUTODARTS] is_running check failed: {e}")
            return False

    def get_pid(self) -> Optional[int]:
        if not IS_WINDOWS:
            return None
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self._process_name}", "/NH", "/FO", "CSV"],
                **_SUBPROCESS_SAFE,
            )
            for line in (result.stdout or "").strip().split("\n"):
                if self._process_name.lower() not in line.lower():
                    continue
                parts = line.replace('"', "").split(",")
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except (ValueError, IndexError):
                        pass
            return None
        except Exception:
            return None

    def ensure_running(self, exe_path: str) -> dict:
        """Start Autodarts Desktop if not running. Cooldown-protected."""
        if not IS_WINDOWS:
            return {"action": "skip", "reason": "not_windows"}
        if not exe_path or not os.path.isfile(exe_path):
            self._last_error = f"exe not found: {exe_path}"
            return {"action": "skip", "reason": "exe_not_found", "path": exe_path}

        if self.is_running():
            return {"action": "skip", "reason": "already_running", "pid": self.get_pid()}

        now = time.monotonic()
        elapsed = now - self._last_start_ts
        if elapsed < _AUTODARTS_COOLDOWN:
            remaining = int(_AUTODARTS_COOLDOWN - elapsed)
            return {"action": "skip", "reason": "cooldown", "remaining_s": remaining}

        self._last_start_ts = now
        self._last_start_attempt = datetime.now(timezone.utc).isoformat()
        return self._start_minimized(exe_path)

    def restart(self, exe_path: str) -> dict:
        """Kill and restart Autodarts Desktop."""
        logger.info(f"[AUTODARTS] restart requested exe={exe_path}")
        self._kill()
        time.sleep(1.5)
        self._last_start_ts = 0  # bypass cooldown for explicit restart
        self._last_start_attempt = datetime.now(timezone.utc).isoformat()
        return self._start_minimized(exe_path)

    def _start_minimized(self, exe_path: str) -> dict:
        """Start Autodarts.exe minimized without focus steal."""
        try:
            if IS_WINDOWS:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 7  # SW_SHOWMINNOACTIVE
                subprocess.Popen(
                    [exe_path],
                    startupinfo=si,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                )
            else:
                subprocess.Popen([exe_path], start_new_session=True)

            logger.info(f"[AUTODARTS] started minimized: {exe_path}")
            self._last_error = None
            self._schedule_focus_correction()
            return {"action": "started", "exe_path": exe_path}
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[AUTODARTS] start failed: {e}")
            return {"action": "failed", "error": str(e)}

    def _kill(self) -> bool:
        if not IS_WINDOWS:
            return False
        try:
            r = subprocess.run(
                ["taskkill", "/IM", self._process_name, "/F"],
                **_SUBPROCESS_SAFE,
            )
            killed = r.returncode == 0
            if killed:
                logger.info("[AUTODARTS] process killed")
            return killed
        except Exception as e:
            logger.error(f"[AUTODARTS] kill failed: {e}")
            return False

    def _schedule_focus_correction(self):
        if not IS_WINDOWS:
            return
        now = time.monotonic()
        if (now - self._last_focus_correction_ts) < _FOCUS_CORRECTION_DEBOUNCE:
            return
        self._last_focus_correction_ts = now
        t = threading.Thread(target=self._do_focus_correction, daemon=True)
        t.start()

    def _do_focus_correction(self):
        try:
            time.sleep(2)
            ps_script = '''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinApi {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$fg = [WinApi]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[WinApi]::GetWindowText($fg, $sb, 256) | Out-Null
$title = $sb.ToString()
if ($title -like "*Autodarts*") {
    [WinApi]::ShowWindow($fg, 6) | Out-Null
    Write-Output "CORRECTED:$title"
} else {
    Write-Output "OK:$title"
}
'''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                **_SUBPROCESS_SAFE,
            )
            stdout = (result.stdout or "").strip()
            if stdout.startswith("CORRECTED:"):
                logger.info(f"[AUTODARTS] focus steal corrected: {stdout.split(':', 1)[1]}")
            else:
                logger.debug(f"[AUTODARTS] no focus steal: {stdout}")
        except Exception as e:
            logger.warning(f"[AUTODARTS] focus correction failed: {e}")

    def get_status(self) -> dict:
        running = False
        pid = None
        try:
            running = self.is_running()
            pid = self.get_pid() if running else None
        except Exception:
            pass
        return {
            "running": running,
            "pid": pid,
            "process_name": self._process_name,
            "last_start_attempt": self._last_start_attempt,
            "last_error": self._last_error,
            "cooldown_active": (time.monotonic() - self._last_start_ts) < _AUTODARTS_COOLDOWN,
        }


# ═══════════════════════════════════════════════════════════════
# SYSTEM COMMANDS
# ═══════════════════════════════════════════════════════════════

class SystemCommandService:
    """OS-level system commands executed by the agent."""

    def __init__(self, backend_url: str):
        self._backend_url = backend_url
        self._last_backend_restart_ts: float = 0.0

    def restart_backend(self) -> dict:
        """Restart the backend process. Agent survives because it's a separate process."""
        now = time.monotonic()
        if (now - self._last_backend_restart_ts) < _BACKEND_RESTART_COOLDOWN:
            remaining = int(_BACKEND_RESTART_COOLDOWN - (now - self._last_backend_restart_ts))
            return {"accepted": False, "reason": "cooldown", "remaining_s": remaining}

        self._last_backend_restart_ts = now
        logger.info("[SYSTEM] backend restart requested")

        if IS_WINDOWS:
            # Find and kill the backend python process
            try:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%uvicorn%' AND CommandLine LIKE '%server%'\" | Select-Object ProcessId | Format-List"],
                    **_SUBPROCESS_SAFE,
                )
                pids = []
                for line in (r.stdout or "").splitlines():
                    s = line.strip()
                    if s.lower().startswith("processid"):
                        pid = s.split(":", 1)[1].strip()
                        if pid.isdigit():
                            pids.append(pid)

                if pids:
                    for pid in pids:
                        subprocess.run(["taskkill", "/F", "/PID", pid], **_SUBPROCESS_SAFE)
                        logger.info(f"[SYSTEM] killed backend pid={pid}")
                    return {"accepted": True, "message": f"Backend killed (pids={pids}). Watchdog should restart it."}
                else:
                    return {"accepted": False, "reason": "backend_process_not_found"}
            except Exception as e:
                logger.error(f"[SYSTEM] backend restart failed: {e}")
                return {"accepted": False, "error": str(e)}
        else:
            # Linux: touch the server file to trigger uvicorn --reload
            try:
                server_py = Path(__file__).parent.parent / "backend" / "server.py"
                if server_py.exists():
                    server_py.touch()
                    logger.info(f"[SYSTEM] backend restart via file touch: {server_py}")
                    return {"accepted": True, "message": "Backend restart triggered (file touch)"}
                return {"accepted": False, "reason": "server.py not found"}
            except Exception as e:
                return {"accepted": False, "error": str(e)}

    def reboot_os(self) -> dict:
        if not IS_WINDOWS:
            return {"accepted": False, "reason": "windows_only"}
        logger.info("[SYSTEM] OS reboot requested")
        try:
            subprocess.Popen(
                ["shutdown", "/r", "/t", "5", "/c", "Darts Kiosk Agent: Neustart"],
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
            return {"accepted": True, "message": "Neustart in 5 Sekunden"}
        except Exception as e:
            logger.error(f"[SYSTEM] reboot failed: {e}")
            return {"accepted": False, "error": str(e)}

    def shutdown_os(self) -> dict:
        if not IS_WINDOWS:
            return {"accepted": False, "reason": "windows_only"}
        logger.info("[SYSTEM] OS shutdown requested")
        try:
            subprocess.Popen(
                ["shutdown", "/s", "/t", "5", "/c", "Darts Kiosk Agent: Herunterfahren"],
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
            return {"accepted": True, "message": "Herunterfahren in 5 Sekunden"}
        except Exception as e:
            logger.error(f"[SYSTEM] shutdown failed: {e}")
            return {"accepted": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# KIOSK CONTROLS (Shell Switch + Task Manager)
# ═══════════════════════════════════════════════════════════════

class KioskControlManager:
    """Windows kiosk controls: shell switch and task manager toggle."""

    _WINLOGON_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    _TASKMGR_KEY = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"

    def get_shell_status(self) -> dict:
        if not IS_WINDOWS:
            return {"supported": False, "reason": "not_windows"}
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self._WINLOGON_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, "Shell")
                lower = value.lower().strip()
                if lower == "explorer.exe" or lower.endswith("\\explorer.exe"):
                    mode = "explorer"
                elif "kiosk" in lower:
                    mode = "kiosk"
                elif lower:
                    mode = "custom"
                else:
                    mode = "unknown"
                return {"supported": True, "current_shell": value, "shell_mode": mode}
        except Exception as e:
            return {"supported": True, "current_shell": None, "shell_mode": "unknown", "error": str(e)}

    def switch_shell(self, target: str) -> dict:
        """Switch shell. target='explorer' or a kiosk shell path."""
        if not IS_WINDOWS:
            return {"success": False, "reason": "not_windows"}
        try:
            import winreg
            shell_value = "explorer.exe" if target == "explorer" else target
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self._WINLOGON_KEY, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                winreg.SetValueEx(key, "Shell", 0, winreg.REG_SZ, shell_value)
            logger.info(f"[KIOSK] shell switched to: {shell_value}")
            return {"success": True, "new_shell": shell_value, "reboot_required": True}
        except PermissionError:
            return {"success": False, "error": "Admin-Rechte erforderlich"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_task_manager_status(self) -> dict:
        if not IS_WINDOWS:
            return {"supported": False, "reason": "not_windows"}
        disabled = False
        scope = None
        try:
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._TASKMGR_KEY, 0, winreg.KEY_READ) as key:
                    val, _ = winreg.QueryValueEx(key, "DisableTaskMgr")
                    if val == 1:
                        disabled = True
                        scope = "user"
            except (FileNotFoundError, OSError):
                pass
            if not disabled:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self._TASKMGR_KEY, 0, winreg.KEY_READ) as key:
                        val, _ = winreg.QueryValueEx(key, "DisableTaskMgr")
                        if val == 1:
                            disabled = True
                            scope = "machine"
                except (FileNotFoundError, OSError):
                    pass
        except Exception:
            pass
        return {"supported": True, "disabled": disabled, "scope": scope}

    def set_task_manager(self, enabled: bool) -> dict:
        if not IS_WINDOWS:
            return {"success": False, "reason": "not_windows"}
        try:
            import winreg
            if enabled:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._TASKMGR_KEY, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, "DisableTaskMgr")
                except FileNotFoundError:
                    pass
                logger.info("[KIOSK] task manager enabled")
                return {"success": True, "disabled": False}
            else:
                key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self._TASKMGR_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                logger.info("[KIOSK] task manager disabled")
                return {"success": True, "disabled": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# KIOSK WINDOW DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_kiosk_window() -> dict:
    """Check if the Kiosk Chrome window is visible."""
    if not IS_WINDOWS:
        return {"detected": False, "reason": "not_windows"}
    try:
        ps_script = '''
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WinEnum {
    public delegate bool EnumWinProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWinProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    public static List<string> titles = new List<string>();
    public static bool Callback(IntPtr hWnd, IntPtr lParam) {
        if (!IsWindowVisible(hWnd)) return true;
        var sb = new StringBuilder(256);
        GetWindowText(hWnd, sb, 256);
        var t = sb.ToString();
        if (t.Length > 0) titles.Add(t);
        return true;
    }
}
"@
[WinEnum]::titles.Clear()
[WinEnum]::EnumWindows([WinEnum+EnumWinProc]::new([WinEnum], "Callback"), [IntPtr]::Zero) | Out-Null
$kiosk = [WinEnum]::titles | Where-Object { $_ -like "*DartsKiosk*" -or $_ -like "*Darts Kiosk*" -or $_ -like "*localhost:8001*" }
if ($kiosk) { Write-Output "FOUND:$($kiosk[0])" } else { Write-Output "NOT_FOUND" }
'''
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            **_SUBPROCESS_SAFE,
        )
        stdout = (result.stdout or "").strip()
        if stdout.startswith("FOUND:"):
            return {"detected": True, "title": stdout.split(":", 1)[1]}
        return {"detected": False}
    except Exception as e:
        return {"detected": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# HTTP REQUEST HANDLER
# ═══════════════════════════════════════════════════════════════

class AgentHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for the agent's local API."""

    server_version = f"DartsAgent/{AGENT_VERSION}"

    # Injected by main()
    agent_secret: str = ""
    autodarts: AutodartsDesktopManager = None
    system_cmd: SystemCommandService = None
    kiosk_ctrl: KioskControlManager = None
    start_time: float = 0
    autodarts_exe_path: str = ""

    def log_message(self, format, *args):
        """Redirect HTTP server logs to our logger."""
        logger.debug(f"[HTTP] {args[0]} {args[1]} {args[2]}")

    def _auth_ok(self) -> bool:
        token = self.headers.get("X-Agent-Secret", "")
        if not token or token != self.agent_secret:
            self._respond(401, {"error": "unauthorized"})
            return False
        return True

    def _respond(self, code: int, data: dict):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    # ── ROUTING ──

    def do_GET(self):
        if self.path == "/status":
            return self._handle_status()
        self._respond(404, {"error": "not_found"})

    def do_POST(self):
        if not self._auth_ok():
            return

        routes = {
            "/autodarts/ensure": self._handle_autodarts_ensure,
            "/autodarts/restart": self._handle_autodarts_restart,
            "/system/restart-backend": self._handle_restart_backend,
            "/system/reboot": self._handle_reboot,
            "/system/shutdown": self._handle_shutdown,
            "/kiosk/shell/switch": self._handle_shell_switch,
            "/kiosk/taskmanager/set": self._handle_taskmanager_set,
        }

        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self._respond(404, {"error": "not_found"})

    # ── HANDLERS ──

    def _handle_status(self):
        """Public status endpoint (no auth required for health checks)."""
        uptime = time.time() - self.start_time
        kiosk_window = detect_kiosk_window()
        shell = self.kiosk_ctrl.get_shell_status()
        taskmgr = self.kiosk_ctrl.get_task_manager_status()

        self._respond(200, {
            "agent_online": True,
            "agent_version": AGENT_VERSION,
            "platform": platform.system(),
            "platform_release": platform.release(),
            "is_windows": IS_WINDOWS,
            "uptime_s": int(uptime),
            "heartbeat": datetime.now(timezone.utc).isoformat(),
            "autodarts": self.autodarts.get_status(),
            "kiosk_window": kiosk_window,
            "shell": shell,
            "task_manager": taskmgr,
        })

    def _handle_autodarts_ensure(self):
        body = self._read_body()
        exe = body.get("exe_path", self.autodarts_exe_path)
        result = self.autodarts.ensure_running(exe)
        logger.info(f"[API] autodarts/ensure result={result}")
        self._respond(200, result)

    def _handle_autodarts_restart(self):
        body = self._read_body()
        exe = body.get("exe_path", self.autodarts_exe_path)
        result = self.autodarts.restart(exe)
        logger.info(f"[API] autodarts/restart result={result}")
        self._respond(200, result)

    def _handle_restart_backend(self):
        result = self.system_cmd.restart_backend()
        logger.info(f"[API] system/restart-backend result={result}")
        self._respond(200, result)

    def _handle_reboot(self):
        result = self.system_cmd.reboot_os()
        logger.info(f"[API] system/reboot result={result}")
        self._respond(200, result)

    def _handle_shutdown(self):
        result = self.system_cmd.shutdown_os()
        logger.info(f"[API] system/shutdown result={result}")
        self._respond(200, result)

    def _handle_shell_switch(self):
        body = self._read_body()
        target = body.get("target", "explorer")
        result = self.kiosk_ctrl.switch_shell(target)
        logger.info(f"[API] kiosk/shell/switch target={target} result={result}")
        self._respond(200, result)

    def _handle_taskmanager_set(self):
        body = self._read_body()
        enabled = body.get("enabled", True)
        result = self.kiosk_ctrl.set_task_manager(enabled)
        logger.info(f"[API] kiosk/taskmanager/set enabled={enabled} result={result}")
        self._respond(200, result)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Darts Kiosk Windows Agent")
    parser.add_argument("--port", type=int, default=int(os.environ.get("AGENT_PORT", DEFAULT_PORT)),
                        help=f"Agent HTTP port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=os.environ.get("AGENT_HOST", DEFAULT_HOST),
                        help=f"Agent bind host (default: {DEFAULT_HOST})")
    parser.add_argument("--secret", default=os.environ.get("AGENT_SECRET", ""),
                        help="Shared secret for authentication")
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL),
                        help=f"Backend URL (default: {DEFAULT_BACKEND_URL})")
    parser.add_argument("--log-dir", default=os.environ.get("AGENT_LOG_DIR", str(Path(__file__).parent.parent / "data" / "logs")),
                        help="Log directory")
    parser.add_argument("--autodarts-exe", default=os.environ.get("AUTODARTS_EXE_PATH", ""),
                        help="Path to Autodarts.exe")
    args = parser.parse_args()

    if not args.secret:
        # Try loading from backend .env
        env_path = Path(__file__).parent.parent / "backend" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("AGENT_SECRET="):
                    args.secret = line.split("=", 1)[1].strip().strip('"')
                    break

    if not args.secret:
        print("ERROR: No AGENT_SECRET configured. Set via --secret, env, or backend/.env")
        sys.exit(1)

    setup_logging(args.log_dir)

    logger.info("=" * 60)
    logger.info(f"Darts Kiosk Agent v{AGENT_VERSION}")
    logger.info(f"  Host:     {args.host}:{args.port}")
    logger.info(f"  Platform: {platform.system()} {platform.release()}")
    logger.info(f"  Backend:  {args.backend_url}")
    logger.info(f"  Log Dir:  {args.log_dir}")
    logger.info(f"  Windows:  {IS_WINDOWS}")
    logger.info("=" * 60)

    # Initialize services
    autodarts = AutodartsDesktopManager()
    system_cmd = SystemCommandService(args.backend_url)
    kiosk_ctrl = KioskControlManager()

    # Inject into handler class
    AgentHandler.agent_secret = args.secret
    AgentHandler.autodarts = autodarts
    AgentHandler.system_cmd = system_cmd
    AgentHandler.kiosk_ctrl = kiosk_ctrl
    AgentHandler.start_time = time.time()
    AgentHandler.autodarts_exe_path = args.autodarts_exe

    server = HTTPServer((args.host, args.port), AgentHandler)

    # Graceful shutdown
    def shutdown_handler(sig, frame):
        logger.info(f"[AGENT] Shutdown signal received ({sig})")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info(f"[AGENT] Listening on {args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        logger.info("[AGENT] Stopped")


if __name__ == "__main__":
    main()
