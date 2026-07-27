"""Cadastro de proibições de pareamento (TRF25 registro 260).

Vale para indivíduos (por start-rank) e para equipes (por TPN); a tela é a
mesma, só muda a entidade e o par de funções do banco.
"""
from __future__ import annotations

from typing import Any

from ...i18n import t
from .page import Field, TournamentRegistryPage
from .state import ProhibitionForm, round_window_label

KEY_TARGET_A = "target_a"
KEY_TARGET_B = "target_b"
KEY_FIRST_ROUND = "first_round"
KEY_LAST_ROUND = "last_round"
KEY_REASON = "reason"


class ProhibitionsPage(TournamentRegistryPage):
    # ---- Texto ------------------------------------------------------------ #

    def title(self) -> str:
        return t("arbitration.prohibitions.title")

    def form_title(self) -> str:
        return t("arbitration.prohibitions.form")

    def table_title(self) -> str:
        return t("arbitration.prohibitions.table")

    def added_message(self) -> str:
        return t("arbitration.prohibitions.added")

    def removed_message(self) -> str:
        return t("arbitration.prohibitions.removed")

    def select_error(self) -> str:
        return t("arbitration.prohibitions.error.select")

    def confirm_texts(self) -> tuple[str, str]:
        return (
            t("arbitration.prohibitions.confirm.title"),
            t("arbitration.prohibitions.confirm.body"),
        )

    # ---- Forma ------------------------------------------------------------ #

    def fields(self) -> list[Field]:
        rotulos = self.target_labels(
            t("arbitration.common.no_teams") if self.is_team else t("arbitration.common.no_players")
        )
        # O segundo seletor começa no segundo item: abrir os dois no mesmo nome
        # convida ao erro que a validação recusa logo em seguida.
        segundo = rotulos[1] if len(rotulos) > 1 else ""
        entidade = t("arbitration.field.team") if self.is_team else t("arbitration.field.player")
        return [
            Field(KEY_TARGET_A, f"{entidade} A", Field.OPTION, values=rotulos),
            Field(KEY_TARGET_B, f"{entidade} B", Field.OPTION, values=rotulos, initial=segundo),
            Field(
                KEY_FIRST_ROUND,
                t("arbitration.prohibitions.field.first_round"),
                placeholder="1",
            ),
            Field(
                KEY_LAST_ROUND,
                t("arbitration.prohibitions.field.last_round"),
                placeholder="0",
            ),
            Field(
                KEY_REASON,
                t("arbitration.field.reason"),
                placeholder=t("arbitration.prohibitions.reason_placeholder"),
            ),
        ]

    def columns(self) -> dict[str, tuple[str, int]]:
        entidade = t("arbitration.field.teams") if self.is_team else t("arbitration.field.players")
        return {
            "players": (entidade, 280),
            "window": (t("arbitration.prohibitions.column.window"), 100),
            "reason": (t("arbitration.field.reason"), 220),
        }

    def clear_on_add(self) -> tuple[str, ...]:
        return (KEY_FIRST_ROUND, KEY_LAST_ROUND, KEY_REASON)

    # ---- Dados ------------------------------------------------------------ #

    def rows(self) -> list[tuple[int, tuple[str, ...]]]:
        chave_a_id = "team_a_id" if self.is_team else "player_a_id"
        chave_b_id = "team_b_id" if self.is_team else "player_b_id"
        chave_a_nome = "team_a_name" if self.is_team else "player_a_name"
        chave_b_nome = "team_b_name" if self.is_team else "player_b_name"
        nome_por_id = {valor: rotulo.rsplit(" (#", 1)[0] for rotulo, valor in self.targets.items()}

        linhas = []
        for proibicao in self.controller.list_prohibitions(self.tournament_id, self.is_team):
            nome_a = proibicao.get(chave_a_nome) or nome_por_id.get(
                int(proibicao.get(chave_a_id) or 0), t("arbitration.common.removed")
            )
            nome_b = proibicao.get(chave_b_nome) or nome_por_id.get(
                int(proibicao.get(chave_b_id) or 0), t("arbitration.common.removed")
            )
            janela = round_window_label(
                int(proibicao.get("first_round") or 1), int(proibicao.get("last_round") or 0)
            )
            linhas.append(
                (
                    int(proibicao["id"]),
                    (f"{nome_a} x {nome_b}", janela, proibicao.get("reason") or ""),
                )
            )
        return linhas

    def add(self, values: dict[str, str]) -> None:
        formulario = ProhibitionForm(
            target_a_id=self.target_id(values.get(KEY_TARGET_A, "")),
            target_b_id=self.target_id(values.get(KEY_TARGET_B, "")),
            first_round_text=values.get(KEY_FIRST_ROUND, ""),
            last_round_text=values.get(KEY_LAST_ROUND, ""),
            reason=values.get(KEY_REASON, ""),
            is_team=self.is_team,
        )
        self.controller.add_prohibition(self.tournament_id, formulario)

    def snapshot(self, record_id: int) -> dict[str, Any] | None:
        return self.controller.find_prohibition(self.tournament_id, record_id, self.is_team)

    def delete(self, record_id: int) -> None:
        self.controller.delete_prohibition(record_id, self.is_team)

    def restore(self, record: dict[str, Any]) -> None:
        self.controller.restore_prohibition(self.tournament_id, record, self.is_team)
