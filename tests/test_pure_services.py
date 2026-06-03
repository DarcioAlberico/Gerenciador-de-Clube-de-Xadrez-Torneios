"""Testes unitários de serviços puros/utilitários antes sem cobertura.

Cobre três módulos que estavam sem testes diretos:
- ``chess_validation`` (validação de FEN e parsing de PGN, usado em LibraryService);
- ``list_layouts`` (normalização/serialização de colunas configuráveis);
- ``integration_service`` (busca de rating no Lichess/Chess.com, com rede mockada).
"""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import chess

from src.services.chess_validation import ChessValidationService
from src.services.constants import AppError
from src.services.export_service import (
    REGISTRATION_FORM_QUESTIONS,
    ExportService,
    ImportService,
)
from src.services.integration_service import IntegrationService
from src.services.list_layouts import (
    DEFAULT_STANDINGS_COLUMNS,
    normalize_column_specs,
    normalize_columns,
    resolve_column_specs,
    resolve_columns,
    serialize_columns,
)
from src.services.report_engine import ReportEngine

START_FEN = chess.STARTING_FEN


class ChessValidationFenTest(unittest.TestCase):
    def test_valid_start_position_returns_full_contract(self) -> None:
        result = ChessValidationService.validate_fen(START_FEN)
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_fen"], START_FEN)
        self.assertEqual(result["side_to_move"], "white")
        self.assertEqual(result["legal_moves_count"], 20)
        self.assertEqual(result["material_balance_cp"], 0)
        self.assertFalse(result["is_check"])
        self.assertFalse(result["is_checkmate"])
        self.assertFalse(result["is_stalemate"])
        self.assertEqual(result["status_code"], 0)
        # contrato de chaves estável (consumido pela UI/biblioteca)
        self.assertEqual(
            set(result),
            {
                "valid", "fen", "normalized_fen", "side_to_move", "legal_moves_count",
                "material_balance_cp", "is_check", "is_checkmate", "is_stalemate",
                "status_code", "message",
            },
        )

    def test_surrounding_whitespace_is_stripped(self) -> None:
        result = ChessValidationService.validate_fen(f"  {START_FEN}  ")
        self.assertEqual(result["fen"], START_FEN)
        self.assertEqual(result["normalized_fen"], START_FEN)

    def test_empty_fen_raises(self) -> None:
        for value in ("", "   ", None):  # type: ignore[arg-type]
            with self.assertRaises(AppError) as ctx:
                ChessValidationService.validate_fen(value)  # type: ignore[arg-type]
            self.assertIn("Informe uma FEN", str(ctx.exception))

    def test_malformed_fen_raises_format_error(self) -> None:
        with self.assertRaises(AppError) as ctx:
            ChessValidationService.validate_fen("this is not a fen")
        self.assertIn("mal formatada", str(ctx.exception))

    def test_structurally_valid_but_illegal_position_raises(self) -> None:
        # Tabuleiro vazio: FEN sintaticamente válida, posição ilegal (sem reis).
        with self.assertRaises(AppError) as ctx:
            ChessValidationService.validate_fen("8/8/8/8/8/8/8/8 w - - 0 1")
        self.assertIn("inválida", str(ctx.exception).lower())

    def test_checkmate_position_flags_and_material(self) -> None:
        result = ChessValidationService.validate_fen("7k/5KQ1/8/8/8/8/8/8 b - - 0 1")
        self.assertEqual(result["side_to_move"], "black")
        self.assertTrue(result["is_check"])
        self.assertTrue(result["is_checkmate"])
        self.assertFalse(result["is_stalemate"])
        # vantagem branca = dama (900cp), medida na perspectiva das brancas
        self.assertEqual(result["material_balance_cp"], 900)

    def test_stalemate_position_flags(self) -> None:
        result = ChessValidationService.validate_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertEqual(result["side_to_move"], "black")
        self.assertFalse(result["is_check"])
        self.assertFalse(result["is_checkmate"])
        self.assertTrue(result["is_stalemate"])

    def test_check_without_mate(self) -> None:
        result = ChessValidationService.validate_fen("4k3/8/8/8/8/8/4R3/4K3 b - - 0 1")
        self.assertTrue(result["is_check"])
        self.assertFalse(result["is_checkmate"])
        self.assertFalse(result["is_stalemate"])


