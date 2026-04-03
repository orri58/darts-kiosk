@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Voraussetzungen pruefen
cd /d "%~dp0"
echo.
echo ================================================================
echo   DARTS KIOSK - Voraussetzungen pruefen
echo ================================================================
echo.

set HAVE_ERRORS=0
set HAVE_WARNS=0

REM === 1. Python ===
echo [1/4] Python pruefen...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] Python nicht gefunden!
    echo          Download: https://www.python.org/downloads/
    echo          WICHTIG: Bei Installation "Add to PATH" ankreuzen!
    set HAVE_ERRORS=1
    goto check_pip
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   [OK]   Python %PYVER%

:check_pip
pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] pip nicht gefunden, wird mit setup installiert
) else (
    echo   [OK]   pip vorhanden
)

REM === 2. Node.js ===
echo.
echo [2/4] Node.js pruefen...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] Node.js nicht gefunden!
    echo          Download: https://nodejs.org/
    echo          WICHTIG: Node 20 oder 22 LTS installieren
    set HAVE_ERRORS=1
    goto check_npm
)
for /f %%i in ('node --version 2^>^&1') do set NODEVER=%%i
echo   [OK]   Node.js %NODEVER%
echo          Empfohlen: Node 20 oder 22 LTS.
echo          Bitte keine odd/ehemaligen preview Builds fuer den Kiosk-Pfad verwenden.

:check_npm
REM === 3. Paketmanager ===
echo.
echo [3/4] Paketmanager pruefen...
npm --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK]   npm vorhanden
    goto check_vcpp
)
echo   [FAIL] npm nicht gefunden!
set HAVE_ERRORS=1

:check_vcpp
REM === 4. VC++ Redistributable ===
echo.
echo [4/4] Microsoft Visual C++ Redistributable pruefen...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK]   VC++ Redistributable x64 vorhanden
) else (
    echo   [WARN] VC++ Redistributable x64 moeglicherweise nicht installiert!
    echo          Wird fuer greenlet/SQLAlchemy benoetigt.
    echo          Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
    set HAVE_WARNS=1
)

REM === Summary ===
echo.
echo ================================================================
if %HAVE_ERRORS% NEQ 0 (
    echo   FEHLER gefunden! Bitte fehlende Software installieren.
)
if %HAVE_WARNS% NEQ 0 (
    echo   WARNUNGEN vorhanden - bei Problemen bitte oben pruefen.
)
if %HAVE_ERRORS% EQU 0 if %HAVE_WARNS% EQU 0 (
    echo   ALLES OK - Bereit fuer setup_windows.bat
)
echo.
echo   Empfohlene Versionen:
echo     Python:  3.11 oder 3.12  (python.org)
echo     Node.js: 20 oder 22 LTS  (nodejs.org - LTS waehlen!)
echo     VC++:    x64 Redistributable
echo ================================================================
echo.
pause
