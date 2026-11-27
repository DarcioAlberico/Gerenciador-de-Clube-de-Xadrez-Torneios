import sys, time, tracemalloc, tempfile, os
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from src.services.fide_list import parse_rating_list
from src.core.database import Database

def line(i):
    s = f"{i:<15}{('Surname'+str(i)+', Given'):<61}{'BRA':<4}{'M':<4}{'':<5}{'':<5}{'':<15}{'':<4}{'1850':<6}{'0':<4}{'40':<3}{'1990':<6}"
    return s
N = 50000
lines = [line(100000 + i) for i in range(N)]
tracemalloc.start()
players, errors = parse_rating_list(lines)
cur, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print("parsed", len(players), "errors", errors[:2], "bytes/player", peak / N)
print("sample", players[0])
with tempfile.TemporaryDirectory() as tmp:
    db = Database(Path(tmp) / "a.db", backup_dir=Path(tmp) / "b")
    base = os.path.getsize(Path(tmp) / "a.db")
    t0 = time.time()
    db.create_official_rating_snapshot_with_players(source="FIDE", list_date="2026-11-01", file_name="x", players=players)
    t1 = time.time()
    db.create_official_rating_snapshot_with_players(source="FIDE", list_date="2026-12-01", file_name="x", players=players)
    print("insert s/50k", t1 - t0, "db growth bytes per import", (os.path.getsize(Path(tmp) / "a.db") - base) / 2)
    t2 = time.time()
    for k in range(200):
        db.find_latest_official_player(fide_id=str(100000 + k * 7))
    print("lookup ms", (time.time() - t2) / 200 * 1000)
