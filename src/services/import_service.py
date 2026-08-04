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
from src.services.prizes import PRIZE_KINDS, PRIZE_POLICIES, allocate_prizes
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


# Campos canonicos de inscricao usados pelo assistente de importacao com
# mapeamento de colunas (REG-02) e pelo gerador de formulario padronizado
# (REG-01). Os sinonimos espelham os aceitos por ``_online_registration_payload``;
# a primeira chave de cada campo coincide com a chave canonica usada no payload,
# de modo que mapear uma coluna para ``key`` a torna reconhecivel por ``_pick``.
REGISTRATION_IMPORT_FIELDS: list[dict[str, Any]] = [
    {"key": "name", "label": "Nome completo", "required": True, "type": "text",
     "synonyms": ["name", "nome", "jogador", "nome completo", "nome completo do jogador",
                  "nome do jogador", "nome do atleta", "atleta", "participante", "full name"]},
    {"key": "surname", "label": "Sobrenome", "required": False, "type": "text",
     "synonyms": ["surname", "sobrenome", "last name"]},
    {"key": "given_name", "label": "Nome proprio", "required": False, "type": "text",
     "synonyms": ["given_name", "nome proprio", "nome_proprio", "first name", "primeiro nome"]},
    {"key": "birth_date", "label": "Data de nascimento", "required": False, "type": "date",
     "synonyms": ["birth_date", "nascimento", "data nascimento", "data de nascimento",
                  "data nasc", "dt nascimento", "data de nasc"]},
    {"key": "age", "label": "Idade", "required": False, "type": "integer",
     "synonyms": ["age", "idade", "anos"]},
    {"key": "sex", "label": "Sexo", "required": False, "type": "choice", "choices": ["M", "F"],
     "synonyms": ["sex", "sexo", "genero", "gênero", "genero do jogador"]},
    {"key": "club", "label": "Clube/Cidade", "required": False, "type": "text",
     "synonyms": ["club", "clube", "cidade", "clube cidade", "clube / cidade", "clube/cidade", "municipio"]},
    {"key": "category", "label": "Categoria", "required": False, "type": "text",
     "synonyms": ["category", "categoria", "categoria pretendida"]},
    {"key": "rating", "label": "Rating", "required": False, "type": "integer",
     "synonyms": ["rating", "rating principal", "elo", "rtg"]},
    {"key": "national_rating", "label": "Rating nacional (CBX)", "required": False, "type": "integer",
     "synonyms": ["national_rating", "rating nacional", "rating_nacional", "elo nacional",
                  "elo_nacional", "cbx_rating", "rating cbx"]},
    {"key": "international_rating", "label": "Rating internacional (FIDE)", "required": False, "type": "integer",
     "synonyms": ["international_rating", "rating internacional", "rating_internacional",
                  "elo fide", "elo_fide", "fide_rating", "rating fide"]},
    {"key": "fide_id", "label": "ID FIDE", "required": False, "type": "text",
     "synonyms": ["fide_id", "fide", "id fide", "id_fide", "fide id"]},
    {"key": "cbx_id", "label": "ID CBX", "required": False, "type": "text",
     "synonyms": ["cbx_id", "cbx", "id cbx", "id_cbx", "cbx id"]},
    {"key": "lbx_id", "label": "ID LBX", "required": False, "type": "text",
     "synonyms": ["lbx_id", "lbx", "id lbx", "id_lbx", "lbx id"]},
    {"key": "federation_id", "label": "ID federacao", "required": False, "type": "text",
     "synonyms": ["federation_id", "id federacao", "id_federacao", "federacao"]},
    {"key": "title", "label": "Titulo FIDE", "required": False, "type": "text",
     "synonyms": ["title", "titulo", "titulo fide"]},
]

# Perguntas do formulario de inscricao padronizado (REG-01). Os titulos sao
# escolhidos para que o CSV de respostas seja reconhecido por
# ``_online_registration_payload`` sem mapeamento manual.
REGISTRATION_FORM_QUESTIONS: list[dict[str, Any]] = [
    {"title": "Nome completo do jogador", "type": "text", "required": True},
    {"title": "Data de nascimento", "type": "date", "required": False},
    {"title": "Sexo", "type": "choice", "required": False, "choices": ["M", "F"]},
    {"title": "Clube/Cidade", "type": "text", "required": False},
    {"title": "Categoria", "type": "text", "required": False},
    {"title": "Rating", "type": "integer", "required": False},
    {"title": "FIDE ID", "type": "text", "required": False},
    {"title": "CBX ID", "type": "text", "required": False},
    {"title": "LBX ID", "type": "text", "required": False},
    {"title": "E-mail", "type": "text", "required": False},
    {"title": "Telefone/WhatsApp", "type": "text", "required": False},
]


