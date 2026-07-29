"""Casca dos diálogos da tela de Jogadores (B-6, canonizada na F5.8).

Esta tela abre **oito** janelas modais (pré-visualizações de importação,
mapeamento de colunas, links de formulário, pacote Chess-Results). Todas
repetiam as mesmas seis linhas de `CTkToplevel` — título, tamanho, `transient`,
`grab_set`, coluna que estica — e a mesma dupla de botões de saída.

Aqui elas viram duas funções. O ganho não é economizar linha: é que **esquecer
o `grab_set` deixa de ser possível**, e um modal sem grab é uma janela que o
usuário consegue deixar para trás sem perceber.

A F5.8 levou a ideia para [`components/dialogs.py`](../../components/dialogs.py)
e as oito passaram a herdar o que faltava a todas: **Esc**, tamanho que cabe na
tela em 160% e ordem canônica de botões. O que sobrou aqui é a tradução do
``"700x540"`` — a assinatura em string que os call-sites usam — para o par de
inteiros do ``Dialog``.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import Dialog, neutral_button


def _parse_size(size: str) -> tuple[int, int]:
    """``"700x540"`` → ``(700, 540)``. Formato herdado dos call-sites."""
    largura, _, altura = size.partition("x")
    return int(largura), int(altura)


def modal(
    host: Any,
    title: str,
    size: str,
    *,
    minsize: tuple[int, int] | None = None,
    stretch_rows: tuple[int, ...] = (),
) -> Dialog:
    """Janela modal presa ao host, com a coluna 0 esticando.

    ``stretch_rows`` recebe as linhas que crescem com a janela (a tabela, em
    geral). O peso é 1 para todas; quando um diálogo precisa de proporção
    diferente, ele reconfigura depois — é o caso raro.
    """
    return Dialog(
        host,
        title,
        size=_parse_size(size),
        min_size=minsize,
        stretch_rows=stretch_rows,
    )


def actions_row(dialog: Any, row: int, pady: tuple[int, int] = (0, 16)) -> ctk.CTkFrame:
    """Faixa de botões alinhada à direita, no rodapé do diálogo."""
    faixa = ctk.CTkFrame(dialog, fg_color="transparent")
    faixa.grid(row=row, column=0, padx=16, pady=pady, sticky="e")
    return faixa


def close_button(parent: Any, text: str, dialog: Any) -> ctk.CTkButton:
    """Botão que só fecha o diálogo (Cancelar/Fechar), já empacotado.

    Usa ``dialog.close`` e não ``destroy``: é o fechamento que devolve o *grab*
    ao modal pai — e esta tela abre modal sobre modal (pré-visualização de
    importação → mapeamento de colunas).
    """
    fechar = getattr(dialog, "close", dialog.destroy)
    botao = neutral_button(parent, text, fechar)
    botao.pack(side="left", padx=(0, 8))
    return botao
