import sys, tempfile, fitz
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from tests.support.core_service_base import CoreServiceTestCase
class T(CoreServiceTestCase):
    def runTest(self): pass
t = T(); t.setUp()
tid = t.db.create_tournament("Copa <Sub-12> & Cia", rounds_count=3)
t.db.create_player(tid, name="Joao <i>", rating=1400)
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "x.pdf"
    t.export_service.export_standings(tid, p)
    print(repr(fitz.open(str(p))[0].get_text()[:300]))
t.tearDown()
