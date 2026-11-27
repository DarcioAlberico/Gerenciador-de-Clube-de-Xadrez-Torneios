import sys, tempfile
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from pathlib import Path
from src.core.database import Database
from src.services.member_service import MemberService
from src.services.prizes import allocate_prizes
from src.core.categories import competition_category_payload
d = tempfile.mkdtemp()
db = Database(Path(d)/"a.db", backup_dir=Path(d)/"b")
ms = MemberService(db)
mid = ms.create_member({"name":"Joao","lichess_username":"joaolx","online_blitz_rating":1700})
m = db.get_member(mid); print("antes", m["lichess_username"], m["online_blitz_rating"])
ms.deactivate_member(mid, "mudou", "2026-11-01")
m = db.get_member(mid); print("desativado", repr(m["lichess_username"]), m["online_blitz_rating"], m["departure_reason"])
data = {k: m[k] for k in ("name","surname","club_id","city","phone","email","document","birth_date","rating","category","member_type","status","guardian_name","guardian_phone","notes")}
data["phone"]="999"
ms.update_member(mid, data)
m = db.get_member(mid); print("editado", repr(m["departure_reason"]), repr(m["departure_date"]))
# duplicata
mid2 = ms.create_member({"name":"Joao"}); print("duplicata aceita", mid2)
# Sub-10 e prêmio Sub-12 no padrão
p = competition_category_payload(birth_date="2017", rating=1300, year=2026, sex="M")
print(p)
st=[{"player_id":1,"position":1,"points":5,"category":p["category"],"categories":p["categories"]},
    {"player_id":2,"position":2,"points":4,"category":"Sub-12","categories":"Sub-12; Sub-1800"}]
r = allocate_prizes(st,[{"kind":"category","category":"Sub-12","rank_from":1,"rank_to":1,"amount":100},{"kind":"category","category":"Sub-1800","rank_from":1,"rank_to":1,"amount":100}],policy="cumulative")
for a in r["allocations"]: print(a["player_id"], a["gross"])