class ChessValidationPgnTest(unittest.TestCase):
    GOOD_PGN = (
        '[Event "T"]\n[Result "1-0"]\n\n'
        "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n"
    )

    def test_valid_pgn_returns_moves_and_metadata(self) -> None:
        result = ChessValidationService.parse_pgn(self.GOOD_PGN)
        self.assertTrue(result["valid"])
        self.assertEqual(result["game_count"], 1)
        game = result["games"][0]
        self.assertEqual(game["result"], "1-0")
        self.assertEqual(game["headers"]["Event"], "T")
        self.assertEqual(game["ply_count"], 7)
        self.assertEqual(game["parse_status"], "valid")
        self.assertEqual(game["errors"], [])
        first = game["moves"][0]
        self.assertEqual(first["ply"], 1)
        self.assertEqual(first["san"], "e4")
        self.assertEqual(first["uci"], "e2e4")
        self.assertNotEqual(first["fen_after"], game["initial_fen"])
        self.assertEqual(game["initial_fen"], START_FEN)

    def test_missing_result_header_defaults_to_star(self) -> None:
        result = ChessValidationService.parse_pgn("1. e4 e5 *")
        self.assertEqual(result["games"][0]["result"], "*")

    def test_multiple_games_are_counted(self) -> None:
        two = self.GOOD_PGN + "\n\n" + '[Event "T2"]\n\n1. d4 d5 *\n'
        result = ChessValidationService.parse_pgn(two)
        self.assertEqual(result["game_count"], 2)

    def test_empty_pgn_raises(self) -> None:
        for value in ("", "   ", None):  # type: ignore[arg-type]
            with self.assertRaises(AppError) as ctx:
                ChessValidationService.parse_pgn(value)  # type: ignore[arg-type]
            self.assertIn("Informe um PGN", str(ctx.exception))

    def test_pgn_without_any_game_raises(self) -> None:
        # Linhas iniciadas por '%' são ignoradas pelo parser → nenhum jogo.
        with self.assertRaises(AppError) as ctx:
            ChessValidationService.parse_pgn("%apenas um comentario\n%outro\n")
        self.assertIn("vazio ou mal formatado", str(ctx.exception))

    def test_illegal_move_strict_raises(self) -> None:
        with self.assertRaises(AppError) as ctx:
            ChessValidationService.parse_pgn('[Event "Bad"]\n\n1. e5 1-0\n', strict=True)
        self.assertIn("erros", str(ctx.exception))

    def test_illegal_move_non_strict_warns(self) -> None:
        result = ChessValidationService.parse_pgn('[Event "Bad"]\n\n1. e5 1-0\n', strict=False)
        self.assertFalse(result["valid"])
        self.assertEqual(result["game_count"], 1)
        game = result["games"][0]
        self.assertTrue(game["errors"])
        self.assertEqual(game["parse_status"], "warning")


class ListLayoutsTest(unittest.TestCase):
    def test_unknown_report_key_returns_empty(self) -> None:
        self.assertEqual(normalize_column_specs(["name"], "bogus"), [])
        self.assertEqual(resolve_column_specs([], "bogus"), [])
        self.assertEqual(resolve_columns([], "bogus"), [])

    def test_blank_and_non_list_inputs_return_empty(self) -> None:
        self.assertEqual(normalize_column_specs("", "standings"), [])
        self.assertEqual(normalize_column_specs("   ", "standings"), [])
        self.assertEqual(normalize_column_specs("name,points", "standings"), [])  # JSON inválido
        self.assertEqual(normalize_column_specs({"key": "name"}, "standings"), [])
        self.assertEqual(normalize_column_specs(123, "standings"), [])

    def test_list_of_strings_dedup_and_filter(self) -> None:
        specs = normalize_column_specs(["name", "points", "name", "bogus"], "standings")
        self.assertEqual(specs, [{"key": "name", "width": 0}, {"key": "points", "width": 0}])
        self.assertEqual(normalize_columns(["name", "points", "bogus"], "standings"), ["name", "points"])

    def test_dict_widths_clamped_and_unknown_dropped(self) -> None:
        specs = normalize_column_specs(
            [{"key": "name", "width": 50}, {"key": "points", "width": -3}, {"key": "x"}],
            "standings",
        )
        self.assertEqual(specs, [{"key": "name", "width": 50}, {"key": "points", "width": 0}])

    def test_invalid_width_falls_back_to_zero(self) -> None:
        specs = normalize_column_specs([{"key": "buchholz", "width": "abc"}], "standings")
        self.assertEqual(specs, [{"key": "buchholz", "width": 0}])

    def test_json_string_input_is_parsed(self) -> None:
        raw = json.dumps([{"key": "name", "width": 20}])
        self.assertEqual(normalize_column_specs(raw, "standings"), [{"key": "name", "width": 20}])

    def test_resolve_uses_defaults_when_empty(self) -> None:
        self.assertEqual(resolve_columns([], "standings"), DEFAULT_STANDINGS_COLUMNS)
        self.assertEqual(
            resolve_column_specs([], "standings"),
            [{"key": key, "width": 0} for key in DEFAULT_STANDINGS_COLUMNS],
        )

    def test_resolve_uses_selection_when_present(self) -> None:
        self.assertEqual(
            resolve_column_specs([{"key": "points", "width": 40}], "standings"),
            [{"key": "points", "width": 40}],
        )
        self.assertEqual(resolve_columns(["points", "name"], "standings"), ["points", "name"])

    def test_serialize_columns_from_keys_and_dicts(self) -> None:
        out = serialize_columns(["name", "points"])
        self.assertEqual(
            json.loads(out),
            [{"key": "name", "width": 0}, {"key": "points", "width": 0}],
        )
        # largura inválida em dict -> 0; chave vazia descartada
        out2 = serialize_columns(
            [{"key": "name", "width": 30}, {"key": "", "width": 5}, "points", {"key": "wins", "width": "xx"}]
        )
        self.assertEqual(
            json.loads(out2),
            [{"key": "name", "width": 30}, {"key": "points", "width": 0}, {"key": "wins", "width": 0}],
        )

    def test_serialize_then_normalize_round_trip(self) -> None:
        raw = serialize_columns([{"key": "name", "width": 15}, {"key": "points", "width": 0}])
        self.assertEqual(
            normalize_column_specs(raw, "standings"),
            [{"key": "name", "width": 15}, {"key": "points", "width": 0}],
        )


