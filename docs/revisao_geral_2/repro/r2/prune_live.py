import tempfile, time, os
from pathlib import Path
from src.core.database import Database
tmp = Path(tempfile.mkdtemp())
data = tmp / "dados"
db = Database(db_path=data / "albericus.db", backup_dir=data)  # usuário escolheu a própria pasta de dados
db.create_tournament if False else None
os.utime(db.db_path, (time.time()-100, time.time()-100))
for i in range(3):
    db.backup(f"manual{i}")
print("antes:", sorted(p.name for p in data.glob("*.db")))
deleted = db.prune_backups(2)
print("apagados:", [p.name for p in deleted])
print("banco vivo existe?", db.db_path.exists())
