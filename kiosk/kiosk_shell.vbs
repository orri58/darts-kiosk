' =============================================================================
'  Darts Kiosk — Shell Replacement
'  This script replaces explorer.exe as the Windows shell.
'  It checks the current user: if it's the kiosk user, it starts the kiosk
'  launcher. If it's any other user, it starts explorer.exe normally.
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
    Dim configContent, lines, line
    Set configContent = fso.OpenTextFile(configFile, 1)
    Do While Not configContent.AtEndOfStream
        line = configContent.ReadLine
        If InStr(LCase(line), "kiosk_user") > 0 Then
            ' Parse: set "KIOSK_USER=DartsKiosk"
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

' Branch: kiosk user gets the launcher, everyone else gets explorer
If LCase(currentUser) = LCase(kioskUser) Then
    ' === KIOSK MODE ===
    ' Start the darts launcher (hidden cmd window)
    launcherPath = installDir & "\darts_launcher.bat"

    If fso.FileExists(launcherPath) Then
        ' Log startup
        Dim logFile, logPath
        logPath = installDir & "\logs\shell.log"
        On Error Resume Next
        Set logFile = fso.OpenTextFile(logPath, 8, True)
        If Not logFile Is Nothing Then
            logFile.WriteLine Now & " [SHELL] Kiosk-Modus gestartet fuer " & currentUser
            logFile.Close
        End If
        On Error GoTo 0

        ' Start launcher hidden (window style 0 = hidden)
        WshShell.Run """" & launcherPath & """", 0, False
    Else
        ' Fallback: if launcher not found, start explorer
        WshShell.Run "explorer.exe", 1, False
    End If

    ' Keep this process alive — if the shell process exits, Windows logs out
    Do While True
        WScript.Sleep 60000
    Loop
Else
    ' === NORMAL MODE (Admin/other users) ===
    ' Start explorer.exe normally
    WshShell.Run "explorer.exe", 1, False
End If
