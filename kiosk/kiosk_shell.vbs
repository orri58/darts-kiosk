' =============================================================================
'  Darts Kiosk - Shell v3.0.3
'  Minimal, bulletproof VBScript. No GoTo, no Sub mid-flow, ASCII only.
'  Kiosk user -> starts darts_launcher.bat
'  Other users -> starts explorer.exe
' =============================================================================
Option Explicit

Dim wsh, fso, net
Dim installDir, configPath, launcherPath, logDir, logPath
Dim currentUser, kioskUser, debugMode
Dim cfgFile, cfgLine, eqPos, cfgVal
Dim launcherCmd, launcherExists, logFile

Set wsh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set net = CreateObject("WScript.Network")

' --- Determine paths ---
installDir = fso.GetParentFolderName(WScript.ScriptFullName)
configPath = installDir & "\kiosk_config.bat"
launcherPath = installDir & "\darts_launcher.bat"
logDir = installDir & "\logs"
logPath = logDir & "\kiosk_shell.log"

' --- Defaults ---
kioskUser = "DartsKiosk"
debugMode = False
currentUser = net.UserName

' --- Read config (kiosk user name + debug flag) ---
If fso.FileExists(configPath) Then
    Set cfgFile = fso.OpenTextFile(configPath, 1, False)
    Do While Not cfgFile.AtEndOfStream
        cfgLine = cfgFile.ReadLine
        eqPos = InStr(cfgLine, "=")
        If eqPos > 0 Then
            cfgVal = Mid(cfgLine, eqPos + 1)
            cfgVal = Replace(cfgVal, """", "")
            cfgVal = Trim(cfgVal)
            If InStr(LCase(cfgLine), "kiosk_user") > 0 And Len(cfgVal) > 0 Then
                kioskUser = cfgVal
            End If
            If InStr(LCase(cfgLine), "kiosk_debug") > 0 Then
                If cfgVal = "1" Then debugMode = True
            End If
        End If
    Loop
    cfgFile.Close
End If

' --- Ensure log directory ---
If Not fso.FolderExists(logDir) Then
    On Error Resume Next
    fso.CreateFolder logDir
    On Error GoTo 0
End If

' --- Log helper: append line to log file ---
' (Inline, no Sub definition to avoid scope issues)

' --- NON-KIOSK USER: start explorer normally ---
If LCase(currentUser) <> LCase(kioskUser) Then
    On Error Resume Next
    Set logFile = fso.OpenTextFile(logPath, 8, True)
    If Not logFile Is Nothing Then
        logFile.WriteLine Now & " [KIOSK_SHELL] non-kiosk user=" & currentUser & " -> explorer.exe"
        logFile.Close
    End If
    On Error GoTo 0
    wsh.Run "explorer.exe", 1, False
    WScript.Quit
End If

' =============================================================================
'  KIOSK USER BOOT SEQUENCE
' =============================================================================

' --- Log: shell start ---
On Error Resume Next
Set logFile = fso.OpenTextFile(logPath, 8, True)
If Not logFile Is Nothing Then
    logFile.WriteLine Now & " [KIOSK_SHELL] ========================================"
    logFile.WriteLine Now & " [KIOSK_SHELL] start user=" & currentUser
    logFile.WriteLine Now & " [KIOSK_SHELL] installDir=" & installDir
    logFile.WriteLine Now & " [KIOSK_SHELL] launcher=" & launcherPath
    logFile.WriteLine Now & " [KIOSK_SHELL] debug=" & debugMode
    logFile.Close
End If
On Error GoTo 0

' --- Check launcher exists ---
launcherExists = fso.FileExists(launcherPath)

If Not launcherExists Then
    ' FAILSAFE: launcher missing -> start explorer, never black screen
    On Error Resume Next
    Set logFile = fso.OpenTextFile(logPath, 8, True)
    If Not logFile Is Nothing Then
        logFile.WriteLine Now & " [KIOSK_SHELL] FEHLER: launcher nicht gefunden!"
        logFile.WriteLine Now & " [KIOSK_SHELL] fallback_to_explorer reason=launcher_missing"
        logFile.Close
    End If
    On Error GoTo 0
    wsh.Run "explorer.exe", 1, False
    WScript.Quit
End If

' --- Trigger scheduled task (primary startup mechanism) ---
On Error Resume Next
Set logFile = fso.OpenTextFile(logPath, 8, True)
If Not logFile Is Nothing Then
    logFile.WriteLine Now & " [KIOSK_SHELL] triggering scheduled task DartsKioskLauncher"
    logFile.Close
End If
On Error GoTo 0
wsh.Run "schtasks /run /tn ""DartsKioskLauncher""", 0, False

' --- Wait 3 seconds for task to start ---
WScript.Sleep 3000

' --- Also start launcher directly as fallback ---
' Build command: cmd.exe /c "C:\DartsKiosk\darts_launcher.bat"
' Debug mode: cmd.exe /k (visible window, stays open)
If debugMode Then
    launcherCmd = "cmd.exe /k """ & launcherPath & """"
Else
    launcherCmd = "cmd.exe /c """ & launcherPath & """"
End If

On Error Resume Next
Set logFile = fso.OpenTextFile(logPath, 8, True)
If Not logFile Is Nothing Then
    logFile.WriteLine Now & " [KIOSK_SHELL] launching " & launcherCmd
    logFile.Close
End If
On Error GoTo 0

' Start launcher (hidden=0, or visible=1 for debug)
If debugMode Then
    wsh.Run launcherCmd, 1, False
Else
    wsh.Run launcherCmd, 0, False
End If

' --- Wait for Chrome to appear (max 120 seconds) ---
Dim chromeFound, waitSec, objWMI, colProcs
chromeFound = False
waitSec = 0

On Error Resume Next
Set logFile = fso.OpenTextFile(logPath, 8, True)
If Not logFile Is Nothing Then
    logFile.WriteLine Now & " [KIOSK_SHELL] waiting for chrome.exe (max 120s)"
    logFile.Close
End If
On Error GoTo 0

Do While waitSec < 120 And Not chromeFound
    WScript.Sleep 5000
    waitSec = waitSec + 5

    ' Check if chrome.exe is running via WMI
    On Error Resume Next
    Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
    Set colProcs = objWMI.ExecQuery("SELECT Name FROM Win32_Process WHERE Name = 'chrome.exe'")
    If Err.Number = 0 Then
        If colProcs.Count > 0 Then chromeFound = True
    End If
    On Error GoTo 0
Loop

On Error Resume Next
Set logFile = fso.OpenTextFile(logPath, 8, True)
If Not logFile Is Nothing Then
    If chromeFound Then
        logFile.WriteLine Now & " [KIOSK_SHELL] chrome.exe detected after " & waitSec & "s - KIOSK READY"
    Else
        logFile.WriteLine Now & " [KIOSK_SHELL] chrome.exe NOT found after 120s"
        logFile.WriteLine Now & " [KIOSK_SHELL] opening maintenance fallback"
    End If
    logFile.Close
End If
On Error GoTo 0

' --- Fallback if Chrome not found ---
If Not chromeFound Then
    Dim maintPath
    maintPath = installDir & "\maintenance.bat"
    If fso.FileExists(maintPath) Then
        wsh.Run "cmd.exe /c """ & maintPath & """", 1, False
    Else
        wsh.Run "cmd.exe /k ""echo Darts Kiosk konnte nicht gestartet werden. && echo. && echo Optionen: && echo   explorer   = Desktop starten && echo   exit       = Fenster schliessen""", 1, False
    End If
End If

' --- Keep shell process alive (exit = Windows logout) ---
Do While True
    WScript.Sleep 60000
Loop
