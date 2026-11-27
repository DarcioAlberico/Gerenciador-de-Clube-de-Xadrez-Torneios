import sys, tempfile
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from pathlib import Path
from src.core.database import Database
from src.services.prizes import allocate_prizes
d = tempfile.mkdtemp()
db = Database(Path(d)/"a.db", backup_dir=Path(d)/"b")
tid = db.create_tournament("T", rounds_count=3)
with db.connect() as c:
    c.execute("UPDATE tournaments SET start_date='2026-03-01' WHERE id=?", (tid,))
pid = db.create_player(tid, name="Ana", birth_date="2015", sex="F", rating=1300)
print("antes", {k: db.get_player(pid)[k] for k in ("category","categories")})
db.replace_tournament_categories(tid, [{"name":"Sub-11","kind":"age","max_value":11},{"name":"Fem","kind":"sex","sex":"F"}])
print("depois edital", {k: db.get_player(pid)[k] for k in ("category","categories")})
db.save_tournament_settings(tid, {"category_reference_date": "2030-01-01"})
print("depois ref", {k: db.get_player(pid)[k] for k in ("category","categories")})

# best_only: categoria soma entre categorias
st = [
 {"player_id":1,"position":1,"points":5,"category":"Sub-12","categories":"Sub-12; Sub-1400; Feminino"},
 {"player_id":2,"position":2,"points":4,"category":"Sub-12","categories":"Sub-12; Sub-1400"},
 {"player_id":3,"position":3,"points":3,"category":"Sub-12","categories":"Sub-12; Sub-1400; Feminino"},
]
pr = [
 {"kind":"overall","rank_from":1,"rank_to":1,"amount":100},
 {"kind":"category","category":"Sub-12","rank_from":1,"rank_to":1,"amount":50},
 {"kind":"category","category":"Sub-1400","rank_from":1,"rank_to":1,"amount":50},
 {"kind":"category","category":"Feminino","rank_from":1,"rank_to":1,"amount":50},
]
r = allocate_prizes(st, pr, policy="best_only")
for a in r["allocations"]: print(a["player_id"], a["overall"], a["category_prize"], a["gross"])
print("total", r["total_gross"])
st2 = [
 {"player_id":1,"position":1,"points":5,"category":"Sub-12","categories":"Sub-1400; Feminino"},
 {"player_id":2,"position":2,"points":4,"category":"Sub-12","categories":"Sub-1400"},
]
r = allocate_prizes(st2, [pr[0], pr[2], pr[3]], policy="best_only")
for a in r["allocations"]: print("b", a["player_id"], a["overall"], a["category_prize"], a["gross"])
