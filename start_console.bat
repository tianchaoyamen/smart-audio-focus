@echo off
title Smart Audio Focus (Console Mode)
cd /d "%~dp0"

set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

echo Checking Python environment...
python.exe --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b
)

echo Starting Smart Audio Focus (Press Ctrl+C to stop)...
python.exe smart_audio_focus.py
pause