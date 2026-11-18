param([double]$RunSeconds = 0, [switch]$Torch)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Create .venv first; see README.md' }
    $python = if ($Torch) { '.venv-model\Scripts\python.exe' } else { '.venv\Scripts\python.exe' }
    & $python -m app.main --run-seconds $RunSeconds
    if ($LASTEXITCODE -ne 0) { throw 'Worker failed; see console and README.md' }
} finally { Pop-Location }
