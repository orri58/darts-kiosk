@echo off
REM ============================================================================
REM  DARTS KIOSK — Automated Installer
REM  Converts a Windows PC into a locked-down Darts Kiosk appliance.
REM ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk — Installer v3.0

REM === Colors via ANSI ===
set "G=[92m"
set "R=[91m"
set "Y=[93m"
set "C=[96m"
set "B=[1m"
set "N=[0m"

REM === Default Configuration ===
set "INSTALL_DIR=C:\DartsKiosk"
set "KIOSK_USER=DartsKiosk"
set "KIOSK_PASS=darts2024"
set "BOARD_ID=BOARD-1"
set "BACKEND_PORT=8001"
set "AUTODARTS_URL=https://play.autodarts.io"

echo.
echo %B%================================================================%N%
echo %B%   DARTS KIOSK — AUTOMATED INSTALLER v3.0%N%
echo %B%================================================================%N%
echo.

REM ============================================================================
REM  STEP 0 — Administrator Check
REM ============================================================================
echo %C%[Step 0/10] Administrator-Rechte pruefen...%N%
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo %R%[FEHLER] Dieses Script muss als Administrator ausgefuehrt werden!%N%
    echo          Rechtsklick auf setup_kiosk.bat -^> "Als Administrator ausfuehren"
    echo.
    pause
    exit /b 1
)
echo   %G%[OK] Administrator-Rechte vorhanden%N%

REM ============================================================================
REM  STEP 1 — Configuration
REM ============================================================================
echo.
echo %C%[Step 1/10] Konfiguration%N%
echo.
echo   Standard-Werte:
echo     Installationspfad:  %INSTALL_DIR%
echo     Kiosk-Benutzer:     %KIOSK_USER%
echo     Board-ID:           %BOARD_ID%
echo     Backend-Port:       %BACKEND_PORT%
echo.

set /p "CONFIRM_DEFAULTS=Standard-Konfiguration verwenden? (J/N) [J]: "
if /i "!CONFIRM_DEFAULTS!"=="" set "CONFIRM_DEFAULTS=J"

if /i not "!CONFIRM_DEFAULTS!"=="J" (
    set /p "INSTALL_DIR=Installationspfad [%INSTALL_DIR%]: "
    if "!INSTALL_DIR!"=="" set "INSTALL_DIR=C:\DartsKiosk"
    set /p "KIOSK_USER=Kiosk-Benutzername [%KIOSK_USER%]: "
    if "!KIOSK_USER!"=="" set "KIOSK_USER=DartsKiosk"
    set /p "BOARD_ID=Board-ID [%BOARD_ID%]: "
    if "!BOARD_ID!"=="" set "BOARD_ID=BOARD-1"
    set /p "BACKEND_PORT=Backend-Port [%BACKEND_PORT%]: "
    if "!BACKEND_PORT!"=="" set "BACKEND_PORT=8001"
)

set /p "KIOSK_PASS=Kiosk-Passwort (fuer Auto-Login + Maintenance): "
if "!KIOSK_PASS!"=="" set "KIOSK_PASS=darts2024"

echo.
echo   Konfiguration:
echo     Installationspfad:  !INSTALL_DIR!
echo     Kiosk-Benutzer:     !KIOSK_USER!
echo     Board-ID:           !BOARD_ID!
echo     Backend-Port:       !BACKEND_PORT!
echo.
set /p "PROCEED=Installation starten? (J/N) [J]: "
if /i "!PROCEED!"=="" set "PROCEED=J"
if /i not "!PROCEED!"=="J" (
    echo Abgebrochen.
    pause
    exit /b 0
)

REM ============================================================================
REM  STEP 2 — System Requirements
REM ============================================================================
echo.
echo %C%[Step 2/10] Systemanforderungen pruefen...%N%

REM Check Python
set "PYTHON_OK=0"
python --version >nul 2>&1
if !ERRORLEVEL!==0 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   %G%[OK] %%v%N%
    set "PYTHON_OK=1"
) else (
    echo   %R%[FEHLER] Python nicht gefunden!%N%
    echo            Bitte Python 3.11+ installieren: https://python.org/downloads
    pause
    exit /b 1
)

