param()
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & .\.venv\Scripts\python.exe -m tools.relay_demo
    if ($LASTEXITCODE -ne 0) { throw 'Android local relay demo failed' }
} finally { Pop-Location }
