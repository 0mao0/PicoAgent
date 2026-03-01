#!/usr/bin/env pwsh
# AnGIneer 一键启动脚本 (PowerShell)
# 必须在项目根目录运行

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AnGIneer 一键启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Test-Command {
    param($Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

Write-Host "[1/3] 检查 Node.js..." -ForegroundColor Yellow
if (-not (Test-Command "node")) {
    Write-Host "[错误] 未安装 Node.js，请先安装 Node.js >= 18.12.0" -ForegroundColor Red
    exit 1
}
Write-Host "       Node.js 已安装: $(node --version)" -ForegroundColor Green

Write-Host ""
Write-Host "[2/3] 检查 pnpm..." -ForegroundColor Yellow
if (-not (Test-Command "pnpm")) {
    Write-Host "[警告] 未安装 pnpm，正在安装..." -ForegroundColor Yellow
    npm install -g pnpm
}
Write-Host "       pnpm 已安装: $(pnpm --version)" -ForegroundColor Green

Write-Host ""
Write-Host "[3/3] 检查 Python..." -ForegroundColor Yellow
if (-not (Test-Command "python")) {
    Write-Host "[警告] 未安装 Python，后端服务可能无法启动" -ForegroundColor Yellow
} else {
    Write-Host "       Python 已安装: $(python --version)" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  开始安装前端依赖..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

pnpm install

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装 Python 依赖..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

pip install -e services/angineer-core/src -e services/sop-core/src -e services/docs-core/src -e services/geo-core/src -e services/engtools/src

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动开发服务器..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "前端地址: " -NoNewline
Write-Host "http://localhost:3000" -ForegroundColor Green
Write-Host "后端地址: " -NoNewline
Write-Host "http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

Start-Process -FilePath "cmd" -ArgumentList "/c", "cd /d $ScriptDir && python apps/api-server/main.py" -WindowStyle Normal
pnpm dev:frontend
