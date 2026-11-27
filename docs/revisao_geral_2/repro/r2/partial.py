import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import PairingService, TournamentService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
ts = TournamentService(db); ps = PairingService(db)
tid = ts.create_tournament({"name": "Aberto", "rounds_count": "5", "bye_points": "1"})
pids = [db.create_player(tid, name=f"J{i}", rating=2000 - 10*i) for i in range(6)]
orig = db.add_player_status_event
def boom(*a, **k): raise RuntimeError("falha simulada no evento")
db.add_player_status_event = boom
try:
    ps.set_player_participation(tid, pids[0], "withdrawn", reason="Desistiu")
except Exception as e:
    print("exceção:", e)
db.add_player_status_event = orig
print("status gravado:", db.get_player(pids[0])["player_status"], "| eventos:", len(db.list_player_status_events(tid)))
# geração individual: falha depois de gravar a rodada
orig_audit = db.create_audit_event
def audit(**kw):
    if kw.get("action") == "round_generated": raise RuntimeError("falha simulada na auditoria")
    return orig_audit(**kw)
db.create_audit_event = audit
try:
    ps.generate_next_round(tid)
except Exception as e:
    print("exceção:", e)
db.create_audit_event = orig_audit
r = db.list_rounds(tid)
print("rodadas gravadas:", [(x["number"], x["status"]) for x in r], "| status torneio:", db.get_tournament(tid)["status"],
      "| eventos round_generated:", len(db.list_audit_events(tid, action="round_generated", limit=100)))
