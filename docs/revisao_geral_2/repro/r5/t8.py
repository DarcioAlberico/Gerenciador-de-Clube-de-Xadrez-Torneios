import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from tests.support.core_service_base import CoreServiceTestCase
class T(CoreServiceTestCase):
    def runTest(self): pass
t = T(); t.setUp()
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "cbx.csv"
    p.write_bytes("ID;Nome;Rating\n12345;João Ãngelo;1800\n".encode("cp1252"))
    try:
        print(t.official_rating_service.import_official_csv(p, "CBX"))
    except Exception as e:
        print("FAIL", type(e).__name__, str(e)[:150])
    try:
        print(t.official_rating_service.import_foreign_list(p, "POR"))
    except Exception as e:
        print("FAIL foreign", type(e).__name__, str(e)[:150])
t.tearDown()
