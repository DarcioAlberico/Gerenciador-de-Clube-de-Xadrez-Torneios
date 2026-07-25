"""Tela inicial: pendências acionáveis com *deep link* (F3.2 / achado P1-8).

É esta a tela que abre depois do login, no lugar do "Perfil do Clube" — quem
entra vê o que precisa de ação, não um cadastro.

A divisão aqui é proposital: ``home.build_pendencies`` (puro) decide **o que**
está pendente; este módulo só lê o banco (``_home_snapshot``) e desenha. Cada
leitura é isolada, porque um serviço com problema não pode deixar a tela inicial
em branco — ela degrada para o que conseguiu apurar.
"""
from __future__ import annotations

from ..components import EmptyState, primary_button
from ..home import ATTENTION, URGENT, HomeSnapshot, Pendency, build_pendencies
from datetime import datetime

import customtkinter as ctk

from ..support import logger
from ..theme import (
    SPACE_LG,
    SPACE_SM,
    SPACE_XL,
    THEME_DANGER,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_WARNING_TEXT,
    font_subsection,
)

_COR_SEVERIDADE = {
    URGENT: THEME_DANGER,
    ATTENTION: THEME_WARNING_TEXT,
}


def _data_br(valor: object) -> str:
    """ISO do banco -> dd/mm/aaaa, como o resto do app mostra data."""
    texto = str(valor or "").strip()
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return texto


class HomePagesMixin:
    def show_home(self) -> None:
        """Painel de pendências. Ponto de entrada do app depois do login."""
        self._clear_content()
        operador = ""
        try:
            operador = str((self.security_service._current_user or {}).get("username") or "")
        except Exception:
            pass
        self._page_title(
            "Inicio" + (f" — {operador}" if operador else ""),
            "O que precisa da sua acao agora.",
        )

        pendencias = build_pendencies(self._home_snapshot())

        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        painel = self._make_panel(body)
        painel.grid(row=0, column=0, sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)

        if not pendencias:
            EmptyState(
                painel,
                title="Tudo em dia",
                description="Nenhuma pendencia encontrada no clube nem no torneio atual.",
                cta_text="Ver torneios",
                cta_command=lambda: self.navigator.go("tournaments"),
            ).grid(row=0, column=0, sticky="nsew", padx=SPACE_LG, pady=SPACE_XL)
            return

        self.home_pendency_cards: list[ctk.CTkFrame] = []
        for indice, pendencia in enumerate(pendencias):
            cartao = self._pendency_card(painel, pendencia)
            cartao.grid(
                row=indice,
                column=0,
                sticky="ew",
                padx=SPACE_LG,
                pady=(SPACE_LG if indice == 0 else SPACE_SM, 0),
            )
            self.home_pendency_cards.append(cartao)

    def _pendency_card(self, parent: ctk.CTkBaseClass, pendencia: Pendency) -> ctk.CTkFrame:
        cartao = ctk.CTkFrame(parent, fg_color="transparent")
        cartao.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cartao,
            text=pendencia.title,
            anchor="w",
            justify="left",
            text_color=_COR_SEVERIDADE.get(pendencia.severity, THEME_TEXT_MAIN),
            font=font_subsection(),
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            cartao,
            text=pendencia.detail,
            anchor="w",
            justify="left",
            text_color=THEME_TEXT_SUB,
            wraplength=680,
        ).grid(row=1, column=0, sticky="ew")

        acao = primary_button(
            cartao,
            pendencia.action_label,
            lambda destino=pendencia.destination: self.navigator.go(destino),
            tip="Abre a tela onde essa pendencia se resolve.",
        )
        acao.grid(row=0, column=1, rowspan=2, padx=(SPACE_LG, 0))
        return cartao

    # -- leitura do estado (I/O) ------------------------------------------

    def _home_snapshot(self) -> HomeSnapshot:
        """Le o estado atual. Cada fonte em seu try: uma falha isolada vira
        ausencia daquele dado, nao uma tela inicial vazia."""
        dados: dict[str, object] = {}

        tournament_id = getattr(self, "current_tournament_id", None)
        if tournament_id:
            dados["has_tournament"] = True
            try:
                painel = self.pairing_service.arbitration_dashboard(int(tournament_id))
                metricas = painel["metrics"]
                dados.update(
                    tournament_name=str(metricas.get("tournament_name") or ""),
                    rounds_count=int(metricas.get("rounds_count") or 0),
                    generated_rounds=int(metricas.get("generated_rounds") or 0),
                    closed_rounds=int(metricas.get("closed_rounds") or 0),
                    pending_results=int(metricas.get("pending_results") or 0),
                    blocking_issues=int(metricas.get("blocking_issues") or 0),
                    qr_pending=int(metricas.get("submitted_results") or 0),
                    absent_players=int(metricas.get("absent_players") or 0),
                )
            except Exception:
                logger.exception("Falha ao apurar pendencias do torneio na tela inicial")
            try:
                dados["players_count"] = len(self.db.list_players(int(tournament_id), active_only=True))
            except Exception:
                logger.exception("Falha ao contar jogadores na tela inicial")

        try:
            visao = self.dashboard_service.overview()
            dados["defaulters"] = int(visao.get("defaulters_count") or 0)
            dados["open_announcements"] = len(visao.get("active_announcements") or [])
            dados["upcoming_events"] = tuple(
                (_data_br(evento.get("event_date")), str(evento.get("title") or "Evento"))
                for evento in (visao.get("upcoming_events") or [])
            )
        except Exception:
            logger.exception("Falha ao apurar a visao do clube na tela inicial")

        return HomeSnapshot(**dados)  # type: ignore[arg-type]
