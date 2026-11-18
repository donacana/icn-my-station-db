param([ValidateSet('onnx_cpu','torch_cpu','torch_cuda')][string]$Backend = 'onnx_cpu')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = if ($Backend -eq 'onnx_cpu') { '.venv\Scripts\python.exe' } else { '.venv-model\Scripts\python.exe' }
    & $python -m scripts.smoke --backend $Backend
    if ($LASTEXITCODE -ne 0) { throw 'Mock integration failed' }
} finally { Pop-Location }
