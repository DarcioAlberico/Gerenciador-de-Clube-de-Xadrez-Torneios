"""Montagem de uma página de diploma, despachando por preset.

Recebe uma ``DrawingSurface`` já dimensionada e desenha o diploma inteiro:
fundo, marca d'água, moldura, banner, nome-herói, corpo, selo/medalha,
assinaturas e código. O *arranjo* mora aqui; o *traçado* das peças mora em
``shapes``; os *dados* de estilo em ``styles``/``palettes``. Sem I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import shapes
from .layout import CM, compute_zones
from .palettes import Palette
from .styles import StylePreset
from .surface import DrawingSurface


@dataclass(frozen=True)
class CertificateContent:
    title: str = ""
    intro: str = ""
    name: str = ""
    body: str = ""
    footer: str = ""
    signature_left: str = ""
    signature_right: str = ""
    source_title: str = ""
    verification_code: str = ""
    position: int = 0          # 1..3 habilita medalha; 0 = sem colocação
    seal_label: str = ""       # rótulo do selo (ex.: "1º"); vazio usa padrão


@dataclass(frozen=True)
class RenderOptions:
    seal_enabled: bool = True
    watermark_enabled: bool = True
    medal_by_placement: bool = True
    watermark_kind: str = ""        # "" = padrão do preset; senão piece/board/numeral/image/none
    watermark_piece: str = ""       # rook|king|knight|pawn (quando kind=piece)
    watermark_image: object | None = None  # ImageReader/caminho (quando kind=image)
    watermark_opacity: float = 0.0  # 0 = padrão por tipo


def render_certificate(surface: DrawingSurface, preset: StylePreset, palette: Palette,
                       content: CertificateContent, options: RenderOptions | None = None) -> None:
    opts = options or RenderOptions()
    zones = compute_zones(surface.width, surface.height, preset.key)

    surface.rect(0, 0, surface.width, surface.height, fill=palette.paper)
    if opts.watermark_enabled:
        _draw_watermark(surface, preset, palette, zones, content, opts)
    _draw_border(surface, preset, palette, zones)
    _draw_header(surface, preset, palette, zones, content)
    _draw_hero(surface, preset, palette, zones, content)
    _draw_body(surface, preset, palette, zones, content)
    if opts.seal_enabled and preset.seal_shape != "none":
        _draw_seal(surface, preset, palette, zones, content, opts)
    _draw_signatures(surface, preset, palette, zones, content)
    _draw_code(surface, preset, palette, zones, content)


# --- blocos ----------------------------------------------------------------
_PIECE_NAMES = ("rook", "king", "queen", "pawn", "knight")


def _draw_watermark(surface, preset, palette, zones, content, options):
    kind = (options.watermark_kind or preset.default_watermark or "").strip()
    if kind in ("", "none"):
        return
    short = min(zones.width, zones.height)
    cx = zones.center_x
    op = options.watermark_opacity if options.watermark_opacity > 0 else 0.0
    if kind in _PIECE_NAMES or kind == "piece":
        name = (options.watermark_piece or "rook") if kind == "piece" else kind
        shapes.piece(surface, name, cx, zones.height * 0.46, short * 0.42, palette.ink, alpha=op or 0.06)
    elif kind == "board":
        shapes.board_watermark(surface, cx, zones.height * 0.5, short * 0.5, palette.ink, alpha=op or 0.05)
    elif kind == "numeral":
        label = content.seal_label or (str(content.position) if content.position else "")
        if label:
            with surface.alpha(op or 0.10):
                shapes.numeral_watermark(surface, zones.content_right - 1.2 * CM,
                                         zones.footer_y, label, 4.6 * CM, palette.ink, anchor="end")
    elif kind == "image" and options.watermark_image is not None:
        size = short * 0.5
        surface.image(options.watermark_image, cx - size / 2.0, zones.height * 0.5 - size / 2.0,
                      size, size, opacity=op or 0.10)


def _draw_border(surface, preset, palette, zones):
    x, y = zones.margin, zones.margin
    w, h = zones.width - 2 * zones.margin, zones.height - 2 * zones.margin
    if preset.border_kind == "double_rule":
        shapes.double_rule_border(surface, x, y, w, h, palette.accent, palette.ink, gap=8.0)
        if preset.corner_motif == "chess":
            shapes.chess_corners(surface, x, y, w, h, 7.0, palette.accent, palette.ink)
    elif preset.border_kind == "rounded":
        shapes.rounded_border(surface, x, y, w, h, palette.ink, dash_color=palette.accent)
        if preset.corner_motif == "dots":
            extras = palette.extras or (palette.accent, palette.ink, palette.accent_dark)
            for i, (cxr, cyr) in enumerate(((x + 18, y + h - 18), (x + w - 18, y + h - 18),
                                            (x + 18, y + 18), (x + w - 18, y + 18))):
                surface.circle(cxr, cyr, 5.0, fill=extras[i % len(extras)])
    elif preset.border_kind == "side_band":
        side_band_x = zones.margin * 0.4
        shapes.side_band(surface, side_band_x, zones.margin, zones.height - 2 * zones.margin, palette.accent, width=7.0)
    elif preset.border_kind == "chess_strip":
        shapes.chess_strip_border(surface, x, y, w, h, 0.5 * CM, palette.ink, palette.accent)
        inset = 0.64 * CM
        surface.rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset, stroke=palette.ink, line_width=1.0)


def _est_text_width(text: str, size: float, char_space: float = 0.0) -> float:
    """Largura aproximada de um texto (para dimensionar banners)."""
    return len(text) * size * 0.62 + char_space * max(0, len(text) - 1)


def _draw_header(surface, preset, palette, zones, content):
    cx = zones.center_x
    top = zones.height - zones.margin
    title = content.title.upper()
    if preset.banner == "bar":
        bh = 0.95 * CM
        bw = max(10.0 * CM, _est_text_width(title, preset.title_size, 1.5) + 1.8 * CM)
        shapes.banner_bar(surface, cx, top - bh + 0.3 * CM, bw, bh, palette.ink,
                          title, palette.accent, preset.title_font, preset.title_size)
    elif preset.banner == "pill":
        bh = 0.9 * CM
        bw = max(7.0 * CM, _est_text_width(title, preset.title_size) + 1.6 * CM)
        ty = top - bh + 0.2 * CM
        shapes.banner_pill(surface, cx, ty, bw, bh, palette.accent,
                           title, palette.accent_dark, preset.title_font, preset.title_size)
        sx = bw / 2.0 + 0.7 * CM
        shapes.sparkle(surface, cx - sx, ty + bh * 0.5, 5.0, palette.accent)
        shapes.sparkle(surface, cx + sx, ty + bh * 0.5, 5.0, palette.accent)
    else:  # label_caps — alinhado à esquerda
        lx = zones.content_left
        ty = zones.banner_y + 0.2 * CM
        if preset.border_kind == "chess_strip":  # limpa a faixa de casas atrás do rótulo
            tw = _est_text_width(title, preset.title_size, 4.0) + 1.1 * CM
            surface.rect(lx - 0.2 * CM, ty - 0.22 * CM, tw, preset.title_size + 10, fill=palette.paper)
        surface.rect(lx, ty, 10.0, 10.0, fill=palette.accent)
        surface.text(lx + 0.7 * CM, ty, title,
                     font=preset.title_font, size=preset.title_size, fill=palette.muted,
                     anchor="start", char_space=4.0)

    if content.intro:
        if preset.name_align == "left":
            surface.text(zones.content_left, zones.hero_y + 1.1 * CM, content.intro,
                         font=preset.meta_font, size=11, fill=palette.muted, anchor="start")
        else:
            surface.text(cx, zones.hero_y + 1.1 * CM, content.intro,
                         font=preset.meta_font, size=12, fill=palette.muted, anchor="middle")


def _draw_hero(surface, preset, palette, zones, content):
    left = preset.name_align == "left"
    x = zones.content_left if left else zones.center_x
    anchor = "start" if left else "middle"
    surface.text(x, zones.hero_y, content.name, font=preset.name_font, size=preset.name_size,
                 fill=palette.ink, anchor=anchor)
    rule_y = zones.hero_y - 0.55 * CM
    if left:
        surface.line(x, rule_y, x + 9.0 * CM, rule_y, stroke=palette.accent, line_width=1.0)
    else:
        half = 4.6 * CM
        surface.line(x - half, rule_y, x + half, rule_y, stroke=palette.accent, line_width=1.5)
        d = 5.0
        surface.polygon([(x, rule_y + d), (x + d, rule_y), (x, rule_y - d), (x - d, rule_y)], fill=palette.accent)


def _draw_body(surface, preset, palette, zones, content):
    left = preset.name_align == "left"
    x = zones.content_left if left else zones.center_x
    anchor = "start" if left else "middle"
    max_chars = max(20, int(zones.content_width / (preset.body_size * 0.52)))
    line_y = zones.hero_y - 1.35 * CM
    for line in _wrap(content.body, max_chars):
        surface.text(x, line_y, line, font=preset.body_font, size=preset.body_size, fill=palette.body, anchor=anchor)
        line_y -= preset.body_size + 6


def _draw_seal(surface, preset, palette, zones, content, opts):
    position = content.position if opts.medal_by_placement else 0
    is_award = position in (1, 2, 3)
    cx = zones.content_left + 1.5 * CM
    cy = zones.footer_y + 0.4 * CM
    label = content.seal_label or (f"{position}º" if is_award else "★")
    if preset.seal_shape == "rosette":
        shapes.rosette_seal(surface, cx, cy, 0.95 * CM, palette.accent, palette.accent_dark,
                            palette.ink, palette.paper, label, preset.name_font)
        if position == 1:
            shapes.crown(surface, cx, cy + 1.35 * CM, 0.8 * CM, palette.accent)
    elif preset.seal_shape == "medal":
        shapes.medal(surface, cx, cy, 0.9 * CM, position, label, palette.accent_dark, preset.name_font)
        if position == 1:
            shapes.crown(surface, cx, cy + 1.3 * CM, 0.8 * CM, palette.accent)
    elif preset.seal_shape == "ring":
        shapes.ring_seal(surface, cx, cy, 0.9 * CM, palette.accent, palette.ink, palette.paper, label, preset.name_font)
        if position == 1:
            shapes.crown(surface, cx, cy + 1.32 * CM, 0.78 * CM, palette.accent)


def _draw_signatures(surface, preset, palette, zones, content):
    y = zones.footer_y
    if preset.name_align == "left":
        x = zones.content_left
        surface.line(x, y, x + 4.0 * CM, y, stroke=palette.ink, line_width=1.0)
        surface.text(x, y - 0.5 * CM, content.signature_left or "Direcao",
                     font=preset.meta_font, size=11, fill=palette.ink, anchor="start")
        return
    for cx_frac, sig in ((0.50, content.signature_left), (0.74, content.signature_right)):
        if not sig:
            continue
        cx = zones.width * cx_frac
        half = 1.9 * CM
        surface.line(cx - half, y, cx + half, y, stroke=palette.ink, line_width=1.0)
        surface.text(cx, y - 0.5 * CM, sig, font=preset.meta_font, size=11, fill=palette.ink, anchor="middle")


def _draw_code(surface, preset, palette, zones, content):
    if not content.verification_code:
        return
    y = zones.margin + (0.9 * CM if preset.border_kind == "chess_strip" else 0.4 * CM)
    surface.text(zones.content_right, y,
                 f"Codigo {content.verification_code} · verificavel",
                 font="Helvetica", size=8, fill=palette.muted, anchor="end")


def _wrap(text: str, max_chars: int) -> list[str]:
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
