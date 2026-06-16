"""
capture_gacrux_pairing.py
=========================
Reproduz um torneio do stress (mesma seed) e CAPTURA o input.trf + o
output.json de CADA chamada de PAREAMENTO ao Gacrux — independente do
returncode. Complementa o capture_gacrux_crash (que so pega rc!=0): aqui o
alvo e o caso em que o Gacrux retorna SUCESSO (rc=0) mas gera um pareamento
invalido (ex.: confronto repetido), detectado depois pela arbitragem.

Tecnica: injeta um subprocess.run instrumentado APENAS no modulo
gacrux_engine (preserva o comportamento real), copiando os arquivos efemeros
antes de o tempdir ser apagado. Nao altera o engine.

Uso:
    .venv\\Scripts\\python.exe tools\\capture_gacrux_pairing.py <indice> [seed]
    (defaults: indice=677, seed=42)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.stress_runner import gen_params  # noqa: E402
from tests.test_stress_10k_tournaments import _run_tournament  # noqa: E402
import src.services.pairing.gacrux_engine as ge  # noqa: E402


def main() -> int:
    idx  = int(sys.argv[1]) if len(sys.argv) > 1 else 677
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    pm = {i: (n, r, s) for (i, n, r, s) in gen_params(idx, seed)}
    n, r, s = pm[idx]
    print(f"Capturando pareamentos de #{idx}: {n} jogadores, {r} rodadas (seed={s})\n")

    real_run = subprocess.run
    saved: list[tuple[str, Path, Path, int]] = []

    def patched_run(cmd, **kw):
        res = real_run(cmd, **kw)
        try:
            inp = cmd[cmd.index("-i") + 1]
            out = cmd[cmd.index("-o") + 1]
            rnd = cmd[cmd.index("-n") + 1] if "-n" in cmd else "?"
            dst_in  = ROOT / "tests" / f"gacrux_pair_{idx}_r{rnd}.trf"
            dst_out = ROOT / "tests" / f"gacrux_pair_{idx}_r{rnd}.out.json"
            shutil.copy(inp, dst_in)
            if Path(out).exists():
                shutil.copy(out, dst_out)
            saved.append((str(rnd), dst_in, dst_out, getattr(res, "returncode", 0)))
        except Exception as exc:  # best-effort
            print("  [captura falhou]", exc)
        return res

    # injeta o patch so no engine; preserva TimeoutExpired usado no except
    ge.subprocess = types.SimpleNamespace(
        run=patched_run, TimeoutExpired=subprocess.TimeoutExpired,
    )

    res = _run_tournament(idx, n, r, s)
    print(f"resultado: success={res.success}  phase={res.failure_phase}  type={res.failure_type}\n")
    print(f"pareamentos capturados: {len(saved)}")
    for (rnd, di, do, rc) in saved:
        print(f"  rodada {rnd}: rc={rc}  {di.name}  {do.name if do.exists() else '(sem output)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
