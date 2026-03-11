# AnGIneer Startup Script (Simplified)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   AnGIneer Simplified Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 检查基础环境
Write-Host "[1/3] 检查 Node.js & Python..." -ForegroundColor Yellow
$nodeVer = node --version 2>$null
if (-not $nodeVer) { Write-Error "Node.js not found!"; exit 1 }
$pythonVer = python --version 2>$null
if (-not $pythonVer) { Write-Error "Python not found!"; exit 1 }

# 2. 安装依赖 (仅在 node_modules 不存在时强制安装，否则手动更新)
if (-not (Test-Path "node_modules")) {
    Write-Host "[2/3] 安装依赖 (首次启动)..." -ForegroundColor Yellow
    pnpm install
} else {
    Write-Host "[2/3] 跳过依赖安装 (已有 node_modules)，如有问题请手动 pnpm install" -ForegroundColor Green
}

# 3. 启动所有服务
Write-Host "[3/3] 启动后端, Admin 和 Frontend..." -ForegroundColor Yellow
Write-Host "      Backend:  http://localhost:8033" -ForegroundColor Green
Write-Host "      Admin:    http://localhost:3002" -ForegroundColor Green
Write-Host "      Frontend: http://localhost:3005" -ForegroundColor Green

$rootDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

# 后端 (独立窗口)
Start-Process cmd -ArgumentList "/k cd /d `"$rootDir`" && title AnGIneer Backend && pnpm dev:backend"

# Admin (独立窗口)
Start-Process cmd -ArgumentList "/k cd /d `"$rootDir`" && title AnGIneer Admin && pnpm dev:admin"

# 等待后端启动
Write-Host ""
Write-Host "等待后端服务启动 (10秒)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Frontend (当前窗口)
pnpm dev:frontend
