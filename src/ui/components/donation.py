"""Modal "Apoie o Projeto".

Extraído de ``AlbericusApp._build_menu`` (onde era uma função aninhada) para manter
o builder do menu enxuto (ver ESPEC_UI_UX §4.4 / ROADMAP F0.5). Recebe a instância
do app como ``app`` para acessar clipboard/after e a janela-pai.
"""
from __future__ import annotations

import webbrowser
from typing import Any

import customtkinter as ctk

from ..theme import THEME_ACCENT

_PIX_KEY = "30436841843"
_LIVEPIX_URL = "https://livepix.gg/darcioalberico"
_WHATSAPP_GREEN = "#25D366"
_LIVEPIX_PURPLE = "#8a2be2"
_LIVEPIX_PURPLE_HOVER = "#5c1d96"


def show_donation_modal(app: Any) -> ctk.CTkToplevel:
    modal = ctk.CTkToplevel(app)
    modal.title("Apoie o Projeto")
    modal.geometry("400x350")
    modal.grab_set()
    modal.resizable(False, False)

    ctk.CTkLabel(
        modal,
        text="❤ Apoie o Desenvolvimento",
        font=ctk.CTkFont(size=20, weight="bold"),
    ).pack(pady=(20, 10))

    ctk.CTkLabel(
        modal,
        text=(
            "O Albericus é um projeto independente.\n"
            "Se o software tem ajudado você e o seu clube,\n"
            "considere pagar um café para o desenvolvedor!"
        ),
        justify="center",
    ).pack(pady=(0, 20))

    ctk.CTkLabel(modal, text="Chave PIX:", font=ctk.CTkFont(weight="bold")).pack()

    entry = ctk.CTkEntry(modal, width=250, justify="center")
    entry.pack(pady=(5, 15))
    entry.insert(0, _PIX_KEY)
    entry.configure(state="readonly")

    def copy_pix() -> None:
        app.clipboard_clear()
        app.clipboard_append(_PIX_KEY)
        app.update()
        copy_btn.configure(text="Copiado!", fg_color=_WHATSAPP_GREEN)
        app.after(2000, lambda: copy_btn.configure(text="Copiar Chave PIX", fg_color=THEME_ACCENT))

    copy_btn = ctk.CTkButton(modal, text="Copiar Chave PIX", command=copy_pix, fg_color=THEME_ACCENT)
    copy_btn.pack(pady=10)

    def open_livepix() -> None:
        webbrowser.open(_LIVEPIX_URL)

    ctk.CTkButton(
        modal,
        text="Cartão / Internacional (LivePix)",
        command=open_livepix,
        fg_color=_LIVEPIX_PURPLE,
        hover_color=_LIVEPIX_PURPLE_HOVER,
    ).pack(pady=(0, 10))

    return modal
