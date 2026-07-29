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

from .contrast import (
    AA_NORMAL_TEXT,
    AA_UI_COMPONENT,
    best_ink,
    contrast_ratio,
    mix_hex,
    relative_luminance,
)

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
# Escurecido na face clara pela auditoria da B-2: #64748B dava 4.33:1 sobre os
# paineis mais claros (forest, sepia) — reprovava AA por pouco, justamente no
# texto de ajuda, que e onde o usuario menos consegue "chutar" o que esta escrito.
THEME_TEXT_SUB     = ColorToken("#526070", "#94A3B8")
THEME_STATUSBAR_BG = ColorToken("#E2E8F0", "#0F172A")
THEME_TREE_BG      = ColorToken("#FFFFFF", "#1E293B")
THEME_TREE_FG      = ColorToken("#0F172A", "#F1F5F9")
THEME_ACCENT        = ColorToken("#2563EB", "#38BDF8")
# Texto POR CIMA do accent (botao primario, toast, faixa de marca do login).
# Valor inicial so para o caso de ninguem aplicar preset; apply_accent_preset
# recalcula com best_ink — ver a nota sobre tinta calculada, mais abaixo.
THEME_ON_ACCENT     = ColorToken("#FFFFFF", "#0B0F19")
# Perigo e sucesso escurecidos na face clara (B-2): com os valores 500 do
# Tailwind, texto branco por cima ficava em 3.7:1 — o botao de excluir era o
# menos legivel da tela, que e o oposto do que ele precisa ser.
THEME_DANGER        = ColorToken("#C81E1E", "#F87171")
THEME_DANGER_HOVER  = ColorToken("#B91C1C", "#DC2626")
THEME_INFO          = ColorToken("#047857", "#34D399")
THEME_SUCCESS       = ColorToken("#047857", "#34D399")
THEME_SUCCESS_HOVER = ColorToken("#065F46", "#10B981")
# Aviso em dois papeis: PREENCHIMENTO (fundo de toast) e TEXTO sobre painel.
THEME_WARNING       = ColorToken("#D97706", "#FBBF24")
THEME_WARNING_HOVER = ColorToken("#B45309", "#F59E0B")
# Aviso COMO TEXTO precisa ser mais escuro que o aviso como preenchimento:
# #B45309 dava 4.27:1 sobre o painel sépia (B-2).
THEME_WARNING_TEXT  = ColorToken("#92400E", "#FBBF24")
THEME_NEUTRAL       = ColorToken("#526070", "#475569")
THEME_NEUTRAL_HOVER = ColorToken("#475569", "#334155")

# ---------------------------------------------------------------------------
# Tinta sobre preenchimento — CALCULADA, nunca escolhida a mao (B-2 / P2-11).
#
# A auditoria mostrou que o texto branco cravado reprovava em massa: sobre o
# ambar do toast de aviso dava 3.19:1, e o rotulo padrao do customtkinter
# (#DCE4EE) sobre o accent amarelo dava 1.30:1 — praticamente invisivel.
# best_ink escolhe entre tinta clara e escura pela razao de contraste, entao
# botao amarelo nasce com texto escuro e botao indigo com texto claro sem que
# ninguem precise manter uma tabela de excecoes.
# ---------------------------------------------------------------------------
def _ink_token(fill: ColorToken) -> ColorToken:
    """Par de tintas legiveis sobre as duas faces de ``fill``."""
    return ColorToken(best_ink(fill[0]), best_ink(fill[1]))


THEME_ON_DANGER  = _ink_token(THEME_DANGER)
THEME_ON_SUCCESS = _ink_token(THEME_SUCCESS)
THEME_ON_WARNING = _ink_token(THEME_WARNING)

