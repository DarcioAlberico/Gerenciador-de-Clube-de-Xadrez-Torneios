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


class WebExportMixin:
    def export_site(self, tournament_id: int, output_dir: str | Path) -> Path:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")

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

    def export_public_json(self, tournament_id: int, file_path: str | Path, mode: str = "publico") -> Path:
        payload = self.public_tournament_payload(tournament_id, mode=mode)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def public_tournament_payload(self, tournament_id: int, mode: str = "publico") -> dict[str, Any]:
        mode = self._portal_mode(mode)
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        app_settings = self.db.get_app_settings()
        is_team_tournament = tournament.get("competition_type") == "team"
        standings = [] if settings.get("hide_standings") else self._standings_for_tournament(tournament_id, tournament)
        rounds = sorted(self.db.list_rounds(tournament_id), key=lambda item: item["number"])
        latest_round = rounds[-1] if rounds else None
        players = self.db.list_players(tournament_id, active_only=False)
        payload = {
            "mode": mode,
            "generated_at": Database.now(),
            "notice": str(app_settings.get("live_portal_notice") or ""),
            "tournament": self._public_tournament_info(tournament, settings, mode),
            "current_round": self._public_round_payload(latest_round, is_team_tournament) if latest_round else None,
            "rounds": [self._public_round_payload(round_data, is_team_tournament) for round_data in rounds],
            "standings": self._public_standings_payload(standings, is_team_tournament, mode),
            "players": [self._public_player_card(player, mode) for player in players],
        }
        if is_team_tournament:
            payload["teams"] = [self._public_team_card(team, mode) for team in self.db.list_teams(tournament_id, active_only=False)]
        return payload

    @staticmethod
    def _portal_mode(mode: str) -> str:
        normalized = str(mode or "publico").strip().casefold()
        if normalized in {"privado", "private"}:
            return "privado"
        if normalized in {"clube", "club"}:
            return "clube"
        return "publico"

    def _public_tournament_info(
        self,
        tournament: dict[str, Any],
        settings: dict[str, Any],
        mode: str,
    ) -> dict[str, Any]:
        info = {
            "id": int(tournament["id"]),
            "name": tournament.get("name", ""),
            "location": tournament.get("location", ""),
            "start_date": tournament.get("start_date", ""),
            "end_date": tournament.get("end_date", ""),
            "rounds_count": int(tournament.get("rounds_count") or 0),
            "time_control": tournament.get("time_control", ""),
            "status": tournament.get("status", ""),
            "competition_type": tournament.get("competition_type", "individual"),
            "chief_arbiter": settings.get("chief_arbiter", ""),
            "organizer": settings.get("organizer", ""),
        }
        if mode == "privado":
            info["contact_email"] = settings.get("contact_email", "")
            info["comments"] = settings.get("comments", "")
        return info

    def _public_round_payload(self, round_data: dict[str, Any], is_team_tournament: bool) -> dict[str, Any]:
        if is_team_tournament:
            matches = []
            for match in self.db.list_team_matches_for_round(int(round_data["id"])):
                matches.append(
                    {
                        "match_number": int(match.get("match_number") or 0),
                        "white_team": match.get("white_team_name", ""),
                        "black_team": "BYE" if match.get("is_bye") else match.get("black_team_name", ""),
                        "result": self._team_match_score(match),
                        "boards": [
                            {
                                "board": int(board.get("board_number") or 0),
                                "white": self._team_board_player_name(board, "white"),
                                "black": self._team_board_player_name(board, "black"),
                                "result": board.get("result", ""),
                            }
                            for board in self.db.list_team_boards(int(match["id"]))
                        ],
                    }
                )
            return {"id": int(round_data["id"]), "number": int(round_data["number"]), "status": round_data["status"], "matches": matches}
        pairings = []
        for pairing in self.db.get_pairings_for_round(int(round_data["id"])):
            pairings.append(
                {
                    "board": int(pairing.get("board_number") or 0),
                    "white": pairing_player_name(pairing, "white"),
                    "black": "BYE" if pairing.get("is_bye") else pairing_player_name(pairing, "black"),
                    "result": pairing.get("result", ""),
                    "is_bye": bool(pairing.get("is_bye")),
                }
            )
        return {"id": int(round_data["id"]), "number": int(round_data["number"]), "status": round_data["status"], "pairings": pairings}

    @staticmethod
    def _public_standings_payload(
        standings: list[dict[str, Any]],
        is_team_tournament: bool,
        mode: str,
    ) -> list[dict[str, Any]]:
        if is_team_tournament:
            return [
                {
                    "position": item["position"],
                    "team": item["name"],
                    "club": item.get("club", ""),
                    "match_points": item.get("match_points", 0),
                    "game_points": item.get("game_points", 0),
                    "wins": item.get("wins", 0),
                    "draws": item.get("draws", 0),
                    "losses": item.get("losses", 0),
                    "buchholz": item.get("buchholz", 0),
                }
                for item in standings
            ]
        rows = []
        for item in standings:
            row = {
                "position": item["position"],
                "name": item["name"],
                "category": item.get("category", ""),
                "points": item.get("points", 0),
                "buchholz": item.get("buchholz", 0),
                "buchholz_median": item.get("buchholz_median", 0),
                "sonneborn_berger": item.get("sonneborn_berger", 0),
                "wins": item.get("wins", 0),
            }
            if mode in {"clube", "privado"}:
                row["rating"] = item.get("rating", 0)
                row["club"] = item.get("club", "")
            rows.append(row)
        return rows

    @staticmethod
    def _public_player_card(player: dict[str, Any], mode: str) -> dict[str, Any]:
        card = {
            "id": int(player.get("id") or 0),
            "name": player_full_name(player),
            "club": player.get("club", ""),
            "category": player.get("category", ""),
            "rating": int(player.get("rating") or 0),
            "status": player.get("player_status", "active"),
        }
        if mode in {"clube", "privado"}:
            card["fide_id"] = player.get("fide_id", "")
            card["cbx_id"] = player.get("cbx_id", "")
        return card

    @staticmethod
    def _public_team_card(team: dict[str, Any], mode: str) -> dict[str, Any]:
        card = {
            "id": int(team.get("id") or 0),
            "name": team.get("name", ""),
            "club": team.get("club", ""),
            "captain": team.get("captain", "") if mode in {"clube", "privado"} else "",
            "active": bool(team.get("active")),
        }
        return card

    def live_portal_html(self, tournament_id: int, mode: str = "publico") -> str:
        payload = self.public_tournament_payload(tournament_id, mode=mode)
        tournament = payload["tournament"]
        standings_rows = "".join(
            "<tr>"
            f"<td>{item.get('position', '')}</td>"
            f"<td>{self._escape(item.get('name') or item.get('team') or '')}</td>"
            f"<td>{self._escape(item.get('category') or item.get('club') or '')}</td>"
            f"<td>{self._escape(item.get('points', item.get('match_points', '')))}</td>"
            f"<td>{self._escape(item.get('buchholz', ''))}</td>"
            "</tr>"
            for item in payload["standings"]
        )
        current = payload.get("current_round") or {}
        pairings = current.get("matches") or current.get("pairings") or []
        current_rows = "".join(
            "<tr>"
            f"<td>{self._escape(item.get('match_number', item.get('board', '')))}</td>"
            f"<td>{self._escape(item.get('white_team', item.get('white', '')))}</td>"
            f"<td>{self._escape(item.get('result', ''))}</td>"
            f"<td>{self._escape(item.get('black_team', item.get('black', '')))}</td>"
            "</tr>"
            for item in pairings
        )
        player_rows = "".join(
            "<tr>"
            f"<td>{self._escape(item.get('name', ''))}</td>"
            f"<td>{self._escape(item.get('club', ''))}</td>"
            f"<td>{self._escape(item.get('category', ''))}</td>"
            f"<td>{self._escape(item.get('rating', ''))}</td>"
            "</tr>"
            for item in payload["players"]
        )
        rounds_rows = "".join(
            "<tr>"
            f"<td>{round_data.get('number', '')}</td>"
            f"<td>{self._escape(round_data.get('status', ''))}</td>"
            f"<td>{len(round_data.get('matches') or round_data.get('pairings') or [])}</td>"
            "</tr>"
            for round_data in payload["rounds"]
        )
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{self._escape(tournament['name'])}</title>
  <style>{self._site_css()}</style>
