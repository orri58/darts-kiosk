@echo off
REM Darts Kiosk Windows Agent — Start Script (v3.4.1)
REM ==================================================
REM Starts the local Windows agent process.
REM The agent runs on 127.0.0.1 (localhost only).
REM
REM For invisible autostart, use start_agent_silent.vbs instead.
REM For Task Scheduler setup, run: python setup_autostart.py
REM
REM Configuration via environment or CLI:
REM   AGENT_PORT        — HTTP port (default: 8002)
REM   AGENT_SECRET      — Shared secret (read from backend\.env if not set)
REM   AUTODARTS_EXE_PATH — Path to Autodarts.exe

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

REM Activate venv if available
if exist "%ROOT_DIR%\.venv\Scripts\activate.bat" (
    call "%ROOT_DIR%\.venv\Scripts\activate.bat"
)

REM Start agent (single instance guard built-in)
echo [AGENT] Starting Darts Kiosk Agent v3.4.1...
echo [AGENT] Logs: %ROOT_DIR%\data\logs\agent.log
echo [AGENT] Lock: %ROOT_DIR%\data\logs\agent.lock
echo.
python "%SCRIPT_DIR%darts_agent.py" --log-dir "%ROOT_DIR%\data\logs" %*
