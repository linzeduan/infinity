$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $AppRoot "setup.ps1"
$RunScript = Join-Path $AppRoot "run.ps1"
. (Join-Path $AppRoot 'runtime.ps1')

Set-Location -LiteralPath $AppRoot

try {
    $State = Get-CockpitSetupState $AppRoot
    if ($State.NeedsPython -or $State.NeedsFrontend) {
        Write-Host "Preparing missing or outdated dependencies/build..." -ForegroundColor Yellow
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
