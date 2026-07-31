"""Controlador da tela de Jogadores — decide e fala com os serviços (B-6).

Não importa Tk. Recebe banco e serviços por parâmetro, então roda com objetos
de mentira e sem abrir janela — o aceite da F1.5.

O que **não** está aqui, de propósito: escolher arquivo, confirmar exclusão,
mostrar toast. Isso é conversa com o usuário, e conversa é da view.
"""
from __future__ import annotations

import logging
from typing import Any

from src.services.constants import PLAYER_STATUSES, player_full_name

from ...i18n import t
from .state import (
    PlayerForm,
    PlayerRow,
    PlayersSummary,
    matches,
    normalize_scheveningen_group,
    summarize,
)

logger = logging.getLogger("src.ui.screens.tournament_players")


def _member_label(member: dict[str, Any]) -> str:
    """"Sobrenome, Nome" — mesma forma que a lista de sócios usa."""
    nome = str(member.get("name") or "").strip()
    sobrenome = str(member.get("surname") or "").strip()
    return f"{sobrenome}, {nome}" if sobrenome and nome else sobrenome or nome


class TournamentPlayersController:
    def __init__(
        self,
        db: Any,
        *,
        member_service: Any,
        pairing_service: Any,
    ) -> None:
        self.db = db
        self.member_service = member_service
        self.pairing_service = pairing_service

    # ---- Leitura ---------------------------------------------------------- #

    def rows(self, tournament_id: int, query: str = "") -> tuple[list[PlayerRow], PlayersSummary]:
        """Linhas visíveis e o resumo. O resumo conta **todos**, não só os visíveis.

        Devolver os dois juntos é o que impede a tela de contar duas vezes — e
        de discordar de si mesma quando alguém mexer só num dos laços.
        """
        jogadores = list(self.db.list_players(tournament_id, active_only=False))
        visiveis = [jogador for jogador in jogadores if matches(query, jogador)]
        return [self._row(jogador) for jogador in visiveis], summarize(jogadores, len(visiveis))

    @staticmethod
    def _row(player: dict[str, Any]) -> PlayerRow:
        status = str(player.get("player_status") or "active")
        return PlayerRow(
            player_id=int(player["id"]),
            name=player_full_name(player),
            source=t("players.source.member") if player.get("member_id") else t("players.source.guest"),
            rating=player.get("rating"),
            fide_id=str(player.get("fide_id") or ""),
            cbx_id=str(player.get("cbx_id") or ""),
            lbx_id=str(player.get("lbx_id") or ""),
            club=str(player.get("club") or ""),
            klass=str(player.get("active_class_name") or ""),
            category=str(player.get("category") or ""),
            age_category=str(player.get("age_category") or ""),
            rating_category=str(player.get("rating_category") or ""),
            tags=str(player.get("prize_tags") or ""),
            status=PLAYER_STATUSES.get(status, status),
        )

    def get_player(self, player_id: int) -> dict[str, Any] | None:
        return self.db.get_player(player_id)

    def member_options(
        self, tournament_id: int, include_out_of_scope: bool = False
    ) -> dict[str, int]:
        """Rótulo → id dos sócios ainda **não** inscritos neste torneio."""
        opcoes: dict[str, int] = {}
        for member in self.db.list_members_for_tournament(
            tournament_id,
            active_only=True,
            include_out_of_scope=include_out_of_scope,
        ):
            if member["registered_player_id"]:
                continue
            clube = str(member.get("club_name") or t("players.member.no_club")).strip()
            turma = str(member.get("active_class_name") or "").strip()
            escopo = " / ".join([clube, turma]) if turma else clube
            rotulo = f"{member['id']} - {_member_label(member)} ({member['rating']}) - {escopo}"
            opcoes[rotulo] = int(member["id"])
        return opcoes

    def member_source_label(self, tournament: dict[str, Any] | None) -> str:
        """Rótulo do seletor de sócios: ele muda com o escopo do torneio.

        "Membro da turma" e "Membro do clube/escola" não são enfeite — dizem de
        onde vem a lista, e é a única pista na tela de que um torneio de turma
        não oferece o clube inteiro.
        """
        if tournament and tournament.get("class_id"):
            return t("players.member.source.class")
        if tournament and tournament.get("club_id"):
            return t("players.member.source.club")
        return t("players.member.source.any")

    def official_match(self, source_key: str, value: str) -> dict[str, Any] | None:
        """Registro mais recente da base oficial para um ID digitado."""
        limpo = (value or "").strip()
        if not limpo:
            return None
        return self.db.find_latest_official_player(**{source_key: limpo})

    # ---- Escrita ---------------------------------------------------------- #

    def create(
        self, tournament_id: int, form: PlayerForm, starting_points: float | None = None
    ) -> int:
        erro = form.validation_error()
        if erro:
            raise self._app_error(erro)
        player_id = int(
            self.db.create_player(tournament_id, **form.create_payload(starting_points))
        )
        logger.info("Jogador criado no torneio %s: %s", tournament_id, form.name.strip())
        return player_id

    def update(self, player_id: int, form: PlayerForm) -> None:
        erro = form.validation_error()
        if erro:
            raise self._app_error(erro)
        atual = self.db.get_player(player_id)
        if not atual:
            raise self._app_error(t("players.error.not_found"))
        self.db.update_player(player_id, **form.update_payload(atual))
        logger.info("Jogador atualizado: %s", player_id)

    def set_status(self, player_id: int, status: str, reason: str = "") -> None:
        """Muda a participacao pelo SERVICO (ARB-05).

        Era `db.set_player_status` cru: o campo guarda o estado de agora e apaga
        o anterior, entao "saiu na rodada 3, voltou na 5" nao ficava em lugar
        nenhum. O servico grava o evento junto, com a rodada de vigencia.
        """
        jogador = self.db.get_player(int(player_id))
        tournament_id = int((jogador or {}).get("tournament_id") or 0)
        self.pairing_service.set_player_participation(
            tournament_id, int(player_id), status, reason
        )
        logger.info("Status do jogador %s alterado para %s", player_id, status)

    def set_scheveningen_group(self, player_id: int, group: str) -> None:
        self.db.set_player_scheveningen_group(player_id, normalize_scheveningen_group(group))

    def delete_if_unpaired(self, tournament_id: int, player_id: int) -> None:
        self.pairing_service.delete_player_if_unpaired(tournament_id, player_id)

    def register_member(
        self, tournament_id: int, member_id: int | None, allow_out_of_scope: bool = False
    ) -> None:
        if not member_id:
            raise self._app_error(t("players.error.no_member_available"))
        self.member_service.register_member_in_tournament(
            tournament_id, member_id, allow_out_of_scope=allow_out_of_scope
        )

    def register_all_active_members(
        self, tournament_id: int, include_out_of_scope: bool = False
    ) -> dict[str, Any]:
        return dict(
            self.member_service.register_active_members_in_tournament(
                tournament_id, include_out_of_scope=include_out_of_scope
            )
        )

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
