param(
    [int]$Port = 8091
)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $AppRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Backend = Join-Path $AppRoot "backend"
$Data = Join-Path $AppRoot "data"
$LogFile = Join-Path $Data "server.log"
$PidFile = Join-Path $Data "server.pid"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found: $Python"
}

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Server is already running on port $Port."
    exit 0
}

$process = Start-Process `
    -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError "$LogFile.error" `
    -PassThru

# 健康检查要同时确认「接口可用」和「本进程还活着」，
# 否则端口被别人占用时会误报启动成功。
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($health.app -eq "remotediag") {
            $ready = $true
            break
        }
    } catch {
        # 服务尚未就绪，继续等待
    }
    if ($process.HasExited) {
        break
    }
    Start-Sleep -Milliseconds 500
}

if ($process.HasExited) {
    if ($ready) {
        Write-Host "Server is already running on port ${Port}: http://127.0.0.1:${Port}"
        exit 0
    }
    throw "启动失败：进程已退出，端口 $Port 可能被其他程序占用。请查看 $LogFile.error"
}

if (-not $ready) {
    Stop-Process -Id $process.Id -Force
    throw "启动超时，或端口 $Port 上运行的是其他应用。请查看 $LogFile.error"
}

Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ascii
Write-Host "Server started: http://127.0.0.1:$Port"
Write-Host "PID: $($process.Id)"
exit 0
