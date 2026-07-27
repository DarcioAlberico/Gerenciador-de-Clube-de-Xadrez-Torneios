"""O mixin das telas de arbitragem — cinco telas, uma casca fina (B-6).

Este arquivo é o que sobrou de 1.527 linhas: cada método público monta uma view
do pacote e sai da frente. O import externo não mudou
(``from .pairing_arbitration import ArbitrationPagesMixin``), então o
`PairingPagesMixin` e a `AlbericusApp` não souberam da mudança.

**As views nascem a cada visita, de propósito.** Guardá-las na instância
economizaria alguns objetos e traria de volta o pior defeito de tela legada:
widget destruído pelo `_clear_content` ainda referenciado por um controlador
vivo. Uma view por visita é barata (o custo da tela é montar widget, medido na
B-4) e não tem estado para envelhecer.
"""
from __future__ import annotations

from typing import Any, Callable

from .adjustments import AdjustmentsPage
from .byes import RequestedByesPage
from .checklist import open_closing_checklist
from .controller import ArbitrationController
from .exports import ArbitrationExportActions
from .issues import ArbitrationIssuesView
from .panel import ArbitrationPanelView
from .prohibitions import ProhibitionsPage
from .refresh import AutoRefresh
from .registry import RegistryView
from .state import (
    ACTION_ABSENT_PLAYERS,
    ACTION_BLOCKING_ISSUES,
    ACTION_CORRECTIONS,
    ACTION_INITIAL_CALL,
    ACTION_LINEUPS,
    ACTION_PENDING_RESULTS,
    ACTION_PREVIEW_NEXT,
    ACTION_QR_PENDING,
    ACTION_READY_TO_CLOSE,
)


class ArbitrationPagesMixin:
    """As cinco telas de arbitragem, montadas sobre a ``AlbericusApp``."""

    # ---- Fábricas --------------------------------------------------------- #

    def _arbitration_controller(self) -> ArbitrationController:
        return ArbitrationController(self.db, pairing_service=self.pairing_service)

    def _arbitration_auto_refresh(self) -> AutoRefresh:
        return AutoRefresh(self, self._arbitration_controller())

    def _arbitration_panel_view(self) -> ArbitrationPanelView:
        controlador = self._arbitration_controller()
        return ArbitrationPanelView(self, controlador, AutoRefresh(self, controlador))

    def _arbitration_exports(self) -> ArbitrationExportActions:
        return ArbitrationExportActions(self, self._arbitration_controller())

    def _arbitration_registry(self, page_class: type) -> RegistryView:
        controlador = self._arbitration_controller()
        torneio = controlador.tournament(self.current_tournament_id)
        return RegistryView(
            self, page_class(controlador, int(self.current_tournament_id), torneio)
        )

    def _arbitration_action(self, action: str) -> Callable[[], None] | None:
        """Chave de ação → o que ela abre. ``None`` quando não há para onde ir.

        Alertas, cartões e checklist falam nas **mesmas** chaves, que vêm do
        serviço. Este mapa é o único lugar que as traduz em navegação — e há um
        teste que cobra que toda chave emitida pelo serviço esteja aqui: deep
        link quebrado no painel do árbitro é pior que alerta nenhum (F3.2).
        """
        destinos: dict[str, Callable[[], None]] = {
            ACTION_BLOCKING_ISSUES: self.show_arbitration_issues,
            ACTION_PENDING_RESULTS: self.show_pairings,
            ACTION_READY_TO_CLOSE: self._close_current_round_from_panel,
            ACTION_INITIAL_CALL: self.show_pairings,
            ACTION_ABSENT_PLAYERS: self.show_players,
            ACTION_CORRECTIONS: self.show_audit_logs,
            ACTION_QR_PENDING: self.show_arbitration_issues,
            ACTION_PREVIEW_NEXT: self._preview_next_round,
            ACTION_LINEUPS: self.show_teams,
        }
        return destinos.get(action)

    # ---- Telas ------------------------------------------------------------ #

    def show_arbitration_panel(self) -> None:
        if not self._require_tournament():
            return
        self._arbitration_panel_view().build()

    def show_arbitration_issues(self) -> None:
        if not self._require_tournament():
            return
        ArbitrationIssuesView(self, self._arbitration_controller()).build()

    def show_point_adjustments(self) -> None:
        if not self._require_tournament():
            return
        self._arbitration_registry(AdjustmentsPage).build()

    def show_requested_byes(self) -> None:
        if not self._require_tournament():
            return
        self._arbitration_registry(RequestedByesPage).build()

    def show_prohibited_pairings(self) -> None:
        if not self._require_tournament():
            return
        self._arbitration_registry(ProhibitionsPage).build()

    # ---- Ações do painel -------------------------------------------------- #

    def _save_arbitration_panel_result(self, result: str) -> str:
        return self._arbitration_panel_view().save_result(result)

    def _open_closing_checklist_dialog(self) -> Any:
        return open_closing_checklist(self, self._arbitration_controller())

    def _close_current_round_from_panel(self) -> None:
        ultima = self._arbitration_controller().latest_round(self.current_tournament_id)
        if not ultima:
            from src.services.constants import AppError

            from ...i18n import t

            self._show_error(AppError(t("arbitration.error.no_round_to_close")))
            return
        self.current_round_id = int(ultima["id"])
        self._close_current_round()
        self.show_arbitration_panel()

    # ---- Auto-atualização (preferências persistidas) ---------------------- #

    def _schedule_arbitration_refresh(self) -> None:
        self._arbitration_auto_refresh().schedule()

    def _cancel_arbitration_refresh(self) -> None:
        self._arbitration_auto_refresh().cancel()

    def _toggle_arbitration_auto_refresh(self) -> None:
        self._arbitration_auto_refresh().toggle()

    def _set_arbitration_refresh_interval(self, value: str) -> None:
        self._arbitration_auto_refresh().set_interval(value)

    def _set_arbitration_inline_tables_limit(self, value: str) -> None:
        self._arbitration_auto_refresh().set_inline_limit(value)

    # ---- Publicações ------------------------------------------------------ #

    def _export_round_package_from_panel(self) -> None:
        self._arbitration_exports().export_round_package()

    def _export_round_bulletin_from_panel(self) -> None:
        self._arbitration_exports().export_round_bulletin()

    def _export_podium_from_panel(self) -> None:
        self._arbitration_exports().export_podium()

    def _export_tournament_minutes_from_panel(self) -> None:
        self._arbitration_exports().export_minutes()

    def _export_site_from_panel(self) -> None:
        self._arbitration_exports().export_site()

    def _publish_live_portal_from_panel(self) -> None:
        self._arbitration_exports().publish_live_portal()
