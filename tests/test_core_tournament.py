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

        # ARB-01: a rodada fechada agora recusa por DOIS motivos independentes —
        # falta de motivo e falta de permissao. Este teste cobra o segundo, entao
        # o motivo vem preenchido e a recusa que sobra e a da permissao.
        with self.assertRaises(AppError):
            self.service.update_result(
                self.tournament_id, pairing["id"], "0-1", "Sumula trocada pelo arbitro"
            )

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
        self.service.update_result(
            self.tournament_id, pairing["id"], "0-1", "Sumula trocada pelo arbitro"
        )

        self.assertEqual(self.db.get_pairing(pairing["id"])["result"], "0-1")

    def test_closed_result_edit_requires_a_reason(self) -> None:
        """ARB-01: permissao nao dispensa o registro do porque.

        O par deste teste com o de cima: la a permissao falta e o motivo esta; aqui
        a permissao esta (interruptor global ligado) e o motivo falta.
        """
        self._create_players(2)
        first_round = self.service.generate_next_round(self.tournament_id)
        pairing = self.db.get_pairings_for_round(first_round["id"])[0]
        self.db.update_pairing_result(pairing["id"], "1-0")
        self.service.close_round(self.tournament_id, first_round["id"])
        self.db.save_tournament_settings(self.tournament_id, {"allow_dangerous_changes": 1})

        with self.assertRaises(AppError) as erro:
            self.service.update_result(self.tournament_id, pairing["id"], "0-1")

        self.assertIn("motivo", str(erro.exception).casefold())
        self.assertEqual("1-0", self.db.get_pairing(pairing["id"])["result"])

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

    def test_save_profile_can_reduce_rounds_with_existing_schedule_rows(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio reduzido",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {},
            [
                {"round_number": 1, "date": "2026-06-01", "time": "09:00"},
                {"round_number": 2, "date": "2026-06-01", "time": "14:00"},
                {"round_number": 3, "date": "2026-06-02", "time": "09:00"},
                {"round_number": 4, "date": "2026-06-02", "time": "14:00"},
                {"round_number": 5, "date": "2026-06-03", "time": "09:00"},
            ],
        )

        tournament = self.db.get_tournament(self.tournament_id)
        schedule = self.db.list_round_schedule(self.tournament_id)
        self.assertEqual(tournament["rounds_count"], 3)
        self.assertEqual([item["round_number"] for item in schedule], [1, 2, 3])

    def test_save_profile_cannot_reduce_rounds_below_generated_rounds(self) -> None:
        self._create_players(4)
        first_round = self.service.generate_next_round(self.tournament_id)
        self._fill_decisive_results(first_round["id"])
        self.service.close_round(self.tournament_id, first_round["id"])
        self.service.generate_next_round(self.tournament_id)

        with self.assertRaisesRegex(AppError, "rodadas geradas"):
            self.tournament_service.save_profile(
                self.tournament_id,
                {
                    "name": "Torneio reduzido",
                    "scope": "standalone",
                    "competition_type": "individual",
                    "rounds_count": "1",
                    "bye_points": "1",
                },
                {},
                [],
            )

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

    def test_save_profile_persists_pairing_method_before_first_round(self) -> None:
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

        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(settings["pairing_method"], "round_robin")

    def test_save_profile_accepts_custom_acceleration_settings(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": "5",
                "bye_points": "1",
            },
            {"acceleration_method": "custom:rounds=3;bonus=2.0;upper=0.25"},
            [],
        )

        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(settings["acceleration_method"], "custom:rounds=3;bonus=2.0;upper=0.25")

    def test_duplicate_tournament_copies_tiebreak_and_prize_settings(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "tiebreak_sequence": '[{"code":"buchholz","params":{}}]',
                "team_tiebreak_sequence": '[{"code":"game_points","params":{}}]',
                "prize_policy": "cumulative",
                "prize_tax_percent": 12.5,
            },
        )

        duplicate_id = self.tournament_service.duplicate_tournament(
            self.tournament_id,
            "Copia configurada",
        )

        settings = self.db.get_tournament_settings(duplicate_id)
        self.assertEqual(settings["tiebreak_sequence"], '[{"code":"buchholz","params":{}}]')
        self.assertEqual(settings["team_tiebreak_sequence"], '[{"code":"game_points","params":{}}]')
        self.assertEqual(settings["prize_policy"], "cumulative")
        self.assertEqual(settings["prize_tax_percent"], 12.5)

    def test_duplicate_tournament_copies_prize_rows_and_report_layouts(self) -> None:
        self.db.replace_tournament_prizes(
            self.tournament_id,
            [
                {
                    "kind": "overall",
                    "label": "Campeao",
                    "category": "",
                    "rank_from": 1,
                    "rank_to": 1,
                    "amount": 250.0,
                },
                {
                    "kind": "category",
                    "label": "Sub-12",
                    "category": "Sub-12",
                    "rank_from": 1,
                    "rank_to": 2,
                    "amount": 50.0,
                },
            ],
        )
        layout = [{"key": "name", "width": 220}, {"key": "points", "width": 60}]
        self.db.save_report_layout(self.tournament_id, "standings", layout)

        duplicate_id = self.tournament_service.duplicate_tournament(
            self.tournament_id,
            "Copia com modelo",
        )

        prizes = self.db.list_tournament_prizes(duplicate_id)
        self.assertEqual([prize["label"] for prize in prizes], ["Campeao", "Sub-12"])
        self.assertEqual(prizes[0]["amount"], 250.0)
        self.assertEqual(prizes[1]["category"], "Sub-12")
        self.assertEqual(self.db.get_report_layout_columns(duplicate_id, "standings"), layout)

    def test_partial_settings_update_preserves_existing_values(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "tiebreak_sequence": '[{"code":"buchholz","params":{}}]',
                "team_tiebreak_sequence": '[{"code":"game_points","params":{}}]',
                "prize_policy": "cumulative",
                "prize_tax_percent": 12.5,
                "allow_public_registration": 1,
                "rating_fee_fide": 2.5,
            },
        )

        self.db.save_tournament_settings(self.tournament_id, {"acceleration_method": "accelerated"})

        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(settings["acceleration_method"], "accelerated")
        self.assertEqual(settings["tiebreak_sequence"], '[{"code":"buchholz","params":{}}]')
        self.assertEqual(settings["team_tiebreak_sequence"], '[{"code":"game_points","params":{}}]')
        self.assertEqual(settings["prize_policy"], "cumulative")
        self.assertEqual(settings["prize_tax_percent"], 12.5)
        self.assertEqual(settings["allow_public_registration"], 1)
        self.assertEqual(settings["rating_fee_fide"], 2.5)

    def test_save_profile_partial_settings_preserves_existing_values(self) -> None:
        self.db.save_tournament_settings(
            self.tournament_id,
            {
                "tiebreak_sequence": '[{"code":"buchholz","params":{}}]',
                "team_tiebreak_sequence": '[{"code":"game_points","params":{}}]',
                "prize_policy": "cumulative",
                "prize_tax_percent": 12.5,
                "allow_public_registration": 1,
                "rating_fee_fide": 2.5,
            },
        )

        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio renomeado",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": "5",
                "bye_points": "1",
            },
            {},
            [],
        )

        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(settings["tiebreak_sequence"], '[{"code": "buchholz", "params": {}}]')
        self.assertEqual(settings["team_tiebreak_sequence"], '[{"code": "game_points", "params": {}}]')
        self.assertEqual(settings["prize_policy"], "cumulative")
        self.assertEqual(settings["prize_tax_percent"], 12.5)
        self.assertEqual(settings["allow_public_registration"], 1)
        self.assertEqual(settings["rating_fee_fide"], 2.5)

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

    def test_split_tournament_respects_initial_order_rating_source(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"initial_order": "national_rating"})
        self.db.create_player(
            self.tournament_id,
            name="FIDE alto",
            rating=1000,
            national_rating=1000,
            international_rating=2500,
        )
        self.db.create_player(
            self.tournament_id,
            name="Nacional 1",
            rating=1000,
            national_rating=2400,
            international_rating=0,
        )
        self.db.create_player(
            self.tournament_id,
            name="Nacional 2",
            rating=1000,
            national_rating=2300,
            international_rating=0,
        )
        self.db.create_player(
            self.tournament_id,
            name="Nacional baixo",
            rating=1000,
            national_rating=900,
            international_rating=0,
        )

        children = self.tournament_service.split_tournament(self.tournament_id, 2)

        group_a_names = {
            player["name"]
            for player in self.db.list_players(children[0], active_only=False)
        }
        self.assertEqual(group_a_names, {"Nacional 1", "Nacional 2"})

    def test_split_tournament_copies_settings_and_schedule(self) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {
                "pairing_method": "round_robin",
                "tiebreak_sequence": '[{"code":"buchholz","params":{}}]',
                "prize_policy": "cumulative",
                "prize_tax_percent": 10,
            },
            [
                {"round_number": 1, "date": "2026-07-01", "time": "09:00"},
                {"round_number": 2, "date": "2026-07-01", "time": "14:00"},
                {"round_number": 3, "date": "2026-07-02", "time": "09:00"},
            ],
        )
        self._create_players(4)

        children = self.tournament_service.split_tournament(self.tournament_id, 2)

        for child_id in children:
            settings = self.db.get_tournament_settings(child_id)
            schedule = self.db.list_round_schedule(child_id)
            self.assertEqual(settings["pairing_method"], "round_robin")
            self.assertEqual(settings["tiebreak_sequence"], '[{"code": "buchholz", "params": {}}]')
            self.assertEqual(settings["prize_policy"], "cumulative")
            self.assertEqual(settings["prize_tax_percent"], 10.0)
            self.assertEqual(schedule[0]["date"], "2026-07-01")
            self.assertEqual(schedule[1]["time"], "14:00")

    def test_split_tournament_copies_prize_rows_and_report_layouts(self) -> None:
        self.db.replace_tournament_prizes(
            self.tournament_id,
            [
                {
                    "kind": "overall",
                    "label": "Campeao",
                    "category": "",
                    "rank_from": 1,
                    "rank_to": 1,
                    "amount": 250.0,
                },
            ],
        )
        layout = [{"key": "name", "width": 220}, {"key": "points", "width": 60}]
        self.db.save_report_layout(self.tournament_id, "standings", layout)
        self._create_players(4)

        children = self.tournament_service.split_tournament(self.tournament_id, 2)

        for child_id in children:
            prizes = self.db.list_tournament_prizes(child_id)
            self.assertEqual([prize["label"] for prize in prizes], ["Campeao"])
            self.assertEqual(prizes[0]["amount"], 250.0)
            self.assertEqual(self.db.get_report_layout_columns(child_id, "standings"), layout)

    def test_split_tournament_preserves_player_status_and_starting_points(self) -> None:
        self._create_players(3)
        withdrawn_id = self.db.create_player(
            self.tournament_id,
            name="Jogador desistente",
            rating=1500,
            club="Clube",
            category="Absoluto",
            player_status="withdrawn",
            starting_points=0.5,
        )
        self.assertEqual(self.db.get_player(withdrawn_id)["active"], 0)

        children = self.tournament_service.split_tournament(self.tournament_id, 2)

        copied_players = [
            player
            for child_id in children
            for player in self.db.list_players(child_id, active_only=False)
            if player["name"] == "Jogador desistente"
        ]
        self.assertEqual(len(copied_players), 1)
        self.assertEqual(copied_players[0]["player_status"], "withdrawn")
        self.assertEqual(copied_players[0]["active"], 0)
        self.assertEqual(copied_players[0]["starting_points"], 0.5)

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
