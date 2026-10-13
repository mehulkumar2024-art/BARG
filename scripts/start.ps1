$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:BARG_MODE = 'demo'
& .\.venv\Scripts\python.exe -m uvicorn barg.backend:app --host 127.0.0.1 --port 8000
