"""Primitivas vetoriais temáticas dos diplomas.

Cada função desenha um ornamento (moldura, tabuleiro, selo, medalha, coroa,
peça, marca d'água) contra uma ``DrawingSurface`` — nunca toca no ReportLab
direto. Coordenadas em pontos, y para cima. Mantido separado do ``renderer``
para o arranjo de página não se misturar com o traçado das peças.
"""
from __future__ import annotations

from typing import Sequence

from .surface import DrawingSurface, PathSeg

# Medalha por colocação: 1º ouro, 2º prata, 3º bronze.
MEDAL_COLORS: dict[int, tuple[str, str, str]] = {
    1: ("#E7C766", "#C9A227", "#9C7B1A"),  # face, anel, fita
    2: ("#D7DBE0", "#AEB4BD", "#8A9099"),
    3: ("#E2A977", "#C8814C", "#9C6234"),
}


def _scaled(norm: Sequence[PathSeg], ox: float, oy: float, size: float) -> list[PathSeg]:
    """Converte segmentos normalizados (0..1) em coordenadas absolutas."""
    out: list[PathSeg] = []
    for seg in norm:
        op = seg[0]
        if op == "z":
            out.append(("z",))
        elif op == "c":
            out.append(("c", ox + seg[1] * size, oy + seg[2] * size,
                        ox + seg[3] * size, oy + seg[4] * size,
                        ox + seg[5] * size, oy + seg[6] * size))
        else:
            out.append((op, ox + seg[1] * size, oy + seg[2] * size))
    return out


# --- Molduras ---------------------------------------------------------------
def double_rule_border(surface: DrawingSurface, x: float, y: float, w: float, h: float,
                       outer: str, inner: str, gap: float = 8.0) -> None:
    surface.rect(x, y, w, h, stroke=outer, line_width=3.0)
    surface.rect(x + gap, y + gap, w - 2 * gap, h - 2 * gap, stroke=inner, line_width=1.0)


def rounded_border(surface: DrawingSurface, x: float, y: float, w: float, h: float,
                   color: str, dash_color: str | None = None, radius: float = 18.0) -> None:
    surface.rect(x, y, w, h, stroke=color, line_width=5.0, radius=radius)
    if dash_color:
        surface.rect(x, y, w, h, stroke=dash_color, line_width=2.0, radius=radius, dash=(2, 7))


def side_band(surface: DrawingSurface, x: float, y: float, h: float, color: str, width: float = 7.0) -> None:
    surface.rect(x, y, width, h, fill=color)


# --- Tabuleiro --------------------------------------------------------------
def chess_corners(surface: DrawingSurface, x: float, y: float, w: float, h: float,
                  square: float, color_a: str, color_b: str) -> None:
    for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        surface.rect(cx - square, cy, square, square, fill=color_a)
        surface.rect(cx, cy, square, square, fill=color_b)
        surface.rect(cx - square, cy - square, square, square, fill=color_b)
        surface.rect(cx, cy - square, square, square, fill=color_a)


def board_strip(surface: DrawingSurface, cx: float, y: float, cells: int, square: float,
                color_a: str, color_b: str) -> None:
    start = cx - (cells * square) / 2.0
    for i in range(cells):
        surface.rect(start + i * square, y, square, square, fill=color_a if i % 2 == 0 else color_b)


def board_watermark(surface: DrawingSurface, cx: float, cy: float, size: float,
                    color: str, alpha: float = 0.06, square: float | None = None) -> None:
    sq = square or size / 8.0
    n = max(1, int(size / sq))
    ox = cx - (n * sq) / 2.0
    oy = cy - (n * sq) / 2.0
    with surface.alpha(alpha):
        for row in range(n):
            for col in range(n):
                if (row + col) % 2 == 0:
                    surface.rect(ox + col * sq, oy + row * sq, sq, sq, fill=color)


# --- Banner / faixas de título ---------------------------------------------
def banner_bar(surface: DrawingSurface, cx: float, y: float, w: float, h: float, fill: str,
               text: str, text_color: str, font: str, size: float, char_space: float = 1.5) -> None:
    surface.rect(cx - w / 2.0, y, w, h, fill=fill, radius=3.0)
    surface.text(cx, y + h / 2.0 - size * 0.36, text, font=font, size=size,
                 fill=text_color, anchor="middle", char_space=char_space)


def banner_pill(surface: DrawingSurface, cx: float, y: float, w: float, h: float, fill: str,
                text: str, text_color: str, font: str, size: float) -> None:
    surface.rect(cx - w / 2.0, y, w, h, fill=fill, radius=h / 2.0)
    surface.text(cx, y + h / 2.0 - size * 0.36, text, font=font, size=size, fill=text_color, anchor="middle")


