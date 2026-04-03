@echo off
REM Darts Kiosk Windows Agent — Start Script
REM ==================================================
REM Starts the local Windows agent process.
REM The agent runs on 127.0.0.1 (localhost only).
REM
REM For invisible autostart, use start_agent_silent.vbs instead.
REM For Task Scheduler setup, run: python setup_autostart.py
REM
REM Configuration via environment or CLI:
REM   AGENT_PORT         — HTTP port (default: 8003)
REM   AGENT_SECRET       — Shared secret (read from backend\.env if not set)
REM   AUTODARTS_EXE_PATH — Path to Autodarts.exe

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "APP_VERSION=unknown"
if exist "%ROOT_DIR%\VERSION" (
    set /p APP_VERSION=<"%ROOT_DIR%\VERSION"
)

REM Load backend .env defaults if present (standalone-friendly)
if exist "%ROOT_DIR%\backend\.env" call :load_env_value AGENT_PORT AGENT_PORT
if exist "%ROOT_DIR%\backend\.env" call :load_env_value AGENT_SECRET AGENT_SECRET
if exist "%ROOT_DIR%\backend\.env" call :load_env_value AUTODARTS_EXE_PATH AUTODARTS_EXE_PATH
if not defined AGENT_PORT set "AGENT_PORT=8003"

REM Activate venv if available
if exist "%ROOT_DIR%\.venv\Scripts\activate.bat" (
    call "%ROOT_DIR%\.venv\Scripts\activate.bat"
)

REM Start agent (single instance guard built-in)
echo [AGENT] Starting Darts Kiosk Agent v!APP_VERSION!...
echo [AGENT] Port: !AGENT_PORT!
echo [AGENT] Logs: %ROOT_DIR%\data\logs\agent.log
echo [AGENT] Lock: %ROOT_DIR%\data\logs\agent.lock
echo.
python "%SCRIPT_DIR%darts_agent.py" --port !AGENT_PORT! --log-dir "%ROOT_DIR%\data\logs" %*
endlocal
exit /b %ERRORLEVEL%

goto :eof

:load_env_value
setlocal enabledelayedexpansion
set "_value="
for /f "tokens=1,* delims==" %%a in ('findstr /R /B /C:"%~1=" "%ROOT_DIR%\backend\.env" 2^>nul') do (
    if /I "%%a"=="%~1" set "_value=%%b"
)
for /f "tokens=* delims= " %%a in ("!_value!") do set "_value=%%a"
endlocal & if not "%_value%"=="" set "%~2=%_value%"
goto :eof
