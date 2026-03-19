' Darts Kiosk Agent — Silent Launcher
' ======================================
' Starts the agent Python script without a visible console window.
' Used by Task Scheduler for invisible autostart.
'
' This VBS wrapper uses WScript.Shell to launch pythonw.exe (or python.exe)
' with the SW_HIDE flag, ensuring no console window appears in kiosk mode.

Dim objShell, objFSO, strAgentDir, strRootDir, strPython, strScript, strLogDir, strCmd

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Resolve paths
strAgentDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strRootDir = objFSO.GetParentFolderName(strAgentDir)
strScript = objFSO.BuildPath(strAgentDir, "darts_agent.py")
strLogDir = objFSO.BuildPath(strRootDir, "data\logs")

' Ensure log directory exists
If Not objFSO.FolderExists(strLogDir) Then
    objFSO.CreateFolder(strLogDir)
End If

' Try pythonw.exe first (no console), fall back to python.exe
strPython = ""

' Check venv first
Dim strVenvPythonW, strVenvPython
strVenvPythonW = objFSO.BuildPath(strRootDir, ".venv\Scripts\pythonw.exe")
strVenvPython = objFSO.BuildPath(strRootDir, ".venv\Scripts\python.exe")

If objFSO.FileExists(strVenvPythonW) Then
    strPython = strVenvPythonW
ElseIf objFSO.FileExists(strVenvPython) Then
    strPython = strVenvPython
Else
    ' Fall back to system Python
    Dim strSysPythonW
    strSysPythonW = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe"
    If objFSO.FileExists(strSysPythonW) Then
        strPython = strSysPythonW
    Else
        strPython = "pythonw.exe"
    End If
End If

' Build command
strCmd = """" & strPython & """ """ & strScript & """ --log-dir """ & strLogDir & """"

' Run hidden (0 = SW_HIDE, False = don't wait)
objShell.Run strCmd, 0, False

Set objShell = Nothing
Set objFSO = Nothing
