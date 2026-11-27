import sys, random
sys.path.insert(0, r"C:\PythonCurso\Albericus")
sys.path.insert(0, r"C:/Users/AMD/AppData/Local/Temp/claude/370b152fc45536df/643559b5-cf98-4a48-aa63-2c2e20aaeabd/scratchpad/r3")
import stress
from src.core.database import Database
orig_cleanup = None
# monkeypatch: capturar db antes do cleanup
import tempfile
captured = {}
_TD = tempfile.TemporaryDirectory
class Keep(_TD):
    def cleanup(self): pass
tempfile.TemporaryDirectory = Keep
_init = Database.__init__
def init(self, *a, **k):
    _init(self, *a, **k); captured.setdefault("db", self)
Database.__init__ = init
pr = stress.run(1, late=False)
print(pr)
db = captured["db"]
tid = 1
for rd in sorted(db.list_rounds(tid), key=lambda x: x["number"]):
    for p in db.get_pairings_for_round(int(rd["id"])):
        if 7 in (p["white_player_id"], p["black_player_id"]):
            print(rd["number"], p["board_number"], p["white_player_id"], p["black_player_id"], p["result"], p["is_bye"])
from src.services.pairing_service import PairingService
for row in PairingService(db).standings(tid)[:12]:
    print(row["player_id"], row["points"], row["name"])
print(db.list_requested_byes(tid))
