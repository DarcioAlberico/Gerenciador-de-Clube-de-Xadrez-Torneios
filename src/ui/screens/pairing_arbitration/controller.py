"""Controlador das telas de arbitragem — decide e fala com os serviços (B-6).

Não importa Tk. Recebe banco e serviços por parâmetro, então roda com objetos
de mentira e sem abrir janela — o aceite da F1.5.

**A escolha entre individual e equipes mora aqui**, e explicitamente. As três
telas TRF25 (ajustes, byes, proibições) atendem os dois tipos de competição
chamando pares de funções diferentes do banco; despachar por ``getattr`` com
nome montado seria mais curto e transformaria um erro de digitação em
``AttributeError`` só na hora em que o árbitro clicasse.

O que **não** está aqui, de propósito: confirmar exclusão, escolher arquivo,
mostrar toast. Isso é conversa com o usuário, e conversa é da view.
"""
from __future__ import annotations

import logging
from typing import Any

from src.services.pairing.corrections import clean_reason
from src.services.pairing.point_adjustments import AdjustmentEntry, describe_entry

from ...i18n import t
from .state import (
    AdjustmentForm,
    ProhibitionForm,
    RequestedByeForm,
    targets_by_label,
)

logger = logging.getLogger("src.ui.screens.pairing_arbitration")


