from __future__ import annotations

import base64
import ctypes
import logging
import os
import shutil
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .categories import competition_category_payload
from .database_certificates import CertificateMixin
from .database_club_events import ClubEventMixin
from .database_clubs import ClubMixin
from .database_education import EducationMixin
from .database_finance import FinanceMixin
from .database_guardians import GuardianMixin
from .database_inventory import InventoryMixin
from .database_learning_levels import LearningLevelMixin
from .database_referees import RefereesMixin
from .database_schema import CREATE_INDEXES_SQL, CREATE_TABLES_SQL
from .database_sync_audit import SyncAuditMixin
from .database_tournament_core import TournamentCoreMixin

logger = logging.getLogger(__name__)

DEFAULT_LEARNING_LEVELS = (
    (
        "Iniciante",
        "Conhece o tabuleiro, movimento das pecas, xeque, xeque-mate e empates basicos.",
    ),
    (
        "Basico",
        "Joga uma partida completa, conhece regras especiais, valor das pecas e mates simples.",
    ),
    (
        "Intermediario",
        "Reconhece taticas, aplica principios de abertura, finais basicos, relogio e anotacao.",
    ),
    (
        "Avancado",
        "Entende planos estrategicos, analisa partidas e conhece finais essenciais.",
    ),
    (
        "Competitivo",
        "Participa de torneios, conhece regras de competicao e representa clube ou turma.",
    ),
)

CERTIFICATE_BACKGROUND_PRESETS = (
    ("Tabuleiro sutil", "assets/certificates/backgrounds/tabuleiro_sutil.png", 0.18),
    ("Xadrez classico", "assets/certificates/backgrounds/xadrez_classico.png", 0.16),
    ("Xadrez escolar", "assets/certificates/backgrounds/xadrez_escolar.png", 0.20),
    ("Xadrez premium", "assets/certificates/backgrounds/xadrez_premium.png", 0.12),
    ("Pecas marca d'agua", "assets/certificates/backgrounds/pecas_marca_dagua.png", 0.18),
)

