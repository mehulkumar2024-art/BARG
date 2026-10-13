param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 22 or 24 (including npm), reopen PowerShell, and retry.'
}
$nodeMajor = & node -p 'Number(process.versions.node.split(".")[0])'
if ($LASTEXITCODE -ne 0 -or [int]$nodeMajor -lt 20) { throw 'Node.js 20 or newer is required; use 22 or 24.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if ($Python) { & $Python -m venv .venv }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3.12 -m venv .venv }
    else { throw 'Install Python 3.12 with the Python launcher, or pass -Python followed by its executable path.' }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
}
& .\.venv\Scripts\python.exe -m pip --version
if ($LASTEXITCODE -ne 0) {
    & .\.venv\Scripts\python.exe -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'This Python distribution lacks pip. Use a standard Python installation to create the virtual environment.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Run powershell -File scripts/start.ps1, then open http://127.0.0.1:8000'