# ---------------------------------------------------------------------------
# Tabelas (ttk.Treeview). O ttk NAO aceita par (claro, escuro): a cor tem de ser
# resolvida com pick() no momento de configurar o estilo. Estes tokens existem
# porque antes as tabelas eram pintadas com valores fixos de modo escuro — no
# tema claro a tabela ficava escura no meio da tela clara.
# ---------------------------------------------------------------------------
THEME_TREE_ODD        = ColorToken("#FFFFFF", "#1E293B")
THEME_TREE_EVEN       = ColorToken("#F1F5F9", "#172032")
THEME_TREE_HEADING    = ColorToken("#CBD5E1", "#0F172A")
# Selecao escurecida na face clara (B-2): o azul 500 dava 3.68:1 com texto
# branco. A linha selecionada e a que o operador esta lendo para digitar o
# resultado — ela nao pode ser a menos legivel da tabela.
THEME_TREE_SELECTED   = ColorToken("#1D4ED8", "#334155")
THEME_TREE_SELECTED_FG = ColorToken("#FFFFFF", "#F1F5F9")

# Estado de um resultado na tabela de rodadas: (texto, fundo). Fundo None herda
# a zebra. Semantica, nao decoracao — e por isso que mora aqui e nao na tela.
# Os cinzas "apagados" (vazio/anulado/bye) foram os piores achados da B-2:
# #94A3B8 sobre linha clara dava 2.34:1. Um estado discreto continua discreto
# em #5C6B80 — o que ele nao pode e ser ilegivel, porque "anulado" e "bye"
# mudam o que o arbitro faz com aquela mesa.
RESULT_STATE_COLORS: dict[str, tuple[ColorToken, ColorToken | None]] = {
    "vazio":         (ColorToken("#5A6678", "#94A3B8"), None),
    "registrado":    (ColorToken("#047857", "#86EFAC"), None),
    "submetido_qr":  (ColorToken("#92400E", "#FCD34D"), ColorToken("#FEF9C3", "#1C1A0A")),
    "aprovado_qr":   (ColorToken("#047857", "#34D399"), ColorToken("#ECFDF5", "#042010")),
    "rejeitado_qr":  (ColorToken("#B91C1C", "#FCA5A5"), ColorToken("#FEF2F2", "#1C0505")),
    "corrigido":     (ColorToken("#6D28D9", "#C4B5FD"), ColorToken("#F5F3FF", "#12080A")),
    "anulado":       (ColorToken("#5C6B80", "#8A97A8"), None),
}

# Resultado lancado (vitoria/empate/bye) — usado nas tags da mesma tabela.
THEME_RESULT_WIN  = ColorToken("#B45309", "#FACC15")
THEME_RESULT_DRAW = ColorToken("#5A6678", "#94A3B8")
THEME_RESULT_BYE  = ColorToken("#5C6B80", "#8A97A8")

# ---------------------------------------------------------------------------
# Campos de entrada (F5.1 / P3-1, P3-2 — ESPEC_UI_UX §4.6).
#
# Antes da F5.1 os campos usavam as cores de FABRICA do customtkinter: fundo
# #F9F9FA/#343638 e borda #979DA2/#565B5E, que nao acompanham preset nenhum —
# a borda dava 2.74:1 sobre painel claro (reprova os 3:1 de componente) e o
# campo sumia nos paineis sepia/floresta (1.04:1). Aqui as cores sao DERIVADAS
# do painel por field_palette(): um preset de painel novo ja nasce com campos
# coerentes, sem tabela para manter.
#
# Tintas do campo (par fixo): as mesmas do texto padrao do app.
_FIELD_INK_DARK = "#0F172A"
_FIELD_INK_LIGHT = "#F1F5F9"


def _least_mix(base: str, ink: str, over: str, minimum: float) -> str:
    """A menor mistura de ``ink`` em ``base`` que alcanca ``minimum`` sobre ``over``.

    Procurada, nao escolhida: e o que garante o limite por construcao para
    qualquer painel — inclusive os que ainda nao existem. A margem de 0.05
    evita a beirada do arredondamento em duas casas usado pelo auditor.
    """
    for passo in range(5, 101, 5):
        candidata = mix_hex(base, ink, passo / 100)
        if contrast_ratio(candidata, over) >= minimum + 0.05:
            return candidata
    return ink


