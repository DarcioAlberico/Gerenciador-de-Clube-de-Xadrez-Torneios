"""Cadastro de byes solicitados (TRF25) — o que ele tem de próprio.

O jogador (ou a equipe) declara antes que vai faltar; o bye é aplicado **quando
a rodada for gerada**. Por isso as rodadas oferecidas aqui são as **previstas**
no cadastro do torneio, e não as já geradas: quem pede bye para a rodada 5 ainda
não viu a rodada 5 existir.
"""
from __future__ import annotations

from typing import Any

from ...i18n import t
from .page import Field, TournamentRegistryPage
from .state import RequestedByeForm, requested_bye_labels, round_labels

KEY_TARGET = "target"
KEY_ROUND = "round"
KEY_TYPE = "type"
KEY_REASON = "reason"


class RequestedByesPage(TournamentRegistryPage):
    def __init__(self, controller: Any, tournament_id: int, tournament: dict[str, Any] | None) -> None:
        super().__init__(controller, tournament_id, tournament)
        self.rounds = round_labels(controller.configured_rounds(tournament), include_all=False)
        self.types = requested_bye_labels()

    # ---- Texto ------------------------------------------------------------ #

    def title(self) -> str:
        return t("arbitration.byes.title")

    def form_title(self) -> str:
        return t("arbitration.byes.form")

    def table_title(self) -> str:
        return t("arbitration.byes.table")

    def hint(self) -> str:
        return t("arbitration.byes.hint.team") if self.is_team else t("arbitration.byes.hint.player")

    def added_message(self) -> str:
        return t("arbitration.byes.added")

    def removed_message(self) -> str:
        return t("arbitration.byes.removed")

    def select_error(self) -> str:
        return t("arbitration.byes.error.select")

    def confirm_texts(self) -> tuple[str, str]:
        return t("arbitration.byes.confirm.title"), t("arbitration.byes.confirm.body")

    # ---- Forma ------------------------------------------------------------ #

    def fields(self) -> list[Field]:
        return [
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
            Field(
                KEY_ROUND,
                t("arbitration.field.round"),
                Field.OPTION,
                values=tuple(self.rounds) or (t("arbitration.common.no_rounds"),),
            ),
            Field(KEY_TYPE, t("arbitration.field.type"), Field.OPTION, values=tuple(self.types)),
            Field(
                KEY_REASON,
                t("arbitration.field.reason"),
                placeholder=t("arbitration.byes.reason_placeholder"),
            ),
        ]

    def columns(self) -> dict[str, tuple[str, int]]:
        alvo = t("arbitration.field.team") if self.is_team else t("arbitration.field.player")
        return {
            "round": (t("arbitration.field.round"), 80),
            "entity": (alvo, 220),
            "type": (t("arbitration.field.type"), 60),
            "reason": (t("arbitration.field.reason"), 240),
        }

    def clear_on_add(self) -> tuple[str, ...]:
        return (KEY_REASON,)

    # ---- Dados ------------------------------------------------------------ #

    def rows(self) -> list[tuple[int, tuple[str, ...]]]:
        chave_nome = "team_name" if self.is_team else "player_name"
        linhas = []
        for bye in self.controller.list_byes(self.tournament_id, self.is_team):
            codigo = str(bye.get("bye_type") or "").upper()
            linhas.append(
                (
                    int(bye["id"]),
                    (
                        str(int(bye.get("round_number") or 0)),
                        bye.get(chave_nome) or t("arbitration.common.removed"),
                        codigo or "-",
                        bye.get("reason") or "",
                    ),
                )
            )
        return linhas

    def add(self, values: dict[str, str]) -> None:
        formulario = RequestedByeForm(
            target_id=self.target_id(values.get(KEY_TARGET, "")),
            round_number=self.rounds.get(values.get(KEY_ROUND, "")),
            bye_type=self.types.get(values.get(KEY_TYPE, ""), ""),
            reason=values.get(KEY_REASON, ""),
            is_team=self.is_team,
        )
        self.controller.add_bye(self.tournament_id, formulario)

    def snapshot(self, record_id: int) -> dict[str, Any] | None:
        return self.controller.find_bye(self.tournament_id, record_id, self.is_team)

    def delete(self, record_id: int) -> None:
        self.controller.delete_bye(record_id, self.is_team)

    def restore(self, record: dict[str, Any]) -> None:
        self.controller.restore_bye(self.tournament_id, record, self.is_team)
