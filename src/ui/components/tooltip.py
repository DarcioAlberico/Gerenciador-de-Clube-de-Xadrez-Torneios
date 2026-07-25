"""Tooltip leve para qualquer widget Tk/CTk.

O CustomTkinter não traz tooltip e a lib externa ``CTkToolTip`` não está instalada,
então implementamos um próprio (ver ESPEC_UI_UX §4.4): aparece após um pequeno
atraso ao passar o mouse, some ao sair ou clicar, e segue as cores do tema.

Uso::

    from src.ui.components import Tooltip
    Tooltip(botao, "Gera a próxima rodada do torneio")
"""
from __future__ import annotations

from tkinter import Label, Toplevel
from typing import Any

import customtkinter as ctk

from ..theme import THEME_ACCENT, THEME_PANEL_BG, THEME_TEXT_MAIN


class Tooltip:
    """Anexa uma dica de texto a ``widget``. Mantém uma referência viva enquanto o
    widget existir; não é preciso guardar o objeto retornado."""

    def __init__(
        self,
        widget: Any,
        text: str,
        *,
        delay_ms: int = 450,
        wraplength: int = 260,
    ) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id: str | None = None
        self._tip: Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: Any = None) -> None:
        self._cancel()
        try:
            self._after_id = self.widget.after(self.delay_ms, self._show)
        except Exception:
            self._after_id = None

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return
        face = 1 if ctk.get_appearance_mode() == "Dark" else 0
        try:
            tip = Toplevel(self.widget)
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            tip.configure(bg=THEME_ACCENT[face])  # borda fina = cor de destaque
            Label(
                tip,
                text=self.text,
                bg=THEME_PANEL_BG[face],
                fg=THEME_TEXT_MAIN[face],
                font=("Segoe UI", 9),
                wraplength=self.wraplength,
                justify="left",
                padx=8,
                pady=4,
            ).pack(padx=1, pady=1)
            tip.geometry(f"+{x}+{y}")
            self._tip = tip
        except Exception:
            self._tip = None

    def _hide(self, _event: Any = None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
