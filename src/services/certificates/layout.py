"""Cálculo de zonas/medidas da página do diploma (puro, em pontos PDF).

Divide a página em margens e faixas (cabeçalho, herói = nome, corpo, rodapé)
a partir das dimensões e do preset. Não desenha — só geometria. O ``renderer``
posiciona os elementos dentro destas zonas conforme o estilo.
"""
from __future__ import annotations

from dataclasses import dataclass

CM = 28.3464567  # 1 cm em pontos PDF (72/2.54)


@dataclass(frozen=True)
class PageZones:
    width: float
    height: float
    margin: float          # margem externa (moldura)
    inner_margin: float    # respiro interno do conteúdo
    banner_y: float        # base do banner/título superior
    hero_y: float          # linha-base do nome (herói)
    body_top: float        # topo do bloco de corpo
    body_bottom: float     # base do bloco de corpo
    footer_y: float        # linha das assinaturas
    content_left: float
    content_right: float

    @property
    def content_width(self) -> float:
        return self.content_right - self.content_left

    @property
    def center_x(self) -> float:
        return self.width / 2.0


def is_landscape(width: float, height: float) -> bool:
    return width >= height


def compute_zones(width: float, height: float, preset_key: str = "classic") -> PageZones:
    """Reparte a página em faixas. Retrato ganha mais altura de corpo."""
    margin = 1.1 * CM
    inner = 1.6 * CM
    content_left = margin + inner
    content_right = width - margin - inner

    # Herói (nome) ~62% da altura; corpo logo abaixo; rodapé fixo perto da base.
    hero_y = height * 0.60
    banner_y = height - margin - 1.0 * CM
    body_top = hero_y - 0.9 * CM
    footer_y = margin + 1.5 * CM
    body_bottom = footer_y + 1.2 * CM

    return PageZones(
        width=width,
        height=height,
        margin=margin,
        inner_margin=inner,
        banner_y=banner_y,
        hero_y=hero_y,
        body_top=body_top,
        body_bottom=body_bottom,
        footer_y=footer_y,
        content_left=content_left,
        content_right=content_right,
    )


def fit_font_size(text: str, max_width: float, base_size: float, char_factor: float = 0.5) -> float:
    """Reduz o corpo da fonte para o texto caber em ``max_width`` (estimativa)."""
    if not text:
        return base_size
    estimated = len(text) * base_size * char_factor
    if estimated <= max_width:
        return base_size
    return max(10.0, base_size * (max_width / estimated))
