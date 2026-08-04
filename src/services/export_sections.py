from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

from src.services.constants import *
from src.services.fide_norms import build_norm_report
from src.services.categories import group_by_category
from src.services.rating import build_report_rows, regulation_from_settings, resolve_speed
from src.services.time_control import SPEED_LABELS, below_blitz_minimum
from src.services.pairing.incidents import (
    decision_label as incident_decision_label,
    infraction_label as incident_infraction_label,
)
from src.services.pairing.point_adjustments import format_signed
from src.services.prizes import PRIZE_KINDS, PRIZE_POLICIES, PRIZE_TIE_SPLITS, allocate_prizes
from src.services.export_federation import FederationReportsMixin

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
            raise AppError("Selecione um torneio válido.")
        rows = [
            ["Nome", tournament["name"]],
            ["Escopo", self._tournament_scope_label(tournament)],
            [
                "Competição",
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
                ["Página web", settings.get("website", "")],
                ["E-mail", settings.get("contact_email", "")],
                ["Diretor", settings.get("director", "")],
                ["Árbitro principal", settings.get("chief_arbiter", "")],
                ["Federação", settings.get("federation", "")],
                ["Estado", settings.get("state", "")],
                ["Categorias", settings.get("categories", "")],
                ["Data de corte", settings.get("cutoff_date", "")],
                ["Ordem inicial", settings.get("initial_order", "")],
                ["Tipo de torneio", settings.get("tournament_type", "")],
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
                        "Critério principal por equipes",
                        TEAM_STANDING_CRITERIA.get(
                            settings.get("team_standing_primary", "match_points"),
                            settings.get("team_standing_primary", ""),
                        ),
                    ],
                    [
                        "Critério secundario por equipes",
                        TEAM_STANDING_CRITERIA.get(
                            settings.get("team_standing_secondary", "game_points"),
                            settings.get("team_standing_secondary", ""),
                        ),
                    ],
                    [
                        "Ordem fixa dos tabuleiros",
                        "Sim" if settings.get("team_fixed_board_order", 1) else "Não",
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
                "Título",
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
                "Tags premiação",
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
            ["Inicial", "Jogador", "Rating", "Clube", "Categoria", "Status", "Presença"],
            rows,
        )

    def _rating_fee_sections(self, tournament_id: int) -> list[tuple[str, list[str], list[list[Any]]]]:
        summary = self.rating_fee_summary(tournament_id)
        summary_rows = [
            ["Torneio", summary["tournament_name"]],
            ["Inscritos", summary["players_count"]],
            ["Rated em alguma base", summary["rated_players"]],
            ["Não rated", summary["unrated_players"]],
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
            ("Taxas por base", ["Base", "Identificados", "Rated", "Não rated", "Taxa unitária", "Subtotal"], base_rows),
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
            raise AppError("Selecione um torneio válido.")
        if rating_type not in self.FIDE_RATING_TYPE_LABELS:
            raise AppError("Tipo de rating invalido para o relatório FIDE.")
        if tournament.get("competition_type") == "team":
            raise AppError("Relatório de variacao de rating disponível apenas para torneios individuais.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        closed = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        start_date = str(tournament.get("start_date") or "").strip()
        year = int(start_date[:4]) if len(start_date) >= 4 and start_date[:4].isdigit() else None
        # FED-07: o ritmo decide a lista de rating e o perfil do regulamento.
        speed, speed_origin = resolve_speed(
            tournament.get("time_control"), settings.get("rating_speed")
        )
        regulation = regulation_from_settings(settings, rating_type, speed)
        rows = build_report_rows(
            players,
            closed,
            rating_type,
            tournament_year=year,
            speed=speed,
            regulation=regulation,
        )
        # Snapshot persistido para auditoria/reimpressao (idempotente por base).
        self.db.save_fide_rating_report(tournament_id, rating_type, rows)

        base_label = self.FIDE_RATING_TYPE_LABELS[rating_type]
        rated = [row for row in rows if row.get("ro")]
        deltas = [float(row["delta"]) for row in rated if row.get("delta") is not None]

        def cell(value: Any) -> Any:
            return "-" if value is None else value

        fallback = [row for row in rows if "sem rating" in str(row.get("rating_source") or "")]
        below_floor = [row for row in rows if row.get("below_floor")]
        notice_rows = [
            ["Estimativa de apoio ao árbitro (We, fator K, Rc, Rp)."],
            [f"Não substitui a homologação oficial da {base_label}."],
            [f"So conta partidas jogadas contra adversarios com rating na base {base_label}."],
            ["Diferencas de rating acima de 400 sao tratadas como 400 (regra dos 400)."],
            [f"Regulamento aplicado: {regulation.label} ({regulation.source})."],
        ]
        if not regulation.confirmed:
            notice_rows.append(
                ["ATENCAO: valores deste regulamento NAO foram conferidos no texto vigente."]
            )
        if fallback:
            notice_rows.append(
                [
                    f"{len(fallback)} jogador(es) sem rating de {SPEED_LABELS.get(speed, speed)}: "
                    "usado o rating standard, o que muda o ΔElo. Importe a lista do ritmo."
                ]
            )
        if below_floor:
            notice_rows.append(
                [
                    f"{len(below_floor)} jogador(es) com Rc abaixo do piso de "
                    f"{regulation.rating_floor}; o relatório publica o piso."
                ]
            )
        if below_blitz_minimum(tournament.get("time_control")):
            notice_rows.append(["Ritmo abaixo do minimo que a FIDE rata (3 minutos)."])
        summary_rows = [
            ["Torneio", tournament["name"]],
            ["Base de rating", base_label],
            ["Ritmo", f"{SPEED_LABELS.get(speed, speed)} ({speed_origin})"],
            ["Regulamento", regulation.label],
            ["Piso de rating", regulation.rating_floor],
            ["Jogadores no relatório", len(rows)],
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
                row.get("rating_source") or "-",
                row["k"] if row.get("ro") else "-",
                row.get("k_reason") or "-",
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
        # Estreantes: quem ainda nao tem rating na base ganha a estimativa de
        # rating INICIAL (B.02 8.2), que o relatorio antigo simplesmente nao
        # calculava — sobrava so a performance, que nao e a mesma conta.
        initial_rows = [
            [
                row["name"],
                row["games_rated"],
                row["score"],
                self._format_report_number(row["average_opponent"]),
                row["rp"],
                row.get("initial_rating") or "-",
                row.get("initial_reason") or "-",
            ]
            for row in rows
            if not row.get("ro")
        ]
        sections: list[tuple[str, list[str], list[list[Any]]]] = [
            ("Aviso", ["Observação"], notice_rows),
            ("Resumo do relatório de rating", ["Campo", "Valor"], summary_rows),
            (
                f"Variacao de rating {base_label}",
                [
                    "Jogador",
                    "Ro",
                    "Origem do Ro",
                    "K",
                    "Motivo do K",
                    "n",
                    "Pts",
                    "We",
                    "ΔElo",
                    "Rc",
                    "Rp",
                    ">400",
                ],
                detail_rows,
            ),
        ]
        if initial_rows:
            sections.append(
                (
                    "Rating inicial estimado (sem rating na base)",
                    ["Jogador", "n", "Pts", "Média adv.", "Rp", "Rating inicial", "Situação"],
                    initial_rows,
                )
            )
        return sections

    def _prize_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Distribuição de prêmios disponível apenas para torneios individuais.")

        settings = self.db.get_tournament_settings(tournament_id) or {}
        prizes = self.db.list_tournament_prizes(tournament_id)
        standings = self.pairing_service.standings(tournament_id)
        result = allocate_prizes(
            standings,
            prizes,
            policy=str(settings.get("prize_policy") or "best_only"),
            tax_percent=float(settings.get("prize_tax_percent") or 0.0),
            tie_split=str(settings.get("prize_tie_split") or "equal"),
            exclude_withdrawn=bool(settings.get("prize_exclude_withdrawn")),
        )

        policy_label = PRIZE_POLICIES.get(result["policy"], result["policy"])
        summary_rows = [
            ["Torneio", tournament["name"]],
            ["Política de premiação", policy_label],
            ["Entre empatados", PRIZE_TIE_SPLITS.get(result["tie_split"], result["tie_split"])],
            ["Desistentes excluídos", result["excluded_withdrawn"]],
            ["Imposto do organizador (%)", result["tax_percent"]],
            ["Premiados", result["winners"]],
            ["Total bruto", self._format_currency(result["total_gross"])],
            ["Total imposto", self._format_currency(result["total_tax"])],
            ["Total líquido distribuido", self._format_currency(result["total_net"])],
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
            ("Resumo da premiação", ["Campo", "Valor"], summary_rows),
            (
                "Premiação por jogador",
                ["Pos", "Jogador", "Categoria", "Pts", "Prêmio geral", "Prêmio categoria", "Bruto", "Líquido"],
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
                    "Prêmios manuais (definir ganhador)",
                    ["Tipo", "Prêmio", "Categoria", "Valor"],
                    manual_rows,
                )
            )
        return sections

    def _individual_tournament(self, tournament_id: int, what: str) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") == "team":
            raise AppError(f"{what} disponível apenas para torneios individuais.")
        return tournament

    def _federation_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self._individual_tournament(tournament_id, "Estatística de federações")
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
            ["Federações", len(groups)],
            ["Jogadores", total_players],
        ]
        return [
            ("Resumo de federações", ["Campo", "Valor"], summary_rows),
            (
                "Estatística de federações",
                ["Federação", "Jogadores", "% jogadores", "Pontos", "Partidas", "Média pts"],
                rows,
            ),
        ]

    def _game_statistics_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self._individual_tournament(tournament_id, "Estatística de partidas")
        closed = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)

        white_wins = draws = black_wins = walkovers = byes = 0
        for pairing in closed:
            if pairing.get("is_bye"):
                byes += 1
                continue
            result = pairing.get("result")
            # Pelos PONTOS, e nao pelo codigo: desde a ARB-02 uma vitoria das
            # brancas pode ser `1-0` ou `1U-0U` (decisao do arbitro), e as duas
            # sao vitoria das brancas numa distribuicao de resultados.
            if result in WALKOVER_RESULTS:
                walkovers += 1
            elif result in RESULT_POINTS:
                brancas, pretas = RESULT_POINTS[result]
                if brancas > pretas:
                    white_wins += 1
                elif pretas > brancas:
                    black_wins += 1
                else:
                    draws += 1

        played = white_wins + draws + black_wins

        def percent(value: int) -> str:
            return f"{100 * value / played:.1f}%" if played else "0%"

        distribution_rows = [
            ["Vitórias de brancas", white_wins, percent(white_wins)],
            ["Empates", draws, percent(draws)],
            ["Vitórias de pretas", black_wins, percent(black_wins)],
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
            ("Distribuição de resultados", ["Resultado", "Quantidade", "%"], distribution_rows),
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
        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        closed = self.db.get_pairings_for_tournament(tournament_id, closed_only=True)
        report = build_norm_report(
            players, closed, "fide", pairing_system=settings.get("pairing_method")
        )

        notice_rows = [
            ["Estimativa de apoio ao árbitro: indica se o jogador atingiu indicadores"],
            ["compativeis com uma norma. NAO concede norma nem título (exclusivo da FIDE)."],
            ["Indicadores conforme o FIDE Handbook B.01, secao 1.4 (edicao de 2024)."],
            ["So conta partida jogada no tabuleiro; sem rating conta como 1400."],
            ["A federacao do candidato NAO entra na contagem de federacoes (1.4.3)."],
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
                item["unrated_opponents"],
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
                        "Sim" if title["meets"] else "Não",
                        title["performance"],
                        self._format_report_number(title["average_opponent"]),
                        "OK" if title["meets"] else "; ".join(title["missing"]),
                    ]
                )
        return [
            ("Aviso", ["Observação"], notice_rows),
            (
                "Indicadores de norma por jogador",
                [
                    "Jogador",
                    "Sexo",
                    "Rp",
                    "Partidas",
                    "Média adv.",
                    "Outras federações",
                    "Titulados",
                    "Sem rating",
                    "Norma atingida",
                ],
                summary_rows,
            ),
            (
                "Detalhe por título",
                ["Jogador", "Título", "Atende?", "Rp da norma", "Ra da norma", "Pendências"],
                detail_rows,
            ),
        ]

    _ARBITER_ROLE_LABELS = {
        "chief": "Árbitro principal",
        "chief_arbiter": "Árbitro principal",
        "main": "Árbitro principal",
        "principal": "Árbitro principal",
        "deputy": "Árbitro adjunto",
        "sector": "Árbitro de setor",
        "arbiter": "Árbitro",
        "assistant": "Assistente",
    }

    def _arbiter_norm_sections(
        self, tournament_id: int
    ) -> list[tuple[str, list[str], list[list[Any]]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        rated = sum(1 for player in players if self._trf_rating(player) > 0)
        referees = self.db.list_tournament_referees(tournament_id)
        competition = "Equipes" if tournament.get("competition_type") == "team" else "Individual"

        notice_rows = [
            ["Documento de apoio para a norma de árbitro (IA/FA)."],
            ["Não e o formulário oficial da FIDE; use os dados abaixo para preenche-lo."],
        ]
        tournament_rows = [
            ["Torneio", tournament["name"]],
            ["Local", tournament.get("location", "")],
            ["Federação", settings.get("federation", "")],
            ["FIDE Event-ID", settings.get("fide_event_id", "")],
            ["Data de início", tournament.get("start_date", "")],
            ["Data de término", tournament.get("end_date", "")],
            ["Ritmo de jogo", tournament.get("time_control", "")],
            ["Rodadas", tournament.get("rounds_count", "")],
            ["Tipo", competition],
            ["Jogadores", len(players)],
            ["Jogadores com rating", rated],
            ["Organizador", settings.get("organizer", "")],
            ["Árbitro principal (config.)", settings.get("chief_arbiter", "")],
        ]

        arbiter_rows: list[list[Any]] = []
        for referee in referees:
            role = str(referee.get("role") or "").strip().lower()
            arbiter_rows.append(
                [
                    referee.get("name", ""),
                    self._ARBITER_ROLE_LABELS.get(role, role.replace("_", " ").title() or "Árbitro"),
                    referee.get("fide_id", ""),
                    referee.get("category", ""),
                    "",
                    "",
                ]
            )
        if not arbiter_rows:
            chief = str(settings.get("chief_arbiter") or "").strip()
            if chief:
                arbiter_rows.append([chief, "Árbitro principal", "", "", "", ""])
            for name in str(settings.get("arbiters") or "").replace(";", ",").split(","):
                cleaned = name.strip()
                if cleaned:
                    arbiter_rows.append([cleaned, "Árbitro", "", "", "", ""])

        return [
            ("Aviso", ["Observação"], notice_rows),
            ("Dados do torneio (norma de árbitro)", ["Campo", "Valor"], tournament_rows),
            (
                "Árbitros designados",
                ["Nome", "Função", "FIDE ID", "Categoria", "Norma (IA/FA)", "Assinatura"],
                arbiter_rows,
            ),
        ]

    def _category_winners_section(
        self, tournament_id: int, top_n: int = 3
    ) -> tuple[str, list[str], list[list[Any]]]:
        """Vencedores por categoria (top N de cada categoria, na ordem da classificação).

        Agrupa por TODAS as categorias premiáveis do jogador (ORG-01), e não
        mais só pela principal: era por isso que a jogadora Sub-10 não aparecia
        em classificação feminina nenhuma.
        """
        groups = group_by_category(self.pairing_service.standings(tournament_id))
        rows: list[list[Any]] = []
        for category in sorted(groups, key=str.casefold):
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
        """Secoes do boletim da rodada: cabecalho + resultados + classificação + destaques."""
        round_data = self.db.get_round(round_id)
        if not round_data:
            raise AppError("Rodada não encontrada.")
        tournament = self.db.get_tournament(int(round_data["tournament_id"]))
        if not tournament:
            raise AppError("Torneio não encontrado.")
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
        sections.append((f"Classificação após a rodada {number} (top 10)", headers, rows[:10]))
        if tournament.get("competition_type") != "team":
            sections.append(self._bulletin_highlights_section(round_id, int(tournament["id"])))
        return sections

    def _bulletin_highlights_section(
        self, round_id: int, tournament_id: int
    ) -> tuple[str, list[str], list[list[Any]]]:
        """Destaques da rodada (individual): líder, decisivas/empates e maior zebra."""
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
            rows.append(["Líder", f"{standings[0].get('name', '')} ({standings[0].get('points', '')} pts)"])
        rows.append(["Partidas decididas", decisive])
        rows.append(["Empates", draws])
        if best_upset:
            rows.append(["Maior zebra", f"{best_upset[0]} venceu {best_upset[1]} (+{best_upset[2]} de rating)"])
        return ("Destaques", ["Item", "Valor"], rows)

    def _podium_data(self, tournament_id: int) -> dict[str, Any]:
        """Dados do podio: top 3 (jogadores ou equipes) + campeoes por categoria."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
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
            # Campeão de cada categoria premiável (ORG-01): quem vem primeiro
            # na classificação geral dentro daquele grupo.
            categories = [
                {"category": name, "name": str(rows[0].get("name") or "")}
                for name, rows in sorted(
                    group_by_category(standings).items(), key=lambda pair: pair[0].casefold()
                )
                if rows
            ]
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
        document.drawCentredString(center, height - 116, "Premiação - Podio")
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
            document.drawCentredString(center, y, "Sem classificação disponível.")

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
        """Secoes da ata final: cabecalho + classificação + categorias + premiação + taxas + árbitros."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        players = self.db.list_players(tournament_id, active_only=False)
        rated = sum(1 for player in players if self._trf_rating(player) > 0)
        competition = "Equipes" if tournament.get("competition_type") == "team" else "Individual"

        header_rows = [
            ["Torneio", tournament["name"]],
            ["Local", tournament.get("location", "")],
            ["Federação", settings.get("federation", "")],
            ["FIDE Event-ID", settings.get("fide_event_id", "")],
            ["Data de início", tournament.get("start_date", "")],
            ["Data de término", tournament.get("end_date", "")],
            ["Ritmo de jogo", tournament.get("time_control", "")],
            ["Rodadas", tournament.get("rounds_count", "")],
            ["Tipo", competition],
            ["Jogadores", len(players)],
            ["Jogadores com rating", rated],
            ["Organizador", settings.get("organizer", "")],
            ["Diretor", settings.get("director", "")],
            ["Árbitro principal", settings.get("chief_arbiter", "")],
        ]

        referees = self.db.list_tournament_referees(tournament_id)
        arbiter_rows: list[list[Any]] = []
        for referee in referees:
            role = str(referee.get("role") or "").strip().lower()
            arbiter_rows.append(
                [
                    referee.get("name", ""),
                    self._ARBITER_ROLE_LABELS.get(role, role.replace("_", " ").title() or "Árbitro"),
                    referee.get("fide_id", ""),
                    referee.get("category", ""),
                    "",
                ]
            )
        if not arbiter_rows:
            chief = str(settings.get("chief_arbiter") or "").strip()
            if chief:
                arbiter_rows.append([chief, "Árbitro principal", "", "", ""])
            for name in str(settings.get("arbiters") or "").replace(";", ",").split(","):
                cleaned = name.strip()
                if cleaned:
                    arbiter_rows.append([cleaned, "Árbitro", "", "", ""])

        sections: list[tuple[str, list[str], list[list[Any]]]] = [
            ("Ata final do torneio", ["Campo", "Valor"], header_rows),
            self._standings_section(tournament_id),
        ]
        adjustments = self._point_adjustments_section(tournament_id)
        if adjustments:
            sections.append(adjustments)
        corrections = self._closed_round_corrections_section(tournament_id)
        if corrections:
            sections.append(corrections)
        participation = self._participation_section(tournament_id)
        if participation:
            sections.append(participation)
        incidents = self._incidents_section(tournament_id)
        if incidents:
            sections.append(incidents)
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
            ("Árbitros e assinaturas", ["Nome", "Função", "FIDE ID", "Categoria", "Assinatura"], arbiter_rows)
        )
        return sections

    def _incidents_section(
        self, tournament_id: int
    ) -> tuple[str, list[str], list[list[Any]]] | None:
        """Anexo disciplinar da ata (ARB-03). ``None`` quando nao houve incidente.

        A reincidencia sai marcada porque e ela que o catalogo existe para
        produzir: no papel, a segunda advertencia do mesmo artigo ao mesmo
        jogador nao era encontravel por ninguem.
        """
        incidentes = self.pairing_service.incidents(tournament_id)
        if not incidentes:
            return None
        reincidentes = self.pairing_service.incident_repeat_offenders(tournament_id)
        linhas = []
        for item in incidentes:
            player_id = int(item.get("player_id") or 0)
            total = reincidentes.get(player_id, 0)
            linhas.append(
                [
                    int(item.get("round_number") or 0) or "-",
                    int(item.get("board_number") or 0) or "-",
                    player_full_name(
                        {
                            "name": item.get("player_name"),
                            "surname": item.get("player_surname"),
                            "given_name": item.get("player_given_name"),
                        }
                    ),
                    incident_infraction_label(str(item.get("infraction") or "")),
                    incident_decision_label(str(item.get("decision") or "")),
                    f"{total}ª ocorrência" if total > 1 else "-",
                    str(item.get("notes") or ""),
                ]
            )
        return (
            "Incidentes disciplinares",
            ["Rodada", "Mesa", "Jogador", "Infração", "Decisão", "Reincidência", "Observações"],
            linhas,
        )

    def _participation_section(
        self, tournament_id: int
    ) -> tuple[str, list[str], list[list[Any]]] | None:
        """Desistencias, ausencias e reentradas, por rodada (ARB-05).

        O TRF nao tem codigo para separar "desistiu" de "faltou" — as duas viram
        `0000 - Z` (nao pareado, zero ponto), e isso esta certo: o que a FIDE
        distingue e `Z` de `-` (pareado e nao compareceu, que exige mesa). A
        diferenca entre desistencia e ausencia e do REGULAMENTO, e por isso ela
        mora aqui, no documento que o arbitro assina.
        """
        resumo = self.pairing_service.participation_summary(tournament_id)
        if not resumo:
            return None
        linhas = [
            [
                item["player_name"],
                PLAYER_STATUSES.get(item["final_status"], item["final_status"]),
                ", ".join(f"R{rodada}" for rodada in item["absence_rounds"]) or "-",
                item["summary"],
            ]
            for item in resumo
        ]
        return (
            "Desistências, ausências e reentradas",
            ["Jogador", "Situação final", "Rodadas fora", "Histórico"],
            linhas,
        )

    def _closed_round_corrections_section(
        self, tournament_id: int
    ) -> tuple[str, list[str], list[list[Any]]] | None:
        """Correções em rodada fechada, com motivo (ARB-01). ``None`` se não há.

        A trilha de auditoria já guarda cada correção, mas ela é uma tela de
        diagnóstico — quem revisa uma apelação lê a ata. Aqui a decisão aparece no
        documento que o árbitro assina: rodada, o que mudou e por quê.

        Sai da própria trilha (`result_corrected` e o equivalente de equipes) para
        não haver duas versões do mesmo fato em lugares diferentes.
        """
        eventos: list[dict[str, Any]] = []
        for action in ("result_corrected", "team_result_corrected"):
            eventos.extend(
                self.db.list_audit_events(tournament_id, action=action, limit=1000)
            )
        if not eventos:
            return None

        rodada_por_id = {
            int(item["id"]): int(item["number"]) for item in self.db.list_rounds(tournament_id)
        }
        eventos.sort(key=lambda item: str(item.get("created_at") or ""))
        rows = [
            [
                rodada_por_id.get(int(evento.get("round_id") or 0), ""),
                self._correction_result_change(evento),
                evento.get("actor", ""),
                evento.get("reason", ""),
                evento.get("created_at", ""),
            ]
            for evento in eventos
        ]
        return (
            "Correções em rodada fechada",
            ["Rodada", "Resultado", "Operador", "Motivo", "Registrado em"],
            rows,
        )

    @staticmethod
    def _correction_result_change(event: Mapping[str, Any]) -> str:
        """``"1-0 → 0-1"`` a partir do before/after do evento de auditoria."""
        def resultado(raw: Any) -> str:
            try:
                payload = json.loads(str(raw) or "{}")
            except (TypeError, ValueError):
                return "?"
            return str(payload.get("result") or "").strip() or "pendente"

        return f"{resultado(event.get('before_json'))} → {resultado(event.get('after_json'))}"

    def _point_adjustments_section(
        self, tournament_id: int
    ) -> tuple[str, list[str], list[list[Any]]] | None:
        """Ajustes de pontos do árbitro, com motivo (TBK-01). ``None`` se não há.

        A classificação mostra só o asterisco — o número somado já está lá. É
        aqui, na ata, que a decisão fica registrada por extenso: quem, quando,
        quanto e **por quê**. Seção omitida quando o torneio não teve ajuste,
        para não plantar na ata uma tabela vazia que sugere pendência.
        """
        adjustments = self.db.list_point_adjustments(tournament_id)
        if not adjustments:
            return None
        rows = [
            [
                adjustment.get("round_number") or "Todas",
                adjustment.get("player_name") or adjustment.get("team_name") or "—",
                adjustment.get("aat_type") or "—",
                format_signed(adjustment.get("match_points") or 0.0),
                format_signed(adjustment.get("game_points") or 0.0),
                adjustment.get("reason") or "",
                adjustment.get("created_at") or "",
            ]
            for adjustment in adjustments
        ]
        return (
            "Ajustes de pontos do árbitro (TRF25 §7.3)",
            ["Rodada", "Competidor", "Tipo", "Match points", "Game points", "Motivo", "Lançado em"],
            rows,
        )

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
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Este relatório esta disponível apenas para torneios por equipes.")
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
            ["ID", "Equipe", "Clube/Cidade", "Capitão", "Titulares", "Jogadores", "Status", "Observações"],
            rows,
        )

    def _team_rosters_section(self, tournament_id: int) -> tuple[str, list[str], list[list[Any]]]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Este relatório esta disponível apenas para torneios por equipes.")

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
            "Escalações",
            [
                "Equipe",
                "Tabuleiro",
                "Função",
                "Jogador",
                "Rating",
                "Clube",
                "Categoria",
                "Categoria idade",
                "Categoria rating",
                "Tags premiação",
                "Status",
            ],
            rows,
        )
