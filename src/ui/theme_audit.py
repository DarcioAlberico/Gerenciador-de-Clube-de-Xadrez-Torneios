"""Contrato de contraste do tema — quais cores se encontram na tela (B-2 / P2-11).

Módulo puro (sem Tk): monta, para uma combinação de presets e uma face
(clara/escura), a lista de pares que a interface realmente produz, e entrega a
:mod:`src.ui.contrast` a tarefa de medir.

**O contrato é a parte difícil, não a conta.** Medir contraste é aritmética de
dez linhas; saber que o rótulo de ajuda cai sobre o painel — e que o painel muda
com o preset de frames — é o que faz a auditoria valer. Um par que existe na tela
e não está aqui é um ponto cego, então cada entrada aponta onde nasce.

Note que ``pick()`` **não** é usado: ele lê a aparência em vigor no processo, e
uma auditoria que depende do estado global só saberia auditar o tema aberto.
Aqui a face é parâmetro.
"""
from __future__ import annotations

from typing import Iterator

from .contrast import (
    AA_UI_COMPONENT,
    COMPONENT,
    FILL,
    SURFACE,
    TABLE,
    ContrastPair,
    best_ink,
)
from .theme import (
    ACCENT_PRESETS,
    BG_COLOR_PRESETS,
    CURATED_THEMES,
    FRAME_BG_PRESETS,
    RESULT_STATE_COLORS,
    THEME_DANGER,
    THEME_ON_DANGER,
    THEME_ON_SUCCESS,
    THEME_ON_WARNING,
    THEME_RESULT_BYE,
    THEME_RESULT_DRAW,
    THEME_RESULT_WIN,
    THEME_SUCCESS,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_TREE_EVEN,
    THEME_TREE_FG,
    THEME_TREE_HEADING,
    THEME_TREE_ODD,
    THEME_TREE_SELECTED,
    THEME_TREE_SELECTED_FG,
    THEME_WARNING,
    THEME_WARNING_TEXT,
    field_palette,
)

LIGHT, DARK = 0, 1
FACE_LABEL = {LIGHT: "claro", DARK: "escuro"}


