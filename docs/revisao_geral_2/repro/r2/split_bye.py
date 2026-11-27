import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import TournamentService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
ts = TournamentService(db)
tid = ts.create_tournament({"name": "Aberto", "rounds_count": "5", "bye_points": "0"})
for i in range(4): db.create_player(tid, name=f"J{i}", rating=2000 - i)
print("mãe bye_points:", db.get_tournament(tid)["bye_points"])
for cid in ts.split_tournament(tid, 2):
    print("filho", db.get_tournament(cid)["name"], "bye_points:", db.get_tournament(cid)["bye_points"])
