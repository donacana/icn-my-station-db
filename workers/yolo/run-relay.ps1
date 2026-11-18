param([string]$BindAddress = '127.0.0.1', [int]$Port = 8000, [long]$CameraId = 1)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & .\.venv\Scripts\python.exe -m local_relay --host $BindAddress --port $Port --camera-id $CameraId
    if ($LASTEXITCODE -ne 0) { throw 'Local relay failed' }
} finally { Pop-Location }
