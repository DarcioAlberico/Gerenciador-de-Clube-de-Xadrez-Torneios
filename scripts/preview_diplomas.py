"""Gera um PDF de amostra com os 3 presets de diploma (premiacao + participacao).

Ferramenta de desenvolvimento: exercita o pacote ``src.services.certificates``
de ponta a ponta no backend ReportLab, sem tocar no banco. Uso::

    python scripts/preview_diplomas.py            # gera e abre o PDF
    python scripts/preview_diplomas.py --no-open  # so gera

Saida: ``%TEMP%/amostras_diplomas.pdf`` (6 paginas).
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from src.services.certificates import text as ctext
from src.services.certificates.gallery import build_gallery
from src.services.certificates.palettes import DEFAULT_PALETTE_BY_PRESET, resolve_palette
from src.services.certificates.renderer import CertificateContent, RenderOptions, render_certificate
from src.services.certificates.styles import STYLE_PRESETS
from src.services.certificates.surface import ReportLabSurface

_TORNEIO = "Torneio Aberto de Teresina 2026"
_NAMES = [
    "Gabriel Alberico", "Marina Costa", "Heitor Lima", "Sofia Andrade", "Rafael Nunes",
    "Helena Dias", "Bernardo Sa", "Laura Pires", "Theo Macedo", "Alice Rocha",
    "Davi Mendes", "Luiza Castro", "Miguel Aragao", "Valentina Reis", "Arthur Gomes",
    "Cecilia Brito", "Noah Farias", "Isadora Melo", "Pedro Tavares", "Manuela Pinto",
]
_SAMPLE = {
    "tournament": _TORNEIO, "position_label": "1o", "position": "1", "points": "6,5",
    "category": "Sub-14", "category_position_label": "1o", "session": "Aula de Finais de Torre",
    "event": "Festival de Xadrez do Clube", "date_range": "12/06/2026",
}


def _content_for(model, idx: int) -> CertificateContent:
    """Constrói o conteúdo de exemplo de um modelo da galeria."""
    name = _NAMES[idx % len(_NAMES)]
    variables = ctext.build_variables({**_SAMPLE, "name": name})
    body = ctext.render_plain(model.body_template, variables)
    award = model.is_award
    return CertificateContent(
        title=model.title_template,
        intro="concedido a" if award else "Certificamos que",
        name=name,
        body=body,
        footer="Teresina-PI - 12/06/2026",
        signature_left="Direcao",
        signature_right="Arbitragem",
        source_title=_TORNEIO,
        verification_code=f"ALB-{1000 + idx:04X}",
        position=1 if award else 0,
        seal_label="1o" if award else "",
    )


def render_gallery(count: int = 20, open_after: bool = True) -> str:
    width, height = landscape(A4)
    out_path = os.path.join(tempfile.gettempdir(), "galeria_diplomas.pdf")
    pdf = canvas.Canvas(out_path, pagesize=(width, height))
    for i, model in enumerate(build_gallery(count)):
        preset = STYLE_PRESETS[model.style_preset]
        palette = resolve_palette(model.palette_key, model.style_preset)
        surface = ReportLabSurface(pdf, width, height)
        render_certificate(surface, preset, palette, _content_for(model, i), RenderOptions())
        pdf.showPage()
    pdf.save()
    print("Galeria gerada:", out_path)
    if open_after and hasattr(os, "startfile"):
        os.startfile(out_path)  # type: ignore[attr-defined]
    return out_path


def _award(preset_name: str) -> CertificateContent:
    return CertificateContent(
        title="Certificado de Premiacao",
        intro=f"O {preset_name} certifica que",
        name="Gabriel Alberico",
        body=f"conquistou o 1o lugar no {_TORNEIO}, com 6,5 pontos em 7 rodadas.",
        footer="Teresina-PI - 12/06/2026",
        signature_left="Direcao",
        signature_right="Arbitragem",
        source_title=_TORNEIO,
        verification_code="ALB-1A2B",
        position=1,
        seal_label="1o",
    )


def _participation(preset_name: str) -> CertificateContent:
    return CertificateContent(
        title="Certificado de Participacao",
        intro="Certificamos que",
        name="Marina Costa",
        body=f"participou do {_TORNEIO}, classificando-se na 5a colocacao geral.",
        footer="Teresina-PI - 12/06/2026",
        signature_left="Direcao",
        signature_right="Arbitragem",
        source_title=_TORNEIO,
        verification_code="ALB-9Z8Y",
        position=0,
    )


def main(open_after: bool = True) -> str:
    width, height = landscape(A4)
    out_path = os.path.join(tempfile.gettempdir(), "diplomas_estilos.pdf")
    pdf = canvas.Canvas(out_path, pagesize=(width, height))

    for preset_key, preset in STYLE_PRESETS.items():
        palette = resolve_palette(DEFAULT_PALETTE_BY_PRESET.get(preset_key, ""), preset_key)
        surface = ReportLabSurface(pdf, width, height)
        render_certificate(surface, preset, palette, _award(preset.name), RenderOptions())
        pdf.showPage()
    pdf.save()
    print("PDF gerado:", out_path)
    if open_after and hasattr(os, "startfile"):
        os.startfile(out_path)  # type: ignore[attr-defined]
    return out_path


if __name__ == "__main__":
    _open = "--no-open" not in sys.argv
    if "--gallery" in sys.argv:
        _i = sys.argv.index("--gallery")
        _n = int(sys.argv[_i + 1]) if _i + 1 < len(sys.argv) and sys.argv[_i + 1].isdigit() else 20
        render_gallery(_n, open_after=_open)
    else:
        main(open_after=_open)
