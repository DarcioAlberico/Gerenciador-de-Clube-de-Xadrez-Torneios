import sys, tempfile, logging
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from src.core.database import Database
from src.services.pairing_service import PairingService
from src.services.pairing.gacrux_engine import GacruxEngine
logging.basicConfig(level=logging.ERROR, format="%(message)s")
CFG = {"pairing_method": "swiss", "time_control": "10 min", "chief_arbiter": "A",
       "federation": "BRA", "location": "SP", "start_date": "2026-06-09", "end_date": "2026-06-09",
       "pairing_system": "gacrux_swiss", "initial_color": "W"}
pts = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
tmp = tempfile.mkdtemp()
db = Database(db_path=Path(tmp) / "t.db", backup_dir=Path(tmp) / "bk")
s = PairingService(db)
tid = db.create_tournament("S", rounds_count=5, bye_points=1.0)
db.save_tournament_settings(tid, CFG)
ids = [db.create_player(tid, f"J{i}", rating=2200 - 50 * i, sex="m", birth_date="2000") for i in range(6)]
for r in (1, 2):
    rd = s.generate_next_round(tid)
    for p in db.get_pairings_for_round(int(rd["id"])):
        if not p["is_bye"]:
            s.update_result(tid, int(p["id"]), "1-0")
    s.close_round(tid, int(rd["id"]))
res = s.register_late_entry(tid, {"name": "Tardio", "rating": 1900, "sex": "m", "birth_date": "2000"}, pts)
print("late:", res)
rd = s.generate_next_round(tid)
print("R3 gerada:", [(p["white_player_id"], p["black_player_id"], p["result"]) for p in db.get_pairings_for_round(int(rd["id"]))])
for e in db.list_audit_events(tid, action="pairing_check_unverified", limit=5):
    print("UNVERIFIED:", e["reason"])
for e in db.list_audit_events(tid, action="pairing_check", limit=5):
    print("CHECK:", e["reason"][:200])
st = s.standings(tid)
print([(r["name"], r["points"]) for r in st])
print("engine report:", getattr(s, "last_engine_report", None))
for e in db.list_audit_events(tid, action="tiebreak_engine_fallback", limit=5):
    print("TB FALLBACK:", e["reason"][:400])
import shutil
orig = GacruxEngine._run_checker
def spy(cmd, output_path, round_number, input_path):
    shutil.copy(input_path, Path(tmp) / "check_copy.trf")
    print("CMD:", cmd[-8:])
    return orig(cmd, output_path, round_number, input_path)
GacruxEngine._run_checker = staticmethod(spy)
print(GacruxEngine(db).check_round(tid, 3).summary())
print(open(Path(tmp) / "check_copy.trf", encoding="utf-8").read())
