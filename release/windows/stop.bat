@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Stoppen
cd /d %~dp0
echo.
echo ================================================================
echo   DARTS KIOSK - Alle Dienste beenden
echo ================================================================
echo.

echo [1/4] Backend beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK]

echo [2/4] Frontend beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK]

echo [3/4] Credits-Overlay beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
REM Kill pythonw overlay processes
for /f "tokens=2" %%a in ('wmic process where "CommandLine like '%%credits_overlay%%'" get ProcessId 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK]

echo [4/4] Kiosk-Chrome beenden...
for /f "tokens=2" %%a in ('wmic process where "CommandLine like '%%kiosk_chrome_profile%%'" get ProcessId 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK]

echo.
echo ================================================================
echo   Alle Dienste beendet.
echo ================================================================
echo.
pause
