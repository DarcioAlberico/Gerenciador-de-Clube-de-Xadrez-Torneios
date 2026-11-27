import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from tests.support.core_service_base import CoreServiceTestCase
from src.services.federation_exporters import TRF16Exporter, TRF25Exporter
from src.services.trf_import import parse_trf, build_trf_rounds

class T(CoreServiceTestCase):
    def runTest(self):
        pass

t = T()
t.setUp()
db = t.db
tid = t.tournament_id
a = db.create_player(tid, name="Ana Souza", surname="Souza", given_name="Ana", rating=1650, sex="F", title="WFM")
b = db.create_player(tid, name="Bruno Øster", surname="Øster", given_name="Bruno", rating=2100, international_rating=2100, sex="M", fide_id="123", federation_id="NOR")
c = db.create_player(tid, name="Carlos <b>X</b>", surname="Łukasz", given_name="Ćarl", rating=1800, international_rating=1800, sex="M")
d = db.create_player(tid, name="Dora", rating=1500, sex="F")
r = t.service.generate_next_round(tid)
t._fill_decisive_results(int(r["id"]))
t.service.close_round(tid, int(r["id"]))
txt = TRF16Exporter(t.export_service).render(tid)
print(txt)
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)/"a.trf"
    TRF25Exporter(t.export_service).export(tid, p)
    print(p.read_text(encoding="utf-8"))
    p2 = Path(tmp)/"b.trf"
    TRF16Exporter(t.export_service).export(tid, p2)
    res = t.import_service.import_trf(p2)
    print("import:", res)
    for pl in db.list_players(res["tournament_id"], active_only=False):
        print(pl["name"], "|", pl["sex"], "|", pl["rating"], pl["international_rating"], pl["title"])

# blank middle cell
line1 = "001    1 m    Alfa, A                           2000 BRA           1        2000/01/01  1.0    1          " + "   2 w 1  "
line2 = "001    2 m    Beta, B                           1900 BRA           2        2000/01/01  0.0    2          " + "   1 b 0  "
# build line where R1 blank then R2 played
base1 = "001    1 m    Alfa, A                           2000 BRA           1 2000/01/01  1.0    1  "
base2 = "001    2 m    Beta, B                           1900 BRA           2 2000/01/01  0.0    2  "
l1 = base1.ljust(91) + " " * 10 + "   2 w 1"
l2 = base2.ljust(91) + " " * 10 + "   1 b 0"
parsed = parse_trf("012 X\r\n" + l1 + "\r\n" + l2 + "\r\n")
print("blank-R1 cells:", [p_["rounds"] for p_ in parsed["players"]], "rounds_count", parsed["rounds_count"])
t.tearDown()
