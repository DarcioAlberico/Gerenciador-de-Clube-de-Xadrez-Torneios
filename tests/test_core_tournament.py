from __future__ import annotations

import unittest

from src.core.services import (
    AppError,
    TournamentService,
)
from tests.support.core_service_base import CoreServiceTestCase


class TournamentSetupTest(CoreServiceTestCase):
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
                "rating_fee_fide": "2.50",
                "rating_fee_cbx": "3.75",
                "rating_fee_lbx": "1.25",
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
        self.assertEqual(settings["rating_fee_fide"], 2.5)
        self.assertEqual(settings["rating_fee_cbx"], 3.75)
        self.assertEqual(settings["rating_fee_lbx"], 1.25)
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

    def test_change_tournament_type_blocked_after_first_round(self) -> None:
        self._create_players(4)
        self.tournament_service.change_tournament_type(self.tournament_id, "round_robin")
        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(settings["pairing_method"], "round_robin")

        self.service.generate_next_round(self.tournament_id)
        with self.assertRaisesRegex(AppError, "primeira rodada"):
            self.tournament_service.change_tournament_type(self.tournament_id, "swiss")

    def test_split_tournament_partitions_by_ranking(self) -> None:
        self._create_players(6)  # ratings 2000..1750 decrescentes
        children = self.tournament_service.split_tournament(self.tournament_id, 2)
        self.assertEqual(len(children), 2)
        for child_id in children:
            self.assertEqual(
                self.db.get_tournament(child_id)["parent_tournament_id"], self.tournament_id
            )
        group_a = self.db.list_players(children[0], active_only=False)
        group_b = self.db.list_players(children[1], active_only=False)
        self.assertEqual(len(group_a), 3)
        self.assertEqual(len(group_b), 3)
        # Grupo A reune os tres maiores ratings (divisao por ranking).
        self.assertGreaterEqual(
            min(int(player["rating"]) for player in group_a),
            max(int(player["rating"]) for player in group_b),
        )

    def test_split_tournament_requires_clean_state(self) -> None:
        self._create_players(4)
        self.service.generate_next_round(self.tournament_id)
        with self.assertRaisesRegex(AppError, "antes de gerar"):
            self.tournament_service.split_tournament(self.tournament_id, 2)

    def test_split_tournament_rejects_insufficient_players(self) -> None:
        self._create_players(2)
        with self.assertRaisesRegex(AppError, "insuficientes"):
            self.tournament_service.split_tournament(self.tournament_id, 3)

    def test_save_profile_blocks_pairing_change_after_round(self) -> None:
        self._create_players(4)
        self.service.generate_next_round(self.tournament_id)
        with self.assertRaisesRegex(AppError, "primeira rodada"):
            self.tournament_service.save_profile(
                self.tournament_id,
                {
                    "name": "Torneio teste",
                    "scope": "standalone",
                    "competition_type": "individual",
                    "rounds_count": "5",
                    "bye_points": "1",
                },
                {"pairing_method": "round_robin"},
                [],
            )

if __name__ == "__main__":
    unittest.main()
