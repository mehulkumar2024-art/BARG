param([ValidateRange(1024,65535)][int]$Port = 8080)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$dashboardUrl = "http://127.0.0.1:$Port"
$existingBarg = $false
try {
    $serviceInfo = Invoke-RestMethod "$dashboardUrl/openapi.json" -TimeoutSec 3
    $existingBarg = $serviceInfo.info.title -eq 'BARG Resource Governance'
} catch {
    # No responding BARG instance: continue with normal startup checks.
}
if ($existingBarg) {
    $runningMode = (Invoke-RestMethod "$dashboardUrl/api/status" -TimeoutSec 3).mode
    if ($runningMode -ne 'system') { throw "An older $runningMode instance is running on port $Port. Stop it with Ctrl+C in its terminal, then rerun this launcher for real system readings." }
    Write-Host "BARG is already running. Open $dashboardUrl in your browser."
    Write-Host 'No second server was started. Stop the existing server in its original terminal if you need to restart it.'
    exit 0
}
$portListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portListener) {
    throw "Port $Port is occupied by a service that could not be verified as BARG. Close that service in its own terminal, then retry. No process was stopped."
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    throw 'Run powershell -File scripts/setup.ps1 first to install dependencies and build the dashboard.'
}
$env:BARG_MODE = 'system'
Write-Host "Open $dashboardUrl in your browser. Keep this terminal open; Ctrl+C stops the demo."
& .\.venv\Scripts\python.exe -m uvicorn barg.backend:app --host 127.0.0.1 --port $Port
if ($LASTEXITCODE -ne 0) { throw "Server failed to start. Check the error above; port $Port may already be in use." }
