@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
python app\bin\runtime_maintenance.py validate
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Runtime-Struktur und Writable-Pfade sehen sauber aus.
) else (
    echo [FAIL] Runtime-Struktur unvollstaendig, schreibgeschuetzt oder fehlerhaft.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%
