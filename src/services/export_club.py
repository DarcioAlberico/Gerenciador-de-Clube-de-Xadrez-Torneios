from __future__ import annotations
import csv
import html
import io
import json
import logging
import math
import re
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.services.access_export import access_driver_available, write_accdb, write_csv_bundle
from src.services.constants import *
from src.services.fide_norms import build_norm_report
from src.services.fide_rating import build_fide_report_rows
from src.services.list_layouts import STANDINGS_COLUMNS, resolve_column_specs, resolve_columns
from src.services.prizes import PRIZE_KINDS, PRIZE_POLICIES, allocate_prizes
from src.services.trf_import import build_trf_rounds, parse_trf

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


class ClubReportsMixin:
    def export_member_evolution(self, member_id: int, file_path: str | Path) -> None:
        sections = self._member_evolution_sections(member_id)
        self._write_multi_report(file_path, sections)

    def export_club_report(self, file_path: str | Path) -> None:
        sections = self._club_report_sections()
        self._write_multi_report(file_path, sections)

    def export_member_report(self, member_id: int, file_path: str | Path) -> None:
        sections = self._member_evolution_sections(member_id)
        self._write_multi_report(file_path, sections)

    def export_tournaments_period_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._tournaments_period_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_attendance_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._attendance_report_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_financial_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._financial_report_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_events_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._events_report_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_internal_ranking_report(
        self,
        file_path: str | Path,
        category: str = "",
        club_id: int | None = None,
        class_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._internal_ranking_sections(
            category,
            club_id=club_id,
            class_id=class_id,
            start_date=start_date,
            end_date=end_date,
        )
        self._write_multi_report(file_path, sections)

    def export_payment_receipt(self, payment_id: int, file_path: str | Path) -> Path:
        payment = self.db.get_payment(payment_id)
        if not payment:
            raise AppError("Lancamento financeiro nao encontrado.")
        finance_service = __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db)
        payment = finance_service._with_effective_status(payment)
        if payment["effective_status"] not in {"paid", "exempt"}:
            raise AppError("Recibo disponivel apenas para lancamentos pagos ou isentos.")

        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            # Para CSV/Excel continua usando o padrão genérico
            rows = [
                ["Recibo", f"REC-{int(payment['id']):06d}"],
                ["Membro", payment.get("member_name") or ""],
                ["Plano", payment.get("plan_name") or ""],
                ["Descricao", payment.get("description") or ""],
                ["Referencia", payment.get("reference_period") or ""],
                ["Valor", self._format_report_number(payment.get("amount") or 0.0)],
                ["Pagamento", payment.get("payment_date") or ""],
            ]
            self._write_report(path, "Recibo financeiro", ["Campo", "Valor"], rows)
            return path
            
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            
            c = canvas.Canvas(str(path), pagesize=A4)
            c.setFont("Helvetica-Bold", 18)
            c.drawString(50, 800, "RECIBO DE PAGAMENTO")
            
            c.setFont("Helvetica-Bold", 12)
            c.drawString(400, 800, f"N. REC-{int(payment['id']):06d}")
            
            c.setFont("Helvetica", 12)
            c.drawString(50, 750, f"Recebemos de: {payment.get('member_name') or 'N/A'}")
            
            amount = float(payment.get("amount") or 0.0)
            c.drawString(50, 720, f"A quantia de: R$ {amount:,.2f}")
            c.drawString(50, 690, f"Referente a: {payment.get('description') or ''} - Ref: {payment.get('reference_period') or ''}")
            
            c.drawString(50, 660, f"Data do Pagamento: {payment.get('payment_date') or ''}")
            
            c.drawString(50, 600, "Por ser verdade, firmamos o presente recibo.")
            
            c.line(50, 520, 300, 520)
            c.drawString(50, 500, "Assinatura do Tesoureiro / Diretoria")
            c.drawString(50, 480, "Clube de Xadrez Albericus")
            
            c.save()
            return path
        except ImportError as exc:
            raise AppError("Instale reportlab para gerar Recibos em PDF (pip install reportlab).") from exc

    def export_administrative_package(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._administrative_package_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_club_portal(
        self,
        output_dir: str | Path,
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> Path:
        club, class_data = self._club_portal_scope(club_id, class_id)
        resolved_club_id = int(club["id"]) if club else None
        resolved_class_id = int(class_data["id"]) if class_data else None
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        html_content = self._club_portal_html(
            club=club,
            class_data=class_data,
            members=self.db.list_members(active_only=True, club_id=resolved_club_id, class_id=resolved_class_id),
            classes=[class_data]
            if class_data
            else self.db.list_classes(club_id=resolved_club_id, active_only=True),
            events=self.db.list_club_events(
                start_date=date.today().isoformat(),
                club_id=resolved_club_id,
                include_canceled=False,
            )[:10],
            sessions=self.db.list_training_sessions(
                start_date=date.today().isoformat(),
                club_id=resolved_club_id,
                class_id=resolved_class_id,
            )[:10],
            tournaments=[
                tournament
                for tournament in self.db.list_tournaments()
                if self._portal_tournament_in_scope(tournament, resolved_club_id, resolved_class_id)
            ][:8],
            ranking=__import__('src.services.rating_service', fromlist=['InternalRatingService']).InternalRatingService(self.db).ranking(
                active_only=True,
                club_id=resolved_club_id,
                class_id=resolved_class_id,
            )[:10],
        )
        (path / "index.html").write_text(html_content, encoding="utf-8")
        (path / "styles.css").write_text(self._club_portal_css(), encoding="utf-8")
        logger.info("Portal estatico do clube exportado em %s", path)
        return path / "index.html"
