@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "BACKUP_PATH=%~1"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
echo [1/1] Erzeuge app-only Runtime-Backup...
if "%BACKUP_PATH%"=="" (
    python app\bin\runtime_maintenance.py create-app-backup
) else (
    python app\bin\runtime_maintenance.py create-app-backup --backup-path "%BACKUP_PATH%"
)
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Runtime-App-Backup erstellt.
) else (
    echo [FAIL] Runtime-App-Backup konnte nicht erstellt werden.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%
