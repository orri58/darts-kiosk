@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "PROJECT=%ROOT%"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "ENV_FILE=%PROJECT%backend\.env"
set "BOARD_ID=BOARD-1"
set "AUTODARTS_URL=https://play.autodarts.io"

if not exist "%PYTHON%" (
  echo [ERROR] Python venv not found: "%PYTHON%"
  echo Run install.bat or setup_windows.bat first.
  exit /b 1
)

if exist "%ENV_FILE%" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /C:"^BOARD_ID=" /C:"^AUTODARTS_URL=" "%ENV_FILE%"`) do (
    if /I "%%A"=="BOARD_ID" set "BOARD_ID=%%B"
    if /I "%%A"=="AUTODARTS_URL" set "AUTODARTS_URL=%%B"
  )
)

set "PROFILE_DIR=%PROJECT%data\chrome_profile\%BOARD_ID%"
set "OUTPUT_DIR=%PROJECT%data\autodarts_capture"
set "SCRIPT=%PROJECT%scripts\autodarts_capture.py"

if not exist "%SCRIPT%" (
  echo [ERROR] Capture script not found: "%SCRIPT%"
  exit /b 1
)

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%" >nul 2>&1
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%" >nul 2>&1

echo.
echo ==============================================
echo   Darts Kiosk - Autodarts Capture Harness
echo ==============================================
echo Board ID:      %BOARD_ID%
echo URL:           %AUTODARTS_URL%
echo Profile dir:   %PROFILE_DIR%
echo Output root:   %OUTPUT_DIR%
echo.
echo Stop with Ctrl+C when you have enough data.
echo Tip: Stop the kiosk first if Chrome says the profile is already in use.
echo.

"%PYTHON%" "%SCRIPT%" --board-id "%BOARD_ID%" --url "%AUTODARTS_URL%" --profile-dir "%PROFILE_DIR%" --output-dir "%OUTPUT_DIR%" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
echo Capture finished with exit code %EXITCODE%.
echo Output folder: %OUTPUT_DIR%
exit /b %EXITCODE%
