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
        from src.services.export_service import ExportService  # lazy: evita ciclo com a fachada export_service

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
        from src.services.export_service import ExportService  # lazy: evita ciclo com a fachada export_service

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
