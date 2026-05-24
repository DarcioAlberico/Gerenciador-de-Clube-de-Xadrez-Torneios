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

class DashboardService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def overview(self) -> dict[str, Any]:
        finance_summary = __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db).finance_summary()
        ranking = __import__('src.services.rating_service', fromlist=['InternalRatingService']).InternalRatingService(self.db).ranking(active_only=True)
        recent_tournaments = []
        for tournament in self.db.list_tournaments()[:5]:
            tournament_id = int(tournament["id"])
            recent_tournaments.append(
                {
                    **tournament,
                    "players_count": len(self.db.list_players(tournament_id, active_only=False)),
                    "rounds_count_generated": len(self.db.list_rounds(tournament_id)),
                }
            )
        
        # New additions for Phase 4
        active_announcements = CommunicationService(self.db).get_active_announcements()
        
        # Find defaulters (members with overdue payments)
        all_payments = self.db._fetch_all("SELECT member_id, status FROM payments WHERE status = 'open' AND due_date < ?", (self.db.now()[:10],))
        defaulters = list(set(p["member_id"] for p in all_payments))
        
        return {
            "summary": self.db.club_summary(),
            "upcoming_events": __import__('src.services.event_service', fromlist=['EventService']).EventService(self.db).upcoming_events(limit=5),
            "finance_summary": finance_summary,
            "ranking_leaders": ranking[:5],
            "recent_tournaments": recent_tournaments,
            "recent_sessions": self.db.list_training_sessions()[:5],
            "backups_count": len(self.db.list_backups()),
            "active_announcements": active_announcements,
            "defaulters_count": len(defaulters)
        }

class CommunicationService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_announcement(self, data: dict[str, Any], announcement_id: int | None = None) -> int:
        title = str(data.get("title", "")).strip()
        content = str(data.get("content", "")).strip()
        if not title or not content:
            raise ValueError("Título e conteúdo são obrigatórios para um aviso.")
        
        payload = {
            "club_id": int(data.get("club_id", 1)),
            "title": title,
            "content": content,
            "category": str(data.get("category", "general")).strip(),
            "expiration_date": str(data.get("expiration_date", "")).strip()
        }

        if announcement_id:
            self.db._update("announcements", announcement_id, {**payload, "updated_at": self.db.now()})
            return announcement_id
        return self.db._insert(
            "announcements", {**payload, "created_at": self.db.now(), "updated_at": self.db.now()}
        )

    def delete_announcement(self, announcement_id: int) -> None:
        self.db._delete("announcements", announcement_id)

    def get_active_announcements(self) -> list[dict[str, Any]]:
        now_date = self.db.now()[:10]
        return self.db._fetch_all(
            "SELECT * FROM announcements WHERE expiration_date = '' OR expiration_date >= ? ORDER BY created_at DESC",
            (now_date,)
        )

    def log_communication(self, member_id: int, subject: str, content: str = "") -> int:
        if member_id <= 0 or not subject.strip():
            raise ValueError("Membro e Assunto são obrigatórios.")
        return self.db._insert(
            "communication_logs",
            {
                "member_id": member_id,
                "subject": subject.strip(),
                "content": content.strip(),
                "sent_at": self.db.now()
            }
        )

    def list_member_communications(self, member_id: int) -> list[dict[str, Any]]:
        return self.db._fetch_all(
            "SELECT * FROM communication_logs WHERE member_id = ? ORDER BY sent_at DESC",
            (member_id,)
        )