"""Estado vazio padronizado.

No lugar de um ``CTkLabel("Nenhum registro")`` solto e centralizado, oferece um
bloco com título, descrição amigável e CTA opcional (ver ESPEC_UI_UX §5.4).

Uso::

    from src.ui.components import EmptyState
    EmptyState(
        parent,
        title="Nenhum torneio ainda",
        description="Crie o primeiro torneio para gerar rodadas e classificações.",
        cta_text="Criar torneio",
        cta_command=self.show_tournaments,
    ).grid(row=0, column=0, sticky="nsew")
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..support import THEME_TEXT_MAIN, THEME_TEXT_SUB, font_section


class EmptyState(ctk.CTkFrame):
    """Frame de estado vazio. Posicione com ``grid``/``pack``; o conteúdo é
    centralizado dentro do espaço disponível."""

    def __init__(
        self,
        master: Any,
        *,
        title: str,
        description: str = "",
        icon: Any = None,
        cta_text: str | None = None,
        cta_command: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        if icon is not None:
            ctk.CTkLabel(inner, image=icon, text="").pack(pady=(0, 8))

        ctk.CTkLabel(
            inner,
            text=title,
            font=font_section(),
            text_color=THEME_TEXT_MAIN,
        ).pack()

        if description:
            ctk.CTkLabel(
                inner,
                text=description,
                text_color=THEME_TEXT_SUB,
                wraplength=360,
                justify="center",
            ).pack(pady=(4, 0))

        if cta_text and cta_command is not None:
            from .buttons import primary_button

            primary_button(inner, cta_text, command=cta_command).pack(pady=(12, 0))
