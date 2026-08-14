$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $AppRoot "setup.ps1"
$RunScript = Join-Path $AppRoot "run.ps1"
$VenvPython = Join-Path $AppRoot ".venv\Scripts\python.exe"
$FrontendIndex = Join-Path $AppRoot "frontend\dist\index.html"

Set-Location -LiteralPath $AppRoot

try {
    if (-not (Test-Path -LiteralPath $VenvPython) -or -not (Test-Path -LiteralPath $FrontendIndex)) {
        Write-Host "First launch: installing local dependencies..." -ForegroundColor Yellow
        & powershell -NoProfile -ExecutionPolicy Bypass -File $SetupScript
        if ($LASTEXITCODE -ne 0) { throw "Setup failed." }
    }

    & powershell -NoProfile -ExecutionPolicy Bypass -File $RunScript
    if ($LASTEXITCODE -ne 0) { throw "Research Cockpit exited with code $LASTEXITCODE." }
}
catch {
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Press any key to close..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
