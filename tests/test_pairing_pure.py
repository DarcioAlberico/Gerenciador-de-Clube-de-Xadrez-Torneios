"""Testes unitários das funções puras extraídas para o pacote pairing/."""

import unittest

from src.services.constants import RESULT_POINTS, AppError
from src.services.pairing import (
    clock_event_issue,
    finalize_issues,
    performance_rating,
    plan_pairing_player_swap,
    plan_team_board_player_swap,
    team_bye_summary,
    team_match_summary,
    team_starter_roster,
)


class TestTeamMatchSummary(unittest.TestCase):
    def test_decisive_match_with_color_swapped_board(self):
        match = {"id": 1, "white_team_id": 100, "black_team_id": 200}
        white_team = {10, 11}
        black_team = {20, 21}
        boards = [
            {"white_player_id": 10, "black_player_id": 20, "result": "1-0"},
            {"white_player_id": 21, "black_player_id": 11, "result": "0-1"},
        ]
        summary = team_match_summary(
            match, boards, white_team, black_team, RESULT_POINTS,
            win_points=2.0, loss_points=0.0, draw_points=1.0,
        )
        self.assertEqual(summary["white_game_points"], 2.0)
        self.assertEqual(summary["black_game_points"], 0.0)
        self.assertEqual(summary["result"], "1-0")
        self.assertEqual(summary["white_match_points"], 2.0)
        self.assertEqual(summary["black_match_points"], 0.0)
        self.assertEqual(summary["team_match_id"], 1)

    def test_drawn_match_awards_draw_points_to_both(self):
        match = {"id": 7, "white_team_id": 100, "black_team_id": 200}
        white_team = {10, 11}
        black_team = {20, 21}
        boards = [
            {"white_player_id": 10, "black_player_id": 20, "result": "1-0"},
            {"white_player_id": 21, "black_player_id": 11, "result": "1-0"},
        ]
        summary = team_match_summary(
            match, boards, white_team, black_team, RESULT_POINTS,
            win_points=2.0, loss_points=0.0, draw_points=1.0,
        )
        self.assertEqual(summary["white_game_points"], 1.0)
        self.assertEqual(summary["black_game_points"], 1.0)
        self.assertEqual(summary["result"], "1/2-1/2")
        self.assertEqual(summary["white_match_points"], 1.0)
        self.assertEqual(summary["black_match_points"], 1.0)


class TestTeamByeSummary(unittest.TestCase):
    def test_bye_awards_win_points_and_full_boards(self):
        summary = team_bye_summary({"id": 5}, win_points=2.0, boards_count=4)
        self.assertEqual(summary["team_match_id"], 5)
        self.assertEqual(summary["result"], "BYE")
        self.assertEqual(summary["white_match_points"], 2.0)
        self.assertEqual(summary["black_match_points"], 0.0)
        self.assertEqual(summary["white_game_points"], 4.0)
        self.assertEqual(summary["black_game_points"], 0.0)


class TestTeamStarterRoster(unittest.TestCase):
    def _assignment(self, board, player_id, rating, role="starter", status="active"):
        return {
            "role": role,
            "board_number": board,
            "player_status": status,
            "player_id": player_id,
            "player_rating": rating,
        }

    def test_collects_starters_and_average_seed(self):
        assignments = [
            self._assignment(1, 10, 1500),
            self._assignment(2, 11, 1700),
            self._assignment(3, 12, 1600, role="reserve"),  # ignorado
        ]
        starters, seed = team_starter_roster("Equipe A", assignments, boards_count=2)
        self.assertEqual(starters, {1: 10, 2: 11})
        self.assertEqual(seed, 1600)

    def test_inactive_starter_is_ignored_and_raises_when_board_missing(self):
        assignments = [
            self._assignment(1, 10, 1500),
            self._assignment(2, 11, 1700, status="absent"),
        ]
        with self.assertRaises(AppError):
            team_starter_roster("Equipe A", assignments, boards_count=2)


class TestPlanPairingPlayerSwap(unittest.TestCase):
    def test_swap_mirrors_into_target_pairing(self):
        pairings = [
            {"id": 1, "white_player_id": 10, "black_player_id": 20},
            {"id": 2, "white_player_id": 30, "black_player_id": 40},
        ]
        target_slot = {"pairing": pairings[1], "color": "white"}
        updates = plan_pairing_player_swap(
            pairings, pairings[0], target_slot, "white",
            source_player_id=10, replacement_player_id=30,
        )
        self.assertEqual(dict((pid, (w, b)) for pid, w, b in updates), {1: (30, 20), 2: (10, 40)})

    def test_only_source_pairing_when_no_target(self):
        pairings = [{"id": 1, "white_player_id": 10, "black_player_id": 20}]
        updates = plan_pairing_player_swap(
            pairings, pairings[0], None, "white",
            source_player_id=10, replacement_player_id=99,
        )
        self.assertEqual(updates, [(1, 99, 20)])

    def test_same_player_both_sides_raises(self):
        pairings = [{"id": 1, "white_player_id": 10, "black_player_id": 20}]
        with self.assertRaises(AppError):
            plan_pairing_player_swap(
                pairings, pairings[0], None, "black",
                source_player_id=20, replacement_player_id=10,
            )


