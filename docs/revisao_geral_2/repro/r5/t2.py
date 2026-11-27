import sys, tempfile, importlib.util
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
d = Path(r"C:\Users\AMD\AppData\Local\Temp\claude\370b152fc45536df\643559b5-cf98-4a48-aa63-2c2e20aaeabd\scratchpad\r5")
p = d / "glyph.pdf"
c = canvas.Canvas(str(p))
c.setFont("Helvetica", 14)
c.drawString(50, 700, "Lukasz: Łukasz Ćwik Şahin Nguyễn Ğ ø é ç")
c.save()
for mod in ("fitz", "pypdf"):
    print(mod, importlib.util.find_spec(mod) is not None)
try:
    import fitz
    doc = fitz.open(str(p))
    print(repr(doc[0].get_text()))
except Exception as e:
    print("fitz err", e)
try:
    import pypdf
    print(repr(pypdf.PdfReader(str(p)).pages[0].extract_text()))
except Exception as e:
    print("pypdf err", e)
name = "Maria Eduarda dos Santos Albuquerque Cavalcanti de Oliveira"
from reportlab.lib.pagesizes import A4, landscape
print("name width pt", stringWidth(name, "Times-Roman", 30), "page width", landscape(A4)[0])
