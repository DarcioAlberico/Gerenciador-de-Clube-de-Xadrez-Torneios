"""Checklist de fechamento da rodada — o diálogo que precede o irreversível.

Fechar rodada é o gesto que trava lançamento e libera o pareamento seguinte. O
checklist existe para que a decisão seja tomada olhando a lista, e não de
memória: cada item traz o próprio "Resolver", e o botão de fechar **nasce
desabilitado** enquanto houver item pendente.

Os itens vêm do serviço (``closing_checklist``), com as mesmas chaves de ação do
painel — ver [`state`](state.py).
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import neutral_button, primary_button, secondary_button
from ...i18n import t
from ...support import THEME_DANGER, THEME_SUCCESS, THEME_SUCCESS_HOVER


def open_closing_checklist(host: Any, controller: Any) -> ctk.CTkToplevel | None:
    """Abre o diálogo. Devolve a janela (ou ``None`` se o serviço recusou)."""
    try:
        itens = controller.closing_checklist(int(host.current_tournament_id))
    except Exception as exc:
        host._show_error(exc)
        return None

    dialogo = ctk.CTkToplevel(host)
    dialogo.title(t("arbitration.checklist.title"))
    dialogo.geometry("560x380")
    dialogo.transient(host)
    dialogo.grab_set()
    dialogo.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(dialogo, text=t("arbitration.checklist.intro"), anchor="w").grid(
        row=0, column=0, padx=16, pady=(16, 8), sticky="ew"
    )

    tudo_ok = True
    for indice, item in enumerate(itens, start=1):
        ok = bool(item.get("ok"))
        tudo_ok = tudo_ok and ok
        linha = ctk.CTkFrame(dialogo, fg_color="transparent")
        linha.grid(row=indice, column=0, padx=16, pady=2, sticky="ew")
        linha.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            linha,
            text=t("arbitration.checklist.ok") if ok else t("arbitration.checklist.fail"),
            width=28,
            text_color=THEME_SUCCESS if ok else THEME_DANGER,
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(linha, text=item.get("label", ""), anchor="w", justify="left").grid(
            row=0, column=1, sticky="w"
        )
        comando = host._arbitration_action(str(item.get("action") or ""))
        if not ok and comando is not None:
            secondary_button(
                linha,
                t("arbitration.checklist.resolve"),
                lambda c=comando, d=dialogo: (d.destroy(), c()),
                width=90,
            ).grid(row=0, column=2, padx=(8, 0))

    acoes = ctk.CTkFrame(dialogo, fg_color="transparent")
    acoes.grid(row=len(itens) + 1, column=0, padx=16, pady=(12, 16), sticky="e")
    neutral_button(acoes, t("arbitration.checklist.close_dialog"), dialogo.destroy).pack(
        side="left", padx=(0, 8)
    )
    fechar_rodada = primary_button(
        acoes,
        t("arbitration.checklist.close_round"),
        lambda: (dialogo.destroy(), host._close_current_round_from_panel()),
        fg_color=THEME_SUCCESS,
        hover_color=THEME_SUCCESS_HOVER,
    )
    fechar_rodada.pack(side="left")
    if not tudo_ok:
        fechar_rodada.configure(state="disabled")
    return dialogo
