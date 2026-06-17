"""
stress_bench_parallel.py
========================
Mede o speedup real de N workers para campos GRANDES, onde o matching pesa mais
e o GIL pode limitar o paralelismo de threads (a corrida real usa
ThreadPoolExecutor). Roda os MESMOS torneios em 1 worker e em 4 workers e
compara — assim o STRESS_NUM da amostra pode ser calibrado para o tempo-alvo.

Uso:
    .venv\\Scripts\\python.exe tools\\stress_bench_parallel.py
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_stress_10k_tournaments import _run_tournament  # noqa: E402

# 4 torneios grandes idênticos em tamanho (150j/7r ~ 23s cada, 1 thread)
JOBS = [(0, 150, 7, 150_000 + i) for i in range(4)]


def _run_all(workers: int) -> float:
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda a: _run_tournament(*a), JOBS))
    return time.perf_counter() - t0


def main() -> int:
    t1 = _run_all(1)
    print(f"1 worker : {t1:6.1f}s  ({t1/len(JOBS):.1f}s/torneio)", flush=True)
    t4 = _run_all(4)
    print(f"4 workers: {t4:6.1f}s  ({t4/len(JOBS):.1f}s/torneio)", flush=True)
    print(f"speedup  : {t1/t4:.2f}x  (de {len(JOBS)} torneios de 150j/7r)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
