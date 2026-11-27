import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from tests.support.core_service_base import CoreServiceTestCase
from src.services.federation_exporters import TRF16Exporter

class T(CoreServiceTestCase):
    def runTest(self): pass

t = T(); t.setUp()
tid = t.tournament_id
t._create_players(6)
r1 = t.service.generate_next_round(tid)
t._fill_decisive_results(int(r1["id"]))
t.service.close_round(tid, int(r1["id"]))
r2 = t.service.generate_next_round(tid)   # R2 pareada, sem resultado
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "a.trf"
    w = TRF16Exporter(t.export_service).export(tid, p)
    print([l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("001")][:2])
    res = t.import_service.import_trf(p)
    print(res)
    nt = res["tournament_id"]
    for rd in t.db.list_rounds(nt):
        prs = t.db.get_pairings_for_round(rd["id"])
        print("round", rd["number"], rd["status"], [pr["result"] for pr in prs])
    print("tournament rounds_count", t.db.get_tournament(nt)["rounds_count"])
t.tearDown()
