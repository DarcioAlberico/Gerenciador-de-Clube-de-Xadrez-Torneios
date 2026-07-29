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
    keyboard_toggle,
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
        self._fields: list[Any] = []
        self._submit: Callable[[], Any] | None = None
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
        self._fields.append(campo)
        self._bind_submit(campo)
        return campo

    # ---- Teclado (F5.10 / P3-13) ------------------------------------------

    def submit(self, action: Callable[[], Any]) -> None:
        """Liga ``Enter`` de todos os campos à ação primária do formulário.

        Vale para os campos já criados **e para os próximos**: um formulário é
        montado em partes, e exigir que a tela chamasse isto por último seria
        justamente o tipo de ordem implícita que a F5.4 tirou do caminho.

        Não alcança ``text_area``: ali o Enter é quebra de linha, e roubá-lo
        impediria escrever um parágrafo. Também não alcança o ``select``, onde
        Enter já abre a lista — o campo tem uso próprio para a tecla.
        """
        self._submit = action
        for campo in self._fields:
            self._bind_submit(campo)

    def _bind_submit(self, campo: Any) -> None:
        if self._submit is None:
            return
        if isinstance(campo, (ctk.CTkTextbox, ctk.CTkOptionMenu)):
            return
        alvo = getattr(campo, "_entry", None) or campo
        try:
            alvo.bind("<Return>", lambda _e: self._submit(), add="+")  # type: ignore[misc]
        except Exception:  # pragma: no cover - widget sem bind
            pass

    def focus_first(self) -> None:
        """Põe o cursor no primeiro campo — o começo do caminho do teclado."""
        for campo in self._fields:
            alvo = getattr(campo, "_entry", None) or getattr(campo, "_canvas", None) or campo
            try:
                alvo.focus_set()
                return
            except Exception:  # pragma: no cover
                continue

    def widget(self, widget: Any, *, label: str = "", help_text: str = "") -> Any:
        """Widget que não é campo (checkbox, editor, botão) na mesma coluna.

        Mantém a assinatura do ``_settings_stack`` original para que os
        call-sites que empilham editores próprios (sequência de desempates,
        premiação, colunas) sigam funcionando sem tradução.

        Caixas de seleção passam pelo ``keyboard_toggle`` (F5.10): sem isso
        elas ficam fora da ordem de Tab, e um formulário com dez ``flags`` —
        o caso da aba "Regras" — vira um trecho intransponível pelo teclado.
        """
        if label:
            self.place(ctk.CTkLabel(self.panel, text=label, anchor="w"), "widget")
        if help_text:
            self.note(help_text)
        if isinstance(widget, (ctk.CTkCheckBox, ctk.CTkSwitch)):
            keyboard_toggle(widget)
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
