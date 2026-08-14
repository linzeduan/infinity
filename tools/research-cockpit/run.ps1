$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $AppRoot ".venv\Scripts\python.exe"
$FrontendIndex = Join-Path $AppRoot "frontend\dist\index.html"

if (-not (Test-Path -LiteralPath $VenvPython) -or -not (Test-Path -LiteralPath $FrontendIndex)) {
    throw "Setup is incomplete. Run setup.ps1 first."
}

Set-Location -LiteralPath $AppRoot
$env:PYTHONPATH = $AppRoot
$CockpitUrl = "http://127.0.0.1:8765"

Write-Host "Infinity Research Cockpit" -ForegroundColor Green
Write-Host "Local URL: $CockpitUrl"
Write-Host "Press Ctrl+C to stop."

Start-Process $CockpitUrl
& $VenvPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
