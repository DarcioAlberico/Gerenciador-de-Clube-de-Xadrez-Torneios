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
from src.services.import_service import REGISTRATION_FORM_QUESTIONS

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


class PlayerRoundReportsMixin:
    def export_players(self, tournament_id: int, file_path: str | Path) -> None:
        title, headers, rows = self._players_section(tournament_id)
        self._write_report(file_path, title, headers, rows)

    def export_player_import_template(self, file_path: str | Path) -> None:
        self._write_report(
            file_path,
            "Modelo de importação de jogadores",
            [
                "nome",
                "sobrenome",
                "rating",
                "clube",
                "categoria",
                "fide_id",
                "cbx_id",
                "lbx_id",
                "nascimento",
                "sexo",
            ],
            [["Ana", "Silva", "1500", "Clube A", "ABS", "", "", "", "2012-05-10", "F"]],
        )

    def export_online_registration_template(self, file_path: str | Path) -> None:
        self._write_report(
            file_path,
            "Modelo de inscrições online",
            [
                "Nome completo do jogador",
                "Rating",
                "Clube/Cidade",
                "Categoria",
                "Data de nascimento",
                "FIDE ID",
                "CBX ID",
                "LBX ID",
                "Sexo",
            ],
            [["Ana Silva", "1500", "Clube A", "ABS", "2012-05-10", "", "", "", "F"]],
        )

    def export_registration_form(
        self, file_path: str | Path, tournament_id: int | None = None
    ) -> dict[str, str]:
        """Gera o formulário de inscrição padronizado (REG-01).

        Produz dois artefatos com o mesmo nome base:
        - ``.gs``: script Google Apps Script colavel em script.google.com que
          cria o formulário com as perguntas padronizadas;
        - ``.json``: definicao reutilizavel dos campos.

        Os titulos das perguntas sao escolhidos para que o CSV de respostas
        importe direto pelo fluxo de inscrições online, sem mapeamento manual.
        """
        title = "Inscrição no torneio"
        if tournament_id is not None:
            tournament = self.db.get_tournament(int(tournament_id))
            if tournament and tournament.get("name"):
                title = f"Inscrição - {tournament['name']}"

        path = Path(file_path)
        if path.suffix.lower() not in {".gs", ".js"}:
            path = path.with_suffix(".gs")
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(self._registration_form_script(title), encoding="utf-8")
        definition_path = path.with_suffix(".json")
        definition_path.write_text(
            json.dumps(
                {"title": title, "questions": REGISTRATION_FORM_QUESTIONS},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("Formulário de inscrição padronizado gerado em %s e %s", path, definition_path)
        return {"script_path": str(path), "definition_path": str(definition_path)}

    @staticmethod
    def _registration_form_script(title: str) -> str:
        def js_text(value: str) -> str:
            return value.replace("\\", "\\\\").replace("'", "\\'")

        lines: list[str] = [
            "/**",
            " * Albericus - Formulário de inscrição padronizado (REG-01).",
            " *",
            " * Passo a passo:",
            " *  1. Acesse https://script.google.com e crie um novo projeto.",
            " *  2. Cole todo este código e salve.",
            " *  3. Execute a função criarFormularioInscricao e autorize o acesso.",
            " *  4. O link do formulário aparece no registro de execução (Ver > Registros).",
            " *  5. No formulário, vincule as respostas a uma planilha.",
            " *  6. Baixe a planilha como CSV (ou publique como CSV) e importe em",
            " *     Jogadores > Importar inscrições online / Importar link Forms/Sheets.",
            " *",
            " * Os titulos das perguntas ja seguem o padrão do importador; não os",
            " * renomeie para manter a importação automatica sem mapeamento.",
            " */",
            "function criarFormularioInscricao() {",
            f"  var form = FormApp.create('{js_text(title)}');",
            "  form.setDescription('Inscrição gerada pelo Albericus. Preencha os dados do jogador.');",
            "  form.setCollectEmail(false);",
            "",
        ]
        for index, question in enumerate(REGISTRATION_FORM_QUESTIONS):
            title_js = js_text(str(question["title"]))
            required = "true" if question.get("required") else "false"
            qtype = question.get("type")
            if qtype == "date":
                lines.append(
                    f"  form.addDateItem().setTitle('{title_js}').setRequired({required});"
                )
            elif qtype == "choice":
                choices = ", ".join(f"'{js_text(str(choice))}'" for choice in question.get("choices", []))
                lines.append(
                    f"  form.addMultipleChoiceItem().setTitle('{title_js}')"
                    f".setChoiceValues([{choices}]).setRequired({required});"
                )
            elif qtype == "integer":
                var = f"q{index}"
                lines.append(
                    f"  var {var} = form.addTextItem().setTitle('{title_js}').setRequired({required});"
                )
                lines.append(
                    f"  {var}.setValidation(FormApp.createTextValidation()"
                    ".setHelpText('Informe um número.').requireNumber().build());"
                )
            else:
                lines.append(
                    f"  form.addTextItem().setTitle('{title_js}').setRequired({required});"
                )
        lines.append("")
        lines.append("  Logger.log('Formulário criado: ' + form.getPublishedUrl());")
        lines.append("  Logger.log('Edição: ' + form.getEditUrl());")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    # --- REG-01: link pre-preenchido do Google Forms ----------------------

    @staticmethod
    def parse_prefill_link(link: str) -> dict[str, Any]:
        """Extrai a URL base e os campos ``entry.*`` de um link pre-preenchido
        do Google Forms (obtido em 'Receber link preenchido automaticamente')."""
        text = (link or "").strip()
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or "docs.google.com" not in parsed.netloc:
            raise AppError("Cole um link válido do Google Forms (pre-preenchido).")
        base_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        query = parse_qs(parsed.query, keep_blank_values=True)
        entries = [
            (key, values[0] if values else "")
            for key, values in query.items()
            if key.startswith("entry.")
        ]
        if not entries:
            raise AppError(
                "Nenhum campo encontrado no link. Use 'Receber link preenchido "
                "automaticamente', preencha o campo do torneio e cole o link gerado."
            )
        return {"base_url": base_url, "entries": entries}

    @staticmethod
    def build_registration_prefill_url(
        base_url: str, tournament_entry: str, tournament_name: str
    ) -> str:
        """Monta o link de inscrição com o nome do torneio ja preenchido e os
        campos do jogador em branco."""
        base = (base_url or "").strip()
        if not base:
            raise AppError("Formulário de inscrição não configurado.")
        params = {"usp": "pp_url"}
        entry = (tournament_entry or "").strip()
        name = (tournament_name or "").strip()
        if entry and name:
            params[entry] = name
        separator = "&" if urlparse(base).query else "?"
        return base + separator + urlencode(params)

    def registration_form_config(self) -> dict[str, str]:
        settings = self.db.get_app_settings()
        return {
            "base_url": str(settings.get("registration_form_prefill_base") or ""),
            "tournament_entry": str(settings.get("registration_form_tournament_entry") or ""),
        }

    def save_registration_form_config(self, prefill_link: str, tournament_entry: str) -> dict[str, str]:
        parsed = self.parse_prefill_link(prefill_link)
        entry = (tournament_entry or "").strip()
        self.db.save_app_settings(
            {
                "registration_form_prefill_base": parsed["base_url"],
                "registration_form_tournament_entry": entry,
            }
        )
        return {"base_url": parsed["base_url"], "tournament_entry": entry}

    def registration_prefill_url(self, tournament_id: int) -> str:
        config = self.registration_form_config()
        if not config["base_url"]:
            raise AppError(
                "Formulário de inscrição não configurado. Use 'Configurar formulário "
                "(link)' e cole o link pre-preenchido do Google Forms."
            )
        tournament = self.db.get_tournament(int(tournament_id))
        name = str(tournament.get("name") or "") if tournament else ""
        return self.build_registration_prefill_url(
            config["base_url"], config["tournament_entry"], name
        )

    def export_member_import_template(self, file_path: str | Path) -> None:
        self._write_report(
            file_path,
            "Modelo de importação de membros",
            [
                "nome",
                "sobrenome",
                "rating",
                "escola",
                "turma",
                "tipo",
                "status",
                "nascimento",
                "email",
                "telefone",
                "responsavel",
                "telefone responsável",
            ],
            [["Ana", "Silva", "1500", "Escola A", "Turma 1", "aluno", "ativo", "2012-05-10", "", "", "", ""]],
        )

    def export_initial_player_list(self, tournament_id: int, file_path: str | Path) -> None:
        title, headers, rows = self._initial_player_list_section(tournament_id)
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            self._write_initial_player_list_pdf(path, title, headers, rows)
            logger.info("%s jogadores exportados na lista de chamada PDF: %s", len(rows), path)
            return
        self._write_report(file_path, title, headers, rows)

    def export_pairings(self, round_id: int, file_path: str | Path) -> None:
        path = Path(file_path)
        round_data = self.db.get_round(round_id)
        if not round_data:
            raise AppError("Rodada não encontrada.")
        tournament = self.db.get_tournament(int(round_data["tournament_id"]))
        if path.suffix.lower() == ".pdf" and tournament and tournament.get("competition_type") != "team":
            self._write_pairings_wall_pdf(path, tournament, round_data)
            logger.info("Folha de mural da rodada %s exportada em PDF: %s", round_data["number"], path)
            return
        title, headers, rows = self._pairings_section(round_id)
        self._write_report(file_path, title, headers, rows)

    def export_scoresheets(self, round_id: int, file_path: str | Path) -> None:
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise AppError("Súmulas de mesa devem ser exportadas em PDF.")
        round_data = self.db.get_round(round_id)
        if not round_data:
            raise AppError("Rodada não encontrada.")
        tournament = self.db.get_tournament(int(round_data["tournament_id"]))
        if not tournament:
            raise AppError("Torneio não encontrado.")
        scoresheets = self._scoresheet_rows(round_data, tournament)
        if not scoresheets:
            raise AppError("Não ha mesas validas para gerar súmulas.")
        self._write_scoresheets_pdf(path, tournament, round_data, scoresheets)
        logger.info("%s sumulas exportadas em PDF: %s", len(scoresheets), path)

    def export_table_cards(
        self,
        file_path: str | Path,
        start_board: int,
        end_board: int,
        round_id: int | None = None,
        include_qr: bool = False,
    ) -> None:
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise AppError("Cartões de mesa devem ser exportados em PDF.")
        if int(start_board) <= 0 or int(end_board) < int(start_board):
            raise AppError("Informe um intervalo válido de mesas.")
        if int(end_board) - int(start_board) + 1 > 500:
            raise AppError("Gere no máximo 500 cartões de mesa por arquivo.")
        round_data = self.db.get_round(int(round_id)) if round_id else None
        tournament = self.db.get_tournament(int(round_data["tournament_id"])) if round_data else None
        if include_qr and not round_data:
            raise AppError("Selecione uma rodada para incluir QR nos cartões.")
        if include_qr and tournament and tournament.get("competition_type") == "team":
            raise AppError("QR nos cartões esta disponível apenas para torneios individuais.")
        self._write_table_cards_pdf(path, int(start_board), int(end_board), tournament, round_data, include_qr)
        logger.info("%s cartoes de mesa exportados em PDF: %s", int(end_board) - int(start_board) + 1, path)

    def export_teams(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(
            file_path,
            [
                self._teams_section(tournament_id),
                self._team_rosters_section(tournament_id),
            ],
        )

    def export_team_lineups(self, tournament_id: int, file_path: str | Path) -> None:
        self._write_multi_report(
            file_path,
            [
                self._team_lineups_section(tournament_id),
                self._team_substitutions_section(tournament_id),
            ],
        )

    def export_all_rounds(self, tournament_id: int, file_path: str | Path) -> None:
        sections = []
        for round_data in sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"]):
            sections.append(self._pairings_section(round_data["id"]))
        if not sections:
            raise AppError("Não ha rodadas para exportar.")
        self._write_multi_report(file_path, sections)

    def export_standings(self, tournament_id: int, file_path: str | Path) -> None:
        title, headers, rows = self._standings_section(tournament_id)
        self._write_report(
            file_path, title, headers, rows, widths=self._standings_column_widths(tournament_id)
        )

    def _standings_column_widths(self, tournament_id: int) -> list[int] | None:
        tournament = self.db.get_tournament(tournament_id)
        if tournament and tournament.get("competition_type") == "team":
            return None
        specs = resolve_column_specs(
            self.db.get_report_layout_columns(tournament_id, "standings"), "standings"
        )
        widths = [int(spec.get("width") or 0) for spec in specs]
        return widths if any(width > 0 for width in widths) else None

    def export_crosstable(self, tournament_id: int, file_path: str | Path) -> None:
        path = Path(file_path)
        title, headers, rows = self._crosstable_section(tournament_id)
        if path.suffix.lower() == ".html":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._crosstable_html(title, headers, rows), encoding="utf-8")
            logger.info("Tabela cruzada exportada em HTML: %s", path)
            return
        self._write_report(path, title, headers, rows)
