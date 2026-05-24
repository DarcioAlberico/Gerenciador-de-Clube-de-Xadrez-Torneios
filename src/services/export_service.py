from __future__ import annotations
import csv
import html
import json
import logging
import math
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.services.constants import *

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

class ImportService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def preview_online_registrations_csv(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
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
        preview = self.preview_online_registrations_csv(tournament_id, file_path)
        imported = 0
        skipped = 0
        imported_player_ids = []
        errors = []
        for row in preview["rows"]:
            if row["status"] != "ready":
                skipped += 1
                if row["status"] == "error":
                    errors.append(f"Linha {row['line']}: {row['message']}")
                continue
            payload = row["payload"]
            imported_player_ids.append(self.db.create_player(tournament_id=tournament_id, **payload))
            imported += 1

        logger.info(
            "%s inscricoes online importadas de %s para o torneio %s; %s ignoradas",
            imported,
            file_path,
            tournament_id,
            skipped,
        )
        return {
            **preview,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "player_ids": imported_player_ids,
        }

    def import_players_csv(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        imported = 0
        errors: list[str] = []

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            sample = file.read(4096)
            file.seek(0)
            reader = csv.DictReader(file, dialect=self._csv_dialect(sample))
            if not reader.fieldnames:
                raise AppError("CSV sem cabecalho.")

            for line_number, row in enumerate(reader, start=2):
                name = self._pick(row, "name", "nome", "jogador")
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
                    birth_date=self._pick(row, "birth_date", "nascimento", "data_nascimento"),
                    surname=self._pick(row, "surname", "sobrenome"),
                    given_name=self._pick(row, "given_name", "nome_proprio"),
                    title=self._pick(row, "title", "titulo"),
                    sex=self._pick(row, "sex", "sexo"),
                    national_rating=national_rating,
                    international_rating=international_rating,
                )
                imported += 1

        logger.info("%s jogadores importados de %s para o torneio %s", imported, path, tournament_id)
        return {"imported": imported, "errors": errors}

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
        path = Path(file_path)
        existing_players = self.db.list_players(tournament_id, active_only=False)
        rows = []
        seen_keys: set[tuple[str, str]] = set()

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            sample = file.read(4096)
            file.seek(0)
            dialect = self._csv_dialect(sample)
            reader = csv.DictReader(file, dialect=dialect)
            if not reader.fieldnames:
                raise AppError("CSV sem cabecalho.")

            for line_number, row in enumerate(reader, start=2):
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
                        message = "Inscricao repetida no proprio CSV"
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

class CertificateService:
    def __init__(self, db: Database, pairing_service: PairingService) -> None:
        self.db = db
        self.pairing_service = pairing_service

    def list_templates(self, active_only: bool = True) -> list[dict[str, Any]]:
        return self.db.list_certificate_templates(active_only=active_only)

    def list_issuances(
        self,
        limit: int = 50,
        context_type: str = "",
        verification_code: str = "",
        recipient_name: str = "",
        include_revoked: bool = True,
    ) -> list[dict[str, Any]]:
        return self.db.list_certificate_issuances(
            limit=limit,
            context_type=context_type,
            verification_code=verification_code,
            recipient_name=recipient_name,
            include_revoked=include_revoked,
        )

    def verify_issuance(self, verification_code: str) -> dict[str, Any]:
        issuance = self.db.get_certificate_issuance_by_code(verification_code)
        if not issuance:
            raise AppError("Codigo de verificacao nao encontrado.")
        return issuance

    def revoke_issuance(self, issuance_id: int, notes: str = "") -> None:
        self.db.revoke_certificate_issuance(issuance_id, notes=notes)

    def export_verification_site(
        self,
        file_path: str | Path,
        include_revoked: bool = True,
        limit: int = 5000,
    ) -> Path:
        issuances = self.list_issuances(limit=limit, include_revoked=include_revoked)
        if not issuances:
            raise AppError("Nao ha diplomas emitidos para exportar.")

        path = Path(file_path)
        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._verification_site_html(issuances), encoding="utf-8")
        logger.info("Verificador de diplomas exportado em %s", path)
        return path

    def get_template(self, template_id: int) -> dict[str, Any]:
        template = self.db.get_certificate_template(template_id)
        if not template:
            raise AppError("Modelo de diploma nao encontrado.")
        return template

    def create_template(self, data: dict[str, Any]) -> int:
        payload = self._validated_template_payload(data)
        try:
            template_id = self.db.create_certificate_template(**payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Ja existe um modelo de diploma com este nome.") from exc
        logger.info("Modelo de diploma criado: %s", template_id)
        return template_id

    def update_template(self, template_id: int, data: dict[str, Any]) -> None:
        if not self.db.get_certificate_template(template_id):
            raise AppError("Modelo de diploma nao encontrado.")
        payload = self._validated_template_payload(data)
        try:
            self.db.update_certificate_template(template_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Ja existe um modelo de diploma com este nome.") from exc
        logger.info("Modelo de diploma atualizado: %s", template_id)

    def preview_template(
        self,
        tournament_id: int,
        template_id: int,
        category: str = "",
        top_n: Any = 0,
        player_ids: list[int] | None = None,
        by_category: bool = False,
    ) -> dict[str, str]:
        template = self.get_template(template_id)
        recipients = self.tournament_recipients(
            tournament_id,
            certificate_type=str(template["certificate_type"]),
            category=category,
            top_n=top_n,
            player_ids=player_ids,
            by_category=by_category,
        )
        recipient = recipients[0]
        return {
            "title": self._render_template_text(str(template.get("title_template") or ""), recipient),
            "body": self._render_template_text(str(template.get("body_template") or ""), recipient),
            "footer": self._render_template_text(str(template.get("footer_template") or ""), recipient),
            "signature_left": self._render_template_text(str(template.get("signature_left") or ""), recipient),
            "signature_right": self._render_template_text(str(template.get("signature_right") or ""), recipient),
        }

    def preview_template_data(
        self,
        tournament_id: int,
        template_data: dict[str, Any],
        category: str = "",
        top_n: Any = 0,
        player_ids: list[int] | None = None,
        by_category: bool = False,
    ) -> dict[str, str]:
        template = self._template_for_export(None, "participation", template_data=template_data)
        recipients = self.tournament_recipients(
            tournament_id,
            certificate_type=str(template["certificate_type"]),
            category=category,
            top_n=top_n,
            player_ids=player_ids,
            by_category=by_category,
        )
        recipient = recipients[0]
        return {
            "title": self._plain_rendered_text(str(template.get("title_template") or ""), recipient),
            "body": self._plain_rendered_text(str(template.get("body_template") or ""), recipient),
            "footer": self._plain_rendered_text(str(template.get("footer_template") or ""), recipient),
        }

    def preview_template_recipient(
        self,
        template_data: dict[str, Any],
        recipient: dict[str, Any],
    ) -> dict[str, str]:
        template = self._template_for_export(
            None,
            str(template_data.get("certificate_type", "participation") or "participation"),
            template_data=template_data,
        )
        return {
            "title": self._plain_rendered_text(str(template.get("title_template") or ""), recipient),
            "body": self._plain_rendered_text(str(template.get("body_template") or ""), recipient),
            "footer": self._plain_rendered_text(str(template.get("footer_template") or ""), recipient),
        }

    def tournament_recipients(
        self,
        tournament_id: int,
        certificate_type: str = "participation",
        category: str = "",
        top_n: Any = 0,
        player_ids: list[int] | None = None,
        by_category: bool = False,
    ) -> list[dict[str, Any]]:
        tournament = self._individual_tournament(tournament_id)
        if certificate_type not in CERTIFICATE_TYPES:
            raise AppError("Modelo de diploma invalido.")

        standings = self.pairing_service.standings(tournament_id)
        if not standings:
            raise AppError("Nao ha jogadores no torneio selecionado.")

        top_limit = self._parse_top_n(top_n)
        use_category_ranking = by_category or certificate_type == "category_award"
        selected_ids = {int(player_id) for player_id in player_ids} if player_ids is not None else None
        category_filter = str(category or "").strip()
        category_positions = self._category_positions(standings)
        recipients = []
        for standing in standings:
            recipient = self._recipient_payload(tournament, standing, category_positions)
            if selected_ids is not None:
                if int(recipient["player_id"]) not in selected_ids:
                    continue
            else:
                if category_filter and recipient["category"] != category_filter:
                    continue
                if use_category_ranking:
                    if top_limit and int(recipient["category_position"]) > top_limit:
                        continue
                elif top_limit and int(recipient["position"]) > top_limit:
                    continue
            recipients.append(recipient)

        if not recipients:
            raise AppError("Nenhum jogador encontrado para os filtros selecionados.")
        return recipients

    def tournament_categories(self, tournament_id: int) -> list[str]:
        tournament = self._individual_tournament(tournament_id)
        return sorted(
            {
                str(item.get("category") or "").strip()
                for item in self.pairing_service.standings(int(tournament["id"]))
                if str(item.get("category") or "").strip()
            },
            key=lambda value: value.casefold(),
        )

    def member_recipients(
        self,
        member_ids: list[int] | None = None,
        active_only: bool = True,
        class_id: int | None = None,
    ) -> list[dict[str, Any]]:
        selected_ids = {int(member_id) for member_id in member_ids} if member_ids is not None else None
        recipients = []
        for member in self.db.list_members(active_only=active_only, class_id=class_id):
            if selected_ids is not None and int(member["id"]) not in selected_ids:
                continue
            recipients.append(self._member_recipient_payload(member))
        if not recipients:
            raise AppError("Nenhum membro encontrado para os filtros selecionados.")
        return recipients

    def training_recipients(
        self,
        session_id: int,
        present_only: bool = True,
        member_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        session = self.db.get_training_session(session_id)
        if not session:
            raise AppError("Aula/turma nao encontrada.")
        selected_ids = {int(member_id) for member_id in member_ids} if member_ids is not None else None
        rows = self.db.list_session_attendance(session_id)
        if not rows:
            rows = self.db.list_session_members_for_attendance(session_id)
        recipients = []
        for row in rows:
            member_id = int(row.get("member_id") or row.get("id") or 0)
            raw_attendance_status = row.get("attendance_status")
            if raw_attendance_status is None and row.get("member_name"):
                raw_attendance_status = row.get("status")
            attendance_status = str(raw_attendance_status or "")
            if selected_ids is not None and member_id not in selected_ids:
                continue
            if present_only and attendance_status and attendance_status != "present":
                continue
            recipients.append(self._training_recipient_payload(session, row, attendance_status))
        if not recipients:
            raise AppError("Nenhum aluno encontrado para a aula/turma selecionada.")
        return recipients

    def event_recipients(
        self,
        event_id: int,
        member_ids: list[int] | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        event = self.db.get_club_event(event_id)
        if not event:
            raise AppError("Evento nao encontrado.")
        selected_ids = {int(member_id) for member_id in member_ids} if member_ids is not None else None
        recipients = []
        for member in self.db.list_members(active_only=active_only, club_id=int(event.get("club_id") or 0) or None):
            if selected_ids is not None and int(member["id"]) not in selected_ids:
                continue
            recipients.append(self._event_recipient_payload(event, member))
        if not recipients:
            raise AppError("Nenhum membro encontrado para o evento selecionado.")
        return recipients

    def ranking_recipients(
        self,
        category: str = "",
        top_n: Any = 3,
        member_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        selected_ids = {int(member_id) for member_id in member_ids} if member_ids is not None else None
        top_limit = self._parse_top_n(top_n)
        ranking = __import__('src.services.rating_service', fromlist=['InternalRatingService']).InternalRatingService(self.db).ranking(category=category, active_only=True)
        recipients = []
        for item in ranking:
            if selected_ids is not None and int(item["member_id"]) not in selected_ids:
                continue
            if selected_ids is None and top_limit and int(item["position"]) > top_limit:
                continue
            recipients.append(self._ranking_recipient_payload(item))
        if not recipients:
            raise AppError("Nenhum membro encontrado no ranking interno.")
        return recipients

    def export_tournament_certificates(
        self,
        tournament_id: int,
        file_path: str | Path,
        certificate_type: str = "participation",
        template_id: int | None = None,
        template_data: dict[str, Any] | None = None,
        category: str = "",
        top_n: Any = 0,
        player_ids: list[int] | None = None,
        by_category: bool = False,
    ) -> dict[str, Any]:
        tournament = self._individual_tournament(tournament_id)
        template = self._template_for_export(template_id, certificate_type, template_data)
        certificate_type = str(template["certificate_type"])
        recipients = self.tournament_recipients(
            tournament_id,
            certificate_type=certificate_type,
            category=category,
            top_n=top_n,
            player_ids=player_ids,
            by_category=by_category,
        )
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        path.parent.mkdir(parents=True, exist_ok=True)
        return self._export_context_certificates(
            path,
            template,
            recipients,
            source_title=str(tournament.get("name") or ""),
            context_type="tournament",
            source_id=tournament_id,
        )

    def export_member_certificates(
        self,
        file_path: str | Path,
        template_id: int | None = None,
        template_data: dict[str, Any] | None = None,
        member_ids: list[int] | None = None,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        template = self._template_for_export(template_id, "member_certificate", template_data)
        recipients = self.member_recipients(member_ids=member_ids, class_id=class_id)
        return self._export_context_certificates(
            file_path,
            template,
            recipients,
            "Membros",
            context_type="members",
            source_id=class_id,
        )

    def export_training_certificates(
        self,
        session_id: int,
        file_path: str | Path,
        template_id: int | None = None,
        template_data: dict[str, Any] | None = None,
        present_only: bool = True,
        member_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        template = self._template_for_export(template_id, "training_participation", template_data)
        session = self.db.get_training_session(session_id)
        recipients = self.training_recipients(session_id, present_only=present_only, member_ids=member_ids)
        return self._export_context_certificates(
            file_path,
            template,
            recipients,
            str(session.get("title") if session else "Aula"),
            context_type="training",
            source_id=session_id,
        )

    def export_event_certificates(
        self,
        event_id: int,
        file_path: str | Path,
        template_id: int | None = None,
        template_data: dict[str, Any] | None = None,
        member_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        template = self._template_for_export(template_id, "event_participation", template_data)
        event = self.db.get_club_event(event_id)
        recipients = self.event_recipients(event_id, member_ids=member_ids)
        return self._export_context_certificates(
            file_path,
            template,
            recipients,
            str(event.get("title") if event else "Evento"),
            context_type="event",
            source_id=event_id,
        )

    def export_ranking_certificates(
        self,
        file_path: str | Path,
        template_id: int | None = None,
        template_data: dict[str, Any] | None = None,
        category: str = "",
        top_n: Any = 3,
        member_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        template = self._template_for_export(template_id, "internal_ranking", template_data)
        recipients = self.ranking_recipients(category=category, top_n=top_n, member_ids=member_ids)
        return self._export_context_certificates(
            file_path,
            template,
            recipients,
            "Ranking interno",
            context_type="ranking",
            source_id=None,
        )

    def _export_context_certificates(
        self,
        file_path: str | Path,
        template: dict[str, Any],
        recipients: list[dict[str, Any]],
        source_title: str,
        context_type: str,
        source_id: int | None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        path.parent.mkdir(parents=True, exist_ok=True)
        issued_at = self.db.now()
        prepared_recipients = self._prepare_issuance_recipients(recipients, issued_at)
        temp_path = path.with_name(f".{path.stem}.{secrets.token_hex(4)}.tmp{path.suffix}")
        issuance_ids: list[int] = []
        try:
            self._write_certificates_pdf(temp_path, template, prepared_recipients, source_title=source_title)
            issuance_ids = self._record_certificate_issuances(
                prepared_recipients,
                template,
                context_type=context_type,
                source_id=source_id,
                source_title=source_title,
                file_path=path,
                issued_at=issued_at,
            )
            try:
                temp_path.replace(path)
            except Exception:
                self.db.delete_certificate_issuances(issuance_ids)
                raise
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    logger.exception("Falha ao remover PDF temporario: %s", temp_path)
            raise
        logger.info("Diplomas exportados em PDF: %s (%s paginas)", path, len(prepared_recipients))
        return {
            "path": path,
            "exported": len(prepared_recipients),
            "issuance_ids": issuance_ids,
            "verification_codes": [str(recipient["verification_code"]) for recipient in prepared_recipients],
        }

    def _prepare_issuance_recipients(
        self,
        recipients: list[dict[str, Any]],
        issued_at: str,
    ) -> list[dict[str, Any]]:
        used_codes: set[str] = set()
        prepared = []
        issued_at_label = self._date_label(issued_at[:10])
        for recipient in recipients:
            code = self._new_verification_code(used_codes)
            used_codes.add(code)
            prepared.append(
                {
                    **recipient,
                    "verification_code": code,
                    "issued_at": issued_at,
                    "issued_at_label": issued_at_label,
                }
            )
        return prepared

    def _new_verification_code(self, used_codes: set[str]) -> str:
        for _attempt in range(100):
            code = f"ALB-{secrets.token_hex(4).upper()}"
            if code in used_codes:
                continue
            if self.db.get_certificate_issuance_by_code(code):
                continue
            return code
        raise AppError("Nao foi possivel gerar um codigo unico para o diploma.")

    def _record_certificate_issuances(
        self,
        recipients: list[dict[str, Any]],
        template: dict[str, Any],
        context_type: str,
        source_id: int | None,
        source_title: str,
        file_path: Path,
        issued_at: str,
    ) -> list[int]:
        template_id = int(template.get("id") or 0) or None
        rows = []
        for recipient in recipients:
            rows.append(
                {
                    "verification_code": recipient.get("verification_code"),
                    "context_type": context_type,
                    "source_id": source_id,
                    "source_title": source_title,
                    "recipient_id": self._recipient_id_for_context(recipient, context_type),
                    "recipient_name": recipient.get("name", ""),
                    "recipient_category": recipient.get("category", ""),
                    "certificate_type": template.get("certificate_type", ""),
                    "template_id": template_id,
                    "template_name": template.get("name", ""),
                    "file_path": str(file_path),
                    "issued_at": issued_at,
                    "payload_json": json.dumps(recipient, ensure_ascii=True, default=str),
                }
            )
        return self.db.create_certificate_issuances(rows)

    @staticmethod
    def _verification_context_label(context_type: Any) -> str:
        labels = {
            "tournament": "Torneio",
            "members": "Membros/alunos",
            "training": "Aula/turma",
            "event": "Evento",
            "ranking": "Ranking interno",
        }
        text = str(context_type or "").strip()
        return labels.get(text, text)

    def _verification_site_html(self, issuances: list[dict[str, Any]]) -> str:
        rows = "".join(self._verification_site_row(item) for item in issuances)
        generated_at = self.db.now()
        active_count = sum(1 for item in issuances if not item.get("revoked"))
        revoked_count = len(issuances) - active_count
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Verificador de diplomas Albericus</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: #172033;
      background: #f6f7fb;
    }}
    header {{
      background: #16213e;
      color: #fff;
      padding: 28px 36px;
    }}
    header p {{ margin: 6px 0 0; color: #d8dee9; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .summary div, section {{
      background: #fff;
      border: 1px solid #d9deea;
      border-radius: 8px;
      padding: 16px;
    }}
    .summary strong, .summary span {{ display: block; }}
    .summary span {{ margin-top: 4px; color: #566175; }}
    input {{
      width: 100%;
      border: 1px solid #cbd3e1;
      border-radius: 6px;
      font-size: 15px;
      margin-bottom: 12px;
      padding: 10px 12px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{
      border-bottom: 1px solid #e1e6ef;
      padding: 9px 10px;
      text-align: left;
      white-space: nowrap;
    }}
    th {{ background: #eef2f7; }}
    .table-wrap {{ overflow-x: auto; }}
    .status-active {{ color: #166534; font-weight: 700; }}
    .status-revoked {{ color: #991b1b; font-weight: 700; }}
    footer {{ color: #667085; font-size: 13px; padding: 0 24px 28px; text-align: center; }}
  </style>
</head>
<body>
  <header>
    <h1>Verificador de diplomas Albericus</h1>
    <p>Consulta local de codigos emitidos pelo gerenciador de clube.</p>
  </header>
  <main>
    <div class="summary">
      <div><strong>Total emitido</strong><span>{len(issuances)}</span></div>
      <div><strong>Ativos</strong><span>{active_count}</span></div>
      <div><strong>Revogados</strong><span>{revoked_count}</span></div>
      <div><strong>Gerado em</strong><span>{self._escape_html(generated_at)}</span></div>
    </div>
    <section>
      <input id="search" type="search" placeholder="Buscar por codigo, nome, origem ou modelo">
      <div class="table-wrap">
        <table id="issuances">
          <thead>
            <tr>
              <th>Codigo</th>
              <th>Status</th>
              <th>Destinatario</th>
              <th>Contexto</th>
              <th>Origem</th>
              <th>Tipo</th>
              <th>Modelo</th>
              <th>Emissao</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
  </main>
  <footer>Este arquivo nao substitui validacao institucional; ele reflete o historico local exportado em {self._escape_html(generated_at)}.</footer>
  <script>
    const search = document.getElementById('search');
    const rows = Array.from(document.querySelectorAll('#issuances tbody tr'));
    search.addEventListener('input', () => {{
      const query = search.value.trim().toLowerCase();
      rows.forEach((row) => {{
        row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
      }});
    }});
  </script>
</body>
</html>
"""

    def _verification_site_row(self, item: dict[str, Any]) -> str:
        revoked = bool(item.get("revoked"))
        status = "Revogado" if revoked else "Ativo"
        status_class = "status-revoked" if revoked else "status-active"
        certificate_type = str(item.get("certificate_type") or "")
        issued_at = str(item.get("issued_at") or "")
        issued_at_label = self._date_label(issued_at[:10]) if issued_at else ""
        return (
            "<tr>"
            f"<td>{self._escape_html(item.get('verification_code'))}</td>"
            f"<td class=\"{status_class}\">{status}</td>"
            f"<td>{self._escape_html(item.get('recipient_name'))}</td>"
            f"<td>{self._escape_html(self._verification_context_label(item.get('context_type')))}</td>"
            f"<td>{self._escape_html(item.get('source_title'))}</td>"
            f"<td>{self._escape_html(CERTIFICATE_TYPES.get(certificate_type, certificate_type))}</td>"
            f"<td>{self._escape_html(item.get('template_name'))}</td>"
            f"<td>{self._escape_html(issued_at_label or issued_at)}</td>"
            "</tr>"
        )

    @staticmethod
    def _escape_html(value: Any) -> str:
        return html.escape(str(value or ""))

    @staticmethod
    def _recipient_id_for_context(recipient: Mapping[str, Any], context_type: str) -> int | None:
        if context_type == "tournament":
            recipient_id = recipient.get("player_id")
        else:
            recipient_id = recipient.get("member_id")
        if recipient_id in (None, ""):
            return None
        return int(str(recipient_id))

    def _template_for_export(
        self,
        template_id: int | None,
        certificate_type: str,
        template_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if template_data is not None:
            payload = self._validated_template_payload(template_data)
            payload.update({"id": 0})
            return payload
        if template_id:
            return self.get_template(template_id)
        templates = [
            template
            for template in self.db.list_certificate_templates(active_only=True)
            if template.get("certificate_type") == certificate_type
        ]
        if templates:
            return templates[0]
        for template in DEFAULT_CERTIFICATE_TEMPLATES:
            if template["certificate_type"] == certificate_type:
                fallback = dict(template)
                fallback.update({"id": 0, "active": 1})
                return fallback
        raise AppError("Modelo de diploma invalido.")

    def _individual_tournament(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Diplomas para torneios por equipes ficam para uma etapa futura.")
        return tournament

    @staticmethod
    def _validated_template_payload(data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do modelo.")
        certificate_type = str(data.get("certificate_type", "participation")).strip() or "participation"
        if certificate_type not in CERTIFICATE_TYPES:
            raise AppError("Tipo de diploma invalido.")
        orientation = str(data.get("orientation", "landscape")).strip() or "landscape"
        if orientation not in CERTIFICATE_ORIENTATIONS:
            raise AppError("Orientacao do diploma invalida.")
        title_template = str(data.get("title_template", "")).strip()
        body_template = str(data.get("body_template", "")).strip()
        if not title_template:
            raise AppError("Informe o titulo do diploma.")
        if not body_template:
            raise AppError("Informe o texto principal do diploma.")
        logo_path = CertificateService._validated_optional_image_path(
            data.get("logo_path", ""),
            "Arquivo de logo nao encontrado.",
        )
        background_image_path = CertificateService._validated_optional_image_path(
            data.get("background_image_path", ""),
            "Imagem de fundo nao encontrada.",
        )
        secondary_logo_path = CertificateService._validated_optional_image_path(
            data.get("secondary_logo_path", ""),
            "Arquivo de logo secundario nao encontrado.",
        )
        return {
            "name": name,
            "certificate_type": certificate_type,
            "title_template": title_template,
            "body_template": body_template,
            "footer_template": str(data.get("footer_template", "")).strip(),
            "orientation": orientation,
            "signature_left": str(data.get("signature_left", "")).strip(),
            "signature_right": str(data.get("signature_right", "")).strip(),
            "logo_path": logo_path,
            "background_image_path": background_image_path,
            "background_opacity": CertificateService._validated_opacity(
                data.get("background_opacity", 0.18),
                "opacidade do fundo",
            ),
            "secondary_logo_path": secondary_logo_path,
            "primary_color": CertificateService._validated_hex_color(
                data.get("primary_color", "#1E3A8A"),
                "cor principal",
            ),
            "accent_color": CertificateService._validated_hex_color(
                data.get("accent_color", "#93C5FD"),
                "cor de destaque",
            ),
            "title_font_size": CertificateService._validated_font_size(
                data.get("title_font_size", 32),
                "titulo",
                18,
                48,
            ),
            "body_font_size": CertificateService._validated_font_size(
                data.get("body_font_size", 18),
                "texto principal",
                10,
                28,
            ),
            "footer_font_size": CertificateService._validated_font_size(
                data.get("footer_font_size", 10),
                "rodape",
                7,
                16,
            ),
            "active": 1 if data.get("active", 1) else 0,
        }

    @staticmethod
    def _validated_optional_image_path(value: Any, message: str) -> str:
        image_path = str(value or "").strip()
        if not image_path:
            return ""
        resolved_image = CertificateService._resolve_template_path(image_path)
        if not resolved_image.exists() or not resolved_image.is_file():
            raise AppError(message)
        return image_path

    @staticmethod
    def _validated_opacity(value: Any, label: str) -> float:
        if value in (None, ""):
            return 0.18
        try:
            opacity = float(str(value).replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise AppError(f"Informe uma {label} valida.") from exc
        if opacity > 1 and opacity <= 100:
            opacity = opacity / 100
        if opacity < 0 or opacity > 1:
            raise AppError(f"A {label} deve ficar entre 0 e 1, ou entre 0 e 100%.")
        return round(opacity, 4)

    @staticmethod
    def _validated_hex_color(value: Any, label: str) -> str:
        text = str(value or "").strip() or "#000000"
        if not text.startswith("#"):
            text = f"#{text}"
        hex_digits = text[1:]
        if len(hex_digits) != 6 or any(character not in "0123456789abcdefABCDEF" for character in hex_digits):
            raise AppError(f"Informe uma {label} em hexadecimal, como #1E3A8A.")
        return f"#{hex_digits.upper()}"

    @staticmethod
    def _validated_font_size(value: Any, label: str, minimum: int, maximum: int) -> int:
        try:
            size = int(value)
        except (TypeError, ValueError) as exc:
            raise AppError(f"Tamanho da fonte do {label} invalido.") from exc
        if size < minimum or size > maximum:
            raise AppError(f"Tamanho da fonte do {label} deve ficar entre {minimum} e {maximum}.")
        return size

    @staticmethod
    def _resolve_template_path(path: str) -> Path:
        logo_path = Path(path).expanduser()
        if logo_path.is_absolute():
            return logo_path
        return BASE_DIR / logo_path

    @staticmethod
    def _parse_top_n(value: Any) -> int:
        if value in (None, ""):
            return 0
        try:
            top_n = int(value)
        except (TypeError, ValueError) as exc:
            raise AppError("Informe um limite numerico para o top N.") from exc
        if top_n < 0:
            raise AppError("O limite do top N nao pode ser negativo.")
        return top_n

    @staticmethod
    def _category_positions(standings: list[dict[str, Any]]) -> dict[int, int]:
        counters: dict[str, int] = {}
        positions = {}
        for standing in standings:
            category = str(standing.get("category") or "Sem categoria").strip() or "Sem categoria"
            counters[category] = counters.get(category, 0) + 1
            positions[int(standing["player_id"])] = counters[category]
        return positions

    @staticmethod
    def _recipient_payload(
        tournament: dict[str, Any],
        standing: dict[str, Any],
        category_positions: dict[int, int],
    ) -> dict[str, Any]:
        player_id = int(standing["player_id"])
        category = str(standing.get("category") or "Sem categoria").strip() or "Sem categoria"
        return {
            "player_id": player_id,
            "name": str(standing.get("name") or ""),
            "tournament": str(tournament.get("name") or ""),
            "location": str(tournament.get("location") or ""),
            "date_range": CertificateService._date_range_label(tournament),
            "position": int(standing.get("position") or 0),
            "position_label": CertificateService._ordinal_label(standing.get("position")),
            "category": category,
            "category_position": category_positions.get(player_id, 0),
            "category_position_label": CertificateService._ordinal_label(category_positions.get(player_id, 0)),
            "points": ExportService._format_report_number(standing.get("points", 0)),
            "rating": int(standing.get("rating") or 0),
            "club": str(standing.get("club") or ""),
        }

    @staticmethod
    def _member_recipient_payload(member: Mapping[str, Any]) -> dict[str, Any]:
        category = str(member.get("category") or "Sem categoria").strip() or "Sem categoria"
        today_label = CertificateService._date_label(date.today().isoformat())
        return {
            "member_id": int(member.get("id") or member.get("member_id") or 0),
            "name": CertificateService._member_display_name(member),
            "tournament": "",
            "event": "",
            "session": "",
            "location": str(member.get("city") or member.get("club_name") or ""),
            "date_range": today_label,
            "position": 0,
            "position_label": "",
            "category": category,
            "category_position": 0,
            "category_position_label": "",
            "points": "0",
            "rating": int(member.get("rating") or 0),
            "club": str(member.get("club_name") or ""),
            "class_name": str(member.get("active_class_name") or member.get("class_name") or ""),
            "member_type": str(member.get("member_type") or ""),
            "status": str(member.get("status") or ""),
            "learning_level": str(member.get("learning_level_name") or ""),
            "date": today_label,
        }

    @staticmethod
    def _training_recipient_payload(
        session: Mapping[str, Any],
        member: Mapping[str, Any],
        attendance_status: str,
    ) -> dict[str, Any]:
        payload = CertificateService._member_recipient_payload(
            {
                **dict(member),
                "id": member.get("member_id") or member.get("id"),
                "name": member.get("member_name") or member.get("name"),
                "category": member.get("member_category") or member.get("category"),
                "status": member.get("member_status") or member.get("status"),
                "club_name": member.get("club_name") or session.get("club_name"),
            }
        )
        payload.update(
            {
                "session_id": int(session.get("id") or 0),
                "session": str(session.get("title") or ""),
                "location": str(session.get("location") or payload.get("location") or ""),
                "date_range": CertificateService._date_label(session.get("session_date")),
                "club": str(session.get("club_name") or payload.get("club") or ""),
                "class_name": str(session.get("class_name") or member.get("active_class_name") or ""),
                "instructor": str(session.get("instructor") or ""),
                "session_type": str(session.get("session_type") or ""),
                "type_label": TRAINING_SESSION_TYPES.get(
                    str(session.get("session_type") or ""),
                    str(session.get("session_type") or ""),
                ),
                "status": ATTENDANCE_STATUSES.get(attendance_status, attendance_status or "Nao lancada"),
                "attendance_status": attendance_status,
                "date": CertificateService._date_label(session.get("session_date")),
            }
        )
        return payload

    @staticmethod
    def _event_recipient_payload(event: Mapping[str, Any], member: Mapping[str, Any]) -> dict[str, Any]:
        payload = CertificateService._member_recipient_payload(member)
        payload.update(
            {
                "event_id": int(event.get("id") or 0),
                "event": str(event.get("title") or ""),
                "location": str(event.get("location") or payload.get("location") or ""),
                "date_range": CertificateService._date_label(event.get("event_date")),
                "club": str(event.get("club_name") or payload.get("club") or ""),
                "event_type": str(event.get("event_type") or ""),
                "type_label": EVENT_TYPES.get(
                    str(event.get("event_type") or ""),
                    str(event.get("event_type") or ""),
                ),
                "status": EVENT_STATUSES.get(
                    str(event.get("status") or ""),
                    str(event.get("status") or ""),
                ),
                "date": CertificateService._date_label(event.get("event_date")),
            }
        )
        return payload

    @staticmethod
    def _ranking_recipient_payload(item: Mapping[str, Any]) -> dict[str, Any]:
        today_label = CertificateService._date_label(date.today().isoformat())
        category = str(item.get("category") or "Sem categoria").strip() or "Sem categoria"
        position = int(item.get("position") or 0)
        return {
            "member_id": int(item.get("member_id") or 0),
            "name": str(item.get("name") or ""),
            "tournament": "",
            "event": "",
            "session": "",
            "location": str(item.get("club_name") or ""),
            "date_range": today_label,
            "position": position,
            "position_label": CertificateService._ordinal_label(position),
            "category": category,
            "category_position": 0,
            "category_position_label": "",
            "points": ExportService._format_report_number(item.get("points", 0)),
            "rating": int(item.get("rating") or 0),
            "club": str(item.get("club_name") or ""),
            "class_name": str(item.get("class_name") or ""),
            "member_type": str(item.get("member_type") or ""),
            "status": str(item.get("status") or ""),
            "last_delta": int(item.get("last_delta") or 0),
            "last_performance": str(item.get("last_performance") or ""),
            "last_tournament": str(item.get("last_tournament") or ""),
            "games": int(item.get("games") or 0),
            "wins": int(item.get("wins") or 0),
            "draws": int(item.get("draws") or 0),
            "losses": int(item.get("losses") or 0),
            "score_rate": ExportService._format_report_number(item.get("score_rate", 0)),
            "date": today_label,
        }

    @staticmethod
    def _member_display_name(member: Mapping[str, Any]) -> str:
        name = str(member.get("name") or "").strip()
        surname = str(member.get("surname") or "").strip()
        if surname and surname.casefold() not in name.casefold().split():
            return f"{name} {surname}".strip()
        return name or surname

    @staticmethod
    def _date_range_label(tournament: dict[str, Any]) -> str:
        start_date = CertificateService._date_label(tournament.get("start_date"))
        end_date = CertificateService._date_label(tournament.get("end_date"))
        if start_date and end_date and start_date != end_date:
            return f"{start_date} a {end_date}"
        return start_date or end_date

    @staticmethod
    def _date_label(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            parsed = date.fromisoformat(text)
        except ValueError:
            return text
        return parsed.strftime("%d/%m/%Y")

    @staticmethod
    def _ordinal_label(value: Any) -> str:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return ""
        return f"{number}o" if number else ""

    @staticmethod
    def _write_certificates_pdf(
        path: Path,
        template: dict[str, Any],
        recipients: list[dict[str, Any]],
        source_title: str = "",
    ) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
            from reportlab.platypus import Frame, Paragraph
        except ImportError as exc:
            raise AppError("Instale reportlab para exportar PDF.") from exc

        page_size = A4 if template.get("orientation") == "portrait" else landscape(A4)
        width, height = page_size
        document = canvas.Canvas(str(path), pagesize=page_size)
        primary_color = colors.HexColor(str(template.get("primary_color") or "#1E3A8A"))
        accent_color = colors.HexColor(str(template.get("accent_color") or "#93C5FD"))
        title_style = ParagraphStyle(
            "CertificateTitle",
            fontName="Helvetica-Bold",
            fontSize=int(template.get("title_font_size") or 32),
            leading=int(template.get("title_font_size") or 32) + 6,
            alignment=TA_CENTER,
            textColor=primary_color,
        )
        body_style = ParagraphStyle(
            "CertificateBody",
            fontName="Helvetica",
            fontSize=int(template.get("body_font_size") or 18),
            leading=int(template.get("body_font_size") or 18) + 10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1F2937"),
        )
        footer_style = ParagraphStyle(
            "CertificateFooter",
            fontName="Helvetica",
            fontSize=int(template.get("footer_font_size") or 10),
            leading=int(template.get("footer_font_size") or 10) + 4,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
        )
        background = CertificateService._load_template_image(
            template,
            "background_image_path",
            "Imagem de fundo nao encontrada.",
            "Nao foi possivel carregar a imagem de fundo do diploma.",
            ImageReader,
        )
        logo = CertificateService._load_template_image(
            template,
            "logo_path",
            "Arquivo de logo nao encontrado.",
            "Nao foi possivel carregar o logo do diploma.",
            ImageReader,
        )
        secondary_logo = CertificateService._load_template_image(
            template,
            "secondary_logo_path",
            "Arquivo de logo secundario nao encontrado.",
            "Nao foi possivel carregar o logo secundario do diploma.",
            ImageReader,
        )
        background_opacity = CertificateService._validated_opacity(
            template.get("background_opacity", 0.18),
            "opacidade do fundo",
        )

        for recipient in recipients:
            CertificateService._draw_certificate_page(
                document,
                width,
                height,
                cm,
                colors,
                primary_color,
                accent_color,
                background,
                background_opacity,
                logo,
                secondary_logo,
                Frame,
                Paragraph,
                title_style,
                body_style,
                footer_style,
                source_title,
                template,
                recipient,
            )
            document.showPage()
        document.save()

    @staticmethod
    def _load_template_image(
        template: dict[str, Any],
        field: str,
        missing_message: str,
        load_message: str,
        image_reader_class: Any,
    ) -> Any | None:
        image_path = str(template.get(field) or "").strip()
        if not image_path:
            return None
        resolved_image = CertificateService._resolve_template_path(image_path)
        if not resolved_image.exists() or not resolved_image.is_file():
            raise AppError(missing_message)
        try:
            return image_reader_class(str(resolved_image))
        except Exception as exc:
            raise AppError(load_message) from exc

    @staticmethod
    def _draw_background_image(
        document: Any,
        background: Any,
        width: float,
        height: float,
        opacity: float,
    ) -> None:
        if not background or opacity <= 0:
            return
        image_width, image_height = background.getSize()
        if image_width <= 0 or image_height <= 0:
            return
        scale = max(width / image_width, height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        x = (width - draw_width) / 2
        y = (height - draw_height) / 2
        document.saveState()
        if hasattr(document, "setFillAlpha"):
            document.setFillAlpha(opacity)
        if hasattr(document, "setStrokeAlpha"):
            document.setStrokeAlpha(opacity)
        document.drawImage(
            background,
            x,
            y,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        document.restoreState()

    @staticmethod
    def _draw_logo(
        document: Any,
        logo: Any,
        x: float,
        y: float,
        max_width: float,
        max_height: float,
    ) -> None:
        image_width, image_height = logo.getSize()
        if image_width <= 0 or image_height <= 0:
            return
        scale = min(max_width / image_width, max_height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        document.drawImage(
            logo,
            x,
            y + (max_height - draw_height) / 2,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )

    @staticmethod
    def _draw_certificate_page(
        document: Any,
        width: float,
        height: float,
        cm: float,
        colors: Any,
        primary_color: Any,
        accent_color: Any,
        background: Any,
        background_opacity: float,
        logo: Any,
        secondary_logo: Any,
        frame_class: Any,
        paragraph_class: Any,
        title_style: Any,
        body_style: Any,
        footer_style: Any,
        source_title: str,
        template: dict[str, Any],
        recipient: dict[str, Any],
    ) -> None:
        CertificateService._draw_background_image(document, background, width, height, background_opacity)
        margin = 1.1 * cm
        document.setStrokeColor(primary_color)
        document.setLineWidth(3)
        document.rect(margin, margin, width - 2 * margin, height - 2 * margin)
        document.setStrokeColor(accent_color)
        document.setLineWidth(1)
        document.rect(margin + 0.28 * cm, margin + 0.28 * cm, width - 2 * (margin + 0.28 * cm), height - 2 * (margin + 0.28 * cm))
        document.setFillColor(accent_color)
        document.rect(margin + 0.52 * cm, height - margin - 0.64 * cm, width - 2 * (margin + 0.52 * cm), 0.08 * cm, stroke=0, fill=1)

        if logo:
            CertificateService._draw_logo(document, logo, 2.1 * cm, height - 3.3 * cm, 3.0 * cm, 1.7 * cm)
        if secondary_logo:
            CertificateService._draw_logo(
                document,
                secondary_logo,
                width - 5.1 * cm,
                height - 3.3 * cm,
                3.0 * cm,
                1.7 * cm,
            )

        title = CertificateService._render_template_text(str(template.get("title_template") or ""), recipient)
        title_frame = frame_class(2.3 * cm, height - 4.0 * cm, width - 4.6 * cm, 1.4 * cm, showBoundary=0)
        title_frame.addFromList([paragraph_class(title, title_style)], document)
        document.setFont("Helvetica", 13)
        document.setFillColor(primary_color)
        document.drawCentredString(width / 2, height - 3.8 * cm, source_title)

        body = CertificateService._render_template_text(str(template.get("body_template") or ""), recipient)
        body_bottom = 6.2 * cm if width > height else 8.5 * cm
        body_height = 7.3 * cm if width > height else 9.0 * cm
        body_frame = frame_class(2.8 * cm, body_bottom, width - 5.6 * cm, body_height, showBoundary=0)
        body_frame.addFromList([paragraph_class(body, body_style)], document)

        document.setStrokeColor(accent_color)
        document.setLineWidth(1)
        line_half = min(3.2 * cm, width * 0.18)
        left_center = width * 0.32
        right_center = width * 0.68
        document.line(left_center - line_half, 3.9 * cm, left_center + line_half, 3.9 * cm)
        document.line(right_center - line_half, 3.9 * cm, right_center + line_half, 3.9 * cm)
        document.setFillColor(primary_color)
        document.setFont("Helvetica", max(8, int(template.get("footer_font_size") or 10)))
        left_signature = CertificateService._plain_rendered_text(str(template.get("signature_left") or ""), recipient)
        right_signature = CertificateService._plain_rendered_text(str(template.get("signature_right") or ""), recipient)
        document.drawCentredString(left_center, 3.45 * cm, left_signature)
        document.drawCentredString(right_center, 3.45 * cm, right_signature)

        footer = CertificateService._render_template_text(str(template.get("footer_template") or ""), recipient)
        if not footer:
            footer = CertificateService._render_template_text("{local} - {periodo}", recipient)
        footer_frame = frame_class(2.8 * cm, 1.7 * cm, width - 5.6 * cm, 1.2 * cm, showBoundary=0)
        footer_frame.addFromList([paragraph_class(footer, footer_style)], document)
        verification_code = str(recipient.get("verification_code") or "").strip()
        if verification_code:
            document.setFillColor(colors.HexColor("#64748B"))
            document.setFont("Helvetica", max(7, int(template.get("footer_font_size") or 10) - 1))
            document.drawRightString(width - 1.45 * cm, 1.25 * cm, f"Codigo: {verification_code}")

    @staticmethod
    def _render_template_text(template: str, recipient: dict[str, Any]) -> str:
        if not template:
            return ""
        rendered = html.escape(template, quote=False).replace("\n", "<br/>")
        for key, value in CertificateService._template_variables(recipient).items():
            rendered = rendered.replace(f"{{{key}}}", CertificateService._escape_pdf_text(value))
        return rendered

    @staticmethod
    def _plain_rendered_text(template: str, recipient: dict[str, Any]) -> str:
        rendered = CertificateService._render_template_text(template, recipient)
        return html.unescape(rendered.replace("<br/>", " "))

    @staticmethod
    def _template_variables(recipient: dict[str, Any]) -> dict[str, str]:
        return {
            "nome": str(recipient.get("name") or ""),
            "torneio": str(recipient.get("tournament") or ""),
            "local": str(recipient.get("location") or ""),
            "periodo": str(recipient.get("date_range") or ""),
            "data": str(recipient.get("date_range") or ""),
            "posicao": str(recipient.get("position_label") or ""),
            "posicao_numero": str(recipient.get("position") or ""),
            "categoria": str(recipient.get("category") or ""),
            "posicao_categoria": str(recipient.get("category_position_label") or ""),
            "posicao_categoria_numero": str(recipient.get("category_position") or ""),
            "pontos": str(recipient.get("points") or "0"),
            "rating": str(recipient.get("rating") or ""),
            "clube": str(recipient.get("club") or ""),
            "turma": str(recipient.get("class_name") or ""),
            "aula": str(recipient.get("session") or ""),
            "evento": str(recipient.get("event") or ""),
            "instrutor": str(recipient.get("instructor") or ""),
            "professor": str(recipient.get("instructor") or ""),
            "tipo": str(recipient.get("type_label") or recipient.get("member_type") or ""),
            "status": str(recipient.get("status") or ""),
            "nivel": str(recipient.get("learning_level") or ""),
            "delta": str(recipient.get("last_delta") or ""),
            "jogos": str(recipient.get("games") or ""),
            "desempenho": str(recipient.get("last_performance") or ""),
            "aproveitamento": str(recipient.get("score_rate") or ""),
            "vitorias": str(recipient.get("wins") or ""),
            "empates": str(recipient.get("draws") or ""),
            "derrotas": str(recipient.get("losses") or ""),
            "ultimo_torneio": str(recipient.get("last_tournament") or ""),
            "codigo": str(recipient.get("verification_code") or ""),
            "codigo_verificacao": str(recipient.get("verification_code") or ""),
            "emissao": str(recipient.get("issued_at_label") or ""),
            "emitido_em": str(recipient.get("issued_at_label") or ""),
        }

    @staticmethod
    def _certificate_title(certificate_type: str) -> str:
        if certificate_type == "participation":
            return "Certificado de Participacao"
        return "Certificado de Premiacao"

    @staticmethod
    def _certificate_body(certificate_type: str, recipient: dict[str, Any]) -> str:
        name = CertificateService._escape_pdf_text(str(recipient.get("name") or ""))
        tournament_name = CertificateService._escape_pdf_text(str(recipient.get("tournament") or ""))
        points = CertificateService._escape_pdf_text(str(recipient.get("points") or "0"))
        position = CertificateService._escape_pdf_text(str(recipient.get("position_label") or ""))
        category = CertificateService._escape_pdf_text(str(recipient.get("category") or ""))
        category_position = CertificateService._escape_pdf_text(str(recipient.get("category_position_label") or ""))

        if certificate_type == "overall_award":
            return (
                f"Certificamos que <b>{name}</b> conquistou a <b>{position}</b> colocacao geral "
                f"no torneio <b>{tournament_name}</b>, com <b>{points}</b> ponto(s)."
            )
        if certificate_type == "category_award":
            return (
                f"Certificamos que <b>{name}</b> conquistou a <b>{category_position}</b> colocacao "
                f"na categoria <b>{category}</b> do torneio <b>{tournament_name}</b>, "
                f"com <b>{points}</b> ponto(s)."
            )
        return (
            f"Certificamos que <b>{name}</b> participou do torneio <b>{tournament_name}</b>, "
            f"obtendo <b>{points}</b> ponto(s) e a <b>{position}</b> colocacao na classificacao."
        )

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return html.escape(value, quote=False)

class ExportService:
    def __init__(self, db: Database, pairing_service: PairingService) -> None:
        self.db = db
        self.pairing_service = pairing_service

    def export_players(self, tournament_id: int, file_path: str | Path) -> None:
        title, headers, rows = self._players_section(tournament_id)
        self._write_report(file_path, title, headers, rows)

    def export_pairings(self, round_id: int, file_path: str | Path) -> None:
        title, headers, rows = self._pairings_section(round_id)
        self._write_report(file_path, title, headers, rows)

    def export_teams(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(
            file_path,
            [
                self._teams_section(tournament_id),
                self._team_rosters_section(tournament_id),
            ],
        )

    def export_all_rounds(self, tournament_id: int, file_path: str | Path) -> None:
        sections = []
        for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"]):
            sections.append(self._pairings_section(round_data["id"]))
        if not sections:
            raise AppError("Nao ha rodadas para exportar.")
        self._write_multi_report(file_path, sections)

    def export_standings(self, tournament_id: int, file_path: str | Path) -> None:
        title, headers, rows = self._standings_section(tournament_id)
        self._write_report(file_path, title, headers, rows)

    def export_complete(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        sections = [
            self._tournament_section(tournament_id),
        ]
        if tournament.get("competition_type") == "team":
            sections.append(self._teams_section(tournament_id))
            sections.append(self._team_rosters_section(tournament_id))
        sections.append(self._players_section(tournament_id))
        for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"]):
            sections.append(self._pairings_section(round_data["id"]))
        sections.append(self._standings_section(tournament_id))
        self._write_multi_report(file_path, sections)

    def export_pgn(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
            
        path = Path(file_path)
        with path.open("w", encoding="utf-8") as f:
            for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda r: r["number"]):
                pairings = self.db.list_pairings(round_data["id"])
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

    def export_trf(self, tournament_id: int, file_path: str | Path) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
            
        players = self.db.list_players(tournament_id)
        players = sorted(players, key=lambda p: (-int(p.get("rating") or 0), str(p.get("name") or "").casefold()))
        
        path = Path(file_path)
        with path.open("w", encoding="utf-8") as f:
            f.write(f"012 {tournament['name']}\n")
            f.write(f"022 {tournament.get('location') or ''}\n")
            f.write("032 \n")
            start = str(tournament.get('start_date') or '').replace("-", "/")
            end = str(tournament.get('end_date') or '').replace("-", "/")
            f.write(f"042 {start}\n")
            f.write(f"052 {end}\n")
            f.write(f"062 {len(players)}\n")
            
            rounds = sorted(self.db.list_rounds(tournament_id), key=lambda r: r["number"])
            f.write("132 \n")
            
            player_id_to_seq = {p["id"]: i+1 for i, p in enumerate(players)}
            
            for i, p in enumerate(players):
                seq = i + 1
                name = str(p.get("name") or "")[:32].ljust(33)
                rating = str(p.get("rating") or "0").rjust(4)
                fide_id = str(p.get("fide_id") or "").rjust(11)
                
                line = f"{seq:4}           {name} {rating}       {fide_id}                      "
                
                for r in rounds:
                    pairings = self.db.list_pairings(r["id"])
                    my_pairing = next((pa for pa in pairings if pa["white_player_id"] == p["id"] or pa["black_player_id"] == p["id"]), None)
                    if not my_pairing:
                        line += "  0000 - - "
                        continue
                        
                    if my_pairing["is_bye"]:
                        if my_pairing["white_player_id"] == p["id"]:
                            line += "  0000 - + " 
                        else:
                            line += "  0000 - - "
                        continue
                        
                    is_white = my_pairing["white_player_id"] == p["id"]
                    color = "w" if is_white else "b"
                    opp_id = my_pairing["black_player_id"] if is_white else my_pairing["white_player_id"]
                    opp_seq = player_id_to_seq.get(opp_id, 0)
                    
                    res_str = " "
                    result = my_pairing.get("result")
                    if result == "1-0":
                        res_str = "1" if is_white else "0"
                    elif result == "0-1":
                        res_str = "0" if is_white else "1"
                    elif result == "1/2-1/2":
                        res_str = "="
                        
                    line += f"  {opp_seq:04d} {color} {res_str} "
                    
                f.write(f"{line}\n")

    def export_member_evolution(self, member_id: int, file_path: str | Path) -> None:
        sections = self._member_evolution_sections(member_id)
        self._write_multi_report(file_path, sections)

    def export_club_report(self, file_path: str | Path) -> None:
        sections = self._club_report_sections()
        self._write_multi_report(file_path, sections)

    def export_member_report(self, member_id: int, file_path: str | Path) -> None:
        sections = self._member_evolution_sections(member_id)
        self._write_multi_report(file_path, sections)

    def export_tournaments_period_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._tournaments_period_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_attendance_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._attendance_report_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_financial_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._financial_report_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_events_report(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._events_report_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_internal_ranking_report(
        self,
        file_path: str | Path,
        category: str = "",
        club_id: int | None = None,
        class_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._internal_ranking_sections(
            category,
            club_id=club_id,
            class_id=class_id,
            start_date=start_date,
            end_date=end_date,
        )
        self._write_multi_report(file_path, sections)

    def export_payment_receipt(self, payment_id: int, file_path: str | Path) -> Path:
        payment = self.db.get_payment(payment_id)
        if not payment:
            raise AppError("Lancamento financeiro nao encontrado.")
        finance_service = __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db)
        payment = finance_service._with_effective_status(payment)
        if payment["effective_status"] not in {"paid", "exempt"}:
            raise AppError("Recibo disponivel apenas para lancamentos pagos ou isentos.")

        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            # Para CSV/Excel continua usando o padrão genérico
            rows = [
                ["Recibo", f"REC-{int(payment['id']):06d}"],
                ["Membro", payment.get("member_name") or ""],
                ["Plano", payment.get("plan_name") or ""],
                ["Descricao", payment.get("description") or ""],
                ["Referencia", payment.get("reference_period") or ""],
                ["Valor", self._format_report_number(payment.get("amount") or 0.0)],
                ["Pagamento", payment.get("payment_date") or ""],
            ]
            self._write_report(path, "Recibo financeiro", ["Campo", "Valor"], rows)
            return path
            
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            
            c = canvas.Canvas(str(path), pagesize=A4)
            c.setFont("Helvetica-Bold", 18)
            c.drawString(50, 800, "RECIBO DE PAGAMENTO")
            
            c.setFont("Helvetica-Bold", 12)
            c.drawString(400, 800, f"N. REC-{int(payment['id']):06d}")
            
            c.setFont("Helvetica", 12)
            c.drawString(50, 750, f"Recebemos de: {payment.get('member_name') or 'N/A'}")
            
            amount = float(payment.get("amount") or 0.0)
            c.drawString(50, 720, f"A quantia de: R$ {amount:,.2f}")
            c.drawString(50, 690, f"Referente a: {payment.get('description') or ''} - Ref: {payment.get('reference_period') or ''}")
            
            c.drawString(50, 660, f"Data do Pagamento: {payment.get('payment_date') or ''}")
            
            c.drawString(50, 600, "Por ser verdade, firmamos o presente recibo.")
            
            c.line(50, 520, 300, 520)
            c.drawString(50, 500, "Assinatura do Tesoureiro / Diretoria")
            c.drawString(50, 480, "Clube de Xadrez Albericus")
            
            c.save()
            return path
        except ImportError as exc:
            raise AppError("Instale reportlab para gerar Recibos em PDF (pip install reportlab).") from exc

    def export_administrative_package(
        self,
        file_path: str | Path,
        start_date: str = "",
        end_date: str = "",
    ) -> None:
        sections = self._administrative_package_sections(start_date, end_date)
        self._write_multi_report(file_path, sections)

    def export_club_portal(
        self,
        output_dir: str | Path,
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> Path:
        club, class_data = self._club_portal_scope(club_id, class_id)
        resolved_club_id = int(club["id"]) if club else None
        resolved_class_id = int(class_data["id"]) if class_data else None
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        html_content = self._club_portal_html(
            club=club,
            class_data=class_data,
            members=self.db.list_members(active_only=True, club_id=resolved_club_id, class_id=resolved_class_id),
            classes=[class_data]
            if class_data
            else self.db.list_classes(club_id=resolved_club_id, active_only=True),
            events=self.db.list_club_events(
                start_date=date.today().isoformat(),
                club_id=resolved_club_id,
                include_canceled=False,
            )[:10],
            sessions=self.db.list_training_sessions(
                start_date=date.today().isoformat(),
                club_id=resolved_club_id,
                class_id=resolved_class_id,
            )[:10],
            tournaments=[
                tournament
                for tournament in self.db.list_tournaments()
                if self._portal_tournament_in_scope(tournament, resolved_club_id, resolved_class_id)
            ][:8],
            ranking=__import__('src.services.rating_service', fromlist=['InternalRatingService']).InternalRatingService(self.db).ranking(
                active_only=True,
                club_id=resolved_club_id,
                class_id=resolved_class_id,
            )[:10],
        )
        (path / "index.html").write_text(html_content, encoding="utf-8")
        (path / "styles.css").write_text(self._club_portal_css(), encoding="utf-8")
        logger.info("Portal estatico do clube exportado em %s", path)
        return path / "index.html"

    def export_site(self, tournament_id: int, output_dir: str | Path) -> Path:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")

        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        settings = self.db.get_tournament_settings(tournament_id) or {}
        schedule = self.db.list_round_schedule(tournament_id)
        players = self.db.list_players(tournament_id, active_only=False)
        standings = (
            []
            if settings.get("hide_standings")
            else self._standings_for_tournament(tournament_id, tournament)
        )
        rounds = sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"])

        index_html = self._site_html(tournament, settings, schedule, players, rounds, standings)
        (path / "index.html").write_text(index_html, encoding="utf-8")
        (path / "styles.css").write_text(self._site_css(), encoding="utf-8")
        logger.info("Site estatico exportado em %s", path)
        return path / "index.html"

    def _club_portal_scope(
        self,
        club_id: int | None,
        class_id: int | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        class_data = self.db.get_class(class_id) if class_id else None
        if class_id and not class_data:
            raise AppError("Turma do portal nao encontrada.")
        if class_data and club_id and int(class_data["club_id"]) != int(club_id):
            raise AppError("A turma selecionada nao pertence ao clube/escola do portal.")

        if class_data and not club_id:
            club_id = int(class_data["club_id"])
        club = self.db.get_club(club_id) if club_id else None
        if club_id and not club:
            raise AppError("Clube/escola do portal nao encontrado.")
        if not club:
            active_clubs = self.db.list_clubs(active_only=True)
            club = active_clubs[0] if active_clubs else self.db.get_club(1)
        return club, class_data

    @staticmethod
    def _portal_tournament_in_scope(
        tournament: Mapping[str, Any],
        club_id: int | None,
        class_id: int | None,
    ) -> bool:
        if class_id and int(tournament.get("class_id") or 0) != class_id:
            return False
        if club_id and int(tournament.get("club_id") or 0) != club_id:
            return False
        return True

    def _club_portal_html(
        self,
        club: dict[str, Any] | None,
        class_data: dict[str, Any] | None,
        members: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        events: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        tournaments: list[dict[str, Any]],
        ranking: list[dict[str, Any]],
    ) -> str:
        title = class_data.get("name") if class_data else club.get("name") if club else "Portal do clube"
        club_kind_labels = {
            "club": "Clube",
            "school": "Escola",
            "project": "Projeto",
            "partner": "Parceiro",
        }
        subtitle = (
            class_data.get("club_name")
            if class_data
            else club_kind_labels.get(str(club.get("kind") or "club"), "") if club else ""
        )
        generated_at = Database.now()
        notice_rows = self._portal_notice_rows(events, sessions)
        class_rows = "".join(
            "<tr>"
            f"<td>{self._escape(item.get('name') or '')}</td>"
            f"<td>{self._escape(item.get('teacher') or '')}</td>"
            f"<td>{self._escape(item.get('weekday') or '')}</td>"
            f"<td>{self._escape(item.get('time') or '')}</td>"
            f"<td>{self._escape(item.get('location') or '')}</td>"
            f"<td>{item.get('active_members_count', '')}</td>"
            "</tr>"
            for item in classes
        )
        event_rows = "".join(
            "<tr>"
            f"<td>{self._escape(item.get('event_date') or '')}</td>"
            f"<td>{self._escape(item.get('start_time') or '')}</td>"
            f"<td>{self._escape(EVENT_TYPES.get(item.get('event_type', ''), item.get('event_type') or ''))}</td>"
            f"<td>{self._escape(item.get('title') or '')}</td>"
            f"<td>{self._escape(item.get('location') or '')}</td>"
            f"<td>{self._escape(EVENT_STATUSES.get(item.get('status', ''), item.get('status') or ''))}</td>"
            "</tr>"
            for item in events
        )
        session_rows = "".join(
            "<tr>"
            f"<td>{self._escape(item.get('session_date') or '')}</td>"
            f"<td>{self._escape(item.get('start_time') or '')}</td>"
            f"<td>{self._escape(item.get('title') or '')}</td>"
            f"<td>{self._escape(item.get('class_name') or '')}</td>"
            f"<td>{self._escape(item.get('learning_level_name') or '')}</td>"
            f"<td>{self._escape(item.get('objective') or '')}</td>"
            "</tr>"
            for item in sessions
        )
        ranking_rows = "".join(
            "<tr>"
            f"<td>{item['position']}</td>"
            f"<td>{self._escape(item.get('name') or '')}</td>"
            f"<td>{item.get('rating', '')}</td>"
            f"<td>{self._escape(item.get('category') or '')}</td>"
            f"<td>{self._escape(item.get('class_name') or '')}</td>"
            f"<td>{self._escape(str(item.get('score_rate') or 0))}%</td>"
            "</tr>"
            for item in ranking
        )
        tournament_rows = "".join(
            "<tr>"
            f"<td>{self._escape(item.get('name') or '')}</td>"
            f"<td>{self._escape(item.get('start_date') or '')}</td>"
            f"<td>{self._escape(item.get('location') or '')}</td>"
            f"<td>{self._escape(item.get('status') or '')}</td>"
            "</tr>"
            for item in tournaments
        )
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{self._escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <p class="eyebrow">Albericus</p>
    <h1>{self._escape(title)}</h1>
    <p>{self._escape(subtitle)}</p>
  </header>
  <main>
    <section class="summary">
      <div><strong>Membros ativos</strong><span>{len(members)}</span></div>
      <div><strong>Turmas</strong><span>{len(classes)}</span></div>
      <div><strong>Eventos futuros</strong><span>{len(events)}</span></div>
      <div><strong>Aulas futuras</strong><span>{len(sessions)}</span></div>
    </section>
    <section>
      <h2>Comunicados</h2>
      <table><thead><tr><th>Data</th><th>Comunicado</th></tr></thead><tbody>{notice_rows}</tbody></table>
    </section>
    <section>
      <h2>Calendario</h2>
      <h3>Eventos</h3>
      <table><thead><tr><th>Data</th><th>Hora</th><th>Tipo</th><th>Evento</th><th>Local</th><th>Status</th></tr></thead><tbody>{event_rows}</tbody></table>
      <h3>Aulas e treinos</h3>
      <table><thead><tr><th>Data</th><th>Hora</th><th>Aula/Treino</th><th>Turma</th><th>Nivel</th><th>Objetivo</th></tr></thead><tbody>{session_rows}</tbody></table>
    </section>
    <section>
      <h2>Turmas</h2>
      <table><thead><tr><th>Turma</th><th>Professor</th><th>Dia</th><th>Horario</th><th>Local</th><th>Alunos</th></tr></thead><tbody>{class_rows}</tbody></table>
    </section>
    <section>
      <h2>Ranking interno</h2>
      <table><thead><tr><th>Pos</th><th>Membro</th><th>Rating</th><th>Categoria</th><th>Turma</th><th>Aproveitamento</th></tr></thead><tbody>{ranking_rows}</tbody></table>
    </section>
    <section>
      <h2>Torneios recentes</h2>
      <table><thead><tr><th>Torneio</th><th>Data</th><th>Local</th><th>Status</th></tr></thead><tbody>{tournament_rows}</tbody></table>
    </section>
  </main>
  <footer>Gerado em {self._escape(generated_at)}</footer>
</body>
</html>
"""

    def _portal_notice_rows(
        self,
        events: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
    ) -> str:
        notices: list[tuple[str, str]] = []
        for event in events[:5]:
            details = " - ".join(
                part
                for part in [
                    str(event.get("title") or ""),
                    str(event.get("location") or ""),
                    str(event.get("notes") or ""),
                ]
                if part
            )
            notices.append((str(event.get("event_date") or ""), details))
        for session in sessions[:5]:
            details = " - ".join(
                part
                for part in [
                    str(session.get("title") or ""),
                    str(session.get("class_name") or ""),
                    str(session.get("homework") or session.get("objective") or ""),
                ]
                if part
            )
            notices.append((str(session.get("session_date") or ""), details))
        notices.sort(key=lambda item: item[0])
        if not notices:
            return "<tr><td colspan=\"2\">Nenhum comunicado futuro cadastrado.</td></tr>"
        return "".join(
            "<tr>"
            f"<td>{self._escape(day)}</td>"
            f"<td>{self._escape(text)}</td>"
            "</tr>"
            for day, text in notices
        )

    @staticmethod
    def _club_portal_css() -> str:
        return """* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  color: #18212f;
  background: #f5f7fb;
}
header {
  background: #17403a;
  color: #fff;
  padding: 30px 40px;
}
header h1 { margin: 4px 0 8px; font-size: 32px; }
header p { margin: 0; color: #dbe8e5; }
.eyebrow { text-transform: uppercase; letter-spacing: 0; font-size: 12px; }
main { max-width: 1180px; margin: 0 auto; padding: 24px; }
section {
  background: #fff;
  border: 1px solid #dfe5ed;
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 18px;
  overflow-x: auto;
}
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}
.summary div {
  border: 1px solid #dfe5ed;
  border-radius: 8px;
  padding: 12px;
}
.summary strong, .summary span { display: block; }
.summary span { margin-top: 4px; color: #546173; }
h2 { margin: 0 0 12px; font-size: 20px; }
h3 { margin: 16px 0 8px; font-size: 15px; color: #344154; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th, td {
  border-bottom: 1px solid #e4e9f1;
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
}
th { background: #eef4f2; }
footer {
  color: #657386;
  font-size: 13px;
  padding: 8px 24px 32px;
  text-align: center;
}
"""

    def _site_html(
        self,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        schedule: list[dict[str, Any]],
        players: list[dict[str, Any]],
        rounds: list[dict[str, Any]],
        standings: list[dict[str, Any]],
    ) -> str:
        tournament_id = int(tournament["id"])
        is_team_tournament = tournament.get("competition_type") == "team"
        round_sections = []
        for round_data in rounds:
            if is_team_tournament:
                round_sections.append(self._site_team_round_section(round_data))
            else:
                round_sections.append(self._site_individual_round_section(round_data))

        schedule_rows = "".join(
            "<tr>"
            f"<td>{item['round_number']}</td>"
            f"<td>{self._escape(item.get('date') or '')}</td>"
            f"<td>{self._escape(item.get('time') or '')}</td>"
            "</tr>"
            for item in schedule
            if item.get("date") or item.get("time")
        )
        players_rows = "".join(
            "<tr>"
            f"<td>{self._escape(player_full_name(player))}</td>"
            f"<td>{self._escape(player.get('title') or '')}</td>"
            f"<td>{self._escape(player.get('fide_id') or '')}</td>"
            f"<td>{self._escape(player.get('cbx_id') or '')}</td>"
            f"<td>{player['rating']}</td>"
            f"<td>{self._escape(player['club'])}</td>"
            f"<td>{self._escape(player['category'])}</td>"
            f"<td>{self._escape(player.get('age_category') or '')}</td>"
            f"<td>{self._escape(player.get('rating_category') or '')}</td>"
            f"<td>{self._escape(player.get('prize_tags') or '')}</td>"
            f"<td>{self._escape(PLAYER_STATUSES.get(player.get('player_status', 'active'), player.get('player_status', '')))}</td>"
            "</tr>"
            for player in players
        )
        standings_section = self._site_standings_section(settings, standings, is_team_tournament)
        team_sections = self._site_team_sections(tournament_id) if is_team_tournament else ""

        generated_at = Database.now()
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{self._escape(tournament['name'])}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <p class="eyebrow">Albericus</p>
    <h1>{self._escape(tournament['name'])}</h1>
    <p>{self._escape(tournament['location'])}</p>
  </header>
  <main>
    <section class="summary">
      <div><strong>Periodo</strong><span>{self._escape(tournament['start_date'])} - {self._escape(tournament['end_date'])}</span></div>
      <div><strong>Rodadas</strong><span>{tournament['rounds_count']}</span></div>
      <div><strong>Ritmo</strong><span>{self._escape(tournament['time_control'])}</span></div>
      <div><strong>Competicao</strong><span>{self._escape(COMPETITION_TYPES.get(tournament.get('competition_type', 'individual'), 'Individual'))}</span></div>
      <div><strong>Status</strong><span>{self._escape(tournament['status'])}</span></div>
    </section>
    <section>
      <h2>Informacoes</h2>
      <dl>
        <dt>FIDE Event-ID</dt><dd>{self._escape(settings.get('fide_event_id') or '')}</dd>
        <dt>Organizador</dt><dd>{self._escape(settings.get('organizer') or '')}</dd>
        <dt>Diretor</dt><dd>{self._escape(settings.get('director') or '')}</dd>
        <dt>Arbitro principal</dt><dd>{self._escape(settings.get('chief_arbiter') or '')}</dd>
        <dt>Categorias</dt><dd>{self._escape(settings.get('categories') or '')}</dd>
      </dl>
    </section>
    <section>
      <h2>Agenda</h2>
      <table><thead><tr><th>Rodada</th><th>Data</th><th>Hora</th></tr></thead><tbody>{schedule_rows}</tbody></table>
    </section>
    {standings_section}
    {team_sections}
    <section>
      <h2>Jogadores</h2>
      <table><thead><tr><th>Nome</th><th>Titulo</th><th>FIDE</th><th>CBX</th><th>Rating</th><th>Clube</th><th>Categoria</th><th>Idade</th><th>Rating cat.</th><th>Tags</th><th>Status</th></tr></thead><tbody>{players_rows}</tbody></table>
    </section>
    {''.join(round_sections)}
  </main>
  <footer>Gerado em {self._escape(generated_at)} - Torneio #{tournament_id}</footer>
</body>
</html>
"""

    def _site_individual_round_section(self, round_data: dict[str, Any]) -> str:
        pairings = self.db.get_pairings_for_round(round_data["id"])
        rows = []
        for pairing in pairings:
            black_name = "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black")
            black_rating = "" if pairing["is_bye"] else pairing["black_rating"]
            rows.append(
                "<tr>"
                f"<td>{pairing['board_number']}</td>"
                f"<td>{self._escape(pairing_player_name(pairing, 'white'))}</td>"
                f"<td>{pairing['white_rating']}</td>"
                f"<td>{self._escape(pairing['result'] or '')}</td>"
                f"<td>{self._escape(black_name or '')}</td>"
                f"<td>{self._escape(black_rating or '')}</td>"
                "</tr>"
            )
        return (
            "<section>"
            f"<h2>Rodada {round_data['number']}</h2>"
            f"<p>Status: {self._escape(round_data['status'])}</p>"
            "<table><thead><tr><th>Mesa</th><th>Brancas</th><th>Rating</th>"
            "<th>Resultado</th><th>Pretas</th><th>Rating</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            "</section>"
        )

    def _site_team_round_section(self, round_data: dict[str, Any]) -> str:
        rows = []
        for match in self.db.list_team_matches_for_round(int(round_data["id"])):
            match_score = self._team_match_score(match)
            if match.get("is_bye"):
                rows.append(
                    "<tr>"
                    f"<td>{match['match_number']}</td>"
                    f"<td>{self._escape(match.get('white_team_name') or '')}</td>"
                    f"<td>{self._escape(match_score)}</td>"
                    "<td>BYE</td><td></td><td></td><td>BYE</td><td></td>"
                    "</tr>"
                )
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                rows.append(
                    "<tr>"
                    f"<td>{match['match_number']}</td>"
                    f"<td>{self._escape(match.get('white_team_name') or '')}</td>"
                    f"<td>{self._escape(match_score)}</td>"
                    f"<td>{self._escape(match.get('black_team_name') or '')}</td>"
                    f"<td>{board['board_number']}</td>"
                    f"<td>{self._escape(self._team_board_player_name(board, 'white'))}</td>"
                    f"<td>{self._escape(board.get('result') or '')}</td>"
                    f"<td>{self._escape(self._team_board_player_name(board, 'black'))}</td>"
                    "</tr>"
                )
        return (
            "<section>"
            f"<h2>Rodada {round_data['number']}</h2>"
            f"<p>Status: {self._escape(round_data['status'])}</p>"
            "<table><thead><tr><th>Confronto</th><th>Equipe A</th><th>Placar</th>"
            "<th>Equipe B</th><th>Tab.</th><th>Brancas</th><th>Resultado</th><th>Pretas</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            "</section>"
        )

    def _site_standings_section(
        self,
        settings: dict[str, Any],
        standings: list[dict[str, Any]],
        is_team_tournament: bool,
    ) -> str:
        if settings.get("hide_standings"):
            return "<section><h2>Classificacao</h2><p>Classificacao ocultada pela organizacao.</p></section>"

        if is_team_tournament:
            standings_rows = "".join(
                "<tr>"
                f"<td>{item['position']}</td>"
                f"<td>{self._escape(item['name'])}</td>"
                f"<td>{self._escape(item.get('club') or '')}</td>"
                f"<td>{self._format_report_number(item['match_points'])}</td>"
                f"<td>{self._format_report_number(item['game_points'])}</td>"
                f"<td>{item['wins']}</td>"
                f"<td>{item['draws']}</td>"
                f"<td>{item['losses']}</td>"
                f"<td>{self._format_report_number(item['buchholz'])}</td>"
                "</tr>"
                for item in standings
            )
            return (
                "<section>"
                "<h2>Classificacao por equipes</h2>"
                "<table><thead><tr><th>Pos</th><th>Equipe</th><th>Clube/Cidade</th><th>MP</th>"
                "<th>GP</th><th>V</th><th>E</th><th>D</th><th>Buchholz</th></tr></thead>"
                f"<tbody>{standings_rows}</tbody></table>"
                "</section>"
            )

        standings_rows = "".join(
            "<tr>"
            f"<td>{item['position']}</td>"
            f"<td>{self._escape(item['name'])}</td>"
            f"<td>{self._escape(item.get('category') or '')}</td>"
            f"<td>{item['points']}</td>"
            f"<td>{item['buchholz']}</td>"
            f"<td>{item['buchholz_median']}</td>"
            f"<td>{item['sonneborn_berger']}</td>"
            f"<td>{item['wins']}</td>"
            f"<td>{self._escape(item['performance'])}</td>"
            "</tr>"
            for item in standings
        )
        return (
            "<section>"
            "<h2>Classificacao</h2>"
            "<table><thead><tr><th>Pos</th><th>Jogador</th><th>Categoria</th><th>Pts</th>"
            "<th>Buchholz</th><th>Buchholz M</th><th>SB</th>"
            "<th>Vitorias</th><th>Perf.</th></tr></thead>"
            f"<tbody>{standings_rows}</tbody></table>"
            "</section>"
        )

    def _site_team_sections(self, tournament_id: int) -> str:
        team_rows = []
        roster_rows = []
        for team in self.db.list_teams(tournament_id, active_only=False):
            team_rows.append(
                "<tr>"
                f"<td>{self._escape(team['name'])}</td>"
                f"<td>{self._escape(team.get('club') or '')}</td>"
                f"<td>{self._escape(team.get('captain') or '')}</td>"
                f"<td>{team.get('starters_count', 0)}</td>"
                f"<td>{team.get('players_count', 0)}</td>"
                f"<td>{'Ativa' if team.get('active') else 'Inativa'}</td>"
                "</tr>"
            )
            for assignment in self.db.list_team_players(int(team["id"]), active_only=False):
                board_label = assignment.get("board_number") or ""
                roster_rows.append(
                    "<tr>"
                    f"<td>{self._escape(team['name'])}</td>"
                    f"<td>{self._escape(board_label)}</td>"
                    f"<td>{self._escape(TEAM_PLAYER_ROLES.get(assignment.get('role', 'starter'), assignment.get('role', '')))}</td>"
                    f"<td>{self._escape(self._team_assignment_player_name(assignment))}</td>"
                    f"<td>{assignment.get('player_rating', '')}</td>"
                    f"<td>{self._escape(PLAYER_STATUSES.get(assignment.get('player_status', 'active'), assignment.get('player_status', '')))}</td>"
                    "</tr>"
                )
        return (
            "<section>"
            "<h2>Equipes</h2>"
            "<table><thead><tr><th>Equipe</th><th>Clube/Cidade</th><th>Capitao</th>"
            "<th>Titulares</th><th>Jogadores</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(team_rows)}</tbody></table>"
            "</section>"
            "<section>"
            "<h2>Escalacoes</h2>"
            "<table><thead><tr><th>Equipe</th><th>Tabuleiro</th><th>Funcao</th><th>Jogador</th>"
            "<th>Rating</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(roster_rows)}</tbody></table>"
            "</section>"
        )

    @staticmethod
    def _site_css() -> str:
        return """* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  color: #0f172a;
  background: #f8fafc;
}
header {
  background: #0f172a;
  color: #fff;
  padding: 32px 40px;
}
header h1 { margin: 4px 0 8px; font-size: 32px; }
header p { margin: 0; color: #cbd5e1; }
.eyebrow { text-transform: uppercase; letter-spacing: 0; font-size: 12px; }
main { max-width: 1180px; margin: 0 auto; padding: 24px; }
section {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 18px;
  overflow-x: auto;
}
h2 { margin: 0 0 12px; font-size: 20px; }
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}
.summary div {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
}
.summary strong, .summary span { display: block; }
.summary span { margin-top: 4px; color: #475569; }
dl {
  display: grid;
  grid-template-columns: minmax(160px, 240px) 1fr;
  gap: 8px 12px;
  margin: 0;
}
dt { font-weight: 700; }
dd { margin: 0; color: #334155; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th, td {
  border-bottom: 1px solid #e2e8f0;
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
}
th { background: #f1f5f9; }
footer {
  color: #64748b;
  font-size: 13px;
  padding: 8px 24px 32px;
  text-align: center;
}
"""

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value or ""))

    @staticmethod
    def _tournament_scope_label(tournament: dict[str, Any]) -> str:
        if tournament.get("class_id"):
            return TOURNAMENT_SCOPES["class"]
        if tournament.get("club_id"):
            return TOURNAMENT_SCOPES["club"]
        return TOURNAMENT_SCOPES["standalone"]

    def _tournament_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        rows = [
            ["Nome", tournament["name"]],
            ["Escopo", self._tournament_scope_label(tournament)],
            [
                "Competicao",
                COMPETITION_TYPES.get(tournament.get("competition_type", "individual"), "Individual"),
            ],
            ["Clube/Escola", tournament.get("club_name", "")],
            ["Turma", tournament.get("class_name", "")],
            ["Local", tournament["location"]],
            ["Data inicial", tournament["start_date"]],
            ["Data final", tournament["end_date"]],
            ["Sistema", tournament["system"]],
            ["Rodadas", tournament["rounds_count"]],
            ["Ritmo", tournament["time_control"]],
            ["Pontos do bye", tournament["bye_points"]],
            ["Status", tournament["status"]],
        ]
        settings = self.db.get_tournament_settings(tournament_id) or {}
        rows.extend(
            [
                ["FIDE Event-ID", settings.get("fide_event_id", "")],
                ["Organizador", settings.get("organizer", "")],
                ["Pagina web", settings.get("website", "")],
                ["E-mail", settings.get("contact_email", "")],
                ["Diretor", settings.get("director", "")],
                ["Arbitro principal", settings.get("chief_arbiter", "")],
                ["Federacao", settings.get("federation", "")],
                ["Estado", settings.get("state", "")],
                ["Categorias", settings.get("categories", "")],
                ["Data de corte", settings.get("cutoff_date", "")],
                ["Ordem inicial", settings.get("initial_order", "")],
                ["Tipo de torneio", settings.get("tournament_type", "")],
                ["Calcular desempenho", "Sim" if settings.get("calculate_performance") else "Nao"],
            ]
        )
        if tournament.get("competition_type") == "team":
            rows.extend(
                [
                    ["Tabuleiros por equipe", settings.get("team_boards_count", "")],
                    ["Pontos por vitoria da equipe", settings.get("team_match_win_points", "")],
                    ["Pontos por empate da equipe", settings.get("team_match_draw_points", "")],
                    ["Pontos por derrota da equipe", settings.get("team_match_loss_points", "")],
                    [
                        "Metodo por equipes",
                        TEAM_PAIRING_METHODS.get(
                            settings.get("team_pairing_method", "swiss"),
                            settings.get("team_pairing_method", ""),
                        ),
                    ],
                    [
                        "Criterio principal por equipes",
                        TEAM_STANDING_CRITERIA.get(
                            settings.get("team_standing_primary", "match_points"),
                            settings.get("team_standing_primary", ""),
                        ),
                    ],
                    [
                        "Criterio secundario por equipes",
                        TEAM_STANDING_CRITERIA.get(
                            settings.get("team_standing_secondary", "game_points"),
                            settings.get("team_standing_secondary", ""),
                        ),
                    ],
                    [
                        "Ordem fixa dos tabuleiros",
                        "Sim" if settings.get("team_fixed_board_order", 1) else "Nao",
                    ],
                ]
            )
        for item in self.db.list_round_schedule(tournament_id):
            if item["date"] or item["time"]:
                rows.append([f"Rodada {item['round_number']}", f"{item['date']} {item['time']}".strip()])
        return "Torneio", ["Campo", "Valor"], rows

    def _players_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        players = self.db.list_players(tournament_id, active_only=False)
        rows = [
            [
                player["id"],
                player_full_name(player),
                player.get("title", ""),
                player.get("fide_id", ""),
                player.get("cbx_id", ""),
                player["rating"],
                player.get("national_rating", 0),
                player.get("international_rating", 0),
                player.get("starting_points", 0),
                player["club"],
                player["category"],
                player.get("age_category", ""),
                player.get("rating_category", ""),
                player.get("prize_tags", ""),
                player.get("birth_date", ""),
                player.get("sex", ""),
                PLAYER_STATUSES.get(player.get("player_status", "active"), player.get("player_status", "")),
            ]
            for player in players
        ]
        return (
            "Jogadores",
            [
                "ID",
                "Nome",
                "Titulo",
                "FIDE ID",
                "CBX ID",
                "Rating",
                "Rating nacional",
                "Rating internacional",
                "Pontos iniciais",
                "Clube",
                "Categoria",
                "Categoria idade",
                "Categoria rating",
                "Tags premiacao",
                "Nascimento",
                "Sexo",
                "Status",
            ],
            rows,
        )

    def _teams_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Este relatorio esta disponivel apenas para torneios por equipes.")
        rows = [
            [
                team["id"],
                team["name"],
                team.get("club", ""),
                team.get("captain", ""),
                team.get("starters_count", 0),
                team.get("players_count", 0),
                "Ativa" if team.get("active") else "Inativa",
                team.get("notes", ""),
            ]
            for team in self.db.list_teams(tournament_id, active_only=False)
        ]
        return (
            "Equipes",
            ["ID", "Equipe", "Clube/Cidade", "Capitao", "Titulares", "Jogadores", "Status", "Observacoes"],
            rows,
        )

    def _team_rosters_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Este relatorio esta disponivel apenas para torneios por equipes.")

        rows = []
        for team in self.db.list_teams(tournament_id, active_only=False):
            for assignment in self.db.list_team_players(int(team["id"]), active_only=False):
                rows.append(
                    [
                        team["name"],
                        assignment.get("board_number") or "",
                        TEAM_PLAYER_ROLES.get(assignment.get("role", "starter"), assignment.get("role", "")),
                        self._team_assignment_player_name(assignment),
                        assignment.get("player_rating", ""),
                        assignment.get("player_club", ""),
                        assignment.get("player_category", ""),
                        assignment.get("player_age_category", ""),
                        assignment.get("player_rating_category", ""),
                        assignment.get("player_prize_tags", ""),
                        PLAYER_STATUSES.get(
                            assignment.get("player_status", "active"),
                            assignment.get("player_status", ""),
                        ),
                    ]
                )
        return (
            "Escalacoes",
            [
                "Equipe",
                "Tabuleiro",
                "Funcao",
                "Jogador",
                "Rating",
                "Clube",
                "Categoria",
                "Categoria idade",
                "Categoria rating",
                "Tags premiacao",
                "Status",
            ],
            rows,
        )

    def _club_report_sections(self) -> list[tuple[str, list[str], list[list[Any]]]]:
        clubs = self.db.list_clubs(active_only=False)
        summary = self.db.club_summary()
        members = self.db.list_members(active_only=False)
        tournaments = self.db.list_tournaments()
        classes = self.db.list_classes(active_only=False)
        guardians = self.db.list_guardians(active_only=False)
        sessions = self.db.list_training_sessions()
        plans = self.db.list_membership_plans(active_only=False)
        events = self.db.list_club_events()
        finance_service = __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db)
        finance_summary = finance_service.finance_summary()
        payments = finance_service.payments_report()
        minor_members_without_guardians = __import__('src.services.member_service', fromlist=['GuardianService']).GuardianService(self.db).minor_members_without_guardians()

        member_ratings = [int(member.get("rating") or 0) for member in members if int(member.get("rating") or 0) > 0]
        average_rating = round(sum(member_ratings) / len(member_ratings), 1) if member_ratings else 0

        club_rows = [
            [
                club["id"],
                club["name"],
                club.get("kind", ""),
                "Sim" if club.get("active") else "Nao",
                club.get("city", ""),
                club.get("phone", ""),
                club.get("email", ""),
                club.get("members_count", 0),
                club.get("active_classes_count", 0),
                club.get("tournaments_count", 0),
            ]
            for club in clubs
        ]
        class_rows = [
            [
                item["id"],
                item["club_name"],
                item["name"],
                item["teacher"],
                item["weekday"],
                item["time"],
                item["location"],
                "Sim" if item["active"] else "Nao",
                item["active_members_count"],
            ]
            for item in classes
        ]
        session_rows = [
            [
                item["id"],
                item["title"],
                TRAINING_SESSION_TYPES.get(item["session_type"], item["session_type"]),
                item["session_date"],
                item["start_time"],
                item["club_name"],
                item["class_name"],
                item.get("learning_level_name") or "",
                item.get("objective") or "",
                item.get("content") or "",
                item.get("homework") or "",
                item["instructor"],
                TRAINING_SESSION_STATUSES.get(item["status"], item["status"]),
                item["present_count"],
                item["absent_count"],
                item["justified_count"],
            ]
            for item in sessions[:100]
        ]
        guardian_rows = [
            [
                guardian["id"],
                guardian["name"],
                guardian["phone"],
                guardian["email"],
                guardian["document"],
                "Sim" if guardian.get("active") else "Nao",
                guardian["members_count"],
                guardian["active_members_count"],
            ]
            for guardian in guardians
        ]
        plan_rows = [
            [
                plan["id"],
                plan["name"],
                plan["amount"],
                BILLING_CYCLES.get(plan["billing_cycle"], plan["billing_cycle"]),
                "Sim" if plan.get("active") else "Nao",
                plan["payments_count"],
            ]
            for plan in plans
        ]
        payment_rows = [
            [
                payment["id"],
                payment["member_name"],
                payment.get("plan_name") or "",
                payment["description"],
                payment["reference_period"],
                payment["due_date"],
                payment["payment_date"],
                payment["amount"],
                PAYMENT_STATUSES.get(payment["effective_status"], payment["effective_status"]),
                payment["method"],
            ]
            for payment in payments[:100]
        ]
        event_rows = [
            [
                event["id"],
                event["title"],
                EVENT_TYPES.get(event["event_type"], event["event_type"]),
                event["event_date"],
                event["start_time"],
                event["club_name"],
                event.get("tournament_name") or "",
                event["location"],
                EVENT_STATUSES.get(event["status"], event["status"]),
            ]
            for event in events[:100]
        ]
        indicator_rows = [
            ["Unidades ativas", summary.get("active_clubs", 0)],
            ["Turmas ativas", summary.get("active_classes", 0)],
            ["Membros ativos", summary.get("active_members", 0)],
            ["Total de membros", summary.get("total_members", 0)],
            ["Responsaveis cadastrados", len(guardians)],
            ["Menores sem responsavel", len(minor_members_without_guardians)],
            ["Aulas/treinos cadastrados", len(sessions)],
            ["Eventos no calendario", len(events)],
            ["Planos financeiros", len(plans)],
            ["Lancamentos financeiros", finance_summary["total_payments"]],
            ["Recebido", finance_summary["paid_amount"]],
            ["Pendente", finance_summary["pending_amount"]],
            ["Atrasado", finance_summary["late_amount"]],
            ["Torneios cadastrados", summary.get("total_tournaments", 0)],
            ["Torneios em andamento", summary.get("running_tournaments", 0)],
            ["Membros com rating interno", len(member_ratings)],
            ["Rating interno medio", average_rating],
        ]
        status_rows = self._count_member_field(members, "status")
        type_rows = self._count_member_field(members, "member_type")
        category_rows = self._count_member_field(members, "category")
        ranking_rows = [
            [
                index,
                member["name"],
                member.get("club_name", ""),
                member.get("active_class_name", ""),
                member["rating"],
                member["category"],
                member["member_type"],
                member["status"],
            ]
            for index, member in enumerate(
                sorted(
                    members,
                    key=lambda item: (
                        -int(item.get("rating") or 0),
                        str(item.get("name") or "").casefold(),
                    ),
                )[:50],
                start=1,
            )
            if int(member.get("rating") or 0) > 0
        ]
        tournament_rows = [
            [
                tournament["id"],
                tournament["name"],
                self._tournament_scope_label(tournament),
                tournament.get("club_name", ""),
                tournament.get("class_name", ""),
                tournament["location"],
                tournament["start_date"],
                tournament["end_date"],
                tournament["rounds_count"],
                tournament["status"],
                len(self.db.list_players(int(tournament["id"]), active_only=False)),
                len(self.db.list_rounds(int(tournament["id"]))),
            ]
            for tournament in tournaments
        ]

        return [
            (
                "Clubes e escolas",
                [
                    "ID",
                    "Nome",
                    "Tipo",
                    "Ativo",
                    "Cidade",
                    "Telefone",
                    "E-mail",
                    "Membros",
                    "Turmas ativas",
                    "Torneios",
                ],
                club_rows,
            ),
            (
                "Turmas",
                ["ID", "Clube/Escola", "Turma", "Professor", "Dia", "Horario", "Local", "Ativa", "Alunos ativos"],
                class_rows,
            ),
            (
                "Responsaveis",
                ["ID", "Nome", "Telefone", "E-mail", "Documento", "Ativo", "Membros", "Membros ativos"],
                guardian_rows,
            ),
            (
                "Aulas e presencas",
                [
                    "ID",
                    "Titulo",
                    "Tipo",
                    "Data",
                    "Inicio",
                    "Clube/Escola",
                    "Turma",
                    "Nivel",
                    "Objetivo",
                    "Conteudo",
                    "Tarefa",
                    "Instrutor",
                    "Status",
                    "Presentes",
                    "Faltas",
                    "Justificadas",
                ],
                session_rows,
            ),
            (
                "Planos financeiros",
                ["ID", "Nome", "Valor", "Ciclo", "Ativo", "Lancamentos"],
                plan_rows,
            ),
            (
                "Financeiro",
                [
                    "ID",
                    "Membro",
                    "Plano",
                    "Descricao",
                    "Referencia",
                    "Vencimento",
                    "Pagamento",
                    "Valor",
                    "Status",
                    "Metodo",
                ],
                payment_rows,
            ),
            (
                "Calendario",
                [
                    "ID",
                    "Titulo",
                    "Tipo",
                    "Data",
                    "Inicio",
                    "Clube/Escola",
                    "Torneio vinculado",
                    "Local",
                    "Status",
                ],
                event_rows,
            ),
            ("Indicadores", ["Indicador", "Valor"], indicator_rows),
            ("Membros por status", ["Status", "Quantidade"], status_rows),
            ("Membros por tipo", ["Tipo", "Quantidade"], type_rows),
            ("Membros por categoria", ["Categoria", "Quantidade"], category_rows),
            (
                "Ranking interno",
                ["Pos", "Nome", "Clube/Escola", "Turma", "Rating", "Categoria", "Tipo", "Status"],
                ranking_rows,
            ),
            (
                "Torneios",
                [
                    "ID",
                    "Nome",
                    "Escopo",
                    "Clube/Escola",
                    "Turma",
                    "Local",
                    "Data inicial",
                    "Data final",
                    "Rodadas previstas",
                    "Status",
                    "Jogadores",
                    "Rodadas geradas",
                ],
                tournament_rows,
            ),
        ]

    def _tournaments_period_sections(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        start_date = start_date.strip()
        end_date = end_date.strip()
        tournaments = [
            tournament
            for tournament in self.db.list_tournaments()
            if self._date_in_period(self._tournament_report_date(tournament), start_date, end_date)
        ]
        tournaments = sorted(
            tournaments,
            key=lambda item: (
                str(item.get("start_date") or item.get("created_at") or ""),
                int(item.get("id") or 0),
            ),
        )

        period_rows: list[list[Any]] = [
            ["Data inicial", start_date or "Sem filtro"],
            ["Data final", end_date or "Sem filtro"],
            ["Torneios encontrados", len(tournaments)],
            ["Gerado em", Database.now()],
        ]
        tournament_rows: list[list[Any]] = []
        standings_rows: list[list[Any]] = []
        for tournament in tournaments:
            tournament_id = int(tournament["id"])
            players = self.db.list_players(tournament_id, active_only=False)
            rounds = self.db.list_rounds(tournament_id)
            closed_rounds = [round_data for round_data in rounds if round_data["status"] == "closed"]
            standings = self.pairing_service.standings(tournament_id)
            leader = standings[0] if standings else None
            tournament_rows.append(
                [
                    tournament_id,
                    tournament["name"],
                    self._tournament_scope_label(tournament),
                    tournament.get("club_name", ""),
                    tournament.get("class_name", ""),
                    self._tournament_report_date(tournament),
                    tournament["location"],
                    tournament["rounds_count"],
                    tournament["status"],
                    len(players),
                    len(rounds),
                    len(closed_rounds),
                    leader["name"] if leader else "",
                    leader["points"] if leader else "",
                ]
            )
            for item in standings[:10]:
                standings_rows.append(
                    [
                        tournament["name"],
                        item["position"],
                        item["name"],
                        item["points"],
                        item["performance"],
                        item["rating"],
                        item["club"],
                    ]
                )

        return [
            ("Periodo", ["Campo", "Valor"], period_rows),
            (
                "Torneios por periodo",
                [
                    "ID",
                    "Nome",
                    "Escopo",
                    "Clube/Escola",
                    "Turma",
                    "Data",
                    "Local",
                    "Rodadas previstas",
                    "Status",
                    "Jogadores",
                    "Rodadas geradas",
                    "Rodadas fechadas",
                    "Lider",
                    "Pontos lider",
                ],
                tournament_rows,
            ),
            (
                "Top 10 por torneio",
                ["Torneio", "Pos", "Jogador", "Pontos", "Performance", "Rating", "Clube"],
                standings_rows,
            ),
        ]

    def _attendance_report_sections(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        start_date = start_date.strip()
        end_date = end_date.strip()
        training_service = __import__('src.services.education_service', fromlist=['TrainingService']).TrainingService(self.db)
        rows = training_service.attendance_report(start_date=start_date, end_date=end_date)
        sessions = self.db.list_training_sessions(start_date=start_date, end_date=end_date)

        summary_rows: list[list[Any]] = [
            ["Data inicial", start_date or "Sem filtro"],
            ["Data final", end_date or "Sem filtro"],
            ["Aulas/treinos no periodo", len(sessions)],
            ["Registros de chamada", len(rows)],
            ["Presencas", sum(1 for item in rows if item["status"] == "present")],
            ["Faltas", sum(1 for item in rows if item["status"] == "absent")],
            ["Faltas justificadas", sum(1 for item in rows if item["status"] == "justified")],
            ["Gerado em", Database.now()],
        ]
        session_rows = [
            [
                item["id"],
                item["title"],
                TRAINING_SESSION_TYPES.get(item["session_type"], item["session_type"]),
                item["session_date"],
                item["start_time"],
                item["end_time"],
                item["club_name"],
                item["class_name"],
                item["instructor"],
                TRAINING_SESSION_STATUSES.get(item["status"], item["status"]),
                item["present_count"],
                item["absent_count"],
                item["justified_count"],
            ]
            for item in sessions
        ]
        attendance_rows = [
            [
                item["session_date"],
                item["start_time"],
                item["title"],
                TRAINING_SESSION_TYPES.get(item["session_type"], item["session_type"]),
                item["club_name"],
                item["class_name"],
                item["member_name"],
                item["member_category"],
                ATTENDANCE_STATUSES.get(item["status"], item["status"]),
                item["notes"],
            ]
            for item in rows
        ]
        return [
            ("Resumo", ["Indicador", "Valor"], summary_rows),
            (
                "Aulas e treinos",
                [
                    "ID",
                    "Titulo",
                    "Tipo",
                    "Data",
                    "Inicio",
                    "Fim",
                    "Clube/Escola",
                    "Turma",
                    "Instrutor",
                    "Status",
                    "Presentes",
                    "Faltas",
                    "Justificadas",
                ],
                session_rows,
            ),
            (
                "Chamada",
                [
                    "Data",
                    "Inicio",
                    "Aula/Treino",
                    "Tipo",
                    "Clube/Escola",
                    "Turma",
                    "Membro",
                    "Categoria",
                    "Presenca",
                    "Observacoes",
                ],
                attendance_rows,
            ),
        ]

    def _financial_report_sections(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        start_date = start_date.strip()
        end_date = end_date.strip()
        finance_service = __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db)
        summary = finance_service.finance_summary(start_date=start_date, end_date=end_date)
        payments = finance_service.payments_report(start_date=start_date, end_date=end_date)
        plans = self.db.list_membership_plans(active_only=False)

        summary_rows: list[list[Any]] = [
            ["Data inicial", start_date or "Sem filtro"],
            ["Data final", end_date or "Sem filtro"],
            ["Lancamentos", summary["total_payments"]],
            ["Pagos", summary["paid"]],
            ["Pendentes", summary["pending"]],
            ["Atrasados", summary["late"]],
            ["Isentos", summary["exempt"]],
            ["Valor recebido", summary["paid_amount"]],
            ["Valor pendente", summary["pending_amount"]],
            ["Valor atrasado", summary["late_amount"]],
            ["Gerado em", Database.now()],
        ]
        plan_rows: list[list[Any]] = [
            [
                plan["id"],
                plan["name"],
                plan["amount"],
                BILLING_CYCLES.get(plan["billing_cycle"], plan["billing_cycle"]),
                "Sim" if plan.get("active") else "Nao",
                plan["payments_count"],
                plan["notes"],
            ]
            for plan in plans
        ]
        payment_rows: list[list[Any]] = [
            [
                payment["id"],
                payment["member_name"],
                payment.get("club_name") or "",
                payment.get("active_class_name") or "",
                payment.get("plan_name") or "",
                payment["description"],
                payment["reference_period"],
                payment["due_date"],
                payment["payment_date"],
                payment["amount"],
                PAYMENT_STATUSES.get(payment["effective_status"], payment["effective_status"]),
                payment["method"],
                payment["notes"],
            ]
            for payment in payments
        ]
        member_rows: list[list[Any]] = []
        for member in self.db.list_members(active_only=False):
            status = finance_service.member_financial_status(int(member["id"]))
            member_rows.append(
                [
                    member["id"],
                    member["name"],
                    member.get("club_name") or "",
                    member.get("active_class_name") or "",
                    status["label"],
                    status["open_amount"],
                    status["late_amount"],
                ]
            )
        return [
            ("Resumo", ["Indicador", "Valor"], summary_rows),
            (
                "Planos",
                ["ID", "Nome", "Valor", "Ciclo", "Ativo", "Lancamentos", "Observacoes"],
                plan_rows,
            ),
            (
                "Lancamentos",
                [
                    "ID",
                    "Membro",
                    "Clube/Escola",
                    "Turma",
                    "Plano",
                    "Descricao",
                    "Referencia",
                    "Vencimento",
                    "Pagamento",
                    "Valor",
                    "Status",
                    "Metodo",
                    "Observacoes",
                ],
                payment_rows,
            ),
            (
                "Status por membro",
                ["ID", "Membro", "Clube/Escola", "Turma", "Status", "Valor aberto", "Valor atrasado"],
                member_rows,
            ),
        ]

    def _events_report_sections(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        start_date = start_date.strip()
        end_date = end_date.strip()
        event_service = __import__('src.services.event_service', fromlist=['EventService']).EventService(self.db)
        events = event_service.events_report(start_date=start_date, end_date=end_date)
        summary_rows: list[list[Any]] = [
            ["Data inicial", start_date or "Sem filtro"],
            ["Data final", end_date or "Sem filtro"],
            ["Eventos encontrados", len(events)],
            ["Planejados", sum(1 for event in events if event["status"] == "planned")],
            ["Confirmados", sum(1 for event in events if event["status"] == "confirmed")],
            ["Concluidos", sum(1 for event in events if event["status"] == "done")],
            ["Cancelados", sum(1 for event in events if event["status"] == "canceled")],
            ["Gerado em", Database.now()],
        ]
        event_rows: list[list[Any]] = [
            [
                event["id"],
                event["title"],
                EVENT_TYPES.get(event["event_type"], event["event_type"]),
                event["event_date"],
                event["start_time"],
                event["end_time"],
                event.get("club_name") or "",
                event.get("tournament_name") or "",
                event["location"],
                EVENT_STATUSES.get(event["status"], event["status"]),
                event["notes"],
            ]
            for event in events
        ]
        return [
            ("Resumo", ["Indicador", "Valor"], summary_rows),
            (
                "Eventos",
                [
                    "ID",
                    "Titulo",
                    "Tipo",
                    "Data",
                    "Inicio",
                    "Fim",
                    "Clube/Escola",
                    "Torneio vinculado",
                    "Local",
                    "Status",
                    "Observacoes",
                ],
                event_rows,
            ),
        ]

    def _internal_ranking_sections(
        self,
        category: str = "",
        club_id: int | None = None,
        class_id: int | None = None,
        start_date: str = "",
        end_date: str = "",
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        ranking_service = __import__('src.services.rating_service', fromlist=['InternalRatingService']).InternalRatingService(self.db)
        ranking = ranking_service.ranking(
            category=category.strip(),
            active_only=True,
            club_id=club_id,
            class_id=class_id,
            start_date=start_date.strip(),
            end_date=end_date.strip(),
        )
        club = self.db.get_club(club_id) if club_id else None
        class_data = self.db.get_class(class_id) if class_id else None
        summary_rows: list[list[Any]] = [
            ["Categoria", category.strip() or "Todas"],
            ["Clube/Escola", club.get("name", "") if club else "Todos"],
            ["Turma", class_data.get("name", "") if class_data else "Todas"],
            ["Temporada inicial", start_date.strip() or "Sem filtro"],
            ["Temporada final", end_date.strip() or "Sem filtro"],
            ["Membros no ranking", len(ranking)],
            ["Gerado em", Database.now()],
        ]
        ranking_rows: list[list[Any]] = [
            [
                item["position"],
                item["name"],
                item["club_name"],
                item["class_name"],
                item["category"],
                item["age_category"],
                item["rating_category"],
                item["prize_tags"],
                item["rating"],
                item["last_delta"],
                item["games"],
                item["wins"],
                item["draws"],
                item["losses"],
                item["points"],
                f"{item['score_rate']}%",
                item["last_performance"],
                item["last_tournament"] or "",
            ]
            for item in ranking
        ]
        category_rows: list[list[Any]] = []
        for category_name, category_ranking in ranking_service.category_rankings(
            active_only=True,
            club_id=club_id,
            class_id=class_id,
            start_date=start_date.strip(),
            end_date=end_date.strip(),
        ).items():
            if not category_ranking:
                continue
            leader = category_ranking[0]
            category_rows.append(
                [
                    category_name,
                    len(category_ranking),
                    leader["name"],
                    leader["rating"],
                    f"{leader['score_rate']}%",
                ]
            )
        return [
            ("Resumo", ["Indicador", "Valor"], summary_rows),
            (
                "Ranking interno",
                [
                    "Pos",
                    "Membro",
                    "Clube/Escola",
                    "Turma",
                    "Categoria",
                    "Categoria idade",
                    "Categoria rating",
                    "Tags premiacao",
                    "Rating",
                    "Variacao",
                    "Partidas",
                    "Vitorias",
                    "Empates",
                    "Derrotas",
                    "Pontos",
                    "Aproveitamento",
                    "Ultima performance",
                    "Ultimo torneio",
                ],
                ranking_rows,
            ),
            (
                "Categorias",
                ["Categoria", "Membros", "Lider", "Rating lider", "Aproveitamento lider"],
                category_rows,
            ),
        ]

    def _administrative_package_sections(
        self,
        start_date: str = "",
        end_date: str = "",
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        start_date = start_date.strip()
        end_date = end_date.strip()
        overview = __import__('src.services.dashboard_service', fromlist=['DashboardService']).DashboardService(self.db).overview()
        finance = overview["finance_summary"]
        cover_rows = [
            ["Gerado em", Database.now()],
            ["Periodo inicial", start_date or "Sem filtro"],
            ["Periodo final", end_date or "Sem filtro"],
            ["Membros ativos", overview["summary"].get("active_members", 0)],
            ["Torneios cadastrados", overview["summary"].get("total_tournaments", 0)],
            ["Proximos eventos", len(overview["upcoming_events"])],
            ["Valor recebido", finance.get("paid_amount", 0.0)],
            ["Valor pendente", finance.get("pending_amount", 0.0)],
            ["Valor atrasado", finance.get("late_amount", 0.0)],
        ]
        sections: list[tuple[str, list[str], list[list[Any]]]] = [
            ("Pacote administrativo", ["Campo", "Valor"], cover_rows)
        ]
        sections.extend(self._club_report_sections())
        sections.extend(self._attendance_report_sections(start_date, end_date))
        sections.extend(self._financial_report_sections(start_date, end_date))
        sections.extend(self._events_report_sections(start_date, end_date))
        sections.extend(self._tournaments_period_sections(start_date, end_date))
        sections.extend(self._internal_ranking_sections())
        return sections

    def _member_evolution_sections(
        self,
        member_id: int,
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        member = self.db.get_member(member_id)
        if not member:
            raise AppError("Membro nao encontrado.")

        member_service = __import__('src.services.member_service', fromlist=['MemberService']).MemberService(self.db)
        tournament_history = member_service.tournament_history(member_id)
        rating_history = self.db.list_member_rating_history(member_id)
        ordered_tournaments = sorted(
            tournament_history,
            key=lambda item: (
                str(item.get("start_date") or ""),
                int(item.get("tournament_id") or 0),
            ),
        )
        ordered_rating_history = sorted(
            rating_history,
            key=lambda item: (
                str(item.get("created_at") or ""),
                int(item.get("id") or 0),
            ),
        )
        rating_by_registration = {
            (int(item["tournament_id"] or 0), int(item["player_id"] or 0)): item
            for item in rating_history
        }

        member_rows: list[list[Any]] = [
            ["Nome", member["name"]],
            ["Clube/Escola", member.get("club_name", "")],
            ["Turma atual", member.get("active_class_name", "")],
            ["Tipo", member["member_type"]],
            ["Status", member["status"]],
            ["Rating interno atual", member["rating"]],
            ["Categoria", member["category"]],
            ["Categoria idade", member.get("age_category", "")],
            ["Categoria rating", member.get("rating_category", "")],
            ["Tags premiacao", member.get("prize_tags", "")],
            ["Cidade", member["city"]],
            ["Telefone", member["phone"]],
            ["E-mail", member["email"]],
            ["Nascimento", member["birth_date"]],
        ]
        guardian_rows: list[list[Any]] = [
            [
                item["guardian_name"],
                item["relationship"],
                "Sim" if item.get("primary_contact") else "Nao",
                "Sim" if item.get("emergency_contact") else "Nao",
                item["guardian_phone"],
                item["guardian_email"],
                item["guardian_document"],
                "Sim" if item.get("guardian_active") else "Nao",
                item["notes"],
            ]
            for item in self.db.list_member_guardians(member_id)
        ]
        attendance_summary = self.db.member_attendance_summary(member_id)
        attendance_summary_rows: list[list[Any]] = [
            ["Registros de chamada", attendance_summary["total"]],
            ["Presencas", attendance_summary["present"]],
            ["Faltas", attendance_summary["absent"]],
            ["Faltas justificadas", attendance_summary["justified"]],
            ["Frequencia", f"{attendance_summary['attendance_rate']}%"],
        ]
        attendance_rows: list[list[Any]] = [
            [
                item["session_date"],
                item["start_time"],
                item["title"],
                TRAINING_SESSION_TYPES.get(item["session_type"], item["session_type"]),
                item["club_name"],
                item["class_name"],
                item["instructor"],
                ATTENDANCE_STATUSES.get(item["status"], item["status"]),
                item["notes"],
            ]
            for item in self.db.list_attendance_report(member_id=member_id)
        ]
        finance_status = __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db).member_financial_status(member_id)
        payment_rows: list[list[Any]] = [
            [
                item["description"],
                item.get("plan_name") or "",
                item["reference_period"],
                item["due_date"],
                item["payment_date"],
                item["amount"],
                PAYMENT_STATUSES.get(item["effective_status"], item["effective_status"]),
                item["method"],
                item["notes"],
            ]
            for item in __import__('src.services.finance_service', fromlist=['FinanceService']).FinanceService(self.db).payments_report(member_id=member_id)
        ]
        finance_rows: list[list[Any]] = [
            ["Status financeiro", finance_status["label"]],
            ["Valor aberto", finance_status["open_amount"]],
            ["Valor atrasado", finance_status["late_amount"]],
        ]

        tournament_rows: list[list[Any]] = []
        for item in ordered_tournaments:
            rating_update = rating_by_registration.get(
                (int(item["tournament_id"]), int(item["player_id"]))
            )
            old_rating = rating_update["old_rating"] if rating_update else ""
            new_rating = rating_update["new_rating"] if rating_update else ""
            delta = ""
            if rating_update:
                delta_value = int(rating_update["new_rating"] or 0) - int(rating_update["old_rating"] or 0)
                delta = f"+{delta_value}" if delta_value >= 0 else str(delta_value)
            tournament_rows.append(
                [
                    item["name"],
                    item["start_date"],
                    item["status"],
                    item["player_rating"],
                    item["points"],
                    item["position"],
                    item["performance"],
                    old_rating,
                    new_rating,
                    delta,
                    item["rounds_played"],
                    item["wins"],
                    item["draws"],
                    item["losses"],
                    item["byes"],
                    item["last_result"],
                ]
            )

        rating_rows: list[list[Any]] = []
        for item in ordered_rating_history:
            old_rating = int(item["old_rating"] or 0)
            new_rating = int(item["new_rating"] or 0)
            rating_delta = new_rating - old_rating
            rating_rows.append(
                [
                    item["created_at"],
                    item.get("tournament_name") or "",
                    old_rating,
                    new_rating,
                    f"+{rating_delta}" if rating_delta >= 0 else str(rating_delta),
                    item["performance"],
                    item["games"],
                    item["points"],
                ]
            )

        result_rows: list[list[Any]] = []
        for tournament_item in ordered_tournaments:
            for result in member_service.tournament_results(member_id, int(tournament_item["tournament_id"])):
                result_rows.append(
                    [
                        tournament_item["name"],
                        result["round_number"],
                        result["round_status"],
                        result["board_number"],
                        result["color"],
                        result["opponent"],
                        result["result"],
                        result["outcome"],
                        "" if result["points"] is None else result["points"],
                    ]
                )

        return [
            ("Aluno", ["Campo", "Valor"], member_rows),
            (
                "Responsaveis",
                [
                    "Nome",
                    "Parentesco",
                    "Principal",
                    "Emergencia",
                    "Telefone",
                    "E-mail",
                    "Documento",
                    "Ativo",
                    "Observacoes",
                ],
                guardian_rows,
            ),
            ("Resumo de frequencia", ["Indicador", "Valor"], attendance_summary_rows),
            (
                "Presencas",
                [
                    "Data",
                    "Inicio",
                    "Aula/Treino",
                    "Tipo",
                    "Clube/Escola",
                    "Turma",
                    "Instrutor",
                    "Presenca",
                    "Observacoes",
                ],
                attendance_rows,
            ),
            ("Resumo financeiro", ["Indicador", "Valor"], finance_rows),
            (
                "Financeiro",
                [
                    "Descricao",
                    "Plano",
                    "Referencia",
                    "Vencimento",
                    "Pagamento",
                    "Valor",
                    "Status",
                    "Metodo",
                    "Observacoes",
                ],
                payment_rows,
            ),
            (
                "Evolucao por torneio",
                [
                    "Torneio",
                    "Data",
                    "Status",
                    "Rating inscricao",
                    "Pontos",
                    "Posicao",
                    "Performance",
                    "Rating anterior",
                    "Rating novo",
                    "Variacao",
                    "Rodadas",
                    "Vitorias",
                    "Empates",
                    "Derrotas",
                    "Byes",
                    "Ultimo resultado",
                ],
                tournament_rows,
            ),
            (
                "Rating interno",
                [
                    "Data",
                    "Torneio",
                    "Rating anterior",
                    "Rating novo",
                    "Variacao",
                    "Performance",
                    "Partidas",
                    "Pontos",
                ],
                rating_rows,
            ),
            (
                "Resultados",
                [
                    "Torneio",
                    "Rodada",
                    "Status rodada",
                    "Mesa",
                    "Cor",
                    "Adversario",
                    "Resultado",
                    "Desfecho",
                    "Pontos",
                ],
                result_rows,
            ),
        ]

    @staticmethod
    def _count_member_field(
        members: list[dict[str, Any]],
        field: str,
    ) -> list[list[Any]]:
        totals: dict[str, int] = {}
        for member in members:
            value = str(member.get(field) or "").strip() or "Sem informacao"
            totals[value] = totals.get(value, 0) + 1
        return [[key, totals[key]] for key in sorted(totals, key=lambda item: item.casefold())]

    @staticmethod
    def _tournament_report_date(tournament: dict[str, Any]) -> str:
        return str(tournament.get("start_date") or tournament.get("created_at") or "")[:10]

    @staticmethod
    def _date_in_period(value: str, start_date: str, end_date: str) -> bool:
        if start_date and value and value < start_date:
            return False
        if end_date and value and value > end_date:
            return False
        if (start_date or end_date) and not value:
            return False
        return True

    def _pairings_section(self, round_id: int) -> tuple[str, list[str], list[list[Any]]]:
        round_data = self.db.get_round(round_id)
        if not round_data:
            raise AppError("Rodada nao encontrada.")
        tournament = self.db.get_tournament(int(round_data["tournament_id"]))
        if tournament and tournament.get("competition_type") == "team":
            return self._team_pairings_section(round_data)
        pairings = self.db.get_pairings_for_round(round_id)
        rows = []
        for pairing in pairings:
            rows.append(
                [
                    pairing["board_number"],
                    pairing_player_name(pairing, "white"),
                    pairing["white_rating"],
                    pairing["result"],
                    "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black"),
                    "" if pairing["is_bye"] else pairing["black_rating"],
                ]
            )
        return (
            f"Rodada {round_data['number']}",
            ["Mesa", "Brancas", "Rating", "Resultado", "Pretas", "Rating"],
            rows,
        )

    def _team_pairings_section(self, round_data: dict[str, Any]) -> tuple[str, list[str], list[list[Any]]]:
        rows = []
        for match in self.db.list_team_matches_for_round(int(round_data["id"])):
            match_result = self._team_match_score(match)
            white_match_points = self._team_match_points_label(match, "white")
            black_match_points = self._team_match_points_label(match, "black")
            if match.get("is_bye"):
                rows.append(
                    [
                        match["match_number"],
                        match.get("white_team_name", ""),
                        white_match_points,
                        match_result,
                        black_match_points,
                        "BYE",
                        "",
                        "",
                        "BYE",
                        "",
                    ]
                )
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                rows.append(
                    [
                        match["match_number"],
                        match.get("white_team_name", ""),
                        white_match_points,
                        match_result,
                        black_match_points,
                        match.get("black_team_name", ""),
                        board["board_number"],
                        self._team_board_player_name(board, "white"),
                        board.get("result", ""),
                        self._team_board_player_name(board, "black"),
                    ]
                )
        return (
            f"Rodada {round_data['number']}",
            [
                "Confronto",
                "Equipe A",
                "MP A",
                "Placar",
                "MP B",
                "Equipe B",
                "Tabuleiro",
                "Brancas",
                "Resultado",
                "Pretas",
            ],
            rows,
        )

    def _standings_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        tournament = self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            return self._team_standings_section(tournament_id)
        standings = self.pairing_service.standings(tournament_id)
        rows = [
            [
                item["position"],
                item["name"],
                item.get("category", ""),
                item.get("age_category", ""),
                item.get("rating_category", ""),
                item.get("prize_tags", ""),
                item["points"],
                item["buchholz"],
                item["buchholz_median"],
                item["sonneborn_berger"],
                item["wins"],
                item["performance"],
                item["rating"],
                item["club"],
            ]
            for item in standings
        ]
        return (
            "Classificacao",
            [
                "Pos",
                "Nome",
                "Categoria",
                "Categoria idade",
                "Categoria rating",
                "Tags premiacao",
                "Pts",
                "Buchholz",
                "Buchholz M",
                "SB",
                "Vitorias",
                "Performance",
                "Rating",
                "Clube",
            ],
            rows,
        )

    def _team_standings_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        standings = self.pairing_service.team_standings(tournament_id)
        rows = [
            [
                item["position"],
                item["name"],
                item.get("club", ""),
                item.get("captain", ""),
                self._format_report_number(item["match_points"]),
                self._format_report_number(item["game_points"]),
                item["wins"],
                item["draws"],
                item["losses"],
                item["byes"],
                item["matches"],
                self._format_report_number(item["buchholz"]),
                "Ativa" if item.get("active") else "Inativa",
            ]
            for item in standings
        ]
        return (
            "Classificacao por equipes",
            [
                "Pos",
                "Equipe",
                "Clube/Cidade",
                "Capitao",
                "Match points",
                "Game points",
                "Vitorias",
                "Empates",
                "Derrotas",
                "Byes",
                "Confrontos",
                "Buchholz",
                "Status",
            ],
            rows,
        )

    def _standings_for_tournament(
        self,
        tournament_id: int,
        tournament: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        tournament = tournament or self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            return self.pairing_service.team_standings(tournament_id)
        return self.pairing_service.standings(tournament_id)

    @staticmethod
    def _team_assignment_player_name(assignment: Mapping[str, Any]) -> str:
        return player_full_name(
            {
                "name": assignment.get("player_name"),
                "surname": assignment.get("player_surname"),
                "given_name": assignment.get("player_given_name"),
            }
        )

    @staticmethod
    def _team_board_player_name(board: Mapping[str, Any], color: str) -> str:
        return player_pairing_name(
            {
                "name": board.get(f"{color}_player_name"),
                "surname": board.get(f"{color}_player_surname"),
                "given_name": board.get(f"{color}_player_given_name"),
            }
        )

    @staticmethod
    def _team_match_score(match: Mapping[str, Any]) -> str:
        if match.get("is_bye"):
            return "BYE"
        if not match.get("result"):
            return ""
        return (
            f"{ExportService._format_report_number(match.get('white_game_points', 0))} x "
            f"{ExportService._format_report_number(match.get('black_game_points', 0))}"
        )

    @staticmethod
    def _team_match_points_label(match: Mapping[str, Any], color: str) -> str:
        if not match.get("result"):
            return ""
        return ExportService._format_report_number(match.get(f"{color}_match_points", 0))

    @staticmethod
    def _format_report_number(value: Any) -> str:
        try:
            numeric = float(value or 0)
        except (TypeError, ValueError):
            return str(value or "")
        if numeric.is_integer():
            return str(int(numeric))
        return f"{numeric:.2f}".rstrip("0").rstrip(".")

    def _write_report(
        self,
        file_path: str | Path,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
    ) -> None:
        path = Path(file_path)
        extension = path.suffix.lower()
        if extension == ".csv":
            self._write_csv(path, headers, rows)
            logger.info("Relatorio exportado em CSV: %s", path)
            return
        if extension == ".xlsx":
            self._write_xlsx(path, title, headers, rows)
            logger.info("Relatorio exportado em XLSX: %s", path)
            return
        if extension == ".pdf":
            self._write_pdf(path, title, headers, rows)
            logger.info("Relatorio exportado em PDF: %s", path)
            return
        raise AppError("Formato nao suportado. Use .csv, .xlsx ou .pdf.")

    def _write_multi_report(
        self,
        file_path: str | Path,
        sections: list[tuple[str, list[str], list[list[Any]]]],
    ) -> None:
        path = Path(file_path)
        extension = path.suffix.lower()
        if extension == ".csv":
            self._write_multi_csv(path, sections)
            logger.info("Relatorio composto exportado em CSV: %s", path)
            return
        if extension == ".xlsx":
            self._write_multi_xlsx(path, sections)
            logger.info("Relatorio composto exportado em XLSX: %s", path)
            return
        if extension == ".pdf":
            self._write_multi_pdf(path, sections)
            logger.info("Relatorio composto exportado em PDF: %s", path)
            return
        raise AppError("Formato nao suportado. Use .csv, .xlsx ou .pdf.")

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)

    @staticmethod
    def _write_multi_csv(
        path: Path,
        sections: list[tuple[str, list[str], list[list[Any]]]],
    ) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            for index, (title, headers, rows) in enumerate(sections):
                if index:
                    writer.writerow([])
                writer.writerow([title])
                writer.writerow(headers)
                writer.writerows(rows)

    @staticmethod
    def _write_xlsx(path: Path, title: str, headers: list[str], rows: list[list[Any]]) -> None:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError as exc:
            raise AppError("Instale openpyxl para exportar Excel.") from exc

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = title[:31]
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append(row)
        for column_cells in sheet.columns:
            length = max(len(str(cell.value or "")) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 10), 40)
        workbook.save(path)

    @staticmethod
    def _write_multi_xlsx(
        path: Path,
        sections: list[tuple[str, list[str], list[list[Any]]]],
    ) -> None:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError as exc:
            raise AppError("Instale openpyxl para exportar Excel.") from exc

        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        used_names: set[str] = set()

        for title, headers, rows in sections:
            sheet_name = ExportService._unique_sheet_name(title, used_names)
            sheet = workbook.create_sheet(sheet_name)
            sheet.append(headers)
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            for row in rows:
                sheet.append(row)
            for column_cells in sheet.columns:
                length = max(len(str(cell.value or "")) for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 10), 42)

        workbook.save(path)

    @staticmethod
    def _unique_sheet_name(title: str, used_names: set[str]) -> str:
        invalid = set("[]:*?/\\")
        base = "".join("_" if character in invalid else character for character in title).strip()
        base = (base or "Relatorio")[:31]
        name = base
        counter = 2
        while name in used_names:
            suffix = f" {counter}"
            name = f"{base[:31 - len(suffix)]}{suffix}"
            counter += 1
        used_names.add(name)
        return name

    @staticmethod
    def _write_pdf(path: Path, title: str, headers: list[str], rows: list[list[Any]]) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise AppError("Instale reportlab para exportar PDF.") from exc

        document = SimpleDocTemplate(str(path), pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        data = [headers] + [[str(value) for value in row] for row in rows]
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        document.build([Paragraph(title, styles["Title"]), Spacer(1, 12), table])

    @staticmethod
    def _write_multi_pdf(
        path: Path,
        sections: list[tuple[str, list[str], list[list[Any]]]],
    ) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise AppError("Instale reportlab para exportar PDF.") from exc

        document = SimpleDocTemplate(str(path), pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        story = []
        for index, (title, headers, rows) in enumerate(sections):
            if index:
                story.append(PageBreak())
            story.append(Paragraph(title, styles["Title"]))
            story.append(Spacer(1, 12))
            data = [headers] + [[str(value) for value in row] for row in rows]
            table = Table(data, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(table)
        document.build(story)
