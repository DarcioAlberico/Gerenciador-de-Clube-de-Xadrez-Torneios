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
from src.services.constants import *

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

class GuardianService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_guardian(self, data: dict[str, Any]) -> int:
        payload = self._validated_payload(data)
        guardian_id = self.db.create_guardian(**payload)
        logger.info("Responsavel criado: %s", guardian_id)
        return guardian_id

    def update_guardian(self, guardian_id: int, data: dict[str, Any]) -> None:
        if not self.db.get_guardian(guardian_id):
            raise AppError("Responsavel nao encontrado.")
        payload = self._validated_payload(data)
        self.db.update_guardian(guardian_id, **payload)
        logger.info("Responsavel atualizado: %s", guardian_id)

    def toggle_guardian_active(self, guardian_id: int) -> int:
        guardian = self.db.get_guardian(guardian_id)
        if not guardian:
            raise AppError("Responsavel nao encontrado.")
        next_active = 0 if guardian.get("active") else 1
        self.db.set_guardian_active(guardian_id, next_active)
        logger.info("Responsavel %s alterado para active=%s", guardian_id, next_active)
        return next_active

    def link_guardian_to_member(self, data: dict[str, Any]) -> None:
        try:
            member_id = int(data.get("member_id") or 0)
            guardian_id = int(data.get("guardian_id") or 0)
        except ValueError as exc:
            raise AppError("Membro ou responsavel invalido.") from exc

        member = self.db.get_member(member_id)
        if not member:
            raise AppError("Membro nao encontrado.")
        guardian = self.db.get_guardian(guardian_id)
        if not guardian:
            raise AppError("Responsavel nao encontrado.")
        if not guardian.get("active"):
            raise AppError("Responsavel inativo nao pode receber novo vinculo.")

        self.db.link_guardian_to_member(
            member_id=member_id,
            guardian_id=guardian_id,
            relationship=str(data.get("relationship", "")),
            primary_contact=1 if data.get("primary_contact") else 0,
            emergency_contact=1 if data.get("emergency_contact") else 0,
            notes=str(data.get("notes", "")),
        )
        logger.info("Responsavel %s vinculado ao membro %s", guardian_id, member_id)

    def unlink_guardian_from_member(self, member_id: int, guardian_id: int) -> None:
        if not self.db.get_member(member_id):
            raise AppError("Membro nao encontrado.")
        if not self.db.get_guardian(guardian_id):
            raise AppError("Responsavel nao encontrado.")
        self.db.unlink_guardian_from_member(member_id, guardian_id)
        logger.info("Responsavel %s removido do membro %s", guardian_id, member_id)

    def minor_members(self, active_only: bool = True) -> list[dict[str, Any]]:
        return [
            member
            for member in self.db.list_members(active_only=active_only)
            if self._is_minor(str(member.get("birth_date") or ""))
        ]

    def minor_members_without_guardians(self, active_only: bool = True) -> list[dict[str, Any]]:
        return [
            member
            for member in self.db.list_members_without_guardians(active_only=active_only)
            if self._is_minor(str(member.get("birth_date") or ""))
        ]

    @staticmethod
    def _validated_payload(data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do responsavel.")
        return {
            "name": name,
            "phone": str(data.get("phone", "")),
            "email": str(data.get("email", "")),
            "document": str(data.get("document", "")),
            "address": str(data.get("address", "")),
            "notes": str(data.get("notes", "")),
            "active": 1 if data.get("active", 1) else 0,
        }

    @staticmethod
    def _is_minor(birth_date: str) -> bool:
        value = birth_date.strip()
        if not value:
            return False
        try:
            born = date.fromisoformat(value)
        except ValueError:
            return False
        today = date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age < 18

class MemberService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_member(self, data: dict[str, Any]) -> int:
        payload = self._validated_payload(data)
        class_id = payload.pop("class_id", None)
        member_id = self.db.create_member(**payload)
        if class_id:
            self.db.set_member_active_class(member_id, class_id)
        logger.info("Membro criado: %s", member_id)
        return member_id

    def update_member(self, member_id: int, data: dict[str, Any]) -> None:
        if not self.db.get_member(member_id):
            raise AppError("Membro nao encontrado.")
        payload = self._validated_payload(data)
        class_id = payload.pop("class_id", None)
        self.db.update_member(member_id, **payload)
        self.db.set_member_active_class(member_id, class_id)
        logger.info("Membro atualizado: %s", member_id)

    def toggle_member_status(self, member_id: int) -> str:
        member = self.db.get_member(member_id)
        if not member:
            raise AppError("Membro nao encontrado.")
        next_status = "inactive" if member["status"] == "active" else "active"
        self.db.set_member_status(member_id, next_status)
        logger.info("Status do membro %s alterado para %s", member_id, next_status)
        return next_status

    def deactivate_member(self, member_id: int, reason: str, date: str, notes: str = "") -> None:
        member = self.db.get_member(member_id)
        if not member:
            raise AppError("Membro nao encontrado.")
        
        self.db.update_member(
            member_id=member_id,
            name=member["name"],
            surname=member["surname"],
            club_id=member["club_id"],
            learning_level_id=member["learning_level_id"],
            city=member["city"],
            phone=member["phone"],
            email=member["email"],
            document=member["document"],
            birth_date=member["birth_date"],
            rating=member["rating"],
            category=member["category"],
            member_type=member["member_type"],
            status="inactive",
            guardian_name=member["guardian_name"],
            guardian_phone=member["guardian_phone"],
            notes=member["notes"],
            departure_date=date,
            departure_reason=reason,
            transfer_notes=notes,
        )
        logger.info("Membro desativado: %s (Motivo: %s)", member_id, reason)

    def register_presence(self, member_id: int, presence_date: str, event_type: str, notes: str = "") -> int:
        return self.db.create_member_presence(member_id, presence_date, event_type, notes)

    def list_presences(self, member_id: int) -> list[dict[str, Any]]:
        return self.db.list_member_presences(member_id)

    def remove_presence(self, presence_id: int) -> None:
        self.db.delete_member_presence(presence_id)

    def add_title(self, member_id: int, title_name: str, date_earned: str, issuer: str, notes: str = "") -> int:
        return self.db.create_member_title(member_id, title_name, date_earned, issuer, notes)

    def list_titles(self, member_id: int) -> list[dict[str, Any]]:
        return self.db.list_member_titles(member_id)

    def remove_title(self, title_id: int) -> None:
        self.db.delete_member_title(title_id)

    def register_member_in_tournament(
        self,
        tournament_id: int,
        member_id: int,
        allow_out_of_scope: bool = False,
    ) -> int:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        member = self.db.get_member(member_id)
        if not member:
            raise AppError("Membro nao encontrado.")
        if member["status"] != "active":
            raise AppError("Somente membros ativos podem ser inscritos.")

        if not allow_out_of_scope:
            eligible_ids = {
                int(item["id"])
                for item in self.db.list_members_for_tournament(tournament_id, active_only=True)
            }
            if member_id not in eligible_ids:
                scope = self._tournament_scope_label(tournament)
                raise AppError(f"Membro fora do escopo do torneio ({scope}).")

        existing = self.db.get_player_by_member(tournament_id, member_id)
        if existing:
            raise AppError("Este membro ja esta inscrito no torneio.")

        player_id = self.db.create_player_from_member(tournament_id, member_id)
        logger.info(
            "Membro %s inscrito no torneio %s como jogador %s",
            member_id,
            tournament_id,
            player_id,
        )
        return player_id

    @staticmethod
    def _tournament_scope_label(tournament: dict[str, Any]) -> str:
        if tournament.get("class_id"):
            return TOURNAMENT_SCOPES["class"]
        if tournament.get("club_id"):
            return TOURNAMENT_SCOPES["club"]
        return TOURNAMENT_SCOPES["standalone"]

    def register_active_members_in_tournament(
        self,
        tournament_id: int,
        include_out_of_scope: bool = False,
    ) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        registered_player_ids = []
        skipped = 0
        for member in self.db.list_members_for_tournament(
            tournament_id,
            active_only=True,
            include_out_of_scope=include_out_of_scope,
        ):
            if member["registered_player_id"]:
                skipped += 1
                continue
            registered_player_ids.append(
                self.db.create_player_from_member(tournament_id, int(member["id"]))
            )

        logger.info(
            "%s membros ativos inscritos no torneio %s; %s ja estavam inscritos",
            len(registered_player_ids),
            tournament_id,
            skipped,
        )
        return {
            "registered": len(registered_player_ids),
            "skipped": skipped,
            "player_ids": registered_player_ids,
        }

    def tournament_history(self, member_id: int) -> list[dict[str, Any]]:
        if not self.db.get_member(member_id):
            raise AppError("Membro nao encontrado.")

        pairing_service = __import__('src.services.pairing_service', fromlist=['PairingService']).PairingService(self.db)
        history = []
        for registration in self.db.list_member_tournament_players(member_id):
            tournament_id = int(registration["tournament_id"])
            standing = next(
                (
                    item
                    for item in pairing_service.standings(tournament_id)
                    if int(item["player_id"]) == int(registration["id"])
                ),
                None,
            )
            results = self.tournament_results(member_id, tournament_id)
            closed_results = [
                result
                for result in results
                if result["round_status"] == "closed" and result["outcome"] != "Pendente"
            ]

            history.append(
                {
                    "tournament_id": tournament_id,
                    "player_id": registration["id"],
                    "name": registration["tournament_name"],
                    "status": registration["tournament_status"],
                    "start_date": registration["tournament_start_date"],
                    "player_rating": int(registration.get("rating") or 0),
                    "player_status": registration.get("player_status", ""),
                    "points": standing["points"] if standing else 0.0,
                    "position": standing["position"] if standing else "",
                    "performance": standing["performance"] if standing else "",
                    "rounds_played": len(closed_results),
                    "wins": self._count_outcomes(closed_results, "Vitoria"),
                    "draws": self._count_outcomes(closed_results, "Empate"),
                    "losses": self._count_outcomes(closed_results, "Derrota"),
                    "byes": self._count_outcomes(closed_results, "Bye"),
                    "last_result": closed_results[-1]["outcome"] if closed_results else "",
                }
            )
        return history

    def tournament_results(self, member_id: int, tournament_id: int) -> list[dict[str, Any]]:
        if not self.db.get_member(member_id):
            raise AppError("Membro nao encontrado.")
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        player = self.db.get_player_by_member(tournament_id, member_id)
        if not player:
            return []

        rows = self.db.list_member_tournament_results(member_id, tournament_id)
        if not rows:
            return []

        member_player_id = int(player["id"])
        bye_points = float(tournament["bye_points"])
        results = []
        for row in rows:
            is_white = int(row["white_player_id"]) == member_player_id
            is_bye = bool(row["is_bye"])
            opponent = "BYE"
            color = "Bye"
            points: float | None = None

            if is_bye:
                points = bye_points
            elif is_white:
                color = "Brancas"
                opponent = player_full_name(
                    {
                        "name": row.get("black_name"),
                        "surname": row.get("black_surname"),
                        "given_name": row.get("black_given_name"),
                    }
                )
                points = self._points_for_result(row["result"], white=True)
            else:
                color = "Pretas"
                opponent = player_full_name(
                    {
                        "name": row.get("white_name"),
                        "surname": row.get("white_surname"),
                        "given_name": row.get("white_given_name"),
                    }
                )
                points = self._points_for_result(row["result"], white=False)

            results.append(
                {
                    "round_number": row["round_number"],
                    "round_status": row["round_status"],
                    "board_number": row["board_number"],
                    "color": color,
                    "opponent": opponent,
                    "result": "BYE" if is_bye else row["result"],
                    "points": points,
                    "outcome": self._outcome_label(row["result"], points, is_bye),
                }
            )
        return results

    @staticmethod
    def _points_for_result(result: str, white: bool) -> float | None:
        if result not in RESULT_POINTS:
            return None
        white_points, black_points = RESULT_POINTS[result]
        return white_points if white else black_points

    @staticmethod
    def _outcome_label(result: str, points: float | None, is_bye: bool) -> str:
        if is_bye:
            return "Bye"
        if result == "0F-0F":
            return "Duplo WO"
        if points is None:
            return "Pendente"
        if points == 1.0:
            return "Vitoria"
        if points == 0.5:
            return "Empate"
        return "Derrota"

    @staticmethod
    def _count_outcomes(results: list[dict[str, Any]], outcome: str) -> int:
        return sum(1 for result in results if result["outcome"] == outcome)

    def _validated_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do membro.")

        member_type = str(data.get("member_type", "socio")).strip() or "socio"
        if member_type not in MEMBER_TYPES:
            raise AppError("Tipo de vinculo invalido.")

        status = str(data.get("status", "active")).strip() or "active"
        if status not in MEMBER_STATUSES:
            raise AppError("Status de membro invalido.")

        try:
            rating = int(data.get("rating") or 0)
        except ValueError as exc:
            raise AppError("Rating do membro invalido.") from exc
        try:
            club_id = int(data.get("club_id") or 1)
        except ValueError as exc:
            raise AppError("Clube/escola do membro invalido.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola do membro nao encontrado.")
        try:
            class_id = int(data.get("class_id") or 0)
        except ValueError as exc:
            raise AppError("Turma do membro invalida.") from exc
        if class_id:
            class_data = self.db.get_class(class_id)
            if not class_data or int(class_data["club_id"]) != club_id:
                raise AppError("Turma nao pertence ao clube/escola selecionado.")
        try:
            learning_level_id = int(data.get("learning_level_id") or 0)
        except ValueError as exc:
            raise AppError("Nivel de aprendizagem invalido.") from exc
        if learning_level_id and not self.db.get_learning_level(learning_level_id):
            raise AppError("Nivel de aprendizagem nao encontrado.")

        try:
            online_blitz_rating = int(data.get("online_blitz_rating") or 0)
        except ValueError:
            online_blitz_rating = 0
        try:
            online_rapid_rating = int(data.get("online_rapid_rating") or 0)
        except ValueError:
            online_rapid_rating = 0

        return {
            "name": name,
            "surname": str(data.get("surname", "")),
            "club_id": club_id,
            "learning_level_id": learning_level_id or None,
            "city": str(data.get("city", "")),
            "phone": str(data.get("phone", "")),
            "email": str(data.get("email", "")),
            "document": str(data.get("document", "")),
            "birth_date": str(data.get("birth_date", "")),
            "rating": rating,
            "category": str(data.get("category", "")),
            "member_type": member_type,
            "status": status,
            "guardian_name": str(data.get("guardian_name", "")),
            "guardian_phone": str(data.get("guardian_phone", "")),
            "notes": str(data.get("notes", "")),
            "class_id": class_id or None,
            "lichess_username": str(data.get("lichess_username", "")),
            "chesscom_username": str(data.get("chesscom_username", "")),
            "online_blitz_rating": online_blitz_rating,
            "online_rapid_rating": online_rapid_rating,
        }