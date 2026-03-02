@echo off
chcp 65001 >nul
echo ========================================
echo   AnGIneer 一键启动脚本
echo ========================================
echo.

echo [1/3] 检查 Node.js...

rem 尝试直接使用 node 命令
node --version >nul 2>&1
if errorlevel 1 (
    rem 尝试常见的 Node.js 安装路径
    if exist "C:\Program Files\nodejs\node.exe" (
        set "PATH=C:\Program Files\nodejs;%PATH%"
        node --version >nul 2>&1
    ) else if exist "C:\Program Files (x86)\nodejs\node.exe" (
        set "PATH=C:\Program Files (x86)\nodejs;%PATH%"
        node --version >nul 2>&1
    ) else if exist "%LOCALAPPDATA%\nvs\current\node.exe" (
        set "PATH=%LOCALAPPDATA%\nvs\current;%PATH%"
        node --version >nul 2>&1
    )
)

node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Node.js，请先安装 Node.js >= 18.12.0
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VER=%%i
echo        Node.js 已安装: %NODE_VER%

echo.
echo [2/3] 检查 pnpm...
pnpm --version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未安装 pnpm，正在安装...
    npm install -g pnpm
)
echo        pnpm 已安装

echo.
echo [3/3] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未安装 Python，后端服务可能无法启动
) else (
    echo        Python 已安装
)

echo.
echo ========================================
echo   开始安装前端依赖...
echo ========================================
echo.

pnpm install

echo.
echo ========================================
echo   安装 Python 依赖...
echo ========================================
echo.

pip install -e services/angineer-core/src -e services/sop-core/src -e services/docs-core/src -e services/geo-core/src -e services/engtools/src

echo.
echo ========================================
echo   启动开发服务器...
echo ========================================
echo.
echo 前端地址: http://localhost:3000
echo 后端地址: http://localhost:8000
echo.
echo 按 Ctrl+C 停止服务
echo.

start "AnGIneer Backend" cmd /k "cd /d %~dp0 && python apps/api-server/main.py"
pnpm dev:frontend

pause
