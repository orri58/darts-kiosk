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
taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1

echo.
echo ================================================================
echo   Alle Dienste beendet.
echo ================================================================
echo.
pause
