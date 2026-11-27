"""Seletor com busca: digitar filtra, Enter escolhe (RGS-23).

Os seletores de jogador do painel (byes, ajustes, proibições) eram
``CTkOptionMenu`` com a lista inteira: num aberto de 100 inscritos, achar o
"Silva" era rolar uma lista sem busca — cerca de oito cliques para um bye.

Aqui o campo é uma ``CTkComboBox`` em que o texto digitado **filtra** as opções
(sem acento e sem caixa: "sil" acha "Silva" e "Sílvio"), e o Enter resolve o
texto para a primeira opção que casa e chama ``on_enter`` — o formulário grava
sem a mão sair do teclado.

``filter_options`` é puro, e é ele que o teste de "≤ 5 opções" exercita.
"""
from __future__ import annotations

import unicodedata
from typing import Any, Callable, Sequence

import customtkinter as ctk

from .fields import FIELD_HEIGHT

# Teclas que não mudam o texto: refiltrar nelas só piscaria a lista.
_TECLAS_NEUTRAS = frozenset(
    {"Return", "KP_Enter", "Tab", "Escape", "Up", "Down", "Left", "Right",
     "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Home", "End"}
)


def fold(text: Any) -> str:
    """Texto comparável: sem acento, sem caixa, espaços colapsados."""
    decomposto = unicodedata.normalize("NFKD", str(text or ""))
    sem_acento = "".join(ch for ch in decomposto if not unicodedata.combining(ch))
    return " ".join(sem_acento.casefold().split())


def filter_options(options: Sequence[str], query: str) -> list[str]:
    """Opções que contêm TODOS os termos digitados, na ordem original.

    Quem começa pelo termo vem antes de quem só o contém no meio: "sil" põe
    "Silva, Ana" à frente de "Basílio" — o árbitro digita o começo do nome.
    """
    termos = fold(query).split()
    if not termos:
        return list(options)
    casam = [opcao for opcao in options if all(termo in fold(opcao) for termo in termos)]
    primeiro = termos[0]
    comeca = [
        opcao for opcao in casam
        if any(palavra.startswith(primeiro) for palavra in fold(opcao).replace(",", " ").split())
    ]
    return comeca + [opcao for opcao in casam if opcao not in comeca]


class SearchCombo(ctk.CTkComboBox):
    """``CTkComboBox`` que filtra enquanto se digita.

    ``resolved()`` é o valor que o formulário deve usar: o texto exato quando
    ele é uma opção, senão a primeira opção que casa com o que foi digitado, ou
    ``""`` quando nada casa (o formulário recusa com o próprio recado).
    """

    def __init__(
        self,
        master: Any,
        values: Sequence[str],
        *,
        on_enter: Callable[[], Any] | None = None,
        initial: str = "",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("height", FIELD_HEIGHT)
        self._all_options = list(values)
        self._on_enter = on_enter
        super().__init__(master, values=list(self._all_options), **kwargs)
        # Começa VAZIO (salvo ``initial``): o seletor antigo abria no primeiro
        # da lista, e um Enter apressado gravava o bye do jogador errado.
        self.set(initial)
        self._entry.bind("<KeyRelease>", self._on_key, add="+")
        self._entry.bind("<Return>", self._on_return, add="+")
        self._entry.bind("<KP_Enter>", self._on_return, add="+")

    # ---- dados ------------------------------------------------------------ #

    @property
    def all_options(self) -> list[str]:
        return list(self._all_options)

    @property
    def options(self) -> list[str]:
        """As opções que a lista mostra agora (depois do filtro)."""
        return list(self.cget("values") or [])

    def set_options(self, values: Sequence[str]) -> None:
        self._all_options = list(values)
        self.configure(values=list(self._all_options))

    def apply_filter(self, query: str | None = None) -> list[str]:
        texto = self.get() if query is None else query
        filtradas = filter_options(self._all_options, texto)
        # Texto que é exatamente uma opção (veio do clique na lista) mostra a
        # lista inteira: o filtro é para quem digita, não para quem já escolheu.
        if texto in self._all_options:
            filtradas = list(self._all_options)
        self.configure(values=filtradas)
        return filtradas

    def resolved(self) -> str:
        texto = self.get()
        if texto in self._all_options:
            return texto
        casam = filter_options(self._all_options, texto)
        return casam[0] if casam and fold(texto) else ""

    # ---- eventos ---------------------------------------------------------- #

    def _on_key(self, event: Any = None) -> None:
        if getattr(event, "keysym", "") in _TECLAS_NEUTRAS:
            return
        self.apply_filter()

    def _on_return(self, _event: Any = None) -> str:
        escolhido = self.resolved()
        if escolhido:
            self.set(escolhido)
            self.configure(values=list(self._all_options))
        if self._on_enter is not None:
            self._on_enter()
        # "break": o Enter já foi tratado aqui. Sem isto ele subiria ao
        # toplevel, onde a tela de Rodadas escuta Enter para salvar resultado.
        return "break"
