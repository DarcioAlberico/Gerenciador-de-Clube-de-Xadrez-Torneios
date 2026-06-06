from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .categories import competition_category_payload, reference_year
from .database_certificates import CertificateMixin
from .database_club_events import ClubEventMixin
from .database_clubs import ClubMixin
from .database_finance import FinanceMixin
from .database_guardians import GuardianMixin
from .database_inventory import InventoryMixin
from .database_learning_levels import LearningLevelMixin
from .database_referees import RefereesMixin
from .database_schema import CREATE_INDEXES_SQL, CREATE_TABLES_SQL

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

    def create_audit_log(
        self,
        action: str,
        actor: str = "",
        role: str = "",
        entity_type: str = "",
        entity_id: int | None = None,
        description: str = "",
        metadata_json: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_log (
                    actor, role, action, entity_type, entity_id, description,
                    metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor.strip(),
                    role.strip(),
                    action.strip(),
                    entity_type.strip(),
                    entity_id,
                    description.strip(),
                    metadata_json.strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_audit_logs(
        self,
        limit: int = 200,
        action: str = "",
        entity_type: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if action:
            conditions.append("action = ?")
            params.append(action.strip())
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type.strip())
        if start_date:
            conditions.append("created_at >= ?")
            params.append(f"{start_date.strip()} 00:00:00")
        if end_date:
            conditions.append("created_at <= ?")
            params.append(f"{end_date.strip()} 23:59:59")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM audit_log
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    @staticmethod
    def _canonical_json(data: Mapping[str, Any] | list[Any] | None) -> str:
        return json.dumps(data or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _hash_payload(cls, data: Mapping[str, Any] | list[Any] | str | None) -> str:
        if isinstance(data, str):
            payload = data
        else:
            payload = cls._canonical_json(data)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _operator_context(self) -> tuple[str, str]:
        settings = self.get_app_settings()
        actor = str(settings.get("operator_name") or "").strip()
        role = str(settings.get("operator_role") or "").strip()
        return actor, role

    def ensure_local_device(self, name: str = "") -> dict[str, Any]:
        settings = self.get_app_settings()
        device_id = str(settings.get("local_device_id") or "").strip()
        if not device_id:
            seed = f"{self.db_path.resolve()}:{self.now()}:{datetime.now().timestamp()}"
            device_id = "dev_" + self._hash_payload(seed)[:24]
            self.save_app_settings({"local_device_id": device_id})
        device_name = name.strip() or str(settings.get("operator_name") or "").strip() or "Desktop local"
        return self.register_device(device_id=device_id, name=device_name, role="desktop", status="authorized")

    def register_device(
        self,
        device_id: str,
        name: str,
        role: str = "assistant",
        status: str = "authorized",
        secret: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_device_id = device_id.strip()
        if not safe_device_id:
            raise ValueError("device_id obrigatorio")
        safe_status = status.strip() or "authorized"
        safe_role = role.strip() or "assistant"
        now = self.now()
        secret_hash = self._hash_payload(secret) if secret else ""
        metadata_json = self._canonical_json(metadata)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO devices (
                    device_id, name, role, status, secret_hash, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name = excluded.name,
                    role = excluded.role,
                    status = excluded.status,
                    secret_hash = CASE
                        WHEN excluded.secret_hash != '' THEN excluded.secret_hash
                        ELSE devices.secret_hash
                    END,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    safe_device_id,
                    name.strip() or safe_device_id,
                    safe_role,
                    safe_status,
                    secret_hash,
                    metadata_json,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM devices WHERE device_id = ?", (safe_device_id,)).fetchone()
            return dict(row)

    def list_devices(self, status: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if status:
            where = "WHERE status = ?"
            params.append(status.strip())
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM devices
                {where}
                ORDER BY status, name
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_device_status(self, device_id: str, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE devices
                SET status = ?, updated_at = ?
                WHERE device_id = ?
                """,
                (status.strip(), self.now(), device_id.strip()),
            )

    def create_sync_outbox_event(
        self,
        action: str,
        payload: Mapping[str, Any] | list[Any],
        tournament_id: int | None = None,
        round_id: int | None = None,
        entity_type: str = "",
        entity_id: int | None = None,
        device_id: str = "",
        conflict_policy: str = "server_authoritative",
        status: str = "pending",
    ) -> int:
        local_device = self.ensure_local_device()
        resolved_device_id = device_id.strip() or str(local_device["device_id"])
        payload_json = self._canonical_json(payload)
        now = self.now()
        event_seed = self._canonical_json(
            {
                "device_id": resolved_device_id,
                "action": action,
                "tournament_id": tournament_id,
                "round_id": round_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload_hash": self._hash_payload(payload_json),
                "created_at": now,
            }
        )
        event_id = self._hash_payload(f"{event_seed}:{datetime.now().timestamp()}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sync_outbox (
                    event_id, device_id, tournament_id, round_id, entity_type,
                    entity_id, action, payload_json, payload_hash, conflict_policy,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    resolved_device_id,
                    tournament_id,
                    round_id,
                    entity_type.strip(),
                    entity_id,
                    action.strip(),
                    payload_json,
                    self._hash_payload(payload_json),
                    conflict_policy.strip() or "server_authoritative",
                    status.strip() or "pending",
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_sync_outbox(self, status: str = "pending", limit: int = 200) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status.strip())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM sync_outbox
                {where}
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def mark_sync_outbox_synced(self, event_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET status = 'synced', synced_at = ?, updated_at = ?, last_error = ''
                WHERE event_id = ?
                """,
                (self.now(), self.now(), event_id),
            )

    def mark_sync_outbox_failed(self, event_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET attempts = attempts + 1, last_error = ?, updated_at = ?, next_attempt_at = ?
                WHERE event_id = ?
                """,
                (error[:500], self.now(), self.now(), event_id),
            )

    def mark_sync_outbox_rejected(self, event_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET status = 'rejected', attempts = attempts + 1, last_error = ?, updated_at = ?
                WHERE event_id = ?
                """,
                (error[:500], self.now(), event_id),
            )

    def create_clock_event(
        self,
        tournament_id: int,
        event_type: str,
        round_id: int | None = None,
        pairing_id: int | None = None,
        board_number: int = 0,
        player_id: int | None = None,
        device_id: str = "",
        source: str = "manual",
        side: str = "",
        seconds_remaining: int | None = None,
        note: str = "",
        payload: Mapping[str, Any] | None = None,
        status: str = "logged",
        occurred_at: str = "",
    ) -> int:
        payload_json = self._canonical_json(payload)
        now = self.now()
        event_seed = self._canonical_json(
            {
                "tournament_id": tournament_id,
                "round_id": round_id,
                "pairing_id": pairing_id,
                "event_type": event_type,
                "device_id": device_id,
                "source": source,
                "occurred_at": occurred_at or now,
                "payload_hash": self._hash_payload(payload_json),
            }
        )
        event_id = self._hash_payload(f"{event_seed}:{datetime.now().timestamp()}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO clock_events (
                    event_id, tournament_id, round_id, pairing_id, board_number,
                    player_id, device_id, source, event_type, side,
                    seconds_remaining, note, payload_json, status, occurred_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tournament_id,
                    round_id,
                    pairing_id,
                    int(board_number or 0),
                    player_id,
                    device_id.strip(),
                    source.strip() or "manual",
                    event_type.strip(),
                    side.strip(),
                    seconds_remaining,
                    note.strip(),
                    payload_json,
                    status.strip() or "logged",
                    occurred_at.strip() or now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_clock_events(
        self,
        tournament_id: int | None = None,
        round_id: int | None = None,
        pairing_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if tournament_id is not None:
            conditions.append("tournament_id = ?")
            params.append(int(tournament_id))
        if round_id is not None:
            conditions.append("round_id = ?")
            params.append(int(round_id))
        if pairing_id is not None:
            conditions.append("pairing_id = ?")
            params.append(int(pairing_id))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM clock_events
                {where}
                ORDER BY occurred_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_audit_event(
        self,
        action: str,
        tournament_id: int | None = None,
        round_id: int | None = None,
        entity_type: str = "",
        entity_id: int | None = None,
        reason: str = "",
        before: Mapping[str, Any] | list[Any] | None = None,
        after: Mapping[str, Any] | list[Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        actor: str = "",
        role: str = "",
    ) -> int:
        before_json = self._canonical_json(before)
        after_json = self._canonical_json(after)
        metadata_json = self._canonical_json(metadata)
        resolved_actor, resolved_role = (actor.strip(), role.strip())
        if not resolved_actor and not resolved_role:
            resolved_actor, resolved_role = self._operator_context()
        event_seed = self._canonical_json(
            {
                "action": action,
                "tournament_id": tournament_id,
                "round_id": round_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "before": before,
                "after": after,
                "metadata": metadata,
                "created_at": self.now(),
            }
        )
        event_id = self._hash_payload(f"{event_seed}:{datetime.now().timestamp()}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, tournament_id, round_id, entity_type, entity_id,
                    action, actor, role, reason, before_hash, after_hash,
                    before_json, after_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tournament_id,
                    round_id,
                    entity_type.strip(),
                    entity_id,
                    action.strip(),
                    resolved_actor,
                    resolved_role,
                    reason.strip(),
                    self._hash_payload(before_json),
                    self._hash_payload(after_json),
                    before_json,
                    after_json,
                    metadata_json,
                    self.now(),
                ),
            )
            audit_row_id = int(cursor.lastrowid)
        if not action.startswith("sync_"):
            self.create_sync_outbox_event(
                action=action,
                tournament_id=tournament_id,
                round_id=round_id,
                entity_type=entity_type,
                entity_id=entity_id,
                payload={
                    "audit_event_id": event_id,
                    "action": action,
                    "actor": resolved_actor,
                    "role": resolved_role,
                    "reason": reason,
                    "before": before,
                    "after": after,
                    "metadata": metadata,
                },
            )
        return audit_row_id

    def list_audit_events(
        self,
        tournament_id: int | None = None,
        limit: int = 200,
        action: str = "",
        entity_type: str = "",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if tournament_id is not None:
            conditions.append("tournament_id = ?")
            params.append(int(tournament_id))
        if action:
            conditions.append("action = ?")
            params.append(action.strip())
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type.strip())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 200), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM audit_events
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_pairing_snapshot(
        self,
        tournament_id: int,
        round_number: int,
        stage: str,
        snapshot: Mapping[str, Any] | list[Any],
        round_id: int | None = None,
        pairing_system: str = "",
        pairing_engine_version: str = "",
        ruleset_version: str = "",
    ) -> int:
        snapshot_json = self._canonical_json(snapshot)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO pairing_snapshots (
                    tournament_id, round_id, round_number, stage, pairing_system,
                    pairing_engine_version, ruleset_version, snapshot_json,
                    snapshot_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    round_id,
                    int(round_number),
                    stage.strip(),
                    pairing_system.strip(),
                    pairing_engine_version.strip(),
                    ruleset_version.strip(),
                    snapshot_json,
                    self._hash_payload(snapshot_json),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_pairing_snapshots(
        self,
        tournament_id: int,
        round_id: int | None = None,
        round_number: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            conditions.append("round_id = ?")
            params.append(int(round_id))
        if round_number is not None:
            conditions.append("round_number = ?")
            params.append(int(round_number))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM pairing_snapshots
                WHERE {' AND '.join(conditions)}
                ORDER BY round_number ASC, stage ASC, id ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_standings_snapshot(
        self,
        tournament_id: int,
        round_id: int,
        round_number: int,
        standings: list[dict[str, Any]],
    ) -> int:
        standings_json = self._canonical_json(standings)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO standings_snapshots (
                    tournament_id, round_id, round_number, standings_json,
                    snapshot_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tournament_id, round_id) DO UPDATE SET
                    standings_json = excluded.standings_json,
                    snapshot_hash = excluded.snapshot_hash,
                    created_at = excluded.created_at
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    int(round_number),
                    standings_json,
                    self._hash_payload(standings_json),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_standings_snapshots(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM standings_snapshots
                WHERE tournament_id = ?
                ORDER BY round_number ASC, id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def replace_tiebreak_components(
        self,
        tournament_id: int,
        round_id: int | None,
        round_number: int,
        components: list[dict[str, Any]],
    ) -> None:
        with self.connect() as connection:
            if round_id is None:
                connection.execute(
                    "DELETE FROM tiebreak_components WHERE tournament_id = ? AND round_id IS NULL",
                    (int(tournament_id),),
                )
            else:
                connection.execute(
                    "DELETE FROM tiebreak_components WHERE tournament_id = ? AND round_id = ?",
                    (int(tournament_id), int(round_id)),
                )
            rows = [
                (
                    int(tournament_id),
                    int(round_id) if round_id is not None else None,
                    int(round_number),
                    int(item["player_id"]),
                    str(item.get("player_name", "")),
                    str(item["criterion"]),
                    item.get("value"),
                    self._canonical_json(item.get("components", {})),
                    self.now(),
                )
                for item in components
            ]
            if rows:
                connection.executemany(
                    """
                    INSERT INTO tiebreak_components (
                        tournament_id, round_id, round_number, player_id, player_name,
                        criterion, value, components_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def list_tiebreak_components(
        self,
        tournament_id: int,
        player_id: int | None = None,
        round_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if player_id is not None:
            conditions.append("player_id = ?")
            params.append(int(player_id))
        if round_id is not None:
            conditions.append("round_id = ?")
            params.append(int(round_id))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM tiebreak_components
                WHERE {' AND '.join(conditions)}
                ORDER BY round_number DESC, player_name COLLATE NOCASE ASC, criterion ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_public_token(
        self,
        token_hash: str,
        tournament_id: int,
        round_id: int,
        pairing_id: int,
        board_number: int,
        expires_at: str,
        purpose: str = "result_submission",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO public_tokens (
                    token_hash, tournament_id, round_id, pairing_id, board_number,
                    purpose, status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    token_hash,
                    int(tournament_id),
                    int(round_id),
                    int(pairing_id),
                    int(board_number),
                    purpose.strip() or "result_submission",
                    expires_at,
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def create_public_tokens_batch(
        self,
        tokens: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not tokens:
            return []
        now = self.now()
        created = []
        with self.connect() as connection:
            for token in tokens:
                previous = connection.execute(
                    """
                    SELECT id
                    FROM public_tokens
                    WHERE pairing_id = ? AND status = 'active' AND expires_at > ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(token["pairing_id"]), now),
                ).fetchone()
                if previous:
                    connection.execute(
                        "UPDATE public_tokens SET status = 'revoked', used_at = '' WHERE id = ?",
                        (int(previous["id"]),),
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO public_tokens (
                        token_hash, tournament_id, round_id, pairing_id, board_number,
                        purpose, status, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        str(token["token_hash"]),
                        int(token["tournament_id"]),
                        int(token["round_id"]),
                        int(token["pairing_id"]),
                        int(token["board_number"]),
                        str(token.get("purpose") or "result_submission"),
                        str(token["expires_at"]),
                        now,
                    ),
                )
                created.append(
                    {
                        **token,
                        "id": int(cursor.lastrowid),
                        "revoked_previous_token_id": int(previous["id"]) if previous else None,
                    }
                )
        return created

    def get_public_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM public_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            return dict(row) if row else None

    def get_active_public_token_for_pairing(self, pairing_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM public_tokens
                WHERE pairing_id = ? AND status = 'active' AND expires_at > ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(pairing_id), self.now()),
            ).fetchone()
            return dict(row) if row else None

    def update_public_token_status(self, token_id: int, status: str, used_at: str = "") -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE public_tokens
                SET status = ?, used_at = ?
                WHERE id = ?
                """,
                (status.strip(), used_at, int(token_id)),
            )

    def create_result_submission(
        self,
        tournament_id: int,
        round_id: int,
        pairing_id: int,
        token_id: int | None,
        board_number: int,
        submitted_result: str,
        submitter: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO result_submissions (
                    tournament_id, round_id, pairing_id, token_id, board_number,
                    submitted_result, submitter, status, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    int(pairing_id),
                    token_id,
                    int(board_number),
                    submitted_result.strip(),
                    submitter.strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def get_result_submission(self, submission_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    s.*,
                    r.status AS round_status,
                    p.result AS current_result
                FROM result_submissions s
                JOIN rounds r ON r.id = s.round_id
                JOIN pairings p ON p.id = s.pairing_id
                WHERE s.id = ?
                """,
                (int(submission_id),),
            ).fetchone()
            return dict(row) if row else None

    def list_result_submissions(
        self,
        tournament_id: int | None = None,
        status: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if tournament_id is not None:
            conditions.append("s.tournament_id = ?")
            params.append(int(tournament_id))
        if status:
            conditions.append("s.status = ?")
            params.append(status.strip())
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    s.*,
                    t.name AS tournament_name,
                    r.number AS round_number,
                    r.status AS round_status,
                    p.result AS current_result
                FROM result_submissions s
                JOIN tournaments t ON t.id = s.tournament_id
                JOIN rounds r ON r.id = s.round_id
                JOIN pairings p ON p.id = s.pairing_id
                {where}
                ORDER BY s.submitted_at DESC, s.id DESC
                LIMIT ?
                """,
                [*params, max(1, min(int(limit or 500), 5000))],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_result_submission_status(
        self,
        submission_id: int,
        status: str,
        reviewer: str = "",
        reason: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE result_submissions
                SET status = ?, reviewer = ?, reason = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status.strip(), reviewer.strip(), reason.strip(), self.now(), int(submission_id)),
            )

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

    def create_class(
        self,
        club_id: int,
        name: str,
        teacher: str = "",
        weekday: str = "",
        time: str = "",
        location: str = "",
        active: int = 1,
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO classes (
                    club_id, name, teacher, weekday, time, location, active,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    club_id,
                    name.strip(),
                    teacher.strip(),
                    weekday.strip(),
                    time.strip(),
                    location.strip(),
                    int(active),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_class(
        self,
        class_id: int,
        club_id: int,
        name: str,
        teacher: str = "",
        weekday: str = "",
        time: str = "",
        location: str = "",
        active: int = 1,
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE classes
                SET club_id = ?, name = ?, teacher = ?, weekday = ?, time = ?,
                    location = ?, active = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    club_id,
                    name.strip(),
                    teacher.strip(),
                    weekday.strip(),
                    time.strip(),
                    location.strip(),
                    int(active),
                    notes.strip(),
                    self.now(),
                    class_id,
                ),
            )

    def get_class(self, class_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT cl.*, c.name AS club_name
                FROM classes cl
                JOIN clubs c ON c.id = cl.club_id
                WHERE cl.id = ?
                """,
                (class_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_classes(
        self,
        club_id: int | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if club_id:
            conditions.append("cl.club_id = ?")
            params.append(club_id)
        if active_only:
            conditions.append("cl.active = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    cl.*,
                    c.name AS club_name,
                    (
                        SELECT COUNT(*)
                        FROM member_class_enrollments e
                        JOIN members m ON m.id = e.member_id
                        WHERE e.class_id = cl.id
                            AND e.status = 'active'
                            AND m.status = 'active'
                    ) AS active_members_count
                FROM classes cl
                JOIN clubs c ON c.id = cl.club_id
                {where}
                ORDER BY cl.active DESC, c.name COLLATE NOCASE ASC, cl.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_member_active_class(
        self,
        member_id: int,
        class_id: int | None,
        start_date: str = "",
        notes: str = "",
    ) -> None:
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE member_class_enrollments
                SET status = 'inactive', end_date = COALESCE(NULLIF(end_date, ''), ?),
                    updated_at = ?
                WHERE member_id = ? AND status = 'active'
                """,
                (now[:10], now, member_id),
            )
            if not class_id:
                return
            connection.execute(
                """
                INSERT INTO member_class_enrollments (
                    member_id, class_id, status, start_date, end_date, notes,
                    created_at, updated_at
                ) VALUES (?, ?, 'active', ?, '', ?, ?, ?)
                ON CONFLICT(member_id, class_id) DO UPDATE SET
                    status = 'active',
                    start_date = excluded.start_date,
                    end_date = '',
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    member_id,
                    class_id,
                    start_date.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )

    def get_member_active_class(self, member_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    e.*,
                    cl.name AS class_name,
                    cl.club_id,
                    c.name AS club_name
                FROM member_class_enrollments e
                JOIN classes cl ON cl.id = e.class_id
                JOIN clubs c ON c.id = cl.club_id
                WHERE e.member_id = ? AND e.status = 'active'
                ORDER BY e.updated_at DESC, e.id DESC
                LIMIT 1
                """,
                (member_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_member_classes(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    e.*,
                    cl.name AS class_name,
                    cl.club_id,
                    c.name AS club_name
                FROM member_class_enrollments e
                JOIN classes cl ON cl.id = e.class_id
                JOIN clubs c ON c.id = cl.club_id
                WHERE e.member_id = ?
                ORDER BY e.status = 'active' DESC, e.updated_at DESC, e.id DESC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_exercise(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO exercise_library (
                    club_id, learning_level_id, title, theme, difficulty, source,
                    fen, pgn, solution, objective, tags, active, notes, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("learning_level_id"),
                    str(data.get("title", "")).strip(),
                    str(data.get("theme", "")).strip(),
                    str(data.get("difficulty", "basic")).strip() or "basic",
                    str(data.get("source", "")).strip(),
                    str(data.get("fen", "")).strip(),
                    str(data.get("pgn", "")).strip(),
                    str(data.get("solution", "")).strip(),
                    str(data.get("objective", "")).strip(),
                    str(data.get("tags", "")).strip(),
                    int(data.get("active", 1) or 0),
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_exercise(self, exercise_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE exercise_library
                SET club_id = ?, learning_level_id = ?, title = ?, theme = ?,
                    difficulty = ?, source = ?, fen = ?, pgn = ?, solution = ?,
                    objective = ?, tags = ?, active = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("learning_level_id"),
                    str(data.get("title", "")).strip(),
                    str(data.get("theme", "")).strip(),
                    str(data.get("difficulty", "basic")).strip() or "basic",
                    str(data.get("source", "")).strip(),
                    str(data.get("fen", "")).strip(),
                    str(data.get("pgn", "")).strip(),
                    str(data.get("solution", "")).strip(),
                    str(data.get("objective", "")).strip(),
                    str(data.get("tags", "")).strip(),
                    int(data.get("active", 1) or 0),
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    exercise_id,
                ),
            )

    def get_exercise(self, exercise_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    e.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.exercise_id = e.id
                    ) AS list_usage_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.exercise_id = e.id
                    ) AS attempt_count
                FROM exercise_library e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN learning_levels ll ON ll.id = e.learning_level_id
                WHERE e.id = ?
                """,
                (exercise_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_exercises(
        self,
        search: str = "",
        club_id: int | None = None,
        learning_level_id: int | None = None,
        theme: str = "",
        difficulty: str = "",
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if search:
            conditions.append(
                """
                (
                    e.title LIKE ? OR e.theme LIKE ? OR e.source LIKE ? OR
                    e.fen LIKE ? OR e.pgn LIKE ? OR e.solution LIKE ? OR
                    e.objective LIKE ? OR e.tags LIKE ? OR e.notes LIKE ?
                )
                """
            )
            params.extend([f"%{search.strip()}%"] * 9)
        if club_id:
            conditions.append("e.club_id = ?")
            params.append(club_id)
        if learning_level_id:
            conditions.append("e.learning_level_id = ?")
            params.append(learning_level_id)
        if theme:
            conditions.append("e.theme = ?")
            params.append(theme.strip())
        if difficulty:
            conditions.append("e.difficulty = ?")
            params.append(difficulty.strip())
        if active_only:
            conditions.append("e.active = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    e.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.exercise_id = e.id
                    ) AS list_usage_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.exercise_id = e.id
                    ) AS attempt_count
                FROM exercise_library e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN learning_levels ll ON ll.id = e.learning_level_id
                {where}
                ORDER BY e.active DESC, e.theme COLLATE NOCASE ASC, e.title COLLATE NOCASE ASC, e.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_exercise_active(self, exercise_id: int, active: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE exercise_library
                SET active = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(active), self.now(), exercise_id),
            )

    def create_training_list(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO training_lists (
                    club_id, class_id, learning_level_id, name, description,
                    target_date, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("class_id"),
                    data.get("learning_level_id"),
                    str(data.get("name", "")).strip(),
                    str(data.get("description", "")).strip(),
                    str(data.get("target_date", "")).strip(),
                    str(data.get("status", "draft")).strip() or "draft",
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_training_list(self, list_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE training_lists
                SET club_id = ?, class_id = ?, learning_level_id = ?, name = ?,
                    description = ?, target_date = ?, status = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("club_id") or 1),
                    data.get("class_id"),
                    data.get("learning_level_id"),
                    str(data.get("name", "")).strip(),
                    str(data.get("description", "")).strip(),
                    str(data.get("target_date", "")).strip(),
                    str(data.get("status", "draft")).strip() or "draft",
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    list_id,
                ),
            )

    def get_training_list(self, list_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tl.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.list_id = tl.id
                    ) AS exercise_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.list_id = tl.id
                    ) AS attempt_count
                FROM training_lists tl
                LEFT JOIN clubs c ON c.id = tl.club_id
                LEFT JOIN classes cl ON cl.id = tl.class_id
                LEFT JOIN learning_levels ll ON ll.id = tl.learning_level_id
                WHERE tl.id = ?
                """,
                (list_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_training_lists(
        self,
        club_id: int | None = None,
        class_id: int | None = None,
        learning_level_id: int | None = None,
        status: str = "",
        include_archived: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if club_id:
            conditions.append("tl.club_id = ?")
            params.append(club_id)
        if class_id:
            conditions.append("(tl.class_id IS NULL OR tl.class_id = ?)")
            params.append(class_id)
        if learning_level_id:
            conditions.append("tl.learning_level_id = ?")
            params.append(learning_level_id)
        if status:
            conditions.append("tl.status = ?")
            params.append(status.strip())
        if not include_archived:
            conditions.append("tl.status <> 'archived'")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tl.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    (
                        SELECT COUNT(*)
                        FROM training_list_exercises tle
                        WHERE tle.list_id = tl.id
                    ) AS exercise_count,
                    (
                        SELECT COUNT(*)
                        FROM exercise_attempts ea
                        WHERE ea.list_id = tl.id
                    ) AS attempt_count
                FROM training_lists tl
                LEFT JOIN clubs c ON c.id = tl.club_id
                LEFT JOIN classes cl ON cl.id = tl.class_id
                LEFT JOIN learning_levels ll ON ll.id = tl.learning_level_id
                {where}
                ORDER BY
                    CASE tl.status
                        WHEN 'ready' THEN 1
                        WHEN 'draft' THEN 2
                        WHEN 'used' THEN 3
                        ELSE 4
                    END,
                    tl.target_date DESC,
                    tl.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def replace_training_list_exercises(self, list_id: int, rows: list[dict[str, Any]]) -> None:
        now = self.now()
        with self.connect() as connection:
            connection.execute("DELETE FROM training_list_exercises WHERE list_id = ?", (list_id,))
            for index, row in enumerate(rows, start=1):
                connection.execute(
                    """
                    INSERT INTO training_list_exercises (
                        list_id, exercise_id, position_order, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        list_id,
                        int(row.get("exercise_id") or 0),
                        int(row.get("position_order") or index),
                        str(row.get("notes", "")).strip(),
                        now,
                        now,
                    ),
                )

    def list_training_list_exercises(self, list_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tle.*,
                    e.title,
                    e.theme,
                    e.difficulty,
                    e.source,
                    e.fen,
                    e.pgn,
                    e.solution,
                    e.objective,
                    e.tags,
                    e.active,
                    ll.name AS learning_level_name
                FROM training_list_exercises tle
                JOIN exercise_library e ON e.id = tle.exercise_id
                LEFT JOIN learning_levels ll ON ll.id = e.learning_level_id
                WHERE tle.list_id = ?
                ORDER BY tle.position_order ASC, tle.id ASC
                """,
                (list_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_exercise_attempt(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO exercise_attempts (
                    exercise_id, member_id, list_id, session_id, attempt_date,
                    result, score, time_seconds, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("exercise_id") or 0),
                    int(data.get("member_id") or 0),
                    data.get("list_id"),
                    data.get("session_id"),
                    str(data.get("attempt_date", "")).strip(),
                    str(data.get("result", "attempted")).strip() or "attempted",
                    float(data.get("score", 0.0) or 0.0),
                    int(data.get("time_seconds", 0) or 0),
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_exercise_attempts(
        self,
        member_id: int | None = None,
        exercise_id: int | None = None,
        list_id: int | None = None,
        session_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if member_id:
            conditions.append("ea.member_id = ?")
            params.append(member_id)
        if exercise_id:
            conditions.append("ea.exercise_id = ?")
            params.append(exercise_id)
        if list_id:
            conditions.append("ea.list_id = ?")
            params.append(list_id)
        if session_id:
            conditions.append("ea.session_id = ?")
            params.append(session_id)
        if start_date:
            conditions.append("ea.attempt_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ea.attempt_date <= ?")
            params.append(end_date)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    ea.*,
                    e.title AS exercise_title,
                    e.theme AS exercise_theme,
                    m.name AS member_name,
                    tl.name AS list_name,
                    s.title AS session_title
                FROM exercise_attempts ea
                JOIN exercise_library e ON e.id = ea.exercise_id
                JOIN members m ON m.id = ea.member_id
                LEFT JOIN training_lists tl ON tl.id = ea.list_id
                LEFT JOIN training_sessions s ON s.id = ea.session_id
                {where}
                ORDER BY ea.attempt_date DESC, ea.created_at DESC, ea.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_training_session(
        self,
        club_id: int = 1,
        class_id: int | None = None,
        training_list_id: int | None = None,
        title: str = "",
        session_type: str = "aula",
        session_date: str = "",
        start_time: str = "",
        end_time: str = "",
        instructor: str = "",
        location: str = "",
        learning_level_id: int | None = None,
        objective: str = "",
        content: str = "",
        homework: str = "",
        status: str = "planned",
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO training_sessions (
                    club_id, class_id, training_list_id, title, session_type, session_date,
                    start_time, end_time, instructor, location, learning_level_id,
                    objective, content, homework, status, notes, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(club_id or 1),
                    class_id,
                    training_list_id,
                    title.strip(),
                    session_type.strip(),
                    session_date.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    instructor.strip(),
                    location.strip(),
                    learning_level_id,
                    objective.strip(),
                    content.strip(),
                    homework.strip(),
                    status.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_training_session(
        self,
        session_id: int,
        club_id: int = 1,
        class_id: int | None = None,
        training_list_id: int | None = None,
        title: str = "",
        session_type: str = "aula",
        session_date: str = "",
        start_time: str = "",
        end_time: str = "",
        instructor: str = "",
        location: str = "",
        learning_level_id: int | None = None,
        objective: str = "",
        content: str = "",
        homework: str = "",
        status: str = "planned",
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE training_sessions
                SET club_id = ?, class_id = ?, training_list_id = ?, title = ?,
                    session_type = ?, session_date = ?, start_time = ?, end_time = ?,
                    instructor = ?, location = ?, learning_level_id = ?, objective = ?,
                    content = ?, homework = ?, status = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(club_id or 1),
                    class_id,
                    training_list_id,
                    title.strip(),
                    session_type.strip(),
                    session_date.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    instructor.strip(),
                    location.strip(),
                    learning_level_id,
                    objective.strip(),
                    content.strip(),
                    homework.strip(),
                    status.strip(),
                    notes.strip(),
                    self.now(),
                    session_id,
                ),
            )

    def get_training_session(self, session_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    s.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    tl.name AS training_list_name
                FROM training_sessions s
                LEFT JOIN clubs c ON c.id = s.club_id
                LEFT JOIN classes cl ON cl.id = s.class_id
                LEFT JOIN learning_levels ll ON ll.id = s.learning_level_id
                LEFT JOIN training_lists tl ON tl.id = s.training_list_id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_training_sessions(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if start_date:
            conditions.append("s.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("s.session_date <= ?")
            params.append(end_date)
        if club_id:
            conditions.append("s.club_id = ?")
            params.append(club_id)
        if class_id:
            conditions.append("s.class_id = ?")
            params.append(class_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    s.*,
                    c.name AS club_name,
                    cl.name AS class_name,
                    ll.name AS learning_level_name,
                    tl.name AS training_list_name,
                    (SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id) AS attendance_count,
                    (
                        SELECT COUNT(*)
                        FROM attendance a
                        WHERE a.session_id = s.id AND a.status = 'present'
                    ) AS present_count,
                    (
                        SELECT COUNT(*)
                        FROM attendance a
                        WHERE a.session_id = s.id AND a.status = 'absent'
                    ) AS absent_count,
                    (
                        SELECT COUNT(*)
                        FROM attendance a
                        WHERE a.session_id = s.id AND a.status = 'justified'
                    ) AS justified_count
                FROM training_sessions s
                LEFT JOIN clubs c ON c.id = s.club_id
                LEFT JOIN classes cl ON cl.id = s.class_id
                LEFT JOIN learning_levels ll ON ll.id = s.learning_level_id
                LEFT JOIN training_lists tl ON tl.id = s.training_list_id
                {where}
                ORDER BY s.session_date DESC, s.start_time DESC, s.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def save_attendance(
        self,
        session_id: int,
        member_id: int,
        status: str = "present",
        notes: str = "",
    ) -> None:
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO attendance (
                    session_id, member_id, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, member_id) DO UPDATE SET
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    member_id,
                    status.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )

    def list_session_attendance(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    a.*,
                    m.name AS member_name,
                    m.phone AS member_phone,
                    m.category AS member_category,
                    m.status AS member_status,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM attendance a
                JOIN members m ON m.id = a.member_id
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE a.session_id = ?
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                (session_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_session_members_for_attendance(self, session_id: int) -> list[dict[str, Any]]:
        session = self.get_training_session(session_id)
        if not session:
            return []
        class_filter = "AND ac.class_id = ?" if session.get("class_id") else ""
        params: list[Any] = [session_id]
        if session.get("class_id"):
            params.append(int(session["class_id"]))
        elif session.get("club_id"):
            class_filter = "AND m.club_id = ?"
            params.append(int(session["club_id"]))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name,
                    a.status AS attendance_status,
                    a.notes AS attendance_notes
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                LEFT JOIN attendance a
                    ON a.member_id = m.id AND a.session_id = ?
                WHERE m.status = 'active'
                {class_filter}
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_attendance_report(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
        member_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if start_date:
            conditions.append("s.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("s.session_date <= ?")
            params.append(end_date)
        if club_id:
            conditions.append("s.club_id = ?")
            params.append(club_id)
        if member_id:
            conditions.append("a.member_id = ?")
            params.append(member_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    a.*,
                    s.title,
                    s.session_type,
                    s.session_date,
                    s.start_time,
                    s.end_time,
                    s.instructor,
                    s.location,
                    s.status AS session_status,
                    c.name AS club_name,
                    cl.name AS class_name,
                    m.name AS member_name,
                    m.category AS member_category,
                    m.member_type,
                    m.status AS member_status
                FROM attendance a
                JOIN training_sessions s ON s.id = a.session_id
                JOIN members m ON m.id = a.member_id
                LEFT JOIN clubs c ON c.id = s.club_id
                LEFT JOIN classes cl ON cl.id = s.class_id
                {where}
                ORDER BY
                    s.session_date ASC,
                    s.start_time ASC,
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def member_attendance_summary(
        self,
        member_id: int,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        conditions = ["a.member_id = ?"]
        params: list[Any] = [member_id]
        if start_date:
            conditions.append("s.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("s.session_date <= ?")
            params.append(end_date)
        where = " AND ".join(conditions)
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present,
                    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent,
                    SUM(CASE WHEN a.status = 'justified' THEN 1 ELSE 0 END) AS justified
                FROM attendance a
                JOIN training_sessions s ON s.id = a.session_id
                WHERE {where}
                """,
                params,
            ).fetchone()
            total = int(row["total"] or 0) if row else 0
            present = int(row["present"] or 0) if row else 0
            return {
                "total": total,
                "present": present,
                "absent": int(row["absent"] or 0) if row else 0,
                "justified": int(row["justified"] or 0) if row else 0,
                "attendance_rate": round((present / total) * 100, 1) if total else 0,
            }

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

    def create_tournament(
        self,
        name: str,
        club_id: int | None = 1,
        location: str = "",
        rounds_count: int = 5,
        time_control: str = "",
        start_date: str = "",
        end_date: str = "",
        bye_points: float = 1.0,
        class_id: int | None = None,
        competition_type: str = "individual",
    ) -> int:
        club_value = int(club_id) if club_id is not None else None
        class_value = int(class_id) if class_id is not None else None
        competition_value = competition_type.strip() or "individual"
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tournaments (
                    club_id, class_id, competition_type, name, location, start_date, end_date, system, rounds_count,
                    time_control, bye_points, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Suico', ?, ?, ?, 'draft', ?)
                """,
                (
                    club_value,
                    class_value,
                    competition_value,
                    name.strip(),
                    location.strip(),
                    start_date.strip(),
                    end_date.strip(),
                    int(rounds_count),
                    time_control.strip(),
                    float(bye_points),
                    self.now(),
                ),
            )
            tournament_id = int(cursor.lastrowid)
            self._ensure_tournament_settings(connection, tournament_id)
            self._ensure_round_schedule(connection, tournament_id, int(rounds_count))
            return tournament_id

    def update_tournament_status(self, tournament_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET status = ? WHERE id = ?",
                (status, tournament_id),
            )

    def update_tournament_details(
        self,
        tournament_id: int,
        name: str,
        club_id: int | None = None,
        location: str = "",
        rounds_count: int = 5,
        time_control: str = "",
        start_date: str = "",
        end_date: str = "",
        bye_points: float = 1.0,
        class_id: int | None = None,
        competition_type: str = "individual",
    ) -> None:
        club_value = int(club_id) if club_id is not None else None
        class_value = int(class_id) if class_id is not None else None
        competition_value = competition_type.strip() or "individual"
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tournaments
                SET club_id = ?, class_id = ?, competition_type = ?, name = ?, location = ?, start_date = ?, end_date = ?,
                    rounds_count = ?, time_control = ?, bye_points = ?
                WHERE id = ?
                """,
                (
                    club_value,
                    class_value,
                    competition_value,
                    name.strip(),
                    location.strip(),
                    start_date.strip(),
                    end_date.strip(),
                    int(rounds_count),
                    time_control.strip(),
                    float(bye_points),
                    tournament_id,
                ),
            )
            self._ensure_round_schedule(connection, tournament_id, int(rounds_count))
            connection.execute(
                """
                DELETE FROM round_schedule
                WHERE tournament_id = ? AND round_number > ?
                """,
                (tournament_id, int(rounds_count)),
            )

    def duplicate_tournament(self, source_tournament_id: int, new_name: str) -> int:
        with self.connect() as connection:
            source = connection.execute(
                """
                SELECT *
                FROM tournaments
                WHERE id = ?
                """,
                (source_tournament_id,),
            ).fetchone()
            if not source:
                raise ValueError("Torneio de origem nao encontrado.")

            cursor = connection.execute(
                """
                INSERT INTO tournaments (
                    club_id, class_id, competition_type, name, location, start_date, end_date, system, rounds_count,
                    time_control, bye_points, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
                """,
                (
                    source["club_id"],
                    source["class_id"],
                    source["competition_type"],
                    new_name.strip(),
                    source["location"],
                    source["start_date"],
                    source["end_date"],
                    source["system"],
                    source["rounds_count"],
                    source["time_control"],
                    source["bye_points"],
                    self.now(),
                ),
            )
            new_tournament_id = int(cursor.lastrowid)
            self._ensure_tournament_settings(connection, source_tournament_id)
            self._ensure_tournament_settings(connection, new_tournament_id)
            connection.execute(
                """
                UPDATE tournament_settings
                SET
                    fide_event_id = src.fide_event_id,
                    organizer = src.organizer,
                    website = src.website,
                    contact_email = src.contact_email,
                    director = src.director,
                    chief_arbiter = src.chief_arbiter,
                    arbiters = src.arbiters,
                    federation = src.federation,
                    state = src.state,
                    categories = src.categories,
                    cutoff_date = src.cutoff_date,
                    comments = src.comments,
                    prizes = src.prizes,
                    initial_order = src.initial_order,
                    tournament_type = src.tournament_type,
                    tournament_profile = src.tournament_profile,
                    allow_public_registration = src.allow_public_registration,
                    allow_player_result_edit = src.allow_player_result_edit,
                    allow_dangerous_changes = src.allow_dangerous_changes,
                    disable_bye = src.disable_bye,
                    late_entry_points = src.late_entry_points,
                    accelerated_system = src.accelerated_system,
                    hide_standings = src.hide_standings,
                    calculate_performance = src.calculate_performance,
                    pairing_method = src.pairing_method,
                    pairing_system = src.pairing_system,
                    acceleration_method = src.acceleration_method,
                    hide_color_names = src.hide_color_names,
                    show_opponents_in_standings = src.show_opponents_in_standings,
                    team_boards_count = src.team_boards_count,
                    team_match_win_points = src.team_match_win_points,
                    team_match_draw_points = src.team_match_draw_points,
                    team_match_loss_points = src.team_match_loss_points,
                    team_pairing_method = src.team_pairing_method,
                    team_standing_primary = src.team_standing_primary,
                    team_standing_secondary = src.team_standing_secondary,
                    team_fixed_board_order = src.team_fixed_board_order,
                    team_board_order_policy = src.team_board_order_policy,
                    team_reserve_policy = src.team_reserve_policy,
                    team_lineup_deadline = src.team_lineup_deadline,
                    team_max_substitutions = src.team_max_substitutions,
                    rating_fee_fide = src.rating_fee_fide,
                    rating_fee_cbx = src.rating_fee_cbx,
                    rating_fee_lbx = src.rating_fee_lbx,
                    archived = src.archived,
                    updated_at = ?
                FROM tournament_settings AS src
                WHERE tournament_settings.tournament_id = ?
                  AND src.tournament_id = ?
                """,
                (self.now(), new_tournament_id, source_tournament_id),
            )
            schedules = connection.execute(
                """
                SELECT round_number, date, time
                FROM round_schedule
                WHERE tournament_id = ?
                ORDER BY round_number
                """,
                (source_tournament_id,),
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        new_tournament_id,
                        int(row["round_number"]),
                        str(row["date"] or ""),
                        str(row["time"] or ""),
                        self.now(),
                    )
                    for row in schedules
                ],
            )
            return new_tournament_id

    def delete_tournament(self, tournament_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))

    def list_tournaments(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    t.*,
                    c.name AS club_name,
                    c.kind AS club_kind,
                    cl.name AS class_name
                FROM tournaments t
                LEFT JOIN clubs c ON c.id = t.club_id
                LEFT JOIN classes cl ON cl.id = t.class_id
                ORDER BY t.created_at DESC, t.id DESC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_tournament(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    t.*,
                    c.name AS club_name,
                    c.kind AS club_kind,
                    cl.name AS class_name
                FROM tournaments t
                LEFT JOIN clubs c ON c.id = t.club_id
                LEFT JOIN classes cl ON cl.id = t.class_id
                WHERE t.id = ?
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_tournament_settings(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            row = connection.execute(
                """
                SELECT *
                FROM tournament_settings
                WHERE tournament_id = ?
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def set_chess_results_url(self, tournament_id: int, url: str) -> None:
        """Guarda o link publicado do torneio no Chess-Results (Fase J)."""
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            connection.execute(
                "UPDATE tournament_settings SET chess_results_url = ?, updated_at = ? WHERE tournament_id = ?",
                ((url or "").strip(), self.now(), tournament_id),
            )

    def save_tournament_settings(
        self,
        tournament_id: int,
        data: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            connection.execute(
                """
                UPDATE tournament_settings
                SET fide_event_id = ?, organizer = ?, website = ?, contact_email = ?,
                    director = ?, chief_arbiter = ?, arbiters = ?, federation = ?,
                    state = ?, categories = ?, cutoff_date = ?, comments = ?,
                    prizes = ?, initial_order = ?, tournament_type = ?, tournament_profile = ?,
                    allow_public_registration = ?, allow_player_result_edit = ?,
                    allow_dangerous_changes = ?, disable_bye = ?,
                    late_entry_points = ?, accelerated_system = ?,
                    hide_standings = ?, calculate_performance = ?,
                    pairing_system = ?, acceleration_method = ?,
                    hide_color_names = ?, show_opponents_in_standings = ?,
                    tiebreak_sequence = ?, team_tiebreak_sequence = ?,
                    prize_policy = ?, prize_tax_percent = ?,
                    team_boards_count = ?, team_match_win_points = ?,
                    team_match_draw_points = ?, team_match_loss_points = ?,
                    team_pairing_method = ?, team_standing_primary = ?,
                    team_standing_secondary = ?, team_fixed_board_order = ?,
                    team_board_order_policy = ?, team_reserve_policy = ?,
                    team_lineup_deadline = ?, team_max_substitutions = ?,
                    rating_fee_fide = ?, rating_fee_cbx = ?, rating_fee_lbx = ?,
                    archived = ?, updated_at = ?
                WHERE tournament_id = ?
                """,
                (
                    str(data.get("fide_event_id", "")).strip(),
                    str(data.get("organizer", "")).strip(),
                    str(data.get("website", "")).strip(),
                    str(data.get("contact_email", "")).strip(),
                    str(data.get("director", "")).strip(),
                    str(data.get("chief_arbiter", "")).strip(),
                    str(data.get("arbiters", "")).strip(),
                    str(data.get("federation", "")).strip(),
                    str(data.get("state", "")).strip(),
                    str(data.get("categories", "")).strip(),
                    str(data.get("cutoff_date", "")).strip(),
                    str(data.get("comments", "")).strip(),
                    str(data.get("prizes", "")).strip(),
                    str(data.get("initial_order", "rating")).strip() or "rating",
                    str(data.get("tournament_type", "real")).strip() or "real",
                    str(data.get("tournament_profile", "free")).strip() or "free",
                    int(data.get("allow_public_registration", 0) or 0),
                    int(data.get("allow_player_result_edit", 0) or 0),
                    int(data.get("allow_dangerous_changes", 0) or 0),
                    int(data.get("disable_bye", 0) or 0),
                    float(data.get("late_entry_points", 0.0) or 0.0),
                    int(data.get("accelerated_system", 0) or 0),
                    int(data.get("hide_standings", 0) or 0),
                    int(data.get("calculate_performance", 0) or 0),
                    str(data.get("pairing_system", "custom_authorized")).strip() or "custom_authorized",
                    str(data.get("acceleration_method", "none")).strip() or "none",
                    int(data.get("hide_color_names", 0) or 0),
                    int(data.get("show_opponents_in_standings", 0) or 0),
                    str(data.get("tiebreak_sequence", "")),
                    str(data.get("team_tiebreak_sequence", "")),
                    str(data.get("prize_policy", "best_only")).strip() or "best_only",
                    float(data.get("prize_tax_percent", 0.0) or 0.0),
                    int(data.get("team_boards_count", 4) or 4),
                    float(data.get("team_match_win_points", 2.0) or 2.0),
                    float(data.get("team_match_draw_points", 1.0) or 1.0),
                    float(data.get("team_match_loss_points", 0.0) or 0.0),
                    str(data.get("team_pairing_method", "swiss")).strip() or "swiss",
                    str(data.get("team_standing_primary", "match_points")).strip() or "match_points",
                    str(data.get("team_standing_secondary", "game_points")).strip() or "game_points",
                    int(data.get("team_fixed_board_order", 1) or 0),
                    str(data.get("team_board_order_policy", "fixed")).strip() or "fixed",
                    str(data.get("team_reserve_policy", "same_team")).strip() or "same_team",
                    str(data.get("team_lineup_deadline", "")).strip(),
                    int(data.get("team_max_substitutions", 0) or 0),
                    float(data.get("rating_fee_fide", 0.0) or 0.0),
                    float(data.get("rating_fee_cbx", 0.0) or 0.0),
                    float(data.get("rating_fee_lbx", 0.0) or 0.0),
                    int(data.get("archived", 0) or 0),
                    self.now(),
                    tournament_id,
                ),
            )

    def save_fide_rating_report(
        self,
        tournament_id: int,
        rating_type: str,
        rows: list[dict[str, Any]],
    ) -> None:
        """Persiste o relatorio de variacao de rating (idempotente por tipo)."""
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM fide_rating_reports WHERE tournament_id = ? AND rating_type = ?",
                (tournament_id, str(rating_type)),
            )
            connection.executemany(
                """
                INSERT INTO fide_rating_reports (
                    tournament_id, player_id, rating_type, ro, k, games_rated,
                    score, we, delta, rc, rp, n_over_400, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tournament_id,
                        int(row["player_id"]),
                        str(rating_type),
                        row.get("ro"),
                        row.get("k"),
                        row.get("games_rated"),
                        row.get("score"),
                        row.get("we"),
                        row.get("delta"),
                        row.get("rc"),
                        row.get("rp"),
                        row.get("n_over_400"),
                        now,
                    )
                    for row in rows
                ],
            )

    def get_fide_rating_report(
        self,
        tournament_id: int,
        rating_type: str = "fide",
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            report_rows = connection.execute(
                """
                SELECT f.*, p.name AS name, p.surname AS surname, p.given_name AS given_name
                FROM fide_rating_reports f
                LEFT JOIN players p ON p.id = f.player_id
                WHERE f.tournament_id = ? AND f.rating_type = ?
                ORDER BY (f.ro IS NULL), f.ro DESC, p.name COLLATE NOCASE
                """,
                (tournament_id, str(rating_type)),
            ).fetchall()
            return [dict(row) for row in report_rows]

    def list_tournament_prizes(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tournament_prizes
                WHERE tournament_id = ?
                ORDER BY position, id
                """,
                (tournament_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def replace_tournament_prizes(
        self,
        tournament_id: int,
        prizes: list[dict[str, Any]],
    ) -> None:
        """Substitui todos os premios do torneio (idempotente)."""
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM tournament_prizes WHERE tournament_id = ?",
                (tournament_id,),
            )
            connection.executemany(
                """
                INSERT INTO tournament_prizes (
                    tournament_id, kind, label, category, rank_from, rank_to,
                    amount, position, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tournament_id,
                        str(prize.get("kind") or "overall"),
                        str(prize.get("label") or ""),
                        str(prize.get("category") or ""),
                        int(prize.get("rank_from") or 1),
                        int(prize.get("rank_to") or prize.get("rank_from") or 1),
                        float(prize.get("amount") or 0.0),
                        index,
                        now,
                    )
                    for index, prize in enumerate(prizes)
                ],
            )

    def get_report_layout_columns(self, tournament_id: int, report_key: str) -> list[Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT columns_json FROM report_layouts WHERE tournament_id = ? AND report_key = ?",
                (tournament_id, str(report_key)),
            ).fetchone()
        if not row or not row["columns_json"]:
            return []
        try:
            data = json.loads(row["columns_json"])
        except (ValueError, TypeError):
            return []
        return list(data) if isinstance(data, list) else []

    def save_report_layout(self, tournament_id: int, report_key: str, columns: list[Any]) -> None:
        payload = json.dumps(list(columns), ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO report_layouts (tournament_id, report_key, columns_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tournament_id, report_key)
                DO UPDATE SET columns_json = excluded.columns_json, updated_at = excluded.updated_at
                """,
                (tournament_id, str(report_key), payload, self.now()),
            )

    def set_tournament_parent(self, tournament_id: int, parent_tournament_id: int | None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET parent_tournament_id = ? WHERE id = ?",
                (parent_tournament_id, tournament_id),
            )

    def update_pairing_method(self, tournament_id: int, pairing_method: str) -> None:
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            connection.execute(
                "UPDATE tournament_settings SET pairing_method = ?, updated_at = ? WHERE tournament_id = ?",
                (str(pairing_method), self.now(), tournament_id),
            )

    def set_player_scheveningen_group(self, player_id: int, group: str) -> None:
        value = str(group or "").strip().upper()
        if value not in ("", "A", "B"):
            value = ""
        with self.connect() as connection:
            connection.execute(
                "UPDATE players SET scheveningen_group = ? WHERE id = ?",
                (value, player_id),
            )

    def list_round_schedule(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return []
        with self.connect() as connection:
            self._ensure_round_schedule(
                connection,
                tournament_id,
                int(tournament["rounds_count"] or 0),
            )
            rows = connection.execute(
                """
                SELECT *
                FROM round_schedule
                WHERE tournament_id = ? AND round_number <= ?
                ORDER BY round_number ASC
                """,
                (tournament_id, int(tournament["rounds_count"] or 0)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def save_round_schedule(
        self,
        tournament_id: int,
        schedule: list[dict[str, Any]],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tournament_id, round_number) DO UPDATE SET
                    date = excluded.date,
                    time = excluded.time,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        tournament_id,
                        int(item["round_number"]),
                        str(item.get("date", "")).strip(),
                        str(item.get("time", "")).strip(),
                        self.now(),
                    )
                    for item in schedule
                ],
            )

    def create_official_rating_snapshot(
        self,
        source: str,
        list_date: str = "",
        file_name: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO official_rating_snapshots (
                    source, list_date, file_name, imported_count, imported_at
                ) VALUES (?, ?, ?, 0, ?)
                """,
                (source.strip().upper(), list_date.strip(), file_name.strip(), self.now()),
            )
            return int(cursor.lastrowid)

    def update_official_rating_snapshot_count(
        self,
        snapshot_id: int,
        imported_count: int,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE official_rating_snapshots
                SET imported_count = ?
                WHERE id = ?
                """,
                (int(imported_count), snapshot_id),
            )

    def create_official_rating_snapshot_with_players(
        self,
        source: str,
        list_date: str = "",
        file_name: str = "",
        players: list[dict[str, Any]] | None = None,
    ) -> int:
        source = source.strip().upper()
        rows = players or []
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO official_rating_snapshots (
                    source, list_date, file_name, imported_count, imported_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (source, list_date.strip(), file_name.strip(), len(rows), now),
            )
            snapshot_id = int(cursor.lastrowid)
            for player in rows:
                self._insert_official_player(
                    connection,
                    snapshot_id=snapshot_id,
                    source=source,
                    updated_at=now,
                    **player,
                )
            return snapshot_id

    def insert_official_player(
        self,
        snapshot_id: int,
        source: str,
        external_id: str,
        name: str,
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        fide_id: str = "",
        cbx_id: str = "",
        federation: str = "",
        club: str = "",
        birth_date: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        standard_rating: int = 0,
        rapid_rating: int = 0,
        blitz_rating: int = 0,
    ) -> int:
        with self.connect() as connection:
            return self._insert_official_player(
                connection,
                snapshot_id=snapshot_id,
                source=source,
                external_id=external_id,
                name=name,
                surname=surname,
                given_name=given_name,
                title=title,
                sex=sex,
                fide_id=fide_id,
                cbx_id=cbx_id,
                federation=federation,
                club=club,
                birth_date=birth_date,
                national_rating=national_rating,
                international_rating=international_rating,
                standard_rating=standard_rating,
                rapid_rating=rapid_rating,
                blitz_rating=blitz_rating,
                updated_at=self.now(),
            )

    @staticmethod
    def _insert_official_player(
        connection: sqlite3.Connection,
        snapshot_id: int,
        source: str,
        external_id: str,
        name: str,
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        fide_id: str = "",
        cbx_id: str = "",
        federation: str = "",
        club: str = "",
        birth_date: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        standard_rating: int = 0,
        rapid_rating: int = 0,
        blitz_rating: int = 0,
        updated_at: str = "",
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO official_players (
                snapshot_id, source, external_id, fide_id, cbx_id, name,
                surname, given_name, title, sex, federation, club, birth_date,
                national_rating, international_rating, standard_rating,
                rapid_rating, blitz_rating, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                source.strip().upper(),
                external_id.strip(),
                fide_id.strip(),
                cbx_id.strip(),
                name.strip(),
                surname.strip(),
                given_name.strip(),
                title.strip(),
                sex.strip(),
                federation.strip(),
                club.strip(),
                birth_date.strip(),
                int(national_rating or 0),
                int(international_rating or 0),
                int(standard_rating or 0),
                int(rapid_rating or 0),
                int(blitz_rating or 0),
                updated_at,
            ),
        )
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Falha ao inserir jogador oficial.")
        return int(lastrowid)

    def find_latest_official_player(
        self,
        fide_id: str = "",
        cbx_id: str = "",
        lbx_id: str = "",
    ) -> dict[str, Any] | None:
        conditions = []
        params: list[Any] = []
        if fide_id:
            conditions.append("op.fide_id = ?")
            params.append(fide_id.strip())
        if cbx_id:
            conditions.append("op.cbx_id = ?")
            params.append(cbx_id.strip())
        if lbx_id:
            # A lista LBX guarda o ID_No (registro proprio) em external_id.
            conditions.append("(op.source = 'LBX' AND op.external_id = ?)")
            params.append(lbx_id.strip())
        if not conditions:
            return None
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    op.*,
                    ors.list_date,
                    ors.imported_at,
                    ors.file_name
                FROM official_players op
                JOIN official_rating_snapshots ors ON ors.id = op.snapshot_id
                WHERE {" OR ".join(conditions)}
                ORDER BY ors.imported_at DESC, op.id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            return dict(row) if row else None

    def search_official_players(
        self,
        query: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        value = query.strip()
        if not value:
            return []
        like = f"%{value}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    op.*,
                    ors.list_date,
                    ors.imported_at,
                    ors.file_name
                FROM official_players op
                JOIN official_rating_snapshots ors ON ors.id = op.snapshot_id
                WHERE op.name LIKE ?
                    OR op.fide_id LIKE ?
                    OR op.cbx_id LIKE ?
                    OR op.external_id LIKE ?
                ORDER BY ors.imported_at DESC, op.name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (like, like, like, like, int(limit)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_player_official_data(
        self,
        player_id: int,
        data: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            current = connection.execute(
                "SELECT * FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if not current:
                return

            def pick(field: str) -> Any:
                value = data.get(field)
                if value not in (None, ""):
                    return value
                return current[field]

            def pick_int(field: str) -> int:
                value = data.get(field)
                if value in (None, ""):
                    value = current[field]
                return int(value or 0)

            rating = pick_int("rating")
            national_rating = pick_int("national_rating")
            international_rating = pick_int("international_rating")
            category_payload = self._player_category_payload(
                connection,
                tournament_id=int(current["tournament_id"]),
                member_id=int(current["member_id"] or 0) or None,
                birth_date=pick("birth_date"),
                rating=rating,
                national_rating=national_rating,
                international_rating=international_rating,
                category=current["category"],
                sex=pick("sex"),
                club=pick("club"),
            )

            connection.execute(
                """
                UPDATE players
                SET name = ?, surname = ?, given_name = ?, title = ?, sex = ?,
                    club = ?, federation_id = ?, fide_id = ?, cbx_id = ?, lbx_id = ?,
                    rating = ?, national_rating = ?, international_rating = ?,
                    category = ?, age_category = ?, rating_category = ?,
                    prize_tags = ?, birth_date = ?
                WHERE id = ?
                """,
                (
                    pick("name"),
                    pick("surname"),
                    pick("given_name"),
                    pick("title"),
                    pick("sex"),
                    pick("club"),
                    pick("federation_id"),
                    pick("fide_id"),
                    pick("cbx_id"),
                    pick("lbx_id"),
                    rating,
                    national_rating,
                    international_rating,
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    pick("birth_date"),
                    player_id,
                ),
            )

    def _player_category_payload(
        self,
        connection: sqlite3.Connection,
        *,
        tournament_id: int,
        member_id: int | None,
        birth_date: str,
        rating: int,
        national_rating: int = 0,
        international_rating: int = 0,
        category: str = "",
        sex: str = "",
        club: str = "",
    ) -> dict[str, str]:
        tournament_row = connection.execute(
            "SELECT * FROM tournaments WHERE id = ?",
            (tournament_id,),
        ).fetchone()
        tournament = dict(tournament_row) if tournament_row else {}
        tournament_club: dict[str, Any] = {}
        if tournament.get("club_id"):
            club_row = connection.execute(
                "SELECT * FROM clubs WHERE id = ?",
                (int(tournament["club_id"]),),
            ).fetchone()
            tournament_club = dict(club_row) if club_row else {}

        member: dict[str, Any] = {}
        if member_id:
            member_row = connection.execute(
                "SELECT * FROM members WHERE id = ?",
                (member_id,),
            ).fetchone()
            member = dict(member_row) if member_row else {}

        effective_rating = int(rating or 0) or max(int(national_rating or 0), int(international_rating or 0))
        return competition_category_payload(
            birth_date=birth_date,
            rating=effective_rating,
            category=category,
            year=reference_year(tournament),
            sex=sex,
            member_type=member.get("member_type", ""),
            city=member.get("city", ""),
            player_club=club,
            tournament_location=tournament.get("location", ""),
            tournament_club_name=tournament_club.get("name", ""),
            tournament_club_city=tournament_club.get("city", ""),
        )

    def create_player(
        self,
        tournament_id: int,
        name: str,
        club: str = "",
        rating: int = 0,
        category: str = "",
        federation_id: str = "",
        fide_id: str = "",
        birth_date: str = "",
        member_id: int | None = None,
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        cbx_id: str = "",
        lbx_id: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        player_status: str = "active",
        starting_points: float | None = None,
    ) -> int:
        with self.connect() as connection:
            if starting_points is None:
                starting_points = self._late_entry_starting_points(connection, tournament_id)
            category_payload = self._player_category_payload(
                connection,
                tournament_id=tournament_id,
                member_id=member_id,
                birth_date=birth_date,
                rating=rating,
                national_rating=national_rating,
                international_rating=international_rating,
                category=category,
                sex=sex,
                club=club,
            )
            active = 1 if player_status == "active" else 0
            cursor = connection.execute(
                """
                INSERT INTO players (
                    tournament_id, member_id, name, surname, given_name, title, sex,
                    club, federation_id, fide_id, cbx_id, lbx_id, rating, national_rating,
                    international_rating, category, age_category, rating_category,
                    prize_tags, birth_date, player_status, starting_points, active,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    member_id,
                    name.strip(),
                    surname.strip(),
                    given_name.strip(),
                    title.strip(),
                    sex.strip(),
                    club.strip(),
                    federation_id.strip(),
                    fide_id.strip(),
                    cbx_id.strip(),
                    lbx_id.strip(),
                    int(rating or 0),
                    int(national_rating or 0),
                    int(international_rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    birth_date.strip(),
                    player_status.strip() or "active",
                    float(starting_points or 0.0),
                    active,
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def update_player(
        self,
        player_id: int,
        name: str,
        club: str,
        rating: int,
        category: str,
        active: int,
        federation_id: str = "",
        fide_id: str = "",
        birth_date: str = "",
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        cbx_id: str = "",
        lbx_id: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        player_status: str | None = None,
        starting_points: float | None = None,
    ) -> None:
        status = (player_status or ("active" if active else "inactive")).strip() or "active"
        active_value = 1 if status == "active" else 0
        with self.connect() as connection:
            current = connection.execute(
                "SELECT tournament_id, member_id, starting_points FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            category_payload = self._player_category_payload(
                connection,
                tournament_id=int(current["tournament_id"] if current else 0),
                member_id=int(current["member_id"] or 0) if current else None,
                birth_date=birth_date,
                rating=rating,
                national_rating=national_rating,
                international_rating=international_rating,
                category=category,
                sex=sex,
                club=club,
            )
            points_value = (
                float(starting_points)
                if starting_points is not None
                else float(current["starting_points"] if current else 0.0)
            )
            connection.execute(
                """
                UPDATE players
                SET name = ?, surname = ?, given_name = ?, title = ?, sex = ?,
                    club = ?, federation_id = ?, fide_id = ?, cbx_id = ?, lbx_id = ?,
                    rating = ?, national_rating = ?, international_rating = ?,
                    category = ?, age_category = ?, rating_category = ?,
                    prize_tags = ?, birth_date = ?, player_status = ?,
                    starting_points = ?, active = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    surname.strip(),
                    given_name.strip(),
                    title.strip(),
                    sex.strip(),
                    club.strip(),
                    federation_id.strip(),
                    fide_id.strip(),
                    cbx_id.strip(),
                    lbx_id.strip(),
                    int(rating or 0),
                    int(national_rating or 0),
                    int(international_rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    birth_date.strip(),
                    status,
                    points_value,
                    active_value,
                    player_id,
                ),
            )

    def list_players(
        self,
        tournament_id: int,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        where = "WHERE p.tournament_id = ?"
        params: list[Any] = [tournament_id]
        if active_only:
            where += " AND p.active = 1 AND p.player_status = 'active'"
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    p.*,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM players p
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = p.member_id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                {where}
                ORDER BY p.active DESC, p.rating DESC, p.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_team(
        self,
        tournament_id: int,
        name: str,
        club: str = "",
        captain: str = "",
        notes: str = "",
        active: int = 1,
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO teams (
                    tournament_id, name, club, captain, notes, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    name.strip(),
                    club.strip(),
                    captain.strip(),
                    notes.strip(),
                    int(active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_team(
        self,
        team_id: int,
        name: str,
        club: str = "",
        captain: str = "",
        notes: str = "",
        active: int = 1,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE teams
                SET name = ?, club = ?, captain = ?, notes = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    club.strip(),
                    captain.strip(),
                    notes.strip(),
                    int(active),
                    self.now(),
                    team_id,
                ),
            )

    def get_team(self, team_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tm.*,
                    t.name AS tournament_name,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1
                    ) AS players_count,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1 AND tp.role = 'starter'
                    ) AS starters_count
                FROM teams tm
                JOIN tournaments t ON t.id = tm.tournament_id
                WHERE tm.id = ?
                """,
                (team_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_teams(
        self,
        tournament_id: int,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        active_filter = "AND tm.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tm.*,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1
                    ) AS players_count,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1 AND tp.role = 'starter'
                    ) AS starters_count
                FROM teams tm
                WHERE tm.tournament_id = ?
                {active_filter}
                ORDER BY tm.active DESC, tm.name COLLATE NOCASE ASC, tm.id ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_team(self, team_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM teams
                WHERE id = ?
                """,
                (team_id,),
            )

    def count_team_matches(self, team_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM team_matches
                WHERE white_team_id = ? OR black_team_id = ?
                """,
                (team_id, team_id),
            ).fetchone()
            return int(row["total"] if row else 0)

    def add_player_to_team(
        self,
        team_id: int,
        player_id: int,
        board_number: int | None = None,
        role: str = "starter",
        active: int = 1,
    ) -> int:
        board_value = int(board_number) if board_number and int(board_number) > 0 else None
        role_value = role.strip() or ("reserve" if board_value is None else "starter")
        now = self.now()
        with self.connect() as connection:
            team = connection.execute(
                "SELECT tournament_id FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()
            if not team:
                raise ValueError("Equipe nao encontrada.")

            player = connection.execute(
                "SELECT tournament_id FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if not player:
                raise ValueError("Jogador nao encontrado.")
            if int(team["tournament_id"]) != int(player["tournament_id"]):
                raise ValueError("Jogador nao pertence ao torneio da equipe.")

            cursor = connection.execute(
                """
                INSERT INTO team_players (
                    team_id, player_id, board_number, role, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_id,
                    player_id,
                    board_value,
                    role_value,
                    int(active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_team_player(
        self,
        team_player_id: int,
        board_number: int | None = None,
        role: str = "starter",
        active: int = 1,
    ) -> None:
        board_value = int(board_number) if board_number and int(board_number) > 0 else None
        role_value = role.strip() or ("reserve" if board_value is None else "starter")
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE team_players
                SET board_number = ?, role = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    board_value,
                    role_value,
                    int(active),
                    self.now(),
                    team_player_id,
                ),
            )

    def list_team_players(
        self,
        team_id: int,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        active_filter = "AND tp.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tp.*,
                    p.tournament_id,
                    p.name AS player_name,
                    p.surname AS player_surname,
                    p.given_name AS player_given_name,
                    p.rating AS player_rating,
                    p.club AS player_club,
                    p.category AS player_category,
                    p.age_category AS player_age_category,
                    p.rating_category AS player_rating_category,
                    p.prize_tags AS player_prize_tags,
                    p.player_status
                FROM team_players tp
                JOIN players p ON p.id = tp.player_id
                WHERE tp.team_id = ?
                {active_filter}
                ORDER BY
                    CASE WHEN tp.board_number IS NULL THEN 9999 ELSE tp.board_number END ASC,
                    tp.role ASC,
                    p.rating DESC,
                    p.name COLLATE NOCASE ASC
                """,
                (team_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_team_player(self, team_player_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tp.*,
                    tm.tournament_id,
                    tm.name AS team_name,
                    p.name AS player_name,
                    p.surname AS player_surname,
                    p.given_name AS player_given_name,
                    p.rating AS player_rating,
                    p.club AS player_club
                FROM team_players tp
                JOIN teams tm ON tm.id = tp.team_id
                JOIN players p ON p.id = tp.player_id
                WHERE tp.id = ?
                """,
                (team_player_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_team_player_by_player(self, player_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tp.*,
                    tm.tournament_id,
                    tm.name AS team_name
                FROM team_players tp
                JOIN teams tm ON tm.id = tp.team_id
                WHERE tp.player_id = ?
                """,
                (player_id,),
            ).fetchone()
            return dict(row) if row else None

    def remove_player_from_team(self, team_player_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM team_players
                WHERE id = ?
                """,
                (team_player_id,),
            )

    def get_player(self, player_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    p.*,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM players p
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = p.member_id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE p.id = ?
                """,
                (player_id,),
            ).fetchone()
            return dict(row) if row else None

    def set_player_active(self, player_id: int, active: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE players
                SET active = ?, player_status = ?
                WHERE id = ?
                """,
                (1 if active else 0, "active" if active else "inactive", player_id),
            )

    def set_player_status(self, player_id: int, status: str) -> None:
        status = status.strip() or "active"
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE players
                SET player_status = ?, active = ?
                WHERE id = ?
                """,
                (status, 1 if status == "active" else 0, player_id),
            )

    def count_player_pairings(self, player_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM pairings
                WHERE white_player_id = ? OR black_player_id = ?
                """,
                (player_id, player_id),
            ).fetchone()
            return int(row["total"] if row else 0)

    def delete_player(self, player_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM players
                WHERE id = ?
                """,
                (player_id,),
            )

    def get_pairing(self, pairing_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    p.*,
                    r.tournament_id,
                    r.number AS round_number,
                    r.status AS round_status
                FROM pairings p
                JOIN rounds r ON r.id = p.round_id
                WHERE p.id = ?
                """,
                (pairing_id,),
            ).fetchone()
            return dict(row) if row else None

    def create_round_with_team_matches(
        self,
        tournament_id: int,
        round_number: int,
        matches: list[dict[str, Any]],
        pairing_engine_version: str = "albericus-team-swiss-1",
        ruleset_version: str = "albericus-2026-phase0",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rounds (
                    tournament_id, number, status, pairing_engine_version,
                    ruleset_version, created_at
                )
                VALUES (?, ?, 'generated', ?, ?, ?)
                """,
                (tournament_id, round_number, pairing_engine_version, ruleset_version, now),
            )
            round_id = int(cursor.lastrowid)
            for match in matches:
                match_cursor = connection.execute(
                    """
                    INSERT INTO team_matches (
                        round_id, match_number, white_team_id, black_team_id, result,
                        white_match_points, black_match_points, white_game_points,
                        black_game_points, is_bye, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        int(match["match_number"]),
                        int(match["white_team_id"]),
                        match.get("black_team_id"),
                        str(match.get("result", "")),
                        float(match.get("white_match_points", 0.0) or 0.0),
                        float(match.get("black_match_points", 0.0) or 0.0),
                        float(match.get("white_game_points", 0.0) or 0.0),
                        float(match.get("black_game_points", 0.0) or 0.0),
                        1 if match.get("is_bye") else 0,
                        now,
                        now,
                    ),
                )
                team_match_id = int(match_cursor.lastrowid)
                for board in match.get("boards", []) or []:
                    connection.execute(
                        """
                        INSERT INTO team_boards (
                            team_match_id, board_number, white_player_id, black_player_id,
                            result, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            team_match_id,
                            int(board["board_number"]),
                            board.get("white_player_id"),
                            board.get("black_player_id"),
                            str(board.get("result", "")),
                            now,
                            now,
                        ),
                    )
            return round_id

    def list_team_matches_for_round(self, round_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tm.*,
                    r.tournament_id,
                    r.number AS round_number,
                    r.status AS round_status,
                    white_team.name AS white_team_name,
                    white_team.club AS white_team_club,
                    black_team.name AS black_team_name,
                    black_team.club AS black_team_club
                FROM team_matches tm
                JOIN rounds r ON r.id = tm.round_id
                JOIN teams white_team ON white_team.id = tm.white_team_id
                LEFT JOIN teams black_team ON black_team.id = tm.black_team_id
                WHERE tm.round_id = ?
                ORDER BY tm.match_number ASC
                """,
                (round_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_matches_for_tournament(
        self,
        tournament_id: int,
        closed_only: bool = False,
    ) -> list[dict[str, Any]]:
        status_filter = "AND r.status = 'closed'" if closed_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tm.*,
                    r.number AS round_number,
                    r.status AS round_status,
                    white_team.name AS white_team_name,
                    black_team.name AS black_team_name
                FROM team_matches tm
                JOIN rounds r ON r.id = tm.round_id
                JOIN teams white_team ON white_team.id = tm.white_team_id
                LEFT JOIN teams black_team ON black_team.id = tm.black_team_id
                WHERE r.tournament_id = ?
                {status_filter}
                ORDER BY r.number ASC, tm.match_number ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_boards(self, team_match_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tb.*,
                    white.name AS white_player_name,
                    white.surname AS white_player_surname,
                    white.given_name AS white_player_given_name,
                    white.rating AS white_player_rating,
                    white.club AS white_player_club,
                    white.fide_id AS white_player_fide_id,
                    white.cbx_id AS white_player_cbx_id,
                    white.lbx_id AS white_player_lbx_id,
                    black.name AS black_player_name,
                    black.surname AS black_player_surname,
                    black.given_name AS black_player_given_name,
                    black.rating AS black_player_rating,
                    black.club AS black_player_club,
                    black.fide_id AS black_player_fide_id,
                    black.cbx_id AS black_player_cbx_id,
                    black.lbx_id AS black_player_lbx_id
                FROM team_boards tb
                LEFT JOIN players white ON white.id = tb.white_player_id
                LEFT JOIN players black ON black.id = tb.black_player_id
                WHERE tb.team_match_id = ?
                ORDER BY tb.board_number ASC
                """,
                (team_match_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_team_board(self, team_board_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tb.*,
                    tm.round_id,
                    tm.white_team_id,
                    tm.black_team_id,
                    tm.is_bye,
                    r.tournament_id,
                    r.status AS round_status
                FROM team_boards tb
                JOIN team_matches tm ON tm.id = tb.team_match_id
                JOIN rounds r ON r.id = tm.round_id
                WHERE tb.id = ?
                """,
                (team_board_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_team_board_result(self, team_board_id: int, result: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE team_boards
                SET result = ?, updated_at = ?
                WHERE id = ?
                """,
                (result.strip(), self.now(), team_board_id),
            )

    def swap_team_board_colors(self, team_board_id: int) -> None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT white_player_id, black_player_id
                FROM team_boards
                WHERE id = ?
                """,
                (team_board_id,),
            ).fetchone()
            if not row or row["white_player_id"] is None or row["black_player_id"] is None:
                return
            connection.execute(
                """
                UPDATE team_boards
                SET white_player_id = ?, black_player_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (row["black_player_id"], row["white_player_id"], self.now(), team_board_id),
            )

    def update_team_board_players(
        self,
        updates: list[tuple[int, int | None, int | None]],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                UPDATE team_boards
                SET white_player_id = ?, black_player_id = ?, updated_at = ?
                WHERE id = ?
                """,
                [
                    (white_player_id, black_player_id, self.now(), team_board_id)
                    for team_board_id, white_player_id, black_player_id in updates
                ],
            )

    def create_team_lineups_from_round(self, round_id: int) -> None:
        with self.connect() as connection:
            round_row = connection.execute(
                "SELECT tournament_id, number FROM rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
            if not round_row:
                return
            now = self.now()
            team_players = {
                int(row["player_id"]): {
                    "team_id": int(row["team_id"]),
                    "role": str(row["role"] or "starter"),
                }
                for row in connection.execute(
                    """
                    SELECT tp.team_id, tp.player_id, tp.role
                    FROM team_players tp
                    JOIN teams tm ON tm.id = tp.team_id
                    WHERE tm.tournament_id = ?
                    """,
                    (int(round_row["tournament_id"]),),
                ).fetchall()
            }
            matches = connection.execute(
                """
                SELECT *
                FROM team_matches
                WHERE round_id = ?
                ORDER BY match_number ASC
                """,
                (round_id,),
            ).fetchall()
            for match in matches:
                team_ids = [int(match["white_team_id"])]
                if match["black_team_id"]:
                    team_ids.append(int(match["black_team_id"]))
                lineup_ids: dict[int, int] = {}
                for team_id in team_ids:
                    cursor = connection.execute(
                        """
                        INSERT INTO team_lineups (
                            tournament_id, round_id, team_match_id, team_id,
                            status, submitted_at, approved_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?, ?)
                        ON CONFLICT(round_id, team_match_id, team_id) DO UPDATE SET
                            status = excluded.status,
                            approved_at = excluded.approved_at,
                            updated_at = excluded.updated_at
                        """,
                        (
                            int(round_row["tournament_id"]),
                            int(round_id),
                            int(match["id"]),
                            team_id,
                            now,
                            now,
                            now,
                            now,
                        ),
                    )
                    lineup_row = connection.execute(
                        """
                        SELECT id
                        FROM team_lineups
                        WHERE round_id = ? AND team_match_id = ? AND team_id = ?
                        """,
                        (int(round_id), int(match["id"]), team_id),
                    ).fetchone()
                    lineup_ids[team_id] = int(lineup_row["id"] if lineup_row else cursor.lastrowid)
                    connection.execute("DELETE FROM team_lineup_boards WHERE lineup_id = ?", (lineup_ids[team_id],))

                boards = connection.execute(
                    """
                    SELECT *
                    FROM team_boards
                    WHERE team_match_id = ?
                    ORDER BY board_number ASC
                    """,
                    (int(match["id"]),),
                ).fetchall()
                for board in boards:
                    for color, player_id in (
                        ("white", board["white_player_id"]),
                        ("black", board["black_player_id"]),
                    ):
                        if not player_id:
                            continue
                        assignment = team_players.get(int(player_id))
                        if not assignment or assignment["team_id"] not in lineup_ids:
                            continue
                        connection.execute(
                            """
                            INSERT INTO team_lineup_boards (
                                lineup_id, board_number, player_id, color, role, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                lineup_ids[assignment["team_id"]],
                                int(board["board_number"]),
                                int(player_id),
                                color,
                                assignment["role"],
                                now,
                            ),
                        )

    def list_team_lineups(self, tournament_id: int, round_id: int | None = None) -> list[dict[str, Any]]:
        conditions = ["tl.tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            conditions.append("tl.round_id = ?")
            params.append(int(round_id))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tl.*,
                    r.number AS round_number,
                    tm.match_number,
                    t.name AS team_name,
                    t.club AS team_club
                FROM team_lineups tl
                JOIN rounds r ON r.id = tl.round_id
                JOIN team_matches tm ON tm.id = tl.team_match_id
                JOIN teams t ON t.id = tl.team_id
                WHERE {' AND '.join(conditions)}
                ORDER BY r.number ASC, tm.match_number ASC, t.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_lineup_boards(self, lineup_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tlb.*,
                    p.name AS player_name,
                    p.surname AS player_surname,
                    p.given_name AS player_given_name,
                    p.rating AS player_rating
                FROM team_lineup_boards tlb
                LEFT JOIN players p ON p.id = tlb.player_id
                WHERE tlb.lineup_id = ?
                ORDER BY tlb.board_number ASC
                """,
                (int(lineup_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def replace_team_lineup_board_player(
        self,
        round_id: int,
        team_match_id: int,
        team_id: int,
        board_number: int,
        player_id: int,
        color: str,
    ) -> None:
        with self.connect() as connection:
            lineup = connection.execute(
                """
                SELECT id
                FROM team_lineups
                WHERE round_id = ? AND team_match_id = ? AND team_id = ?
                """,
                (int(round_id), int(team_match_id), int(team_id)),
            ).fetchone()
            if not lineup:
                return
            connection.execute(
                """
                INSERT INTO team_lineup_boards (
                    lineup_id, board_number, player_id, color, role, created_at
                ) VALUES (?, ?, ?, ?, 'reserve', ?)
                ON CONFLICT(lineup_id, board_number) DO UPDATE SET
                    player_id = excluded.player_id,
                    color = excluded.color,
                    role = excluded.role
                """,
                (int(lineup["id"]), int(board_number), int(player_id), color, self.now()),
            )

    def create_team_substitution_event(
        self,
        tournament_id: int,
        round_id: int,
        team_match_id: int,
        team_board_id: int,
        team_id: int,
        board_number: int,
        color: str,
        out_player_id: int | None,
        in_player_id: int,
        reason: str = "",
        requires_correction: bool = False,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO team_substitution_events (
                    tournament_id, round_id, team_match_id, team_board_id, team_id,
                    board_number, color, out_player_id, in_player_id, reason,
                    requires_correction, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    int(team_match_id),
                    int(team_board_id),
                    int(team_id),
                    int(board_number),
                    color,
                    out_player_id,
                    int(in_player_id),
                    reason.strip(),
                    1 if requires_correction else 0,
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_team_substitution_events(self, tournament_id: int, round_id: int | None = None) -> list[dict[str, Any]]:
        conditions = ["tse.tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            conditions.append("tse.round_id = ?")
            params.append(int(round_id))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tse.*,
                    r.number AS round_number,
                    tm.match_number,
                    team.name AS team_name,
                    out_player.name AS out_player_name,
                    in_player.name AS in_player_name
                FROM team_substitution_events tse
                JOIN rounds r ON r.id = tse.round_id
                JOIN team_matches tm ON tm.id = tse.team_match_id
                JOIN teams team ON team.id = tse.team_id
                LEFT JOIN players out_player ON out_player.id = tse.out_player_id
                JOIN players in_player ON in_player.id = tse.in_player_id
                WHERE {' AND '.join(conditions)}
                ORDER BY tse.created_at ASC, tse.id ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def add_point_adjustment(
        self,
        tournament_id: int,
        *,
        round_number: int = 0,
        player_id: int | None = None,
        team_id: int | None = None,
        aat_type: str = "",
        match_points: float = 0.0,
        game_points: float = 0.0,
        reason: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO point_adjustments (
                    tournament_id, round_number, player_id, team_id,
                    aat_type, match_points, game_points, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(round_number or 0),
                    int(player_id) if player_id else None,
                    int(team_id) if team_id else None,
                    str(aat_type or "").strip(),
                    float(match_points or 0.0),
                    float(game_points or 0.0),
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_point_adjustments(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pa.*, p.name AS player_name, t.name AS team_name
                FROM point_adjustments pa
                LEFT JOIN players p ON p.id = pa.player_id
                LEFT JOIN teams t ON t.id = pa.team_id
                WHERE pa.tournament_id = ?
                ORDER BY pa.round_number ASC, pa.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_point_adjustment(self, adjustment_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM point_adjustments WHERE id = ?", (int(adjustment_id),)
            )

    def add_prohibited_pairing(
        self,
        tournament_id: int,
        player_a_id: int,
        player_b_id: int,
        *,
        first_round: int = 1,
        last_round: int = 0,
        reason: str = "",
    ) -> int:
        """Registra uma proibição de pareamento entre dois jogadores.

        `last_round=0` significa "até a última rodada" (proibição aberta)."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO prohibited_pairings (
                    tournament_id, player_a_id, player_b_id,
                    first_round, last_round, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(player_a_id),
                    int(player_b_id),
                    int(first_round or 1),
                    int(last_round or 0),
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_prohibited_pairings(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pp.*, pa.name AS player_a_name, pb.name AS player_b_name
                FROM prohibited_pairings pp
                LEFT JOIN players pa ON pa.id = pp.player_a_id
                LEFT JOIN players pb ON pb.id = pp.player_b_id
                WHERE pp.tournament_id = ?
                ORDER BY pp.first_round ASC, pp.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_prohibited_pairing(self, prohibition_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM prohibited_pairings WHERE id = ?", (int(prohibition_id),)
            )

    def add_prohibited_team_pairing(
        self,
        tournament_id: int,
        team_a_id: int,
        team_b_id: int,
        *,
        first_round: int = 1,
        last_round: int = 0,
        reason: str = "",
    ) -> int:
        """Registra uma proibição de pareamento entre duas equipes.

        `last_round=0` significa "até a última rodada" (proibição aberta)."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO prohibited_team_pairings (
                    tournament_id, team_a_id, team_b_id,
                    first_round, last_round, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(team_a_id),
                    int(team_b_id),
                    int(first_round or 1),
                    int(last_round or 0),
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_prohibited_team_pairings(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pp.*, ta.name AS team_a_name, tb.name AS team_b_name
                FROM prohibited_team_pairings pp
                LEFT JOIN teams ta ON ta.id = pp.team_a_id
                LEFT JOIN teams tb ON tb.id = pp.team_b_id
                WHERE pp.tournament_id = ?
                ORDER BY pp.first_round ASC, pp.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_prohibited_team_pairing(self, prohibition_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM prohibited_team_pairings WHERE id = ?", (int(prohibition_id),)
            )

    def add_requested_bye(
        self,
        tournament_id: int,
        player_id: int,
        round_number: int,
        bye_type: str = "H",
        *,
        reason: str = "",
    ) -> int:
        """Registra um bye solicitado (F/H/Z) de um jogador numa rodada.

        Sobrescreve o tipo caso já exista solicitação para o mesmo jogador/rodada."""
        normalized = str(bye_type or "H").strip().upper()
        if normalized not in {"F", "H", "Z"}:
            raise ValueError("Tipo de bye inválido (use F, H ou Z).")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO requested_byes (
                    tournament_id, player_id, round_number, bye_type, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tournament_id, player_id, round_number)
                DO UPDATE SET bye_type = excluded.bye_type, reason = excluded.reason
                """,
                (
                    int(tournament_id),
                    int(player_id),
                    int(round_number),
                    normalized,
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_requested_byes(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, p.name AS player_name
                FROM requested_byes rb
                LEFT JOIN players p ON p.id = rb.player_id
                WHERE rb.tournament_id = ?
                ORDER BY rb.round_number ASC, rb.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_requested_byes_for_round(
        self, tournament_id: int, round_number: int
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, p.name AS player_name
                FROM requested_byes rb
                LEFT JOIN players p ON p.id = rb.player_id
                WHERE rb.tournament_id = ? AND rb.round_number = ?
                ORDER BY rb.id ASC
                """,
                (int(tournament_id), int(round_number)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_requested_bye(self, requested_bye_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM requested_byes WHERE id = ?", (int(requested_bye_id),)
            )

    def add_requested_team_bye(
        self,
        tournament_id: int,
        team_id: int,
        round_number: int,
        bye_type: str = "H",
        *,
        reason: str = "",
    ) -> int:
        """Registra um bye solicitado (F/H/Z) de uma equipe numa rodada.

        Sobrescreve o tipo caso já exista solicitação para a mesma equipe/rodada."""
        normalized = str(bye_type or "H").strip().upper()
        if normalized not in {"F", "H", "Z"}:
            raise ValueError("Tipo de bye inválido (use F, H ou Z).")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO requested_team_byes (
                    tournament_id, team_id, round_number, bye_type, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tournament_id, team_id, round_number)
                DO UPDATE SET bye_type = excluded.bye_type, reason = excluded.reason
                """,
                (
                    int(tournament_id),
                    int(team_id),
                    int(round_number),
                    normalized,
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_requested_team_byes(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, t.name AS team_name
                FROM requested_team_byes rb
                LEFT JOIN teams t ON t.id = rb.team_id
                WHERE rb.tournament_id = ?
                ORDER BY rb.round_number ASC, rb.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_requested_team_byes_for_round(
        self, tournament_id: int, round_number: int
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, t.name AS team_name
                FROM requested_team_byes rb
                LEFT JOIN teams t ON t.id = rb.team_id
                WHERE rb.tournament_id = ? AND rb.round_number = ?
                ORDER BY rb.id ASC
                """,
                (int(tournament_id), int(round_number)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_requested_team_bye(self, requested_bye_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM requested_team_byes WHERE id = ?", (int(requested_bye_id),)
            )

    def update_team_match_summary(
        self,
        team_match_id: int,
        result: str,
        white_match_points: float,
        black_match_points: float,
        white_game_points: float,
        black_game_points: float,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE team_matches
                SET result = ?, white_match_points = ?, black_match_points = ?,
                    white_game_points = ?, black_game_points = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    result.strip(),
                    float(white_match_points),
                    float(black_match_points),
                    float(white_game_points),
                    float(black_game_points),
                    self.now(),
                    team_match_id,
                ),
            )

    def create_round_with_pairings(
        self,
        tournament_id: int,
        round_number: int,
        pairings: list[dict[str, Any]],
        pairing_engine_version: str = "albericus-swiss-1",
        ruleset_version: str = "albericus-2026-phase0",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rounds (
                    tournament_id, number, status, pairing_engine_version,
                    ruleset_version, created_at
                )
                VALUES (?, ?, 'generated', ?, ?, ?)
                """,
                (tournament_id, round_number, pairing_engine_version, ruleset_version, self.now()),
            )
            round_id = int(cursor.lastrowid)
            for pairing in pairings:
                connection.execute(
                    """
                    INSERT INTO pairings (
                        round_id, board_number, white_player_id, black_player_id,
                        result, is_bye, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        pairing["board_number"],
                        pairing["white_player_id"],
                        pairing.get("black_player_id"),
                        pairing.get("result", ""),
                        1 if pairing.get("is_bye") else 0,
                        self.now(),
                    ),
                )
            return round_id

    def list_rounds(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM rounds
                WHERE tournament_id = ?
                ORDER BY number DESC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_round_by_number(
        self,
        tournament_id: int,
        round_number: int,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM rounds
                WHERE tournament_id = ? AND number = ?
                """,
                (tournament_id, round_number),
            ).fetchone()
            return dict(row) if row else None

    def get_round(self, round_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_latest_round(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM rounds
                WHERE tournament_id = ?
                ORDER BY number DESC
                LIMIT 1
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_pairings_for_round(self, round_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.*,
                    white.name AS white_name,
                    white.surname AS white_surname,
                    white.given_name AS white_given_name,
                    white.rating AS white_rating,
                    white.club AS white_club,
                    white.fide_id AS white_fide_id,
                    white.cbx_id AS white_cbx_id,
                    white.lbx_id AS white_lbx_id,
                    black.name AS black_name,
                    black.surname AS black_surname,
                    black.given_name AS black_given_name,
                    black.rating AS black_rating,
                    black.club AS black_club,
                    black.fide_id AS black_fide_id,
                    black.cbx_id AS black_cbx_id,
                    black.lbx_id AS black_lbx_id
                FROM pairings p
                JOIN players white ON white.id = p.white_player_id
                LEFT JOIN players black ON black.id = p.black_player_id
                WHERE p.round_id = ?
                ORDER BY p.board_number ASC
                """,
                (round_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_pairings_for_tournament(
        self,
        tournament_id: int,
        closed_only: bool = False,
    ) -> list[dict[str, Any]]:
        status_filter = "AND r.status = 'closed'" if closed_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    p.*,
                    r.number AS round_number,
                    r.status AS round_status
                FROM pairings p
                JOIN rounds r ON r.id = p.round_id
                WHERE r.tournament_id = ?
                {status_filter}
                ORDER BY r.number ASC, p.board_number ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_pairing_result(self, pairing_id: int, result: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE pairings SET result = ? WHERE id = ?",
                (result, pairing_id),
            )

    def swap_pairing_colors(self, pairing_id: int) -> None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT white_player_id, black_player_id, is_bye
                FROM pairings
                WHERE id = ?
                """,
                (pairing_id,),
            ).fetchone()
            if not row or row["is_bye"] or row["black_player_id"] is None:
                return
            connection.execute(
                """
                UPDATE pairings
                SET white_player_id = ?, black_player_id = ?
                WHERE id = ?
                """,
                (row["black_player_id"], row["white_player_id"], pairing_id),
            )

    def update_pairing_players(
        self,
        updates: list[tuple[int, int, int | None]],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                UPDATE pairings
                SET white_player_id = ?, black_player_id = ?
                WHERE id = ?
                """,
                [
                    (white_player_id, black_player_id, pairing_id)
                    for pairing_id, white_player_id, black_player_id in updates
                ],
            )

    def close_round(self, round_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE rounds
                SET status = 'closed',
                    closed_at = CASE WHEN closed_at = '' THEN ? ELSE closed_at END
                WHERE id = ?
                """,
                (self.now(), round_id),
            )

    def delete_round(self, round_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM rounds WHERE id = ?", (round_id,))

    def _ensure_tournament_settings(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO tournament_settings (tournament_id, updated_at)
            VALUES (?, ?)
            """,
            (tournament_id, self.now()),
        )

    def _ensure_round_schedule(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
        rounds_count: int,
    ) -> None:
        now = self.now()
        for round_number in range(1, max(rounds_count, 0) + 1):
            connection.execute(
                """
                INSERT OR IGNORE INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, '', '', ?)
                """,
                (tournament_id, round_number, now),
            )

    def _late_entry_starting_points(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
    ) -> float:
        settings = connection.execute(
            """
            SELECT late_entry_points
            FROM tournament_settings
            WHERE tournament_id = ?
            """,
            (tournament_id,),
        ).fetchone()
        if not settings or not float(settings["late_entry_points"] or 0):
            return 0.0
        closed_rounds = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM rounds
            WHERE tournament_id = ? AND status = 'closed'
            """,
            (tournament_id,),
        ).fetchone()
        return round(float(settings["late_entry_points"] or 0) * int(closed_rounds["total"] or 0), 2)
