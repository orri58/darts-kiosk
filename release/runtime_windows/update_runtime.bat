@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if not exist "data\update_manifest.json" (
    echo [FEHLER] Kein Runtime-Update vorbereitet.
    echo         Erwartet: data\update_manifest.json
    pause
    exit /b 1
)

if exist "app\.venv\Scripts\activate.bat" (
    call "app\.venv\Scripts\activate.bat"
) else (
    echo [FAIL] app\.venv fehlt. Bitte zuerst app\bin\setup_runtime.bat ausfuehren.
    pause
    exit /b 1
)

echo [1/4] Runtime-Struktur pruefen...
python app\bin\runtime_maintenance.py validate
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Runtime-Struktur nicht update-faehig.
    pause
    exit /b 1
)

echo [2/4] Runtime-Update-Payload pruefen...
python app\bin\runtime_maintenance.py validate-update --manifest "data\update_manifest.json"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Runtime-Update ist nicht app-only oder unvollstaendig.
    echo        Erwartet wird ein Staging mit app\backend, app\frontend\build, app\agent und app\bin.
    pause
    exit /b 1
)

echo [3/4] Vorab-Bereinigung (Vorschau)...
python app\bin\runtime_maintenance.py cleanup --dry-run >nul

echo [4/4] Starte Updater...
python app\bin\updater.py "data\update_manifest.json"
set "EXIT_CODE=!ERRORLEVEL!"

set "UPDATER_LOG_PATH="
if exist "logs\updater.log" (
    set "UPDATER_LOG_PATH=logs\updater.log"
) else if exist "data\logs\updater.log" (
    set "UPDATER_LOG_PATH=data\logs\updater.log"
)

if "%UPDATER_LOG_PATH%"=="" (
    python app\bin\runtime_maintenance.py record-updater-run --manifest "data\update_manifest.json" --exit-code !EXIT_CODE!
) else (
    python app\bin\runtime_maintenance.py record-updater-run --manifest "data\update_manifest.json" --exit-code !EXIT_CODE! --log-path "%UPDATER_LOG_PATH%"
)

echo.
if exist "data\update_result.json" (
    echo Update-Ergebnis: data\update_result.json
)
if exist "data\last_updater_run.json" (
    echo Updater-Lauf erfasst: data\last_updater_run.json
)
if exist "logs\updater.log" (
    echo Updater-Log: logs\updater.log
) else if exist "data\logs\updater.log" (
    echo Updater-Log: data\logs\updater.log
)
echo.
pause
endlocal & exit /b %EXIT_CODE%