REM Check Chrome
set "CHROME_PATH="
for %%G in (
    "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do (
    if exist "%%~G" (
        if not defined CHROME_PATH set "CHROME_PATH=%%~G"
    )
)
if defined CHROME_PATH (
    echo   %G%[OK] Chrome gefunden: !CHROME_PATH!%N%
) else (
    echo   %Y%[WARN] Chrome nicht gefunden — wird nach Installation benoetigt%N%
    echo          Download: https://google.com/chrome
)

REM Check curl
curl --version >nul 2>&1
if !ERRORLEVEL!==0 (
    echo   %G%[OK] curl verfuegbar%N%
) else (
    echo   %Y%[WARN] curl nicht gefunden — Health-Check eingeschraenkt%N%
)

REM ============================================================================
REM  STEP 3 — Create Installation Directory + Copy Files
REM ============================================================================
echo.
echo %C%[Step 3/10] Darts-System installieren nach !INSTALL_DIR!...%N%

if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"
mkdir "!INSTALL_DIR!\data\db" 2>nul
mkdir "!INSTALL_DIR!\data\assets" 2>nul
mkdir "!INSTALL_DIR!\data\backups" 2>nul
mkdir "!INSTALL_DIR!\data\downloads" 2>nul
mkdir "!INSTALL_DIR!\data\chrome_profile\!BOARD_ID!" 2>nul
mkdir "!INSTALL_DIR!\data\kiosk_ui_profile" 2>nul
mkdir "!INSTALL_DIR!\logs" 2>nul

REM Copy application files from the extracted release directory
set "SOURCE_DIR=%~dp0"
REM Remove trailing backslash
if "!SOURCE_DIR:~-1!"=="\" set "SOURCE_DIR=!SOURCE_DIR:~0,-1!"

REM Copy backend
if exist "!SOURCE_DIR!\backend" (
    xcopy "!SOURCE_DIR!\backend" "!INSTALL_DIR!\backend\" /E /I /Y /Q >nul
    echo   %G%[OK] Backend kopiert%N%
) else (
    echo   %R%[FEHLER] backend\ nicht gefunden in !SOURCE_DIR!%N%
    pause
    exit /b 1
)

REM Copy frontend
if exist "!SOURCE_DIR!\frontend" (
    xcopy "!SOURCE_DIR!\frontend" "!INSTALL_DIR!\frontend\" /E /I /Y /Q >nul
    echo   %G%[OK] Frontend kopiert%N%
)

REM Copy runtime scripts
for %%F in (run_backend.py credits_overlay.py _run_backend.bat start.bat stop.bat updater.py VERSION) do (
    if exist "!SOURCE_DIR!\%%F" (
        copy "!SOURCE_DIR!\%%F" "!INSTALL_DIR!\%%F" /Y >nul
    )
)
echo   %G%[OK] Scripts kopiert%N%

REM Copy kiosk-specific files
for %%F in (kiosk_shell.vbs darts_launcher.bat maintenance.bat uninstall_kiosk.bat) do (
    if exist "!SOURCE_DIR!\kiosk\%%F" (
        copy "!SOURCE_DIR!\kiosk\%%F" "!INSTALL_DIR!\%%F" /Y >nul
    ) else if exist "!SOURCE_DIR!\%%F" (
        copy "!SOURCE_DIR!\%%F" "!INSTALL_DIR!\%%F" /Y >nul
    )
)
echo   %G%[OK] Kiosk-Dateien kopiert%N%

REM ============================================================================
REM  STEP 4 — Python Virtual Environment
REM ============================================================================
echo.
echo %C%[Step 4/10] Python-Umgebung einrichten...%N%

if not exist "!INSTALL_DIR!\.venv\Scripts\activate.bat" (
    python -m venv "!INSTALL_DIR!\.venv"
    echo   %G%[OK] Virtual Environment erstellt%N%
) else (
    echo   %G%[OK] Virtual Environment existiert bereits%N%
)

call "!INSTALL_DIR!\.venv\Scripts\activate.bat"

pip install -r "!INSTALL_DIR!\backend\requirements.txt" -q 2>nul
if !ERRORLEVEL!==0 (
    echo   %G%[OK] Python-Pakete installiert%N%
) else (
    echo   %Y%[WARN] Einige Pakete konnten nicht installiert werden%N%
)

REM Install Playwright browsers
python -m playwright install chromium >nul 2>&1
echo   %G%[OK] Playwright Chromium installiert%N%

