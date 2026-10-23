@echo off
title Stop Smart Audio Focus
cd /d "%~dp0"
echo Stopping Smart Audio Focus background processes...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*smart_audio_focus.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('[Stopped] PID: ' + $_.ProcessId) }"
echo Done.
ping 127.0.0.1 -n 2 >nul