from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.core.database import Database
from src.core.services import (
    AppError,
    TeamService,
)
from tests.support.core_service_base import CoreServiceTestCase


class TeamRosterPolicyValidatorTest(unittest.TestCase):
    """Spec §6.2 — validador de policy de escalação retorna warnings."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.db = Database(base_path / "albericus.db", backup_dir=base_path / "backups")
        self.team_service = TeamService(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validator_returns_empty_when_no_team_tournament(self) -> None:
        # Torneio individual recém-criado — sem lineups, sem warnings.
        tournament_id = self.db.create_tournament("Vazio")
        issues = self.team_service.validate_roster_policy(tournament_id)
        self.assertEqual([], issues)

    def test_validator_signature_accepts_round_filter(self) -> None:
        tournament_id = self.db.create_tournament("Filtrado")
        # Não deve levantar exceção mesmo sem dados.
        self.assertEqual(
            [],
            self.team_service.validate_roster_policy(tournament_id, round_id=999),
        )

    def test_migration_added_team_rating_tolerance_column(self) -> None:
        tournament_id = self.db.create_tournament("Tolerancia")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        # Coluna existe e default é 0.
        self.assertEqual(0, int(settings.get("team_rating_tolerance", -1) or 0))


class TeamTournamentsTest(CoreServiceTestCase):
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

    def test_team_tournament_format_change_is_blocked_when_teams_exist(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)

        with self.assertRaisesRegex(AppError, "equipes cadastradas"):
            self.tournament_service.save_profile(
                tournament_id,
                {
                    "name": "Interclubes convertido",
                    "competition_type": "individual",
                    "scope": "standalone",
                    "rounds_count": "5",
                    "bye_points": "1",
                },
                {},
                [],
            )

        self.assertEqual(self.db.get_tournament(tournament_id)["competition_type"], "team")

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

    def test_team_tournament_settings_save_rating_tolerance(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Equipes tolerancia",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

        self.tournament_service.save_profile(
            tournament_id,
            {
                "name": "Equipes tolerancia",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {
                "team_boards_count": "2",
                "team_rating_tolerance": "75",
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
        self.assertEqual(settings["team_rating_tolerance"], 75)

    def test_team_max_substitutions_rejects_invalid_value(self) -> None:
        tournament_id = self.tournament_service.create_tournament(
            {
                "name": "Equipes substituicoes",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )

        with self.assertRaisesRegex(AppError, "substituicoes"):
            self.tournament_service.save_profile(
                tournament_id,
                {
                    "name": "Equipes substituicoes",
                    "competition_type": "team",
                    "scope": "standalone",
                    "rounds_count": "3",
                    "bye_points": "1",
                },
                {
                    "team_max_substitutions": "abc",
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

    def test_team_board_manual_color_swap(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        board = self.db.list_team_boards(int(match["id"]))[0]

        self.service.swap_team_board_colors(tournament_id, round_data["id"], int(board["id"]))

        updated = self.db.list_team_boards(int(match["id"]))[0]
        self.assertEqual(updated["white_player_id"], board["black_player_id"])
        self.assertEqual(updated["black_player_id"], board["white_player_id"])

    def test_team_board_manual_player_swap_keeps_player_in_same_team(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))

        source_player_id = int(boards[0]["white_player_id"])
        replacement_player_id = int(boards[1]["black_player_id"])
        self.service.adjust_team_board_player(
            tournament_id,
            round_data["id"],
            int(boards[0]["id"]),
            "white",
            replacement_player_id,
        )

        updated = self.db.list_team_boards(int(match["id"]))
        self.assertEqual(updated[0]["white_player_id"], replacement_player_id)
        self.assertEqual(updated[1]["black_player_id"], source_player_id)

    def test_team_board_manual_player_swap_rejects_other_team_player(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))

        with self.assertRaisesRegex(AppError, "mesma equipe"):
            self.service.adjust_team_board_player(
                tournament_id,
                round_data["id"],
                int(boards[0]["id"]),
                "white",
                int(boards[0]["black_player_id"]),
            )

    def test_phase6_team_lineups_substitutions_and_export_are_recorded(self) -> None:
        tournament_id, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        reserve_id = self.db.create_player(tournament_id, name="Reserva Equipe 1", rating=1600, club="Clube 1")
        self.team_service.add_player(team_ids[0], reserve_id, board_number="", role="reserve")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        settings.update(
            {
                "team_max_substitutions": 2,
                "team_board_order_policy": "fixed",
                "team_reserve_policy": "same_team",
            }
        )
        self.db.save_tournament_settings(tournament_id, settings)

        round_data = self.service.generate_next_round(tournament_id)
        lineups = self.db.list_team_lineups(tournament_id, round_id=int(round_data["id"]))
        self.assertEqual(2, len(lineups))
        self.assertEqual(4, sum(len(self.db.list_team_lineup_boards(int(lineup["id"]))) for lineup in lineups))

        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        board = self.db.list_team_boards(int(match["id"]))[0]
        team_player_ids = {int(item["player_id"]) for item in self.db.list_team_players(team_ids[0], active_only=True)}
        color = "white" if int(board["white_player_id"]) in team_player_ids else "black"

        self.service.adjust_team_board_player(
            tournament_id,
            int(round_data["id"]),
            int(board["id"]),
            color,
            reserve_id,
            reason="Titular chegou atrasado",
        )

        substitutions = self.db.list_team_substitution_events(tournament_id, round_id=int(round_data["id"]))
        self.assertEqual(1, len(substitutions))
        self.assertEqual("Titular chegou atrasado", substitutions[0]["reason"])
        self.assertEqual(reserve_id, substitutions[0]["in_player_id"])
        lineup_player_ids = {
            int(board_row["player_id"])
            for lineup in self.db.list_team_lineups(tournament_id, round_id=int(round_data["id"]))
            for board_row in self.db.list_team_lineup_boards(int(lineup["id"]))
            if board_row.get("player_id")
        }
        self.assertIn(reserve_id, lineup_player_ids)

        export_path = Path(self.temp_dir.name) / "escalacoes.csv"
        self.export_service.export_team_lineups(tournament_id, export_path)
        content = export_path.read_text(encoding="utf-8-sig")
        self.assertIn("Escalações por equipes", content)
        self.assertIn("Substituições por equipes", content)
        self.assertIn("Reserva Equipe 1", content)

    def test_phase6_team_substitution_after_result_requires_formal_correction(self) -> None:
        tournament_id, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        reserve_id = self.db.create_player(tournament_id, name="Reserva Bloqueio", rating=1500)
        self.team_service.add_player(team_ids[0], reserve_id, board_number="", role="reserve")
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        board = self.db.list_team_boards(int(match["id"]))[0]
        self.service.update_result(tournament_id, int(board["id"]), "1-0")
        team_player_ids = {int(item["player_id"]) for item in self.db.list_team_players(team_ids[0], active_only=True)}
        color = "white" if int(board["white_player_id"]) in team_player_ids else "black"

        with self.assertRaisesRegex(AppError, "correcao formal"):
            self.service.adjust_team_board_player(
                tournament_id,
                int(round_data["id"]),
                int(board["id"]),
                color,
                reserve_id,
            )

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

    def test_export_chess_results_trf16_supports_team_tournaments(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))
        self.service.update_result(tournament_id, int(boards[0]["id"]), "1-0")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "1/2-1/2")
        self.service.close_round(tournament_id, round_data["id"])

        output_path = Path(self.temp_dir.name) / "team_chess_results.trf"
        warnings = self.export_service.export_chess_results_trf(tournament_id, output_path)
        content = output_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        player_lines = [line for line in lines if line.startswith("001 ")]
        team_lines = [line for line in lines if line.startswith("013 ")]

        self.assertIn("082 2", content)
        # 092 no vocabulario das federacoes (FED-03), e nao no texto proprietario.
        self.assertIn("092 Team: Swiss-System", content)
        self.assertEqual(len(player_lines), 4)
        self.assertEqual(len(team_lines), 2)
        self.assertTrue(any("Equipe 1" in line and "1" in line and "2" in line for line in team_lines))
        self.assertTrue(any("   3 w 1" in line for line in player_lines))
        self.assertTrue(any("   4 b =" in line for line in player_lines))
        self.assertTrue(any("Jogadores sem FIDE ID" in warning for warning in warnings))

    def test_trf25_export_emits_310_and_header_extensions_for_teams(self) -> None:
        from src.services.federation_exporters import (
            TRF25_SCAFFOLD_WARNING,
            TRF25Exporter,
        )

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        boards = self.db.list_team_boards(int(match["id"]))
        self.service.update_result(tournament_id, int(boards[0]["id"]), "1-0")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "1/2-1/2")
        self.service.close_round(tournament_id, round_data["id"])

        output_path = Path(self.temp_dir.name) / "team_trf25.trf"
        warnings = TRF25Exporter(self.export_service).export(tournament_id, output_path)
        content = output_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        player_lines = [line for line in lines if line.startswith("001 ")]
        team_310 = [line for line in lines if line.startswith("310 ")]
        team_802 = [line for line in lines if line.startswith("802 ")]

        # Cabeçalho TRF25: nº de rodadas (142), tipo codificado (192) e
        # sequência de cores dos tabuleiros (352) para torneio por equipes.
        self.assertTrue(any(line.startswith("142 ") for line in lines))
        self.assertIn("192 FIDE_TEAM_TYPEA_MP_GP", content)
        self.assertIn("352 WB", content)
        # Tie-breaks de classificação (212). Era a lista fixa `PTS,BH:MP,WIN`,
        # escrita quando o projeto não tinha sequência configurável; desde a
        # TBK-04 o registro sai da MESMA sequência que o motor executa, então
        # ele é literalmente o plano enviado ao `tiebreakchecker`. Três
        # diferenças, todas conserto:
        #  - `MPTS` no lugar de `PTS`: em equipes o primário é match points;
        #  - `GPTS` aparece — o motor sempre o usou, o 212 é que o omitia;
        #  - `WON` no lugar de `WIN`: vitórias no tabuleiro (ver TBK-03).
        # O `BH` herda os match points do primário (`parse_tiebreak` do Gacrux
        # usa `primaryscore`), então equivale ao antigo `BH:MP`.
        self.assertIn("212 MPTS,GPTS,BH,WON", content)
        # Pontuação padrão (TW=2/TD=1/TL=0) → 362 omitido.
        self.assertFalse(any(line.startswith("362 ") for line in lines))
        # Equipes saem como 310 (substitui o 013); o 013 não é mais emitido.
        self.assertEqual(len(team_310), 2)
        self.assertFalse(any(line.startswith("013 ") for line in lines))
        # Linhas 001 dos jogadores continuam idênticas ao TRF16.
        self.assertEqual(len(player_lines), 4)
        # Registro informativo 802: um por equipe, espelhando o TPN do 310.
        self.assertEqual(len(team_802), 2)
        # Warning de scaffold continua presente.
        self.assertIn(TRF25_SCAFFOLD_WARNING, warnings)

    def test_trf25_export_emits_320_pab_for_team_bye(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        # 3 equipes → uma recebe bye (pairing-allocated-bye) a cada rodada.
        tournament_id, _team_ids = self._create_team_tournament(teams_count=3, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        matches = self.db.list_team_matches_for_round(round_data["id"])
        played = [m for m in matches if not m.get("is_bye")]
        bye = [m for m in matches if m.get("is_bye")]
        self.assertEqual(len(bye), 1)
        for board in self.db.list_team_boards(int(played[0]["id"])):
            self.service.update_result(tournament_id, int(board["id"]), "1-0")
        self.service.close_round(tournament_id, round_data["id"])

        output_path = Path(self.temp_dir.name) / "team_trf25_bye.trf"
        TRF25Exporter(self.export_service).export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        pab_lines = [line for line in lines if line.startswith("320 ")]
        # Um único registro 320 por torneio, com MP/GP do bye e o TPN na rodada 1.
        self.assertEqual(len(pab_lines), 1)
        self.assertEqual(pab_lines[0][4:8], " 2.0")
        self.assertEqual(pab_lines[0][9:13], " 2.0")

    def test_trf25_emits_299_for_team_point_adjustment(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        # Penalidade de 2 match points e 1 game point a uma equipe.
        self.db.add_point_adjustment(
            tournament_id,
            round_number=0,
            team_id=team_ids[0],
            aat_type="",
            match_points=-2.0,
            game_points=-1.0,
            reason="Penalidade de equipe",
        )

        output_path = Path(self.temp_dir.name) / "team_299.trf"
        TRF25Exporter(self.export_service).export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        # Mapeia nome da equipe (cols 9-40) -> TPN (cols 5-7) a partir dos 310.
        target_name = next(
            t["name"] for t in self.db.list_teams(tournament_id, active_only=False)
            if int(t["id"]) == team_ids[0]
        )
        tpn_by_name = {
            line[8:40].strip(): line[4:7].strip()
            for line in lines
            if line.startswith("310 ")
        }
        expected_tpn = tpn_by_name[target_name]

        adj_lines = [line for line in lines if line.startswith("299 ")]
        self.assertEqual(len(adj_lines), 1)
        line = adj_lines[0]
        self.assertEqual(line[7:11], "-2.0")
        self.assertEqual(line[13:17], "-1.0")
        self.assertEqual(line[23:27].strip(), expected_tpn)

    def test_trf25_emits_300_only_for_out_of_order_team(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        team_a, team_b = team_ids[0], team_ids[1]

        def roster(team_id: int) -> list[int]:
            assignments = sorted(
                self.db.list_team_players(team_id, active_only=False),
                key=lambda a: int(a.get("board_number") or 0),
            )
            return [int(a["player_id"]) for a in assignments]

        a_board1, a_board2 = roster(team_a)
        b_board1, b_board2 = roster(team_b)

        # Cores: tab.1 (impar) branco=A/preto=B; tab.2 (par) branco=B/preto=A.
        # Equipe A escala invertida (tab.1 com o jogador do tab.2 e vice-versa);
        # equipe B mantém a ordem do roster.
        round_id = self.db.create_round_with_team_matches(
            tournament_id,
            1,
            [
                {
                    "match_number": 1,
                    "white_team_id": team_a,
                    "black_team_id": team_b,
                    "is_bye": 0,
                    "boards": [
                        {
                            "board_number": 1,
                            "white_player_id": a_board2,
                            "black_player_id": b_board1,
                            "result": "1-0",
                        },
                        {
                            "board_number": 2,
                            "white_player_id": b_board2,
                            "black_player_id": a_board1,
                            "result": "0-1",
                        },
                    ],
                }
            ],
        )
        self.db.close_round(round_id)

        output_path = Path(self.temp_dir.name) / "team_300.trf"
        TRF25Exporter(self.export_service).export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        name_by_id = {
            int(t["id"]): t["name"]
            for t in self.db.list_teams(tournament_id, active_only=False)
        }
        tpn_by_name = {
            line[8:40].strip(): line[4:7].strip()
            for line in lines
            if line.startswith("310 ")
        }
        a_tpn = tpn_by_name[name_by_id[team_a]]
        start_rank = {
            int(p["id"]): index
            for index, p in enumerate(
                sorted(
                    self.db.list_players(tournament_id, active_only=False),
                    key=lambda p: -self.export_service._trf_rating(p),
                ),
                start=1,
            )
        }

        order_lines = [line for line in lines if line.startswith("300 ")]
        self.assertEqual(len(order_lines), 1)
        line = order_lines[0]
        self.assertEqual(line[4:7].strip(), a_tpn)
        # Tab.1 jogado pelo jogador do tab.2 do roster; tab.2 pelo do tab.1.
        self.assertEqual(line[16:20].strip(), str(start_rank[a_board2]))
        self.assertEqual(line[21:25].strip(), str(start_rank[a_board1]))

    def test_prohibited_team_pairing_is_never_paired(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        teams = self.db.list_teams(tournament_id, active_only=True)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        boards_count = int(settings.get("team_boards_count") or 2)
        rosters, seed_ratings = self.service._team_starter_rosters(teams, boards_count)

        def match_set(matches: list[dict[str, Any]]) -> set[frozenset[int]]:
            return {
                frozenset((int(m["white_team_id"]), int(m["black_team_id"])))
                for m in matches
                if m.get("black_team_id") is not None and not m.get("is_bye")
            }

        # Rodada 2 sem resultados: grupo único, dobra por seed.
        plain = match_set(
            self.service._swiss_team_matches(
                tournament_id, teams, rosters, seed_ratings, boards_count, settings, 2
            )
        )
        self.assertEqual(len(plain), 2)
        sample = next(iter(plain))
        team_a, team_b = tuple(sample)

        # Proibindo o par, ele nunca pode ser pareado.
        self.db.add_prohibited_team_pairing(tournament_id, team_a, team_b)
        guarded = match_set(
            self.service._swiss_team_matches(
                tournament_id, teams, rosters, seed_ratings, boards_count, settings, 2
            )
        )
        self.assertIn(sample, plain)
        self.assertNotIn(sample, guarded)
        self.assertEqual(len(guarded), 2)  # 4 equipes → 2 confrontos íntegros

    def test_trf25_emits_260_for_prohibited_team_pairing(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, team_ids = self._create_team_tournament(teams_count=4, boards_count=2)
        # Proíbe a equipe seed 1 (TPN 1) x seed 3 (TPN 3), janela aberta.
        self.db.add_prohibited_team_pairing(tournament_id, team_ids[0], team_ids[2])
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_prohib.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        prohibition_lines = [line for line in lines if line.startswith("260 ")]
        self.assertEqual(len(prohibition_lines), 1)
        line = prohibition_lines[0]
        self.assertEqual(line[4:7].strip(), "1")  # primeira rodada
        self.assertEqual(line[8:11].strip(), "5")  # última rodada (rounds_count=5)
        self.assertEqual(line[12:16].strip(), "1")  # TPN da seed 1
        self.assertEqual(line[17:21].strip(), "3")  # TPN da seed 3

    def test_requested_team_bye_excludes_team_from_pairing(self) -> None:
        # 5 equipes, 1 bye solicitado → 4 a parear (par), sem bye alocado extra.
        tournament_id, team_ids = self._create_team_tournament(teams_count=5, boards_count=2)
        self.db.add_requested_team_bye(tournament_id, team_ids[4], 1, "H")

        round_data = self.service.generate_next_round(tournament_id)
        matches = self.db.list_team_matches_for_round(int(round_data["id"]))

        byes = [m for m in matches if m["is_bye"]]
        self.assertEqual(len(byes), 1)
        self.assertEqual(int(byes[0]["white_team_id"]), team_ids[4])
        self.assertEqual(str(byes[0]["result"]).upper(), "H")

        normal = [m for m in matches if not m["is_bye"]]
        self.assertEqual(len(normal), 2)  # 4 equipes → 2 confrontos
        paired = {int(m["white_team_id"]) for m in normal}
        paired |= {int(m["black_team_id"]) for m in normal if m["black_team_id"]}
        self.assertNotIn(team_ids[4], paired)

    def test_requested_team_bye_scores_by_type(self) -> None:
        # H num torneio com win=2/draw=1/loss=0 e 2 tabuleiros:
        # match = draw (1.0), game = boards/2 (1.0) — distinto da vitória cheia.
        tournament_id, team_ids = self._create_team_tournament(teams_count=5, boards_count=2)
        self.db.add_requested_team_bye(tournament_id, team_ids[4], 1, "H")
        round_data = self.service.generate_next_round(tournament_id)

        for match in self.db.list_team_matches_for_round(int(round_data["id"])):
            if match["is_bye"]:
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                self.service.update_result(tournament_id, int(board["id"]), "1-0")
        self.service.close_round(tournament_id, int(round_data["id"]))

        bye = next(
            m for m in self.db.list_team_matches_for_round(int(round_data["id"])) if m["is_bye"]
        )
        self.assertEqual(float(bye["white_match_points"]), 1.0)  # draw points
        self.assertEqual(float(bye["white_game_points"]), 1.0)  # boards/2

    def test_trf25_emits_240_for_requested_team_bye(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, team_ids = self._create_team_tournament(teams_count=5, boards_count=2)
        # Equipe seed 5 (TPN 5, rating mais baixo) com bye zero-point na rodada 1.
        self.db.add_requested_team_bye(tournament_id, team_ids[4], 1, "Z")
        self.service.generate_next_round(tournament_id)

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_bye240.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        bye_lines = [line for line in lines if line.startswith("240 ")]
        self.assertEqual(len(bye_lines), 1)
        line = bye_lines[0]
        self.assertEqual(line[4:5], "Z")           # tipo (col 5)
        self.assertEqual(line[6:9].strip(), "1")   # rodada (col 7-9)
        self.assertEqual(line[10:14].strip(), "5")  # TPN da equipe (col 11-14)

    def test_trf25_requested_team_bye_is_not_pab_and_uses_zpb_in_802(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, team_ids = self._create_team_tournament(teams_count=5, boards_count=2)
        self.db.add_requested_team_bye(tournament_id, team_ids[4], 1, "Z")
        round_data = self.service.generate_next_round(tournament_id)
        self._close_team_round_with_decisive_boards(tournament_id, int(round_data["id"]))

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_req_bye.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        # Bye solicitado nao e pairing-allocated: nenhum registro 320.
        self.assertEqual([line for line in lines if line.startswith("320 ")], [])
        # Sai como 240 (tipo Z).
        self.assertTrue(any(line.startswith("240 ") and line[4:5] == "Z" for line in lines))
        # O 802 da equipe TPN 5 mostra ZPB (zero-point-bye) na rodada 1.
        team5_802 = next(line for line in lines if line.startswith("802 ") and line[4:7].strip() == "5")
        self.assertEqual(team5_802[28:31], "ZPB")

    def test_trf25_allocated_team_bye_is_pab_in_320_and_802(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, _team_ids = self._create_team_tournament(teams_count=3, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        self._close_team_round_with_decisive_boards(tournament_id, int(round_data["id"]))

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_pab.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        # Bye alocado pelo pareamento: ha um 320 (PAB) e nenhum 240 (nada solicitado).
        self.assertEqual(len([line for line in lines if line.startswith("320 ")]), 1)
        self.assertFalse(any(line.startswith("240 ") for line in lines))
        # O 802 do bye alocado usa o codigo PAB.
        self.assertTrue(any(line.startswith("802 ") and "PAB" in line for line in lines))

    def test_fide_statistics_reject_team_tournaments(self) -> None:
        team_tournament_id, _team_ids = self._create_team_tournament()
        with self.assertRaisesRegex(AppError, "individuais"):
            self.export_service._game_statistics_sections(team_tournament_id)

    def test_norm_report_rejects_team_tournaments(self) -> None:
        team_tournament_id, _team_ids = self._create_team_tournament()
        with self.assertRaisesRegex(AppError, "individuais"):
            self.norm_assistant_service.evaluate_tournament(team_tournament_id)

    def test_trf25_team_192_score_code_reflects_standing_criteria(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        exporter = TRF25Exporter(self.export_service)
        team = {"competition_type": "team"}

        def code(primary: str, secondary: str) -> str:
            return exporter._type_code_192(
                team,
                {"team_standing_primary": primary, "team_standing_secondary": secondary},
            )

        # Padrao: match points primario, game points secundario.
        self.assertEqual(code("match_points", "game_points"), "FIDE_TEAM_TYPEA_MP_GP")
        # Ordem invertida.
        self.assertEqual(code("game_points", "match_points"), "FIDE_TEAM_TYPEA_GP_MP")
        # 'wins' e desempate, nao codigo de pontuacao: e ignorado.
        self.assertEqual(code("match_points", "wins"), "FIDE_TEAM_TYPEA_MP")
        self.assertEqual(code("wins", "game_points"), "FIDE_TEAM_TYPEA_GP")
        # Criterios repetidos deduplicam.
        self.assertEqual(code("match_points", "match_points"), "FIDE_TEAM_TYPEA_MP")
        # Sem MP/GP configurado, cai no padrao FIDE MP_GP.
        self.assertEqual(code("wins", "wins"), "FIDE_TEAM_TYPEA_MP_GP")

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
        scoresheets_path = Path(self.temp_dir.name) / "team_scoresheets.pdf"
        site_dir = Path(self.temp_dir.name) / "team_site"

        self.export_service.export_standings(tournament_id, standings_path)
        self.export_service.export_pairings(round_data["id"], pairings_path)
        self.export_service.export_teams(tournament_id, teams_path)
        self.export_service.export_complete(tournament_id, complete_path)
        self.export_service.export_scoresheets(round_data["id"], scoresheets_path)
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
        self.assertIn("Escalações", teams_csv)
        self.assertIn("Titular", teams_csv)
        self.assertIn("Classificação por equipes", complete_csv)
        self.assertIn("Rodada 1", complete_csv)
        self.assertIn("Classificação por equipes", html)
        self.assertIn("Equipes", html)
        self.assertIn("Escalações", html)
        self.assertIn("2 x 0", html)
        self.assertEqual(scoresheets_path.read_bytes()[:4], b"%PDF")
        from pypdf import PdfReader

        self.assertEqual(2, len(PdfReader(scoresheets_path).pages))

    def test_team_crosstable_preserves_board_history_totals_and_exports(self) -> None:
        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(int(round_data["id"]))[0]
        boards = self.db.list_team_boards(int(match["id"]))
        source_team = self.db.get_team_player_by_player(int(boards[0]["white_player_id"]))
        reserve_id = self.db.create_player(tournament_id, name="Reserva escalado", rating=1750)
        self.team_service.add_player(int(source_team["team_id"]), reserve_id, board_number="", role="reserve")
        self.service.adjust_team_board_player(
            tournament_id,
            int(round_data["id"]),
            int(boards[0]["id"]),
            "white",
            reserve_id,
        )
        for board in boards:
            white_player_team = self.db.get_team_player_by_player(int(board["white_player_id"]))
            result = "1-0" if int(white_player_team["team_id"]) == int(match["white_team_id"]) else "0-1"
            self.service.update_result(tournament_id, int(board["id"]), result)
        self.service.close_round(tournament_id, int(round_data["id"]))

        payload = self.service.team_crosstable(tournament_id)
        standings = self.service.team_standings(tournament_id)
        white_row = next(item for item in payload["rows"] if int(item["team_id"]) == int(match["white_team_id"]))
        black_row = next(item for item in payload["rows"] if int(item["team_id"]) == int(match["black_team_id"]))
        white_cell = white_row["rounds"][1]
        black_cell = black_row["rounds"][1]

        self.assertEqual("team", payload["competition_type"])
        self.assertIn("B 1-0 MP 2 GP 2", white_cell["label"])
        self.assertIn("P 0-1 MP 0 GP 0", black_cell["label"])
        self.assertEqual("Reserva escalado", white_cell["boards"][0]["white_player_name"])
        self.assertEqual(
            sum(float(item["match_points"]) for item in standings),
            sum(float(item["match_points"]) for item in payload["rows"]),
        )
        self.assertEqual(
            sum(float(item["game_points"]) for item in standings),
            sum(float(item["game_points"]) for item in payload["rows"]),
        )

        for extension in ("csv", "xlsx", "pdf", "html"):
            output_path = Path(self.temp_dir.name) / f"tabela_cruzada_equipes.{extension}"
            self.export_service.export_crosstable(tournament_id, output_path)
            self.assertTrue(output_path.exists())
        csv_content = (Path(self.temp_dir.name) / "tabela_cruzada_equipes.csv").read_text(encoding="utf-8-sig")
        html_content = (Path(self.temp_dir.name) / "tabela_cruzada_equipes.html").read_text(encoding="utf-8")
        self.assertIn("Equipe", csv_content)
        self.assertIn("MP 2 GP 2", csv_content)
        self.assertIn("Tabela cruzada por equipes", html_content)

if __name__ == "__main__":
    unittest.main()
