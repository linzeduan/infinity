$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $AppRoot ".venv\Scripts\python.exe"
. (Join-Path $AppRoot 'runtime.ps1')

Set-Location -LiteralPath $AppRoot

$PythonExecutable = Get-CockpitPython $AppRoot
$State = Get-CockpitSetupState $AppRoot

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $PythonExecutable -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}

& $VenvPython -c 'import sys; assert sys.version_info[:2] == (3, 12)'
if ($LASTEXITCODE -ne 0) { throw 'Existing .venv does not use Python 3.12. Preserve or move it before creating a new environment.' }
if ($State.NeedsPython) {
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
}

if ($State.NeedsFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js/npm is required to build the frontend. Install Node.js, then retry launch.ps1.' }
    Push-Location -LiteralPath (Join-Path $AppRoot "frontend")
    try {
        npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally { Pop-Location }
}

$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $State.StampPath)
@{ requirements = $State.Requirements; frontend = $State.Frontend } | ConvertTo-Json | Set-Content -LiteralPath $State.StampPath -Encoding UTF8

Write-Host ""
Write-Host "Infinity Research Cockpit setup complete." -ForegroundColor Green
Write-Host "Run: powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1"
