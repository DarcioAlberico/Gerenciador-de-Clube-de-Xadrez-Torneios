param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Comando Python falhou: $Python $($Arguments -join ' ')"
    }
}

$Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel executar o Python selecionado: $Python"
}
if ([version]$Version -lt [version]"3.11") {
    throw "Python 3.11 ou superior e necessario para gerar o build. Versao atual: $Version"
}

$null = & $Python -m pip --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Invoke-Python -m ensurepip --upgrade
}

Invoke-Python -m pip install --upgrade pip
Invoke-Python -m pip install -r requirements.txt
Invoke-Python -m pip install "pyinstaller>=6.11.0"

$pyinstallerArgs = @("albericus.spec")
if ($Clean) {
    $pyinstallerArgs += "--clean"
}

Invoke-Python -m PyInstaller @pyinstallerArgs
Write-Host "Build concluido em dist\Albericus.exe"
