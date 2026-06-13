"""Paletas de cor nomeadas dos diplomas (dados puros, sem ReportLab/Tk).

Cada paleta é um conjunto coeso de cores hex usado por um preset de estilo
(ver ``styles.py``) e pela galeria de modelos (ver ``gallery.py``). Mantido
puro de propósito: nenhuma dependência de desenho, 100% testável isolado.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Palette:
    """Cores de um diploma. ``extras`` só é usado pelos estilos festivos."""

    key: str
    name: str
    paper: str          # fundo "papel"
    ink: str            # cor principal (texto-título, bordas, nome)
    accent: str         # destaque (dourado/ âmbar/ acento)
    accent_dark: str    # variação escura do destaque (fitas, sombras)
    body: str           # texto de corpo
    muted: str          # texto secundário/itálico
    extras: tuple[str, ...] = field(default_factory=tuple)  # confete lúdico


# --- Clássico: sóbrio, papel creme, destaque metálico ---------------------
_CLASSIC = (
    Palette("navy_gold", "Azul-marinho e ouro", "#FBF7EC", "#14315C", "#C9A227", "#9C7B1A", "#3A3A3A", "#6B5B2E"),
    Palette("wine_gold", "Vinho e ouro", "#FBF4EF", "#6A1B2A", "#C9A227", "#9C7B1A", "#3A2A2A", "#7A5A3E"),
    Palette("forest_gold", "Verde e ouro", "#F6F8F1", "#14432B", "#C9A227", "#9C7B1A", "#2F3A2F", "#5E6B4E"),
    Palette("charcoal_silver", "Grafite e prata", "#F7F7F8", "#1F2937", "#9CA3AF", "#6B7280", "#374151", "#6B7280"),
)

# --- Lúdico: papel claro, cores vivas + confete -----------------------------
_PLAYFUL = (
    Palette("rainbow", "Arco-íris", "#FFFEF9", "#2563EB", "#F59E0B", "#B45309", "#374151", "#6B7280",
            ("#EF4444", "#10B981", "#8B5CF6", "#F59E0B")),
    Palette("candy", "Algodão-doce", "#FFF7FB", "#DB2777", "#F59E0B", "#B45309", "#4A3540", "#9D6B82",
            ("#F472B6", "#FB7185", "#A78BFA", "#34D399")),
    Palette("ocean", "Oceano", "#F2FBFF", "#0EA5E9", "#22C55E", "#15803D", "#334155", "#64748B",
            ("#0EA5E9", "#22D3EE", "#14B8A6", "#FACC15")),
    Palette("sunset", "Pôr do sol", "#FFF9F2", "#EA580C", "#F59E0B", "#B45309", "#44312A", "#9A6B4E",
            ("#F97316", "#EF4444", "#EC4899", "#F59E0B")),
)

# --- Moderno: papel branco, um acento forte, sem metálico -------------------
_MODERN = (
    Palette("indigo", "Índigo", "#FFFFFF", "#111827", "#4F46E5", "#3730A3", "#4B5563", "#9CA3AF"),
    Palette("slate", "Ardósia", "#FFFFFF", "#0F172A", "#334155", "#1E293B", "#475569", "#94A3B8"),
    Palette("emerald", "Esmeralda", "#FFFFFF", "#064E3B", "#059669", "#047857", "#374151", "#9CA3AF"),
    Palette("crimson", "Carmim", "#FFFFFF", "#1F2937", "#DC2626", "#991B1B", "#4B5563", "#9CA3AF"),
)

# --- Paletas dos 7 estilos adicionais --------------------------------------
_EXTRA = (
    Palette("noir_gold", "Preto e ouro", "#FAFAF7", "#141414", "#C9A227", "#9C7B1A", "#2A2A2A", "#7A6E50"),
    Palette("sepia", "Sépia/pergaminho", "#F3E8D0", "#5B4327", "#A9822F", "#7C5E20", "#4A3924", "#8A734E"),
    Palette("burgundy_gold", "Borgonha e ouro", "#FBF6EF", "#5A1A2E", "#C9A227", "#9C7B1A", "#3A2A2E", "#7A5A4E"),
    Palette("laurel_green", "Verde-louro e ouro", "#F4F7EE", "#1E4D2B", "#C9A227", "#9C7B1A", "#2F3A2F", "#5E6B4E"),
    Palette("teal_bold", "Teal e laranja", "#FFFFFF", "#0F766E", "#F97316", "#C2410C", "#334155", "#94A3B8",
            ("#0F766E", "#F97316", "#FACC15", "#1D4ED8")),
    Palette("mono_red", "Preto, branco e vermelho", "#FFFFFF", "#141414", "#DC2626", "#991B1B", "#3A3A3A", "#9CA3AF"),
)

PALETTES: dict[str, Palette] = {
    p.key: p for group in (_CLASSIC, _PLAYFUL, _MODERN, _EXTRA) for p in group
}

# Paletas recomendadas por preset (a galeria distribui a partir daqui).
PALETTES_BY_PRESET: dict[str, tuple[str, ...]] = {
    "classic": tuple(p.key for p in _CLASSIC),
    "playful": tuple(p.key for p in _PLAYFUL),
    "modern": tuple(p.key for p in _MODERN),
    "elegant": ("noir_gold", "charcoal_silver"),
    "vintage": ("sepia", "wine_gold"),
    "royal": ("burgundy_gold", "wine_gold"),
    "laurel": ("laurel_green", "forest_gold"),
    "geometric": ("teal_bold", "indigo"),
    "kids": ("candy", "rainbow", "sunset"),
    "mono": ("mono_red", "charcoal_silver"),
}

DEFAULT_PALETTE_BY_PRESET: dict[str, str] = {
    "classic": "navy_gold",
    "playful": "rainbow",
    "modern": "indigo",
    "elegant": "noir_gold",
    "vintage": "sepia",
    "royal": "burgundy_gold",
    "laurel": "laurel_green",
    "geometric": "teal_bold",
    "kids": "candy",
    "mono": "mono_red",
}


def resolve_palette(palette_key: str, preset_key: str = "classic") -> Palette:
    """Devolve a paleta pedida; se vazia/inválida, o padrão do preset."""
    palette = PALETTES.get((palette_key or "").strip())
    if palette is not None:
        return palette
    fallback = DEFAULT_PALETTE_BY_PRESET.get(preset_key, "navy_gold")
    return PALETTES[fallback]


def palette_from_colors(primary_color: str, accent_color: str, paper: str = "#FFFFFF") -> Palette:
    """Constrói uma paleta efêmera a partir das cores do modelo (override do usuário)."""
    ink = (primary_color or "#14315C").strip() or "#14315C"
    accent = (accent_color or "#C9A227").strip() or "#C9A227"
    return Palette(
        key="custom",
        name="Personalizada",
        paper=(paper or "#FFFFFF").strip() or "#FFFFFF",
        ink=ink,
        accent=accent,
        accent_dark=accent,
        body="#3A3A3A",
        muted="#6B5B2E",
    )
