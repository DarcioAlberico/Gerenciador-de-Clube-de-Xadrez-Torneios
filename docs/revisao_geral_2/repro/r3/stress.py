"""Stress: torneio suíço Gacrux com byes, W.O., retirada, entrada tardia."""
import json
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\PythonCurso\Albericus")
from src.core.database import Database
from src.services.pairing_service import PairingService
from src.services.constants import AppError, RESULT_POINTS, WALKOVER_RESULTS

CFG = {"pairing_method": "swiss", "time_control": "10 min", "chief_arbiter": "A",
       "federation": "BRA", "location": "SP", "start_date": "2026-06-09", "end_date": "2026-06-09",
       "pairing_system": "gacrux_swiss"}


def run(seed, n=11, rounds=7, bye_points=1.0, late=True, withdraw=True):
    rnd = random.Random(seed)
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db = Database(db_path=Path(tmp.name) / "t.db", backup_dir=Path(tmp.name) / "bk")
    s = PairingService(db)
    tid = db.create_tournament("S", rounds_count=rounds, bye_points=bye_points)
    db.save_tournament_settings(tid, CFG)
    ids = [db.create_player(tid, f"J{i:02d}", rating=2200 - 37 * i, sex="m", birth_date="2000") for i in range(n)]
    problems = []
    for r in range(1, rounds + 1):
        if r == 3 and late:
            try:
                res = s.register_late_entry(tid, {"name": "Tardio", "rating": 1900, "sex": "m", "birth_date": "2000"}, 0.5)
                ids.append(int(res.get("player_id") or res.get("id")))
            except Exception as e:
                problems.append(f"late: {e!r}")
        if r == 4 and withdraw:
            s.set_player_participation(tid, ids[3], "withdrawn", reason="desistiu")
        # bye solicitado aleatório
        if r < rounds and rnd.random() < 0.6:
            pid = rnd.choice(ids)
            try:
                s.request_bye(tid, pid, r, rnd.choice(["H", "Z"]))
            except AppError:
                pass
        try:
            rodada = s.generate_next_round(tid)
        except Exception as e:
            problems.append(f"R{r} generate: {type(e).__name__}: {str(e)[:300]}")
            try:
                rodada = s.generate_next_round(tid, reserve_engine=True)
                problems.append(f"R{r} reserve used")
            except Exception as e2:
                problems.append(f"R{r} reserve fail: {e2!r}")
                break
        rid = int(rodada["id"])
        prev=set(); pabs=set()
        for rr in db.list_rounds(tid):
            if int(rr["number"]) >= r: continue
            for q in db.get_pairings_for_round(int(rr["id"])):
                if q["is_bye"]:
                    if str(q["result"] or "").upper() in ("","BYE","U"): pabs.add(q["white_player_id"])
                    continue
                if q["result"] == "1F-0F": pabs.add(q["white_player_id"])
                if q["result"] == "0F-1F": pabs.add(q["black_player_id"])
                if q["result"] in WALKOVER_RESULTS: continue
                prev.add(frozenset((q["white_player_id"], q["black_player_id"])))
        cur = db.get_pairings_for_round(rid)
        rep = [(q["white_player_id"], q["black_player_id"]) for q in cur if not q["is_bye"] and frozenset((q["white_player_id"], q["black_player_id"])) in prev]
        if rep:
            pool = [q["white_player_id"] for q in cur if not q["is_bye"]] + [q["black_player_id"] for q in cur if not q["is_bye"]] + [q["white_player_id"] for q in cur if q["is_bye"] and str(q["result"] or "").upper() in ("","BYE","U")]
            def can(rest):
                if not rest: return True
                a = rest[0]
                return any(frozenset((a,b)) not in prev and can([x for x in rest[1:] if x != b]) for b in rest[1:])
            opts = [pool] if len(pool)%2==0 else [[x for x in pool if x!=bt] for bt in pool if bt not in pabs]
            problems.append(f"R{r}: repetiu {rep}; alternativa sem repetir existia: {any(can(o) for o in opts)}")
        for p in db.get_pairings_for_round(rid):
            if p["is_bye"]:
                continue
            x = rnd.random()
            res = "1-0" if x < .4 else "0-1" if x < .7 else "1/2-1/2" if x < .92 else rnd.choice(["1F-0F", "0F-1F"])
            s.update_result(tid, int(p["id"]), res)
        s.close_round(tid, rid)
    # invariantes
    hist = defaultdict(list)
    opp = defaultdict(list)
    pab = defaultdict(int)
    for rd in sorted(db.list_rounds(tid), key=lambda x: x["number"]):
        for p in db.get_pairings_for_round(int(rd["id"])):
            w, b = p["white_player_id"], p["black_player_id"]
            if p["is_bye"]:
                if str(p["result"] or "").upper() in ("", "BYE", "U"):
                    pab[w] += 1
                continue
            played = p["result"] not in WALKOVER_RESULTS
            if played:
                hist[w].append("W"); hist[b].append("B")
                opp[w].append(b); opp[b].append(w)
    for pid in hist:
        c = "".join(hist[pid])
        if "WWW" in c or "BBB" in c:
            linhas = []
            for rd in sorted(db.list_rounds(tid), key=lambda x: x["number"]):
                for p in db.get_pairings_for_round(int(rd["id"])):
                    if pid in (p["white_player_id"], p["black_player_id"]):
                        linhas.append((rd["number"], p["white_player_id"], p["black_player_id"], p["result"]))
            pts = {r["player_id"]: r["points"] for r in s.standings(tid)}
            problems.append(f"3 cores iguais seguidas {pid}: {c} {linhas} pts={pts.get(pid)} cor={db.get_tournament_settings(tid).get('initial_color')}")
        if abs(c.count("W") - c.count("B")) > 2:
            problems.append(f"diferenca de cor > 2 {pid}: {c}")
        if len(set(opp[pid])) != len(opp[pid]):
            problems.append(f"reencontro {pid}: {opp[pid]}")
    for pid, k in pab.items():
        if k > 1:
            problems.append(f"PAB repetido {pid}: {k}")
    for ev in ("pairing_check_divergence", "pairing_check_unverified", "pairing_engine_fallback", "tiebreak_engine_fallback", "pairing_warning"):
        evs = db.list_audit_events(tid, action=ev, limit=100)
        for e in evs:
            problems.append(f"evento {ev}: {(e.get('reason') or e.get('after_json') or '')[:300]}")
    try:
        st = s.standings(tid)
    except Exception as e:
        problems.append(f"standings: {e!r}")
    rep = getattr(s, "tiebreak_engine_report", None)
    tmp.cleanup()
    return problems


if __name__ == "__main__":
    seeds = range(int(sys.argv[1]), int(sys.argv[2]))
    kw = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    for sd in seeds:
        pr = run(sd, **kw)
        print(f"seed {sd}: {len(pr)} problemas")
        for p in pr:
            print("   ", p)
