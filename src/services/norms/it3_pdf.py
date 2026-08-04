"""Desenho do certificado IT3 em PDF (reportlab).

Único módulo do pacote com I/O: recebe um ``IT3Certificate`` já pronto e o
transforma em papel. Se o modelo estiver certo, o desenho é só desenho — foi
para isso que o modelo ficou puro em ``it3``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from src.services.constants import AppError
from src.services.norms.it3 import DISCLAIMER, IT3Certificate, IT3Game

_COLUMNS: tuple[tuple[str, float, str], ...] = (
    ("Rd", 12.0, "center"),
    ("Opponent", 68.0, "left"),
    ("Fed", 14.0, "center"),
    ("Title", 14.0, "center"),
    ("Rating", 20.0, "center"),
    ("Used", 20.0, "center"),
    ("Col", 14.0, "center"),
    ("Res", 18.0, "center"),
)


def _fitted(text: object, max_width: float, font: str, size: float) -> str:
    """Encurta com reticências o que não couber na coluna."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    value = str(text or "")
    if stringWidth(value, font, size) <= max_width:
        return value
    while value and stringWidth(f"{value}...", font, size) > max_width:
        value = value[:-1]
    return f"{value}..."


def _game_cells(game: IT3Game) -> tuple[str, ...]:
    return (
        str(game.round_number or ""),
        game.opponent_name,
        game.federation,
        game.title,
        str(game.rating) if game.rating > 0 else "-",
        str(game.rating_used),
        game.color,
        game.result,
    )


class _Sheet:
    """Cursor de desenho: sabe onde está a linha e quando virar a página."""

    def __init__(self, document: Any, page_width: float, page_height: float, margin: float) -> None:
        self.document = document
        self.page_width = page_width
        self.page_height = page_height
        self.margin = margin
        self.content_width = page_width - 2 * margin
        self.y = page_height - margin

    def space(self, amount: float) -> None:
        self.y -= amount

    def ensure(self, needed: float) -> None:
        if self.y - needed < self.margin:
            self.document.showPage()
            self.y = self.page_height - self.margin

    def text(self, value: str, font: str = "Helvetica", size: float = 9.0, indent: float = 0.0) -> None:
        self.ensure(size + 2)
        self.document.setFont(font, size)
        self.document.drawString(self.margin + indent, self.y, value)
        self.y -= size + 2

    def paragraph(self, value: str, font: str = "Helvetica", size: float = 9.0) -> None:
        """Quebra o texto na largura do papel — `text` não quebra, e deve mesmo."""
        from reportlab.pdfbase.pdfmetrics import stringWidth

        line = ""
        for word in str(value).split():
            candidate = f"{line} {word}".strip()
            if line and stringWidth(candidate, font, size) > self.content_width:
                self.text(line, font, size)
                line = word
            else:
                line = candidate
        if line:
            self.text(line, font, size)

    def rule(self, gap: float = 3.0) -> None:
        self.ensure(gap + 1)
        self.document.setLineWidth(0.4)
        self.document.line(self.margin, self.y, self.margin + self.content_width, self.y)
        self.y -= gap


def _draw_header(sheet: _Sheet, certificate: IT3Certificate, mm: float) -> None:
    document = sheet.document
    document.setFillGray(0.90)
    document.rect(sheet.margin, sheet.y - 13 * mm, sheet.content_width, 13 * mm, fill=1, stroke=0)
    document.setFillGray(0)
    document.setFont("Helvetica-Bold", 15)
    document.drawString(sheet.margin + 3 * mm, sheet.y - 6 * mm, "IT3 - TITLE NORM CERTIFICATE")
    document.setFont("Helvetica", 9)
    document.drawString(
        sheet.margin + 3 * mm,
        sheet.y - 10.5 * mm,
        f"Norm applied for: {certificate.norm_title} - {certificate.norm_label}",
    )
    document.drawRightString(
        sheet.margin + sheet.content_width - 3 * mm,
        sheet.y - 10.5 * mm,
        "FIDE Handbook B.01, section 1.4",
    )
    sheet.y -= 13 * mm + 5 * mm


def _draw_fields(sheet: _Sheet, title: str, fields: Sequence[tuple[str, str]], mm: float) -> None:
    sheet.ensure(10 * mm)
    sheet.document.setFont("Helvetica-Bold", 10)
    sheet.document.drawString(sheet.margin, sheet.y, title)
    sheet.y -= 5 * mm
    sheet.rule(2 * mm)

    column_width = sheet.content_width / 2
    for index in range(0, len(fields), 2):
        row = fields[index : index + 2]
        sheet.ensure(6 * mm)
        for position, (label, value) in enumerate(row):
            x = sheet.margin + position * column_width
            sheet.document.setFont("Helvetica", 7.5)
            sheet.document.setFillGray(0.35)
            sheet.document.drawString(x, sheet.y, label.upper())
            sheet.document.setFillGray(0)
            sheet.document.setFont("Helvetica-Bold", 9.5)
            sheet.document.drawString(
                x,
                sheet.y - 4.2 * mm,
                _fitted(value or "-", column_width - 4 * mm, "Helvetica-Bold", 9.5),
            )
        sheet.y -= 8.5 * mm
    sheet.y -= 1.5 * mm


