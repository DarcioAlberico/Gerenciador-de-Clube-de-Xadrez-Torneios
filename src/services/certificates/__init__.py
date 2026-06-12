"""Pacote de diplomas do Albericus — desenho modular e testável.

Fronteiras (ver ESPEC_DIPLOMAS.md):
- ``styles`` / ``palettes`` — dados puros dos 3 presets e das cores.
- ``text`` / ``layout`` — substituição de variáveis e geometria da página (puros).
- ``surface`` / ``shapes`` / ``renderer`` — desenho contra uma superfície
  abstrata (PDF via ReportLab, preview via Tk).
- ``gallery`` / ``standard_size`` / ``overlay`` — galeria de modelos, tamanho
  padrão de imagem e modo "imagem de fundo".

O ``CertificateService`` é a fachada: recipients, emissão e persistência; o
desenho é delegado a este pacote.
"""
from __future__ import annotations

from . import layout, palettes, styles, text
from .palettes import PALETTES, Palette, resolve_palette
from .styles import DEFAULT_STYLE_PRESET, STYLE_PRESETS, StylePreset, resolve_preset

__all__ = [
    "layout",
    "palettes",
    "styles",
    "text",
    "PALETTES",
    "Palette",
    "resolve_palette",
    "STYLE_PRESETS",
    "StylePreset",
    "resolve_preset",
    "DEFAULT_STYLE_PRESET",
]