def field_palette(panel: str) -> dict[str, str]:
    """Paleta de campo derivada de UMA cor de painel. Pura — serve ao preset e a auditoria.

    Regras (ESPEC_UI_UX §4.6):

    - ``bg``: proximo do painel, deslocado para a direcao clara da face — em
      painel tingido (sepia, floresta) o campo conserva a temperatura em vez do
      cinza-azulado de fabrica;
    - ``border``: >= 3:1 sobre o painel (AA de componente de interface);
    - ``text`` e ``placeholder``: >= 4.5:1 sobre o fundo do campo.
    """
    face_clara = relative_luminance(panel) >= 0.4
    ink = _FIELD_INK_DARK if face_clara else _FIELD_INK_LIGHT
    bg = mix_hex(panel, "#FFFFFF", 0.85 if face_clara else 0.10)
    return {
        "bg": bg,
        "border": _least_mix(panel, ink, over=panel, minimum=AA_UI_COMPONENT),
        "text": ink,
        "placeholder": _least_mix(bg, ink, over=bg, minimum=AA_NORMAL_TEXT),
    }


def _field_tokens_from_panels(panel_light: str, panel_dark: str) -> dict[str, tuple[str, str]]:
    """As duas faces de cada token de campo, a partir do par de paineis."""
    claro, escuro = field_palette(panel_light), field_palette(panel_dark)
    return {chave: (claro[chave], escuro[chave]) for chave in ("bg", "border", "text", "placeholder")}


_campos_iniciais = _field_tokens_from_panels("#FFFFFF", "#1E293B")
THEME_FIELD_BG     = ColorToken(*_campos_iniciais["bg"])
THEME_FIELD_BORDER = ColorToken(*_campos_iniciais["border"])
THEME_FIELD_TEXT   = ColorToken(*_campos_iniciais["text"])
THEME_PLACEHOLDER  = ColorToken(*_campos_iniciais["placeholder"])
# Foco = accent, erro = perigo: ALIASES do mesmo objeto, de proposito — quando
# apply_accent_preset muta THEME_ACCENT, o anel de foco acompanha sozinho.
THEME_FIELD_BORDER_FOCUS = THEME_ACCENT
THEME_FIELD_BORDER_ERROR = THEME_DANGER


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
# A face CLARA usa a faixa 600/700; a ESCURA, a faixa 300/400 (B-2 / P2-11).
# Nao e capricho de paleta: os tons 500 nascem para viver sobre fundo escuro, e
# sobre painel claro nenhum deles alcancava os 3:1 que um componente de
# interface precisa — nem mesmo o azul padrao (2.99:1). Com a faixa escura, os
# quinze presets passam como componente E como preenchimento de botao.
ACCENT_PRESETS: dict[str, dict[str, str]] = {
    "blue":      {"label": "Azul",          "l": "#2563EB", "d": "#38BDF8", "hl": "#1D4ED8", "hd": "#0EA5E9"},
    "indigo":    {"label": "Indigo",         "l": "#4F46E5", "d": "#818CF8", "hl": "#4338CA", "hd": "#6366F1"},
    "violet":    {"label": "Violeta",        "l": "#7C3AED", "d": "#A78BFA", "hl": "#6D28D9", "hd": "#8B5CF6"},
    "purple":    {"label": "Roxo",           "l": "#9333EA", "d": "#C084FC", "hl": "#7E22CE", "hd": "#A855F7"},
    "pink":      {"label": "Rosa",           "l": "#DB2777", "d": "#F472B6", "hl": "#BE185D", "hd": "#EC4899"},
    "rose":      {"label": "Rosa Choque",    "l": "#E11D48", "d": "#FB7185", "hl": "#BE123C", "hd": "#F43F5E"},
    "red":       {"label": "Vermelho",       "l": "#DC2626", "d": "#F87171", "hl": "#B91C1C", "hd": "#EF4444"},
    "orange":    {"label": "Laranja",        "l": "#C2410C", "d": "#FB923C", "hl": "#9A3412", "hd": "#F97316"},
    "amber":     {"label": "Ambar",          "l": "#B45309", "d": "#FBBF24", "hl": "#92400E", "hd": "#F59E0B"},
    "yellow":    {"label": "Amarelo",        "l": "#A16207", "d": "#FACC15", "hl": "#854D0E", "hd": "#EAB308"},
    "lime":      {"label": "Lima",           "l": "#4D7C0F", "d": "#A3E635", "hl": "#3F6212", "hd": "#84CC16"},
    "emerald":   {"label": "Esmeralda",      "l": "#047857", "d": "#34D399", "hl": "#065F46", "hd": "#059669"},
    "teal":      {"label": "Verde-Agua",     "l": "#0F766E", "d": "#2DD4BF", "hl": "#115E59", "hd": "#14B8A6"},
    "cyan":      {"label": "Ciano",          "l": "#0E7490", "d": "#22D3EE", "hl": "#155E75", "hd": "#06B6D4"},
    "sky":       {"label": "Ceu",            "l": "#0369A1", "d": "#38BDF8", "hl": "#075985", "hd": "#0EA5E9"},
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
    # Alto contraste (B-2 / ESPEC §6). Unico preset que tambem troca o TEXTO:
    # o ganho de acessibilidade mora justamente no cinza de apoio, que nos
    # outros temas fica em ~6:1 e aqui sobe para AAA. Ver _TEXT_DEFAULTS.
    "contrast":   {
        "app": ("#FFFFFF", "#000000"),
        "statusbar": ("#DDDDDD", "#000000"),
        "text": ("#000000", "#FFFFFF"),
        "sub": ("#1F2937", "#E5E7EB"),
    },
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
    "contrast":   "Alto Contraste",
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
    # Painel levemente destacado do fundo: em alto contraste a estrutura da
    # tela nao pode depender so de sombra, que e o que some quando o usuario
    # aumenta o contraste do sistema operacional.
    "contrast":   {"panel": ("#EFEFEF", "#141414"), "tree": ("#FFFFFF", "#000000")},
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
    "contrast":   "Alto Contraste",
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
    "alto_contraste":  {"label": "Alto Contraste",        "accent": "blue",    "bg": "contrast", "frame": "contrast", "appearance": "Light"},
}

