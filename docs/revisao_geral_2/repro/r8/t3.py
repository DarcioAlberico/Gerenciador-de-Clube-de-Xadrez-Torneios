import sys, tempfile
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from pathlib import Path
from src.core.database import Database
from src.services.member_service import MemberService
from src.services.pairing_service import PairingService
from src.services.prize_service import PrizeService
d = tempfile.mkdtemp()
db = Database(Path(d)/"a.db", backup_dir=Path(d)/"b")
ms = MemberService(db)
mid = ms.create_member({"name":"Bia","birth_date":"2014-05-01","rating":1300,"member_type":"aluno"})
print("membro", db.get_member(mid)["category"])
tid = db.create_tournament("T", rounds_count=3)
with db.connect() as c: c.execute("UPDATE tournaments SET start_date='2026-03-01' WHERE id=?", (tid,))
db.replace_tournament_categories(tid, [{"name":"Sub-13","kind":"age","max_value":13},{"name":"Feminino","kind":"sex","sex":"F"}])
pid = db.create_player_from_member(tid, mid)
p = db.get_player(pid); print("jogador", p["category"], "|", p["categories"], "| sex:", repr(p["sex"]))
