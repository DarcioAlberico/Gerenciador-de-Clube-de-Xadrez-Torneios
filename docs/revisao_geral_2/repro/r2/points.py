import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import TournamentService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
ts = TournamentService(db)
for bye, late in (("inf", "0"), ("0,3", "-2"), ("7", "nan"), ("nan", "0")):
    try:
        tid = ts.create_tournament({"name": f"T{bye}{late}", "rounds_count": "5", "bye_points": bye, "late_entry_points": late})
        t = db.get_tournament(tid); s = db.get_tournament_settings(tid)
        print(repr(bye), repr(late), "-> gravado bye_points=", t.get("bye_points"), "late_entry_points=", s.get("late_entry_points"))
    except Exception as e:
        print(repr(bye), repr(late), "->", type(e).__name__, e)
