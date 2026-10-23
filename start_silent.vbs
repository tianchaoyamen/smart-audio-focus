Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 优先使用 pythonw 启动无窗口后台进程
cmd = "cmd.exe /c cd /d """ & currentDir & """ && pythonw smart_audio_focus.py"
ws.Run cmd, 0, False
