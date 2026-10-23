@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 推送到 GitHub (Smart Audio Focus)

echo ========================================================
echo   Smart Audio Focus - GitHub 远程仓库推送助手
echo ========================================================
echo.

git status >nul 2>&1
if %errorlevel% neq 0 (
    echo 初始化本地 Git 仓库...
    git init
    git branch -M main
)

git add .
git commit -m "feat: initial commit with smart audio focus, auto pause, delay and fade-in" >nul 2>&1

echo.
echo 提示: GitHub 从 2021 年起要求使用 Personal Access Token (PAT) 认证。
echo 如果你已在 GitHub 上创建名为 smart-audio-focus 的仓库:
echo 请输入你的 GitHub 个人访问令牌 (Token) 或直接回车使用现有配置:
set /p USER_TOKEN="GitHub Token (留空则使用默认配置): "

if not "%USER_TOKEN%"=="" (
    git remote remove origin >nul 2>&1
    git remote add origin https://tianchaoyamen:%USER_TOKEN%@github.com/tianchaoyamen/smart-audio-focus.git
)

echo.
echo 正在推送到 GitHub main 分支...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo [成功] 代码已成功推送到 https://github.com/tianchaoyamen/smart-audio-focus !
) else (
    echo.
    echo [提示] 如果推送失败，请确认：
    echo 1. 已在 https://github.com/new 创建了名为 smart-audio-focus 的空仓库
    echo 2. Token 拥有 repo 勾选权限
    echo 3. 本地网络是否已开启代理 (如 Clash 7897 端口)
)

pause
