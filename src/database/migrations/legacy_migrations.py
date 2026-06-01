import sqlite3
import json
from typing import Callable, Any
from datetime import datetime

from src.core.database import DEFAULT_LEARNING_LEVELS, DEFAULT_CERTIFICATE_TEMPLATES
from src.core.categories import competition_category_payload

class LegacyMigrations:
    def __init__(self, db) -> None:
        self.db = db

    def _schema_migrations(self) -> dict[int, Callable[[sqlite3.Connection], None]]:
        return {
            1: self._migrate_to_v1,
            2: self._migrate_to_v2,
            3: self._migrate_to_v3,
            4: self._migrate_to_v4,
            5: self._migrate_to_v5,
            6: self._migrate_to_v6,
            7: self._migrate_to_v7,
            8: self._migrate_to_v8,
            9: self._migrate_to_v9,
            10: self._migrate_to_v10,
            11: self._migrate_to_v11,
            12: self._migrate_to_v12,
            13: self._migrate_to_v13,
            14: self._migrate_to_v14,
            15: self._migrate_to_v15,
            16: self._migrate_to_v16,
            17: self._migrate_to_v17,
            18: self._migrate_to_v18,
            19: self._migrate_to_v19,
            20: self._migrate_to_v20,
            21: self._migrate_to_v21,
            22: self._migrate_to_v22,
            23: self._migrate_to_v23,
            24: self._migrate_to_v24,
            25: self._migrate_to_v25,
            26: self._migrate_to_v26,
            27: self._migrate_to_v27,
            28: self._migrate_to_v28,
            29: self._migrate_to_v29,
            30: self._migrate_to_v30,
            31: self._migrate_to_v31,
            32: self._migrate_to_v32,
            33: self._migrate_to_v33,
            34: self._migrate_to_v34,
            35: self._migrate_to_v35,
            36: self._migrate_to_v36,
            37: self._migrate_to_v37,
            38: self._migrate_to_v38,
            39: self._migrate_to_v39,
        }

    def _run_schema_migrations(self, connection: sqlite3.Connection) -> None:
        current_version = self.db._schema_user_version(connection)
        self._ensure_supported_schema_version(connection)

        migrations = self._schema_migrations()
        for target_version in range(current_version + 1, self.db.SCHEMA_VERSION + 1):
            migration = migrations.get(target_version)
            if migration is None:
                raise RuntimeError(f"Migracao de banco ausente para a versao {target_version}.")
            migration(connection)
            connection.execute(f"PRAGMA user_version = {target_version}")

        if current_version == self.db.SCHEMA_VERSION:
            self._ensure_current_schema(connection)

    def _ensure_current_schema(self, connection: sqlite3.Connection) -> None:
        if self.db.SCHEMA_VERSION >= 1:
            self._migrate_to_v1(connection)
        if self.db.SCHEMA_VERSION >= 2:
            self._migrate_to_v2(connection)
        if self.db.SCHEMA_VERSION >= 3:
            self._migrate_to_v3(connection)
        if self.db.SCHEMA_VERSION >= 4:
            self._migrate_to_v4(connection)
        if self.db.SCHEMA_VERSION >= 5:
            self._migrate_to_v5(connection)
        if self.db.SCHEMA_VERSION >= 6:
            self._migrate_to_v6(connection)
        if self.db.SCHEMA_VERSION >= 7:
            self._migrate_to_v7(connection)
        if self.db.SCHEMA_VERSION >= 8:
            self._migrate_to_v8(connection)
        if self.db.SCHEMA_VERSION >= 9:
            self._migrate_to_v9(connection)
        if self.db.SCHEMA_VERSION >= 10:
            self._migrate_to_v10(connection)
        if self.db.SCHEMA_VERSION >= 11:
            self._migrate_to_v11(connection)
        if self.db.SCHEMA_VERSION >= 12:
            self._migrate_to_v12(connection)
        if self.db.SCHEMA_VERSION >= 13:
            self._migrate_to_v13(connection)
        if self.db.SCHEMA_VERSION >= 14:
            self._migrate_to_v14(connection)
        if self.db.SCHEMA_VERSION >= 15:
            self._migrate_to_v15(connection)
        if self.db.SCHEMA_VERSION >= 16:
            self._migrate_to_v16(connection)
        if self.db.SCHEMA_VERSION >= 17:
            self._migrate_to_v17(connection)
        if self.db.SCHEMA_VERSION >= 18:
            self._migrate_to_v18(connection)
        if self.db.SCHEMA_VERSION >= 19:
            self._migrate_to_v19(connection)
        if self.db.SCHEMA_VERSION >= 20:
            self._migrate_to_v20(connection)
        if self.db.SCHEMA_VERSION >= 21:
            self._migrate_to_v21(connection)
        if self.db.SCHEMA_VERSION >= 22:
            self._migrate_to_v22(connection)
        if self.db.SCHEMA_VERSION >= 23:
            self._migrate_to_v23(connection)
        if self.db.SCHEMA_VERSION >= 24:
            self._migrate_to_v24(connection)
        if self.db.SCHEMA_VERSION >= 25:
            self._migrate_to_v25(connection)
        if self.db.SCHEMA_VERSION >= 26:
            self._migrate_to_v26(connection)
        if self.db.SCHEMA_VERSION >= 27:
            self._migrate_to_v27(connection)
        if self.db.SCHEMA_VERSION >= 28:
            self._migrate_to_v28(connection)
        if self.db.SCHEMA_VERSION >= 29:
            self._migrate_to_v29(connection)
        if self.db.SCHEMA_VERSION >= 30:
            self._migrate_to_v30(connection)
        if self.db.SCHEMA_VERSION >= 31:
            self._migrate_to_v31(connection)
        if self.db.SCHEMA_VERSION >= 32:
            self._migrate_to_v32(connection)
        if self.db.SCHEMA_VERSION >= 33:
            self._migrate_to_v33(connection)
        if self.db.SCHEMA_VERSION >= 34:
            self._migrate_to_v34(connection)
        if self.db.SCHEMA_VERSION >= 35:
            self._migrate_to_v35(connection)
        if self.db.SCHEMA_VERSION >= 36:
            self._migrate_to_v36(connection)
        if self.db.SCHEMA_VERSION >= 37:
            self._migrate_to_v37(connection)
        if self.db.SCHEMA_VERSION >= 38:
            self._migrate_to_v38(connection)
        if self.db.SCHEMA_VERSION >= 39:
            self._migrate_to_v39(connection)

    def _migrate_to_v1(self, connection: sqlite3.Connection) -> None:
        now = self.db.now()
        connection.execute(
            """
            INSERT OR IGNORE INTO clubs (id, name, created_at, updated_at)
            VALUES (1, '', ?, ?)
            """,
            (now, now),
        )
        club_columns = self.db._table_columns(connection, "clubs")
        club_migrations = {
            "kind": "TEXT NOT NULL DEFAULT 'club'",
            "active": "INTEGER NOT NULL DEFAULT 1",
        }
        for column, definition in club_migrations.items():
            if column not in club_columns:
                connection.execute(f"ALTER TABLE clubs ADD COLUMN {column} {definition}")

        member_columns = self.db._table_columns(connection, "members")
        member_migrations = {
            "surname": "TEXT DEFAULT ''",
            "age_category": "TEXT DEFAULT ''",
            "rating_category": "TEXT DEFAULT ''",
            "prize_tags": "TEXT DEFAULT ''",
        }
        for column, definition in member_migrations.items():
            if column not in member_columns:
                connection.execute(f"ALTER TABLE members ADD COLUMN {column} {definition}")

        tournament_columns = self.db._table_columns(connection, "tournaments")
        if "club_id" not in tournament_columns:
            connection.execute("ALTER TABLE tournaments ADD COLUMN club_id INTEGER DEFAULT 1")
            connection.execute("UPDATE tournaments SET club_id = 1 WHERE club_id IS NULL")
        if "class_id" not in tournament_columns:
            connection.execute("ALTER TABLE tournaments ADD COLUMN class_id INTEGER")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_club ON tournaments(club_id, created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_class ON tournaments(class_id, created_at)")

        player_columns = self.db._table_columns(connection, "players")
        player_migrations = {
            "member_id": "INTEGER",
            "surname": "TEXT DEFAULT ''",
            "given_name": "TEXT DEFAULT ''",
            "title": "TEXT DEFAULT ''",
            "sex": "TEXT DEFAULT ''",
            "cbx_id": "TEXT DEFAULT ''",
            "national_rating": "INTEGER NOT NULL DEFAULT 0",
            "international_rating": "INTEGER NOT NULL DEFAULT 0",
            "player_status": "TEXT NOT NULL DEFAULT 'active'",
            "starting_points": "REAL NOT NULL DEFAULT 0.0",
            "age_category": "TEXT DEFAULT ''",
            "rating_category": "TEXT DEFAULT ''",
            "prize_tags": "TEXT DEFAULT ''",
        }
        for column, definition in player_migrations.items():
            if column not in player_columns:
                connection.execute(f"ALTER TABLE players ADD COLUMN {column} {definition}")
        connection.execute(
            """
            UPDATE players
            SET player_status = CASE WHEN active = 1 THEN 'active' ELSE 'inactive' END
            WHERE player_status IS NULL OR player_status = ''
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_players_member ON players(member_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_players_official_ids ON players(fide_id, cbx_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_pairings_white_player ON pairings(white_player_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_pairings_black_player ON pairings(black_player_id)")
        self._refresh_competition_categories(connection)

        for tournament in connection.execute("SELECT id, rounds_count FROM tournaments").fetchall():
            self._ensure_tournament_settings(connection, int(tournament["id"]))
            self._ensure_round_schedule(
                connection,
                int(tournament["id"]),
                int(tournament["rounds_count"] or 0),
            )

    def _migrate_to_v2(self, connection: sqlite3.Connection) -> None:
        self._ensure_team_tournament_schema(connection)

    def _migrate_to_v3(self, connection: sqlite3.Connection) -> None:
        self._ensure_team_tournament_schema(connection)

    def _migrate_to_v4(self, connection: sqlite3.Connection) -> None:
        self._ensure_learning_level_schema(connection)

    def _migrate_to_v5(self, connection: sqlite3.Connection) -> None:
        self._ensure_certificate_template_schema(connection)

    def _migrate_to_v6(self, connection: sqlite3.Connection) -> None:
        self._ensure_certificate_template_schema(connection)

    def _migrate_to_v7(self, connection: sqlite3.Connection) -> None:
        self._ensure_certificate_issuance_schema(connection)

    def _migrate_to_v8(self, connection: sqlite3.Connection) -> None:
        self._ensure_team_tournament_schema(connection)
        self._ensure_learning_level_schema(connection)
        self._ensure_certificate_template_schema(connection)
        self._ensure_certificate_issuance_schema(connection)
        self._ensure_tournament_profile_schema(connection)

    def _migrate_to_v9(self, connection: sqlite3.Connection) -> None:
        self._ensure_certificate_visual_asset_schema(connection)

    def _migrate_to_v10(self, connection: sqlite3.Connection) -> None:
        self._ensure_training_pedagogical_schema(connection)

    def _migrate_to_v11(self, connection: sqlite3.Connection) -> None:
        self._ensure_exercise_library_schema(connection)

    def _migrate_to_v12(self, connection: sqlite3.Connection) -> None:
        self._ensure_inventory_schema(connection)

    def _migrate_to_v13(self, connection: sqlite3.Connection) -> None:
        self._ensure_security_schema(connection)

    def _ensure_security_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT DEFAULT '',
                role TEXT DEFAULT '',
                action TEXT NOT NULL,
                entity_type TEXT DEFAULT '',
                entity_id INTEGER,
                description TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '',
                sent_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_log_created
                ON audit_log(created_at, action);
            CREATE INDEX IF NOT EXISTS idx_audit_log_entity
                ON audit_log(entity_type, entity_id, created_at);
            """
        )

    def _ensure_inventory_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER DEFAULT 1,
                code TEXT DEFAULT '',
                name TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'other',
                quantity_total INTEGER NOT NULL DEFAULT 1,
                condition_status TEXT NOT NULL DEFAULT 'good',
                storage_location TEXT DEFAULT '',
                acquisition_date TEXT DEFAULT '',
                acquisition_value REAL NOT NULL DEFAULT 0.0,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS inventory_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                loan_date TEXT DEFAULT '',
                due_date TEXT DEFAULT '',
                return_date TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS inventory_maintenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                opened_date TEXT DEFAULT '',
                resolved_date TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                description TEXT NOT NULL DEFAULT '',
                cost REAL NOT NULL DEFAULT 0.0,
                vendor TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_inventory_items_filters
                ON inventory_items(active, club_id, item_type, condition_status, name);
            CREATE INDEX IF NOT EXISTS idx_inventory_items_code
                ON inventory_items(code);
            CREATE INDEX IF NOT EXISTS idx_inventory_loans_item
                ON inventory_loans(item_id, status, due_date);
            CREATE INDEX IF NOT EXISTS idx_inventory_loans_member
                ON inventory_loans(member_id, status, due_date);
            CREATE INDEX IF NOT EXISTS idx_inventory_maintenance_item
                ON inventory_maintenance(item_id, status, opened_date);
            """
        )

    def _ensure_exercise_library_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS exercise_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER DEFAULT 1,
                learning_level_id INTEGER,
                title TEXT NOT NULL,
                theme TEXT DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'basic',
                source TEXT DEFAULT '',
                fen TEXT DEFAULT '',
                pgn TEXT DEFAULT '',
                solution TEXT DEFAULT '',
                objective TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
                FOREIGN KEY (learning_level_id) REFERENCES learning_levels(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS training_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER DEFAULT 1,
                class_id INTEGER,
                learning_level_id INTEGER,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                target_date TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
                FOREIGN KEY (learning_level_id) REFERENCES learning_levels(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS training_list_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                exercise_id INTEGER NOT NULL,
                position_order INTEGER NOT NULL DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (list_id, exercise_id),
                UNIQUE (list_id, position_order),
                FOREIGN KEY (list_id) REFERENCES training_lists(id) ON DELETE CASCADE,
                FOREIGN KEY (exercise_id) REFERENCES exercise_library(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exercise_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                list_id INTEGER,
                session_id INTEGER,
                attempt_date TEXT DEFAULT '',
                result TEXT NOT NULL DEFAULT 'attempted',
                score REAL NOT NULL DEFAULT 0.0,
                time_seconds INTEGER NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (exercise_id) REFERENCES exercise_library(id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
                FOREIGN KEY (list_id) REFERENCES training_lists(id) ON DELETE SET NULL,
                FOREIGN KEY (session_id) REFERENCES training_sessions(id) ON DELETE SET NULL
            );
            """
        )
        training_columns = self.db._table_columns(connection, "training_sessions")
        if "training_list_id" not in training_columns:
            connection.execute("ALTER TABLE training_sessions ADD COLUMN training_list_id INTEGER")
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_exercise_library_filters
                ON exercise_library(active, club_id, learning_level_id, theme, difficulty);
            CREATE INDEX IF NOT EXISTS idx_exercise_library_title
                ON exercise_library(title);
            CREATE INDEX IF NOT EXISTS idx_training_lists_filters
                ON training_lists(status, club_id, class_id, learning_level_id, target_date);
            CREATE INDEX IF NOT EXISTS idx_training_list_exercises_list
                ON training_list_exercises(list_id, position_order);
            CREATE INDEX IF NOT EXISTS idx_training_sessions_training_list
                ON training_sessions(training_list_id, session_date);
            CREATE INDEX IF NOT EXISTS idx_exercise_attempts_member
                ON exercise_attempts(member_id, attempt_date);
            CREATE INDEX IF NOT EXISTS idx_exercise_attempts_exercise
                ON exercise_attempts(exercise_id, result, attempt_date);
            """
        )

    def _migrate_to_v14(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS member_presences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                presence_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS member_titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                title_name TEXT NOT NULL,
                date_earned TEXT NOT NULL,
                issuer TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
            )
            """
        )
        for col, col_type in [
            ("departure_date", "TEXT DEFAULT ''"),
            ("departure_reason", "TEXT DEFAULT ''"),
            ("transfer_notes", "TEXT DEFAULT ''"),
        ]:
            try:
                connection.execute(f"ALTER TABLE members ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

    def _migrate_to_v15(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0.0,
                transaction_date TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT DEFAULT '',
                payment_method TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    def _migrate_to_v16(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER DEFAULT 1,
                title TEXT NOT NULL,
                date_start TEXT NOT NULL,
                date_end TEXT DEFAULT '',
                event_type TEXT NOT NULL DEFAULT 'other',
                location TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (club_id) REFERENCES clubs (id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS event_rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES calendar_events (id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE,
                UNIQUE (event_id, member_id)
            );
            
            CREATE TABLE IF NOT EXISTS inventory_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                loan_date TEXT NOT NULL,
                expected_return_date TEXT NOT NULL,
                actual_return_date TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES inventory_items (id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
            );
            """
        )

    def _migrate_to_v17(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER DEFAULT 1,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                expiration_date TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (club_id) REFERENCES clubs (id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS communication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                content TEXT DEFAULT '',
                sent_at TEXT NOT NULL,
                FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
            );
            """
        )

    def _migrate_to_v18(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS library_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'exercise',
                phase TEXT DEFAULT 'general',
                theme TEXT DEFAULT '',
                level TEXT DEFAULT '',
                fen_pgn TEXT DEFAULT '',
                content TEXT DEFAULT '',
                solution TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                author TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_library_items_phase ON library_items(phase);
            CREATE INDEX IF NOT EXISTS idx_library_items_theme ON library_items(theme);
            CREATE INDEX IF NOT EXISTS idx_library_items_type ON library_items(item_type);
            """
        )

    def _migrate_to_v19(self, connection: sqlite3.Connection) -> None:
        """Adiciona tabelas para Coleções/Apostilas e Histórico da Biblioteca."""
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS library_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS library_collection_items (
                collection_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                display_order INTEGER DEFAULT 0,
                PRIMARY KEY (collection_id, item_id),
                FOREIGN KEY(collection_id) REFERENCES library_collections(id) ON DELETE CASCADE,
                FOREIGN KEY(item_id) REFERENCES library_items(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS library_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                collection_id INTEGER,
                item_id INTEGER,
                sent_date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
                FOREIGN KEY(collection_id) REFERENCES library_collections(id) ON DELETE CASCADE,
                FOREIGN KEY(item_id) REFERENCES library_items(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_library_history_class ON library_history(class_id);
            CREATE INDEX IF NOT EXISTS idx_library_history_sent_date ON library_history(sent_date);
            CREATE INDEX IF NOT EXISTS idx_library_collection_items_order ON library_collection_items(collection_id, display_order);
        """)

    def _migrate_to_v20(self, connection: sqlite3.Connection) -> None:
        """Adiciona tabela para Patrocínios e Doações."""
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS sponsors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sponsor_type TEXT DEFAULT 'company',
                contribution_amount REAL DEFAULT 0.0,
                frequency TEXT DEFAULT 'monthly',
                benefits_notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

    def _migrate_to_v21(self, connection: sqlite3.Connection) -> None:
        """Adiciona tabela de usuários."""
        now = self.db.now()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        user_columns = self.db._table_columns(connection, "users")
        user_migrations = {
            "username": "TEXT NOT NULL DEFAULT ''",
            "password_hash": "TEXT NOT NULL DEFAULT ''",
            "role": "TEXT NOT NULL DEFAULT 'admin'",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in user_migrations.items():
            if column not in user_columns:
                connection.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        connection.execute(
            """
            UPDATE users
            SET created_at = CASE WHEN created_at = '' THEN ? ELSE created_at END,
                updated_at = CASE WHEN updated_at = '' THEN ? ELSE updated_at END,
                role = CASE WHEN role = '' THEN 'admin' ELSE role END
            """,
            (now, now),
        )
        # Verifica se já existe algum admin. Se não houver, insere o padrão.
        cursor = connection.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if cursor.fetchone()[0] == 0:
            import hashlib
            import os
            iterations = 210_000
            salt = os.urandom(16)
            digest = hashlib.pbkdf2_hmac("sha256", b"admin", salt, iterations)
            pw_hash = f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
            connection.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at, updated_at)
                VALUES (?, ?, 'admin', ?, ?)
                """,
                ("admin", pw_hash, now, now)
            )
    def _ensure_training_pedagogical_schema(self, connection: sqlite3.Connection) -> None:
        training_columns = self.db._table_columns(connection, "training_sessions")
        training_migrations = {
            "learning_level_id": "INTEGER",
            "objective": "TEXT DEFAULT ''",
            "content": "TEXT DEFAULT ''",
            "homework": "TEXT DEFAULT ''",
        }
        for column, definition in training_migrations.items():
            if column not in training_columns:
                connection.execute(f"ALTER TABLE training_sessions ADD COLUMN {column} {definition}")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_training_sessions_level
                ON training_sessions(learning_level_id, status, session_date)
            """
        )

    def _ensure_tournament_profile_schema(self, connection: sqlite3.Connection) -> None:
        settings_columns = self.db._table_columns(connection, "tournament_settings")
        if "tournament_profile" not in settings_columns:
            connection.execute(
                "ALTER TABLE tournament_settings ADD COLUMN tournament_profile TEXT NOT NULL DEFAULT 'free'"
            )
        connection.execute(
            """
            UPDATE tournament_settings
            SET tournament_profile = 'free'
            WHERE tournament_profile IS NULL OR tournament_profile = ''
            """
        )

    def _ensure_certificate_visual_asset_schema(self, connection: sqlite3.Connection) -> None:
        template_columns = self.db._table_columns(connection, "certificate_templates")
        template_migrations = {
            "background_image_path": "TEXT DEFAULT ''",
            "background_opacity": "REAL NOT NULL DEFAULT 0.18",
            "secondary_logo_path": "TEXT DEFAULT ''",
        }
        for column, definition in template_migrations.items():
            if column not in template_columns:
                connection.execute(f"ALTER TABLE certificate_templates ADD COLUMN {column} {definition}")
        connection.execute(
            """
            UPDATE certificate_templates
            SET background_image_path = CASE
                    WHEN background_image_path IS NULL THEN ''
                    ELSE background_image_path
                END,
                background_opacity = CASE
                    WHEN background_opacity IS NULL THEN 0.18
                    ELSE background_opacity
                END,
                secondary_logo_path = CASE
                    WHEN secondary_logo_path IS NULL THEN ''
                    ELSE secondary_logo_path
                END
            """
        )

    def _ensure_certificate_template_schema(self, connection: sqlite3.Connection) -> None:
        now = self.db.now()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS certificate_templates (
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
                background_image_path TEXT DEFAULT '',
                background_opacity REAL NOT NULL DEFAULT 0.18,
                secondary_logo_path TEXT DEFAULT '',
                primary_color TEXT NOT NULL DEFAULT '#1E3A8A',
                accent_color TEXT NOT NULL DEFAULT '#93C5FD',
                title_font_size INTEGER NOT NULL DEFAULT 32,
                body_font_size INTEGER NOT NULL DEFAULT 18,
                footer_font_size INTEGER NOT NULL DEFAULT 10,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        template_columns = self.db._table_columns(connection, "certificate_templates")
        template_migrations = {
            "certificate_type": "TEXT NOT NULL DEFAULT 'participation'",
            "title_template": "TEXT NOT NULL DEFAULT ''",
            "body_template": "TEXT NOT NULL DEFAULT ''",
            "footer_template": "TEXT DEFAULT ''",
            "orientation": "TEXT NOT NULL DEFAULT 'landscape'",
            "signature_left": "TEXT DEFAULT ''",
            "signature_right": "TEXT DEFAULT ''",
            "logo_path": "TEXT DEFAULT ''",
            "background_image_path": "TEXT DEFAULT ''",
            "background_opacity": "REAL NOT NULL DEFAULT 0.18",
            "secondary_logo_path": "TEXT DEFAULT ''",
            "primary_color": "TEXT NOT NULL DEFAULT '#1E3A8A'",
            "accent_color": "TEXT NOT NULL DEFAULT '#93C5FD'",
            "title_font_size": "INTEGER NOT NULL DEFAULT 32",
            "body_font_size": "INTEGER NOT NULL DEFAULT 18",
            "footer_font_size": "INTEGER NOT NULL DEFAULT 10",
            "active": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in template_migrations.items():
            if column not in template_columns:
                connection.execute(f"ALTER TABLE certificate_templates ADD COLUMN {column} {definition}")

        connection.execute(
            """
            UPDATE certificate_templates
            SET created_at = CASE WHEN created_at = '' THEN ? ELSE created_at END,
                updated_at = CASE WHEN updated_at = '' THEN ? ELSE updated_at END
            """,
            (now, now),
        )
        for template in DEFAULT_CERTIFICATE_TEMPLATES:
            connection.execute(
                """
                INSERT OR IGNORE INTO certificate_templates (
                    name, certificate_type, title_template, body_template, footer_template,
                    orientation, signature_left, signature_right, logo_path,
                    background_image_path, background_opacity, secondary_logo_path,
                    primary_color,
                    accent_color, title_font_size, body_font_size, footer_font_size,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    template["name"],
                    template["certificate_type"],
                    template["title_template"],
                    template["body_template"],
                    template["footer_template"],
                    template["orientation"],
                    template["signature_left"],
                    template["signature_right"],
                    template["logo_path"],
                    template.get("background_image_path", ""),
                    float(str(template.get("background_opacity", 0.18) or 0.18)),
                    template.get("secondary_logo_path", ""),
                    template["primary_color"],
                    template["accent_color"],
                    template["title_font_size"],
                    template["body_font_size"],
                    template["footer_font_size"],
                    now,
                    now,
                ),
            )

    def _ensure_certificate_issuance_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS certificate_issuances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_code TEXT NOT NULL UNIQUE,
                context_type TEXT NOT NULL DEFAULT '',
                source_id INTEGER,
                source_title TEXT DEFAULT '',
                recipient_id INTEGER,
                recipient_name TEXT NOT NULL DEFAULT '',
                recipient_category TEXT DEFAULT '',
                certificate_type TEXT NOT NULL DEFAULT '',
                template_id INTEGER,
                template_name TEXT DEFAULT '',
                file_path TEXT NOT NULL DEFAULT '',
                issued_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                payload_json TEXT DEFAULT '',
                FOREIGN KEY (template_id) REFERENCES certificate_templates(id) ON DELETE SET NULL
            )
            """
        )
        issuance_columns = self.db._table_columns(connection, "certificate_issuances")
        issuance_migrations = {
            "verification_code": "TEXT NOT NULL DEFAULT ''",
            "context_type": "TEXT NOT NULL DEFAULT ''",
            "source_id": "INTEGER",
            "source_title": "TEXT DEFAULT ''",
            "recipient_id": "INTEGER",
            "recipient_name": "TEXT NOT NULL DEFAULT ''",
            "recipient_category": "TEXT DEFAULT ''",
            "certificate_type": "TEXT NOT NULL DEFAULT ''",
            "template_id": "INTEGER",
            "template_name": "TEXT DEFAULT ''",
            "file_path": "TEXT NOT NULL DEFAULT ''",
            "issued_at": "TEXT NOT NULL DEFAULT ''",
            "revoked": "INTEGER NOT NULL DEFAULT 0",
            "revoked_at": "TEXT DEFAULT ''",
            "notes": "TEXT DEFAULT ''",
            "payload_json": "TEXT DEFAULT ''",
        }
        for column, definition in issuance_migrations.items():
            if column not in issuance_columns:
                connection.execute(f"ALTER TABLE certificate_issuances ADD COLUMN {column} {definition}")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_certificate_issuances_code
                ON certificate_issuances(verification_code)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_certificate_issuances_context
                ON certificate_issuances(context_type, source_id, issued_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_certificate_issuances_recipient
                ON certificate_issuances(recipient_name, issued_at)
            """
        )

    def _ensure_learning_level_schema(self, connection: sqlite3.Connection) -> None:
        now = self.db.now()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                display_order INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        member_columns = self.db._table_columns(connection, "members")
        if "learning_level_id" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN learning_level_id INTEGER")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_levels_order
                ON learning_levels(active, display_order, name)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_members_learning_level
                ON members(learning_level_id, status, name)
            """
        )
        for index, (name, description) in enumerate(DEFAULT_LEARNING_LEVELS, start=1):
            connection.execute(
                """
                INSERT OR IGNORE INTO learning_levels (
                    name, description, display_order, active, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)
                """,
                (name, description, index * 10, now, now),
            )

    def _ensure_team_tournament_schema(self, connection: sqlite3.Connection) -> None:
        tournament_columns = self.db._table_columns(connection, "tournaments")
        if "competition_type" not in tournament_columns:
            connection.execute(
                "ALTER TABLE tournaments ADD COLUMN competition_type TEXT NOT NULL DEFAULT 'individual'"
            )
        connection.execute(
            """
            UPDATE tournaments
            SET competition_type = 'individual'
            WHERE competition_type IS NULL OR competition_type = ''
            """
        )

        settings_columns = self.db._table_columns(connection, "tournament_settings")
        settings_migrations = {
            "team_boards_count": "INTEGER NOT NULL DEFAULT 4",
            "team_match_win_points": "REAL NOT NULL DEFAULT 2.0",
            "team_match_draw_points": "REAL NOT NULL DEFAULT 1.0",
            "team_match_loss_points": "REAL NOT NULL DEFAULT 0.0",
            "team_pairing_method": "TEXT NOT NULL DEFAULT 'swiss'",
            "pairing_method": "TEXT NOT NULL DEFAULT 'swiss'",
            "team_standing_primary": "TEXT NOT NULL DEFAULT 'match_points'",
            "team_standing_secondary": "TEXT NOT NULL DEFAULT 'game_points'",
            "team_fixed_board_order": "INTEGER NOT NULL DEFAULT 1",
        }
        for column, definition in settings_migrations.items():
            if column not in settings_columns:
                connection.execute(f"ALTER TABLE tournament_settings ADD COLUMN {column} {definition}")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                club TEXT DEFAULT '',
                captain TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (tournament_id, name),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS team_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                board_number INTEGER,
                role TEXT NOT NULL DEFAULT 'starter',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (team_id, player_id),
                UNIQUE (team_id, board_number),
                UNIQUE (player_id),
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS team_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                match_number INTEGER NOT NULL,
                white_team_id INTEGER NOT NULL,
                black_team_id INTEGER,
                result TEXT DEFAULT '',
                white_match_points REAL NOT NULL DEFAULT 0.0,
                black_match_points REAL NOT NULL DEFAULT 0.0,
                white_game_points REAL NOT NULL DEFAULT 0.0,
                black_game_points REAL NOT NULL DEFAULT 0.0,
                is_bye INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (round_id, match_number),
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (white_team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (black_team_id) REFERENCES teams(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS team_boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_match_id INTEGER NOT NULL,
                board_number INTEGER NOT NULL,
                white_player_id INTEGER,
                black_player_id INTEGER,
                result TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (team_match_id, board_number),
                FOREIGN KEY (team_match_id) REFERENCES team_matches(id) ON DELETE CASCADE,
                FOREIGN KEY (white_player_id) REFERENCES players(id) ON DELETE SET NULL,
                FOREIGN KEY (black_player_id) REFERENCES players(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_teams_tournament
                ON teams(tournament_id, active, name);

            CREATE INDEX IF NOT EXISTS idx_team_players_team
                ON team_players(team_id, board_number);

            CREATE INDEX IF NOT EXISTS idx_team_players_player
                ON team_players(player_id);

            CREATE INDEX IF NOT EXISTS idx_team_matches_round
                ON team_matches(round_id, match_number);

            CREATE INDEX IF NOT EXISTS idx_team_matches_white_team
                ON team_matches(white_team_id);

            CREATE INDEX IF NOT EXISTS idx_team_matches_black_team
                ON team_matches(black_team_id);

            CREATE INDEX IF NOT EXISTS idx_team_boards_match
                ON team_boards(team_match_id, board_number);
            """
        )

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
            (tournament_id, self.db.now()),
        )

    def _ensure_round_schedule(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
        rounds_count: int,
    ) -> None:
        now = self.db.now()
        for round_number in range(1, max(rounds_count, 0) + 1):
            connection.execute(
                """
                INSERT OR IGNORE INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, '', '', ?)
                """,
                (tournament_id, round_number, now),
            )

    def _refresh_competition_categories(self, connection: sqlite3.Connection) -> None:
        member_rows = connection.execute(
            """
            SELECT m.*, c.name AS club_name, c.city AS club_city
            FROM members m
            LEFT JOIN clubs c ON c.id = m.club_id
            """
        ).fetchall()
        for member_row in member_rows:
            member = dict(member_row)
            category_payload = competition_category_payload(
                birth_date=member.get("birth_date", ""),
                rating=member.get("rating", 0),
                category=member.get("category", ""),
                city=member.get("city", ""),
                member_type=member.get("member_type", ""),
                tournament_club_name=member.get("club_name", ""),
                tournament_club_city=member.get("club_city", ""),
            )
            connection.execute(
                """
                UPDATE members
                SET category = ?, age_category = ?, rating_category = ?, prize_tags = ?
                WHERE id = ?
                """,
                (
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    member["id"],
                ),
            )

        player_rows = connection.execute("SELECT * FROM players").fetchall()
        for player_row in player_rows:
            player = dict(player_row)
            category_payload = self.db._player_category_payload(
                connection,
                tournament_id=int(player["tournament_id"]),
                member_id=int(player.get("member_id") or 0) or None,
                birth_date=str(player.get("birth_date") or ""),
                rating=int(player.get("rating") or 0),
                national_rating=int(player.get("national_rating") or 0),
                international_rating=int(player.get("international_rating") or 0),
                category=str(player.get("category") or ""),
                sex=str(player.get("sex") or ""),
                club=str(player.get("club") or ""),
            )
            connection.execute(
                """
                UPDATE players
                SET category = ?, age_category = ?, rating_category = ?, prize_tags = ?
                WHERE id = ?
                """,
                (
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    player["id"],
                ),
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

    def _migrate_to_v22(self, connection: sqlite3.Connection) -> None:
        member_columns = self.db._table_columns(connection, "members")
        if "lichess_username" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN lichess_username TEXT DEFAULT ''")
        if "chesscom_username" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN chesscom_username TEXT DEFAULT ''")
        if "online_blitz_rating" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN online_blitz_rating INTEGER DEFAULT 0")
        if "online_rapid_rating" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN online_rapid_rating INTEGER DEFAULT 0")

    def _migrate_to_v23(self, connection: sqlite3.Connection) -> None:
        self._ensure_arbitration_phase0_schema(connection)

    def _migrate_to_v24(self, connection: sqlite3.Connection) -> None:
        self._ensure_tiebreak_components_schema(connection)

    def _migrate_to_v25(self, connection: sqlite3.Connection) -> None:
        self._ensure_public_result_submission_schema(connection)

    def _migrate_to_v26(self, connection: sqlite3.Connection) -> None:
        self._ensure_team_lineup_schema(connection)

    def _migrate_to_v27(self, connection: sqlite3.Connection) -> None:
        self._ensure_sync_schema(connection)

    def _migrate_to_v28(self, connection: sqlite3.Connection) -> None:
        self._ensure_clock_events_schema(connection)

    def _migrate_to_v29(self, connection: sqlite3.Connection) -> None:
        """Adiciona team_rating_tolerance a tournament_settings.

        Os demais campos da policy (team_board_order_policy, team_reserve_policy,
        team_lineup_deadline, team_max_substitutions) já existem; só falta o
        threshold de tolerância de rating para a validação de ordem de força.
        """
        columns = self.db._table_columns(connection, "tournament_settings")
        if "team_rating_tolerance" not in columns:
            connection.execute(
                "ALTER TABLE tournament_settings ADD COLUMN team_rating_tolerance INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_arbitration_phase0_schema(self, connection: sqlite3.Connection) -> None:
        round_columns = self.db._table_columns(connection, "rounds")
        if "pairing_engine_version" not in round_columns:
            connection.execute(
                "ALTER TABLE rounds ADD COLUMN pairing_engine_version TEXT NOT NULL DEFAULT 'albericus-swiss-1'"
            )
        if "ruleset_version" not in round_columns:
            connection.execute(
                "ALTER TABLE rounds ADD COLUMN ruleset_version TEXT NOT NULL DEFAULT 'albericus-2026-phase0'"
            )

        settings_columns = self.db._table_columns(connection, "tournament_settings")
        if "pairing_system" not in settings_columns:
            connection.execute(
                "ALTER TABLE tournament_settings ADD COLUMN pairing_system TEXT NOT NULL DEFAULT 'custom_authorized'"
            )
        if "acceleration_method" not in settings_columns:
            connection.execute(
                "ALTER TABLE tournament_settings ADD COLUMN acceleration_method TEXT NOT NULL DEFAULT 'none'"
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                tournament_id INTEGER,
                round_id INTEGER,
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id INTEGER,
                action TEXT NOT NULL,
                actor TEXT DEFAULT '',
                role TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                before_hash TEXT DEFAULT '',
                after_hash TEXT DEFAULT '',
                before_json TEXT DEFAULT '',
                after_json TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS pairing_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER,
                round_number INTEGER NOT NULL,
                stage TEXT NOT NULL,
                pairing_system TEXT NOT NULL DEFAULT '',
                pairing_engine_version TEXT NOT NULL DEFAULT '',
                ruleset_version TEXT NOT NULL DEFAULT '',
                snapshot_json TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS standings_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                standings_json TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (tournament_id, round_id),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_audit_events_tournament
                ON audit_events(tournament_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_events_entity
                ON audit_events(entity_type, entity_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_pairing_snapshots_round
                ON pairing_snapshots(tournament_id, round_number, stage);
            CREATE INDEX IF NOT EXISTS idx_standings_snapshots_round
                ON standings_snapshots(tournament_id, round_id);
            """
        )

    def _ensure_public_result_submission_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS public_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER NOT NULL,
                pairing_id INTEGER NOT NULL,
                board_number INTEGER NOT NULL DEFAULT 0,
                purpose TEXT NOT NULL DEFAULT 'result_submission',
                status TEXT NOT NULL DEFAULT 'active',
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                used_at TEXT DEFAULT '',
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS result_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER NOT NULL,
                pairing_id INTEGER NOT NULL,
                token_id INTEGER,
                board_number INTEGER NOT NULL DEFAULT 0,
                submitted_result TEXT NOT NULL,
                submitter TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'submitted',
                submitted_at TEXT NOT NULL,
                reviewed_at TEXT DEFAULT '',
                reviewer TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE CASCADE,
                FOREIGN KEY (token_id) REFERENCES public_tokens(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_public_tokens_hash
                ON public_tokens(token_hash);
            CREATE INDEX IF NOT EXISTS idx_public_tokens_pairing
                ON public_tokens(tournament_id, round_id, pairing_id, status);
            CREATE INDEX IF NOT EXISTS idx_result_submissions_status
                ON result_submissions(tournament_id, status, submitted_at);
            CREATE INDEX IF NOT EXISTS idx_result_submissions_pairing
                ON result_submissions(pairing_id, status);
            """
        )

    def _ensure_team_lineup_schema(self, connection: sqlite3.Connection) -> None:
        settings_columns = self.db._table_columns(connection, "tournament_settings")
        additions = {
            "team_board_order_policy": "TEXT NOT NULL DEFAULT 'fixed'",
            "team_reserve_policy": "TEXT NOT NULL DEFAULT 'same_team'",
            "team_lineup_deadline": "TEXT DEFAULT ''",
            "team_max_substitutions": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in additions.items():
            if column not in settings_columns:
                connection.execute(f"ALTER TABLE tournament_settings ADD COLUMN {column} {definition}")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS team_lineups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER NOT NULL,
                team_match_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'approved',
                submitted_at TEXT DEFAULT '',
                approved_at TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (round_id, team_match_id, team_id),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (team_match_id) REFERENCES team_matches(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS team_lineup_boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lineup_id INTEGER NOT NULL,
                board_number INTEGER NOT NULL,
                player_id INTEGER,
                color TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'starter',
                created_at TEXT NOT NULL,
                UNIQUE (lineup_id, board_number),
                FOREIGN KEY (lineup_id) REFERENCES team_lineups(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS team_substitution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER NOT NULL,
                team_match_id INTEGER NOT NULL,
                team_board_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                board_number INTEGER NOT NULL,
                color TEXT NOT NULL,
                out_player_id INTEGER,
                in_player_id INTEGER NOT NULL,
                reason TEXT DEFAULT '',
                requires_correction INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (team_match_id) REFERENCES team_matches(id) ON DELETE CASCADE,
                FOREIGN KEY (team_board_id) REFERENCES team_boards(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (out_player_id) REFERENCES players(id) ON DELETE SET NULL,
                FOREIGN KEY (in_player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_team_lineups_round
                ON team_lineups(tournament_id, round_id, team_id);
            CREATE INDEX IF NOT EXISTS idx_team_lineup_boards_lineup
                ON team_lineup_boards(lineup_id, board_number);
            CREATE INDEX IF NOT EXISTS idx_team_substitutions_round
                ON team_substitution_events(tournament_id, round_id, team_id);
            """
        )

    def _ensure_sync_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'assistant',
                status TEXT NOT NULL DEFAULT 'authorized',
                secret_hash TEXT DEFAULT '',
                last_seen_at TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                device_id TEXT NOT NULL DEFAULT '',
                tournament_id INTEGER,
                round_id INTEGER,
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id INTEGER,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                conflict_policy TEXT NOT NULL DEFAULT 'server_authoritative',
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT DEFAULT '',
                next_attempt_at TEXT DEFAULT '',
                synced_at TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_devices_status
                ON devices(status, role, name);
            CREATE INDEX IF NOT EXISTS idx_sync_outbox_status
                ON sync_outbox(status, next_attempt_at, created_at);
            CREATE INDEX IF NOT EXISTS idx_sync_outbox_tournament
                ON sync_outbox(tournament_id, status, created_at);
            """
        )

    def _ensure_clock_events_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS clock_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER,
                pairing_id INTEGER,
                board_number INTEGER NOT NULL DEFAULT 0,
                player_id INTEGER,
                device_id TEXT DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                event_type TEXT NOT NULL,
                side TEXT DEFAULT '',
                seconds_remaining INTEGER,
                note TEXT DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'logged',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL,
                FOREIGN KEY (pairing_id) REFERENCES pairings(id) ON DELETE SET NULL,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_clock_events_tournament
                ON clock_events(tournament_id, round_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_clock_events_pairing
                ON clock_events(pairing_id, event_type, occurred_at);
            """
        )

    def _ensure_tiebreak_components_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tiebreak_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_id INTEGER,
                round_number INTEGER NOT NULL DEFAULT 0,
                player_id INTEGER NOT NULL,
                player_name TEXT NOT NULL DEFAULT '',
                criterion TEXT NOT NULL,
                value REAL,
                components_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (tournament_id, round_id, player_id, criterion),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_tiebreak_components_player
                ON tiebreak_components(tournament_id, player_id, criterion);
            CREATE INDEX IF NOT EXISTS idx_tiebreak_components_round
                ON tiebreak_components(tournament_id, round_id);
            """
        )

    def _migrate_to_v30(self, connection: sqlite3.Connection) -> None:
        columns = self.db._table_columns(connection, "library_items")
        if "cover_image" not in columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN cover_image TEXT NOT NULL DEFAULT ''"
            )

    def _migrate_to_v31(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                channel TEXT NOT NULL DEFAULT 'email',
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                audience_kind TEXT NOT NULL DEFAULT 'all_active',
                audience_value TEXT DEFAULT '',
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result_summary TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                sent_at TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_scheduled_messages_status
                ON scheduled_messages(status, scheduled_at);
            """
        )

    def _migrate_to_v32(self, connection: sqlite3.Connection) -> None:
        """LBX (Liga Brasileira de Xadrez) como fonte de rating oficial: numero
        de registro proprio da LBX (ID_No) nos jogadores e arbitros, ao lado de
        fide_id/cbx_id. Aditivo e idempotente — bancos antigos so ganham a coluna
        que falta."""
        for table in ("players", "referees"):
            columns = self.db._table_columns(connection, table)
            if "lbx_id" not in columns:
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN lbx_id TEXT DEFAULT ''"
                )

    def _migrate_to_v33(self, connection: sqlite3.Connection) -> None:
        """Congela o horario final das rodadas fechadas para o relogio arbitral."""
        columns = self.db._table_columns(connection, "rounds")
        if "closed_at" not in columns:
            connection.execute("ALTER TABLE rounds ADD COLUMN closed_at TEXT DEFAULT ''")
        connection.execute(
            """
            UPDATE rounds
            SET closed_at = created_at
            WHERE status = 'closed' AND (closed_at IS NULL OR closed_at = '')
            """
        )

    def _migrate_to_v34(self, connection: sqlite3.Connection) -> None:
        """Adiciona taxas locais por base para prestacao de contas de rating."""
        columns = self.db._table_columns(connection, "tournament_settings")
        for column in ("rating_fee_fide", "rating_fee_cbx", "rating_fee_lbx"):
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE tournament_settings ADD COLUMN {column} REAL NOT NULL DEFAULT 0.0"
                )

    def _migrate_to_v35(self, connection: sqlite3.Connection) -> None:
        """Sequencia de desempates configuravel por torneio (individual e equipes).

        Coluna vazia preserva a ordem historica (pontos, Buchholz, Buchholz
        mediano, Sonneborn-Berger, vitorias), entao bancos antigos nao mudam de
        classificacao.
        """
        columns = self.db._table_columns(connection, "tournament_settings")
        for column in ("tiebreak_sequence", "team_tiebreak_sequence"):
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE tournament_settings ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                )

    def _migrate_to_v36(self, connection: sqlite3.Connection) -> None:
        """Relatorio de variacao de rating FIDE (Fase B) + fator K por jogador.

        Apenas adiciona a coluna opcional players.k_factor e cria a tabela de
        relatorios; nao altera dados existentes nem classificacoes.
        """
        player_columns = self.db._table_columns(connection, "players")
        if "k_factor" not in player_columns:
            connection.execute("ALTER TABLE players ADD COLUMN k_factor INTEGER")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS fide_rating_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                rating_type TEXT NOT NULL DEFAULT 'fide',
                ro INTEGER,
                k INTEGER,
                games_rated INTEGER,
                score REAL,
                we REAL,
                delta REAL,
                rc REAL,
                rp INTEGER,
                n_over_400 INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE (tournament_id, rating_type, player_id),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_fide_rating_reports_lookup
                ON fide_rating_reports(tournament_id, rating_type);
            """
        )

    def _migrate_to_v37(self, connection: sqlite3.Connection) -> None:
        """Distribuicao de premios (Fase C): tabela de premios + politica/imposto.

        Apenas adiciona colunas/ tabela novas; nao altera classificacoes nem
        premios ja calculados (nao havia premios estruturados antes).
        """
        settings_columns = self.db._table_columns(connection, "tournament_settings")
        if "prize_policy" not in settings_columns:
            connection.execute(
                "ALTER TABLE tournament_settings ADD COLUMN prize_policy TEXT NOT NULL DEFAULT 'best_only'"
            )
        if "prize_tax_percent" not in settings_columns:
            connection.execute(
                "ALTER TABLE tournament_settings ADD COLUMN prize_tax_percent REAL NOT NULL DEFAULT 0.0"
            )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tournament_prizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                kind TEXT NOT NULL DEFAULT 'overall',
                label TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                rank_from INTEGER NOT NULL DEFAULT 1,
                rank_to INTEGER NOT NULL DEFAULT 1,
                amount REAL NOT NULL DEFAULT 0,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_tournament_prizes_lookup
                ON tournament_prizes(tournament_id, position);
            """
        )

    def _migrate_to_v38(self, connection: sqlite3.Connection) -> None:
        """Layout configuravel de listas (Fase F): tabela report_layouts.

        Tabela nova e opcional; sem ela, as listas usam as colunas padrao.
        """
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS report_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                report_key TEXT NOT NULL,
                columns_json TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE (tournament_id, report_key),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
            );
            """
        )

    def _migrate_to_v39(self, connection: sqlite3.Connection) -> None:
        """Divisao de torneios (Fase I): vinculo opcional ao torneio de origem."""
        columns = self.db._table_columns(connection, "tournaments")
        if "parent_tournament_id" not in columns:
            connection.execute("ALTER TABLE tournaments ADD COLUMN parent_tournament_id INTEGER")
