import shutil, sqlite3, tempfile, sys
from pathlib import Path
from src.core.database import Database
for src in sys.argv[1:]:
    tmp = Path(tempfile.mkdtemp()); dst = tmp / "albericus.db"; shutil.copy2(src, dst)
    Database(dst, backup_dir=tmp / "bk")
    c = sqlite3.connect(dst)
    print(Path(src).name, "dist entry_round:", c.execute("select entry_round, count(*) from players group by 1").fetchall())
    bad = c.execute("""
      select p.id, p.tournament_id, p.entry_round, min(r.number)
      from players p join pairings g on g.white_player_id=p.id or g.black_player_id=p.id
      join rounds r on r.id=g.round_id
      group by p.id having min(r.number) < p.entry_round""").fetchall()
    print("  jogaram antes da entry_round:", len(bad), bad[:5])