# --- Selo, medalha, coroa ---------------------------------------------------
def rosette_seal(surface: DrawingSurface, cx: float, cy: float, r: float, gold: str,
                 gold_dark: str, ink: str, paper: str, label: str, label_font: str) -> None:
    # Fitas atrás.
    surface.polygon([(cx - r * 0.45, cy - r * 0.6), (cx - r * 0.9, cy - r * 1.9),
                     (cx - r * 0.35, cy - r * 1.45), (cx + r * 0.1, cy - r * 1.85),
                     (cx, cy - r * 0.6)], fill=gold_dark)
    # Serrilha (anel tracejado grosso) + disco.
    surface.circle(cx, cy, r, fill=gold, stroke=gold_dark, line_width=1.5, dash=(3, 2.2))
    surface.circle(cx, cy, r * 0.72, fill=paper, stroke=ink, line_width=1.3)
    surface.text(cx, cy - r * 0.28, label, font=label_font, size=r * 0.74, fill=ink, anchor="middle")


def medal(surface: DrawingSurface, cx: float, cy: float, r: float, position: int,
          label: str, label_color: str, label_font: str) -> None:
    face, ring, ribbon = MEDAL_COLORS.get(position, MEDAL_COLORS[1])
    surface.polygon([(cx - r * 0.6, cy + r * 0.3), (cx - r * 0.3, cy - r * 1.5),
                     (cx, cy - r * 0.9), (cx + r * 0.3, cy - r * 1.5),
                     (cx + r * 0.6, cy + r * 0.3)], fill=ribbon)
    surface.circle(cx, cy, r, fill=face, stroke=ring, line_width=2.0)
    surface.text(cx, cy - r * 0.34, label, font=label_font, size=r * 0.9, fill=label_color, anchor="middle")


def crown(surface: DrawingSurface, cx: float, cy: float, w: float, color: str) -> None:
    left, right = cx - w / 2.0, cx + w / 2.0
    surface.path([
        ("m", left, cy), ("l", left, cy + 0.30 * w), ("l", cx - 0.22 * w, cy + 0.12 * w),
        ("l", cx, cy + 0.40 * w), ("l", cx + 0.22 * w, cy + 0.12 * w),
        ("l", right, cy + 0.30 * w), ("l", right, cy), ("z",),
    ], fill=color)
    for px, py in ((left, cy + 0.30 * w), (cx, cy + 0.40 * w), (right, cy + 0.30 * w)):
        surface.circle(px, py, w * 0.06, fill=color)


# Silhuetas de peças de xadrez, normalizadas 0..1, y para cima, como path único
# (path único evita bordas duplas quando desenhado com opacidade de marca d'água).
_ROOK: tuple[PathSeg, ...] = (
    ("m", 0.18, 0.78), ("l", 0.18, 0.88), ("l", 0.12, 0.88), ("l", 0.12, 1.0),
    ("l", 0.30, 1.0), ("l", 0.30, 0.91), ("l", 0.41, 0.91), ("l", 0.41, 1.0),
    ("l", 0.59, 1.0), ("l", 0.59, 0.91), ("l", 0.70, 0.91), ("l", 0.70, 1.0),
    ("l", 0.88, 1.0), ("l", 0.88, 0.88), ("l", 0.82, 0.88), ("l", 0.82, 0.78),
    ("l", 0.72, 0.22), ("l", 0.86, 0.22), ("l", 0.86, 0.04), ("l", 0.14, 0.04),
    ("l", 0.14, 0.22), ("l", 0.28, 0.22), ("z",),
)
_PAWN: tuple[PathSeg, ...] = (
    ("m", 0.26, 0.05), ("l", 0.74, 0.05), ("l", 0.66, 0.22),
    ("c", 0.60, 0.30, 0.60, 0.36, 0.64, 0.44),
    ("c", 0.74, 0.50, 0.74, 0.66, 0.60, 0.70),
    ("c", 0.70, 0.76, 0.70, 0.90, 0.58, 0.94),
    ("c", 0.53, 0.98, 0.47, 0.98, 0.42, 0.94),
    ("c", 0.30, 0.90, 0.30, 0.76, 0.40, 0.70),
    ("c", 0.26, 0.66, 0.26, 0.50, 0.36, 0.44),
    ("c", 0.40, 0.36, 0.40, 0.30, 0.34, 0.22), ("z",),
)
_KING: tuple[PathSeg, ...] = (
    ("m", 0.18, 0.05), ("l", 0.18, 0.18), ("l", 0.33, 0.22), ("l", 0.40, 0.50),
    ("l", 0.33, 0.55), ("l", 0.39, 0.61), ("l", 0.43, 0.74), ("l", 0.45, 0.74),
    ("l", 0.45, 0.82), ("l", 0.38, 0.82), ("l", 0.38, 0.89), ("l", 0.45, 0.89),
    ("l", 0.45, 0.99), ("l", 0.55, 0.99), ("l", 0.55, 0.89), ("l", 0.62, 0.89),
    ("l", 0.62, 0.82), ("l", 0.55, 0.82), ("l", 0.55, 0.74), ("l", 0.57, 0.74),
    ("l", 0.61, 0.61), ("l", 0.67, 0.55), ("l", 0.60, 0.50), ("l", 0.67, 0.22),
    ("l", 0.82, 0.18), ("l", 0.82, 0.05), ("z",),
)
_KNIGHT: tuple[PathSeg, ...] = (
    ("m", 0.16, 0.04), ("l", 0.84, 0.04), ("l", 0.84, 0.14), ("l", 0.70, 0.14),
    ("c", 0.78, 0.36, 0.78, 0.52, 0.72, 0.62),   # nuca sobe pela direita
    ("l", 0.64, 0.74), ("l", 0.70, 0.80), ("l", 0.58, 0.76),  # crina serrilhada
    ("l", 0.61, 0.92), ("l", 0.50, 0.78),        # orelha
    ("c", 0.42, 0.82, 0.30, 0.78, 0.20, 0.68),   # testa desce à esquerda
    ("l", 0.10, 0.58), ("l", 0.15, 0.49), ("l", 0.30, 0.52),  # focinho e boca
    ("c", 0.34, 0.42, 0.33, 0.30, 0.30, 0.22),   # garganta/peito
    ("l", 0.38, 0.14), ("l", 0.30, 0.14), ("z",),
)
# Dama: corpo + coroa de 3 pontas; as bolinhas das pontas são desenhadas à parte.
_QUEEN: tuple[PathSeg, ...] = (
    ("m", 0.16, 0.05), ("l", 0.16, 0.18), ("l", 0.32, 0.22), ("l", 0.40, 0.58),
    ("l", 0.35, 0.66), ("l", 0.41, 0.84), ("l", 0.455, 0.68), ("l", 0.50, 0.86),
    ("l", 0.545, 0.68), ("l", 0.59, 0.84), ("l", 0.65, 0.66), ("l", 0.60, 0.58),
    ("l", 0.68, 0.22), ("l", 0.84, 0.18), ("l", 0.84, 0.05), ("z",),
)
_QUEEN_TIPS = ((0.41, 0.85), (0.50, 0.87), (0.59, 0.85))

