@echo off
chcp 65001 >nul 2>&1
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
for /f "tokens=2" %%a in ('wmic process where "CommandLine like '%%kiosk_chrome_profile%%'" get ProcessId 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%a >nul 2>&1
)
taskkill /F /FI "WINDOWTITLE eq Darts Kiosk*" >nul 2>&1

REM Also kill any autodarts observer Chrome instances
for /f "tokens=2" %%a in ('wmic process where "CommandLine like '%%autodarts_chrome_profile%%'" get ProcessId 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ================================================================
echo   Alle Dienste beendet.
echo ================================================================
echo.
pause
