from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from time import perf_counter
from typing import Any

from src.core.database import Database
from src.core.services import (
    AppError,
    PairingService,
)
from tests.fixtures import load_tournament_fixture
from tests.support.core_service_base import CoreServiceTestCase


class TournamentFixtureTest(unittest.TestCase):
    """Smoke da pasta tests/fixtures/tournaments/ — garante que o cenário
    carrega e o motor produz um estado consistente."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.db = Database(base_path / "albericus.db", backup_dir=base_path / "backups")
        self.service = PairingService(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_individual_8_players_3_rounds_fixture(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.service
        )

        players = self.db.list_players(tournament_id, active_only=False)
        rounds = self.db.list_rounds(tournament_id)
        standings = self.service.standings(tournament_id)

        self.assertEqual(8, len(players))
        self.assertEqual(3, len(rounds))
        self.assertTrue(
            all(r["status"] == "closed" for r in rounds),
            "Todas as rodadas da fixture devem ficar fechadas.",
        )
        self.assertEqual(8, len(standings))
        # Soma de pontos = total de mesas (4 por rodada) × 3 rodadas × 1.0
        total_points = sum(float(row.get("points") or 0) for row in standings)
        self.assertAlmostEqual(12.0, total_points, places=2)

        # result_states_summary cobre todas as mesas como "locked" (round closed,
        # com resultado) — exercita o derive_pairing_state na ponta.
        states = self.service.result_states_summary(tournament_id)
        self.assertEqual(12, states["locked"])
        self.assertEqual(0, states["empty"])
        self.assertEqual(0, states["published"])


class DerivePairingStateTest(unittest.TestCase):
    """Função pura — exercita a matriz de estados sem precisar de banco."""

    def test_empty_when_no_result(self) -> None:
        self.assertEqual(
            PairingService.derive_pairing_state(result="", round_closed=False), "empty"
        )

    def test_submitted_when_pending_submission_no_result(self) -> None:
        self.assertEqual(
            PairingService.derive_pairing_state(
                result="", round_closed=False, has_pending_submission=True
            ),
            "submitted",
        )

    def test_published_when_result_open_round(self) -> None:
        self.assertEqual(
            PairingService.derive_pairing_state(result="1-0", round_closed=False),
            "published",
        )

    def test_locked_when_round_closed_with_result(self) -> None:
        self.assertEqual(
            PairingService.derive_pairing_state(result="1-0", round_closed=True),
            "locked",
        )

    def test_corrected_trumps_locked(self) -> None:
        self.assertEqual(
            PairingService.derive_pairing_state(
                result="0-1", round_closed=True, has_correction=True
            ),
            "corrected",
        )

    def test_corrected_trumps_submitted(self) -> None:
        self.assertEqual(
            PairingService.derive_pairing_state(
                result="1-0", round_closed=False,
                has_pending_submission=True, has_correction=True,
            ),
            "corrected",
        )

    def test_closed_round_without_result_is_empty(self) -> None:
        # Mesa sem resultado em rodada fechada ainda é "empty" (não locked).
        self.assertEqual(
            PairingService.derive_pairing_state(result="", round_closed=True),
            "empty",
        )


class PairingRulesTest(CoreServiceTestCase):
    def test_phase3_tiebreak_components_are_persisted_and_exported(self) -> None:
        self._create_players(4)
        first_round = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(first_round["id"])
        self.service.close_round(self.tournament_id, first_round["id"])

        second_round = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(second_round["id"])
        self.service.close_round(self.tournament_id, second_round["id"])

        standings = self.service.tiebreak_report(self.tournament_id)
        first = standings[0]
        components = first["tiebreak_components"]
        self.assertIn("buchholz", components)
        self.assertIn("buchholz_median", components)
        self.assertIn("sonneborn_berger", components)
        self.assertIn("direct_encounter", components)
        self.assertIn("performance", components)
        self.assertEqual(first["buchholz"], components["buchholz"]["total"])
        self.assertEqual(first["sonneborn_berger"], components["sonneborn_berger"]["total"])
        self.assertTrue(components["buchholz"]["opponents"])

        persisted = self.db.list_tiebreak_components(
            self.tournament_id,
            player_id=int(first["player_id"]),
            round_id=int(second_round["id"]),
        )
        self.assertGreaterEqual(len(persisted), 6)
        self.assertIn("buchholz", {item["criterion"] for item in persisted})
        self.assertIn("opponents", persisted[0]["components_json"])

        report_path = Path(self.temp_dir.name) / "desempates.csv"
        self.export_service.export_tiebreak_report(self.tournament_id, report_path)
        report_content = report_path.read_text(encoding="utf-8-sig")
        self.assertIn("Buchholz", report_content)
        self.assertIn("Sonneborn-Berger", report_content)

        site_path = self.export_service.export_site(self.tournament_id, Path(self.temp_dir.name) / "site")
        html = site_path.read_text(encoding="utf-8")
        self.assertIn("Componentes de desempate", html)
        self.assertIn("Buchholz", html)

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

    def test_first_round_respects_initial_order_rating_source(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "rounds_count": "5",
                "bye_points": "1",
            },
            {"initial_order": "national_rating"},
            [],
        )
        fide_high_id = self.db.create_player(
            self.tournament_id,
            name="FIDE alto",
            rating=1000,
            national_rating=1000,
            international_rating=2500,
        )
        national_1_id = self.db.create_player(
            self.tournament_id,
            name="Nacional 1",
            rating=1000,
            national_rating=2400,
            international_rating=0,
        )
        national_2_id = self.db.create_player(
            self.tournament_id,
            name="Nacional 2",
            rating=1000,
            national_rating=2300,
            international_rating=0,
        )
        national_low_id = self.db.create_player(
            self.tournament_id,
            name="Nacional baixo",
            rating=1000,
            national_rating=900,
            international_rating=0,
        )

        round_data = self.service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(round_data["id"])

        self.assertEqual(pairings[0]["white_player_id"], national_1_id)
        self.assertEqual(pairings[0]["black_player_id"], fide_high_id)
        self.assertEqual(pairings[1]["white_player_id"], national_low_id)
        self.assertEqual(pairings[1]["black_player_id"], national_2_id)

    def test_prohibited_pairing_is_never_paired(self) -> None:
        self._create_players(8)
        players = self.db.list_players(self.tournament_id, active_only=True)
        seeding = [
            int(p["id"])
            for p in sorted(players, key=lambda p: -int(p.get("rating") or 0))
        ]

        def pair_set(pairings: list[dict[str, Any]]) -> set[frozenset[int]]:
            return {
                frozenset({int(p["white_player_id"]), int(p["black_player_id"])})
                for p in pairings
                if p.get("black_player_id") is not None
            }

        # Sem proibição: seed 1 pareia com seed 5 (topo vs base do mesmo grupo).
        plain = pair_set(self.service._swiss_pairings(self.tournament_id, players, 2))
        self.assertIn(frozenset({seeding[0], seeding[4]}), plain)

        # Proibindo seed 1 x seed 5, eles nunca podem ser pareados.
        self.db.add_prohibited_pairing(self.tournament_id, seeding[0], seeding[4])
        guarded = pair_set(self.service._swiss_pairings(self.tournament_id, players, 2))
        self.assertNotIn(frozenset({seeding[0], seeding[4]}), guarded)
        self.assertEqual(len(guarded), 4)  # 8 jogadores → 4 jogos íntegros

    def test_prohibition_respects_round_window(self) -> None:
        self._create_players(8)
        players = self.db.list_players(self.tournament_id, active_only=True)
        seeding = [
            int(p["id"])
            for p in sorted(players, key=lambda p: -int(p.get("rating") or 0))
        ]

        def pair_set(pairings: list[dict[str, Any]]) -> set[frozenset[int]]:
            return {
                frozenset({int(p["white_player_id"]), int(p["black_player_id"])})
                for p in pairings
                if p.get("black_player_id") is not None
            }

        # Proibição válida só na rodada 3.
        self.db.add_prohibited_pairing(
            self.tournament_id, seeding[0], seeding[4], first_round=3, last_round=3
        )
        # Rodada 2 fora da janela: o par ainda ocorre.
        self.assertIn(
            frozenset({seeding[0], seeding[4]}),
            pair_set(self.service._swiss_pairings(self.tournament_id, players, 2)),
        )
        # Rodada 3 dentro da janela: bloqueado.
        self.assertNotIn(
            frozenset({seeding[0], seeding[4]}),
            pair_set(self.service._swiss_pairings(self.tournament_id, players, 3)),
        )

    def test_requested_bye_excludes_player_from_pairing(self) -> None:
        # 5 jogadores, 1 bye solicitado → 4 a parear (par), sem bye alocado extra.
        player_ids = self._create_players(5)
        self.db.add_requested_bye(self.tournament_id, player_ids[4], 1, "H")

        round_data = self.service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(int(round_data["id"]))

        byes = [p for p in pairings if p["is_bye"]]
        self.assertEqual(len(byes), 1)
        self.assertEqual(int(byes[0]["white_player_id"]), player_ids[4])
        self.assertEqual(str(byes[0]["result"]).upper(), "H")

        normal = [p for p in pairings if not p["is_bye"]]
        self.assertEqual(len(normal), 2)  # 4 jogadores → 2 confrontos
        paired = {int(p["white_player_id"]) for p in normal}
        paired |= {int(p["black_player_id"]) for p in normal if p["black_player_id"]}
        self.assertNotIn(player_ids[4], paired)

    def test_requested_bye_makes_odd_field_pairable_under_disable_bye(self) -> None:
        # disable_bye + 5 ativos (impar): o bye solicitado deixa 4 a parear, par.
        # A guarda de paridade deve incidir sobre to_pair, nao sobre todos.
        self._enable_disable_bye()
        player_ids = self._create_players(5)
        self.db.add_requested_bye(self.tournament_id, player_ids[4], 1, "H")

        round_data = self.service.generate_next_round(self.tournament_id)
        pairings = self.db.get_pairings_for_round(int(round_data["id"]))

        byes = [p for p in pairings if p["is_bye"]]
        self.assertEqual(len(byes), 1)  # apenas o bye solicitado, nenhum alocado
        self.assertEqual(int(byes[0]["white_player_id"]), player_ids[4])
        self.assertEqual(len([p for p in pairings if not p["is_bye"]]), 2)

    def test_disable_bye_still_blocks_odd_field_without_requested_bye(self) -> None:
        # Sem bye solicitado, disable_bye + impar continua bloqueando.
        self._enable_disable_bye()
        self._create_players(5)
        with self.assertRaises(AppError):
            self.service.generate_next_round(self.tournament_id)

    def test_requested_bye_rejected_in_round_robin(self) -> None:
        player_ids = self._create_players(4)
        self._set_individual_pairing_method("round_robin")
        self.db.add_requested_bye(self.tournament_id, player_ids[0], 1, "H")
        with self.assertRaisesRegex(AppError, "exclusivos do sistema Suico"):
            self.service.generate_next_round(self.tournament_id)

    def test_requested_bye_rejected_in_knockout(self) -> None:
        player_ids = self._create_players(4)
        self._set_individual_pairing_method("knockout")
        self.db.add_requested_bye(self.tournament_id, player_ids[0], 1, "Z")
        with self.assertRaisesRegex(AppError, "exclusivos do sistema Suico"):
            self.service.generate_next_round(self.tournament_id)

    def test_round_robin_still_generates_without_requested_bye(self) -> None:
        # Regressao: sem bye solicitado, round-robin continua gerando normalmente.
        self._create_players(4)
        self._set_individual_pairing_method("round_robin")
        round_data = self.service.generate_next_round(self.tournament_id)
        self.assertTrue(int(round_data["id"]))
        pairings = self.db.get_pairings_for_round(int(round_data["id"]))
        self.assertEqual(len(pairings), 2)  # 4 jogadores → 2 confrontos

    def test_requested_bye_scores_by_type(self) -> None:
        from src.services.pairing import calculate_player_standings

        player_ids = self._create_players(4)  # bye_points padrão = 1.0
        players = self.db.list_players(self.tournament_id, active_only=False)
        tournament = self.db.get_tournament(self.tournament_id)
        closed_pairings = [
            {"white_player_id": player_ids[0], "black_player_id": None,
             "result": "F", "is_bye": 1, "round_number": 1},
            {"white_player_id": player_ids[1], "black_player_id": None,
             "result": "H", "is_bye": 1, "round_number": 1},
            {"white_player_id": player_ids[2], "black_player_id": None,
             "result": "Z", "is_bye": 1, "round_number": 1},
            {"white_player_id": player_ids[3], "black_player_id": None,
             "result": "BYE", "is_bye": 1, "round_number": 1},
        ]
        standings = calculate_player_standings(tournament, players, closed_pairings)
        points = {int(s["player_id"]): float(s["points"]) for s in standings}
        self.assertEqual(points[player_ids[0]], 1.0)  # F = ponto inteiro
        self.assertEqual(points[player_ids[1]], 0.5)  # H = meio ponto
        self.assertEqual(points[player_ids[2]], 0.0)  # Z = zero ponto
        self.assertEqual(points[player_ids[3]], 1.0)  # bye alocado usa bye_points

    def test_tiebreak_default_sequence_reproduces_legacy_order(self) -> None:
        from src.services.pairing import DEFAULT_PLAYER_TIEBREAKS, calculate_player_standings

        tournament, closed, ids = self._phase_a_fixture()
        players = self.db.list_players(self.tournament_id, active_only=False)

        standings = calculate_player_standings(tournament, players, closed)

        # Ordem por pontos (P1>P2>P3>P4) e a sequencia padrao (sem config) e usada.
        self.assertEqual([s["player_id"] for s in standings], [ids[0], ids[1], ids[2], ids[3]])
        self.assertEqual(standings[0]["tiebreak_order"], DEFAULT_PLAYER_TIEBREAKS)
        # Componentes historicos seguem presentes (compat. com exportacoes).
        self.assertLessEqual(
            {"buchholz", "buchholz_median", "sonneborn_berger", "direct_encounter", "wins", "performance"},
            set(standings[0]["tiebreak_components"].keys()),
        )

    def test_tiebreak_new_criteria_values_match_manual(self) -> None:
        from src.services.pairing import calculate_player_standings, parse_player_tiebreak_sequence

        tournament, closed, ids = self._phase_a_fixture()
        players = self.db.list_players(self.tournament_id, active_only=False)
        sequence = parse_player_tiebreak_sequence(
            [{"code": "buchholz_cut1"}, {"code": "cumulative"}, {"code": "koya"}, {"code": "aro"}, {"code": "black_games"}]
        )

        standings = calculate_player_standings(tournament, players, closed, sequence=sequence)
        leader = next(s for s in standings if s["player_id"] == ids[0])
        components = leader["tiebreak_components"]

        # P1 enfrentou P4(0 pts), P2(2.0 pts), P3(1.5 pts); ratings 1850/1950/1900.
        self.assertEqual(components["buchholz_cut1"]["value"], 3.5)   # descarta o 0 → 2.0+1.5
        self.assertEqual(components["cumulative"]["value"], 5.5)      # 1+2+2.5
        self.assertEqual(components["koya"]["value"], 1.5)            # vs P2 (1.0) + vs P3 (0.5)
        self.assertEqual(components["aro"]["value"], 1900.0)          # (1850+1950+1900)/3
        self.assertEqual(components["black_games"]["value"], 0.0)     # P1 jogou sempre de brancas

    def test_tiebreak_buchholz_cut_handles_bye_via_unplayed_param(self) -> None:
        from src.services.pairing import calculate_player_standings

        ids = self._create_players(3)  # X=ids[0], Y=ids[1], Z=ids[2]
        tournament = self.db.get_tournament(self.tournament_id)
        players = self.db.list_players(self.tournament_id, active_only=False)
        closed = [
            {"white_player_id": ids[0], "black_player_id": ids[1], "result": "1-0", "is_bye": 0, "round_number": 1},
            {"white_player_id": ids[0], "black_player_id": ids[2], "result": "1-0", "is_bye": 0, "round_number": 2},
            {"white_player_id": ids[0], "black_player_id": None, "result": "BYE", "is_bye": 1, "round_number": 3},
        ]

        def cut1(unplayed: str) -> float:
            standings = calculate_player_standings(
                tournament, players, closed,
                sequence=[{"code": "buchholz_cut1", "params": {"cut_low": 1, "unplayed": unplayed}}],
            )
            leader = next(s for s in standings if s["player_id"] == ids[0])
            return leader["tiebreak_values"]["buchholz_cut1"]

        # Adversarios Y e Z terminam com 0 pts. "real" ignora o bye → descarta um 0 → 0.0.
        self.assertEqual(cut1("real"), 0.0)
        # "self" injeta a propria pontuacao do jogador (3.0) para a rodada de bye.
        self.assertEqual(cut1("self"), 3.0)

    def test_tiebreak_sequence_changes_final_order(self) -> None:
        from src.services.pairing import calculate_player_standings

        ids = self._create_players(8)  # A=ids[0] (2000), B=ids[1] (1950)
        tournament = self.db.get_tournament(self.tournament_id)
        players = self.db.list_players(self.tournament_id, active_only=False)
        closed = [
            # A: 2 vitorias de brancas e 1 derrota → 2 pts, 2 vitorias, 0 partidas de pretas.
            {"white_player_id": ids[0], "black_player_id": ids[2], "result": "1-0", "is_bye": 0, "round_number": 1},
            {"white_player_id": ids[0], "black_player_id": ids[3], "result": "1-0", "is_bye": 0, "round_number": 2},
            {"white_player_id": ids[0], "black_player_id": ids[4], "result": "0-1", "is_bye": 0, "round_number": 3},
            # B: vitoria de pretas + 2 empates de pretas → 2 pts, 1 vitoria, 3 partidas de pretas.
            {"white_player_id": ids[5], "black_player_id": ids[1], "result": "0-1", "is_bye": 0, "round_number": 1},
            {"white_player_id": ids[6], "black_player_id": ids[1], "result": "1/2-1/2", "is_bye": 0, "round_number": 2},
            {"white_player_id": ids[7], "black_player_id": ids[1], "result": "1/2-1/2", "is_bye": 0, "round_number": 3},
        ]

        def position_of(player_id: int, sequence: list[dict]) -> int:
            standings = calculate_player_standings(tournament, players, closed, sequence=sequence)
            return next(s["position"] for s in standings if s["player_id"] == player_id)

        # Empatados em pontos (2.0). Por vitorias, A (2) fica a frente de B (1).
        self.assertLess(position_of(ids[0], [{"code": "wins"}]), position_of(ids[1], [{"code": "wins"}]))
        # Por partidas com pretas, B (3) fica a frente de A (0) — ordem invertida.
        self.assertLess(position_of(ids[1], [{"code": "black_games"}]), position_of(ids[0], [{"code": "black_games"}]))

    def test_tiebreak_sequence_persists_and_threads_into_standings(self) -> None:
        from src.services.pairing import serialize_tiebreak_sequence

        self._create_players(4)
        sequence = [{"code": "direct_encounter", "params": {}}, {"code": "cumulative", "params": {}}, {"code": "wins", "params": {}}]
        self.db.save_tournament_settings(
            self.tournament_id, {"tiebreak_sequence": serialize_tiebreak_sequence(sequence)}
        )

        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)

        # A sequencia gravada chega ate o calculo da classificacao.
        standings = self.service.standings(self.tournament_id)
        self.assertEqual(standings[0]["tiebreak_order"], ["direct_encounter", "cumulative", "wins"])
        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(settings["tiebreak_sequence"], serialize_tiebreak_sequence(sequence))

    def test_validated_settings_normalizes_tiebreak_sequence(self) -> None:
        from src.services.pairing import serialize_tiebreak_sequence

        payload = self.tournament_service._validated_settings(
            {"tiebreak_sequence": [{"code": "points"}, {"code": "buchholz"}, {"code": "xxx"}, {"code": "buchholz"}]}
        )

        # 'points' (implicito), criterio desconhecido e duplicata sao descartados.
        self.assertEqual(payload["tiebreak_sequence"], serialize_tiebreak_sequence([{"code": "buchholz", "params": {}}]))
        self.assertEqual(payload["team_tiebreak_sequence"], "[]")

    def test_fide_report_excludes_byes_and_walkovers(self) -> None:
        from src.services.fide_rating import build_fide_report_rows

        rows = build_fide_report_rows(
            [self._fide_player(1, 2000), self._fide_player(2, 1800)],
            [
                {"white_player_id": 1, "black_player_id": 2, "result": "1F-0F", "is_bye": 0},  # WO: nao conta
                {"white_player_id": 1, "black_player_id": None, "result": "BYE", "is_bye": 1},  # bye: nao conta
            ],
            "fide",
        )
        # Nenhuma partida valida para rating → ninguem entra no relatorio.
        self.assertEqual(rows, [])

    def test_scheveningen_requires_even_field(self) -> None:
        from src.services.pairing import scheveningen_pairings

        players = [{"id": index, "name": f"P{index}", "rating": 2000 - index} for index in range(5)]
        with self.assertRaisesRegex(AppError, "par"):
            scheveningen_pairings(players, 1, {})

    def test_scheveningen_pairs_every_cross_group_match(self) -> None:
        ids = self._create_players(6)  # A = 3 de maior rating, B = 3 de menor
        group_a, group_b = set(ids[:3]), set(ids[3:])
        self._set_individual_pairing_method("scheveningen")

        seen: set[tuple[int, int]] = set()
        for _round in range(3):  # 3 jogadores por grupo => 3 rodadas
            round_data = self.service.generate_next_round(self.tournament_id)
            round_id = int(round_data["id"])
            pairings = self.db.get_pairings_for_round(round_id)
            self.assertEqual(len(pairings), 3)
            for pairing in pairings:
                white, black = int(pairing["white_player_id"]), int(pairing["black_player_id"])
                self.assertFalse(pairing["is_bye"])
                # Cada confronto cruza os grupos (exatamente um lado em A).
                self.assertTrue((white in group_a) != (black in group_a))
                a_player = white if white in group_a else black
                b_player = black if white in group_a else white
                seen.add((a_player, b_player))
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, round_id)

        # Todos os 9 cruzamentos A×B ocorreram exatamente uma vez.
        self.assertEqual(seen, {(a, b) for a in group_a for b in group_b})

    def test_scheveningen_uses_manual_groups(self) -> None:
        ids = self._create_players(4)  # ratings 2000,1950,1900,1850
        # Grupos manuais que NAO sao as metades por ranking: A = mais forte + mais fraco.
        self.db.set_player_scheveningen_group(ids[0], "A")
        self.db.set_player_scheveningen_group(ids[3], "A")
        self.db.set_player_scheveningen_group(ids[1], "B")
        self.db.set_player_scheveningen_group(ids[2], "B")
        self._set_individual_pairing_method("scheveningen")
        group_a, group_b = {ids[0], ids[3]}, {ids[1], ids[2]}

        seen: set[tuple[int, int]] = set()
        for _round in range(2):
            round_data = self.service.generate_next_round(self.tournament_id)
            round_id = int(round_data["id"])
            for pairing in self.db.get_pairings_for_round(round_id):
                white, black = int(pairing["white_player_id"]), int(pairing["black_player_id"])
                self.assertTrue((white in group_a) != (black in group_a))
                a_player = white if white in group_a else black
                b_player = black if white in group_a else white
                seen.add((a_player, b_player))
                self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
            self.service.close_round(self.tournament_id, round_id)

        self.assertEqual(seen, {(a, b) for a in group_a for b in group_b})

    def test_scheveningen_manual_groups_must_match_size(self) -> None:
        from src.services.pairing import scheveningen_pairings

        players = [
            {"id": 1, "name": "A1", "rating": 2000, "scheveningen_group": "A"},
            {"id": 2, "name": "A2", "rating": 1900, "scheveningen_group": "A"},
            {"id": 3, "name": "B1", "rating": 1800, "scheveningen_group": "B"},
        ]
        with self.assertRaisesRegex(AppError, "mesmo numero"):
            scheveningen_pairings(players, 1, {})

    def test_classic_acceleration_bonus_boundaries(self) -> None:
        from src.services.pairing import classic_acceleration_bonus

        # 8 jogadores: metade superior = ranks 1..4.
        self.assertEqual(classic_acceleration_bonus(1, 8, 1), 1.0)
        self.assertEqual(classic_acceleration_bonus(4, 8, 2), 1.0)
        self.assertEqual(classic_acceleration_bonus(5, 8, 1), 0.0)
        # Fora das rodadas 1 e 2 não há bônus, mesmo para o topo.
        self.assertEqual(classic_acceleration_bonus(1, 8, 3), 0.0)
        # 7 jogadores: piso de N/2 = 3 (ranks 1..3).
        self.assertEqual(classic_acceleration_bonus(3, 7, 1), 1.0)
        self.assertEqual(classic_acceleration_bonus(4, 7, 1), 0.0)
        # start_rank inválido não recebe bônus.
        self.assertEqual(classic_acceleration_bonus(0, 8, 1), 0.0)

    def test_accelerated_standings_adds_bonus_only_to_top_half(self) -> None:
        from src.services.pairing import accelerated_standings

        standings = {pid: {"points": 0.0} for pid in range(1, 5)}
        seeding = [1, 2, 3, 4]

        # Método não acelerado devolve o standings original (sem cópia).
        self.assertIs(accelerated_standings(standings, seeding, 2, "none"), standings)

        effective = accelerated_standings(standings, seeding, 2, "accelerated")
        self.assertEqual(effective[1]["points"], 1.0)
        self.assertEqual(effective[2]["points"], 1.0)
        self.assertEqual(effective[3]["points"], 0.0)
        self.assertEqual(effective[4]["points"], 0.0)
        # O standings real permanece intacto.
        self.assertEqual(standings[1]["points"], 0.0)
        # Rodada 3 não recebe bônus.
        round3 = accelerated_standings(standings, seeding, 3, "accelerated")
        self.assertEqual(round3[1]["points"], 0.0)

    def test_classic_acceleration_reshapes_round_two_score_groups(self) -> None:
        self._create_players(8)
        players = self.db.list_players(self.tournament_id, active_only=True)

        def pair_set(pairings: list[dict[str, Any]]) -> set[frozenset[int]]:
            return {
                frozenset({int(p["white_player_id"]), int(p["black_player_id"])})
                for p in pairings
                if p.get("black_player_id") is not None
            }

        seeding = [
            int(p["id"])
            for p in sorted(players, key=lambda p: -int(p.get("rating") or 0))
        ]

        # Sem aceleração: todos no mesmo grupo (0 pontos) → topo vs base.
        self.db.save_tournament_settings(self.tournament_id, {"acceleration_method": "none"})
        plain = pair_set(self.service._swiss_pairings(self.tournament_id, players, 2))
        self.assertIn(frozenset({seeding[0], seeding[4]}), plain)

        # Com aceleração clássica: top-metade (seeds 1..4) ganha +1 fictício,
        # formando dois grupos de pontuação. Seed 1 pareia dentro do topo (seed 3),
        # não cruza para a base (seed 5).
        self.db.save_tournament_settings(
            self.tournament_id, {"acceleration_method": "accelerated"}
        )
        accel = pair_set(self.service._swiss_pairings(self.tournament_id, players, 2))
        self.assertIn(frozenset({seeding[0], seeding[2]}), accel)
        self.assertNotIn(frozenset({seeding[0], seeding[4]}), accel)

    def test_acceleration_seeding_respects_initial_order(self) -> None:
        # Regressão: o seeding que alimenta a aceleração no Suíço deve seguir a
        # MESMA ordem inicial da R1 (initial_order), não o rating puro. Aqui o
        # national_rating define o topo {A,B,C,D}, enquanto o rating puro elegeria
        # {A,B,E,F}; com o bug, a metade superior por ordem nacional ficaria
        # espalhada entre os dois grupos de pontuação e cruzaria para a base.
        self.db.save_tournament_settings(
            self.tournament_id,
            {"initial_order": "national_rating", "acceleration_method": "accelerated"},
        )
        # (rotulo, national, rating): national desc = A..H; rating desc = A,B,E,F,C,D,G,H.
        specs = [
            ("A", 2400, 1080),
            ("B", 2300, 1070),
            ("C", 2200, 1040),
            ("D", 2100, 1030),
            ("E", 2000, 1060),
            ("F", 1900, 1050),
            ("G", 1800, 1020),
            ("H", 1700, 1010),
        ]
        ids = {
            label: self.db.create_player(
                self.tournament_id,
                name=label,
                rating=rating,
                national_rating=national,
                international_rating=0,
            )
            for label, national, rating in specs
        }

        players = self.db.list_players(self.tournament_id, active_only=True)
        pairings = self.service._swiss_pairings(self.tournament_id, players, 2)
        pairs = {
            frozenset({int(p["white_player_id"]), int(p["black_player_id"])})
            for p in pairings
            if p.get("black_player_id") is not None
        }

        top = {ids[label] for label in ("A", "B", "C", "D")}
        crossing = [pair for pair in pairs if len(pair & top) == 1]
        self.assertEqual(crossing, [], f"aceleracao ignorou initial_order: {crossing}")
        # Topo por ordem nacional pareia S1 x S2: A (1o) com C (3o), nunca com a base.
        self.assertIn(frozenset({ids["A"], ids["C"]}), pairs)
        self.assertNotIn(frozenset({ids["A"], ids["E"]}), pairs)

    def test_swiss_avoids_avoidable_opponent_repeat(self) -> None:
        # Regressao confirmada contra o JaVaFo (motor FIDE oficial): com 14
        # jogadores e o favorito vencendo, na R6 o pareamento guloso por bracket
        # repetia um par do fundo (J13xJ14, ja jogados na R3) mesmo existindo um
        # pareamento sem repeticao. A salvaguarda global deve elimina-la
        # (regra FIDE C.04.1.b: nao repetir adversario).
        tid = self.db.create_tournament("Anti-repeticao", rounds_count=7)
        rating_by_id = {}
        for i in range(14):
            pid = self.db.create_player(tid, name=f"J{i + 1:02d}", rating=2000 - i * 25)
            rating_by_id[pid] = 2000 - i * 25

        played: set = set()
        for _ in range(5):
            rd = self.service.generate_next_round(tid)
            for p in self.db.get_pairings_for_round(int(rd["id"])):
                white, black = p.get("white_player_id"), p.get("black_player_id")
                if black is None:
                    continue
                played.add(frozenset({white, black}))
                result = "1-0" if rating_by_id[white] >= rating_by_id[black] else "0-1"
                self.service.update_result(tid, int(p["id"]), result)
            self.service.close_round(tid, int(rd["id"]))

        rd6 = self.service.generate_next_round(tid)
        repeats = [
            (p["white_player_id"], p["black_player_id"])
            for p in self.db.get_pairings_for_round(int(rd6["id"]))
            if p.get("black_player_id") is not None
            and frozenset({p["white_player_id"], p["black_player_id"]}) in played
        ]
        self.assertEqual(repeats, [], f"repeticao de adversario evitavel na R6: {repeats}")

    def test_swiss_avoids_avoidable_hard_color_violations_in_bottom_boards(self) -> None:
        # Regressao comparada contra o JaVaFo/Swiss-Manager: com 10 jogadores e
        # favoritos vencendo, a R5 antiga mantinha grupos de pontuacao no fundo
        # mas dava saldo de cor +/-3 e terceira cor igual evitaveis.
        tid = self.db.create_tournament("Cores no fundo", rounds_count=7)
        rating_by_id = {
            self.db.create_player(tid, name=f"J{i + 1:02d}", rating=2400 - i * 10): 2400 - i * 10
            for i in range(10)
        }

        for _ in range(4):
            rd = self.service.generate_next_round(tid)
            for p in self.db.get_pairings_for_round(int(rd["id"])):
                white, black = p.get("white_player_id"), p.get("black_player_id")
                if black is None:
                    continue
                result = "1-0" if rating_by_id[white] >= rating_by_id[black] else "0-1"
                self.service.update_result(tid, int(p["id"]), result)
            self.service.close_round(tid, int(rd["id"]))

        histories = self.service._color_histories(tid)
        rd5 = self.service.generate_next_round(tid)
        violations = self._hard_color_violations(
            self.db.get_pairings_for_round(int(rd5["id"])), histories
        )

        self.assertEqual([], violations)

    def test_swiss_avoids_avoidable_color_third_repeat_after_many_floats(self) -> None:
        # Mesmo padrao em campo maior: na R6 de 14 jogadores, o fundo da tabela
        # antigo podia produzir terceira cor igual apesar de haver pareamento
        # global sem essa violacao.
        tid = self.db.create_tournament("Cores apos floats", rounds_count=7)
        rating_by_id = {
            self.db.create_player(tid, name=f"J{i + 1:02d}", rating=2400 - i * 10): 2400 - i * 10
            for i in range(14)
        }

        for _ in range(5):
            rd = self.service.generate_next_round(tid)
            for p in self.db.get_pairings_for_round(int(rd["id"])):
                white, black = p.get("white_player_id"), p.get("black_player_id")
                if black is None:
                    continue
                result = "1-0" if rating_by_id[white] >= rating_by_id[black] else "0-1"
                self.service.update_result(tid, int(p["id"]), result)
            self.service.close_round(tid, int(rd["id"]))

        histories = self.service._color_histories(tid)
        rd6 = self.service.generate_next_round(tid)
        violations = self._hard_color_violations(
            self.db.get_pairings_for_round(int(rd6["id"])), histories
        )

        self.assertEqual([], violations)

    def test_swiss_bye_tiebreak_avoids_avoidable_color_violation(self) -> None:
        # Regressao achada por stress: com 7 jogadores, a escolha padrao do bye
        # entre jogadores empatados no menor score deixava o restante sem
        # pareamento de cor limpo. O desempate deve considerar a qualidade do
        # pareamento restante sem dar bye a jogador de score superior.
        tid = self.db.create_tournament("Bye desempata cor", rounds_count=7)
        for index, rating in enumerate([2402, 2391, 2383, 2377, 2371, 2365, 2359], start=1):
            self.db.create_player(tid, name=f"J{index:02d}", rating=rating)

        for round_number in range(1, 8):
            histories = self.service._color_histories(tid)
            rd = self.service.generate_next_round(tid)
            pairings = self.db.get_pairings_for_round(int(rd["id"]))
            violations = self._hard_color_violations(pairings, histories)
            self.assertEqual([], violations, f"violacao evitavel na rodada {round_number}: {violations}")

            for pairing in pairings:
                if pairing.get("is_bye"):
                    continue
                result = ("1-0", "0-1", "1/2-1/2")[
                    (round_number + int(pairing["board_number"])) % 3
                ]
                self.service.update_result(tid, int(pairing["id"]), result)
            self.service.close_round(tid, int(rd["id"]))

    def test_bbp_dutch_2025_c5_fixture_matches_reference(self) -> None:
        self.assertEqual(
            self._bbp_fixture_next_pairs("dutch_2025_C5"),
            self._bbp_expected_pairs("dutch_2025_C5"),
        )

    def test_bbp_dutch_2025_c9_fixture_matches_reference(self) -> None:
        self.assertEqual(
            self._bbp_fixture_next_pairs("dutch_2025_C9"),
            self._bbp_expected_pairs("dutch_2025_C9"),
        )

    def test_bbp_issue_7_large_fixture_generates_valid_pairing(self) -> None:
        summary = self._bbp_fixture_next_summary("issue_7")

        self.assertEqual(30, len(summary["pairs"]))
        self.assertEqual([], summary["repeats"])
        self.assertEqual([], summary["hard_colors"])
        self.assertNotEqual(summary["pairs"], self._bbp_expected_pairs("issue_7"))

    def test_swiss_global_swap_reduces_hard_color_violations_above_exhaustive_limit(self) -> None:
        # Acima de 16 jogadores nao usamos otimo global completo; a salvaguarda
        # gulosa + trocas locais precisa cobrir casos grandes em que uma troca
        # 2-a-2 ainda nao basta. Este cenario de 46 jogadores exigiu remalha de
        # 4 mesas para eliminar a violacao restante no fundo.
        tid = self.db.create_tournament("Cores campo grande", rounds_count=7)
        rating_by_id = {
            self.db.create_player(tid, name=f"J{i + 1:02d}", rating=2400 - i * 10): 2400 - i * 10
            for i in range(46)
        }

        for round_number in range(1, 8):
            histories = self.service._color_histories(tid)
            played = self.service._played_pairs(tid)
            rd = self.service.generate_next_round(tid)
            pairings = self.db.get_pairings_for_round(int(rd["id"]))
            repeats = [
                (pairing["white_player_id"], pairing["black_player_id"])
                for pairing in pairings
                if pairing.get("black_player_id") is not None
                and frozenset({pairing["white_player_id"], pairing["black_player_id"]}) in played
            ]
            violations = self._hard_color_violations(pairings, histories)
            self.assertEqual([], repeats, f"repeticao evitavel na rodada {round_number}: {repeats}")
            self.assertEqual([], violations, f"violacao evitavel na rodada {round_number}: {violations}")

            for pairing in pairings:
                white, black = pairing.get("white_player_id"), pairing.get("black_player_id")
                if black is None:
                    continue
                result = "1-0" if rating_by_id[white] >= rating_by_id[black] else "0-1"
                self.service.update_result(tid, int(pairing["id"]), result)
            self.service.close_round(tid, int(rd["id"]))

    def _bbp_fixture_next_pairs(self, case_name: str) -> list[tuple[int, int]]:
        return list(self._bbp_fixture_next_summary(case_name)["pairs"])

    def _bbp_fixture_next_summary(self, case_name: str) -> dict[str, Any]:
        from src.services.trf_import import build_trf_rounds, parse_trf

        fixture_dir = Path(__file__).resolve().parents[1] / "bbpPairings-6.0.0" / "test" / "tests"
        parsed = parse_trf((fixture_dir / f"{case_name}.input").read_text(encoding="utf-8"))
        identity = {int(player["start_rank"]): int(player["start_rank"]) for player in parsed["players"]}
        played_rounds = max((number for number, _pairings in build_trf_rounds(parsed["players"], identity)), default=0)
        target_round = played_rounds + 1

        tournament_id = self.db.create_tournament(f"BBP {case_name}", rounds_count=max(3, target_round))
        rank_to_id: dict[int, int] = {}
        rank_by_id: dict[int, int] = {}
        for player in parsed["players"]:
            rank = int(player["start_rank"])
            player_id = self.db.create_player(
                tournament_id,
                name=str(player["name"]),
                rating=int(player["rating"] or 0),
            )
            rank_to_id[rank] = player_id
            rank_by_id[player_id] = rank

        pairings_by_round: dict[int, list[dict[str, Any]]] = {
            number: list(pairings)
            for number, pairings in build_trf_rounds(parsed["players"], rank_to_id)
            if number < target_round
        }
        for player in parsed["players"]:
            player_id = rank_to_id[int(player["start_rank"])]
            for round_number, cell in enumerate(player["rounds"], start=1):
                code = self._bbp_nonpairing_result(cell)
                if not code:
                    continue
                if round_number < target_round:
                    round_pairings = pairings_by_round.setdefault(round_number, [])
                    if not self._bbp_round_has_player(round_pairings, player_id):
                        round_pairings.append(
                            {
                                "board_number": len(round_pairings) + 1,
                                "white_player_id": player_id,
                                "black_player_id": None,
                                "result": code,
                                "is_bye": 1,
                            }
                        )
                elif round_number == target_round:
                    self.db.add_requested_bye(tournament_id, player_id, target_round, code)

        for round_number in sorted(pairings_by_round):
            round_pairings = pairings_by_round[round_number]
            for board_number, pairing in enumerate(round_pairings, start=1):
                pairing["board_number"] = board_number
            round_id = self.db.create_round_with_pairings(tournament_id, round_number, round_pairings)
            self.db.close_round(round_id)

        histories = self.service._color_histories(tournament_id)
        played_pairs = self.service._played_pairs(tournament_id)
        round_data = self.service.generate_next_round(tournament_id)
        pairs: list[tuple[int, int]] = []
        repeats: list[tuple[int, int]] = []
        hard_colors: list[tuple[int, str, str, int]] = []
        for pairing in self.db.get_pairings_for_round(int(round_data["id"])):
            if pairing.get("is_bye") and str(pairing.get("result") or "").strip().upper() in {"F", "H", "Z"}:
                continue
            white_id = int(pairing["white_player_id"])
            white_rank = rank_by_id[white_id]
            black_id = pairing.get("black_player_id")
            black_id = int(black_id) if black_id else 0
            black_rank = rank_by_id[black_id] if black_id else 0
            pairs.append((white_rank, black_rank))
            if black_id and frozenset((white_id, black_id)) in played_pairs:
                repeats.append((white_rank, black_rank))
            if black_id:
                hard_colors.extend(self._hard_color_violations([pairing], histories))
        return {
            "pairs": pairs,
            "repeats": repeats,
            "hard_colors": [
                (rank_by_id[player_id], color, history, balance)
                for player_id, color, history, balance in hard_colors
            ],
        }

    @staticmethod
    def _bbp_nonpairing_result(cell: dict[str, str]) -> str:
        if str(cell.get("opponent_rank") or "").strip() != "0000":
            return ""
        if str(cell.get("color") or "").strip() != "-":
            return ""
        code = str(cell.get("result") or "").strip().upper()
        return code if code in {"F", "H", "Z"} else ""

    @staticmethod
    def _bbp_round_has_player(pairings: list[dict[str, Any]], player_id: int) -> bool:
        return any(
            int(pairing.get("white_player_id") or 0) == player_id
            or int(pairing.get("black_player_id") or 0) == player_id
            for pairing in pairings
        )

    @staticmethod
    def _bbp_expected_pairs(case_name: str) -> list[tuple[int, int]]:
        fixture_dir = Path(__file__).resolve().parents[1] / "bbpPairings-6.0.0" / "test" / "tests"
        lines = (fixture_dir / f"{case_name}.output.expected").read_text(encoding="utf-8").splitlines()
        return [tuple(map(int, line.split())) for line in lines[1:]]

    @staticmethod
    def _hard_color_violations(
        pairings: list[dict[str, Any]],
        histories: dict[int, list[str]],
    ) -> list[tuple[int, str, str, int]]:
        violations = []
        for pairing in pairings:
            if pairing.get("is_bye") or pairing.get("black_player_id") is None:
                continue
            assignments = (
                (int(pairing["white_player_id"]), "W"),
                (int(pairing["black_player_id"]), "B"),
            )
            for player_id, color in assignments:
                history = [item for item in histories.get(player_id, []) if item in {"W", "B"}]
                color_balance = history.count("W") - history.count("B")
                color_balance += 1 if color == "W" else -1
                if abs(color_balance) > 2 or history[-2:] == [color, color]:
                    violations.append((player_id, color, "".join(history), color_balance))
        return violations

    def test_custom_acceleration_applies_configured_params(self) -> None:
        from src.services.pairing import accelerated_standings, acceleration_spec

        spec = acceleration_spec("custom:rounds=3;bonus=2.0;upper=0.25")
        self.assertEqual(spec["scheme"], "custom")
        self.assertEqual(spec["round_count"], 3)
        self.assertEqual(spec["bonus"], 2.0)
        self.assertEqual(spec["upper_fraction"], 0.25)

        standings = {pid: {"points": 0.0} for pid in range(1, 9)}
        seeding = list(range(1, 9))
        # upper=0.25 de 8 → só ranks 1..2; rodada 3 ainda dentro de round_count=3.
        effective = accelerated_standings(
            standings, seeding, 3, "custom:rounds=3;bonus=2.0;upper=0.25"
        )
        self.assertEqual(effective[1]["points"], 2.0)
        self.assertEqual(effective[2]["points"], 2.0)
        self.assertEqual(effective[3]["points"], 0.0)
        # Rodada 4 fora da janela.
        round4 = accelerated_standings(
            standings, seeding, 4, "custom:rounds=3;bonus=2.0;upper=0.25"
        )
        self.assertEqual(round4[1]["points"], 0.0)

    def test_custom_acceleration_ignores_nonpositive_params(self) -> None:
        from src.services.federation_exporters import TRF25Exporter
        from src.services.pairing import acceleration_bonus, acceleration_spec

        # Bônus zero: sem efeito no motor.
        spec_zero = acceleration_spec("custom:rounds=2;bonus=0;upper=0.5")
        self.assertEqual(acceleration_bonus(1, 8, 1, spec_zero), 0.0)
        # Bônus negativo nunca "desacelera".
        spec_neg = acceleration_spec("custom:rounds=2;bonus=-1;upper=0.5")
        self.assertEqual(acceleration_bonus(1, 8, 1, spec_neg), 0.0)
        # Zero rodadas: sem efeito.
        spec_no_round = acceleration_spec("custom:rounds=0;bonus=1;upper=0.5")
        self.assertEqual(acceleration_bonus(1, 8, 1, spec_no_round), 0.0)

        self._create_players(8)
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "noop.trf"
        for method in (
            "custom:rounds=2;bonus=0;upper=0.5",
            "custom:rounds=0;bonus=1;upper=0.5",
            "custom:rounds=2;bonus=1;upper=0",
        ):
            self.db.save_tournament_settings(self.tournament_id, {"acceleration_method": method})
            exporter.export(self.tournament_id, output_path)
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertFalse(
                [line for line in lines if line.startswith("250 ")],
                msg=f"250 indevido para {method}",
            )

    def test_baku_does_not_apply_bonus_or_emit_250(self) -> None:
        from src.services.federation_exporters import TRF25Exporter
        from src.services.federation_exporters.trf25 import BAKU_NOT_IMPLEMENTED
        from src.services.pairing import accelerated_standings

        # Motor: Baku não soma bônus (sem fórmula oficial).
        standings = {pid: {"points": 0.0} for pid in range(1, 5)}
        self.assertIs(accelerated_standings(standings, [1, 2, 3, 4], 2, "baku"), standings)

        self._create_players(8)
        self.db.save_tournament_settings(self.tournament_id, {"acceleration_method": "baku"})
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "baku.trf"
        warnings = exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        # Nenhum 250 e nenhum sufixo _BAKU no registro 192.
        self.assertFalse([line for line in lines if line.startswith("250 ")])
        type_line = next(line for line in lines if line.startswith("192 "))
        self.assertNotIn("_BAKU", type_line)
        # Aviso ao árbitro de que Baku não está implementado.
        self.assertIn(BAKU_NOT_IMPLEMENTED, warnings)

    def test_scoresheets_pdf_skips_bye_and_includes_player_data(self) -> None:
        self.db.create_player(
            self.tournament_id,
            name="Ana Silva",
            rating=1810,
            club="Clube A",
            fide_id="1234567",
        )
        self.db.create_player(
            self.tournament_id,
            name="Bruno Souza",
            rating=1720,
            club="Clube B",
            cbx_id="7654",
        )
        self.db.create_player(self.tournament_id, name="Carla Lima", rating=1650, club="Clube C")
        round_data = self.service.generate_next_round(self.tournament_id)
        output_path = Path(self.temp_dir.name) / "sumulas.pdf"

        self.export_service.export_scoresheets(int(round_data["id"]), output_path)

        from pypdf import PdfReader

        reader = PdfReader(output_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertEqual(output_path.read_bytes()[:4], b"%PDF")
        self.assertEqual(1, len(reader.pages))
        self.assertIn("Resultado:", text)
        self.assertIn("Assinatura das brancas", text)
        self.assertTrue("Ana Silva" in text or "Bruno Souza" in text or "Carla Lima" in text)

    def test_pairings_wall_pdf_exports_60_tables_under_five_seconds(self) -> None:
        for index in range(120):
            self.db.create_player(
                self.tournament_id,
                name=f"Jogador {index + 1:03d}",
                rating=2400 - index,
            )
        round_data = self.service.generate_next_round(self.tournament_id)
        output_path = Path(self.temp_dir.name) / "mural_60_mesas.pdf"

        started_at = perf_counter()
        self.export_service.export_pairings(int(round_data["id"]), output_path)
        elapsed = perf_counter() - started_at

        from pypdf import PdfReader

        self.assertEqual(4, len(PdfReader(output_path).pages))
        self.assertLess(elapsed, 5.0)

    def test_individual_crosstable_round_robin_fixture_and_exports(self) -> None:
        player_ids = [
            self.db.create_player(self.tournament_id, name=f"Jogador {index}", rating=2100 - index * 50)
            for index in range(1, 7)
        ]
        schedules = [
            [(0, 5), (1, 4), (2, 3)],
            [(5, 3), (4, 2), (0, 1)],
            [(1, 5), (2, 0), (3, 4)],
            [(5, 4), (0, 3), (1, 2)],
            [(2, 5), (3, 1), (4, 0)],
        ]
        for round_number, schedule in enumerate(schedules, start=1):
            round_id = self.db.create_round_with_pairings(
                self.tournament_id,
                round_number,
                [
                    {
                        "board_number": board_number,
                        "white_player_id": player_ids[white],
                        "black_player_id": player_ids[black],
                        "result": "1-0",
                    }
                    for board_number, (white, black) in enumerate(schedule, start=1)
                ],
            )
            self.db.close_round(round_id)

        payload = self.service.crosstable(self.tournament_id)
        rows_by_player = {int(row["player_id"]): row for row in payload["rows"]}
        first = rows_by_player[player_ids[0]]

        self.assertEqual([1, 2, 3, 4, 5], payload["rounds"])
        self.assertEqual(6, len(payload["rows"]))
        self.assertEqual("6B 1-0", first["rounds"][1]["label"])
        self.assertEqual("2B 1-0", first["rounds"][2]["label"])
        self.assertEqual("3P 1-0", first["rounds"][3]["label"])
        self.assertAlmostEqual(15.0, sum(float(row["points"]) for row in payload["rows"]))

        for extension in ("csv", "xlsx", "pdf", "html"):
            output_path = Path(self.temp_dir.name) / f"tabela_cruzada.{extension}"
            self.export_service.export_crosstable(self.tournament_id, output_path)
            self.assertTrue(output_path.exists())
        csv_content = (Path(self.temp_dir.name) / "tabela_cruzada.csv").read_text(encoding="utf-8-sig")
        html_content = (Path(self.temp_dir.name) / "tabela_cruzada.html").read_text(encoding="utf-8")
        self.assertIn("R5", csv_content)
        self.assertIn("6B 1-0", csv_content)
        self.assertIn("Tabela cruzada", html_content)
        self.assertIn("B = brancas", html_content)

    def test_individual_crosstable_distinguishes_bye_wo_and_absence(self) -> None:
        player_ids = [
            self.db.create_player(self.tournament_id, name=f"Jogador {index}", rating=1800 - index)
            for index in range(1, 5)
        ]
        round_id = self.db.create_round_with_pairings(
            self.tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": player_ids[0],
                    "black_player_id": player_ids[1],
                    "result": "1F-0F",
                },
                {
                    "board_number": 2,
                    "white_player_id": player_ids[2],
                    "black_player_id": None,
                    "result": "H",
                    "is_bye": 1,
                },
            ],
        )
        self.db.close_round(round_id)

        payload = self.service.crosstable(self.tournament_id)
        rows_by_player = {int(row["player_id"]): row for row in payload["rows"]}
        self.assertEqual("1F-0F", rows_by_player[player_ids[0]]["rounds"][1]["result"])
        self.assertEqual("bye", rows_by_player[player_ids[2]]["rounds"][1]["kind"])
        self.assertEqual("BYE H", rows_by_player[player_ids[2]]["rounds"][1]["label"])
        self.assertEqual("absent", rows_by_player[player_ids[3]]["rounds"][1]["kind"])
        self.assertEqual("-", rows_by_player[player_ids[3]]["rounds"][1]["label"])

if __name__ == "__main__":
    unittest.main()
