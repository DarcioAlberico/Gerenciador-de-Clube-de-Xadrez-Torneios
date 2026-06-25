"""Botão de menu suspenso para recolher ações secundárias.

Em vez de espalhar dezenas de botões de mesmo peso ("wall of buttons"), as ações
de apoio (exportar, imprimir, utilitários) ficam atrás de um único ``"Texto ▾"``
(ver ESPEC_UI_UX §4.4 e princípio P2: hierarquia antes de densidade).

O menu usa ``tk.Menu`` — o mesmo widget da barra de menus do app — então herda de
graça navegação por teclado e fechamento ao clicar fora; aqui ele recebe as cores
do tema para não destoar da interface. O menu é remontado a cada abertura, logo
reflete o estado atual (itens podem ser habilitados/desabilitados dinamicamente).

Uso::

    from src.ui.components import menu_button
    menu_button(
        toolbar,
        "Exportar",
        [
            ("Exportar rodada", self._export_round),
            None,                                    # separador
            ("Imprimir sumulas", self._print_sheets),
        ],
        tip="Exportar/imprimir a rodada atual.",
    ).grid(row=0, column=1)
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional, Sequence, Tuple

import customtkinter as ctk

from ..support import (
    THEME_ACCENT,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
)
from .tooltip import Tooltip

__all__ = ["menu_button", "MenuItem"]

# Cada item é ``(rótulo, comando)``; ``comando`` None deixa o item desabilitado e
# ``None`` no lugar do item insere um separador.
MenuItem = Optional[Tuple[str, Optional[Callable[[], None]]]]

_DEFAULT_HEIGHT = 36


def menu_button(
    master: Any,
    text: str,
    items: Sequence[MenuItem],
    *,
    tip: str | None = None,
    **kwargs: Any,
) -> ctk.CTkButton:
    """Cria um botão ``"text  ▾"`` que abre um menu com ``items`` ao ser clicado.

    ``items``: sequência de ``(rótulo, comando)``; use ``None`` para um separador e
    ``(rótulo, None)`` para um item inativo (acinzentado).

    Por padrão o gatilho tem o visual *secundário* (contorno, fundo transparente) —
    é uma ação de apoio recolhida, não a ação primária da tela. Sobrescreva via
    ``fg_color=...`` quando precisar de um gatilho preenchido."""
    kwargs.setdefault("height", _DEFAULT_HEIGHT)
    kwargs.setdefault("fg_color", "transparent")
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("text_color", THEME_TEXT_MAIN)
    button = ctk.CTkButton(master, text=f"{text}  ▾", **kwargs)

    def _open_menu() -> None:
        face = 1 if ctk.get_appearance_mode() == "Dark" else 0
        menu = tk.Menu(
            button,
            tearoff=0,
            bd=0,
            activeborderwidth=0,
            bg=THEME_PANEL_BG[face],
            fg=THEME_TEXT_MAIN[face],
            activebackground=THEME_ACCENT[face],
            activeforeground=THEME_PANEL_BG[face],
            disabledforeground=THEME_TEXT_SUB[face],
        )
        for item in items:
            if item is None:
                menu.add_separator()
                continue
            label, command = item
            menu.add_command(
                label=label,
                command=command,
                state="normal" if command is not None else "disabled",
            )
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    button.configure(command=_open_menu)
    # Itens expostos para introspeccao (testes/automacao): o tk.Menu so existe
    # durante o popup, entao guardamos a lista que o alimenta.
    button._menu_items = list(items)
    if tip:
        Tooltip(button, tip)
    return button
