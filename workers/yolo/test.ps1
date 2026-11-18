param([switch]$Real)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path reports | Out-Null
    if ($Real) { & .\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/pytest.xml }
    else { & .\.venv\Scripts\python.exe -m pytest -q -m 'not real' --junitxml=reports/pytest_unit.xml }
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
} finally { Pop-Location }
