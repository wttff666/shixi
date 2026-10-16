param(
    [string]$Drive = "D",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $PSScriptRoot
$DriveRoot = if ($Drive.EndsWith(":")) { $Drive } else { "$Drive`:" }
$OcrRoot = Join-Path $DriveRoot "PaddleOCR"
$VenvRoot = Join-Path $OcrRoot "venv"
$ModelsRoot = Join-Path $OcrRoot "models"
$CacheRoot = Join-Path $OcrRoot "cache"
$OcrPython = Join-Path $VenvRoot "Scripts\python.exe"
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

    try {
        $resolved = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            return $resolved.Trim()
        }
    } catch {
        # Fall through to the error below.
    }

    throw "Python 3.12 was not found. Install Python 3.12 or pass -PythonExe."
}

Write-Host "Creating OCR directories under $OcrRoot"
New-Item -ItemType Directory -Force -Path $OcrRoot, $VenvRoot, $ModelsRoot, $CacheRoot | Out-Null

$BasePython = Find-Python -Preferred $PythonExe
Write-Host "Using Python: $BasePython"

if (-not (Test-Path -LiteralPath $OcrPython)) {
    & $BasePython -m venv $VenvRoot
}

$env:PADDLEOCR_HOME = $ModelsRoot
$env:PADDLE_PDX_CACHE_HOME = $ModelsRoot
$env:PADDLEX_HOME = Join-Path $CacheRoot "paddlex"
$env:HF_HOME = Join-Path $CacheRoot "huggingface"
$env:FLAGS_use_mkldnn = "0"
$env:FLAGS_use_onednn = "0"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Installing PaddlePaddle and PaddleOCR"
& $OcrPython -m pip install --upgrade pip
& $OcrPython -m pip install "paddlepaddle==3.3.1" "paddleocr==3.7.0"

Write-Host "Initializing OCR and downloading models to $ModelsRoot"
& $OcrPython -c "from paddleocr import PaddleOCR; PaddleOCR(lang='ch', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True, enable_mkldnn=False, cpu_threads=4)"

$ocrLines = @(
    "OCR_PYTHON=$OcrPython",
    "OCR_HOME=$ModelsRoot",
    "OCR_CACHE=$CacheRoot"
)

if (Test-Path -LiteralPath $EnvFile) {
    $existing = Get-Content -LiteralPath $EnvFile | Where-Object {
        $_ -notmatch "^\s*OCR_(PYTHON|HOME|CACHE)\s*="
    }
    Set-Content -LiteralPath $EnvFile -Value $existing -Encoding utf8
}
Add-Content -LiteralPath $EnvFile -Encoding utf8 -Value $ocrLines

Write-Host ""
Write-Host "OCR installation completed."
Write-Host "OCR_PYTHON=$OcrPython"
Write-Host "OCR_HOME=$ModelsRoot"
Write-Host "Restart the application after installation."
