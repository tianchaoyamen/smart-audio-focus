@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在停止 Smart Audio Focus 后台进程...
wmic process where "commandline like '%%smart_audio_focus.py%%' and not commandline like '%%wmic%%'" call terminate >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Smart Audio Focus*" >nul 2>&1
echo 停止完成。
timeout /t 2 >nul
