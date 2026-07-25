"""Camada de tema: tokens de design, presets e notificação de mudança.

Fonte única dos tokens (ESPEC_UI_UX §4.2–4.3). Nada aqui importa outras camadas
da UI — telas e componentes importam **daqui**, nunca o contrário.

Os tokens de cor são ``ColorToken``, uma lista de dois elementos (claro, escuro)
**mutada no lugar** quando o preset muda. Quem importou ``THEME_ACCENT`` guarda
uma referência ao mesmo objeto, então a troca de tema alcança todo mundo sem
reescrever ``sys.modules`` — que era o que ``_propagate_theme_globals`` fazia
(achado P0-5). O customtkinter aceita lista de cores nativamente: é assim que os
temas JSON dele já vêm.

Quem precisa reagir à troca (redesenhar, reconfigurar widget) registra-se em
``on_theme_change``; ``apply_*_preset`` avisa os inscritos no fim.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import customtkinter as ctk

logger = logging.getLogger("src.ui.theme")


class ColorToken(list):
    """Par ``(claro, escuro)`` mutável, aceito pelo customtkinter como cor.

    Mutável de propósito: ``set()`` troca o valor **sem trocar o objeto**, e
    todos os módulos que importaram o token enxergam o novo valor.
    """

    def __init__(self, light: str, dark: str) -> None:
        super().__init__((light, dark))

    def set(self, light: str, dark: str) -> None:
        self[:] = (light, dark)

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"ColorToken({self[0]!r}, {self[1]!r})"


# Inscritos em troca de tema (ver on_theme_change).
_listeners: list[Callable[[], None]] = []


def on_theme_change(callback: Callable[[], None]) -> Callable[[], None]:
    """Registra ``callback`` para rodar depois de cada troca de preset."""
    if callback not in _listeners:
        _listeners.append(callback)
    return callback


def off_theme_change(callback: Callable[[], None]) -> None:
    """Cancela a inscrição (janela destruída, tela trocada)."""
    if callback in _listeners:
        _listeners.remove(callback)


def notify_theme_change() -> None:
    """Avisa os inscritos. Um inscrito quebrado não pode derrubar a troca."""
    for callback in list(_listeners):
        try:
            callback()
        except Exception:
            logger.exception("Falha em listener de troca de tema")


# Escala tipográfica — use estes tokens em vez de literais em CTkFont(size=...)
SIZE_PAGE_TITLE = 22       # Título de página (consumido por _page_title)
SIZE_PAGE_SUBTITLE = 14    # Subtítulo de página
SIZE_SECTION = 15          # Cabeçalho de painel/seção
SIZE_SUBSECTION = 13       # Mini-cabeçalho dentro de painel
SIZE_KPI_VALUE = 22        # Valor numérico em card de KPI
SIZE_MODAL_TITLE = 18      # Título dentro de modal (maior que seção, menor que página)
SIZE_BODY = 12             # Texto corrido

# Escala de espaçamento — use estes tokens em pady/padx no lugar de literais soltos.
# Padroniza o ritmo vertical/horizontal entre telas (ver ESPEC_UI_UX §4.3).
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24


def font_section() -> ctk.CTkFont:
    return ctk.CTkFont(size=SIZE_SECTION, weight="bold")


def font_subsection() -> ctk.CTkFont:
    return ctk.CTkFont(size=SIZE_SUBSECTION, weight="bold")


def font_kpi_value() -> ctk.CTkFont:
    return ctk.CTkFont(size=SIZE_KPI_VALUE, weight="bold")


# ---------------------------------------------------------------------------
# Tokens de tema (Light / Dark) — valores padrão; sobrescritos pelos presets.
# Os quatro primeiros mudam com os presets; os demais são fixos hoje, mas todos
# são ColorToken para que trocar um deles nunca vire de novo um hack de globais.
# ---------------------------------------------------------------------------
THEME_APP_BG       = ColorToken("#F8FAFC", "#0B0F19")
THEME_PANEL_BG     = ColorToken("#FFFFFF", "#1E293B")
THEME_TEXT_MAIN    = ColorToken("#0F172A", "#F1F5F9")
THEME_TEXT_SUB     = ColorToken("#64748B", "#94A3B8")
THEME_STATUSBAR_BG = ColorToken("#E2E8F0", "#0F172A")
THEME_TREE_BG      = ColorToken("#FFFFFF", "#1E293B")
THEME_TREE_FG      = ColorToken("#0F172A", "#F1F5F9")
THEME_ACCENT        = ColorToken("#3B82F6", "#38BDF8")
THEME_DANGER        = ColorToken("#EF4444", "#F87171")
THEME_DANGER_HOVER  = ColorToken("#DC2626", "#B91C1C")
THEME_INFO          = ColorToken("#10B981", "#34D399")
THEME_SUCCESS       = ColorToken("#059669", "#34D399")
THEME_SUCCESS_HOVER = ColorToken("#047857", "#10B981")
# Aviso em dois papeis: PREENCHIMENTO (fundo de toast, com texto escuro por cima)
# e TEXTO sobre painel claro — o ambar de preenchimento nao atinge 4.5:1 como
# texto no modo claro, por isso a variante escurecida (ver ESPEC_UI_UX §6).
THEME_WARNING       = ColorToken("#D97706", "#FBBF24")
THEME_WARNING_HOVER = ColorToken("#B45309", "#F59E0B")
THEME_WARNING_TEXT  = ColorToken("#B45309", "#FBBF24")
# Texto POR CIMA do preenchimento de aviso (claro sobre ambar escuro, escuro
# sobre ambar claro) — o par inverso do THEME_WARNING.
THEME_ON_WARNING    = ColorToken("#FFFFFF", "#0B0F19")
THEME_NEUTRAL       = ColorToken("#64748B", "#475569")
THEME_NEUTRAL_HOVER = ColorToken("#475569", "#334155")

# ---------------------------------------------------------------------------
# Tabelas (ttk.Treeview). O ttk NAO aceita par (claro, escuro): a cor tem de ser
# resolvida com pick() no momento de configurar o estilo. Estes tokens existem
# porque antes as tabelas eram pintadas com valores fixos de modo escuro — no
# tema claro a tabela ficava escura no meio da tela clara.
# ---------------------------------------------------------------------------
THEME_TREE_ODD        = ColorToken("#FFFFFF", "#1E293B")
THEME_TREE_EVEN       = ColorToken("#F1F5F9", "#172032")
THEME_TREE_HEADING    = ColorToken("#CBD5E1", "#0F172A")
THEME_TREE_SELECTED   = ColorToken("#3B82F6", "#334155")
THEME_TREE_SELECTED_FG = ColorToken("#FFFFFF", "#F1F5F9")

# Estado de um resultado na tabela de rodadas: (texto, fundo). Fundo None herda
# a zebra. Semantica, nao decoracao — e por isso que mora aqui e nao na tela.
RESULT_STATE_COLORS: dict[str, tuple[ColorToken, ColorToken | None]] = {
    "vazio":         (ColorToken("#64748B", "#94A3B8"), None),
    "registrado":    (ColorToken("#047857", "#86EFAC"), None),
    "submetido_qr":  (ColorToken("#92400E", "#FCD34D"), ColorToken("#FEF9C3", "#1C1A0A")),
    "aprovado_qr":   (ColorToken("#059669", "#34D399"), ColorToken("#ECFDF5", "#042010")),
    "rejeitado_qr":  (ColorToken("#B91C1C", "#FCA5A5"), ColorToken("#FEF2F2", "#1C0505")),
    "corrigido":     (ColorToken("#6D28D9", "#C4B5FD"), ColorToken("#F5F3FF", "#12080A")),
    "anulado":       (ColorToken("#94A3B8", "#475569"), None),
}

# Resultado lancado (vitoria/empate/bye) — usado nas tags da mesma tabela.
THEME_RESULT_WIN  = ColorToken("#B45309", "#FACC15")
THEME_RESULT_DRAW = ColorToken("#64748B", "#94A3B8")
THEME_RESULT_BYE  = ColorToken("#94A3B8", "#475569")


def pick(token: Any, mode: str | None = None) -> str:
    """Resolve um par ``(claro, escuro)`` para a aparencia atual.

    Serve para quem so aceita **uma** cor: ``ttk.Style``, tags de ``Treeview``,
    widgets Tk puros. Aceita tambem uma string, e devolve ela mesma — assim o
    chamador nao precisa saber se recebeu token ou cor literal.
    """
    if isinstance(token, str):
        return token
    atual = mode or ctk.get_appearance_mode()
    return token[1] if str(atual).lower().startswith("dark") else token[0]

# ---------------------------------------------------------------------------
# Presets de Cor de Destaque (Accent)
# Cada preset: light (modo claro), dark (modo escuro), hover_l, hover_d
# ---------------------------------------------------------------------------
ACCENT_PRESETS: dict[str, dict[str, str]] = {
    "blue":      {"label": "Azul",          "l": "#3B82F6", "d": "#38BDF8", "hl": "#2563EB", "hd": "#0EA5E9"},
    "indigo":    {"label": "Indigo",         "l": "#6366F1", "d": "#818CF8", "hl": "#4F46E5", "hd": "#6366F1"},
    "violet":    {"label": "Violeta",        "l": "#8B5CF6", "d": "#A78BFA", "hl": "#7C3AED", "hd": "#8B5CF6"},
    "purple":    {"label": "Roxo",           "l": "#A855F7", "d": "#C084FC", "hl": "#9333EA", "hd": "#A855F7"},
    "pink":      {"label": "Rosa",           "l": "#EC4899", "d": "#F472B6", "hl": "#DB2777", "hd": "#EC4899"},
    "rose":      {"label": "Rosa Choque",    "l": "#F43F5E", "d": "#FB7185", "hl": "#E11D48", "hd": "#F43F5E"},
    "red":       {"label": "Vermelho",       "l": "#EF4444", "d": "#F87171", "hl": "#DC2626", "hd": "#EF4444"},
    "orange":    {"label": "Laranja",        "l": "#F97316", "d": "#FB923C", "hl": "#EA580C", "hd": "#F97316"},
    "amber":     {"label": "Ambar",          "l": "#F59E0B", "d": "#FBBF24", "hl": "#D97706", "hd": "#F59E0B"},
    "yellow":    {"label": "Amarelo",        "l": "#EAB308", "d": "#FACC15", "hl": "#CA8A04", "hd": "#EAB308"},
    "lime":      {"label": "Lima",           "l": "#84CC16", "d": "#A3E635", "hl": "#65A30D", "hd": "#84CC16"},
    "emerald":   {"label": "Esmeralda",      "l": "#059669", "d": "#34D399", "hl": "#047857", "hd": "#059669"},
    "teal":      {"label": "Verde-Agua",     "l": "#14B8A6", "d": "#2DD4BF", "hl": "#0D9488", "hd": "#14B8A6"},
    "cyan":      {"label": "Ciano",          "l": "#06B6D4", "d": "#22D3EE", "hl": "#0891B2", "hd": "#06B6D4"},
    "sky":       {"label": "Ceu",            "l": "#0EA5E9", "d": "#38BDF8", "hl": "#0284C7", "hd": "#0EA5E9"},
}
ACCENT_PRESET_LABELS: dict[str, str] = {k: v["label"] for k, v in ACCENT_PRESETS.items()}

# ---------------------------------------------------------------------------
# Presets de Cor de Fundo principal (app background)
# ---------------------------------------------------------------------------
BG_COLOR_PRESETS: dict[str, dict[str, tuple[str, str]]] = {
    "slate":      {"app": ("#F8FAFC", "#0B0F19"), "statusbar": ("#E2E8F0", "#0F172A")},
    "gray":       {"app": ("#F9FAFB", "#111827"), "statusbar": ("#E5E7EB", "#0B1120")},
    "zinc":       {"app": ("#FAFAFA", "#09090B"), "statusbar": ("#E4E4E7", "#050507")},
    "carbon":     {"app": ("#F0F0F2", "#0A0A0C"), "statusbar": ("#D8D8E0", "#070709")},
    "navy":       {"app": ("#EEF2FF", "#050D1E"), "statusbar": ("#C7D5F5", "#040A18")},
    "midnight":   {"app": ("#EFF6FF", "#0C1222"), "statusbar": ("#DBEAFE", "#08101E")},
    "forest":     {"app": ("#F0FDF4", "#041D0D"), "statusbar": ("#DCFCE7", "#031509")},
    "amethyst":   {"app": ("#F5F3FF", "#100820"), "statusbar": ("#D8C8F8", "#08041A")},
    "sepia":      {"app": ("#FDF6EC", "#130D07"), "statusbar": ("#E8D8BC", "#0D0904")},
    "rose_bg":    {"app": ("#FFF1F2", "#1A0510"), "statusbar": ("#FECDD3", "#14040D")},
    "teal_bg":    {"app": ("#F0FDFA", "#042018"), "statusbar": ("#CCFBF1", "#031510")},
    "indigo_bg":  {"app": ("#EEF2FF", "#0E0B27"), "statusbar": ("#E0E7FF", "#09071E")},
}
BG_COLOR_PRESET_LABELS: dict[str, str] = {
    "slate":      "Slate (Padrão)",
    "gray":       "Cinza",
    "zinc":       "Zinco",
    "carbon":     "Carbono",
    "navy":       "Azul Marinho",
    "midnight":   "Meia-Noite",
    "forest":     "Floresta",
    "amethyst":   "Ametista",
    "sepia":      "Sepia",
    "rose_bg":    "Rosa",
    "teal_bg":    "Verde-Agua",
    "indigo_bg":  "Indigo",
}
# Alias de compatibilidade (settings antigos usavam 'bg_preset')
BG_PRESETS = BG_COLOR_PRESETS
BG_PRESET_LABELS = BG_COLOR_PRESET_LABELS

# ---------------------------------------------------------------------------
# Presets de Cor de Fundo dos Frames (cards, paineis, dialogs)
# ---------------------------------------------------------------------------
FRAME_BG_PRESETS: dict[str, dict[str, tuple[str, str]]] = {
    "slate":      {"panel": ("#FFFFFF", "#1E293B"), "tree": ("#FFFFFF", "#1E293B")},
    "gray":       {"panel": ("#F9FAFB", "#1F2937"), "tree": ("#F9FAFB", "#1F2937")},
    "zinc":       {"panel": ("#FAFAFA", "#18181B"), "tree": ("#FAFAFA", "#18181B")},
    "carbon":     {"panel": ("#E8E8ED", "#111111"), "tree": ("#E8E8ED", "#111111")},
    "navy":       {"panel": ("#E0E8FA", "#0D1B38"), "tree": ("#E0E8FA", "#0D1B38")},
    "midnight":   {"panel": ("#DBEAFE", "#0F1E40"), "tree": ("#DBEAFE", "#0F1E40")},
    "forest":     {"panel": ("#DCFCE7", "#052E16"), "tree": ("#DCFCE7", "#052E16")},
    "amethyst":   {"panel": ("#EDE5FF", "#1C1030"), "tree": ("#EDE5FF", "#1C1030")},
    "sepia":      {"panel": ("#F5ECD8", "#211607"), "tree": ("#F5ECD8", "#211607")},
    "rose_f":     {"panel": ("#FFE4E6", "#2D0A18"), "tree": ("#FFE4E6", "#2D0A18")},
    "teal_f":     {"panel": ("#CCFBF1", "#0A2A24"), "tree": ("#CCFBF1", "#0A2A24")},
    "indigo_f":   {"panel": ("#E0E7FF", "#1A1A3A"), "tree": ("#E0E7FF", "#1A1A3A")},
}
FRAME_BG_PRESET_LABELS: dict[str, str] = {
    "slate":      "Slate (Padrão)",
    "gray":       "Cinza",
    "zinc":       "Zinco",
    "carbon":     "Carbono",
    "navy":       "Azul Marinho",
    "midnight":   "Meia-Noite",
    "forest":     "Floresta",
    "amethyst":   "Ametista",
    "sepia":      "Sepia",
    "rose_f":     "Rosa",
    "teal_f":     "Verde-Agua",
    "indigo_f":   "Indigo",
}

# ---------------------------------------------------------------------------
# Temas curados — combinacoes prontas (destaque + fundo + frame) equilibradas
# e com contraste testado. Selecionar um aplica os tres presets de uma vez;
# o modo "Personalizado" mantem os tres dropdowns avancados.
# ---------------------------------------------------------------------------
CURATED_THEMES: dict[str, dict[str, Any]] = {
    "slate_blue":      {"label": "Ardosia & Azul",        "accent": "blue",    "bg": "slate",  "frame": "slate",  "appearance": "Light", "recommended": True},
    "graphite_indigo": {"label": "Grafite & Indigo",      "accent": "indigo",  "bg": "zinc",   "frame": "slate",  "appearance": "Light"},
    "navy_amber":      {"label": "Marinho & Ambar",       "accent": "amber",   "bg": "navy",   "frame": "navy",   "appearance": "Dark"},
    "carbon_cyan":     {"label": "Carbono & Ciano",       "accent": "cyan",    "bg": "carbon", "frame": "carbon", "appearance": "Dark"},
    "sepia_wood":      {"label": "Sepia & Madeira",       "accent": "amber",   "bg": "sepia",  "frame": "sepia",  "appearance": "Light"},
    "forest_emerald":  {"label": "Floresta & Esmeralda",  "accent": "emerald", "bg": "forest", "frame": "forest", "appearance": "Light"},
}


def curated_theme_swatches(theme_key: str) -> dict[str, str]:
    """Cores na face (claro/escuro) do tema, para o preview do cartao."""
    theme = CURATED_THEMES.get(theme_key) or CURATED_THEMES["slate_blue"]
    face = 1 if str(theme.get("appearance")) == "Dark" else 0
    bg = BG_COLOR_PRESETS.get(theme["bg"], BG_COLOR_PRESETS["slate"])
    frame = FRAME_BG_PRESETS.get(theme["frame"], FRAME_BG_PRESETS["slate"])
    accent = ACCENT_PRESETS.get(theme["accent"], ACCENT_PRESETS["blue"])
    return {
        "app":       bg["app"][face],
        "statusbar": bg["statusbar"][face],
        "panel":     frame["panel"][face],
        "accent":    accent["d"] if face else accent["l"],
        "text":      THEME_TEXT_MAIN[face],
        "sub":       THEME_TEXT_SUB[face],
    }


def match_curated_theme(accent: str, bg: str, frame: str) -> str | None:
    """Chave do tema curado cuja paleta casa com a combinacao, ou None."""
    for key, theme in CURATED_THEMES.items():
        if theme["accent"] == accent and theme["bg"] == bg and theme["frame"] == frame:
            return key
    return None


def apply_accent_preset(preset_key: str) -> None:
    """Aplica a cor de destaque no ThemeManager do CTk e no token THEME_ACCENT.

    Deve ser chamada DEPOIS de set_default_color_theme() e ANTES de criar/recriar
    os widgets — o patch no ThemeManager só alcança widgets criados depois."""
    preset = ACCENT_PRESETS.get(preset_key, ACCENT_PRESETS["blue"])
    l_color, d_color = preset["l"], preset["d"]
    hl_color, hd_color = preset["hl"], preset["hd"]

    # Patch no ThemeManager — afeta todos os widgets criados apos esta chamada
    try:
        import customtkinter as ctk
        tm = ctk.ThemeManager.theme
        for widget_cls, overrides in {
            "CTkButton":         {"fg_color": [l_color, d_color], "hover_color": [hl_color, hd_color]},
            "CTkCheckBox":       {"fg_color": [l_color, d_color], "hover_color": [hl_color, hd_color]},
            "CTkRadioButton":    {"fg_color": [l_color, d_color], "hover_color": [hl_color, hd_color]},
            "CTkSwitch":         {"progress_color": [l_color, d_color]},
            "CTkSlider":         {"progress_color": [l_color, d_color], "button_color": [l_color, d_color], "button_hover_color": [hl_color, hd_color]},
            "CTkProgressBar":    {"progress_color": [l_color, d_color]},
            "CTkOptionMenu":     {"button_color": [l_color, d_color], "button_hover_color": [hl_color, hd_color]},
            "CTkComboBox":       {"button_color": [l_color, d_color], "button_hover_color": [hl_color, hd_color]},
            "CTkSegmentedButton":{"selected_color": [l_color, d_color], "selected_hover_color": [hl_color, hd_color]},
            "CTkTabview":        {"segmented_button_selected_color": [l_color, d_color], "segmented_button_selected_hover_color": [hl_color, hd_color]},
        }.items():
            if widget_cls in tm:
                tm[widget_cls].update(overrides)
    except Exception:
        pass

    THEME_ACCENT.set(l_color, d_color)
    notify_theme_change()


def apply_bg_preset(preset_key: str) -> None:
    """Atualiza THEME_APP_BG e THEME_STATUSBAR_BG para o preset de fundo principal."""
    preset = BG_COLOR_PRESETS.get(preset_key, BG_COLOR_PRESETS["slate"])
    THEME_APP_BG.set(*preset["app"])
    THEME_STATUSBAR_BG.set(*preset["statusbar"])
    notify_theme_change()


def apply_frame_bg_preset(preset_key: str) -> None:
    """Atualiza THEME_PANEL_BG e THEME_TREE_BG para o preset de fundo dos frames."""
    preset = FRAME_BG_PRESETS.get(preset_key, FRAME_BG_PRESETS["slate"])
    THEME_PANEL_BG.set(*preset["panel"])
    THEME_TREE_BG.set(*preset["tree"])
    notify_theme_change()