def theme_pairs(accent: str, bg: str, frame: str, face: int) -> list[ContrastPair]:
    """Todos os encontros de cor de uma combinação de presets, numa face."""
    accent_color = ACCENT_PRESETS[accent]["d" if face == DARK else "l"]
    # A tinta sobre o accent e calculada em apply_accent_preset; a auditoria
    # refaz a mesma conta em vez de ler o token, que reflete o preset aplicado
    # no processo — auditar o estado global so saberia auditar o tema aberto.
    on_accent = best_ink(accent_color)
    app_bg = BG_COLOR_PRESETS[bg]["app"][face]
    statusbar = BG_COLOR_PRESETS[bg]["statusbar"][face]
    panel = FRAME_BG_PRESETS[frame]["panel"][face]

    # O preset de fundo PODE trazer a cor do texto (hoje so o de alto
    # contraste, ver apply_bg_preset). Ler o token global aqui faria a
    # auditoria medir um texto que aquele tema nao usa.
    preset_bg = BG_COLOR_PRESETS[bg]
    text_main = preset_bg.get("text", tuple(THEME_TEXT_MAIN))[face]
    text_sub = preset_bg.get("sub", tuple(THEME_TEXT_SUB))[face]
    tree_fg = THEME_TREE_FG[face]
    zebra = {"ímpar": THEME_TREE_ODD[face], "par": THEME_TREE_EVEN[face]}

    pares: list[ContrastPair] = [
        # --- Texto sobre superfície -------------------------------------- #
        ContrastPair("texto principal sobre painel", text_main, panel, kind=SURFACE),
        ContrastPair("texto de apoio sobre painel", text_sub, panel),
        ContrastPair("texto principal sobre fundo da janela", text_main, app_bg),
        ContrastPair("texto de apoio sobre fundo da janela", text_sub, app_bg),
        ContrastPair("texto da barra de status", text_main, statusbar),
        ContrastPair("aviso como texto sobre painel", THEME_WARNING_TEXT[face], panel, kind=FILL),
        # --- Texto sobre preenchimento ----------------------------------- #
        ContrastPair("rótulo do botão primário", on_accent, accent_color, kind=FILL),
        ContrastPair("rótulo do botão de perigo", THEME_ON_DANGER[face], THEME_DANGER[face], kind=FILL),
        ContrastPair("toast de informação", on_accent, accent_color, kind=FILL),
        ContrastPair("toast de sucesso", THEME_ON_SUCCESS[face], THEME_SUCCESS[face], kind=FILL),
        ContrastPair("toast de erro", THEME_ON_DANGER[face], THEME_DANGER[face], kind=FILL),
        ContrastPair("toast de aviso", THEME_ON_WARNING[face], THEME_WARNING[face], kind=FILL),
        # --- Tabelas ------------------------------------------------------ #
        ContrastPair("cabeçalho da tabela", tree_fg, THEME_TREE_HEADING[face], kind=TABLE),
        ContrastPair(
            "linha selecionada",
            THEME_TREE_SELECTED_FG[face],
            THEME_TREE_SELECTED[face],
            kind=TABLE,
        ),
        # --- Componente de interface (não é texto: limite 3:1) ------------ #
        ContrastPair("destaque sobre painel", accent_color, panel, AA_UI_COMPONENT, COMPONENT),
    ]

    # --- Campos de entrada (F5.1 / P3-2) ---------------------------------- #
    # Antes da F5.1 o auditor tinha ZERO pares de campo — por isso a borda de
    # fabrica a 2.74:1 nunca apareceu no relatorio. A paleta e derivada do
    # painel pela mesma funcao pura que o preset usa: auditor e tema nao podem
    # divergir. O rotulo do seletor (accent) ja e coberto pelo par do botao
    # primario, pois desde a F5.1 o corpo do OptionMenu E o accent.
    campo = field_palette(panel)
    pares += [
        ContrastPair(
            "borda do campo sobre painel", campo["border"], panel, AA_UI_COMPONENT, COMPONENT
        ),
        ContrastPair("texto do campo sobre o campo", campo["text"], campo["bg"], kind=SURFACE),
        # Placeholder e texto de apoio efemero: cobra AA, mas nao entra na
        # familia SURFACE — exigir AAA dele no alto contraste o tornaria tao
        # escuro quanto o texto real, e a dica pararia de parecer dica.
        ContrastPair("placeholder sobre o campo", campo["placeholder"], campo["bg"], kind=FILL),
    ]

    for nome, fundo in zebra.items():
        pares.append(ContrastPair(f"texto da tabela (linha {nome})", tree_fg, fundo, kind=TABLE))
        for rotulo, token in (
            ("vitória", THEME_RESULT_WIN),
            ("empate", THEME_RESULT_DRAW),
            ("bye", THEME_RESULT_BYE),
        ):
            pares.append(
                ContrastPair(f"resultado {rotulo} (linha {nome})", token[face], fundo, kind=TABLE)
            )

    # Estado do resultado: cada um traz o próprio fundo, ou herda a zebra.
    for estado, (frente, fundo_token) in RESULT_STATE_COLORS.items():
        if fundo_token is None:
            for nome, fundo in zebra.items():
                pares.append(
                    ContrastPair(f"estado '{estado}' (linha {nome})", frente[face], fundo, kind=TABLE)
                )
        else:
            pares.append(
                ContrastPair(f"estado '{estado}'", frente[face], fundo_token[face], kind=TABLE)
            )

    return pares


def curated_pairs() -> Iterator[tuple[str, int, list[ContrastPair]]]:
    """Os temas que o app **oferece pronto**, na face que cada um abre.

    É o conjunto que precisa passar sem ressalva: um tema curado reprovado é um
    tema que o app entrega quebrado, não uma combinação que o usuário montou.
    """
    for key, theme in CURATED_THEMES.items():
        face = DARK if str(theme.get("appearance")) == "Dark" else LIGHT
        yield key, face, theme_pairs(theme["accent"], theme["bg"], theme["frame"], face)


def all_combination_pairs() -> Iterator[tuple[str, int, list[ContrastPair]]]:
    """Toda combinação que o modo avançado permite montar (accent × fundo × frame).

    Muito maior que o conjunto curado, e por isso serve de **relatório**, não de
    gate: o usuário pode escolher amarelo sobre bege, e impedi-lo seria tirar
    dele uma decisão que é dele.
    """
    for accent in ACCENT_PRESETS:
        for bg in BG_COLOR_PRESETS:
            for frame in FRAME_BG_PRESETS:
                for face in (LIGHT, DARK):
                    yield (
                        f"{accent}/{bg}/{frame}",
                        face,
                        theme_pairs(accent, bg, frame, face),
                    )
