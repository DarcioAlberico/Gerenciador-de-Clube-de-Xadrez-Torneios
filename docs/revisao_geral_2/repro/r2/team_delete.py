import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import PairingService, TournamentService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
ts = TournamentService(db); ps = PairingService(db)
tid = ts.create_tournament({"name": "Interclubes", "competition_type": "team", "rounds_count": "3", "bye_points": "1"})
p = [db.create_player(tid, name=f"J{i}", rating=2000-i) for i in range(4)]
a = db.create_team(tid, "A"); b = db.create_team(tid, "B")
db.add_player_to_team(a, p[0], board_number=1); db.add_player_to_team(b, p[2], board_number=1)
rid = db.create_round_with_team_matches(tid, 1, [{"match_number": 1, "white_team_id": a, "black_team_id": b,
    "boards": [{"board_number": 1, "white_player_id": p[0], "black_player_id": p[2]}]}])
m = db.list_team_matches_for_round(rid)[0]
bd = db.list_team_boards(m["id"])[0]
with db.connect() as c:
    c.execute("UPDATE team_boards SET result='1-0' WHERE id=?", (bd["id"],))
print("pairings do jogador:", db.count_player_pairings(p[0]))
ps.delete_player_if_unpaired(tid, p[0])
bd2 = db.list_team_boards(m["id"])[0]
print("tabuleiro depois:", {k: bd2.get(k) for k in ("white_player_id", "black_player_id", "result")})
