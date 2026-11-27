import tempfile
from pathlib import Path
from openpyxl import Workbook, load_workbook
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "a.xlsx"
    wb = Workbook(); ws = wb.active; ws.append(["=HYPERLINK(\"http://x\",\"a\")"]); wb.save(p)
    c = load_workbook(p)["Sheet"]["A1"]
    print(c.data_type, c.value)
