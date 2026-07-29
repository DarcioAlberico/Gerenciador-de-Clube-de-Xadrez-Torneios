"""Factories de campo de entrada — anatomia única (F5.2 / ESPEC_UI_UX §4.6).

O que as factories fecham, e que solto em cada tela virava variação (P3-3/5/6):

- **altura única de 36px** (``FIELD_HEIGHT``, a mesma dos botões): campo e botão
  alinham na mesma linha — antes o campo nascia com 28px ao lado de botões de 36;
- **escala fechada de larguras**: ``FIELD_SM`` (números/datas), ``FIELD_MD``
  (padrão), ``FIELD_LG`` (nomes/caminhos) — no lugar das 67 larguras distintas;
  para ocupar a coluna toda, posicione com ``sticky="ew"`` (o ``width`` vira
  mínimo, não use larguras fora da escala para isso);
- **placeholder obrigatório** em campo de texto: a caixa vazia sem dica era a
  regra (94 de 150 campos);
- **raio e fonte únicos** (``FIELD_RADIUS``, ``font_field``).

As CORES não são passadas aqui de propósito (exceto no ``select_field``): desde a
F5.1 elas vêm dos padrões do ``ThemeManager`` patchados pelos presets, e é isso
que deixa o ``restyle.py`` repintar os campos na troca de tema.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..theme import (
    SPACE_XS,
    THEME_ACCENT,
    THEME_FIELD_BG,
    THEME_FIELD_BORDER,
    THEME_FIELD_TEXT,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_TREE_EVEN,
    font_field,
    font_field_label,
)

# Mesma altura de components/buttons.py (_DEFAULT_HEIGHT): e o alinhamento
# campo-botao na mesma linha que define a escala, nao um numero solto.
FIELD_HEIGHT = 36
FIELD_RADIUS = 6

# Escala fechada de larguras (ESPEC §4.6). FULL nao e uma largura: e grid com
# sticky="ew" — use FIELD_MD como minimo e deixe a coluna esticar.
FIELD_SM = 120
FIELD_MD = 240
FIELD_LG = 360


def text_field(master: Any, *, placeholder: str, **kwargs: Any) -> ctk.CTkEntry:
    """Campo de texto de uma linha. ``placeholder`` é obrigatório (P3-6):
    a dica de formato ("Ex.: 90'+30\"", "dd/mm/aaaa") faz parte da anatomia."""
    kwargs.setdefault("width", FIELD_MD)
    kwargs.setdefault("height", FIELD_HEIGHT)
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("font", font_field())
    return ctk.CTkEntry(master, placeholder_text=placeholder, **kwargs)


def select_field(
    master: Any,
    *,
    values: list[str],
    command: Callable[[str], None] | None = None,
    variable: Any = None,
    **kwargs: Any,
) -> ctk.CTkOptionMenu:
    """Seleção com anatomia de CAMPO, não de botão (P3-5).

    O ``CTkOptionMenu`` padrão é um bloco preenchido com o accent — correto para
    ação, errado para dado: numa coluna de formulário ele alterna caixa clara /
    bloco de cor. Aqui o corpo usa o fundo de campo do tema, o texto usa a tinta
    de campo e o chevron fica na cor da borda; o dropdown segue o painel. As
    cores são os *tokens vivos* (mutados pelo preset), então o ``restyle``
    reaplica a troca de tema normalmente.
    """
    kwargs.setdefault("width", FIELD_MD)
    kwargs.setdefault("height", FIELD_HEIGHT)
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("font", font_field())
    kwargs.setdefault("fg_color", THEME_FIELD_BG)
    kwargs.setdefault("text_color", THEME_FIELD_TEXT)
    kwargs.setdefault("button_color", THEME_FIELD_BORDER)
    kwargs.setdefault("button_hover_color", THEME_ACCENT)
    kwargs.setdefault("dropdown_fg_color", THEME_PANEL_BG)
    kwargs.setdefault("dropdown_text_color", THEME_TEXT_MAIN)
    kwargs.setdefault("dropdown_hover_color", THEME_TREE_EVEN)
    return ctk.CTkOptionMenu(master, values=values, command=command, variable=variable, **kwargs)


def text_area(master: Any, *, height: int = 110, **kwargs: Any) -> ctk.CTkTextbox:
    """Texto multilinha. Nasce com borda de 1px (P3-5): o ``CTkTextbox`` de
    fábrica tem ``border_width=0`` e vira uma área invisível sobre o painel.
    Alturas em passos: 80 (curta), 110 (padrão), 200 (corpo de mensagem)."""
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("wrap", "word")
    kwargs.setdefault("font", font_field())
    return ctk.CTkTextbox(master, height=height, **kwargs)


def date_field(master: Any, **kwargs: Any) -> Any:
    """Campo de data do app: ``MaskedDateEntry`` (máscara, clamp, calendário),
    dimensionado pela escala. Único campo de data permitido — nada de
    ``DateEntry`` nativo destoando do tema."""
    from ..support import MaskedDateEntry  # tardio: support importa components

    kwargs.setdefault("width", FIELD_SM)
    kwargs.setdefault("height", FIELD_HEIGHT)
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("font", font_field())
    return MaskedDateEntry(master, **kwargs)


def labeled_field(
    master: Any,
    label: str,
    builder: Callable[[ctk.CTkFrame], Any],
    **kwargs: Any,
) -> tuple[ctk.CTkFrame, Any]:
    """Rótulo ACIMA do campo como unidade única (container transparente).

    ``builder`` recebe o container e devolve o campo (``text_field``,
    ``select_field``, ...). Devolve ``(container, campo)`` — a tela posiciona o
    container e guarda o campo. Fecha o espaçamento rótulo→campo em
    ``SPACE_XS``, que solto variava em mais de dez combinações de ``pady``.
    """
    box = ctk.CTkFrame(master, fg_color="transparent", **kwargs)
    box.grid_columnconfigure(0, weight=1)
    rotulo = ctk.CTkLabel(
        box, text=label, font=font_field_label(), text_color=THEME_TEXT_SUB, anchor="w"
    )
    rotulo.grid(row=0, column=0, sticky="w")
    campo = builder(box)
    campo.grid(row=1, column=0, sticky="ew", pady=(SPACE_XS, 0))
    return box, campo
