"""Modo "imagem com campos" (template_kind = image_overlay).

Desenha a imagem importada cobrindo a página e sobrepõe apenas os dados
(saudação, nome-herói, texto, assinaturas, rodapé e código). Sem moldura, banner ou
selo gerados — a arte do usuário já traz o design. Posições vindas de
``layout.compute_zones`` para casarem com o guia de ``standard_size``.
"""
from __future__ import annotations

from typing import Any

from .layout import CM, compute_zones
from .palettes import Palette
from .renderer import CertificateContent, _wrap
from .surface import DrawingSurface


def render_overlay(surface: DrawingSurface, palette: Palette, content: CertificateContent,
                   background_image: Any | None = None) -> None:
    zones = compute_zones(surface.width, surface.height, "classic")
    surface.rect(0, 0, surface.width, surface.height, fill=palette.paper)
    if background_image is not None:
        surface.image(background_image, 0, 0, surface.width, surface.height, opacity=1.0)

    cx = zones.center_x
    if content.intro:
        surface.text(cx, zones.hero_y + 1.1 * CM, content.intro,
                     font="Times-Italic", size=12, fill=palette.muted, anchor="middle")
    surface.text(cx, zones.hero_y, content.name, font="Times-Roman", size=30, fill=palette.ink, anchor="middle")

    max_chars = max(20, int(zones.content_width / (12 * 0.52)))
    line_y = zones.hero_y - 1.35 * CM
    for line in _wrap(content.body, max_chars):
        surface.text(cx, line_y, line, font="Times-Roman", size=12, fill=palette.body, anchor="middle")
        line_y -= 18

    for frac, signature in ((0.50, content.signature_left), (0.74, content.signature_right)):
        if signature:
            surface.text(zones.width * frac, zones.footer_y - 0.3 * CM, signature,
                         font="Times-Italic", size=11, fill=palette.ink, anchor="middle")
    # O rodape do modelo (local e periodo) tambem sumia aqui, pelo mesmo motivo
    # do modo gerado: `adapter.build_inputs` o renderiza e ninguem o desenhava.
    if content.footer:
        surface.text(cx, zones.margin + 0.5 * CM, content.footer,
                     font="Times-Italic", size=9, fill=palette.muted, anchor="middle")
    if content.verification_code:
        surface.text(zones.content_right, zones.margin + 0.4 * CM,
                     f"Codigo {content.verification_code}", font="Helvetica", size=8,
                     fill=palette.muted, anchor="end")
