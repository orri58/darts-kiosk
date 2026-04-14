@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "NO_PAUSE="
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if defined DARTS_KIOSK_NO_PAUSE set "NO_PAUSE=1"

set "BOARD_ID=BOARD-1"
if exist "backend\.env" call :load_env_value BOARD_ID BOARD_ID

echo.
echo ================================================================
echo   DARTS KIOSK - Alle Dienste beenden
echo ================================================================
echo.

echo Stoppe Backend...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1

echo Stoppe Overlay...
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1

echo Stoppe Kiosk Chrome...
call :kill_chrome_profile "data\kiosk_ui_profile"
call :kill_chrome_profile "data\chrome_profile\!BOARD_ID!"

echo Stoppe Agent...
taskkill /F /FI "WINDOWTITLE eq Darts Agent" >nul 2>&1

echo.
echo ================================================================
echo   Alle Dienste beendet.
echo ================================================================
echo.
if not defined NO_PAUSE pause
endlocal
goto :eof

:load_env_value
setlocal enabledelayedexpansion
set "_lookup=%~1"
set "_value="
for /f "tokens=1,* delims==" %%a in ('findstr /R /B /C:"%~1=" "backend\.env" 2^>nul') do (
    if /I "%%a"=="%~1" set "_value=%%b"
)
for /f "tokens=* delims= " %%a in ("!_value!") do set "_value=%%a"
endlocal & if not "%_value%"=="" set "%~2=%_value%"
goto :eof

:kill_chrome_profile
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*%~1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
goto :eof
