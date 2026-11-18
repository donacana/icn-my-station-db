param(
    [string]$EnvFile = '.env.ec2',
    [double]$RunSeconds = 0,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run setup.ps1 first.' }
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        throw "Missing $EnvFile. Copy ec2.env.example to .env.ec2 and set YOLO_WORKER_TOKEN."
    }
    $tokenLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^YOLO_WORKER_TOKEN=.+' } | Select-Object -First 1
    if (-not $tokenLine) { throw 'YOLO_WORKER_TOKEN is empty in the selected env file.' }
    $resolved = (Resolve-Path -LiteralPath $EnvFile).Path
    $env:YOLO_ENV_FILE = $resolved
    $arguments = @('-m', 'app.main', '--run-seconds', $RunSeconds)
    if ($CheckOnly) { $arguments += '--check-config' }
    & .\.venv\Scripts\python.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'EC2 Worker failed; check the redacted console log.' }
} finally {
    Remove-Item Env:YOLO_ENV_FILE -ErrorAction SilentlyContinue
    Pop-Location
}
