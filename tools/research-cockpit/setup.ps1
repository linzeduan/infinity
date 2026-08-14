$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $AppRoot ".venv\Scripts\python.exe"

Set-Location -LiteralPath $AppRoot

$PythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $PythonVersion -ne "3.12") {
    throw "Python 3.12 is required. Current version: $PythonVersion"
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    python -m venv .venv
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }

Push-Location -LiteralPath (Join-Path $AppRoot "frontend")
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Infinity Research Cockpit setup complete." -ForegroundColor Green
Write-Host "Run: powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1"
