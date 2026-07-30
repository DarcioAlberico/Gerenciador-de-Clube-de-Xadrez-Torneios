"""Central de pendências: filtro, tabela e as ações sobre a pendência escolhida.

Segunda tela do pacote. O filtro e a busca não mudam nada no banco — filtrar é
ler —, e é isso que o teste da B-4 cobra: depois de buscar, a base continua com
as mesmas ocorrências.

**O rodapé quebra linha (B-8):** eram oito botões numa linha rígida, ~1.050px
de conteúdo num app que quer caber em janela de 1.040px.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...components import WrapRow, debounce, secondary_button
from ...i18n import t
from ...support import THEME_DANGER, THEME_TEXT_SUB, THEME_WARNING_TEXT, font_kpi_value, pick
from .state import issue_filter_labels

ISSUE_COLUMNS = ("severity", "source", "kind", "title", "detail", "round", "created")


class ArbitrationIssuesView:
    """Monta a Central de pendências sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any, controller: Any) -> None:
        self.host = host
        self.controller = controller
        self.issue_cache: dict[str, dict[str, Any]] = {}
        self.round_numbers: dict[int, int] = {}
        self.filters = issue_filter_labels()
        self.payload: dict[str, Any] = {}
        self.tree: Any = None
        self.filter_option: Any = None
        self.search_entry: Any = None
        self.count_label: Any = None

    @property
    def tournament_id(self) -> int:
        return int(self.host.current_tournament_id)

    # ---- Montagem --------------------------------------------------------- #

    def build(self) -> None:
        host = self.host
        torneio = self.controller.tournament(self.tournament_id)
        self.payload = self.controller.issues(self.tournament_id)
        self.round_numbers = self.controller.round_numbers(self.tournament_id)
        self.issue_cache = {}

        host._clear_content()
        host._page_title(
            t("arbitration.issues.title"),
            t("arbitration.subtitle", torneio=(torneio or {}).get("name") or ""),
        )
        host._build_tournament_nav("arbiter")

        body = ctk.CTkFrame(host.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 22), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self._build_summary(body, self.payload["metrics"])
        self._build_table(body)
        self._build_footer(body)
        self.reload()

    def _build_summary(self, body: ctk.CTkFrame, metrics: dict[str, Any]) -> None:
        painel = self.host._make_panel(body)
        painel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        cartoes = [
            (t("arbitration.issues.card.total"), metrics["total"]),
            (t("arbitration.issues.card.qr"), metrics["qr_pending"]),
            (t("arbitration.issues.card.sync"), metrics["sync_conflicts"]),
            (t("arbitration.issues.card.clock"), metrics["clock_alerts"]),
            (t("arbitration.issues.card.tiebreak"), metrics["tiebreak_alerts"]),
            (t("arbitration.issues.card.correction"), metrics["correction_alerts"]),
            (t("arbitration.issues.card.decision"), metrics["decision_required"]),
        ]
        for coluna, (rotulo, valor) in enumerate(cartoes):
            painel.grid_columnconfigure(coluna, weight=1)
            ctk.CTkLabel(painel, text=rotulo, text_color=THEME_TEXT_SUB).grid(
                row=0, column=coluna, padx=12, pady=(10, 0), sticky="w"
            )
            ctk.CTkLabel(painel, text=str(valor), font=font_kpi_value()).grid(
                row=1, column=coluna, padx=12, pady=(0, 10), sticky="w"
            )

    def _build_table(self, body: ctk.CTkFrame) -> None:
        host = self.host
        painel = host._make_panel(body)
        painel.grid(row=1, column=0, sticky="nsew")
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(1, weight=1)

        faixa = WrapRow(painel)
        faixa.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        self.filter_option = faixa.add_field(
            t("arbitration.issues.filter"),
            lambda pai: ctk.CTkOptionMenu(pai, values=list(self.filters), width=130),
            130,
        )
        self.search_entry = ctk.CTkEntry(
            faixa.frame, placeholder_text=t("arbitration.issues.search_placeholder")
        )
        faixa.add(self.search_entry, 240, grow=True)
        self.count_label = ctk.CTkLabel(faixa.frame, text="", text_color=THEME_TEXT_SUB)
        faixa.add(self.count_label, 140)
        faixa.bind_to(host.content)

        holder = ctk.CTkFrame(painel, fg_color="transparent")
        holder.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.tree = host._make_tree(
            holder,
            list(ISSUE_COLUMNS),
            {
                "severity": t("arbitration.issues.column.severity"),
                "source": t("arbitration.issues.column.source"),
                "kind": t("arbitration.issues.column.kind"),
                "title": t("arbitration.issues.column.title"),
                "detail": t("arbitration.issues.column.detail"),
                "round": t("arbitration.field.round"),
                "created": t("arbitration.issues.column.created"),
            },
            {
                "severity": 95,
                "source": 80,
                "kind": 150,
                "title": 220,
                "detail": 360,
                "round": 80,
                "created": 150,
            },
            visible_rows=18,
        )
        self.tree.tag_configure("decision", foreground=pick(THEME_DANGER))
        self.tree.tag_configure("attention", foreground=pick(THEME_WARNING_TEXT))
        self.tree.bind("<Double-1>", self.show_detail)

        host.arbitration_issues_tree = self.tree
        host.arbitration_issue_filter_option = self.filter_option
        host.arbitration_issue_search_entry = self.search_entry
        host.arbitration_issue_count_label = self.count_label

        self.filter_option.configure(command=self.reload)
        # Guardado na instância: quem precisa do resultado agora (Enter, teste)
        # chama flush() em vez de esperar o intervalo (B-4).
        host.arbitration_issue_search_debounced = debounce(self.search_entry, self.reload)
        self.search_entry.bind("<KeyRelease>", host.arbitration_issue_search_debounced)

    def _build_footer(self, body: ctk.CTkFrame) -> None:
        host = self.host
        faixa = WrapRow(body)
        faixa.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        acoes = [
            (t("arbitration.common.refresh"), host.show_arbitration_issues, 120),
            (t("arbitration.issues.action.detail"), self.show_detail, 120),
            (t("arbitration.issues.action.approve_qr"), self.approve_qr, 130),
            (t("arbitration.issues.action.reject_qr"), self.reject_qr, 130),
            (t("arbitration.issues.action.acknowledge"), self.acknowledge, 150),
            (t("arbitration.issues.action.qr_queue"), host._open_qr_submissions_queue, 140),
            (t("arbitration.issues.action.integrations"), host.show_integrations, 140),
            (t("arbitration.common.back_to_panel"), host.show_arbitration_panel, 150),
        ]
        for rotulo, comando, largura in acoes:
            faixa.add(secondary_button(faixa.frame, rotulo, comando, width=largura), largura)
        faixa.bind_to(host.content)

    # ---- Ponte ------------------------------------------------------------ #

    def reload(self, _event: Any = None) -> None:
        """Refaz a tabela a partir do filtro e da busca. Não toca no banco."""
        tabela = self.tree
        if tabela is None:
            return
        tabela.delete(*tabela.get_children())
        self.issue_cache.clear()
        filtradas = self.controller.filter_issues(
            self.payload["issues"],
            self.filters.get(self.filter_option.get(), "all"),
            self.search_entry.get(),
        )
        self.count_label.configure(
            text=t(
                "arbitration.issues.showing",
                exibidos=len(filtradas),
                total=self.payload["metrics"]["total"],
            )
        )
        for indice, pendencia in enumerate(filtradas, start=1):
            iid = str(indice)
            self.issue_cache[iid] = pendencia
            tabela.insert(
                "",
                "end",
                iid=iid,
                values=(
                    pendencia.get("severity") or "",
                    pendencia.get("source") or "",
                    pendencia.get("kind") or "",
                    pendencia.get("title") or "",
                    pendencia.get("detail") or "",
                    self.round_numbers.get(int(pendencia.get("round_id") or 0), ""),
                    pendencia.get("created_at") or "",
                ),
                tags=(str(pendencia.get("severity") or ""),),
            )
        primeira = tabela.get_children()
        if primeira:
            tabela.selection_set(primeira[0])
            tabela.focus(primeira[0])
            tabela.see(primeira[0])

    def selected_issue(self) -> dict[str, Any]:
        selecionado = self.tree.selection() if self.tree is not None else ()
        if not selecionado:
            raise self._app_error(t("arbitration.issues.error.select"))
        return self.issue_cache.get(str(selecionado[0]), {})

    def selected_qr_submission_id(self) -> int:
        pendencia = self.selected_issue()
        if pendencia.get("source") != "qr" or pendencia.get("kind") != "result_submission":
            raise self._app_error(t("arbitration.issues.error.select_qr"))
        return int(pendencia["entity_id"])

    def show_detail(self, _event: Any = None) -> None:
        try:
            pendencia = self.selected_issue()
        except Exception as exc:
            self.host._show_error(exc)
            return
        self.host._show_json_detail(t("arbitration.issues.detail_title"), pendencia)

    def approve_qr(self) -> None:
        try:
            self.host._approve_qr_submission(self.selected_qr_submission_id())
            self.host.show_arbitration_issues()
        except Exception as exc:
            self.host._show_error(exc)

    def reject_qr(self) -> None:
        try:
            self.host._reject_qr_submission(self.selected_qr_submission_id())
            self.host.show_arbitration_issues()
        except Exception as exc:
            self.host._show_error(exc)

    def acknowledge(self) -> None:
        try:
            pendencia = self.selected_issue()
            if pendencia.get("source") == "qr":
                raise self._app_error(t("arbitration.issues.error.qr_needs_decision"))
            self.controller.acknowledge_issue(
                self.tournament_id, str(pendencia.get("issue_key") or "")
            )
            self.host._show_toast(t("arbitration.issues.acknowledged"), kind="success")
            self.host.show_arbitration_issues()
        except Exception as exc:
            self.host._show_error(exc)

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
