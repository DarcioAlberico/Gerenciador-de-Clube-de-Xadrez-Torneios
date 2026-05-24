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

class ClubService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_profile(self, data: dict[str, Any], club_id: int | None = 1) -> int:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do clube/escola.")
        kind = str(data.get("kind", "club")).strip() or "club"
        if kind not in CLUB_KINDS:
            raise AppError("Tipo de unidade invalido.")
        saved_id = self.db.save_club(
            name=name,
            kind=kind,
            city=str(data.get("city", "")),
            address=str(data.get("address", "")),
            phone=str(data.get("phone", "")),
            email=str(data.get("email", "")),
            notes=str(data.get("notes", "")),
            active=1 if data.get("active", 1) else 0,
            club_id=club_id,
        )
        logger.info("Clube/escola atualizado: %s", saved_id)
        return saved_id

    def save_class(self, data: dict[str, Any], class_id: int | None = None) -> int:
        try:
            club_id = int(data.get("club_id") or 0)
        except ValueError as exc:
            raise AppError("Clube/escola invalido para a turma.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola nao encontrado.")

        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome da turma.")

        payload: dict[str, Any] = {
            "club_id": club_id,
            "name": name,
            "teacher": str(data.get("teacher", "")),
            "weekday": str(data.get("weekday", "")),
            "time": str(data.get("time", "")),
            "location": str(data.get("location", "")),
            "active": 1 if data.get("active", 1) else 0,
            "notes": str(data.get("notes", "")),
        }
        if class_id:
            if not self.db.get_class(class_id):
                raise AppError("Turma nao encontrada.")
            self.db.update_class(class_id, **payload)
            logger.info("Turma atualizada: %s", class_id)
            return class_id
        saved_id = self.db.create_class(**payload)
        logger.info("Turma criada: %s", saved_id)
        return saved_id