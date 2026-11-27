"""Faixa fixa de erro de regra (RGS-26).

A recusa de uma regra — "rodada fechada", "motivo curto demais" — ia para o
mesmo toast do sucesso, que some em 5 s. O árbitro que estava olhando para a
súmula quando a recusa apareceu não a lia, e tentava de novo pelo caminho que
lembrava: foi assim que "mudanças perigosas" virou rotina.

Aqui a recusa fica **até ser fechada** (ou trocada pela próxima), diz o que
fazer em seguida e, quando a tela sabe, oferece o botão dessa ação. Toast
continua existindo, mas só para sucesso.

    host = RuleBannerHost(janela, anchor=lambda: janela.content)
    host.show("Rodada fechada.", suggestion="Use Corrigir resultado…")

``rule_banner`` monta só a faixa; os diálogos a usam direto (grid), para
recusar sem fechar o que o árbitro já digitou.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..i18n import t
from ..theme import (
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    THEME_DANGER,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    font_section,
)
from .buttons import neutral_button, secondary_button

BannerAction = tuple[str, Callable[[], None]]


def rule_banner(
    parent: Any,
    message: str,
    *,
    title: str = "",
    suggestion: str = "",
    action: BannerAction | None = None,
    on_close: Callable[[], None] | None = None,
    wraplength: int = 760,
) -> ctk.CTkFrame:
    """Faixa com título, recado, ação sugerida e **Fechar**. Não tem relógio."""
    faixa = ctk.CTkFrame(
        parent,
        fg_color=THEME_PANEL_BG,
        border_color=THEME_DANGER,
        border_width=2,
        corner_radius=8,
    )
    # Marca para quem procura a faixa na árvore de widgets (teste, F5).
    faixa._rule_banner = True  # type: ignore[attr-defined]
    faixa.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        faixa,
        text=title or t("banner.rule.title"),
        font=font_section(),
        text_color=THEME_DANGER,
        anchor="w",
        justify="left",
    ).grid(row=0, column=0, padx=SPACE_MD, pady=(SPACE_SM, 0), sticky="ew")
    ctk.CTkLabel(
        faixa,
        text=message,
        text_color=THEME_TEXT_MAIN,
        anchor="w",
        justify="left",
        wraplength=wraplength,
    ).grid(
        row=1,
        column=0,
        padx=SPACE_MD,
        pady=(SPACE_XS, 0 if suggestion else SPACE_MD),
        sticky="ew",
    )
    if suggestion:
        ctk.CTkLabel(
            faixa,
            text=t("banner.rule.suggestion", sugestao=suggestion),
            text_color=THEME_TEXT_SUB,
            anchor="w",
            justify="left",
            wraplength=wraplength,
        ).grid(row=2, column=0, padx=SPACE_MD, pady=(SPACE_XS, SPACE_MD), sticky="ew")

    botoes = ctk.CTkFrame(faixa, fg_color="transparent")
    botoes.grid(row=0, column=1, rowspan=3, padx=SPACE_MD, pady=SPACE_SM, sticky="ne")
    if action is not None:
        rotulo, comando = action
        secondary_button(botoes, rotulo, comando).pack(side="left", padx=(0, SPACE_SM))
    neutral_button(
        botoes,
        t("banner.rule.close"),
        on_close if on_close is not None else faixa.destroy,
        width=90,
    ).pack(side="left")
    return faixa


class RuleBannerHost:
    """Uma faixa por janela, sobreposta ao pé da área de conteúdo.

    Sobreposta (``place``) e não encaixada no grid: as telas são reconstruídas
    a cada atualização (o painel do árbitro se redesenha sozinho), e uma faixa
    filha do conteúdo sumiria junto — exatamente o que a RGS-26 proíbe.
    """

    def __init__(self, window: Any, *, anchor: Callable[[], Any] | None = None) -> None:
        self._window = window
        self._anchor = anchor
        self._current: ctk.CTkFrame | None = None

    @property
    def current(self) -> ctk.CTkFrame | None:
        """A faixa na tela, ou ``None``."""
        faixa = self._current
        if faixa is None:
            return None
        try:
            if not faixa.winfo_exists():
                self._current = None
                return None
        except Exception:
            self._current = None
            return None
        return faixa

    def show(
        self,
        message: str,
        *,
        title: str = "",
        suggestion: str = "",
        action: BannerAction | None = None,
    ) -> ctk.CTkFrame:
        """Mostra a recusa, trocando a anterior. Fica até o árbitro fechar."""
        self.dismiss()
        acao = None
        if action is not None:
            rotulo, comando = action

            def agir() -> None:
                # A ação resolve o problema: a faixa que o descrevia sai antes.
                self.dismiss()
                comando()

            acao = (rotulo, agir)
        faixa = rule_banner(
            self._window,
            message,
            title=title,
            suggestion=suggestion,
            action=acao,
            on_close=self.dismiss,
        )
        self._current = faixa
        self._place(faixa)
        return faixa

    def dismiss(self) -> None:
        faixa, self._current = self._current, None
        if faixa is None:
            return
        try:
            faixa.destroy()
        except Exception:
            pass  # a faixa já foi destruída junto com a tela

    def _place(self, faixa: ctk.CTkFrame) -> None:
        alvo = None
        if self._anchor is not None:
            try:
                alvo = self._anchor()
                if alvo is not None and not alvo.winfo_exists():
                    alvo = None
            except Exception:
                alvo = None
        opcoes: dict[str, Any] = {"relx": 0.5, "rely": 1.0, "y": -SPACE_MD, "anchor": "s", "relwidth": 0.96}
        if alvo is not None:
            opcoes["in_"] = alvo
        faixa.place(**opcoes)
        try:
            faixa.lift()
        except Exception:
            pass  # a faixa já foi destruída junto com a tela
