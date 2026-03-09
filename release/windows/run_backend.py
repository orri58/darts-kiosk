"""
Dedicated Windows Backend Launcher with Watchdog
==================================================
Sets the correct asyncio event loop policy BEFORE uvicorn starts.

On Windows, Playwright needs ProactorEventLoop for subprocess execution.
This launcher:
1. Forces WindowsProactorEventLoopPolicy (before any loop creation)
2. Starts uvicorn programmatically with reload=False
3. Binds to 0.0.0.0 for LAN access
4. Auto-restarts on crash (up to MAX_RESTARTS within RESTART_WINDOW)

Usage:
  python run_backend.py
"""
import sys
import os
import asyncio
import time

# ===== CRITICAL: Set event loop policy BEFORE anything else =====
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[OK] Windows ProactorEventLoop policy set")

# Set working directory to script location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

MAX_RESTARTS = 5
RESTART_WINDOW = 300  # 5 minutes — reset counter after this period of stability


def run_server():
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8001"))

    print(f"[OK] Starting Darts Kiosk backend on {host}:{port}")
    print(f"[OK] Platform: {sys.platform}, Python: {sys.version}")
    print(f"[OK] Event loop policy: {type(asyncio.get_event_loop_policy()).__name__}")

    uvicorn.run(
        "backend.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    restarts = 0
    last_start = time.time()

    while True:
        now = time.time()
        # Reset counter if server ran long enough
        if now - last_start > RESTART_WINDOW:
            restarts = 0

        last_start = now
        try:
            run_server()
        except SystemExit:
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            restarts += 1
            print(f"\n[WATCHDOG] Backend crashed: {e}")
            print(f"[WATCHDOG] Restart {restarts}/{MAX_RESTARTS}")

            if restarts >= MAX_RESTARTS:
                print(f"[WATCHDOG] Max restarts reached within {RESTART_WINDOW}s — giving up")
                print(f"[WATCHDOG] Check logs\\backend.log for details")
                sys.exit(1)

            wait = min(5 * restarts, 30)
            print(f"[WATCHDOG] Restarting in {wait}s...")
            time.sleep(wait)
