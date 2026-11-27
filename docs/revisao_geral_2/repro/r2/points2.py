import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import TournamentService, PairingService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
ts = TournamentService(db)
for late in ("-1", "inf", "nan", "0,25"):
    try:
        tid = ts.create_tournament_from_profile({"name": f"T{late}", "rounds_count": "5"}, {"late_entry_points": late}, [])
        print(repr(late), "-> late_entry_points gravado =", db.get_tournament_settings(tid).get("late_entry_points"))
    except Exception as e:
        print(repr(late), "->", type(e).__name__, e)
