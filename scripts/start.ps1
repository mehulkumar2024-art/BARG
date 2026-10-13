$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    throw 'Run powershell -File scripts/setup.ps1 first to install dependencies and build the dashboard.'
}
$env:BARG_MODE = 'demo'
Write-Host 'Open http://127.0.0.1:8000 in your browser. Keep this terminal open; Ctrl+C stops the demo.'
& .\.venv\Scripts\python.exe -m uvicorn barg.backend:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw 'Server failed to start. Check the error above; port 8000 may already be in use.' }
