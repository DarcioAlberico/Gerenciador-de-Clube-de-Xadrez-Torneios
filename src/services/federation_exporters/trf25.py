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
- Fatia 6: registros 300 (out-of-order, equipes) e 299 (ajustes anormais de
  pontos, lançados manualmente). O 250 (aceleração clássica individual) é
  emitido quando `acceleration_method == "accelerated"`, espelhando o bônus
  fictício que o motor de pareamento aplica (ver `pairing/acceleration.py`).
- Fatia 7: registro 260 (proibições de pareamento individuais). O árbitro
  cadastra pares proibidos (tabela `prohibited_pairings`); o motor os honra
  unindo-os ao `played_pairs` (bloqueio absoluto já existente) e o exporter
  emite um 260 por par (ver `pairing/prohibitions.py`).

Como o layout ainda é *final draft* (não ratificado), `export()` segue
devolvendo o TRF25_SCAFFOLD_WARNING e recomendando o TRF16 para envio oficial
— para nunca enganar o árbitro.

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
- **192**: tipo de torneio codificado (obrigatório p/ pareamento). O Suíço
  Dutch é datado pela data do torneio (FIDE_DUTCH_2017/_2025; default-por-data
  quando a data é desconhecida).
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

from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.services.constants import RESULT_POINTS, AppError, player_pairing_name
from src.services.federation_exporters.base import FederationExportFormat
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.services.federation_exporters.trf25_records import (
    encode_time_control,
    record_212,
    record_250,
    record_260,
    record_299,
    record_300,
    record_310,
    record_320,
    record_330,
    record_362,
    record_802,
    tournament_line,
)
from src.services.pairing.acceleration import (
    BAKU_NOT_IMPLEMENTED,
    acceleration_spec,
    scheme_emits_250,
    scheme_is_baku,
    upper_share_size,
)


# Resultados de tabuleiro que representam W.O. (não jogado).
_FORFEIT_RESULTS = frozenset({"1F-0F", "0F-1F", "0F-0F"})


