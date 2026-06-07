from __future__ import annotations

import hashlib
import os
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from src.core import database as database_module
from src.core.database import APP_DATA_DIR_ENV_VAR, Database, resolve_app_data_dir
from src.core.services import (
    SecurityService,
)
from tests.support.core_service_base import CoreServiceTestCase


class DatabaseMigrationsTest(CoreServiceTestCase):
    def test_user_data_path_resolver_supports_env_and_platform_defaults(self) -> None:
        base_path = Path(self.temp_dir.name)

        self.assertEqual(
            resolve_app_data_dir(
                {APP_DATA_DIR_ENV_VAR: str(base_path / "custom")},
                platform="win32",
                home=base_path / "home",
            ),
            base_path / "custom",
        )
        self.assertEqual(
            resolve_app_data_dir(
                {"LOCALAPPDATA": str(base_path / "local")},
                platform="win32",
                home=base_path / "home",
            ),
            base_path / "local" / "Albericus",
        )
        self.assertEqual(
            resolve_app_data_dir(
                {"XDG_DATA_HOME": str(base_path / "xdg")},
                platform="linux",
                home=base_path / "home",
            ),
            base_path / "xdg" / "Albericus",
        )
        self.assertEqual(
            resolve_app_data_dir({}, platform="darwin", home=base_path / "home"),
            base_path / "home" / "Library" / "Application Support" / "Albericus",
        )

    def test_default_database_uses_user_data_dir_and_copies_legacy_database(self) -> None:
        base_path = Path(self.temp_dir.name)
        legacy_db_path = base_path / "legacy" / "data" / "albericus.db"
        legacy_backup_dir = base_path / "legacy" / "backups"
        legacy_db = Database(legacy_db_path, backup_dir=legacy_backup_dir)
        legacy_db.create_tournament("Torneio legado")
        legacy_backup_path = legacy_db.backup("manual")

        user_data_dir = base_path / "user-data"
        with (
            mock.patch.dict(os.environ, {APP_DATA_DIR_ENV_VAR: str(user_data_dir)}),
            mock.patch.object(database_module, "LEGACY_DB_PATH", legacy_db_path),
            mock.patch.object(database_module, "LEGACY_BACKUP_DIR", legacy_backup_dir),
        ):
            migrated_db = Database()

        self.assertEqual(migrated_db.db_path, user_data_dir / "data" / "albericus.db")
        self.assertEqual(migrated_db.backup_dir, user_data_dir / "backups")
        self.assertTrue(migrated_db.db_path.exists())
        self.assertTrue((migrated_db.backup_dir / legacy_backup_path.name).exists())
        self.assertTrue(
            any(tournament["name"] == "Torneio legado" for tournament in migrated_db.list_tournaments())
        )

    def test_database_schema_version_and_pairing_indexes_exist(self) -> None:
        with self.db.connect() as connection:
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            tournament_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tournaments)").fetchall()
            }
            settings_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            round_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(rounds)").fetchall()
            }
            member_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(members)").fetchall()
            }
            training_session_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(training_sessions)").fetchall()
            }
            pairing_indexes = {
                row["name"]
                for row in connection.execute("PRAGMA index_list(pairings)").fetchall()
            }
            learning_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'learning_levels'
                    """
                ).fetchall()
            }
            learning_indexes = {
                row["name"]
                for row in connection.execute("PRAGMA index_list(learning_levels)").fetchall()
            }
            team_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'teams', 'team_players', 'team_matches', 'team_boards',
                            'team_lineups', 'team_lineup_boards', 'team_substitution_events'
                        )
                    """
                ).fetchall()
            }
            team_indexes = {
                row["name"]
                for table_name in (
                    "teams", "team_players", "team_matches", "team_boards",
                    "team_lineups", "team_lineup_boards", "team_substitution_events"
                )
                for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            certificate_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN ('certificate_templates', 'certificate_issuances')
                    """
                ).fetchall()
            }
            certificate_indexes = {
                row["name"]
                for table_name in ("certificate_templates", "certificate_issuances")
                for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            exercise_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'exercise_library',
                            'training_lists',
                            'training_list_exercises',
                            'exercise_attempts'
                        )
                    """
                ).fetchall()
            }
            exercise_indexes = {
                row["name"]
                for table_name in (
                    "exercise_library",
                    "training_lists",
                    "training_list_exercises",
                    "exercise_attempts",
                    "training_sessions",
                )
                for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            inventory_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'inventory_items',
                            'inventory_loans',
                            'inventory_maintenance'
                        )
                    """
                ).fetchall()
            }
            inventory_indexes = {
                row["name"]
                for table_name in ("inventory_items", "inventory_loans", "inventory_maintenance")
                for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            audit_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'audit_log'
                """
            ).fetchone()
            phase0_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'audit_events', 'pairing_snapshots', 'standings_snapshots',
                            'tiebreak_components', 'public_tokens', 'result_submissions'
                        )
                    """
                ).fetchall()
            }
            audit_indexes = {
                row["name"]
                for row in connection.execute("PRAGMA index_list(audit_log)").fetchall()
            }
            phase0_indexes = {
                row["name"]
                for table_name in (
                    "audit_events", "pairing_snapshots", "standings_snapshots",
                    "tiebreak_components", "public_tokens", "result_submissions"
                )
                for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            integration_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN ('devices', 'sync_outbox', 'clock_events')
                    """
                ).fetchall()
            }
            integration_indexes = {
                row["name"]
                for table_name in ("devices", "sync_outbox", "clock_events")
                for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            certificate_template_count = connection.execute(
                "SELECT COUNT(*) FROM certificate_templates"
            ).fetchone()[0]
            certificate_template_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(certificate_templates)").fetchall()
            }

        self.assertEqual(user_version, Database.SCHEMA_VERSION)
        self.assertIn("competition_type", tournament_columns)
        self.assertIn("tournament_profile", settings_columns)
        self.assertIn("pairing_system", settings_columns)
        self.assertIn("acceleration_method", settings_columns)
        self.assertIn("team_boards_count", settings_columns)
        self.assertIn("team_match_win_points", settings_columns)
        self.assertIn("team_standing_primary", settings_columns)
        self.assertIn("team_standing_secondary", settings_columns)
        self.assertIn("team_board_order_policy", settings_columns)
        self.assertIn("team_reserve_policy", settings_columns)
        self.assertIn("team_lineup_deadline", settings_columns)
        self.assertIn("team_max_substitutions", settings_columns)
        self.assertIn("rating_fee_fide", settings_columns)
        self.assertIn("rating_fee_cbx", settings_columns)
        self.assertIn("rating_fee_lbx", settings_columns)
        self.assertIn("learning_level_id", member_columns)
        self.assertIn("training_list_id", training_session_columns)
        self.assertIn("pairing_engine_version", round_columns)
        self.assertIn("ruleset_version", round_columns)
        self.assertIn("closed_at", round_columns)
        self.assertEqual({"learning_levels"}, learning_tables)
        self.assertIn("idx_learning_levels_order", learning_indexes)
        self.assertIn("idx_pairings_white_player", pairing_indexes)
        self.assertIn("idx_pairings_black_player", pairing_indexes)
        self.assertEqual(
            {
                "teams", "team_players", "team_matches", "team_boards",
                "team_lineups", "team_lineup_boards", "team_substitution_events",
            },
            team_tables,
        )
        self.assertIn("idx_teams_tournament", team_indexes)
        self.assertIn("idx_team_matches_round", team_indexes)
        self.assertIn("idx_team_lineups_round", team_indexes)
        self.assertIn("idx_team_substitutions_round", team_indexes)
        self.assertEqual({"certificate_templates", "certificate_issuances"}, certificate_tables)
        self.assertIn("idx_certificate_templates_type", certificate_indexes)
        self.assertIn("idx_certificate_issuances_context", certificate_indexes)
        self.assertEqual(
            {"exercise_library", "training_lists", "training_list_exercises", "exercise_attempts"},
            exercise_tables,
        )
        self.assertIn("idx_exercise_library_filters", exercise_indexes)
        self.assertIn("idx_training_lists_filters", exercise_indexes)
        self.assertIn("idx_training_sessions_training_list", exercise_indexes)
        self.assertIn("idx_exercise_attempts_member", exercise_indexes)
        self.assertEqual({"inventory_items", "inventory_loans", "inventory_maintenance"}, inventory_tables)
        self.assertIn("idx_inventory_items_filters", inventory_indexes)
        self.assertIn("idx_inventory_loans_item", inventory_indexes)
        self.assertIn("idx_inventory_maintenance_item", inventory_indexes)
        self.assertIsNotNone(audit_table)
        self.assertEqual(
            {
                "audit_events", "pairing_snapshots", "standings_snapshots",
                "tiebreak_components", "public_tokens", "result_submissions",
            },
            phase0_tables,
        )
        self.assertIn("idx_audit_log_created", audit_indexes)
        self.assertIn("idx_audit_log_entity", audit_indexes)
        self.assertIn("idx_audit_events_tournament", phase0_indexes)
        self.assertIn("idx_pairing_snapshots_round", phase0_indexes)
        self.assertIn("idx_standings_snapshots_round", phase0_indexes)
        self.assertIn("idx_tiebreak_components_player", phase0_indexes)
        self.assertIn("idx_public_tokens_hash", phase0_indexes)
        self.assertIn("idx_result_submissions_status", phase0_indexes)
        self.assertEqual({"devices", "sync_outbox", "clock_events"}, integration_tables)
        self.assertIn("idx_devices_status", integration_indexes)
        self.assertIn("idx_sync_outbox_status", integration_indexes)
        self.assertIn("idx_clock_events_tournament", integration_indexes)
        self.assertGreaterEqual(certificate_template_count, 7)
        self.assertIn("logo_path", certificate_template_columns)
        self.assertIn("background_image_path", certificate_template_columns)
        self.assertIn("background_opacity", certificate_template_columns)
        self.assertIn("secondary_logo_path", certificate_template_columns)
        self.assertIn("primary_color", certificate_template_columns)
        self.assertIn("accent_color", certificate_template_columns)
        self.assertIn("title_font_size", certificate_template_columns)

    def test_v35_database_adds_tiebreak_sequence_columns(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v35_tiebreaks.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE tournament_settings (
                    tournament_id INTEGER PRIMARY KEY,
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                INSERT INTO tournament_settings (tournament_id, updated_at)
                VALUES (1, '2026-06-01 00:00:00');
                PRAGMA user_version = 34;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("tiebreak_sequence", columns)
        self.assertIn("team_tiebreak_sequence", columns)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v36_database_adds_fide_rating_schema(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v36_fide.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER,
                    name TEXT NOT NULL
                );
                PRAGMA user_version = 35;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            player_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(players)").fetchall()
            }
            tables = {
                row["name"]
                for row in migrated_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("k_factor", player_columns)
        self.assertIn("fide_rating_reports", tables)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v37_database_adds_prize_schema(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v37_prizes.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE tournament_settings (
                    tournament_id INTEGER PRIMARY KEY,
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                INSERT INTO tournament_settings (tournament_id, updated_at)
                VALUES (1, '2026-06-01 00:00:00');
                PRAGMA user_version = 36;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            settings_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            tables = {
                row["name"]
                for row in migrated_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("prize_policy", settings_columns)
        self.assertIn("prize_tax_percent", settings_columns)
        self.assertIn("tournament_prizes", tables)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v38_database_adds_report_layouts(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v38_layouts.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript("PRAGMA user_version = 37;")
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            tables = {
                row["name"]
                for row in migrated_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("report_layouts", tables)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v40_database_adds_scheveningen_group_column(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v40_schev.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER,
                    name TEXT NOT NULL
                );
                PRAGMA user_version = 39;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(players)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("scheveningen_group", columns)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v39_database_adds_parent_tournament_column(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v39_split.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    club_id INTEGER,
                    class_id INTEGER,
                    created_at TEXT
                );
                PRAGMA user_version = 38;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournaments)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("parent_tournament_id", columns)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_existing_database_gets_member_column_on_initialize(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    location TEXT DEFAULT '',
                    start_date TEXT DEFAULT '',
                    end_date TEXT DEFAULT '',
                    system TEXT NOT NULL DEFAULT 'Suico',
                    rounds_count INTEGER NOT NULL DEFAULT 5,
                    time_control TEXT DEFAULT '',
                    bye_points REAL NOT NULL DEFAULT 1.0,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    club TEXT DEFAULT '',
                    federation_id TEXT DEFAULT '',
                    fide_id TEXT DEFAULT '',
                    rating INTEGER NOT NULL DEFAULT 0,
                    category TEXT DEFAULT '',
                    birth_date TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(players)").fetchall()
            }
            club_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(clubs)").fetchall()
            }
            member_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(members)").fetchall()
            }
            tournament_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournaments)").fetchall()
            }
            settings_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            settings_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'tournament_settings'
                """
            ).fetchone()
            schedule_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'round_schedule'
                """
            ).fetchone()
            official_snapshots_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'official_rating_snapshots'
                """
            ).fetchone()
            official_players_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'official_players'
                """
            ).fetchone()
            internal_rating_history_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'internal_rating_history'
                """
            ).fetchone()
            app_settings_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'app_settings'
                """
            ).fetchone()
            audit_log_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'audit_log'
                """
            ).fetchone()
            classes_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'classes'
                """
            ).fetchone()
            enrollments_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'member_class_enrollments'
                """
            ).fetchone()
            guardians_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'guardians'
                """
            ).fetchone()
            member_guardians_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'member_guardians'
                """
            ).fetchone()
            learning_levels_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'learning_levels'
                """
            ).fetchone()
            learning_levels_count = migrated_connection.execute(
                "SELECT COUNT(*) FROM learning_levels"
            ).fetchone()[0]
            training_sessions_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'training_sessions'
                """
            ).fetchone()
            training_session_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(training_sessions)").fetchall()
            }
            exercise_library_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'exercise_library'
                """
            ).fetchone()
            training_lists_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'training_lists'
                """
            ).fetchone()
            training_list_exercises_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'training_list_exercises'
                """
            ).fetchone()
            exercise_attempts_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'exercise_attempts'
                """
            ).fetchone()
            attendance_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'attendance'
                """
            ).fetchone()
            membership_plans_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'membership_plans'
                """
            ).fetchone()
            payments_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'payments'
                """
            ).fetchone()
            club_events_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'club_events'
                """
            ).fetchone()
            inventory_items_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'inventory_items'
                """
            ).fetchone()
            inventory_loans_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'inventory_loans'
                """
            ).fetchone()
            inventory_maintenance_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'inventory_maintenance'
                """
            ).fetchone()
            teams_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'teams'
                """
            ).fetchone()
            team_players_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_players'
                """
            ).fetchone()
            team_matches_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_matches'
                """
            ).fetchone()
            team_boards_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_boards'
                """
            ).fetchone()
            team_lineups_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_lineups'
                """
            ).fetchone()
            team_lineup_boards_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_lineup_boards'
                """
            ).fetchone()
            team_substitution_events_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'team_substitution_events'
                """
            ).fetchone()
            certificate_templates_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'certificate_templates'
                """
            ).fetchone()
            certificate_issuances_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'certificate_issuances'
                """
            ).fetchone()
            certificate_templates_count = migrated_connection.execute(
                "SELECT COUNT(*) FROM certificate_templates"
            ).fetchone()[0]
            certificate_template_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(certificate_templates)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("member_id", columns)
        self.assertIn("cbx_id", columns)
        self.assertIn("lbx_id", columns)
        self.assertIn("national_rating", columns)
        self.assertIn("international_rating", columns)
        self.assertIn("player_status", columns)
        self.assertIn("starting_points", columns)
        self.assertIn("age_category", columns)
        self.assertIn("rating_category", columns)
        self.assertIn("prize_tags", columns)
        self.assertIn("kind", club_columns)
        self.assertIn("active", club_columns)
        self.assertIn("surname", member_columns)
        self.assertIn("age_category", member_columns)
        self.assertIn("rating_category", member_columns)
        self.assertIn("prize_tags", member_columns)
        self.assertIn("learning_level_id", member_columns)
        self.assertIn("club_id", tournament_columns)
        self.assertIn("class_id", tournament_columns)
        self.assertIn("competition_type", tournament_columns)
        self.assertIn("tournament_profile", settings_columns)
        self.assertIn("team_boards_count", settings_columns)
        self.assertIn("team_match_win_points", settings_columns)
        self.assertIn("team_match_draw_points", settings_columns)
        self.assertIn("team_match_loss_points", settings_columns)
        self.assertIn("team_pairing_method", settings_columns)
        self.assertIn("team_standing_primary", settings_columns)
        self.assertIn("team_standing_secondary", settings_columns)
        self.assertIn("team_fixed_board_order", settings_columns)
        self.assertIn("team_board_order_policy", settings_columns)
        self.assertIn("team_reserve_policy", settings_columns)
        self.assertIn("team_lineup_deadline", settings_columns)
        self.assertIn("team_max_substitutions", settings_columns)
        self.assertIsNotNone(settings_table)
        self.assertIsNotNone(schedule_table)
        self.assertIsNotNone(official_snapshots_table)
        self.assertIsNotNone(official_players_table)
        self.assertIsNotNone(internal_rating_history_table)
        self.assertIsNotNone(app_settings_table)
        self.assertIsNotNone(audit_log_table)
        self.assertIsNotNone(classes_table)
        self.assertIsNotNone(enrollments_table)
        self.assertIsNotNone(guardians_table)
        self.assertIsNotNone(member_guardians_table)
        self.assertIsNotNone(learning_levels_table)
        self.assertGreaterEqual(learning_levels_count, 5)
        self.assertIsNotNone(training_sessions_table)
        self.assertIn("training_list_id", training_session_columns)
        self.assertIn("learning_level_id", training_session_columns)
        self.assertIn("objective", training_session_columns)
        self.assertIn("content", training_session_columns)
        self.assertIn("homework", training_session_columns)
        self.assertIsNotNone(exercise_library_table)
        self.assertIsNotNone(training_lists_table)
        self.assertIsNotNone(training_list_exercises_table)
        self.assertIsNotNone(exercise_attempts_table)
        self.assertIsNotNone(attendance_table)
        self.assertIsNotNone(membership_plans_table)
        self.assertIsNotNone(payments_table)
        self.assertIsNotNone(club_events_table)
        self.assertIsNotNone(inventory_items_table)
        self.assertIsNotNone(inventory_loans_table)
        self.assertIsNotNone(inventory_maintenance_table)
        self.assertIsNotNone(teams_table)
        self.assertIsNotNone(team_players_table)
        self.assertIsNotNone(team_matches_table)
        self.assertIsNotNone(team_boards_table)
        self.assertIsNotNone(team_lineups_table)
        self.assertIsNotNone(team_lineup_boards_table)
        self.assertIsNotNone(team_substitution_events_table)
        self.assertIsNotNone(certificate_templates_table)
        self.assertIsNotNone(certificate_issuances_table)
        self.assertGreaterEqual(certificate_templates_count, 7)
        self.assertIn("logo_path", certificate_template_columns)
        self.assertIn("background_image_path", certificate_template_columns)
        self.assertIn("background_opacity", certificate_template_columns)
        self.assertIn("secondary_logo_path", certificate_template_columns)
        self.assertIn("primary_color", certificate_template_columns)
        self.assertIn("title_font_size", certificate_template_columns)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v3_database_adds_learning_level_column_before_indexes(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v3.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_id INTEGER DEFAULT 1,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    surname TEXT DEFAULT '',
                    age_category TEXT DEFAULT '',
                    rating_category TEXT DEFAULT '',
                    prize_tags TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                PRAGMA user_version = 3;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            member_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(members)").fetchall()
            }
            member_indexes = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA index_list(members)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("learning_level_id", member_columns)
        self.assertIn("idx_members_learning_level", member_indexes)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v7_database_repairs_missing_learning_column_during_v8_migration(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v7_missing_learning.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_id INTEGER DEFAULT 1,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                PRAGMA user_version = 7;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            member_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(members)").fetchall()
            }
            settings_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("learning_level_id", member_columns)
        self.assertIn("tournament_profile", settings_columns)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v8_database_adds_certificate_visual_asset_columns(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v8_certificate_assets.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE certificate_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    certificate_type TEXT NOT NULL DEFAULT 'participation',
                    title_template TEXT NOT NULL DEFAULT '',
                    body_template TEXT NOT NULL DEFAULT '',
                    footer_template TEXT DEFAULT '',
                    orientation TEXT NOT NULL DEFAULT 'landscape',
                    signature_left TEXT DEFAULT '',
                    signature_right TEXT DEFAULT '',
                    logo_path TEXT DEFAULT '',
                    primary_color TEXT NOT NULL DEFAULT '#1E3A8A',
                    accent_color TEXT NOT NULL DEFAULT '#93C5FD',
                    title_font_size INTEGER NOT NULL DEFAULT 32,
                    body_font_size INTEGER NOT NULL DEFAULT 18,
                    footer_font_size INTEGER NOT NULL DEFAULT 10,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                INSERT INTO certificate_templates (
                    name, certificate_type, title_template, body_template,
                    created_at, updated_at
                ) VALUES (
                    'Modelo antigo', 'participation', 'Titulo', 'Texto', '2026-01-01', '2026-01-01'
                );

                PRAGMA user_version = 8;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            certificate_template_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(certificate_templates)").fetchall()
            }
            template = migrated_connection.execute(
                """
                SELECT background_image_path, background_opacity, secondary_logo_path
                FROM certificate_templates
                WHERE name = 'Modelo antigo'
                """
            ).fetchone()
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("background_image_path", certificate_template_columns)
        self.assertIn("background_opacity", certificate_template_columns)
        self.assertIn("secondary_logo_path", certificate_template_columns)
        self.assertEqual(template["background_image_path"], "")
        self.assertEqual(template["background_opacity"], 0.18)
        self.assertEqual(template["secondary_logo_path"], "")
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v10_database_adds_exercise_library_schema(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v10_exercises.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE training_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_id INTEGER DEFAULT 1,
                    class_id INTEGER,
                    title TEXT NOT NULL,
                    session_type TEXT NOT NULL DEFAULT 'aula',
                    session_date TEXT DEFAULT '',
                    start_time TEXT DEFAULT '',
                    end_time TEXT DEFAULT '',
                    instructor TEXT DEFAULT '',
                    location TEXT DEFAULT '',
                    learning_level_id INTEGER,
                    objective TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    homework TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'planned',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                PRAGMA user_version = 10;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            training_session_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(training_sessions)").fetchall()
            }
            exercise_tables = {
                row["name"]
                for row in migrated_connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'exercise_library',
                            'training_lists',
                            'training_list_exercises',
                            'exercise_attempts'
                        )
                    """
                ).fetchall()
            }
            exercise_indexes = {
                row["name"]
                for table_name in (
                    "exercise_library",
                    "training_lists",
                    "training_list_exercises",
                    "exercise_attempts",
                    "training_sessions",
                )
                for row in migrated_connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("training_list_id", training_session_columns)
        self.assertEqual(
            {"exercise_library", "training_lists", "training_list_exercises", "exercise_attempts"},
            exercise_tables,
        )
        self.assertIn("idx_exercise_library_filters", exercise_indexes)
        self.assertIn("idx_training_lists_filters", exercise_indexes)
        self.assertIn("idx_training_sessions_training_list", exercise_indexes)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v11_database_adds_inventory_schema(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v11_inventory.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                PRAGMA user_version = 11;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            inventory_tables = {
                row["name"]
                for row in migrated_connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'inventory_items',
                            'inventory_loans',
                            'inventory_maintenance'
                        )
                    """
                ).fetchall()
            }
            inventory_indexes = {
                row["name"]
                for table_name in ("inventory_items", "inventory_loans", "inventory_maintenance")
                for row in migrated_connection.execute(f"PRAGMA index_list({table_name})").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertEqual({"inventory_items", "inventory_loans", "inventory_maintenance"}, inventory_tables)
        self.assertIn("idx_inventory_items_filters", inventory_indexes)
        self.assertIn("idx_inventory_loans_item", inventory_indexes)
        self.assertIn("idx_inventory_maintenance_item", inventory_indexes)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v12_database_adds_audit_log_schema(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v12_audit.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                PRAGMA user_version = 12;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            audit_table = migrated_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'audit_log'
                """
            ).fetchone()
            audit_indexes = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA index_list(audit_log)").fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIsNotNone(audit_table)
        self.assertIn("idx_audit_log_created", audit_indexes)
        self.assertIn("idx_audit_log_entity", audit_indexes)
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v22_database_adds_phase0_arbitration_schema(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v22_phase0.db"
        Database(legacy_path, backup_dir=self.backup_dir)
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                DROP TABLE IF EXISTS audit_events;
                DROP TABLE IF EXISTS pairing_snapshots;
                DROP TABLE IF EXISTS standings_snapshots;
                DROP TABLE IF EXISTS tiebreak_components;
                DROP TABLE IF EXISTS public_tokens;
                DROP TABLE IF EXISTS result_submissions;
                PRAGMA user_version = 22;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            settings_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(tournament_settings)").fetchall()
            }
            round_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(rounds)").fetchall()
            }
            phase0_tables = {
                row["name"]
                for row in migrated_connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                        AND name IN (
                            'audit_events', 'pairing_snapshots', 'standings_snapshots',
                            'tiebreak_components', 'public_tokens', 'result_submissions'
                        )
                    """
                ).fetchall()
            }
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("pairing_system", settings_columns)
        self.assertIn("acceleration_method", settings_columns)
        self.assertIn("pairing_engine_version", round_columns)
        self.assertIn("ruleset_version", round_columns)
        self.assertEqual(
            {
                "audit_events", "pairing_snapshots", "standings_snapshots",
                "tiebreak_components", "public_tokens", "result_submissions",
            },
            phase0_tables,
        )
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_v32_database_adds_round_closed_at_and_backfills_closed_rounds(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_v32_round_clock.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER NOT NULL,
                    number INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'generated',
                    pairing_engine_version TEXT NOT NULL DEFAULT 'albericus-swiss-1',
                    ruleset_version TEXT NOT NULL DEFAULT 'albericus-2026-phase0',
                    created_at TEXT NOT NULL
                );
                INSERT INTO rounds (tournament_id, number, status, created_at)
                VALUES (1, 1, 'closed', '2026-05-31 09:00:00');
                PRAGMA user_version = 32;
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        with migrated.connect() as migrated_connection:
            columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(rounds)").fetchall()
            }
            round_data = migrated_connection.execute("SELECT * FROM rounds WHERE id = 1").fetchone()
            user_version = migrated_connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("closed_at", columns)
        self.assertEqual("2026-05-31 09:00:00", round_data["closed_at"])
        self.assertEqual(Database.SCHEMA_VERSION, user_version)

    def test_current_database_repairs_legacy_users_table_before_login(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy_current_users.db"
        legacy_hash = hashlib.sha256("admin".encode()).hexdigest()
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                f"""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                INSERT INTO users (username, password_hash, role, created_at)
                VALUES ('admin', '{legacy_hash}', 'admin', '2026-01-01 00:00:00');

                PRAGMA user_version = {Database.SCHEMA_VERSION};
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(legacy_path, backup_dir=self.backup_dir)
        security_service = SecurityService(migrated)

        self.assertTrue(security_service.login("admin", "admin"))
        with migrated.connect() as migrated_connection:
            user_columns = {
                row["name"]
                for row in migrated_connection.execute("PRAGMA table_info(users)").fetchall()
            }
            user = migrated_connection.execute(
                "SELECT password_hash, updated_at FROM users WHERE username = 'admin'"
            ).fetchone()

        self.assertIn("updated_at", user_columns)
        self.assertTrue(str(user["password_hash"]).startswith("pbkdf2_sha256$"))
        self.assertTrue(user["updated_at"])

    def test_future_database_version_is_rejected(self) -> None:
        future_path = Path(self.temp_dir.name) / "future.db"
        connection = sqlite3.connect(future_path)
        try:
            connection.execute(f"PRAGMA user_version = {Database.SCHEMA_VERSION + 1}")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(RuntimeError, "versao mais nova"):
            Database(future_path, backup_dir=self.backup_dir)

if __name__ == "__main__":
    unittest.main()
