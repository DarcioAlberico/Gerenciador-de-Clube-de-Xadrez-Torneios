"""
stress_runner.py
================
Orquestra a corrida de stress de 10.000 torneios FORA do unittest, gravando
progresso incremental em ``tests/stress_progress.json`` para que a janela de
monitoramento (``tools/stress_monitor.py``) possa exibir o andamento em tempo
real e encerrar a corrida graciosamente.

A LÓGICA DE CARGA (geração de torneios, execução e relatório) é importada do
módulo de teste ``tests.test_stress_10k_tournaments`` — aqui só vive a camada
de I/O (progresso, flag de parada, relatórios). Mesma seed ⇒ mesmo conjunto de
torneios do teste oficial, então os relatórios finais são comparáveis.

Configuração por variáveis de ambiente (todas opcionais):
    STRESS_NUM      nº de torneios   (default: 10.000)
    STRESS_WORKERS  threads paralelas(default: 4)
    STRESS_SEED     seed mestre      (default: 42)

Arquivos (em tests/):
    stress_progress.json   heartbeat lido pela GUI (escrita atômica)
    stress_stop.flag       criado pela GUI para pedir parada graciosa
    stress_report_10k.json relatório final completo
    stress_report_10k.txt  relatório final legível
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# --- torna a raiz do projeto importável (tests.*, src.*) --------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reusa a lógica PURA do teste oficial (sem duplicar geração/execução).
from tests.test_stress_10k_tournaments import (  # noqa: E402
    MAX_WORKERS,
    NUM_TOURNAMENTS,
    REPORT_DIR,
    SEED,
    _build_report,
    _num_rounds,
    _player_size,
    _run_tournament,
    _write_txt,
)

import random  # noqa: E402  (após o ajuste de sys.path)

# ---------------------------------------------------------------------------
# Caminhos e parâmetros de I/O
# ---------------------------------------------------------------------------
PROGRESS_PATH = REPORT_DIR / "stress_progress.json"
STOP_FLAG     = REPORT_DIR / "stress_stop.flag"
JSON_REPORT   = REPORT_DIR / "stress_report_10k.json"
TXT_REPORT    = REPORT_DIR / "stress_report_10k.txt"

PROGRESS_SCHEMA   = 1
WRITE_MIN_GAP_S   = 0.5   # não grava o json com mais frequência que isto
RECENT_KEEP       = 14    # quantos torneios recentes manter para exibir

NUM     = int(os.environ.get("STRESS_NUM", NUM_TOURNAMENTS))
WORKERS = int(os.environ.get("STRESS_WORKERS", MAX_WORKERS))
RUN_SEED = int(os.environ.get("STRESS_SEED", SEED))


# ---------------------------------------------------------------------------
# Camada PURA — montagem do payload de progresso (sem I/O, testável)
# ---------------------------------------------------------------------------

def build_progress(
    *,
    status: str,
    total: int,
    completed: int,
    failures: int,
    timeouts: int,
    warnings: int,
    workers: int,
    started_ts: float,
    now_ts: float,
    recent: list[dict[str, Any]],
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta o dicionário gravado em ``stress_progress.json``.

    Função pura: recebe números e devolve o payload. O ``ts`` (carimbo de
    frescor lido pela GUI) é ``now_ts``, passado de fora para manter pureza.
    """
    elapsed = max(0.0, now_ts - started_ts)
    throughput = completed / elapsed if elapsed > 0 and completed else 0.0
    remaining = max(0, total - completed)
    eta = remaining / throughput if throughput > 0 else None
    failure_pct = (100.0 * failures / completed) if completed else 0.0

    payload: dict[str, Any] = {
        "schema": PROGRESS_SCHEMA,
        "status": status,                 # running | done | stopped | error
        "pid": os.getpid(),
        "total": total,
        "completed": completed,
        "failures": failures,
        "failure_pct": round(failure_pct, 3),
        "timeouts": timeouts,
        "warnings": warnings,
        "throughput": round(throughput, 3),
        "elapsed_s": round(elapsed, 2),
        "eta_s": round(eta, 1) if eta is not None else None,
        "workers": workers,
        "started_ts": started_ts,
        "ts": now_ts,
        "recent": recent,
    }
    if report is not None:
        payload["report"] = report
    return payload


