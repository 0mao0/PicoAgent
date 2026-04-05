[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$rootDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$logsDir = Join-Path $rootDir "logs"

# Stop the target service process by PID file and clean stale state.
function Stop-ServiceProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [Parameter(Mandatory = $true)]
        [string]$PidPath
    )

    if (-not (Test-Path $PidPath)) {
        Write-Host "${ServiceName}: PID file not found, skipped." -ForegroundColor DarkGray
        return
    }

    $pidText = (Get-Content $PidPath -Raw -ErrorAction SilentlyContinue).Trim()
    if (-not ($pidText -match '^\d+$')) {
        Write-Warning "${ServiceName}: PID file is invalid and has been removed."
        Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
        return
    }

    $targetProcess = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
    if ($targetProcess) {
        Stop-Process -Id $targetProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "${ServiceName}: stopped PID $pidText" -ForegroundColor Green
    } else {
        Write-Host "${ServiceName}: process not found, removing stale PID $pidText" -ForegroundColor DarkYellow
    }

    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $logsDir)) {
    Write-Host "logs directory not found, nothing to stop." -ForegroundColor DarkGray
    exit 0
}

Stop-ServiceProcess -ServiceName "Backend" -PidPath (Join-Path $logsDir "backend.pid")
Stop-ServiceProcess -ServiceName "Admin" -PidPath (Join-Path $logsDir "admin.pid")