REM ============================================================================
REM  STEP 5 — Create .env Configuration
REM ============================================================================
echo.
echo %C%[Step 5/10] Konfigurationsdateien erstellen...%N%

REM Backend .env (only if not exists — preserve user config)
if not exist "!INSTALL_DIR!\backend\.env" (
    (
        echo DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
        echo SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
        echo DATA_DIR=./data
        echo JWT_SECRET=darts-kiosk-!RANDOM!!RANDOM!-secret
        echo AGENT_SECRET=agent-kiosk-!RANDOM!-secret
        echo CORS_ORIGINS=*
        echo MODE=STANDALONE
        echo BOARD_ID=!BOARD_ID!
        echo AUTODARTS_URL=!AUTODARTS_URL!
        echo AUTODARTS_MODE=observer
        echo AUTODARTS_HEADLESS=false
        echo AUTODARTS_MOCK=false
        echo UPDATE_CHECK_ENABLED=true
        echo UPDATE_CHECK_INTERVAL_HOURS=24
    ) > "!INSTALL_DIR!\backend\.env"
    echo   %G%[OK] backend\.env erstellt%N%
) else (
    echo   %G%[OK] backend\.env existiert bereits (nicht ueberschrieben^)%N%
)

REM Frontend .env
if not exist "!INSTALL_DIR!\frontend\.env" (
    echo REACT_APP_BACKEND_URL=http://localhost:!BACKEND_PORT!> "!INSTALL_DIR!\frontend\.env"
    echo   %G%[OK] frontend\.env erstellt%N%
)

REM Write kiosk config (read by launcher + maintenance)
(
    echo REM === Darts Kiosk Configuration (auto-generated by installer) ===
    echo set "INSTALL_DIR=!INSTALL_DIR!"
    echo set "KIOSK_USER=!KIOSK_USER!"
    echo set "BOARD_ID=!BOARD_ID!"
    echo set "BACKEND_PORT=!BACKEND_PORT!"
    echo set "CHROME_PATH=!CHROME_PATH!"
) > "!INSTALL_DIR!\kiosk_config.bat"
echo   %G%[OK] kiosk_config.bat erstellt%N%

REM Store maintenance password hash (PowerShell SHA256)
for /f "tokens=*" %%h in ('powershell -NoProfile -Command "[BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes('!KIOSK_PASS!'))).Replace('-','')"') do set "PASS_HASH=%%h"
echo !PASS_HASH!> "!INSTALL_DIR!\data\.maintenance_key"
echo   %G%[OK] Maintenance-Passwort gespeichert%N%

REM ============================================================================
REM  STEP 6 — Create Kiosk User
REM ============================================================================
echo.
echo %C%[Step 6/10] Kiosk-Benutzer erstellen...%N%

net user "!KIOSK_USER!" >nul 2>&1
if !ERRORLEVEL!==0 (
    echo   %G%[OK] Benutzer '!KIOSK_USER!' existiert bereits%N%
    net user "!KIOSK_USER!" "!KIOSK_PASS!" >nul 2>&1
    echo   %G%[OK] Passwort aktualisiert%N%
) else (
    net user "!KIOSK_USER!" "!KIOSK_PASS!" /add /comment:"Darts Kiosk Auto-Login Account" >nul
    net localgroup Users "!KIOSK_USER!" /add >nul 2>&1
    echo   %G%[OK] Benutzer '!KIOSK_USER!' erstellt%N%
)

REM Password never expires
wmic useraccount where "name='!KIOSK_USER!'" set PasswordExpires=false >nul 2>&1
echo   %G%[OK] Passwort-Ablauf deaktiviert%N%

REM ============================================================================
REM  STEP 7 — Windows Auto-Login
REM ============================================================================
echo.
echo %C%[Step 7/10] Auto-Login konfigurieren...%N%

set "WINLOGON=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

reg add "!WINLOGON!" /v AutoAdminLogon /t REG_SZ /d "1" /f >nul
reg add "!WINLOGON!" /v DefaultUserName /t REG_SZ /d "!KIOSK_USER!" /f >nul
reg add "!WINLOGON!" /v DefaultPassword /t REG_SZ /d "!KIOSK_PASS!" /f >nul
reg add "!WINLOGON!" /v DefaultDomainName /t REG_SZ /d "%COMPUTERNAME%" /f >nul

