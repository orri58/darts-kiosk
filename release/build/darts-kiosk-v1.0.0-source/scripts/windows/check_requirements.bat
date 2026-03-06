@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Voraussetzungen pruefen
echo.
echo ================================================================
echo   DARTS KIOSK - Voraussetzungen pruefen
echo ================================================================
echo.

set ERRORS=0

:: Python
echo [1/3] Python pruefen...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] Python nicht gefunden!
    echo          Download: https://www.python.org/downloads/
    echo          WICHTIG: Bei Installation "Add to PATH" ankreuzen!
    set ERRORS=1
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
    echo   [OK]   Python %PYVER%
)

:: pip
pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] pip nicht gefunden, wird mit setup installiert
) else (
    echo   [OK]   pip vorhanden
)

:: Node.js
echo.
echo [2/3] Node.js pruefen...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] Node.js nicht gefunden!
    echo          Download: https://nodejs.org/ (LTS Version)
    set ERRORS=1
) else (
    for /f %%i in ('node --version 2^>^&1') do set NODEVER=%%i
    echo   [OK]   Node.js %NODEVER%
)

:: yarn / npm
echo.
echo [3/3] Paketmanager pruefen...
call yarn --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    npm --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo   [FAIL] Weder yarn noch npm gefunden!
        set ERRORS=1
    ) else (
        echo   [OK]   npm vorhanden (yarn wird bei Setup installiert)
    )
) else (
    echo   [OK]   yarn vorhanden
)

echo.
echo ================================================================
if %ERRORS% NEQ 0 (
    echo   FEHLER: Bitte fehlende Software installieren!
    echo   Danach erneut ausfuehren.
) else (
    echo   ALLES OK - Bereit fuer setup_windows.bat
)
echo ================================================================
echo.
pause
