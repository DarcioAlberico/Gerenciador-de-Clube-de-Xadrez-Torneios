"""R10: a trilha audit_events registra o operador das configurações, não o usuário logado."""
import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import PairingService, SecurityService

with tempfile.TemporaryDirectory() as d:
    db = Database(Path(d) / "a.db", backup_dir=Path(d) / "bk")
    sec = SecurityService(db)
    # cria um usuário viewer como admin padrão (sem login = admin pelas configurações)
    sec.create_user("monitor", "segredo123", "viewer")
    assert sec.login("monitor", "segredo123")
    print("operador corrente:", sec.current_operator())
    ps = PairingService(db)
    tid = db.create_tournament("T", rounds_count=3)
    for i in range(4):
        db.create_player(tid, name=f"J{i}", rating=2000 - i * 10, club="C", category="Absoluto")
    r = ps.generate_next_round(tid)
    p = db.get_pairings_for_round(int(r["id"]))[0]
    ps.update_result(tid, int(p["id"]), "1-0")
    ev = [e for e in db.list_audit_events(tid) if "result" in e["action"]]
    print("audit_events:", [(e["action"], e["actor"], e["role"]) for e in ev][:3])
    print("audit_logs:", [(x["action"], x["actor"], x["role"]) for x in db.list_audit_logs(limit=5)])
