from __future__ import annotations
import csv
import html
import json
import logging
import math
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.core.database_tournament_core import default_pairing_system
from src.services.constants import *
from src.services.pairing import (
    acceleration_spec,
    parse_player_tiebreak_sequence,
    parse_team_tiebreak_sequence,
    serialize_tiebreak_sequence,
)
from src.services.pairing.constraints import rating_for_initial_order
from src.services.prizes import PRIZE_POLICIES
from src.services.rating import SPEED_CHOICES, serialize_regulation_overrides

if TYPE_CHECKING:
    from src.services.club_service import ClubService
    from src.services.member_service import MemberService, GuardianService
    from src.services.tournament_service import TournamentService, RefereeService, TeamService
    from src.services.pairing_service import PairingService
    from src.services.finance_service import FinanceService
    from src.services.event_service import EventService, CalendarService
    from src.services.education_service import TrainingService, ExerciseService, LibraryService, LearningLevelService
    from src.services.inventory_service import InventoryService
    from src.services.security_service import SecurityService
    from src.services.export_service import ExportService, ImportService, CertificateService
    from src.services.rating_service import OfficialRatingService, InternalRatingService
    from src.services.dashboard_service import DashboardService, CommunicationService

logger = logging.getLogger(__name__)

class RefereeService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_referees(self, active_only: bool = True) -> list[dict[str, Any]]:
        return self.db.list_referees(active_only)

    def create_referee(self, data: dict[str, Any]) -> int:
        if not data.get("name"):
            raise AppError("Nome do árbitro é obrigatório.")
        return self.db.insert_referee(data)

    def update_referee(self, referee_id: int, data: dict[str, Any]) -> None:
        if not data.get("name"):
            raise AppError("Nome do árbitro é obrigatório.")
        self.db.update_referee(referee_id, data)

    def toggle_referee_active(self, referee_id: int) -> None:
        referee = self.db.get_referee(referee_id)
        if not referee:
            raise AppError("Árbitro não encontrado.")
        data = dict(referee)
        data["active"] = 0 if referee["active"] else 1
        self.db.update_referee(referee_id, data)

    def list_tournament_referees(self, tournament_id: int) -> list[dict[str, Any]]:
        return self.db.list_tournament_referees(tournament_id)

    def assign_tournament_referee(self, tournament_id: int, referee_id: int, role: str) -> None:
        self.db.assign_tournament_referee(tournament_id, referee_id, role)

    def remove_tournament_referee(self, tournament_id: int, referee_id: int) -> None:
        self.db.remove_tournament_referee(tournament_id, referee_id)

