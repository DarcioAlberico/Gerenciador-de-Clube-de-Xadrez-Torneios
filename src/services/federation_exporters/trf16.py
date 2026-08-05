from __future__ import annotations

from pathlib import Path
from typing import Any

from src.services.constants import AppError, FINAL_RESULTS, RESULT_POINTS, player_pairing_name
from src.services.starting_rank import order_players
from src.services.results_registry import is_played_result
from src.services.federation_exporters.base import FederationExportFormat
from src.services.federation_exporters.trf16_records import (
    duplicate_fide_ids,
    initial_color,
    pending_result_cells,
    reciprocity_errors,
    record_xxc,
    record_xxe,
    record_xxr,
    submission_message,
)
from src.services.federation_exporters.trf25_records import record_250
from src.services.pairing.acceleration import (
    acceleration_spec,
    scheme_emits_250,
    upper_share_size,
)


class TRF16Exporter:
    format = FederationExportFormat(
        code="trf16",
        label="Chess-Results/TRF16",
        extension="trf",
    )

    def __init__(self, export_service: Any) -> None:
        self.export_service = export_service
        self.db = export_service.db

    def export(
        self,
        tournament_id: int,
        file_path: str | Path,
        *,
        submission: bool = False,
    ) -> list[str]:
        """Gera o TRF16. `submission=True` recusa arquivo com pendencia critica.

        No modo normal o arquivo sai com avisos — e o que o arbitro usa durante o
        evento. No modo submissao ele NAO sai: resultado pendente, FIDE ID
        repetido ou mesa que nao confere entre as duas linhas 001 viram uma lista
        de pendencias, porque a federacao recusaria o arquivo depois do envio
        (FED-03).
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        warnings = self.validate(tournament_id)
        # A ordem do SNo e a MESMA que o motor de pareamento usa: fonte unica em
        # `services/starting_rank.py`. Antes cada um montava a sua, ambas pelo
        # rating FIDE, e a ordem inicial declarada no torneio nao valia em
        # lugar nenhum.
        players = order_players(
            self.db.list_players(tournament_id, active_only=False),
            settings.get("initial_order"),
            fide_rating=self.export_service._trf_rating,
        )
        rounds = sorted(self.db.list_rounds(tournament_id), key=lambda round_data: round_data["number"])
        schedule = {
            int(item["round_number"]): str(item.get("date") or "").strip()
            for item in self.db.list_round_schedule(tournament_id)
        }
        is_team_tournament = tournament.get("competition_type") == "team"
        pairings_by_round = self.export_service._trf_pairings_by_round(tournament, rounds)
        player_id_to_start_rank = {int(player["id"]): index for index, player in enumerate(players, start=1)}
        standings_by_player = self.export_service._trf_player_standings(tournament, players)
        # Dois numeros DIFERENTES, e de proposito (FED-03):
        #  - `round_count` (celulas de rodada) = o que JA ACONTECEU. Emitir
        #    celula de rodada futura faz o motor FIDE tratar o jogador como ja
        #    resolvido naquela rodada e nao parear ninguem;
        #  - `declared_rounds` (142/XXR e o calendario de datas) = o total do
        #    TORNEIO, que e o que o motor precisa saber para, por exemplo,
        #    reconhecer a ultima rodada.
        # O TRF25 usava o total configurado tambem nas celulas — era essa a
        # divergencia entre os dois arquivos do mesmo torneio.
        round_count = max([int(round_data["number"]) for round_data in rounds], default=0)
        declared_rounds = max(int(tournament.get("rounds_count") or 0), round_count)
        teams = self.db.list_teams(tournament_id, active_only=False) if is_team_tournament else []

        service = self.export_service
        linha = service._trf_tournament_line
        linhas: list[str] = [
            linha("012", tournament["name"]),
            linha("022", tournament.get("location", "")),
            linha("032", settings.get("federation", "")),
            linha("042", service._trf_date(tournament.get("start_date"), long_year=True)),
            linha("052", service._trf_date(tournament.get("end_date"), long_year=True)),
            linha("062", str(len(players))),
            linha("072", str(sum(1 for player in players if service._trf_rating(player) > 0))),
        ]
        # `082` e o numero de EQUIPES: em torneio individual saia "082 0", que
        # descreve um torneio por equipes com zero equipes (FED-03).
        if is_team_tournament:
            linhas.append(linha("082", str(len(teams))))
        linhas.append(linha("092", service._trf_tournament_type(tournament, settings)))
        evento = record_xxe(settings.get("fide_event_id"))
        if evento:
            linhas.append(f"{evento}\r\n")
        linhas.append(linha("102", service._trf_chief_arbiter_text(tournament_id, settings)))
        linhas.extend(
            linha("112", deputy)
            for deputy in service._trf_deputy_arbiter_texts(tournament_id, settings)
        )
        linhas.append(linha("122", tournament.get("time_control", "")))
        linhas.append(linha("142", str(declared_rounds)))
        # Extensoes do dialeto TRF16 (FED-03): quem le TRF16 espera `XXR`, e nao
        # o `142`, que e registro TRF25.
        linhas.append(f"{record_xxr(declared_rounds)}\r\n")
        linhas.append(
            f"{record_xxc(initial_color(pairings_by_round.get(1, []), player_id_to_start_rank))}\r\n"
        )
        aceleracao = self._acceleration_record_250(players, settings)
        if aceleracao:
            linhas.append(aceleracao)
        linhas.append(service._trf_round_dates_line(declared_rounds, schedule))
        linhas.extend(
            service._trf_player_line(
                player,
                player_id_to_start_rank,
                standings_by_player,
                pairings_by_round,
                round_count,
                settings,
            )
            for player in players
        )
        linhas.extend(
            service._trf_team_line(team, player_id_to_start_rank) for team in teams
        )

        conteudo = "".join(linhas)
        problemas = self._file_problems(conteudo, players)
        if submission and problemas:
            raise AppError(submission_message(problemas))
        warnings = [*warnings, *problemas]

        Path(file_path).write_text(conteudo, encoding="utf-8", newline="")
        return warnings

    @staticmethod
    def _file_problems(content: str, players: list[dict[str, Any]]) -> list[str]:
        """Pendencias que so o ARQUIVO PRONTO revela (FED-03).

        Reciprocidade entre as duas linhas 001 de cada mesa, resultado pendente e
        FIDE ID repetido: as tres coisas que fazem a federacao recusar a
        submissao depois do envio.
        """
        linhas = content.splitlines()
        return [
            *reciprocity_errors(linhas),
            *pending_result_cells(linhas),
            *duplicate_fide_ids(players),
        ]

    @staticmethod
    def _acceleration_record_250(
        players: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> str | None:
        """Registro 250 — aceleracao de pareamento, individual (§5.1).

        Emite so para esquemas que somam bonus de verdade (classico/custom). O
        spec vem da coluna `acceleration_method`: `bonus` por jogador nas rodadas
        `1..round_count`, aplicado ao topo `upper_fraction` do campo — exatamente
        o que o motor aplica em `pairing/acceleration.py`.

        Fica aqui, e nao so no TRF25, porque e o registro que a implementacao de
        referencia LE (o `XXA` do dialeto TRF16 quebra o parser dela — ver
        `trf16_records`). Baku fica de fora: sem a formula oficial nao se emite
        250 nem sufixo `_BAKU`, para nunca enganar o arbitro.
        """
        method = str(settings.get("acceleration_method") or "none")
        if not scheme_emits_250(method):
            return None
        spec = acceleration_spec(method)
        upper = upper_share_size(len(players), spec.get("upper_fraction", 0.5))
        round_count = int(spec.get("round_count", 0) or 0)
        bonus = float(spec.get("bonus", 0.0) or 0.0)
        if upper <= 0 or round_count <= 0 or bonus <= 0:
            return None
        return record_250(0.0, bonus, 1, round_count, [1, upper])

    def validate(self, tournament_id: int) -> list[str]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        rounds = self.db.list_rounds(tournament_id)
        warnings: list[str] = []

        if not players:
            raise AppError("Cadastre jogadores antes de exportar para Chess-Results/TRF16.")
        if not str(tournament.get("name") or "").strip():
            raise AppError("Informe o nome do torneio antes de exportar para Chess-Results/TRF16.")
        if tournament.get("competition_type") == "team" and not self.db.list_teams(tournament_id, active_only=False):
            raise AppError("Cadastre equipes antes de exportar um TRF16 por equipes.")

        required_tournament_fields = [
            ("location", "cidade/local"),
            ("start_date", "data de inicio"),
            ("end_date", "data de termino"),
            ("time_control", "ritmo de jogo"),
        ]
        for field, label in required_tournament_fields:
            if not str(tournament.get(field) or "").strip():
                warnings.append(f"Torneio sem {label}.")
        if not str(settings.get("federation") or "").strip():
            warnings.append("Torneio sem federacao FIDE.")
        elif not self.export_service._trf_valid_federation_code(settings.get("federation")):
            warnings.append("Federacao FIDE do torneio deve ter 3 letras.")
        if str(settings.get("tournament_profile") or "").strip() == "fide" and not str(
            settings.get("fide_event_id") or ""
        ).strip():
            warnings.append("Torneio FIDE-rated sem FIDE Event-ID.")
        if not self.export_service._trf_chief_arbiter(tournament_id, settings):
            warnings.append("Torneio sem arbitro-chefe.")
        if not rounds:
            warnings.append("Torneio sem rodadas geradas; jogadores serao exportados sem resultados.")
        open_rounds = [
            str(round_data["number"])
            for round_data in rounds
            if str(round_data.get("status") or "") != "closed"
        ]
        if open_rounds:
            warnings.append(f"Rodadas ainda nao fechadas: {', '.join(open_rounds)}.")
        pending_rounds = self.export_service._trf_pending_result_rounds(tournament, rounds)
        if pending_rounds:
            warnings.append(f"Rodadas com resultados pendentes/incompletos: {', '.join(pending_rounds)}.")

        warnings.extend(self._result_status_warnings(tournament_id, tournament, rounds))

        schedule = {
            int(item["round_number"]): str(item.get("date") or "").strip()
            for item in self.db.list_round_schedule(tournament_id)
        }
        rounds_count = int(tournament.get("rounds_count") or 0)
        missing_round_dates = [
            str(round_number)
            for round_number in range(1, rounds_count + 1)
            if not schedule.get(round_number)
        ]
        if missing_round_dates:
            warnings.append(f"Rodadas sem data no calendario: {', '.join(missing_round_dates)}.")
        invalid_round_dates = [
            str(round_number)
            for round_number, date_value in schedule.items()
            if date_value and not self.export_service._trf_date_is_valid(date_value)
        ]
        if invalid_round_dates:
            warnings.append(f"Rodadas com data invalida no calendario: {', '.join(invalid_round_dates)}.")
        for field, label in [("start_date", "data de inicio"), ("end_date", "data de termino")]:
            date_value = str(tournament.get(field) or "").strip()
            if date_value and not self.export_service._trf_date_is_valid(date_value):
                warnings.append(f"Torneio com {label} invalida.")

        missing_fide = []
        missing_birth = []
        missing_federation = []
        missing_rating = []
        invalid_fide = []
        invalid_birth = []
        invalid_federation = []
        for player in players:
            name = player_pairing_name(player)
            if not str(player.get("fide_id") or "").strip():
                missing_fide.append(name)
            elif not str(player.get("fide_id") or "").strip().isdigit():
                invalid_fide.append(name)
            if not str(player.get("birth_date") or "").strip():
                missing_birth.append(name)
            elif not self.export_service._trf_date_is_valid(player.get("birth_date")):
                invalid_birth.append(name)
            if not str(player.get("federation_id") or settings.get("federation") or "").strip():
                missing_federation.append(name)
            elif not self.export_service._trf_valid_federation_code(
                player.get("federation_id") or settings.get("federation")
            ):
                invalid_federation.append(name)
            if self.export_service._trf_rating(player) <= 0:
                missing_rating.append(name)

        warnings.extend(self.export_service._trf_missing_field_warnings("FIDE ID", missing_fide))
        warnings.extend(self.export_service._trf_missing_field_warnings("data de nascimento", missing_birth))
        warnings.extend(self.export_service._trf_missing_field_warnings("federacao", missing_federation))
        warnings.extend(self.export_service._trf_missing_field_warnings("rating FIDE", missing_rating))
        warnings.extend(self.export_service._trf_missing_field_warnings("FIDE ID numerico", invalid_fide))
        warnings.extend(self.export_service._trf_missing_field_warnings("data de nascimento valida", invalid_birth))
        warnings.extend(self.export_service._trf_missing_field_warnings("federacao FIDE com 3 letras", invalid_federation))
        return warnings

    def validation_report_rows(self, tournament_id: int) -> list[list[object]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        rounds = self.db.list_rounds(tournament_id)
        summary = self.result_summary(tournament_id, tournament, rounds)
        rows: list[list[object]] = [
            ["Resumo", "Partidas jogadas", summary["played"]],
            ["Resumo", "Byes", summary["byes"]],
            ["Resumo", "WO", summary["forfeits"]],
            ["Resumo", "Dupla ausencia", summary["double_absences"]],
            ["Resumo", "Nao emparceirados", summary["unpaired"]],
        ]
        rows.extend(["Pendencia", warning, ""] for warning in self.validate(tournament_id))
        return rows

    def _result_status_warnings(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        rounds: list[dict[str, Any]],
    ) -> list[str]:
        summary = self.result_summary(tournament_id, tournament, rounds)
        warnings: list[str] = []
        if summary["byes"]:
            warnings.append(f"TRF16 contem {summary['byes']} bye(s).")
        if summary["forfeits"]:
            warnings.append(f"TRF16 contem {summary['forfeits']} resultado(s) por WO.")
        if summary["double_absences"]:
            warnings.append(f"TRF16 contem {summary['double_absences']} dupla(s) ausencia(s).")
        if summary["unpaired"]:
            warnings.append(f"TRF16 contem {summary['unpaired']} jogador(es) nao emparceirado(s) em rodadas geradas.")
        return warnings

    def result_summary(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        rounds: list[dict[str, Any]],
    ) -> dict[str, int]:
        summary = {
            "played": 0,
            "byes": 0,
            "forfeits": 0,
            "double_absences": 0,
            "pending": 0,
            "unpaired": 0,
        }
        if tournament.get("competition_type") == "team":
            for round_data in rounds:
                for match in self.db.list_team_matches_for_round(int(round_data["id"])):
                    if match.get("is_bye"):
                        summary["byes"] += 1
                        continue
                    for board in self.db.list_team_boards(int(match["id"])):
                        self._count_result(summary, str(board.get("result") or ""), is_bye=False)
            return summary

        active_player_ids = {
            int(player["id"])
            for player in self.db.list_players(tournament_id, active_only=True)
        }
        for round_data in rounds:
            paired_player_ids: set[int] = set()
            for pairing in self.db.get_pairings_for_round(int(round_data["id"])):
                is_bye = bool(pairing.get("is_bye"))
                white_id = int(pairing.get("white_player_id") or 0)
                black_id = int(pairing.get("black_player_id") or 0)
                if white_id:
                    paired_player_ids.add(white_id)
                if black_id:
                    paired_player_ids.add(black_id)
                self._count_result(summary, str(pairing.get("result") or ""), is_bye=is_bye)
            summary["unpaired"] += len(active_player_ids - paired_player_ids)
        return summary

    @staticmethod
    def _count_result(summary: dict[str, int], result: str, *, is_bye: bool) -> None:
        if is_bye:
            summary["byes"] += 1
            return
        # Resultado por decisao do arbitro conta como PARTIDA JOGADA (ARB-02):
        # a mesa aconteceu, so nao e ratavel. Somar com o W.O. diria ao arbitro
        # que houve uma ausencia que nao houve.
        if is_played_result(result):
            summary["played"] += 1
        elif result in {"1F-0F", "0F-1F"}:
            summary["forfeits"] += 1
        elif result == "0F-0F":
            summary["double_absences"] += 1
        elif not result or result not in FINAL_RESULTS or result not in RESULT_POINTS:
            summary["pending"] += 1