def _draw_games(sheet: _Sheet, games: Sequence[IT3Game], mm: float) -> None:
    document = sheet.document
    widths = [width * mm for _label, width, _align in _COLUMNS]
    positions = [sheet.margin]
    for width in widths:
        positions.append(positions[-1] + width)
    row_height = 5.6 * mm

    def header() -> None:
        sheet.ensure(row_height * 2)
        document.setFillGray(0.88)
        document.rect(sheet.margin, sheet.y - row_height, sum(widths), row_height, fill=1, stroke=0)
        document.setFillGray(0)
        document.setFont("Helvetica-Bold", 8)
        for index, (label, _width, align) in enumerate(_COLUMNS):
            _cell(index, label, align, 8, "Helvetica-Bold")
        sheet.y -= row_height

    def _cell(index: int, value: str, align: str, size: float, font: str) -> None:
        left, right = positions[index], positions[index + 1]
        baseline = sheet.y - row_height + 1.8 * mm
        text = _fitted(value, right - left - 2 * mm, font, size)
        if align == "center":
            document.drawCentredString((left + right) / 2, baseline, text)
        else:
            document.drawString(left + 1.5 * mm, baseline, text)

    sheet.ensure(12 * mm)
    document.setFont("Helvetica-Bold", 10)
    document.drawString(sheet.margin, sheet.y, "Games")
    sheet.y -= 5 * mm
    header()

    document.setFont("Helvetica", 8.5)
    for game in games:
        if sheet.y - row_height < sheet.margin:
            document.showPage()
            sheet.y = sheet.page_height - sheet.margin
            header()
            document.setFont("Helvetica", 8.5)
        for index, (value, (_label, _width, align)) in enumerate(zip(_game_cells(game), _COLUMNS)):
            _cell(index, value, align, 8.5, "Helvetica")
        document.setLineWidth(0.25)
        document.line(sheet.margin, sheet.y - row_height, sheet.margin + sum(widths), sheet.y - row_height)
        sheet.y -= row_height
    sheet.y -= 4 * mm


def _draw_signature(sheet: _Sheet, certificate: IT3Certificate, mm: float) -> None:
    sheet.ensure(28 * mm)
    sheet.y -= 8 * mm
    half = sheet.content_width / 2
    for position, label in enumerate(("Chief Arbiter", "Date / Place")):
        x = sheet.margin + position * half
        sheet.document.setLineWidth(0.5)
        sheet.document.line(x, sheet.y, x + half - 12 * mm, sheet.y)
        sheet.document.setFont("Helvetica", 8)
        sheet.document.drawString(x, sheet.y - 4 * mm, label)
    sheet.document.setFont("Helvetica", 8.5)
    sheet.document.drawString(sheet.margin, sheet.y + 2 * mm, certificate.chief_arbiter)
    sheet.y -= 10 * mm


def _draw_certificate(sheet: _Sheet, certificate: IT3Certificate, mm: float) -> None:
    _draw_header(sheet, certificate, mm)
    _draw_fields(
        sheet,
        "Tournament",
        [
            ("Tournament name", certificate.tournament_name),
            ("FIDE event ID", certificate.event_id),
            ("Place", certificate.location),
            ("Organizing federation", certificate.organizing_federation),
            ("From", certificate.start_date),
            ("To", certificate.end_date),
            ("Type of tournament", certificate.tournament_type),
            ("Rate of play", certificate.time_control),
            ("Number of rounds", str(certificate.rounds or "-")),
            ("Chief arbiter", certificate.chief_arbiter),
        ],
        mm,
    )
    _draw_fields(
        sheet,
        "Candidate",
        [
            ("Name", certificate.candidate_name),
            ("FIDE ID", certificate.candidate_fide_id),
            ("Federation", certificate.candidate_federation),
            ("Rating", str(certificate.candidate_rating or "-")),
            ("Title held", certificate.candidate_title or "-"),
            ("Norm", f"{certificate.norm_title} ({certificate.norm_label})"),
        ],
        mm,
    )
    _draw_games(sheet, certificate.games, mm)
    _draw_fields(
        sheet,
        "Norm summary",
        [
            ("Games played", str(certificate.game_count)),
            ("Score", f"{certificate.score:g}"),
            ("Average rating of opponents (Ra)", f"{certificate.average_opponent:g}"),
            ("Rating performance (Rp)", str(certificate.performance)),
            ("Title holders among opponents", str(certificate.title_holders)),
            (
                f"Opponents titled {certificate.level_label}",
                str(certificate.level_title_holders),
            ),
            ("Federations other than candidate's", str(certificate.other_federations)),
            ("All indicators met", "YES" if certificate.meets else "NO"),
        ],
        mm,
    )

    if certificate.missing:
        sheet.text("Pendências apontadas pelo Handbook B.01:", "Helvetica-Bold", 9)
        for item in certificate.missing:
            sheet.text(f"- {item}", "Helvetica", 8, indent=3 * mm)
        sheet.space(2 * mm)

    _draw_signature(sheet, certificate, mm)
    sheet.paragraph(DISCLAIMER, "Helvetica-Oblique", 7.5)


def write_it3_pdf(certificates: Sequence[IT3Certificate], file_path: str | Path) -> Path:
    """Escreve um IT3 por norma detectada. Devolve o caminho, sempre `.pdf`."""
    if not certificates:
        raise AppError("Nenhuma norma para certificar.")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise AppError("Instale reportlab para exportar o certificado IT3 em PDF.") from exc

    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = A4
    document = canvas.Canvas(str(path), pagesize=A4)
    first = certificates[0]
    document.setTitle(f"IT3 {first.norm_title} - {first.candidate_name}")

    for certificate in certificates:
        sheet = _Sheet(document, page_width, page_height, 15 * mm)
        _draw_certificate(sheet, certificate, mm)
        document.showPage()

    document.save()
    return path
