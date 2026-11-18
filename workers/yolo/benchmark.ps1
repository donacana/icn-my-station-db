param(
    [ValidateSet('onnx_cpu','torch_cpu','torch_cuda')][string]$Backend = 'onnx_cpu',
    [int]$ImageSize = 416,
    [int]$Threads = 4,
    [int]$Seconds = 30
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = if ($Backend -eq 'onnx_cpu') { '.venv\Scripts\python.exe' } else { '.venv-model\Scripts\python.exe' }
    & $python -m tools.benchmark --backend $Backend --imgsz $ImageSize --threads $Threads --seconds $Seconds
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark failed; see reports/benchmark_*.json' }
} finally { Pop-Location }
