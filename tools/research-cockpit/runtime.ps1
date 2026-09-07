$ErrorActionPreference = 'Stop'
# 子进程可能继承 PowerShell 7 的模块路径，显式加载当前宿主的标准模块。
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force -ErrorAction Stop

function Get-CockpitPython([string]$Root) {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $candidates.Add((Join-Path $Root '.venv\Scripts\python.exe'))
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $candidates.Add($command.Source) }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($line in @(& py -0p 2>$null)) {
            if ($line -match '^\s*-\S+\s+\*?\s*(.+python.exe)\s*$') { $candidates.Add($Matches[1].Trim()) }
        }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        try {
            $version = & $candidate -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))' 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -eq '3.12') { return $candidate }
        } catch { continue }
    }
    throw 'Python 3.12 was not found. Install Python 3.12 from python.org (with the Python launcher), then run launch.ps1 again. Other Python installations will be preserved.'
}

function Get-CockpitFingerprint([string]$Root, [string[]]$Paths) {
    $parts = foreach ($path in ($Paths | Sort-Object)) {
        $relative = $path.Substring($Root.Length).Replace('\', '/')
        $relative + ':' + (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes(($parts -join "`n")))).Replace('-', '')
    } finally { $algorithm.Dispose() }
}

function Test-CockpitPython([string]$PythonPath) {
    if (-not (Test-Path -LiteralPath $PythonPath)) { return $false }
    try {
        & $PythonPath -c 'import sys; assert sys.version_info[:2] == (3, 12); import fastapi, uvicorn, pydantic, pypdf, docx, httpx' 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Get-CockpitSetupState([string]$Root) {
    $venv = Join-Path $Root '.venv\Scripts\python.exe'
    $stamp = $null
    $stampPath = Join-Path $Root '.cache\setup.json'
    if (Test-Path -LiteralPath $stampPath) {
        try { $stamp = Get-Content -LiteralPath $stampPath -Raw | ConvertFrom-Json } catch { $stamp = $null }
    }
    $requirements = (Get-FileHash -LiteralPath (Join-Path $Root 'requirements.txt') -Algorithm SHA256).Hash
    $frontend = Join-Path $Root 'frontend'
    $inputs = @(
        Get-ChildItem -LiteralPath (Join-Path $frontend 'src') -Recurse -File
        Get-ChildItem -LiteralPath $frontend -File | Where-Object { $_.Name -match '^(package(-lock)?\.json|index\.html|tsconfig.*\.json|vite\.config\..+)$' }
    )
    $fingerprint = Get-CockpitFingerprint $frontend @($inputs.FullName)
    $pythonReady = Test-CockpitPython $venv
    $index = Join-Path $frontend 'dist\index.html'
    $frontendReady = Test-Path -LiteralPath $index
    if ($frontendReady) {
        $html = Get-Content -LiteralPath $index -Raw
        foreach ($match in [regex]::Matches($html, '(?:src|href)="(/assets/[^"]+)"')) {
            if (-not (Test-Path -LiteralPath (Join-Path $frontend ('dist' + $match.Groups[1].Value)))) { $frontendReady = $false }
        }
    }
    [pscustomobject]@{
        NeedsPython = (-not $pythonReady -or $stamp.requirements -ne $requirements)
        NeedsFrontend = (-not $frontendReady -or $stamp.frontend -ne $fingerprint)
        Requirements = $requirements
        Frontend = $fingerprint
        StampPath = $stampPath
    }
}

function Get-CockpitHealth([string]$Url, [string]$VaultRoot) {
    try {
        $health = Invoke-RestMethod -Uri ($Url + '/api/health') -TimeoutSec 2
        if ($health.status -eq 'ok' -and $health.database_ready -and $health.frontend_ready -and
            [IO.Path]::GetFullPath($health.vault_root).TrimEnd('\', '/') -eq $VaultRoot.TrimEnd('\', '/')) {
            return $health
        }
    } catch { }
    return $null
}
