"""Tabela temada — zebra, ordenação por cabeçalho e estado vazio (F5.5 / P3-9).

``ThemedTreeview`` é o ``ttk.Treeview`` que o ``_make_tree`` do app instancia.
Tudo acontece por dentro do ``insert``/``delete``, então **nenhum dos ~57
call-sites muda**:

- **zebra**: linhas de topo alternam ``THEME_TREE_ODD``/``THEME_TREE_EVEN`` —
  os tokens existiam desde a B-2 e nunca haviam sido aplicados. A tag de zebra
  entra por ÚLTIMO na lista de tags do item: no ttk, a primeira tag que define
  uma opção vence, então as tags semânticas das telas (estado do resultado,
  vitória/empate) continuam mandando na cor;
- **nulos viram vazio**: ``None`` (e a string ``"None"``, que nunca é dado
  legítimo em PT-BR) não aparecem mais na célula;
- **ordenação**: clique no cabeçalho ordena a coluna (numérico quando a coluna
  inteira é numérica, texto caso contrário; vazios sempre ao fim), segundo
  clique inverte, com indicador ▲/▼. Uma tela que registre o próprio
  ``heading(command=...)`` depois — como a explicação de desempates — substitui
  a ordenação naquela coluna, que é o comportamento certo;
- **estado vazio**: um ``EmptyState`` central aparece quando a tabela fica sem
  linhas e some na primeira inserção.

As cores da zebra acompanham preset e claro/escuro: cada instância se inscreve
em ``on_theme_change`` e no ``AppearanceModeTracker`` e se desinscreve no
``<Destroy>`` — sem isso, cada tela visitada seria um ouvinte imortal.
"""
from __future__ import annotations

from tkinter import TclError, ttk
from typing import Any

import customtkinter as ctk

from ..theme import (
    THEME_TREE_EVEN,
    THEME_TREE_ODD,
    off_theme_change,
    on_theme_change,
    pick,
)

_ZEBRA_ODD = "zebra_impar"
_ZEBRA_EVEN = "zebra_par"
_SORT_ASC = " ▲"   # ▲
_SORT_DESC = " ▼"  # ▼


def _clean_value(value: Any) -> Any:
    """``None`` (e a string "None") viram célula vazia — o resto passa intacto."""
    if value is None or value == "None":
        return ""
    return value


def _numeric(value: str) -> float | None:
    """Interpreta "1740", "1.5" e "1,5" como número; devolve ``None`` se não for."""
    texto = str(value).strip()
    if not texto:
        return None
    for candidato in (texto, texto.replace(",", ".")):
        try:
            return float(candidato)
        except ValueError:
            continue
    return None


