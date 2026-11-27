<#
.SYNOPSIS
    Gate de qualidade do Albericus: compilação, lint, tipos e testes.

.DESCRIPTION
    Roda os mesmos passos que o CI (.github/workflows/quality.yml) e, por
    padrão, também a suíte de janela — que só roda aqui, no Windows, onde o app
    é entregue. Cada passo é nomeado: falhou, você sabe qual.

.PARAMETER Fast
    Só os passos estáticos (compilação, lint, tipos). Segundos, não minutos —
    serve para rodar antes de cada commit.

.PARAMETER NoGui
    Pula a suíte marcada como 'gui'. É o que o CI faz, por não ter display.

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

Invoke-Step "Compilação" { uv run --extra dev python -m compileall -q .\src .\tests .\app.py }
Invoke-Step "Lint (ruff)" { uv run --extra dev ruff check . }
Invoke-Step "Tipos (mypy, src/core)" { uv run --extra dev mypy }
Invoke-Step "Convenções de UI (tokens e imports)" { uv run --extra dev python scripts/check_ui_conventions.py }
Invoke-Step "Acentuação dos textos visíveis" { uv run --extra dev python scripts/check_ui_accents.py }

if (-not $Fast) {
    if ($NoGui) {
        Invoke-Step "Testes sem janela" { uv run --extra dev pytest -m "not gui" }
    }
    else {
        Invoke-Step "Testes (suíte completa)" { uv run --extra dev pytest }
    }
}

Write-Host ""
Write-Host "Gate concluído:" -ForegroundColor Green
$script:Passos | ForEach-Object { Write-Host "  $_" }
if ($Fast) {
    Write-Host "  (modo -Fast: testes não rodaram)" -ForegroundColor Yellow
}
