"""Tamanho padrão de imagem dos diplomas e guia de arte (modo image_overlay).

Define as dimensões A4 a 300 DPI que o usuário deve usar para criar a arte do
fundo fora do app, e desenha um "guia" (margens + zonas de texto marcadas) para
ele posicionar o desenho. O preenchimento dos dados sobre a imagem importada
fica em ``overlay.py``. Desenho via ``DrawingSurface`` (sem ReportLab direto).
"""
from __future__ import annotations

from .layout import CM, compute_zones
from .surface import DrawingSurface

STANDARD_DPI = 300
# A4 em pixels a 300 DPI — o usuário exporta a arte exatamente neste tamanho.
A4_LANDSCAPE_PX = (3508, 2480)
A4_PORTRAIT_PX = (2480, 3508)
# A4 em pontos PDF (o que o canvas usa).
A4_LANDSCAPE_PT = (841.89, 595.28)
A4_PORTRAIT_PT = (595.28, 841.89)


def standard_pixels(orientation: str = "landscape") -> tuple[int, int]:
    """Dimensão recomendada da arte importada (px a 300 DPI)."""
    return A4_PORTRAIT_PX if orientation == "portrait" else A4_LANDSCAPE_PX


def page_points(orientation: str = "landscape") -> tuple[float, float]:
    return A4_PORTRAIT_PT if orientation == "portrait" else A4_LANDSCAPE_PT


def render_guide(surface: DrawingSurface, orientation: str = "landscape") -> None:
    """Desenha o guia: borda da página, área segura e as zonas de cada campo."""
    zones = compute_zones(surface.width, surface.height, "classic")
    ink, gold, muted = "#1E3A8A", "#C9A227", "#94A3B8"
    width_px, height_px = standard_pixels(orientation)
    cx = zones.center_x

    surface.rect(0, 0, surface.width, surface.height, fill="#FFFFFF")
    surface.rect(zones.margin, zones.margin, surface.width - 2 * zones.margin,
                 surface.height - 2 * zones.margin, stroke=muted, line_width=1.0, dash=(4, 4))

    def zone(y: float, height: float, label: str) -> None:
        surface.rect(zones.content_left, y, zones.content_width, height,
                     stroke=gold, line_width=0.8, dash=(2, 3))
        surface.text(zones.content_left + 0.2 * CM, y + height - 0.45 * CM, label,
                     font="Helvetica", size=9, fill=muted, anchor="start")

    zone(zones.hero_y + 0.7 * CM, 0.9 * CM, "titulo / saudacao")
    zone(zones.hero_y - 0.5 * CM, 1.1 * CM, "NOME DO PREMIADO")
    zone(zones.body_top - 2.0 * CM, 1.8 * CM, "texto do diploma")
    zone(zones.footer_y - 0.4 * CM, 1.0 * CM, "assinaturas")

    surface.text(cx, zones.hero_y, "[ NOME DO PREMIADO ]", font="Helvetica-Bold",
                 size=20, fill=ink, anchor="middle")
    surface.text(cx, zones.margin + 0.7 * CM,
                 f"Guia de arte A4 {orientation} — desenhe o fundo em {width_px}x{height_px}px (300 DPI); "
                 "os campos serao sobrepostos nas areas tracejadas.",
                 font="Helvetica", size=9, fill=muted, anchor="middle")
