$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RootPrefix = $Root.TrimEnd([char[]]@("\", "/")) + [System.IO.Path]::DirectorySeparatorChar
$IgnoredRootPrefixes = @(
    (Join-Path $Root ".venv"),
    (Join-Path $Root "data"),
    (Join-Path $Root "backups"),
    (Join-Path $Root "logs"),
    (Join-Path $Root "exports")
) | ForEach-Object {
    if (Test-Path -LiteralPath $_) {
        (Resolve-Path -LiteralPath $_).Path.TrimEnd([char[]]@("\", "/")) + [System.IO.Path]::DirectorySeparatorChar
    }
}

function Assert-PathInsideProject {
    param([string]$Path)

    $ResolvedPath = (Resolve-Path -LiteralPath $Path).Path
    if (
        $ResolvedPath -ne $Root -and
        -not $ResolvedPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Caminho fora do projeto recusado: $ResolvedPath"
    }
    return $ResolvedPath
}

function Test-IsIgnoredPath {
    param([string]$Path)

    foreach ($IgnoredRootPrefix in $IgnoredRootPrefixes) {
        if ($Path.StartsWith($IgnoredRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Remove-ProjectPath {
    param([string]$RelativePath)

    $Candidate = Join-Path $Root $RelativePath
    if (-not (Test-Path -LiteralPath $Candidate)) {
        return
    }

    $ResolvedPath = Assert-PathInsideProject $Candidate
    Remove-Item -LiteralPath $ResolvedPath -Recurse -Force
    Write-Host "Removido: $RelativePath"
}

$TopLevelTargets = @(
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "__pycache__"
)

foreach ($Target in $TopLevelTargets) {
    Remove-ProjectPath $Target
}

Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -Filter "__pycache__" |
    ForEach-Object {
        $ResolvedPath = Assert-PathInsideProject $_.FullName
        if (-not (Test-IsIgnoredPath $ResolvedPath)) {
            Remove-Item -LiteralPath $ResolvedPath -Recurse -Force
            Write-Host "Removido: $($_.FullName.Substring($RootPrefix.Length))"
        }
    }

Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
    Where-Object { $_.Name -like "*.pyc" -or $_.Name -like "*.pyo" -or $_.Name -eq ".coverage" } |
    ForEach-Object {
        $ResolvedPath = Assert-PathInsideProject $_.FullName
        if (-not (Test-IsIgnoredPath $ResolvedPath)) {
            Remove-Item -LiteralPath $ResolvedPath -Force
            Write-Host "Removido: $($_.FullName.Substring($RootPrefix.Length))"
        }
    }
