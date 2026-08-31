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

$sourceRoot = Get-ChildItem -LiteralPath $RepositoryRoot -Directory |
    Where-Object { $_.Name -match '^\u539F\u59CB\u8D44\u6599$' } |
    Select-Object -First 1
$wereadRoot = if ($sourceRoot) {
    Get-ChildItem -LiteralPath $sourceRoot.FullName -Directory |
        Where-Object { $_.Name -match '^\u5FAE\u4FE1\u8BFB\u4E66$' } |
        Select-Object -First 1
}
if (-not $wereadRoot) {
    Write-Host 'Weread export directory not found; no cleanup needed.'
    exit 0
}

$utf8 = [Text.UTF8Encoding]::new($false, $true)
$changedFiles = 0
$changedLines = 0

foreach ($file in Get-ChildItem -LiteralPath $wereadRoot.FullName -File -Filter '*.md') {
    $content = [IO.File]::ReadAllText($file.FullName, $utf8)
    $fileChangedLines = [ref]0
    $normalized = [regex]::Replace(
        $content,
        '(?m)^(?<body>[^\r\n]*?)(?<trailing>[ \t]+)(?=\r?$)',
        {
            param($match)
            $trailing = $match.Groups['trailing'].Value
            $body = $match.Groups['body'].Value
            $validHardBreak = $trailing -eq '  ' -and $body.Trim().Length -gt 0
            if ($validHardBreak) {
                return $match.Value
            }

            $fileChangedLines.Value++
            return $body
        }
    )

    if ($fileChangedLines.Value -gt 0) {
        [IO.File]::WriteAllText($file.FullName, $normalized, $utf8)
        $changedFiles++
        $changedLines += $fileChangedLines.Value
    }
}

Write-Host ("Weread export whitespace cleanup complete: {0} file(s), {1} line(s). Valid two-space hard breaks were preserved." -f $changedFiles, $changedLines)
exit 0
