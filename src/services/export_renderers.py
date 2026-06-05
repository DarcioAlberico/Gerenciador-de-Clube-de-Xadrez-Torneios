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

from src.services.export_writers import ReportWritersMixin

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


class ReportRenderersMixin:
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
            result_url = ""
            if not pairing["is_bye"] and round_data.get("status") != "closed":
                result_url = self._qr_result_url(int(round_data["tournament_id"]), int(pairing["id"]))
            rows.append(
                [
                    pairing["board_number"],
                    pairing_player_name(pairing, "white"),
                    pairing["white_rating"],
                    pairing["result"],
                    "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black"),
                    "" if pairing["is_bye"] else pairing["black_rating"],
                    result_url,
                ]
            )
        return (
            f"Rodada {round_data['number']}",
            ["Mesa", "Brancas", "Rating", "Resultado", "Pretas", "Rating", "Link resultado QR"],
            rows,
        )

    def _scoresheet_rows(
        self,
        round_data: dict[str, Any],
        tournament: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if tournament.get("competition_type") != "team":
            return [
                {
                    "board_label": str(pairing["board_number"]),
                    "context": "",
                    "white_name": pairing_player_name(pairing, "white"),
                    "white_rating": pairing.get("white_rating", ""),
                    "white_club": pairing.get("white_club", ""),
                    "white_ids": self._official_ids_label(pairing, "white"),
                    "black_name": pairing_player_name(pairing, "black"),
                    "black_rating": pairing.get("black_rating", ""),
                    "black_club": pairing.get("black_club", ""),
                    "black_ids": self._official_ids_label(pairing, "black"),
                }
                for pairing in self.db.get_pairings_for_round(int(round_data["id"]))
                if not pairing.get("is_bye")
            ]

        scoresheets: list[dict[str, Any]] = []
        for match in self.db.list_team_matches_for_round(int(round_data["id"])):
            if match.get("is_bye"):
                continue
            for board in self.db.list_team_boards(int(match["id"])):
                scoresheets.append(
                    {
                        "board_label": f"{match['match_number']}.{board['board_number']}",
                        "context": f"{match.get('white_team_name', '')} x {match.get('black_team_name', '')}",
                        "white_name": self._team_board_player_name(board, "white"),
                        "white_rating": board.get("white_player_rating", ""),
                        "white_club": board.get("white_player_club", ""),
                        "white_ids": self._team_board_official_ids_label(board, "white"),
                        "black_name": self._team_board_player_name(board, "black"),
                        "black_rating": board.get("black_player_rating", ""),
                        "black_club": board.get("black_player_club", ""),
                        "black_ids": self._team_board_official_ids_label(board, "black"),
                    }
                )
        return scoresheets

    @staticmethod
    def _official_ids_label(player: Mapping[str, Any], color: str) -> str:
        values = [
            ("FIDE", player.get(f"{color}_fide_id")),
            ("CBX", player.get(f"{color}_cbx_id")),
            ("LBX", player.get(f"{color}_lbx_id")),
        ]
        return " | ".join(f"{label}: {value}" for label, value in values if value)

    @staticmethod
    def _team_board_official_ids_label(board: Mapping[str, Any], color: str) -> str:
        values = [
            ("FIDE", board.get(f"{color}_player_fide_id")),
            ("CBX", board.get(f"{color}_player_cbx_id")),
            ("LBX", board.get(f"{color}_player_lbx_id")),
        ]
        return " | ".join(f"{label}: {value}" for label, value in values if value)

    @staticmethod
    def _write_scoresheets_pdf(
        path: Path,
        tournament: Mapping[str, Any],
        round_data: Mapping[str, Any],
        scoresheets: list[dict[str, Any]],
    ) -> None:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfbase.pdfmetrics import stringWidth
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise AppError("Instale reportlab para exportar PDF.") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        page_width, page_height = A4
        document = canvas.Canvas(str(path), pagesize=A4)
        document.setTitle(f"Sumulas - {tournament.get('name', '')} - Rodada {round_data.get('number', '')}")

        def fitted_text(text: Any, max_width: float, font_name: str = "Helvetica", font_size: int = 9) -> str:
            value = str(text or "")
            if stringWidth(value, font_name, font_size) <= max_width:
                return value
            while value and stringWidth(f"{value}...", font_name, font_size) > max_width:
                value = value[:-1]
            return f"{value}..."

        margin = 14 * mm
        content_width = page_width - 2 * margin
        row_height = 6.2 * mm
        grid_top = page_height - 83 * mm
        column_widths = [9 * mm, 41 * mm, 41 * mm] * 2

        for scoresheet in scoresheets:
            document.setFont("Helvetica-Bold", 14)
            document.drawString(margin, page_height - 17 * mm, fitted_text(tournament.get("name", ""), content_width, "Helvetica-Bold", 14))
            document.setFont("Helvetica", 9)
            document.drawString(margin, page_height - 23 * mm, f"Rodada: {round_data.get('number', '')}")
            document.drawRightString(page_width - margin, page_height - 23 * mm, f"Mesa: {scoresheet['board_label']}")
            if scoresheet.get("context"):
                document.drawString(margin, page_height - 28 * mm, fitted_text(scoresheet["context"], content_width, font_size=9))

            player_top = page_height - 37 * mm
            for color_label, prefix in (("Brancas", "white"), ("Pretas", "black")):
                document.setFont("Helvetica-Bold", 10)
                document.drawString(margin, player_top, f"{color_label}: {fitted_text(scoresheet[f'{prefix}_name'], 116 * mm, 'Helvetica-Bold', 10)}")
                document.setFont("Helvetica", 8)
                details = f"Rating: {scoresheet[f'{prefix}_rating'] or '-'}   Clube: {scoresheet[f'{prefix}_club'] or '-'}"
                document.drawString(margin + 18 * mm, player_top - 4 * mm, fitted_text(details, content_width - 18 * mm, font_size=8))
                document.drawString(margin + 18 * mm, player_top - 8 * mm, fitted_text(scoresheet[f"{prefix}_ids"], content_width - 18 * mm, font_size=8))
                player_top -= 14 * mm

            headers = ["N.", "Brancas", "Pretas", "N.", "Brancas", "Pretas"]
            x_positions = [margin]
            for width in column_widths:
                x_positions.append(x_positions[-1] + width)
            document.setFillGray(0.92)
            document.rect(margin, grid_top, content_width, row_height, fill=1, stroke=0)
            document.setFillGray(0)
            document.setFont("Helvetica-Bold", 8)
            for index, header in enumerate(headers):
                document.drawCentredString((x_positions[index] + x_positions[index + 1]) / 2, grid_top + 2.1 * mm, header)

            document.setLineWidth(0.35)
            for row in range(31):
                y = grid_top - row * row_height
                document.line(margin, y, margin + content_width, y)
            for x in x_positions:
                document.line(x, grid_top + row_height, x, grid_top - 30 * row_height)
            document.setFont("Helvetica", 8)
            for row in range(30):
                y = grid_top - (row + 1) * row_height + 2.1 * mm
                document.drawCentredString((x_positions[0] + x_positions[1]) / 2, y, str(row + 1))
                document.drawCentredString((x_positions[3] + x_positions[4]) / 2, y, str(row + 31))

            footer_y = grid_top - 30 * row_height - 8 * mm
            document.setFont("Helvetica-Bold", 9)
            document.drawString(margin, footer_y, "Resultado:  1-0  [  ]    1/2-1/2  [  ]    0-1  [  ]")
            document.setFont("Helvetica", 8)
            document.line(margin, footer_y - 12 * mm, margin + 76 * mm, footer_y - 12 * mm)
            document.line(page_width - margin - 76 * mm, footer_y - 12 * mm, page_width - margin, footer_y - 12 * mm)
            document.drawCentredString(margin + 38 * mm, footer_y - 16 * mm, "Assinatura das brancas")
            document.drawCentredString(page_width - margin - 38 * mm, footer_y - 16 * mm, "Assinatura das pretas")
            document.showPage()

        document.save()

    @staticmethod
    def _write_initial_player_list_pdf(
        path: Path,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
    ) -> None:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfbase.pdfmetrics import stringWidth
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise AppError("Instale reportlab para exportar PDF.") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        page_width, page_height = A4
        document = canvas.Canvas(str(path), pagesize=A4)
        document.setTitle(title)
        margin = 11 * mm
        content_width = page_width - 2 * margin
        column_widths = [14 * mm, 52 * mm, 16 * mm, 28 * mm, 19 * mm, 18 * mm, 41 * mm]
        row_height = 6.2 * mm
        table_top = page_height - 39 * mm
        rows_per_page = 38
        pdf_headers = [*headers[:-1], "Assinatura"]
        total_pages = max(1, math.ceil(len(rows) / rows_per_page))

        def fitted_text(text: Any, max_width: float, font_name: str = "Helvetica", font_size: int = 7) -> str:
            value = str(text or "")
            if stringWidth(value, font_name, font_size) <= max_width:
                return value
            while value and stringWidth(f"{value}...", font_name, font_size) > max_width:
                value = value[:-1]
            return f"{value}..."

        for page_index in range(total_pages):
            document.setFont("Helvetica-Bold", 13)
            document.drawString(margin, page_height - 15 * mm, fitted_text(title, content_width, "Helvetica-Bold", 13))
            document.setFont("Helvetica", 8)
            document.drawString(margin, page_height - 21 * mm, "Lista de chamada por ranking inicial")
            document.drawRightString(
                page_width - margin,
                page_height - 21 * mm,
                f"Pagina {page_index + 1}/{total_pages}",
            )
            document.drawString(margin, page_height - 27 * mm, f"Jogadores inscritos: {len(rows)}")

            x_positions = [margin]
            for width in column_widths:
                x_positions.append(x_positions[-1] + width)
            document.setFillGray(0.92)
            document.rect(margin, table_top, content_width, row_height, fill=1, stroke=0)
            document.setFillGray(0)
            document.setFont("Helvetica-Bold", 7)
            for index, header in enumerate(pdf_headers):
                document.drawCentredString(
                    (x_positions[index] + x_positions[index + 1]) / 2,
                    table_top + 2.1 * mm,
                    header,
                )

            page_rows = rows[page_index * rows_per_page : (page_index + 1) * rows_per_page]
            document.setLineWidth(0.35)
            for row_index, row in enumerate(page_rows, start=1):
                bottom = table_top - row_index * row_height
                document.line(margin, bottom, margin + content_width, bottom)
                document.setFont("Helvetica", 7)
                for column_index, value in enumerate(row[:-1]):
                    left = x_positions[column_index]
                    width = column_widths[column_index]
                    text = fitted_text(value, width - 2 * mm)
                    if column_index in {0, 2}:
                        document.drawCentredString(left + width / 2, bottom + 2.1 * mm, text)
                    else:
                        document.drawString(left + 1 * mm, bottom + 2.1 * mm, text)
            for x_position in x_positions:
                document.line(x_position, table_top + row_height, x_position, table_top - len(page_rows) * row_height)

            document.setFont("Helvetica", 7)
            document.drawRightString(page_width - margin, 8 * mm, "Albericus - Lista de chamada")
            document.showPage()

        document.save()

    def _write_pairings_wall_pdf(
        self,
        path: Path,
        tournament: Mapping[str, Any],
        round_data: Mapping[str, Any],
    ) -> None:
        try:
            import qrcode
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfbase.pdfmetrics import stringWidth
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise AppError("Instale reportlab e qrcode para exportar o mural em PDF.") from exc

        pairings = self.db.get_pairings_for_round(int(round_data["id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        page_width, page_height = A4
        document = canvas.Canvas(str(path), pagesize=A4)
        document.setTitle(f"Mural - {tournament.get('name', '')} - Rodada {round_data.get('number', '')}")
        margin = 10 * mm
        content_width = page_width - 2 * margin
        column_widths = [12 * mm, 58 * mm, 16 * mm, 58 * mm, 16 * mm, 30 * mm]
        row_height = 16 * mm
        header_height = 7 * mm
        table_top = page_height - 38 * mm
        rows_per_page = 15
        is_open = round_data.get("status") != "closed"
        total_pages = max(1, math.ceil(len(pairings) / rows_per_page))
        qr_urls = self._qr_result_urls(
            int(round_data["tournament_id"]),
            [
                {**pairing, "tournament_id": int(round_data["tournament_id"])}
                for pairing in pairings
                if is_open and not pairing["is_bye"]
            ],
        )

        def fitted_text(text: Any, max_width: float, font_name: str = "Helvetica", font_size: int = 9) -> str:
            value = str(text or "")
            if stringWidth(value, font_name, font_size) <= max_width:
                return value
            while value and stringWidth(f"{value}...", font_name, font_size) > max_width:
                value = value[:-1]
            return f"{value}..."

        for page_index in range(total_pages):
            document.setFont("Helvetica-Bold", 14)
            document.drawString(
                margin,
                page_height - 14 * mm,
                fitted_text(tournament.get("name", ""), content_width - 42 * mm, "Helvetica-Bold", 14),
            )
            document.setFont("Helvetica-Bold", 12)
            document.drawRightString(page_width - margin, page_height - 14 * mm, f"Rodada {round_data.get('number', '')}")
            document.setFont("Helvetica", 8)
            status_label = "Rodada aberta - QR para envio de resultado" if is_open else "Rodada fechada - QR desativado"
            document.drawString(margin, page_height - 21 * mm, status_label)
            document.drawRightString(
                page_width - margin,
                page_height - 21 * mm,
                f"Pagina {page_index + 1}/{total_pages}",
            )
            document.drawString(margin, page_height - 27 * mm, f"Mesas: {len(pairings)}")

            x_positions = [margin]
            for width in column_widths:
                x_positions.append(x_positions[-1] + width)
            document.setFillGray(0.92)
            document.rect(margin, table_top, content_width, header_height, fill=1, stroke=0)
            document.setFillGray(0)
            document.setFont("Helvetica-Bold", 8)
            for index, header in enumerate(["Mesa", "Brancas", "Rating", "Pretas", "Rating", "QR resultado"]):
                document.drawCentredString(
                    (x_positions[index] + x_positions[index + 1]) / 2,
                    table_top + 2.3 * mm,
                    header,
                )

            page_rows = pairings[page_index * rows_per_page : (page_index + 1) * rows_per_page]
            document.setLineWidth(0.35)
            for row_index, pairing in enumerate(page_rows, start=1):
                bottom = table_top - row_index * row_height
                middle = bottom + row_height / 2
                document.line(margin, bottom, margin + content_width, bottom)
                document.setFont("Helvetica-Bold", 11)
                document.drawCentredString(x_positions[0] + column_widths[0] / 2, middle - 1.5 * mm, str(pairing["board_number"]))
                document.setFont("Helvetica-Bold", 9)
                document.drawString(
                    x_positions[1] + 1.5 * mm,
                    middle - 1.5 * mm,
                    fitted_text(pairing_player_name(pairing, "white"), column_widths[1] - 3 * mm, "Helvetica-Bold", 9),
                )
                black_name = "BYE" if pairing["is_bye"] else pairing_player_name(pairing, "black")
                document.drawString(
                    x_positions[3] + 1.5 * mm,
                    middle - 1.5 * mm,
                    fitted_text(black_name, column_widths[3] - 3 * mm, "Helvetica-Bold", 9),
                )
                document.setFont("Helvetica", 9)
                document.drawCentredString(x_positions[2] + column_widths[2] / 2, middle - 1.5 * mm, str(pairing["white_rating"]))
                black_rating = "" if pairing["is_bye"] else pairing["black_rating"]
                document.drawCentredString(x_positions[4] + column_widths[4] / 2, middle - 1.5 * mm, str(black_rating))
                if is_open and not pairing["is_bye"]:
                    url = qr_urls[int(pairing["id"])]
                    qr_code = qrcode.QRCode(
                        error_correction=qrcode.constants.ERROR_CORRECT_M,
                        box_size=2,
                        border=1,
                    )
                    qr_code.add_data(url)
                    qr_code.make(fit=True)
                    image = qr_code.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    buffer.seek(0)
                    qr_size = 13 * mm
                    document.drawImage(
                        ImageReader(buffer),
                        x_positions[5] + (column_widths[5] - qr_size) / 2,
                        bottom + (row_height - qr_size) / 2,
                        width=qr_size,
                        height=qr_size,
                    )
            for x_position in x_positions:
                document.line(x_position, table_top + header_height, x_position, table_top - len(page_rows) * row_height)

            document.setFont("Helvetica", 7)
            document.drawRightString(page_width - margin, 7 * mm, "Albericus - Emparceiramento para mural")
            document.showPage()

        document.save()

    def _write_table_cards_pdf(
        self,
        path: Path,
        start_board: int,
        end_board: int,
        tournament: Mapping[str, Any] | None,
        round_data: Mapping[str, Any] | None,
        include_qr: bool,
    ) -> None:
        try:
            import qrcode
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise AppError("Instale reportlab e qrcode para exportar cartoes de mesa.") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        pairings_by_board = {
            int(pairing["board_number"]): pairing
            for pairing in self.db.get_pairings_for_round(int(round_data["id"]))
        } if round_data else {}
        document = canvas.Canvas(str(path), pagesize=A4)
        document.setTitle("Cartoes de mesa")
        page_width, page_height = A4
        margin = 10 * mm
        gap = 6 * mm
        card_width = (page_width - 2 * margin - gap) / 2
        card_height = (page_height - 2 * margin - gap) / 2
        cards_per_page = 4
        boards = list(range(start_board, end_board + 1))
        is_open = bool(round_data and round_data.get("status") != "closed")
        qr_urls = self._qr_result_urls(
            int(round_data["tournament_id"]),
            [
                {**pairing, "tournament_id": int(round_data["tournament_id"])}
                for pairing in pairings_by_board.values()
                if include_qr and is_open and not pairing.get("is_bye")
            ],
        ) if round_data else {}

        for card_index, board_number in enumerate(boards):
            page_slot = card_index % cards_per_page
            if card_index and page_slot == 0:
                document.showPage()
            column = page_slot % 2
            row = page_slot // 2
            left = margin + column * (card_width + gap)
            bottom = page_height - margin - card_height - row * (card_height + gap)
            center_x = left + card_width / 2

            document.setLineWidth(1.2)
            document.roundRect(left, bottom, card_width, card_height, 4 * mm, stroke=1, fill=0)
            document.setFont("Helvetica-Bold", 14)
            document.drawCentredString(center_x, bottom + card_height - 17 * mm, "MESA")
            document.setFont("Helvetica-Bold", 68)
            document.drawCentredString(center_x, bottom + card_height - 53 * mm, str(board_number))

            details_y = bottom + 19 * mm
            if tournament:
                document.setFont("Helvetica-Bold", 8)
                document.drawCentredString(center_x, details_y, str(tournament.get("name") or "")[:48])
                details_y -= 5 * mm
            if round_data:
                document.setFont("Helvetica", 9)
                document.drawCentredString(center_x, details_y, f"Rodada {round_data.get('number', '')}")

            pairing = pairings_by_board.get(board_number)
            if include_qr and is_open and pairing and not pairing.get("is_bye"):
                url = qr_urls[int(pairing["id"])]
                qr_code = qrcode.QRCode(
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=3,
                    border=1,
                )
                qr_code.add_data(url)
                qr_code.make(fit=True)
                image = qr_code.make_image(fill_color="black", back_color="white")
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                buffer.seek(0)
                qr_size = 27 * mm
                document.drawImage(
                    ImageReader(buffer),
                    center_x - qr_size / 2,
                    bottom + 31 * mm,
                    width=qr_size,
                    height=qr_size,
                )
                document.setFont("Helvetica", 7)
                document.drawCentredString(center_x, bottom + 27 * mm, "QR para enviar resultado")
            elif include_qr:
                document.setFont("Helvetica", 7)
                document.drawCentredString(center_x, bottom + 30 * mm, "QR indisponivel para esta mesa")

        if boards:
            document.showPage()
        document.save()

    def _qr_result_url(self, tournament_id: int, pairing_id: int) -> str:
        from src.services.qr_result_service import QRResultService

        settings = self.db.get_app_settings()
        base_url = str(settings.get("local_result_server_url") or "http://localhost:8765")
        return str(QRResultService(self.db, self.pairing_service).result_url_for_pairing(tournament_id, pairing_id, base_url)["url"])

    def _qr_result_urls(self, tournament_id: int, pairings: list[dict[str, Any]]) -> dict[int, str]:
        if not pairings:
            return {}
        from src.services.qr_result_service import QRResultService

        settings = self.db.get_app_settings()
        base_url = str(settings.get("local_result_server_url") or "http://localhost:8765")
        return QRResultService(self.db, self.pairing_service).result_urls_for_pairings(tournament_id, pairings, base_url)

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
        columns = resolve_columns(
            self.db.get_report_layout_columns(tournament_id, "standings"), "standings"
        )
        headers = [STANDINGS_COLUMNS[key] for key in columns]
        rows = [[item.get(key, "") for key in columns] for item in standings]
        return ("Classificacao", headers, rows)

    def _crosstable_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        payload = self.pairing_service.crosstable(tournament_id)
        rounds = list(payload["rounds"])
        if payload.get("competition_type") == "team":
            headers = ["Pos", "Equipe", *[f"R{number}" for number in rounds], "MP", "GP", "Buchholz", "Clube/Cidade"]
            rows = [
                [
                    item["position"],
                    item["name"],
                    *[item["rounds"][number]["label"] for number in rounds],
                    self._format_report_number(item["match_points"]),
                    self._format_report_number(item["game_points"]),
                    self._format_report_number(item["buchholz"]),
                    item.get("club", ""),
                ]
                for item in payload["rows"]
            ]
            return f"Tabela cruzada por equipes - {payload['tournament_name']}", headers, rows
        headers = ["Pos", "Jogador", "Rating", *[f"R{number}" for number in rounds], "Pts", "Buchholz", "SB", "Clube"]
        rows = [
            [
                item["position"],
                item["name"],
                item["rating"],
                *[item["rounds"][number]["label"] for number in rounds],
                self._format_report_number(item["points"]),
                self._format_report_number(item["buchholz"]),
                self._format_report_number(item["sonneborn_berger"]),
                item.get("club", ""),
            ]
            for item in payload["rows"]
        ]
        return f"Tabela cruzada - {payload['tournament_name']}", headers, rows

    @staticmethod
    def _crosstable_html(title: str, headers: list[str], rows: list[list[Any]]) -> str:
        header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str('' if value is None else value))}</td>" for value in row) + "</tr>"
            for row in rows
        )
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    h1 {{ font-size: 22px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #9ca3af; padding: 5px 7px; text-align: center; }}
    th {{ background: #e5e7eb; }}
    td:nth-child(2), td:last-child {{ text-align: left; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>Celulas: posicao do adversario, lado (B = brancas; P = pretas), resultado e pontuacao.</p>
  <table>
    <thead><tr>{header_html}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>
"""

    @staticmethod
    def _tiebreak_component_summary(component: dict[str, Any]) -> str:
        if "opponents" in component:
            return " | ".join(
                "{name}: {value}".format(
                    name=item.get("opponent_name", ""),
                    value=item.get("contribution", item.get("points", "")),
                )
                for item in component.get("opponents", [])
            )
        if "used_scores" in component:
            cuts = []
            if component.get("cut_low") is not None:
                cuts.append(f"corte menor {component['cut_low']}")
            if component.get("cut_high") is not None:
                cuts.append(f"corte maior {component['cut_high']}")
            return f"usados: {component.get('used_scores', [])}; {'; '.join(cuts)}"
        if "games" in component:
            return " | ".join(
                "{name}: {earned}".format(
                    name=item.get("opponent_name", ""),
                    earned=item.get("earned", ""),
                )
                for item in component.get("games", [])
            )
        return json.dumps(component, ensure_ascii=False, sort_keys=True)

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

    def _team_lineups_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        rows = []
        for lineup in self.db.list_team_lineups(tournament_id):
            for board in self.db.list_team_lineup_boards(int(lineup["id"])):
                rows.append(
                    [
                        lineup.get("round_number", ""),
                        lineup.get("match_number", ""),
                        lineup.get("team_name", ""),
                        board.get("board_number", ""),
                        board.get("color", ""),
                        player_full_name(
                            {
                                "name": board.get("player_name", ""),
                                "surname": board.get("player_surname", ""),
                                "given_name": board.get("player_given_name", ""),
                            }
                        ),
                        board.get("player_rating", ""),
                        board.get("role", ""),
                        lineup.get("status", ""),
                    ]
                )
        return (
            "Escalacoes por equipes",
            ["Rodada", "Match", "Equipe", "Tabuleiro", "Cor", "Jogador", "Rating", "Funcao", "Status"],
            rows,
        )

    def _team_substitutions_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        rows = [
            [
                item.get("created_at", ""),
                item.get("round_number", ""),
                item.get("match_number", ""),
                item.get("team_name", ""),
                item.get("board_number", ""),
                item.get("color", ""),
                item.get("out_player_name", ""),
                item.get("in_player_name", ""),
                "Sim" if item.get("requires_correction") else "Nao",
                item.get("reason", ""),
            ]
            for item in self.db.list_team_substitution_events(tournament_id)
        ]
        return (
            "Substituicoes por equipes",
            [
                "Data/hora",
                "Rodada",
                "Match",
                "Equipe",
                "Tabuleiro",
                "Cor",
                "Saiu",
                "Entrou",
                "Correcao formal",
                "Motivo",
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
            f"{ReportWritersMixin._format_report_number(match.get('white_game_points', 0))} x "
            f"{ReportWritersMixin._format_report_number(match.get('black_game_points', 0))}"
        )

    @staticmethod
    def _team_match_points_label(match: Mapping[str, Any], color: str) -> str:
        if not match.get("result"):
            return ""
        return ReportWritersMixin._format_report_number(match.get(f"{color}_match_points", 0))
