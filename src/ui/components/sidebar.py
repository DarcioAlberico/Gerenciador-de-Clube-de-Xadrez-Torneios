"""Sidebar de navegação primária: grupos, ícones, destino ativo e modo responsivo.

Espelha o registro único de destinos (``navigation.DESTINATIONS``), então
nenhuma lista é mantida à mão aqui — acrescentar um destino no registro o faz
aparecer na barra (ESPEC_UI_UX §4.5 / achado P1-7). O ``tk.Menu`` nativo
continua existindo como *fallback* e acessibilidade.

**Três modos**, porque a barra não pode roubar a largura de que as telas
precisam (medido: a barra completa custa ~250px, e telas como Exportar usam
quase toda a janela em 1180px):

- ``full``   — rótulos e grupos, para janela larga;
- ``rail``   — só ícones, com o rótulo no tooltip;
- ``hidden`` — some; a navegação fica no menu nativo.

    sidebar = Sidebar(janela, navigator=app.navigator, icons=app._ctk_menu_icons)
    sidebar.frame.grid(row=0, column=0, sticky="nsw")
    sidebar.set_mode("rail")
    sidebar.highlight("show_pairings")

A barra não decide navegação: chama ``navigator.go(chave)`` e deixa o
``Navigator`` resolver o destino e anotar a tela atual.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..navigation import DESTINATIONS, Destination, by_group
from ..theme import (
    SIZE_BODY,
    SPACE_SM,
    SPACE_XS,
    THEME_ACCENT,
    THEME_PANEL_BG,
    THEME_STATUSBAR_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
)
from .tooltip import Tooltip

MODE_FULL = "full"
MODE_RAIL = "rail"
MODE_HIDDEN = "hidden"

_WIDTH_FULL = 196
_WIDTH_RAIL = 52
_ITEM_HEIGHT = 30


class Sidebar:
    """Navegação primária persistente. Uma instância por montagem da janela."""

    def __init__(
        self,
        master: Any,
        *,
        navigator: Any,
        icons: dict[str, Any] | None = None,
        destinations: tuple[Destination, ...] = DESTINATIONS,
        on_navigate: Callable[[str], None] | None = None,
    ) -> None:
        self._navigator = navigator
        self._icons = icons or {}
        self._on_navigate = on_navigate
        self._items: dict[str, ctk.CTkButton] = {}
        self._labels: dict[str, str] = {}
        self._group_labels: list[ctk.CTkLabel] = []
        self._active: str | None = None
        self._mode = MODE_FULL

        self.frame = ctk.CTkScrollableFrame(
            master,
            width=_WIDTH_FULL,
            corner_radius=0,
            fg_color=THEME_STATUSBAR_BG,
        )
        self.frame.grid_columnconfigure(0, weight=1)
        self._build(destinations)

    # -- montagem ---------------------------------------------------------

    def _build(self, destinations: tuple[Destination, ...]) -> None:
        linha = 0
        for grupo, itens in by_group(destinations).items():
            if grupo:
                rotulo = ctk.CTkLabel(
                    self.frame,
                    text=grupo.upper(),
                    anchor="w",
                    text_color=THEME_TEXT_SUB,
                    font=ctk.CTkFont(size=SIZE_BODY - 1, weight="bold"),
                )
                rotulo.grid(row=linha, column=0, sticky="ew", padx=SPACE_SM, pady=(SPACE_SM, 2))
                self._group_labels.append(rotulo)
                linha += 1
            for destino in itens:
                self._items[destino.method] = self._item(destino, linha)
                self._labels[destino.method] = destino.label
                linha += 1

    def _item(self, destino: Destination, linha: int) -> ctk.CTkButton:
        botao = ctk.CTkButton(
            self.frame,
            text=f" {destino.label}",
            image=self._icons.get(destino.icon) if destino.icon else None,
            compound="left",
            anchor="w",
            height=_ITEM_HEIGHT,
            corner_radius=6,
            fg_color="transparent",
            hover_color=THEME_PANEL_BG,
            text_color=THEME_TEXT_MAIN,
            font=ctk.CTkFont(size=SIZE_BODY),
            command=lambda key=destino.key: self._navigate(key),
        )
        botao.grid(row=linha, column=0, sticky="ew", padx=SPACE_XS, pady=1)
        # No modo rail so sobra o icone: o tooltip e quem diz o que o item e.
        Tooltip(botao, destino.label)
        return botao

    # -- modo responsivo --------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Alterna entre ``full``/``rail``/``hidden``. Idempotente."""
        if mode == self._mode:
            return
        self._mode = mode
        if mode == MODE_HIDDEN:
            try:
                self.frame.grid_remove()
            except Exception:
                pass
            return

        compacto = mode == MODE_RAIL
        try:
            self.frame.grid()
            self.frame.configure(width=_WIDTH_RAIL if compacto else _WIDTH_FULL)
        except Exception:
            return
        for rotulo in self._group_labels:
            try:
                rotulo.grid_remove() if compacto else rotulo.grid()
            except Exception:
                pass
        for metodo, botao in self._items.items():
            try:
                botao.configure(
                    text="" if compacto else f" {self._labels[metodo]}",
                    anchor="center" if compacto else "w",
                )
            except Exception:
                pass

    # -- interação --------------------------------------------------------

    def _navigate(self, key: str) -> None:
        self._navigator.go(key)
        if self._on_navigate is not None:
            self._on_navigate(key)

    def highlight(self, method_name: str | None) -> None:
        """Marca o destino ativo. Aceita ``None`` (nenhum) e nome desconhecido —
        telas fora do registro (ex.: um detalhe) simplesmente não acendem nada."""
        if method_name == self._active:
            return
        self._active = method_name
        for metodo, botao in self._items.items():
            ativo = metodo == method_name
            try:
                botao.configure(
                    fg_color=THEME_ACCENT if ativo else "transparent",
                    text_color=("#FFFFFF", "#0B0F19") if ativo else THEME_TEXT_MAIN,
                )
            except Exception:
                pass  # janela em destruicao

    @property
    def active(self) -> str | None:
        return self._active

    @property
    def items(self) -> dict[str, ctk.CTkButton]:
        """Botões por nome de método — usado em teste e por quem quiser desabilitar."""
        return dict(self._items)
