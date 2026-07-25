"""Factories de botão com hierarquia visual padronizada.

Três níveis, uma única linguagem visual em todo o app (ver ESPEC_UI_UX §4.4):

- ``primary_button``   — ação principal da tela (preenchida com a cor de destaque).
- ``secondary_button`` — ação de apoio (contorno, fundo transparente).
- ``danger_button``    — ação destrutiva (cor de perigo do tema), visualmente isolada.

As factories centralizam cor/altura/raio para que nenhuma tela precise repetir
``fg_color=...``/``height=...`` à mão. As cores vêm dos tokens ``THEME_*`` — nunca
literais hex — então acompanham o tema/accent escolhido pelo usuário.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..theme import THEME_DANGER, THEME_DANGER_HOVER, THEME_TEXT_MAIN
from .tooltip import Tooltip

_DEFAULT_HEIGHT = 36


def _with_tip(button: ctk.CTkButton, tip: str | None) -> ctk.CTkButton:
    """Anexa um ``Tooltip`` ao botão quando ``tip`` é informado e o devolve."""
    if tip:
        Tooltip(button, tip)
    return button


def primary_button(
    master: Any,
    text: str,
    command: Callable[[], None] | None = None,
    *,
    tip: str | None = None,
    **kwargs: Any,
) -> ctk.CTkButton:
    """Ação principal. Usa a cor de destaque do tema (fg_color padrão do CTkButton,
    já alinhado ao accent via ``apply_accent_preset``)."""
    kwargs.setdefault("height", _DEFAULT_HEIGHT)
    return _with_tip(ctk.CTkButton(master, text=text, command=command, **kwargs), tip)


def secondary_button(
    master: Any,
    text: str,
    command: Callable[[], None] | None = None,
    *,
    tip: str | None = None,
    **kwargs: Any,
) -> ctk.CTkButton:
    """Ação de apoio: contorno discreto, fundo transparente, texto na cor principal."""
    kwargs.setdefault("height", _DEFAULT_HEIGHT)
    kwargs.setdefault("fg_color", "transparent")
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("text_color", THEME_TEXT_MAIN)
    return _with_tip(ctk.CTkButton(master, text=text, command=command, **kwargs), tip)


def danger_button(
    master: Any,
    text: str,
    command: Callable[[], None] | None = None,
    *,
    tip: str | None = None,
    **kwargs: Any,
) -> ctk.CTkButton:
    """Ação destrutiva (excluir/restaurar): cor de perigo do tema. Posicione-a
    separada das ações comuns (ver ESPEC_UI_UX §5.1)."""
    kwargs.setdefault("height", _DEFAULT_HEIGHT)
    kwargs.setdefault("fg_color", THEME_DANGER)
    kwargs.setdefault("hover_color", THEME_DANGER_HOVER)
    return _with_tip(ctk.CTkButton(master, text=text, command=command, **kwargs), tip)
