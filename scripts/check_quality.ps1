<#
.SYNOPSIS
    Gate de qualidade do Albericus: compilacao, lint, tipos e testes.

.DESCRIPTION
    Roda os mesmos passos que o CI (.github/workflows/quality.yml) e, por
    padrao, tambem a suite de janela — que so roda aqui, no Windows, onde o app
    e entregue. Cada passo e nomeado: falhou, voce sabe qual.

.PARAMETER Fast
    So os passos estaticos (compilacao, lint, tipos). Segundos, nao minutos —
    serve para rodar antes de cada commit.

.PARAMETER NoGui
    Pula a suite marcada como 'gui'. E o que o CI faz, por nao ter display.

.EXAMPLE
    .\scripts\check_quality.ps1 -Fast
    .\scripts\check_quality.ps1
#>
[CmdletBinding()]
param(
    [switch]$Fast,
    [switch]$NoGui
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Get-Location).Path

$script:Passos = @()

function Invoke-Step {
    param(
        [Parameter(Mandatory)][string]$Nome,
        [Parameter(Mandatory)][scriptblock]$Comando
    )

    Write-Host ""
    Write-Host "==> $Nome" -ForegroundColor Cyan
    $inicio = Get-Date
    & $Comando
    $duracao = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FALHOU: $Nome (${duracao}s)" -ForegroundColor Red
        $script:Passos | ForEach-Object { Write-Host "  $_" }
        exit $LASTEXITCODE
    }

    $script:Passos += "OK   $Nome (${duracao}s)"
    Write-Host "OK ($duracao s)" -ForegroundColor Green
}

Invoke-Step "Compilacao" { uv run --extra dev python -m compileall -q .\src .\tests .\app.py }
Invoke-Step "Lint (ruff)" { uv run --extra dev ruff check . }
Invoke-Step "Tipos (mypy, src/core)" { uv run --extra dev mypy }

if (-not $Fast) {
    if ($NoGui) {
        Invoke-Step "Testes sem janela" { uv run --extra dev pytest -m "not gui" }
    }
    else {
        Invoke-Step "Testes (suite completa)" { uv run --extra dev pytest }
    }
}

Write-Host ""
Write-Host "Gate concluido:" -ForegroundColor Green
$script:Passos | ForEach-Object { Write-Host "  $_" }
if ($Fast) {
    Write-Host "  (modo -Fast: testes nao rodaram)" -ForegroundColor Yellow
}
