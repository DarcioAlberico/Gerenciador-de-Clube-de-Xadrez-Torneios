from __future__ import annotations
import csv
import html
import io
import json
import logging
import math
import re
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.services.access_export import access_driver_available, write_accdb, write_csv_bundle
from src.services.constants import *
from src.services.fide_norms import build_norm_report
from src.services.fide_rating import build_fide_report_rows
from src.services.list_layouts import STANDINGS_COLUMNS, resolve_column_specs, resolve_columns
from src.services.pairing.tiebreak_engine import legacy_engine_note
from src.services.prizes import PRIZE_KINDS, PRIZE_POLICIES, allocate_prizes
from src.services.text_ascii import headers_to_ascii
from src.services.trf_import import build_trf_rounds, parse_trf

if TYPE_CHECKING:
    from src.services.club_service import ClubService
    from src.services.member_service import MemberService, GuardianService
    from src.services.tournament_service import TournamentService, RefereeService, TeamService
    from src.services.pairing_service import PairingService
    from src.services.finance_service import FinanceService
    from src.services.event_service import EventService, CalendarService
    from src.services.education_service import TrainingService, ExerciseService, LibraryService, LearningLevelService
    from src.services.inventory_service import InventoryService
    from src.services.security_service import SecurityService
    from src.services.export_service import ExportService, ImportService, CertificateService
    from src.services.rating_service import OfficialRatingService, InternalRatingService
    from src.services.dashboard_service import DashboardService, CommunicationService

logger = logging.getLogger(__name__)


