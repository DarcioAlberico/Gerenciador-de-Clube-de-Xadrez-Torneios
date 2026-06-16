"""Testes unitários das funções puras extraídas para o pacote pairing/."""

import unittest

from src.services.constants import RESULT_POINTS, AppError
from src.services.pairing import (
    bye_player_ids,
    choose_colors,
    clock_event_issue,
    color_histories,
    color_preference,
    finalize_issues,
    pairing_diagnostics,
    performance_rating,
    plan_pairing_player_swap,
    plan_team_board_player_swap,
    played_pairs,
    swiss_pairings,
    team_bye_summary,
    team_match_summary,
    team_starter_roster,
)


def _players(count: int) -> list[dict[str, object]]:
    return [
        {"id": player_id, "name": f"Jogador {player_id}", "rating": 1800 - player_id}
        for player_id in range(1, count + 1)
    ]


class TestWalkoverNaoContaComoConfronto(unittest.TestCase):
    """FIDE C.04.2 (3.4/3.5): uma partida por W.O./forfait foi PAREADA mas nao
    jogada, entao nao conta nem para a regra de nao-repeticao nem para a
    sequencia de cores. Regressao do impasse em que o Gacrux repareava/recolorava
    duplas de W.O. (correto) e a arbitragem do Albericus bloqueava (errado)."""

    def test_played_pairs_exclui_walkover(self):
        pairings = [
            {"is_bye": 0, "white_player_id": 1, "black_player_id": 2, "result": "1-0"},
            {"is_bye": 0, "white_player_id": 3, "black_player_id": 4, "result": "1F-0F"},
            {"is_bye": 0, "white_player_id": 5, "black_player_id": 6, "result": "0F-1F"},
            {"is_bye": 0, "white_player_id": 7, "black_player_id": 8, "result": "0F-0F"},
        ]
        # Apenas o jogo realmente jogado (1 x 2) conta como confronto.
        self.assertEqual(played_pairs(pairings), {frozenset((1, 2))})

    def test_color_histories_exclui_walkover(self):
        pairings = [
            {"is_bye": 0, "white_player_id": 1, "black_player_id": 2, "result": "0-1"},
            {"is_bye": 0, "white_player_id": 1, "black_player_id": 3, "result": "1F-0F"},  # W.O.
            {"is_bye": 0, "white_player_id": 1, "black_player_id": 4, "result": "1-0"},
        ]
        histories = color_histories(pairings)
        self.assertEqual(histories[1], ["W", "W"])  # a branca do W.O. nao entra na sequencia
        self.assertEqual(histories[2], ["B"])
        self.assertEqual(histories[3], [])           # so teve W.O. -> nenhuma cor registrada
        self.assertEqual(histories[4], ["B"])

    def test_jogo_real_ainda_conta(self):
        pairings = [{"is_bye": 0, "white_player_id": 1, "black_player_id": 2, "result": "1-0"}]
        self.assertEqual(played_pairs(pairings), {frozenset((1, 2))})
        self.assertEqual(color_histories(pairings), {1: ["W"], 2: ["B"]})


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


class TestPairingDiagnostics(unittest.TestCase):
    def test_repeated_opponent_is_marked_inevitable_with_two_players(self):
        diagnostics = pairing_diagnostics(
            [{"board_number": 1, "white_player_id": 1, "black_player_id": 2, "is_bye": 0}],
            histories={},
            played_pairs={frozenset((1, 2))},
            bye_player_ids=set(),
            players=_players(2),
        )

        self.assertEqual(1, len(diagnostics))
        self.assertEqual("opponent_repeat", diagnostics[0]["kind"])
        self.assertIs(diagnostics[0]["avoidable"], False)
        self.assertEqual("attention", diagnostics[0]["severity"])

    def test_repeated_opponent_is_marked_avoidable_when_exact_alternative_exists(self):
        diagnostics = pairing_diagnostics(
            [
                {"board_number": 1, "white_player_id": 1, "black_player_id": 2, "is_bye": 0},
                {"board_number": 2, "white_player_id": 3, "black_player_id": 4, "is_bye": 0},
            ],
            histories={},
            played_pairs={frozenset((1, 2))},
            bye_player_ids=set(),
            players=_players(4),
        )

        repeated = [item for item in diagnostics if item["kind"] == "opponent_repeat"]
        self.assertEqual(1, len(repeated))
        self.assertIs(repeated[0]["avoidable"], True)
        self.assertEqual("decision", repeated[0]["severity"])

    def test_hard_color_violation_is_marked_avoidable_when_colors_can_be_repaired(self):
        diagnostics = pairing_diagnostics(
            [
                {"board_number": 1, "white_player_id": 1, "black_player_id": 2, "is_bye": 0},
                {"board_number": 2, "white_player_id": 3, "black_player_id": 4, "is_bye": 0},
            ],
            histories={1: ["W", "W"], 2: ["B", "B"], 3: ["W", "W"], 4: ["B", "B"]},
            played_pairs=set(),
            bye_player_ids=set(),
            players=_players(4),
        )

        hard_colors = [item for item in diagnostics if item["kind"] == "hard_color"]
        self.assertEqual(4, len(hard_colors))
        self.assertTrue(all(item["avoidable"] is True for item in hard_colors))
        self.assertTrue(all(item["severity"] == "decision" for item in hard_colors))

    def test_duplicate_player_is_flagged_as_decision(self):
        diagnostics = pairing_diagnostics(
            [
                {"board_number": 1, "white_player_id": 1, "black_player_id": 2, "is_bye": 0},
                {"board_number": 2, "white_player_id": 1, "black_player_id": 3, "is_bye": 0},
            ],
            histories={},
            played_pairs=set(),
            bye_player_ids=set(),
            players=_players(3),
        )

        duplicates = [item for item in diagnostics if item["kind"] == "duplicate_player"]
        self.assertEqual(1, len(duplicates))
        self.assertEqual([1], duplicates[0]["player_ids"])
        self.assertEqual("decision", duplicates[0]["severity"])
        self.assertIn("mais de uma mesa", duplicates[0]["detail"])

    def test_repeated_float_is_flagged_when_same_direction_repeats(self):
        diagnostics = pairing_diagnostics(
            [{"board_number": 1, "white_player_id": 1, "black_player_id": 2, "is_bye": 0}],
            histories={},
            played_pairs=set(),
            bye_player_ids=set(),
            players=_players(2),
            standings={1: {"points": 1.0}, 2: {"points": 2.0}},
            float_histories={1: ["up"], 2: ["down"]},
        )

        floats = [item for item in diagnostics if item["kind"] == "float_repeat"]
        self.assertEqual(2, len(floats))
        self.assertEqual({1, 2}, {item["player_ids"][0] for item in floats})
        self.assertTrue(all(item["severity"] == "attention" for item in floats))
        self.assertTrue(all(item["avoidable"] is None for item in floats))


