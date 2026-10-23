Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
ws.CurrentDirectory = currentDir

appData = ws.ExpandEnvironmentStrings("%LOCALAPPDATA%")
pyw = appData & "\Programs\Python\Python312\pythonw.exe"
If Not fso.FileExists(pyw) Then
    pyw = "pythonw.exe"
End If

scriptPath = currentDir & "\smart_audio_focus.py"
cmd = Chr(34) & pyw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34)
ws.Run cmd, 0, False