def make_recent_entry(res: Any) -> dict[str, Any]:
    """Resumo enxuto de um torneio concluído para a lista 'recentes' da GUI."""
    return {
        "index": res.index,
        "players": res.num_players,
        "rounds": res.num_rounds,
        "ok": bool(res.success),
        "rounds_done": res.rounds_completed,
        "ms": round(res.duration_ms, 0),
        "phase": res.failure_phase or "",
        "ftype": res.failure_type or "",
    }


# ---------------------------------------------------------------------------
# Camada de I/O
# ---------------------------------------------------------------------------

def write_progress_atomic(payload: dict[str, Any]) -> None:
    """Grava o json de progresso atomicamente (tmp + os.replace).

    Evita que a GUI leia um arquivo pela metade durante a escrita.
    """
    tmp = PROGRESS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, PROGRESS_PATH)


def stop_requested() -> bool:
    return STOP_FLAG.exists()


def clear_stop_flag() -> None:
    try:
        STOP_FLAG.unlink()
    except FileNotFoundError:
        pass


def gen_params(num: int, seed: int) -> list[tuple[int, int, int, int]]:
    """Replica EXATAMENTE a geração de parâmetros do teste oficial.

    Mesma sequência do master_rng ⇒ mesmo conjunto de torneios, tornando o
    relatório comparável ao run do unittest.
    """
    master_rng = random.Random(seed)
    params: list[tuple[int, int, int, int]] = []
    for i in range(1, num + 1):
        n = _player_size(master_rng)
        r = _num_rounds(n, master_rng)
        s = master_rng.randint(0, 2**31)
        params.append((i, n, r, s))
    return params


def run() -> int:
    clear_stop_flag()
    params = gen_params(NUM, RUN_SEED)

    results: list[Any | None] = [None] * NUM
    recent: deque[dict[str, Any]] = deque(maxlen=RECENT_KEEP)
    state = {"completed": 0, "failures": 0, "timeouts": 0, "warnings": 0}
    lock = threading.Lock()
    started = time.time()
    last_write = 0.0
    stopping = False

    def snapshot(status: str, report: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_progress(
            status=status, total=NUM, completed=state["completed"],
            failures=state["failures"], timeouts=state["timeouts"],
            warnings=state["warnings"], workers=WORKERS, started_ts=started,
            now_ts=time.time(), recent=list(recent), report=report,
        )

    # progresso inicial (a GUI já mostra "Em execução…")
    write_progress_atomic(snapshot("running"))

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {
            ex.submit(_run_tournament, i, n, r, s): idx
            for idx, (i, n, r, s) in enumerate(params)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                res = fut.result()
            except Exception:  # cancelado/abortado — ignora
                continue
            with lock:
                results[idx] = res
                state["completed"] += 1
                if not res.success:
                    state["failures"] += 1
                if res.timed_out:
                    state["timeouts"] += 1
                state["warnings"] += len(res.warnings)
                recent.appendleft(make_recent_entry(res))
                now = time.time()
                do_write = (now - last_write) >= WRITE_MIN_GAP_S
                if do_write:
                    last_write = now
            if do_write:
                write_progress_atomic(snapshot("running"))

            if not stopping and stop_requested():
                stopping = True
                # cancela os torneios ainda não iniciados; os em execução terminam
                ex.shutdown(wait=False, cancel_futures=True)
                break

    elapsed = time.time() - started
    ordered = [r for r in results if r is not None]
    report = _build_report(ordered, elapsed)

    # relatórios finais (reusa o formatador do teste oficial)
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_txt(report, TXT_REPORT)

    final_status = "stopped" if stopping else "done"
    write_progress_atomic(snapshot(final_status, report=report))
    return 0


def main() -> int:
    try:
        return run()
    except Exception:
        # registra o erro no próprio progress.json para a GUI exibir
        err = traceback.format_exc()
        try:
            write_progress_atomic({
                "schema": PROGRESS_SCHEMA, "status": "error", "pid": os.getpid(),
                "total": NUM, "completed": 0, "failures": 0, "failure_pct": 0.0,
                "timeouts": 0, "warnings": 0, "throughput": 0.0, "elapsed_s": 0.0,
                "eta_s": None, "workers": WORKERS, "started_ts": time.time(),
                "ts": time.time(), "recent": [], "error": err[:2000],
            })
        except Exception:
            pass
        sys.stderr.write(err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
