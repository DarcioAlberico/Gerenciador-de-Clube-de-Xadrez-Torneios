param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$Version -lt [version]"3.11") {
    throw "Python 3.11 ou superior e necessario para gerar o build. Versao atual: $Version"
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install "pyinstaller>=6.11.0"

$args = @("albericus.spec")
if ($Clean) {
    $args += "--clean"
}

python -m PyInstaller @args
Write-Host "Build concluido em dist\Albericus.exe"
