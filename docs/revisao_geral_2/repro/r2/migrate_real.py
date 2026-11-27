import shutil, sqlite3, tempfile, sys
from pathlib import Path
from src.core.database import Database
for src in sys.argv[1:]:
    tmp = Path(tempfile.mkdtemp())
    dst = tmp / "albericus.db"
    shutil.copy2(src, dst)
    c = sqlite3.connect(dst)
    v0 = c.execute("PRAGMA user_version").fetchone()[0]
    tabs = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
    before = {t: c.execute(f"select count(*) from [{t}]").fetchone()[0] for t in tabs}
    c.close()
    db = Database(dst, backup_dir=tmp / "bk")
    c = sqlite3.connect(dst)
    v1 = c.execute("PRAGMA user_version").fetchone()[0]
    after = {t: c.execute(f"select count(*) from [{t}]").fetchone()[0] for t in tabs}
    fk = c.execute("PRAGMA foreign_key_check").fetchall()
    ic = c.execute("PRAGMA integrity_check").fetchone()[0]
    diff = {t: (before[t], after[t]) for t in tabs if before[t] != after[t]}
    print(Path(src).name, "v", v0, "->", v1, "integrity", ic, "fk_violations", len(fk), "contagens alteradas", diff)
    if fk: print("  fk:", fk[:10])
    # segunda abertura: idempotente?
    Database(dst, backup_dir=tmp / "bk")
    c2 = sqlite3.connect(dst)
    again = {t: c2.execute(f"select count(*) from [{t}]").fetchone()[0] for t in tabs}
    print("  reabertura altera contagens?", {t: (after[t], again[t]) for t in tabs if after[t] != again[t]})
