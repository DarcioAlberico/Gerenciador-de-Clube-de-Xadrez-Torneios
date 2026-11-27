import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import PairingService, TournamentService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
ts = TournamentService(db); ps = PairingService(db)
tid = ts.create_tournament({"name": "Interclubes", "competition_type": "team", "rounds_count": "3", "bye_points": "1"})
s = db.get_tournament_settings(tid); s["team_boards_count"] = 1; db.save_tournament_settings(tid, s)
p = [db.create_player(tid, name=f"J{i}", rating=2000-i) for i in range(2)]
a = db.create_team(tid, "A"); b = db.create_team(tid, "B")
db.add_player_to_team(a, p[0], board_number=1); db.add_player_to_team(b, p[1], board_number=1)
rid = db.create_round_with_team_matches(tid, 1, [{"match_number": 1, "white_team_id": a, "black_team_id": b,
    "boards": [{"board_number": 1, "white_player_id": p[0], "black_player_id": p[1]}]}])
m = db.list_team_matches_for_round(rid)[0]; bd = db.list_team_boards(m["id"])[0]
ps.update_result(tid, bd["id"], "1-0")
for i in range(2):
    ps.close_round(tid, rid)
print("eventos team_round_closed:", len(db.list_audit_events(tid, action="team_round_closed", limit=100)))
print("backups close_team_round:", len(list((tmp / "b").glob("*close_team_round*"))))
# atomicidade: falha simulada depois de fechar
rid2 = db.create_round_with_team_matches(tid, 2, [{"match_number": 1, "white_team_id": b, "black_team_id": a,
    "boards": [{"board_number": 1, "white_player_id": p[1], "black_player_id": p[0]}]}])
m2 = db.list_team_matches_for_round(rid2)[0]; bd2 = db.list_team_boards(m2["id"])[0]
ps.update_result(tid, bd2["id"], "0-1")
orig = db.create_standings_snapshot
def boom(**k): raise RuntimeError("falha simulada no retrato")
db.create_standings_snapshot = boom
try: ps.close_round(tid, rid2)
except Exception as e: print("exceção:", e)
db.create_standings_snapshot = orig
print("rodada 2 status:", db.get_round(rid2)["status"], "| retratos:", [x["round_number"] for x in db.list_standings_snapshots(tid)])
