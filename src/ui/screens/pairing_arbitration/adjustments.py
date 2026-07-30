"""Cadastro de ajustes de pontos (TRF25 §7.3) — o que ele tem de próprio.

Penalidade, bônus e atribuição anormal de resultado (W/D/L/F/H/Z/+/-). A casca
vem de [`registry`](registry.py); aqui ficam campos, colunas e a ponte com o
controlador.
"""
from __future__ import annotations

from typing import Any

from ...i18n import t
from .page import Field, TournamentRegistryPage
from .state import AdjustmentForm, aat_type_labels, round_labels

KEY_TARGET = "target"
KEY_ROUND = "round"
KEY_TYPE = "type"
KEY_MATCH_POINTS = "match_points"
KEY_GAME_POINTS = "game_points"
KEY_REASON = "reason"


class AdjustmentsPage(TournamentRegistryPage):
    def __init__(self, controller: Any, tournament_id: int, tournament: dict[str, Any] | None) -> None:
        super().__init__(controller, tournament_id, tournament)
        self.rounds = round_labels(
            controller.generated_rounds(self.tournament_id), include_all=True
        )
        self.types = aat_type_labels()

    # ---- Texto ------------------------------------------------------------ #

    def title(self) -> str:
        return t("arbitration.adjustments.title")

    def form_title(self) -> str:
        return t("arbitration.adjustments.form")

    def table_title(self) -> str:
        return t("arbitration.adjustments.table")

    def added_message(self) -> str:
        return t("arbitration.adjustments.added")

    def removed_message(self) -> str:
        return t("arbitration.adjustments.removed")

    def select_error(self) -> str:
        return t("arbitration.adjustments.error.select")

    def confirm_texts(self) -> tuple[str, str]:
        return t("arbitration.adjustments.confirm.title"), t("arbitration.adjustments.confirm.body")

    # ---- Forma ------------------------------------------------------------ #

    def fields(self) -> list[Field]:
        campos = [
            Field(
                KEY_TARGET,
                t("arbitration.field.team") if self.is_team else t("arbitration.field.player"),
                Field.OPTION,
                values=self.target_labels(
                    t("arbitration.common.no_teams")
                    if self.is_team
                    else t("arbitration.common.no_players")
                ),
            ),
            Field(KEY_ROUND, t("arbitration.field.round"), Field.OPTION, values=tuple(self.rounds)),
            Field(KEY_TYPE, t("arbitration.field.type"), Field.OPTION, values=tuple(self.types)),
        ]
        # Match points só existem em torneio por equipes: num individual o campo
        # seria sempre zero, e um campo que só aceita zero é ruído.
        if self.is_team:
            campos.append(
                Field(
                    KEY_MATCH_POINTS,
                    t("arbitration.field.match_points"),
                    placeholder=t("arbitration.field.points_placeholder"),
                )
            )
        campos.append(
            Field(
                KEY_GAME_POINTS,
                t("arbitration.field.game_points"),
                placeholder=t("arbitration.field.points_placeholder"),
            )
        )
        campos.append(
            Field(
                KEY_REASON,
                t("arbitration.field.reason"),
                placeholder=t("arbitration.adjustments.reason_placeholder"),
            )
        )
        return campos

    def columns(self) -> dict[str, tuple[str, int]]:
        return {
            "round": (t("arbitration.field.round"), 80),
            "target": (t("arbitration.adjustments.column.target"), 200),
            "type": (t("arbitration.field.type"), 60),
            "mp": (t("arbitration.adjustments.column.mp"), 60),
            "gp": (t("arbitration.adjustments.column.gp"), 60),
            "reason": (t("arbitration.field.reason"), 240),
        }

    def clear_on_add(self) -> tuple[str, ...]:
        return (KEY_MATCH_POINTS, KEY_GAME_POINTS, KEY_REASON)

    # ---- Dados ------------------------------------------------------------ #

    def rows(self) -> list[tuple[int, tuple[str, ...]]]:
        linhas = []
        for ajuste in self.controller.list_adjustments(self.tournament_id):
            numero = int(ajuste.get("round_number") or 0)
            alvo = ajuste.get("team_name") if self.is_team else ajuste.get("player_name")
            linhas.append(
                (
                    int(ajuste["id"]),
                    (
                        t("arbitration.round.all_short") if numero == 0 else str(numero),
                        alvo or t("arbitration.common.removed"),
                        ajuste.get("aat_type") or "-",
                        f"{float(ajuste.get('match_points') or 0.0):+.1f}",
                        f"{float(ajuste.get('game_points') or 0.0):+.1f}",
                        ajuste.get("reason") or "",
                    ),
                )
            )
        return linhas

    def add(self, values: dict[str, str]) -> None:
        formulario = AdjustmentForm(
            target_id=self.target_id(values.get(KEY_TARGET, "")),
            round_number=self.rounds.get(values.get(KEY_ROUND, ""), 0),
            aat_type=self.types.get(values.get(KEY_TYPE, ""), ""),
            match_points_text=values.get(KEY_MATCH_POINTS, ""),
            game_points_text=values.get(KEY_GAME_POINTS, ""),
            reason=values.get(KEY_REASON, ""),
            is_team=self.is_team,
        )
        self.controller.add_adjustment(self.tournament_id, formulario)

    def snapshot(self, record_id: int) -> dict[str, Any] | None:
        return self.controller.find_adjustment(self.tournament_id, record_id)

    def delete(self, record_id: int) -> None:
        self.controller.delete_adjustment(self.tournament_id, record_id)

    def restore(self, record: dict[str, Any]) -> None:
        self.controller.restore_adjustment(self.tournament_id, record)
