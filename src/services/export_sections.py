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

from src.services.export_federation import FederationReportsMixin

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


class ReportSectionsMixin:
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
                player.get("lbx_id", ""),
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
                "LBX ID",
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

    def _initial_player_list_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        tournament = self.db.get_tournament(tournament_id)
        ordered_players = self._initial_ranked_players(
            self.db.list_players(tournament_id, active_only=False)
        )
        rows = [
            [
                index,
                player_full_name(player),
                self._trf_rating(player),
                player.get("club", ""),
                player.get("category", ""),
                PLAYER_STATUSES.get(player.get("player_status", "active"), player.get("player_status", "")),
                "",
            ]
            for index, player in enumerate(ordered_players, start=1)
        ]
        title = "Lista inicial de jogadores"
        if tournament:
            title = f"{title} - {tournament['name']}"
        return (
            title,
            ["Inicial", "Jogador", "Rating", "Clube", "Categoria", "Status", "Presenca"],
            rows,
        )

    def _rating_fee_sections(self, tournament_id: int) -> list[tuple[str, list[str], list[list[Any]]]]:
        summary = self.rating_fee_summary(tournament_id)
        summary_rows = [
            ["Torneio", summary["tournament_name"]],
            ["Inscritos", summary["players_count"]],
            ["Rated em alguma base", summary["rated_players"]],
            ["Nao rated", summary["unrated_players"]],
            ["Com ID oficial", summary["players_with_base"]],
            ["Sem ID oficial", summary["players_without_base"]],
            ["Total das taxas", self._format_currency(summary["total"])],
            ["Regra", "Cada base cobra separadamente os inscritos identificados nela."],
        ]
        base_rows = [
            [
                item["base"],
                item["identified"],
                item["rated"],
                item["unrated"],
                self._format_currency(item["unit_fee"]),
                self._format_currency(item["subtotal"]),
            ]
            for item in summary["bases"]
        ]
        player_rows = []
        for player in summary["players"]:
            bases = [
                label
                for label, field in (("FIDE", "fide_id"), ("CBX", "cbx_id"), ("LBX", "lbx_id"))
                if str(player.get(field) or "").strip()
            ]
            player_rows.append(
                [
                    player["name"],
                    player.get("fide_id", ""),
                    player.get("international_rating", 0),
                    player.get("cbx_id", ""),
                    player.get("national_rating", 0),
                    player.get("lbx_id", ""),
                    player.get("rating", 0),
                    ", ".join(bases) or "Sem base",
                ]
            )
        return [
            ("Resumo de taxas de rating", ["Campo", "Valor"], summary_rows),
            ("Taxas por base", ["Base", "Identificados", "Rated", "Nao rated", "Taxa unitaria", "Subtotal"], base_rows),
            (
                "Inscritos por base",
                ["Jogador", "FIDE ID", "Rating FIDE", "CBX ID", "Rating CBX", "LBX ID", "Rating LBX", "Bases cobradas"],
                player_rows,
            ),
        ]

    FIDE_RATING_TYPE_LABELS = {"fide": "FIDE", "cbx": "CBX"}

    def _fide_rating_sections(
        self, tournament_id: int, rating_type: str = "fide"
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if rating_type not in self.FIDE_RATING_TYPE_LABELS:
            raise AppError("Tipo de rating invalido para o relatorio FIDE.")
        if tournament.get("competition_type") == "team":
            raise AppError("Relatorio de variacao de rating disponivel apenas para torneios individuais.")

        players = self.db.list_players(tournament_id, active_only=False)
        closed = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        start_date = str(tournament.get("start_date") or "").strip()
        year = int(start_date[:4]) if len(start_date) >= 4 and start_date[:4].isdigit() else None
        rows = build_fide_report_rows(players, closed, rating_type, tournament_year=year)
        # Snapshot persistido para auditoria/reimpressao (idempotente por base).
        self.db.save_fide_rating_report(tournament_id, rating_type, rows)

        base_label = self.FIDE_RATING_TYPE_LABELS[rating_type]
        rated = [row for row in rows if row.get("ro")]
        deltas = [float(row["delta"]) for row in rated if row.get("delta") is not None]

        def cell(value: Any) -> Any:
            return "-" if value is None else value

        notice_rows = [
            ["Estimativa de apoio ao arbitro (We, fator K, Rc, Rp)."],
            [f"Nao substitui a homologacao oficial da {base_label}."],
            [f"So conta partidas jogadas contra adversarios com rating na base {base_label}."],
            ["Diferencas de rating acima de 400 sao tratadas como 400 (regra dos 400)."],
        ]
        summary_rows = [
            ["Torneio", tournament["name"]],
            ["Base de rating", base_label],
            ["Jogadores no relatorio", len(rows)],
            ["Com rating", len(rated)],
            ["Sem rating (somente performance)", len(rows) - len(rated)],
            ["Variacao total (ΔElo)", round(sum(deltas), 2)],
            ["Maior ganho", round(max(deltas), 2) if deltas else 0.0],
            ["Maior perda", round(min(deltas), 2) if deltas else 0.0],
        ]
        detail_rows = [
            [
                row["name"],
                row["ro"] if row.get("ro") else "-",
                row["k"] if row.get("ro") else "-",
                row["games_rated"],
                row["score"],
                cell(row["we"]),
                cell(row["delta"]),
                cell(row["rc"]),
                row["rp"],
                row["n_over_400"],
            ]
            for row in rows
        ]
        return [
            ("Aviso", ["Observacao"], notice_rows),
            ("Resumo do relatorio de rating", ["Campo", "Valor"], summary_rows),
            (
                f"Variacao de rating {base_label}",
                ["Jogador", "Ro", "K", "n", "Pts", "We", "ΔElo", "Rc", "Rp", ">400"],
                detail_rows,
            ),
        ]

    def _prize_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Distribuicao de premios disponivel apenas para torneios individuais.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        prizes = self.db.list_tournament_prizes(tournament_id)
        standings = self.pairing_service.standings(tournament_id)
        result = allocate_prizes(
            standings,
            prizes,
            policy=str(settings.get("prize_policy") or "best_only"),
            tax_percent=float(settings.get("prize_tax_percent") or 0.0),
        )

        policy_label = PRIZE_POLICIES.get(result["policy"], result["policy"])
        summary_rows = [
            ["Torneio", tournament["name"]],
            ["Politica de premiacao", policy_label],
            ["Imposto do organizador (%)", result["tax_percent"]],
            ["Premiados", result["winners"]],
            ["Total bruto", self._format_currency(result["total_gross"])],
            ["Total imposto", self._format_currency(result["total_tax"])],
            ["Total liquido distribuido", self._format_currency(result["total_net"])],
        ]
        winner_rows = [
            [
                allocation["position"],
                allocation["name"],
                allocation["category"],
                allocation["points"],
                self._format_currency(allocation["overall"]),
                self._format_currency(allocation["category_prize"]),
                self._format_currency(allocation["gross"]),
                self._format_currency(allocation["net"]),
            ]
            for allocation in result["allocations"]
        ]
        sections: list[tuple[str, list[str], list[list[Any]]]] = [
            ("Resumo da premiacao", ["Campo", "Valor"], summary_rows),
            (
                "Premiacao por jogador",
                ["Pos", "Jogador", "Categoria", "Pts", "Premio geral", "Premio categoria", "Bruto", "Liquido"],
                winner_rows,
            ),
        ]
        if result["manual_prizes"]:
            manual_rows = [
                [
                    PRIZE_KINDS.get(prize["kind"], prize["kind"]),
                    prize["label"],
                    prize["category"],
                    self._format_currency(prize["amount"]),
                ]
                for prize in result["manual_prizes"]
            ]
            sections.append(
                (
                    "Premios manuais (definir ganhador)",
                    ["Tipo", "Premio", "Categoria", "Valor"],
                    manual_rows,
                )
            )
        return sections

    def _individual_tournament(self, tournament_id: int, what: str) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            raise AppError(f"{what} disponivel apenas para torneios individuais.")
        return tournament

    def _federation_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self._individual_tournament(tournament_id, "Estatistica de federacoes")
        players = self.db.list_players(tournament_id, active_only=False)
        federation_by_id = {
            int(player["id"]): (str(player.get("federation_id") or "").strip().upper() or "—")
            for player in players
        }
        standings = self.pairing_service.standings(tournament_id)

        groups: dict[str, list[float]] = {}
        for standing in standings:
            federation = federation_by_id.get(int(standing["player_id"]), "—")
            bucket = groups.setdefault(federation, [0.0, 0.0, 0.0])
            bucket[0] += 1
            bucket[1] += float(standing.get("points") or 0.0)
            bucket[2] += sum(1 for game in standing.get("games", []) if game.get("color") != "bye")

        total_players = int(sum(bucket[0] for bucket in groups.values())) or 1
        rows = []
        for federation, (count, points, games) in sorted(
            groups.items(), key=lambda item: (-item[1][0], item[0])
        ):
            rows.append(
                [
                    federation,
                    int(count),
                    f"{100 * count / total_players:.1f}%",
                    self._format_report_number(round(points, 2)),
                    int(games),
                    self._format_report_number(round(points / count, 2)) if count else "0",
                ]
            )
        summary_rows = [
            ["Torneio", tournament["name"]],
            ["Federacoes", len(groups)],
            ["Jogadores", total_players],
        ]
        return [
            ("Resumo de federacoes", ["Campo", "Valor"], summary_rows),
            (
                "Estatistica de federacoes",
                ["Federacao", "Jogadores", "% jogadores", "Pontos", "Partidas", "Media pts"],
                rows,
            ),
        ]

    def _game_statistics_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self._individual_tournament(tournament_id, "Estatistica de partidas")
        closed = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)

        white_wins = draws = black_wins = walkovers = byes = 0
        for pairing in closed:
            if pairing.get("is_bye"):
                byes += 1
                continue
            result = pairing.get("result")
            if result == "1-0":
                white_wins += 1
            elif result == "0-1":
                black_wins += 1
            elif result == "1/2-1/2":
                draws += 1
            elif result in ("1F-0F", "0F-1F", "0F-0F"):
                walkovers += 1

        played = white_wins + draws + black_wins

        def percent(value: int) -> str:
            return f"{100 * value / played:.1f}%" if played else "0%"

        distribution_rows = [
            ["Vitorias de brancas", white_wins, percent(white_wins)],
            ["Empates", draws, percent(draws)],
            ["Vitorias de pretas", black_wins, percent(black_wins)],
        ]
        summary_rows = [
            ["Torneio", tournament["name"]],
            ["Partidas jogadas (tabuleiro)", played],
            ["WO / forfait", walkovers],
            ["Byes", byes],
            ["Total de pareamentos fechados", len(closed)],
        ]
        return [
            ("Resumo de partidas", ["Campo", "Valor"], summary_rows),
            ("Distribuicao de resultados", ["Resultado", "Quantidade", "%"], distribution_rows),
        ]

    def _player_cards_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        self._individual_tournament(tournament_id, "Fichas individuais")
        players = self.db.list_players(tournament_id, active_only=False)
        federation_by_id = {
            int(player["id"]): str(player.get("federation_id") or "").strip().upper()
            for player in players
        }
        standings = self.pairing_service.standings(tournament_id)

        color_labels = {"white": "Brancas", "black": "Pretas", "bye": "Bye"}
        summary_rows = []
        game_rows = []
        for standing in standings:
            games = standing.get("games", [])
            board_games = [game for game in games if game.get("color") != "bye"]
            wins = sum(1 for game in board_games if float(game.get("earned") or 0.0) == 1.0)
            draws = sum(1 for game in board_games if float(game.get("earned") or 0.0) == 0.5)
            losses = sum(1 for game in board_games if float(game.get("earned") or 0.0) == 0.0)
            performance = standing.get("performance")
            summary_rows.append(
                [
                    standing.get("position", 0),
                    standing.get("name", ""),
                    standing.get("category", ""),
                    federation_by_id.get(int(standing["player_id"]), ""),
                    self._format_report_number(standing.get("points", 0)),
                    performance if isinstance(performance, int) else "-",
                    wins,
                    draws,
                    losses,
                    standing.get("white_count", 0),
                    standing.get("black_count", 0),
                    standing.get("byes", 0),
                ]
            )
            running = float(standing.get("starting_points", 0.0) or 0.0)
            for game in sorted(games, key=lambda item: int(item.get("round") or 0)):
                running += float(game.get("earned") or 0.0)
                game_rows.append(
                    [
                        standing.get("position", 0),
                        standing.get("name", ""),
                        int(game.get("round") or 0),
                        color_labels.get(str(game.get("color")), ""),
                        game.get("opponent_name", "") or "BYE",
                        game.get("result", "") or "",
                        self._format_report_number(round(running, 2)),
                    ]
                )
        return [
            (
                "Resumo por jogador",
                ["Pos", "Jogador", "Categoria", "Fed", "Pts", "Rp", "V", "E", "D", "Brancas", "Pretas", "Byes"],
                summary_rows,
            ),
            (
                "Resultados rodada a rodada",
                ["Pos", "Jogador", "Rodada", "Cor", "Adversario", "Resultado", "Pts acum."],
                game_rows,
            ),
        ]

    def _norm_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        self._individual_tournament(tournament_id, "Normas FIDE")
        players = self.db.list_players(tournament_id, active_only=False)
        closed = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        report = build_norm_report(players, closed, "fide")

        notice_rows = [
            ["Estimativa de apoio ao arbitro: indica se o jogador atingiu indicadores"],
            ["compativeis com uma norma. NAO concede norma nem titulo (exclusivo da FIDE)."],
            ["So conta partidas jogadas contra adversarios com rating."],
        ]
        summary_rows = [
            [
                item["name"],
                item["sex"],
                item["performance"],
                item["games"],
                self._format_report_number(item["average_opponent"]),
                item["federations"],
                item["titled_opponents"],
                ", ".join(item["achieved"]) or "-",
            ]
            for item in report
        ]
        detail_rows = []
        for item in report:
            for title in item["titles"]:
                detail_rows.append(
                    [
                        item["name"],
                        title["label"],
                        "Sim" if title["meets"] else "Nao",
                        "OK" if title["meets"] else "; ".join(title["missing"]),
                    ]
                )
        return [
            ("Aviso", ["Observacao"], notice_rows),
            (
                "Indicadores de norma por jogador",
                ["Jogador", "Sexo", "Rp", "Partidas", "Media adv.", "Federacoes", "Titulados", "Norma atingida"],
                summary_rows,
            ),
            ("Detalhe por titulo", ["Jogador", "Titulo", "Atende?", "Pendencias"], detail_rows),
        ]

    _ARBITER_ROLE_LABELS = {
        "chief": "Arbitro principal",
        "chief_arbiter": "Arbitro principal",
        "main": "Arbitro principal",
        "principal": "Arbitro principal",
        "deputy": "Arbitro adjunto",
        "sector": "Arbitro de setor",
        "arbiter": "Arbitro",
        "assistant": "Assistente",
    }

    def _arbiter_norm_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        rated = sum(1 for player in players if self._trf_rating(player) > 0)
        referees = self.db.list_tournament_referees(tournament_id)
        competition = "Equipes" if tournament.get("competition_type") == "team" else "Individual"

        notice_rows = [
            ["Documento de apoio para a norma de arbitro (IA/FA)."],
            ["Nao e o formulario oficial da FIDE; use os dados abaixo para preenche-lo."],
        ]
        tournament_rows = [
            ["Torneio", tournament["name"]],
            ["Local", tournament.get("location", "")],
            ["Federacao", settings.get("federation", "")],
            ["FIDE Event-ID", settings.get("fide_event_id", "")],
            ["Data de inicio", tournament.get("start_date", "")],
            ["Data de termino", tournament.get("end_date", "")],
            ["Ritmo de jogo", tournament.get("time_control", "")],
            ["Rodadas", tournament.get("rounds_count", "")],
            ["Tipo", competition],
            ["Jogadores", len(players)],
            ["Jogadores com rating", rated],
            ["Organizador", settings.get("organizer", "")],
            ["Arbitro principal (config.)", settings.get("chief_arbiter", "")],
        ]

        arbiter_rows: list[list[Any]] = []
        for referee in referees:
            role = str(referee.get("role") or "").strip().lower()
            arbiter_rows.append(
                [
                    referee.get("name", ""),
                    self._ARBITER_ROLE_LABELS.get(role, role.replace("_", " ").title() or "Arbitro"),
                    referee.get("fide_id", ""),
                    referee.get("category", ""),
                    "",
                    "",
                ]
            )
        if not arbiter_rows:
            chief = str(settings.get("chief_arbiter") or "").strip()
            if chief:
                arbiter_rows.append([chief, "Arbitro principal", "", "", "", ""])
            for name in str(settings.get("arbiters") or "").replace(";", ",").split(","):
                cleaned = name.strip()
                if cleaned:
                    arbiter_rows.append([cleaned, "Arbitro", "", "", "", ""])

        return [
            ("Aviso", ["Observacao"], notice_rows),
            ("Dados do torneio (norma de arbitro)", ["Campo", "Valor"], tournament_rows),
            (
                "Arbitros designados",
                ["Nome", "Funcao", "FIDE ID", "Categoria", "Norma (IA/FA)", "Assinatura"],
                arbiter_rows,
            ),
        ]

    def _category_winners_section(
        self, tournament_id: int, top_n: int = 3
    ) -> tuple[str, list[str], list[list[Any]]]:
        """Vencedores por categoria (top N de cada categoria, na ordem da classificacao)."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in self.pairing_service.standings(tournament_id):
            category = str(item.get("category") or "").strip()
            if category:
                groups.setdefault(category, []).append(item)
        rows: list[list[Any]] = []
        for category in sorted(groups):
            for rank, item in enumerate(groups[category][: max(1, top_n)], start=1):
                rows.append(
                    [
                        category,
                        rank,
                        item.get("name", ""),
                        item.get("points", ""),
                        item.get("performance", ""),
                    ]
                )
        if not rows:
            rows = [["", "", "Sem categorias definidas neste torneio.", "", ""]]
        return ("Vencedores por categoria", ["Categoria", "Pos", "Jogador", "Pts", "Performance"], rows)

    def _round_bulletin_sections(
        self, round_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        """Secoes do boletim da rodada: cabecalho + resultados + classificacao + destaques."""
        round_data = self.db.get_round(round_id)
        if not round_data:
            raise AppError("Rodada nao encontrada.")
        tournament = self.db.get_tournament(int(round_data["tournament_id"]))
        if not tournament:
            raise AppError("Torneio nao encontrado.")
        number = round_data["number"]

        header_rows = [
            ["Torneio", tournament["name"]],
            ["Rodada", number],
            ["Estado", round_data.get("status", "")],
            ["Local", tournament.get("location", "")],
            ["Data", round_data.get("scheduled_at", "") or tournament.get("start_date", "")],
        ]
        sections: list[tuple[str, list[str], list[list[Any]]]] = [
            (f"Boletim da rodada {number}", ["Campo", "Valor"], header_rows),
        ]
        sections.append(self._pairings_section(round_id))
        # Classificacao apos a rodada (top 10) reaproveita o layout da classificacao.
        title, headers, rows = self._standings_section(int(tournament["id"]))
        sections.append((f"Classificacao apos a rodada {number} (top 10)", headers, rows[:10]))
        if tournament.get("competition_type") != "team":
            sections.append(self._bulletin_highlights_section(round_id, int(tournament["id"])))
        return sections

    def _bulletin_highlights_section(
        self, round_id: int, tournament_id: int
    ) -> tuple[str, list[str], list[list[Any]]]:
        """Destaques da rodada (individual): lider, decisivas/empates e maior zebra."""
        pairings = [item for item in self.db.get_pairings_for_round(round_id) if not item.get("is_bye")]
        decisive = sum(1 for item in pairings if item.get("result") in ("1-0", "0-1"))
        draws = sum(1 for item in pairings if item.get("result") == "1/2-1/2")
        standings = self.pairing_service.standings(tournament_id)

        best_upset: tuple[str, str, int] | None = None
        for item in pairings:
            result = item.get("result")
            white_rating = int(item.get("white_rating") or 0)
            black_rating = int(item.get("black_rating") or 0)
            if not white_rating or not black_rating:
                continue
            if result == "1-0" and black_rating > white_rating:
                diff, winner, loser = black_rating - white_rating, pairing_player_name(item, "white"), pairing_player_name(item, "black")
            elif result == "0-1" and white_rating > black_rating:
                diff, winner, loser = white_rating - black_rating, pairing_player_name(item, "black"), pairing_player_name(item, "white")
            else:
                continue
            if best_upset is None or diff > best_upset[2]:
                best_upset = (winner, loser, diff)

        rows: list[list[Any]] = []
        if standings:
            rows.append(["Lider", f"{standings[0].get('name', '')} ({standings[0].get('points', '')} pts)"])
        rows.append(["Partidas decididas", decisive])
        rows.append(["Empates", draws])
        if best_upset:
            rows.append(["Maior zebra", f"{best_upset[0]} venceu {best_upset[1]} (+{best_upset[2]} de rating)"])
        return ("Destaques", ["Item", "Valor"], rows)

    def _podium_data(self, tournament_id: int) -> dict[str, Any]:
        """Dados do podio: top 3 (jogadores ou equipes) + campeoes por categoria."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        is_team = tournament.get("competition_type") == "team"
        top: list[dict[str, Any]] = []
        categories: list[dict[str, Any]] = []
        if is_team:
            for index, item in enumerate(self.pairing_service.team_standings(tournament_id)[:3], start=1):
                top.append(
                    {
                        "rank": index,
                        "name": str(item.get("name") or item.get("team_name") or ""),
                        "points": item.get("match_points", ""),
                        "detail": f"GP {item.get('game_points', '')}",
                    }
                )
        else:
            standings = self.pairing_service.standings(tournament_id)
            for index, item in enumerate(standings[:3], start=1):
                top.append(
                    {
                        "rank": index,
                        "name": str(item.get("name") or ""),
                        "points": item.get("points", ""),
                        "detail": f"perf {item.get('performance', '')}",
                    }
                )
            champions: dict[str, str] = {}
            for item in standings:
                category = str(item.get("category") or "").strip()
                if category and category not in champions:
                    champions[category] = str(item.get("name") or "")
            categories = [{"category": cat, "name": name} for cat, name in sorted(champions.items())]
        return {"tournament": tournament, "top": top, "categories": categories, "is_team": is_team}

    def _write_podium_poster_pdf(self, path: Path, data: dict[str, Any]) -> None:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise AppError("Instale reportlab para gerar o poster do podio (pip install reportlab).") from exc

        tournament = data["tournament"]
        width, height = A4
        center = width / 2
        document = canvas.Canvas(str(path), pagesize=A4)
        document.setLineWidth(2)
        document.rect(30, 30, width - 60, height - 60)

        document.setFont("Helvetica-Bold", 24)
        document.drawCentredString(center, height - 90, str(tournament.get("name") or "Torneio"))
        document.setFont("Helvetica", 14)
        document.drawCentredString(center, height - 116, "Premiacao - Podio")
        subtitle = " - ".join(
            part for part in [str(tournament.get("location") or ""), str(tournament.get("start_date") or "")] if part
        )
        if subtitle:
            document.setFont("Helvetica", 11)
            document.drawCentredString(center, height - 136, subtitle)

        medals = {1: "1o lugar", 2: "2o lugar", 3: "3o lugar"}
        y = height - 230
        for entry in data["top"]:
            rank = int(entry["rank"])
            document.setFont("Helvetica-Bold", 22 if rank == 1 else 16)
            document.drawCentredString(center, y, f"{medals.get(rank, f'{rank}o')}: {entry['name']}")
            document.setFont("Helvetica", 12)
            document.drawCentredString(center, y - 20, f"{entry['points']} pts  ({entry['detail']})")
            y -= 70 if rank == 1 else 60
        if not data["top"]:
            document.setFont("Helvetica", 12)
            document.drawCentredString(center, y, "Sem classificacao disponivel.")

        if data["categories"]:
            y -= 20
            document.setFont("Helvetica-Bold", 14)
            document.drawCentredString(center, y, "Campeoes por categoria")
            y -= 24
            document.setFont("Helvetica", 12)
            for champion in data["categories"]:
                if y < 80:
                    break
                document.drawCentredString(center, y, f"{champion['category']}: {champion['name']}")
                y -= 20

        document.setFont("Helvetica-Oblique", 9)
        document.drawCentredString(center, 50, "Gerado pelo Albericus")
        document.save()

    def _tournament_minutes_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        """Secoes da ata final: cabecalho + classificacao + categorias + premiacao + taxas + arbitros."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        rated = sum(1 for player in players if self._trf_rating(player) > 0)
        competition = "Equipes" if tournament.get("competition_type") == "team" else "Individual"

        header_rows = [
            ["Torneio", tournament["name"]],
            ["Local", tournament.get("location", "")],
            ["Federacao", settings.get("federation", "")],
            ["FIDE Event-ID", settings.get("fide_event_id", "")],
            ["Data de inicio", tournament.get("start_date", "")],
            ["Data de termino", tournament.get("end_date", "")],
            ["Ritmo de jogo", tournament.get("time_control", "")],
            ["Rodadas", tournament.get("rounds_count", "")],
            ["Tipo", competition],
            ["Jogadores", len(players)],
            ["Jogadores com rating", rated],
            ["Organizador", settings.get("organizer", "")],
            ["Diretor", settings.get("director", "")],
            ["Arbitro principal", settings.get("chief_arbiter", "")],
        ]

        referees = self.db.list_tournament_referees(tournament_id)
        arbiter_rows: list[list[Any]] = []
        for referee in referees:
            role = str(referee.get("role") or "").strip().lower()
            arbiter_rows.append(
                [
                    referee.get("name", ""),
                    self._ARBITER_ROLE_LABELS.get(role, role.replace("_", " ").title() or "Arbitro"),
                    referee.get("fide_id", ""),
                    referee.get("category", ""),
                    "",
                ]
            )
        if not arbiter_rows:
            chief = str(settings.get("chief_arbiter") or "").strip()
            if chief:
                arbiter_rows.append([chief, "Arbitro principal", "", "", ""])
            for name in str(settings.get("arbiters") or "").replace(";", ",").split(","):
                cleaned = name.strip()
                if cleaned:
                    arbiter_rows.append([cleaned, "Arbitro", "", "", ""])

        sections: list[tuple[str, list[str], list[list[Any]]]] = [
            ("Ata final do torneio", ["Campo", "Valor"], header_rows),
            self._standings_section(tournament_id),
        ]
        if tournament.get("competition_type") != "team":
            sections.append(self._category_winners_section(tournament_id))
        # Premiacao e taxas sao opcionais: AppError quando nao se aplicam.
        try:
            sections.extend(self._prize_sections(tournament_id))
        except AppError:
            pass
        try:
            sections.extend(self._rating_fee_sections(tournament_id))
        except AppError:
            pass
        sections.append(
            ("Arbitros e assinaturas", ["Nome", "Funcao", "FIDE ID", "Categoria", "Assinatura"], arbiter_rows)
        )
        return sections

    @staticmethod
    def _format_currency(value: Any) -> str:
        return f"R$ {float(value or 0):.2f}".replace(".", ",")

    @staticmethod
    def _initial_ranked_players(players: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return sorted(
            players,
            key=lambda player: (
                -FederationReportsMixin._trf_rating(player),
                player_pairing_name(player).casefold(),
                int(player.get("id") or 0),
            ),
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
