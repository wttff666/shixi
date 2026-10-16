param(
    [int]$Port = 8091
)

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $AppRoot "data\server.pid"

# 只停止本目录 PID 文件记录的服务，不按端口杀进程，
# 避免误杀同一端口上运行的其他项目。
$stopped = $false
if (Test-Path -LiteralPath $PidFile) {
    $serverPid = [int](Get-Content -LiteralPath $PidFile | Select-Object -First 1)
    $process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $serverPid -Force
        $stopped = $true
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

if ($stopped) {
    Write-Host "Server on port $Port stopped."
} else {
    Write-Host "No server is running on port $Port."
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    Write-Host "注意：端口 $Port 仍被 PID $($listener.OwningProcess) 占用，可能是另一个项目，本脚本不会停止它。"
}
