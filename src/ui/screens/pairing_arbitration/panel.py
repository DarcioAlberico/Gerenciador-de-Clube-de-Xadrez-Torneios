"""Painel do árbitro: monta widgets e faz a ponte com o controlador (B-6).

Terceira camada do molde da F1.5. O que sobrou aqui é só o que precisa de Tk:
montar, ler campo, redesenhar. Quais cartões existem e qual é o próximo passo
recomendado são decisões puras, e moram em [`state`](state.py); a conversa com
o banco, em [`controller`](controller.py).

**O gargalo de largura da B-8 morreu aqui**, e não como se esperava: a faixa
que quebra linha resolve a busca de mesas (coluna larga) e **não** as
preferências de atualização (coluna estreita, onde a conta gira em círculo).
Ver ``_build_controls``.

A lista de mesas pendentes tem módulo próprio ([`pending`](pending.py)): é a
parte do painel que o árbitro **usa**, enquanto o resto informa.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import FormStack, Tooltip, primary_button, secondary_button
from ...i18n import t
from ...support import (
    THEME_DANGER,
    THEME_PANEL_BG,
    THEME_SUCCESS,
    THEME_SUCCESS_HOVER,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
)
from .pending import PendingTablesSection
from .state import (
    INLINE_LIMIT_CHOICES,
    REFRESH_INTERVAL_CHOICES,
    next_step,
    panel_cards,
    progress_ratio,
)

# Severidade do alerta → token de cor. "warning" divide o token com "danger"
# porque, num painel de arbitragem, aviso e bloqueio pedem o mesmo olhar.
ALERT_COLORS = {
    "danger": THEME_DANGER,
    "warning": THEME_DANGER,
    "success": THEME_SUCCESS,
    "info": THEME_TEXT_MAIN,
}


class ArbitrationPanelView:
    """Monta o painel do árbitro sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any, controller: Any, auto_refresh: Any) -> None:
        self.host = host
        self.controller = controller
        self.auto_refresh = auto_refresh
        self.pending = PendingTablesSection(host, controller)

    @property
    def tournament_id(self) -> int:
        return int(self.host.current_tournament_id)

    # ---- Montagem --------------------------------------------------------- #

    def build(self) -> None:
        host = self.host
        torneio = self.controller.tournament(self.tournament_id)
        painel = self.controller.dashboard(
            self.tournament_id,
            pending_limit=host._arbitration_inline_tables_limit,
            pending_query=getattr(host, "_arbitration_pending_query", ""),
        )
        metrics = painel["metrics"]

        host._clear_content()
        host._page_title(
            t("arbitration.panel.title"),
            t("arbitration.subtitle", torneio=(torneio or {}).get("name") or ""),
        )
        host._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(host.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self._build_cards(body, metrics)

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._build_alerts(main, metrics, painel.get("alerts_detailed", []))
        self._build_actions(main)
        self.pending.build(main, metrics, painel["pending_items"])

        self.auto_refresh.schedule()

    def _build_cards(self, body: ctk.CTkFrame, metrics: dict[str, Any]) -> None:
        host = self.host
        cards = ctk.CTkFrame(body, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for coluna in range(6):
            cards.grid_columnconfigure(coluna, weight=1)

        for indice, cartao in enumerate(panel_cards(metrics)):
            widget = host._kpi_card(
                cards,
                cartao.title,
                cartao.value,
                subtitle=cartao.subtitle,
                command=self.host._arbitration_action(cartao.action),
            )
            widget.grid(row=0, column=indice, padx=(0 if indice == 0 else 8, 0), sticky="ew")

        fracao = progress_ratio(metrics)
        if fracao is None:
            return
        barra = ctk.CTkProgressBar(cards)
        barra.set(fracao)
        barra.grid(row=1, column=0, columnspan=5, padx=(0, 8), pady=(12, 0), sticky="ew")
        ctk.CTkLabel(
            cards,
            text=t(
                "arbitration.panel.progress",
                resolvidas=int(metrics.get("resolved_results") or 0),
                total=int(metrics.get("total_results") or 0),
                percentual=int(metrics.get("round_progress_percent") or 0),
            ),
            text_color=THEME_TEXT_SUB,
        ).grid(row=1, column=5, padx=(8, 0), pady=(12, 0), sticky="e")

        # Tolerancia de atraso (ORG-03): quem declara ausencia e o arbitro de
        # sala, e o numero vivia so no edital.
        tolerancia = int(metrics.get("late_tolerance_minutes") or 0)
        ctk.CTkLabel(
            cards,
            text=(
                f"Tolerância de atraso: {tolerancia} min"
                if tolerancia
                else "Tolerância de atraso: zero (perde a hora marcada)"
            ),
            text_color=THEME_TEXT_SUB,
        ).grid(row=2, column=0, columnspan=6, padx=(0, 8), pady=(6, 0), sticky="w")

    def _build_alerts(
        self, main: ctk.CTkFrame, metrics: dict[str, Any], alerts: list[dict[str, Any]]
    ) -> None:
        host = self.host
        painel = host._make_panel(main)
        painel.grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_columnconfigure(1, weight=0)
        host._section_title(painel, t("arbitration.alerts.title")).grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )

        passo = next_step(metrics)
        ctk.CTkLabel(painel, text=t("arbitration.alerts.next_step"), text_color=THEME_TEXT_SUB).grid(
            row=0, column=1, padx=(8, 14), pady=(14, 2), sticky="e"
        )
        primary_button(
            painel,
            passo.label,
            host._arbitration_action(passo.action),
            fg_color=THEME_SUCCESS,
            hover_color=THEME_SUCCESS_HOVER,
        ).grid(row=1, column=1, rowspan=max(1, len(alerts)), padx=(8, 14), pady=(0, 12), sticky="ne")

        if not alerts:
            ctk.CTkLabel(painel, text=t("arbitration.alerts.empty")).grid(
                row=1, column=0, padx=14, pady=(0, 12), sticky="w"
            )
            return

        for linha, alerta in enumerate(alerts, start=1):
            cor = ALERT_COLORS.get(str(alerta.get("severity") or "info"), THEME_TEXT_MAIN)
            comando = host._arbitration_action(str(alerta.get("action") or ""))
            if comando is not None:
                ctk.CTkButton(
                    painel,
                    text=t("arbitration.alerts.item_action", texto=alerta["text"]),
                    anchor="w",
                    fg_color="transparent",
                    text_color=cor,
                    hover_color=THEME_PANEL_BG,
                    command=comando,
                ).grid(row=linha, column=0, padx=10, pady=(0, 4), sticky="ew")
            else:
                ctk.CTkLabel(
                    painel,
                    text=t("arbitration.alerts.item", texto=alerta["text"]),
                    anchor="w",
                    justify="left",
                    text_color=cor,
                ).grid(row=linha, column=0, padx=14, pady=(0, 6), sticky="ew")

    def _build_actions(self, main: ctk.CTkFrame) -> None:
        """"Ações rápidas" em 3 colunas: cabem sem rolagem e aproveitam a
        largura cedida pela coluna esquerda."""
        host = self.host
        painel = host._make_panel(main)
        painel.grid(row=0, column=1, rowspan=2, sticky="nsew")
        colunas = 3
        for coluna in range(colunas):
            painel.grid_columnconfigure(coluna, weight=1)
        host._section_title(painel, t("arbitration.actions.title")).grid(
            row=0, column=0, columnspan=colunas, padx=14, pady=(14, 8), sticky="w"
        )

        linha = 1
        for rotulo_grupo, acoes in self._action_groups():
            host._section_title(painel, rotulo_grupo, subsection=True).grid(
                row=linha, column=0, columnspan=colunas, padx=14, pady=(4, 4), sticky="w"
            )
            linha += 1
            for indice, (rotulo, completo, comando) in enumerate(acoes):
                coluna = indice % colunas
                botao = ctk.CTkButton(painel, text=rotulo, command=comando)
                if completo != rotulo:
                    Tooltip(botao, completo)
                botao.grid(
                    row=linha + indice // colunas,
                    column=coluna,
                    padx=(14 if coluna == 0 else 4, 14 if coluna == colunas - 1 else 4),
                    pady=(0, 8),
                    sticky="ew",
                )
            linha += (len(acoes) + colunas - 1) // colunas

        self._build_controls(painel, linha, colunas)

    def _action_groups(self) -> list[tuple[str, list[tuple[str, str, Any]]]]:
        """Grupos de ação: ``(rótulo curto, texto completo, comando)``.

        O rótulo do botão e o nome da ação deixaram de ser a mesma string
        (P3-16). Em três colunas, "Ajustes de pontos (TRF25)" não cabe e o
        ``CTkButton`` **corta o texto pelos dois lados** — o screenshot do
        manual mostrava "justes de pontos (TRF25". O botão passa a levar a
        forma curta e o tooltip guarda o nome inteiro, que é onde a referência
        ao TRF25 faz falta: na hora de conferir a regra, não na de clicar.
        """
        host = self.host
        return [
            (
                t("arbitration.actions.group.round"),
                [
                    (t("arbitration.action.issues.short"), t("arbitration.action.issues"), host.show_arbitration_issues),
                    (t("arbitration.action.pairings"), t("arbitration.action.pairings"), host.show_pairings),
                    (t("arbitration.action.preview.short"), t("arbitration.action.preview"), host._preview_next_round),
                    (t("arbitration.action.checklist.short"), t("arbitration.action.checklist"), host._open_closing_checklist_dialog),
                    (t("arbitration.action.close_round.short"), t("arbitration.action.close_round"), host._close_current_round_from_panel),
                ],
            ),
            (
                t("arbitration.actions.group.config"),
                [
                    (t("arbitration.action.adjustments.short"), t("arbitration.action.adjustments"), host.show_point_adjustments),
                    (t("arbitration.action.prohibitions.short"), t("arbitration.action.prohibitions"), host.show_prohibited_pairings),
                    (t("arbitration.action.byes.short"), t("arbitration.action.byes"), host.show_requested_byes),
                ],
            ),
            (
                t("arbitration.actions.group.publish"),
                [
                    (t("arbitration.action.export"), t("arbitration.action.export"), host.show_export),
                    (t("arbitration.action.site"), t("arbitration.action.site"), host._export_site_from_panel),
                    (t("arbitration.action.live"), t("arbitration.action.live"), host._publish_live_portal_from_panel),
                    (t("arbitration.action.round_package.short"), t("arbitration.action.round_package"), host._export_round_package_from_panel),
                    (t("arbitration.action.bulletin.short"), t("arbitration.action.bulletin"), host._export_round_bulletin_from_panel),
                    (t("arbitration.action.podium"), t("arbitration.action.podium"), host._export_podium_from_panel),
                    (t("arbitration.action.minutes"), t("arbitration.action.minutes"), host._export_tournament_minutes_from_panel),
                ],
            ),
        ]

    def _build_controls(self, painel: ctk.CTkFrame, linha: int, colunas: int) -> None:
        """As preferências de atualização — o gargalo de largura da B-8.

        **Empilhadas, e não numa faixa que quebra linha.** Foi o que a medição
        mandou. A `WrapRow` mede o quanto lhe sobra a partir de onde ela
        começa, e aqui ela começa dentro de um painel estreito cuja largura
        depende dela: a conta gira em círculo e lê a posição de antes de a
        coluna assentar — o "Atualizar agora" acabava a 1px da borda. Numa
        coluna larga (a busca de mesas, logo abaixo) isso não acontece, e lá a
        faixa continua.

        Empilhar dispensa medição: a linha mais larga é a caixa de seleção
        (~230px), e ela cabe em qualquer largura que este painel possa ter.
        """
        host = self.host
        controles = ctk.CTkFrame(painel, fg_color="transparent")
        controles.grid(row=linha, column=0, columnspan=colunas, padx=14, pady=(4, 12), sticky="ew")
        # Empilhar continua sendo a decisao da B-8; o que muda na F5.4 e QUEM
        # empilha: a mesma FormStack das outras telas, com os dois seletores
        # ganhando a anatomia de campo (rotulo acima, altura de 36px) em vez do
        # par rotulo-a-esquerda / bloco-de-cor-a-direita que so existia aqui.
        pilha = FormStack(controles, padx=0)

        auto = ctk.CTkCheckBox(
            controles,
            text=t("arbitration.control.auto_refresh"),
            command=host._toggle_arbitration_auto_refresh,
        )
        pilha.place(auto, "widget", sticky="w")
        if host._arbitration_auto_refresh_enabled:
            auto.select()

        pilha.place(
            secondary_button(
                controles,
                t("arbitration.control.refresh_now"),
                host.show_arbitration_panel,
                width=130,
            ),
            "widget",
            sticky="w",
        )

        intervalo = pilha.select(
            t("arbitration.control.interval"),
            list(REFRESH_INTERVAL_CHOICES),
            command=host._set_arbitration_refresh_interval,
        )
        intervalo.set(str(host._arbitration_refresh_interval_seconds))
        limite = pilha.select(
            t("arbitration.control.inline_limit"),
            list(INLINE_LIMIT_CHOICES),
            command=host._set_arbitration_inline_tables_limit,
        )
        limite.set(str(host._arbitration_inline_tables_limit))
