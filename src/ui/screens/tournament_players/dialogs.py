"""Casca dos diálogos da tela de Jogadores (B-6).

Esta tela abre **oito** janelas modais (pré-visualizações de importação,
mapeamento de colunas, links de formulário, pacote Chess-Results). Todas
repetiam as mesmas seis linhas de `CTkToplevel` — título, tamanho, `transient`,
`grab_set`, coluna que estica — e a mesma dupla de botões de saída.

Aqui elas viram duas funções. O ganho não é economizar linha: é que **esquecer
o `grab_set` deixa de ser possível**, e um modal sem grab é uma janela que o
usuário consegue deixar para trás sem perceber.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import neutral_button


def modal(
    host: Any,
    title: str,
    size: str,
    *,
    minsize: tuple[int, int] | None = None,
    stretch_rows: tuple[int, ...] = (),
) -> ctk.CTkToplevel:
    """Janela modal presa ao host, com a coluna 0 esticando.

    ``stretch_rows`` recebe as linhas que crescem com a janela (a tabela, em
    geral). O peso é 1 para todas; quando um diálogo precisa de proporção
    diferente, ele reconfigura depois — é o caso raro.
    """
    dialog = ctk.CTkToplevel(host)
    dialog.title(title)
    dialog.geometry(size)
    if minsize:
        dialog.minsize(*minsize)
    dialog.transient(host)
    dialog.grab_set()
    dialog.grid_columnconfigure(0, weight=1)
    for linha in stretch_rows:
        dialog.grid_rowconfigure(linha, weight=1)
    return dialog


def actions_row(dialog: ctk.CTkToplevel, row: int, pady: tuple[int, int] = (0, 16)) -> ctk.CTkFrame:
    """Faixa de botões alinhada à direita, no rodapé do diálogo."""
    faixa = ctk.CTkFrame(dialog, fg_color="transparent")
    faixa.grid(row=row, column=0, padx=16, pady=pady, sticky="e")
    return faixa


def close_button(parent: Any, text: str, dialog: ctk.CTkToplevel) -> ctk.CTkButton:
    """Botão que só fecha o diálogo (Cancelar/Fechar), já empacotado."""
    botao = neutral_button(parent, text, dialog.destroy)
    botao.pack(side="left", padx=(0, 8))
    return botao
