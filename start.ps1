# AnGIneer Startup Script
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Header($text) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   $text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Step($num, $total, $text) {
    Write-Host ""
    Write-Host "[$num/$total] $text..." -ForegroundColor Yellow
}

Write-Header "AnGIneer Startup"

# Check Node.js
Write-Step 1 4 "Check Node.js"
$nodePath = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodePath) {
    $possiblePaths = @(
        "C:\Program Files\nodejs\node.exe",
        "C:\Program Files (x86)\nodejs\node.exe",
        "$env:LOCALAPPDATA\nvs\current\node.exe"
    )
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $env:PATH = "$([System.IO.Path]::GetDirectoryName($path));$env:PATH"
            break
        }
    }
}

try {
    $nodeVer = node --version 2>$null
    if (-not $nodeVer) { throw }
    Write-Host "        Node.js OK: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "[Error] Node.js not found" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check pnpm
Write-Step 2 4 "Check pnpm"
try {
    $pnpmVer = pnpm --version 2>$null
    if (-not $pnpmVer) { throw }
    Write-Host "        pnpm OK" -ForegroundColor Green
} catch {
    Write-Host "[Warn] Installing pnpm..." -ForegroundColor Yellow
    npm install -g pnpm
}

# Check Python
Write-Step 3 4 "Check Python"
try {
    $pythonVer = python --version 2>$null
    if (-not $pythonVer) { throw }
    Write-Host "        Python OK" -ForegroundColor Green
} catch {
    Write-Host "[Warn] Python not found" -ForegroundColor Yellow
}

# Install dependencies
Write-Header "Install Dependencies"

Write-Host ""
Write-Host "Installing frontend deps..." -ForegroundColor Yellow
pnpm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Error] Frontend install failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Installing Python deps..." -ForegroundColor Yellow
pip install -e services/angineer-core/src -e services/sop-core/src -e services/docs-core/src -e services/geo-core/src -e services/engtools/src

# Start services
Write-Header "Start Services"
Write-Host ""
Write-Host "Frontend: http://localhost:3005" -ForegroundColor Green
Write-Host "Admin:    http://localhost:3002" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8033" -ForegroundColor Green
Write-Host ""

$rootDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

# Start backend
Start-Process cmd -ArgumentList "/k cd /d `"$rootDir`" && title AnGIneer Backend && python apps/api-server/main.py"

# Start admin
Start-Process cmd -ArgumentList "/k cd /d `"$rootDir`" && title AnGIneer Admin && pnpm dev:admin"

# Wait
Start-Sleep -Seconds 3

# Start frontend (blocking)
pnpm dev:frontend

Read-Host "Press Enter to exit"
