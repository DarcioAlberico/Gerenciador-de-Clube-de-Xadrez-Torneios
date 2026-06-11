from __future__ import annotations

from pathlib import Path
from typing import Any

from src.services.constants import AppError, FINAL_RESULTS, RESULT_POINTS, player_pairing_name
from src.services.federation_exporters.base import FederationExportFormat


class TRF16Exporter:
    format = FederationExportFormat(
        code="trf16",
        label="Chess-Results/TRF16",
        extension="trf",
    )

    def __init__(self, export_service: Any) -> None:
        self.export_service = export_service
        self.db = export_service.db

    def export(self, tournament_id: int, file_path: str | Path) -> list[str]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        warnings = self.validate(tournament_id)
        players = sorted(
            self.db.list_players(tournament_id, active_only=False),
            key=lambda player: (
                -self.export_service._trf_rating(player),
                player_pairing_name(player).casefold(),
                int(player.get("id") or 0),
            ),
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
        round_count = max(
            [int(round_data["number"]) for round_data in rounds],
            default=0,
        )
        teams = self.db.list_teams(tournament_id, active_only=False) if is_team_tournament else []

        path = Path(file_path)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(self.export_service._trf_tournament_line("012", tournament["name"]))
            handle.write(self.export_service._trf_tournament_line("022", tournament.get("location", "")))
            handle.write(self.export_service._trf_tournament_line("032", settings.get("federation", "")))
            handle.write(
                self.export_service._trf_tournament_line(
                    "042",
                    self.export_service._trf_date(tournament.get("start_date"), long_year=True),
                )
            )
            handle.write(
                self.export_service._trf_tournament_line(
                    "052",
                    self.export_service._trf_date(tournament.get("end_date"), long_year=True),
                )
            )
            handle.write(self.export_service._trf_tournament_line("062", str(len(players))))
            rated_count = sum(1 for player in players if self.export_service._trf_rating(player) > 0)
            handle.write(self.export_service._trf_tournament_line("072", str(rated_count)))
            handle.write(self.export_service._trf_tournament_line("082", str(len(teams))))
            handle.write(
                self.export_service._trf_tournament_line(
                    "092",
                    self.export_service._trf_tournament_type(tournament, settings),
                )
            )
            handle.write(
                self.export_service._trf_tournament_line(
                    "102",
                    self.export_service._trf_chief_arbiter(tournament_id, settings),
                )
            )
            for deputy in self.export_service._trf_deputy_arbiters(tournament_id, settings):
                handle.write(self.export_service._trf_tournament_line("112", deputy))
            handle.write(self.export_service._trf_tournament_line("122", tournament.get("time_control", "")))
            handle.write(self.export_service._trf_tournament_line("142", str(tournament.get("rounds_count") or round_count)))
            handle.write(self.export_service._trf_round_dates_line(round_count, schedule))

            for player in players:
                handle.write(
                    self.export_service._trf_player_line(
                        player,
                        player_id_to_start_rank,
                        standings_by_player,
                        pairings_by_round,
                        round_count,
                        settings,
                    )
                )
            for team in teams:
                handle.write(self.export_service._trf_team_line(team, player_id_to_start_rank))

        return warnings

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
        if result in {"1-0", "0-1", "1/2-1/2"}:
            summary["played"] += 1
        elif result in {"1F-0F", "0F-1F"}:
            summary["forfeits"] += 1
        elif result == "0F-0F":
            summary["double_absences"] += 1
        elif not result or result not in FINAL_RESULTS or result not in RESULT_POINTS:
            summary["pending"] += 1
