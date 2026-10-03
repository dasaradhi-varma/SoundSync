' SoundSync Multi-Out - Silent Desktop Application Launcher
' Launches SoundSync as a native desktop window without showing a black command prompt window.

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strAppDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strAppDir

' Use pythonw.exe to suppress console window, fallback to python.exe
strCmd = "pythonw.exe run.py"

On Error Resume Next
objShell.Run strCmd, 0, False
If Err.Number <> 0 Then
    objShell.Run "python.exe run.py", 1, False
End If