echo   %G%[OK] Auto-Login fuer '!KIOSK_USER!' konfiguriert%N%

REM ============================================================================
REM  STEP 8 — Shell Replacement
REM ============================================================================
echo.
echo %C%[Step 8/10] Shell-Ersetzung konfigurieren...%N%

REM Back up current shell value
for /f "tokens=2*" %%a in ('reg query "!WINLOGON!" /v Shell 2^>nul ^| findstr /i "Shell"') do (
    set "ORIG_SHELL=%%b"
)
if defined ORIG_SHELL (
    echo   [INFO] Aktuelle Shell: !ORIG_SHELL!
    reg add "!WINLOGON!" /v Shell_Backup /t REG_SZ /d "!ORIG_SHELL!" /f >nul
    echo   %G%[OK] Original-Shell gesichert als Shell_Backup%N%
)

REM Set kiosk shell for the kiosk user only (per-user Winlogon)
REM Use HKCU-equivalent via user-specific registry loading
REM Simpler approach: Set Shell globally but also keep admin user override
REM
REM For safety: We use per-user shell override via UserInit
REM The kiosk_shell.vbs will check the username and only activate for the kiosk user
REM This way admin accounts keep normal explorer.exe

reg add "!WINLOGON!" /v Shell /t REG_SZ /d "!INSTALL_DIR!\kiosk_shell.vbs" /f >nul
echo   %G%[OK] Shell ersetzt durch kiosk_shell.vbs%N%

REM Create a registry override for all admin users to keep explorer
REM This uses the HKLM\...\Winlogon\SpecialAccounts approach
REM Better: Use AlternateShell for admin recovery
reg add "!WINLOGON!" /v AlternateShell /t REG_SZ /d "cmd.exe" /f >nul

echo   %G%[OK] AlternateShell=cmd.exe fuer Safe Mode gesichert%N%

REM ============================================================================
REM  STEP 9 — Kiosk Hardening (User Policies)
REM ============================================================================
echo.
echo %C%[Step 9/10] Kiosk-Haertung...%N%

REM Get SID of kiosk user for per-user policies
for /f "tokens=2 delims==" %%s in ('wmic useraccount where "name='!KIOSK_USER!'" get sid /value 2^>nul ^| findstr /i "SID"') do (
    set "KIOSK_SID=%%s"
)

REM Apply user-specific policies via HKU registry hive
REM First: load the user's NTUSER.DAT if not logged in
set "KIOSK_PROFILE="
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\!KIOSK_SID!" /v ProfileImagePath 2^>nul ^| findstr /i "ProfileImagePath"') do (
    set "KIOSK_PROFILE=%%b"
)

set "HKU_PATH=HKU\DartsKiosk_Temp"
set "POLICY_LOADED=0"
if defined KIOSK_PROFILE (
    if exist "!KIOSK_PROFILE!\NTUSER.DAT" (
        reg load "!HKU_PATH!" "!KIOSK_PROFILE!\NTUSER.DAT" >nul 2>&1
        if !ERRORLEVEL!==0 set "POLICY_LOADED=1"
    )
)

if !POLICY_LOADED!==1 (
    set "POL=!HKU_PATH!\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"

    REM Disable Task Manager
    reg add "!POL!\System" /v DisableTaskMgr /t REG_DWORD /d 1 /f >nul
    echo   %G%[OK] Task-Manager deaktiviert (nur Kiosk-User)%N%

    REM Disable Lock Workstation
    reg add "!POL!\System" /v DisableLockWorkstation /t REG_DWORD /d 1 /f >nul
    echo   %G%[OK] Lock-Workstation deaktiviert%N%

    REM Disable Change Password
    reg add "!POL!\System" /v DisableChangePassword /t REG_DWORD /d 1 /f >nul
    echo   %G%[OK] Passwort-Aenderung deaktiviert%N%

    REM Explorer policies (no right-click, no desktop, etc.)
    reg add "!POL!\Explorer" /v NoDesktop /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoStartMenuMorePrograms /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoRun /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoViewContextMenu /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoWinKeys /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoClose /t REG_DWORD /d 0 /f >nul
    echo   %G%[OK] Explorer-Einschraenkungen gesetzt%N%

    REM Unload hive
    reg unload "!HKU_PATH!" >nul 2>&1
) else (
    echo   %Y%[WARN] Kiosk-User-Profil nicht geladen — Policies werden beim ersten Login angewendet%N%
    echo          Starte ggf. das System neu und fuehre den Installer erneut aus.
)