class TournamentService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_tournament(self, tournament_data: dict[str, Any]) -> int:
        payload = self._validated_tournament_payload(tournament_data, {})
        tournament_id = self.db.create_tournament(**payload)
        logger.info("Torneio criado: %s", tournament_id)
        return tournament_id

    def create_tournament_from_profile(
        self,
        tournament_data: dict[str, Any],
        settings_data: dict[str, Any],
        schedule: list[dict[str, Any]],
    ) -> int:
        tournament_payload = self._validated_tournament_payload(tournament_data, {})
        settings_payload = self._validated_settings(settings_data)
        schedule_payload = self._validated_schedule(schedule, tournament_payload["rounds_count"])
        tournament_id = self.db.create_tournament(**tournament_payload)
        self.db.save_tournament_settings(tournament_id, settings_payload)
        self.db.save_round_schedule(tournament_id, schedule_payload)
        logger.info("Torneio criado a partir de modelo: %s", tournament_id)
        return tournament_id

    def duplicate_tournament(self, source_tournament_id: int, new_name: str) -> int:
        source = self.db.get_tournament(source_tournament_id)
        if not source:
            raise AppError("Selecione um torneio valido para duplicar.")
        clean_name = str(new_name or "").strip()
        if not clean_name:
            raise AppError("Informe o nome do novo torneio.")
        tournament_id = self.db.duplicate_tournament(source_tournament_id, clean_name)
        logger.info("Torneio %s duplicado como %s", source_tournament_id, tournament_id)
        return tournament_id

    def delete_tournament(self, tournament_id: int) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido para excluir.")
        self.db.delete_tournament(tournament_id)
        logger.info("Torneio excluido: %s", tournament_id)

    def save_profile(
        self,
        tournament_id: int,
        tournament_data: dict[str, Any],
        settings_data: dict[str, Any],
        schedule: list[dict[str, Any]],
    ) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        tournament_payload = self._validated_tournament_payload(tournament_data, tournament)
        generated_rounds = self.db.list_rounds(tournament_id)
        highest_generated_round = max((int(item["number"]) for item in generated_rounds), default=0)
        if int(tournament_payload["rounds_count"]) < highest_generated_round:
            raise AppError(
                f"O torneio ja possui rodadas geradas ate a rodada {highest_generated_round}. "
                "Exclua as rodadas geradas antes de reduzir o total."
            )
        self._validate_competition_type_change(
            tournament_id,
            tournament,
            tournament_payload,
            generated_rounds,
        )
        current_settings = self.db.get_tournament_settings(tournament_id) or {}
        settings_for_validation = {**current_settings, **settings_data}
        settings_payload = self._validated_settings(settings_for_validation)
        schedule_payload = self._validated_schedule(schedule, tournament_payload["rounds_count"])
        self._validate_team_settings_compatibility(tournament_id, tournament_payload, settings_payload)

        requested_method = str(settings_payload.get("pairing_method") or "").strip()
        if (
            requested_method
            and requested_method != str(current_settings.get("pairing_method", "swiss"))
            and self.db.list_rounds(tournament_id)
        ):
            raise AppError(
                "Nao e possivel mudar o metodo de pareamento depois de gerar a primeira rodada."
            )

        self.db.update_tournament_details(
            tournament_id=tournament_id,
            **tournament_payload,
        )
        self.db.save_tournament_settings(tournament_id, settings_payload)
        self.db.save_round_schedule(tournament_id, schedule_payload)
        logger.info("Configuracoes do torneio %s atualizadas", tournament_id)

    def change_tournament_type(self, tournament_id: int, pairing_method: str) -> None:
        """Muda o metodo de pareamento (RR <-> Suico <-> ...), bloqueado apos a R1."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        method = str(pairing_method or "").strip()
        if method not in PAIRING_METHODS:
            raise AppError("Metodo de pareamento invalido.")
        if self.db.list_rounds(tournament_id):
            raise AppError(
                "Nao e possivel mudar o metodo de pareamento depois de gerar a primeira rodada."
            )
        self.db.update_pairing_method(tournament_id, method)
        logger.info("Torneio %s teve o pareamento alterado para %s", tournament_id, method)

    def split_tournament(self, tournament_id: int, group_count: int) -> list[int]:
        """Divide os jogadores em N torneios-filho por ranking inicial (A=mais forte)."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            raise AppError("A divisao esta disponivel apenas para torneios individuais.")
        try:
            groups = int(group_count)
        except (TypeError, ValueError) as exc:
            raise AppError("Quantidade de grupos invalida.") from exc
        if groups < 2:
            raise AppError("Divida em pelo menos 2 grupos.")
        if self.db.list_rounds(tournament_id):
            raise AppError("Divida o torneio antes de gerar a primeira rodada.")

        players = self.db.list_players(tournament_id, active_only=False)
        if len(players) < groups:
            raise AppError("Jogadores insuficientes para a quantidade de grupos.")

        source_settings = self.db.get_tournament_settings(tournament_id) or {}
        initial_order = str(source_settings.get("initial_order") or "rating")
        ordered = sorted(
            players,
            key=lambda player: (
                -rating_for_initial_order(player, initial_order),
                str(player.get("name") or "").casefold(),
            ),
        )
        source_schedule = self.db.list_round_schedule(tournament_id)
        source_prizes = self.db.list_tournament_prizes(tournament_id)
        source_standings_layout = self.db.get_report_layout_columns(tournament_id, "standings")
        base_size, remainder = divmod(len(ordered), groups)

        child_ids: list[int] = []
        index = 0
        for group_index in range(groups):
            size = base_size + (1 if group_index < remainder else 0)
            chunk = ordered[index:index + size]
            index += size
            label = chr(ord("A") + group_index)
            child_id = self.db.create_tournament(
                name=f"{tournament['name']} - {label}",
                club_id=tournament.get("club_id"),
                location=str(tournament.get("location") or ""),
                rounds_count=int(tournament.get("rounds_count") or 5),
                time_control=str(tournament.get("time_control") or ""),
                start_date=str(tournament.get("start_date") or ""),
                end_date=str(tournament.get("end_date") or ""),
                bye_points=float(tournament.get("bye_points") or 1.0),
                class_id=tournament.get("class_id"),
                competition_type="individual",
            )
            self.db.set_tournament_parent(child_id, tournament_id)
            self.db.save_tournament_settings(child_id, source_settings)
            self.db.save_round_schedule(child_id, source_schedule)
            if source_prizes:
                self.db.replace_tournament_prizes(child_id, source_prizes)
            if source_standings_layout:
                self.db.save_report_layout(child_id, "standings", source_standings_layout)
            for player in chunk:
                self.db.create_player(
                    tournament_id=child_id,
                    name=str(player.get("name") or ""),
                    surname=str(player.get("surname") or ""),
                    given_name=str(player.get("given_name") or ""),
                    title=str(player.get("title") or ""),
                    sex=str(player.get("sex") or ""),
                    club=str(player.get("club") or ""),
                    rating=int(player.get("rating") or 0),
                    national_rating=int(player.get("national_rating") or 0),
                    international_rating=int(player.get("international_rating") or 0),
                    category=str(player.get("category") or ""),
                    federation_id=str(player.get("federation_id") or ""),
                    fide_id=str(player.get("fide_id") or ""),
                    cbx_id=str(player.get("cbx_id") or ""),
                    lbx_id=str(player.get("lbx_id") or ""),
                    birth_date=str(player.get("birth_date") or ""),
                    member_id=player.get("member_id"),
                    player_status=str(player.get("player_status") or "active"),
                    starting_points=float(player.get("starting_points") or 0.0),
                )
            child_ids.append(child_id)

        logger.info("Torneio %s dividido em %s grupos: %s", tournament_id, groups, child_ids)
        return child_ids

    def _validate_competition_type_change(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        tournament_payload: dict[str, Any],
        generated_rounds: list[dict[str, Any]],
    ) -> None:
        current_type = str(tournament.get("competition_type") or "individual")
        requested_type = str(tournament_payload.get("competition_type") or current_type)
        if requested_type == current_type:
            return
        if generated_rounds:
            raise AppError("Nao e possivel mudar o formato do torneio depois de gerar rodadas.")
        if current_type == "team" and self.db.list_teams(tournament_id, active_only=False):
            raise AppError("Nao e possivel mudar o formato do torneio enquanto houver equipes cadastradas.")

    def _validate_team_settings_compatibility(
        self,
        tournament_id: int,
        tournament_payload: dict[str, Any],
        settings_payload: dict[str, Any],
    ) -> None:
        if tournament_payload.get("competition_type") != "team":
            return
        boards_count = int(settings_payload.get("team_boards_count") or 4)
        highest_board = 0
        for team in self.db.list_teams(tournament_id, active_only=False):
            for assignment in self.db.list_team_players(int(team["id"]), active_only=False):
                if assignment.get("board_number"):
                    highest_board = max(highest_board, int(assignment["board_number"]))
        if highest_board > boards_count:
            raise AppError(
                f"Ja existe jogador escalado no tabuleiro {highest_board}. "
                f"Aumente ou mantenha a quantidade de tabuleiros por equipe."
            )

    def _validated_tournament_payload(
        self,
        data: dict[str, Any],
        tournament: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do torneio.")

        try:
            rounds_count = int(data.get("rounds_count") or 1)
        except ValueError as exc:
            raise AppError("Numero de rodadas invalido.") from exc
        if rounds_count < 1:
            raise AppError("O torneio precisa ter pelo menos uma rodada.")

        try:
            bye_points = float(str(data.get("bye_points") or "0").replace(",", "."))
        except ValueError as exc:
            raise AppError("Pontuacao do bye invalida.") from exc
        if bye_points < 0:
            raise AppError("Pontuacao do bye nao pode ser negativa.")

        start_date = self._normalize_optional_date(data.get("start_date", ""), "Data inicial invalida.")
        end_date = self._normalize_optional_date(data.get("end_date", ""), "Data final invalida.")
        if start_date and end_date and start_date > end_date:
            raise AppError("Data final nao pode ser anterior a data inicial.")

        competition_type = str(
            data.get("competition_type") or tournament.get("competition_type") or "individual"
        ).strip() or "individual"
        if competition_type not in COMPETITION_TYPES:
            raise AppError("Formato do torneio invalido.")

        _scope, club_id, class_id = self._validated_tournament_scope(data, tournament)
        return {
            "name": name,
            "club_id": club_id,
            "class_id": class_id,
            "competition_type": competition_type,
            "location": str(data.get("location", "")),
            "rounds_count": rounds_count,
            "time_control": str(data.get("time_control", "")),
            "start_date": start_date,
            "end_date": end_date,
            "bye_points": bye_points,
        }

    def _validated_tournament_scope(
        self,
        data: dict[str, Any],
        tournament: dict[str, Any],
    ) -> tuple[str, int | None, int | None]:
        scope = str(data.get("scope") or "").strip()
        if not scope:
            if data.get("class_id") or tournament.get("class_id"):
                scope = "class"
            elif "club_id" in data:
                scope = "club" if data.get("club_id") else "standalone"
            elif tournament.get("club_id"):
                scope = "club"
            else:
                scope = "standalone"
        if scope not in TOURNAMENT_SCOPES:
            raise AppError("Escopo do torneio invalido.")

        if scope == "standalone":
            return scope, None, None

        class_id: int | None = None
        class_data: dict[str, Any] | None = None
        try:
            if scope == "class":
                class_id = int(data.get("class_id") or tournament.get("class_id") or 0)
        except ValueError as exc:
            raise AppError("Turma do torneio invalida.") from exc
        if scope == "class":
            class_data = self.db.get_class(class_id or 0)
            if not class_data:
                raise AppError("Turma do torneio nao encontrada.")

        if data.get("club_id"):
            club_source = data.get("club_id")
        elif class_data:
            club_source = class_data["club_id"]
        else:
            club_source = tournament.get("club_id")
        try:
            club_id = int(club_source or 0)
        except ValueError as exc:
            raise AppError("Clube/escola do torneio invalido.") from exc
        if not club_id or not self.db.get_club(club_id):
            raise AppError("Clube/escola do torneio nao encontrado.")

        if scope == "club":
            return scope, club_id, None

        if class_data and int(class_data["club_id"]) != club_id:
            raise AppError("A turma selecionada nao pertence ao clube/escola do torneio.")
        return scope, club_id, class_id

    def _validated_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        initial_order = str(data.get("initial_order", "rating")).strip() or "rating"
        if initial_order not in INITIAL_ORDER_OPTIONS:
            raise AppError("Ordem inicial invalida.")

        tournament_type = str(data.get("tournament_type", "real")).strip() or "real"
        if tournament_type not in TOURNAMENT_TYPES:
            raise AppError("Tipo de torneio invalido.")

        tournament_profile = str(data.get("tournament_profile", "free")).strip() or "free"
        if tournament_profile not in TOURNAMENT_PROFILES:
            raise AppError("Perfil do torneio invalido.")

        pairing_system = str(data.get("pairing_system", default_pairing_system())).strip() or default_pairing_system()
        if pairing_system not in PAIRING_SYSTEMS:
            raise AppError("Sistema de emparceiramento normativo invalido.")

        pairing_method = None
        if "pairing_method" in data:
            pairing_method = str(data.get("pairing_method") or "swiss").strip() or "swiss"
            if pairing_method not in PAIRING_METHODS:
                raise AppError("Metodo de pareamento invalido.")

        acceleration_method = str(data.get("acceleration_method", "none")).strip() or "none"
        acceleration_head = acceleration_method.partition(":")[0]
        if acceleration_head not in ACCELERATION_METHODS:
            raise AppError("Metodo de aceleracao invalido.")
        if acceleration_head == "custom":
            spec = acceleration_spec(acceleration_method)
            if (
                spec.get("scheme") != "custom"
                or int(spec.get("round_count") or 0) < 1
                or float(spec.get("bonus") or 0.0) <= 0.0
                or not 0.0 < float(spec.get("upper_fraction") or 0.0) <= 1.0
            ):
                raise AppError("Metodo de aceleracao invalido.")

        try:
            late_entry_points = float(str(data.get("late_entry_points") or "0").replace(",", "."))
        except ValueError as exc:
            raise AppError("Pontos por adesao tardia invalidos.") from exc
        try:
            team_boards_count = int(data.get("team_boards_count") or 4)
        except ValueError as exc:
            raise AppError("Quantidade de tabuleiros por equipe invalida.") from exc
        if team_boards_count < 1:
            raise AppError("Use pelo menos um tabuleiro por equipe.")

        try:
            team_rating_tolerance = int(data.get("team_rating_tolerance") or 0)
        except ValueError as exc:
            raise AppError("Tolerancia de rating por equipe invalida.") from exc
        if team_rating_tolerance < 0:
            raise AppError("Tolerancia de rating por equipe nao pode ser negativa.")

        try:
            team_max_substitutions = int(data.get("team_max_substitutions") or 0)
        except ValueError as exc:
            raise AppError("Limite de substituicoes por equipe invalido.") from exc
        if team_max_substitutions < 0:
            team_max_substitutions = 0

        team_point_fields = {
            "team_match_win_points": "Pontos por vitoria da equipe invalidos.",
            "team_match_draw_points": "Pontos por empate da equipe invalidos.",
            "team_match_loss_points": "Pontos por derrota da equipe invalidos.",
        }
        team_point_defaults = {
            "team_match_win_points": "2",
            "team_match_draw_points": "1",
            "team_match_loss_points": "0",
        }
        team_points: dict[str, float] = {}
        for field, message in team_point_fields.items():
            raw_value = data.get(field)
            if raw_value in (None, ""):
                raw_value = team_point_defaults[field]
            try:
                value = float(str(raw_value).replace(",", "."))
            except ValueError as exc:
                raise AppError(message) from exc
            if value < 0:
                raise AppError(message)
            team_points[field] = value

        rating_fees: dict[str, float] = {}
        for field, label in (
            ("rating_fee_fide", "FIDE"),
            ("rating_fee_cbx", "CBX"),
            ("rating_fee_lbx", "LBX"),
        ):
            try:
                value = float(str(data.get(field) or "0").replace(",", "."))
            except ValueError as exc:
                raise AppError(f"Taxa de rating {label} invalida.") from exc
            if value < 0:
                raise AppError(f"Taxa de rating {label} nao pode ser negativa.")
            rating_fees[field] = value

        team_pairing_method = str(data.get("team_pairing_method", "swiss")).strip() or "swiss"
        if team_pairing_method not in TEAM_PAIRING_METHODS:
            raise AppError("Metodo de emparceiramento por equipes invalido.")
        team_standing_primary = str(data.get("team_standing_primary", "match_points")).strip() or "match_points"
        team_standing_secondary = str(data.get("team_standing_secondary", "game_points")).strip() or "game_points"
        if team_standing_primary not in TEAM_STANDING_CRITERIA:
            raise AppError("Criterio principal por equipes invalido.")
        if team_standing_secondary not in TEAM_STANDING_CRITERIA:
            raise AppError("Criterio secundario por equipes invalido.")
        if team_standing_primary == team_standing_secondary:
            raise AppError("Use criterios diferentes para classificacao por equipes.")

        tiebreak_sequence = serialize_tiebreak_sequence(
            parse_player_tiebreak_sequence(data.get("tiebreak_sequence"))
        )
        team_tiebreak_sequence = serialize_tiebreak_sequence(
            parse_team_tiebreak_sequence(data.get("team_tiebreak_sequence"))
        )

        rating_speed = str(data.get("rating_speed", "")).strip().lower()
        if rating_speed not in SPEED_CHOICES:
            raise AppError("Ritmo para rating invalido.")
        rating_regulation = serialize_regulation_overrides(data.get("rating_regulation"))

        prize_policy = str(data.get("prize_policy", "best_only")).strip() or "best_only"
        if prize_policy not in PRIZE_POLICIES:
            raise AppError("Politica de premiacao invalida.")
        try:
            prize_tax_percent = float(str(data.get("prize_tax_percent") or "0").replace(",", "."))
        except ValueError as exc:
            raise AppError("Imposto de premiacao invalido.") from exc
        if not 0.0 <= prize_tax_percent <= 100.0:
            raise AppError("Imposto de premiacao deve estar entre 0 e 100%.")

        payload = {
            "fide_event_id": str(data.get("fide_event_id", "")),
            "organizer": str(data.get("organizer", "")),
            "website": str(data.get("website", "")),
            "contact_email": str(data.get("contact_email", "")),
            "director": str(data.get("director", "")),
            "chief_arbiter": str(data.get("chief_arbiter", "")),
            "arbiters": str(data.get("arbiters", "")),
            "federation": str(data.get("federation", "")),
            "state": str(data.get("state", "")),
            "categories": str(data.get("categories", "")),
            "cutoff_date": str(data.get("cutoff_date", "")),
            "comments": str(data.get("comments", "")),
            "prizes": str(data.get("prizes", "")),
            "initial_order": initial_order,
            "tournament_type": tournament_type,
            "tournament_profile": tournament_profile,
            "pairing_system": pairing_system,
            "acceleration_method": acceleration_method,
            "late_entry_points": late_entry_points,
            "team_boards_count": team_boards_count,
            "team_match_win_points": team_points["team_match_win_points"],
            "team_match_draw_points": team_points["team_match_draw_points"],
            "team_match_loss_points": team_points["team_match_loss_points"],
            "team_pairing_method": team_pairing_method,
            "team_standing_primary": team_standing_primary,
            "team_standing_secondary": team_standing_secondary,
            "tiebreak_sequence": tiebreak_sequence,
            "team_tiebreak_sequence": team_tiebreak_sequence,
            "prize_policy": prize_policy,
            "prize_tax_percent": prize_tax_percent,
            "team_fixed_board_order": 1 if data.get("team_fixed_board_order", 1) else 0,
            "team_board_order_policy": str(data.get("team_board_order_policy", "fixed")).strip() or "fixed",
            "team_reserve_policy": str(data.get("team_reserve_policy", "same_team")).strip() or "same_team",
            "team_lineup_deadline": str(data.get("team_lineup_deadline", "")).strip(),
            "team_rating_tolerance": team_rating_tolerance,
            "team_max_substitutions": team_max_substitutions,
            "rating_speed": rating_speed,
            "rating_regulation": rating_regulation,
            **rating_fees,
        }
        if pairing_method is not None:
            payload["pairing_method"] = pairing_method
        for field in TOURNAMENT_FLAG_FIELDS:
            payload[field] = 1 if data.get(field) else 0
        return payload

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        TournamentService._normalize_optional_date(value, message)

    @staticmethod
    def _normalize_optional_date(value: Any, message: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return ""
        try:
            return date.fromisoformat(cleaned).isoformat()
        except ValueError:
            pass

        for separator in ("/", "-"):
            parts = cleaned.split(separator)
            if len(parts) != 3:
                continue
            day, month, year = (part.strip() for part in parts)
            if len(year) != 4:
                continue
            try:
                return date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                continue

        try:
            raise ValueError(cleaned)
        except ValueError as exc:
            raise AppError(message) from exc

    @staticmethod
    def _validated_schedule(
        schedule: list[dict[str, Any]],
        rounds_count: int,
    ) -> list[dict[str, Any]]:
        rows = []
        seen: set[int] = set()
        for item in schedule:
            try:
                round_number = int(item.get("round_number") or 0)
            except ValueError as exc:
                raise AppError("Numero de rodada invalido na agenda.") from exc
            if round_number < 1:
                raise AppError("Agenda contem rodada fora do total configurado.")
            if round_number > rounds_count:
                continue
            if round_number in seen:
                raise AppError("Agenda contem rodada repetida.")
            round_date = str(item.get("date", "")).strip()
            if round_date:
                try:
                    date.fromisoformat(round_date)
                except ValueError as exc:
                    raise AppError("Data invalida na agenda de rodadas.") from exc
            seen.add(round_number)
            rows.append(
                {
                    "round_number": round_number,
                    "date": round_date,
                    "time": str(item.get("time", "")).strip(),
                }
            )

        for round_number in range(1, rounds_count + 1):
            if round_number not in seen:
                rows.append({"round_number": round_number, "date": "", "time": ""})

        return sorted(rows, key=lambda item: item["round_number"])

    @staticmethod
    def generate_round_schedule(
        rounds_count: Any,
        start_date: Any,
        first_time: Any,
        round_duration_minutes: Any,
        break_minutes: Any,
        rounds_per_day: Any,
    ) -> list[dict[str, Any]]:
        try:
            total_rounds = int(rounds_count)
        except (TypeError, ValueError) as exc:
            raise AppError("Numero de rodadas invalido para gerar agenda.") from exc
        if total_rounds < 1:
            raise AppError("O torneio precisa ter pelo menos uma rodada para gerar agenda.")

        start_date_text = TournamentService._normalize_optional_date(
            start_date,
            "Data inicial da agenda invalida.",
        )
        if not start_date_text:
            raise AppError("Informe a data inicial da agenda.")
        start_day = date.fromisoformat(start_date_text)

        try:
            start_time = time.fromisoformat(str(first_time or "").strip())
        except ValueError as exc:
            raise AppError("Hora inicial da agenda invalida. Use HH:MM.") from exc

        try:
            duration_minutes = int(round_duration_minutes)
        except (TypeError, ValueError) as exc:
            raise AppError("Duracao da rodada invalida.") from exc
        if duration_minutes < 1:
            raise AppError("Duracao da rodada deve ser maior que zero.")

        try:
            interval_minutes = int(break_minutes)
        except (TypeError, ValueError) as exc:
            raise AppError("Intervalo entre rodadas invalido.") from exc
        if interval_minutes < 0:
            raise AppError("Intervalo entre rodadas nao pode ser negativo.")

        try:
            per_day = int(rounds_per_day)
        except (TypeError, ValueError) as exc:
            raise AppError("Rodadas por dia invalidas.") from exc
        if per_day < 1 or per_day > total_rounds:
            per_day = total_rounds

        step = timedelta(minutes=duration_minutes + interval_minutes)
        rows = []
        for index in range(total_rounds):
            day_offset = index // per_day
            slot = index % per_day
            day_start = datetime.combine(start_day + timedelta(days=day_offset), start_time)
            scheduled_at = day_start + (step * slot)
            rows.append(
                {
                    "round_number": index + 1,
                    "date": scheduled_at.date().isoformat(),
                    "time": scheduled_at.strftime("%H:%M"),
                }
            )
        return rows

class TeamService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_team(self, tournament_id: int, data: dict[str, Any]) -> int:
        self._require_team_tournament(tournament_id)
        payload = self._validated_team_payload(data)
        try:
            team_id = self.db.create_team(tournament_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Ja existe uma equipe com este nome no torneio.") from exc
        logger.info("Equipe criada no torneio %s: %s", tournament_id, team_id)
        return team_id

    def update_team(self, team_id: int, data: dict[str, Any]) -> None:
        team = self.db.get_team(team_id)
        if not team:
            raise AppError("Equipe nao encontrada.")
        self._require_team_tournament(int(team["tournament_id"]))
        payload = self._validated_team_payload(data)
        try:
            self.db.update_team(team_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Ja existe uma equipe com este nome no torneio.") from exc
        logger.info("Equipe atualizada: %s", team_id)

    def add_player(
        self,
        team_id: int,
        player_id: int,
        board_number: Any = None,
        role: str = "starter",
    ) -> int:
        team = self.db.get_team(team_id)
        if not team:
            raise AppError("Equipe nao encontrada.")
        self._require_team_tournament(int(team["tournament_id"]))

        player = self.db.get_player(player_id)
        if not player or int(player["tournament_id"]) != int(team["tournament_id"]):
            raise AppError("Jogador nao pertence ao torneio da equipe.")

        existing = self.db.get_team_player_by_player(player_id)
        if existing:
            raise AppError(f"Jogador ja esta na equipe {existing['team_name']}.")

        payload = self._validated_assignment_payload(
            int(team["tournament_id"]),
            board_number,
            role,
        )
        self._ensure_board_available(team_id, payload["board_number"])
        try:
            team_player_id = self.db.add_player_to_team(team_id, player_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Jogador ou tabuleiro ja cadastrado em uma equipe.") from exc
        logger.info("Jogador %s adicionado a equipe %s", player_id, team_id)
        return team_player_id

    def update_player_assignment(
        self,
        team_player_id: int,
        board_number: Any = None,
        role: str = "starter",
    ) -> None:
        assignment = self.db.get_team_player(team_player_id)
        if not assignment:
            raise AppError("Jogador da equipe nao encontrado.")
        self._require_team_tournament(int(assignment["tournament_id"]))
        payload = self._validated_assignment_payload(
            int(assignment["tournament_id"]),
            board_number,
            role,
        )
        self._ensure_board_available(
            int(assignment["team_id"]),
            payload["board_number"],
            ignore_team_player_id=team_player_id,
        )
        try:
            self.db.update_team_player(team_player_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Tabuleiro ja ocupado nesta equipe.") from exc
        logger.info("Escalacao da equipe atualizada: %s", team_player_id)

    def remove_player(self, team_player_id: int) -> None:
        if not self.db.get_team_player(team_player_id):
            raise AppError("Jogador da equipe nao encontrado.")
        self.db.remove_player_from_team(team_player_id)
        logger.info("Jogador removido da equipe: %s", team_player_id)

    def delete_team(self, team_id: int) -> None:
        team = self.db.get_team(team_id)
        if not team:
            raise AppError("Equipe nao encontrada.")
        if self.db.count_team_matches(team_id) > 0:
            raise AppError(
                "Equipe ja apareceu em rodadas. Para preservar o historico, desmarque Ativa e atualize a equipe."
            )
        self.db.delete_team(team_id)
        logger.info("Equipe excluida: %s", team_id)

    def validate_roster_policy(
        self,
        tournament_id: int,
        round_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Avalia escalações e substituições contra a policy do torneio (spec §6.2).

        Retorna lista de avisos não-bloqueantes:
          - board_order_broken: tabuleiro com rating maior que o anterior
            (respeitando team_rating_tolerance)
          - substitution_limit_exceeded: equipe ultrapassou team_max_substitutions

        Quando round_id é dado, filtra avisos para aquela rodada.
        """
        issues: list[dict[str, Any]] = []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        enforce_order = bool(int(settings.get("team_fixed_board_order", 1) or 0)) and (
            str(settings.get("team_board_order_policy", "fixed")) == "fixed"
        )
        tolerance = int(settings.get("team_rating_tolerance", 0) or 0)
        max_subs = int(settings.get("team_max_substitutions", 0) or 0)

        lineups = self.db.list_team_lineups(tournament_id, round_id=round_id)
        if enforce_order:
            for lineup in lineups:
                boards = self.db.list_team_lineup_boards(int(lineup["id"]))
                previous_rating: int | None = None
                previous_board: int | None = None
                for board in boards:
                    rating = int(board.get("player_rating") or 0)
                    board_number = int(board.get("board_number") or 0)
                    if previous_rating is not None and rating > previous_rating + tolerance:
                        issues.append({
                            "severity": "warning",
                            "kind": "board_order_broken",
                            "tournament_id": tournament_id,
                            "team_id": lineup.get("team_id"),
                            "team_name": lineup.get("team_name"),
                            "round_id": lineup.get("round_id"),
                            "round_number": lineup.get("round_number"),
                            "board_number": board_number,
                            "message": (
                                f"{lineup.get('team_name', 'Equipe')} R{lineup.get('round_number')}: "
                                f"tabuleiro {board_number} rating {rating} > "
                                f"tabuleiro {previous_board} ({previous_rating}) "
                                f"além da tolerância ({tolerance})."
                            ),
                        })
                    previous_rating = rating
                    previous_board = board_number

        if max_subs > 0:
            subs_by_team: dict[int, dict[str, Any]] = {}
            for event in self.db.list_team_substitution_events(tournament_id, round_id=round_id):
                team_id = int(event.get("team_id") or 0)
                bucket = subs_by_team.setdefault(team_id, {"count": 0, "team_name": None})
                bucket["count"] += 1
                bucket["team_name"] = event.get("team_name") or bucket["team_name"]
            for team_id, bucket in subs_by_team.items():
                if bucket["count"] > max_subs:
                    issues.append({
                        "severity": "warning",
                        "kind": "substitution_limit_exceeded",
                        "tournament_id": tournament_id,
                        "team_id": team_id,
                        "team_name": bucket["team_name"],
                        "round_id": None,
                        "round_number": None,
                        "message": (
                            f"{bucket['team_name'] or 'Equipe'}: "
                            f"{bucket['count']} substituição(ões) excede o limite "
                            f"de {max_subs}."
                        ),
                    })

        return issues

    def _require_team_tournament(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Esta tela exige um torneio no formato Equipes.")
        return tournament

    @staticmethod
    def _validated_team_payload(data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome da equipe.")
        return {
            "name": name,
            "club": str(data.get("club", "")),
            "captain": str(data.get("captain", "")),
            "notes": str(data.get("notes", "")),
            "active": 1 if data.get("active", 1) else 0,
        }

    def _validated_assignment_payload(
        self,
        tournament_id: int,
        board_number: Any,
        role: str,
    ) -> dict[str, Any]:
        role_value = str(role or "starter").strip() or "starter"
        if role_value not in TEAM_PLAYER_ROLES:
            raise AppError("Funcao do jogador na equipe invalida.")

        board_value: int | None = None
        if role_value == "starter":
            try:
                board_value = int(board_number or 0)
            except ValueError as exc:
                raise AppError("Numero do tabuleiro invalido.") from exc
            if board_value < 1:
                raise AppError("Informe o tabuleiro do titular.")
            settings = self.db.get_tournament_settings(tournament_id) or {}
            boards_count = int(settings.get("team_boards_count") or 4)
            if board_value > boards_count:
                raise AppError(f"O torneio esta configurado para {boards_count} tabuleiros por equipe.")

        return {
            "board_number": board_value,
            "role": role_value,
            "active": 1,
        }

    def _ensure_board_available(
        self,
        team_id: int,
        board_number: int | None,
        ignore_team_player_id: int | None = None,
    ) -> None:
        if board_number is None:
            return
        for assignment in self.db.list_team_players(team_id, active_only=False):
            if ignore_team_player_id and int(assignment["id"]) == ignore_team_player_id:
                continue
            if assignment.get("board_number") and int(assignment["board_number"]) == board_number:
                raise AppError("Ja existe jogador neste tabuleiro da equipe.")
