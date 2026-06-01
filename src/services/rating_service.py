from __future__ import annotations
import csv
import html
import io
import json
import logging
import math
import secrets
import shutil
import sqlite3
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.services.constants import *
from src.services.export_service import ImportService
from src.services.fide_norms import build_norm_report
from src.services.fide_rating import build_fide_report_rows

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

class OfficialRatingService:
    SOURCES = {"FIDE", "CBX", "LBX"}
    LBX_LIST_URLS = {
        "standard": "https://lbx.org.br/LBXstandard.php",
        "rapid": "https://lbx.org.br/LBXrapid.php",
        "blitz": "https://lbx.org.br/LBXblitz.php",
    }

    def __init__(self, db: Database) -> None:
        self.db = db

    def import_official_csv(
        self,
        file_path: str | Path,
        source: str,
        list_date: str = "",
    ) -> dict[str, Any]:
        source = source.strip().upper()
        if source not in self.SOURCES:
            raise AppError("Fonte invalida. Use FIDE, CBX ou LBX.")

        path = Path(file_path)
        errors: list[str] = []
        payloads: list[dict[str, Any]] = []

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            sample = file.read(4096)
            file.seek(0)
            reader = csv.DictReader(file, dialect=ImportService._csv_dialect(sample))
            if not reader.fieldnames:
                raise AppError("CSV sem cabecalho.")

            for line_number, row in enumerate(reader, start=2):
                payload = self._official_payload(row, source)
                if not payload["name"]:
                    errors.append(f"Linha {line_number}: nome vazio.")
                    continue
                if not payload["external_id"]:
                    errors.append(f"Linha {line_number}: ID {source} vazio.")
                    continue
                payloads.append(payload)

        if payloads:
            snapshot_id = self.db.create_official_rating_snapshot_with_players(
                source=source,
                list_date=list_date,
                file_name=path.name,
                players=payloads,
            )
        else:
            snapshot_id = None

        logger.info("%s jogadores oficiais importados de %s (%s)", len(payloads), path, source)
        return {
            "snapshot_id": snapshot_id,
            "source": source,
            "imported": len(payloads),
            "errors": errors,
        }

    def import_lbx_lists_from_url(self) -> dict[str, Any]:
        players_by_id: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for rating_type, url in self.LBX_LIST_URLS.items():
            payloads, list_errors = self._download_lbx_list(url)
            errors.extend(list_errors)
            for payload in payloads:
                external_id = str(payload["external_id"])
                if rating_type == "standard":
                    payload["standard_rating"] = payload["national_rating"]
                    players_by_id[external_id] = payload
                    continue
                player = players_by_id.setdefault(external_id, payload)
                player[f"{rating_type}_rating"] = payload["national_rating"]

        payloads = list(players_by_id.values())
        snapshot_id = None
        if payloads:
            snapshot_id = self.db.create_official_rating_snapshot_with_players(
                source="LBX",
                list_date=date.today().isoformat(),
                file_name="LBXstandard.php + LBXrapid.php + LBXblitz.php",
                players=payloads,
            )

        logger.info("%s jogadores importados das listas online da LBX", len(payloads))
        return {
            "snapshot_id": snapshot_id,
            "source": "LBX",
            "imported": len(payloads),
            "errors": errors,
        }

    def _download_lbx_list(self, url: str) -> tuple[list[dict[str, Any]], list[str]]:
        request = urllib.request.Request(url, headers={"User-Agent": "Albericus Chess Club Manager"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8-sig", errors="replace")
        except (OSError, urllib.error.URLError) as exc:
            raise AppError(f"Nao foi possivel baixar a lista LBX: {exc}") from exc

        errors: list[str] = []
        payloads: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(content), dialect=ImportService._csv_dialect(content[:4096]))
        if not reader.fieldnames:
            raise AppError("Lista LBX sem cabecalho.")
        for line_number, row in enumerate(reader, start=2):
            payload = self._official_payload(row, "LBX")
            if not payload["name"] or not payload["external_id"]:
                errors.append(f"Linha {line_number}: jogador LBX incompleto.")
                continue
            payloads.append(payload)
        return payloads, errors

    def import_official_xml(self, file_path: str | Path, source: str, list_date: str = "") -> dict[str, Any]:
        import xml.etree.ElementTree as ET
        source = source.strip().upper()
        if source not in self.SOURCES:
            raise AppError("Fonte invalida. Use FIDE, CBX ou LBX.")
            
        path = Path(file_path)
        errors: list[str] = []
        payloads: list[dict[str, Any]] = []
        
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError:
            raise AppError("Arquivo XML invalido.")

        for index, node in enumerate(root):
            row = {child.tag.lower(): child.text or "" for child in node}
            payload = self._official_payload(row, source)
            
            if not payload["name"]:
                errors.append(f"Registro {index}: nome vazio.")
                continue
            if not payload["external_id"]:
                errors.append(f"Registro {index}: ID {source} vazio.")
                continue
            payloads.append(payload)

        if payloads:
            snapshot_id = self.db.create_official_rating_snapshot_with_players(
                source=source,
                list_date=list_date,
                file_name=path.name,
                players=payloads,
            )
        else:
            snapshot_id = None

        logger.info("%s jogadores oficiais importados de %s (%s)", len(payloads), path, source)
        return {
            "snapshot_id": snapshot_id,
            "source": source,
            "imported": len(payloads),
            "errors": errors,
        }

    def import_official_excel(self, file_path: str | Path, source: str, list_date: str = "") -> dict[str, Any]:
        source = source.strip().upper()
        if source not in self.SOURCES:
            raise AppError("Fonte invalida. Use FIDE, CBX ou LBX.")
            
        path = Path(file_path)
        errors: list[str] = []
        payloads: list[dict[str, Any]] = []
        
        try:
            if path.suffix.lower() == ".xls":
                try:
                    import xlrd
                    book = xlrd.open_workbook(path)
                    sheet = book.sheet_by_index(0)
                    if sheet.nrows == 0:
                        raise AppError("Planilha vazia.")
                    headers = [str(sheet.cell_value(0, col)).strip().lower() for col in range(sheet.ncols)]
                    
                    for row_idx in range(1, sheet.nrows):
                        row_dict = {}
                        for col_idx in range(sheet.ncols):
                            val = sheet.cell_value(row_idx, col_idx)
                            if isinstance(val, float) and val.is_integer():
                                val = int(val)
                            row_dict[headers[col_idx]] = str(val).strip()
                        payload = self._official_payload(row_dict, source)
                        if not payload["name"] or not payload["external_id"]:
                            continue
                        payloads.append(payload)
                except Exception as xlrd_exc:
                    # Pode ser um arquivo HTML disfarçado de XLS (comum em sistemas web). Usar pandas.
                    import pandas as pd
                    try:
                        dfs = pd.read_html(path, encoding="utf-8")
                        if not dfs:
                            raise AppError("Nenhuma tabela HTML encontrada no arquivo .xls.")
                        df = dfs[0].fillna("")
                        headers = [str(c).strip().lower() for c in df.columns]
                        
                        for _, row in df.iterrows():
                            row_dict = {}
                            for col_idx, val in enumerate(row):
                                if col_idx < len(headers):
                                    if isinstance(val, float) and val.is_integer():
                                        val = int(val)
                                    row_dict[headers[col_idx]] = str(val).strip()
                            payload = self._official_payload(row_dict, source)
                            if not payload["name"] or not payload["external_id"]:
                                continue
                            payloads.append(payload)
                    except Exception as pd_exc:
                        raise AppError(f"Erro xlrd: {xlrd_exc}. Erro HTML: {pd_exc}")

            else:
                import openpyxl
                book = openpyxl.load_workbook(path, data_only=True)
                sheet = book.active
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    raise AppError("Planilha vazia.")
                headers = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]
                
                for row in rows[1:]:
                    row_dict = {}
                    for col_idx, cell in enumerate(row):
                        if col_idx < len(headers):
                            val = cell if cell is not None else ""
                            if isinstance(val, float) and val.is_integer():
                                val = int(val)
                            row_dict[headers[col_idx]] = str(val).strip()
                    payload = self._official_payload(row_dict, source)
                    if not payload["name"] or not payload["external_id"]:
                        continue
                    payloads.append(payload)
                    
        except Exception as e:
            logger.error("Erro ao ler Excel: %s", e)
            raise AppError(f"Arquivo Excel invalido ou corrompido: {e}")

        if payloads:
            snapshot_id = self.db.create_official_rating_snapshot_with_players(
                source=source,
                list_date=list_date,
                file_name=path.name,
                players=payloads,
            )
        else:
            snapshot_id = None

        logger.info("%s jogadores oficiais importados de %s (%s)", len(payloads), path, source)
        return {
            "snapshot_id": snapshot_id,
            "source": source,
            "imported": len(payloads),
            "errors": errors,
        }

    def import_fide_list_from_url(self) -> dict[str, Any]:
        import urllib.request
        import zipfile
        import io

        url = "http://ratings.fide.com/download/standard_rating_list.zip"
        logger.info("Baixando lista da FIDE de %s", url)
        
        req = urllib.request.Request(url, headers={"User-Agent": "Albericus Chess Club Manager"})
        with urllib.request.urlopen(req, timeout=30) as response:
            zip_data = response.read()

        payloads: list[dict[str, Any]] = []
        errors: list[str] = []
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            name = z.namelist()[0]
            with z.open(name) as file:
                # Ler linha por linha
                lines = io.TextIOWrapper(file, encoding="utf-8-sig", errors="replace")
                next(lines, None) # Ignorar cabeçalho
                
                for line_number, line in enumerate(lines, start=2):
                    if len(line) < 120:
                        continue
                        
                    fide_id = line[0:15].strip()
                    name = line[15:76].strip()
                    fed = line[76:80].strip()
                    sex = line[80:84].strip()
                    title = line[84:89].strip()
                    rating_str = line[113:119].strip()
                    birth_year = line[126:131].strip()

                    if not fide_id or not name:
                        continue
                        
                    rating = int(rating_str) if rating_str.isdigit() else 0

                    payloads.append({
                        "external_id": fide_id,
                        "fide_id": fide_id,
                        "cbx_id": "",
                        "name": name,
                        "surname": "",
                        "given_name": "",
                        "title": title,
                        "sex": sex,
                        "federation": fed,
                        "club": "",
                        "birth_date": birth_year,
                        "national_rating": 0,
                        "international_rating": rating,
                        "standard_rating": rating,
                        "rapid_rating": 0,
                        "blitz_rating": 0,
                    })

        snapshot_id = None
        if payloads:
            snapshot_id = self.db.create_official_rating_snapshot_with_players(
                source="FIDE",
                list_date=datetime.now().strftime("%Y-%m-%d"),
                file_name="standard_rating_list.zip",
                players=payloads,
            )

        logger.info("%s jogadores importados da FIDE URL", len(payloads))
        return {
            "snapshot_id": snapshot_id,
            "source": "FIDE",
            "imported": len(payloads),
            "errors": errors,
        }

    def preview_tournament_player_updates(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}

        rows = []
        unmatched = []
        for player in self.db.list_players(tournament_id, active_only=False):
            official = self._merged_official_player(player)
            if not official:
                unmatched.append(
                    {
                        "player_id": int(player["id"]),
                        "name": player["name"],
                        "fide_id": player.get("fide_id", ""),
                        "cbx_id": player.get("cbx_id", ""),
                        "lbx_id": player.get("lbx_id", ""),
                    }
                )
                continue

            payload = self._official_update_payload(player, official, settings)
            before = self._official_comparison_values(player)
            after = self._official_comparison_values(payload)
            changed_fields = [
                field
                for field in before
                if before[field] != after[field]
            ]
            rows.append(
                {
                    "player_id": int(player["id"]),
                    "name": player["name"],
                    "status": "changed" if changed_fields else "unchanged",
                    "status_label": "Alterar" if changed_fields else "Sem mudanca",
                    "changed_fields": changed_fields,
                    "changes_label": ", ".join(self._comparison_field_label(field) for field in changed_fields),
                    "before": before,
                    "after": after,
                    "_payload": payload,
                }
            )

        changed = sum(1 for row in rows if row["status"] == "changed")
        unchanged = len(rows) - changed
        return {
            "total": len(rows) + len(unmatched),
            "matched": len(rows),
            "changed": changed,
            "unchanged": unchanged,
            "unmatched_count": len(unmatched),
            "rows": rows,
            "unmatched": unmatched,
        }

    def apply_tournament_player_updates(
        self,
        tournament_id: int,
        player_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        preview = self.preview_tournament_player_updates(tournament_id)
        selected_ids = {int(player_id) for player_id in player_ids} if player_ids is not None else None
        updated = 0
        skipped = 0
        for row in preview["rows"]:
            player_id = int(row["player_id"])
            if row["status"] != "changed" or (selected_ids is not None and player_id not in selected_ids):
                skipped += 1
                continue
            self.db.update_player_official_data(
                player_id,
                row["_payload"],
            )
            updated += 1

        logger.info(
            "%s jogadores atualizados por base oficial no torneio %s; %s sem correspondencia; %s ignorados",
            updated,
            tournament_id,
            preview["unmatched_count"],
            skipped,
        )
        return {
            "updated": updated,
            "skipped": skipped,
            "unmatched": [row["name"] for row in preview["unmatched"]],
        }

    def update_tournament_players(self, tournament_id: int) -> dict[str, Any]:
        return self.apply_tournament_player_updates(tournament_id)

    def _official_update_payload(
        self,
        player: dict[str, Any],
        official: dict[str, Any],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        national_rating = int(official.get("national_rating") or 0) or int(player.get("national_rating") or 0)
        international_rating = (
            int(official.get("international_rating") or 0)
            or int(official.get("standard_rating") or 0)
            or int(player.get("international_rating") or 0)
        )
        rating = self._rating_for_order(
            settings.get("initial_order", "rating"),
            current=int(player.get("rating") or 0),
            national=national_rating,
            international=international_rating,
        )
        return {
            "name": official.get("name") or player["name"],
            "surname": official.get("surname") or player.get("surname", ""),
            "given_name": official.get("given_name") or player.get("given_name", ""),
            "title": official.get("title") or player.get("title", ""),
            "sex": official.get("sex") or player.get("sex", ""),
            "club": official.get("club") or player.get("club", ""),
            "federation_id": official.get("federation") or player.get("federation_id", ""),
            "fide_id": official.get("fide_id") or player.get("fide_id", ""),
            "cbx_id": official.get("cbx_id") or player.get("cbx_id", ""),
            "lbx_id": official.get("lbx_id") or player.get("lbx_id", ""),
            "birth_date": official.get("birth_date") or player.get("birth_date", ""),
            "national_rating": national_rating,
            "international_rating": international_rating,
            "rating": rating,
        }

    @staticmethod
    def _official_comparison_values(player: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": str(player.get("name") or ""),
            "club": str(player.get("club") or ""),
            "title": str(player.get("title") or ""),
            "rating": int(player.get("rating") or 0),
            "national_rating": int(player.get("national_rating") or 0),
            "international_rating": int(player.get("international_rating") or 0),
        }

    @staticmethod
    def _comparison_field_label(field: str) -> str:
        return {
            "name": "nome",
            "club": "clube",
            "title": "titulo",
            "rating": "rating",
            "national_rating": "rating nacional",
            "international_rating": "rating internacional",
        }[field]

    def _merged_official_player(self, player: dict[str, Any]) -> dict[str, Any] | None:
        fide = self.db.find_latest_official_player(fide_id=str(player.get("fide_id") or ""))
        cbx = self.db.find_latest_official_player(cbx_id=str(player.get("cbx_id") or ""))
        lbx = self.db.find_latest_official_player(lbx_id=str(player.get("lbx_id") or ""))
        if not fide and not cbx and not lbx:
            return None
        merged: dict[str, Any] = {}
        for source in [fide, cbx, lbx]:
            if not source:
                continue
            for key, value in source.items():
                if value not in (None, ""):
                    merged[key] = value
        if fide:
            for key in ["title", "sex", "federation", "birth_date", "international_rating", "standard_rating"]:
                if fide.get(key) not in (None, ""):
                    merged[key] = fide[key]
        if cbx:
            for key in ["club", "national_rating", "cbx_id"]:
                if cbx.get(key) not in (None, ""):
                    merged[key] = cbx[key]
        if lbx:
            # O registro LBX guarda o ID_No em external_id; propaga como lbx_id e
            # deixa o rating nacional/clube da LBX prevalecer (fonte regional).
            if lbx.get("external_id") not in (None, ""):
                merged["lbx_id"] = lbx["external_id"]
            for key in ["club", "national_rating"]:
                if lbx.get(key) not in (None, ""):
                    merged[key] = lbx[key]
        return merged

    @staticmethod
    def _official_payload(row: dict[str, Any], source: str) -> dict[str, Any]:
        pick = ImportService._pick
        parse_optional_int = ImportService._parse_optional_int
        # "fide_no"/"id_no"/"rtg_nat"/"rtg_int"/"clubname"/"birthday" sao os
        # cabecalhos do formato Swiss-Manager usado pela lista da LBX (Liga
        # Brasileira de Xadrez); os demais cobrem CSV/Excel proprios e a FIDE.
        fide_id = pick(row, "fide_id", "fide", "id_fide", "fideid", "fide_no")
        cbx_id = pick(row, "cbx_id", "cbx", "id_cbx", "cbxid")
        lbx_id = pick(row, "lbx_id", "lbx", "id_lbx", "id_no", "idno")

        if source == "FIDE":
            external_id = fide_id
        elif source == "LBX":
            lbx_id = lbx_id or pick(row, "id", "codigo", "code")
            external_id = lbx_id
            # A lista Swiss-Manager da LBX usa Fide_No para transportar o ID LBX.
            # Ele nao e um FIDE ID e nao pode contaminar exportacoes TRF.
            fide_id = ""
        else:  # CBX
            external_id = cbx_id
        external_id = external_id or pick(row, "id", "codigo", "code")

        surname = pick(row, "surname", "sobrenome", "last_name")
        given_name = pick(row, "given_name", "nome_proprio", "first_name")
        name = pick(row, "name", "nome", "jogador", "player")
        if not name:
            name = " ".join(part for part in [given_name, surname] if part).strip()

        standard_rating = parse_optional_int(pick(row, "standard_rating", "standard", "rating_standard", "std"))
        national_rating = parse_optional_int(
            pick(row, "national_rating", "rating_nacional", "elo_nacional", "cbx_rating", "rtg_nat")
        )
        international_rating = parse_optional_int(
            pick(row, "international_rating", "rating_internacional", "elo_fide", "fide_rating", "rtg_int")
        )
        generic_rating = parse_optional_int(pick(row, "rating", "elo", "rtg"))
        if source == "FIDE":
            international_rating = international_rating or standard_rating or generic_rating
            standard_rating = standard_rating or international_rating
        elif source == "LBX":
            national_rating = national_rating or generic_rating
            # Sem FIDE real, o Rtg_Int da lista LBX apenas espelha o Rtg_Nat — nao
            # e um ELO internacional, entao nao o propagamos como rating FIDE.
            if not fide_id:
                international_rating = 0
        else:  # CBX
            national_rating = national_rating or generic_rating

        return {
            # external_id ja carrega o ID_No da LBX; a busca por lbx_id usa
            # (source='LBX' AND external_id), entao nao ha coluna lbx_id aqui.
            "external_id": external_id,
            "fide_id": fide_id,
            "cbx_id": cbx_id,
            "name": name,
            "surname": surname,
            "given_name": given_name,
            "title": pick(row, "title", "titulo"),
            "sex": pick(row, "sex", "sexo"),
            "federation": pick(row, "federation", "fed", "federacao", "pais"),
            "club": pick(row, "club", "clube", "cidade", "clubname"),
            "birth_date": pick(row, "birth_date", "nascimento", "data_nascimento", "data_nac", "b-day", "b-year", "ano", "ano_nasc", "birthday"),
            "national_rating": national_rating,
            "international_rating": international_rating,
            "standard_rating": standard_rating,
            "rapid_rating": parse_optional_int(pick(row, "rapid_rating", "rapid", "rapido")),
            "blitz_rating": parse_optional_int(pick(row, "blitz_rating", "blitz")),
        }

    @staticmethod
    def _rating_for_order(
        initial_order: str,
        current: int,
        national: int,
        international: int,
    ) -> int:
        if initial_order == "national_rating":
            return national or current
        if initial_order == "international_rating":
            return international or current
        if initial_order == "international_then_national":
            return international or national or current
        if initial_order == "max_rating":
            return max(national, international, current)
        return max(national, international, current)

class InternalRatingService:
    HISTORY_REASON = "tournament_performance"

    def __init__(self, db: Database) -> None:
        self.db = db

    def apply_tournament_ratings(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        pairing_service = __import__('src.services.pairing_service', fromlist=['PairingService']).PairingService(self.db)
        updated = 0
        duplicates = 0
        skipped = 0
        external = 0
        no_member = 0

        for standing in pairing_service.standings(tournament_id):
            player = self.db.get_player(int(standing["player_id"]))
            if not player:
                skipped += 1
                continue
            member_id = int(player.get("member_id") or 0)
            if not member_id:
                external += 1
                continue

            performance = standing.get("performance")
            games = len(standing.get("earned_against") or [])
            if not isinstance(performance, int) or games <= 0:
                skipped += 1
                continue

            member = self.db.get_member(member_id)
            if not member:
                no_member += 1
                continue

            old_rating = int(member.get("rating") or 0)
            new_rating = self._next_rating(old_rating, int(performance), games)
            recorded = self.db.record_internal_rating_update(
                member_id=member_id,
                tournament_id=tournament_id,
                player_id=int(player["id"]),
                old_rating=old_rating,
                new_rating=new_rating,
                performance=int(performance),
                points=float(standing.get("points") or 0.0),
                games=games,
                reason=self.HISTORY_REASON,
            )
            if recorded:
                updated += 1
            else:
                duplicates += 1

        logger.info(
            "Rating interno aplicado no torneio %s: %s atualizados, %s ja aplicados",
            tournament_id,
            updated,
            duplicates,
        )
        return {
            "updated": updated,
            "duplicates": duplicates,
            "skipped": skipped,
            "external": external,
            "no_member": no_member,
        }

    def member_rating_history(self, member_id: int) -> list[dict[str, Any]]:
        member = self.db.get_member(member_id)
        if not member:
            raise AppError("Membro nao encontrado.")
        return self.db.list_member_rating_history(member_id)

    def ranking(
        self,
        category: str = "",
        active_only: bool = True,
        club_id: int | None = None,
        class_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        start_date = start_date.strip()
        end_date = end_date.strip()
        self._validate_optional_date(start_date, "Data inicial da temporada invalida.")
        self._validate_optional_date(end_date, "Data final da temporada invalida.")
        if start_date and end_date and start_date > end_date:
            raise AppError("Data final da temporada nao pode ser anterior a data inicial.")

        member_service = __import__('src.services.member_service', fromlist=['MemberService']).MemberService(self.db)
        rows = []
        for member in self.db.list_members(active_only=active_only, club_id=club_id, class_id=class_id):
            if category and str(member.get("category") or "") != category:
                continue
            rating_history = self.db.list_member_rating_history(int(member["id"]))
            filtered_history = [
                item
                for item in rating_history
                if self._history_item_in_period(item, start_date=start_date, end_date=end_date)
            ]
            latest_rating = filtered_history[0] if filtered_history else None
            summary = self._member_score_summary(
                member_service,
                int(member["id"]),
                start_date=start_date,
                end_date=end_date,
            )
            old_rating = int(latest_rating["old_rating"] or 0) if latest_rating else int(member.get("rating") or 0)
            new_rating = int(member.get("rating") or 0)
            period_delta = sum(
                int(item.get("new_rating") or 0) - int(item.get("old_rating") or 0)
                for item in filtered_history
            )
            delta = period_delta if start_date or end_date else (new_rating - old_rating if latest_rating else 0)
            rows.append(
                {
                    "member_id": member["id"],
                    "name": member["name"],
                    "club_name": member.get("club_name") or "",
                    "class_name": member.get("active_class_name") or "",
                    "category": member.get("category") or "",
                    "age_category": member.get("age_category") or "",
                    "rating_category": member.get("rating_category") or "",
                    "prize_tags": member.get("prize_tags") or "",
                    "member_type": member.get("member_type") or "",
                    "status": member.get("status") or "",
                    "rating": new_rating,
                    "last_delta": delta,
                    "last_performance": latest_rating["performance"] if latest_rating else "",
                    "last_tournament": latest_rating.get("tournament_name") if latest_rating else "",
                    "season_delta": period_delta,
                    **summary,
                }
            )

        rows.sort(
            key=lambda item: (
                -int(item["rating"] or 0),
                -float(item["score_rate"] or 0.0),
                -int(item["games"] or 0),
                str(item["name"]).casefold(),
            )
        )
        for position, row in enumerate(rows, start=1):
            row["position"] = position
        return rows

    def category_rankings(
        self,
        active_only: bool = True,
        club_id: int | None = None,
        class_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, list[dict[str, Any]]]:
        categories = sorted(
            {
                str(member.get("category") or "").strip()
                for member in self.db.list_members(active_only=active_only, club_id=club_id, class_id=class_id)
                if str(member.get("category") or "").strip()
            },
            key=lambda value: value.casefold(),
        )
        return {
            category: self.ranking(
                category=category,
                active_only=active_only,
                club_id=club_id,
                class_id=class_id,
                start_date=start_date,
                end_date=end_date,
            )
            for category in categories
        }

    def _member_score_summary(
        self,
        member_service: MemberService,
        member_id: int,
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        tournaments = member_service.tournament_history(member_id)
        wins = draws = losses = byes = games = 0
        points = 0.0
        for tournament in tournaments:
            tournament_date = str(tournament.get("start_date") or "")
            if not self._date_in_period(tournament_date, start_date, end_date):
                continue
            for result in member_service.tournament_results(member_id, int(tournament["tournament_id"])):
                if result["round_status"] != "closed" or result["outcome"] == "Pendente":
                    continue
                outcome = result["outcome"]
                if outcome == "Bye":
                    byes += 1
                    continue
                if outcome == "Vitoria":
                    wins += 1
                    games += 1
                elif outcome == "Empate":
                    draws += 1
                    games += 1
                elif outcome in {"Derrota", "Duplo WO"}:
                    losses += 1
                    games += 1
                if result["points"] is not None and outcome != "Bye":
                    points += float(result["points"] or 0.0)
        return {
            "tournaments": len(tournaments),
            "games": games,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "byes": byes,
            "points": round(points, 2),
            "score_rate": round((points / games) * 100, 1) if games else 0.0,
        }

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        if not value:
            return
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise AppError(message) from exc

    @staticmethod
    def _date_in_period(value: str, start_date: str, end_date: str) -> bool:
        if not start_date and not end_date:
            return True
        if not value:
            return False
        day = value[:10]
        if start_date and day < start_date:
            return False
        if end_date and day > end_date:
            return False
        return True

    @classmethod
    def _history_item_in_period(
        cls,
        item: Mapping[str, Any],
        start_date: str,
        end_date: str,
    ) -> bool:
        tournament_date = str(item.get("tournament_start_date") or "").strip()
        if tournament_date:
            return cls._date_in_period(tournament_date, start_date, end_date)
        return cls._date_in_period(str(item.get("created_at") or "")[:10], start_date, end_date)

    @staticmethod
    def _next_rating(current_rating: int, performance: int, games: int) -> int:
        if games <= 0:
            return int(current_rating or 0)
        if current_rating <= 0:
            return max(0, int(performance or 0))
        weight = min(0.40, max(0.08, games * 0.08))
        next_rating = current_rating + (performance - current_rating) * weight
        return max(0, int(round(next_rating)))


class FideRatingService:
    """Relatorio de variacao de rating FIDE (Fase B / spec E3).

    Estimativa de apoio ao arbitro (Ro, K, We, ΔElo, Rc, Rp). A homologacao
    oficial continua sendo da federacao — este relatorio nao substitui o
    processamento da lista pela FIDE/CBX.
    """

    RATING_TYPES = {"fide": "FIDE", "cbx": "CBX"}

    def __init__(self, db: Database) -> None:
        self.db = db

    def compute_report(self, tournament_id: int, rating_type: str = "fide") -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if rating_type not in self.RATING_TYPES:
            raise AppError("Tipo de rating invalido para o relatorio FIDE.")
        players = self.db.list_players(tournament_id, active_only=False)
        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        rows = build_fide_report_rows(
            players,
            closed_pairings,
            rating_type,
            tournament_year=self._tournament_year(tournament),
        )
        return {
            "tournament": tournament,
            "rating_type": rating_type,
            "rows": rows,
            "summary": self._summary(rows),
        }

    def save_report(self, tournament_id: int, rating_type: str = "fide") -> dict[str, Any]:
        report = self.compute_report(tournament_id, rating_type)
        self.db.save_fide_rating_report(tournament_id, rating_type, report["rows"])
        return report

    def get_saved_report(self, tournament_id: int, rating_type: str = "fide") -> list[dict[str, Any]]:
        return self.db.get_fide_rating_report(tournament_id, rating_type)

    @staticmethod
    def _tournament_year(tournament: Mapping[str, Any]) -> int:
        raw = str(tournament.get("start_date") or "").strip()
        if len(raw) >= 4 and raw[:4].isdigit():
            return int(raw[:4])
        return date.today().year

    @staticmethod
    def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        rated = [row for row in rows if row.get("ro")]
        deltas = [float(row["delta"]) for row in rated if row.get("delta") is not None]
        return {
            "players": len(rows),
            "rated_players": len(rated),
            "unrated_players": len(rows) - len(rated),
            "total_delta": round(sum(deltas), 2),
            "best_gain": round(max(deltas), 2) if deltas else 0.0,
            "worst_loss": round(min(deltas), 2) if deltas else 0.0,
        }


class NormAssistantService:
    """Assistente de normas/títulos FIDE (Fase E / spec E5).

    Estimativa de apoio ao árbitro: indica se um jogador atingiu indicadores
    compatíveis com uma norma. NÃO concede norma nem título — isso é exclusivo da
    FIDE e segue o regulamento completo.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def evaluate_tournament(self, tournament_id: int, rating_type: str = "fide") -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Normas FIDE disponiveis apenas para torneios individuais.")
        players = self.db.list_players(tournament_id, active_only=False)
        closed_pairings = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        return {
            "tournament": tournament,
            "rating_type": rating_type,
            "players": build_norm_report(players, closed_pairings, rating_type),
        }

    def evaluate(self, tournament_id: int, player_id: int, rating_type: str = "fide") -> dict[str, Any] | None:
        report = self.evaluate_tournament(tournament_id, rating_type)
        return next(
            (item for item in report["players"] if int(item["player_id"]) == int(player_id)),
            None,
        )
