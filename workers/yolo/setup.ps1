param([switch]$Relay)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.cache\pip'
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 venv creation failed' }
    }
    & .\.venv\Scripts\python.exe --version
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed' }
    if ($Relay) {
        & .\.venv\Scripts\python.exe -m pip install -r requirements-relay.txt
        if ($LASTEXITCODE -ne 0) { throw 'Relay dependency install failed' }
    }
    & .\.venv\Scripts\python.exe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency conflict' }
    & .\.venv\Scripts\python.exe -c 'import onnxruntime, cv2, numpy, trackers, websockets, psutil; print("ONNX worker imports OK")'
    if ($LASTEXITCODE -ne 0) { throw 'Import check failed' }
} finally { Pop-Location }
