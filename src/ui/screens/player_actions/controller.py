"""Controlador das ações na linha do jogador — fala com o serviço (RGS-22/23/24).

Não importa Tk. Toda mudança de status passa por
``PairingService.set_player_participation`` (histórico ARB-05) e todo bye por
``request_bye``/``miss_round`` (política ARB-04): a tela não grava nada direto
no banco.
"""
from __future__ import annotations

from typing import Any, Mapping

from src.services.constants import AppError
from src.services.pairing.participation import STATUS_ACTIVE

from .state import SCOPE_ROUND


class PlayerActionsController:
    def __init__(self, db: Any, pairing_service: Any) -> None:
        self.db = db
        self.service = pairing_service

    # ---- Leitura ---------------------------------------------------------- #

    def player(self, player_id: int) -> dict[str, Any]:
        jogador = self.db.get_player(int(player_id))
        if not jogador:
            raise AppError("Jogador não encontrado.")
        return dict(jogador)

    def next_round(self, tournament_id: int) -> int:
        return int(self.service.next_round_number(int(tournament_id)))

    def rounds_count(self, tournament_id: int) -> int:
        return int((self.db.get_tournament(int(tournament_id)) or {}).get("rounds_count") or 0)

    def open_round_board(self, tournament_id: int, player_id: int) -> int:
        """Número da rodada GERADA e aberta em que o jogador tem mesa sem resultado.

        ``0`` quando não há: é a rodada em que "faltar" já não é bye, é W.O.
        """
        ultima = self.db.get_latest_round(int(tournament_id))
        if not ultima or str(ultima.get("status") or "") == "closed":
            return 0
        numero = int(ultima.get("number") or 0)
        situacao = self.service.player_round_situation(int(tournament_id), int(player_id), numero)
        if situacao["pairing_id"] and not situacao["is_bye"] and not situacao["has_result"]:
            return numero
        return 0

    def absence_round(self, tournament_id: int, player_id: int) -> int:
        """A rodada que "Faltar só à rodada N…" oferece primeiro.

        A rodada em andamento, se o jogador ainda está numa mesa dela sem
        resultado (o caso do "não vou conseguir chegar"); senão, a próxima.
        """
        return self.open_round_board(tournament_id, player_id) or self.next_round(tournament_id)

    def bye_rounds(self, tournament_id: int, player_id: int) -> list[int]:
        """Rodadas que o diálogo de bye oferece: a aberta (para W.O.) e as futuras."""
        proxima = self.next_round(tournament_id)
        total = self.rounds_count(tournament_id) or proxima
        rodadas = list(range(proxima, total + 1))
        aberta = self.open_round_board(tournament_id, player_id)
        return ([aberta] if aberta else []) + rodadas

    def situation(self, tournament_id: int, player_id: int, round_number: int) -> dict[str, Any]:
        return dict(
            self.service.player_round_situation(int(tournament_id), int(player_id), int(round_number))
        )

    def bye_balance(self, tournament_id: int, player_id: int) -> str:
        return str(self.service.bye_balance(int(tournament_id), int(player_id)))

    # ---- Escrita ---------------------------------------------------------- #

    def request_bye(
        self, tournament_id: int, player_id: int, round_number: int, bye_type: str, reason: str
    ) -> None:
        if str(bye_type).upper() == "Z":
            self.service.miss_round(int(tournament_id), int(player_id), int(round_number), reason)
            return
        self.service.request_bye(
            int(tournament_id), int(player_id), int(round_number), str(bye_type).upper(), reason=reason
        )

    def forfeit(self, tournament_id: int, player_id: int, round_number: int, reason: str) -> Mapping[str, Any]:
        return self.service.forfeit_absent_player(
            int(tournament_id), int(player_id), int(round_number), reason
        )

    def withdraw(self, tournament_id: int, player_id: int, scope: str, reason: str) -> int:
        """Aplica o escopo escolhido. Devolve a rodada a partir da qual vale."""
        if scope == SCOPE_ROUND:
            rodada = self.next_round(tournament_id)
            self.service.miss_round(int(tournament_id), int(player_id), rodada, reason)
            return rodada
        return int(
            self.service.set_player_participation(
                int(tournament_id), int(player_id), scope, reason
            )
        )

    def reinstate(self, tournament_id: int, player_id: int, reason: str) -> int:
        return int(
            self.service.set_player_participation(
                int(tournament_id), int(player_id), STATUS_ACTIVE, reason
            )
        )

    # ---- Entrada tardia (RGS-24) ------------------------------------------ #

    def late_entry_plan(self, tournament_id: int, per_round_points: float | None = None) -> Any:
        return self.service.late_entry_plan(int(tournament_id), per_round_points)

    def official_lookup(self, identifier: str) -> dict[str, Any] | None:
        """Registro da base oficial (FIDE, depois CBX) para o ID digitado."""
        limpo = (identifier or "").strip()
        if not limpo:
            return None
        for chave in ("fide_id", "cbx_id"):
            achado = self.db.find_latest_official_player(**{chave: limpo})
            if achado:
                return dict(achado)
        return None

    def register_late_entry(
        self, tournament_id: int, data: Mapping[str, Any], per_round_points: float
    ) -> Mapping[str, Any]:
        return self.service.register_late_entry(int(tournament_id), dict(data), per_round_points)
