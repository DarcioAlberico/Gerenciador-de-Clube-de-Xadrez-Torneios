import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from tests.support.core_service_base import CoreServiceTestCase

class T(CoreServiceTestCase):
    def runTest(self):
        pass

t = T(); t.setUp()
db = t.db
tid = db.create_tournament("Copa <Sub-12> & Cia", rounds_count=3)
db.create_player(tid, name="=HYPERLINK(\"http://x\";\"a\")", rating=1500)
db.create_player(tid, name="Joao <i>", rating=1400)
with tempfile.TemporaryDirectory() as tmp:
    for ext in ("pdf", "csv"):
        for meth in ("export_players", "export_standings"):
            p = Path(tmp) / f"x.{ext}"
            try:
                getattr(t.export_service, meth)(tid, p)
                print(meth, ext, "OK", p.stat().st_size)
                if ext == "csv":
                    print(p.read_text(encoding="utf-8-sig")[:300])
            except Exception as e:
                print(meth, ext, "FAIL", type(e).__name__, str(e)[:200])
t.tearDown()
