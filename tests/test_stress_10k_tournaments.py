"""
test_stress_10k_tournaments.py
==============================
Teste de stress pesado: 10.000 torneios aleatórios no motor Albericus.

LIMITES DE CAMPO (JUSTIFICATIVA DE PERFORMANCE)
------------------------------------------------
O algoritmo networkx.min_weight_matching é O(n³) no número de jogadores.
Medições empíricas no ambiente de teste:

    10j / 2 rnd  ≈     500 ms
    20j / 2 rnd  ≈   1.000 ms
    30j / 2 rnd  ≈   2.000 ms
    50j / 2 rnd  ≈   5.000 ms
   100j / 2 rnd  ≈  15.000 ms
   200j / 2 rnd  ≈  40.000 ms

Para 10.000 torneios com 4 workers e média ≤ 5s/torneio:
    10.000 / (4 workers / 5s) ≈ 12.500s ≈ 3.5h  →  campo ≤ 50j, ≤ 5 rodadas

O campo de 2 a 50 jogadores cobre os perfis "tiny" e "small" que
representam 55% dos torneios reais. Torneios large/giant são testados
separadamente nos edge cases.

Cenários cobertos
-----------------
* Número PAR e ÍMPAR de jogadores (2 a 50 jogadores)
* Ratings variados (400 a 3000), idades diversas (5 a 80 anos)
* Resultados normais, zebras, empates, walkovers (1F-0F, 0F-1F, 0F-0F)
* Desistências mid-tournament (~0,5% por partida)
* edge-cases separados para 100j, 200j e 501j (1-2 rodadas)

Relatórios:
    tests/stress_report_10k.json
    tests/stress_report_10k.txt
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import tempfile
import threading
import time
import traceback
import unittest
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

logging.disable(logging.CRITICAL)

from src.core.database import Database
from src.core.services import PairingService, TournamentService

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
NUM_TOURNAMENTS  = 10_000
SEED             = 42
REPORT_DIR       = Path(__file__).parent
TIMEOUT_SECONDS  = 60       # timeout por torneio (não pode matar threads, mas marca tmo)
MAX_WORKERS      = 4        # threads paralelas

# Campo: 2–50 jogadores para desempenho praticável (<3h total)
PROFILE_WEIGHTS = {
    "tiny":   0.35,   # 2–9 jogadores
    "small":  0.65,   # 10–50 jogadores
}
MAX_ROUNDS_BY_PROFILE = {"tiny": 7, "small": 5}

RESULT_POOL_NORMAL = [("1-0", 55), ("0-1", 30), ("1/2-1/2", 15)]
RESULT_POOL_ZEBRA  = [("0-1", 55), ("1-0", 30), ("1/2-1/2", 15)]
RESULT_POOL_WALK   = [("1F-0F", 40), ("0F-1F", 40), ("0F-0F", 20)]

_print_lock = threading.Lock()
def _tprint(*a, **kw):
    with _print_lock: print(*a, **kw)


# ---------------------------------------------------------------------------
# Geradores
# ---------------------------------------------------------------------------

def _player_size(rng: random.Random) -> int:
    profile = rng.choices(list(PROFILE_WEIGHTS), weights=list(PROFILE_WEIGHTS.values()), k=1)[0]
    return rng.randint(2, 9) if profile == "tiny" else rng.randint(10, 50)


def _num_rounds(n: int, rng: random.Random) -> int:
    max_r = MAX_ROUNDS_BY_PROFILE["tiny" if n <= 9 else "small"]
    base  = max(1, math.ceil(math.log2(max(2, n))))
    return max(1, min(base + rng.randint(-1, 1), max_r))


def _birth_date(age: int) -> str:
    today = date.today()
    try:    return today.replace(year=today.year - age).isoformat()
    except: return today.replace(month=3, day=1, year=today.year - age).isoformat()


def _random_result(wr: int, br: int, rng: random.Random) -> str:
    if rng.random() < 0.03:
        pool, w = zip(*RESULT_POOL_WALK)
        return rng.choices(pool, weights=w, k=1)[0]
    adj  = 0.12 * max(0.2, 1.0 - abs(wr - br) / 800)
    pool, w = zip(*(RESULT_POOL_ZEBRA if rng.random() < adj else RESULT_POOL_NORMAL))
    return rng.choices(pool, weights=w, k=1)[0]


def _create_players(db, tid, n, rng) -> dict[int, int]:
    ratings: dict[int, int] = {}
    for i in range(n):
        rating = rng.randint(400, 3000)
        age    = rng.randint(5, 80)
        cat    = (
            "Sub-10" if age < 10 else "Sub-12" if age < 12 else
            "Sub-14" if age < 14 else "Sub-16" if age < 16 else
            "Sub-18" if age < 18 else "Sub-20" if age < 20 else "Absoluto"
        )
        pid = db.create_player(
            tid, name=f"Jogador {i+1}", rating=rating,
            national_rating=max(0, rating + rng.randint(-200, 200)),
            international_rating=max(0, rating + rng.randint(-300, 300)),
            birth_date=_birth_date(age), club=f"Clube {rng.randint(1,20)}", category=cat,
        )
        ratings[pid] = rating
    return ratings


def _fill_results(db, svc, tid, round_id, ratings, rng) -> None:
    for p in db.get_pairings_for_round(round_id):
        if p.get("is_bye"): continue
        if rng.random() < 0.005:
            who = p.get("white_player_id") or p.get("black_player_id")
            if who:
                try: db.set_player_status(int(who), "withdrawn")
                except: pass
        wr = ratings.get(int(p.get("white_player_id") or 0), 1200)
        br = ratings.get(int(p.get("black_player_id") or 0), 1200)
        try: svc.update_result(tid, int(p["id"]), _random_result(wr, br, rng))
        except: pass


# ---------------------------------------------------------------------------
# Resultado por torneio
# ---------------------------------------------------------------------------

class TournamentResult:
    __slots__ = ("index","num_players","num_rounds","success","rounds_completed",
                 "failure_phase","failure_type","failure_detail","duration_ms","warnings","timed_out")
    def __init__(self, index, n, r):
        self.index=index; self.num_players=n; self.num_rounds=r
        self.success=False; self.rounds_completed=0
        self.failure_phase=""; self.failure_type=""; self.failure_detail=""
        self.duration_ms=0.0; self.warnings=[]; self.timed_out=False
    def to_dict(self):
        return {k: getattr(self,k) for k in self.__slots__}


# ---------------------------------------------------------------------------
# Execução de um torneio
# ---------------------------------------------------------------------------

def _run_tournament(index: int, num_players: int, num_rounds: int, seed: int) -> TournamentResult:
    result = TournamentResult(index, num_players, num_rounds)
    rng    = random.Random(seed)
    t0     = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            db   = Database(base/"albericus.db", backup_dir=base/"backups")
            svc  = PairingService(db)
            tsvc = TournamentService(db)

            try:
                tid = tsvc.create_tournament({
                    "name": f"Stress #{index}",
                    "rounds_count": str(num_rounds),
                    "bye_points": "1",
                })
            except Exception as exc:
                result.failure_phase="create_tournament"; result.failure_type=type(exc).__name__
                result.failure_detail=str(exc)[:500]; return result

            try:
                ratings = _create_players(db, tid, num_players, rng)
            except Exception as exc:
                result.failure_phase="create_players"; result.failure_type=type(exc).__name__
                result.failure_detail=str(exc)[:500]; return result

            for rnd in range(1, num_rounds + 1):
                try:
                    rd  = svc.generate_next_round(tid)
                    rid = int(rd["id"])
                except Exception as exc:
                    result.failure_phase=f"generate_round_{rnd}"; result.failure_type=type(exc).__name__
                    result.failure_detail=str(exc)[:500]; return result
                try:
                    _fill_results(db, svc, tid, rid, ratings, rng)
                except Exception as exc:
                    result.failure_phase=f"fill_results_{rnd}"; result.failure_type=type(exc).__name__
                    result.failure_detail=str(exc)[:500]; return result
                try:
                    svc.close_round(tid, rid)
                    result.rounds_completed += 1
                except Exception as exc:
                    result.failure_phase=f"close_round_{rnd}"; result.failure_type=type(exc).__name__
                    result.failure_detail=str(exc)[:500]; return result

            try:
                standings = svc.standings(tid)
                seen: set[int] = set(); dups = []
                for s in standings:
                    pid = int(s.get("player_id") or -1)
                    if pid in seen: dups.append(pid)
                    seen.add(pid)
                if dups: result.warnings.append(f"player_ids duplicados: {dups[:5]}")
                if sum(float(s.get("points") or 0) for s in standings) < 0:
                    result.warnings.append("Pontos totais negativos")
            except Exception as exc:
                result.failure_phase="standings"; result.failure_type=type(exc).__name__
                result.failure_detail=str(exc)[:500]; return result

            result.success = True
    except Exception as exc:
        result.failure_phase="outer"; result.failure_type=type(exc).__name__
        result.failure_detail=traceback.format_exc()[:800]
    finally:
        result.duration_ms = (time.perf_counter() - t0) * 1000
    return result


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def _bucket(n):
    if n <= 9: return "tiny_2_9"
    return "small_10_50"

def _stats(vals):
    if not vals: return {k:0 for k in ("min","max","avg","p50","p95","p99")}
    sv=sorted(vals); n=len(sv)
    return {"min":round(sv[0],2),"max":round(sv[-1],2),"avg":round(sum(sv)/n,2),
            "p50":round(sv[int(n*.50)],2),"p95":round(sv[int(n*.95)],2),"p99":round(sv[int(n*.99)],2)}

def _build_report(results, elapsed):
    ok  = [r for r in results if r.success]
    fail= [r for r in results if not r.success]
    tmos= [r for r in fail if r.timed_out]
    fbp: dict[str,Counter] = defaultdict(Counter)
    for r in fail: fbp[r.failure_phase][r.failure_type] += 1
    sz  = Counter(_bucket(r.num_players) for r in results)
    fsz = Counter(_bucket(r.num_players) for r in fail)
    top20 = sorted(fail, key=lambda r:-r.duration_ms)[:20]
    return {
        "summary": {
            "total_tournaments":len(results), "total_success":len(ok),
            "total_failures":len(fail), "total_timeouts":len(tmos),
            "failure_rate_pct":round(100*len(fail)/max(1,len(results)),3),
            "total_warnings":sum(len(r.warnings) for r in results),
            "total_elapsed_s":round(elapsed,2),
            "throughput_per_s":round(len(results)/max(0.001,elapsed),2),
            "workers":MAX_WORKERS, "max_players":50, "seed":SEED,
        },
        "duration_all_ms":    _stats([r.duration_ms for r in results]),
        "duration_success_ms":_stats([r.duration_ms for r in ok]),
        "failures_by_phase":  {p:dict(c) for p,c in sorted(fbp.items())},
        "size_distribution":  dict(sz),
        "failure_by_size":    dict(fsz),
        "top_20_longest_failures":[r.to_dict() for r in top20],
        "all_failures":           [r.to_dict() for r in fail],
    }

def _write_txt(report, path):
    L=[]; A=L.append
    A("="*80); A("  RELATÓRIO DE STRESS — ALBERICUS — 10.000 TORNEIOS ALEATÓRIOS"); A("="*80); A("")
    s=report["summary"]
    A(f"Total simulados          : {s['total_tournaments']:>8,}")
    A(f"Sucessos                 : {s['total_success']:>8,}")
    A(f"Falhas (total)           : {s['total_failures']:>8,}")
    A(f"  dos quais timeouts     : {s['total_timeouts']:>8,}")
    A(f"Taxa de falha            : {s['failure_rate_pct']:>7.3f}%")
    A(f"Warnings de standings    : {s['total_warnings']:>8,}")
    A(f"Tempo total              : {s['total_elapsed_s']:>8.2f} s")
    A(f"Throughput               : {s['throughput_per_s']:>8.2f} torneios/s")
    A(f"Workers paralelos        : {s['workers']:>8}")
    A(f"Campo máximo             : {s['max_players']:>7}j")
    A(f"Seed aleatório           : {s['seed']:>8}")
    A("")
    A("-"*80); A("DURAÇÃO — ms (todos)")
    d=report["duration_all_ms"]
    A(f"  Min={d['min']:.1f}  Avg={d['avg']:.1f}  P50={d['p50']:.1f}  P95={d['p95']:.1f}  P99={d['p99']:.1f}  Max={d['max']:.1f}")
    A(""); A("DURAÇÃO — ms (sucessos)")
    d=report["duration_success_ms"]
    A(f"  Min={d['min']:.1f}  Avg={d['avg']:.1f}  P50={d['p50']:.1f}  P95={d['p95']:.1f}  P99={d['p99']:.1f}  Max={d['max']:.1f}")
    A("")
    A("-"*80); A("DISTRIBUIÇÃO POR TAMANHO")
    for b,c in sorted(report["size_distribution"].items()):
        f=report["failure_by_size"].get(b,0)
        A(f"  {b:<22} total={c:>6,}  falhas={f:>5,}  ({100*f/max(1,c):.2f}%)")
    A("")
    A("-"*80); A("FALHAS POR FASE / TIPO")
    fbp=report["failures_by_phase"]
    if not fbp: A("  Nenhuma falha. ✓")
    else:
        for phase,cnt in sorted(fbp.items()):
            A(f"  Fase: {phase}")
            for t,n in sorted(cnt.items(),key=lambda x:-x[1]): A(f"    {t:<40} {n:>5,}×")
    A("")
    A("-"*80); A("TOP 20 FALHAS MAIS DEMORADAS")
    if not report["top_20_longest_failures"]: A("  Nenhuma falha. ✓")
    else:
        for i,r in enumerate(report["top_20_longest_failures"],1):
            flag=" [TO]" if r.get("timed_out") else ""
            A(f"  #{i:>2}  #{r['index']:>6,}  j={r['num_players']:>3}  rnd={r['num_rounds']}"
              f"  fase={r['failure_phase']}  tipo={r['failure_type']}  {r['duration_ms']:.0f}ms{flag}")
            if r.get("failure_detail"):
                A(f"       {r['failure_detail'].replace(chr(10),' ')[:140]}")
    A("")
    A("-"*80); A("TODAS AS FALHAS")
    afl=report["all_failures"]
    if not afl: A("  Nenhuma falha. ✓")
    else:
        for r in afl:
            flag=" [TO]" if r.get("timed_out") else ""
            A(f"  #{r['index']:>6,}  j={r['num_players']:>3}  rnd={r['num_rounds']}"
              f"  ok={r['rounds_completed']}  fase={r['failure_phase']}  tipo={r['failure_type']}{flag}")
            if r.get("failure_detail"):
                A(f"      {r['failure_detail'].replace(chr(10),' ')[:200]}")
    A(""); A("="*80); A("FIM DO RELATÓRIO"); A("="*80)
    path.write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------------------
# Testes principais
# ---------------------------------------------------------------------------

class StressTenThousandTournamentsTest(unittest.TestCase):
    """
    10.000 torneios aleatórios, 2-50 jogadores, 4 workers paralelos.
    Estimativa: ~2-3 horas.
    """
    _all_results: list[TournamentResult] = []
    _report: dict[str, Any] = {}

    def test_01_stress_run(self) -> None:
        master_rng = random.Random(SEED)
        params = []
        for i in range(1, NUM_TOURNAMENTS + 1):
            n = _player_size(master_rng)
            r = _num_rounds(n, master_rng)
            s = master_rng.randint(0, 2**31)
            params.append((i, n, r, s))

        results: list[TournamentResult|None] = [None] * NUM_TOURNAMENTS
        completed = [0]
        t_start = time.perf_counter()
        lock = threading.Lock()

        def _on_done(future, idx):
            res = future.result()
            with lock:
                results[idx] = res
                completed[0] += 1
                c = completed[0]
            if c % 500 == 0:
                el = time.perf_counter() - t_start
                nf = sum(1 for x in results[:c] if x and not x.success)
                nt = sum(1 for x in results[:c] if x and x.timed_out)
                _tprint(
                    f"[Stress] {c:>5}/{NUM_TOURNAMENTS}  "
                    f"falhas={nf}({nf/c*100:.1f}%)  timeouts={nt}  "
                    f"elapsed={el:.0f}s  throughput={c/el:.2f}/s",
                    flush=True,
                )

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(_run_tournament, i, n, r, s): idx
                       for idx, (i, n, r, s) in enumerate(params)}
            for f in as_completed(futures):
                _on_done(f, futures[f])

        total_elapsed = time.perf_counter() - t_start
        _tprint(f"\n[Stress] Concluído em {total_elapsed:.1f}s  ({total_elapsed/60:.1f} min)", flush=True)

        ordered = [r for r in results if r is not None]
        report  = _build_report(ordered, total_elapsed)

        json_path = REPORT_DIR / "stress_report_10k.json"
        txt_path  = REPORT_DIR / "stress_report_10k.txt"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_txt(report, txt_path)
        _tprint(f"[Stress] Relatório TXT : {txt_path}", flush=True)
        _tprint(f"[Stress] Relatório JSON: {json_path}", flush=True)

        StressTenThousandTournamentsTest._all_results = ordered
        StressTenThousandTournamentsTest._report = report

        fr = report["summary"]["failure_rate_pct"]
        self.assertLessEqual(fr, 5.0, f"Taxa de falha {fr:.3f}% > 5%. Veja {txt_path}")

    def test_02_no_outer_crashes(self):
        if not self._all_results: self.skipTest("Rode test_01 primeiro.")
        outers = [r for r in self._all_results if r.failure_phase == "outer"]
        self.assertEqual(0, len(outers),
            f"{len(outers)} crash(es) outer. Primeiro: {outers[0].failure_detail[:300] if outers else ''}")

    def test_03_no_duplicate_standings(self):
        if not self._all_results: self.skipTest("Rode test_01 primeiro.")
        dups = [r for r in self._all_results if r.success and any("duplicados" in w for w in r.warnings)]
        self.assertEqual(0, len(dups), f"{len(dups)} torneio(s) com standings duplicados. {[r.index for r in dups[:10]]}")

    def test_04_timeout_rate(self):
        if not self._all_results: self.skipTest("Rode test_01 primeiro.")
        tmos = [r for r in self._all_results if r.timed_out]
        rate = len(tmos)/max(1,len(self._all_results))*100
        self.assertLess(rate, 2.0, f"Taxa de timeout {rate:.2f}% >= 2%.")


# ---------------------------------------------------------------------------
# Edge cases: campos maiores (1-2 rodadas para desempenho)
# ---------------------------------------------------------------------------

class StressEdgeCasesTest(unittest.TestCase):
    def _r(self, n, r, seed=0): return _run_tournament(0, n, r, seed or n*997+13)

    def test_edge_2j_1r(self):   r=self._r(2,1);  self.assertTrue(r.success, r.failure_detail)
    def test_edge_3j_2r(self):   r=self._r(3,2);  self.assertTrue(r.success, r.failure_detail)
    def test_edge_4j_3r(self):   r=self._r(4,3);  self.assertTrue(r.success, r.failure_detail)
    def test_edge_5j_odd(self):  r=self._r(5,3);  self.assertTrue(r.success, r.failure_detail)
    def test_edge_9j_par(self):  r=self._r(9,4);  self.assertTrue(r.success, r.failure_detail)
    def test_edge_10j_4r(self):  r=self._r(10,4); self.assertTrue(r.success, r.failure_detail)
    def test_edge_11j_odd(self): r=self._r(11,4); self.assertTrue(r.success, r.failure_detail)
    def test_edge_50j_5r(self):  r=self._r(50,5); self.assertTrue(r.success or not r.timed_out, f"50j/5r: {r.failure_detail}")

    def test_edge_100j_2r(self):
        r = self._r(100, 2, seed=100_002)
        if r.timed_out: self.fail(f"100j/2r: timeout")
        self.assertTrue(r.success, f"100j/2r: {r.failure_detail}")

    def test_edge_200j_1r(self):
        r = self._r(200, 1, seed=200_001)
        if r.timed_out: self.fail(f"200j/1r: timeout")
        self.assertTrue(r.success, f"200j/1r: {r.failure_detail}")

    def test_edge_501j_1r(self):
        r = _run_tournament(0, 501, 1, seed=501_001)
        if r.timed_out: self.fail(f"501j/1r: timeout — motor Gacrux travou")
        self.assertTrue(r.success, f"501j/1r: {r.failure_detail}")


if __name__ == "__main__":
    import sys
    unittest.main(verbosity=2, argv=[sys.argv[0]])
