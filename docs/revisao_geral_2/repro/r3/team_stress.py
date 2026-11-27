import sys, random, logging
from collections import defaultdict
sys.path.insert(0, r"C:\PythonCurso\Albericus")
logging.disable(logging.WARNING)
from tests.support.core_service_base import CoreServiceTestCase

class T(CoreServiceTestCase):
    def runTest(self): pass

def run(seed, teams=7, rounds=6, boards=2):
    rnd = random.Random(seed)
    t = T(); t.setUp()
    tid, team_ids = t._create_team_tournament(teams_count=teams, boards_count=boards)
    with t.db.connect() as c:
        c.execute("UPDATE tournaments SET rounds_count=? WHERE id=?", (rounds, tid))
    problems = []
    for r in range(1, rounds + 1):
        try:
            rd = t.service.generate_next_round(tid)
        except Exception as e:
            problems.append(f"R{r}: {type(e).__name__}: {str(e)[:200]}"); break
        rid = int(rd["id"])
        # existia pareamento sem repetição?
        prev = set(); byes_prev = set()
        for rr in t.db.list_rounds(tid):
            if int(rr["number"]) >= r: continue
            for m in t.db.list_team_matches_for_round(int(rr["id"])):
                if m.get("is_bye") or not m["black_team_id"]: byes_prev.add(m["white_team_id"]); continue
                prev.add(frozenset((m["white_team_id"], m["black_team_id"])))
        cur = [m for m in t.db.list_team_matches_for_round(rid)]
        rep = [m for m in cur if not m.get("is_bye") and m["black_team_id"] and frozenset((m["white_team_id"], m["black_team_id"])) in prev]
        if rep:
            ids = list(team_ids)
            def can(rest):
                if not rest: return True
                a = rest[0]
                return any(frozenset((a,b)) not in prev and can([x for x in rest[1:] if x != b]) for b in rest[1:])
            options = [ids] if len(ids)%2==0 else [[x for x in ids if x!=bt] for bt in ids if bt not in byes_prev]
            problems.append(f"R{r}: repetiu {[(m['white_team_id'], m['black_team_id']) for m in rep]}; havia alternativa sem repetir: {any(can(o) for o in options)}")
        for m in t.db.list_team_matches_for_round(rid):
            for b in t.db.list_team_boards(int(m["id"])):
                if m.get("is_bye"): continue
                t.service.update_result(tid, int(b["id"]), rnd.choice(["1-0", "0-1", "1/2-1/2", "1-0", "0-1"]))
        t.service.close_round(tid, rid)
    met = defaultdict(list); col = defaultdict(str); byes = defaultdict(int)
    for rd in sorted(t.db.list_rounds(tid), key=lambda x: x["number"]):
        for m in t.db.list_team_matches_for_round(int(rd["id"])):
            w, b = m["white_team_id"], m["black_team_id"]
            if m.get("is_bye") or not b:
                byes[w] += 1; continue
            met[w].append(b); met[b].append(w); col[w] += "W"; col[b] += "B"
    for tm in met:
        if len(set(met[tm])) != len(met[tm]): problems.append(f"reencontro equipe {tm}: {met[tm]}")
        if "WWW" in col[tm] or "BBB" in col[tm]: problems.append(f"3 cores seguidas equipe {tm}: {col[tm]}")
    for tm, k in byes.items():
        if k > 1: problems.append(f"bye repetido equipe {tm}: {k}")
    t.tearDown()
    return problems

for sd in range(int(sys.argv[1]), int(sys.argv[2])):
    pr = run(sd, *[int(x) for x in sys.argv[3:]])
    print(f"seed {sd}: {pr}")