class FederationReportsMixin:
    def rating_fee_summary(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        base_specs = [
            ("FIDE", "fide_id", "international_rating", "rating_fee_fide"),
            ("CBX", "cbx_id", "national_rating", "rating_fee_cbx"),
            ("LBX", "lbx_id", "rating", "rating_fee_lbx"),
        ]
        bases = []
        for label, id_field, rating_field, fee_field in base_specs:
            identified = [player for player in players if str(player.get(id_field) or "").strip()]
            rated = [player for player in identified if int(player.get(rating_field) or 0) > 0]
            unit_fee = float(settings.get(fee_field) or 0.0)
            bases.append(
                {
                    "base": label,
                    "id_field": id_field,
                    "rating_field": rating_field,
                    "identified": len(identified),
                    "rated": len(rated),
                    "unrated": len(identified) - len(rated),
                    "unit_fee": unit_fee,
                    "subtotal": round(len(identified) * unit_fee, 2),
                }
            )
        players_with_base = sum(
            1
            for player in players
            if any(str(player.get(field) or "").strip() for field in ("fide_id", "cbx_id", "lbx_id"))
        )
        rated_players = sum(
            1
            for player in players
            if max(
                int(player.get("rating") or 0),
                int(player.get("national_rating") or 0),
                int(player.get("international_rating") or 0),
            )
            > 0
        )
        return {
            "tournament_id": int(tournament_id),
            "tournament_name": tournament["name"],
            "players_count": len(players),
            "players_with_base": players_with_base,
            "players_without_base": len(players) - players_with_base,
            "rated_players": rated_players,
            "unrated_players": len(players) - rated_players,
            "bases": bases,
            "total": round(sum(float(item["subtotal"]) for item in bases), 2),
            "players": players,
        }

    def export_rating_fee_report(self, tournament_id: int, file_path: str | Path) -> None:
        path = Path(file_path)
        if path.suffix.lower() not in {".xlsx", ".pdf"}:
            raise AppError("Relatório de taxas de rating deve ser exportado em XLSX ou PDF.")
        self._write_multi_report(path, self._rating_fee_sections(tournament_id))

    def export_fide_rating_report(
        self, tournament_id: int, file_path: str | Path, rating_type: str = "fide"
    ) -> None:
        self._write_multi_report(
            Path(file_path), self._fide_rating_sections(tournament_id, rating_type)
        )

    def export_prize_report(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(Path(file_path), self._prize_sections(tournament_id))

    def export_federation_statistics(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(Path(file_path), self._federation_sections(tournament_id))

    def export_game_statistics(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(Path(file_path), self._game_statistics_sections(tournament_id))

    def export_player_cards(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(Path(file_path), self._player_cards_sections(tournament_id))

    def export_norm_report(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(Path(file_path), self._norm_sections(tournament_id))

    def export_arbiter_norm_report(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(Path(file_path), self._arbiter_norm_sections(tournament_id))

    def export_access(self, tournament_id: int, dest_dir: str | Path) -> dict[str, Any]:
        """Exporta o torneio para Access (Fase J).

        Gera sempre um pacote importável (CSV por tabela + ``schema.ini``) e, quando
        o driver ACE estiver instalado, também um ``.accdb`` real. Reaproveita os
        construtores de seção (jogadores, classificação, emparceiramentos).
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        directory = Path(dest_dir)

        # Fronteira ASCII (B-7). Estes cabeçalhos são os MESMOS das exportações
        # para gente, que passaram a ser acentuados — mas aqui viram nome de
        # coluna de CSV lido por driver ODBC com schema.ini, e acento ali é
        # risco de importação, não polimento. Em vez de manter duas listas de
        # cabeçalhos (que divergem no primeiro descuido), a lista é uma só e a
        # dobra acontece aqui, no ponto de entrega que exige ASCII.
        tables: dict[str, tuple[list[str], list[list[Any]]]] = {}
        _, player_headers, player_rows = self._players_section(tournament_id)
        tables["Jogadores"] = (
            headers_to_ascii(player_headers),
            [list(row) for row in player_rows],
        )
        _, standings_headers, standings_rows = self._standings_section(tournament_id)
        tables["Classificacao"] = (
            headers_to_ascii(standings_headers),
            [list(row) for row in standings_rows],
        )

        pairing_headers: list[str] | None = None
        pairing_rows: list[list[Any]] = []
        for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"]):
            try:
                _, headers, rows = self._pairings_section(round_data["id"])
            except Exception:
                continue
            if pairing_headers is None:
                pairing_headers = ["Rodada", *headers]
            for row in rows:
                pairing_rows.append([round_data["number"], *list(row)])
        if pairing_headers is not None:
            tables["Emparceiramentos"] = (headers_to_ascii(pairing_headers), pairing_rows)

        bundle = write_csv_bundle(tables, directory)

        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(tournament.get("name") or "torneio").strip()).strip("_") or "torneio"
        accdb_path = directory / f"{slug}_access.accdb"
        accdb = str(accdb_path) if write_accdb(tables, accdb_path) else None

        logger.info(
            "Exportacao Access do torneio %s: %s tabelas, accdb=%s",
            tournament_id,
            len(tables),
            bool(accdb),
        )
        return {
            "csv_paths": bundle["csv_paths"],
            "schema_ini": bundle["schema_ini"],
            "accdb": accdb,
            "driver_available": access_driver_available(),
            "tables": list(tables.keys()),
        }

    def export_round_package(
        self,
        round_id: int,
        dest_dir: str | Path,
        *,
        wall: bool = True,
        scoresheets: bool = True,
        cards: bool = True,
    ) -> dict[str, Any]:
        """Pacote da rodada em um passo: mural + súmulas + cartões numa pasta (PDF).

        Reaproveita os geradores existentes e isola erros (um documento que falha
        não impede os demais). Pensado para o árbitro afixar/distribuir de uma vez.
        """
        round_data = self.db.get_round(round_id)
        if not round_data:
            raise AppError("Rodada não encontrada.")
        tournament = self.db.get_tournament(int(round_data["tournament_id"]))
        if not tournament:
            raise AppError("Torneio não encontrado.")
        directory = Path(dest_dir)
        directory.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(tournament.get("name") or "torneio").strip()).strip("_") or "torneio"
        base = f"{slug}_rodada_{round_data['number']}"

        generated: list[str] = []
        errors: list[str] = []
        if wall:
            try:
                path = directory / f"{base}_mural.pdf"
                self.export_pairings(round_id, path)
                generated.append(str(path))
            except Exception as exc:
                errors.append(f"Mural: {exc}")
        if scoresheets:
            try:
                path = directory / f"{base}_sumulas.pdf"
                self.export_scoresheets(round_id, path)
                generated.append(str(path))
            except Exception as exc:
                errors.append(f"Súmulas: {exc}")
        if cards:
            try:
                if tournament.get("competition_type") == "team":
                    # Em equipes os tabuleiros ficam em team_boards (nao na tabela pairings):
                    # o total de cartoes = soma dos tabuleiros dos confrontos sem bye.
                    total_boards = sum(
                        len(self.db.list_team_boards(int(match["id"])))
                        for match in self.db.list_team_matches_for_round(round_id)
                        if not match.get("is_bye")
                    )
                else:
                    pairings = self.db.get_pairings_for_round(round_id)
                    total_boards = max((int(item.get("board_number") or 0) for item in pairings), default=0)
                if total_boards <= 0:
                    raise AppError("Rodada sem mesas para cartões.")
                path = directory / f"{base}_cartoes.pdf"
                self.export_table_cards(path, 1, total_boards, round_id, False)
                generated.append(str(path))
            except Exception as exc:
                errors.append(f"Cartões: {exc}")

        logger.info(
            "Pacote da rodada %s do torneio %s: %s documentos, %s erros",
            round_data["number"],
            tournament["id"],
            len(generated),
            len(errors),
        )
        return {"generated": generated, "errors": errors, "count": len(generated)}

    def export_tournament_minutes(self, tournament_id: int, file_path: str | Path) -> None:
        """Ata final do torneio: documento unico de encerramento (Fase painel)."""
        self._write_multi_report(Path(file_path), self._tournament_minutes_sections(tournament_id))

    def export_round_bulletin(self, round_id: int, file_path: str | Path) -> None:
        """Boletim/press-release da rodada: resultados + classificação + destaques."""
        self._write_multi_report(Path(file_path), self._round_bulletin_sections(round_id))

    def export_podium(self, tournament_id: int, file_path: str | Path) -> None:
        """Poster/diploma do podio (PDF A4): top 3 + campeoes por categoria."""
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise AppError("Poster do podio deve ser exportado em PDF.")
        self._write_podium_poster_pdf(path, self._podium_data(tournament_id))
        logger.info("Poster do podio gerado: %s", path)

    def export_tiebreak_report(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Relatório de desempates por jogador disponível apenas para torneios individuais.")
        rows = []
        # Aviso de não conformidade no topo do relatório (TBK-03): é o documento
        # que alguém usa para conferir a ordem final, então é onde a informação
        # "este número não é o oficial" precisa estar — antes dos números.
        aviso = legacy_engine_note(
            self.pairing_service.tiebreak_engine_report(tournament_id).used
        )
        if aviso:
            rows.append(["", "", "", "AVISO", "", "", aviso])
        for standing in self.pairing_service.tiebreak_report(tournament_id):
            components = dict(standing.get("tiebreak_components") or {})
            for criterion in (
                "buchholz",
                "buchholz_median",
                "sonneborn_berger",
                "direct_encounter",
                "wins",
                "performance",
            ):
                item = dict(components.get(criterion) or {})
                rows.append(
                    [
                        standing["position"],
                        standing["name"],
                        standing["points"],
                        item.get("label", criterion),
                        item.get("value", ""),
                        item.get("formula", ""),
                        self._tiebreak_component_summary(item),
                    ]
                )
        self._write_report(
            file_path,
            f"Desempates - {tournament['name']}",
            ["Pos", "Jogador", "Pts", "Critério", "Valor", "Formula", "Componentes"],
            rows,
        )

    def export_tournament_audit(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        events = self.db.list_audit_events(tournament_id, limit=5000)
        rows = [
            [
                event.get("created_at", ""),
                event.get("action", ""),
                event.get("entity_type", ""),
                event.get("entity_id", ""),
                event.get("round_id", ""),
                event.get("actor", ""),
                event.get("role", ""),
                event.get("reason", ""),
                event.get("before_hash", ""),
                event.get("after_hash", ""),
            ]
            for event in events
        ]
        self._write_report(
            file_path,
            f"Auditoria do torneio - {tournament['name']}",
            [
                "Data/hora",
                "Acao",
                "Entidade",
                "ID entidade",
                "Rodada ID",
                "Operador",
                "Perfil",
                "Motivo",
                "Hash anterior",
                "Hash posterior",
            ],
            rows,
        )

    def export_complete(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        sections = [
            self._tournament_section(tournament_id),
        ]
        if tournament.get("competition_type") == "team":
            sections.append(self._teams_section(tournament_id))
            sections.append(self._team_rosters_section(tournament_id))
            sections.append(self._team_lineups_section(tournament_id))
            sections.append(self._team_substitutions_section(tournament_id))
        sections.append(self._players_section(tournament_id))
        for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"]):
            sections.append(self._pairings_section(round_data["id"]))
        sections.append(self._standings_section(tournament_id))
        self._write_multi_report(file_path, sections)

    def export_pgn(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
            
        path = Path(file_path)
        with path.open("w", encoding="utf-8") as f:
            for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda r: r["number"]):
                pairings = self.db.get_pairings_for_round(round_data["id"])
                for p in pairings:
                    if p["is_bye"]:
                        continue
                    
                    white_name = p.get("white_name") or "Unknown"
                    black_name = p.get("black_name") or "Unknown"
                    result = p.get("result") or "*"
                    if result == "1-0":
                        res_str = "1-0"
                    elif result == "0-1":
                        res_str = "0-1"
                    elif result == "1/2-1/2":
                        res_str = "1/2-1/2"
                    else:
                        res_str = "*"
                        
                    f.write(f'[Event "{tournament["name"]}"]\n')
                    f.write(f'[Site "{tournament.get("location") or ""}"]\n')
                    f.write(f'[Date "{tournament.get("start_date") or ""}"]\n')
                    f.write(f'[Round "{round_data["number"]}"]\n')
                    f.write(f'[White "{white_name}"]\n')
                    f.write(f'[Black "{black_name}"]\n')
                    f.write(f'[Result "{res_str}"]\n')
                    f.write(f'\n{res_str}\n\n')

    def export_trf(self, tournament_id: int, file_path: str | Path) -> list[str]:
        return self.export_chess_results_trf(tournament_id, file_path)

    def export_chess_results_trf(self, tournament_id: int, file_path: str | Path) -> list[str]:
        return self._federation_exporter("trf16").export(tournament_id, file_path)

    def export_chess_results_trf25(self, tournament_id: int, file_path: str | Path) -> list[str]:
        return self._federation_exporter("trf25").export(tournament_id, file_path)

    def validate_chess_results_trf(self, tournament_id: int) -> list[str]:
        return self._federation_exporter("trf16").validate(tournament_id)

    def export_chess_results_trf_validation_report(self, tournament_id: int, file_path: str | Path) -> None:
        rows = self._federation_exporter("trf16").validation_report_rows(tournament_id)
        self._write_report(
            file_path,
            "Pendências TRF16",
            ["Tipo", "Item", "Valor"],
            rows,
        )

    def _federation_exporter(self, code: str):
        from src.services.federation_exporters import (
            FederationExporterRegistry,
            TRF16Exporter,
            TRF25Exporter,
        )

        registry = FederationExporterRegistry()
        registry.register(TRF16Exporter(self))
        registry.register(TRF25Exporter(self))
        return registry.get(code)

    def _trf_pending_result_rounds(
        self,
        tournament: Mapping[str, Any],
        rounds: list[dict[str, Any]],
    ) -> list[str]:
        pending_rounds = []
        for round_data in rounds:
            if tournament.get("competition_type") == "team":
                has_pending = any(
                    not board.get("result") or str(board.get("result")) not in RESULT_POINTS
                    for match in self.db.list_team_matches_for_round(int(round_data["id"]))
                    if not match.get("is_bye")
                    for board in self.db.list_team_boards(int(match["id"]))
                )
            else:
                has_pending = any(
                    not pairing.get("result") or str(pairing.get("result")) not in FINAL_RESULTS
                    for pairing in self.db.get_pairings_for_round(int(round_data["id"]))
                )
            if has_pending:
                pending_rounds.append(str(round_data["number"]))
        return pending_rounds

    @staticmethod
    def _trf_clean(value: Any, width: int | None = None) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
        if width is not None:
            return text[:width].ljust(width)
        return text

    @staticmethod
    def _trf_date(value: Any, *, long_year: bool) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        ano = FederationReportsMixin._year_only(raw)
        if ano:
            # A FIDE publica APENAS o ano na lista de rating, e o TRF aceita
            # `YYYY` no campo de nascimento (FED-05). Completar com 01/01
            # inventaria um aniversario que ninguem informou.
            return ano if long_year else ano[2:]
        parsed: datetime | None = None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%d. %m. %Y", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if not parsed:
            return raw.replace("-", "/")[:10]
        return parsed.strftime("%Y/%m/%d" if long_year else "%y/%m/%d")

    @staticmethod
    def _year_only(value: Any) -> str:
        """`"1985"` quando o dado e so o ano (inclusive `1985-00-00`); senao `""`.

        `YYYY-00-00` aparece em base importada de outros programas, que usam o
        zero para dizer "mes e dia desconhecidos" — e a mesma informacao.
        """
        raw = str(value or "").strip()
        if len(raw) == 4 and raw.isdigit():
            return raw
        for separador in ("-", "/", "."):
            partes = raw.split(separador)
            if len(partes) == 3 and len(partes[0]) == 4 and partes[0].isdigit():
                if all(parte.strip("0") == "" for parte in partes[1:]):
                    return partes[0]
        return ""

    @classmethod
    def _trf_date_is_valid(cls, value: Any) -> bool:
        """Data que o TRF aceita: `YYYY/MM/DD` completa, ou so o ano.

        Ano-so era tratado como data QUEBRADA, e como a lista da FIDE nao publica
        outra coisa, todo jogador importado dela envenenava o arquivo com um aviso
        de nascimento invalido (FED-05).
        """
        raw = str(value or "").strip()
        if not raw:
            return False
        if cls._year_only(raw):
            return True
        normalized = cls._trf_date(raw, long_year=True)
        try:
            datetime.strptime(normalized, "%Y/%m/%d")
            return True
        except ValueError:
            return False

    @staticmethod
    def _trf_valid_federation_code(value: Any) -> bool:
        code = str(value or "").strip()
        return len(code) == 3 and code.isalpha()

    @staticmethod
    def _trf_rating(player: Mapping[str, Any]) -> int:
        return int(
            player.get("international_rating")
            or player.get("rating")
            or player.get("national_rating")
            or 0
        )

    @staticmethod
    def _trf_points(value: Any) -> str:
        points = float(value or 0.0)
        if points >= 100:
            return f"{points:4.0f}"[:4]
        return f"{points:4.1f}"[-4:]

    @staticmethod
    def _trf_missing_field_warnings(field_name: str, player_names: list[str]) -> list[str]:
        if not player_names:
            return []
        shown = ", ".join(player_names[:5])
        suffix = f" e mais {len(player_names) - 5}" if len(player_names) > 5 else ""
        return [f"Jogadores sem {field_name}: {shown}{suffix}."]

    @staticmethod
    def _trf_player_result(result: str, *, is_white: bool, is_bye: bool) -> str:
        """Letra TRF do lado pedido. `Z` para mesa sem resultado.

        As letras saem do registro de resultados (ARB-02): era uma escada de
        `if` que precisava crescer a cada codigo novo, e a `W`/`D`/`L` — partida
        disputada e nao ratavel — teria passado despercebida em metade dos
        lugares que perguntam a mesma coisa de outro jeito.
        """
        if is_bye:
            return "U"
        letras = trf_letters(result)
        if letras is None:
            return "Z"
        return letras[0] if is_white else letras[1]

    @staticmethod
    def _trf_tournament_line(code: str, value: Any) -> str:
        return f"{code} {FederationReportsMixin._trf_clean(value)}\r\n"

    def _trf_tournament_type(self, tournament: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
        profile = str(settings.get("tournament_profile") or "").strip()
        suffix = "FIDE-rated" if profile == "fide" else "Standard"
        system = str(tournament.get("system") or "Suico").strip()
        if tournament.get("competition_type") == "team":
            return f"Team: {system} ({suffix})"
        return f"Individual: {system} ({suffix})"

    def _trf_pairings_by_round(
        self,
        tournament: Mapping[str, Any],
        rounds: list[dict[str, Any]],
    ) -> dict[int, list[dict[str, Any]]]:
        if tournament.get("competition_type") != "team":
            return {
                int(round_data["number"]): self.db.get_pairings_for_round(round_data["id"])
                for round_data in rounds
            }

        pairings_by_round: dict[int, list[dict[str, Any]]] = {}
        for round_data in rounds:
            board_pairings = []
            for match in self.db.list_team_matches_for_round(int(round_data["id"])):
                if match.get("is_bye"):
                    continue
                for board in self.db.list_team_boards(int(match["id"])):
                    if not board.get("white_player_id") or not board.get("black_player_id"):
                        continue
                    board_pairings.append(
                        {
                            "white_player_id": int(board["white_player_id"]),
                            "black_player_id": int(board["black_player_id"]),
                            "result": str(board.get("result") or ""),
                            "is_bye": 0,
                        }
                    )
            pairings_by_round[int(round_data["number"])] = board_pairings
        return pairings_by_round

    def _trf_player_standings(
        self,
        tournament: Mapping[str, Any],
        players: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        if tournament.get("competition_type") != "team":
            return {
                int(item["player_id"]): item
                for item in self.pairing_service.standings(int(tournament["id"]))
            }

        stats = {
            int(player["id"]): {
                "player_id": int(player["id"]),
                "points": float(player.get("starting_points", 0.0) or 0.0),
                "position": 0,
                "rating": self._trf_rating(player),
                "name": player_pairing_name(player),
            }
            for player in players
        }
        for round_data in self.db.list_rounds(int(tournament["id"])):
            for match in self.db.list_team_matches_for_round(int(round_data["id"])):
                for board in self.db.list_team_boards(int(match["id"])):
                    white_id = int(board.get("white_player_id") or 0)
                    black_id = int(board.get("black_player_id") or 0)
                    result = str(board.get("result") or "")
                    if not white_id or not black_id or result not in RESULT_POINTS:
                        continue
                    white_points, black_points = RESULT_POINTS[result]
                    if white_id in stats:
                        stats[white_id]["points"] += white_points
                    if black_id in stats:
                        stats[black_id]["points"] += black_points

        ordered_stats = sorted(
            stats.values(),
            key=lambda item: (-float(item["points"]), -int(item["rating"]), str(item["name"]).casefold()),
        )
        for index, item in enumerate(ordered_stats, start=1):
            item["position"] = index
        return stats

    def _trf_chief_arbiter(self, tournament_id: int, settings: Mapping[str, Any]) -> str:
        chief = str(settings.get("chief_arbiter") or "").strip()
        if chief:
            return chief
        for referee in self.db.list_tournament_referees(tournament_id):
            role = str(referee.get("role") or "").casefold()
            if "chief" in role or "principal" in role or "árbitro chefe" in role:
                return str(referee.get("name") or "").strip()
        return str(settings.get("director") or settings.get("organizer") or "").strip()

    def _trf_deputy_arbiters(self, tournament_id: int, settings: Mapping[str, Any]) -> list[str]:
        deputies = [
            item.strip()
            for item in str(settings.get("arbiters") or "").replace(";", "\n").splitlines()
            if item.strip()
        ]
        chief = self._trf_chief_arbiter(tournament_id, settings).casefold()
        for referee in self.db.list_tournament_referees(tournament_id):
            name = str(referee.get("name") or "").strip()
            if name and name.casefold() != chief and name not in deputies:
                deputies.append(name)
        return deputies

    def _trf_round_dates_line(self, round_count: int, schedule: Mapping[int, str]) -> str:
        line = "132" + (" " * 88)
        for round_number in range(1, round_count + 1):
            line += f"{self._trf_date(schedule.get(round_number), long_year=False):<8}  "
        return f"{line.rstrip()}\r\n"

    def _trf_player_line(
        self,
        player: Mapping[str, Any],
        player_id_to_start_rank: Mapping[int, int],
        standings_by_player: Mapping[int, Mapping[str, Any]],
        pairings_by_round: Mapping[int, list[dict[str, Any]]],
        round_count: int,
        settings: Mapping[str, Any],
    ) -> str:
        player_id = int(player["id"])
        start_rank = player_id_to_start_rank[player_id]
        standing = standings_by_player.get(player_id, {})
        sex = self._trf_clean(str(player.get("sex") or "")[:1].lower(), 1)
        title = self._trf_clean(str(player.get("title") or "").upper(), 3)
        name = self._trf_clean(player_pairing_name(player), 33)
        rating = f"{self._trf_rating(player):4d}"[-4:]
        federation = self._trf_clean(
            str(player.get("federation_id") or settings.get("federation") or "").upper(),
            3,
        )
        fide_id = self._trf_clean(player.get("fide_id"))[:11].rjust(11)
        birth_date = self._trf_clean(self._trf_date(player.get("birth_date"), long_year=True), 10)
        points = self._trf_points(standing.get("points", player.get("starting_points", 0.0)))
        rank = int(standing.get("position") or 0)
        line = (
            f"001 {start_rank:4d} {sex}{title} {name} {rating} {federation} "
            f"{fide_id} {birth_date} {points} {rank:4d}  "
        )
        for round_number in range(1, round_count + 1):
            line += self._trf_round_cell(player_id, player_id_to_start_rank, pairings_by_round.get(round_number, []))
        return f"{line.rstrip()}\r\n"

    def _trf_round_cell(
        self,
        player_id: int,
        player_id_to_start_rank: Mapping[int, int],
        pairings: list[dict[str, Any]],
    ) -> str:
        pairing = next(
            (
                item
                for item in pairings
                if int(item["white_player_id"]) == player_id
                or int(item.get("black_player_id") or 0) == player_id
            ),
            None,
        )
        if not pairing:
            return "0000 - Z  "
        is_bye = bool(pairing.get("is_bye"))
        is_white = int(pairing["white_player_id"]) == player_id
        if is_bye:
            code = str(pairing.get("result") or "").strip().upper()
            bye_code = code if code in {"F", "H", "Z"} else "U"
            return f"0000 - {bye_code}  "
        opponent_id = int(pairing["black_player_id"] if is_white else pairing["white_player_id"])
        opponent_rank = player_id_to_start_rank.get(opponent_id, 0)
        color = "w" if is_white else "b"
        result = self._trf_player_result(str(pairing.get("result") or ""), is_white=is_white, is_bye=is_bye)
        return f"{opponent_rank:4d} {color} {result}  "

    def _trf_team_line(
        self,
        team: Mapping[str, Any],
        player_id_to_start_rank: Mapping[int, int],
    ) -> str:
        team_name = self._trf_clean(team.get("name"), 32)
        line = f"013 {team_name}"
        for assignment in self.db.list_team_players(int(team["id"]), active_only=False):
            start_rank = player_id_to_start_rank.get(int(assignment["player_id"]))
            if start_rank:
                line += f"{start_rank:4d} "
        return f"{line.rstrip()}\r\n"