class ImportService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def preview_online_registrations_csv(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        return self.preview_online_registrations(tournament_id, file_path)

    def preview_online_registrations(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        rows = self._online_registration_rows(tournament_id, file_path)
        summary = {
            "total": len(rows),
            "ready": sum(1 for row in rows if row["status"] == "ready"),
            "duplicate": sum(1 for row in rows if row["status"] == "duplicate"),
            "error": sum(1 for row in rows if row["status"] == "error"),
        }
        return {"rows": rows, **summary}

    def import_online_registrations_csv(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        return self.import_online_registrations(tournament_id, file_path)

    def import_online_registrations(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        preview = self.preview_online_registrations(tournament_id, file_path)
        result = self._persist_ready_rows(tournament_id, preview)
        logger.info(
            "%s inscricoes online importadas de %s para o torneio %s; %s ignoradas",
            result["imported"],
            file_path,
            tournament_id,
            result["skipped"],
        )
        return result

    def _persist_ready_rows(self, tournament_id: int, preview: dict[str, Any]) -> dict[str, Any]:
        imported = 0
        skipped = 0
        imported_player_ids: list[int] = []
        errors: list[str] = []
        for row in preview["rows"]:
            if row["status"] != "ready":
                skipped += 1
                if row["status"] == "error":
                    errors.append(f"Linha {row['line']}: {row['message']}")
                continue
            payload = row["payload"]
            imported_player_ids.append(self.db.create_player(tournament_id=tournament_id, **payload))
            imported += 1
        return {
            **preview,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "player_ids": imported_player_ids,
        }

    # --- REG-02: importacao com mapeamento de colunas ---------------------

    def inspect_source(self, source: str | Path, sample_size: int = 5) -> dict[str, Any]:
        """Le um arquivo/URL tabular e devolve cabecalhos, amostra e palpite de
        mapeamento por heuristica para o assistente de importacao."""
        tabular = self._read_tabular(source)
        headers = tabular["headers"]
        sample_rows = [dict(row) for _, row in tabular["rows"][: max(0, int(sample_size))]]
        fields = [
            {
                "key": field["key"],
                "label": field["label"],
                "required": field["required"],
                "type": field["type"],
                "choices": list(field.get("choices", [])),
            }
            for field in REGISTRATION_IMPORT_FIELDS
        ]
        return {
            "headers": headers,
            "sample_rows": sample_rows,
            "fields": fields,
            "suggested_mapping": self._suggest_mapping(headers),
            "total_rows": len(tabular["rows"]),
        }

    def _suggest_mapping(self, headers: list[str]) -> dict[str, str]:
        normalized_headers = [(header, self._normalize_key(header)) for header in headers]
        used: set[str] = set()
        mapping: dict[str, str] = {}
        for field in REGISTRATION_IMPORT_FIELDS:
            synonyms = [self._normalize_key(value) for value in field["synonyms"] if value]
            chosen = ""
            for header, normalized in normalized_headers:
                if header in used:
                    continue
                if normalized in synonyms:
                    chosen = header
                    break
            if not chosen:
                for header, normalized in normalized_headers:
                    if header in used or not normalized:
                        continue
                    if any(len(synonym) >= 3 and synonym in normalized for synonym in synonyms):
                        chosen = header
                        break
            mapping[field["key"]] = chosen
            if chosen:
                used.add(chosen)
        return mapping

    def _apply_mapping(self, row: dict[str, Any], mapping: Mapping[str, str]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for field_key, header in mapping.items():
            if not header or header not in row:
                continue
            mapped[field_key] = row.get(header, "")

        age_value = str(mapped.pop("age", "") or "").strip()
        if age_value and not str(mapped.get("birth_date") or "").strip():
            birth_year = self._birth_year_from_age(age_value)
            if birth_year:
                mapped["birth_date"] = birth_year

        name = str(mapped.get("name") or "").strip()
        if name and "," in name and not str(mapped.get("surname") or "").strip():
            surname, _, given = name.partition(",")
            surname = surname.strip()
            given = given.strip()
            if surname and given:
                mapped["surname"] = surname
                if not str(mapped.get("given_name") or "").strip():
                    mapped["given_name"] = given
                mapped["name"] = f"{given} {surname}"
        return mapped

    @staticmethod
    def _birth_year_from_age(value: str) -> str:
        try:
            age = int(float(str(value).strip()))
        except (ValueError, TypeError):
            return ""
        if age <= 0 or age > 120:
            return ""
        return str(date.today().year - age)

    def preview_mapped_registrations(
        self, tournament_id: int, source: str | Path, mapping: Mapping[str, str]
    ) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        name_header = mapping.get("name", "")
        if not name_header:
            raise AppError("Mapeie a coluna do nome do jogador antes de importar.")

        tabular = self._read_tabular(source)
        source_rows = [(line, self._apply_mapping(row, mapping)) for line, row in tabular["rows"]]
        rows = self._build_registration_rows(tournament_id, source_rows)
        summary = {
            "total": len(rows),
            "ready": sum(1 for row in rows if row["status"] == "ready"),
            "duplicate": sum(1 for row in rows if row["status"] == "duplicate"),
            "error": sum(1 for row in rows if row["status"] == "error"),
        }
        return {"rows": rows, **summary}

    def import_mapped_registrations(
        self, tournament_id: int, source: str | Path, mapping: Mapping[str, str]
    ) -> dict[str, Any]:
        preview = self.preview_mapped_registrations(tournament_id, source, mapping)
        result = self._persist_ready_rows(tournament_id, preview)
        logger.info(
            "%s inscricoes importadas com mapeamento de %s para o torneio %s; %s ignoradas",
            result["imported"],
            source,
            tournament_id,
            result["skipped"],
        )
        return result

    # --- REG-02: perfis de mapeamento reutilizaveis -----------------------

    def list_mapping_profiles(self) -> dict[str, dict[str, str]]:
        raw = str(self.db.get_app_settings().get("import_mapping_profiles") or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        profiles: dict[str, dict[str, str]] = {}
        for name, mapping in data.items():
            if isinstance(mapping, dict):
                profiles[str(name)] = {str(k): str(v) for k, v in mapping.items() if v}
        return profiles

    def save_mapping_profile(self, name: str, mapping: Mapping[str, str]) -> None:
        name = str(name or "").strip()
        if not name:
            raise AppError("Informe um nome para o perfil de mapeamento.")
        profiles = self.list_mapping_profiles()
        profiles[name] = {str(k): str(v) for k, v in mapping.items() if v}
        self.db.save_app_settings(
            {"import_mapping_profiles": json.dumps(profiles, ensure_ascii=False)}
        )

    def delete_mapping_profile(self, name: str) -> None:
        profiles = self.list_mapping_profiles()
        if str(name) in profiles:
            del profiles[str(name)]
            self.db.save_app_settings(
                {"import_mapping_profiles": json.dumps(profiles, ensure_ascii=False)}
            )

    def import_players_csv(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        rows = self._player_rows_from_csv(path)
        result = self._import_player_rows(tournament_id, rows, path)
        logger.info("%s jogadores importados de %s para o torneio %s", result["imported"], path, tournament_id)
        return result

    def import_trf(self, file_path: str | Path) -> dict[str, Any]:
        """Cria um novo torneio a partir de um arquivo TRF (FIDE/Swiss-Manager).

        Importa cabecalho, arbitros, calendario, jogadores, rodadas e equipes
        (FED-04). O que o arquivo nao tem — clube, categoria, inscricao — fica
        vazio; o round-trip promete o que o TRF carrega, e nao mais do que isso.
        """
        path = Path(file_path)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")

        parsed = parse_trf(content)
        if not parsed["players"]:
            raise AppError("Arquivo TRF sem jogadores reconheciveis (linhas 001).")

        name = parsed["name"] or f"Torneio importado ({path.stem})"
        rounds_count = parsed["rounds_count"] if parsed["rounds_count"] > 0 else 7
        tournament_id = self.db.create_tournament(
            name=name,
            location=parsed["location"],
            rounds_count=rounds_count,
            time_control=parsed["time_control"],
            start_date=parsed["start_date"],
            end_date=parsed["end_date"],
        )
        # Federacao, arbitros e calendario vinham no arquivo e eram descartados
        # (FED-04): o torneio importado nascia sem arbitro e sem datas, e o TRF
        # que ele exportava depois ja nao era o mesmo arquivo.
        ajustes = {
            chave: valor
            for chave, valor in (
                ("federation", parsed["federation"]),
                ("chief_arbiter", parsed.get("chief_arbiter", "")),
                ("arbiters", "\n".join(parsed.get("deputy_arbiters") or [])),
            )
            if valor
        }
        if ajustes:
            settings = self.db.get_tournament_settings(tournament_id) or {}
            settings.update(ajustes)
            self.db.save_tournament_settings(tournament_id, settings)

        agenda = [
            {"round_number": numero, "date": data, "time": ""}
            for numero, data in enumerate(parsed.get("round_dates") or [], start=1)
            if data
        ]
        if agenda:
            self.db.save_round_schedule(tournament_id, agenda)

        rank_to_id: dict[int, int] = {}
        for player in parsed["players"]:
            player_id = self.db.create_player(
                tournament_id=tournament_id,
                name=player["name"],
                surname=player["surname"],
                given_name=player["given_name"],
                title=player["title"],
                sex=player["sex"],
                rating=player["rating"],
                international_rating=player["rating"],
                federation_id=player["federation_id"],
                fide_id=player["fide_id"],
                birth_date=player["birth_date"],
            )
            rank_to_id[int(player["start_rank"])] = player_id

        equipes = self._create_imported_teams(tournament_id, parsed.get("teams") or [], rank_to_id)
        rounds = build_trf_rounds(parsed["players"], rank_to_id)
        for round_number, pairings in rounds:
            round_id = self.db.create_round_with_pairings(
                tournament_id,
                round_number,
                pairings,
                pairing_engine_version="trf-import",
                ruleset_version="trf-import",
            )
            self.db.close_round(round_id)

        logger.info(
            "TRF importado de %s: torneio %s com %s jogadores e %s rodadas",
            path,
            tournament_id,
            len(parsed["players"]),
            len(rounds),
        )
        return {
            "tournament_id": tournament_id,
            "name": name,
            "players_imported": len(parsed["players"]),
            "rounds_imported": len(rounds),
            "rounds_count": rounds_count,
            "teams_imported": equipes,
        }

    def _create_imported_teams(
        self,
        tournament_id: int,
        teams: list[dict[str, Any]],
        rank_to_id: dict[int, int],
    ) -> int:
        """Recria a secao de equipes do TRF (registros 013/310) — FED-04.

        O tabuleiro sai da ORDEM em que os start-ranks aparecem na linha, que e
        como o TRF declara a ordem de forca da equipe. Jogador que a linha cita e
        o arquivo nao traz e ignorado: melhor uma equipe menor do que uma equipe
        com um jogador inventado.
        """
        criadas = 0
        for equipe in teams:
            membros = [
                rank_to_id[int(rank)] for rank in equipe.get("start_ranks", []) if int(rank) in rank_to_id
            ]
            if not membros:
                continue
            team_id = self.db.create_team(tournament_id, str(equipe["name"]))
            for tabuleiro, player_id in enumerate(membros, start=1):
                self.db.add_player_to_team(team_id, player_id, board_number=tabuleiro)
            criadas += 1
        return criadas

    def import_players(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        extension = path.suffix.lower()
        if extension == ".csv":
            return self.import_players_csv(tournament_id, path)
        if extension in {".xls", ".xlsx"}:
            rows = self._player_rows_from_spreadsheet(path)
            result = self._import_player_rows(tournament_id, rows, path)
            logger.info("%s jogadores importados de %s para o torneio %s", result["imported"], path, tournament_id)
            return result
        raise AppError("Formato nao suportado. Use .csv, .xls ou .xlsx.")

    def import_members(self, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        extension = path.suffix.lower()
        if extension == ".csv":
            rows = self._player_rows_from_csv(path)
        elif extension in {".xls", ".xlsx"}:
            rows = self._player_rows_from_spreadsheet(path)
        else:
            raise AppError("Formato nao suportado. Use .csv, .xls ou .xlsx.")

        result = self._import_member_rows(rows)
        logger.info("%s membros importados de %s", result["imported"], path)
        return result

    def _import_member_rows(self, rows: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
        from src.services.member_service import MemberService

        member_service = MemberService(self.db)
        imported = 0
        skipped = 0
        errors: list[str] = []
        existing_members = self.db.list_members(active_only=False)
        seen_keys: set[tuple[str, str]] = set()

        for line_number, row in rows:
            payload, row_errors = self._member_payload_from_row(row)
            if row_errors:
                skipped += 1
                errors.extend(f"Linha {line_number}: {error}" for error in row_errors)
                continue

            duplicate_key = self._member_duplicate_key(payload)
            if duplicate_key in seen_keys or self._matches_existing_member(payload, existing_members):
                skipped += 1
                errors.append(f"Linha {line_number}: membro duplicado ignorado.")
                continue

            try:
                member_id = member_service.create_member(payload)
            except Exception as exc:
                skipped += 1
                errors.append(f"Linha {line_number}: {exc}")
                continue

            created = self.db.get_member(member_id)
            if created:
                existing_members.append(created)
            seen_keys.add(duplicate_key)
            imported += 1

        return {"imported": imported, "skipped": skipped, "errors": errors}

    def _member_payload_from_row(self, row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        full_name = self._pick(row, "name", "nome", "membro", "aluno", "jogador", "nome completo")
        surname = self._pick(row, "surname", "sobrenome")
        name = full_name
        if not surname and "," in full_name:
            surname, name = [part.strip() for part in full_name.split(",", maxsplit=1)]
        if not name:
            errors.append("nome vazio")

        rating_text = self._pick(row, "rating", "elo", "rtg")
        try:
            rating = int(float(rating_text)) if rating_text else 0
        except ValueError:
            rating = 0
            errors.append("rating invalido")

        club_id, club_error = self._resolve_club_id(
            self._pick(row, "club_id", "id_clube", "id escola", "id_escola"),
            self._pick(row, "club", "clube", "escola", "unidade"),
        )
        if club_error:
            errors.append(club_error)

        class_id, class_error = self._resolve_class_id(
            club_id,
            self._pick(row, "class_id", "id_turma", "turma_id"),
            self._pick(row, "class", "turma", "sala"),
        )
        if class_error:
            errors.append(class_error)

        learning_level_id = self._resolve_learning_level_id(
            self._pick(row, "learning_level_id", "nivel_id", "id_nivel"),
            self._pick(row, "learning_level", "nivel", "nivel de aprendizagem"),
        )
        member_type = self._normalize_member_type(self._pick(row, "member_type", "tipo", "vinculo"))
        status = self._normalize_member_status(self._pick(row, "status", "situacao"))

        payload = {
            "name": name,
            "surname": surname,
            "club_id": club_id,
            "class_id": class_id,
            "learning_level_id": learning_level_id,
            "city": self._pick(row, "city", "cidade"),
            "phone": self._pick(row, "phone", "telefone", "celular", "whatsapp"),
            "email": self._pick(row, "email", "e-mail"),
            "document": self._pick(row, "document", "documento", "cpf", "rg"),
            "birth_date": self._pick(row, "birth_date", "nascimento", "data nascimento", "data de nascimento"),
            "rating": rating,
            "category": self._pick(row, "category", "categoria"),
            "member_type": member_type,
            "status": status,
            "guardian_name": self._pick(row, "guardian_name", "responsavel", "responsável", "nome responsavel"),
            "guardian_phone": self._pick(row, "guardian_phone", "telefone responsavel", "telefone responsável"),
            "notes": self._pick(row, "notes", "observacoes", "observações"),
            "lichess_username": self._pick(row, "lichess", "lichess_username", "usuario lichess"),
            "chesscom_username": self._pick(row, "chesscom", "chesscom_username", "usuario chess.com"),
            "online_blitz_rating": self._parse_optional_int(
                self._pick(row, "online_blitz_rating", "blitz online", "rating blitz")
            ),
            "online_rapid_rating": self._parse_optional_int(
                self._pick(row, "online_rapid_rating", "rapid online", "rating rapid")
            ),
        }
        return payload, errors

    def _resolve_club_id(self, raw_id: str, raw_name: str) -> tuple[int, str]:
        if raw_id:
            try:
                club_id = int(raw_id)
            except ValueError:
                return 1, "id do clube/escola invalido"
            if self.db.get_club(club_id):
                return club_id, ""
            return 1, "clube/escola nao encontrado"

        if raw_name:
            normalized = self._normalize_text(raw_name)
            for club in self.db.list_clubs(active_only=False):
                if self._normalize_text(str(club.get("name") or "")) == normalized:
                    return int(club["id"]), ""
            club_id = self.db.save_club(
                name=raw_name,
                kind="school",
                active=1,
                club_id=None,
            )
            return club_id, ""
        return 1, ""

    def _resolve_class_id(self, club_id: int, raw_id: str, raw_name: str) -> tuple[int | None, str]:
        if raw_id:
            try:
                class_id = int(raw_id)
            except ValueError:
                return None, "id da turma invalido"
            class_data = self.db.get_class(class_id)
            if not class_data:
                return None, "turma nao encontrada"
            if int(class_data["club_id"]) != int(club_id):
                return None, "turma nao pertence ao clube/escola informado"
            return class_id, ""

        if raw_name:
            normalized = self._normalize_text(raw_name)
            for class_data in self.db.list_classes(club_id=club_id, active_only=False):
                if self._normalize_text(str(class_data.get("name") or "")) == normalized:
                    return int(class_data["id"]), ""
            class_id = self.db.create_class(club_id=club_id, name=raw_name, active=1)
            return class_id, ""
        return None, ""

    def _resolve_learning_level_id(self, raw_id: str, raw_name: str) -> int | None:
        if raw_id:
            try:
                level_id = int(raw_id)
            except ValueError:
                return None
            return level_id if self.db.get_learning_level(level_id) else None
        if raw_name:
            normalized = self._normalize_text(raw_name)
            for level in self.db.list_learning_levels(active_only=False):
                if self._normalize_text(str(level.get("name") or "")) == normalized:
                    return int(level["id"])
        return None

    @classmethod
    def _matches_existing_member(cls, payload: dict[str, Any], existing_members: list[dict[str, Any]]) -> bool:
        candidate_key = cls._member_duplicate_key(payload)
        for member in existing_members:
            if candidate_key == cls._member_duplicate_key(member):
                return True
        return False

    @staticmethod
    def _member_duplicate_key(payload: dict[str, Any]) -> tuple[str, str]:
        document = ImportService._normalize_text(str(payload.get("document") or ""))
        if document:
            return "document", document
        email = ImportService._normalize_text(str(payload.get("email") or ""))
        if email:
            return "email", email
        name = ImportService._normalize_text(str(payload.get("name") or ""))
        surname = ImportService._normalize_text(str(payload.get("surname") or ""))
        birth_date = str(payload.get("birth_date") or "").strip()
        return "name_birth", f"{surname}|{name}|{birth_date}"

    @staticmethod
    def _normalize_member_type(value: str) -> str:
        normalized = ImportService._normalize_text(value)
        mapping = {
            "": "aluno",
            "aluno": "aluno",
            "socio": "socio",
            "sócio": "socio",
            "convidado": "convidado",
            "visitante": "visitante",
        }
        return mapping.get(normalized, normalized if normalized in MEMBER_TYPES else "aluno")

    @staticmethod
    def _normalize_member_status(value: str) -> str:
        normalized = ImportService._normalize_text(value)
        mapping = {
            "": "active",
            "ativo": "active",
            "active": "active",
            "inativo": "inactive",
            "inactive": "inactive",
            "visitante": "visitor",
            "visitor": "visitor",
            "convidado": "guest",
            "guest": "guest",
            "desistente": "withdrawn",
            "withdrawn": "withdrawn",
        }
        return mapping.get(normalized, normalized if normalized in MEMBER_STATUSES else "active")

    def _import_player_rows(
        self,
        tournament_id: int,
        rows: list[tuple[int, dict[str, Any]]],
        path: Path,
    ) -> dict[str, Any]:
        imported = 0
        errors: list[str] = []

        for line_number, row in rows:
            name = self._pick(
                row, "name", "nome", "jogador", "nome completo", "nome do jogador",
                "nome do atleta", "atleta", "participante", "full name",
            )
            if not name:
                errors.append(f"Linha {line_number}: nome vazio.")
                continue

            national_rating = self._parse_optional_int(
                self._pick(row, "national_rating", "rating_nacional", "elo_nacional", "cbx_rating")
            )
            international_rating = self._parse_optional_int(
                self._pick(row, "international_rating", "rating_internacional", "elo_fide", "fide_rating")
            )
            rating_text = self._pick(row, "rating", "elo", "rtg")
            if rating_text:
                try:
                    rating = int(float(rating_text))
                except ValueError:
                    errors.append(f"Linha {line_number}: rating invalido.")
                    continue
            else:
                rating = max(national_rating, international_rating)

            self.db.create_player(
                tournament_id=tournament_id,
                name=name,
                club=self._pick(row, "club", "clube", "cidade"),
                rating=rating,
                category=self._pick(row, "category", "categoria"),
                federation_id=self._pick(row, "federation_id", "id_federacao"),
                fide_id=self._pick(row, "fide_id", "fide", "id_fide"),
                cbx_id=self._pick(row, "cbx_id", "cbx", "id_cbx"),
                lbx_id=self._pick(row, "lbx_id", "lbx", "id_lbx"),
                birth_date=self._pick(row, "birth_date", "nascimento", "data_nascimento"),
                surname=self._pick(row, "surname", "sobrenome"),
                given_name=self._pick(row, "given_name", "nome_proprio"),
                title=self._pick(row, "title", "titulo"),
                sex=self._pick(row, "sex", "sexo"),
                national_rating=national_rating,
                international_rating=international_rating,
            )
            imported += 1

        return {"imported": imported, "errors": errors}

    def _read_tabular(self, source: str | Path) -> dict[str, Any]:
        """Le CSV/XLS/XLSX (arquivo ou URL CSV publicada) e devolve
        ``{"headers": [...], "rows": [(linha, {coluna: valor})]}``."""
        source_text = str(source).strip()
        if self._is_url(source_text):
            return self._tabular_from_url(source_text)
        path = Path(source)
        extension = path.suffix.lower()
        if extension == ".csv":
            return self._tabular_from_csv_text(path.read_text(encoding="utf-8-sig"))
        if extension in {".xls", ".xlsx"}:
            return self._tabular_from_spreadsheet(path)
        raise AppError("Formato nao suportado. Use .csv, .xls, .xlsx ou link CSV do Google Sheets.")

    def _tabular_from_csv_text(self, content: str) -> dict[str, Any]:
        sample = content[:4096]
        reader = csv.DictReader(io.StringIO(content), dialect=self._csv_dialect(sample))
        if not reader.fieldnames:
            raise AppError("CSV sem cabecalho.")
        headers = [str(name) for name in reader.fieldnames]
        rows = [(line_number, dict(row)) for line_number, row in enumerate(reader, start=2)]
        return {"headers": headers, "rows": rows}

    def _tabular_from_url(self, url: str) -> dict[str, Any]:
        csv_url = self._google_sheets_csv_url(url)
        request = Request(csv_url, headers={"User-Agent": "Albericus"})
        try:
            with urlopen(request, timeout=20) as response:
                content = response.read().decode("utf-8-sig")
        except Exception as exc:
            raise AppError(f"Nao foi possivel baixar a planilha: {exc}") from exc
        return self._tabular_from_csv_text(content)

    def _tabular_from_spreadsheet(self, path: Path) -> dict[str, Any]:
        try:
            import pandas as pd
        except ImportError as exc:
            raise AppError("Importacao Excel indisponivel. Instale pandas, openpyxl e xlrd.") from exc

        try:
            dataframe = pd.read_excel(path, sheet_name=0, dtype=object)
        except Exception as exc:
            raise AppError(f"Nao foi possivel ler a planilha: {exc}") from exc

        if dataframe.columns.empty:
            raise AppError("Planilha sem cabecalho.")

        headers = [str(column) for column in dataframe.columns]
        rows: list[tuple[int, dict[str, Any]]] = []
        for index, row in dataframe.iterrows():
            parsed = {str(column): self._clean_spreadsheet_cell(value) for column, value in row.items()}
            rows.append((int(index) + 2, parsed))
        return {"headers": headers, "rows": rows}

    def _player_rows_from_csv(self, path: Path) -> list[tuple[int, dict[str, Any]]]:
        return self._tabular_from_csv_text(path.read_text(encoding="utf-8-sig"))["rows"]

    def _player_rows_from_spreadsheet(self, path: Path) -> list[tuple[int, dict[str, Any]]]:
        return self._tabular_from_spreadsheet(path)["rows"]

    @staticmethod
    def _clean_spreadsheet_cell(value: Any) -> Any:
        try:
            import pandas as pd

            if pd.isna(value):
                return ""
        except Exception:
            pass
        return value

    def import_rating_list_csv(self, file_path: str | Path, rating_type: str = "fide") -> dict[str, Any]:
        """Importa um CSV de ratings FIDE ou CBX e atualiza os membros do clube correspondentes."""
        path = Path(file_path)
        updated = 0
        skipped = 0
        errors: list[str] = []

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            sample = file.read(4096)
            file.seek(0)
            reader = csv.DictReader(file, dialect=self._csv_dialect(sample))
            if not reader.fieldnames:
                raise AppError("CSV sem cabecalho.")
                
            all_members = self.db.list_members()
            fide_map = {str(m.get("fide_id")).strip(): m["id"] for m in all_members if m.get("fide_id")}
            cbx_map = {str(m.get("cbx_id")).strip(): m["id"] for m in all_members if m.get("cbx_id")}

            for line_number, row in enumerate(reader, start=2):
                player_id_csv = self._pick(row, "fide_id", "fide", "id_fide", "idnumber", "id", "cbx_id", "cbx", "id_cbx")
                if not player_id_csv:
                    errors.append(f"Linha {line_number}: ID (FIDE/CBX) nao encontrado.")
                    skipped += 1
                    continue
                    
                player_id_csv = str(player_id_csv).strip()
                rating_text = self._pick(row, "rating", "elo", "rtg", "standard", "rating_fide", "rating_cbx")
                if not rating_text:
                    errors.append(f"Linha {line_number}: Rating vazio.")
                    skipped += 1
                    continue
                    
                try:
                    rating = int(float(rating_text))
                except ValueError:
                    errors.append(f"Linha {line_number}: Rating invalido ({rating_text}).")
                    skipped += 1
                    continue
                    
                member_id = None
                if rating_type == "fide":
                    member_id = fide_map.get(player_id_csv)
                else:
                    member_id = cbx_map.get(player_id_csv)
                    
                if not member_id:
                    skipped += 1
                    continue
                    
                member = self.db.get_member(member_id)
                if not member:
                    continue
                    
                payload = dict(member)
                if rating_type == "fide":
                    payload["international_rating"] = rating
                else:
                    payload["national_rating"] = rating
                    
                self.db.update_member(member_id, payload)
                updated += 1
                
        logger.info("%s membros atualizados via importacao de rating %s de %s", updated, rating_type, path)
        return {"updated": updated, "skipped": skipped, "errors": errors}

    def _online_registration_rows(self, tournament_id: int, file_path: str | Path) -> list[dict[str, Any]]:
        source_rows = self._online_registration_source_rows(file_path)
        return self._build_registration_rows(tournament_id, source_rows)

    def _build_registration_rows(
        self, tournament_id: int, source_rows: list[tuple[int, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        existing_players = self.db.list_players(tournament_id, active_only=False)
        rows = []
        seen_keys: set[tuple[str, str]] = set()

        for line_number, row in source_rows:
            parsed = self._online_registration_payload(row)
            status = "ready"
            status_label = "Pronto"
            message = "Pronto para importar"
            payload = parsed.get("payload") or {}

            if parsed["errors"]:
                status = "error"
                status_label = "Erro"
                message = "; ".join(parsed["errors"])
            else:
                duplicate_key = self._registration_duplicate_key(payload)
                if self._matches_existing_player(payload, existing_players):
                    status = "duplicate"
                    status_label = "Duplicado"
                    message = "Ja existe jogador equivalente no torneio"
                elif duplicate_key in seen_keys:
                    status = "duplicate"
                    status_label = "Duplicado"
                    message = "Inscricao repetida no proprio arquivo"
                else:
                    seen_keys.add(duplicate_key)

            rows.append(
                {
                    "line": line_number,
                    "status": status,
                    "status_label": status_label,
                    "message": message,
                    "name": payload.get("name", parsed.get("name", "")),
                    "birth_date": payload.get("birth_date", ""),
                    "rating": payload.get("rating", ""),
                    "club": payload.get("club", ""),
                    "category": payload.get("category", ""),
                    "fide_id": payload.get("fide_id", ""),
                    "cbx_id": payload.get("cbx_id", ""),
                    "payload": payload,
                }
            )
        return rows

    def _online_registration_source_rows(self, source: str | Path) -> list[tuple[int, dict[str, Any]]]:
        source_text = str(source).strip()
        if self._is_url(source_text):
            return self._player_rows_from_csv_url(source_text)

        path = Path(source)
        extension = path.suffix.lower()
        if extension == ".csv":
            return self._player_rows_from_csv(path)
        if extension in {".xls", ".xlsx"}:
            return self._player_rows_from_spreadsheet(path)
        raise AppError("Formato nao suportado. Use .csv, .xls, .xlsx ou link CSV do Google Sheets.")

    @staticmethod
    def _is_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _player_rows_from_csv_url(self, url: str) -> list[tuple[int, dict[str, Any]]]:
        return self._tabular_from_url(url)["rows"]

    @staticmethod
    def _google_sheets_csv_url(url: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "docs.google.com" not in parsed.netloc or "/spreadsheets/" not in parsed.path:
            return url
        if query.get("output", [""])[0].lower() == "csv":
            return url

        parts = parsed.path.strip("/").split("/")
        try:
            sheet_id = parts[parts.index("d") + 1]
        except (ValueError, IndexError):
            return url

        fragment_query = parse_qs(parsed.fragment)
        gid = (query.get("gid") or fragment_query.get("gid") or ["0"])[0]
        export_query = urlencode({"format": "csv", "gid": gid})
        return urlunparse((parsed.scheme, parsed.netloc, f"/spreadsheets/d/{sheet_id}/export", "", export_query, ""))

    def _online_registration_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        errors = []
        name = self._pick(
            row,
            "name",
            "nome",
            "jogador",
            "nome completo",
            "nome completo do jogador",
            "nome do jogador",
        )
        if not name:
            return {"name": "", "payload": {}, "errors": ["nome vazio"]}

        national_rating = self._parse_optional_int(
            self._pick(
                row,
                "national_rating",
                "rating nacional",
                "rating_nacional",
                "elo nacional",
                "elo_nacional",
                "cbx_rating",
            )
        )
        international_rating = self._parse_optional_int(
            self._pick(
                row,
                "international_rating",
                "rating internacional",
                "rating_internacional",
                "elo fide",
                "elo_fide",
                "fide_rating",
            )
        )
        rating_text = self._pick(row, "rating", "rating principal", "elo", "rtg")
        try:
            rating = int(float(rating_text)) if rating_text else max(national_rating, international_rating)
        except ValueError:
            rating = 0
            errors.append("rating invalido")

        birth_date = self._pick(row, "birth_date", "nascimento", "data nascimento", "data de nascimento")
        sex = self._pick(row, "sex", "sexo", "genero", "genero do jogador", "gênero")
        payload = {
            "name": name,
            "club": self._pick(row, "club", "clube", "cidade", "clube cidade", "clube / cidade"),
            "rating": rating,
            "category": self._pick(row, "category", "categoria", "categoria pretendida"),
            "federation_id": self._pick(row, "federation_id", "id federacao", "id_federacao"),
            "fide_id": self._pick(row, "fide_id", "fide", "id fide", "id_fide", "fide id"),
            "cbx_id": self._pick(row, "cbx_id", "cbx", "id cbx", "id_cbx", "cbx id"),
            "lbx_id": self._pick(row, "lbx_id", "lbx", "id lbx", "id_lbx", "lbx id"),
            "birth_date": birth_date,
            "surname": self._pick(row, "surname", "sobrenome"),
            "given_name": self._pick(row, "given_name", "nome proprio", "nome_proprio"),
            "title": self._pick(row, "title", "titulo", "titulo fide"),
            "sex": sex,
            "national_rating": national_rating,
            "international_rating": international_rating,
        }
        return {"name": name, "payload": payload, "errors": errors}

    @staticmethod
    def _csv_dialect(sample: str) -> Any:
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;")
        except csv.Error:
            first_line = sample.splitlines()[0] if sample.splitlines() else ""
            if first_line.count(";") > first_line.count(","):
                class SemicolonDialect(csv.excel):
                    delimiter = ";"

                return SemicolonDialect
            return csv.get_dialect("excel")

    @staticmethod
    def _registration_duplicate_key(payload: dict[str, Any]) -> tuple[str, str]:
        fide_id = str(payload.get("fide_id") or "").strip()
        if fide_id:
            return "fide", fide_id.casefold()
        cbx_id = str(payload.get("cbx_id") or "").strip()
        if cbx_id:
            return "cbx", cbx_id.casefold()
        lbx_id = str(payload.get("lbx_id") or "").strip()
        if lbx_id:
            return "lbx", lbx_id.casefold()
        name = ImportService._normalize_text(str(payload.get("name") or ""))
        birth_date = str(payload.get("birth_date") or "").strip()
        if birth_date:
            return "name_birth", f"{name}|{birth_date}"
        club = ImportService._normalize_text(str(payload.get("club") or ""))
        return "name_club", f"{name}|{club}"

    @classmethod
    def _matches_existing_player(
        cls,
        payload: dict[str, Any],
        existing_players: list[dict[str, Any]],
    ) -> bool:
        candidate_key = cls._registration_duplicate_key(payload)
        for player in existing_players:
            player_key = cls._registration_duplicate_key(player)
            if candidate_key == player_key:
                return True
        return False

    @staticmethod
    def _pick(row: dict[str, Any], *keys: str) -> str:
        normalized = {ImportService._normalize_key(key): value for key, value in row.items()}
        for key in keys:
            value = normalized.get(ImportService._normalize_key(key))
            if value is not None:
                return str(value).strip()
        return ""

    @staticmethod
    def _normalize_key(value: str) -> str:
        text = ImportService._normalize_text(value)
        return "".join(character for character in text if character.isalnum())

    @staticmethod
    def _normalize_text(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
        return "".join(character for character in decomposed if not unicodedata.combining(character))

    @staticmethod
    def _parse_optional_int(value: str) -> int:
        if not value:
            return 0
        try:
            return int(float(value))
        except ValueError:
            return 0
