' =============================================================================
'  Darts Kiosk - Shell Readiness Gate v3.0.2
'  Replaces explorer.exe as the Windows shell.
'
'  ARCHITECTURE:
'  - Scheduled Task "DartsKioskLauncher" is the PRIMARY startup mechanism
'    (starts backend + chrome with elevation, created by installer)
'  - This VBS shell is the SAFETY NET:
'    1. Logs boot start
'    2. Triggers scheduled task if not already running
'    3. Waits for Chrome to appear (max 90s)
'    4. If Chrome appears -> stays alive silently
'    5. If Chrome does NOT appear -> shows fallback recovery
'  - Non-kiosk users get normal explorer.exe
'  - NEVER leaves a permanent black screen
' =============================================================================
Option Explicit

Dim WshShell, WshNetwork, fso
Dim installDir, configFile, kioskUser, currentUser
Dim bootLog, logPath

Set WshShell = CreateObject("WScript.Shell")
Set WshNetwork = CreateObject("WScript.Network")
Set fso = CreateObject("Scripting.FileSystemObject")

installDir = fso.GetParentFolderName(WScript.ScriptFullName)
currentUser = WshNetwork.UserName

' --- Read kiosk user from config ---
kioskUser = "DartsKiosk"
configFile = installDir & "\kiosk_config.bat"
If fso.FileExists(configFile) Then
    Dim cfgFile, cfgLine
    Set cfgFile = fso.OpenTextFile(configFile, 1)
    Do While Not cfgFile.AtEndOfStream
        cfgLine = cfgFile.ReadLine
        If InStr(LCase(cfgLine), "kiosk_user") > 0 Then
            Dim ep, v
            ep = InStr(cfgLine, "=")
            If ep > 0 Then
                v = Mid(cfgLine, ep + 1)
                v = Replace(v, """", "")
                v = Trim(v)
                If Len(v) > 0 Then kioskUser = v
            End If
        End If
    Loop
    cfgFile.Close
End If

' --- Non-kiosk users get normal explorer ---
If LCase(currentUser) <> LCase(kioskUser) Then
    WshShell.Run "explorer.exe", 1, False
    WScript.Quit
End If

' =============================================================================
'  KIOSK MODE - Readiness Gate
' =============================================================================

' Ensure log directory exists
Dim logDir
logDir = installDir & "\logs"
If Not fso.FolderExists(logDir) Then
    On Error Resume Next
    fso.CreateFolder logDir
    On Error GoTo 0
End If

' --- Boot logging helper ---
logPath = installDir & "\logs\kiosk_boot.log"

Sub WriteBootLog(msg)
    On Error Resume Next
    Dim lf
    Set lf = fso.OpenTextFile(logPath, 8, True)
    If Not lf Is Nothing Then
        lf.WriteLine Now & " " & msg
        lf.Close
    End If
    On Error GoTo 0
End Sub

' --- Check if a process is running ---
Function IsProcessRunning(procName)
    Dim objWMI, colProcs
    On Error Resume Next
    Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
    Set colProcs = objWMI.ExecQuery("SELECT Name FROM Win32_Process WHERE Name = '" & procName & "'")
    If Err.Number = 0 Then
        IsProcessRunning = (colProcs.Count > 0)
    Else
        IsProcessRunning = False
    End If
    On Error GoTo 0
End Function

' --- Check backend health via PowerShell (returns True/False) ---
Function IsBackendHealthy(port)
    Dim exitCode
    On Error Resume Next
    exitCode = WshShell.Run("powershell -NoProfile -WindowStyle Hidden -Command ""try { $r = Invoke-WebRequest -Uri http://127.0.0.1:" & port & "/api/health -TimeoutSec 3 -UseBasicParsing; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }""", 0, True)
    If Err.Number = 0 Then
        IsBackendHealthy = (exitCode = 0)
    Else
        IsBackendHealthy = False
    End If
    On Error GoTo 0
End Function

