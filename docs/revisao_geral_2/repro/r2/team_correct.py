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
ps.close_round(tid, rid)
show = lambda: [(r.get("team_name") or r.get("name"), r.get("match_points"), r.get("game_points")) for r in ps.team_standings(tid)]
print("antes da correção:", show())
ps.correct_result(tid, bd["id"], "0-1", "Súmula conferida: preto venceu")
print("tabuleiro:", db.list_team_boards(m["id"])[0]["result"])
print("depois da correção:", show())
print("reconciliados:", ps.reconcile_pending_snapshots(tid))
snap = db.list_standings_snapshots(tid)[0]
print("retrato R1 reconciliado (trecho):", str(snap.get("standings_json") or snap)[:300])
