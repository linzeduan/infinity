[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepositoryRoot = Split-Path -Parent $scriptDirectory
}
Set-Location -LiteralPath $RepositoryRoot

$errors = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

function Add-ValidationError([string]$Message) {
    $errors.Add($Message)
}

function Add-ValidationWarning([string]$Message) {
    $warnings.Add($Message)
}

function Get-TableIds([string]$Path) {
    Select-String -LiteralPath $Path -Pattern '^\|\s*([^|]+?)\s*\|' -Encoding UTF8 |
        ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() } |
        Where-Object { $_ -notin @('#', '---') }
}

$ledgerPath = Join-Path $RepositoryRoot '知识库/_processed.md'
$indexPath = Join-Path $RepositoryRoot '知识库/目录.md'
$predictionPath = Join-Path $RepositoryRoot '知识库/预测追踪表.md'

foreach ($required in @($ledgerPath, $indexPath, $predictionPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        Add-ValidationError "Missing required file: $required"
    }
}

if ($errors.Count -eq 0) {
    $ledgerRaw = Get-Content -LiteralPath $ledgerPath -Raw -Encoding UTF8
    $indexRaw = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8

    $ledgerIds = Get-TableIds $ledgerPath
    $numericLedgerIds = @($ledgerIds | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
    $duplicateLedgerIds = @($numericLedgerIds | Group-Object | Where-Object Count -gt 1)
    foreach ($duplicate in $duplicateLedgerIds) {
        Add-ValidationError "Duplicate numeric ledger ID: $($duplicate.Name)"
    }

    if ($numericLedgerIds.Count -gt 0) {
        $maxLedgerId = ($numericLedgerIds | Measure-Object -Maximum).Maximum
        $ledgerSet = [System.Collections.Generic.HashSet[int]]::new()
        foreach ($id in $numericLedgerIds) { [void]$ledgerSet.Add($id) }
        foreach ($expected in 1..$maxLedgerId) {
            if (-not $ledgerSet.Contains($expected)) {
                Add-ValidationError "Missing numeric ledger ID: $expected"
            }
        }
    }

    $predictionIds = @(
        Select-String -LiteralPath $predictionPath -Pattern '^\|\s*(\d+)\s*\|' -Encoding UTF8 |
            ForEach-Object { [int]$_.Matches[0].Groups[1].Value }
    )
    foreach ($duplicate in @($predictionIds | Group-Object | Where-Object Count -gt 1)) {
        Add-ValidationError "Duplicate prediction ID: $($duplicate.Name)"
    }
    if ($predictionIds.Count -gt 0) {
        $maxPredictionId = ($predictionIds | Measure-Object -Maximum).Maximum
        $predictionSet = [System.Collections.Generic.HashSet[int]]::new()
        foreach ($id in $predictionIds) { [void]$predictionSet.Add($id) }
        foreach ($expected in 1..$maxPredictionId) {
            if (-not $predictionSet.Contains($expected)) {
                Add-ValidationError "Missing prediction ID: $expected"
            }
        }
    }

    $sourceFiles = @(
        Get-ChildItem -LiteralPath (Join-Path $RepositoryRoot '原始资料') -Recurse -File |
            Where-Object Extension -ne '.gitkeep'
    )
    foreach ($file in $sourceFiles) {
        $relative = $file.FullName.Substring($RepositoryRoot.Length + 1).Replace('\', '/')
        if (-not $ledgerRaw.Contains($relative)) {
            Add-ValidationWarning "Source file is not present in the ledger under its current full path: $relative"
        }
    }

    $linkMatches = [regex]::Matches($indexRaw, '\[[^\]]+\]\(([^)]+)\)')
    foreach ($match in $linkMatches) {
        $target = $match.Groups[1].Value
        if ($target -match '^(https?://|#)') { continue }
        $decoded = [uri]::UnescapeDataString(($target -split '#')[0])
        $fullPath = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $indexPath) $decoded))
        if (-not (Test-Path -LiteralPath $fullPath)) {
            Add-ValidationError "Index link target does not exist: $target"
        }
    }

    $knowledgeMarkdown = @(
        Get-ChildItem -LiteralPath (Join-Path $RepositoryRoot '知识库') -Recurse -File -Filter '*.md' |
            Where-Object Name -notin @('_processed.md', '目录.md')
    )
    foreach ($file in $knowledgeMarkdown) {
        if (-not $indexRaw.Contains($file.Name)) {
            Add-ValidationWarning "Knowledge Markdown is not present in the index by filename: $($file.FullName.Substring($RepositoryRoot.Length + 1))"
        }
    }

    $utf8 = [Text.UTF8Encoding]::new($false, $true)
    foreach ($file in Get-ChildItem -LiteralPath $RepositoryRoot -Recurse -File -Filter '*.md') {
        try {
            [void][IO.File]::ReadAllText($file.FullName, $utf8)
        }
        catch {
            Add-ValidationError "Markdown is not valid UTF-8: $($file.FullName)"
        }
    }

    Write-Host "Numeric ledger rows: $($numericLedgerIds.Count); latest: #$(($numericLedgerIds | Measure-Object -Maximum).Maximum)"
    Write-Host "Prediction rows: $($predictionIds.Count); latest: #$(($predictionIds | Measure-Object -Maximum).Maximum)"
    Write-Host "Source files (excluding .gitkeep): $($sourceFiles.Count)"
    Write-Host "Knowledge Markdown files (excluding ledger and index): $($knowledgeMarkdown.Count)"
    Write-Host "Index links: $($linkMatches.Count)"
}

foreach ($warning in $warnings) {
    Write-Warning $warning
}

if ($errors.Count -gt 0) {
    foreach ($validationError in $errors) {
        Write-Error $validationError
    }
    exit 1
}

Write-Host "Validation passed: 0 errors, $($warnings.Count) warnings." -ForegroundColor Green
exit 0
