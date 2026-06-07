from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from src.core.services import (
    AppError,
)
from tests.support.core_service_base import CoreServiceTestCase


class PlayerImportTest(CoreServiceTestCase):
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

        from openpyxl import Workbook

        xlsx_path = Path(self.temp_dir.name) / "players.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["nome", "clube", "elo", "categoria", "id_fide", "id_cbx"])
        sheet.append(["Carlos Lima", "Clube C", 1610, "ABS", "666", "777"])
        workbook.save(xlsx_path)

        xlsx_result = self.import_service.import_players(self.tournament_id, xlsx_path)
        xlsx_imported = next(
            player
            for player in self.db.list_players(self.tournament_id)
            if player["name"] == "Carlos Lima"
        )

        self.assertEqual(xlsx_result["imported"], 1)
        self.assertEqual(xlsx_imported["rating"], 1610)
        self.assertEqual(xlsx_imported["fide_id"], "666")
        self.assertEqual(xlsx_imported["cbx_id"], "777")

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

    def test_online_registration_import_accepts_google_sheets_link(self) -> None:
        csv_content = (
            "Nome completo;Data de nascimento;Sexo;Clube / Cidade;Rating nacional;FIDE ID;Categoria\n"
            "Carla Forms;2007-02-03;Feminino;Curitiba;1510;333;Sub-18\n"
        ).encode("utf-8")

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            @staticmethod
            def read() -> bytes:
                return csv_content

        requested_urls: list[str] = []

        def fake_urlopen(request: object, timeout: int = 0) -> FakeResponse:
            requested_urls.append(request.full_url)
            self.assertEqual(timeout, 20)
            return FakeResponse()

        source_url = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=987"
        with mock.patch("src.services.import_service.urlopen", side_effect=fake_urlopen):
            preview = self.import_service.preview_online_registrations(self.tournament_id, source_url)
            result = self.import_service.import_online_registrations(self.tournament_id, source_url)

        imported = next(
            player
            for player in self.db.list_players(self.tournament_id, active_only=False)
            if player["name"] == "Carla Forms"
        )

        self.assertEqual(
            requested_urls[0],
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=987",
        )
        self.assertEqual(preview["ready"], 1)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(imported["club"], "Curitiba")
        self.assertEqual(imported["fide_id"], "333")
        self.assertEqual(imported["category"], "Sub-20")

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

    def test_official_rating_preview_does_not_persist_before_confirmation(self) -> None:
        matched_player_id = self.db.create_player(
            self.tournament_id,
            name="Nome antigo",
            rating=1500,
            fide_id="222",
            club="Clube antigo",
        )
        unmatched_player_id = self.db.create_player(
            self.tournament_id,
            name="Sem cadastro oficial",
            rating=1400,
            fide_id="999",
        )
        fide_csv = Path(self.temp_dir.name) / "fide_preview.csv"
        fide_csv.write_text(
            "name,fide,title,fide_rating,club\n"
            "Nome oficial,222,FM,1810,Clube novo\n",
            encoding="utf-8",
        )
        self.official_rating_service.import_official_csv(fide_csv, "FIDE", "2026-05")

        preview = self.official_rating_service.preview_tournament_player_updates(self.tournament_id)
        matched_before_confirmation = self.db.get_player(matched_player_id)
        unmatched = self.db.get_player(unmatched_player_id)

        self.assertEqual(preview["total"], 2)
        self.assertEqual(preview["matched"], 1)
        self.assertEqual(preview["changed"], 1)
        self.assertEqual(preview["unchanged"], 0)
        self.assertEqual(preview["unmatched_count"], 1)
        self.assertEqual(preview["rows"][0]["status"], "changed")
        self.assertEqual(
            preview["rows"][0]["changed_fields"],
            ["name", "club", "title", "rating", "international_rating"],
        )
        self.assertEqual(preview["unmatched"][0]["name"], unmatched["name"])
        self.assertEqual(matched_before_confirmation["name"], "Nome antigo")
        self.assertEqual(matched_before_confirmation["club"], "Clube antigo")
        self.assertEqual(matched_before_confirmation["rating"], 1500)

        result = self.official_rating_service.apply_tournament_player_updates(
            self.tournament_id,
            [matched_player_id],
        )
        matched_after_confirmation = self.db.get_player(matched_player_id)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["unmatched"], ["Sem cadastro oficial"])
        self.assertEqual(matched_after_confirmation["name"], "Nome oficial")
        self.assertEqual(matched_after_confirmation["club"], "Clube novo")
        self.assertEqual(matched_after_confirmation["title"], "FM")
        self.assertEqual(matched_after_confirmation["rating"], 1810)

    def test_official_rating_preview_confirmation_applies_only_selected_players(self) -> None:
        first_player_id = self.db.create_player(
            self.tournament_id,
            name="Primeiro antigo",
            rating=1500,
            fide_id="101",
        )
        second_player_id = self.db.create_player(
            self.tournament_id,
            name="Segundo antigo",
            rating=1400,
            fide_id="202",
        )
        fide_csv = Path(self.temp_dir.name) / "fide_selected.csv"
        fide_csv.write_text(
            "name,fide,fide_rating\n"
            "Primeiro oficial,101,1800\n"
            "Segundo oficial,202,1700\n",
            encoding="utf-8",
        )
        self.official_rating_service.import_official_csv(fide_csv, "FIDE", "2026-05")

        preview = self.official_rating_service.preview_tournament_player_updates(self.tournament_id)
        result = self.official_rating_service.apply_tournament_player_updates(
            self.tournament_id,
            [first_player_id],
        )

        self.assertEqual(preview["changed"], 2)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(self.db.get_player(first_player_id)["name"], "Primeiro oficial")
        self.assertEqual(self.db.get_player(second_player_id)["name"], "Segundo antigo")

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

    def test_lbx_online_import_combines_lists_and_updates_player_by_lbx_id(self) -> None:
        player_id = self.db.create_player(
            self.tournament_id,
            name="Nome antigo",
            rating=1200,
            lbx_id="350004",
        )
        header = "ID_No;Name;Fed;Sex;Clubnumber;ClubName;Birthday;Rtg_Nat;Fide_No;Rtg_Int;Title;Type;Status;K;\n"
        ratings = {
            "LBXstandard.php": 2348,
            "LBXrapid.php": 2438,
            "LBXblitz.php": 2436,
        }

        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.content = content.encode("utf-8")

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return self.content

        def fake_urlopen(request: object, timeout: int = 0) -> FakeResponse:
            url = str(getattr(request, "full_url", ""))
            rating = next(value for suffix, value in ratings.items() if url.endswith(suffix))
            row = f"350004;Reis, Paulo F Jatoba de Oliveira;BRA;;29;Salvador (BA);1973-01-01;{rating};350004;{rating};FM;;;30;\n"
            return FakeResponse(header + row)

        with mock.patch("src.services.rating_service.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.official_rating_service.import_lbx_lists_from_url()
        update_result = self.official_rating_service.update_tournament_players(self.tournament_id)
        player = self.db.get_player(player_id)
        official = self.db.find_latest_official_player(lbx_id="350004")

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(update_result["updated"], 1)
        self.assertEqual(official["standard_rating"], 2348)
        self.assertEqual(official["rapid_rating"], 2438)
        self.assertEqual(official["blitz_rating"], 2436)
        self.assertEqual(official["fide_id"], "")
        self.assertEqual(player["lbx_id"], "350004")
        self.assertEqual(player["fide_id"], "")
        self.assertEqual(player["national_rating"], 2348)
        self.assertEqual(player["rating"], 2348)
        self.assertEqual(player["club"], "Salvador (BA)")

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

if __name__ == "__main__":
    unittest.main()