class ArbitrationController:
    def __init__(self, db: Any, *, pairing_service: Any) -> None:
        self.db = db
        self.pairing_service = pairing_service

    # ---- Leitura ---------------------------------------------------------- #

    def tournament(self, tournament_id: int) -> dict[str, Any] | None:
        return self.db.get_tournament(tournament_id)

    @staticmethod
    def is_team(tournament: dict[str, Any] | None) -> bool:
        return (tournament or {}).get("competition_type") == "team"

    def dashboard(
        self, tournament_id: int, *, pending_limit: int, pending_query: str
    ) -> dict[str, Any]:
        return dict(
            self.pairing_service.arbitration_dashboard(
                tournament_id,
                pending_limit=pending_limit,
                pending_query=pending_query,
            )
        )

    def issues(self, tournament_id: int) -> dict[str, Any]:
        return dict(self.pairing_service.arbitration_issues(int(tournament_id)))

    def filter_issues(
        self, issues: list[dict[str, Any]], filter_code: str, query: str
    ) -> list[dict[str, Any]]:
        return list(self.pairing_service.filter_arbitration_issues(issues, filter_code, query))

    def closing_checklist(self, tournament_id: int) -> list[dict[str, Any]]:
        return list(self.pairing_service.closing_checklist(int(tournament_id)))

    def round_numbers(self, tournament_id: int) -> dict[int, int]:
        """Id da rodada → número, para a coluna "Rodada" da Central."""
        return {
            int(rodada["id"]): int(rodada["number"])
            for rodada in self.db.list_rounds(int(tournament_id))
        }

    def generated_rounds(self, tournament_id: int) -> list[int]:
        """Números das rodadas **geradas**, em ordem."""
        rodadas = sorted(self.db.list_rounds(int(tournament_id)), key=lambda r: int(r["number"]))
        return [int(rodada["number"]) for rodada in rodadas]

    @staticmethod
    def configured_rounds(tournament: dict[str, Any] | None) -> list[int]:
        """Números das rodadas **previstas** no cadastro do torneio.

        Bye solicitado é declarado *antes* de a rodada existir — é essa a
        diferença para ``generated_rounds``, e é por isso que as duas listas não
        podem ser a mesma função.
        """
        total = int((tournament or {}).get("rounds_count") or 0)
        return list(range(1, total + 1))

    def targets(self, tournament_id: int, is_team: bool) -> dict[str, int]:
        """Rótulo → id de quem pode receber ajuste, bye ou proibição."""
        registros = (
            self.db.list_teams(tournament_id, active_only=False)
            if is_team
            else self.db.list_players(tournament_id, active_only=False)
        )
        return targets_by_label(list(registros))

    def latest_round(self, tournament_id: int) -> dict[str, Any] | None:
        return self.db.get_latest_round(tournament_id)

    def latest_round_id(self, tournament_id: int) -> int:
        """Id da última rodada gerada. Levanta se não houver nenhuma."""
        rodadas = self.db.list_rounds(tournament_id)
        if not rodadas:
            raise self._app_error(t("arbitration.error.no_round"))
        return int(sorted(rodadas, key=lambda item: int(item["number"]))[-1]["id"])

    # ---- Painel ----------------------------------------------------------- #

    def save_result(
        self, tournament_id: int, pairing_id: int, result: str, reason: str = ""
    ) -> None:
        """Lançamento inline do painel. `reason` só é exigido em rodada fechada.

        O painel trabalha na rodada em andamento, então o motivo vem vazio; o
        parâmetro existe para que o caminho de correção (ARB-01) não tenha uma
        porta de trás por aqui.

        Rodada fechada sem motivo é recusada **aqui**, com o recado do painel: o
        serviço diria "descreva o motivo", e a faixa de lançamento rápido não tem
        onde escrever um. O árbitro precisa saber para onde ir, não o que
        preencher numa tela que não tem o campo.
        """
        if not clean_reason(reason):
            pareamento = self.db.get_pairing(int(pairing_id)) or {}
            if str(pareamento.get("round_status") or "") == "closed":
                raise self._app_error(t("arbitration.error.closed_round_inline"))
        self.pairing_service.update_result(
            int(tournament_id), int(pairing_id), result, reason
        )

    def postpone_pairing(self, tournament_id: int, pairing_id: int, note: str = "") -> None:
        """Marca a mesa como adiada (ARB-02). Quem valida é o serviço."""
        self.pairing_service.postpone_pairing(int(tournament_id), int(pairing_id), note)

    def resume_pairing(self, tournament_id: int, pairing_id: int) -> None:
        self.pairing_service.resume_pairing(int(tournament_id), int(pairing_id))

    def acknowledge_issue(self, tournament_id: int, issue_key: str) -> None:
        self.pairing_service.acknowledge_arbitration_issue(int(tournament_id), str(issue_key))

    def save_settings(self, values: dict[str, str]) -> None:
        self.db.save_app_settings(values)

    # ---- Ajustes de pontos (TRF25 §7.3) ----------------------------------- #

    def list_adjustments(self, tournament_id: int) -> list[dict[str, Any]]:
        return list(self.db.list_point_adjustments(tournament_id))

    def add_adjustment(self, tournament_id: int, form: AdjustmentForm) -> None:
        erro = form.validation_error()
        if erro:
            raise self._app_error(erro)
        payload = form.payload()
        payload["id"] = self.db.add_point_adjustment(tournament_id, **payload)
        # Desde a TBK-01 o ajuste MOVE a classificação. Um lançamento que muda o
        # pódio precisa de trilha: sem isto, o registro do "por quê" vivia só na
        # tabela do painel, que o próprio árbitro pode apagar.
        self._audit(
            "point_adjustment_added",
            tournament_id,
            f"Ajuste de pontos lançado: {self._adjustment_digest(payload)}",
            payload,
        )
        logger.info("Ajuste de pontos lancado no torneio %s", tournament_id)

    def find_adjustment(self, tournament_id: int, adjustment_id: int) -> dict[str, Any] | None:
        return self._by_id(self.list_adjustments(tournament_id), adjustment_id)

    def delete_adjustment(self, tournament_id: int, adjustment_id: int) -> None:
        """Exclui e registra. Apagar um ajuste também reordena a classificação.

        Recebe o torneio (e não só o id do ajuste) porque a auditoria precisa
        dizer de onde o lançamento saiu — e porque uma única porta de exclusão,
        sempre auditada, é mais segura que duas com uma delas muda.
        """
        registro = self.find_adjustment(tournament_id, adjustment_id) or {"id": adjustment_id}
        self.db.delete_point_adjustment(int(adjustment_id))
        self._audit(
            "point_adjustment_removed",
            tournament_id,
            f"Ajuste de pontos excluído: {self._adjustment_digest(registro)}",
            registro,
        )

    def restore_adjustment(self, tournament_id: int, record: dict[str, Any]) -> None:
        self.db.add_point_adjustment(
            tournament_id,
            round_number=int(record.get("round_number") or 0),
            player_id=record.get("player_id"),
            team_id=record.get("team_id"),
            aat_type=str(record.get("aat_type") or ""),
            match_points=float(record.get("match_points") or 0.0),
            game_points=float(record.get("game_points") or 0.0),
            reason=str(record.get("reason") or ""),
        )
        self._audit(
            "point_adjustment_restored",
            tournament_id,
            f"Ajuste de pontos restaurado: {self._adjustment_digest(record)}",
            record,
        )

    # ---- Byes solicitados (TRF25) ----------------------------------------- #

    def list_byes(self, tournament_id: int, is_team: bool) -> list[dict[str, Any]]:
        if is_team:
            return list(self.db.list_requested_team_byes(tournament_id))
        return list(self.db.list_requested_byes(tournament_id))

    def add_bye(self, tournament_id: int, form: RequestedByeForm) -> None:
        erro = form.validation_error()
        if erro:
            raise self._app_error(erro)
        self._add_bye(
            tournament_id,
            form.is_team,
            int(form.target_id or 0),
            int(form.round_number or 0),
            form.bye_type,
            form.reason.strip(),
        )
        logger.info("Bye solicitado registrado no torneio %s", tournament_id)

    def find_bye(
        self, tournament_id: int, bye_id: int, is_team: bool
    ) -> dict[str, Any] | None:
        return self._by_id(self.list_byes(tournament_id, is_team), bye_id)

    def delete_bye(self, bye_id: int, is_team: bool) -> None:
        if is_team:
            self.db.delete_requested_team_bye(int(bye_id))
        else:
            self.db.delete_requested_bye(int(bye_id))

    def restore_bye(self, tournament_id: int, record: dict[str, Any], is_team: bool) -> None:
        chave = "team_id" if is_team else "player_id"
        self._add_bye(
            tournament_id,
            is_team,
            int(record[chave]),
            int(record.get("round_number") or 0),
            str(record.get("bye_type") or "H"),
            str(record.get("reason") or ""),
        )

    def _add_bye(
        self,
        tournament_id: int,
        is_team: bool,
        target_id: int,
        round_number: int,
        bye_type: str,
        reason: str,
    ) -> None:
        adicionar = self.db.add_requested_team_bye if is_team else self.db.add_requested_bye
        adicionar(tournament_id, target_id, round_number, bye_type, reason=reason)

    # ---- Proibições de pareamento (TRF25 registro 260) -------------------- #

    def list_prohibitions(self, tournament_id: int, is_team: bool) -> list[dict[str, Any]]:
        if is_team:
            return list(self.db.list_prohibited_team_pairings(tournament_id))
        return list(self.db.list_prohibited_pairings(tournament_id))

    def add_prohibition(self, tournament_id: int, form: ProhibitionForm) -> None:
        erro = form.validation_error()
        if erro:
            raise self._app_error(erro)
        self._add_prohibition(
            tournament_id,
            form.is_team,
            int(form.target_a_id or 0),
            int(form.target_b_id or 0),
            form.payload(),
        )
        logger.info("Proibicao de pareamento cadastrada no torneio %s", tournament_id)

    def find_prohibition(
        self, tournament_id: int, prohibition_id: int, is_team: bool
    ) -> dict[str, Any] | None:
        return self._by_id(self.list_prohibitions(tournament_id, is_team), prohibition_id)

    def delete_prohibition(self, prohibition_id: int, is_team: bool) -> None:
        if is_team:
            self.db.delete_prohibited_team_pairing(int(prohibition_id))
        else:
            self.db.delete_prohibited_pairing(int(prohibition_id))

    def restore_prohibition(
        self, tournament_id: int, record: dict[str, Any], is_team: bool
    ) -> None:
        chave_a = "team_a_id" if is_team else "player_a_id"
        chave_b = "team_b_id" if is_team else "player_b_id"
        self._add_prohibition(
            tournament_id,
            is_team,
            int(record[chave_a]),
            int(record[chave_b]),
            {
                "first_round": int(record.get("first_round") or 1),
                "last_round": int(record.get("last_round") or 0),
                "reason": str(record.get("reason") or ""),
            },
        )

    def _add_prohibition(
        self,
        tournament_id: int,
        is_team: bool,
        target_a_id: int,
        target_b_id: int,
        payload: dict[str, Any],
    ) -> None:
        adicionar = (
            self.db.add_prohibited_team_pairing if is_team else self.db.add_prohibited_pairing
        )
        adicionar(tournament_id, target_a_id, target_b_id, **payload)

    # ---- Apoio ------------------------------------------------------------ #

    @staticmethod
    def _by_id(records: list[dict[str, Any]], record_id: int) -> dict[str, Any] | None:
        """Retrato do registro **antes** da exclusão, para o Desfazer da F2.4."""
        return next((row for row in records if int(row["id"]) == int(record_id)), None)

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)

    @staticmethod
    def _adjustment_digest(record: dict[str, Any]) -> str:
        """Uma linha legível do ajuste, para a descrição do evento de auditoria."""
        alvo = record.get("player_name") or record.get("team_name")
        if not alvo:
            alvo = f"#{record.get('player_id') or record.get('team_id') or '?'}"
        entrada = AdjustmentEntry(
            round_number=int(record.get("round_number") or 0),
            aat_type=str(record.get("aat_type") or ""),
            match_points=float(record.get("match_points") or 0.0),
            game_points=float(record.get("game_points") or 0.0),
            reason=str(record.get("reason") or ""),
        )
        return f"{alvo} — {describe_entry(entrada)}"

    def _audit(
        self,
        action: str,
        tournament_id: int,
        description: str,
        record: dict[str, Any],
    ) -> None:
        """Evento na trilha do torneio — a mesma de ``round_generated``.

        Vai para `audit_events` (e não para o log de segurança) porque é onde o
        `export_tournament_audit` procura: assim o motivo escrito pelo árbitro
        sai no relatório de auditoria com operador, data e hora.

        Falha de auditoria não desfaz o que o árbitro já decidiu — o lançamento
        está gravado, e derrubar a tela por causa da trilha trocaria um problema
        de registro por um de operação em pleno salão. Vai para o log.
        """
        campos = ("round_number", "player_id", "team_id", "aat_type",
                  "match_points", "game_points")
        metadata: dict[str, Any] = {"summary": description}
        metadata.update(
            {campo: record[campo] for campo in campos if record.get(campo) is not None}
        )
        try:
            self.db.create_audit_event(
                action=action,
                tournament_id=int(tournament_id),
                entity_type="point_adjustment",
                entity_id=int(record.get("id") or 0) or None,
                reason=str(record.get("reason") or "").strip(),
                metadata=metadata,
            )
        except Exception:  # pragma: no cover - trilha nunca bloqueia a decisão
            logger.exception("Falha ao registrar auditoria de %s", action)
