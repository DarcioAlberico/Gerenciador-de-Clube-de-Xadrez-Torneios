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

class EventService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_event(self, data: dict[str, Any], event_id: int | None = None) -> int:
        payload = self._validated_event_payload(data)
        if event_id:
            if not self.db.get_club_event(event_id):
                raise AppError("Evento nao encontrado.")
            self.db.update_club_event(event_id, **payload)
            logger.info("Evento atualizado: %s", event_id)
            return event_id
        saved_id = self.db.create_club_event(**payload)
        logger.info("Evento criado: %s", saved_id)
        return saved_id

    def sync_tournament_event(self, tournament_id: int) -> int:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Torneio nao encontrado.")
        existing = self.db.get_club_event_by_tournament(tournament_id)
        data = {
            "club_id": tournament.get("club_id") or 1,
            "tournament_id": tournament_id,
            "title": tournament["name"],
            "event_type": "tournament",
            "event_date": tournament.get("start_date") or "",
            "start_time": "",
            "end_time": "",
            "location": tournament.get("location") or "",
            "status": "confirmed" if tournament.get("status") == "running" else "planned",
            "notes": f"Torneio com {tournament.get('rounds_count') or ''} rodadas.".strip(),
        }
        return self.save_event(data, int(existing["id"]) if existing else None)

    def events_report(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_optional_date(start_date, "Data inicial invalida.")
        self._validate_optional_date(end_date, "Data final invalida.")
        return self.db.list_club_events(
            start_date=start_date.strip(),
            end_date=end_date.strip(),
            club_id=club_id,
        )

    def upcoming_events(self, limit: int = 5) -> list[dict[str, Any]]:
        return self.db.list_club_events(
            start_date=date.today().isoformat(),
            include_canceled=False,
        )[:limit]

    def _validated_event_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            tournament_id = int(data.get("tournament_id") or 0)
        except ValueError as exc:
            raise AppError("Torneio vinculado invalido.") from exc
        tournament = self.db.get_tournament(tournament_id) if tournament_id else None
        if tournament_id and not tournament:
            raise AppError("Torneio vinculado nao encontrado.")

        try:
            club_id = int(data.get("club_id") or (tournament.get("club_id") if tournament else 1) or 1)
        except ValueError as exc:
            raise AppError("Clube/escola do evento invalido.") from exc
        if not self.db.get_club(club_id):
            raise AppError("Clube/escola do evento nao encontrado.")

        title = str(data.get("title", "")).strip()
        if not title and tournament:
            title = str(tournament["name"])
        if not title:
            raise AppError("Informe o titulo do evento.")

        event_type = str(data.get("event_type", "other")).strip() or "other"
        if event_type not in EVENT_TYPES:
            raise AppError("Tipo de evento invalido.")

        status = str(data.get("status", "planned")).strip() or "planned"
        if status not in EVENT_STATUSES:
            raise AppError("Status de evento invalido.")

        event_date = str(data.get("event_date", "")).strip()
        self._validate_optional_date(event_date, "Data do evento invalida.")

        return {
            "club_id": club_id,
            "tournament_id": tournament_id or None,
            "title": title,
            "event_type": event_type,
            "event_date": event_date,
            "start_time": str(data.get("start_time", "")),
            "end_time": str(data.get("end_time", "")),
            "location": str(data.get("location", "")),
            "status": status,
            "notes": str(data.get("notes", "")),
        }

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            return
        try:
            date.fromisoformat(cleaned)
        except ValueError as exc:
            raise AppError(message) from exc

class CalendarService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_event(self, data: dict[str, Any], event_id: int | None = None) -> int:
        payload = self._validated_event_payload(data)
        if event_id:
            self.db._update("calendar_events", event_id, {**payload, "updated_at": self.db.now()})
            return event_id
        return self.db._insert(
            "calendar_events", {**payload, "created_at": self.db.now(), "updated_at": self.db.now()}
        )

    def delete_event(self, event_id: int) -> None:
        self.db._delete("calendar_events", event_id)

    def list_events(self) -> list[dict[str, Any]]:
        return self.db._fetch_all("SELECT * FROM calendar_events ORDER BY date_start ASC")

    def _validated_event_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        title = str(data.get("title", "")).strip()
        date_start = str(data.get("date_start", "")).strip()
        if not title:
            raise ValueError("O título do evento é obrigatório.")
        if not date_start:
            raise ValueError("A data de início é obrigatória.")

        return {
            "club_id": int(data.get("club_id", 1)),
            "title": title,
            "date_start": date_start,
            "date_end": str(data.get("date_end", "")).strip(),
            "event_type": str(data.get("event_type", "other")).strip(),
            "location": str(data.get("location", "")).strip(),
            "description": str(data.get("description", "")).strip(),
        }

    def save_rsvp(self, data: dict[str, Any]) -> int:
        event_id = int(data.get("event_id", 0))
        member_id = int(data.get("member_id", 0))
        if event_id <= 0 or member_id <= 0:
            raise ValueError("Evento e Membro são obrigatórios para o RSVP.")
        
        status = str(data.get("status", "pending")).strip()
        notes = str(data.get("notes", "")).strip()

        existing = self.db._fetch_one(
            "SELECT id FROM event_rsvps WHERE event_id = ? AND member_id = ?",
            (event_id, member_id)
        )
        if existing:
            self.db._update("event_rsvps", existing["id"], {"status": status, "notes": notes, "updated_at": self.db.now()})
            return existing["id"]
        else:
            return self.db._insert(
                "event_rsvps",
                {
                    "event_id": event_id,
                    "member_id": member_id,
                    "status": status,
                    "notes": notes,
                    "created_at": self.db.now(),
                    "updated_at": self.db.now()
                }
            )

    def list_rsvps_for_event(self, event_id: int) -> list[dict[str, Any]]:
        return self.db._fetch_all(
            """
            SELECT r.*, m.name as member_name 
            FROM event_rsvps r
            JOIN members m ON r.member_id = m.id
            WHERE r.event_id = ?
            ORDER BY m.name ASC
            """,
            (event_id,)
        )