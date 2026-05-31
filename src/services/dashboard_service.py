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

    def bulk_email_members(
        self,
        message_service: Any,
        subject: str,
        body: str,
        *,
        active_only: bool = True,
        club_id: int | None = None,
        class_id: int | None = None,
        member_type: str = "",
    ) -> dict[str, Any]:
        """Dispara o mesmo e-mail para um publico-alvo de membros e registra cada
        envio bem-sucedido em `communication_logs`.

        O publico vem de `list_members` (filtros `active_only`/`club_id`/
        `class_id`) e pode ser refinado por `member_type`. Membros sem e-mail sao
        contados em `skipped_no_email` e nunca contam como falha de envio. Devolve
        um resumo com `sent_count`, `failed_count`, `skipped_no_email`,
        `recipients_total` e a lista `failed` (motivo por destinatario)."""
        subject = (subject or "").strip()
        body = (body or "").strip()
        if not subject or not body:
            raise ValueError("Assunto e mensagem são obrigatórios.")

        members = self.db.list_members(
            active_only=active_only, club_id=club_id, class_id=class_id
        )
        member_type = (member_type or "").strip()
        recipients: list[dict[str, Any]] = []
        skipped_no_email = 0
        for member in members:
            if member_type and str(member.get("member_type") or "") != member_type:
                continue
            email = str(member.get("email") or "").strip()
            if not email:
                skipped_no_email += 1
                continue
            recipients.append(
                {"member_id": int(member["id"]), "email": email, "name": member.get("name", "")}
            )

        if not recipients:
            return {
                "sent_count": 0,
                "failed_count": 0,
                "skipped_no_email": skipped_no_email,
                "recipients_total": 0,
                "failed": [],
            }

        result = message_service.send_bulk_email(recipients, subject, body)
        for recipient in result["sent"]:
            self.log_communication(int(recipient["member_id"]), subject, body)

        return {
            "sent_count": result["sent_count"],
            "failed_count": result["failed_count"],
            "skipped_no_email": skipped_no_email,
            "recipients_total": len(recipients),
            "failed": result["failed"],
        }

    # --- Mensagens agendadas ---------------------------------------------
    # Atencao: num desktop offline, mensagens agendadas so disparam enquanto o
    # app estiver aberto. A fila e persistida; o despacho roda na inicializacao
    # e em um tick periodico (ver app._dispatch_scheduled_messages_once).

    _AUDIENCE_KINDS = {"all_active", "class", "member_type"}

    @staticmethod
    def _normalize_schedule_datetime(value: Any) -> str:
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        raise ValueError("Data/hora invalida. Use o formato AAAA-MM-DD HH:MM.")

    def schedule_email(
        self,
        subject: str,
        body: str,
        scheduled_at: str,
        *,
        audience_kind: str = "all_active",
        audience_value: str = "",
        club_id: int | None = None,
    ) -> int:
        """Enfileira um e-mail em massa para disparo futuro. O envio em si
        acontece quando `dispatch_due_scheduled_messages` roda (na inicializacao
        e no tick periodico do app)."""
        subject = (subject or "").strip()
        body = (body or "").strip()
        if not subject or not body:
            raise ValueError("Assunto e mensagem são obrigatórios.")
        if audience_kind not in self._AUDIENCE_KINDS:
            raise ValueError("Público-alvo inválido.")
        return self.db._insert(
            "scheduled_messages",
            {
                "club_id": club_id,
                "channel": "email",
                "subject": subject,
                "body": body,
                "audience_kind": audience_kind,
                "audience_value": str(audience_value or ""),
                "scheduled_at": self._normalize_schedule_datetime(scheduled_at),
                "status": "pending",
                "created_at": self.db.now(),
            },
        )

    def list_scheduled_messages(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            return self.db._fetch_all(
                "SELECT * FROM scheduled_messages WHERE status = ? ORDER BY scheduled_at ASC",
                (status,),
            )
        return self.db._fetch_all(
            "SELECT * FROM scheduled_messages ORDER BY scheduled_at ASC"
        )

    def cancel_scheduled_message(self, message_id: int) -> None:
        self.db._update("scheduled_messages", int(message_id), {"status": "cancelled"})

    def dispatch_due_scheduled_messages(
        self, message_service: Any, now: str | None = None
    ) -> list[dict[str, Any]]:
        """Envia as mensagens pendentes cujo horario ja chegou (`scheduled_at <=
        now`). Cada mensagem e marcada como `sent` (com resumo) ou `failed` (com
        erro); uma falha numa mensagem nao impede as demais."""
        now = now or self.db.now()
        due = self.db._fetch_all(
            "SELECT * FROM scheduled_messages "
            "WHERE status = 'pending' AND scheduled_at <= ? ORDER BY scheduled_at ASC",
            (now,),
        )
        dispatched: list[dict[str, Any]] = []
        for message in due:
            kwargs: dict[str, Any] = {"active_only": True}
            kind = str(message.get("audience_kind") or "all_active")
            value = str(message.get("audience_value") or "")
            if kind == "class" and value:
                kwargs["class_id"] = int(value)
            elif kind == "member_type" and value:
                kwargs["member_type"] = value
            try:
                summary = self.bulk_email_members(
                    message_service, message["subject"], message["body"], **kwargs
                )
                self.db._update(
                    "scheduled_messages",
                    int(message["id"]),
                    {
                        "status": "sent",
                        "sent_at": self.db.now(),
                        "result_summary": (
                            f"enviados={summary['sent_count']} "
                            f"falhas={summary['failed_count']} "
                            f"sem_email={summary['skipped_no_email']}"
                        ),
                    },
                )
                dispatched.append({"id": int(message["id"]), "status": "sent", "summary": summary})
            except Exception as exc:
                self.db._update(
                    "scheduled_messages",
                    int(message["id"]),
                    {"status": "failed", "error": str(exc), "sent_at": self.db.now()},
                )
                dispatched.append({"id": int(message["id"]), "status": "failed", "error": str(exc)})
        return dispatched