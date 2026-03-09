@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Update
cd /d "%~dp0"
echo.
echo ================================================================
echo   DARTS KIOSK - Update installieren
echo ================================================================
echo.

REM Check for manifest
if not exist "data\update_manifest.json" (
    echo [FEHLER] Kein Update vorbereitet!
    echo          Bitte zuerst im Admin-Panel unter System ^> Updates
    echo          ein Update herunterladen und vorbereiten.
    echo.
    pause
    exit /b 1
)

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Python .venv aktiviert
)

echo.
echo ACHTUNG: Das Update wird jetzt installiert.
echo Alle Dienste werden gestoppt und neu gestartet.
echo.
echo Druecke eine beliebige Taste zum Starten...
pause >nul

echo.
echo Starte Updater...
python updater.py "data\update_manifest.json"

echo.
pause
