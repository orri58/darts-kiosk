@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Stoppen
cd /d %~dp0
echo.
echo ================================================================
echo   DARTS KIOSK - Alle Dienste beenden
echo ================================================================
echo.

echo [1/2] Backend beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK]

echo [2/2] Frontend beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK]

echo.
echo ================================================================
echo   Alle Dienste beendet.
echo ================================================================
echo.
pause