_PIECES: dict[str, tuple[PathSeg, ...]] = {
    "rook": _ROOK, "pawn": _PAWN, "king": _KING, "knight": _KNIGHT, "queen": _QUEEN,
}


def piece(surface: DrawingSurface, name: str, cx: float, cy: float, size: float,
          color: str, alpha: float = 1.0) -> None:
    ox, oy = cx - size / 2.0, cy - size / 2.0
    segs = _scaled(_PIECES.get(name, _ROOK), ox, oy, size)

    def _draw() -> None:
        surface.path(segs, fill=color)
        if name == "queen":  # bolinhas coroando as pontas
            for fx, fy in _QUEEN_TIPS:
                surface.circle(ox + fx * size, oy + fy * size, size * 0.045, fill=color)

    if alpha < 1.0:
        with surface.alpha(alpha):
            _draw()
    else:
        _draw()


def knight(surface: DrawingSurface, cx: float, cy: float, size: float, color: str,
           alpha: float = 1.0) -> None:
    piece(surface, "knight", cx, cy, size, color, alpha)


def ring_seal(surface: DrawingSurface, cx: float, cy: float, r: float, accent: str,
              ink: str, paper: str, label: str, label_font: str) -> None:
    """Selo minimalista: dois anéis concêntricos + rótulo (sem fitas)."""
    surface.circle(cx, cy, r, stroke=accent, line_width=2.4)
    surface.circle(cx, cy, r * 0.74, fill=paper, stroke=ink, line_width=1.0)
    surface.text(cx, cy - r * 0.3, label, font=label_font, size=r * 0.78, fill=ink, anchor="middle")


def chess_strip_border(surface: DrawingSurface, x: float, y: float, w: float, h: float,
                       square: float, color_a: str, color_b: str) -> None:
    """Moldura formada por faixas de casas de tabuleiro nas quatro bordas."""
    cols = max(2, int(w / square))
    rows = max(2, int(h / square))
    for i in range(cols):
        ca = color_a if i % 2 == 0 else color_b
        surface.rect(x + i * square, y + h - square, square, square, fill=ca)
        surface.rect(x + i * square, y, square, square, fill=color_b if i % 2 == 0 else color_a)
    for j in range(rows):
        ca = color_a if j % 2 == 0 else color_b
        surface.rect(x, y + j * square, square, square, fill=ca)
        surface.rect(x + w - square, y + j * square, square, square, fill=color_b if j % 2 == 0 else color_a)


def sparkle(surface: DrawingSurface, cx: float, cy: float, r: float, color: str) -> None:
    surface.polygon([(cx, cy + r), (cx + r * 0.28, cy + r * 0.28), (cx + r, cy),
                     (cx + r * 0.28, cy - r * 0.28), (cx, cy - r), (cx - r * 0.28, cy - r * 0.28),
                     (cx - r, cy), (cx - r * 0.28, cy + r * 0.28)], fill=color)


def numeral_watermark(surface: DrawingSurface, x: float, y: float, text: str, size: float,
                      color: str, anchor: str = "middle") -> None:
    surface.text(x, y, text, font="Helvetica-Bold", size=size, fill=color, anchor=anchor)