class TestPlanTeamBoardPlayerSwap(unittest.TestCase):
    def test_swap_mirrors_into_target_board(self):
        boards = [
            {"id": 1, "white_player_id": 10, "black_player_id": 20},
            {"id": 2, "white_player_id": 30, "black_player_id": 40},
        ]
        target_slot = {"board": boards[1], "color": "white"}
        updates = plan_team_board_player_swap(
            boards, {1, 2}, 1, target_slot, "white",
            source_player_id=10, replacement_player_id=30,
        )
        self.assertEqual(dict((bid, (w, b)) for bid, w, b in updates), {1: (30, 20), 2: (10, 40)})

    def test_same_player_both_sides_raises(self):
        boards = [{"id": 1, "white_player_id": 10, "black_player_id": 20}]
        with self.assertRaises(AppError):
            plan_team_board_player_swap(
                boards, {1}, 1, None, "black",
                source_player_id=20, replacement_player_id=10,
            )


class TestClockEventIssue(unittest.TestCase):
    def test_flag_fall_is_issue(self):
        issue = clock_event_issue({"event_type": "flag_fall", "id": 1})
        self.assertIsNotNone(issue)
        self.assertEqual(issue["kind"], "flag_fall")

    def test_time_warning_above_threshold_is_not_issue(self):
        self.assertIsNone(clock_event_issue({"event_type": "time_warning", "seconds_remaining": 120}))

    def test_time_warning_at_threshold_is_issue(self):
        self.assertIsNotNone(clock_event_issue({"event_type": "time_warning", "seconds_remaining": 60}))

    def test_unknown_event_is_not_issue(self):
        self.assertIsNone(clock_event_issue({"event_type": "move_made"}))


class TestFinalizeIssues(unittest.TestCase):
    def test_drops_acknowledged_sorts_desc_and_truncates(self):
        issues = [
            {"issue_key": "a", "created_at": "2026-01-01"},
            {"issue_key": "b", "created_at": "2026-03-01"},
            {"issue_key": "c", "created_at": "2026-02-01"},
        ]
        result = finalize_issues(issues, acknowledged_keys={"a"}, limit=10)
        self.assertEqual([item["issue_key"] for item in result], ["b", "c"])

    def test_limit_applies_after_sort(self):
        issues = [
            {"issue_key": "a", "created_at": "2026-01-01"},
            {"issue_key": "b", "created_at": "2026-03-01"},
        ]
        result = finalize_issues(issues, acknowledged_keys=set(), limit=1)
        self.assertEqual([item["issue_key"] for item in result], ["b"])


class TestPerformanceRating(unittest.TestCase):
    def test_unrated_opponents_excluded_from_score_and_average(self):
        # Empate contra ranqueado (1600) + vitoria contra nao-ranqueado.
        # A vitoria contra o sem-rating nao pode entrar no score nem na media:
        # performance = media(1600) + 0 (50% sobre 1 jogo ranqueado) = 1600.
        player_stat = {"earned_against": [(1, 0.5), (2, 1.0)]}
        stats = {1: {"rating": 1600}, 2: {"rating": 0}}
        self.assertEqual(performance_rating(player_stat, stats), 1600)

    def test_no_rated_opponents_returns_empty(self):
        player_stat = {"earned_against": [(1, 1.0)]}
        stats = {1: {"rating": 0}}
        self.assertEqual(performance_rating(player_stat, stats), "")

    def test_fifty_percent_returns_average_rating(self):
        # Vitoria sobre 1600 e derrota para 1800: 50% -> media (1700).
        player_stat = {"earned_against": [(1, 1.0), (2, 0.0)]}
        stats = {1: {"rating": 1600}, 2: {"rating": 1800}}
        self.assertEqual(performance_rating(player_stat, stats), 1700)

    def test_perfect_score_caps_at_plus_800(self):
        player_stat = {"earned_against": [(1, 1.0)]}
        stats = {1: {"rating": 1600}}
        self.assertEqual(performance_rating(player_stat, stats), 2400)


if __name__ == "__main__":
    unittest.main()
