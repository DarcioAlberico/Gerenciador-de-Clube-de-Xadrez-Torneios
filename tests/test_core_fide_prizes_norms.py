from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from src.core import database as database_module
from src.core.database import APP_DATA_DIR_ENV_VAR
from src.core.services import (
    AppError,
)
from tests.support.core_service_base import CoreServiceTestCase


class FidePrizesNormsTest(CoreServiceTestCase):
    def test_schedule_email_normalizes_and_persists(self) -> None:
        from src.services.dashboard_service import CommunicationService

        comm = CommunicationService(self.db)
        msg_id = comm.schedule_email(
            "Assunto", "Corpo", "2026-06-01 09:30", audience_kind="all_active"
        )

        pending = comm.list_scheduled_messages(status="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], msg_id)
        self.assertEqual(pending[0]["scheduled_at"], "2026-06-01 09:30:00")

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

    def test_fide_expected_score_applies_400_rule(self) -> None:
        from src.services.fide_rating import fide_expected_score

        self.assertEqual(fide_expected_score(2000, 2000), 0.50)
        self.assertEqual(fide_expected_score(2000, 1800), 0.76)
        self.assertEqual(fide_expected_score(1800, 2000), 0.24)
        # Diferenca de 500 e tratada como 400 (regra dos 400).
        self.assertEqual(fide_expected_score(2000, 1500), 0.92)
        self.assertEqual(fide_expected_score(1500, 2000), 0.08)

    def test_fide_k_factor_rules(self) -> None:
        from src.services.fide_rating import fide_k_factor

        self.assertEqual(fide_k_factor(2500), 10)
        self.assertEqual(fide_k_factor(2000), 20)
        self.assertEqual(fide_k_factor(2000, k_override=40), 40)
        self.assertEqual(fide_k_factor(2200, birth_year=2012, tournament_year=2026), 40)  # sub-18 <2300
        self.assertEqual(fide_k_factor(2350, birth_year=2012, tournament_year=2026), 20)  # sub-18 mas >=2300

    def test_fide_report_delta_matches_manual(self) -> None:
        from src.services.fide_rating import build_fide_report_rows

        rows = build_fide_report_rows(
            [self._fide_player(1, 2000), self._fide_player(2, 1800)],
            [{"white_player_id": 1, "black_player_id": 2, "result": "1-0", "is_bye": 0}],
            "fide",
        )
        by_id = {row["player_id"]: row for row in rows}
        # We(A)=0.76, K=20, ΔA=20*(1-0.76)=4.8, Rc=2005.
        self.assertEqual(by_id[1]["we"], 0.76)
        self.assertEqual(by_id[1]["k"], 20)
        self.assertEqual(by_id[1]["delta"], 4.8)
        self.assertEqual(by_id[1]["rc"], 2005)
        # We(B)=0.24, ΔB=-4.8, Rc=1795.
        self.assertEqual(by_id[2]["delta"], -4.8)
        self.assertEqual(by_id[2]["rc"], 1795)

    def test_fide_report_400_rule_and_unrated_opponent(self) -> None:
        from src.services.fide_rating import build_fide_report_rows

        # 400: A=2000 vence C=1500 → We=0.92, n_over_400=1, Δ=1.6.
        rows = build_fide_report_rows(
            [self._fide_player(1, 2000), self._fide_player(3, 1500)],
            [{"white_player_id": 1, "black_player_id": 3, "result": "1-0", "is_bye": 0}],
            "fide",
        )
        leader = next(row for row in rows if row["player_id"] == 1)
        self.assertEqual(leader["we"], 0.92)
        self.assertEqual(leader["n_over_400"], 1)
        self.assertEqual(leader["delta"], 1.6)

        # Adversario sem rating e ignorado no calculo; jogador sem rating recebe so Rp.
        rows = build_fide_report_rows(
            [self._fide_player(1, 2000), self._fide_player(2, 1800), self._fide_player(4, 0, intl=0)],
            [
                {"white_player_id": 1, "black_player_id": 2, "result": "1-0", "is_bye": 0},
                {"white_player_id": 1, "black_player_id": 4, "result": "1-0", "is_bye": 0},
            ],
            "fide",
        )
        by_id = {row["player_id"]: row for row in rows}
        self.assertEqual(by_id[1]["games_rated"], 1)   # D (sem rating) nao conta para A
        self.assertEqual(by_id[1]["we"], 0.76)
        self.assertEqual(by_id[4]["ro"], 0)
        self.assertIsNone(by_id[4]["delta"])
        self.assertEqual(by_id[4]["rp"], 1200)         # 2000 + dp(0.0) = 2000 - 800

    def test_fide_rating_report_persists_idempotently(self) -> None:
        from src.services.rating_service import FideRatingService

        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)

        service = FideRatingService(self.db)
        service.save_report(self.tournament_id, "fide")
        service.save_report(self.tournament_id, "fide")  # recomputar nao duplica

        saved = self.db.get_fide_rating_report(self.tournament_id, "fide")
        self.assertEqual(len(saved), 4)                       # 4 jogadores, 1 partida ranqueada cada
        self.assertEqual(len({row["player_id"] for row in saved}), 4)
        self.assertTrue(all(row["games_rated"] == 1 for row in saved))

    def test_export_fide_rating_report_writes_file(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)

        path = Path(self.temp_dir.name) / "rating_fide.csv"
        self.export_service.export_fide_rating_report(self.tournament_id, path, "fide")

        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8-sig")
        self.assertIn("Variacao de rating FIDE", content)
        self.assertIn("Rp", content)
        # Exportar persiste um snapshot para auditoria/reimpressao.
        self.assertEqual(len(self.db.get_fide_rating_report(self.tournament_id, "fide")), 4)

    def test_prize_best_only_splits_ties_without_double_counting(self) -> None:
        from src.services.prizes import allocate_prizes

        result = allocate_prizes(self._prize_standings(), self._prize_rows(), "best_only", 0.0)
        by_id = {row["player_id"]: row for row in result["allocations"]}
        # Empate 1-2 divide (1000+600)/2 = 800 cada; sem somar a categoria.
        self.assertEqual(by_id[1]["gross"], 800.0)
        self.assertEqual(by_id[2]["gross"], 800.0)
        self.assertEqual(by_id[3]["gross"], 200.0)
        self.assertNotIn(4, by_id)
        self.assertEqual(result["total_gross"], 1800.0)

    def test_prize_cumulative_adds_overall_and_category(self) -> None:
        from src.services.prizes import allocate_prizes

        result = allocate_prizes(self._prize_standings(), self._prize_rows(), "cumulative", 0.0)
        by_id = {row["player_id"]: row for row in result["allocations"]}
        self.assertEqual(by_id[1]["gross"], 1100.0)  # 800 + 300
        self.assertEqual(by_id[2]["gross"], 1100.0)
        self.assertEqual(by_id[3]["gross"], 200.0)
        self.assertEqual(result["total_gross"], 2400.0)

    def test_prize_hort_policy_combines_overall_and_category(self) -> None:
        from src.services.prizes import allocate_prizes

        standings = [
            {"player_id": 1, "name": "P1", "position": 1, "points": 5.0, "category": "Y"},
            {"player_id": 2, "name": "P2", "position": 2, "points": 4.0, "category": "Y"},
            {"player_id": 3, "name": "P3", "position": 3, "points": 3.0, "category": "Y"},
            {"player_id": 10, "name": "P10", "position": 4, "points": 1.0, "category": "X"},
        ]
        prizes = [
            {"kind": "overall", "label": "4o", "rank_from": 4, "rank_to": 4, "amount": 100},
            {"kind": "category", "label": "Cat X 1o", "category": "X", "rank_from": 1, "rank_to": 1, "amount": 500},
        ]

        def gross(policy: str) -> float:
            return allocate_prizes(standings, prizes, policy, 0.0)["allocations"][0]["gross"]

        self.assertEqual(gross("best_only"), 500.0)        # max(100, 500)
        self.assertEqual(gross("cumulative"), 600.0)       # 100 + 500
        self.assertEqual(gross("hort"), 300.0)             # max(100, (100+500)/2)

    def test_prize_tax_deduction(self) -> None:
        from src.services.prizes import allocate_prizes

        result = allocate_prizes(self._prize_standings(), self._prize_rows(), "best_only", 10.0)
        by_id = {row["player_id"]: row for row in result["allocations"]}
        self.assertEqual(by_id[1]["net"], 720.0)           # 800 * 0.9
        self.assertEqual(result["total_net"], 1620.0)      # 1800 * 0.9
        self.assertEqual(result["total_tax"], 180.0)

    def test_prize_special_listed_as_manual(self) -> None:
        from src.services.prizes import allocate_prizes

        prizes = self._prize_rows() + [{"kind": "special", "label": "Melhor feminino", "amount": 150}]
        result = allocate_prizes(self._prize_standings(), prizes, "best_only", 0.0)
        self.assertEqual(len(result["manual_prizes"]), 1)
        self.assertEqual(result["manual_prizes"][0]["label"], "Melhor feminino")
        self.assertEqual(result["total_gross"], 1800.0)    # especial nao entra no total automatico

    def test_prize_service_persists_validates_and_allocates(self) -> None:
        self._create_players(4)  # categoria "Absoluto"
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)

        self.prize_service.replace_prizes(
            self.tournament_id,
            [
                {"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": 1000},
                {"kind": "overall", "label": "2o", "rank_from": 2, "rank_to": 2, "amount": 600},
            ],
        )
        # Persistencia idempotente.
        self.assertEqual(len(self.db.list_tournament_prizes(self.tournament_id)), 2)

        result = self.prize_service.allocate(self.tournament_id)
        # 2 vencedores empatados em 1.0 dividem (1000+600)/2 = 800 cada.
        self.assertEqual(result["winners"], 2)
        self.assertEqual(result["total_gross"], 1600.0)
        self.assertTrue(all(row["gross"] == 800.0 for row in result["allocations"]))

        with self.assertRaisesRegex(AppError, "categoria"):
            self.prize_service.replace_prizes(
                self.tournament_id,
                [{"kind": "category", "label": "Sub-12", "amount": 100}],  # sem categoria
            )

    def test_export_prize_report_writes_file(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)
        self.prize_service.replace_prizes(
            self.tournament_id,
            [{"kind": "overall", "label": "1o", "rank_from": 1, "rank_to": 1, "amount": 1000}],
        )

        path = Path(self.temp_dir.name) / "premiacao.csv"
        self.export_service.export_prize_report(self.tournament_id, path)
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8-sig")
        self.assertIn("Premiação por jogador", content)
        self.assertIn("Total líquido distribuido", content)

    def test_norm_verdict_meets_and_lists_missing(self) -> None:
        from src.services.norms import evaluate_norms
        from tests.support.norm_fixtures import gm_norm_opponents, weak_field_opponents

        meets = next(
            item
            for item in evaluate_norms("BRA", "M", gm_norm_opponents())
            if item.title == "GM"
        )
        self.assertTrue(meets.meets)
        self.assertEqual(meets.missing, [])

        fails = next(
            item
            for item in evaluate_norms("BRA", "M", weak_field_opponents())
            if item.title == "GM"
        )
        self.assertFalse(fails.meets)
        joined = " | ".join(fails.missing)
        self.assertIn("Performance", joined)
        self.assertIn("Federações", joined)

    def test_norm_report_identifies_gm_candidate(self) -> None:
        from src.services.fide_norms import build_norm_report

        def player(pid: int, rating: int, title: str = "", federation: str = "") -> dict:
            return {
                "id": pid, "name": f"P{pid}", "surname": "", "given_name": "",
                "international_rating": rating, "national_rating": 0, "rating": rating,
                "title": title, "federation_id": federation, "sex": "M",
            }

        players = [player(1, 2700, federation="A")]
        federations = ["A", "B", "C"]
        for opponent in range(2, 11):
            players.append(player(opponent, 2500, "GM" if opponent % 2 else "IM", federations[opponent % 3]))
        pairings = [
            {"white_player_id": 1, "black_player_id": opponent, "result": "1-0" if index < 6 else "0-1", "is_bye": 0}
            for index, opponent in enumerate(range(2, 11))
        ]

        report = build_norm_report(players, pairings, "fide")
        leader = next(item for item in report if item["player_id"] == 1)
        self.assertEqual(leader["games"], 9)
        self.assertGreaterEqual(leader["performance"], 2600)
        self.assertTrue(any(title["title"] == "GM" and title["meets"] for title in leader["titles"]))

    def test_norm_service_and_export(self) -> None:
        self._create_players(8)
        self._play_first_round(["1-0", "0-1", "1/2-1/2", "1-0"])

        report = self.norm_assistant_service.evaluate_tournament(self.tournament_id)
        self.assertTrue(report["players"])  # todos jogaram 1 partida

        path = Path(self.temp_dir.name) / "normas.csv"
        self.export_service.export_norm_report(self.tournament_id, path)
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8-sig")
        self.assertIn("Indicadores de norma por jogador", content)
        self.assertIn("NAO concede norma", content)

    def test_export_arbiter_norm_report_writes_file(self) -> None:
        self._create_players(2)
        settings = self.db.get_tournament_settings(self.tournament_id) or {}
        settings["chief_arbiter"] = "Joao Arbitro"
        settings["arbiters"] = "Maria Aux, Pedro Aux"
        settings["federation"] = "BRA"
        self.db.save_tournament_settings(self.tournament_id, settings)

        path = Path(self.temp_dir.name) / "arbitro.csv"
        self.export_service.export_arbiter_norm_report(self.tournament_id, path)

        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8-sig")
        self.assertIn("Dados do torneio (norma de árbitro)", content)
        self.assertIn("Árbitros designados", content)
        self.assertIn("Joao Arbitro", content)
        self.assertIn("Maria Aux", content)

    def test_list_layout_normalizes_and_validates(self) -> None:
        self._create_players(2)
        # Coluna desconhecida e duplicata sao descartadas; ordem preservada.
        saved = self.list_layout_service.save_columns(
            self.tournament_id, ["position", "xxx", "name", "name"], "standings"
        )
        self.assertEqual([spec["key"] for spec in saved], ["position", "name"])
        selected = self.list_layout_service.get_columns(self.tournament_id, "standings")["selected"]
        self.assertEqual([spec["key"] for spec in selected], ["position", "name"])
        # Selecao vazia / so codigos invalidos sao rejeitadas.
        with self.assertRaisesRegex(AppError, "ao menos uma coluna"):
            self.list_layout_service.save_columns(self.tournament_id, [], "standings")
        with self.assertRaisesRegex(AppError, "ao menos uma coluna"):
            self.list_layout_service.save_columns(self.tournament_id, ["xxx"], "standings")

if __name__ == "__main__":
    unittest.main()
