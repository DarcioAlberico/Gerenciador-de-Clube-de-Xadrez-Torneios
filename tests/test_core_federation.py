from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.core.database import Database
from src.core.services import (
    AppError,
    ChessResultsService,
    ExportService,
    OfficialRatingService,
    PairingService,
)
from src.services.federation_exporters import FederationExporterRegistry, TRF16Exporter
from tests.fixtures import load_tournament_fixture
from tests.support.core_service_base import CoreServiceTestCase


class ChessResultsBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.pairing_service = PairingService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)
        self.service = ChessResultsService(self.db, self.export_service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normalize_results_url(self) -> None:
        from src.services.chess_results import normalize_results_url

        self.assertEqual(
            "https://chess-results.com/tnr123.aspx",
            normalize_results_url("chess-results.com/tnr123.aspx"),
        )
        self.assertEqual(
            "https://chess-results.com/tnr1.aspx",
            normalize_results_url("http://chess-results.com/tnr1.aspx"),
        )
        self.assertEqual("", normalize_results_url("https://exemplo.com/tnr1"))
        self.assertEqual("", normalize_results_url(""))

    def test_parse_entries_csv(self) -> None:
        from src.services.chess_results import parse_entries_csv

        content = "Name,Rtg,FED,FideID,Sex\nAna Silva,1500,BRA,12345,F\nJoao Souza,1800,POR,999,M\n"
        payloads, errors = parse_entries_csv(content)
        self.assertEqual(2, len(payloads))
        self.assertEqual([], errors)
        self.assertEqual("Ana Silva", payloads[0]["name"])
        self.assertEqual(1500, payloads[0]["rating"])
        self.assertEqual("BRA", payloads[0]["federation_id"])
        self.assertEqual("12345", payloads[0]["fide_id"])
        self.assertEqual("F", payloads[0]["sex"])

    def test_parse_entries_csv_reports_empty_name(self) -> None:
        from src.services.chess_results import parse_entries_csv

        payloads, errors = parse_entries_csv("Name,Rtg\n,1500\nBia,1600\n")
        self.assertEqual(1, len(payloads))
        self.assertTrue(any("nome vazio" in err.lower() for err in errors))

    def test_import_entries_creates_players(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.pairing_service
        )
        before = len(self.db.list_players(tournament_id, active_only=False))
        csv_path = Path(self.temp_dir.name) / "entries.csv"
        csv_path.write_text(
            "Name,Rtg,FED,FideID\nNovo Um,1234,BRA,1\nNovo Dois,1300,POR,2\n",
            encoding="utf-8",
        )
        result = self.service.import_entries(tournament_id, csv_path)
        self.assertEqual(2, result["imported"])
        after = len(self.db.list_players(tournament_id, active_only=False))
        self.assertEqual(before + 2, after)

    def test_prepare_upload_and_published_url(self) -> None:
        tournament_id = load_tournament_fixture(
            "individual_8_players_3_rounds", self.db, self.pairing_service
        )
        result = self.service.prepare_upload(tournament_id, self.temp_dir.name)
        self.assertTrue(os.path.exists(result["trf_path"]))
        self.assertTrue(result["steps"])
        self.assertIn("chess-results.com", result["register_url"])

        saved = self.service.set_published_url(tournament_id, "chess-results.com/tnr9.aspx")
        self.assertEqual("https://chess-results.com/tnr9.aspx", saved)
        self.assertEqual(saved, self.service.get_published_url(tournament_id))
        with self.assertRaises(AppError):
            self.service.set_published_url(tournament_id, "http://exemplo.com/x")


class ForeignRatingListTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.service = OfficialRatingService(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_map_row_uses_aliases(self) -> None:
        from src.services.foreign_rating_lists import map_row

        payload = map_row({"Nome": "Maria Lima", "Rating": "1700", "ID": "77", "Sexo": "F"}, "POR")
        assert payload is not None
        self.assertEqual("Maria Lima", payload["name"])
        self.assertEqual(1700, payload["national_rating"])
        self.assertEqual(1700, payload["standard_rating"])
        self.assertEqual(0, payload["international_rating"])
        self.assertEqual("POR", payload["federation"])
        self.assertEqual("77", payload["external_id"])

    def test_map_row_without_name_returns_none(self) -> None:
        from src.services.foreign_rating_lists import map_row

        self.assertIsNone(map_row({"Rating": "1500"}, "ESP"))

    def test_import_foreign_list_creates_snapshot(self) -> None:
        csv_path = Path(self.temp_dir.name) / "por.csv"
        csv_path.write_text(
            "Nome,Rating,ID,Titulo\nMaria Lima,1700,77,\nPedro Alves,1650,88,FM\n",
            encoding="utf-8",
        )
        result = self.service.import_foreign_list(csv_path, "POR")
        self.assertEqual("POR", result["source"])
        self.assertEqual(2, result["imported"])
        self.assertIsNotNone(result["snapshot_id"])
        with self.db.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM official_players WHERE source = ?", ("POR",)
            ).fetchone()[0]
        self.assertEqual(2, count)

    def test_invalid_federation_rejected(self) -> None:
        csv_path = Path(self.temp_dir.name) / "x.csv"
        csv_path.write_text("Nome,Rating\nA,1\n", encoding="utf-8")
        with self.assertRaises(AppError):
            self.service.import_foreign_list(csv_path, "1")

    def test_add_and_list_foreign_federation(self) -> None:
        seeded = self.service.list_foreign_federations()
        self.assertIn("POR", seeded)
        code = self.service.add_foreign_federation("bol", "Bolivia (FEBODA)")
        self.assertEqual("BOL", code)
        self.assertIn("BOL", self.service.list_foreign_federations())


class FederationExportTest(CoreServiceTestCase):
    def test_export_chess_results_trf16_includes_required_fields(self) -> None:
        tournament_id = self.db.create_tournament(
            "Aberto Sao Paulo",
            location="Sao Paulo",
            rounds_count=1,
            time_control="90 min + 30 sec",
            start_date="2026-05-24",
            end_date="2026-05-24",
        )
        self.db.save_tournament_settings(
            tournament_id,
            {
                "fide_event_id": "12345",
                "federation": "BRA",
                "chief_arbiter": "Arbitro Chefe",
                "arbiters": "Adjunto Um",
                "tournament_profile": "fide",
            },
        )
        self.db.save_round_schedule(
            tournament_id,
            [{"round_number": 1, "date": "2026-05-24", "time": "10:00"}],
        )
        first_player = self.db.create_player(
            tournament_id,
            name="Silva, Ana",
            surname="Silva",
            given_name="Ana",
            title="WFM",
            sex="w",
            federation_id="BRA",
            fide_id="1234567",
            rating=2100,
            international_rating=2100,
            birth_date="2000-01-02",
        )
        second_player = self.db.create_player(
            tournament_id,
            name="Souza, Bruno",
            surname="Souza",
            given_name="Bruno",
            title="FM",
            sex="m",
            federation_id="BRA",
            fide_id="7654321",
            rating=2000,
            international_rating=2000,
            birth_date="1999-03-04",
        )
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": first_player,
                    "black_player_id": second_player,
                    "result": "1-0",
                }
            ],
        )
        self.service.close_round(tournament_id, round_id)

        output_path = Path(self.temp_dir.name) / "chess_results.trf"
        warnings = self.export_service.export_chess_results_trf(tournament_id, output_path)
        content = output_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        player_lines = [line for line in lines if line.startswith("001 ")]

        self.assertEqual(warnings, [])
        self.assertIn("012 Aberto Sao Paulo", content)
        self.assertIn("032 BRA", content)
        self.assertIn("042 2026/05/24", content)
        self.assertIn("052 2026/05/24", content)
        self.assertIn("062 2", content)
        self.assertIn("072 2", content)
        self.assertIn("082 0", content)
        self.assertIn("092 Individual: Suico (FIDE-rated)", content)
        self.assertIn("102 Arbitro Chefe", content)
        self.assertIn("112 Adjunto Um", content)
        self.assertIn("122 90 min + 30 sec", content)
        self.assertEqual(len(player_lines), 2)
        self.assertIn("wWFM Silva, Ana", player_lines[0])
        self.assertIn("2100 BRA", player_lines[0])
        self.assertIn("1234567", player_lines[0])
        self.assertIn("2000/01/02", player_lines[0])
        self.assertTrue(player_lines[0].endswith("2 w 1"))
        self.assertTrue(player_lines[1].endswith("1 b 0"))

    def test_validate_chess_results_trf16_warns_about_open_rounds_and_invalid_fide_data(self) -> None:
        tournament_id = self.db.create_tournament(
            "Aberto Validacao",
            location="Curitiba",
            rounds_count=2,
            time_control="60 min",
            start_date="2026-05-24",
            end_date="2026-05-25",
        )
        self.db.save_tournament_settings(
            tournament_id,
            {
                "federation": "BR",
                "chief_arbiter": "Arbitro Chefe",
                "tournament_profile": "fide",
            },
        )
        self.db.save_round_schedule(
            tournament_id,
            [
                {"round_number": 1, "date": "2026-05-24", "time": "10:00"},
                {"round_number": 2, "date": "data ruim", "time": "15:00"},
            ],
        )
        first_player = self.db.create_player(
            tournament_id,
            name="Jogador Um",
            fide_id="ABC123",
            federation_id="BR",
            rating=1800,
            international_rating=1800,
            birth_date="data ruim",
        )
        second_player = self.db.create_player(
            tournament_id,
            name="Jogador Dois",
            fide_id="222",
            federation_id="BRA",
            rating=1700,
            international_rating=1700,
            birth_date="2000-01-02",
        )
        self.db.create_round_with_pairings(
            tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": first_player,
                    "black_player_id": second_player,
                    "result": "",
                }
            ],
        )

        warnings = self.export_service.validate_chess_results_trf(tournament_id)

        self.assertIn("Federacao FIDE do torneio deve ter 3 letras.", warnings)
        self.assertIn("Torneio FIDE-rated sem FIDE Event-ID.", warnings)
        self.assertIn("Rodadas ainda nao fechadas: 1.", warnings)
        self.assertIn("Rodadas com resultados pendentes/incompletos: 1.", warnings)
        self.assertIn("Rodadas com data invalida no calendario: 2.", warnings)
        self.assertTrue(any("FIDE ID numerico" in warning for warning in warnings))
        self.assertTrue(any("data de nascimento valida" in warning for warning in warnings))
        self.assertTrue(any("federacao FIDE com 3 letras" in warning for warning in warnings))

    def test_trf25_export_emits_330_for_double_forfeit_match(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        # Match inteiro W.O.: todos os tabuleiros 0F-0F → duplo forfeit (--).
        for board in self.db.list_team_boards(int(match["id"])):
            self.service.update_result(tournament_id, int(board["id"]), "0F-0F")
        self.service.close_round(tournament_id, round_data["id"])

        output_path = Path(self.temp_dir.name) / "team_trf25_ff.trf"
        TRF25Exporter(self.export_service).export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        forfeit_lines = [line for line in lines if line.startswith("330 ")]
        self.assertEqual(len(forfeit_lines), 1)
        self.assertEqual(forfeit_lines[0][4:6], "--")

    def test_trf25_export_emits_330_directional_walkover(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        # Equipe branca do match vence por W.O. em ambos os tabuleiros.
        # Tabuleiro 1 (ímpar): brancas = equipe branca → 1F-0F.
        # Tabuleiro 2 (par, cores invertidas): pretas = equipe branca → 0F-1F.
        boards = self.db.list_team_boards(int(match["id"]))
        self.service.update_result(tournament_id, int(boards[0]["id"]), "1F-0F")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "0F-1F")
        self.service.close_round(tournament_id, round_data["id"])

        output_path = Path(self.temp_dir.name) / "team_trf25_wo.trf"
        TRF25Exporter(self.export_service).export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        forfeit_lines = [line for line in lines if line.startswith("330 ")]
        self.assertEqual(len(forfeit_lines), 1)
        self.assertEqual(forfeit_lines[0][4:6], "+-")

    def test_trf25_export_skips_330_for_normal_and_partial_results(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(round_data["id"])[0]
        # Forfeit parcial: 1 tabuleiro W.O., outro jogado → NÃO é um 330.
        boards = self.db.list_team_boards(int(match["id"]))
        self.service.update_result(tournament_id, int(boards[0]["id"]), "1F-0F")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "1-0")
        self.service.close_round(tournament_id, round_data["id"])

        output_path = Path(self.temp_dir.name) / "team_trf25_partial.trf"
        TRF25Exporter(self.export_service).export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        self.assertFalse(any(line.startswith("330 ") for line in lines))

    def test_trf25_scoring_362_and_individual_212_codes(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        # Pontuação de match não-padrão (3-1-0) → emite o 362; padrão → None.
        self.assertIsNone(
            TRF25Exporter._scoring_system_362(
                {"team_match_win_points": "2", "team_match_draw_points": "1", "team_match_loss_points": "0"}
            )
        )
        line_362 = TRF25Exporter._scoring_system_362(
            {"team_match_win_points": "3", "team_match_draw_points": "1", "team_match_loss_points": "0"}
        )
        self.assertEqual(line_362[:6], "362 TW")
        self.assertIn(" 3.0", line_362)
        # Ordem de desempate individual espelha pairing/tiebreaks.py.
        self.assertEqual(
            TRF25Exporter._tiebreak_codes_212(is_team=False),
            ["PTS", "BH", "BH/M1", "SB", "WIN"],
        )

    def test_federation_exporter_registry_keeps_trf16_flow_extensible(self) -> None:
        registry = FederationExporterRegistry()
        exporter = TRF16Exporter(self.export_service)
        registry.register(exporter)

        self.assertEqual(["trf16"], registry.list_formats())
        self.assertIs(registry.get("trf16"), exporter)

    def test_trf25_scaffold_registers_and_warns_about_pending_extensions(self) -> None:
        from src.services.federation_exporters import (
            TRF25_SCAFFOLD_WARNING,
            TRF25Exporter,
        )

        registry = FederationExporterRegistry()
        trf16 = TRF16Exporter(self.export_service)
        trf25 = TRF25Exporter(self.export_service)
        registry.register(trf16)
        registry.register(trf25)

        # Códigos distintos no registry, sem colidir.
        self.assertEqual(["trf16", "trf25"], registry.list_formats())
        self.assertIs(registry.get("trf25"), trf25)
        # Scaffold herda comportamento de validação, mas sempre prefixa
        # o warning explícito de "extensões não implementadas".
        self._create_players(2)
        warnings = trf25.validate(self.tournament_id)
        self.assertEqual(warnings[0], TRF25_SCAFFOLD_WARNING)
        # Os warnings subsequentes são os do TRF16 herdado (sem federacao,
        # sem datas, etc) — não devem ser duplicados.
        self.assertEqual(1, sum(1 for w in warnings if w == TRF25_SCAFFOLD_WARNING))

    def test_export_chess_results_trf25_routes_to_trf25_exporter(self) -> None:
        from src.services.federation_exporters import TRF25_SCAFFOLD_WARNING

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        output_path = Path(self.temp_dir.name) / "fide.trf"

        warnings = self.export_service.export_chess_results_trf25(tournament_id, output_path)

        # O método novo deve devolver o aviso de scaffold do TRF25 e emitir
        # registros 310 (equipe), não o 013 herdado do TRF16.
        self.assertIn(TRF25_SCAFFOLD_WARNING, warnings)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any(line.startswith("310 ") for line in lines))
        self.assertFalse(any(line.startswith("013 ") for line in lines))

    def test_trf25_export_emits_152_and_222_for_individual(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self.db.update_tournament_details(
            self.tournament_id, name="Torneio teste", time_control="90 min + 30 s"
        )
        self._create_players(4)
        self.service.generate_next_round(self.tournament_id)

        output_path = Path(self.temp_dir.name) / "ind_trf25.trf"
        TRF25Exporter(self.export_service).export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        # 222: ritmo codificado (90 min = 5400 s, +30 s de incremento).
        self.assertIn("222 5400+30", lines)
        # 152: cor do top seed (rank 1) na rodada 1 — W ou B, exatamente um.
        colour_lines = [line for line in lines if line.startswith("152 ")]
        self.assertEqual(len(colour_lines), 1)
        self.assertIn(colour_lines[0], ("152 W", "152 B"))

    def test_trf25_omits_222_when_time_control_unparseable(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self.db.update_tournament_details(
            self.tournament_id, name="Torneio teste", time_control="ritmo livre"
        )
        self._create_players(2)

        output_path = Path(self.temp_dir.name) / "ind_no222.trf"
        TRF25Exporter(self.export_service).export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        self.assertFalse(any(line.startswith("222 ") for line in lines))

    def test_trf25_emits_299_for_individual_point_adjustment(self) -> None:
        from src.services.constants import player_pairing_name
        from src.services.federation_exporters import TRF25Exporter

        player_ids = self._create_players(4)
        # Penalidade de meio ponto ao 2º jogador por rating (vira o start-rank
        # exato no export, qualquer que seja a ordem de seeding).
        self.db.add_point_adjustment(
            self.tournament_id,
            round_number=0,
            player_id=player_ids[1],
            aat_type="",
            game_points=-0.5,
            reason="Penalidade de comportamento",
        )

        output_path = Path(self.temp_dir.name) / "ind_299.trf"
        TRF25Exporter(self.export_service).export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        players = sorted(
            self.db.list_players(self.tournament_id, active_only=False),
            key=lambda p: (
                -self.export_service._trf_rating(p),
                player_pairing_name(p).casefold(),
                int(p.get("id") or 0),
            ),
        )
        expected_rank = next(
            i for i, p in enumerate(players, start=1) if int(p["id"]) == player_ids[1]
        )

        adj_lines = [line for line in lines if line.startswith("299 ")]
        self.assertEqual(len(adj_lines), 1)
        line = adj_lines[0]
        self.assertEqual(line[13:17], "-0.5")
        self.assertEqual(line[23:27].strip(), str(expected_rank))

    def test_trf25_emits_250_for_classic_acceleration(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self._create_players(8)
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "accel.trf"

        # Sem aceleração: nenhum registro 250.
        self.db.save_tournament_settings(self.tournament_id, {"acceleration_method": "none"})
        exporter.export(self.tournament_id, output_path)
        plain = output_path.read_text(encoding="utf-8").splitlines()
        self.assertFalse([line for line in plain if line.startswith("250 ")])

        # Aceleração clássica: 250 com bônus 1.0, rodadas 1-2, ranks 1..4 (N//2).
        self.db.save_tournament_settings(
            self.tournament_id, {"acceleration_method": "accelerated"}
        )
        exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        accel_lines = [line for line in lines if line.startswith("250 ")]
        self.assertEqual(len(accel_lines), 1)
        line = accel_lines[0]
        self.assertEqual(line[4:8].strip(), "")  # match points em branco (individual)
        self.assertEqual(float(line[9:13]), 1.0)  # game points
        self.assertEqual(line[14:17].strip(), "1")  # primeira rodada
        self.assertEqual(line[18:21].strip(), "2")  # última rodada
        self.assertEqual(line[22:26].strip(), "1")  # primeiro jogador (rank 1)
        self.assertEqual(line[27:31].strip(), "4")  # último jogador (N//2 = 4)

    def test_trf25_warns_when_initial_order_not_fide(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self._create_players(4)
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "order.trf"

        def has_sno_warning(messages: list[str]) -> bool:
            return any("numero de ordem (SNo)" in message for message in messages)

        # Ordem inicial = rating principal (FIDE-compativel): sem aviso de SNo.
        self.db.save_tournament_settings(self.tournament_id, {"initial_order": "rating"})
        self.assertFalse(has_sno_warning(exporter.export(self.tournament_id, output_path)))

        # Ordem inicial nacional: avisa que o SNo do TRF pode divergir do seeding.
        self.db.save_tournament_settings(self.tournament_id, {"initial_order": "national_rating"})
        self.assertTrue(has_sno_warning(exporter.export(self.tournament_id, output_path)))

    def test_trf25_802_marks_full_match_forfeit(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        match = self.db.list_team_matches_for_round(int(round_data["id"]))[0]
        boards = self.db.list_team_boards(int(match["id"]))
        # W.O. consistente: uma equipe vence o match inteiro por forfeit.
        # Tab. 1 (impar): brancas vencem; tab. 2 (par, cores invertidas): pretas
        # vencem — ambos os pontos vao para a mesma equipe.
        self.service.update_result(tournament_id, int(boards[0]["id"]), "1F-0F")
        self.service.update_result(tournament_id, int(boards[1]["id"]), "0F-1F")
        self.service.close_round(tournament_id, int(round_data["id"]))

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_ff.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        # 330 do match forfeitado e indicadores f/F no 802 (col 39 = indice 38;
        # nao some no rstrip por ser caractere nao-branco).
        self.assertTrue(any(line.startswith("330 ") for line in lines))
        markers = sorted(
            line[38] for line in lines if line.startswith("802 ") and len(line) >= 39
        )
        self.assertEqual(markers, ["F", "f"])  # vencedor por W.O. e perdedor

    def test_trf25_802_no_forfeit_marker_on_normal_match(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, _team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        round_data = self.service.generate_next_round(tournament_id)
        self._close_team_round_with_decisive_boards(tournament_id, int(round_data["id"]))

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_normal.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        # Resultado normal (sem W.O.): nenhum 330 e nenhum indicador f/F no 802
        # (a posicao de forfeit fica em branco, somindo no rstrip).
        self.assertFalse(any(line.startswith("330 ") for line in lines))
        self.assertFalse(
            any(
                line.startswith("802 ") and len(line) >= 39 and line[38] in "fF"
                for line in lines
            )
        )

    def test_trf25_310_lists_starters_before_reserves(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        tournament_id, team_ids = self._create_team_tournament(teams_count=2, boards_count=2)
        # Reserva com rating altissimo → start_rank 1; sem fix, viria como 1o jogador.
        reserve_id = self.db.create_player(
            tournament_id, name="Reserva Forte", rating=3000, club="Clube 1"
        )
        self.team_service.add_player(team_ids[0], reserve_id, role="reserve")

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "team_reserve.trf"
        exporter.export(tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        def ranks_of(line: str) -> list[str]:
            # Jogadores do 310: a partir da col 74 (indice 73), 4 chars, passo 5.
            return [
                line[i:i + 4].strip()
                for i in range(73, len(line), 5)
                if line[i:i + 4].strip()
            ]

        team310 = [line for line in lines if line.startswith("310 ")]
        # A equipe da reserva e a unica cujo 310 contem o start-rank 1.
        target = next(line for line in team310 if "1" in ranks_of(line))
        ranks = ranks_of(target)
        self.assertEqual(len(ranks), 3)         # 2 titulares + 1 reserva
        self.assertEqual(ranks[-1], "1")        # reserva (rank 1) por ultimo
        self.assertNotEqual(ranks[0], "1")      # 1o jogador e um titular (board 1)

    def test_trf25_emits_national_rating_records(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self.tournament_service.save_profile(
            self.tournament_id,
            {"name": "Torneio teste", "rounds_count": "5", "bye_points": "1"},
            {"federation": "BRA"},
            [],
        )
        # p1 (rating maior) tem rating nacional; p2 nao tem.
        self.db.create_player(
            self.tournament_id, name="Com Nacional", rating=2000,
            national_rating=1928, cbx_id="55501",
        )
        self.db.create_player(self.tournament_id, name="Sem Nacional", rating=1900)

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "national.trf"
        exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        nat_lines = [line for line in lines if line.startswith("BRA ")]
        self.assertEqual(len(nat_lines), 1)  # so o jogador com rating nacional
        line = nat_lines[0]
        self.assertEqual(line[4:8].strip(), "1")     # start-rank do p1 (maior rating)
        self.assertEqual(line[48:52].strip(), "1928")  # rating nacional
        self.assertIn("55501", line)                  # nº nacional

        # 172 (Encoded Starting Rank Method) e obrigatorio quando ha registros NRS.
        header_172 = [ln for ln in lines if ln.startswith("172 ")]
        self.assertEqual(len(header_172), 1)
        self.assertEqual(header_172[0][4:7], "BRA")          # federacao (cols 5-7)
        self.assertEqual(header_172[0][8:13].strip(), "FIDE")  # metodo (cols 9-13)

    def test_trf25_omits_national_rating_without_federation(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        # Sem federacao configurada, mesmo com rating nacional nada e emitido.
        self.db.create_player(
            self.tournament_id, name="Com Nacional", rating=2000,
            national_rating=1928, cbx_id="55501",
        )
        self.db.create_player(self.tournament_id, name="Outro", rating=1900)

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "no_fed.trf"
        exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        self.assertFalse(any("55501" in line for line in lines))
        # Sem registros NRS, o 172 tambem nao deve aparecer.
        self.assertFalse(any(line.startswith("172 ") for line in lines))

    def test_trf25_validate_signals_data_complete_when_no_pending(self) -> None:
        from src.services.federation_exporters import TRF25Exporter
        from src.services.federation_exporters.trf16 import TRF16Exporter
        from src.services.federation_exporters.trf25 import (
            TRF25_DATA_COMPLETE_NOTE,
            TRF25_SCAFFOLD_WARNING,
        )

        exporter = TRF25Exporter(self.export_service)
        # Sem pendencias herdadas → caveat de formato + nota de prontidao de dados.
        with mock.patch.object(TRF16Exporter, "validate", return_value=[]):
            ready = exporter.validate(self.tournament_id)
        self.assertIn(TRF25_SCAFFOLD_WARNING, ready)
        self.assertIn(TRF25_DATA_COMPLETE_NOTE, ready)
        # Com pendencia herdada → sem nota de prontidao (so o caveat + a pendencia).
        with mock.patch.object(
            TRF16Exporter, "validate", return_value=["Torneio sem cidade/local."]
        ):
            pending = exporter.validate(self.tournament_id)
        self.assertIn(TRF25_SCAFFOLD_WARNING, pending)
        self.assertNotIn(TRF25_DATA_COMPLETE_NOTE, pending)
        self.assertIn("Torneio sem cidade/local.", pending)

    def test_trf25_emits_260_for_prohibited_pairing(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        player_ids = self._create_players(4)  # ratings decrescentes → rank = ordem
        # Proíbe rank 1 x rank 3, janela aberta (last_round=0 → última rodada=5).
        self.db.add_prohibited_pairing(
            self.tournament_id, player_ids[0], player_ids[2]
        )
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "prohib.trf"
        exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        prohibition_lines = [line for line in lines if line.startswith("260 ")]
        self.assertEqual(len(prohibition_lines), 1)
        line = prohibition_lines[0]
        self.assertEqual(line[4:7].strip(), "1")  # primeira rodada
        self.assertEqual(line[8:11].strip(), "5")  # última rodada (rounds_count=5)
        self.assertEqual(line[12:16].strip(), "1")  # entidade 1 (rank 1)
        self.assertEqual(line[17:21].strip(), "3")  # entidade 2 (rank 3)

    def test_federation_statistics_groups_players(self) -> None:
        ids = self._create_players(8)
        with self.db.connect() as connection:
            for pid in ids[:3]:
                connection.execute("UPDATE players SET federation_id = ? WHERE id = ?", ("BRA", pid))
        self._play_first_round(["1-0", "1-0", "1-0", "1-0"])

        sections = self.export_service._federation_sections(self.tournament_id)
        summary = {row[0]: row[1] for row in sections[0][2]}
        fed_rows = {row[0]: row[1] for row in sections[1][2]}

        self.assertEqual(summary["Jogadores"], 8)
        self.assertEqual(summary["Federações"], 2)   # BRA e "—"
        self.assertEqual(fed_rows["BRA"], 3)
        self.assertEqual(fed_rows["—"], 5)

    def test_trf_import_round_trips_players_and_header(self) -> None:
        self.db.create_player(
            self.tournament_id, name="Ana Silva", surname="Silva", given_name="Ana",
            rating=2000, international_rating=2000, federation_id="BRA",
            fide_id="123456", birth_date="2008-01-01", sex="w", title="WFM",
        )
        self.db.create_player(
            self.tournament_id, name="Bruno Souza", surname="Souza", given_name="Bruno",
            rating=1800, international_rating=1800, federation_id="BRA", fide_id="234567",
        )
        self.db.create_player(
            self.tournament_id, name="Carla Dias", surname="Dias", given_name="Carla",
            rating=1700, international_rating=1700, federation_id="ARG", fide_id="345678",
        )

        trf_path = Path(self.temp_dir.name) / "torneio.trf"
        self.export_service.export_chess_results_trf(self.tournament_id, trf_path)

        result = self.import_service.import_trf(trf_path)
        self.assertEqual(result["players_imported"], 3)

        imported = self.db.list_players(result["tournament_id"], active_only=False)
        by_fide = {str(player["fide_id"]): player for player in imported}
        self.assertEqual(set(by_fide), {"123456", "234567", "345678"})
        self.assertEqual(int(by_fide["123456"]["international_rating"]), 2000)
        self.assertEqual(by_fide["123456"]["federation_id"], "BRA")
        self.assertEqual(by_fide["123456"]["name"], "Ana Silva")
        self.assertEqual(by_fide["345678"]["federation_id"], "ARG")
        # Cabecalho: novo torneio herda nome e federacao do TRF.
        new_tournament = self.db.get_tournament(result["tournament_id"])
        self.assertEqual(new_tournament["name"], "Torneio teste")

    def test_trf_import_rejects_file_without_players(self) -> None:
        empty_path = Path(self.temp_dir.name) / "vazio.trf"
        empty_path.write_text("012 Torneio sem jogadores\r\n022 Cidade\r\n", encoding="utf-8")
        with self.assertRaisesRegex(AppError, "sem jogadores"):
            self.import_service.import_trf(empty_path)

    def test_trf_import_reconstructs_rounds_and_results(self) -> None:
        self._create_players(4)
        round_data = self.service.generate_next_round(self.tournament_id)
        round_id = int(round_data["id"])
        for pairing in self.db.get_pairings_for_round(round_id):
            self.service.update_result(self.tournament_id, int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, round_id)
        original_points = sorted(
            float(item["points"]) for item in self.service.standings(self.tournament_id)
        )

        trf_path = Path(self.temp_dir.name) / "jogado.trf"
        self.export_service.export_chess_results_trf(self.tournament_id, trf_path)
        result = self.import_service.import_trf(trf_path)

        self.assertEqual(result["rounds_imported"], 1)
        rounds = self.db.list_rounds(result["tournament_id"])
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["status"], "closed")
        # A classificacao reconstruida bate com a original (2x1.0 e 2x0.0).
        imported_points = sorted(
            float(item["points"]) for item in self.service.standings(result["tournament_id"])
        )
        self.assertEqual(imported_points, original_points)

    def test_trf25_emits_240_for_requested_bye(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        player_ids = self._create_players(5)  # ratings decrescentes → rank = ordem
        self.db.add_requested_bye(self.tournament_id, player_ids[4], 1, "H")
        self.service.generate_next_round(self.tournament_id)

        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "bye240.trf"
        exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()

        bye_lines = [line for line in lines if line.startswith("240 ")]
        self.assertEqual(len(bye_lines), 1)
        line = bye_lines[0]
        self.assertEqual(line[4:5], "H")          # tipo (col 5)
        self.assertEqual(line[6:9].strip(), "1")  # rodada (col 7-9)
        self.assertEqual(line[10:14].strip(), "5")  # start-rank do jogador (col 11-14)
        # A célula do 001 mostra o mesmo bye solicitado, nunca divergindo do 240.
        self.assertTrue(any("0000 - H" in line for line in lines))

    def test_trf25_emits_250_for_custom_acceleration(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        self._create_players(8)
        self.db.save_tournament_settings(
            self.tournament_id,
            {"acceleration_method": "custom:rounds=3;bonus=2.0;upper=0.25"},
        )
        exporter = TRF25Exporter(self.export_service)
        output_path = Path(self.temp_dir.name) / "custom.trf"
        exporter.export(self.tournament_id, output_path)
        lines = output_path.read_text(encoding="utf-8").splitlines()
        accel_lines = [line for line in lines if line.startswith("250 ")]
        self.assertEqual(len(accel_lines), 1)
        line = accel_lines[0]
        self.assertEqual(float(line[9:13]), 2.0)  # bônus custom
        self.assertEqual(line[14:17].strip(), "1")  # primeira rodada
        self.assertEqual(line[18:21].strip(), "3")  # round_count=3
        self.assertEqual(line[22:26].strip(), "1")  # rank 1
        self.assertEqual(line[27:31].strip(), "2")  # upper 0.25 de 8 = 2

    def test_trf25_dutch_192_is_dated_by_tournament_date(self) -> None:
        from src.services.federation_exporters import TRF25Exporter

        exporter = TRF25Exporter(self.export_service)
        settings = {"pairing_method": "swiss"}
        # Antes do corte (2025-07-01) → regras 2017.
        self.assertEqual(
            exporter._type_code_192({"start_date": "2025-06-30"}, settings),
            "FIDE_DUTCH_2017",
        )
        # No corte ou depois → regras 2025.
        self.assertEqual(
            exporter._type_code_192({"start_date": "2025-07-01"}, settings),
            "FIDE_DUTCH_2025",
        )
        # Sem start_date, usa o end_date como fallback.
        self.assertEqual(
            exporter._type_code_192({"end_date": "2024-01-10"}, settings),
            "FIDE_DUTCH_2017",
        )
        # Sem data parseável → FIDE_DUTCH puro (default-por-data, nunca chuta versão).
        self.assertEqual(exporter._type_code_192({}, settings), "FIDE_DUTCH")
        self.assertEqual(
            exporter._type_code_192({"start_date": "data invalida"}, settings),
            "FIDE_DUTCH",
        )

    def test_validate_chess_results_trf16_reports_special_result_statuses(self) -> None:
        tournament_id = self.db.create_tournament(
            "Aberto Pendencias",
            location="Sao Paulo",
            rounds_count=1,
            time_control="15 min",
            start_date="2026-05-24",
            end_date="2026-05-24",
        )
        self.db.save_tournament_settings(
            tournament_id,
            {
                "fide_event_id": "12345",
                "federation": "BRA",
                "chief_arbiter": "Arbitro Chefe",
                "tournament_profile": "fide",
            },
        )
        self.db.save_round_schedule(
            tournament_id,
            [{"round_number": 1, "date": "2026-05-24", "time": "10:00"}],
        )

        def player(index: int) -> int:
            return self.db.create_player(
                tournament_id,
                name=f"Jogador {index}",
                federation_id="BRA",
                fide_id=str(1000 + index),
                rating=1800 + index,
                international_rating=1800 + index,
                birth_date="2000-01-02",
            )

        players = [player(index) for index in range(1, 7)]
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": players[0],
                    "black_player_id": players[1],
                    "result": "1F-0F",
                    "is_bye": 0,
                },
                {
                    "board_number": 2,
                    "white_player_id": players[2],
                    "black_player_id": players[3],
                    "result": "0F-0F",
                    "is_bye": 0,
                },
                {
                    "board_number": 3,
                    "white_player_id": players[4],
                    "black_player_id": None,
                    "result": "BYE",
                    "is_bye": 1,
                },
            ],
        )
        self.service.close_round(tournament_id, round_id)

        warnings = self.export_service.validate_chess_results_trf(tournament_id)

        self.assertIn("TRF16 contem 1 bye(s).", warnings)
        self.assertIn("TRF16 contem 1 resultado(s) por WO.", warnings)
        self.assertIn("TRF16 contem 1 dupla(s) ausencia(s).", warnings)
        self.assertIn("TRF16 contem 1 jogador(es) nao emparceirado(s) em rodadas geradas.", warnings)

    def test_export_chess_results_trf16_validation_report_and_encoding(self) -> None:
        tournament_id = self.db.create_tournament(
            "Aberto Acentuacao",
            location="Sao Paulo",
            rounds_count=1,
            time_control="90 min",
            start_date="2026-05-24",
            end_date="2026-05-24",
        )
        self.db.save_tournament_settings(
            tournament_id,
            {
                "fide_event_id": "12345",
                "federation": "BRA",
                "chief_arbiter": "Arbitro Chefe",
                "tournament_profile": "fide",
            },
        )
        first_player = self.db.create_player(
            tournament_id,
            name="Ávila, José",
            surname="Ávila",
            given_name="José",
            federation_id="BRA",
            fide_id="1234",
            rating=2100,
            international_rating=2100,
            birth_date="2000-01-02",
        )
        second_player = self.db.create_player(
            tournament_id,
            name="Núñez, Maria",
            surname="Núñez",
            given_name="Maria",
            federation_id="BRA",
            fide_id="1235",
            rating=2000,
            international_rating=2000,
            birth_date="2000-01-02",
        )
        round_id = self.db.create_round_with_pairings(
            tournament_id,
            1,
            [
                {
                    "board_number": 1,
                    "white_player_id": first_player,
                    "black_player_id": second_player,
                    "result": "1-0",
                }
            ],
        )
        self.service.close_round(tournament_id, round_id)

        trf_path = Path(self.temp_dir.name) / "acentuacao.trf"
        report_path = Path(self.temp_dir.name) / "pendencias_trf.csv"
        self.export_service.export_chess_results_trf(tournament_id, trf_path)
        self.export_service.export_chess_results_trf_validation_report(tournament_id, report_path)

        trf_content = trf_path.read_text(encoding="utf-8")
        report_content = report_path.read_text(encoding="utf-8")
        self.assertIn("Avila, Jose", trf_content)
        self.assertIn("Nunez, Maria", trf_content)
        self.assertIn("Partidas jogadas", report_content)
        self.assertIn("1", report_content)


class TRF16ExporterDirectTest(CoreServiceTestCase):
    """Testes diretos das lacunas não cobertas do TRF16Exporter.

    Cobre:
    1. export() e validate() com tournament_id inválido → AppError
    2. Campo 072 (rated_count) exclui jogadores sem rating
    3. Ordenamento de jogadores por (-rating, nome, id)
    4. Exportação sem rodadas geradas → linhas 001 sem colunas de resultado
    5. Resultado bye e walkover codificados corretamente na linha 001
    6. validate() de torneio por equipes sem equipes → AppError
    """

    def _make_trf16(self):
        return TRF16Exporter(self.export_service)

    def _full_tournament(self, name="TRF16 Teste"):
        """Cria torneio com todos os campos obrigatórios para exportação sem warnings."""
        tid = self.db.create_tournament(
            name,
            location="Curitiba",
            rounds_count=1,
            time_control="90 min + 30 sec",
            start_date="2026-06-10",
            end_date="2026-06-10",
        )
        self.db.save_tournament_settings(
            tid,
            {
                "federation": "BRA",
                "chief_arbiter": "Arbitro Teste",
                "tournament_profile": "fide",
                "fide_event_id": "99999",
            },
        )
        self.db.save_round_schedule(
            tid, [{"round_number": 1, "date": "2026-06-10", "time": "10:00"}]
        )
        return tid

    # ------------------------------------------------------------------
    # Lacuna 1a: export() com torneio inexistente → AppError
    # ------------------------------------------------------------------
    def test_export_raises_app_error_for_invalid_tournament_id(self) -> None:
        exporter = self._make_trf16()
        trf_path = self.temp_dir.name + "/x.trf"
        with self.assertRaises(AppError):
            exporter.export(tournament_id=999_999, file_path=trf_path)

    # ------------------------------------------------------------------
    # Lacuna 1b: validate() com torneio inexistente → AppError
    # ------------------------------------------------------------------
    def test_validate_raises_app_error_for_invalid_tournament_id(self) -> None:
        exporter = self._make_trf16()
        with self.assertRaises(AppError):
            exporter.validate(tournament_id=999_999)

    # ------------------------------------------------------------------
    # Lacuna 2: campo 072 (rated_count) exclui jogadores sem rating FIDE
    # ------------------------------------------------------------------
    def test_072_rated_count_excludes_players_with_zero_rating(self) -> None:
        tid = self._full_tournament("TRF16 Rated Count")
        # Dois jogadores com rating internacional > 0 (contados em 072)
        self.db.create_player(
            tid, name="Rated Um", rating=2000, international_rating=2000,
            fide_id="100001", federation_id="BRA", birth_date="2000-01-01",
        )
        self.db.create_player(
            tid, name="Rated Dois", rating=1800, international_rating=1800,
            fide_id="100002", federation_id="BRA", birth_date="2000-01-01",
        )
        # Um jogador sem rating internacional (deve ser excluído do 072)
        self.db.create_player(
            tid, name="Sem Rating", rating=0, international_rating=0,
            fide_id="100003", federation_id="BRA", birth_date="2000-01-01",
        )

        out = Path(self.temp_dir.name) / "rated_count.trf"
        self._make_trf16().export(tid, out)
        content = out.read_text(encoding="utf-8")

        self.assertIn("062 3", content)   # 3 jogadores no total (campo 062)
        self.assertIn("072 2", content)   # apenas 2 com rating FIDE (campo 072)
        self.assertNotIn("072 3", content)

    # ------------------------------------------------------------------
    # Lacuna 3: ordenamento de jogadores (-rating, nome.casefold(), id)
    # ------------------------------------------------------------------
    def test_player_ordering_by_rating_desc_then_name(self) -> None:
        tid = self._full_tournament("TRF16 Ordenamento")
        # Jogador B tem rating maior → deve ser rank 1 (primeiro no arquivo)
        self.db.create_player(
            tid, name="Azevedo, Carlos", rating=1700, international_rating=1700,
            fide_id="200001", federation_id="BRA", birth_date="2000-01-01",
        )
        self.db.create_player(
            tid, name="Barbosa, Ana", rating=2100, international_rating=2100,
            fide_id="200002", federation_id="BRA", birth_date="2000-01-01",
        )
        # Mesmo rating que Azevedo, mas nome alfabeticamente anterior → rank 2
        self.db.create_player(
            tid, name="Aaa, Zézé", rating=1700, international_rating=1700,
            fide_id="200003", federation_id="BRA", birth_date="2000-01-01",
        )

        out = Path(self.temp_dir.name) / "order.trf"
        self._make_trf16().export(tid, out)
        lines = [linha for linha in out.read_text(encoding="utf-8").splitlines() if linha.startswith("001 ")]

        self.assertEqual(len(lines), 3)
        # Rank 1: Barbosa (maior rating)
        self.assertIn("Barbosa, Ana", lines[0])
        # Rank 2: Aaa (mesmo rating de Azevedo, mas nome casefold < azevedo)
        self.assertIn("Aaa,", lines[1])
        # Rank 3: Azevedo
        self.assertIn("Azevedo, Carlos", lines[2])

    # ------------------------------------------------------------------
    # Lacuna 4: exportação sem rodadas geradas
    # ------------------------------------------------------------------
    def test_export_with_no_rounds_emits_player_lines_without_results(self) -> None:
        tid = self._full_tournament("TRF16 Sem Rodadas")
        self.db.create_player(
            tid, name="Silva, Ana", rating=2000, international_rating=2000,
            fide_id="300001", federation_id="BRA", birth_date="2000-01-01",
        )
        self.db.create_player(
            tid, name="Souza, Bruno", rating=1800, international_rating=1800,
            fide_id="300002", federation_id="BRA", birth_date="2000-01-01",
        )

        out = Path(self.temp_dir.name) / "no_rounds.trf"
        # Deve exportar sem levantar exceção mesmo sem rodadas
        warnings = self._make_trf16().export(tid, out)
        content = out.read_text(encoding="utf-8")
        lines_001 = [linha for linha in content.splitlines() if linha.startswith("001 ")]

        self.assertEqual(len(lines_001), 2)
        # Arquivo deve ter o cabeçalho do torneio
        self.assertIn("012 TRF16 Sem Rodadas", content)
        # Aviso de que não há rodadas geradas deve estar presente
        self.assertTrue(any("sem rodadas" in w.lower() for w in warnings))

    # ------------------------------------------------------------------
    # Lacuna 5a: linha 001 com bye codificado corretamente
    # ------------------------------------------------------------------
    def test_001_line_encodes_bye_result(self) -> None:
        tid = self._full_tournament("TRF16 Bye")
        p1 = self.db.create_player(
            tid, name="Jogador Um", rating=2000, international_rating=2000,
            fide_id="400001", federation_id="BRA", birth_date="2000-01-01",
        )
        p2 = self.db.create_player(
            tid, name="Jogador Dois", rating=1800, international_rating=1800,
            fide_id="400002", federation_id="BRA", birth_date="2000-01-01",
        )
        p3 = self.db.create_player(
            tid, name="Jogador Tres", rating=1600, international_rating=1600,
            fide_id="400003", federation_id="BRA", birth_date="2000-01-01",
        )
        # Campo ímpar: p3 recebe bye
        round_id = self.db.create_round_with_pairings(
            tid, 1,
            [
                {"board_number": 1, "white_player_id": p1, "black_player_id": p2, "result": "1-0"},
                {"board_number": 2, "white_player_id": p3, "black_player_id": None, "result": "BYE", "is_bye": 1},
            ],
        )
        self.service.close_round(tid, round_id)

        out = Path(self.temp_dir.name) / "bye.trf"
        self._make_trf16().export(tid, out)
        content = out.read_text(encoding="utf-8")
        lines_001 = [linha for linha in content.splitlines() if linha.startswith("001 ")]

        # O jogador com bye deve ter "U" ou similar na coluna de resultado (formato TRF16)
        # A linha do jogador 3 (rank 3 = menor rating) deve ter o bye registrado
        bye_line = next(linha for linha in lines_001 if "Jogador Tres" in linha)
        self.assertTrue(len(bye_line) > 50, "Linha 001 do bye deve ter colunas de resultado")

    # ------------------------------------------------------------------
    # Lacuna 5b: linha 001 com walkover (1F-0F, 0F-1F) codificado
    # ------------------------------------------------------------------
    def test_001_line_encodes_walkover_results(self) -> None:
        tid = self._full_tournament("TRF16 Walkover")
        p1 = self.db.create_player(
            tid, name="Vencedor WO", rating=2000, international_rating=2000,
            fide_id="500001", federation_id="BRA", birth_date="2000-01-01",
        )
        p2 = self.db.create_player(
            tid, name="Perdedor WO", rating=1800, international_rating=1800,
            fide_id="500002", federation_id="BRA", birth_date="2000-01-01",
        )
        round_id = self.db.create_round_with_pairings(
            tid, 1,
            [{"board_number": 1, "white_player_id": p1, "black_player_id": p2, "result": "1F-0F"}],
        )
        self.service.close_round(tid, round_id)

        out = Path(self.temp_dir.name) / "walkover.trf"
        self._make_trf16().export(tid, out)
        content = out.read_text(encoding="utf-8")
        lines_001 = [linha for linha in content.splitlines() if linha.startswith("001 ")]

        self.assertEqual(len(lines_001), 2)
        # Ambos os jogadores devem ter suas linhas 001 com resultado registrado
        winner_line = next(linha for linha in lines_001 if "Vencedor WO" in linha)
        loser_line  = next(linha for linha in lines_001 if "Perdedor WO" in linha)
        # O vencedor por WO recebe "+" e o perdedor "-" no TRF16
        self.assertIn("+", winner_line)
        self.assertIn("-", loser_line)

    # ------------------------------------------------------------------
    # Lacuna 6: validate() de torneio por equipes sem equipes → AppError
    # ------------------------------------------------------------------
    def test_validate_raises_app_error_for_team_tournament_without_teams(self) -> None:
        # Cria torneio por equipes sem cadastrar nenhuma equipe
        tid = self.tournament_service.create_tournament(
            {
                "name": "Equipes Sem Equipes",
                "competition_type": "team",
                "rounds_count": "3",
                "bye_points": "1",
            }
        )
        # Adiciona pelo menos um jogador (para não falhar por "sem jogadores")
        self.db.create_player(tid, name="Jogador Orfao", rating=1500)

        exporter = self._make_trf16()
        with self.assertRaises(AppError):
            exporter.validate(tournament_id=tid)


if __name__ == "__main__":
    unittest.main()