# Temas que a auditoria de contraste (B-2) cobra em nível AAA (7:1) no texto,
# e não apenas AA. Existe um só: prometer "alto contraste" e entregar o mesmo
# 4.5:1 dos outros seria vender o nome sem o conteúdo.
HIGH_CONTRAST_THEMES = {"alto_contraste"}


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
        # O preset pode trazer o proprio texto (alto contraste): o cartao tem de
        # mostrar o tema que sera aplicado, nao o texto do tema em vigor.
        "text":      bg.get("text", tuple(THEME_TEXT_MAIN))[face],
        "sub":       bg.get("sub", tuple(THEME_TEXT_SUB))[face],
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
    # Tinta do rotulo calculada a partir do proprio accent (B-2). O padrao do
    # customtkinter e um cinza-claro fixo (#DCE4EE) que sobre o accent amarelo
    # dava 1.30:1 — texto que so existe no codigo, nao na tela.
    on_light, on_dark = best_ink(l_color), best_ink(d_color)
    THEME_ON_ACCENT.set(on_light, on_dark)

    # Patch no ThemeManager — afeta todos os widgets criados apos esta chamada
    try:
        import customtkinter as ctk
        tm = ctk.ThemeManager.theme
        for widget_cls, overrides in {
            "CTkButton":         {"fg_color": [l_color, d_color], "hover_color": [hl_color, hd_color], "text_color": [on_light, on_dark]},
            "CTkCheckBox":       {"fg_color": [l_color, d_color], "hover_color": [hl_color, hd_color]},
            "CTkRadioButton":    {"fg_color": [l_color, d_color], "hover_color": [hl_color, hd_color]},
            "CTkSwitch":         {"progress_color": [l_color, d_color]},
            "CTkSlider":         {"progress_color": [l_color, d_color], "button_color": [l_color, d_color], "button_hover_color": [hl_color, hd_color]},
            "CTkProgressBar":    {"progress_color": [l_color, d_color]},
            # F5.1 / P3-1: antes so a "setinha" (button_color) acompanhava o
            # accent — o CORPO do OptionMenu ficava no azul de fabrica em 141
            # widgets. Agora corpo e rotulo seguem o accent, com tinta calculada.
            "CTkOptionMenu":     {"fg_color": [l_color, d_color], "button_color": [hl_color, hd_color], "button_hover_color": [hl_color, hd_color], "text_color": [on_light, on_dark]},
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


# Cor de texto de todos os presets menos o de alto contraste. Guardada aqui
# para que sair do alto contraste seja tao simples quanto entrar — sem isso, o
# preto puro ficaria grudado no tema seguinte.
_TEXT_DEFAULTS = {"text": ("#0F172A", "#F1F5F9"), "sub": ("#526070", "#94A3B8")}


def apply_bg_preset(preset_key: str) -> None:
    """Atualiza THEME_APP_BG e THEME_STATUSBAR_BG para o preset de fundo principal.

    O preset pode ainda trazer ``text``/``sub`` (hoje só o de alto contraste);
    quem não traz recebe de volta o texto padrão.
    """
    preset = BG_COLOR_PRESETS.get(preset_key, BG_COLOR_PRESETS["slate"])
    THEME_APP_BG.set(*preset["app"])
    THEME_STATUSBAR_BG.set(*preset["statusbar"])
    THEME_TEXT_MAIN.set(*preset.get("text", _TEXT_DEFAULTS["text"]))
    THEME_TEXT_SUB.set(*preset.get("sub", _TEXT_DEFAULTS["sub"]))
    notify_theme_change()


def _patch_field_defaults() -> None:
    """Leva os tokens de campo aos padroes do ThemeManager (F5.1 / P3-1).

    Sem isto os campos nascem com as cores de fabrica do customtkinter e nunca
    acompanham preset nenhum. Com o padrao patchado, campos novos ja nascem
    certos e o restyle.py repinta os existentes na troca de tema — a
    infraestrutura ja sabia reestilizar CTkEntry/CTkTextbox e rodava a vazio
    porque o padrao nunca mudava.
    """
    try:
        import customtkinter as ctk
        tm = ctk.ThemeManager.theme
        for widget_cls, overrides in {
            "CTkEntry": {
                "fg_color": list(THEME_FIELD_BG),
                "border_color": list(THEME_FIELD_BORDER),
                "text_color": list(THEME_FIELD_TEXT),
                "placeholder_text_color": list(THEME_PLACEHOLDER),
            },
            "CTkTextbox": {
                "fg_color": list(THEME_FIELD_BG),
                "border_color": list(THEME_FIELD_BORDER),
                "text_color": list(THEME_FIELD_TEXT),
            },
            "CTkComboBox": {
                "fg_color": list(THEME_FIELD_BG),
                "border_color": list(THEME_FIELD_BORDER),
                "text_color": list(THEME_FIELD_TEXT),
            },
        }.items():
            if widget_cls in tm:
                tm[widget_cls].update(overrides)
    except Exception:
        pass


def apply_frame_bg_preset(preset_key: str) -> None:
    """Atualiza THEME_PANEL_BG e THEME_TREE_BG para o preset de fundo dos frames.

    Os tokens de campo (THEME_FIELD_*) sao derivados AQUI, porque o campo vive
    sobre o painel: trocar o painel e o que muda o que "coerente" significa.
    """
    preset = FRAME_BG_PRESETS.get(preset_key, FRAME_BG_PRESETS["slate"])
    THEME_PANEL_BG.set(*preset["panel"])
    THEME_TREE_BG.set(*preset["tree"])
    campos = _field_tokens_from_panels(*preset["panel"])
    THEME_FIELD_BG.set(*campos["bg"])
    THEME_FIELD_BORDER.set(*campos["border"])
    THEME_FIELD_TEXT.set(*campos["text"])
    THEME_PLACEHOLDER.set(*campos["placeholder"])
    _patch_field_defaults()
    notify_theme_change()


