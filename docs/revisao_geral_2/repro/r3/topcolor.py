import sys, tempfile, logging
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
logging.disable(logging.WARNING)
from src.core.database import Database
from src.services.pairing_service import PairingService
CFG = {"pairing_method": "swiss", "time_control": "10 min", "chief_arbiter": "A",
       "federation": "BRA", "location": "SP", "start_date": "2026-06-09", "end_date": "2026-06-09",
       "pairing_system": "gacrux_swiss", "initial_color": "W"}
out = []
for trial in range(3):
    tmp = tempfile.mkdtemp()
    db = Database(db_path=Path(tmp) / "t.db", backup_dir=Path(tmp) / "bk")
    s = PairingService(db)
    tid = db.create_tournament("S", rounds_count=5, bye_points=1.0)
    db.save_tournament_settings(tid, CFG)
    ids = [db.create_player(tid, f"J{i}", rating=2200 - 50 * i, sex="m", birth_date="2000") for i in range(7)]
    rd = s.generate_next_round(tid)
    ps = db.get_pairings_for_round(int(rd["id"]))
    top = [p for p in ps if not p["is_bye"]][0]
    s.swap_pairing_colors(tid, int(rd["id"]), int(top["id"]), reason="erro de mesa")
    for p in db.get_pairings_for_round(int(rd["id"])):
        if not p["is_bye"]:
            s.update_result(tid, int(p["id"]), "1/2-1/2")
    s.close_round(tid, int(rd["id"]))
    rd2 = s.generate_next_round(tid)
    evs = [e["reason"][:300] for e in db.list_audit_events(tid, action="pairing_check", limit=5) if int(e["round_id"]) == int(rd2["id"])]
    print("R2:", evs)
