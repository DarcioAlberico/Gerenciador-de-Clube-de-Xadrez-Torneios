"""Exportador TRF25 — scaffold sobre TRF16.

Status (2026-05-29): TRF25 é um *final draft* da FIDE Technical Commission
com layout de campo estável (ver `ESPEC_TRF25_FIDE.md`). Esta implementação é
**parcial e incremental** — cresce por fatias, cada uma com testes.

Já implementado:
- Fatia 1: registro 310 (equipe, substitui o 013) com match/game points e
  rank; cabeçalho 142 (nº de rodadas) e 192 (tipo codificado); 352 (sequência
  de cores dos tabuleiros) em torneios por equipes.
- Fatia 2: registro 320 (pairing-allocated-bye de equipes), mapeado dos byes
  de equipe já fechados. Os construtores puros de 240/330/300/299 existem em
  `trf25_records.py` (com testes de coluna), mas **ainda não são emitidos** —
  o modelo de dados do projeto não distingue forfeit/out-of-order/ajuste
  anormal de um resultado normal, então emiti-los enganaria o árbitro.

Ainda equivalente ao TRF16 (warning obrigatório enquanto incompleto):
tiebreaks 212, sistemas 162/362, forfeits/out-of-order/ajustes estruturados
(330/300/299) e informativos 801/802. Por isso `export()` ainda devolve o
TRF25_SCAFFOLD_WARNING — para nunca enganar o árbitro.

## O que falta para um TRF25 completo

O layout exato dos registros já foi consolidado em `ESPEC_TRF25_FIDE.md`
(na raiz do projeto). Quando implementado, estes registros precisam ser
adicionados (sobrescrevendo `export`); os nomes abaixo são os códigos
numéricos reais da spec — **não** existem "linha TC" nem "XXR/XXC", e a
linha 001 **não** carrega tiebreaks/TPR:

- **310** (equipes): substitui o 013, com match points, game points, rank,
  strength factor e nickname.
- **162 / 362**: sistemas de pontuação (individual / equipes), só quando
  divergem do padrão FIDE.
- **192**: tipo de torneio codificado (obrigatório p/ pareamento).
- **202 / 212**: tie-breaks usados (a classificação fica no 212).
- **352**: sequência de cores dos tabuleiros (equipes; obrigatório).
- **142 / 152 / 222**: nº de rodadas, cor inicial, time control codificado.
- **240 / 320 / 330 / 300 / 299**: byes, PAB, forfeits, out-of-order e
  ajustes anormais de pontos.
- **801 / 802**: registros informativos opcionais (priorizar 802).

Tabelas de código (192 e 212) já consolidadas: ver Anexos A e B da
ESPEC_TRF25_FIDE.md (Tournament-Type Code Table e Mandatory Tie-Breaks).

Fontes:
- https://tec.fide.com/2025/01/09/trf25-final-draft/
- http://tec.fide.com/wp-content/uploads/2025/01/TRF25-FinalDraft.pdf
- https://tec.fide.com/2024/09/04/draft-trf-2025-extensions-for-team-pairing-and-tie-breaks/

"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.services.constants import AppError, player_pairing_name
from src.services.federation_exporters.base import FederationExportFormat
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.federation_exporters.trf25_records import (
    record_310,
    record_320,
    tournament_line,
)


TRF25_SCAFFOLD_WARNING = (
    "TRF25: implementação parcial — tiebreaks (212), sistemas de pontuação "
    "(162/362) e byes/forfeits estruturados ainda não emitidos. "
    "Use TRF16 para envio oficial até a especificação ser finalizada."
)


class TRF25Exporter(TRF16Exporter):
    """Exportador TRF25 incremental (ver ESPEC_TRF25_FIDE.md)."""

    format = FederationExportFormat(
        code="trf25",
        label="FIDE TRF25 (draft — parcial)",
        extension="trf",
    )

    def export(self, tournament_id: int, file_path: str | Path) -> list[str]:
        service = self.export_service
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        warnings = self.validate(tournament_id)
        players = sorted(
            self.db.list_players(tournament_id, active_only=False),
            key=lambda player: (
                -service._trf_rating(player),
                player_pairing_name(player).casefold(),
                int(player.get("id") or 0),
            ),
        )
        rounds = sorted(self.db.list_rounds(tournament_id), key=lambda r: r["number"])
        schedule = {
            int(item["round_number"]): str(item.get("date") or "").strip()
            for item in self.db.list_round_schedule(tournament_id)
        }
        is_team = tournament.get("competition_type") == "team"
        pairings_by_round = service._trf_pairings_by_round(tournament, rounds)
        start_rank_by_player = {int(p["id"]): i for i, p in enumerate(players, start=1)}
        standings_by_player = service._trf_player_standings(tournament, players)
        round_count = max(
            [int(tournament.get("rounds_count") or 0), *(int(r["number"]) for r in rounds)],
            default=0,
        )
        teams = self.db.list_teams(tournament_id, active_only=False) if is_team else []

        path = Path(file_path)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(service._trf_tournament_line("012", tournament["name"]))
            handle.write(service._trf_tournament_line("022", tournament.get("location", "")))
            handle.write(service._trf_tournament_line("032", settings.get("federation", "")))
            handle.write(service._trf_tournament_line("042", service._trf_date(tournament.get("start_date"), long_year=True)))
            handle.write(service._trf_tournament_line("052", service._trf_date(tournament.get("end_date"), long_year=True)))
            handle.write(service._trf_tournament_line("062", str(len(players))))
            rated = sum(1 for p in players if service._trf_rating(p) > 0)
            handle.write(service._trf_tournament_line("072", str(rated)))
            handle.write(service._trf_tournament_line("082", str(len(teams))))
            handle.write(service._trf_tournament_line("092", service._trf_tournament_type(tournament, settings)))
            handle.write(service._trf_tournament_line("102", service._trf_chief_arbiter(tournament_id, settings)))
            for deputy in service._trf_deputy_arbiters(tournament_id, settings):
                handle.write(service._trf_tournament_line("112", deputy))
            handle.write(service._trf_tournament_line("122", tournament.get("time_control", "")))
            handle.write(service._trf_round_dates_line(round_count, schedule))

            # Extensões TRF25 (ESPEC §1).
            handle.write(tournament_line("142", round_count))
            handle.write(tournament_line("192", self._type_code_192(tournament, settings)))
            if is_team:
                handle.write(tournament_line("352", self._colour_sequence_352(settings)))

            for player in players:
                handle.write(
                    service._trf_player_line(
                        player, start_rank_by_player, standings_by_player,
                        pairings_by_round, round_count, settings,
                    )
                )
            prepared = self._prepare_teams(tournament_id, teams, players, start_rank_by_player)
            tpn_by_team = {item["team_id"]: number for number, item in enumerate(prepared, start=1)}
            for line in self._team_records_310(prepared):
                handle.write(line)
            if is_team:
                pab_line = self._pab_record_320(tournament_id, tpn_by_team, round_count, settings)
                if pab_line:
                    handle.write(pab_line)

        return warnings

    def validate(self, tournament_id: int) -> list[str]:
        warnings = super().validate(tournament_id)
        return [TRF25_SCAFFOLD_WARNING, *warnings]

    @staticmethod
    def _score_token(name: str) -> str:
        return "GP" if "game" in str(name).casefold() else "MP"

    def _type_code_192(self, tournament: dict[str, Any], settings: dict[str, Any]) -> str:
        if tournament.get("competition_type") == "team":
            primary = self._score_token(settings.get("team_standing_primary", "match_points"))
            secondary = self._score_token(settings.get("team_standing_secondary", "game_points"))
            score = f"{primary}_{secondary}" if secondary != primary else primary
            return f"FIDE_TEAM_TYPEA_{score}"
        method = str(settings.get("pairing_method", "swiss")).casefold()
        if method == "round_robin":
            return "FIDE_ROUNDROBIN"
        if method == "knockout":
            return "WORLDCUP_KNOCKOUT"
        return "FIDE_DUTCH"

    @staticmethod
    def _colour_sequence_352(settings: dict[str, Any]) -> str:
        boards = int(settings.get("team_boards_count") or 0)
        return "".join("W" if index % 2 == 0 else "B" for index in range(boards))

    def _prepare_teams(
        self,
        tournament_id: int,
        teams: list[dict[str, Any]],
        players: list[dict[str, Any]],
        start_rank_by_player: dict[int, int],
    ) -> list[dict[str, Any]]:
        """Reúne e ordena os dados de equipe usados pelos 310/320 (ordena por
        força decrescente; a ordem define o Team Pairing Number sequencial)."""
        if not teams:
            return []
        rating_by_player = {int(p["id"]): self.export_service._trf_rating(p) for p in players}
        standings = {
            int(item["team_id"]): item
            for item in self.export_service.pairing_service.team_standings(tournament_id)
        }
        prepared: list[dict[str, Any]] = []
        for team in teams:
            team_id = int(team["id"])
            assignments = sorted(
                self.db.list_team_players(team_id, active_only=False),
                key=lambda a: (int(a.get("board_number") or 0), int(a.get("id") or 0)),
            )
            board_ranks: list[int] = []
            ratings: list[int] = []
            for assignment in assignments:
                player_id = int(assignment["player_id"])
                rank = start_rank_by_player.get(player_id)
                if not rank:
                    continue
                board_ranks.append(rank)
                if rating_by_player.get(player_id):
                    ratings.append(rating_by_player[player_id])
            standing = standings.get(team_id, {})
            prepared.append(
                {
                    "team": team,
                    "team_id": team_id,
                    "ranks": board_ranks,
                    "strength": round(sum(ratings) / len(ratings)) if ratings else 0,
                    "match_points": float(standing.get("match_points", 0.0) or 0.0),
                    "game_points": float(standing.get("game_points", 0.0) or 0.0),
                    "rank": int(standing.get("position") or 0),
                }
            )

        prepared.sort(key=lambda item: (-item["strength"], str(item["team"].get("name") or "").casefold()))
        return prepared

    @staticmethod
    def _team_records_310(prepared: list[dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        for pairing_number, item in enumerate(prepared, start=1):
            team = item["team"]
            lines.append(
                record_310(
                    team_pairing_number=pairing_number,
                    team_name=team.get("name", ""),
                    nickname=TRF25Exporter._team_nickname(team),
                    strength_factor=item["strength"],
                    match_points=item["match_points"],
                    game_points=item["game_points"],
                    team_rank=item["rank"],
                    player_start_ranks=item["ranks"],
                )
            )
        return lines

    def _pab_record_320(
        self,
        tournament_id: int,
        tpn_by_team: dict[int, int],
        round_count: int,
        settings: dict[str, Any],
    ) -> str | None:
        """Registro 320 — pairing-allocated-bye das equipes (1 por torneio).

        Cada bye de equipe registrado é um PAB: mapeia rodada → TPN da equipe
        que recebeu o bye. Só emite se houver pelo menos um bye fechado."""
        tpn_by_round: dict[int, int] = {}
        win_points = 0.0
        game_points = 0.0
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            if not match.get("is_bye"):
                continue
            round_number = int(match.get("round_number") or 0)
            team_id = int(match.get("white_team_id") or 0)
            tpn = tpn_by_team.get(team_id)
            if not round_number or not tpn:
                continue
            tpn_by_round[round_number] = tpn
            win_points = float(match.get("white_match_points", win_points) or win_points)
            game_points = float(match.get("white_game_points", game_points) or game_points)
        if not tpn_by_round:
            return None
        sequence = [tpn_by_round.get(rnd, 0) for rnd in range(1, round_count + 1)]
        return record_320(win_points, game_points, sequence)

    @staticmethod
    def _team_nickname(team: dict[str, Any]) -> str:
        letters = "".join(ch for ch in str(team.get("name") or "") if ch.isalnum())
        return letters[:5].upper()