class TestByeEligibilityHistory(unittest.TestCase):
    def test_zero_and_half_point_absences_do_not_block_pairing_allocated_bye(self):
        pairings = [
            {"white_player_id": 1, "black_player_id": None, "result": "Z", "is_bye": 1},
            {"white_player_id": 2, "black_player_id": None, "result": "H", "is_bye": 1},
            {"white_player_id": 3, "black_player_id": None, "result": "F", "is_bye": 1},
            {"white_player_id": 4, "black_player_id": None, "result": "BYE", "is_bye": 1},
        ]

        self.assertEqual({3, 4}, bye_player_ids(pairings))


class TestColorPreference(unittest.TestCase):
    def test_no_history_has_no_preference(self):
        preference = color_preference(1, {})

        self.assertIsNone(preference.due_color)
        self.assertEqual("none", preference.strength)
        self.assertEqual(0, preference.color_imbalance)

    def test_two_same_colors_are_absolute_preference(self):
        preference = color_preference(1, {1: ["W", "W"]})

        self.assertEqual("B", preference.due_color)
        self.assertEqual("absolute", preference.strength)
        self.assertEqual(2, preference.color_imbalance)
        self.assertEqual("W", preference.repeated_color)
        self.assertTrue(preference.is_absolute)

    def test_color_imbalance_is_strong_preference_when_not_absolute(self):
        preference = color_preference(1, {1: ["W", "B", "W"]})

        self.assertEqual("B", preference.due_color)
        self.assertEqual("strong", preference.strength)
        self.assertEqual(1, preference.color_imbalance)

    def test_balanced_history_prefers_alternating_last_color_mildly(self):
        preference = color_preference(1, {1: ["W", "B"]})

        self.assertEqual("W", preference.due_color)
        self.assertEqual("mild", preference.strength)
        self.assertEqual(0, preference.color_imbalance)

    def test_choose_colors_satisfies_opposite_absolute_preferences(self):
        white_id, black_id = choose_colors(
            {"id": 1, "name": "A", "rating": 1800},
            {"id": 2, "name": "B", "rating": 1700},
            {1: ["W", "W"], 2: ["B", "B"]},
        )

        self.assertEqual((2, 1), (white_id, black_id))


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


class TestSwissDownfloatOrdering(unittest.TestCase):
    """Floaters que descem entram pelo topo do grupo seguinte (downfloat mínimo).

    Cenário: um jogador isolado no topo (2.0 pts) acima de um grupo de 1.0 e um
    jogador isolado no fundo (0.0). Sem reordenar o grupo ao receber os floaters,
    o jogador de 2.0 despencava de grupo em grupo e acabava pareado contra o de
    0.0 (diferença de 2 pontos). O esperado FIDE (C.04) é descer um grupo por
    vez, mantendo a diferença de pontuação dos pares em no máximo 1.
    """

    @staticmethod
    def _standings(points: dict[int, float]) -> dict[int, dict[str, object]]:
        return {
            pid: {
                "player_id": pid,
                "points": pts,
                "position": rank,
                "rating": 2100 - pid * 100,
                "buchholz": 0.0,
                "buchholz_median": 0.0,
                "sonneborn_berger": 0.0,
                "wins": 0,
            }
            for rank, (pid, pts) in enumerate(points.items(), start=1)
        }

    def test_high_floater_drops_one_group_not_to_the_bottom(self) -> None:
        points = {1: 2.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 0.0}
        players = [{"id": pid, "name": f"P{pid}", "rating": 2100 - pid * 100} for pid in points]

        pairs = swiss_pairings(
            players,
            self._standings(points),
            {},
            {},
            set(),
            set(),
            max_exhaustive_pairing_players=16,
            repeat_pairing_penalty=1_000_000,
            score_group_float_penalty=10_000,
            score_diff_penalty=1_000,
        )

        max_diff = max(
            abs(points[pair["white_player_id"]] - points[pair["black_player_id"]])
            for pair in pairs
            if not pair["is_bye"]
        )
        self.assertEqual(max_diff, 1.0)


if __name__ == "__main__":
    unittest.main()
