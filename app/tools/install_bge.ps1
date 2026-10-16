param(
    [string]$Drive = "D",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $PSScriptRoot
$DriveRoot = if ($Drive.EndsWith(":")) { $Drive } else { "$Drive`:" }
$BgeRoot = Join-Path $DriveRoot "BGE-M3"
$VenvRoot = Join-Path $BgeRoot "venv"
$ModelsRoot = Join-Path $BgeRoot "models"
$CacheRoot = Join-Path $BgeRoot "cache"
$ModelDir = Join-Path $ModelsRoot "bge-m3"
$BgePython = Join-Path $VenvRoot "Scripts\python.exe"
$EnvFile = Join-Path $AppRoot ".env"

function Find-Python {
    param([string]$Preferred)
    if ($Preferred) {
        if (-not (Test-Path -LiteralPath $Preferred)) {
            throw "Python not found: $Preferred"
        }
        return $Preferred
    }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python312\python.exe",
        "C:\Program Files\Python312\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "Python 3.12 was not found. Install Python 3.12 or pass -PythonExe."
}

Write-Host "Creating BGE-M3 directories under $BgeRoot"
New-Item -ItemType Directory -Force -Path $BgeRoot, $VenvRoot, $ModelsRoot, $CacheRoot | Out-Null

$BasePython = Find-Python -Preferred $PythonExe
if (-not (Test-Path -LiteralPath $BgePython)) {
    & $BasePython -m venv $VenvRoot
}

$env:HF_HOME = Join-Path $CacheRoot "huggingface"
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:HF_HUB_DISABLE_XET = "1"

Write-Host "Installing sentence-transformers"
& $BgePython -m pip install --upgrade pip
& $BgePython -m pip install sentence-transformers modelscope

Write-Host "Downloading BGE-M3 to $ModelDir"
& $BgePython -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-m3', local_dir=r'$ModelDir', allow_patterns=['*.json','*.model','*.txt','*.safetensors','*.bin'], ignore_patterns=['imgs/*','*.png','*.jpg','*.jpeg','.DS_Store'], max_workers=4)"

$bgeLines = @(
    "BGE_PYTHON=$BgePython",
    "BGE_MODEL_PATH=$ModelDir",
    "BGE_CACHE=$CacheRoot",
    "RETRIEVAL_MODE=hybrid"
)
if (Test-Path -LiteralPath $EnvFile) {
    $existing = Get-Content -LiteralPath $EnvFile | Where-Object {
        $_ -notmatch "^\s*(BGE_PYTHON|BGE_MODEL_PATH|BGE_CACHE|RETRIEVAL_MODE)\s*="
    }
    Set-Content -LiteralPath $EnvFile -Value $existing -Encoding utf8
}
Add-Content -LiteralPath $EnvFile -Encoding utf8 -Value $bgeLines

Write-Host ""
Write-Host "BGE-M3 installation completed."
Write-Host "BGE_PYTHON=$BgePython"
Write-Host "BGE_MODEL_PATH=$ModelDir"
Write-Host "Restart the application and rebuild embeddings."
