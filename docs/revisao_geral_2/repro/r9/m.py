import sys,sqlite3,shutil,traceback
from src.core.database import Database
for f in sys.argv[1:]:
    try:
        db=Database(f)
        c=sqlite3.connect(f)
        print(f[-30:], c.execute('pragma user_version').fetchone(), c.execute('pragma integrity_check').fetchone(), c.execute('pragma foreign_key_check').fetchall()[:3])
    except Exception:
        traceback.print_exc()
