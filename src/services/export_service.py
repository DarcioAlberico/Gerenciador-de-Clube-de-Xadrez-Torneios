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

# ImportService e CertificateService foram extraidos para modulos proprios
# (import_service.py / certificate_service.py). Reexportados aqui para
# preservar a API publica historica deste modulo:
#     from src.services.export_service import ImportService, CertificateService
from src.services.certificate_service import CertificateService
from src.services.import_service import (
    REGISTRATION_FORM_QUESTIONS,
    REGISTRATION_IMPORT_FIELDS,
    ImportService,
)

from src.services.export_players import PlayerRoundReportsMixin
from src.services.export_federation import FederationReportsMixin
from src.services.export_club import ClubReportsMixin
from src.services.export_web import WebExportMixin
from src.services.export_sections import ReportSectionsMixin
from src.services.export_renderers import ReportRenderersMixin
from src.services.export_writers import ReportWritersMixin

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


class ExportService(
    PlayerRoundReportsMixin,
    FederationReportsMixin,
    ClubReportsMixin,
    WebExportMixin,
    ReportSectionsMixin,
    ReportRenderersMixin,
    ReportWritersMixin,
):
    def __init__(self, db: Database, pairing_service: PairingService) -> None:
        self.db = db
        self.pairing_service = pairing_service
