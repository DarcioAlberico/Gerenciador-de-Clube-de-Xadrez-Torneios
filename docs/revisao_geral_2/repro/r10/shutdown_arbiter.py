"""R10: árbitro (e qualquer papel sem settings_write) fecha o app sem backup."""
import tempfile
from pathlib import Path
from src.core.database import Database
from src.core.services import SecurityService

with tempfile.TemporaryDirectory() as d:
    db = Database(Path(d) / "a.db", backup_dir=Path(d) / "bk")
    sec = SecurityService(db)
    sec.create_user("arb", "senha-arb", "arbiter")
    assert sec.login("arb", "senha-arb")
    try:
        sec.create_backup("auto_shutdown")
        print("backup criado")
    except Exception as exc:
        print("auto_shutdown falhou:", type(exc).__name__, exc)
    print("arquivos na pasta de backup:", sorted(p.name for p in (Path(d) / "bk").glob("*.db")))
    print("audit:", [(x["action"], x["actor"], x["role"]) for x in db.list_audit_logs(limit=3)])
