import sys, tempfile
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from pathlib import Path
from src.core.database import Database
from src.services.tournament_service import TournamentService
d = tempfile.mkdtemp()
db = Database(Path(d)/"a.db", backup_dir=Path(d)/"b")
ts = TournamentService(db)
tid = db.create_tournament("T2025", rounds_count=3)
db.replace_tournament_categories(tid, [{"name":"Sub-11","kind":"age","max_value":11}])
db.replace_tournament_prizes(tid, [{"kind":"category","label":"1o Sub-11","category":"Sub-11","rank_from":1,"rank_to":1,"amount":100}])
db.save_tournament_settings(tid, {"category_reference_date":"2025-01-01","archived":1})
new = ts.duplicate_tournament(tid, "T2026")
print("cats", db.list_tournament_categories(new))
print("prizes", [p["category"] for p in db.list_tournament_prizes(new)])
s = db.get_tournament_settings(new); print("ref", s["category_reference_date"], "archived", s["archived"])
print("listado?", any(t["id"]==new for t in db.list_tournaments()))
