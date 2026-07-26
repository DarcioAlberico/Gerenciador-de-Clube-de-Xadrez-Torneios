"""Controlador da tela de Torneios — decide e fala com os serviços (B-6).

Não importa Tk. Recebe banco e serviços por parâmetro, o que o torna testável
com objetos de mentira e sem abrir janela — que é o aceite da F1.5, agora
aplicado a uma tela de verdade em vez da tela-piloto.

O que **não** está aqui, deliberadamente: confirmar exclusão, escolher arquivo,
mostrar toast. Isso é conversa com o usuário, e conversa é da view. O
controlador responde "dá para excluir?" e "exclua"; quem pergunta "tem certeza?"
é quem tem uma janela.
"""
from __future__ import annotations

import logging
from typing import Any

from .state import TournamentForm, TournamentRow

logger = logging.getLogger("src.ui.screens.tournaments")


class TournamentListController:
    def __init__(
        self,
        db: Any,
        tournament_service: Any,
        import_service: Any,
        *,
        scope_labels: dict[str, str],
        competition_labels: dict[str, str],
        scope_key: Any,
    ) -> None:
        self.db = db
        self.tournament_service = tournament_service
        self.import_service = import_service
        self._scope_labels = scope_labels
        self._competition_labels = competition_labels
        self._scope_key = scope_key

    # ---- Leitura ---------------------------------------------------------- #

    def rows(self) -> list[TournamentRow]:
        """Lista pronta para a tabela, com os rótulos já resolvidos."""
        return [self._row(tournament) for tournament in self.db.list_tournaments()]

    def _row(self, tournament: dict[str, Any]) -> TournamentRow:
        competition = str(tournament.get("competition_type") or "individual")
        return TournamentRow(
            tournament_id=int(tournament["id"]),
            name=str(tournament["name"]),
            competition=self._competition_labels.get(competition, "Individual"),
            scope=self._scope_labels[self._scope_key(tournament)],
            club=str(tournament.get("club_name") or ""),
            klass=str(tournament.get("class_name") or ""),
            location=str(tournament["location"]),
            rounds=str(tournament["rounds_count"]),
            status=str(tournament["status"]),
        )

    def club_options(self, club_kind_labels: dict[str, str]) -> dict[str, int]:
        """Rótulo → id dos clubes ativos. Nunca vazio: sem clube cadastrado, a
        tela precisa de ao menos uma opção para o escopo 'clube' funcionar."""
        opcoes: dict[str, int] = {}
        for club in self.db.list_clubs(active_only=True):
            kind = str(club.get("kind", "club"))
            rotulo = f"{club['id']} - {club['name'] or 'Clube padrao'} ({club_kind_labels.get(kind, kind)})"
            opcoes[rotulo] = int(club["id"])
        if not opcoes:
            opcoes["1 - Clube padrao (Clube)"] = 1
        return opcoes

    def class_options(self, club_id: int | None) -> dict[str, int | None]:
        """Rótulo → id das turmas do clube. "Sem turma" sempre presente."""
        opcoes: dict[str, int | None] = {"Sem turma": None}
        if club_id:
            for turma in self.db.list_classes(club_id=club_id, active_only=True):
                opcoes[f"{turma['id']} - {turma['name']}"] = int(turma["id"])
        return opcoes

    # ---- Escrita ---------------------------------------------------------- #

    def create(self, form: TournamentForm) -> int:
        """Cria e devolve o id. Levanta ``AppError`` com a primeira pendência."""
        erro = form.validation_error()
        if erro:
            raise self._app_error(erro)
        tournament_id = int(self.tournament_service.create_tournament(form.payload()))
        logger.info("Torneio criado: %s", tournament_id)
        return tournament_id

    def duplicate(self, tournament_id: int, new_name: str) -> int:
        """Duplica. Nome vazio cai no sugerido — o usuário só apertou Enter."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise self._app_error("Torneio selecionado nao encontrado.")
        nome = new_name.strip() or self.suggested_copy_name(tournament)
        return int(self.tournament_service.duplicate_tournament(tournament_id, nome))

    @staticmethod
    def suggested_copy_name(tournament: dict[str, Any]) -> str:
        return f"{tournament['name']} - copia"

    def delete(self, tournament_id: int) -> None:
        self.tournament_service.delete_tournament(tournament_id)

    def split(self, tournament_id: int, groups: str) -> list[int]:
        return list(self.tournament_service.split_tournament(tournament_id, groups.strip()))

    def import_trf(self, file_path: str) -> dict[str, Any]:
        return dict(self.import_service.import_trf(file_path))

    def display_name(self, tournament_id: int) -> str:
        """Nome para a mensagem de confirmação; cai no id se o registro sumiu."""
        tournament = self.db.get_tournament(tournament_id)
        return str(tournament["name"]) if tournament else str(tournament_id)

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
