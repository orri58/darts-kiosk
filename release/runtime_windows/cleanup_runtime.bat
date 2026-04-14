@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "MODE=%~1"
if /I "%MODE%"=="--apply" (
    set "DRYRUN="
    echo [INFO] Wende Runtime-Bereinigung an...
) else (
    set "DRYRUN=--dry-run"
    echo [INFO] Fuehre Runtime-Bereinigung nur als Vorschau aus.
    echo        Fuer echte Bereinigung: app\bin\cleanup_runtime.bat --apply
)

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
python app\bin\runtime_maintenance.py cleanup %DRYRUN%
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
endlocal & exit /b %EXIT_CODE%