DEFAULT_CERTIFICATE_TEMPLATES = (
    {
        "name": "Participacao padrao",
        "certificate_type": "participation",
        "title_template": "Certificado de Participacao",
        "body_template": (
            "Certificamos que {nome} participou do torneio {torneio}, "
            "obtendo {pontos} ponto(s) e a {posicao} colocacao na classificacao."
        ),
        "footer_template": "{local} - {periodo}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Premiacao geral padrao",
        "certificate_type": "overall_award",
        "title_template": "Certificado de Premiacao",
        "body_template": (
            "Certificamos que {nome} conquistou a {posicao} colocacao geral "
            "no torneio {torneio}, com {pontos} ponto(s)."
        ),
        "footer_template": "{local} - {periodo}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Premiacao por categoria padrao",
        "certificate_type": "category_award",
        "title_template": "Certificado de Premiacao",
        "body_template": (
            "Certificamos que {nome} conquistou a {posicao_categoria} colocacao "
            "na categoria {categoria} do torneio {torneio}, com {pontos} ponto(s)."
        ),
        "footer_template": "{local} - {periodo}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Membro aluno padrao",
        "certificate_type": "member_certificate",
        "title_template": "Certificado",
        "body_template": (
            "Certificamos que {nome} integra as atividades do clube {clube}, "
            "na turma {turma}, categoria {categoria}."
        ),
        "footer_template": "{local} - {data}",
        "orientation": "landscape",
        "signature_left": "Coordenacao",
        "signature_right": "Professor / Instrutor",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Aula turma padrao",
        "certificate_type": "training_participation",
        "title_template": "Certificado de Participacao",
        "body_template": (
            "Certificamos que {nome} participou da atividade {aula}, "
            "realizada em {data}, na turma {turma}."
        ),
        "footer_template": "{clube} - {local}",
        "orientation": "landscape",
        "signature_left": "Coordenacao",
        "signature_right": "Professor / Instrutor",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Evento padrao",
        "certificate_type": "event_participation",
        "title_template": "Certificado de Participacao",
        "body_template": "Certificamos que {nome} participou do evento {evento}, realizado em {data}.",
        "footer_template": "{clube} - {local}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Coordenacao",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Ranking interno padrao",
        "certificate_type": "internal_ranking",
        "title_template": "Certificado de Destaque",
        "body_template": (
            "Certificamos que {nome} obteve a {posicao} colocacao no ranking interno, "
            "com rating {rating}."
        ),
        "footer_template": "{clube} - {data}",
        "orientation": "landscape",
        "signature_left": "Coordenacao",
        "signature_right": "Direcao",
        "logo_path": "",
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Xadrez classico - Participacao",
        "certificate_type": "participation",
        "title_template": "Certificado de Participacao",
        "body_template": (
            "Certificamos que {nome} participou do torneio {torneio}, "
            "obtendo {pontos} ponto(s) e a {posicao} colocacao na classificacao."
        ),
        "footer_template": "{local} - {periodo}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "logo_path": "",
        "background_image_path": CERTIFICATE_BACKGROUND_PRESETS[1][1],
        "background_opacity": CERTIFICATE_BACKGROUND_PRESETS[1][2],
        "primary_color": "#1E3A8A",
        "accent_color": "#C8A24A",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Xadrez escolar - Membro aluno",
        "certificate_type": "member_certificate",
        "title_template": "Certificado",
        "body_template": (
            "Certificamos que {nome} integra as atividades do clube {clube}, "
            "na turma {turma}, categoria {categoria}."
        ),
        "footer_template": "{local} - {data}",
        "orientation": "landscape",
        "signature_left": "Coordenacao",
        "signature_right": "Professor / Instrutor",
        "logo_path": "",
        "background_image_path": CERTIFICATE_BACKGROUND_PRESETS[2][1],
        "background_opacity": CERTIFICATE_BACKGROUND_PRESETS[2][2],
        "primary_color": "#0F766E",
        "accent_color": "#F59E0B",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Xadrez premium - Premiacao geral",
        "certificate_type": "overall_award",
        "title_template": "Certificado de Premiacao",
        "body_template": (
            "Certificamos que {nome} conquistou a {posicao} colocacao geral "
            "no torneio {torneio}, com {pontos} ponto(s)."
        ),
        "footer_template": "{local} - {periodo}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "logo_path": "",
        "background_image_path": CERTIFICATE_BACKGROUND_PRESETS[3][1],
        "background_opacity": CERTIFICATE_BACKGROUND_PRESETS[3][2],
        "primary_color": "#0F172A",
        "accent_color": "#B8860B",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Tabuleiro sutil - Premiacao por categoria",
        "certificate_type": "category_award",
        "title_template": "Certificado de Premiacao",
        "body_template": (
            "Certificamos que {nome} conquistou a {posicao_categoria} colocacao "
            "na categoria {categoria} do torneio {torneio}, com {pontos} ponto(s)."
        ),
        "footer_template": "{local} - {periodo}",
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "logo_path": "",
        "background_image_path": CERTIFICATE_BACKGROUND_PRESETS[0][1],
        "background_opacity": CERTIFICATE_BACKGROUND_PRESETS[0][2],
        "primary_color": "#1E3A8A",
        "accent_color": "#93C5FD",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
    {
        "name": "Pecas marca d'agua - Ranking interno",
        "certificate_type": "internal_ranking",
        "title_template": "Certificado de Destaque",
        "body_template": (
            "Certificamos que {nome} obteve a {posicao} colocacao no ranking interno, "
            "com rating {rating}."
        ),
        "footer_template": "{clube} - {data}",
        "orientation": "landscape",
        "signature_left": "Coordenacao",
        "signature_right": "Direcao",
        "logo_path": "",
        "background_image_path": CERTIFICATE_BACKGROUND_PRESETS[4][1],
        "background_opacity": CERTIFICATE_BACKGROUND_PRESETS[4][2],
        "primary_color": "#334155",
        "accent_color": "#94A3B8",
        "title_font_size": 32,
        "body_font_size": 18,
        "footer_font_size": 10,
    },
)


APP_NAME = "Albericus"
APP_DATA_DIR_ENV_VAR = "ALBERICUS_DATA_DIR"


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve_app_data_dir(
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    environment = os.environ if environ is None else environ
    override = str(environment.get(APP_DATA_DIR_ENV_VAR, "")).strip()
    if override:
        return Path(override).expanduser()

    current_platform = platform or sys.platform
    home_dir = Path.home() if home is None else Path(home)
    if current_platform.startswith("win"):
        root = str(environment.get("LOCALAPPDATA") or environment.get("APPDATA") or "").strip()
        if root:
            return Path(root) / APP_NAME
        return home_dir / "AppData" / "Local" / APP_NAME
    if current_platform == "darwin":
        return home_dir / "Library" / "Application Support" / APP_NAME

    xdg_data_home = str(environment.get("XDG_DATA_HOME", "")).strip()
    if xdg_data_home:
        return Path(xdg_data_home) / APP_NAME
    return home_dir / ".local" / "share" / APP_NAME


def app_data_dir() -> Path:
    return resolve_app_data_dir()


def default_data_dir() -> Path:
    return app_data_dir() / "data"


def default_db_path() -> Path:
    return default_data_dir() / "albericus.db"


def default_backup_dir() -> Path:
    return app_data_dir() / "backups"


def default_export_dir() -> Path:
    return app_data_dir() / "exports"


def default_logs_dir() -> Path:
    return app_data_dir() / "logs"


BASE_DIR = _base_dir()
APP_DATA_DIR = app_data_dir()
DATA_DIR = default_data_dir()
BACKUP_DIR = default_backup_dir()
EXPORTS_DIR = default_export_dir()
LOGS_DIR = default_logs_dir()
DB_PATH = default_db_path()
LEGACY_DATA_DIR = BASE_DIR / "data"
LEGACY_DB_PATH = LEGACY_DATA_DIR / "albericus.db"
LEGACY_BACKUP_DIR = BASE_DIR / "backups"
LEGACY_EXPORTS_DIR = BASE_DIR / "exports"
LEGACY_LOGS_DIR = BASE_DIR / "logs"


class Database(
    CertificateMixin,
    TournamentCoreMixin,
    SyncAuditMixin,
    EducationMixin,
    ClubMixin,
    ClubEventMixin,
    FinanceMixin,
    GuardianMixin,
    LearningLevelMixin,
    InventoryMixin,
    RefereesMixin,
):
    SCHEMA_VERSION = 41

    def __init__(
        self,
        db_path: Path | str | None = None,
        backup_dir: Path | str | None = None,
    ) -> None:
        using_default_db_path = db_path is None
        self.db_path = default_db_path() if db_path is None else Path(db_path)
        self.backup_dir = Path(backup_dir) if backup_dir else default_backup_dir()
        # Resultado da ultima copia de backup para a nuvem (pasta sincronizada).
        # Preenchido por backup(); lido pela UI/SecurityService para reportar
        # status sem repetir a copia. Inicializado antes de qualquer backup de
        # migracao disparado no __init__.
        self.last_cloud_backup: dict[str, str] | None = None
        if using_default_db_path:
            self._copy_legacy_default_database_if_needed()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self._backup_before_schema_migration_if_needed()
        self.initialize()

    def _copy_legacy_default_database_if_needed(self) -> None:
        if self.db_path.exists() or not LEGACY_DB_PATH.exists():
            return
        if self.db_path.resolve() == LEGACY_DB_PATH.resolve():
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_DB_PATH, self.db_path)
        self._copy_legacy_default_backups_if_needed()

    def _copy_legacy_default_backups_if_needed(self) -> None:
        if not LEGACY_BACKUP_DIR.exists():
            return
        if self.backup_dir.resolve() == LEGACY_BACKUP_DIR.resolve():
            return
        if self.backup_dir.exists() and any(self.backup_dir.glob(f"*{self.db_path.suffix}")):
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        for backup_path in LEGACY_BACKUP_DIR.glob(f"*{self.db_path.suffix}"):
            target_path = self.backup_dir / backup_path.name
            if not target_path.exists():
                shutil.copy2(backup_path, target_path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _create_indexes(connection: sqlite3.Connection) -> None:
        connection.executescript(CREATE_INDEXES_SQL)

    def initialize(self) -> None:
        with self.connect() as connection:
            self._ensure_supported_schema_version(connection)
            connection.executescript(CREATE_TABLES_SQL)
            from src.core.migration_engine import MigrationEngine
            MigrationEngine(self).run_migrations(connection)
            self._create_indexes(connection)

    @staticmethod
    def now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    @staticmethod
    def _schema_user_version(connection: sqlite3.Connection) -> int:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def _ensure_supported_schema_version(self, connection: sqlite3.Connection) -> None:
        current_version = self._schema_user_version(connection)
        if current_version > self.SCHEMA_VERSION:
            raise RuntimeError(
                "Banco criado por uma versao mais nova do Albericus. "
                "Atualize o aplicativo antes de abrir este arquivo."
            )

    def _backup_before_schema_migration_if_needed(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if 0 < schema_version < self.SCHEMA_VERSION:
                self.backup("before_schema_migration")
                return

            players_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'players'
                """
            ).fetchone()
            if not players_table:
                return
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(players)").fetchall()}
            club_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(clubs)").fetchall()}
            member_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(members)").fetchall()}
            tournament_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(tournaments)").fetchall()
            }
            round_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(rounds)").fetchall()}
            settings_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            required_player_columns = {
                "member_id",
                "surname",
                "given_name",
                "title",
                "sex",
                "cbx_id",
                "national_rating",
                "international_rating",
                "player_status",
                "starting_points",
                "age_category",
                "rating_category",
                "prize_tags",
                "k_factor",
                "scheveningen_group",
            }
            required_club_columns = {"kind", "active"}
            required_member_columns = {
                "surname",
                "age_category",
                "rating_category",
                "prize_tags",
                "learning_level_id",
            }
            required_tournament_columns = {"club_id", "class_id", "competition_type"}
            required_round_columns = {"pairing_engine_version", "ruleset_version", "closed_at"}
            required_settings_columns = {
                "tournament_profile",
                "team_boards_count",
                "team_match_win_points",
                "team_match_draw_points",
                "team_match_loss_points",
                "team_pairing_method",
                "team_standing_primary",
                "team_standing_secondary",
                "team_fixed_board_order",
                "team_board_order_policy",
                "team_reserve_policy",
                "team_lineup_deadline",
                "team_max_substitutions",
                "rating_fee_fide",
                "rating_fee_cbx",
                "rating_fee_lbx",
                "pairing_system",
                "acceleration_method",
                "tiebreak_sequence",
                "team_tiebreak_sequence",
                "prize_policy",
                "prize_tax_percent",
            }
            settings_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'tournament_settings'
                """
            ).fetchone()
            schedule_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'round_schedule'
                """
            ).fetchone()
            official_snapshots_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'official_rating_snapshots'
                """
            ).fetchone()
            official_players_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'official_players'
                """
            ).fetchone()
            internal_rating_history_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'internal_rating_history'
                """
            ).fetchone()
            app_settings_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'app_settings'
                """
            ).fetchone()
            audit_log_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'audit_log'
                """
            ).fetchone()
            audit_events_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'audit_events'
                """
            ).fetchone()
            pairing_snapshots_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'pairing_snapshots'
                """
            ).fetchone()
            standings_snapshots_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'standings_snapshots'
                """
            ).fetchone()
            tiebreak_components_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'tiebreak_components'
                """
            ).fetchone()
            public_tokens_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'public_tokens'
                """
            ).fetchone()
            result_submissions_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'result_submissions'
                """
            ).fetchone()
            devices_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'devices'
                """
            ).fetchone()
            sync_outbox_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'sync_outbox'
                """
            ).fetchone()
            clock_events_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'clock_events'
                """
            ).fetchone()
            classes_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'classes'
                """
            ).fetchone()
            enrollments_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'member_class_enrollments'
                """
            ).fetchone()
            guardians_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'guardians'
                """
            ).fetchone()
            member_guardians_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'member_guardians'
                """
            ).fetchone()
            learning_levels_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'learning_levels'
                """
            ).fetchone()
            training_sessions_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'training_sessions'
                """
            ).fetchone()
            training_session_columns = (
                {str(row[1]) for row in connection.execute("PRAGMA table_info(training_sessions)").fetchall()}
                if training_sessions_table
                else set()
            )
            exercise_library_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'exercise_library'
                """
            ).fetchone()
            training_lists_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'training_lists'
                """
            ).fetchone()
            training_list_exercises_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'training_list_exercises'
                """
            ).fetchone()
            exercise_attempts_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'exercise_attempts'
                """
            ).fetchone()
            attendance_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'attendance'
                """
            ).fetchone()
            membership_plans_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'membership_plans'
                """
            ).fetchone()
            payments_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'payments'
                """
            ).fetchone()
            club_events_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'club_events'
                """
            ).fetchone()
            inventory_items_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'inventory_items'
                """
            ).fetchone()
            inventory_loans_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'inventory_loans'
                """
            ).fetchone()
            inventory_maintenance_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'inventory_maintenance'
                """
            ).fetchone()
            teams_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'teams'
                """
            ).fetchone()
            team_players_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_players'
                """
            ).fetchone()
            team_matches_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_matches'
                """
            ).fetchone()
            team_boards_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_boards'
                """
            ).fetchone()
            team_lineups_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_lineups'
                """
            ).fetchone()
            team_lineup_boards_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_lineup_boards'
                """
            ).fetchone()
            team_substitution_events_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_substitution_events'
                """
            ).fetchone()
            certificate_templates_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'certificate_templates'
                """
            ).fetchone()
            certificate_issuances_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'certificate_issuances'
                """
            ).fetchone()
            certificate_template_columns = (
                {str(row[1]) for row in connection.execute("PRAGMA table_info(certificate_templates)").fetchall()}
                if certificate_templates_table
                else set()
            )
            required_certificate_template_columns = {
                "logo_path",
                "background_image_path",
                "background_opacity",
                "secondary_logo_path",
                "primary_color",
                "accent_color",
                "title_font_size",
                "body_font_size",
                "footer_font_size",
            }
            required_training_session_columns = {
                "training_list_id",
                "learning_level_id",
                "objective",
                "content",
                "homework",
            }
            if (
                not required_player_columns.issubset(columns)
                or not required_club_columns.issubset(club_columns)
                or not required_member_columns.issubset(member_columns)
                or not required_tournament_columns.issubset(tournament_columns)
                or not required_round_columns.issubset(round_columns)
                or not required_settings_columns.issubset(settings_columns)
                or not settings_table
                or not schedule_table
                or not official_snapshots_table
                or not official_players_table
                or not internal_rating_history_table
                or not app_settings_table
                or not audit_log_table
                or not audit_events_table
                or not pairing_snapshots_table
                or not standings_snapshots_table
                or not tiebreak_components_table
                or not public_tokens_table
                or not result_submissions_table
                or not devices_table
                or not sync_outbox_table
                or not clock_events_table
                or not classes_table
                or not enrollments_table
                or not guardians_table
                or not member_guardians_table
                or not learning_levels_table
                or not exercise_library_table
                or not training_lists_table
                or not training_list_exercises_table
                or not training_sessions_table
                or not attendance_table
                or not exercise_attempts_table
                or not membership_plans_table
                or not payments_table
                or not club_events_table
                or not inventory_items_table
                or not inventory_loans_table
                or not inventory_maintenance_table
                or not teams_table
                or not team_players_table
                or not team_matches_table
                or not team_boards_table
                or not team_lineups_table
                or not team_lineup_boards_table
                or not team_substitution_events_table
                or not certificate_templates_table
                or not certificate_issuances_table
                or not required_certificate_template_columns.issubset(certificate_template_columns)
                or not required_training_session_columns.issubset(training_session_columns)
            ):
                self.backup("before_schema_migration")
        finally:
            connection.close()

    def backup(self, reason: str = "manual") -> Path:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Banco nao encontrado: {self.db_path}")

        safe_reason = "".join(
            character.lower() if character.isalnum() else "_"
            for character in reason.strip()
        ).strip("_")
        safe_reason = safe_reason or "manual"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{self.db_path.stem}_{safe_reason}_{timestamp}{self.db_path.suffix}"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        source = sqlite3.connect(self.db_path)
        try:
            target = sqlite3.connect(backup_path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()

        self.last_cloud_backup = self.copy_backup_to_cloud(backup_path)
        return backup_path

    def copy_backup_to_cloud(self, backup_path: Path | str) -> dict[str, str]:
        """Copia um backup para a pasta de nuvem configurada (`cloud_sync_dir`),
        no estilo Dropbox/OneDrive/Drive desktop. Nunca levanta excecao — o
        backup local ja foi gravado, entao uma falha de nuvem e registrada e
        reportada, mas nao interrompe o fluxo. Devolve `{status, path}` com
        status em {`success`, `not_configured`, `invalid_directory`,
        `error: <msg>`}."""
        try:
            cloud_dir_str = (self.get_app_settings().get("cloud_sync_dir") or "").strip()
        except Exception:
            # Cedo no __init__ (backup de migracao) as settings podem nao existir.
            return {"status": "not_configured", "path": ""}
        if not cloud_dir_str:
            return {"status": "not_configured", "path": ""}
        cloud_dir = Path(cloud_dir_str)
        if not (cloud_dir.exists() and cloud_dir.is_dir()):
            logger.warning("Pasta de nuvem invalida para backup: %s", cloud_dir_str)
            return {"status": "invalid_directory", "path": ""}
        try:
            target = cloud_dir / Path(backup_path).name
            shutil.copy2(backup_path, target)
            return {"status": "success", "path": str(target)}
        except Exception as exc:
            logger.error("Falha ao copiar backup para nuvem %s: %s", cloud_dir_str, exc)
            return {"status": f"error: {exc}", "path": ""}

    def backup_before(
        self,
        action: str,
        tournament_id: int | None = None,
        round_id: int | None = None,
    ) -> Path:
        parts = ["before", action.strip() or "action"]
        if tournament_id is not None:
            parts.append(f"t{int(tournament_id)}")
        if round_id is not None:
            parts.append(f"r{int(round_id)}")
        backup_path = self.backup("_".join(parts))
        self.create_audit_event(
            action="backup_created",
            tournament_id=tournament_id,
            round_id=round_id,
            entity_type="backup",
            reason=f"Backup automatico antes de {action}.",
            after={"path": str(backup_path), "reason": "_".join(parts)},
        )
        return backup_path

    def list_backups(self) -> list[dict[str, Any]]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backups = []
        for path in self.backup_dir.glob(f"*{self.db_path.suffix}"):
            stat = path.stat()
            backups.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        return sorted(backups, key=lambda item: str(item["modified_at"]), reverse=True)

    def prune_backups(self, keep_count: int) -> list[Path]:
        keep = max(1, int(keep_count or 1))
        backups = self.list_backups()
        deleted: list[Path] = []
        for backup in backups[keep:]:
            path = Path(str(backup["path"]))
            if path.exists() and path.is_file() and path.suffix.lower() == self.db_path.suffix.lower():
                path.unlink()
                deleted.append(path)
        return deleted

    def restore_backup(self, backup_path: Path | str) -> Path:
        source_path = Path(backup_path).resolve()
        backup_root = self.backup_dir.resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Backup nao encontrado: {source_path}")
        if not source_path.is_file() or source_path.suffix.lower() != self.db_path.suffix.lower():
            raise ValueError("Selecione um arquivo de backup valido.")
        if source_path != backup_root and backup_root not in source_path.parents:
            raise ValueError("Por seguranca, restaure apenas arquivos da pasta de backups configurada.")

        safety_backup = self.backup("before_restore")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            source = sqlite3.connect(source_path)
            try:
                target = sqlite3.connect(self.db_path)
                try:
                    source.backup(target)
                finally:
                    target.close()
            finally:
                source.close()
            self.initialize()
        except Exception:
            shutil.copy2(safety_backup, self.db_path)
            self.initialize()
            raise
        return safety_backup

    def get_app_settings(self) -> dict[str, Any]:
        defaults = {
            "appearance_mode": "System",
            "default_export_dir": str(default_export_dir()),
            "backup_dir": str(self.backup_dir),
            "operator_name": "Administrador",
            "operator_role": "admin",
            "backup_retention_count": "10",
            "ui_scale_percent": "120",
            "arbitration_auto_refresh_enabled": "1",
            "arbitration_refresh_interval_seconds": "15",
            "arbitration_inline_tables_limit": "20",
        }
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT key, value
                FROM app_settings
                """
            ).fetchall()
            settings = defaults.copy()
            settings.update({str(row["key"]): row["value"] for row in rows})
        for secret_key in ("smtp_password", "ftp_password"):
            if secret_key in settings:
                settings[secret_key] = self._unprotect_secret(str(settings.get(secret_key) or ""))
        settings = self._normalize_legacy_app_settings(settings)
        if settings.get("backup_dir"):
            self.backup_dir = Path(str(settings["backup_dir"]))
        return settings

    @staticmethod
    def _normalize_legacy_app_settings(settings: dict[str, Any]) -> dict[str, Any]:
        normalized = settings.copy()
        if Database._same_path(str(normalized.get("default_export_dir") or ""), LEGACY_EXPORTS_DIR):
            normalized["default_export_dir"] = str(default_export_dir())
        if Database._same_path(str(normalized.get("backup_dir") or ""), LEGACY_BACKUP_DIR):
            normalized["backup_dir"] = str(default_backup_dir())
        return normalized

    @staticmethod
    def _same_path(left: str, right: Path) -> bool:
        if not left:
            return False
        try:
            return Path(left).expanduser().resolve() == right.expanduser().resolve()
        except OSError:
            return Path(left).expanduser() == right.expanduser()

    @staticmethod
    def _protect_secret(value: str) -> str:
        if not value or value.startswith("dpapi$"):
            return value
        if not sys.platform.startswith("win"):
            return value

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint), ("pbData", ctypes.POINTER(ctypes.c_char))]

        data = value.encode("utf-8")
        buffer = ctypes.create_string_buffer(data)
        in_blob = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        out_blob = DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            return value
        try:
            encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return "dpapi$" + base64.b64encode(encrypted).decode("ascii")
        finally:
            kernel32.LocalFree(out_blob.pbData)

    @staticmethod
    def _unprotect_secret(value: str) -> str:
        if not value.startswith("dpapi$"):
            return value
        if not sys.platform.startswith("win"):
            return ""

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint), ("pbData", ctypes.POINTER(ctypes.c_char))]

        try:
            encrypted = base64.b64decode(value.removeprefix("dpapi$"))
        except ValueError:
            return ""
        buffer = ctypes.create_string_buffer(encrypted)
        in_blob = DataBlob(len(encrypted), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        out_blob = DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            return ""
        try:
            decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return decrypted.decode("utf-8")
        finally:
            kernel32.LocalFree(out_blob.pbData)

    def save_app_settings(self, settings: dict[str, Any]) -> None:
        allowed_keys = {
            "appearance_mode",
            "color_theme",
            "default_export_dir",
            "backup_dir",
            "cloud_sync_dir",
            "operator_name",
            "operator_role",
            "backup_retention_count",
            "ui_scale_percent",
            "local_result_server_url",
            "sync_server_url",
            "sync_enabled",
            "local_device_id",
            "device_integrations_enabled",
            "notifications_enabled",
            "live_portal_notice",
            "live_portal_mode",
            "smtp_server",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "ftp_host",
            "ftp_port",
            "ftp_user",
            "ftp_password",
            "ftp_remote_dir",
            "ftp_use_tls",
            "ftp_passive",
            "foreign_rating_federations",
            "arbitration_auto_refresh_enabled",
            "arbitration_refresh_interval_seconds",
            "arbitration_inline_tables_limit",
        }
        secret_keys = {"smtp_password", "ftp_password"}
        now = self.now()
        rows = [
            (key, self._protect_secret(str(value)) if key in secret_keys else str(value), now)
            for key, value in settings.items()
            if key in allowed_keys
        ]
        if not rows:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        if "backup_dir" in settings:
            self.backup_dir = Path(str(settings["backup_dir"]))

    @staticmethod
    def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return self.rows_to_dicts(conn.execute(query, params).fetchall())

    def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _insert(self, table: str, values: Mapping[str, Any]) -> int:
        if not values:
            raise ValueError("Informe ao menos um campo para inserir.")
        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)
        with self.connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
            return int(cursor.lastrowid)

    def _update(self, table: str, row_id: int, values: Mapping[str, Any]) -> None:
        if not values:
            return
        columns = list(values.keys())
        assignments = ", ".join(f"{column} = ?" for column in columns)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE {table} SET {assignments} WHERE id = ?",
                [*(values[column] for column in columns), row_id],
            )

    def _delete(self, table: str, row_id: int) -> None:
        with self.connect() as conn:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    def _get_connection(self):
        return self.connect()

    def create_member_presence(
        self, member_id: int, presence_date: str, event_type: str, notes: str = ""
    ) -> int:
        with self._get_connection() as conn:
            now = self.now()
            cursor = conn.execute(
                """
                INSERT INTO member_presences (
                    member_id, presence_date, event_type, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (member_id, presence_date, event_type, notes, now, now),
            )
            return cursor.lastrowid

    def list_member_presences(self, member_id: int) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, member_id, presence_date, event_type, notes, created_at, updated_at
                FROM member_presences
                WHERE member_id = ?
                ORDER BY presence_date DESC, id DESC
                """,
                (member_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_member_presence(self, presence_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM member_presences WHERE id = ?", (presence_id,))

    def create_member_title(
        self, member_id: int, title_name: str, date_earned: str, issuer: str, notes: str = ""
    ) -> int:
        with self._get_connection() as conn:
            now = self.now()
            cursor = conn.execute(
                """
                INSERT INTO member_titles (
                    member_id, title_name, date_earned, issuer, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (member_id, title_name, date_earned, issuer, notes, now, now),
            )
            return cursor.lastrowid

    def list_member_titles(self, member_id: int) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, member_id, title_name, date_earned, issuer, notes, created_at, updated_at
                FROM member_titles
                WHERE member_id = ?
                ORDER BY date_earned DESC, id DESC
                """,
                (member_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_member_title(self, title_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM member_titles WHERE id = ?", (title_id,))

    def create_member(
        self,
        name: str,
        surname: str = "",
        club_id: int = 1,
        learning_level_id: int | None = None,
        city: str = "",
        phone: str = "",
        email: str = "",
        document: str = "",
        birth_date: str = "",
        rating: int = 0,
        category: str = "",
        member_type: str = "socio",
        status: str = "active",
        guardian_name: str = "",
        guardian_phone: str = "",
        notes: str = "",
        lichess_username: str = "",
        chesscom_username: str = "",
        online_blitz_rating: int = 0,
        online_rapid_rating: int = 0,
    ) -> int:
        club = self.get_club(int(club_id or 1))
        category_payload = competition_category_payload(
            birth_date=birth_date,
            rating=rating,
            category=category,
            city=city,
            member_type=member_type,
            tournament_club_city=club.get("city", "") if club else "",
            tournament_club_name=club.get("name", "") if club else "",
        )
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO members (
                    club_id, learning_level_id, name, surname, city, phone, email, document, birth_date, rating,
                    category, age_category, rating_category, prize_tags,
                    member_type, status, guardian_name, guardian_phone,
                    notes, lichess_username, chesscom_username, online_blitz_rating, online_rapid_rating, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(club_id or 1),
                    learning_level_id,
                    name.strip(),
                    surname.strip(),
                    city.strip(),
                    phone.strip(),
                    email.strip(),
                    document.strip(),
                    birth_date.strip(),
                    int(rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    member_type.strip(),
                    status.strip(),
                    guardian_name.strip(),
                    guardian_phone.strip(),
                    notes.strip(),
                    lichess_username.strip(),
                    chesscom_username.strip(),
                    int(online_blitz_rating or 0),
                    int(online_rapid_rating or 0),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_member(
        self,
        member_id: int,
        name: str,
        surname: str = "",
        club_id: int = 1,
        learning_level_id: int | None = None,
        city: str = "",
        phone: str = "",
        email: str = "",
        document: str = "",
        birth_date: str = "",
        rating: int = 0,
        category: str = "",
        member_type: str = "socio",
        status: str = "active",
        guardian_name: str = "",
        guardian_phone: str = "",
        notes: str = "",
        departure_date: str = "",
        departure_reason: str = "",
        transfer_notes: str = "",
        lichess_username: str = "",
        chesscom_username: str = "",
        online_blitz_rating: int = 0,
        online_rapid_rating: int = 0,
    ) -> None:
        club = self.get_club(int(club_id or 1))
        category_payload = competition_category_payload(
            birth_date=birth_date,
            rating=rating,
            category=category,
            city=city,
            member_type=member_type,
            tournament_club_city=club.get("city", "") if club else "",
            tournament_club_name=club.get("name", "") if club else "",
        )
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE members
                SET club_id = ?, learning_level_id = ?, name = ?, surname = ?, city = ?, phone = ?, email = ?, document = ?,
                    birth_date = ?, rating = ?, category = ?, age_category = ?,
                    rating_category = ?, prize_tags = ?, member_type = ?,
                    status = ?, guardian_name = ?, guardian_phone = ?,
                    notes = ?, lichess_username = ?, chesscom_username = ?, online_blitz_rating = ?, online_rapid_rating = ?, departure_date = ?, departure_reason = ?, transfer_notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(club_id or 1),
                    learning_level_id,
                    name.strip(),
                    surname.strip(),
                    city.strip(),
                    phone.strip(),
                    email.strip(),
                    document.strip(),
                    birth_date.strip(),
                    int(rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    member_type.strip(),
                    status.strip(),
                    guardian_name.strip(),
                    guardian_phone.strip(),
                    notes.strip(),
                    lichess_username.strip(),
                    chesscom_username.strip(),
                    int(online_blitz_rating or 0),
                    int(online_rapid_rating or 0),
                    departure_date.strip(),
                    departure_reason.strip(),
                    transfer_notes.strip(),
                    self.now(),
                    member_id,
                ),
            )

    def get_member(self, member_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    m.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    ll.description AS learning_level_description,
                    ll.display_order AS learning_level_order,
                    ll.active AS learning_level_active,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name,
                    (
                        SELECT COUNT(*)
                        FROM member_guardians mg
                        WHERE mg.member_id = m.id
                    ) AS guardians_count
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN learning_levels ll ON ll.id = m.learning_level_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE m.id = ?
                ORDER BY ac.updated_at DESC, ac.id DESC
                LIMIT 1
                """,
                (member_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_members(
        self,
        active_only: bool = False,
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if active_only:
            conditions.append("m.status = 'active'")
        if club_id:
            conditions.append("m.club_id = ?")
            params.append(club_id)
        if class_id:
            conditions.append("ac.class_id = ?")
            params.append(class_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    ll.display_order AS learning_level_order,
                    ll.active AS learning_level_active,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN learning_levels ll ON ll.id = m.learning_level_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                {where}
                ORDER BY
                    m.status ASC,
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_members_for_tournament(
        self,
        tournament_id: int,
        active_only: bool = True,
        include_out_of_scope: bool = False,
    ) -> list[dict[str, Any]]:
        status_filter = "AND m.status = 'active'" if active_only else ""
        with self.connect() as connection:
            tournament = connection.execute(
                "SELECT club_id, class_id FROM tournaments WHERE id = ?",
                (tournament_id,),
            ).fetchone()
            scope_filter = ""
            params: list[Any] = [tournament_id]
            if not include_out_of_scope and tournament and tournament["class_id"]:
                scope_filter = "AND ac.class_id = ?"
                params.append(int(tournament["class_id"]))
            elif not include_out_of_scope and tournament and tournament["club_id"]:
                scope_filter = "AND m.club_id = ?"
                params.append(int(tournament["club_id"]))
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
                    p.id AS registered_player_id,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name,
                    (
                        SELECT COUNT(*)
                        FROM member_guardians mg
                        WHERE mg.member_id = m.id
                    ) AS guardians_count
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                LEFT JOIN players p
                    ON p.member_id = m.id AND p.tournament_id = ?
                WHERE 1 = 1
                {status_filter}
                {scope_filter}
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_member_tournament_players(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.*,
                    t.name AS tournament_name,
                    t.location AS tournament_location,
                    t.start_date AS tournament_start_date,
                    t.end_date AS tournament_end_date,
                    t.rounds_count AS tournament_rounds_count,
                    t.status AS tournament_status,
                    t.created_at AS tournament_created_at
                FROM players p
                JOIN tournaments t ON t.id = p.tournament_id
                WHERE p.member_id = ?
                ORDER BY
                    t.start_date DESC,
                    t.created_at DESC,
                    t.id DESC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_member_tournament_results(
        self,
        member_id: int,
        tournament_id: int,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            player = connection.execute(
                """
                SELECT id
                FROM players
                WHERE member_id = ? AND tournament_id = ?
                """,
                (member_id, tournament_id),
            ).fetchone()
            if not player:
                return []

            rows = connection.execute(
                """
                SELECT
                    p.*,
                    r.number AS round_number,
                    r.status AS round_status,
                    white.name AS white_name,
                    white.surname AS white_surname,
                    white.given_name AS white_given_name,
                    white.rating AS white_rating,
                    black.name AS black_name,
                    black.surname AS black_surname,
                    black.given_name AS black_given_name,
                    black.rating AS black_rating
                FROM pairings p
                JOIN rounds r ON r.id = p.round_id
                JOIN players white ON white.id = p.white_player_id
                LEFT JOIN players black ON black.id = p.black_player_id
                WHERE r.tournament_id = ?
                    AND (p.white_player_id = ? OR p.black_player_id = ?)
                ORDER BY r.number ASC, p.board_number ASC
                """,
                (tournament_id, player["id"], player["id"]),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_member_rating_history(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    h.*,
                    t.name AS tournament_name,
                    t.start_date AS tournament_start_date,
                    p.name AS player_name
                FROM internal_rating_history h
                LEFT JOIN tournaments t ON t.id = h.tournament_id
                LEFT JOIN players p ON p.id = h.player_id
                WHERE h.member_id = ?
                ORDER BY h.created_at DESC, h.id DESC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def record_internal_rating_update(
        self,
        member_id: int,
        tournament_id: int,
        player_id: int,
        old_rating: int,
        new_rating: int,
        performance: int,
        points: float,
        games: int,
        reason: str = "tournament_performance",
    ) -> bool:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO internal_rating_history (
                    member_id, tournament_id, player_id, old_rating, new_rating,
                    performance, points, games, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_id,
                    tournament_id,
                    player_id,
                    int(old_rating or 0),
                    int(new_rating or 0),
                    int(performance or 0),
                    float(points or 0.0),
                    int(games or 0),
                    reason.strip() or "tournament_performance",
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.execute(
                """
                UPDATE members
                SET rating = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(new_rating or 0), now, member_id),
            )
            return True

    def set_member_status(self, member_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE members
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.strip(), self.now(), member_id),
            )

    def get_player_by_member(
        self,
        tournament_id: int,
        member_id: int,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM players
                WHERE tournament_id = ? AND member_id = ?
                """,
                (tournament_id, member_id),
            ).fetchone()
            return dict(row) if row else None

    def create_player_from_member(self, tournament_id: int, member_id: int) -> int:
        member = self.get_member(member_id)
        if not member:
            raise ValueError("Membro nao encontrado.")

        club = self.get_club(int(member.get("club_id") or 1))
        club_name = club["name"] if club and club["name"] else member["city"]
        given_name = str(member.get("name") or "").strip()
        surname = str(member.get("surname") or "").strip()
        tournament_name = " ".join(part for part in [given_name, surname] if part)
        return self.create_player(
            tournament_id=tournament_id,
            name=tournament_name,
            club=club_name,
            rating=int(member["rating"] or 0),
            category=member["category"],
            birth_date=member["birth_date"],
            member_id=member_id,
            surname=surname,
            given_name=given_name,
        )
