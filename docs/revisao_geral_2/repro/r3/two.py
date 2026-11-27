import sys, tempfile, logging
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
logging.disable(logging.WARNING)
from src.core.database import Database
from src.services.pairing_service import PairingService
CFG = {"pairing_method": "swiss", "time_control": "10 min", "chief_arbiter": "A",
       "federation": "BRA", "location": "SP", "start_date": "2026-06-09", "end_date": "2026-06-09",
       "pairing_system": "gacrux_swiss", "initial_color": "W"}
for n in (2, 3):
    tmp = tempfile.mkdtemp()
    db = Database(db_path=Path(tmp) / "t.db", backup_dir=Path(tmp) / "bk")
    s = PairingService(db)
    tid = db.create_tournament("S", rounds_count=4, bye_points=1.0)
    db.save_tournament_settings(tid, CFG)
    ids = [db.create_player(tid, f"J{i}", rating=2200 - 50 * i, sex="m", birth_date="2000") for i in range(n)]
    for r in range(1, 5):
        try:
            rd = s.generate_next_round(tid)
        except Exception as e:
            print(n, r, type(e).__name__, str(e)[-500:].replace("\n", " | "))
            try:
                rd = s.generate_next_round(tid, reserve_engine=True)
            except Exception as e2:
                print("  reserve:", type(e2).__name__, str(e2)[:200].replace("\n"," | ")); break
        ps = db.get_pairings_for_round(int(rd["id"]))
        print(n, r, [(p["white_player_id"], p["black_player_id"], p["result"]) for p in ps])
        for p in ps:
            if not p["is_bye"]:
                s.update_result(tid, int(p["id"]), "1-0")
        s.close_round(tid, int(rd["id"]))