def _json_response(payload: dict) -> mock.MagicMock:
    """Constrói um context manager mockado para urlopen, com .read() -> bytes JSON."""
    cm = mock.MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    return cm


class IntegrationServiceTest(unittest.TestCase):
    PATCH = "src.services.integration_service.urllib.request.urlopen"

    def test_lichess_success_parses_blitz_and_rapid(self) -> None:
        payload = {"perfs": {"blitz": {"rating": 1800}, "rapid": {"rating": 1700}}}
        with mock.patch(self.PATCH, return_value=_json_response(payload)):
            ratings = IntegrationService().fetch_lichess_ratings("alice")
        self.assertEqual(ratings, {"blitz": 1800, "rapid": 1700})

    def test_lichess_missing_perfs_returns_zeros(self) -> None:
        with mock.patch(self.PATCH, return_value=_json_response({})):
            ratings = IntegrationService().fetch_lichess_ratings("alice")
        self.assertEqual(ratings, {"blitz": 0, "rapid": 0})

    def test_lichess_http_error_returns_zeros(self) -> None:
        err = urllib.error.HTTPError("u", 404, "Not Found", {}, None)  # type: ignore[arg-type]
        with mock.patch(self.PATCH, side_effect=err):
            ratings = IntegrationService().fetch_lichess_ratings("ghost")
        self.assertEqual(ratings, {"blitz": 0, "rapid": 0})

    def test_lichess_generic_error_returns_zeros(self) -> None:
        with mock.patch(self.PATCH, side_effect=ValueError("boom")):
            ratings = IntegrationService().fetch_lichess_ratings("alice")
        self.assertEqual(ratings, {"blitz": 0, "rapid": 0})

    def test_chesscom_success_parses_blitz_and_rapid(self) -> None:
        payload = {
            "chess_blitz": {"last": {"rating": 1500}},
            "chess_rapid": {"last": {"rating": 1450}},
        }
        with mock.patch(self.PATCH, return_value=_json_response(payload)):
            ratings = IntegrationService().fetch_chesscom_ratings("bob")
        self.assertEqual(ratings, {"blitz": 1500, "rapid": 1450})

    def test_chesscom_missing_fields_returns_zeros(self) -> None:
        with mock.patch(self.PATCH, return_value=_json_response({})):
            ratings = IntegrationService().fetch_chesscom_ratings("bob")
        self.assertEqual(ratings, {"blitz": 0, "rapid": 0})

    def test_chesscom_http_error_returns_zeros(self) -> None:
        err = urllib.error.HTTPError("u", 500, "Server Error", {}, None)  # type: ignore[arg-type]
        with mock.patch(self.PATCH, side_effect=err):
            ratings = IntegrationService().fetch_chesscom_ratings("bob")
        self.assertEqual(ratings, {"blitz": 0, "rapid": 0})

    def test_chesscom_generic_error_returns_zeros(self) -> None:
        with mock.patch(self.PATCH, side_effect=ValueError("boom")):
            ratings = IntegrationService().fetch_chesscom_ratings("bob")
        self.assertEqual(ratings, {"blitz": 0, "rapid": 0})


