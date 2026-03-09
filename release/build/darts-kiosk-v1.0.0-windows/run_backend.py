"""
Dedicated Windows Backend Launcher
===================================
Sets the correct asyncio event loop policy BEFORE uvicorn starts.

On Windows, Playwright needs ProactorEventLoop for subprocess execution.
The default uvicorn + --reload uses SelectorEventLoop which causes:
  NotImplementedError: asyncio.create_subprocess_exec

This launcher:
1. Forces WindowsProactorEventLoopPolicy (before any loop creation)
2. Starts uvicorn programmatically with reload=False
3. Binds to 0.0.0.0 for LAN access

Usage:
  python run_backend.py
"""
import sys
import os
import asyncio

# ===== CRITICAL: Set event loop policy BEFORE anything else =====
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[OK] Windows ProactorEventLoop policy set")

# Set working directory to script location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8001"))
    
    print(f"[OK] Starting Darts Kiosk backend on {host}:{port}")
    print(f"[OK] Platform: {sys.platform}, Python: {sys.version}")
    print(f"[OK] Event loop policy: {type(asyncio.get_event_loop_policy()).__name__}")
    print(f"[OK] reload=False (required for Playwright on Windows)")
    
    uvicorn.run(
        "backend.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
