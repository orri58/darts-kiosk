@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "APP_VERSION=unknown"
if exist "config\VERSION" set /p APP_VERSION=<config\VERSION
set "BACKEND_PORT=8001"
set "AGENT_PORT=8003"
set "BOARD_ID=BOARD-1"

if not exist "app\backend\.env" (
    echo [FAIL] app\backend\.env fehlt. Bitte zuerst app\bin\setup_runtime.bat ausfuehren.
    pause
    exit /b 1
)

call :load_env_value BOARD_ID BOARD_ID
call :load_env_value BACKEND_PORT BACKEND_PORT
call :load_env_value AGENT_PORT AGENT_PORT

if exist "app\.venv\Scripts\activate.bat" (
    call "app\.venv\Scripts\activate.bat"
) else (
    echo [FAIL] app\.venv fehlt. Bitte zuerst app\bin\setup_runtime.bat ausfuehren.
    pause
    exit /b 1
)

if not exist "data\logs" mkdir data\logs
if not exist "data\db" mkdir data\db
if not exist "data\downloads" mkdir data\downloads
if not exist "data\app_backups" mkdir data\app_backups
if not exist "data\chrome_profile\!BOARD_ID!" mkdir "data\chrome_profile\!BOARD_ID!"
if not exist "data\kiosk_ui_profile" mkdir data\kiosk_ui_profile

echo.
echo ================================================================
echo   DARTS KIOSK v!APP_VERSION! - Runtime Start
echo ================================================================
echo.

taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Agent" >nul 2>&1
timeout /t 2 /nobreak >nul

echo [1/3] Backend starten...
start "Darts Backend" /MIN "%~dp0_run_backend.bat"
timeout /t 5 /nobreak >nul

set "BACKEND_READY=0"
for /L %%i in (1,1,6) do (
    if !BACKEND_READY!==0 (
        curl -sf "http://localhost:!BACKEND_PORT!/api/health" >nul 2>&1
        if !ERRORLEVEL!==0 (
            set "BACKEND_READY=1"
            echo   [OK] Backend erreichbar
        ) else (
            timeout /t 2 /nobreak >nul
        )
    )
)
if !BACKEND_READY!==1 if exist "app\agent\start_agent.bat" (
    echo [2/3] Agent starten...
    start "Darts Agent" /MIN cmd /c ""%CD%\app\agent\start_agent.bat""
) else (
    echo [2/3] Kein Agent enthalten - uebersprungen
)

echo [3/3] Kiosk-UI starten...
start "Darts Overlay" /MIN pythonw app\bin\credits_overlay.py --board-id "!BOARD_ID!" --api "http://localhost:!BACKEND_PORT!"
start "" "http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!"

echo.
echo Runtime laeuft:
echo   Kiosk: http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!
echo   Admin: http://localhost:!BACKEND_PORT!/admin
echo   Logs:  data\logs\backend.log
echo.
pause
endlocal
goto :eof

:load_env_value
setlocal enabledelayedexpansion
set "_value="
for /f "tokens=1,* delims==" %%a in ('findstr /R /B /C:"%~1=" "app\backend\.env" 2^>nul') do (
    if /I "%%a"=="%~1" set "_value=%%b"
)
for /f "tokens=* delims= " %%a in ("!_value!") do set "_value=%%a"
endlocal & if not "%_value%"=="" set "%~2=%_value%"
goto :eof
