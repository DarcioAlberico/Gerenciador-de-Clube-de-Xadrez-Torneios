"""Pontos de PAREAMENTO que o Gacrux lê de um TRF (RGS-03).

O JSON de pareamento do Gacrux só traz os pares; para provar que o motor parearia
com o placar da classificação, os testes perguntam ao próprio Gacrux, pelo
``tiebreakchecker``, o critério ``ACC``: é exatamente o valor que o
``crosstable`` usa para montar os grupos de pontuação (pontos das rodadas +
ajustes 299 + aceleração 250 da rodada seguinte).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from src.core.resources import PROJECT_ROOT
from src.services.pairing import gacrux_runner


def gacrux_pairing_scores(trf_path: Path, closed_rounds: int) -> dict[int, float]:
    """``{start_rank: pontos}`` que o Gacrux usaria para parear a rodada seguinte."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "acc.json"
        cmd = gacrux_runner.gacrux_command("tiebreak", [
            "-i", str(trf_path),
            "-o", str(saida),
            "-b", "utf-8",
            "-s",
            "-n", str(int(closed_rounds)),
            "-F", "JSON",
            "-t", "ACC",
        ])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        resultado = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            cwd=str(PROJECT_ROOT), env=env, timeout=120,
        )
        if resultado.returncode != 0 or not saida.exists():
            raise AssertionError(
                f"tiebreakchecker falhou ({resultado.returncode}):\n"
                f"{resultado.stdout}\n{resultado.stderr}"
            )
        dados = json.loads(saida.read_text(encoding="utf-8"), parse_float=Decimal)
    return {
        int(item["cid"]): float(item["tiebreakScore"][0])
        for item in dados["tiebreakResult"]["competitors"]
    }
