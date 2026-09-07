param([switch]$NoBrowser, [switch]$CheckOnly, [ValidateRange(1, 600)][int]$StartupTimeoutSeconds = 120)

$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $AppRoot ".venv\Scripts\python.exe"
. (Join-Path $AppRoot 'runtime.ps1')

$State = Get-CockpitSetupState $AppRoot
if ($State.NeedsPython -or $State.NeedsFrontend) {
    throw "Setup is missing or outdated. Run launch.ps1 first."
}

Set-Location -LiteralPath $AppRoot
$env:PYTHONPATH = $AppRoot
$CockpitUrl = "http://127.0.0.1:8765"

Write-Host "Infinity Research Cockpit" -ForegroundColor Green
Write-Host "Local URL: $CockpitUrl"
Write-Host "Press Ctrl+C to stop."

$VaultRoot = & $VenvPython -c 'from backend.config import settings; print(settings.vault_root)'
if ($LASTEXITCODE -ne 0) { throw 'Unable to load Vault configuration.' }
if (Get-CockpitHealth $CockpitUrl $VaultRoot) {
    Write-Host 'Reusing the healthy service for this Vault.'
    if (-not $NoBrowser -and -not $CheckOnly) { Start-Process $CockpitUrl }
    exit 0
}

$Probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('127.0.0.1'), 8765)
try { $Probe.Start() } catch { throw 'Port 8765 is occupied by another or unready service. No existing process was stopped.' } finally { $Probe.Stop() }
$LogRoot = Join-Path $AppRoot '.cache'
$null = New-Item -ItemType Directory -Force -Path $LogRoot
$LogId = [Guid]::NewGuid().ToString('N')
$StdoutLog = Join-Path $LogRoot "server-$LogId.out.log"
$StderrLog = Join-Path $LogRoot "server-$LogId.err.log"
$Service = $null
try {
    $Service = Start-Process -FilePath $VenvPython -ArgumentList @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8765') -WorkingDirectory $AppRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog
    $Deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $Ready = $false
    while ([DateTime]::UtcNow -lt $Deadline) {
        if ($Service.HasExited) { throw "Service exited before becoming ready. See $StderrLog" }
        if (Get-CockpitHealth $CockpitUrl $VaultRoot) { $Ready = $true; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $Ready) { throw "Service startup timed out. See $StderrLog" }
    Write-Host 'Service health check passed.' -ForegroundColor Green
    if ($CheckOnly) { exit 0 }
    if (-not $NoBrowser) { Start-Process $CockpitUrl }
    while (-not $Service.WaitForExit(500)) { }
    if ($Service.ExitCode -ne 0) { throw "Service failed. See $StderrLog" }
} finally {
    if ($Service -and -not $Service.HasExited) { Stop-Process -Id $Service.Id }
}