TRF25_SCAFFOLD_WARNING = (
    "TRF25: implementação incremental — o layout segue o final draft da FIDE "
    "(ainda não ratificado). Use TRF16 para envio oficial até a especificação "
    "ser finalizada."
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

            prepared = self._prepare_teams(tournament_id, teams, players, start_rank_by_player)
            tpn_by_team = {item["team_id"]: number for number, item in enumerate(prepared, start=1)}

            # Extensões TRF25 (ESPEC §1).
            handle.write(tournament_line("142", round_count))
            initial_colour = self._initial_colour_152(players, prepared, rounds, is_team)
            if initial_colour:
                handle.write(tournament_line("152", initial_colour))
            encoded_time = encode_time_control(tournament.get("time_control"))
            if encoded_time:
                handle.write(tournament_line("222", encoded_time))
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
            for line in self._team_records_310(prepared):
                handle.write(line)
            if is_team:
                pab_line = self._pab_record_320(tournament_id, tpn_by_team, round_count, settings)
                if pab_line:
                    handle.write(pab_line)
                for line in self._forfeit_records_330(tournament_id, tpn_by_team):
                    handle.write(line)
                for line in self._out_of_order_records_300(
                    tournament_id, prepared, tpn_by_team, start_rank_by_player
                ):
                    handle.write(line)
                for line in self._team_records_802(tournament_id, prepared, tpn_by_team, round_count):
                    handle.write(line)
                for line in self._prohibited_team_pairing_records_260(
                    tournament_id, tpn_by_team, round_count
                ):
                    handle.write(line)

            if not is_team:
                if scheme_is_baku(str(settings.get("acceleration_method") or "none")):
                    warnings = [*warnings, BAKU_NOT_IMPLEMENTED]
                acceleration_line = self._acceleration_record_250(players, settings)
                if acceleration_line:
                    handle.write(acceleration_line)
                for line in self._prohibited_pairing_records_260(
                    tournament_id, start_rank_by_player, round_count
                ):
                    handle.write(line)

            for line in self._point_adjustment_records_299(
                tournament_id, is_team, start_rank_by_player, tpn_by_team
            ):
                handle.write(line)

        return warnings

    @staticmethod
    def _acceleration_record_250(
        players: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> str | None:
        """Registro 250 — aceleração de pareamento, individual (§5.1).

        Emite só para esquemas que somam bônus de verdade (clássico/custom). O spec
        vem da coluna `acceleration_method`: `bonus` por jogador nas rodadas
        `1..round_count`, aplicado ao topo `upper_fraction` do campo — exatamente o
        que o motor aplica em `pairing/acceleration.py`. Match points ficam em
        branco (individual); o intervalo de jogadores é contíguo [1, topo].

        Baku fica de fora: enquanto a fórmula oficial não estiver implementada, não
        emitimos 250 nem o sufixo `_BAKU`, para nunca enganar o árbitro."""
        method = str(settings.get("acceleration_method") or "none")
        if not scheme_emits_250(method):
            return None
        spec = acceleration_spec(method)
        upper = upper_share_size(len(players), spec.get("upper_fraction", 0.5))
        round_count = int(spec.get("round_count", 0) or 0)
        bonus = float(spec.get("bonus", 0.0) or 0.0)
        # Sem topo, sem rodadas ou sem bônus efetivo → não há aceleração a declarar.
        if upper <= 0 or round_count <= 0 or bonus <= 0:
            return None
        return record_250(0.0, bonus, 1, round_count, [1, upper])

    def _prohibited_pairing_records_260(
        self,
        tournament_id: int,
        start_rank_by_player: dict[int, int],
        round_count: int,
    ) -> list[str]:
        """Registro 260 — proibições de pareamento arbitrais (§5.2), individual.

        Uma linha por par proibido (start-ranks), com o intervalo de rodadas;
        `last_round=0` na base de dados vira a última rodada do torneio. Pares
        cujos jogadores não constam do export, ou com rank repetido, são omitidos
        — nunca se emite uma proibição que o árbitro não conseguiria conferir. O
        motor honra a mesma proibição via played_pairs (ver pairing/prohibitions)."""
        prohibitions = self.db.list_prohibited_pairings(tournament_id)
        if not prohibitions:
            return []
        lines: list[str] = []
        for prohibition in prohibitions:
            rank_a = start_rank_by_player.get(int(prohibition.get("player_a_id") or 0))
            rank_b = start_rank_by_player.get(int(prohibition.get("player_b_id") or 0))
            if not rank_a or not rank_b or rank_a == rank_b:
                continue
            first_round = int(prohibition.get("first_round") or 1)
            last_round = int(prohibition.get("last_round") or 0) or round_count
            lines.append(record_260(first_round, last_round, sorted((rank_a, rank_b))))
        return lines

    def _prohibited_team_pairing_records_260(
        self,
        tournament_id: int,
        tpn_by_team: dict[int, int],
        round_count: int,
    ) -> list[str]:
        """Registro 260 — proibições arbitrais entre equipes (§5.2), por TPN.

        Espelha a versão individual usando o Team Pairing Number no lugar do
        start-rank. Proibições cujas equipes não constam do export, ou com TPN
        repetido, são omitidas — nunca se emite uma proibição que o árbitro não
        conseguiria conferir. O motor honra a mesma proibição via played_pairs
        por equipes (ver pairing/prohibitions)."""
        prohibitions = self.db.list_prohibited_team_pairings(tournament_id)
        if not prohibitions:
            return []
        lines: list[str] = []
        for prohibition in prohibitions:
            tpn_a = tpn_by_team.get(int(prohibition.get("team_a_id") or 0))
            tpn_b = tpn_by_team.get(int(prohibition.get("team_b_id") or 0))
            if not tpn_a or not tpn_b or tpn_a == tpn_b:
                continue
            first_round = int(prohibition.get("first_round") or 1)
            last_round = int(prohibition.get("last_round") or 0) or round_count
            lines.append(record_260(first_round, last_round, sorted((tpn_a, tpn_b))))
        return lines

    def _point_adjustment_records_299(
        self,
        tournament_id: int,
        is_team: bool,
        start_rank_by_player: dict[int, int],
        tpn_by_team: dict[int, int],
    ) -> list[str]:
        """Registro 299 — abnormal assignment points lançados manualmente (§7.3).

        Agrupa os ajustes por `(aat_type, match_points, game_points, round_number)`
        e mapeia cada alvo para a entidade TRF25: starting-rank (individual) ou TPN
        (equipe). Ajustes individuais não usam match points. Alvos que não puderem
        ser resolvidos (jogador/equipe ausente do export) são omitidos — nunca se
        emite uma entidade inexistente para não enganar o árbitro.
        """
        adjustments = self.db.list_point_adjustments(tournament_id)
        if not adjustments:
            return []

        grouped: dict[tuple[str, float, float, int], list[int]] = {}
        for adjustment in adjustments:
            if is_team:
                entity = tpn_by_team.get(int(adjustment.get("team_id") or 0))
                match_points = float(adjustment.get("match_points") or 0.0)
            else:
                entity = start_rank_by_player.get(int(adjustment.get("player_id") or 0))
                match_points = 0.0
            if not entity:
                continue
            key = (
                str(adjustment.get("aat_type") or ""),
                match_points,
                float(adjustment.get("game_points") or 0.0),
                int(adjustment.get("round_number") or 0),
            )
            grouped.setdefault(key, []).append(int(entity))

        lines: list[str] = []
        for (aat_type, match_points, game_points, round_number), entities in grouped.items():
            lines.append(
                record_299(aat_type, match_points, game_points, round_number, sorted(entities))
            )
        return lines

    def validate(self, tournament_id: int) -> list[str]:
        warnings = super().validate(tournament_id)
        return [TRF25_SCAFFOLD_WARNING, *warnings]

    @staticmethod
    def _team_score_code_192(settings: dict[str, Any]) -> str:
        """Código `<score>` do 192 de equipes (Anexo A): ordem dos pontos
        MP/GP usada na classificação e na alocação de cores.

        Lê `team_standing_primary`/`_secondary` na ordem configurada. Só
        match-points (MP) e game-points (GP) entram no código — `wins` é um
        critério de desempate, não um esquema de pontuação, então é ignorado.
        Sem nenhum MP/GP configurado, cai no padrão FIDE `MP_GP`."""
        tokens: list[str] = []
        for key in ("team_standing_primary", "team_standing_secondary"):
            criterion = str(settings.get(key, "")).strip().casefold()
            if criterion == "match_points":
                token = "MP"
            elif criterion == "game_points":
                token = "GP"
            else:
                continue  # 'wins' ou desconhecido não é um código de pontuação
            if token not in tokens:
                tokens.append(token)
        return "_".join(tokens) if tokens else "MP_GP"

    def _team_code_192(self, settings: dict[str, Any]) -> str:
        """Código 192 do Suíço por equipes: `FIDE_TEAM_TYPEA_<score>` (Anexo A).

        O projeto usa sempre a sequência de cores fixa WBWB… (ver 352) e não
        modela o sistema de cores TYPEB, então mantemos o default `TYPEA` do
        Anexo A. Baku fica sem o sufixo `_BAKU` enquanto a fórmula oficial não
        estiver implementada, para não enganar o árbitro."""
        return f"FIDE_TEAM_TYPEA_{self._team_score_code_192(settings)}"

    def _initial_colour_152(
        self,
        players: list[dict[str, Any]],
        prepared: list[dict[str, Any]],
        rounds: list[dict[str, Any]],
        is_team: bool,
    ) -> str | None:
        """Cor (W/B) do 1º tabuleiro do top seed na rodada 1.

        Devolve None quando não é possível determinar (sem rodada 1, top seed com
        bye, ou pareamento ausente) — o exporter então omite o 152.
        """
        first_round = next((r for r in rounds if int(r["number"]) == 1), None)
        if not first_round:
            return None
        round_id = int(first_round["id"])

        if is_team:
            if not prepared:
                return None
            top_team_id = int(prepared[0]["team_id"])
            for match in self.db.list_team_matches_for_round(round_id):
                if match.get("is_bye"):
                    continue
                if int(match.get("white_team_id") or 0) == top_team_id:
                    return "W"
                if int(match.get("black_team_id") or 0) == top_team_id:
                    return "B"
            return None

        if not players:
            return None
        top_id = int(players[0]["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            if pairing.get("is_bye"):
                continue
            if int(pairing.get("white_player_id") or 0) == top_id:
                return "W"
            if int(pairing.get("black_player_id") or 0) == top_id:
                return "B"
        return None

    def _type_code_192(self, tournament: dict[str, Any], settings: dict[str, Any]) -> str:
        if tournament.get("competition_type") == "team":
            return self._team_code_192(settings)
        method = str(settings.get("pairing_method", "swiss")).casefold()
        if method == "round_robin":
            return "FIDE_ROUNDROBIN"
        if method == "knockout":
            return "WORLDCUP_KNOCKOUT"
        return self._dutch_code_192(tournament)

    # As regras de pareamento Dutch da FIDE mudaram em 2025-07-01: torneios
    # disputados a partir dessa data usam a versão 2025; antes, a 2017 (Anexo A).
    _DUTCH_RULES_2025_CUTOFF = date(2025, 7, 1)

    @staticmethod
    def _parse_tournament_date(value: Any) -> date | None:
        raw = str(value or "").strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%d. %m. %Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    def _dutch_code_192(self, tournament: dict[str, Any]) -> str:
        """Código 192 do Suíço Dutch, datado conforme as regras vigentes.

        Usa a data do torneio (início, com fallback no fim). Sem data parseável
        devolve `FIDE_DUTCH` puro (default-por-data do Anexo A) — nunca inventamos
        a versão das regras quando a data é desconhecida. Baku continua sem o
        sufixo `_BAKU`: a fórmula oficial não está implementada, então não a
        declaramos no 192 para não enganar o árbitro."""
        event_date = (
            self._parse_tournament_date(tournament.get("start_date"))
            or self._parse_tournament_date(tournament.get("end_date"))
        )
        if event_date is None:
            return "FIDE_DUTCH"
        if event_date >= self._DUTCH_RULES_2025_CUTOFF:
            return "FIDE_DUTCH_2025"
        return "FIDE_DUTCH_2017"

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

    @staticmethod
    def _is_out_of_default_order(actual_ranks: list[int], default_order: list[int]) -> bool | None:
        """Decide se a escalação efetiva diverge da ordem padrão do 310.

        `actual_ranks` é o start-rank por tabuleiro (0 = vazio); `default_order` é
        a lista de ranks na ordem do roster (campo do 310). Considera-se OOdO
        quando os jogadores presentes não respeitam a ordem do roster entre si.
        Substituir um titular por um reserva mantendo a ordem NÃO é OOdO.

        Devolve None quando não dá para verificar com segurança (algum jogador
        escalado não consta da ordem padrão) — aí o exporter omite, para não
        afirmar ao árbitro uma OOdO que não consegue comprovar.
        """
        played = [rank for rank in actual_ranks if rank]
        try:
            positions = [default_order.index(rank) for rank in played]
        except ValueError:
            return None
        return positions != sorted(positions)

    def _out_of_order_records_300(
        self,
        tournament_id: int,
        prepared: list[dict[str, Any]],
        tpn_by_team: dict[int, int],
        start_rank_by_player: dict[int, int],
    ) -> list[str]:
        """Registros 300 — equipes que jogaram fora da ordem padrão (§7.2).

        Para cada lado de cada match fechado, monta o start-rank efetivo por
        tabuleiro (cores invertem nos pares, como no 330/352) e compara com a
        ordem do roster. Só emite quando a divergência é comprovável."""
        ranks_by_team = {item["team_id"]: item["ranks"] for item in prepared}
        lines: list[str] = []
        for match in self.db.list_team_matches_for_tournament(tournament_id, closed_only=True):
            if match.get("is_bye"):
                continue
            white_team = int(match.get("white_team_id") or 0)
            black_team = int(match.get("black_team_id") or 0)
            white_tpn = tpn_by_team.get(white_team)
            black_tpn = tpn_by_team.get(black_team)
            if not white_tpn or not black_tpn:
                continue
            boards = sorted(
                self.db.list_team_boards(int(match["id"])),
                key=lambda board: int(board.get("board_number") or 0),
            )
            round_number = int(match.get("round_number") or 0)
            for team_id, team_tpn, opponent_tpn, is_white in (
                (white_team, white_tpn, black_tpn, True),
                (black_team, black_tpn, white_tpn, False),
            ):
                actual_ranks: list[int] = []
                for board in boards:
                    odd = int(board.get("board_number") or 0) % 2 == 1
                    if is_white:
                        player_id = board.get("white_player_id") if odd else board.get("black_player_id")
                    else:
                        player_id = board.get("black_player_id") if odd else board.get("white_player_id")
                    actual_ranks.append(
                        start_rank_by_player.get(int(player_id), 0) if player_id else 0
                    )
                out_of_order = self._is_out_of_default_order(
                    actual_ranks, ranks_by_team.get(team_id, [])
                )
                if out_of_order:
                    lines.append(
                        record_300(round_number, team_tpn, opponent_tpn, actual_ranks)
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
