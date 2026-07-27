"""Painel do árbitro: monta widgets e faz a ponte com o controlador (B-6).

Terceira camada do molde da F1.5. O que sobrou aqui é só o que precisa de Tk:
montar, ler campo, redesenhar. Quais cartões existem e qual é o próximo passo
recomendado são decisões puras, e moram em [`state`](state.py); a conversa com
o banco, em [`controller`](controller.py).

**A faixa de controles quebra linha (B-8).** Este painel era o próximo dono do
gargalo: com a sidebar completa, o botão "Atualizar agora" pedia 1.200px de
janela e sozinho definia o limiar em que a barra de navegação aparece.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import WrapRow, primary_button, secondary_button
from ...i18n import t
from ...support import (
    THEME_DANGER,
    THEME_PANEL_BG,
    THEME_SUCCESS,
    THEME_SUCCESS_HOVER,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
)
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

PENDING_COLUMNS = ("board", "context", "white", "black")

# Atalhos de teclado da lista de mesas: tecla → resultado lançado. O árbitro
# digita "1" com a mão esquerda enquanto a direita segura a súmula, e o teclado
# numérico precisa valer o mesmo que o de cima.
RESULT_SHORTCUTS = {
    "1": "1-0",
    "<KP_1>": "1-0",
    "0": "0-1",
    "<KP_0>": "0-1",
    "-": "1/2-1/2",
    "<KP_Subtract>": "1/2-1/2",
    "<BackSpace>": "",
    "<Delete>": "",
}


class ArbitrationPanelView:
    """Monta o painel do árbitro sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any, controller: Any, auto_refresh: Any) -> None:
        self.host = host
        self.controller = controller
        self.auto_refresh = auto_refresh

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
        self._build_pending(main, metrics, painel["pending_items"])

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
            for indice, (rotulo, comando) in enumerate(acoes):
                coluna = indice % colunas
                ctk.CTkButton(painel, text=rotulo, command=comando).grid(
                    row=linha + indice // colunas,
                    column=coluna,
                    padx=(14 if coluna == 0 else 4, 14 if coluna == colunas - 1 else 4),
                    pady=(0, 8),
                    sticky="ew",
                )
            linha += (len(acoes) + colunas - 1) // colunas

        self._build_controls(painel, linha, colunas)

    def _action_groups(self) -> list[tuple[str, list[tuple[str, Any]]]]:
        host = self.host
        return [
            (
                t("arbitration.actions.group.round"),
                [
                    (t("arbitration.action.issues"), host.show_arbitration_issues),
                    (t("arbitration.action.pairings"), host.show_pairings),
                    (t("arbitration.action.preview"), host._preview_next_round),
                    (t("arbitration.action.checklist"), host._open_closing_checklist_dialog),
                    (t("arbitration.action.close_round"), host._close_current_round_from_panel),
                ],
            ),
            (
                t("arbitration.actions.group.config"),
                [
                    (t("arbitration.action.adjustments"), host.show_point_adjustments),
                    (t("arbitration.action.prohibitions"), host.show_prohibited_pairings),
                    (t("arbitration.action.byes"), host.show_requested_byes),
                ],
            ),
            (
                t("arbitration.actions.group.publish"),
                [
                    (t("arbitration.action.export"), host.show_export),
                    (t("arbitration.action.site"), host._export_site_from_panel),
                    (t("arbitration.action.live"), host._publish_live_portal_from_panel),
                    (t("arbitration.action.round_package"), host._export_round_package_from_panel),
                    (t("arbitration.action.bulletin"), host._export_round_bulletin_from_panel),
                    (t("arbitration.action.podium"), host._export_podium_from_panel),
                    (t("arbitration.action.minutes"), host._export_tournament_minutes_from_panel),
                ],
            ),
        ]

    def _build_controls(self, painel: ctk.CTkFrame, linha: int, colunas: int) -> None:
        """A faixa de preferências — e o gargalo de largura que a B-8 apontou.

        Checkbox, botão e dois seletores numa linha rígida dentro de um painel
        estreito: era o "Atualizar agora" que ficava fora da janela, e era ele
        que segurava o limiar da sidebar completa em 1.200px.
        """
        host = self.host
        faixa = WrapRow(painel)
        faixa.grid(row=linha, column=0, columnspan=colunas, padx=14, pady=(4, 12), sticky="ew")

        auto = ctk.CTkCheckBox(
            faixa.frame,
            text=t("arbitration.control.auto_refresh"),
            command=host._toggle_arbitration_auto_refresh,
        )
        faixa.add(auto, 200)
        if host._arbitration_auto_refresh_enabled:
            auto.select()

        faixa.add(
            secondary_button(
                faixa.frame,
                t("arbitration.control.refresh_now"),
                host.show_arbitration_panel,
                width=130,
            ),
            130,
        )
        intervalo = faixa.add_field(
            t("arbitration.control.interval"),
            lambda pai: ctk.CTkOptionMenu(
                pai,
                values=list(REFRESH_INTERVAL_CHOICES),
                width=80,
                command=host._set_arbitration_refresh_interval,
            ),
            80,
        )
        intervalo.set(str(host._arbitration_refresh_interval_seconds))
        limite = faixa.add_field(
            t("arbitration.control.inline_limit"),
            lambda pai: ctk.CTkOptionMenu(
                pai,
                values=list(INLINE_LIMIT_CHOICES),
                width=80,
                command=host._set_arbitration_inline_tables_limit,
            ),
            80,
        )
        limite.set(str(host._arbitration_inline_tables_limit))
        faixa.bind_to(host.content)

    # ---- Mesas aguardando resultado --------------------------------------- #

    def _build_pending(
        self, main: ctk.CTkFrame, metrics: dict[str, Any], pending_items: list[dict[str, Any]]
    ) -> None:
        host = self.host
        painel = host._make_panel(main)
        painel.grid(row=1, column=0, padx=(0, 12), pady=(12, 0), sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)

        self._build_pending_header(painel, metrics, len(pending_items))
        if pending_items:
            self._build_pending_table(painel, pending_items)
        else:
            host.arbitration_pending_row_map = {}
            host.arbitration_pending_tree = None
            ctk.CTkLabel(
                painel, text=t("arbitration.pending.empty"), text_color=THEME_TEXT_SUB
            ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

    def _build_pending_header(
        self, painel: ctk.CTkFrame, metrics: dict[str, Any], exibidos: int
    ) -> None:
        host = self.host
        cabecalho = ctk.CTkFrame(painel, fg_color="transparent")
        cabecalho.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        cabecalho.grid_columnconfigure(0, weight=1)
        host._section_title(cabecalho, t("arbitration.pending.title")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            cabecalho,
            text=t(
                "arbitration.pending.showing",
                exibidos=exibidos,
                total=metrics["pending_results"],
            ),
            text_color=THEME_TEXT_SUB,
        ).grid(row=0, column=1, padx=(8, 0), sticky="e")
        secondary_button(
            cabecalho, t("arbitration.pending.open"), host.show_pairings, width=140
        ).grid(row=0, column=2, padx=(10, 0), sticky="e")

        # A faixa de busca quebra linha: três itens de ~400px somados dentro de
        # um painel que já divide a largura com as "Ações rápidas".
        faixa = WrapRow(cabecalho)
        faixa.grid(row=1, column=0, columnspan=3, pady=(8, 0), sticky="ew")
        # O campo nasce dentro da faixa: no Tk um widget não troca de pai depois
        # de criado, e um `master` reatribuído à mão mente para o layout.
        busca = ctk.CTkEntry(
            faixa.frame, width=160, placeholder_text=t("arbitration.pending.search_placeholder")
        )
        busca.insert(0, getattr(host, "_arbitration_pending_query", ""))
        host.arbitration_pending_query_entry = busca
        faixa.add(busca, 160, grow=True)
        faixa.add(
            secondary_button(
                faixa.frame, t("arbitration.pending.search"), self._apply_query, width=120
            ),
            120,
        )
        faixa.add(
            secondary_button(
                faixa.frame, t("arbitration.pending.clear"), self._clear_query, width=120
            ),
            120,
        )
        busca.bind("<Return>", self._apply_query)
        faixa.bind_to(host.content)

    def _build_pending_table(self, painel: ctk.CTkFrame, pending_items: list[dict[str, Any]]) -> None:
        host = self.host
        tabela = host._make_tree(
            painel,
            list(PENDING_COLUMNS),
            {
                "board": t("arbitration.pending.column.board"),
                "context": t("arbitration.pending.column.context"),
                "white": t("arbitration.pending.column.white"),
                "black": t("arbitration.pending.column.black"),
            },
            {"board": 70, "context": 100, "white": 320, "black": 320},
            visible_rows=min(6, len(pending_items)),
        )
        tabela.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
        host.arbitration_pending_tree = tabela
        host.arbitration_pending_row_map = {}
        for item in pending_items:
            iid = tabela.insert(
                "",
                "end",
                values=(item["board"], item["context"], item["white"], item["black"]),
            )
            host.arbitration_pending_row_map[iid] = int(item["pairing_id"])

        tabela.bind("<Double-1>", lambda _evento: host.show_pairings())
        for tecla, resultado in RESULT_SHORTCUTS.items():
            tabela.bind(
                tecla,
                lambda _evento, valor=resultado: host._save_arbitration_panel_result(valor),
            )
        primeira = tabela.get_children()
        if primeira:
            tabela.selection_set(primeira[0])
            tabela.focus(primeira[0])
            tabela.see(primeira[0])

        self._build_inline_actions(painel)
        tabela.focus_set()

    def _build_inline_actions(self, painel: ctk.CTkFrame) -> None:
        host = self.host
        faixa = WrapRow(painel)
        faixa.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        faixa.add(
            ctk.CTkLabel(
                faixa.frame, text=t("arbitration.pending.enter_result"), text_color=THEME_TEXT_SUB
            ),
            130,
        )
        for rotulo, resultado in (
            ("1-0", "1-0"),
            ("1/2", "1/2-1/2"),
            ("0-1", "0-1"),
            (t("arbitration.pending.clear_result"), ""),
        ):
            faixa.add(
                ctk.CTkButton(
                    faixa.frame,
                    text=rotulo,
                    width=70,
                    command=lambda valor=resultado: host._save_arbitration_panel_result(valor),
                ),
                70,
            )
        faixa.add(
            ctk.CTkLabel(
                faixa.frame, text=t("arbitration.pending.shortcuts"), text_color=THEME_TEXT_SUB
            ),
            170,
        )
        faixa.bind_to(host.content)

    # ---- Ponte ------------------------------------------------------------ #

    def _apply_query(self, _event: Any = None) -> None:
        entrada = self.host.arbitration_pending_query_entry
        self.host._arbitration_pending_query = entrada.get().strip()
        self.host.show_arbitration_panel()

    def _clear_query(self) -> None:
        self.host._arbitration_pending_query = ""
        self.host.show_arbitration_panel()

    def save_result(self, result: str) -> str:
        """Lança o resultado da mesa selecionada. Devolve "break" (é um bind)."""
        host = self.host
        try:
            tabela = getattr(host, "arbitration_pending_tree", None)
            if tabela is None:
                raise self._app_error(t("arbitration.error.no_pending"))
            selecionado = tabela.selection()
            if not selecionado:
                raise self._app_error(t("arbitration.error.select_table"))
            pairing_id = host.arbitration_pending_row_map.get(selecionado[0])
            if not pairing_id:
                raise self._app_error(t("arbitration.error.table_not_found"))
            self.controller.save_result(self.tournament_id, int(pairing_id), result)
            host.show_arbitration_panel()
        except Exception as exc:
            host._show_error(exc)
        return "break"

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
