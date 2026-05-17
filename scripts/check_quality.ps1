$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Get-Location).Path

function Invoke-Checked {
    param([scriptblock]$Command)

    & $Command
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-Checked { uv run --extra dev python -m compileall -q .\src .\tests .\app.py }
Invoke-Checked { uv run --extra dev ruff check . }
Invoke-Checked { uv run --extra dev mypy }
Invoke-Checked { uv run --extra dev pytest }
