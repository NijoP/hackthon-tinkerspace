$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

$env:SERVER_HOST = if ($env:SERVER_HOST) { $env:SERVER_HOST } else { "0.0.0.0" }
$env:SERVER_PORT = if ($env:SERVER_PORT) { $env:SERVER_PORT } else { "8000" }

python -m uvicorn server.app:app --host $env:SERVER_HOST --port $env:SERVER_PORT