</head>
<body>
  <header><p class="eyebrow">Albericus Live</p><h1>{self._escape(tournament['name'])}</h1><p>{self._escape(tournament.get('location', ''))}</p></header>
  <main>
    <section class="summary">
      <div><strong>Modo</strong><span>{self._escape(payload['mode'])}</span></div>
      <div><strong>Rodada atual</strong><span>{self._escape(current.get('number', 'Sem rodada'))}</span></div>
      <div><strong>Status</strong><span>{self._escape(tournament.get('status', ''))}</span></div>
    </section>
    <section><h2>Avisos do árbitro</h2><p>{self._escape(payload.get('notice') or 'Nenhum aviso publicado.')}</p></section>
    <section><h2>Rodada atual</h2><table><thead><tr><th>Mesa</th><th>Brancas/Equipe A</th><th>Resultado</th><th>Pretas/Equipe B</th></tr></thead><tbody>{current_rows}</tbody></table></section>
    <section><h2>Classificação</h2><table><thead><tr><th>Pos</th><th>Nome</th><th>Categoria/Clube</th><th>Pts</th><th>Buchholz</th></tr></thead><tbody>{standings_rows}</tbody></table></section>
    <section><h2>Histórico de rodadas</h2><table><thead><tr><th>Rodada</th><th>Status</th><th>Mesas</th></tr></thead><tbody>{rounds_rows}</tbody></table></section>
    <section><h2>Fichas publicas</h2><table><thead><tr><th>Nome</th><th>Clube</th><th>Categoria</th><th>Rating</th></tr></thead><tbody>{player_rows}</tbody></table></section>
  </main>
  <footer>Atualizado em {self._escape(payload['generated_at'])}</footer>
