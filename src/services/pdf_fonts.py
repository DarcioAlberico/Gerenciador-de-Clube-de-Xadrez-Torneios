"""As fontes dos PDFs — uma decisão num lugar só (RG2-29).

Os PDFs usavam só as fontes embutidas do ReportLab (Helvetica, Times), que não
têm ``Ł``, ``Ć``, ``Ş`` nem ``ễ``: "Łukasz Ćwik Şahin Nguyễn" saía
"■ukasz ■wik ■ahin Nguy■n" — no IT3, que a FIDE exige com os adversários
estrangeiros, inclusive.

``install_pdf_fonts`` registra a DejaVu (empacotada em ``assets/fonts``, com a
licença ao lado) **nos nomes que o código já usa**. Assim nenhum dos ~100
``setFont("Helvetica…")`` muda, e os modelos de diploma gravados no banco com
"Times-Roman" continuam valendo. A variante **Condensed** foi escolhida por ter
a largura da Helvetica (a DejaVu Sans normal é ~10 % mais larga e estouraria as
súmulas e os cartões de mesa, desenhados na medida).

Quem cria um documento PDF chama ``install_pdf_fonts()`` antes; a varredura em
``tests/test_rg2_29_fonte_pdf.py`` reprova o módulo que cria ``Canvas`` ou
``DocTemplate`` sem chamar.
"""
from __future__ import annotations

from src.core.resources import bundled_resource

FONT_FILES: dict[str, str] = {
    "Helvetica": "DejaVuSansCondensed.ttf",
    "Helvetica-Bold": "DejaVuSansCondensed-Bold.ttf",
    "Helvetica-Oblique": "DejaVuSansCondensed-Oblique.ttf",
    "Helvetica-BoldOblique": "DejaVuSansCondensed-BoldOblique.ttf",
    "Times-Roman": "DejaVuSerifCondensed.ttf",
    "Times-Bold": "DejaVuSerifCondensed-Bold.ttf",
    "Times-Italic": "DejaVuSerifCondensed-Italic.ttf",
    "Times-BoldItalic": "DejaVuSerifCondensed-BoldItalic.ttf",
}

_FAMILIES = {
    "Helvetica": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
    "Times-Roman": ("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
}

_installed = False


def install_pdf_fonts() -> None:
    """Registra a DejaVu nos nomes Helvetica e Times. Chamar de novo não faz nada."""
    global _installed
    if _installed:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for name, filename in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(bundled_resource(f"assets/fonts/{filename}"))))
    for family, (normal, bold, italic, bold_italic) in _FAMILIES.items():
        pdfmetrics.registerFontFamily(family, normal=normal, bold=bold, italic=italic, boldItalic=bold_italic)
    _installed = True
