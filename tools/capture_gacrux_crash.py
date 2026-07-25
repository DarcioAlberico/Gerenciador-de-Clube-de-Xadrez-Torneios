"""
capture_gacrux_crash.py
=======================
Reproduz um torneio do stress (mesma seed) e, quando o motor Gacrux estoura
(returncode != 0 no pairingchecker.py), CAPTURA o ``input.trf`` exato + o
comando + o stderr, salvando um caso reproduzível em ``tests/``.

Funciona injetando um ``subprocess.run`` instrumentado APENAS no módulo
``gacrux_engine`` (preservando o comportamento real) — assim pega o TRF antes
de o tempdir efêmero ser apagado, sem alterar o engine.

Uso:
    .venv\\Scripts\\python.exe tools\\capture_gacrux_crash.py [indice] [total] [seed]
    (defaults: indice=496, total=500, seed=42)
"""

from __future__ import annotations

import random
import shutil
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import src.services.pairing.gacrux_engine as ge  # noqa: E402
from tests.test_stress_10k_tournaments import (  # noqa: E402
    _num_rounds,
    _player_size,
    _run_tournament,
)


def gen_params(total: int, seed: int) -> list[tuple[int, int, int, int]]:
    """Replica a geração de parâmetros do stress (mesma seed ⇒ mesmos torneios)."""
    mr = random.Random(seed)
    out = []
    for i in range(1, total + 1):
        n = _player_size(mr)
        r = _num_rounds(n, mr)
        s = mr.randint(0, 2**31)
        out.append((i, n, r, s))
    return out


def main() -> int:
    idx   = int(sys.argv[1]) if len(sys.argv) > 1 else 496
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    seed  = int(sys.argv[3]) if len(sys.argv) > 3 else 42

    params = gen_params(total, seed)
    try:
        i, n, rr, s = next(p for p in params if p[0] == idx)
    except StopIteration:
        print(f"Índice {idx} fora do range 1..{total}")
        return 2
    print(f"Reproduzindo #{i}: {n} jogadores, {rr} rodadas (seed={s})")

    captures: list[dict] = []
    real_run = subprocess.run

    def patched_run(cmd, **kw):
        res = real_run(cmd, **kw)
        if getattr(res, "returncode", 0) != 0:
            try:
                inp = cmd[cmd.index("-i") + 1]
                rnd = cmd[cmd.index("-n") + 1] if "-n" in cmd else "?"
                dst = ROOT / "tests" / f"gacrux_crash_{idx}_r{rnd}.trf"
                shutil.copy(inp, dst)
                captures.append({
                    "cmd": list(cmd), "trf": str(dst), "rc": res.returncode,
                    "stderr": res.stderr, "stdout": res.stdout, "round": rnd,
                })
            except Exception as exc:  # captura best-effort
                print("  [captura falhou]", exc)
        return res

    # injeta o patch só no engine; preserva TimeoutExpired usado no except
    ge.subprocess = types.SimpleNamespace(
        run=patched_run, TimeoutExpired=subprocess.TimeoutExpired,
    )

    res = _run_tournament(i, n, rr, s)
    print(f"resultado: success={res.success} "
          f"phase={res.failure_phase} type={res.failure_type}")
    print(f"capturas de crash do Gacrux: {len(captures)}")
    for c in captures:
        print("=" * 72)
        print("rodada     :", c["round"])
        print("returncode :", c["rc"])
        print("TRF salvo  :", c["trf"])
        print("cmd        :", " ".join(str(x) for x in c["cmd"]))
        print("-" * 72)
        print("STDERR (Gacrux):")
        print(c["stderr"])
        print("-" * 72)
        print("TRF (conteúdo):")
        print(Path(c["trf"]).read_text(encoding="utf-8"))
    return 0 if captures else 1


if __name__ == "__main__":
    raise SystemExit(main())