</body>
</html>"""

    def _club_portal_scope(
        self,
        club_id: int | None,
        class_id: int | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        class_data = self.db.get_class(class_id) if class_id else None
        if class_id and not class_data:
            raise AppError("Turma do portal não encontrada.")
        if class_data and club_id and int(class_data["club_id"]) != int(club_id):
            raise AppError("A turma selecionada não pertence ao clube/escola do portal.")

        if class_data and not club_id:
            club_id = int(class_data["club_id"])
        club = self.db.get_club(club_id) if club_id else None
        if club_id and not club:
            raise AppError("Clube/escola do portal não encontrado.")
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
      <table><thead><tr><th>Data</th><th>Hora</th><th>Aula/Treino</th><th>Turma</th><th>Nível</th><th>Objetivo</th></tr></thead><tbody>{session_rows}</tbody></table>
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
            f"<td>{self._escape(player.get('lbx_id') or '')}</td>"
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
      <div><strong>Período</strong><span>{self._escape(tournament['start_date'])} - {self._escape(tournament['end_date'])}</span></div>
      <div><strong>Rodadas</strong><span>{tournament['rounds_count']}</span></div>
      <div><strong>Ritmo</strong><span>{self._escape(tournament['time_control'])}</span></div>
      <div><strong>Competição</strong><span>{self._escape(COMPETITION_TYPES.get(tournament.get('competition_type', 'individual'), 'Individual'))}</span></div>
      <div><strong>Status</strong><span>{self._escape(tournament['status'])}</span></div>
    </section>
    <section>
      <h2>Informações</h2>
      <dl>
        <dt>FIDE Event-ID</dt><dd>{self._escape(settings.get('fide_event_id') or '')}</dd>
        <dt>Organizador</dt><dd>{self._escape(settings.get('organizer') or '')}</dd>
        <dt>Diretor</dt><dd>{self._escape(settings.get('director') or '')}</dd>
        <dt>Árbitro principal</dt><dd>{self._escape(settings.get('chief_arbiter') or '')}</dd>
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
      <table><thead><tr><th>Nome</th><th>Título</th><th>FIDE</th><th>CBX</th><th>LBX</th><th>Rating</th><th>Clube</th><th>Categoria</th><th>Idade</th><th>Rating cat.</th><th>Tags</th><th>Status</th></tr></thead><tbody>{players_rows}</tbody></table>
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
            qr_cell = ""
            if not pairing["is_bye"] and round_data.get("status") != "closed":
                url = self._qr_result_url(int(round_data["tournament_id"]), int(pairing["id"]))
                qr_cell = (
                    f"<a href='{self._escape(url)}'>Enviar</a><br>"
                    f"<img alt='QR mesa {pairing['board_number']}' width='84' height='84' "
                    f"src='{self._escape(self._qr_image_data_uri(url))}'>"
                )
            rows.append(
                "<tr>"
                f"<td>{pairing['board_number']}</td>"
                f"<td>{self._escape(pairing_player_name(pairing, 'white'))}</td>"
                f"<td>{pairing['white_rating']}</td>"
                f"<td>{self._escape(pairing['result'] or '')}</td>"
                f"<td>{self._escape(black_name or '')}</td>"
                f"<td>{self._escape(black_rating or '')}</td>"
                f"<td>{qr_cell}</td>"
                "</tr>"
            )
        return (
            "<section>"
            f"<h2>Rodada {round_data['number']}</h2>"
            f"<p>Status: {self._escape(round_data['status'])}</p>"
            "<table><thead><tr><th>Mesa</th><th>Brancas</th><th>Rating</th>"
            "<th>Resultado</th><th>Pretas</th><th>Rating</th><th>QR resultado</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            "</section>"
        )

    @staticmethod
    def _qr_image_data_uri(url: str) -> str:
        try:
            import qrcode

            image = qrcode.make(url)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception:
            return ""

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
            return "<section><h2>Classificação</h2><p>Classificação ocultada pela organização.</p></section>"

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
                "<h2>Classificação por equipes</h2>"
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
        tiebreak_rows = []
        for item in standings:
            components = dict(item.get("tiebreak_components") or {})
            buchholz = components.get("buchholz", {})
            median = components.get("buchholz_median", {})
            sb = components.get("sonneborn_berger", {})
            summary = " | ".join(
                part
                for part in (
                    f"Buchholz: {self._tiebreak_component_summary(buchholz)}",
                    f"Mediano: {self._tiebreak_component_summary(median)}",
                    f"SB: {self._tiebreak_component_summary(sb)}",
                )
                if part.strip()
            )
            tiebreak_rows.append(
                "<tr>"
                f"<td>{item['position']}</td>"
                f"<td>{self._escape(item['name'])}</td>"
                f"<td>{self._escape(summary)}</td>"
                "</tr>"
            )
        return (
            "<section>"
            "<h2>Classificação</h2>"
            "<table><thead><tr><th>Pos</th><th>Jogador</th><th>Categoria</th><th>Pts</th>"
            "<th>Buchholz</th><th>Buchholz M</th><th>SB</th>"
            "<th>Vitórias</th><th>Perf.</th></tr></thead>"
            f"<tbody>{standings_rows}</tbody></table>"
            "<h3>Componentes de desempate</h3>"
            "<table><thead><tr><th>Pos</th><th>Jogador</th><th>Resumo</th></tr></thead>"
            f"<tbody>{''.join(tiebreak_rows)}</tbody></table>"
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
            "<table><thead><tr><th>Equipe</th><th>Clube/Cidade</th><th>Capitão</th>"
            "<th>Titulares</th><th>Jogadores</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(team_rows)}</tbody></table>"
            "</section>"
            "<section>"
            "<h2>Escalações</h2>"
            "<table><thead><tr><th>Equipe</th><th>Tabuleiro</th><th>Função</th><th>Jogador</th>"
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
