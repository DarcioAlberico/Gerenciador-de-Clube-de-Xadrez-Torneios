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
- Fatia 3: registro 212 (tie-breaks de classificação, espelhando a ordem fixa
  de `pairing/tiebreaks.py`) e registro 362 (sistema de pontuação por equipes,
  só quando diverge do padrão TW=2/TD=1/TL=0). O 162 (individual) nunca é
  emitido: o projeto sempre usa pontos FIDE-padrão (1/0.5/0), então omiti-lo é
  o comportamento correto.
- Fatia 4: registro 802 (resumo informativo de equipe, comprimento fixo) com
  oponente/cor/game-points por rodada. O 801 (variável) é dispensado em favor
  do 802; o indicador de forfeit fica vazio (o modelo não o distingue).
- Fatia 5: registro 330 (matches forfeitados). O projeto só marca W.O. por
  tabuleiro, então inferimos de forma conservadora — só emite quando *todos* os
  tabuleiros do match são W.O. consistente (+-/-+/--); forfeit parcial/misto é
  ignorado para não enganar o árbitro.

Ainda não emitidos (por falta de modelo de dados): 300 (out-of-order) exigiria
marcação explícita de escalação fora de ordem; 299 (ajuste anormal de pontos)
exigiria uma tabela de penalidades/bônus manuais. Os construtores puros de
ambos já existem e estão testados. Como o layout ainda é *final draft*,
`export()` segue devolvendo o TRF25_SCAFFOLD_WARNING — para nunca enganar o
árbitro.

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

from src.services.constants import RESULT_POINTS, AppError, player_pairing_name
from src.services.federation_exporters.base import FederationExportFormat
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.federation_exporters.trf25_records import (
    record_212,
    record_310,
    record_320,
    record_330,
    record_362,
    record_802,
    tournament_line,
)


# Resultados de tabuleiro que representam W.O. (não jogado).
_FORFEIT_RESULTS = frozenset({"1F-0F", "0F-1F", "0F-0F"})


