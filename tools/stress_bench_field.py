"""
stress_bench_field.py
=====================
Benchmark de calibração: mede o custo de um torneio completo (criar jogadores,
gerar todas as rodadas, preencher resultados, fechar e ranquear) por tamanho de
campo, usando EXATAMENTE a mesma carga do teste oficial
(``tests.test_stress_10k_tournaments._run_tournament``).

Serve para recalibrar a faixa de jogadores / nº de rodadas / nº de torneios do
stress quando o motor de pareamento muda (ex.: networkx -> Gacrux).

Roda sequencialmente (1 thread) para tempos limpos por ponto. O paralelismo da
corrida real (4 workers) reduz o tempo agregado, mas a CURVA de escala com o
tamanho do campo é o que este benchmark expõe.

Uso:
    .venv\\Scripts\\python.exe tools\\stress_bench_field.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_stress_10k_tournaments import _run_tournament  # noqa: E402

# (jogadores, rodadas) — curva do tiny ao giant, rodadas ~ suiço real
POINTS = [
    (6, 4), (30, 5), (50, 5),
    (75, 6), (100, 6),
    (150, 7), (200, 8), (250, 9),
    (350, 9), (501, 9), (501, 11),
]


def main() -> int:
    print(f"{'jogadores':>9} {'rodadas':>7} {'status':>14} {'rnd_ok':>6} {'tempo_s':>9}",
          flush=True)
    print("-" * 52, flush=True)
    for n, r in POINTS:
        seed = n * 1000 + r
        t0 = time.perf_counter()
        res = _run_tournament(0, n, r, seed)
        dt = time.perf_counter() - t0
        status = "OK" if res.success else f"FAIL:{res.failure_phase}"
        print(f"{n:>9} {r:>7} {status:>14} {res.rounds_completed:>6} {dt:>9.2f}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
