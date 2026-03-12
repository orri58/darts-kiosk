' =============================================================================
'  Darts Kiosk - Shell Replacement v3.0.1
'  Replaces explorer.exe as the Windows shell.
'  Kiosk user -> starts darts_launcher.bat (hidden)
'  Any other user -> starts explorer.exe (normal desktop)
' =============================================================================
Option Explicit

Dim WshShell, WshNetwork, currentUser, fso
Dim installDir, configFile, kioskUser, launcherPath

Set WshShell = CreateObject("WScript.Shell")
Set WshNetwork = CreateObject("WScript.Network")
Set fso = CreateObject("Scripting.FileSystemObject")

' Determine install directory (same folder as this script)
installDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Read kiosk user from config
kioskUser = "DartsKiosk"
configFile = installDir & "\kiosk_config.bat"
If fso.FileExists(configFile) Then
    Dim configContent, line
    Set configContent = fso.OpenTextFile(configFile, 1)
    Do While Not configContent.AtEndOfStream
        line = configContent.ReadLine
        If InStr(LCase(line), "kiosk_user") > 0 Then
            Dim eqPos, val
            eqPos = InStr(line, "=")
            If eqPos > 0 Then
                val = Mid(line, eqPos + 1)
                val = Replace(val, """", "")
                val = Trim(val)
                If Len(val) > 0 Then kioskUser = val
            End If
        End If
    Loop
    configContent.Close
End If

' Get current logged-in user
currentUser = WshNetwork.UserName

' Ensure log directory exists
Dim logDir
logDir = installDir & "\logs"
If Not fso.FolderExists(logDir) Then
    On Error Resume Next
    fso.CreateFolder(logDir)
    On Error GoTo 0
End If

' Branch: kiosk user gets the launcher, everyone else gets explorer
If LCase(currentUser) = LCase(kioskUser) Then
    ' === KIOSK MODE ===
    launcherPath = installDir & "\darts_launcher.bat"

    ' Log startup
    Dim logFile, logPath
    logPath = installDir & "\logs\shell.log"
    On Error Resume Next
    Set logFile = fso.OpenTextFile(logPath, 8, True)
    If Not logFile Is Nothing Then
        logFile.WriteLine Now & " [SHELL] Kiosk-Modus gestartet fuer " & currentUser
        logFile.WriteLine Now & " [SHELL] installDir=" & installDir
        logFile.WriteLine Now & " [SHELL] launcherPath=" & launcherPath
        logFile.Close
    End If
    On Error GoTo 0

    If fso.FileExists(launcherPath) Then
        ' Start launcher via cmd.exe hidden (window style 0 = hidden)
        ' cmd /c ensures the batch file runs properly as a child process
        WshShell.Run "cmd.exe /c """ & launcherPath & """", 0, False
    Else
        ' Fallback: if launcher not found, start explorer
        On Error Resume Next
        Set logFile = fso.OpenTextFile(logPath, 8, True)
        If Not logFile Is Nothing Then
            logFile.WriteLine Now & " [SHELL] FEHLER: darts_launcher.bat nicht gefunden!"
            logFile.WriteLine Now & " [SHELL] Fallback: starte explorer.exe"
            logFile.Close
        End If
        On Error GoTo 0
        WshShell.Run "explorer.exe", 1, False
    End If

    ' Keep this process alive - if the shell process exits, Windows logs out
    Do While True
        WScript.Sleep 60000
    Loop
Else
    ' === NORMAL MODE (Admin/other users) ===
    ' Start explorer.exe normally
    WshShell.Run "explorer.exe", 1, False
End If
