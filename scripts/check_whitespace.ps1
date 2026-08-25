param(
    [ValidateSet('WorkingTree', 'Staged', 'Range')]
    [string]$Mode = 'WorkingTree',

    [string]$Range = 'origin/main..HEAD'
)

$ErrorActionPreference = 'Continue'

function Test-MarkdownHardBreak {
    param([string]$AddedLine)

    if (-not $AddedLine.StartsWith('+')) {
        return $false
    }

    $content = $AddedLine.Substring(1)
    $withoutSpaces = $content.TrimEnd([char]' ')
    $spaceCount = $content.Length - $withoutSpaces.Length

    return $spaceCount -eq 2 -and $withoutSpaces.Trim().Length -gt 0
}

function Invoke-DiffWhitespaceCheck {
    param([string[]]$DiffArguments)

    $output = @(& git -c core.quotepath=false diff --check @DiffArguments 2>&1)
    $gitExit = $LASTEXITCODE
    if ($gitExit -eq 0) {
        return @()
    }

    $issues = [System.Collections.Generic.List[string]]::new()
    for ($i = 0; $i -lt $output.Count; $i++) {
        $line = [string]$output[$i]
        $match = [regex]::Match($line, '^(?<path>.+):(?<line>\d+): trailing whitespace\.$')

        if ($match.Success -and $i + 1 -lt $output.Count) {
            $path = $match.Groups['path'].Value.Trim('"')
            $addedLine = [string]$output[$i + 1]
            if ($path -match '(?i)\.md$' -and (Test-MarkdownHardBreak -AddedLine $addedLine)) {
                $i++
                continue
            }

            $issues.Add($line)
            $issues.Add($addedLine)
            $i++
            continue
        }

        $issues.Add($line)
    }

    return $issues.ToArray()
}

function Test-UntrackedMarkdownFiles {
    $issues = [System.Collections.Generic.List[string]]::new()
    $repoRoot = (& git rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to determine the Git repository root.'
    }

    $paths = @(& git -c core.quotepath=false ls-files --others --exclude-standard -- '*.md')
    foreach ($relativePath in $paths) {
        if ([string]::IsNullOrWhiteSpace($relativePath)) {
            continue
        }

        $fullPath = Join-Path $repoRoot $relativePath
        $lines = [System.IO.File]::ReadAllLines($fullPath)
        for ($index = 0; $index -lt $lines.Count; $index++) {
            $line = $lines[$index]
            if ($line -match '\s+$') {
                $withoutSpaces = $line.TrimEnd([char]' ')
                $spaceCount = $line.Length - $withoutSpaces.Length
                $validHardBreak = $spaceCount -eq 2 -and $withoutSpaces.Trim().Length -gt 0
                if (-not $validHardBreak) {
                    $issues.Add(('{0}:{1}: invalid trailing whitespace.' -f $relativePath, ($index + 1)))
                }
            }
        }

        $bytes = [System.IO.File]::ReadAllBytes($fullPath)
        if ($bytes.Length -eq 0 -or $bytes[-1] -ne 10) {
            $issues.Add(('{0}: missing newline at end of file.' -f $relativePath))
            continue
        }

        $lastNewlineStart = $bytes.Length - 1
        if ($lastNewlineStart -gt 0 -and $bytes[$lastNewlineStart - 1] -eq 13) {
            $lastNewlineStart--
        }
        if ($lastNewlineStart -gt 0 -and ($bytes[$lastNewlineStart - 1] -eq 10 -or $bytes[$lastNewlineStart - 1] -eq 13)) {
            $issues.Add(('{0}: extra blank line at end of file.' -f $relativePath))
        }
    }

    return $issues.ToArray()
}

$allIssues = [System.Collections.Generic.List[string]]::new()
switch ($Mode) {
    'WorkingTree' {
        foreach ($issue in (Invoke-DiffWhitespaceCheck -DiffArguments @())) {
            $allIssues.Add($issue)
        }
        foreach ($issue in (Invoke-DiffWhitespaceCheck -DiffArguments @('--cached'))) {
            $allIssues.Add($issue)
        }
        foreach ($issue in (Test-UntrackedMarkdownFiles)) {
            $allIssues.Add($issue)
        }
    }
    'Staged' {
        foreach ($issue in (Invoke-DiffWhitespaceCheck -DiffArguments @('--cached'))) {
            $allIssues.Add($issue)
        }
    }
    'Range' {
        foreach ($issue in (Invoke-DiffWhitespaceCheck -DiffArguments @($Range))) {
            $allIssues.Add($issue)
        }
    }
}

if ($allIssues.Count -gt 0) {
    $allIssues | ForEach-Object { Write-Host $_ }
    Write-Host ('Whitespace validation failed: {0} issue lines.' -f $allIssues.Count)
    exit 1
}

Write-Host 'Whitespace validation passed.'
exit 0