TRF25_SCAFFOLD_WARNING = (
    "TRF25: implementação parcial — out-of-order/ajustes (300/299) ainda não "
    "emitidos, e o layout segue final draft da FIDE. "
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
            handle.write(record_212(self._tiebreak_codes_212(is_team)))
            if is_team:
                handle.write(tournament_line("352", self._colour_sequence_352(settings)))
                scoring_362 = self._scoring_system_362(settings)
                if scoring_362:
                    handle.write(scoring_362)

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
                for line in self._forfeit_records_330(tournament_id, tpn_by_team):
                    handle.write(line)
                for line in self._team_records_802(tournament_id, prepared, tpn_by_team, round_count):
                    handle.write(line)

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
    def _tiebreak_codes_212(is_team: bool) -> list[str]:
        """Códigos FIDE da ordem de desempate efetivamente usada pelo projeto.

        Espelha a ordenação fixa de `pairing/tiebreaks.py` (não há configuração
        de critérios no projeto): individual = pontos, Buchholz, Buchholz mediano,
        Sonneborn-Berger, vitórias; equipes = pontos, Buchholz (base match points),
        vitórias. Fallbacks por rating/nome não são tie-breaks FIDE e ficam de fora.
        """
        if is_team:
            return ["PTS", "BH:MP", "WIN"]
        return ["PTS", "BH", "BH/M1", "SB", "WIN"]

    @staticmethod
    def _scoring_system_362(settings: dict[str, Any]) -> str | None:
        """Registro 362 só quando os pontos de match divergem do padrão FIDE
        (TW=2.0, TD=1.0, TL=0.0). Caso contrário não emite (omissão = padrão)."""
        win = float(settings.get("team_match_win_points", 2.0) or 0.0)
        draw = float(settings.get("team_match_draw_points", 1.0) or 0.0)
        loss = float(settings.get("team_match_loss_points", 0.0) or 0.0)
        if (win, draw, loss) == (2.0, 1.0, 0.0):
            return None
        return record_362([("TW", win), ("TD", draw), ("TL", loss)])

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

    def _forfeit_records_330(
        self,
        tournament_id: int,
        tpn_by_team: dict[int, int],
    ) -> list[str]:
        """Registros 330 — matches de equipe forfeitados (W.O. do match inteiro).

        O projeto só marca W.O. por tabuleiro, então inferimos de forma
        conservadora: só é um 330 quando *todos* os tabuleiros do match são W.O.
        e a direção é consistente. As cores invertem nos tabuleiros pares, então
        os pontos são atribuídos por paridade. Forfeit parcial/misto é ignorado
        — emiti-lo enganaria o árbitro."""
        lines: list[str] = []
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            if match.get("is_bye"):
                continue
            boards = self.db.list_team_boards(int(match["id"]))
            results = [str(board.get("result") or "") for board in boards]
            if not results or any(result not in _FORFEIT_RESULTS for result in results):
                continue

            white_points = black_points = 0.0
            for board in boards:
                white_pts, black_pts = RESULT_POINTS[str(board["result"])]
                if int(board.get("board_number") or 0) % 2 == 1:
                    white_points += white_pts
                    black_points += black_pts
                else:
                    white_points += black_pts
                    black_points += white_pts

            if white_points == 0 and black_points == 0:
                match_type = "--"
            elif white_points > 0 and black_points == 0:
                match_type = "+-"
            elif black_points > 0 and white_points == 0:
                match_type = "-+"
            else:
                continue

            white_tpn = tpn_by_team.get(int(match.get("white_team_id") or 0))
            black_tpn = tpn_by_team.get(int(match.get("black_team_id") or 0))
            if not white_tpn or not black_tpn:
                continue
            lines.append(
                record_330(match_type, int(match.get("round_number") or 0), white_tpn, black_tpn)
            )
        return lines

    def _team_records_802(
        self,
        tournament_id: int,
        prepared: list[dict[str, Any]],
        tpn_by_team: dict[int, int],
        round_count: int,
    ) -> list[str]:
        """Registros 802 (informativos): por equipe, o resumo rodada-a-rodada
        (oponente/cor/game points). Forfeit fica vazio — o modelo não distingue
        W.O. de equipe de um resultado normal."""
        if not prepared:
            return []
        matches_by_round: dict[int, list[dict[str, Any]]] = {}
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            matches_by_round.setdefault(int(match.get("round_number") or 0), []).append(match)

        lines: list[str] = []
        for pairing_number, item in enumerate(prepared, start=1):
            team_id = item["team_id"]
            rounds: list[tuple[str, str, float | None, str]] = []
            for round_number in range(1, round_count + 1):
                opponent, colour, game_points = "", "", None
                for match in matches_by_round.get(round_number, []):
                    white = int(match.get("white_team_id") or 0)
                    black = int(match.get("black_team_id") or 0)
                    if match.get("is_bye") and white == team_id:
                        opponent = "PAB"
                        game_points = float(match.get("white_game_points") or 0.0)
                        break
                    if white == team_id:
                        opponent = str(tpn_by_team.get(black, ""))
                        colour = "w"
                        game_points = float(match.get("white_game_points") or 0.0)
                        break
                    if black == team_id:
                        opponent = str(tpn_by_team.get(white, ""))
                        colour = "b"
                        game_points = float(match.get("black_game_points") or 0.0)
                        break
                rounds.append((opponent, colour, game_points, ""))
            lines.append(
                record_802(
                    team_pairing_number=pairing_number,
                    nickname=self._team_nickname(item["team"]),
                    match_points=item["match_points"],
                    game_points=item["game_points"],
                    rounds=rounds,
                )
            )
        return lines

    @staticmethod
    def _team_nickname(team: dict[str, Any]) -> str:
        letters = "".join(ch for ch in str(team.get("name") or "") if ch.isalnum())
        return letters[:5].upper()
