import tempfile, os, time
from pathlib import Path
from src.core.database import Database
from src.services.security_service import SecurityService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
t0 = time.time() - 1000
mig = db.backup("before_schema_migration"); os.utime(mig, (t0, t0))
rest = db.backup("before_restore"); os.utime(rest, (t0+1, t0+1))
for i in range(12):
    p = db.backup_before("generate_round", tournament_id=None); os.utime(p, (t0+10+i, t0+10+i))
deleted = db.prune_backups(10)
print("apagados:", sorted(p.name.split("_2026")[0] for p in deleted))
