@echo off
chcp 65001 >nul
title Smart Audio Focus (控制台模式)
cd /d "%~dp0"

echo 正在检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b
)

echo 正在启动 Smart Audio Focus (按 Ctrl+C 可停止)...
python smart_audio_focus.py
pause