' --- Read backend port from config ---
Dim backendPort
backendPort = "8001"
If fso.FileExists(configFile) Then
    Dim cfgFile2, cfgLine2
    Set cfgFile2 = fso.OpenTextFile(configFile, 1)
    Do While Not cfgFile2.AtEndOfStream
        cfgLine2 = cfgFile2.ReadLine
        If InStr(LCase(cfgLine2), "backend_port") > 0 Then
            Dim ep2, v2
            ep2 = InStr(cfgLine2, "=")
            If ep2 > 0 Then
                v2 = Mid(cfgLine2, ep2 + 1)
                v2 = Replace(v2, """", "")
                v2 = Trim(v2)
                If Len(v2) > 0 Then backendPort = v2
            End If
        End If
    Loop
    cfgFile2.Close
End If

' =============================================================================
'  BOOT SEQUENCE
' =============================================================================

WriteBootLog "[BOOT] ========================================"
WriteBootLog "[BOOT] shell start user=" & currentUser
WriteBootLog "[BOOT] installDir=" & installDir
WriteBootLog "[BOOT] backendPort=" & backendPort

' --- Step 1: Trigger scheduled task (primary launcher) ---
WriteBootLog "[BOOT] triggering scheduled task DartsKioskLauncher"
WshShell.Run "schtasks /run /tn ""DartsKioskLauncher""", 0, False
WScript.Sleep 2000

' --- Step 2: Also start launcher directly as fallback ---
' (In case scheduled task was not created or fails)
Dim launcherPath
launcherPath = installDir & "\darts_launcher.bat"
If Not IsProcessRunning("python.exe") Then
    WriteBootLog "[BOOT] no python.exe found - starting launcher directly as fallback"
    If fso.FileExists(launcherPath) Then
        WshShell.Run "cmd.exe /c """ & launcherPath & """", 0, False
    End If
End If

' --- Step 3: Wait for backend health (max 90s) ---
WriteBootLog "[BOOT] waiting for backend health http://127.0.0.1:" & backendPort & "/api/health"

Dim backendReady, waitCount, maxWait
backendReady = False
waitCount = 0
maxWait = 30  ' 30 x 3s = 90 seconds

Do While waitCount < maxWait And Not backendReady
    WScript.Sleep 3000
    waitCount = waitCount + 1
    backendReady = IsBackendHealthy(backendPort)
    If waitCount Mod 10 = 0 Then
        WriteBootLog "[BOOT] still waiting... attempt " & waitCount & "/" & maxWait
    End If
Loop

If backendReady Then
    WriteBootLog "[BOOT] backend ready after " & (waitCount * 3) & "s"
Else
    WriteBootLog "[BOOT] WARNING: backend NOT ready after 90s"
End If

' --- Step 4: Wait for Chrome to appear (max 30s after backend) ---
WriteBootLog "[BOOT] waiting for chrome.exe"

Dim chromeReady, chromeWait
chromeReady = False
chromeWait = 0

Do While chromeWait < 10 And Not chromeReady
    WScript.Sleep 3000
    chromeWait = chromeWait + 1
    chromeReady = IsProcessRunning("chrome.exe")
Loop

If chromeReady Then
    WriteBootLog "[BOOT] chrome.exe detected - kiosk UI running"
    WriteBootLog "[BOOT] KIOSK READY"
Else
    WriteBootLog "[BOOT] chrome.exe NOT detected after 30s"

    ' --- Step 5: FALLBACK - Show recovery window ---
    If backendReady Then
        WriteBootLog "[BOOT] fallback: backend OK but no Chrome - attempting Chrome start"
        ' Try to start Chrome directly
        Dim chromePath, boardId
        chromePath = ""
        boardId = "BOARD-1"

        ' Read Chrome path and board ID from config
        If fso.FileExists(configFile) Then
            Dim cfgFile3, cfgLine3
            Set cfgFile3 = fso.OpenTextFile(configFile, 1)
            Do While Not cfgFile3.AtEndOfStream
                cfgLine3 = cfgFile3.ReadLine
                If InStr(LCase(cfgLine3), "chrome_path") > 0 Then
                    Dim ep3, v3
                    ep3 = InStr(cfgLine3, "=")
                    If ep3 > 0 Then
                        v3 = Mid(cfgLine3, ep3 + 1)
                        v3 = Replace(v3, """", "")
                        v3 = Trim(v3)
                        If Len(v3) > 0 Then chromePath = v3
                    End If
                End If
                If InStr(LCase(cfgLine3), "board_id") > 0 Then
                    Dim ep4, v4
                    ep4 = InStr(cfgLine3, "=")
                    If ep4 > 0 Then
                        v4 = Mid(cfgLine3, ep4 + 1)
                        v4 = Replace(v4, """", "")
                        v4 = Trim(v4)
                        If Len(v4) > 0 Then boardId = v4
                    End If
                End If
            Loop
            cfgFile3.Close
        End If

        If Len(chromePath) > 0 And fso.FileExists(chromePath) Then
            Dim kioskUrl
            kioskUrl = "http://127.0.0.1:" & backendPort & "/kiosk/" & boardId
            WshShell.Run """" & chromePath & """ --kiosk --user-data-dir=""" & installDir & "\data\kiosk_ui_profile"" --no-first-run --disable-infobars --disable-session-crashed-bubble """ & kioskUrl & """", 1, False
            WriteBootLog "[BOOT] fallback: Chrome started directly"
        Else
            WriteBootLog "[BOOT] fallback: Chrome path not found - opening recovery"
            GoTo FallbackRecovery
        End If
    Else
        GoTo FallbackRecovery
    End If
End If

' --- Stay alive (shell must not exit) ---
WriteBootLog "[BOOT] entering keep-alive loop"
Do While True
    WScript.Sleep 60000
Loop

' Never reached normally - only via GoTo
WScript.Quit

FallbackRecovery:
    ' =============================================================================
    '  FALLBACK RECOVERY - Visible window so user is not stuck on black screen
    ' =============================================================================
    WriteBootLog "[BOOT] FALLBACK INVOKED reason=startup_failed"

    Dim maintenancePath
    maintenancePath = installDir & "\maintenance.bat"

    If fso.FileExists(maintenancePath) Then
        WriteBootLog "[BOOT] opening maintenance.bat"
        WshShell.Run "cmd.exe /c """ & maintenancePath & """", 1, False
    Else
        ' Last resort: open a visible cmd window
        WriteBootLog "[BOOT] opening recovery cmd window"
        WshShell.Run "cmd.exe /k ""echo. & echo ======================================== & echo   Darts Kiosk konnte nicht gestartet werden & echo ======================================== & echo. & echo   Backend: nicht erreichbar & echo   Chrome:  nicht gestartet & echo. & echo   Optionen: & echo     1. 'exit' eingeben und neu starten & echo     2. 'explorer' eingeben fuer Desktop & echo     3. 'cd /d " & installDir & " ^&^& darts_launcher.bat' zum manuellen Start & echo.""", 1, False
    End If

    ' Stay alive even in fallback
    Do While True
        WScript.Sleep 60000
    Loop