class _FakeFinance:
    """Stub de FinanceService: devolve listas fixas, sem banco."""

    def __init__(self, payments: list[dict], transactions: list[dict]) -> None:
        self._payments = payments
        self._transactions = transactions

    def payments_report(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        return self._payments

    def list_transactions(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        return self._transactions


class ReportEngineDreTest(unittest.TestCase):
    def _engine(self, payments: list[dict], transactions: list[dict]) -> ReportEngine:
        return ReportEngine(db=None, finance_service=_FakeFinance(payments, transactions))  # type: ignore[arg-type]

    def test_calculate_dre_aggregates_income_and_expense(self) -> None:
        payments = [
            {"amount": 100.0, "effective_status": "paid"},
            {"amount": 50.0, "effective_status": "paid"},
            {"amount": 30.0, "effective_status": "pending"},  # ignorado
        ]
        transactions = [
            {"type": "income", "category": "Doacoes", "amount": 200.0},
            {"type": "income", "category": "Doacoes", "amount": 50.0},  # acumula
            {"type": "expense", "category": "  Aluguel  ", "amount": 80.0},  # strip
            {"type": "expense", "category": "", "amount": 20.0},  # -> Geral
            {"type": "income", "amount": 10.0},  # categoria ausente -> Geral
        ]
        dre = self._engine(payments, transactions).calculate_dre("2026-01-01", "2026-12-31")
        self.assertEqual(
            dre["income_by_category"],
            {"Mensalidades (Pagamentos dos Sócios)": 150.0, "Doacoes": 250.0, "Geral": 10.0},
        )
        self.assertEqual(dre["expense_by_category"], {"Aluguel": 80.0, "Geral": 20.0})
        self.assertEqual(dre["total_income"], 410.0)
        self.assertEqual(dre["total_expense"], 100.0)
        self.assertEqual(dre["net_balance"], 310.0)

    def test_calculate_dre_without_paid_payments_omits_mensalidades(self) -> None:
        dre = self._engine([{"amount": 30.0, "effective_status": "pending"}], []).calculate_dre("", "")
        self.assertNotIn("Mensalidades (Pagamentos dos Sócios)", dre["income_by_category"])
        self.assertEqual(dre["total_income"], 0.0)
        self.assertEqual(dre["total_expense"], 0.0)
        self.assertEqual(dre["net_balance"], 0.0)

    def test_generate_dre_report_writes_pdf_and_forces_suffix(self) -> None:
        engine = self._engine(
            [{"amount": 100.0, "effective_status": "paid"}],
            [{"type": "expense", "category": "Aluguel", "amount": 40.0}],
        )
        with tempfile.TemporaryDirectory() as tmp:
            requested = Path(tmp) / "dre.txt"
            engine.generate_dre_report("2026-01-01", "2026-12-31", requested)
            pdf = requested.with_suffix(".pdf")
            self.assertTrue(pdf.exists())
            self.assertGreater(pdf.stat().st_size, 0)


class _RecordingDB:
    """DB falso: registra chamadas de create_player, sem banco real."""

    def __init__(self) -> None:
        self.players: list[dict] = []

    def create_player(self, **kwargs: object) -> int:
        self.players.append(kwargs)
        return len(self.players)


class ImportPlayerNameTest(unittest.TestCase):
    """Regressao: CSV do Google Forms usa cabecalho 'NOME COMPLETO'."""

    def _import(self, rows: list[tuple[int, dict]]) -> tuple[_RecordingDB, dict]:
        db = _RecordingDB()
        svc = ImportService(db)  # type: ignore[arg-type]
        result = svc._import_player_rows(1, rows, Path("forms.csv"))
        return db, result

    def test_google_forms_nome_completo_header_is_recognized(self) -> None:
        rows = [(
            2,
            {
                "Carimbo de data/hora": "29/04/2026 12:57:31",
                "ID LBX ( caso nao possua... )": "624649",
                "NOME COMPLETO": "Alisson Carlos dos Santos Silva ",
                "Participará de qual torneio? ": "TORNEIO SUB 15",
            },
        )]
        db, result = self._import(rows)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(db.players[0]["name"], "Alisson Carlos dos Santos Silva")

    def test_legacy_and_alias_headers_still_work(self) -> None:
        for header in ("nome", "Name", "Jogador", "Nome Completo", "Atleta", "Participante"):
            db, result = self._import([(2, {header: "Fulano de Tal "})])
            self.assertEqual(result["imported"], 1, header)
            self.assertEqual(db.players[0]["name"], "Fulano de Tal")

    def test_truly_empty_name_still_errors(self) -> None:
        db, result = self._import([(2, {"NOME COMPLETO": "   ", "Telefone": "123"})])
        self.assertEqual(result["imported"], 0)
        self.assertEqual(result["errors"], ["Linha 2: nome vazio."])


class _FakeImportDB:
    """DB falso para o assistente de importacao (REG-02): torneio fixo, sem
    jogadores previos, app_settings em memoria."""

    def __init__(self) -> None:
        self.players: list[dict] = []
        self.settings: dict[str, str] = {}

    def get_tournament(self, tournament_id: int) -> dict:
        return {"id": tournament_id, "name": "Torneio Teste"}

    def list_players(self, tournament_id: int, active_only: bool = False) -> list[dict]:
        return list(self.players)

    def create_player(self, **kwargs: object) -> int:
        self.players.append(kwargs)
        return len(self.players)

    def get_app_settings(self) -> dict:
        return dict(self.settings)

    def save_app_settings(self, settings: dict) -> None:
        self.settings.update({str(k): str(v) for k, v in settings.items()})


def _write_csv(directory: str, name: str, header: list[str], rows: list[list[str]]) -> Path:
    path = Path(directory) / name
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


class InspectSourceTest(unittest.TestCase):
    """REG-02: leitura e palpite de mapeamento de planilhas nao padronizadas."""

    HEADER = ["Carimbo", "NOME COMPLETO", "Idade", "ELO", "Clube / Cidade", "ID FIDE"]
    ROWS = [["2026-04-29", "Joao Silva", "12", "1500", "Clube A", "12345"]]

    def _service(self) -> ImportService:
        return ImportService(_FakeImportDB())  # type: ignore[arg-type]

    def test_inspect_returns_headers_sample_and_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_csv(tmp, "forms.csv", self.HEADER, self.ROWS)
            result = self._service().inspect_source(path)

        self.assertEqual(result["headers"], self.HEADER)
        self.assertEqual(result["total_rows"], 1)
        self.assertEqual(result["sample_rows"][0]["NOME COMPLETO"], "Joao Silva")
        suggestion = result["suggested_mapping"]
        self.assertEqual(suggestion["name"], "NOME COMPLETO")
        self.assertEqual(suggestion["age"], "Idade")
        self.assertEqual(suggestion["rating"], "ELO")
        self.assertEqual(suggestion["club"], "Clube / Cidade")
        self.assertEqual(suggestion["fide_id"], "ID FIDE")
        self.assertEqual(suggestion["birth_date"], "")
        # cada campo canonico aparece no palpite
        self.assertEqual({field["key"] for field in result["fields"]}, set(suggestion))

    def test_suggestion_does_not_reuse_a_column(self) -> None:
        result = self._service()._suggest_mapping(["Nome", "Nome do responsavel"])
        chosen = [value for value in result.values() if value]
        self.assertEqual(len(chosen), len(set(chosen)))


class ApplyMappingTest(unittest.TestCase):
    def _service(self) -> ImportService:
        return ImportService(_FakeImportDB())  # type: ignore[arg-type]

    def test_age_is_converted_to_birth_year(self) -> None:
        from datetime import date

        mapped = self._service()._apply_mapping(
            {"col_idade": "12"}, {"name": "", "age": "col_idade"}
        )
        self.assertEqual(mapped["birth_date"], str(date.today().year - 12))
        self.assertNotIn("age", mapped)

    def test_existing_birth_date_wins_over_age(self) -> None:
        mapped = self._service()._apply_mapping(
            {"a": "30", "b": "2000-01-01"},
            {"age": "a", "birth_date": "b"},
        )
        self.assertEqual(mapped["birth_date"], "2000-01-01")

    def test_surname_comma_name_is_split(self) -> None:
        mapped = self._service()._apply_mapping({"n": "Silva, Joao"}, {"name": "n"})
        self.assertEqual(mapped["name"], "Joao Silva")
        self.assertEqual(mapped["surname"], "Silva")
        self.assertEqual(mapped["given_name"], "Joao")

    def test_invalid_age_is_ignored(self) -> None:
        mapped = self._service()._apply_mapping({"a": "abc"}, {"age": "a"})
        self.assertNotIn("birth_date", mapped)
        self.assertEqual(ImportService._birth_year_from_age("999"), "")


class MappedRegistrationImportTest(unittest.TestCase):
    HEADER = ["Carimbo", "NOME COMPLETO", "Idade", "ELO", "Clube / Cidade", "ID FIDE"]
    ROWS = [
        ["2026-04-29", "Joao Silva", "12", "1500", "Clube A", "12345"],
        ["2026-04-29", "Maria Souza", "", "1600", "Clube B", "67890"],
        ["2026-04-29", "", "10", "1200", "Clube C", ""],  # nome vazio -> erro
    ]

    def test_preview_and_import_apply_mapping(self) -> None:
        from datetime import date

        db = _FakeImportDB()
        service = ImportService(db)  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_csv(tmp, "forms.csv", self.HEADER, self.ROWS)
            mapping = service.inspect_source(path)["suggested_mapping"]

            preview = service.preview_mapped_registrations(1, path, mapping)
            self.assertEqual(preview["total"], 3)
            self.assertEqual(preview["ready"], 2)
            self.assertEqual(preview["error"], 1)

            result = service.import_mapped_registrations(1, path, mapping)

        self.assertEqual(result["imported"], 2)
        self.assertEqual(db.players[0]["name"], "Joao Silva")
        self.assertEqual(db.players[0]["rating"], 1500)
        self.assertEqual(db.players[0]["club"], "Clube A")
        self.assertEqual(db.players[0]["fide_id"], "12345")
        self.assertEqual(db.players[0]["birth_date"], str(date.today().year - 12))

    def test_missing_name_mapping_raises(self) -> None:
        service = ImportService(_FakeImportDB())  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_csv(tmp, "forms.csv", self.HEADER, self.ROWS)
            with self.assertRaises(AppError):
                service.preview_mapped_registrations(1, path, {"name": ""})


class MappingProfilesTest(unittest.TestCase):
    def test_save_list_and_delete_profile(self) -> None:
        db = _FakeImportDB()
        service = ImportService(db)  # type: ignore[arg-type]
        service.save_mapping_profile("Forms 2026", {"name": "NOME", "rating": "ELO", "age": ""})
        profiles = service.list_mapping_profiles()
        self.assertEqual(profiles["Forms 2026"], {"name": "NOME", "rating": "ELO"})  # vazio descartado

        service.delete_mapping_profile("Forms 2026")
        self.assertEqual(service.list_mapping_profiles(), {})

    def test_blank_name_raises_and_corrupt_value_is_safe(self) -> None:
        db = _FakeImportDB()
        service = ImportService(db)  # type: ignore[arg-type]
        with self.assertRaises(AppError):
            service.save_mapping_profile("  ", {"name": "NOME"})
        db.settings["import_mapping_profiles"] = "not-json"
        self.assertEqual(service.list_mapping_profiles(), {})


class RegistrationFormTest(unittest.TestCase):
    """REG-01: gerador de formulario padronizado (Google Apps Script + JSON)."""

    def _export_service(self, db: object) -> ExportService:
        return ExportService(db, None)  # type: ignore[arg-type]

    def test_generates_script_and_definition(self) -> None:
        db = _FakeImportDB()
        with tempfile.TemporaryDirectory() as tmp:
            requested = Path(tmp) / "formulario.txt"
            result = self._export_service(db).export_registration_form(requested, tournament_id=1)
            script_path = Path(result["script_path"])
            definition_path = Path(result["definition_path"])

            self.assertTrue(script_path.exists())
            self.assertEqual(script_path.suffix, ".gs")
            script = script_path.read_text(encoding="utf-8")
            self.assertIn("FormApp.create('Inscricao - Torneio Teste')", script)
            self.assertIn("Nome completo do jogador", script)
            self.assertIn("addDateItem", script)
            self.assertIn("addMultipleChoiceItem", script)

            definition = json.loads(definition_path.read_text(encoding="utf-8"))
            self.assertEqual(definition["title"], "Inscricao - Torneio Teste")
            self.assertEqual(len(definition["questions"]), 11)

    def test_form_titles_import_without_manual_mapping(self) -> None:
        row = {}
        samples = {
            "Nome completo do jogador": "Ana Silva",
            "Data de nascimento": "2012-05-10",
            "Sexo": "F",
            "Clube/Cidade": "Clube A",
            "Categoria": "ABS",
            "Rating": "1500",
            "FIDE ID": "111",
            "CBX ID": "222",
            "LBX ID": "333",
        }
        for question in REGISTRATION_FORM_QUESTIONS:
            row[question["title"]] = samples.get(question["title"], "")

        parsed = ImportService(_FakeImportDB())._online_registration_payload(row)  # type: ignore[arg-type]
        self.assertEqual(parsed["errors"], [])
        payload = parsed["payload"]
        self.assertEqual(payload["name"], "Ana Silva")
        self.assertEqual(payload["rating"], 1500)
        self.assertEqual(payload["club"], "Clube A")
        self.assertEqual(payload["fide_id"], "111")
        self.assertEqual(payload["cbx_id"], "222")
        self.assertEqual(payload["lbx_id"], "333")
        self.assertEqual(payload["sex"], "F")


class _Exec:
    def __init__(self, value: dict) -> None:
        self._value = value

    def execute(self) -> dict:
        return self._value


class _FakeFormsApi:
    def __init__(self) -> None:
        self.created_body: dict | None = None
        self.batch: dict | None = None
        self.got: str | None = None

    def create(self, body: dict) -> _Exec:
        self.created_body = body
        return _Exec({"formId": "FID"})

    def batchUpdate(self, formId: str, body: dict) -> _Exec:  # noqa: N803 (API kw)
        self.batch = {"formId": formId, "body": body}
        return _Exec({})

    def get(self, formId: str) -> _Exec:  # noqa: N803 (API kw)
        self.got = formId
        return _Exec(
            {"responderUri": "https://docs.google.com/forms/d/FID/viewform", "formId": formId}
        )


class _FakeFormsService:
    def __init__(self) -> None:
        self.api = _FakeFormsApi()

    def forms(self) -> _FakeFormsApi:
        return self.api


class RegistrationPrefillTest(unittest.TestCase):
    """REG-01: link pre-preenchido do Google Forms (sem OAuth)."""

    SAMPLE = (
        "https://docs.google.com/forms/d/e/ABC123/viewform?usp=pp_url"
        "&entry.111=Copa+Exemplo&entry.222=Fulano&entry.333="
    )

    def _service(self, db: object | None = None) -> ExportService:
        return ExportService(db or _FakeImportDB(), None)  # type: ignore[arg-type]

    def test_parse_prefill_link_extracts_base_and_entries(self) -> None:
        parsed = self._service().parse_prefill_link(self.SAMPLE)
        self.assertEqual(parsed["base_url"], "https://docs.google.com/forms/d/e/ABC123/viewform")
        self.assertEqual(
            parsed["entries"],
            [("entry.111", "Copa Exemplo"), ("entry.222", "Fulano"), ("entry.333", "")],
        )

    def test_parse_prefill_link_rejects_non_google_url(self) -> None:
        with self.assertRaises(AppError):
            self._service().parse_prefill_link("https://example.com/form")

    def test_parse_prefill_link_requires_entries(self) -> None:
        with self.assertRaises(AppError):
            self._service().parse_prefill_link("https://docs.google.com/forms/d/e/ABC/viewform")

    def test_build_prefill_url_fills_tournament_and_keeps_player_blank(self) -> None:
        url = ExportService.build_registration_prefill_url(
            "https://docs.google.com/forms/d/e/ABC/viewform", "entry.111", "Copa X"
        )
        self.assertTrue(url.startswith("https://docs.google.com/forms/d/e/ABC/viewform?"))
        self.assertIn("usp=pp_url", url)
        self.assertIn("entry.111=Copa+X", url)
        self.assertNotIn("entry.222", url)  # campos do jogador ficam de fora (em branco)

    def test_build_prefill_url_without_base_raises(self) -> None:
        with self.assertRaises(AppError):
            ExportService.build_registration_prefill_url("", "entry.111", "Copa X")

    def test_save_config_and_build_url_from_tournament(self) -> None:
        db = _FakeImportDB()
        service = self._service(db)
        service.save_registration_form_config(self.SAMPLE, "entry.111")
        self.assertEqual(db.settings["registration_form_prefill_base"],
                         "https://docs.google.com/forms/d/e/ABC123/viewform")
        self.assertEqual(db.settings["registration_form_tournament_entry"], "entry.111")

        url = service.registration_prefill_url(1)  # _FakeImportDB -> nome "Torneio Teste"
        self.assertIn("entry.111=Torneio+Teste", url)

    def test_prefill_url_without_config_raises(self) -> None:
        with self.assertRaises(AppError):
            self._service().registration_prefill_url(1)


class GoogleFormsBuildRequestsTest(unittest.TestCase):
    """REG-01: payload do batchUpdate (funcao pura, sem libs Google)."""

    def test_build_requests_maps_each_question_type(self) -> None:
        from src.services.google_forms_service import GoogleFormsService

        questions = [
            {"title": "Nome", "type": "text", "required": True},
            {"title": "Nasc", "type": "date", "required": False},
            {"title": "Sexo", "type": "choice", "required": False, "choices": ["M", "F"]},
        ]
        requests = GoogleFormsService.build_form_requests(questions)
        self.assertEqual(len(requests), 4)  # 1 descricao + 3 perguntas
        self.assertIn("updateFormInfo", requests[0])

        text_q = requests[1]["createItem"]["item"]["questionItem"]["question"]
        self.assertTrue(text_q["required"])
        self.assertEqual(text_q["textQuestion"], {"paragraph": False})
        self.assertEqual(requests[1]["createItem"]["location"]["index"], 0)

        date_q = requests[2]["createItem"]["item"]["questionItem"]["question"]
        self.assertEqual(date_q["dateQuestion"], {"includeYear": True})

        choice_q = requests[3]["createItem"]["item"]["questionItem"]["question"]
        self.assertEqual(choice_q["choiceQuestion"]["type"], "RADIO")
        self.assertEqual(
            choice_q["choiceQuestion"]["options"], [{"value": "M"}, {"value": "F"}]
        )

    def test_standard_questions_produce_one_item_each(self) -> None:
        from src.services.google_forms_service import GoogleFormsService

        requests = GoogleFormsService.build_form_requests(REGISTRATION_FORM_QUESTIONS)
        self.assertEqual(len(requests), 1 + len(REGISTRATION_FORM_QUESTIONS))


class GoogleFormsCreateTest(unittest.TestCase):
    def test_create_form_orchestrates_api_calls(self) -> None:
        from src.services.google_forms_service import GoogleFormsService

        service = GoogleFormsService(_FakeImportDB())  # type: ignore[arg-type]
        fake = _FakeFormsService()
        result = service._create_form(
            fake, "Inscricao - Copa", REGISTRATION_FORM_QUESTIONS
        )

        self.assertEqual(result["form_id"], "FID")
        self.assertEqual(result["responder_url"], "https://docs.google.com/forms/d/FID/viewform")
        self.assertEqual(result["edit_url"], "https://docs.google.com/forms/d/FID/edit")
        self.assertEqual(
            fake.api.created_body,
            {"info": {"title": "Inscricao - Copa", "documentTitle": "Inscricao - Copa"}},
        )
        self.assertEqual(fake.api.batch["formId"], "FID")
        self.assertEqual(
            len(fake.api.batch["body"]["requests"]), 1 + len(REGISTRATION_FORM_QUESTIONS)
        )
        self.assertEqual(fake.api.got, "FID")


class GoogleFormsAvailabilityTest(unittest.TestCase):
    def test_unavailable_when_libraries_missing(self) -> None:
        from src.services.google_forms_service import GoogleFormsService

        service = GoogleFormsService(_FakeImportDB())  # type: ignore[arg-type]
        with mock.patch.object(GoogleFormsService, "libraries_available", return_value=False):
            self.assertFalse(service.is_configured())
            self.assertIn("Bibliotecas Google", service.unavailable_reason())
            with self.assertRaises(AppError):
                service.create_registration_form("Inscricao")

    def test_unavailable_when_secret_missing(self) -> None:
        from src.services.google_forms_service import GoogleFormsService

        db = _FakeImportDB()
        with tempfile.TemporaryDirectory() as tmp:
            db.settings["google_oauth_client_secret_path"] = str(Path(tmp) / "missing.json")
            service = GoogleFormsService(db)  # type: ignore[arg-type]
            with mock.patch.object(GoogleFormsService, "libraries_available", return_value=True):
                self.assertFalse(service.is_configured())
                self.assertIn("Credencial OAuth", service.unavailable_reason())

    def test_configured_when_libraries_and_secret_present(self) -> None:
        from src.services.google_forms_service import GoogleFormsService

        db = _FakeImportDB()
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "client_secret.json"
            secret.write_text("{}", encoding="utf-8")
            db.settings["google_oauth_client_secret_path"] = str(secret)
            service = GoogleFormsService(db)  # type: ignore[arg-type]
            with mock.patch.object(GoogleFormsService, "libraries_available", return_value=True):
                self.assertTrue(service.is_configured())
                self.assertEqual(service.unavailable_reason(), "")


if __name__ == "__main__":
    unittest.main()
