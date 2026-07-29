"""Formulário canônico: uma coluna, seções, sem aritmética de linha (F5.4).

Promoção do ``_settings_stack`` que vivia dentro da Config. do torneio. Ele já
era a melhor das três formas de montar formulário no app — empilhava sozinho,
sem ``row=index * 2 + 1`` — e por isso é ele que vira componente, em vez de um
quarto padrão novo (P3-12).

O que a promoção acrescenta ao original:

- **seções** (``section``), que nenhum dos três padrões tinha: formulários de 14
  a 25 campos eram uma coluna corrida de rótulos;
- **campos vindos do [`fields`](fields.py)**, com a anatomia da F5.2/F5.3 —
  altura de 36px, placeholder, anel de foco e linha de mensagem de erro sob o
  campo — no lugar do ``CTkEntry`` cru de largura arbitrária;
- **ritmo vertical vindo do [`form_layout`](../form_layout.py)**, que é puro:
  quem decide espaço não abre widget.

Uso típico::

    form = FormStack(painel)
    form.section("Identificação")
    nome = form.text("Nome do torneio", placeholder="Ex.: Aberto de Verão")
    form.section("Datas")
    inicio = form.date("Data inicial")

A largura dos campos **não** é passada pela tela: ``sticky="ew"`` faz o campo
ocupar a coluna, e a coluna é ``FORM_PANEL_WIDTH``. Era daí que vinham as 67
larguras distintas do P3-3 — cada tela reinventando quanto o campo devia medir.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..form_layout import FORM_PADX, RowKind, row_padding
from ..theme import THEME_TEXT_SUB, font_section
from .fields import (
    date_field,
    labeled_field,
    select_field,
    text_area,
    text_field,
)

_STACK_ATTR = "_albericus_form_stack"


class FormStack:
    """Empilha rótulo + campo numa coluna, avançando a linha sozinho.

    Guarda-se no próprio painel (``form_of``) para que código antigo, que só
    tem o painel na mão, alcance a mesma pilha — a alternativa seria dois
    contadores de linha sobre o mesmo grid, que é como o formulário se
    desalinha em silêncio.
    """

    def __init__(self, panel: Any, *, padx: int = FORM_PADX) -> None:
        self.panel = panel
        self.padx = padx
        self._row = 0
        panel.grid_columnconfigure(0, weight=1)
        setattr(panel, _STACK_ATTR, self)

    # ---- Posicionamento --------------------------------------------------- #

    def place(self, widget: Any, kind: RowKind = "widget", **grid: Any) -> Any:
        """Põe ``widget`` na próxima linha da coluna e devolve o widget."""
        pady = row_padding(kind, first=self._row == 0)
        grid.setdefault("sticky", "ew")
        widget.grid(row=self._row, column=0, padx=self.padx, pady=pady, **grid)
        self._row += 1
        return widget

    @property
    def row(self) -> int:
        """Próxima linha livre — para quem precisa posicionar fora da pilha."""
        return self._row

    # ---- Blocos ----------------------------------------------------------- #

    def section(self, title: str, *, help_text: str = "") -> ctk.CTkLabel:
        """Cabeçalho de grupo. O respiro maior antes dele é o que agrupa."""
        rotulo = ctk.CTkLabel(self.panel, text=title, font=font_section(), anchor="w")
        self.place(rotulo, "section")
        if help_text:
            self.note(help_text)
        return rotulo

    def note(self, text: str) -> ctk.CTkLabel:
        """Linha de apoio: explica a seção ou o campo sem virar rótulo."""
        rotulo = ctk.CTkLabel(
            self.panel, text=text, text_color=THEME_TEXT_SUB, justify="left", anchor="w"
        )
        return self.place(rotulo, "note")

    def field(
        self,
        label: str,
        builder: Callable[[Any], Any],
        *,
        help_text: str = "",
    ) -> Any:
        """Rótulo + campo + linha de mensagem, como unidade (``labeled_field``)."""
        box, campo = labeled_field(self.panel, label, builder, help_text=help_text)
        self.place(box, "field")
        return campo

    def widget(self, widget: Any, *, label: str = "", help_text: str = "") -> Any:
        """Widget que não é campo (checkbox, editor, botão) na mesma coluna.

        Mantém a assinatura do ``_settings_stack`` original para que os
        call-sites que empilham editores próprios (sequência de desempates,
        premiação, colunas) sigam funcionando sem tradução.
        """
        if label:
            self.place(ctk.CTkLabel(self.panel, text=label, anchor="w"), "widget")
        if help_text:
            self.note(help_text)
        return self.place(widget, "widget")

    # ---- Atalhos de campo (a anatomia da F5.2 sem repetir o builder) ------- #

    def text(self, label: str, *, placeholder: str = "", help_text: str = "", **kwargs: Any) -> Any:
        return self.field(
            label,
            lambda box: text_field(box, placeholder=placeholder or label, **kwargs),
            help_text=help_text,
        )

    def select(
        self,
        label: str,
        values: list[str],
        *,
        help_text: str = "",
        command: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self.field(
            label,
            lambda box: select_field(box, values=values, command=command, **kwargs),
            help_text=help_text,
        )

    def date(self, label: str, *, help_text: str = "", **kwargs: Any) -> Any:
        return self.field(label, lambda box: date_field(box, **kwargs), help_text=help_text)

    def area(self, label: str, *, height: int = 110, help_text: str = "", **kwargs: Any) -> Any:
        return self.field(
            label, lambda box: text_area(box, height=height, **kwargs), help_text=help_text
        )


def form_of(panel: Any) -> FormStack:
    """A pilha do painel, criando-a na primeira chamada. Idempotente."""
    pilha = getattr(panel, _STACK_ATTR, None)
    if pilha is None:
        pilha = FormStack(panel)
    return pilha
