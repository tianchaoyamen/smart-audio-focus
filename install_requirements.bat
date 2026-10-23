@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在安装 Smart Audio Focus 依赖项...
python -m pip install -r requirements.txt
if %errorlevel% equ 0 (
    echo [成功] 所有依赖已成功安装！
) else (
    echo [失败] 依赖安装出错，请检查网络或代理设置。
)
pause
