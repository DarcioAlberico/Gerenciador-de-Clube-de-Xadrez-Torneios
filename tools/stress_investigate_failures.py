"""
stress_investigate_failures.py
==============================
Investiga as falhas do stress de forma DETERMINISTICA (mesma geracao/seed do
teste oficial), persistindo cada falha em disco na hora — ao contrario do
stress_runner, que so grava o relatorio no fim.

Dois modos:

  SCAN (default): roda os torneios [STRESS_START..STRESS_END] e grava cada
      falha em tests/stress_failures.jsonl assim que ocorre; no fim imprime
      um resumo por (fase, tipo). Use para mapear TODAS as falhas.

  REPRO (STRESS_REPRO=<indice>): roda um unico torneio replicando as fases
      SEM engolir excecao, imprimindo o TRACEBACK COMPLETO da fase que falhar.
      Use para entender a causa-raiz de uma falha especifica.

A geracao de parametros reusa tools.stress_runner.gen_params; a execucao de
um torneio reusa tests.test_stress_10k_tournaments. Mesma seed => mesmos
torneios da corrida oficial.

Env vars (todas opcionais):
    STRESS_START   primeiro indice (default 1)
    STRESS_END     ultimo indice   (default 686 — evita o #687 que trava)
    STRESS_WORKERS workers no scan  (default 4)
    STRESS_SEED    seed mestre      (default 42)
    STRESS_REPRO   indice unico p/ modo repro (ativa o modo repro)
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import threading
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# --- torna a raiz do projeto importavel (tests.*, tools.*, src.*) ----------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.stress_runner import gen_params  # noqa: E402
from tests.test_stress_10k_tournaments import (  # noqa: E402
    REPORT_DIR,
    _create_players,
    _fill_results,
    _run_tournament,
)
from src.core.database import Database  # noqa: E402
from src.core.services import PairingService, TournamentService  # noqa: E402

SEED          = int(os.environ.get("STRESS_SEED", 42))
FAILURES_PATH = REPORT_DIR / "stress_failures.jsonl"


# ---------------------------------------------------------------------------
# Camada PURA
# ---------------------------------------------------------------------------

def failure_record(res: Any) -> dict[str, Any]:
    """TournamentResult de falha -> dict serializavel (sem I/O)."""
    return {
        "index": res.index,
        "players": res.num_players,
        "rounds": res.num_rounds,
        "rounds_done": res.rounds_completed,
        "phase": res.failure_phase,
        "type": res.failure_type,
        "detail": (res.failure_detail or "")[:800],
    }


def params_for(start: int, end: int, seed: int) -> list[tuple[int, int, int, int]]:
    """Parametros deterministicos dos torneios no intervalo [start, end]."""
    return [p for p in gen_params(end, seed) if start <= p[0] <= end]


# ---------------------------------------------------------------------------
# Modo SCAN — mapeia TODAS as falhas, gravando incrementalmente
# ---------------------------------------------------------------------------

def scan() -> int:
    start   = int(os.environ.get("STRESS_START", 1))
    end     = int(os.environ.get("STRESS_END", 686))
    workers = int(os.environ.get("STRESS_WORKERS", 4))
    params  = params_for(start, end, SEED)

    FAILURES_PATH.write_text("", encoding="utf-8")  # zera o arquivo
    lock = threading.Lock()
    by: Counter = Counter()
    done = 0
    fails = 0

    print(f"SCAN torneios #{start}..#{end} ({len(params)}) com {workers} workers\n", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_run_tournament, i, n, r, s): i for (i, n, r, s) in params}
        for fut in as_completed(futs):
            res = fut.result()
            with lock:
                done += 1
                if not res.success:
                    fails += 1
                    rec = failure_record(res)
                    by[(rec["phase"], rec["type"])] += 1
                    with FAILURES_PATH.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    print(f"[FALHA #{rec['index']:>4}] {rec['players']:>2}j {rec['rounds']}r  "
                          f"{rec['phase']}/{rec['type']}", flush=True)
                if done % 50 == 0:
                    print(f"... {done}/{len(params)} ({fails} falhas)", flush=True)

    print(f"\n=== RESUMO ({done} torneios, {fails} falhas) ===", flush=True)
    for (phase, typ), c in by.most_common():
        print(f"  {c:>3}x  {phase} / {typ}", flush=True)
    print(f"\nDetalhes (1 JSON por linha): {FAILURES_PATH}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Modo REPRO — um torneio, traceback completo da fase que falhar
# ---------------------------------------------------------------------------

def _played_opponents(closed_pairings: list[dict[str, Any]]) -> dict[int, set[int]]:
    """pid -> conjunto de oponentes ja enfrentados (ignora byes)."""
    played: dict[int, set[int]] = {}
    for p in closed_pairings:
        if p.get("is_bye"):
            continue
        w = p.get("white_player_id")
        b = p.get("black_player_id")
        if w and b:
            played.setdefault(int(w), set()).add(int(b))
            played.setdefault(int(b), set()).add(int(w))
    return played


def _pair_results(closed_pairings: list[dict[str, Any]]) -> dict[frozenset[int], str]:
    """frozenset({w, b}) -> resultado registrado (classifica forfeit vs jogo real)."""
    out: dict[frozenset[int], str] = {}
    for p in closed_pairings:
        if p.get("is_bye"):
            continue
        w = p.get("white_player_id")
        b = p.get("black_player_id")
        if w and b:
            out[frozenset((int(w), int(b)))] = str(p.get("result") or "")
    return out


def _dump_repeat_context(db: Any, svc: Any, tid: int, rid: int, rnd: int) -> None:
    """Despeja o estado que levou ao bloqueio: ativos/desistentes, historico,
    pareamento proposto, par(es) repetido(s), o RESULTADO do confronto anterior
    (forfeit vs jogo real) e uma heuristica de evitabilidade."""
    print(f"\n--- CONTEXTO da rodada {rnd} (round_id={rid}) ---", flush=True)

    all_players = db.list_players(tid, active_only=False)
    active = db.list_players(tid, active_only=True)
    active_ids = {int(p["id"]) for p in active}
    withdrawn = [int(p["id"]) for p in all_players if int(p["id"]) not in active_ids]
    print(f"jogadores: {len(all_players)} total | {len(active_ids)} ativos | "
          f"{len(withdrawn)} desistentes {withdrawn or ''}", flush=True)

    closed = db.get_pairings_for_tournament(tid, closed_only=True)
    played = _played_opponents(closed)
    results = _pair_results(closed)
    color_seq: dict[int, list[str]] = {}
    for p in closed:
        if p.get("is_bye"):
            color_seq.setdefault(int(p.get("white_player_id") or 0), []).append("bye")
            continue
        w = p.get("white_player_id")
        b = p.get("black_player_id")
        if not (w and b):
            continue
        wo = "*" if str(p.get("result") or "").strip().upper() in {"1F-0F", "0F-1F", "0F-0F"} else ""
        color_seq.setdefault(int(w), []).append(f"W{wo}")
        color_seq.setdefault(int(b), []).append(f"B{wo}")
    print("historico de cor por jogador (* = W.O., nao conta p/ FIDE):", flush=True)
    for pid in sorted(color_seq):
        print(f"  J{pid}: {color_seq[pid]}   (oponentes {sorted(played.get(pid, []))})", flush=True)

    repeats: list[tuple[int, int]] = []
    print(f"pareamento PROPOSTO da rodada {rnd}:", flush=True)
    for p in sorted(db.get_pairings_for_round(rid), key=lambda x: x.get("board_number") or 0):
        if p.get("is_bye"):
            print(f"  mesa {p.get('board_number')}: J{p.get('white_player_id')}  (BYE)", flush=True)
            continue
        w = int(p.get("white_player_id") or 0)
        b = int(p.get("black_player_id") or 0)
        repeated = b in played.get(w, set())
        if repeated:
            repeats.append((w, b))
        print(f"  mesa {p.get('board_number')}: J{w} x J{b}{'   <<< REPETIDO' if repeated else ''}", flush=True)

    issues = [i for i in svc.arbitration_issues(tid)["issues"] if i.get("severity") == "decision"]
    print(f"pendencias bloqueantes: {len(issues)}", flush=True)
    for i in issues:
        ids = (i.get("payload") or {}).get("player_ids")
        print(f"  - {i.get('source')}/{i.get('kind')}: {i.get('title')}  ids={ids}", flush=True)

    print("classificacao do confronto ANTERIOR de cada par repetido:", flush=True)
    for (w, b) in repeats:
        prev = results.get(frozenset((w, b)), "?")
        is_wo = "F" in prev.upper()
        verdict = "W.O./forfeit (nao jogaram de verdade)" if is_wo else ">>> JOGO REAL <<<"
        alt_w = sorted(active_ids - {w} - played.get(w, set()))
        alt_b = sorted(active_ids - {b} - played.get(b, set()))
        print(f"  J{w} x J{b}: resultado anterior = '{prev}'  -> {verdict}", flush=True)
        print(f"      ineditos disponiveis: J{w}->{len(alt_w)} {alt_w} | J{b}->{len(alt_b)} {alt_b}", flush=True)


def repro(index: int) -> int:
    pm = {i: (n, r, s) for (i, n, r, s) in gen_params(index, SEED)}
    n, r, seed = pm[index]
    print(f"=== REPRO torneio #{index}: {n} jogadores, {r} rodadas, seed {seed} ===\n", flush=True)

    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        db   = Database(base / "albericus.db", backup_dir=base / "backups")
        svc  = PairingService(db)
        tsvc = TournamentService(db)

        tid = tsvc.create_tournament(
            {"name": f"Repro #{index}", "rounds_count": str(r), "bye_points": "1"})
        ratings = _create_players(db, tid, n, rng)

        for rnd in range(1, r + 1):
            try:
                rd  = svc.generate_next_round(tid)
                rid = int(rd["id"])
            except Exception:
                print(f"[FALHA em generate_round_{rnd}]\n{traceback.format_exc()}", flush=True)
                return 1

            _fill_results(db, svc, tid, rid, ratings, rng)

            try:
                svc.close_round(tid, rid)
            except Exception:
                print(f"[FALHA em close_round_{rnd}]\n{traceback.format_exc()}", flush=True)
                _dump_repeat_context(db, svc, tid, rid, rnd)
                return 1

            print(f"rodada {rnd}: OK", flush=True)

        print("\nTorneio concluiu SEM falha (nao reproduziu o erro).", flush=True)
    return 0


def main() -> int:
    rp = os.environ.get("STRESS_REPRO")
    return repro(int(rp)) if rp else scan()


if __name__ == "__main__":
    raise SystemExit(main())
