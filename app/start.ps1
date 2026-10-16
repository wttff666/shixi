param(
    [int]$Port = 8091
)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $AppRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found: $Python"
}

Set-Location (Join-Path $AppRoot "backend")
& $Python -m uvicorn main:app --host 127.0.0.1 --port $Port