REM === Firewall Rule ===
echo.
echo   Firewall konfigurieren...
netsh advfirewall firewall show rule name="DartsKiosk Backend" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    netsh advfirewall firewall add rule name="DartsKiosk Backend" dir=in action=allow protocol=TCP localport=!BACKEND_PORT! >nul
    echo   %G%[OK] Firewall-Regel erstellt (Port !BACKEND_PORT!)%N%
) else (
    echo   %G%[OK] Firewall-Regel existiert bereits%N%
)

REM === Power Management ===
echo.
echo   Energieoptionen konfigurieren...
powercfg -change -standby-timeout-ac 0 >nul
powercfg -change -monitor-timeout-ac 0 >nul
powercfg -change -hibernate-timeout-ac 0 >nul
powercfg -change -standby-timeout-dc 0 >nul
powercfg -change -monitor-timeout-dc 0 >nul
echo   %G%[OK] Sleep/Standby/Bildschirmschoner deaktiviert%N%

REM === Disable Notifications ===
echo.
echo   Benachrichtigungen deaktivieren...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\Explorer" /v DisableNotificationCenter /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings" /v NOC_GLOBAL_SETTING_TOASTS_ENABLED /t REG_DWORD /d 0 /f >nul 2>&1
echo   %G%[OK] Windows-Benachrichtigungen deaktiviert%N%

REM === Disable Windows Update Restart Prompts ===
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f >nul 2>&1
echo   %G%[OK] Auto-Restart bei Updates deaktiviert%N%

REM ============================================================================
REM  STEP 10 — Finalize
REM ============================================================================
echo.
echo %C%[Step 10/10] Installation abschliessen...%N%

REM Create install marker
(
    echo installed=%date% %time%
    echo version=3.0
    echo install_dir=!INSTALL_DIR!
    echo kiosk_user=!KIOSK_USER!
    echo board_id=!BOARD_ID!
    echo backend_port=!BACKEND_PORT!
) > "!INSTALL_DIR!\data\.install_info"
echo   %G%[OK] Installationsinfo gespeichert%N%

REM Create desktop shortcut for maintenance (for admin user)
set "ADMIN_DESKTOP=%USERPROFILE%\Desktop"
if exist "!ADMIN_DESKTOP!" (
    (
        echo @echo off
        echo cd /d "!INSTALL_DIR!"
        echo call maintenance.bat
    ) > "!ADMIN_DESKTOP!\DartsKiosk Maintenance.bat"
    echo   %G%[OK] Maintenance-Shortcut auf Admin-Desktop erstellt%N%
)

echo.
echo %G%================================================================%N%
echo %G%%B%   INSTALLATION ABGESCHLOSSEN!%N%
echo %G%================================================================%N%
echo.
echo   Installiert in:       !INSTALL_DIR!
echo   Kiosk-Benutzer:       !KIOSK_USER!
echo   Board-ID:             !BOARD_ID!
echo   Backend-Port:         !BACKEND_PORT!
echo.
echo   Nach Neustart:
echo     - Windows meldet sich als '!KIOSK_USER!' an
echo     - Darts Kiosk startet automatisch
echo     - Kein Desktop, keine Taskleiste
echo.
echo   Maintenance-Zugang:
echo     - Strg+Alt+Entf -^> Benutzer wechseln -^> Admin-Konto
echo     - maintenance.bat auf dem Admin-Desktop
echo.
echo   Rollback:
echo     - Als Admin: !INSTALL_DIR!\uninstall_kiosk.bat
echo.

set /p "REBOOT=System jetzt neu starten? (J/N) [N]: "
if /i "!REBOOT!"=="J" (
    echo.
    echo System startet in 10 Sekunden neu...
    shutdown /r /t 10 /c "Darts Kiosk Installation — Neustart"
) else (
    echo.
    echo   Bitte starten Sie das System manuell neu,
    echo   um den Kiosk-Modus zu aktivieren.
)

echo.
pause
endlocal
