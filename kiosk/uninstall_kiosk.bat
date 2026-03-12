@echo off
REM ============================================================================
REM  DARTS KIOSK - Uninstaller / Rollback v3.0.2
REM  Reverses all changes made by setup_kiosk.bat.
REM  MUST be run as Administrator.
REM ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk - Uninstaller

echo.
echo ================================================================
echo   DARTS KIOSK - UNINSTALLER
echo ================================================================
echo.

REM === Admin Check ===
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FEHLER] Dieses Script muss als Administrator ausgefuehrt werden!
    pause
    exit /b 1
)

REM === Load Configuration ===
set "INSTALL_DIR=%~dp0"
if "!INSTALL_DIR:~-1!"=="\" set "INSTALL_DIR=!INSTALL_DIR:~0,-1!"

set "KIOSK_USER=DartsKiosk"
if exist "!INSTALL_DIR!\kiosk_config.bat" (
    call "!INSTALL_DIR!\kiosk_config.bat"
)

echo   Installationspfad: !INSTALL_DIR!
echo   Kiosk-Benutzer:    !KIOSK_USER!
echo.

set /p "CONFIRM=Kiosk-Modus wirklich deinstallieren? (J/N): "
if /i not "!CONFIRM!"=="J" (
    echo Abgebrochen.
    pause
    exit /b 0
)

echo.
echo [1/7] Dienste stoppen...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1
taskkill /F /FI "IMAGENAME eq wscript.exe" >nul 2>&1
echo   [OK] Dienste gestoppt

echo.
echo [2/7] Scheduled Task entfernen...
schtasks /delete /tn "DartsKioskLauncher" /f >nul 2>&1
if !ERRORLEVEL!==0 (
    echo   [OK] Scheduled Task 'DartsKioskLauncher' entfernt
) else (
    echo   [OK] Kein Scheduled Task vorhanden
)

echo.
echo [3/7] Shell wiederherstellen...
set "WINLOGON=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

set "BACKUP_SHELL="
for /f "tokens=2*" %%a in ('reg query "!WINLOGON!" /v Shell_Backup 2^>nul ^| findstr /i "Shell_Backup"') do (
    set "BACKUP_SHELL=%%b"
)
if defined BACKUP_SHELL (
    reg add "!WINLOGON!" /v Shell /t REG_SZ /d "!BACKUP_SHELL!" /f >nul
    echo   [OK] Shell wiederhergestellt: !BACKUP_SHELL!
) else (
    reg add "!WINLOGON!" /v Shell /t REG_SZ /d "explorer.exe" /f >nul
    echo   [OK] Shell wiederhergestellt: explorer.exe
)
reg delete "!WINLOGON!" /v Shell_Backup /f >nul 2>&1

echo.
echo [4/7] Auto-Login deaktivieren...
reg add "!WINLOGON!" /v AutoAdminLogon /t REG_SZ /d "0" /f >nul
reg delete "!WINLOGON!" /v DefaultPassword /f >nul 2>&1
echo   [OK] Auto-Login deaktiviert

echo.
echo [5/7] Kiosk-Richtlinien entfernen...
set "KIOSK_SID="
for /f "tokens=2 delims==" %%s in ('wmic useraccount where "name='!KIOSK_USER!'" get sid /value 2^>nul ^| findstr /i "SID"') do (
    set "KIOSK_SID=%%s"
)

if defined KIOSK_SID (
    set "KIOSK_PROFILE="
    for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\!KIOSK_SID!" /v ProfileImagePath 2^>nul ^| findstr /i "ProfileImagePath"') do (
        set "KIOSK_PROFILE=%%b"
    )

    set "HKU_PATH=HKU\DartsKiosk_Temp"
    if defined KIOSK_PROFILE (
        if exist "!KIOSK_PROFILE!\NTUSER.DAT" (
            reg load "!HKU_PATH!" "!KIOSK_PROFILE!\NTUSER.DAT" >nul 2>&1
            if !ERRORLEVEL!==0 (
                set "POL=!HKU_PATH!\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"
                reg delete "!POL!\System" /v DisableTaskMgr /f >nul 2>&1
                reg delete "!POL!\System" /v DisableLockWorkstation /f >nul 2>&1
                reg delete "!POL!\System" /v DisableChangePassword /f >nul 2>&1
                reg delete "!POL!\Explorer" /v NoDesktop /f >nul 2>&1
                reg delete "!POL!\Explorer" /v NoStartMenuMorePrograms /f >nul 2>&1
                reg delete "!POL!\Explorer" /v NoRun /f >nul 2>&1
                reg delete "!POL!\Explorer" /v NoViewContextMenu /f >nul 2>&1
                reg delete "!POL!\Explorer" /v NoWinKeys /f >nul 2>&1
                reg unload "!HKU_PATH!" >nul 2>&1
                echo   [OK] Kiosk-Richtlinien entfernt
            )
        )
    )
) else (
    echo   [WARN] Kiosk-User SID nicht gefunden
)

REM Remove global policies
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\Explorer" /v DisableNotificationCenter /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings" /v NOC_GLOBAL_SETTING_TOASTS_ENABLED /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /f >nul 2>&1
echo   [OK] Globale Richtlinien entfernt

echo.
echo [6/7] Firewall-Regel entfernen...
netsh advfirewall firewall delete rule name="DartsKiosk Backend" >nul 2>&1
echo   [OK] Firewall-Regel entfernt

echo.
echo [7/7] Kiosk-Benutzer...
set /p "DEL_USER=Kiosk-Benutzer '!KIOSK_USER!' loeschen? (J/N) [N]: "
if /i "!DEL_USER!"=="J" (
    net user "!KIOSK_USER!" /delete >nul 2>&1
    echo   [OK] Benutzer '!KIOSK_USER!' geloescht
) else (
    echo   [OK] Benutzer '!KIOSK_USER!' beibehalten
)

echo.
echo ================================================================
echo   DEINSTALLATION ABGESCHLOSSEN
echo ================================================================
echo.
echo   Shell:          explorer.exe wiederhergestellt
echo   Auto-Login:     deaktiviert
echo   Scheduled Task: entfernt
echo   Richtlinien:    entfernt
echo   Firewall:       Regel entfernt
echo.
echo   HINWEIS: Dateien in !INSTALL_DIR! bleiben erhalten.
echo.

set /p "REBOOT=System jetzt neu starten? (J/N) [N]: "
if /i "!REBOOT!"=="J" (
    shutdown /r /t 10 /c "Darts Kiosk Deinstallation - Neustart"
)

echo.
start explorer.exe
echo   [OK] Explorer gestartet fuer aktuelle Sitzung
echo.
pause
endlocal
