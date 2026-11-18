param([int]$Port = 8000, [long]$CameraId = 1, [double]$RunSeconds = 0)
$ErrorActionPreference = 'Stop'
$values = @{
    YOLO_PROTOCOL='demo-v0.3'; CAMERA_ID=[string]$CameraId; INFERENCE_BACKEND='onnx_cpu';
    WS_URL="ws://127.0.0.1:$Port/ws/yolo/worker"; MOCK_MODE='true'; YOLO_MAX_FPS='3'
}
if (-not $env:YOLO_WORKER_TOKEN) { $values['YOLO_WORKER_TOKEN']='local-worker-demo' }
$previous = @{}
Push-Location $PSScriptRoot
try {
    foreach ($key in $values.Keys) {
        $previous[$key]=[Environment]::GetEnvironmentVariable($key,'Process')
        [Environment]::SetEnvironmentVariable($key,$values[$key],'Process')
    }
    & .\.venv\Scripts\python.exe -m app.main --run-seconds $RunSeconds
    if ($LASTEXITCODE -ne 0) { throw 'v0.3 Worker failed' }
} finally {
    foreach ($key in $previous.Keys) { [Environment]::SetEnvironmentVariable($key,$previous[$key],'Process') }
    Pop-Location
}
