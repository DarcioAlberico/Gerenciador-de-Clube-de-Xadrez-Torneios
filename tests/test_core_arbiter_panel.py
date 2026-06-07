from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.core.services import (
    AppError,
    ExportService,
    PairingService,
    TeamService,
    TournamentService,
)
from tests.fixtures import load_tournament_fixture


class ArbiterPanelMetricsProgressTest(unittest.TestCase):
    FINAL = {"1-0", "0-1", "1/2-1/2"}

    def test_individual_progress(self) -> None:
        from src.services.pairing.arbitration import individual_round_dashboard_metrics

        pairings = [{"result": "1-0"}, {"result": ""}, {"is_bye": True, "result": ""}]
        metrics = individual_round_dashboard_metrics(pairings, self.FINAL)
        self.assertEqual(2, metrics["total_results"])  # exclui o bye
        self.assertEqual(1, metrics["resolved_results"])
        self.assertEqual(1, metrics["byes"])

    def test_team_progress(self) -> None:
        from src.services.pairing.arbitration import team_round_dashboard_metrics

        matches = [{"id": 1, "is_bye": False}, {"id": 2, "is_bye": True}]
        boards = {1: [{"result": "1-0"}, {"result": ""}]}
        metrics = team_round_dashboard_metrics(matches, boards, self.FINAL)
        self.assertEqual(2, metrics["total_results"])
        self.assertEqual(1, metrics["resolved_results"])
        self.assertEqual(1, metrics["pending_results"])
        self.assertEqual(1, metrics["byes"])


class ArbiterPanelDeepeningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.pairing_service = PairingService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _open_round_tournament(self) -> int:
        tournament_id = self.db.create_tournament(
            name="Aberto",
            location="Sala",
            rounds_count=3,
            time_control="90+30",
            start_date="2026-06-02",
            end_date="2026-06-02",
        )
        for index in range(4):
            self.db.create_player(tournament_id=tournament_id, name=f"Jogador {index}", rating=1500 - index)
        self.pairing_service.generate_next_round(tournament_id)
        return tournament_id

    def test_dashboard_structured_alerts_and_progress(self) -> None:
        tournament_id = self._open_round_tournament()
        dashboard = self.pairing_service.arbitration_dashboard(tournament_id)
        metrics = dashboard["metrics"]
        self.assertEqual(2, metrics["total_results"])
        self.assertEqual(0, metrics["resolved_results"])
        self.assertEqual(0, metrics["round_progress_percent"])
        detailed = dashboard["alerts_detailed"]
        self.assertTrue(detailed)
        for alert in detailed:
            self.assertIn("text", alert)
            self.assertIn("severity", alert)
            self.assertIn("action", alert)
        self.assertTrue(any(alert["action"] == "pending_results" for alert in detailed))
        # `alerts` (strings) continua em sincronia.
        self.assertEqual([alert["text"] for alert in detailed], dashboard["alerts"])

    def test_progress_updates_after_result(self) -> None:
        tournament_id = self._open_round_tournament()
        rounds = self.db.list_rounds(tournament_id)
        pairings = self.db.get_pairings_for_round(int(rounds[-1]["id"]))
        self.pairing_service.update_result(tournament_id, int(pairings[0]["id"]), "1-0")
        metrics = self.pairing_service.arbitration_dashboard(tournament_id)["metrics"]
        self.assertEqual(1, metrics["resolved_results"])
        self.assertEqual(50, metrics["round_progress_percent"])

    def test_export_round_package(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.pairing_service
        )
        latest_round = sorted(self.db.list_rounds(tournament_id), key=lambda item: int(item["number"]))[-1]
        dest = Path(self.temp_dir.name) / "pacote"
        result = self.export_service.export_round_package(int(latest_round["id"]), dest)
        self.assertEqual([], result["errors"])
        self.assertEqual(3, result["count"])  # mural + sumulas + cartoes
        self.assertTrue(all(os.path.exists(path) for path in result["generated"]))

    def test_export_tournament_minutes(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.pairing_service
        )
        sections = self.export_service._tournament_minutes_sections(tournament_id)
        titles = [title for title, _headers, _rows in sections]
        self.assertEqual("Ata final do torneio", titles[0])
        self.assertTrue(any("assinatura" in title.lower() for title in titles))
        out_path = Path(self.temp_dir.name) / "ata.xlsx"
        self.export_service.export_tournament_minutes(tournament_id, out_path)
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)


class ArbiterPanelNetNewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.pairing_service = PairingService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _open_round_tournament(self) -> int:
        tournament_id = self.db.create_tournament(
            name="Aberto",
            location="Sala",
            rounds_count=3,
            time_control="90+30",
            start_date="2026-06-02",
            end_date="2026-06-02",
        )
        for index in range(4):
            self.db.create_player(
                tournament_id=tournament_id,
                name=f"Jogador {index}",
                rating=1500 - index,
                category="Absoluto" if index % 2 == 0 else "Sub-12",
            )
        self.pairing_service.generate_next_round(tournament_id)
        return tournament_id

    def _team_tournament(self) -> tuple[int, int]:
        tournament_id = self.tournament_service.create_tournament(
            {"name": "Equipes", "competition_type": "team", "rounds_count": "3", "bye_points": "1"}
        )
        self.tournament_service.save_profile(
            tournament_id,
            {
                "name": "Equipes",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {
                "team_boards_count": "4",
                "team_match_win_points": "2",
                "team_match_draw_points": "1",
                "team_match_loss_points": "0",
                "team_pairing_method": "swiss",
                "team_standing_primary": "match_points",
                "team_standing_secondary": "game_points",
            },
            [],
        )
        for team_index in range(4):
            team_id = self.team_service.create_team(
                tournament_id,
                {"name": f"Equipe {team_index + 1}", "club": f"Clube {team_index + 1}", "captain": f"Cap {team_index + 1}"},
            )
            for board_number in range(1, 5):
                player_id = self.db.create_player(
                    tournament_id,
                    name=f"E{team_index + 1} J{board_number}",
                    rating=2200 - team_index * 100 - board_number * 10,
                    club=f"Clube {team_index + 1}",
                )
                self.team_service.add_player(team_id, player_id, board_number=str(board_number), role="starter")
        round_data = self.pairing_service.generate_next_round(tournament_id)
        return tournament_id, int(round_data["id"])

    # N1 - Ata por categoria
    def test_category_winners_section(self) -> None:
        tournament_id = self._open_round_tournament()
        title, headers, rows = self.export_service._category_winners_section(tournament_id)
        categories = {row[0] for row in rows}
        self.assertIn("Absoluto", categories)
        self.assertIn("Sub-12", categories)
        self.assertNotIn("", categories)

    def test_minutes_includes_category_section(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.pairing_service
        )
        titles = [title for title, _h, _r in self.export_service._tournament_minutes_sections(tournament_id)]
        self.assertIn("Vencedores por categoria", titles)

    # N2 - Boletim da rodada
    def test_round_bulletin(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.pairing_service
        )
        latest = sorted(self.db.list_rounds(tournament_id), key=lambda item: int(item["number"]))[-1]
        sections = self.export_service._round_bulletin_sections(int(latest["id"]))
        titles = [title for title, _h, _r in sections]
        self.assertTrue(titles[0].startswith("Boletim da rodada"))
        self.assertTrue(any("Classificacao apos a rodada" in title for title in titles))
        self.assertIn("Destaques", titles)
        out_path = Path(self.temp_dir.name) / "boletim.xlsx"
        self.export_service.export_round_bulletin(int(latest["id"]), out_path)
        self.assertTrue(out_path.exists())

    # N3 - Checklist de fechamento
    def test_closing_checklist_open_round(self) -> None:
        tournament_id = self._open_round_tournament()
        checklist = self.pairing_service.closing_checklist(tournament_id)
        results_item = next(item for item in checklist if item["action"] == "pending_results")
        self.assertFalse(results_item["ok"])
        ready_item = next(item for item in checklist if item["action"] == "ready_to_close")
        self.assertFalse(ready_item["ok"])
        rounds = self.db.list_rounds(tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rounds[-1]["id"])):
            if not pairing.get("is_bye"):
                self.pairing_service.update_result(tournament_id, int(pairing["id"]), "1-0")
        checklist_after = self.pairing_service.closing_checklist(tournament_id)
        self.assertTrue(next(item for item in checklist_after if item["action"] == "pending_results")["ok"])
        self.assertTrue(next(item for item in checklist_after if item["action"] == "ready_to_close")["ok"])

    def test_closing_checklist_without_rounds(self) -> None:
        tournament_id = self.db.create_tournament(
            name="Vazio", location="", rounds_count=3, time_control="", start_date="", end_date=""
        )
        checklist = self.pairing_service.closing_checklist(tournament_id)
        self.assertEqual(1, len(checklist))
        self.assertEqual("initial_call", checklist[0]["action"])
        self.assertFalse(checklist[0]["ok"])

    # N4 - Pacote da rodada para equipes
    def test_export_round_package_team(self) -> None:
        _tournament_id, round_id = self._team_tournament()
        dest = Path(self.temp_dir.name) / "pacote_equipes"
        result = self.export_service.export_round_package(round_id, dest)
        self.assertTrue(all(os.path.exists(path) for path in result["generated"]))
        self.assertTrue(any("cartoes" in path for path in result["generated"]))
        self.assertTrue(any("sumulas" in path for path in result["generated"]))


class ArbiterPanelExtrasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.pairing_service = PairingService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _individual_with_categories(self) -> int:
        tournament_id = self.db.create_tournament(
            name="Podio", location="Sala", rounds_count=3, time_control="", start_date="2026-06-02", end_date="2026-06-02"
        )
        for index in range(4):
            self.db.create_player(
                tournament_id=tournament_id,
                name=f"Jogador {index}",
                rating=1600 - index * 10,
                category="Absoluto" if index % 2 == 0 else "Sub-12",
            )
        self.pairing_service.generate_next_round(tournament_id)
        return tournament_id

    def _team_tournament(self) -> int:
        tournament_id = self.tournament_service.create_tournament(
            {"name": "Equipes", "competition_type": "team", "rounds_count": "3", "bye_points": "1"}
        )
        self.tournament_service.save_profile(
            tournament_id,
            {
                "name": "Equipes",
                "competition_type": "team",
                "scope": "standalone",
                "rounds_count": "3",
                "bye_points": "1",
            },
            {
                "team_boards_count": "4",
                "team_match_win_points": "2",
                "team_match_draw_points": "1",
                "team_match_loss_points": "0",
                "team_pairing_method": "swiss",
                "team_standing_primary": "match_points",
                "team_standing_secondary": "game_points",
            },
            [],
        )
        for team_index in range(4):
            team_id = self.team_service.create_team(
                tournament_id,
                {"name": f"Equipe {team_index + 1}", "club": f"Clube {team_index + 1}", "captain": "Cap"},
            )
            for board_number in range(1, 5):
                player_id = self.db.create_player(
                    tournament_id,
                    name=f"E{team_index + 1} J{board_number}",
                    rating=2200 - team_index * 100 - board_number * 10,
                )
                self.team_service.add_player(team_id, player_id, board_number=str(board_number), role="starter")
        self.pairing_service.generate_next_round(tournament_id)
        return tournament_id

    # M1 - Poster do podio
    def test_podium_data(self) -> None:
        tournament_id = self._individual_with_categories()
        data = self.export_service._podium_data(tournament_id)
        self.assertFalse(data["is_team"])
        self.assertEqual(3, len(data["top"]))
        self.assertEqual(1, data["top"][0]["rank"])
        category_labels = {row["category"] for row in data["categories"]}
        self.assertIn("Absoluto", category_labels)
        self.assertIn("Sub-12", category_labels)

    def test_export_podium_pdf(self) -> None:
        tournament_id = self._individual_with_categories()
        out_path = Path(self.temp_dir.name) / "podio.pdf"
        self.export_service.export_podium(tournament_id, out_path)
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        with self.assertRaises(AppError):
            self.export_service.export_podium(tournament_id, Path(self.temp_dir.name) / "podio.csv")

    # M3 - Checklist especifico para equipes
    def test_team_closing_checklist_has_lineups(self) -> None:
        tournament_id = self._team_tournament()
        checklist = self.pairing_service.closing_checklist(tournament_id)
        actions = [item["action"] for item in checklist]
        self.assertIn("lineups", actions)
        self.assertIn("ready_to_close", actions)

if __name__ == "__main__":
    unittest.main()
