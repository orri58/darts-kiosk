@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "BOARD_ID=BOARD-1"
set "BASE_URL=http://localhost:8001"
if exist "backend\.env" call :load_env_value BOARD_ID BOARD_ID
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

python scripts\local_smoke.py --base-url "%BASE_URL%" --board-id "%BOARD_ID%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Smoke-Test erfolgreich.
) else (
    echo [FAIL] Smoke-Test fehlgeschlagen. Bitte data\logs\app.log und logs\backend.log pruefen.
)

echo.
pause
endlocal & exit /b %EXIT_CODE%

goto :eof

:load_env_value
setlocal enabledelayedexpansion
set "_value="
for /f "tokens=1,* delims==" %%a in ('findstr /R /B /C:"%~1=" "backend\.env" 2^>nul') do (
    if /I "%%a"=="%~1" set "_value=%%b"
)
for /f "tokens=* delims= " %%a in ("!_value!") do set "_value=%%a"
endlocal & if not "%_value%"=="" set "%~2=%_value%"
goto :eof
