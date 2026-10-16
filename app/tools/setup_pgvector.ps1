<#
.SYNOPSIS
    用 Docker 起一个自带 pgvector 的 PostgreSQL，并把现有 SQLite 数据迁进去。

.DESCRIPTION
    步骤：
    1. 检查 Docker 是否可用；
    2. 在指定目录保存数据库数据文件（默认 D:\PostgreSQL\data）；
    3. 启动 pgvector/pgvector:pg16 容器；
    4. 安装 psycopg 驱动；
    5. 调用 tools\migrate_to_postgres.py 迁移数据；
    6. 输出 app\.env 需要改的两行，加 -UpdateEnv 则直接改。

    需要先安装 Docker Desktop（安装目录建议 D:\DockerDesktop）并启用 WSL2。

.EXAMPLE
    cd C:\Users\honor\Desktop\zuoye\app
    .\tools\setup_pgvector.ps1
    .\tools\setup_pgvector.ps1 -Port 5433 -UpdateEnv
#>

param(
    [string]$DataRoot = "D:\PostgreSQL\data",
    [int]$Port = 5432,
    [string]$Database = "remotediag",
    [string]$DbUser = "remotediag",
    [string]$Password = "",
    [string]$ContainerName = "wind-ops-pgvector",
    [string]$Image = "pgvector/pgvector:pg16",
    [switch]$UpdateEnv,
    [switch]$SkipMigrate,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path (Split-Path -Parent $AppDir) ".venv\Scripts\python.exe"
$EnvFile = Join-Path $AppDir ".env"

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Set-EnvValue([string]$Path, [string]$Key, [string]$Value) {
    $lines = Get-Content -LiteralPath $Path -Encoding UTF8
    $found = $false
    $output = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
            $found = $true
            "$Key=$Value"
        }
        else {
            $line
        }
    }
    if (-not $found) {
        $output = @($output) + "$Key=$Value"
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($Path, @($output), $utf8)
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "没有找到 docker 命令。" -ForegroundColor Yellow
    Write-Host "请先安装 Docker Desktop（安装路径建议 D:\DockerDesktop）："
    Write-Host "  winget install -e --id Docker.DockerDesktop --location D:\DockerDesktop"
    Write-Host "安装后启动 Docker Desktop，确认托盘图标变绿，再重新运行本脚本。"
    exit 1
}

Write-Step "检查 Docker 运行状态"
try {
    docker info --format "{{.ServerVersion}}" | Out-Null
}
catch {
    Write-Host "Docker 已安装但没有运行，请先启动 Docker Desktop。" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "找不到项目虚拟环境：$Python" -ForegroundColor Yellow
    exit 1
}

if (-not $Password) {
    $alphabet = [char[]](48..57 + 65..90 + 97..122)
    $Password = -join (1..24 | ForEach-Object { $alphabet | Get-Random })
    Write-Host "已生成随机数据库密码，请保存在密码管理器里。"
}
elseif ($Password -notmatch "^[A-Za-z0-9]+$") {
    Write-Host "密码含特殊字符，连接串里需要 URL 转义，建议只用字母和数字。" -ForegroundColor Yellow
}

Write-Step "准备数据目录 $DataRoot"
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

$existing = docker ps -a --filter "name=^/$ContainerName$" --format "{{.Names}}"
if ($existing -eq $ContainerName) {
    Write-Host "容器 $ContainerName 已存在，直接启动。"
    docker start $ContainerName | Out-Null
}
else {
    Write-Host "创建容器 $ContainerName"
    docker run -d `
        --name $ContainerName `
        -e "POSTGRES_PASSWORD=$Password" `
        -e "POSTGRES_DB=$Database" `
        -e "POSTGRES_USER=$DbUser" `
        -p "${Port}:5432" `
        -v "${DataRoot}:/var/lib/postgresql/data" `
        --restart unless-stopped `
        $Image | Out-Null
}

Write-Step "等待数据库就绪"
$ready = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
    docker exec $ContainerName pg_isready -U $DbUser -d $Database | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "数据库 2 分钟内没有就绪，请查看：docker logs $ContainerName" -ForegroundColor Yellow
    exit 1
}

$dbExists = docker exec $ContainerName psql -U $DbUser -d postgres -tAc `
    "SELECT 1 FROM pg_database WHERE datname = '$Database'"
if (-not $dbExists) {
    Write-Host "创建数据库 $Database"
    docker exec $ContainerName createdb -U $DbUser $Database | Out-Null
}

$TargetUrl = "postgresql+psycopg://${DbUser}:${Password}@127.0.0.1:${Port}/${Database}"

Write-Step "安装 psycopg 驱动"
& $Python -m pip install -r (Join-Path $AppDir "requirements-postgres.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "驱动安装失败，请检查网络后重试。" -ForegroundColor Yellow
    exit 1
}

if (-not $SkipMigrate) {
    Write-Step "迁移现有 SQLite 数据"
    $migrateArgs = @(
        (Join-Path $AppDir "tools\migrate_to_postgres.py"),
        "--target-url", $TargetUrl
    )
    if ($Force) { $migrateArgs += "--replace" }
    & $Python @migrateArgs
}

Write-Step "需要写入 $EnvFile 的配置"
Write-Host "DATABASE_URL=$TargetUrl"
Write-Host "VECTOR_BACKEND=pgvector"

if ($UpdateEnv) {
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Write-Host "没有找到 $EnvFile，跳过写入。" -ForegroundColor Yellow
    }
    else {
        Set-EnvValue -Path $EnvFile -Key "DATABASE_URL" -Value $TargetUrl
        Set-EnvValue -Path $EnvFile -Key "VECTOR_BACKEND" -Value "pgvector"
        Write-Host "已更新 .env，重启后台服务后生效。" -ForegroundColor Green
    }
}
else {
    Write-Host "加 -UpdateEnv 可以让脚本直接写入上面两行。"
}
