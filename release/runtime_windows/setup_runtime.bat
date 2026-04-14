@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "APP_VERSION=unknown"
if exist "config\VERSION" set /p APP_VERSION=<config\VERSION

echo.
echo ================================================================
echo   DARTS KIOSK v!APP_VERSION! - Runtime Setup
echo ================================================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Python nicht gefunden.
    pause
    exit /b 1
)

if not exist "data" mkdir data
if not exist "data\db" mkdir data\db
if not exist "data\logs" mkdir data\logs
if not exist "data\backups" mkdir data\backups
if not exist "data\app_backups" mkdir data\app_backups
if not exist "data\downloads" mkdir data\downloads
if not exist "data\assets" mkdir data\assets
if not exist "data\chrome_profile" mkdir data\chrome_profile
if not exist "data\kiosk_ui_profile" mkdir data\kiosk_ui_profile

if not exist "app\.venv\Scripts\activate.bat" (
    echo [1/5] Erstelle Python-.venv unter app\.venv ...
    python -m venv app\.venv
    if !ERRORLEVEL! NEQ 0 (
        echo [FAIL] .venv konnte nicht erstellt werden.
        pause
        exit /b 1
    )
) else (
    echo [1/5] app\.venv existiert bereits
)

call "app\.venv\Scripts\activate.bat"
echo [2/5] Installiere Backend-Pakete ...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r app\backend\requirements.txt
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Backend-Pakete konnten nicht installiert werden.
    pause
    exit /b 1
)

if exist "app\agent\requirements.txt" (
    echo [3/5] Installiere Agent-Pakete ...
    python -m pip install -r app\agent\requirements.txt
    if !ERRORLEVEL! NEQ 0 (
        echo [FAIL] Agent-Pakete konnten nicht installiert werden.
        pause
        exit /b 1
    )
) else (
    echo [3/5] Keine Agent requirements gefunden - uebersprungen
)

if not exist "app\backend\.env" (
    copy "config\backend.env.example" "app\backend\.env" >nul
    echo [4/5] app\backend\.env aus config\backend.env.example erstellt
) else (
    echo [4/5] app\backend\.env existiert bereits
)

if not exist "app\frontend\.env" (
    copy "config\frontend.env.example" "app\frontend\.env" >nul
    echo [5/5] app\frontend\.env aus config\frontend.env.example erstellt
) else (
    echo [5/5] app\frontend\.env existiert bereits
)

echo.
echo Setup abgeschlossen.
echo Naechster Schritt: app\bin\start_runtime.bat
echo.
pause
endlocal
