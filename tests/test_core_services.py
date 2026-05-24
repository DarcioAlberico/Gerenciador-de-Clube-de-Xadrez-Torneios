from __future__ import annotations

import base64
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from src.core import database as database_module
from src.core.database import APP_DATA_DIR_ENV_VAR, Database, resolve_app_data_dir
from src.core.services import (
    AppError,
    CertificateService,
    ClubService,
    DashboardService,
    EventService,
    ExerciseService,
    ExportService,
    FinanceService,
    GuardianService,
    ImportService,
    InternalRatingService,
    InventoryService,
    LearningLevelService,
    MemberService,
    OfficialRatingService,
    PairingService,
    SecurityService,
    TeamService,
    TournamentService,
    TrainingService,
)


class PairingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.backup_dir = base_path / "backups"
        self.db = Database(base_path / "albericus.db", backup_dir=self.backup_dir)
        self.service = PairingService(self.db)
        self.club_service = ClubService(self.db)
        self.dashboard_service = DashboardService(self.db)
        self.guardian_service = GuardianService(self.db)
        self.member_service = MemberService(self.db)
        self.learning_level_service = LearningLevelService(self.db)
        self.training_service = TrainingService(self.db)
        self.exercise_service = ExerciseService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.event_service = EventService(self.db)
        self.import_service = ImportService(self.db)
        self.official_rating_service = OfficialRatingService(self.db)
        self.internal_rating_service = InternalRatingService(self.db)
        self.inventory_service = InventoryService(self.db)
        self.security_service = SecurityService(self.db)
        self.export_service = ExportService(self.db, self.service)
        self.certificate_service = CertificateService(self.db, self.service)
        self.finance_service = FinanceService(self.db)
        self.tournament_id = self.db.create_tournament("Torneio teste", rounds_count=5)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

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

    def _create_players(self, total: int) -> list[int]:
        player_ids = []
        for index in range(total):
            player_ids.append(
                self.db.create_player(
                    self.tournament_id,
                    name=f"Jogador {index + 1}",
                    rating=2000 - index * 50,
                    club="Clube",
                    category="Absoluto",
                )
            )
        return player_ids

    def _create_team_tournament(
        self,
        teams_count: int = 4,
        boards_count: int = 2,
    ) -> tuple[int, list[int]]:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Torneio por equipes",
                "competition_type": "team",
                "rounds_count": "5",
                "bye_points": "1",
            }
        )
        self.tournament_service.save_profile(
            tournament_id,
            {
                "name": "Torneio por equipes",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "5",
                "bye_points": "1",
            },
            {
                "team_boards_count": str(boards_count),
                "team_match_win_points": "2",
                "team_match_draw_points": "1",
                "team_match_loss_points": "0",
                "team_pairing_method": "swiss",
                "team_standing_primary": "match_points",
                "team_standing_secondary": "game_points",
            },
            [],
        )
        team_ids = []
        for team_index in range(teams_count):
            team_id = self.team_service.create_team(
                tournament_id,
                {
                    "name": f"Equipe {team_index + 1}",
                    "club": f"Clube {team_index + 1}",
                    "captain": f"Capitao {team_index + 1}",
                },
            )
            team_ids.append(team_id)
            for board_number in range(1, boards_count + 1):
                player_id = self.db.create_player(
                    tournament_id,
                    name=f"Equipe {team_index + 1} Jogador {board_number}",
                    rating=2200 - team_index * 100 - board_number * 10,
                    club=f"Clube {team_index + 1}",
                )
                self.team_service.add_player(team_id, player_id, board_number=str(board_number), role="starter")
        return tournament_id, team_ids

    def _fill_decisive_results(self, round_id: int) -> None:
        for pairing in self.db.get_pairings_for_round(round_id):
            if not pairing["is_bye"]:
                self.db.update_pairing_result(pairing["id"], "1-0")

    def _create_member_win(self, rating: int = 1600) -> tuple[int, int]:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Rating",
                "rating": str(rating),
                "member_type": "aluno",
                "status": "active",
            }
        )
        member_player_id = self.member_service.register_member_in_tournament(
            self.tournament_id,
            member_id,
        )
        self.db.create_player(
            self.tournament_id,
            name="Oponente",
            rating=1500,
            club="Clube",
            category="Absoluto",
        )
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(round_data["id"])[0]
        result = "1-0" if pairing["white_player_id"] == member_player_id else "0-1"
        self.db.update_pairing_result(pairing["id"], result)
        self.service.close_round(self.tournament_id, round_data["id"])
        return member_id, member_player_id

    def test_tournament_service_validates_creation_payload(self) -> None:
        with self.assertRaises(AppError):
            self.tournament_service.create_tournament(
                {"name": "Invalido", "rounds_count": "0", "bye_points": "1"}
            )
        with self.assertRaises(AppError):
            self.tournament_service.create_tournament(
                {"name": "Invalido", "rounds_count": "3", "bye_points": "-1"}
            )
        with self.assertRaises(AppError):
            self.tournament_service.create_tournament(
                {
                    "name": "Invalido",
                    "rounds_count": "3",
                    "bye_points": "1",
                    "start_date": "2026-05-14",
                    "end_date": "2026-05-13",
                }
            )

        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Valido",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "0.5",
                "start_date": "2026-05-13",
                "end_date": "2026-05-14",
            }
        )
        tournament = self.db.get_tournament(tournament_id)
        self.assertIsNotNone(tournament)
        self.assertEqual(tournament["rounds_count"], 3)
        self.assertEqual(tournament["bye_points"], 0.5)

    def test_tournament_creation_accepts_brazilian_date_format(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Data brasileira",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
                "start_date": "13/05/2026",
                "end_date": "14/05/2026",
            }
        )

        tournament = self.db.get_tournament(tournament_id)
        self.assertIsNotNone(tournament)
        self.assertEqual(tournament["start_date"], "2026-05-13")
        self.assertEqual(tournament["end_date"], "2026-05-14")

    def test_player_competition_categories_use_tournament_year_and_rating(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Categorias automaticas",
                "scope": "standalone",
                "location": "Sao Paulo",
                "start_date": "2024-05-01",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

        player_id = self.db.create_player(
            tournament_id,
            name="Jovem Local",
            rating=1399,
            club="Sao Paulo",
            birth_date="2008-01-01",
            sex="F",
        )
        player = self.db.get_player(player_id)

        self.assertIsNotNone(player)
        self.assertEqual(player["category"], "Sub-16")
        self.assertEqual(player["age_category"], "Sub-16")
        self.assertEqual(player["rating_category"], "Sub-1400")
        self.assertEqual(player["prize_tags"], "Feminino; Melhor Local")

    def test_member_registration_recalculates_age_category_for_tournament_year(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Sub",
                "birth_date": "2008-01-01",
                "rating": "1500",
                "member_type": "socio",
                "status": "active",
            }
        )
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Torneio Sub",
                "scope": "club",
                "club_id": "1",
                "start_date": "2024-06-01",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

        player_id = self.member_service.register_member_in_tournament(tournament_id, member_id)
        player = self.db.get_player(player_id)

        self.assertIsNotNone(player)
        self.assertEqual(player["category"], "Sub-16")
        self.assertEqual(player["age_category"], "Sub-16")
        self.assertEqual(player["rating_category"], "Sub-1800")
        self.assertEqual(player["prize_tags"], "Socio do Clube")

    def test_learning_levels_can_be_assigned_to_members(self) -> None:
        default_levels = self.db.list_learning_levels(active_only=True)
        self.assertGreaterEqual(len(default_levels), 5)
        self.assertEqual(default_levels[0]["name"], "Iniciante")

        level_id = self.learning_level_service.create_level(
            {
                "name": "Pre-competitivo",
                "description": "Pronto para torneios internos.",
                "display_order": "45",
            }
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Nivel",
                "member_type": "aluno",
                "status": "active",
                "learning_level_id": str(level_id),
            }
        )

        member = self.db.get_member(member_id)
        levels = self.db.list_learning_levels(active_only=False)
        custom_level = self.db.get_learning_level(level_id)

        self.assertIsNotNone(member)
        self.assertEqual(member["learning_level_id"], level_id)
        self.assertEqual(member["learning_level_name"], "Pre-competitivo")
        self.assertEqual(custom_level["members_count"], 1)
        self.assertIn("Pre-competitivo", {level["name"] for level in levels})

        self.member_service.update_member(
            member_id,
            {
                "name": "Aluno Nivel",
                "member_type": "aluno",
                "status": "active",
                "learning_level_id": "",
            },
        )
        self.assertIsNone(self.db.get_member(member_id)["learning_level_id"])

        with self.assertRaisesRegex(AppError, "Nivel de aprendizagem"):
            self.member_service.update_member(
                member_id,
                {
                    "name": "Aluno Nivel",
                    "member_type": "aluno",
                    "status": "active",
                    "learning_level_id": "99999",
                },
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
                        AND name IN ('teams', 'team_players', 'team_matches', 'team_boards')
                    """
                ).fetchall()
            }
            team_indexes = {
                row["name"]
                for table_name in ("teams", "team_players", "team_matches", "team_boards")
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
            audit_indexes = {
                row["name"]
                for row in connection.execute("PRAGMA index_list(audit_log)").fetchall()
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
        self.assertIn("team_boards_count", settings_columns)
        self.assertIn("team_match_win_points", settings_columns)
        self.assertIn("team_standing_primary", settings_columns)
        self.assertIn("team_standing_secondary", settings_columns)
        self.assertIn("learning_level_id", member_columns)
        self.assertIn("training_list_id", training_session_columns)
        self.assertEqual({"learning_levels"}, learning_tables)
        self.assertIn("idx_learning_levels_order", learning_indexes)
        self.assertIn("idx_pairings_white_player", pairing_indexes)
        self.assertIn("idx_pairings_black_player", pairing_indexes)
        self.assertEqual({"teams", "team_players", "team_matches", "team_boards"}, team_tables)
        self.assertIn("idx_teams_tournament", team_indexes)
        self.assertIn("idx_team_matches_round", team_indexes)
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
        self.assertIn("idx_audit_log_created", audit_indexes)
        self.assertIn("idx_audit_log_entity", audit_indexes)
        self.assertGreaterEqual(certificate_template_count, 7)
        self.assertIn("logo_path", certificate_template_columns)
        self.assertIn("background_image_path", certificate_template_columns)
        self.assertIn("background_opacity", certificate_template_columns)
        self.assertIn("secondary_logo_path", certificate_template_columns)
        self.assertIn("primary_color", certificate_template_columns)
        self.assertIn("accent_color", certificate_template_columns)
        self.assertIn("title_font_size", certificate_template_columns)

    def test_team_tournament_storage_foundation(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Interclubes",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        tournament = self.db.get_tournament(tournament_id)

        self.assertIsNotNone(tournament)
        self.assertEqual(tournament["competition_type"], "team")

        players = [
            self.db.create_player(tournament_id, name="Equipe A 1", rating=2100, club="A"),
            self.db.create_player(tournament_id, name="Equipe A 2", rating=2000, club="A"),
            self.db.create_player(tournament_id, name="Equipe B 1", rating=2050, club="B"),
            self.db.create_player(tournament_id, name="Equipe B 2", rating=1950, club="B"),
        ]
        team_a = self.db.create_team(tournament_id, "Equipe A", club="A", captain="Capitao A")
        team_b = self.db.create_team(tournament_id, "Equipe B", club="B", captain="Capitao B")
        self.db.add_player_to_team(team_a, players[0], board_number=1)
        self.db.add_player_to_team(team_a, players[1], board_number=2)
        self.db.add_player_to_team(team_b, players[2], board_number=1)
        self.db.add_player_to_team(team_b, players[3], board_number=2)

        teams = self.db.list_teams(tournament_id)
        team_players = self.db.list_team_players(team_a)

        self.assertEqual([team["name"] for team in teams], ["Equipe A", "Equipe B"])
        self.assertEqual(teams[0]["starters_count"], 2)
        self.assertEqual([player["board_number"] for player in team_players], [1, 2])

        round_id = self.db.create_round_with_team_matches(
            tournament_id,
            1,
            [
                {
                    "match_number": 1,
                    "white_team_id": team_a,
                    "black_team_id": team_b,
                    "boards": [
                        {
                            "board_number": 1,
                            "white_player_id": players[0],
                            "black_player_id": players[2],
                        },
                        {
                            "board_number": 2,
                            "white_player_id": players[3],
                            "black_player_id": players[1],
                        },
                    ],
                }
            ],
        )
        matches = self.db.list_team_matches_for_round(round_id)
        boards = self.db.list_team_boards(matches[0]["id"])

        self.assertEqual(matches[0]["white_team_name"], "Equipe A")
        self.assertEqual(matches[0]["black_team_name"], "Equipe B")
        self.assertEqual([board["board_number"] for board in boards], [1, 2])
        self.assertEqual(boards[0]["white_player_name"], "Equipe A 1")

    def test_team_service_validates_team_roster(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Equipes validacao",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        player_a = self.db.create_player(tournament_id, name="Titular A", rating=1900)
        player_b = self.db.create_player(tournament_id, name="Titular B", rating=1800)
        team_id = self.team_service.create_team(
            tournament_id,
            {"name": "Equipe Azul", "club": "Clube", "captain": "Capitao"},
        )

        assignment_id = self.team_service.add_player(team_id, player_a, board_number="1", role="starter")
        assignment = self.db.get_team_player(assignment_id)

        self.assertIsNotNone(assignment)
        self.assertEqual(assignment["board_number"], 1)
        self.assertEqual(assignment["role"], "starter")

        with self.assertRaisesRegex(AppError, "tabuleiro"):
            self.team_service.add_player(team_id, player_b, board_number="1", role="starter")

        with self.assertRaisesRegex(AppError, "equipe Equipe Azul"):
            self.team_service.add_player(team_id, player_a, board_number="2", role="starter")

        self.team_service.add_player(team_id, player_b, board_number="", role="reserve")
        players = self.db.list_team_players(team_id)
        self.assertEqual([player["role"] for player in players], ["starter", "reserve"])

    def test_team_service_rejects_individual_tournament(self) -> None:
        with self.assertRaisesRegex(AppError, "formato Equipes"):
            self.team_service.create_team(self.tournament_id, {"name": "Equipe indevida"})

    def test_team_service_deletes_only_unused_teams(self) -> None:
        tournament_id, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        unused_team_id = self.team_service.create_team(tournament_id, {"name": "Equipe sem rodada"})

        self.team_service.delete_team(unused_team_id)

        self.assertIsNone(self.db.get_team(unused_team_id))

        self.service.generate_next_round(tournament_id)

        with self.assertRaisesRegex(AppError, "preservar o historico"):
            self.team_service.delete_team(team_ids[0])

        self.assertIsNotNone(self.db.get_team(team_ids[0]))
        self.assertGreater(self.db.count_team_matches(team_ids[0]), 0)

    def test_team_tournament_settings_are_saved_and_validate_board_limit(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Equipes regras",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        player_id = self.db.create_player(tournament_id, name="Segundo tabuleiro", rating=1800)
        team_id = self.team_service.create_team(tournament_id, {"name": "Equipe Regras"})
        self.team_service.add_player(team_id, player_id, board_number="2", role="starter")

        self.tournament_service.save_profile(
            tournament_id,
            {
                "name": "Equipes regras",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {
                "team_boards_count": "2",
                "team_match_win_points": "3",
                "team_match_draw_points": "1",
                "team_match_loss_points": "0",
                "team_pairing_method": "swiss",
                "team_standing_primary": "match_points",
                "team_standing_secondary": "game_points",
            },
            [],
        )
        settings = self.db.get_tournament_settings(tournament_id)

        self.assertEqual(settings["team_boards_count"], 2)
        self.assertEqual(settings["team_match_win_points"], 3.0)
        self.assertEqual(settings["team_match_draw_points"], 1.0)
        self.assertEqual(settings["team_match_loss_points"], 0.0)
        self.assertEqual(settings["team_pairing_method"], "swiss")
        self.assertEqual(settings["team_standing_primary"], "match_points")
        self.assertEqual(settings["team_standing_secondary"], "game_points")

        with self.assertRaisesRegex(AppError, "tabuleiro 2"):
            self.tournament_service.save_profile(
                tournament_id,
                {
                    "name": "Equipes regras",
                    "competition_type": "team",
                    "scope": "standalone",
                    "rounds_count": "3",
                    "bye_points": "1",
                },
                {
                    "team_boards_count": "1",
                    "team_match_win_points": "3",
                    "team_match_draw_points": "1",
                    "team_match_loss_points": "0",
                    "team_pairing_method": "swiss",
                    "team_standing_primary": "match_points",
                    "team_standing_secondary": "game_points",
                },
                [],
            )

    def test_team_standing_criteria_must_be_different(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Equipes criterios",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

        with self.assertRaisesRegex(AppError, "criterios diferentes"):
            self.tournament_service.save_profile(
                tournament_id,
                {
                    "name": "Equipes criterios",
                    "competition_type": "team",
                    "scope": "standalone",
                    "rounds_count": "3",
                    "bye_points": "1",
                },
                {
                    "team_boards_count": "4",
                    "team_standing_primary": "match_points",
                    "team_standing_secondary": "match_points",
                },
                [],
            )

    def test_invalid_competition_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(AppError, "Formato do torneio invalido"):
            self.tournament_service.create_tournament(
                {
                    "name": "Formato invalido",
                    "competition_type": "duplas",
                    "rounds_count": "3",
                    "bye_points": "1",
                }
            )

    def test_close_round_creates_backup_and_updates_standings(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(round_data["id"])

        self.service.close_round(self.tournament_id, round_data["id"])

        backups = list(self.backup_dir.glob("*.db"))
        standings = self.service.standings(self.tournament_id)
        closed_round = self.db.get_round(round_data["id"])

        self.assertEqual(closed_round["status"], "closed")
        self.assertEqual(len(backups), 1)
        self.assertEqual(standings[0]["points"], 1.0)

    def test_team_pairing_generates_matches_and_boards(self) -> None:
        tournament_id, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)

        round_data = self.service.generate_next_round(tournament_id)
        matches = self.db.list_team_matches_for_round(round_data["id"])
        individual_pairings = self.db.get_pairings_for_round(round_data["id"])

        self.assertEqual(len(matches), 2)
        self.assertEqual(individual_pairings, [])
        scheduled_players = []
        for match in matches:
            boards = self.db.list_team_boards(int(match["id"]))
            self.assertEqual(len(boards), 2)
            self.assertFalse(match["is_bye"])
            scheduled_players.extend(
                player_id
                for board in boards
                for player_id in (board["white_player_id"], board["black_player_id"])
                if player_id
            )
            white_roster = self.db.list_team_players(int(match["white_team_id"]))
            black_roster = self.db.list_team_players(int(match["black_team_id"]))
            white_board_1 = next(item for item in white_roster if item["board_number"] == 1)
            white_board_2 = next(item for item in white_roster if item["board_number"] == 2)
            black_board_1 = next(item for item in black_roster if item["board_number"] == 1)
            black_board_2 = next(item for item in black_roster if item["board_number"] == 2)
            self.assertEqual(boards[0]["white_player_id"], white_board_1["player_id"])
            self.assertEqual(boards[0]["black_player_id"], black_board_1["player_id"])
            self.assertEqual(boards[1]["white_player_id"], black_board_2["player_id"])
            self.assertEqual(boards[1]["black_player_id"], white_board_2["player_id"])

        all_team_players = [
            item["player_id"]
            for team_id in team_ids
            for item in self.db.list_team_players(team_id)
        ]
        self.assertCountEqual(scheduled_players, all_team_players)

    def test_team_swiss_pairing_avoids_repeat_when_possible(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=4, boards_count=2)

        first_round = self.service.generate_next_round(tournament_id)
        first_matches = self.db.list_team_matches_for_round(first_round["id"])
        first_pairs = {
            frozenset((match["white_team_id"], match["black_team_id"]))
            for match in first_matches
            if not match["is_bye"]
        }
        for match in first_matches:
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(tournament_id, int(board["id"]), "1-0")
        self.service.close_round(tournament_id, first_round["id"])

        second_round = self.service.generate_next_round(tournament_id)
        second_pairs = {
            frozenset((match["white_team_id"], match["black_team_id"]))
            for match in self.db.list_team_matches_for_round(second_round["id"])
            if not match["is_bye"]
        }

        self.assertTrue(first_pairs.isdisjoint(second_pairs))

    def test_odd_team_count_gets_team_bye(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=3, boards_count=2)

        round_data = self.service.generate_next_round(tournament_id)
        matches = self.db.list_team_matches_for_round(round_data["id"])
        bye_matches = [match for match in matches if match["is_bye"]]

        self.assertEqual(len(matches), 2)
        self.assertEqual(len(bye_matches), 1)
        self.assertEqual(bye_matches[0]["result"], "BYE")
        self.assertEqual(self.db.list_team_boards(int(bye_matches[0]["id"])), [])

    def test_team_round_close_calculates_match_summary_and_standings(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))

        self.service.update_result(tournament_id, int(boards[0]["id"]), "1-0")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "0-1")
        self.service.close_round(tournament_id, round_data["id"])

        updated_match = self.db.list_team_matches_for_round(round_data["id"])[0]
        standings = self.service.team_standings(tournament_id)

        self.assertEqual(updated_match["result"], "1-0")
        self.assertEqual(updated_match["white_game_points"], 2.0)
        self.assertEqual(updated_match["black_game_points"], 0.0)
        self.assertEqual(updated_match["white_match_points"], 2.0)
        self.assertEqual(updated_match["black_match_points"], 0.0)
        self.assertEqual(standings[0]["team_id"], updated_match["white_team_id"])
        self.assertEqual(standings[0]["match_points"], 2.0)
        self.assertEqual(standings[0]["game_points"], 2.0)
        self.assertEqual(standings[0]["wins"], 1)
        self.assertEqual(self.db.get_round(round_data["id"])["status"], "closed")

    def test_team_round_cannot_close_with_pending_board_result(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))

        self.service.update_result(tournament_id, int(boards[0]["id"]), "1-0")

        with self.assertRaisesRegex(AppError, "resultados dos tabuleiros"):
            self.service.close_round(tournament_id, round_data["id"])

    def test_odd_player_count_does_not_repeat_bye_next_round(self) -> None:
        self._create_players(5)
        first_round = self.service.generate_next_round(self.tournament_id)
        first_bye = [
            pairing["white_player_id"]
            for pairing in self.db.get_pairings_for_round(first_round["id"])
            if pairing["is_bye"]
        ][0]
        self._fill_decisive_results(first_round["id"])
        self.service.close_round(self.tournament_id, first_round["id"])

        second_round = self.service.generate_next_round(self.tournament_id)
        second_bye = [
            pairing["white_player_id"]
            for pairing in self.db.get_pairings_for_round(second_round["id"])
            if pairing["is_bye"]
        ][0]

        self.assertNotEqual(first_bye, second_bye)

    def test_swiss_pairing_uses_global_matching_to_avoid_repeat_when_possible(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {"name": "Pareamento global", "rounds_count": "20", "bye_points": "1"}
        )
        player_ids = [
            self.db.create_player(
                tournament_id,
                name=f"Jogador {index + 1}",
                rating=2000 - index * 10,
                club="Clube",
                category="Absoluto",
            )
            for index in range(6)
        ]
        allowed_pairs = {
            frozenset((player_ids[0], player_ids[1])),
            frozenset((player_ids[0], player_ids[2])),
            frozenset((player_ids[1], player_ids[3])),
            frozenset((player_ids[4], player_ids[5])),
        }
        played_pairs = [
            (white_id, black_id)
            for index, white_id in enumerate(player_ids)
            for black_id in player_ids[index + 1 :]
            if frozenset((white_id, black_id)) not in allowed_pairs
        ]
        for round_number, (white_id, black_id) in enumerate(played_pairs, start=1):
            round_id = self.db.create_round_with_pairings(
                tournament_id,
                round_number,
                [
                    {
                        "board_number": 1,
                        "white_player_id": white_id,
                        "black_player_id": black_id,
                        "result": "0F-0F",
                        "is_bye": 0,
                    }
                ],
            )
            self.db.close_round(round_id)

        next_round = self.service.generate_next_round(tournament_id)
        generated_pairs = {
            frozenset((pairing["white_player_id"], pairing["black_player_id"]))
            for pairing in self.db.get_pairings_for_round(next_round["id"])
            if not pairing["is_bye"]
        }

        self.assertTrue(generated_pairs.issubset(allowed_pairs))
        self.assertEqual(
            {
                frozenset((player_ids[0], player_ids[2])),
                frozenset((player_ids[1], player_ids[3])),
                frozenset((player_ids[4], player_ids[5])),
            },
            generated_pairs,
        )

    def test_swiss_pairing_keeps_score_groups_when_possible(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {"name": "Grupos de pontuacao", "rounds_count": "5", "bye_points": "1"}
        )
        player_ids = [
            self.db.create_player(
                tournament_id,
                name=f"Jogador {index + 1}",
                rating=2000 - index * 10,
                club="Clube",
                category="Absoluto",
                starting_points=starting_points,
            )
            for index, starting_points in enumerate([2.0, 2.0, 1.0, 1.0, 0.0, 0.0])
        ]
        previous_round_id = self.db.create_round_with_pairings(tournament_id, 1, [])
        self.db.close_round(previous_round_id)

        next_round = self.service.generate_next_round(tournament_id)
        points_by_player = {
            item["player_id"]: item["points"]
            for item in self.service.standings(tournament_id)
        }

        for pairing in self.db.get_pairings_for_round(next_round["id"]):
            if pairing["is_bye"]:
                continue
            self.assertEqual(
                points_by_player[pairing["white_player_id"]],
                points_by_player[pairing["black_player_id"]],
            )
        self.assertCountEqual(
            [
                player_id
                for pairing in self.db.get_pairings_for_round(next_round["id"])
                for player_id in (pairing["white_player_id"], pairing["black_player_id"])
                if player_id
            ],
            player_ids,
        )

    def test_swiss_pairing_avoids_repeating_same_float_when_possible(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {"name": "Historico de flutuacao", "rounds_count": "5", "bye_points": "1"}
        )
        player_ids = [
            self.db.create_player(
                tournament_id,
                name=f"Jogador {index + 1}",
                rating=2000 - index * 10,
                club="Clube",
                category="Absoluto",
                starting_points=starting_points,
            )
            for index, starting_points in enumerate([2.0, 2.0, 2.0, 1.0, 1.0, 1.0])
        ]
        prior_floater = player_ids[3]
        prior_round_id = self.db.create_round_with_pairings(
            tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": player_ids[0],
                    "black_player_id": prior_floater,
                    "result": "0F-0F",
                    "is_bye": 0,
                }
            ],
        )
        self.db.close_round(prior_round_id)

        next_round = self.service.generate_next_round(tournament_id)
        high_score_players = set(player_ids[:3])
        lower_score_players = set(player_ids[3:])
        cross_pairs = []
        for pairing in self.db.get_pairings_for_round(next_round["id"]):
            if pairing["is_bye"]:
                continue
            pair = {pairing["white_player_id"], pairing["black_player_id"]}
            if pair & high_score_players and pair & lower_score_players:
                cross_pairs.append(pair)

        self.assertEqual(1, len(cross_pairs))
        lower_floater = next(iter(cross_pairs[0] & lower_score_players))
        self.assertNotEqual(prior_floater, lower_floater)

    def test_adjust_pairing_player_swaps_players_between_slots(self) -> None:
        player_ids = self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])
        first_pairing = pairings[0]
        second_pairing = pairings[1]

        source_player_id = first_pairing["white_player_id"]
        replacement_player_id = second_pairing["black_player_id"]
        self.service.adjust_pairing_player(
            self.tournament_id,
            round_data["id"],
            first_pairing["id"],
            "white",
            replacement_player_id,
        )

        updated_pairings = self.db.get_pairings_for_round(round_data["id"])
        updated_first = next(pairing for pairing in updated_pairings if pairing["id"] == first_pairing["id"])
        updated_second = next(pairing for pairing in updated_pairings if pairing["id"] == second_pairing["id"])
        scheduled_player_ids = []
        for pairing in updated_pairings:
            scheduled_player_ids.append(pairing["white_player_id"])
            if pairing["black_player_id"]:
                scheduled_player_ids.append(pairing["black_player_id"])

        self.assertEqual(updated_first["white_player_id"], replacement_player_id)
        self.assertEqual(updated_second["black_player_id"], source_player_id)
        self.assertCountEqual(scheduled_player_ids, player_ids)

    def test_member_registration_creates_linked_tournament_player(self) -> None:
        self.db.save_club("Clube Teste", city="Curitiba")
        member_id = self.member_service.create_member(
            {
                "name": "Ana Membro",
                "rating": "1800",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )

        player_id = self.member_service.register_member_in_tournament(self.tournament_id, member_id)
        player = self.db.get_player(player_id)

        self.assertEqual(player["member_id"], member_id)
        self.assertEqual(player["name"], "Ana Membro")
        self.assertEqual(player["club"], "Clube Teste")

    def test_member_surname_formats_tournament_player_name(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Lucas",
                "surname": "Costa",
                "rating": "1700",
                "member_type": "aluno",
                "status": "active",
            }
        )

        player_id = self.member_service.register_member_in_tournament(self.tournament_id, member_id)
        member = self.db.get_member(member_id)
        player = self.db.get_player(player_id)

        self.assertEqual(member["surname"], "Costa")
        self.assertEqual(player["name"], "Lucas Costa")
        self.assertEqual(player["surname"], "Costa")
        self.assertEqual(player["given_name"], "Lucas")

    def test_pairings_use_inverted_names_and_standings_use_full_names(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Lucas",
            surname="Lima",
            given_name="Lucas",
            rating=1800,
        )
        self.db.create_player(
            self.tournament_id,
            name="Rafael",
            surname="Cruz",
            given_name="Rafael",
            rating=1700,
        )

        standings_names = [item["name"] for item in self.service.standings(self.tournament_id)]
        self.assertIn("Lucas Lima", standings_names)
        self.assertIn("Rafael Cruz", standings_names)
        self.assertNotIn("Lima, Lucas", standings_names)

        round_data = self.service.generate_next_round(self.tournament_id)
        _title, _headers, rows = self.export_service._pairings_section(round_data["id"])
        pairing_names = {str(row[1]) for row in rows} | {str(row[4]) for row in rows if row[4] != "BYE"}

        self.assertIn("Lima, Lucas", pairing_names)
        self.assertIn("Cruz, Rafael", pairing_names)
        self.assertNotIn("Lucas Lima", pairing_names)

    def test_delete_unpaired_player_removes_registration(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Cadastro errado",
            rating=1200,
        )

        self.service.delete_player_if_unpaired(self.tournament_id, player_id)

        self.assertIsNone(self.db.get_player(player_id))

    def test_delete_paired_player_is_blocked_to_preserve_history(self) -> None:
        player_ids = self._create_players(2)
        self.service.generate_next_round(self.tournament_id)

        with self.assertRaises(AppError):
            self.service.delete_player_if_unpaired(self.tournament_id, player_ids[0])

        self.assertIsNotNone(self.db.get_player(player_ids[0]))

    def test_member_statuses_control_tournament_registration_eligibility(self) -> None:
        active_id = self.member_service.create_member(
            {
                "name": "Ativo",
                "member_type": "socio",
                "status": "active",
            }
        )
        visitor_id = self.member_service.create_member(
            {
                "name": "Visitante",
                "member_type": "visitante",
                "status": "visitor",
            }
        )
        guest_id = self.member_service.create_member(
            {
                "name": "Convidado",
                "member_type": "convidado",
                "status": "guest",
            }
        )
        withdrawn_id = self.member_service.create_member(
            {
                "name": "Desistente",
                "member_type": "aluno",
                "status": "withdrawn",
            }
        )

        eligible = self.db.list_members_for_tournament(self.tournament_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}

        self.assertIn(active_id, eligible_ids)
        self.assertNotIn(visitor_id, eligible_ids)
        self.assertNotIn(guest_id, eligible_ids)
        self.assertNotIn(withdrawn_id, eligible_ids)

        with self.assertRaises(AppError):
            self.member_service.register_member_in_tournament(self.tournament_id, visitor_id)

    def test_school_classes_filter_members_for_tournament_registration(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Alpha",
                "kind": "school",
                "city": "Teresina",
                "active": 1,
            },
            club_id=None,
        )
        other_club_id = self.club_service.save_profile(
            {
                "name": "Clube Beta",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma A",
                "teacher": "Professora",
                "weekday": "Segunda",
                "time": "14:00",
                "active": 1,
            }
        )
        school_member_id = self.member_service.create_member(
            {
                "name": "Aluno Escola",
                "rating": "1500",
                "club_id": school_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        other_member_id = self.member_service.create_member(
            {
                "name": "Aluno Outro Clube",
                "rating": "1450",
                "club_id": other_club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        school_tournament_id = self.db.create_tournament(
            "Interclasse",
            club_id=school_id,
            rounds_count=3,
        )

        eligible = self.db.list_members_for_tournament(school_tournament_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}
        player_id = self.member_service.register_member_in_tournament(
            school_tournament_id,
            school_member_id,
        )
        player = self.db.get_player(player_id)
        member = self.db.get_member(school_member_id)
        class_data = self.db.list_classes(club_id=school_id)[0]

        self.assertIn(school_member_id, eligible_ids)
        self.assertNotIn(other_member_id, eligible_ids)
        self.assertEqual(player["club"], "Escola Alpha")
        self.assertEqual(member["club_name"], "Escola Alpha")
        self.assertEqual(member["active_class_name"], "Turma A")
        self.assertEqual(class_data["active_members_count"], 1)

    def test_standalone_tournament_accepts_members_from_any_club(self) -> None:
        club_a_id = self.club_service.save_profile(
            {
                "name": "Clube A",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        club_b_id = self.club_service.save_profile(
            {
                "name": "Clube B",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        member_a_id = self.member_service.create_member(
            {
                "name": "Jogador A",
                "club_id": club_a_id,
                "status": "active",
            }
        )
        member_b_id = self.member_service.create_member(
            {
                "name": "Jogador B",
                "club_id": club_b_id,
                "status": "active",
            }
        )
        standalone_id = self.db.create_tournament(
            "Avulso",
            club_id=None,
            class_id=None,
            rounds_count=3,
        )

        eligible = self.db.list_members_for_tournament(standalone_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}
        player_id = self.member_service.register_member_in_tournament(standalone_id, member_b_id)

        self.assertIn(member_a_id, eligible_ids)
        self.assertIn(member_b_id, eligible_ids)
        self.assertIsNotNone(self.db.get_player(player_id))
        self.assertIsNone(self.db.get_tournament(standalone_id)["club_id"])

    def test_class_tournament_filters_members_by_class(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Gamma",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_a_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma A",
                "active": 1,
            }
        )
        class_b_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma B",
                "active": 1,
            }
        )
        class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma A",
                "club_id": school_id,
                "class_id": class_a_id,
                "status": "active",
            }
        )
        other_class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma B",
                "club_id": school_id,
                "class_id": class_b_id,
                "status": "active",
            }
        )
        no_class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Sem Turma",
                "club_id": school_id,
                "status": "active",
            }
        )
        class_tournament_id = self.db.create_tournament(
            "Interturma A",
            club_id=school_id,
            class_id=class_a_id,
            rounds_count=3,
        )

        eligible = self.db.list_members_for_tournament(class_tournament_id, active_only=True)
        eligible_ids = {member["id"] for member in eligible}
        player_id = self.member_service.register_member_in_tournament(
            class_tournament_id,
            class_member_id,
        )

        self.assertEqual(eligible_ids, {class_member_id})
        self.assertIsNotNone(self.db.get_player(player_id))
        self.assertEqual(self.db.get_tournament(class_tournament_id)["class_name"], "Turma A")
        self.assertNotIn(other_class_member_id, eligible_ids)
        self.assertNotIn(no_class_member_id, eligible_ids)
        with self.assertRaises(AppError):
            self.member_service.register_member_in_tournament(class_tournament_id, other_class_member_id)

    def test_class_tournament_can_import_members_from_other_classes_when_allowed(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Delta",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_a_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma A",
                "active": 1,
            }
        )
        class_b_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma B",
                "active": 1,
            }
        )
        class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma A",
                "club_id": school_id,
                "class_id": class_a_id,
                "status": "active",
            }
        )
        other_class_member_id = self.member_service.create_member(
            {
                "name": "Aluno Turma B",
                "club_id": school_id,
                "class_id": class_b_id,
                "status": "active",
            }
        )
        class_tournament_id = self.db.create_tournament(
            "Interturma com convidados",
            club_id=school_id,
            class_id=class_a_id,
            rounds_count=3,
        )

        scoped = self.db.list_members_for_tournament(class_tournament_id, active_only=True)
        all_available = self.db.list_members_for_tournament(
            class_tournament_id,
            active_only=True,
            include_out_of_scope=True,
        )
        imported_player_id = self.member_service.register_member_in_tournament(
            class_tournament_id,
            other_class_member_id,
            allow_out_of_scope=True,
        )
        result = self.member_service.register_active_members_in_tournament(
            class_tournament_id,
            include_out_of_scope=True,
        )

        self.assertEqual({member["id"] for member in scoped}, {class_member_id})
        self.assertEqual({member["id"] for member in all_available}, {class_member_id, other_class_member_id})
        self.assertEqual(self.db.get_player(imported_player_id)["member_id"], other_class_member_id)
        self.assertEqual(result["registered"], 1)
        self.assertEqual(result["skipped"], 1)

    def test_guardian_links_multiple_members_and_keeps_one_primary_contact(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno menor",
                "birth_date": f"{date.today().year - 12}-01-01",
                "member_type": "aluno",
                "status": "active",
            }
        )
        sibling_id = self.member_service.create_member(
            {
                "name": "Irmao menor",
                "birth_date": f"{date.today().year - 10}-01-01",
                "member_type": "aluno",
                "status": "active",
            }
        )
        mother_id = self.guardian_service.create_guardian(
            {"name": "Maria Responsavel", "phone": "1111", "email": "maria@example.com"}
        )
        father_id = self.guardian_service.create_guardian(
            {"name": "Jose Responsavel", "phone": "2222"}
        )

        self.guardian_service.link_guardian_to_member(
            {
                "member_id": member_id,
                "guardian_id": mother_id,
                "relationship": "Mae",
                "primary_contact": 1,
                "emergency_contact": 1,
            }
        )
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": member_id,
                "guardian_id": father_id,
                "relationship": "Pai",
                "primary_contact": 1,
            }
        )
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": sibling_id,
                "guardian_id": mother_id,
                "relationship": "Mae",
                "primary_contact": 1,
            }
        )

        member_guardians = self.db.list_member_guardians(member_id)
        mother_members = self.db.list_guardian_members(mother_id)

        self.assertEqual(len(member_guardians), 2)
        self.assertEqual(member_guardians[0]["guardian_id"], father_id)
        self.assertEqual(member_guardians[0]["primary_contact"], 1)
        self.assertEqual(member_guardians[1]["primary_contact"], 0)
        self.assertCountEqual(
            [item["member_id"] for item in mother_members],
            [member_id, sibling_id],
        )

    def test_minor_members_without_guardians_filters_only_active_minors(self) -> None:
        minor_id = self.member_service.create_member(
            {
                "name": "Menor sem responsavel",
                "birth_date": f"{date.today().year - 9}-01-01",
                "member_type": "aluno",
                "status": "active",
            }
        )
        adult_id = self.member_service.create_member(
            {
                "name": "Adulto",
                "birth_date": f"{date.today().year - 30}-01-01",
                "member_type": "socio",
                "status": "active",
            }
        )
        inactive_minor_id = self.member_service.create_member(
            {
                "name": "Menor inativo",
                "birth_date": f"{date.today().year - 11}-01-01",
                "member_type": "aluno",
                "status": "inactive",
            }
        )
        guardian_id = self.guardian_service.create_guardian({"name": "Responsavel"})

        missing_before = self.guardian_service.minor_members_without_guardians()
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": minor_id,
                "guardian_id": guardian_id,
                "relationship": "Responsavel",
                "primary_contact": 1,
            }
        )
        missing_after = self.guardian_service.minor_members_without_guardians()

        self.assertIn(minor_id, {member["id"] for member in missing_before})
        self.assertNotIn(adult_id, {member["id"] for member in missing_before})
        self.assertNotIn(inactive_minor_id, {member["id"] for member in missing_before})
        self.assertNotIn(minor_id, {member["id"] for member in missing_after})

    def test_training_session_records_attendance_and_exports_report(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola de Xadrez",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Iniciantes",
                "teacher": "Instrutora",
                "weekday": "Quarta",
                "time": "15:00",
                "active": 1,
            }
        )
        present_member_id = self.member_service.create_member(
            {
                "name": "Aluno Presente",
                "club_id": club_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        absent_member_id = self.member_service.create_member(
            {
                "name": "Aluno Ausente",
                "club_id": club_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        outside_member_id = self.member_service.create_member(
            {
                "name": "Aluno Outra Turma",
                "club_id": club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )

        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "title": "Aula de finais",
                "session_type": "aula",
                "session_date": "2026-05-20",
                "start_time": "15:00",
                "end_time": "16:30",
                "instructor": "Instrutora",
                "location": "Sala 1",
                "status": "planned",
            }
        )
        session_members = self.db.list_session_members_for_attendance(session_id)

        result = self.training_service.record_attendance(
            session_id,
            [
                {"member_id": present_member_id, "status": "present"},
                {"member_id": absent_member_id, "status": "absent", "notes": "Avisado"},
            ],
        )
        summary = self.training_service.member_attendance_summary(present_member_id)
        sessions = self.db.list_training_sessions()
        report_rows = self.training_service.attendance_report("2026-05-01", "2026-05-31")
        output_path = Path(self.temp_dir.name) / "presencas.csv"
        self.export_service.export_attendance_report(
            output_path,
            start_date="2026-05-01",
            end_date="2026-05-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertCountEqual(
            [member["id"] for member in session_members],
            [present_member_id, absent_member_id],
        )
        self.assertNotIn(outside_member_id, {member["id"] for member in session_members})
        self.assertEqual(result["saved"], 2)
        self.assertEqual(summary["present"], 1)
        self.assertEqual(summary["attendance_rate"], 100.0)
        self.assertEqual(sessions[0]["present_count"], 1)
        self.assertEqual(sessions[0]["absent_count"], 1)
        self.assertEqual(len(report_rows), 2)
        self.assertIn("Aula de finais", content)
        self.assertIn("Aluno Presente", content)
        self.assertIn("Aluno Ausente", content)

    def test_training_sessions_store_pedagogical_plan_fields(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Pedagogica",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Estrategia",
                "teacher": "Instrutora",
                "active": 1,
            }
        )
        level_id = self.learning_level_service.create_level(
            {
                "name": "Plano Tatico",
                "description": "Reconhece cravadas, garfos e ataques duplos.",
                "display_order": 42,
                "active": 1,
            }
        )

        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "learning_level_id": level_id,
                "title": "Taticas de ataque duplo",
                "session_type": "aula",
                "session_date": "2026-05-21",
                "start_time": "14:00",
                "end_time": "15:30",
                "instructor": "Instrutora",
                "location": "Sala 3",
                "objective": "Identificar garfos em posicoes simples.",
                "content": "Exercicios de ataque duplo com dama, cavalo e torre.",
                "homework": "Resolver 10 diagramas de garfo.",
                "status": "planned",
                "notes": "Usar tabuleiro mural.",
            }
        )

        session = self.db.get_training_session(session_id)
        sessions = self.db.list_training_sessions(class_id=class_id)

        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session["learning_level_id"], level_id)
        self.assertEqual(session["learning_level_name"], "Plano Tatico")
        self.assertEqual(session["objective"], "Identificar garfos em posicoes simples.")
        self.assertEqual(session["content"], "Exercicios de ataque duplo com dama, cavalo e torre.")
        self.assertEqual(session["homework"], "Resolver 10 diagramas de garfo.")
        self.assertEqual(sessions[0]["learning_level_name"], "Plano Tatico")

        self.training_service.save_session(
            {
                **session,
                "objective": "Aplicar garfos em partidas de treino.",
                "homework": "Anotar dois exemplos encontrados em casa.",
            },
            session_id=session_id,
        )
        updated = self.db.get_training_session(session_id)

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["objective"], "Aplicar garfos em partidas de treino.")
        self.assertEqual(updated["homework"], "Anotar dois exemplos encontrados em casa.")
        with self.assertRaisesRegex(AppError, "Nivel pedagogico"):
            self.training_service.save_session(
                {
                    "club_id": club_id,
                    "class_id": class_id,
                    "learning_level_id": 99999,
                    "title": "Aula invalida",
                    "session_type": "aula",
                    "status": "planned",
                }
            )

    def test_exercise_library_lists_attempts_and_training_session_link(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Taticas",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Taticas",
                "teacher": "Instrutor",
                "active": 1,
            }
        )
        level_id = self.learning_level_service.create_level(
            {
                "name": "Tatica Basica",
                "description": "Garfos, cravadas e mates simples.",
                "display_order": 50,
                "active": 1,
            }
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Tatico",
                "club_id": club_id,
                "class_id": class_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        exercise_id = self.exercise_service.save_exercise(
            {
                "club_id": club_id,
                "learning_level_id": level_id,
                "title": "Mate em 1 com dama",
                "theme": "Mate em 1",
                "difficulty": "easy",
                "fen": "6k1/5ppp/8/8/8/8/5PPP/5QK1 w - - 0 1",
                "solution": "Df7#",
                "objective": "Reconhecer mate direto.",
                "tags": "mate,dama",
            }
        )
        second_exercise_id = self.exercise_service.save_exercise(
            {
                "club_id": club_id,
                "learning_level_id": level_id,
                "title": "Garfo de cavalo",
                "theme": "Garfo",
                "difficulty": "basic",
            }
        )
        list_id = self.exercise_service.save_training_list(
            {
                "club_id": club_id,
                "class_id": class_id,
                "learning_level_id": level_id,
                "name": "Lista de mates e garfos",
                "target_date": "2026-05-22",
                "status": "ready",
                "description": "Treino tatico da turma.",
            }
        )
        self.exercise_service.set_training_list_exercises(list_id, [exercise_id, second_exercise_id])
        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "learning_level_id": level_id,
                "training_list_id": list_id,
                "title": "Treino tatico guiado",
                "session_type": "treino",
                "session_date": "2026-05-22",
                "status": "planned",
            }
        )
        attempt_id = self.exercise_service.record_attempt(
            {
                "exercise_id": exercise_id,
                "member_id": member_id,
                "list_id": list_id,
                "session_id": session_id,
                "attempt_date": "2026-05-22",
                "result": "correct",
            }
        )

        exercise = self.db.get_exercise(exercise_id)
        training_list = self.db.get_training_list(list_id)
        list_items = self.db.list_training_list_exercises(list_id)
        session = self.db.get_training_session(session_id)
        attempts = self.db.list_exercise_attempts(member_id=member_id)

        self.assertIsNotNone(exercise)
        self.assertIsNotNone(training_list)
        self.assertIsNotNone(session)
        assert exercise is not None
        assert training_list is not None
        assert session is not None
        self.assertEqual(exercise["learning_level_name"], "Tatica Basica")
        self.assertEqual(training_list["exercise_count"], 2)
        self.assertEqual([item["exercise_id"] for item in list_items], [exercise_id, second_exercise_id])
        self.assertEqual(session["training_list_id"], list_id)
        self.assertEqual(session["training_list_name"], "Lista de mates e garfos")
        self.assertEqual(attempts[0]["id"], attempt_id)
        self.assertEqual(attempts[0]["score"], 1.0)
        self.assertEqual(attempts[0]["exercise_title"], "Mate em 1 com dama")

        self.exercise_service.remove_exercise_from_training_list(list_id, exercise_id)
        remaining = self.db.list_training_list_exercises(list_id)

        self.assertEqual([item["exercise_id"] for item in remaining], [second_exercise_id])
        with self.assertRaisesRegex(AppError, "Dificuldade"):
            self.exercise_service.save_exercise({"title": "Invalido", "difficulty": "impossivel"})

    def test_inventory_tracks_items_loans_and_maintenance(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Clube Material",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Emprestimo",
                "club_id": club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        item_id = self.inventory_service.save_item(
            {
                "club_id": club_id,
                "code": "REL-001",
                "name": "Relogio digital",
                "item_type": "clocks",
                "quantity_total": "2",
                "condition_status": "good",
                "storage_location": "Armario 1",
                "acquisition_date": "2026-05-01",
                "acquisition_value": "150,50",
            }
        )
        loan_id = self.inventory_service.save_loan(
            {
                "item_id": item_id,
                "member_id": member_id,
                "quantity": "1",
                "loan_date": "2026-05-10",
                "due_date": "2026-05-20",
                "status": "open",
                "notes": "Treino em casa",
            }
        )

        item = self.db.get_inventory_item(item_id)
        loans = self.db.list_inventory_loans(item_id=item_id)
        summary = self.inventory_service.inventory_summary()

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["borrowed_quantity"], 1)
        self.assertEqual(item["available_quantity"], 1)
        self.assertEqual(loans[0]["member_name"], "Aluno Emprestimo")
        self.assertEqual(summary["borrowed_quantity"], 1)
        self.assertEqual(summary["open_loans"], 1)

        with self.assertRaisesRegex(AppError, "Quantidade indisponivel"):
            self.inventory_service.save_loan(
                {
                    "item_id": item_id,
                    "member_id": member_id,
                    "quantity": "2",
                    "status": "open",
                }
            )
        with self.assertRaisesRegex(AppError, "emprestimos em aberto"):
            self.inventory_service.toggle_item_active(item_id)

        self.inventory_service.return_loan(loan_id, return_date="2026-05-18")
        returned = self.db.get_inventory_loan(loan_id)
        item_after_return = self.db.get_inventory_item(item_id)

        self.assertIsNotNone(returned)
        self.assertIsNotNone(item_after_return)
        assert returned is not None
        assert item_after_return is not None
        self.assertEqual(returned["status"], "returned")
        self.assertEqual(returned["return_date"], "2026-05-18")
        self.assertEqual(item_after_return["available_quantity"], 2)

        maintenance_id = self.inventory_service.save_maintenance(
            {
                "item_id": item_id,
                "opened_date": "2026-05-19",
                "description": "Trocar pilha",
                "cost": "12,75",
                "vendor": "Loja local",
                "status": "open",
            }
        )
        maintenance_open = self.db.get_inventory_maintenance(maintenance_id)
        self.inventory_service.close_maintenance(maintenance_id, resolved_date="2026-05-20")
        maintenance_closed = self.db.get_inventory_maintenance(maintenance_id)

        self.assertIsNotNone(maintenance_open)
        self.assertIsNotNone(maintenance_closed)
        assert maintenance_open is not None
        assert maintenance_closed is not None
        self.assertEqual(maintenance_open["cost"], 12.75)
        self.assertEqual(maintenance_closed["status"], "done")
        self.assertEqual(maintenance_closed["resolved_date"], "2026-05-20")

    def test_financial_plans_payments_status_and_export_report(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Financeiro",
                "member_type": "aluno",
                "status": "active",
            }
        )
        plan_id = self.finance_service.save_plan(
            {
                "name": "Mensalidade",
                "amount": "120,50",
                "billing_cycle": "monthly",
                "active": 1,
            }
        )

        overdue_payment_id = self.finance_service.save_payment(
            {
                "member_id": member_id,
                "plan_id": plan_id,
                "reference_period": "2000-01",
                "due_date": "2000-01-10",
                "status": "pending",
            }
        )
        paid_payment_id = self.finance_service.save_payment(
            {
                "member_id": member_id,
                "description": "Aula avulsa",
                "reference_period": "2999-01",
                "due_date": "2999-01-10",
                "payment_date": "2999-01-09",
                "amount": "50",
                "status": "paid",
                "method": "Pix",
            }
        )

        payments = self.finance_service.payments_report()
        status = self.finance_service.member_financial_status(member_id)
        summary = self.finance_service.finance_summary()
        output_path = Path(self.temp_dir.name) / "financeiro.csv"
        self.export_service.export_financial_report(output_path)
        content = output_path.read_text(encoding="utf-8-sig")

        overdue_payment = next(payment for payment in payments if payment["id"] == overdue_payment_id)
        paid_payment = next(payment for payment in payments if payment["id"] == paid_payment_id)
        self.assertEqual(overdue_payment["amount"], 120.5)
        self.assertEqual(overdue_payment["effective_status"], "late")
        self.assertEqual(paid_payment["effective_status"], "paid")
        self.assertEqual(status["status"], "late")
        self.assertEqual(status["open_amount"], 120.5)
        self.assertEqual(summary["late"], 1)
        self.assertEqual(summary["paid"], 1)
        self.assertEqual(summary["paid_amount"], 50.0)
        self.assertIn("Aluno Financeiro", content)
        self.assertIn("Mensalidade", content)
        self.assertIn("Atrasado", content)

    def test_finance_generates_recurring_payments_and_receipts(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Financeira",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        billable_member_id = self.member_service.create_member(
            {
                "name": "Aluno Mensalidade",
                "club_id": club_id,
                "member_type": "aluno",
                "status": "active",
            }
        )
        second_billable_member_id = self.member_service.create_member(
            {
                "name": "Socio Mensalidade",
                "club_id": club_id,
                "member_type": "socio",
                "status": "active",
            }
        )
        visitor_id = self.member_service.create_member(
            {
                "name": "Visitante Sem Cobranca",
                "club_id": club_id,
                "member_type": "visitante",
                "status": "active",
            }
        )
        plan_id = self.finance_service.save_plan(
            {
                "name": "Mensalidade recorrente",
                "amount": "95",
                "billing_cycle": "monthly",
                "active": 1,
            }
        )

        result = self.finance_service.generate_recurring_payments(
            plan_id,
            "2999-06",
            "2999-06-10",
            club_id=club_id,
        )
        duplicate_result = self.finance_service.generate_recurring_payments(
            plan_id,
            "2999-06",
            "2999-06-10",
            club_id=club_id,
        )
        payments = self.finance_service.payments_report(
            start_date="2999-06-01",
            end_date="2999-06-30",
        )
        generated_member_ids = {int(payment["member_id"]) for payment in payments}

        self.assertEqual(result["created"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(duplicate_result["created"], 0)
        self.assertEqual(duplicate_result["skipped"], 2)
        self.assertIn(billable_member_id, generated_member_ids)
        self.assertIn(second_billable_member_id, generated_member_ids)
        self.assertNotIn(visitor_id, generated_member_ids)
        for payment in payments:
            self.assertEqual(payment["description"], "Mensalidade recorrente - 2999-06")
            self.assertEqual(payment["reference_period"], "2999-06")
            self.assertEqual(payment["due_date"], "2999-06-10")
            self.assertEqual(payment["amount"], 95.0)

        first_payment_id = int(result["payment_ids"][0])
        receipt_path = Path(self.temp_dir.name) / "recibo.pdf"
        with self.assertRaisesRegex(AppError, "Recibo"):
            self.export_service.export_payment_receipt(first_payment_id, receipt_path)

        self.finance_service.mark_payment_paid(first_payment_id, payment_date="2999-06-09", method="Pix")
        exported_receipt = self.export_service.export_payment_receipt(first_payment_id, receipt_path)

        self.assertEqual(exported_receipt, receipt_path)
        self.assertTrue(receipt_path.exists())
        self.assertEqual(receipt_path.read_bytes()[:4], b"%PDF")

    def test_calendar_events_sync_tournament_and_export_report(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Clube Calendario",
                "kind": "club",
                "active": 1,
            },
            club_id=None,
        )
        tournament_id = self.db.create_tournament(
            "Aberto do Clube",
            club_id=club_id,
            location="Salao",
            start_date="2999-01-10",
            rounds_count=3,
        )

        tournament_event_id = self.event_service.sync_tournament_event(tournament_id)
        meeting_event_id = self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Reuniao de pais",
                "event_type": "meeting",
                "event_date": "2999-01-05",
                "start_time": "19:00",
                "location": "Sala 2",
                "status": "confirmed",
            }
        )
        canceled_event_id = self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Evento cancelado",
                "event_type": "social",
                "event_date": "2999-01-03",
                "status": "canceled",
            }
        )

        tournament_event = self.db.get_club_event(tournament_event_id)
        events = self.event_service.events_report("2999-01-01", "2999-01-31")
        upcoming = self.event_service.upcoming_events(limit=10)
        output_path = Path(self.temp_dir.name) / "eventos.csv"
        self.export_service.export_events_report(
            output_path,
            start_date="2999-01-01",
            end_date="2999-01-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(tournament_event["title"], "Aberto do Clube")
        self.assertEqual(tournament_event["event_type"], "tournament")
        self.assertEqual(tournament_event["tournament_id"], tournament_id)
        self.assertCountEqual([event["id"] for event in events], [tournament_event_id, meeting_event_id, canceled_event_id])
        self.assertNotIn("Evento cancelado", [event["title"] for event in upcoming])
        self.assertIn("Aberto do Clube", content)
        self.assertIn("Reuniao de pais", content)
        self.assertIn("Torneio", content)

    def test_dashboard_overview_and_administrative_package(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Painel",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        self.finance_service.save_payment(
            {
                "member_id": member_id,
                "description": "Mensalidade painel",
                "due_date": "2999-02-10",
                "amount": "100",
                "status": "pending",
            }
        )
        self.event_service.save_event(
            {
                "title": "Encontro do clube",
                "event_type": "social",
                "event_date": "2999-02-05",
                "status": "confirmed",
            }
        )
        self.db.create_tournament("Torneio painel", start_date="2999-02-20")
        output_path = Path(self.temp_dir.name) / "pacote.csv"

        overview = self.dashboard_service.overview()
        self.export_service.export_administrative_package(
            output_path,
            start_date="2999-02-01",
            end_date="2999-02-28",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(overview["summary"]["active_members"], 1)
        self.assertEqual(overview["finance_summary"]["pending_amount"], 100.0)
        self.assertEqual(overview["upcoming_events"][0]["title"], "Encontro do clube")
        self.assertEqual(overview["recent_tournaments"][0]["name"], "Torneio painel")
        self.assertIn("Pacote administrativo", content)
        self.assertIn("Mensalidade painel", content)
        self.assertIn("Encontro do clube", content)
        self.assertIn("Ranking interno", content)

    def test_register_active_members_in_tournament_skips_existing_and_ineligible(self) -> None:
        active_id = self.member_service.create_member(
            {
                "name": "Ativo 1",
                "member_type": "socio",
                "status": "active",
            }
        )
        second_active_id = self.member_service.create_member(
            {
                "name": "Ativo 2",
                "member_type": "aluno",
                "status": "active",
            }
        )
        visitor_id = self.member_service.create_member(
            {
                "name": "Visitante",
                "member_type": "visitante",
                "status": "visitor",
            }
        )
        self.member_service.register_member_in_tournament(self.tournament_id, active_id)

        result = self.member_service.register_active_members_in_tournament(self.tournament_id)
        players = self.db.list_players(self.tournament_id, active_only=False)
        registered_member_ids = {player["member_id"] for player in players}

        self.assertEqual(result["registered"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertIn(active_id, registered_member_ids)
        self.assertIn(second_active_id, registered_member_ids)
        self.assertNotIn(visitor_id, registered_member_ids)

    def test_member_tournament_history_summarizes_results(self) -> None:
        member_id = self.member_service.create_member(
            {
                "name": "Ana Membro",
                "rating": "1800",
                "member_type": "aluno",
                "status": "active",
            }
        )
        member_player_id = self.member_service.register_member_in_tournament(
            self.tournament_id,
            member_id,
        )
        self.db.create_player(
            self.tournament_id,
            name="Oponente",
            rating=1500,
            club="Clube",
            category="Absoluto",
        )
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(round_data["id"])[0]
        result = "1-0" if pairing["white_player_id"] == member_player_id else "0-1"
        self.db.update_pairing_result(pairing["id"], result)
        self.service.close_round(self.tournament_id, round_data["id"])

        history = self.member_service.tournament_history(member_id)
        results = self.member_service.tournament_results(member_id, self.tournament_id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["name"], "Torneio teste")
        self.assertEqual(history[0]["points"], 1.0)
        self.assertEqual(history[0]["wins"], 1)
        self.assertEqual(history[0]["rounds_played"], 1)
        self.assertEqual(history[0]["last_result"], "Vitoria")
        self.assertEqual(results[0]["opponent"], "Oponente")
        self.assertEqual(results[0]["outcome"], "Vitoria")
        self.assertEqual(results[0]["points"], 1.0)
        self.assertNotEqual(self.service.standings(self.tournament_id)[0]["performance"], "")

    def test_internal_rating_update_creates_history_and_updates_member_rating(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)

        result = self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        member = self.db.get_member(member_id)
        history = self.internal_rating_service.member_rating_history(member_id)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["duplicates"], 0)
        self.assertEqual(result["external"], 1)
        self.assertGreater(member["rating"], 1600)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["old_rating"], 1600)
        self.assertEqual(history[0]["new_rating"], member["rating"])
        self.assertEqual(history[0]["games"], 1)
        self.assertEqual(history[0]["performance"], 2300)

    def test_internal_rating_update_is_idempotent(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)

        first = self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        rating_after_first = self.db.get_member(member_id)["rating"]
        second = self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        rating_after_second = self.db.get_member(member_id)["rating"]
        history = self.internal_rating_service.member_rating_history(member_id)

        self.assertEqual(first["updated"], 1)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(rating_after_second, rating_after_first)
        self.assertEqual(len(history), 1)

    def test_next_tournament_registration_uses_updated_internal_rating(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        updated_rating = self.db.get_member(member_id)["rating"]
        next_tournament_id = self.db.create_tournament("Torneio seguinte", rounds_count=3)

        next_player_id = self.member_service.register_member_in_tournament(
            next_tournament_id,
            member_id,
        )
        next_player = self.db.get_player(next_player_id)

        self.assertEqual(next_player["rating"], updated_rating)

    def test_internal_ranking_summarizes_rating_results_and_exports(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        self.member_service.update_member(
            member_id,
            {
                "name": "Aluno Rating",
                "rating": str(self.db.get_member(member_id)["rating"]),
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            },
        )
        self.member_service.create_member(
            {
                "name": "Aluno Sem Jogos",
                "rating": "1200",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )
        output_path = Path(self.temp_dir.name) / "ranking.csv"

        ranking = self.internal_rating_service.ranking(category="Sub-18")
        self.export_service.export_internal_ranking_report(output_path, category="Sub-18")
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(ranking[0]["member_id"], member_id)
        self.assertEqual(ranking[0]["games"], 1)
        self.assertEqual(ranking[0]["wins"], 1)
        self.assertEqual(ranking[0]["score_rate"], 100.0)
        self.assertGreater(ranking[0]["last_delta"], 0)
        self.assertIn("Ranking interno", content)
        self.assertIn("Aluno Rating", content)
        self.assertIn("Aproveitamento", content)

    def test_internal_ranking_filters_by_season_club_and_class(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Ranking",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Ranking",
                "teacher": "Professor",
                "active": 1,
            }
        )
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.db.update_tournament_details(
            self.tournament_id,
            name="Torneio temporada",
            club_id=club_id,
            class_id=class_id,
            location="Sala 1",
            rounds_count=5,
            start_date="2026-05-10",
        )
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        updated_rating = self.db.get_member(member_id)["rating"]
        self.member_service.update_member(
            member_id,
            {
                "name": "Aluno Temporada",
                "club_id": club_id,
                "class_id": class_id,
                "rating": str(updated_rating),
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            },
        )
        outside_member_id = self.member_service.create_member(
            {
                "name": "Aluno Fora",
                "rating": "1900",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )
        output_path = Path(self.temp_dir.name) / "ranking_temporada.csv"

        ranking = self.internal_rating_service.ranking(
            category="Sub-18",
            club_id=club_id,
            class_id=class_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        empty_season = self.internal_rating_service.ranking(
            category="Sub-18",
            club_id=club_id,
            class_id=class_id,
            start_date="2027-01-01",
            end_date="2027-12-31",
        )
        self.export_service.export_internal_ranking_report(
            output_path,
            category="Sub-18",
            club_id=club_id,
            class_id=class_id,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual([item["member_id"] for item in ranking], [member_id])
        self.assertNotIn(outside_member_id, {item["member_id"] for item in ranking})
        self.assertEqual(ranking[0]["games"], 1)
        self.assertGreater(ranking[0]["season_delta"], 0)
        self.assertGreater(ranking[0]["last_delta"], 0)
        self.assertEqual(empty_season[0]["games"], 0)
        self.assertEqual(empty_season[0]["last_delta"], 0)
        self.assertIn("Escola Ranking", content)
        self.assertIn("Turma Ranking", content)
        self.assertIn("Temporada inicial", content)
        self.assertIn("2026-01-01", content)

        with self.assertRaisesRegex(AppError, "temporada"):
            self.internal_rating_service.ranking(start_date="2026-13-01")

    def test_export_member_evolution_report_includes_rating_and_results(self) -> None:
        member_id, _member_player_id = self._create_member_win(rating=1600)
        self.internal_rating_service.apply_tournament_ratings(self.tournament_id)
        guardian_id = self.guardian_service.create_guardian(
            {"name": "Maria Responsavel", "phone": "1111"}
        )
        self.guardian_service.link_guardian_to_member(
            {
                "member_id": member_id,
                "guardian_id": guardian_id,
                "relationship": "Mae",
                "primary_contact": 1,
            }
        )
        output_path = Path(self.temp_dir.name) / "evolucao.csv"

        self.export_service.export_member_evolution(member_id, output_path)
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertIn("Aluno Rating", content)
        self.assertIn("Maria Responsavel", content)
        self.assertIn("Mae", content)
        self.assertIn("Evolucao por torneio", content)
        self.assertIn("Rating interno", content)
        self.assertIn("Resultados", content)
        self.assertIn("Torneio teste", content)
        self.assertIn("2300", content)
        self.assertIn("Vitoria", content)

    def test_export_club_report_includes_administrative_summary(self) -> None:
        self.db.save_club("Clube Teste", city="Teresina", email="contato@example.com")
        self.member_service.create_member(
            {
                "name": "Aluno Ativo",
                "rating": "1700",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )
        output_path = Path(self.temp_dir.name) / "clube.csv"

        self.export_service.export_club_report(output_path)
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertIn("Clube Teste", content)
        self.assertIn("Indicadores", content)
        self.assertIn("Membros ativos", content)
        self.assertIn("Ranking interno", content)
        self.assertIn("Aluno Ativo", content)

    def test_export_tournaments_period_report_filters_by_date(self) -> None:
        self.db.create_tournament("Torneio maio", start_date="2026-05-10")
        self.db.create_tournament("Torneio junho", start_date="2026-06-10")
        output_path = Path(self.temp_dir.name) / "torneios_periodo.csv"

        self.export_service.export_tournaments_period_report(
            output_path,
            start_date="2026-05-01",
            end_date="2026-05-31",
        )
        content = output_path.read_text(encoding="utf-8-sig")

        self.assertIn("Torneios por periodo", content)
        self.assertIn("Torneio maio", content)
        self.assertNotIn("Torneio junho", content)

    def test_app_settings_and_backup_restore_roundtrip(self) -> None:
        export_dir = Path(self.temp_dir.name) / "exports"
        self.db.save_app_settings(
            {
                "appearance_mode": "Dark",
                "default_export_dir": str(export_dir),
                "backup_dir": str(self.backup_dir),
            }
        )
        before_member_id = self.member_service.create_member(
            {
                "name": "Antes do backup",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        backup_path = self.db.backup("roundtrip")
        self.member_service.create_member(
            {
                "name": "Depois do backup",
                "rating": "1600",
                "member_type": "aluno",
                "status": "active",
            }
        )

        safety_backup = self.db.restore_backup(backup_path)
        settings = self.db.get_app_settings()
        members = self.db.list_members(active_only=False)
        member_names = {member["name"] for member in members}
        backups = self.db.list_backups()

        self.assertEqual(settings["appearance_mode"], "Dark")
        self.assertEqual(settings["default_export_dir"], str(export_dir))
        self.assertTrue(safety_backup.exists())
        self.assertTrue(any(backup["name"] == backup_path.name for backup in backups))
        self.assertIn("Antes do backup", member_names)
        self.assertNotIn("Depois do backup", member_names)
        self.assertIsNotNone(self.db.get_member(before_member_id))

    def test_app_settings_normalizes_legacy_default_paths(self) -> None:
        base_path = Path(self.temp_dir.name)
        legacy_export_dir = base_path / "repo" / "exports"
        legacy_backup_dir = base_path / "repo" / "backups"
        user_data_dir = base_path / "user-data"
        self.db.save_app_settings(
            {
                "default_export_dir": str(legacy_export_dir),
                "backup_dir": str(legacy_backup_dir),
            }
        )

        with (
            mock.patch.dict(os.environ, {APP_DATA_DIR_ENV_VAR: str(user_data_dir)}),
            mock.patch.object(database_module, "LEGACY_EXPORTS_DIR", legacy_export_dir),
            mock.patch.object(database_module, "LEGACY_BACKUP_DIR", legacy_backup_dir),
        ):
            settings = self.db.get_app_settings()

        self.assertEqual(settings["default_export_dir"], str(user_data_dir / "exports"))
        self.assertEqual(settings["backup_dir"], str(user_data_dir / "backups"))
        self.assertEqual(self.db.backup_dir, user_data_dir / "backups")

    def test_security_settings_audit_and_backup_retention(self) -> None:
        self.security_service.save_security_settings(
            {
                "backup_retention_count": "2",
            }
        )
        first = self.security_service.create_backup("seguranca_1")
        second = self.security_service.create_backup("seguranca_2")
        third = self.security_service.create_backup("seguranca_3")

        settings = self.db.get_app_settings()
        audit_rows = self.security_service.list_audit_logs(limit=20)
        backups = self.db.list_backups()
        backup_names = {backup["name"] for backup in backups}

        self.assertEqual(settings["backup_retention_count"], "2")
        self.assertTrue(first["path"].exists() or first["path"].name not in backup_names)
        self.assertTrue(second["path"].exists() or second["path"].name not in backup_names)
        self.assertTrue(third["path"].exists() or third["path"].name not in backup_names)
        self.assertLessEqual(len(backups), 2)
        self.assertTrue(any(row["action"] == "settings_saved" for row in audit_rows))
        self.assertTrue(any(row["action"] == "backup_created" for row in audit_rows))
        self.assertTrue(any(row["action"] == "backup_retention_applied" for row in audit_rows))

    def test_restore_corrupted_backup_keeps_current_database_usable(self) -> None:
        before_member_id = self.member_service.create_member(
            {
                "name": "Antes da falha",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        corrupted_backup = self.backup_dir / "corrompido.db"
        corrupted_backup.parent.mkdir(parents=True, exist_ok=True)
        corrupted_backup.write_text("nao e um sqlite valido", encoding="utf-8")

        with self.assertRaises(sqlite3.DatabaseError):
            self.db.restore_backup(corrupted_backup)
        after_member_id = self.member_service.create_member(
            {
                "name": "Depois da falha",
                "rating": "1510",
                "member_type": "aluno",
                "status": "active",
            }
        )
        member_names = {member["name"] for member in self.db.list_members(active_only=False)}

        self.assertIsNotNone(self.db.get_member(before_member_id))
        self.assertIsNotNone(self.db.get_member(after_member_id))
        self.assertIn("Antes da falha", member_names)
        self.assertIn("Depois da falha", member_names)

    def test_restore_legacy_backup_migrates_restored_database(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = self.backup_dir / "legacy_restore.db"
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

        safety_backup = self.db.restore_backup(legacy_path)
        with self.db.connect() as restored_connection:
            user_version = restored_connection.execute("PRAGMA user_version").fetchone()[0]
            issuance_table = restored_connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'certificate_issuances'
                """
            ).fetchone()
            template_count = restored_connection.execute(
                "SELECT COUNT(*) FROM certificate_templates"
            ).fetchone()[0]

        self.assertTrue(safety_backup.exists())
        self.assertEqual(Database.SCHEMA_VERSION, user_version)
        self.assertIsNotNone(issuance_table)
        self.assertGreaterEqual(template_count, 7)
        self.assertEqual([], self.db.list_certificate_issuances(limit=1))

    def test_withdrawn_player_keeps_history_but_is_not_paired_again(self) -> None:
        player_ids = self._create_players(4)
        first_round = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(first_round["id"])
        self.service.close_round(self.tournament_id, first_round["id"])

        self.db.set_player_status(player_ids[0], "withdrawn")
        second_round = self.service.generate_next_round(self.tournament_id)
        scheduled_player_ids = []
        for pairing in self.db.get_pairings_for_round(second_round["id"]):
            scheduled_player_ids.append(pairing["white_player_id"])
            if pairing["black_player_id"]:
                scheduled_player_ids.append(pairing["black_player_id"])
        withdrawn_standing = next(
            item for item in self.service.standings(self.tournament_id)
            if item["player_id"] == player_ids[0]
        )

        self.assertNotIn(player_ids[0], scheduled_player_ids)
        self.assertEqual(withdrawn_standing["player_status"], "withdrawn")
        self.assertGreaterEqual(withdrawn_standing["points"], 0.0)

    def test_late_entry_points_are_added_to_new_players(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "location": "",
                "rounds_count": "3",
                "time_control": "",
                "start_date": "",
                "end_date": "",
                "bye_points": "1",
            },
            {
                "initial_order": "rating",
                "tournament_type": "real",
                "late_entry_points": "0.5",
            },
            [],
        )
        self._create_players(2)
        first_round = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(first_round["id"])
        self.service.close_round(self.tournament_id, first_round["id"])

        late_player_id = self.db.create_player(
            self.tournament_id,
            name="Entrada Tardia",
            rating=1200,
        )
        standing = next(
            item for item in self.service.standings(self.tournament_id)
            if item["player_id"] == late_player_id
        )

        self.assertEqual(self.db.get_player(late_player_id)["starting_points"], 0.5)
        self.assertEqual(standing["points"], 0.5)

    def test_disable_bye_requires_even_active_players(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "location": "",
                "rounds_count": "3",
                "time_control": "",
                "start_date": "",
                "end_date": "",
                "bye_points": "1",
            },
            {
                "initial_order": "rating",
                "tournament_type": "real",
                "disable_bye": 1,
            },
            [],
        )
        self._create_players(3)

        with self.assertRaises(AppError):
            self.service.generate_next_round(self.tournament_id)

    def test_closed_result_edit_requires_dangerous_changes_flag(self) -> None:
        self._create_players(2)
        first_round = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(first_round["id"])[0]
        self.db.update_pairing_result(pairing["id"], "1-0")
        self.service.close_round(self.tournament_id, first_round["id"])

        with self.assertRaises(AppError):
            self.service.update_result(self.tournament_id, pairing["id"], "0-1")

        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "location": "",
                "rounds_count": "5",
                "time_control": "",
                "start_date": "",
                "end_date": "",
                "bye_points": "1",
            },
            {
                "initial_order": "rating",
                "tournament_type": "real",
                "allow_dangerous_changes": 1,
            },
            [],
        )
        self.service.update_result(self.tournament_id, pairing["id"], "0-1")

        self.assertEqual(self.db.get_pairing(pairing["id"])["result"], "0-1")

    def test_tournament_settings_and_schedule_are_saved(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Aberto Escolar",
                "location": "Clube Central",
                "start_date": "2026-06-01",
                "end_date": "2026-06-03",
                "rounds_count": "3",
                "time_control": "Rapido 15+10",
                "bye_points": "1",
            },
            {
                "fide_event_id": "123456",
                "organizer": "Clube Central",
                "website": "https://example.com",
                "contact_email": "contato@example.com",
                "director": "Diretor",
                "chief_arbiter": "Arbitro",
                "arbiters": "Auxiliar",
                "federation": "BRA",
                "state": "PI",
                "categories": "S10,S12,ABS",
                "cutoff_date": "2026-01-01",
                "comments": "Premiacao escolar",
                "prizes": "Medalhas",
                "initial_order": "international_then_national",
                "tournament_type": "real",
                "tournament_profile": "club",
                "allow_public_registration": 1,
                "calculate_performance": 1,
                "late_entry_points": "0.5",
            },
            [
                {"round_number": 1, "date": "2026-06-01", "time": "09:00"},
                {"round_number": 2, "date": "2026-06-01", "time": "14:00"},
                {"round_number": 3, "date": "2026-06-02", "time": "09:00"},
            ],
        )

        tournament = self.db.get_tournament(self.tournament_id)
        settings = self.db.get_tournament_settings(self.tournament_id)
        schedule = self.db.list_round_schedule(self.tournament_id)

        self.assertEqual(tournament["name"], "Aberto Escolar")
        self.assertEqual(tournament["rounds_count"], 3)
        self.assertEqual(settings["fide_event_id"], "123456")
        self.assertEqual(settings["initial_order"], "international_then_national")
        self.assertEqual(settings["tournament_profile"], "club")
        self.assertEqual(settings["allow_public_registration"], 1)
        self.assertEqual(settings["calculate_performance"], 1)
        self.assertEqual(settings["late_entry_points"], 0.5)
        self.assertEqual(len(schedule), 3)
        self.assertEqual(schedule[1]["date"], "2026-06-01")
        self.assertEqual(schedule[1]["time"], "14:00")

    def test_tournament_profile_defaults_to_free_and_rejects_invalid(self) -> None:
        settings = self.db.get_tournament_settings(self.tournament_id)

        self.assertEqual(settings["tournament_profile"], "free")

        with self.assertRaisesRegex(AppError, "Perfil do torneio"):
            self.tournament_service.save_profile(
                self.tournament_id,
                {
                    "name": "Perfil invalido",
                    "location": "",
                    "rounds_count": "3",
                    "time_control": "",
                    "start_date": "",
                    "end_date": "",
                    "bye_points": "1",
                },
                {"tournament_profile": "oficial-obrigatorio"},
                [],
            )

    def test_tournament_schedule_generator_can_fill_all_rounds_same_day(self) -> None:
        generated = TournamentService.generate_round_schedule(
            rounds_count=5,
            start_date="2026-06-01",
            first_time="08:00",
            round_duration_minutes="45",
            break_minutes="15",
            rounds_per_day=5,
        )

        self.assertEqual([item["date"] for item in generated], ["2026-06-01"] * 5)
        self.assertEqual([item["time"] for item in generated], ["08:00", "09:00", "10:00", "11:00", "12:00"])

    def test_tournament_schedule_generator_splits_rounds_by_day(self) -> None:
        generated = TournamentService.generate_round_schedule(
            rounds_count=5,
            start_date="2026-06-01",
            first_time="08:30",
            round_duration_minutes=30,
            break_minutes=10,
            rounds_per_day=2,
        )

        self.assertEqual(
            [item["date"] for item in generated],
            ["2026-06-01", "2026-06-01", "2026-06-02", "2026-06-02", "2026-06-03"],
        )
        self.assertEqual([item["time"] for item in generated], ["08:30", "09:10", "08:30", "09:10", "08:30"])

    def test_tournament_profile_saves_standalone_and_class_scope(self) -> None:
        school_id = self.club_service.save_profile(
            {
                "name": "Escola Delta",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": school_id,
                "name": "Turma Delta",
                "active": 1,
            }
        )

        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio avulso",
                "location": "",
                "rounds_count": "3",
                "time_control": "",
                "start_date": "",
                "end_date": "",
                "bye_points": "1",
                "scope": "standalone",
                "club_id": None,
                "class_id": None,
            },
            {
                "initial_order": "rating",
                "tournament_type": "real",
            },
            [],
        )
        standalone_tournament = self.db.get_tournament(self.tournament_id)

        self.assertIsNone(standalone_tournament["club_id"])
        self.assertIsNone(standalone_tournament["class_id"])

        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio da turma",
                "location": "",
                "rounds_count": "3",
                "time_control": "",
                "start_date": "",
                "end_date": "",
                "bye_points": "1",
                "scope": "class",
                "club_id": school_id,
                "class_id": class_id,
            },
            {
                "initial_order": "rating",
                "tournament_type": "real",
            },
            [],
        )
        class_tournament = self.db.get_tournament(self.tournament_id)

        self.assertEqual(class_tournament["club_id"], school_id)
        self.assertEqual(class_tournament["class_id"], class_id)
        self.assertEqual(class_tournament["class_name"], "Turma Delta")

    def test_player_official_fields_and_csv_import(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Francisco Ximenes",
            surname="Ximenes",
            given_name="Francisco",
            title="NM",
            sex="M",
            club="Clube",
            fide_id="1896",
            cbx_id="1928",
            rating=1928,
            national_rating=1928,
            international_rating=1896,
            category="ABS",
            birth_date="2003-01-01",
        )

        self.db.update_player(
            player_id,
            name="Francisco E Ximenes",
            club="Clube",
            rating=1950,
            category="ABS",
            active=1,
            fide_id="1896",
            cbx_id="1928",
            surname="Ximenes",
            given_name="Francisco E",
            title="NM",
            sex="M",
            birth_date="2003-01-01",
            national_rating=1950,
            international_rating=1900,
        )

        player = self.db.get_player(player_id)
        self.assertEqual(player["cbx_id"], "1928")
        self.assertEqual(player["national_rating"], 1950)
        self.assertEqual(player["international_rating"], 1900)

        csv_path = Path(self.temp_dir.name) / "players.csv"
        csv_path.write_text(
            "nome,sobrenome,titulo,fide,cbx,rating_nacional,rating_internacional,categoria\n"
            "Ana Silva,Silva,WFM,222,333,1800,1750,Sub-18\n",
            encoding="utf-8",
        )
        result = self.import_service.import_players_csv(self.tournament_id, csv_path)
        imported = next(
            player
            for player in self.db.list_players(self.tournament_id)
            if player["name"] == "Ana Silva"
        )

        self.assertEqual(result["imported"], 1)
        self.assertEqual(imported["title"], "WFM")
        self.assertEqual(imported["fide_id"], "222")
        self.assertEqual(imported["cbx_id"], "333")
        self.assertEqual(imported["rating"], 1800)

        semicolon_csv_path = Path(self.temp_dir.name) / "players_semicolon.csv"
        semicolon_csv_path.write_text(
            "nome;clube;elo;categoria;id_fide;id_cbx\n"
            "Bruna Costa;Clube B;1675;ABS;444;555\n",
            encoding="utf-8",
        )
        semicolon_result = self.import_service.import_players_csv(self.tournament_id, semicolon_csv_path)
        semicolon_imported = next(
            player
            for player in self.db.list_players(self.tournament_id)
            if player["name"] == "Bruna Costa"
        )

        self.assertEqual(semicolon_result["imported"], 1)
        self.assertEqual(semicolon_imported["rating"], 1675)
        self.assertEqual(semicolon_imported["fide_id"], "444")
        self.assertEqual(semicolon_imported["cbx_id"], "555")

    def test_online_registration_import_previews_duplicates_and_imports_ready_rows(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "scope": "standalone",
                "location": "Sao Paulo",
                "rounds_count": "5",
                "time_control": "",
                "start_date": "2024-05-01",
                "end_date": "",
                "bye_points": "1",
            },
            {
                "initial_order": "rating",
                "tournament_type": "real",
            },
            [],
        )
        self.db.create_player(
            self.tournament_id,
            name="Duplicado Existente",
            fide_id="999",
            rating=1700,
        )
        csv_path = Path(self.temp_dir.name) / "inscricoes.csv"
        csv_path.write_text(
            "Carimbo de data/hora;Nome completo;Data de nascimento;Sexo;Clube / Cidade;"
            "Rating nacional;Rating internacional;FIDE ID;CBX ID;Categoria\n"
            "2026-05-14 10:00;Ana Silva;2008-01-01;Feminino;Sao Paulo;1390;;111;222;\n"
            "2026-05-14 10:01;Duplicado Existente;1990-01-01;M;Rio;1700;;999;;ABS\n"
            "2026-05-14 10:02;Ana Silva;2008-01-01;Feminino;Sao Paulo;1390;;111;222;\n"
            "2026-05-14 10:03;;2009-01-01;M;Sao Paulo;1200;;;;\n",
            encoding="utf-8",
        )

        preview = self.import_service.preview_online_registrations_csv(self.tournament_id, csv_path)
        result = self.import_service.import_online_registrations_csv(self.tournament_id, csv_path)
        imported = next(
            player
            for player in self.db.list_players(self.tournament_id, active_only=False)
            if player["name"] == "Ana Silva"
        )

        self.assertEqual(preview["total"], 4)
        self.assertEqual(preview["ready"], 1)
        self.assertEqual(preview["duplicate"], 2)
        self.assertEqual(preview["error"], 1)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skipped"], 3)
        self.assertEqual(imported["category"], "Sub-16")
        self.assertEqual(imported["age_category"], "Sub-16")
        self.assertEqual(imported["rating_category"], "Sub-1400")
        self.assertEqual(imported["prize_tags"], "Feminino; Melhor Local")

    def test_official_rating_import_updates_tournament_players(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Ana Silva",
            rating=1500,
            fide_id="222",
            cbx_id="333",
            club="Clube antigo",
        )
        fide_csv = Path(self.temp_dir.name) / "fide.csv"
        fide_csv.write_text(
            "name,fide,title,fide_rating,federation,birth_date\n"
            "Ana Silva,222,WFM,1810,BRA,2008-01-01\n",
            encoding="utf-8",
        )
        cbx_csv = Path(self.temp_dir.name) / "cbx.csv"
        cbx_csv.write_text(
            "nome,cbx,rating_nacional,clube\n"
            "Ana Silva,333,1850,Clube novo\n",
            encoding="utf-8",
        )

        fide_result = self.official_rating_service.import_official_csv(fide_csv, "FIDE", "2026-05")
        cbx_result = self.official_rating_service.import_official_csv(cbx_csv, "CBX", "2026-05")
        update_result = self.official_rating_service.update_tournament_players(self.tournament_id)
        player = self.db.get_player(player_id)

        self.assertEqual(fide_result["imported"], 1)
        self.assertEqual(cbx_result["imported"], 1)
        self.assertEqual(update_result["updated"], 1)
        self.assertEqual(player["title"], "WFM")
        self.assertEqual(player["international_rating"], 1810)
        self.assertEqual(player["national_rating"], 1850)
        self.assertEqual(player["rating"], 1850)
        self.assertEqual(player["club"], "Clube novo")

    def test_official_rating_import_accepts_semicolon_csv_and_normalized_headers(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Carla Lima",
            rating=1300,
            fide_id="777",
        )
        official_csv = Path(self.temp_dir.name) / "fide_semicolon.csv"
        official_csv.write_text(
            "Nome;FIDE ID;Titulo;Rating internacional;Federacao;Data nascimento\n"
            "Carla Lima;777;WCM;1888;BRA;2009-02-03\n",
            encoding="utf-8",
        )

        result = self.official_rating_service.import_official_csv(official_csv, "FIDE", "2026-05")
        update_result = self.official_rating_service.update_tournament_players(self.tournament_id)
        player = self.db.get_player(player_id)

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["errors"], [])
        self.assertIsNotNone(result["snapshot_id"])
        self.assertEqual(update_result["updated"], 1)
        self.assertEqual(player["title"], "WCM")
        self.assertEqual(player["international_rating"], 1888)
        self.assertEqual(player["rating"], 1888)

    def test_official_rating_import_without_header_does_not_create_snapshot(self) -> None:
        bad_csv = Path(self.temp_dir.name) / "official_empty.csv"
        bad_csv.write_text("", encoding="utf-8")

        with self.assertRaises(AppError):
            self.official_rating_service.import_official_csv(bad_csv, "FIDE")
        with self.db.connect() as connection:
            snapshots_count = connection.execute(
                "SELECT COUNT(*) FROM official_rating_snapshots"
            ).fetchone()[0]

        self.assertEqual(snapshots_count, 0)

    def test_official_rating_import_rolls_back_snapshot_when_player_insert_fails(self) -> None:
        official_csv = Path(self.temp_dir.name) / "official_rollback.csv"
        official_csv.write_text(
            "name,fide,rating\n"
            "Ana Silva,222,1810\n"
            "Bruno Souza,333,1720\n",
            encoding="utf-8",
        )
        original_insert = self.db._insert_official_player
        call_count = 0

        def flaky_insert(*args: object, **kwargs: object) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise sqlite3.OperationalError("falha simulada")
            return original_insert(*args, **kwargs)

        with mock.patch.object(self.db, "_insert_official_player", side_effect=flaky_insert):
            with self.assertRaises(sqlite3.OperationalError):
                self.official_rating_service.import_official_csv(official_csv, "FIDE")
        with self.db.connect() as connection:
            snapshots_count = connection.execute(
                "SELECT COUNT(*) FROM official_rating_snapshots"
            ).fetchone()[0]
            players_count = connection.execute("SELECT COUNT(*) FROM official_players").fetchone()[0]

        self.assertEqual(snapshots_count, 0)
        self.assertEqual(players_count, 0)

    def test_official_rating_update_respects_initial_order(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "location": "",
                "rounds_count": "5",
                "time_control": "",
                "start_date": "",
                "end_date": "",
                "bye_points": "1",
            },
            {
                "initial_order": "international_then_national",
                "tournament_type": "real",
            },
            [],
        )
        player_id = self.db.create_player(
            self.tournament_id,
            name="Bruno Souza",
            rating=1200,
            fide_id="444",
            cbx_id="555",
        )
        official_csv = Path(self.temp_dir.name) / "official.csv"
        official_csv.write_text(
            "name,fide,cbx,rating_nacional,rating_internacional\n"
            "Bruno Souza,444,555,1900,1750\n",
            encoding="utf-8",
        )

        self.official_rating_service.import_official_csv(official_csv, "FIDE")
        self.official_rating_service.update_tournament_players(self.tournament_id)
        player = self.db.get_player(player_id)

        self.assertEqual(player["rating"], 1750)

    def test_export_site_creates_static_html_package(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Jogador A",
            rating=1800,
            club="Clube",
            category="ABS",
        )
        self.db.create_player(
            self.tournament_id,
            name="Jogador B",
            rating=1700,
            club="Clube",
            category="ABS",
        )
        round_data = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(round_data["id"])[0]
        self.db.update_pairing_result(pairing["id"], "1-0")
        self.service.close_round(self.tournament_id, round_data["id"])

        output_dir = Path(self.temp_dir.name) / "site"
        index_path = self.export_service.export_site(self.tournament_id, output_dir)
        html = index_path.read_text(encoding="utf-8")

        self.assertTrue(index_path.exists())
        self.assertTrue((output_dir / "styles.css").exists())
        self.assertIn("Torneio teste", html)
        self.assertIn("Classificacao", html)
        self.assertIn("Rodada 1", html)

    def test_export_club_portal_creates_static_html_package(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Portal",
                "kind": "school",
                "city": "Curitiba",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Portal",
                "teacher": "Professora Portal",
                "weekday": "Sabado",
                "time": "09:00",
                "location": "Sala 1",
                "active": 1,
            }
        )
        self.member_service.create_member(
            {
                "name": "Aluno Portal",
                "club_id": club_id,
                "class_id": class_id,
                "rating": "1500",
                "category": "Sub-12",
                "member_type": "aluno",
                "status": "active",
            }
        )
        self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "title": "Aula de estrategia",
                "session_type": "aula",
                "session_date": "2999-08-05",
                "start_time": "09:00",
                "instructor": "Professora Portal",
                "location": "Sala 1",
                "objective": "Plano de meio-jogo",
                "homework": "Resolver dois diagramas.",
                "status": "planned",
            }
        )
        self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Festival Portal",
                "event_type": "social",
                "event_date": "2999-08-10",
                "start_time": "10:00",
                "location": "Salao",
                "status": "confirmed",
                "notes": "Comunicado aos responsaveis.",
            }
        )
        self.db.create_tournament(
            "Torneio Portal",
            club_id=club_id,
            class_id=class_id,
            start_date="2999-08-20",
            location="Salao",
        )

        output_dir = Path(self.temp_dir.name) / "portal"
        index_path = self.export_service.export_club_portal(output_dir, club_id=club_id, class_id=class_id)
        html = index_path.read_text(encoding="utf-8")

        self.assertTrue(index_path.exists())
        self.assertTrue((output_dir / "styles.css").exists())
        self.assertIn("Turma Portal", html)
        self.assertIn("Comunicados", html)
        self.assertIn("Festival Portal", html)
        self.assertIn("Aula de estrategia", html)
        self.assertIn("Resolver dois diagramas.", html)
        self.assertIn("Aluno Portal", html)
        self.assertIn("Ranking interno", html)
        self.assertIn("Torneio Portal", html)

    def test_certificate_service_exports_tournament_pdf(self) -> None:
        player_a = self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno",
            surname="Souza",
            rating=1800,
            club="Clube A",
            category="Sub-18",
        )
        player_c = self.db.create_player(
            self.tournament_id,
            name="Carla",
            surname="Lima",
            rating=1700,
            club="Clube B",
            category="Absoluto",
        )
        self.db.create_player(
            self.tournament_id,
            name="Diego",
            surname="Rocha",
            rating=1600,
            club="Clube B",
            category="Absoluto",
        )

        category_recipients = self.certificate_service.tournament_recipients(
            self.tournament_id,
            certificate_type="category_award",
            top_n=1,
        )
        selected_path = Path(self.temp_dir.name) / "diplomas.pdf"
        result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            selected_path,
            certificate_type="participation",
            player_ids=[player_a, player_c],
        )

        self.assertEqual(result["exported"], 2)
        self.assertEqual(len(result["verification_codes"]), 2)
        issuance = self.certificate_service.verify_issuance(result["verification_codes"][0])
        self.assertEqual(issuance["context_type"], "tournament")
        self.assertEqual(issuance["source_title"], "Torneio teste")
        self.assertTrue(selected_path.exists())
        self.assertEqual(selected_path.read_bytes()[:4], b"%PDF")
        self.assertEqual({item["category"] for item in category_recipients}, {"Sub-18", "Absoluto"})
        self.assertEqual(len(category_recipients), 2)

    def test_certificate_export_without_issuance_record_does_not_leave_pdf(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno",
            surname="Souza",
            rating=1800,
            club="Clube A",
            category="Sub-18",
        )
        output_path = Path(self.temp_dir.name) / "falha_registro.pdf"

        with mock.patch.object(
            self.db,
            "create_certificate_issuances",
            side_effect=sqlite3.OperationalError("registro falhou"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.certificate_service.export_tournament_certificates(
                    self.tournament_id,
                    output_path,
                    certificate_type="participation",
                )

        self.assertFalse(output_path.exists())
        self.assertEqual([], list(output_path.parent.glob("*.tmp.pdf")))

    def test_certificate_export_replace_failure_removes_issuance_records_and_temp_pdf(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        output_path = Path(self.temp_dir.name) / "falha_substituir.pdf"

        with mock.patch.object(Path, "replace", side_effect=OSError("replace falhou")):
            with self.assertRaises(OSError):
                self.certificate_service.export_tournament_certificates(
                    self.tournament_id,
                    output_path,
                    certificate_type="participation",
                )
        with self.db.connect() as connection:
            issuance_count = connection.execute("SELECT COUNT(*) FROM certificate_issuances").fetchone()[0]

        self.assertEqual(issuance_count, 0)
        self.assertFalse(output_path.exists())
        self.assertEqual([], list(output_path.parent.glob("*.tmp.pdf")))

    def test_certificate_templates_can_be_saved_previewed_and_used(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno",
            surname="Souza",
            rating=1800,
            club="Clube A",
            category="Sub-18",
        )
        logo_path = Path(self.temp_dir.name) / "logo.png"
        logo_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
            )
        )
        background_path = Path(self.temp_dir.name) / "fundo.png"
        background_path.write_bytes(logo_path.read_bytes())
        secondary_logo_path = Path(self.temp_dir.name) / "logo_secundario.png"
        secondary_logo_path.write_bytes(logo_path.read_bytes())
        template_id = self.certificate_service.create_template(
            {
                "name": "Modelo personalizado",
                "certificate_type": "overall_award",
                "title_template": "Diploma {torneio}",
                "body_template": "{nome} ficou em {posicao} com {pontos} ponto(s).",
                "footer_template": "{local} {periodo}",
                "orientation": "portrait",
                "signature_left": "Direcao",
                "signature_right": "Arbitro",
                "logo_path": str(logo_path),
                "background_image_path": str(background_path),
                "background_opacity": "35",
                "secondary_logo_path": str(secondary_logo_path),
                "primary_color": "#0F766E",
                "accent_color": "#F59E0B",
                "title_font_size": "30",
                "body_font_size": "16",
                "footer_font_size": "9",
            }
        )

        self.certificate_service.update_template(
            template_id,
            {
                "name": "Modelo personalizado",
                "certificate_type": "overall_award",
                "title_template": "Diploma especial {torneio}",
                "body_template": "{nome} ficou em {posicao} com {pontos} ponto(s).",
                "footer_template": "{local} {periodo}",
                "orientation": "portrait",
                "signature_left": "Direcao",
                "signature_right": "Arbitro",
                "logo_path": str(logo_path),
                "background_image_path": str(background_path),
                "background_opacity": "0.42",
                "secondary_logo_path": str(secondary_logo_path),
                "primary_color": "#0F766E",
                "accent_color": "#F59E0B",
                "title_font_size": "30",
                "body_font_size": "16",
                "footer_font_size": "9",
            },
        )
        preview = self.certificate_service.preview_template(
            self.tournament_id,
            template_id,
            top_n=1,
        )
        output_path = Path(self.temp_dir.name) / "modelo_personalizado.pdf"
        result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            output_path,
            template_id=template_id,
            top_n=1,
        )

        template = self.db.get_certificate_template(template_id)
        self.assertEqual(template["orientation"], "portrait")
        self.assertEqual(template["primary_color"], "#0F766E")
        self.assertEqual(template["accent_color"], "#F59E0B")
        self.assertEqual(template["background_image_path"], str(background_path))
        self.assertEqual(template["background_opacity"], 0.42)
        self.assertEqual(template["secondary_logo_path"], str(secondary_logo_path))
        self.assertEqual(template["title_font_size"], 30)
        self.assertEqual(result["exported"], 1)
        self.assertIn("Diploma especial Torneio teste", preview["title"])
        self.assertIn("Ana Silva", preview["body"])
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.read_bytes()[:4], b"%PDF")

    def test_default_certificate_background_assets_and_templates_export(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno",
            surname="Souza",
            rating=1800,
            club="Clube B",
            category="Absoluto",
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Fundo",
                "rating": "1700",
                "category": "Sub-18",
                "member_type": "aluno",
                "status": "active",
            }
        )

        for _label, relative_path, _opacity in database_module.CERTIFICATE_BACKGROUND_PRESETS:
            path = database_module.BASE_DIR / relative_path
            self.assertTrue(path.exists(), relative_path)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

        templates_by_name = {
            str(template["name"]): template
            for template in self.certificate_service.list_templates(active_only=True)
        }
        expected_templates = {
            "Xadrez classico - Participacao",
            "Xadrez escolar - Membro aluno",
            "Xadrez premium - Premiacao geral",
            "Tabuleiro sutil - Premiacao por categoria",
            "Pecas marca d'agua - Ranking interno",
        }
        self.assertTrue(expected_templates.issubset(templates_by_name))

        participation_path = Path(self.temp_dir.name) / "participacao_fundo.pdf"
        overall_path = Path(self.temp_dir.name) / "premiacao_fundo.pdf"
        category_path = Path(self.temp_dir.name) / "categoria_fundo.pdf"
        member_path = Path(self.temp_dir.name) / "membro_fundo.pdf"
        ranking_path = Path(self.temp_dir.name) / "ranking_fundo.pdf"

        participation_result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            participation_path,
            template_id=int(templates_by_name["Xadrez classico - Participacao"]["id"]),
        )
        overall_result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            overall_path,
            template_id=int(templates_by_name["Xadrez premium - Premiacao geral"]["id"]),
            top_n=1,
        )
        category_result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            category_path,
            template_id=int(templates_by_name["Tabuleiro sutil - Premiacao por categoria"]["id"]),
            top_n=1,
        )
        member_result = self.certificate_service.export_member_certificates(
            member_path,
            template_id=int(templates_by_name["Xadrez escolar - Membro aluno"]["id"]),
            member_ids=[member_id],
        )
        ranking_result = self.certificate_service.export_ranking_certificates(
            ranking_path,
            template_id=int(templates_by_name["Pecas marca d'agua - Ranking interno"]["id"]),
            top_n=1,
        )

        self.assertEqual(participation_result["exported"], 2)
        self.assertEqual(overall_result["exported"], 1)
        self.assertEqual(category_result["exported"], 2)
        self.assertEqual(member_result["exported"], 1)
        self.assertEqual(ranking_result["exported"], 1)
        for path in (participation_path, overall_path, category_path, member_path, ranking_path):
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes()[:4], b"%PDF")

    def test_default_certificate_logo_assets_export_as_primary_and_secondary(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        logo_dir = database_module.BASE_DIR / "assets" / "certificates" / "logos"
        primary_logo = logo_dir / "albericus_knight.png"
        secondary_logo = logo_dir / "clube_rook.png"
        expected_logos = {
            "albericus_knight.png",
            "clube_rook.png",
            "escola_pawn.png",
            "torneio_trophy.png",
            "selo_queen.png",
        }

        for filename in expected_logos:
            path = logo_dir / filename
            self.assertTrue(path.exists(), filename)
            content = path.read_bytes()
            self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(content[25], 6)

        template_id = self.certificate_service.create_template(
            {
                "name": "Modelo com logos padrao",
                "certificate_type": "participation",
                "title_template": "Certificado",
                "body_template": "Certificamos que {nome} participou do torneio {torneio}.",
                "footer_template": "{local} - {periodo}",
                "orientation": "landscape",
                "signature_left": "Direcao",
                "signature_right": "Arbitragem",
                "logo_path": str(primary_logo),
                "secondary_logo_path": str(secondary_logo),
                "primary_color": "#1E3A8A",
                "accent_color": "#C8A24A",
                "title_font_size": "30",
                "body_font_size": "16",
                "footer_font_size": "9",
            }
        )
        output_path = Path(self.temp_dir.name) / "logos_padrao.pdf"
        result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            output_path,
            template_id=template_id,
        )

        self.assertEqual(result["exported"], 1)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.read_bytes()[:4], b"%PDF")

    def test_certificate_service_exports_member_training_event_and_ranking_pdfs(self) -> None:
        club_id = self.club_service.save_profile(
            {
                "name": "Escola Diplomas",
                "kind": "school",
                "active": 1,
            },
            club_id=None,
        )
        class_id = self.club_service.save_class(
            {
                "club_id": club_id,
                "name": "Turma Diplomas",
                "teacher": "Professora",
                "active": 1,
            }
        )
        member_id = self.member_service.create_member(
            {
                "name": "Aluno Diploma",
                "club_id": club_id,
                "class_id": class_id,
                "category": "Sub-14",
                "rating": "1500",
                "member_type": "aluno",
                "status": "active",
            }
        )
        absent_member_id = self.member_service.create_member(
            {
                "name": "Aluno Ausente",
                "club_id": club_id,
                "class_id": class_id,
                "category": "Sub-14",
                "rating": "1200",
                "member_type": "aluno",
                "status": "active",
            }
        )
        ranking_member_id = self.member_service.create_member(
            {
                "name": "Aluno Ranking",
                "club_id": club_id,
                "category": "Sub-14",
                "rating": "2200",
                "member_type": "aluno",
                "status": "active",
            }
        )
        session_id = self.training_service.save_session(
            {
                "club_id": club_id,
                "class_id": class_id,
                "title": "Aula de calculo",
                "session_type": "aula",
                "session_date": "2026-05-20",
                "instructor": "Professora",
                "location": "Sala 2",
                "status": "done",
            }
        )
        self.training_service.record_attendance(
            session_id,
            [
                {"member_id": member_id, "status": "present"},
                {"member_id": absent_member_id, "status": "absent"},
            ],
        )
        event_id = self.event_service.save_event(
            {
                "club_id": club_id,
                "title": "Festival Escolar",
                "event_type": "social",
                "event_date": "2026-05-21",
                "location": "Auditorio",
                "status": "done",
            }
        )

        member_path = Path(self.temp_dir.name) / "membro.pdf"
        training_path = Path(self.temp_dir.name) / "aula.pdf"
        event_path = Path(self.temp_dir.name) / "evento.pdf"
        ranking_path = Path(self.temp_dir.name) / "ranking.pdf"
        member_result = self.certificate_service.export_member_certificates(
            member_path,
            member_ids=[member_id],
        )
        training_result = self.certificate_service.export_training_certificates(
            session_id,
            training_path,
            present_only=False,
            member_ids=[member_id, absent_member_id],
        )
        event_result = self.certificate_service.export_event_certificates(
            event_id,
            event_path,
            member_ids=[member_id],
        )
        ranking_result = self.certificate_service.export_ranking_certificates(
            ranking_path,
            category="Sub-14",
            top_n=1,
        )
        member_recipient = self.certificate_service.member_recipients(member_ids=[member_id])[0]
        training_recipients = self.certificate_service.training_recipients(
            session_id,
            present_only=False,
        )
        event_recipient = self.certificate_service.event_recipients(event_id, member_ids=[member_id])[0]
        ranking_recipient = self.certificate_service.ranking_recipients(category="Sub-14", top_n=1)[0]

        self.assertEqual(member_result["exported"], 1)
        self.assertEqual(training_result["exported"], 2)
        self.assertEqual(event_result["exported"], 1)
        self.assertEqual(ranking_result["exported"], 1)
        all_codes = (
            member_result["verification_codes"]
            + training_result["verification_codes"]
            + event_result["verification_codes"]
            + ranking_result["verification_codes"]
        )
        issued_records = self.certificate_service.list_issuances(limit=10)
        verified_member = self.certificate_service.verify_issuance(member_result["verification_codes"][0])
        self.assertEqual(len(all_codes), 5)
        self.assertEqual(len(set(all_codes)), 5)
        self.assertEqual(len(issued_records), 5)
        self.assertEqual(verified_member["context_type"], "members")
        self.assertEqual(verified_member["recipient_name"], "Aluno Diploma")
        self.assertEqual(member_recipient["class_name"], "Turma Diplomas")
        self.assertEqual({item["status"] for item in training_recipients}, {"Presente", "Falta"})
        self.assertEqual(event_recipient["event"], "Festival Escolar")
        self.assertEqual(ranking_recipient["member_id"], ranking_member_id)
        for path in (member_path, training_path, event_path, ranking_path):
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes()[:4], b"%PDF")

    def test_certificate_service_exports_local_verification_site(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana",
            surname="Silva",
            rating=1900,
            club="Clube A",
            category="Sub-18",
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno",
            surname="Souza",
            rating=1800,
            club="Clube B",
            category="Absoluto",
        )
        pdf_path = Path(self.temp_dir.name) / "diplomas.pdf"
        result = self.certificate_service.export_tournament_certificates(
            self.tournament_id,
            pdf_path,
        )
        revoked_issuance = self.certificate_service.verify_issuance(result["verification_codes"][0])
        self.certificate_service.revoke_issuance(int(revoked_issuance["id"]), notes="Reemitido")

        site_path = Path(self.temp_dir.name) / "verificador"
        exported_path = self.certificate_service.export_verification_site(site_path)
        html = exported_path.read_text(encoding="utf-8")

        self.assertEqual(exported_path, site_path.with_suffix(".html"))
        self.assertIn("Verificador de diplomas Albericus", html)
        self.assertIn(result["verification_codes"][0], html)
        self.assertIn(result["verification_codes"][1], html)
        self.assertIn("Ana Silva", html)
        self.assertIn("Bruno Souza", html)
        self.assertIn("Revogado", html)
        self.assertIn("Ativo", html)
        self.assertIn("Torneio teste", html)
        self.assertNotIn(str(pdf_path), html)

    def test_team_tournament_exports_reports_and_site(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))
        self.service.update_result(tournament_id, int(boards[0]["id"]), "1-0")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "0-1")
        self.service.close_round(tournament_id, round_data["id"])

        standings_path = Path(self.temp_dir.name) / "team_standings.csv"
        pairings_path = Path(self.temp_dir.name) / "team_pairings.csv"
        teams_path = Path(self.temp_dir.name) / "teams.csv"
        complete_path = Path(self.temp_dir.name) / "team_complete.csv"
        site_dir = Path(self.temp_dir.name) / "team_site"

        self.export_service.export_standings(tournament_id, standings_path)
        self.export_service.export_pairings(round_data["id"], pairings_path)
        self.export_service.export_teams(tournament_id, teams_path)
        self.export_service.export_complete(tournament_id, complete_path)
        index_path = self.export_service.export_site(tournament_id, site_dir)

        standings_csv = standings_path.read_text(encoding="utf-8-sig")
        pairings_csv = pairings_path.read_text(encoding="utf-8-sig")
        teams_csv = teams_path.read_text(encoding="utf-8-sig")
        complete_csv = complete_path.read_text(encoding="utf-8-sig")
        html = index_path.read_text(encoding="utf-8")

        self.assertIn("Match points", standings_csv)
        self.assertIn("Equipe 1", standings_csv)
        self.assertIn("Confronto", pairings_csv)
        self.assertIn("2 x 0", pairings_csv)
        self.assertIn("Escalacoes", teams_csv)
        self.assertIn("Titular", teams_csv)
        self.assertIn("Classificacao por equipes", complete_csv)
        self.assertIn("Rodada 1", complete_csv)
        self.assertIn("Classificacao por equipes", html)
        self.assertIn("Equipes", html)
        self.assertIn("Escalacoes", html)
        self.assertIn("2 x 0", html)

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
