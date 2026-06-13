"""Presets de estilo dos diplomas (dados puros, sem ReportLab/Tk).

Um preset descreve *como* um diploma é montado — fontes (built-in do
ReportLab), tipo de moldura, banner, selo, alinhamento do nome e marca d'água
padrão — sem desenhar nada. O desenho concreto fica em ``shapes.py`` /
``renderer.py``, que consomem estes valores. Puro e testável isolado.
"""
from __future__ import annotations

from dataclasses import dataclass

# Vocabulário fechado dos campos (validado em styles e no serviço).
BORDER_KINDS = ("double_rule", "rounded", "side_band", "chess_strip")
CORNER_MOTIFS = ("chess", "dots", "none")
BANNERS = ("bar", "pill", "label_caps", "none")
SEAL_SHAPES = ("rosette", "medal", "ring", "none")
NAME_ALIGNS = ("center", "left")
WATERMARKS = ("knight", "rook", "king", "queen", "pawn", "board", "numeral", "image", "none")


@dataclass(frozen=True)
class StylePreset:
    """Receita visual de um estilo. Fontes são nomes built-in do ReportLab."""

    key: str
    name: str
    title_font: str
    name_font: str
    body_font: str
    meta_font: str       # itálico/leve para "concedido a", assinaturas
    border_kind: str
    corner_motif: str
    banner: str
    seal_shape: str
    name_align: str
    default_watermark: str
    title_size: int = 16
    name_size: int = 30
    body_size: int = 12


CLASSIC = StylePreset(
    key="classic",
    name="Clássico",
    title_font="Times-Bold",
    name_font="Times-Roman",
    body_font="Times-Roman",
    meta_font="Times-Italic",
    border_kind="double_rule",
    corner_motif="chess",
    banner="bar",
    seal_shape="rosette",
    name_align="center",
    default_watermark="knight",
    title_size=15,
    name_size=30,
    body_size=12,
)

PLAYFUL = StylePreset(
    key="playful",
    name="Escolar lúdico",
    title_font="Helvetica-Bold",
    name_font="Helvetica-Bold",
    body_font="Helvetica",
    meta_font="Helvetica-Bold",
    border_kind="rounded",
    corner_motif="dots",
    banner="pill",
    seal_shape="medal",
    name_align="center",
    default_watermark="board",
    title_size=14,
    name_size=29,
    body_size=12,
)

MODERN = StylePreset(
    key="modern",
    name="Moderno",
    title_font="Helvetica",
    name_font="Helvetica",
    body_font="Helvetica",
    meta_font="Helvetica",
    border_kind="side_band",
    corner_motif="none",
    banner="label_caps",
    seal_shape="none",
    name_align="left",
    default_watermark="numeral",
    title_size=12,
    name_size=34,
    body_size=12,
)

ELEGANT = StylePreset(
    key="elegant", name="Elegante",
    title_font="Times-Bold", name_font="Times-Roman", body_font="Times-Roman", meta_font="Times-Italic",
    border_kind="double_rule", corner_motif="none", banner="bar", seal_shape="ring",
    name_align="center", default_watermark="king", title_size=14, name_size=30, body_size=12,
)

VINTAGE = StylePreset(
    key="vintage", name="Vintage",
    title_font="Times-Bold", name_font="Times-Roman", body_font="Times-Roman", meta_font="Times-Italic",
    border_kind="double_rule", corner_motif="none", banner="bar", seal_shape="rosette",
    name_align="center", default_watermark="rook", title_size=14, name_size=30, body_size=12,
)

ROYAL = StylePreset(
    key="royal", name="Real",
    title_font="Times-Bold", name_font="Times-Roman", body_font="Times-Roman", meta_font="Times-Italic",
    border_kind="double_rule", corner_motif="chess", banner="bar", seal_shape="rosette",
    name_align="center", default_watermark="king", title_size=15, name_size=30, body_size=12,
)

LAUREL = StylePreset(
    key="laurel", name="Louros",
    title_font="Times-Bold", name_font="Times-Roman", body_font="Times-Roman", meta_font="Times-Italic",
    border_kind="double_rule", corner_motif="none", banner="bar", seal_shape="rosette",
    name_align="center", default_watermark="board", title_size=15, name_size=30, body_size=12,
)

GEOMETRIC = StylePreset(
    key="geometric", name="Geométrico",
    title_font="Helvetica-Bold", name_font="Helvetica-Bold", body_font="Helvetica", meta_font="Helvetica-Bold",
    border_kind="chess_strip", corner_motif="none", banner="bar", seal_shape="ring",
    name_align="center", default_watermark="board", title_size=13, name_size=30, body_size=12,
)

KIDS = StylePreset(
    key="kids", name="Infantil",
    title_font="Helvetica-Bold", name_font="Helvetica-Bold", body_font="Helvetica", meta_font="Helvetica-Bold",
    border_kind="rounded", corner_motif="dots", banner="pill", seal_shape="medal",
    name_align="center", default_watermark="pawn", title_size=14, name_size=30, body_size=12,
)

MONO = StylePreset(
    key="mono", name="Tabuleiro",
    title_font="Helvetica-Bold", name_font="Helvetica-Bold", body_font="Helvetica", meta_font="Helvetica",
    border_kind="chess_strip", corner_motif="none", banner="label_caps", seal_shape="ring",
    name_align="center", default_watermark="board", title_size=12, name_size=31, body_size=12,
)

STYLE_PRESETS: dict[str, StylePreset] = {
    p.key: p for p in (CLASSIC, PLAYFUL, MODERN, ELEGANT, VINTAGE, ROYAL, LAUREL, GEOMETRIC, KIDS, MONO)
}
DEFAULT_STYLE_PRESET = "classic"


def resolve_preset(preset_key: str | None) -> StylePreset:
    """Devolve o preset pedido; se vazio/inválido, o Clássico."""
    return STYLE_PRESETS.get((preset_key or "").strip(), CLASSIC)


def is_valid_preset(preset_key: str | None) -> bool:
    return (preset_key or "").strip() in STYLE_PRESETS