class ThemedTreeview(ttk.Treeview):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self._empty_state: ctk.CTkFrame | None = None
        self._empty_visible = False
        self._base_headings: dict[str, str] = {}
        self._sort_state: tuple[str, bool] | None = None
        self._apply_zebra_colors()
        on_theme_change(self._apply_zebra_colors)
        ctk.AppearanceModeTracker.add(self._on_appearance_change, self)
        self.bind("<Destroy>", self._on_destroy, add="+")

    # ------------------------------------------------------------------ tema
    def _apply_zebra_colors(self) -> None:
        try:
            self.tag_configure(_ZEBRA_ODD, background=pick(THEME_TREE_ODD))
            self.tag_configure(_ZEBRA_EVEN, background=pick(THEME_TREE_EVEN))
        except TclError:  # pragma: no cover - widget ja destruido durante a troca
            pass

    def _on_appearance_change(self, _mode: str) -> None:
        self._apply_zebra_colors()

    def _on_destroy(self, event: Any) -> None:
        if event.widget is not self:
            return
        off_theme_change(self._apply_zebra_colors)
        try:
            ctk.AppearanceModeTracker.remove(self._on_appearance_change)
        except Exception:  # pragma: no cover - tracker sem o callback
            pass

    # ------------------------------------------------------- linhas e zebra
    def insert(self, parent: str = "", index: Any = "end", iid: Any = None, **kw: Any) -> str:
        values = kw.get("values")
        if values is not None:
            kw["values"] = tuple(_clean_value(v) for v in values)
        if parent == "":
            stripe = _ZEBRA_ODD if len(self.get_children("")) % 2 == 0 else _ZEBRA_EVEN
            tags = kw.get("tags") or ()
            if isinstance(tags, str):
                tags = (tags,)
            kw["tags"] = (*tuple(tags), stripe)
        item = super().insert(parent, index, iid=iid, **kw)
        if self._empty_visible:
            self._sync_empty_state()
        return item

    def delete(self, *items: Any) -> None:
        super().delete(*items)
        self._restripe()
        self._sync_empty_state()

    def _restripe(self) -> None:
        """Reaplica a alternância na ordem visual — após excluir ou ordenar."""
        for indice, iid in enumerate(self.get_children("")):
            stripe = _ZEBRA_ODD if indice % 2 == 0 else _ZEBRA_EVEN
            tags = [t for t in self.item(iid, "tags") if t not in (_ZEBRA_ODD, _ZEBRA_EVEN)]
            self.item(iid, tags=(*tags, stripe))

    # ------------------------------------------------------------ ordenação
    def enable_sorting(self) -> None:
        """Liga a ordenação por clique em todas as colunas atuais.

        Chamada pelo ``_make_tree`` depois de definir os cabeçalhos; telas que
        precisarem de outro clique no cabeçalho registram o próprio ``command``
        por cima, coluna a coluna.
        """
        for column in [str(c) for c in self["columns"]]:
            self._base_headings[column] = str(self.heading(column, "text"))
            self.heading(column, command=lambda c=column: self.sort_by(c))

    def sort_by(self, column: str) -> None:
        reverse = self._sort_state == (column, False)
        linhas = [(self.set(iid, column), iid) for iid in self.get_children("")]
        preenchidas = [(valor, iid) for valor, iid in linhas if str(valor).strip()]
        vazias = [iid for valor, iid in linhas if not str(valor).strip()]

        numeros = {iid: _numeric(valor) for valor, iid in preenchidas}
        so_numeros = preenchidas and all(numeros[iid] is not None for _v, iid in preenchidas)
        if so_numeros:
            preenchidas.sort(key=lambda par: numeros[par[1]], reverse=reverse)
        else:
            preenchidas.sort(key=lambda par: str(par[0]).casefold(), reverse=reverse)

        # Vazias sempre ao fim: linha sem dado não pode "vencer" a ordenação.
        for pos, (_valor, iid) in enumerate(preenchidas):
            self.move(iid, "", pos)
        for pos, iid in enumerate(vazias, start=len(preenchidas)):
            self.move(iid, "", pos)

        self._sort_state = (column, reverse)
        self._update_sort_arrows()
        self._restripe()

    def _update_sort_arrows(self) -> None:
        atual = self._sort_state
        for column, base in self._base_headings.items():
            texto = base
            if atual and atual[0] == column:
                texto = base + (_SORT_DESC if atual[1] else _SORT_ASC)
            self.heading(column, text=texto)

    # ---------------------------------------------------------- estado vazio
    def attach_empty_state(self, widget: ctk.CTkFrame) -> None:
        """Recebe o overlay (criado pelo ``_make_tree``) e passa a gerenciá-lo."""
        self._empty_state = widget
        self._sync_empty_state()

    def _sync_empty_state(self) -> None:
        if self._empty_state is None:
            return
        vazio = not self.get_children("")
        if vazio and not self._empty_visible:
            self._empty_state.place(in_=self, relx=0.5, rely=0.5, anchor="center")
            self._empty_visible = True
        elif not vazio and self._empty_visible:
            self._empty_state.place_forget()
            self._empty_visible = False
