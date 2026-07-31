"""Mixin do nucleo de torneios da Database.

Torneios e configuracoes, premios, layouts de relatorio, agenda de rodadas,
ratings oficiais, jogadores, equipes, tabuleiros/escalacoes, ajustes de pontos,
byes e proibicoes, rodadas e pareamentos. Extraido de ``src.core.database`` na
decomposicao da God Class. Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from ._database_base import _DatabaseInfra
from .categories import competition_category_payload, reference_year


def default_pairing_system() -> str:
    """Motor de pareamento padrao para novos torneios.

    Producao usa o Gacrux (motor FIDE oficial). Lido em runtime para que os
    testes possam forcar o motor proprio via ALBERICUS_DEFAULT_PAIRING_SYSTEM
    (ver tests/conftest.py) — suite rapida e deterministica, sem subprocesso.
    """
    return os.environ.get("ALBERICUS_DEFAULT_PAIRING_SYSTEM", "gacrux_swiss")


def default_tiebreak_engine() -> str:
    """Motor de desempate/classificacao padrao para novos torneios.

    Producao usa o Gacrux (motor FIDE oficial, tiebreakchecker.py). Lido em
    runtime para que os testes possam forcar o motor proprio via
    ALBERICUS_DEFAULT_TIEBREAK_ENGINE (ver tests/conftest.py) — suite rapida e
    deterministica, sem subprocesso.
    """
    return os.environ.get("ALBERICUS_DEFAULT_TIEBREAK_ENGINE", "gacrux")


class TournamentCoreMixin(_DatabaseInfra):
    def create_tournament(
        self,
        name: str,
        club_id: int | None = 1,
        location: str = "",
        rounds_count: int = 5,
        time_control: str = "",
        start_date: str = "",
        end_date: str = "",
        bye_points: float = 1.0,
        class_id: int | None = None,
        competition_type: str = "individual",
    ) -> int:
        club_value = int(club_id) if club_id is not None else None
        class_value = int(class_id) if class_id is not None else None
        competition_value = competition_type.strip() or "individual"
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tournaments (
                    club_id, class_id, competition_type, name, location, start_date, end_date, system, rounds_count,
                    time_control, bye_points, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Suico', ?, ?, ?, 'draft', ?)
                """,
                (
                    club_value,
                    class_value,
                    competition_value,
                    name.strip(),
                    location.strip(),
                    start_date.strip(),
                    end_date.strip(),
                    int(rounds_count),
                    time_control.strip(),
                    float(bye_points),
                    self.now(),
                ),
            )
            tournament_id = int(cursor.lastrowid)
            self._ensure_tournament_settings(connection, tournament_id)
            self._ensure_round_schedule(connection, tournament_id, int(rounds_count))
            return tournament_id

    def update_tournament_status(self, tournament_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET status = ? WHERE id = ?",
                (status, tournament_id),
            )

    def update_tournament_details(
        self,
        tournament_id: int,
        name: str,
        club_id: int | None = None,
        location: str = "",
        rounds_count: int = 5,
        time_control: str = "",
        start_date: str = "",
        end_date: str = "",
        bye_points: float = 1.0,
        class_id: int | None = None,
        competition_type: str = "individual",
    ) -> None:
        club_value = int(club_id) if club_id is not None else None
        class_value = int(class_id) if class_id is not None else None
        competition_value = competition_type.strip() or "individual"
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tournaments
                SET club_id = ?, class_id = ?, competition_type = ?, name = ?, location = ?, start_date = ?, end_date = ?,
                    rounds_count = ?, time_control = ?, bye_points = ?
                WHERE id = ?
                """,
                (
                    club_value,
                    class_value,
                    competition_value,
                    name.strip(),
                    location.strip(),
                    start_date.strip(),
                    end_date.strip(),
                    int(rounds_count),
                    time_control.strip(),
                    float(bye_points),
                    tournament_id,
                ),
            )
            self._ensure_round_schedule(connection, tournament_id, int(rounds_count))
            connection.execute(
                """
                DELETE FROM round_schedule
                WHERE tournament_id = ? AND round_number > ?
                """,
                (tournament_id, int(rounds_count)),
            )

    def duplicate_tournament(self, source_tournament_id: int, new_name: str) -> int:
        with self.connect() as connection:
            source = connection.execute(
                """
                SELECT *
                FROM tournaments
                WHERE id = ?
                """,
                (source_tournament_id,),
            ).fetchone()
            if not source:
                raise ValueError("Torneio de origem nao encontrado.")

            cursor = connection.execute(
                """
                INSERT INTO tournaments (
                    club_id, class_id, competition_type, name, location, start_date, end_date, system, rounds_count,
                    time_control, bye_points, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
                """,
                (
                    source["club_id"],
                    source["class_id"],
                    source["competition_type"],
                    new_name.strip(),
                    source["location"],
                    source["start_date"],
                    source["end_date"],
                    source["system"],
                    source["rounds_count"],
                    source["time_control"],
                    source["bye_points"],
                    self.now(),
                ),
            )
            new_tournament_id = int(cursor.lastrowid)
            self._ensure_tournament_settings(connection, source_tournament_id)
            self._ensure_tournament_settings(connection, new_tournament_id)
            connection.execute(
                """
                UPDATE tournament_settings
                SET
                    fide_event_id = src.fide_event_id,
                    organizer = src.organizer,
                    website = src.website,
                    contact_email = src.contact_email,
                    director = src.director,
                    chief_arbiter = src.chief_arbiter,
                    arbiters = src.arbiters,
                    federation = src.federation,
                    state = src.state,
                    categories = src.categories,
                    cutoff_date = src.cutoff_date,
                    comments = src.comments,
                    prizes = src.prizes,
                    initial_order = src.initial_order,
                    tournament_type = src.tournament_type,
                    tournament_profile = src.tournament_profile,
                    free_mode = src.free_mode,
                    allow_public_registration = src.allow_public_registration,
                    allow_player_result_edit = src.allow_player_result_edit,
                    allow_dangerous_changes = src.allow_dangerous_changes,
                    disable_bye = src.disable_bye,
                    late_entry_points = src.late_entry_points,
                    accelerated_system = src.accelerated_system,
                    hide_standings = src.hide_standings,
                    calculate_performance = src.calculate_performance,
                    tiebreak_sequence = src.tiebreak_sequence,
                    prize_policy = src.prize_policy,
                    prize_tax_percent = src.prize_tax_percent,
                    pairing_method = src.pairing_method,
                    pairing_system = src.pairing_system,
                    acceleration_method = src.acceleration_method,
                    hide_color_names = src.hide_color_names,
                    show_opponents_in_standings = src.show_opponents_in_standings,
                    team_boards_count = src.team_boards_count,
                    team_match_win_points = src.team_match_win_points,
                    team_match_draw_points = src.team_match_draw_points,
                    team_match_loss_points = src.team_match_loss_points,
                    team_pairing_method = src.team_pairing_method,
                    team_standing_primary = src.team_standing_primary,
                    team_standing_secondary = src.team_standing_secondary,
                    team_tiebreak_sequence = src.team_tiebreak_sequence,
                    team_fixed_board_order = src.team_fixed_board_order,
                    team_board_order_policy = src.team_board_order_policy,
                    team_reserve_policy = src.team_reserve_policy,
                    team_lineup_deadline = src.team_lineup_deadline,
                    team_rating_tolerance = src.team_rating_tolerance,
                    team_max_substitutions = src.team_max_substitutions,
                    rating_fee_fide = src.rating_fee_fide,
                    rating_fee_cbx = src.rating_fee_cbx,
                    rating_fee_lbx = src.rating_fee_lbx,
                    archived = src.archived,
                    updated_at = ?
                FROM tournament_settings AS src
                WHERE tournament_settings.tournament_id = ?
                  AND src.tournament_id = ?
                """,
                (self.now(), new_tournament_id, source_tournament_id),
            )
            schedules = connection.execute(
                """
                SELECT round_number, date, time
                FROM round_schedule
                WHERE tournament_id = ?
                ORDER BY round_number
                """,
                (source_tournament_id,),
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        new_tournament_id,
                        int(row["round_number"]),
                        str(row["date"] or ""),
                        str(row["time"] or ""),
                        self.now(),
                    )
                    for row in schedules
                ],
            )
            prizes = connection.execute(
                """
                SELECT kind, label, category, rank_from, rank_to, amount, position
                FROM tournament_prizes
                WHERE tournament_id = ?
                ORDER BY position, id
                """,
                (source_tournament_id,),
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO tournament_prizes (
                    tournament_id, kind, label, category, rank_from, rank_to,
                    amount, position, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        new_tournament_id,
                        str(row["kind"] or "overall"),
                        str(row["label"] or ""),
                        str(row["category"] or ""),
                        int(row["rank_from"] or 1),
                        int(row["rank_to"] or row["rank_from"] or 1),
                        float(row["amount"] or 0.0),
                        int(row["position"] or 0),
                        self.now(),
                    )
                    for row in prizes
                ],
            )
            layouts = connection.execute(
                """
                SELECT report_key, columns_json
                FROM report_layouts
                WHERE tournament_id = ?
                """,
                (source_tournament_id,),
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO report_layouts (
                    tournament_id, report_key, columns_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        new_tournament_id,
                        str(row["report_key"] or ""),
                        str(row["columns_json"] or "[]"),
                        self.now(),
                    )
                    for row in layouts
                ],
            )
            return new_tournament_id

    def delete_tournament(self, tournament_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))

    def list_tournaments(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    t.*,
                    c.name AS club_name,
                    c.kind AS club_kind,
                    cl.name AS class_name
                FROM tournaments t
                LEFT JOIN clubs c ON c.id = t.club_id
                LEFT JOIN classes cl ON cl.id = t.class_id
                ORDER BY t.created_at DESC, t.id DESC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_tournament(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    t.*,
                    c.name AS club_name,
                    c.kind AS club_kind,
                    cl.name AS class_name
                FROM tournaments t
                LEFT JOIN clubs c ON c.id = t.club_id
                LEFT JOIN classes cl ON cl.id = t.class_id
                WHERE t.id = ?
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_tournament_settings(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            row = connection.execute(
                """
                SELECT *
                FROM tournament_settings
                WHERE tournament_id = ?
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def set_chess_results_url(self, tournament_id: int, url: str) -> None:
        """Guarda o link publicado do torneio no Chess-Results (Fase J)."""
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            connection.execute(
                "UPDATE tournament_settings SET chess_results_url = ?, updated_at = ? WHERE tournament_id = ?",
                ((url or "").strip(), self.now(), tournament_id),
            )

    def set_free_mode(self, tournament_id: int, enabled: bool) -> None:
        """Marca/desmarca o torneio como Modo Livre (fluxo 'Torneio | Modo Livre').

        Fonte unica de verdade do Modo Livre: as ferramentas pedagogicas
        (re-emparceiramento livre, entrada tardia flexivel) e o indicador de
        modo passam a depender desta marca, nao mais do perfil 'free' -- que e
        o default de qualquer torneio e por isso nao distingue o modo.
        """
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            connection.execute(
                "UPDATE tournament_settings SET free_mode = ?, updated_at = ? WHERE tournament_id = ?",
                (1 if enabled else 0, self.now(), tournament_id),
            )

    def save_tournament_settings(
        self,
        tournament_id: int,
        data: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            incoming = dict(data)
            current = connection.execute(
                """
                SELECT *
                FROM tournament_settings
                WHERE tournament_id = ?
                """,
                (tournament_id,),
            ).fetchone()
            merged = dict(current) if current else {}
            merged.update(incoming)
            data = merged
            connection.execute(
                """
                UPDATE tournament_settings
                SET fide_event_id = ?, organizer = ?, website = ?, contact_email = ?,
                    director = ?, chief_arbiter = ?, arbiters = ?, federation = ?,
                    state = ?, categories = ?, cutoff_date = ?, comments = ?,
                    prizes = ?, initial_order = ?, tournament_type = ?, tournament_profile = ?,
                    allow_public_registration = ?, allow_player_result_edit = ?,
                    allow_dangerous_changes = ?, disable_bye = ?,
                    late_entry_points = ?, accelerated_system = ?,
                    hide_standings = ?, calculate_performance = ?,
                    pairing_system = ?, tiebreak_engine = ?, tiebreak_strict = ?,
                    max_requested_byes = ?, last_requested_bye_round = ?,
                    acceleration_method = ?,
                    hide_color_names = ?, show_opponents_in_standings = ?,
                    tiebreak_sequence = ?, team_tiebreak_sequence = ?,
                    prize_policy = ?, prize_tax_percent = ?,
                    team_boards_count = ?, team_match_win_points = ?,
                    team_match_draw_points = ?, team_match_loss_points = ?,
                    team_pairing_method = ?, team_standing_primary = ?,
                    team_standing_secondary = ?, team_fixed_board_order = ?,
                    team_board_order_policy = ?, team_reserve_policy = ?,
                    team_lineup_deadline = ?, team_rating_tolerance = ?,
                    team_max_substitutions = ?,
                    rating_fee_fide = ?, rating_fee_cbx = ?, rating_fee_lbx = ?,
                    archived = ?, updated_at = ?
                WHERE tournament_id = ?
                """,
                (
                    str(data.get("fide_event_id", "")).strip(),
                    str(data.get("organizer", "")).strip(),
                    str(data.get("website", "")).strip(),
                    str(data.get("contact_email", "")).strip(),
                    str(data.get("director", "")).strip(),
                    str(data.get("chief_arbiter", "")).strip(),
                    str(data.get("arbiters", "")).strip(),
                    str(data.get("federation", "")).strip(),
                    str(data.get("state", "")).strip(),
                    str(data.get("categories", "")).strip(),
                    str(data.get("cutoff_date", "")).strip(),
                    str(data.get("comments", "")).strip(),
                    str(data.get("prizes", "")).strip(),
                    str(data.get("initial_order", "rating")).strip() or "rating",
                    str(data.get("tournament_type", "real")).strip() or "real",
                    str(data.get("tournament_profile", "free")).strip() or "free",
                    int(data.get("allow_public_registration", 0) or 0),
                    int(data.get("allow_player_result_edit", 0) or 0),
                    int(data.get("allow_dangerous_changes", 0) or 0),
                    int(data.get("disable_bye", 0) or 0),
                    float(data.get("late_entry_points", 0.0) or 0.0),
                    int(data.get("accelerated_system", 0) or 0),
                    int(data.get("hide_standings", 0) or 0),
                    int(data.get("calculate_performance", 0) or 0),
                    str(data.get("pairing_system", default_pairing_system())).strip() or default_pairing_system(),
                    str(data.get("tiebreak_engine", default_tiebreak_engine())).strip() or default_tiebreak_engine(),
                    int(data.get("tiebreak_strict", 0) or 0),
                    int(data.get("max_requested_byes", 0) or 0),
                    int(data.get("last_requested_bye_round", 0) or 0),
                    str(data.get("acceleration_method", "none")).strip() or "none",
                    int(data.get("hide_color_names", 0) or 0),
                    int(data.get("show_opponents_in_standings", 0) or 0),
                    str(data.get("tiebreak_sequence", "")),
                    str(data.get("team_tiebreak_sequence", "")),
                    str(data.get("prize_policy", "best_only")).strip() or "best_only",
                    float(data.get("prize_tax_percent", 0.0) or 0.0),
                    int(data.get("team_boards_count", 4) or 4),
                    float(data.get("team_match_win_points", 2.0) or 2.0),
                    float(data.get("team_match_draw_points", 1.0) or 1.0),
                    float(data.get("team_match_loss_points", 0.0) or 0.0),
                    str(data.get("team_pairing_method", "swiss")).strip() or "swiss",
                    str(data.get("team_standing_primary", "match_points")).strip() or "match_points",
                    str(data.get("team_standing_secondary", "game_points")).strip() or "game_points",
                    int(data.get("team_fixed_board_order", 1) or 0),
                    str(data.get("team_board_order_policy", "fixed")).strip() or "fixed",
                    str(data.get("team_reserve_policy", "same_team")).strip() or "same_team",
                    str(data.get("team_lineup_deadline", "")).strip(),
                    int(data.get("team_rating_tolerance", 0) or 0),
                    int(data.get("team_max_substitutions", 0) or 0),
                    float(data.get("rating_fee_fide", 0.0) or 0.0),
                    float(data.get("rating_fee_cbx", 0.0) or 0.0),
                    float(data.get("rating_fee_lbx", 0.0) or 0.0),
                    int(data.get("archived", 0) or 0),
                    self.now(),
                    tournament_id,
                ),
            )
            if "pairing_method" in incoming:
                connection.execute(
                    """
                    UPDATE tournament_settings
                    SET pairing_method = ?, updated_at = ?
                    WHERE tournament_id = ?
                    """,
                    (
                        str(data.get("pairing_method") or "swiss").strip() or "swiss",
                        self.now(),
                        tournament_id,
                    ),
                )

    def save_fide_rating_report(
        self,
        tournament_id: int,
        rating_type: str,
        rows: list[dict[str, Any]],
    ) -> None:
        """Persiste o relatorio de variacao de rating (idempotente por tipo)."""
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM fide_rating_reports WHERE tournament_id = ? AND rating_type = ?",
                (tournament_id, str(rating_type)),
            )
            connection.executemany(
                """
                INSERT INTO fide_rating_reports (
                    tournament_id, player_id, rating_type, ro, k, games_rated,
                    score, we, delta, rc, rp, n_over_400, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tournament_id,
                        int(row["player_id"]),
                        str(rating_type),
                        row.get("ro"),
                        row.get("k"),
                        row.get("games_rated"),
                        row.get("score"),
                        row.get("we"),
                        row.get("delta"),
                        row.get("rc"),
                        row.get("rp"),
                        row.get("n_over_400"),
                        now,
                    )
                    for row in rows
                ],
            )

    def get_fide_rating_report(
        self,
        tournament_id: int,
        rating_type: str = "fide",
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            report_rows = connection.execute(
                """
                SELECT f.*, p.name AS name, p.surname AS surname, p.given_name AS given_name
                FROM fide_rating_reports f
                LEFT JOIN players p ON p.id = f.player_id
                WHERE f.tournament_id = ? AND f.rating_type = ?
                ORDER BY (f.ro IS NULL), f.ro DESC, p.name COLLATE NOCASE
                """,
                (tournament_id, str(rating_type)),
            ).fetchall()
            return [dict(row) for row in report_rows]

    def list_tournament_prizes(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tournament_prizes
                WHERE tournament_id = ?
                ORDER BY position, id
                """,
                (tournament_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def replace_tournament_prizes(
        self,
        tournament_id: int,
        prizes: list[dict[str, Any]],
    ) -> None:
        """Substitui todos os premios do torneio (idempotente)."""
        now = self.now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM tournament_prizes WHERE tournament_id = ?",
                (tournament_id,),
            )
            connection.executemany(
                """
                INSERT INTO tournament_prizes (
                    tournament_id, kind, label, category, rank_from, rank_to,
                    amount, position, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tournament_id,
                        str(prize.get("kind") or "overall"),
                        str(prize.get("label") or ""),
                        str(prize.get("category") or ""),
                        int(prize.get("rank_from") or 1),
                        int(prize.get("rank_to") or prize.get("rank_from") or 1),
                        float(prize.get("amount") or 0.0),
                        index,
                        now,
                    )
                    for index, prize in enumerate(prizes)
                ],
            )

    def get_report_layout_columns(self, tournament_id: int, report_key: str) -> list[Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT columns_json FROM report_layouts WHERE tournament_id = ? AND report_key = ?",
                (tournament_id, str(report_key)),
            ).fetchone()
        if not row or not row["columns_json"]:
            return []
        try:
            data = json.loads(row["columns_json"])
        except (ValueError, TypeError):
            return []
        return list(data) if isinstance(data, list) else []

    def save_report_layout(self, tournament_id: int, report_key: str, columns: list[Any]) -> None:
        payload = json.dumps(list(columns), ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO report_layouts (tournament_id, report_key, columns_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tournament_id, report_key)
                DO UPDATE SET columns_json = excluded.columns_json, updated_at = excluded.updated_at
                """,
                (tournament_id, str(report_key), payload, self.now()),
            )

    def set_tournament_parent(self, tournament_id: int, parent_tournament_id: int | None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tournaments SET parent_tournament_id = ? WHERE id = ?",
                (parent_tournament_id, tournament_id),
            )

    def update_pairing_method(self, tournament_id: int, pairing_method: str) -> None:
        with self.connect() as connection:
            self._ensure_tournament_settings(connection, tournament_id)
            connection.execute(
                "UPDATE tournament_settings SET pairing_method = ?, updated_at = ? WHERE tournament_id = ?",
                (str(pairing_method), self.now(), tournament_id),
            )

    def set_player_scheveningen_group(self, player_id: int, group: str) -> None:
        value = str(group or "").strip().upper()
        if value not in ("", "A", "B"):
            value = ""
        with self.connect() as connection:
            connection.execute(
                "UPDATE players SET scheveningen_group = ? WHERE id = ?",
                (value, player_id),
            )

    def list_round_schedule(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self.get_tournament(tournament_id)
        if not tournament:
            return []
        with self.connect() as connection:
            self._ensure_round_schedule(
                connection,
                tournament_id,
                int(tournament["rounds_count"] or 0),
            )
            rows = connection.execute(
                """
                SELECT *
                FROM round_schedule
                WHERE tournament_id = ? AND round_number <= ?
                ORDER BY round_number ASC
                """,
                (tournament_id, int(tournament["rounds_count"] or 0)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def save_round_schedule(
        self,
        tournament_id: int,
        schedule: list[dict[str, Any]],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tournament_id, round_number) DO UPDATE SET
                    date = excluded.date,
                    time = excluded.time,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        tournament_id,
                        int(item["round_number"]),
                        str(item.get("date", "")).strip(),
                        str(item.get("time", "")).strip(),
                        self.now(),
                    )
                    for item in schedule
                ],
            )

    def create_official_rating_snapshot(
        self,
        source: str,
        list_date: str = "",
        file_name: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO official_rating_snapshots (
                    source, list_date, file_name, imported_count, imported_at
                ) VALUES (?, ?, ?, 0, ?)
                """,
                (source.strip().upper(), list_date.strip(), file_name.strip(), self.now()),
            )
            return int(cursor.lastrowid)

    def update_official_rating_snapshot_count(
        self,
        snapshot_id: int,
        imported_count: int,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE official_rating_snapshots
                SET imported_count = ?
                WHERE id = ?
                """,
                (int(imported_count), snapshot_id),
            )

    def create_official_rating_snapshot_with_players(
        self,
        source: str,
        list_date: str = "",
        file_name: str = "",
        players: list[dict[str, Any]] | None = None,
    ) -> int:
        source = source.strip().upper()
        rows = players or []
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO official_rating_snapshots (
                    source, list_date, file_name, imported_count, imported_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (source, list_date.strip(), file_name.strip(), len(rows), now),
            )
            snapshot_id = int(cursor.lastrowid)
            for player in rows:
                self._insert_official_player(
                    connection,
                    snapshot_id=snapshot_id,
                    source=source,
                    updated_at=now,
                    **player,
                )
            return snapshot_id

    def insert_official_player(
        self,
        snapshot_id: int,
        source: str,
        external_id: str,
        name: str,
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        fide_id: str = "",
        cbx_id: str = "",
        federation: str = "",
        club: str = "",
        birth_date: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        standard_rating: int = 0,
        rapid_rating: int = 0,
        blitz_rating: int = 0,
    ) -> int:
        with self.connect() as connection:
            return self._insert_official_player(
                connection,
                snapshot_id=snapshot_id,
                source=source,
                external_id=external_id,
                name=name,
                surname=surname,
                given_name=given_name,
                title=title,
                sex=sex,
                fide_id=fide_id,
                cbx_id=cbx_id,
                federation=federation,
                club=club,
                birth_date=birth_date,
                national_rating=national_rating,
                international_rating=international_rating,
                standard_rating=standard_rating,
                rapid_rating=rapid_rating,
                blitz_rating=blitz_rating,
                updated_at=self.now(),
            )

    @staticmethod
    def _insert_official_player(
        connection: sqlite3.Connection,
        snapshot_id: int,
        source: str,
        external_id: str,
        name: str,
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        fide_id: str = "",
        cbx_id: str = "",
        federation: str = "",
        club: str = "",
        birth_date: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        standard_rating: int = 0,
        rapid_rating: int = 0,
        blitz_rating: int = 0,
        updated_at: str = "",
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO official_players (
                snapshot_id, source, external_id, fide_id, cbx_id, name,
                surname, given_name, title, sex, federation, club, birth_date,
                national_rating, international_rating, standard_rating,
                rapid_rating, blitz_rating, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                source.strip().upper(),
                external_id.strip(),
                fide_id.strip(),
                cbx_id.strip(),
                name.strip(),
                surname.strip(),
                given_name.strip(),
                title.strip(),
                sex.strip(),
                federation.strip(),
                club.strip(),
                birth_date.strip(),
                int(national_rating or 0),
                int(international_rating or 0),
                int(standard_rating or 0),
                int(rapid_rating or 0),
                int(blitz_rating or 0),
                updated_at,
            ),
        )
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Falha ao inserir jogador oficial.")
        return int(lastrowid)

    def find_latest_official_player(
        self,
        fide_id: str = "",
        cbx_id: str = "",
        lbx_id: str = "",
    ) -> dict[str, Any] | None:
        conditions = []
        params: list[Any] = []
        if fide_id:
            conditions.append("op.fide_id = ?")
            params.append(fide_id.strip())
        if cbx_id:
            conditions.append("op.cbx_id = ?")
            params.append(cbx_id.strip())
        if lbx_id:
            # A lista LBX guarda o ID_No (registro proprio) em external_id.
            conditions.append("(op.source = 'LBX' AND op.external_id = ?)")
            params.append(lbx_id.strip())
        if not conditions:
            return None
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    op.*,
                    ors.list_date,
                    ors.imported_at,
                    ors.file_name
                FROM official_players op
                JOIN official_rating_snapshots ors ON ors.id = op.snapshot_id
                WHERE {" OR ".join(conditions)}
                ORDER BY ors.imported_at DESC, op.id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            return dict(row) if row else None

    def search_official_players(
        self,
        query: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        value = query.strip()
        if not value:
            return []
        like = f"%{value}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    op.*,
                    ors.list_date,
                    ors.imported_at,
                    ors.file_name
                FROM official_players op
                JOIN official_rating_snapshots ors ON ors.id = op.snapshot_id
                WHERE op.name LIKE ?
                    OR op.fide_id LIKE ?
                    OR op.cbx_id LIKE ?
                    OR op.external_id LIKE ?
                ORDER BY ors.imported_at DESC, op.name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (like, like, like, like, int(limit)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_player_official_data(
        self,
        player_id: int,
        data: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            current = connection.execute(
                "SELECT * FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if not current:
                return

            def pick(field: str) -> Any:
                value = data.get(field)
                if value not in (None, ""):
                    return value
                return current[field]

            def pick_int(field: str) -> int:
                value = data.get(field)
                if value in (None, ""):
                    value = current[field]
                return int(value or 0)

            rating = pick_int("rating")
            national_rating = pick_int("national_rating")
            international_rating = pick_int("international_rating")
            category_payload = self._player_category_payload(
                connection,
                tournament_id=int(current["tournament_id"]),
                member_id=int(current["member_id"] or 0) or None,
                birth_date=pick("birth_date"),
                rating=rating,
                national_rating=national_rating,
                international_rating=international_rating,
                category=current["category"],
                sex=pick("sex"),
                club=pick("club"),
            )

            connection.execute(
                """
                UPDATE players
                SET name = ?, surname = ?, given_name = ?, title = ?, sex = ?,
                    club = ?, federation_id = ?, fide_id = ?, cbx_id = ?, lbx_id = ?,
                    rating = ?, national_rating = ?, international_rating = ?,
                    category = ?, age_category = ?, rating_category = ?,
                    prize_tags = ?, birth_date = ?
                WHERE id = ?
                """,
                (
                    pick("name"),
                    pick("surname"),
                    pick("given_name"),
                    pick("title"),
                    pick("sex"),
                    pick("club"),
                    pick("federation_id"),
                    pick("fide_id"),
                    pick("cbx_id"),
                    pick("lbx_id"),
                    rating,
                    national_rating,
                    international_rating,
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    pick("birth_date"),
                    player_id,
                ),
            )

    def _player_category_payload(
        self,
        connection: sqlite3.Connection,
        *,
        tournament_id: int,
        member_id: int | None,
        birth_date: str,
        rating: int,
        national_rating: int = 0,
        international_rating: int = 0,
        category: str = "",
        sex: str = "",
        club: str = "",
    ) -> dict[str, str]:
        tournament_row = connection.execute(
            "SELECT * FROM tournaments WHERE id = ?",
            (tournament_id,),
        ).fetchone()
        tournament = dict(tournament_row) if tournament_row else {}
        tournament_club: dict[str, Any] = {}
        if tournament.get("club_id"):
            club_row = connection.execute(
                "SELECT * FROM clubs WHERE id = ?",
                (int(tournament["club_id"]),),
            ).fetchone()
            tournament_club = dict(club_row) if club_row else {}

        member: dict[str, Any] = {}
        if member_id:
            member_row = connection.execute(
                "SELECT * FROM members WHERE id = ?",
                (member_id,),
            ).fetchone()
            member = dict(member_row) if member_row else {}

        effective_rating = int(rating or 0) or max(int(national_rating or 0), int(international_rating or 0))
        return competition_category_payload(
            birth_date=birth_date,
            rating=effective_rating,
            category=category,
            year=reference_year(tournament),
            sex=sex,
            member_type=member.get("member_type", ""),
            city=member.get("city", ""),
            player_club=club,
            tournament_location=tournament.get("location", ""),
            tournament_club_name=tournament_club.get("name", ""),
            tournament_club_city=tournament_club.get("city", ""),
        )

    def create_player(
        self,
        tournament_id: int,
        name: str,
        club: str = "",
        rating: int = 0,
        category: str = "",
        federation_id: str = "",
        fide_id: str = "",
        birth_date: str = "",
        member_id: int | None = None,
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        cbx_id: str = "",
        lbx_id: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        player_status: str = "active",
        starting_points: float | None = None,
    ) -> int:
        with self.connect() as connection:
            if starting_points is None:
                starting_points = self._late_entry_starting_points(connection, tournament_id)
            category_payload = self._player_category_payload(
                connection,
                tournament_id=tournament_id,
                member_id=member_id,
                birth_date=birth_date,
                rating=rating,
                national_rating=national_rating,
                international_rating=international_rating,
                category=category,
                sex=sex,
                club=club,
            )
            active = 1 if player_status == "active" else 0
            cursor = connection.execute(
                """
                INSERT INTO players (
                    tournament_id, member_id, name, surname, given_name, title, sex,
                    club, federation_id, fide_id, cbx_id, lbx_id, rating, national_rating,
                    international_rating, category, age_category, rating_category,
                    prize_tags, birth_date, player_status, starting_points, active,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    member_id,
                    name.strip(),
                    surname.strip(),
                    given_name.strip(),
                    title.strip(),
                    sex.strip(),
                    club.strip(),
                    federation_id.strip(),
                    fide_id.strip(),
                    cbx_id.strip(),
                    lbx_id.strip(),
                    int(rating or 0),
                    int(national_rating or 0),
                    int(international_rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    birth_date.strip(),
                    player_status.strip() or "active",
                    float(starting_points or 0.0),
                    active,
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def update_player(
        self,
        player_id: int,
        name: str,
        club: str,
        rating: int,
        category: str,
        active: int,
        federation_id: str = "",
        fide_id: str = "",
        birth_date: str = "",
        surname: str = "",
        given_name: str = "",
        title: str = "",
        sex: str = "",
        cbx_id: str = "",
        lbx_id: str = "",
        national_rating: int = 0,
        international_rating: int = 0,
        player_status: str | None = None,
        starting_points: float | None = None,
    ) -> None:
        status = (player_status or ("active" if active else "inactive")).strip() or "active"
        active_value = 1 if status == "active" else 0
        with self.connect() as connection:
            current = connection.execute(
                "SELECT tournament_id, member_id, starting_points FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            category_payload = self._player_category_payload(
                connection,
                tournament_id=int(current["tournament_id"] if current else 0),
                member_id=int(current["member_id"] or 0) if current else None,
                birth_date=birth_date,
                rating=rating,
                national_rating=national_rating,
                international_rating=international_rating,
                category=category,
                sex=sex,
                club=club,
            )
            points_value = (
                float(starting_points)
                if starting_points is not None
                else float(current["starting_points"] if current else 0.0)
            )
            connection.execute(
                """
                UPDATE players
                SET name = ?, surname = ?, given_name = ?, title = ?, sex = ?,
                    club = ?, federation_id = ?, fide_id = ?, cbx_id = ?, lbx_id = ?,
                    rating = ?, national_rating = ?, international_rating = ?,
                    category = ?, age_category = ?, rating_category = ?,
                    prize_tags = ?, birth_date = ?, player_status = ?,
                    starting_points = ?, active = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    surname.strip(),
                    given_name.strip(),
                    title.strip(),
                    sex.strip(),
                    club.strip(),
                    federation_id.strip(),
                    fide_id.strip(),
                    cbx_id.strip(),
                    lbx_id.strip(),
                    int(rating or 0),
                    int(national_rating or 0),
                    int(international_rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    birth_date.strip(),
                    status,
                    points_value,
                    active_value,
                    player_id,
                ),
            )

    def list_players(
        self,
        tournament_id: int,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        where = "WHERE p.tournament_id = ?"
        params: list[Any] = [tournament_id]
        if active_only:
            where += " AND p.active = 1 AND p.player_status = 'active'"
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    p.*,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM players p
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = p.member_id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                {where}
                ORDER BY p.active DESC, p.rating DESC, p.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_team(
        self,
        tournament_id: int,
        name: str,
        club: str = "",
        captain: str = "",
        notes: str = "",
        active: int = 1,
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO teams (
                    tournament_id, name, club, captain, notes, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    name.strip(),
                    club.strip(),
                    captain.strip(),
                    notes.strip(),
                    int(active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_team(
        self,
        team_id: int,
        name: str,
        club: str = "",
        captain: str = "",
        notes: str = "",
        active: int = 1,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE teams
                SET name = ?, club = ?, captain = ?, notes = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    club.strip(),
                    captain.strip(),
                    notes.strip(),
                    int(active),
                    self.now(),
                    team_id,
                ),
            )

    def get_team(self, team_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tm.*,
                    t.name AS tournament_name,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1
                    ) AS players_count,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1 AND tp.role = 'starter'
                    ) AS starters_count
                FROM teams tm
                JOIN tournaments t ON t.id = tm.tournament_id
                WHERE tm.id = ?
                """,
                (team_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_teams(
        self,
        tournament_id: int,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        active_filter = "AND tm.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tm.*,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1
                    ) AS players_count,
                    (
                        SELECT COUNT(*)
                        FROM team_players tp
                        WHERE tp.team_id = tm.id AND tp.active = 1 AND tp.role = 'starter'
                    ) AS starters_count
                FROM teams tm
                WHERE tm.tournament_id = ?
                {active_filter}
                ORDER BY tm.active DESC, tm.name COLLATE NOCASE ASC, tm.id ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_team(self, team_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM teams
                WHERE id = ?
                """,
                (team_id,),
            )

    def count_team_matches(self, team_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM team_matches
                WHERE white_team_id = ? OR black_team_id = ?
                """,
                (team_id, team_id),
            ).fetchone()
            return int(row["total"] if row else 0)

    def add_player_to_team(
        self,
        team_id: int,
        player_id: int,
        board_number: int | None = None,
        role: str = "starter",
        active: int = 1,
    ) -> int:
        board_value = int(board_number) if board_number and int(board_number) > 0 else None
        role_value = role.strip() or ("reserve" if board_value is None else "starter")
        now = self.now()
        with self.connect() as connection:
            team = connection.execute(
                "SELECT tournament_id FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()
            if not team:
                raise ValueError("Equipe nao encontrada.")

            player = connection.execute(
                "SELECT tournament_id FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if not player:
                raise ValueError("Jogador nao encontrado.")
            if int(team["tournament_id"]) != int(player["tournament_id"]):
                raise ValueError("Jogador nao pertence ao torneio da equipe.")

            cursor = connection.execute(
                """
                INSERT INTO team_players (
                    team_id, player_id, board_number, role, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_id,
                    player_id,
                    board_value,
                    role_value,
                    int(active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_team_player(
        self,
        team_player_id: int,
        board_number: int | None = None,
        role: str = "starter",
        active: int = 1,
    ) -> None:
        board_value = int(board_number) if board_number and int(board_number) > 0 else None
        role_value = role.strip() or ("reserve" if board_value is None else "starter")
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE team_players
                SET board_number = ?, role = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    board_value,
                    role_value,
                    int(active),
                    self.now(),
                    team_player_id,
                ),
            )

    def list_team_players(
        self,
        team_id: int,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        active_filter = "AND tp.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tp.*,
                    p.tournament_id,
                    p.name AS player_name,
                    p.surname AS player_surname,
                    p.given_name AS player_given_name,
                    p.rating AS player_rating,
                    p.club AS player_club,
                    p.category AS player_category,
                    p.age_category AS player_age_category,
                    p.rating_category AS player_rating_category,
                    p.prize_tags AS player_prize_tags,
                    p.player_status
                FROM team_players tp
                JOIN players p ON p.id = tp.player_id
                WHERE tp.team_id = ?
                {active_filter}
                ORDER BY
                    CASE WHEN tp.board_number IS NULL THEN 9999 ELSE tp.board_number END ASC,
                    tp.role ASC,
                    p.rating DESC,
                    p.name COLLATE NOCASE ASC
                """,
                (team_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_team_player(self, team_player_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tp.*,
                    tm.tournament_id,
                    tm.name AS team_name,
                    p.name AS player_name,
                    p.surname AS player_surname,
                    p.given_name AS player_given_name,
                    p.rating AS player_rating,
                    p.club AS player_club
                FROM team_players tp
                JOIN teams tm ON tm.id = tp.team_id
                JOIN players p ON p.id = tp.player_id
                WHERE tp.id = ?
                """,
                (team_player_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_team_player_by_player(self, player_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tp.*,
                    tm.tournament_id,
                    tm.name AS team_name
                FROM team_players tp
                JOIN teams tm ON tm.id = tp.team_id
                WHERE tp.player_id = ?
                """,
                (player_id,),
            ).fetchone()
            return dict(row) if row else None

    def remove_player_from_team(self, team_player_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM team_players
                WHERE id = ?
                """,
                (team_player_id,),
            )

    def get_player(self, player_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    p.*,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM players p
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = p.member_id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE p.id = ?
                """,
                (player_id,),
            ).fetchone()
            return dict(row) if row else None

    def set_player_active(self, player_id: int, active: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE players
                SET active = ?, player_status = ?
                WHERE id = ?
                """,
                (1 if active else 0, "active" if active else "inactive", player_id),
            )

    def set_player_status(self, player_id: int, status: str) -> None:
        status = status.strip() or "active"
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE players
                SET player_status = ?, active = ?
                WHERE id = ?
                """,
                (status, 1 if status == "active" else 0, player_id),
            )

    def count_player_pairings(self, player_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM pairings
                WHERE white_player_id = ? OR black_player_id = ?
                """,
                (player_id, player_id),
            ).fetchone()
            return int(row["total"] if row else 0)

    def delete_player(self, player_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM players
                WHERE id = ?
                """,
                (player_id,),
            )

    def get_pairing(self, pairing_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    p.*,
                    r.tournament_id,
                    r.number AS round_number,
                    r.status AS round_status
                FROM pairings p
                JOIN rounds r ON r.id = p.round_id
                WHERE p.id = ?
                """,
                (pairing_id,),
            ).fetchone()
            return dict(row) if row else None

    def create_round_with_team_matches(
        self,
        tournament_id: int,
        round_number: int,
        matches: list[dict[str, Any]],
        pairing_engine_version: str = "albericus-team-swiss-1",
        ruleset_version: str = "albericus-2026-phase0",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rounds (
                    tournament_id, number, status, pairing_engine_version,
                    ruleset_version, created_at
                )
                VALUES (?, ?, 'generated', ?, ?, ?)
                """,
                (tournament_id, round_number, pairing_engine_version, ruleset_version, now),
            )
            round_id = int(cursor.lastrowid)
            for match in matches:
                match_cursor = connection.execute(
                    """
                    INSERT INTO team_matches (
                        round_id, match_number, white_team_id, black_team_id, result,
                        white_match_points, black_match_points, white_game_points,
                        black_game_points, is_bye, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        int(match["match_number"]),
                        int(match["white_team_id"]),
                        match.get("black_team_id"),
                        str(match.get("result", "")),
                        float(match.get("white_match_points", 0.0) or 0.0),
                        float(match.get("black_match_points", 0.0) or 0.0),
                        float(match.get("white_game_points", 0.0) or 0.0),
                        float(match.get("black_game_points", 0.0) or 0.0),
                        1 if match.get("is_bye") else 0,
                        now,
                        now,
                    ),
                )
                team_match_id = int(match_cursor.lastrowid)
                for board in match.get("boards", []) or []:
                    connection.execute(
                        """
                        INSERT INTO team_boards (
                            team_match_id, board_number, white_player_id, black_player_id,
                            result, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            team_match_id,
                            int(board["board_number"]),
                            board.get("white_player_id"),
                            board.get("black_player_id"),
                            str(board.get("result", "")),
                            now,
                            now,
                        ),
                    )
            return round_id

    def list_team_matches_for_round(self, round_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tm.*,
                    r.tournament_id,
                    r.number AS round_number,
                    r.status AS round_status,
                    white_team.name AS white_team_name,
                    white_team.club AS white_team_club,
                    black_team.name AS black_team_name,
                    black_team.club AS black_team_club
                FROM team_matches tm
                JOIN rounds r ON r.id = tm.round_id
                JOIN teams white_team ON white_team.id = tm.white_team_id
                LEFT JOIN teams black_team ON black_team.id = tm.black_team_id
                WHERE tm.round_id = ?
                ORDER BY tm.match_number ASC
                """,
                (round_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_matches_for_tournament(
        self,
        tournament_id: int,
        closed_only: bool = False,
    ) -> list[dict[str, Any]]:
        status_filter = "AND r.status = 'closed'" if closed_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tm.*,
                    r.number AS round_number,
                    r.status AS round_status,
                    white_team.name AS white_team_name,
                    black_team.name AS black_team_name
                FROM team_matches tm
                JOIN rounds r ON r.id = tm.round_id
                JOIN teams white_team ON white_team.id = tm.white_team_id
                LEFT JOIN teams black_team ON black_team.id = tm.black_team_id
                WHERE r.tournament_id = ?
                {status_filter}
                ORDER BY r.number ASC, tm.match_number ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_board_results(
        self,
        tournament_id: int,
        closed_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Resultados de tabuleiro do torneio, com a equipe de CADA cor (TBK-05).

        O board count precisa saber quem pontuou em cada tabuleiro, e a equipe
        vem do elenco do jogador, nao do lado do confronto: tabuleiros pares tem
        as cores invertidas e um jogador pode ter sido substituido. E a mesma
        regra que `team_match_result` usa para somar os game points — se aqui
        fosse por paridade, a soma por tabuleiro poderia nao fechar com o total
        do confronto.
        """
        status_filter = "AND r.status = 'closed'" if closed_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tb.team_match_id,
                    tb.board_number,
                    tb.result,
                    r.number AS round_number,
                    tm.is_bye,
                    white_team.team_id AS white_team_id,
                    black_team.team_id AS black_team_id
                FROM team_boards tb
                JOIN team_matches tm ON tm.id = tb.team_match_id
                JOIN rounds r ON r.id = tm.round_id
                LEFT JOIN team_players white_team ON white_team.player_id = tb.white_player_id
                LEFT JOIN team_players black_team ON black_team.player_id = tb.black_player_id
                WHERE r.tournament_id = ?
                {status_filter}
                ORDER BY r.number ASC, tm.match_number ASC, tb.board_number ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_boards(self, team_match_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tb.*,
                    white.name AS white_player_name,
                    white.surname AS white_player_surname,
                    white.given_name AS white_player_given_name,
                    white.rating AS white_player_rating,
                    white.club AS white_player_club,
                    white.fide_id AS white_player_fide_id,
                    white.cbx_id AS white_player_cbx_id,
                    white.lbx_id AS white_player_lbx_id,
                    black.name AS black_player_name,
                    black.surname AS black_player_surname,
                    black.given_name AS black_player_given_name,
                    black.rating AS black_player_rating,
                    black.club AS black_player_club,
                    black.fide_id AS black_player_fide_id,
                    black.cbx_id AS black_player_cbx_id,
                    black.lbx_id AS black_player_lbx_id
                FROM team_boards tb
                LEFT JOIN players white ON white.id = tb.white_player_id
                LEFT JOIN players black ON black.id = tb.black_player_id
                WHERE tb.team_match_id = ?
                ORDER BY tb.board_number ASC
                """,
                (team_match_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_team_board(self, team_board_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tb.*,
                    tm.round_id,
                    tm.white_team_id,
                    tm.black_team_id,
                    tm.is_bye,
                    r.tournament_id,
                    r.status AS round_status
                FROM team_boards tb
                JOIN team_matches tm ON tm.id = tb.team_match_id
                JOIN rounds r ON r.id = tm.round_id
                WHERE tb.id = ?
                """,
                (team_board_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_team_board_result(self, team_board_id: int, result: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE team_boards
                SET result = ?, updated_at = ?
                WHERE id = ?
                """,
                (result.strip(), self.now(), team_board_id),
            )

    def swap_team_board_colors(self, team_board_id: int) -> None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT white_player_id, black_player_id
                FROM team_boards
                WHERE id = ?
                """,
                (team_board_id,),
            ).fetchone()
            if not row or row["white_player_id"] is None or row["black_player_id"] is None:
                return
            connection.execute(
                """
                UPDATE team_boards
                SET white_player_id = ?, black_player_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (row["black_player_id"], row["white_player_id"], self.now(), team_board_id),
            )

    def update_team_board_players(
        self,
        updates: list[tuple[int, int | None, int | None]],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                UPDATE team_boards
                SET white_player_id = ?, black_player_id = ?, updated_at = ?
                WHERE id = ?
                """,
                [
                    (white_player_id, black_player_id, self.now(), team_board_id)
                    for team_board_id, white_player_id, black_player_id in updates
                ],
            )

    def create_team_lineups_from_round(self, round_id: int) -> None:
        with self.connect() as connection:
            round_row = connection.execute(
                "SELECT tournament_id, number FROM rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
            if not round_row:
                return
            now = self.now()
            team_players = {
                int(row["player_id"]): {
                    "team_id": int(row["team_id"]),
                    "role": str(row["role"] or "starter"),
                }
                for row in connection.execute(
                    """
                    SELECT tp.team_id, tp.player_id, tp.role
                    FROM team_players tp
                    JOIN teams tm ON tm.id = tp.team_id
                    WHERE tm.tournament_id = ?
                    """,
                    (int(round_row["tournament_id"]),),
                ).fetchall()
            }
            matches = connection.execute(
                """
                SELECT *
                FROM team_matches
                WHERE round_id = ?
                ORDER BY match_number ASC
                """,
                (round_id,),
            ).fetchall()
            for match in matches:
                team_ids = [int(match["white_team_id"])]
                if match["black_team_id"]:
                    team_ids.append(int(match["black_team_id"]))
                lineup_ids: dict[int, int] = {}
                for team_id in team_ids:
                    cursor = connection.execute(
                        """
                        INSERT INTO team_lineups (
                            tournament_id, round_id, team_match_id, team_id,
                            status, submitted_at, approved_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?, ?)
                        ON CONFLICT(round_id, team_match_id, team_id) DO UPDATE SET
                            status = excluded.status,
                            approved_at = excluded.approved_at,
                            updated_at = excluded.updated_at
                        """,
                        (
                            int(round_row["tournament_id"]),
                            int(round_id),
                            int(match["id"]),
                            team_id,
                            now,
                            now,
                            now,
                            now,
                        ),
                    )
                    lineup_row = connection.execute(
                        """
                        SELECT id
                        FROM team_lineups
                        WHERE round_id = ? AND team_match_id = ? AND team_id = ?
                        """,
                        (int(round_id), int(match["id"]), team_id),
                    ).fetchone()
                    lineup_ids[team_id] = int(lineup_row["id"] if lineup_row else cursor.lastrowid)
                    connection.execute("DELETE FROM team_lineup_boards WHERE lineup_id = ?", (lineup_ids[team_id],))

                boards = connection.execute(
                    """
                    SELECT *
                    FROM team_boards
                    WHERE team_match_id = ?
                    ORDER BY board_number ASC
                    """,
                    (int(match["id"]),),
                ).fetchall()
                for board in boards:
                    for color, player_id in (
                        ("white", board["white_player_id"]),
                        ("black", board["black_player_id"]),
                    ):
                        if not player_id:
                            continue
                        assignment = team_players.get(int(player_id))
                        if not assignment or assignment["team_id"] not in lineup_ids:
                            continue
                        connection.execute(
                            """
                            INSERT INTO team_lineup_boards (
                                lineup_id, board_number, player_id, color, role, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                lineup_ids[assignment["team_id"]],
                                int(board["board_number"]),
                                int(player_id),
                                color,
                                assignment["role"],
                                now,
                            ),
                        )

    def list_team_lineups(self, tournament_id: int, round_id: int | None = None) -> list[dict[str, Any]]:
        conditions = ["tl.tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            conditions.append("tl.round_id = ?")
            params.append(int(round_id))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tl.*,
                    r.number AS round_number,
                    tm.match_number,
                    t.name AS team_name,
                    t.club AS team_club
                FROM team_lineups tl
                JOIN rounds r ON r.id = tl.round_id
                JOIN team_matches tm ON tm.id = tl.team_match_id
                JOIN teams t ON t.id = tl.team_id
                WHERE {' AND '.join(conditions)}
                ORDER BY r.number ASC, tm.match_number ASC, t.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_team_lineup_boards(self, lineup_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    tlb.*,
                    p.name AS player_name,
                    p.surname AS player_surname,
                    p.given_name AS player_given_name,
                    p.rating AS player_rating
                FROM team_lineup_boards tlb
                LEFT JOIN players p ON p.id = tlb.player_id
                WHERE tlb.lineup_id = ?
                ORDER BY tlb.board_number ASC
                """,
                (int(lineup_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def replace_team_lineup_board_player(
        self,
        round_id: int,
        team_match_id: int,
        team_id: int,
        board_number: int,
        player_id: int,
        color: str,
    ) -> None:
        with self.connect() as connection:
            lineup = connection.execute(
                """
                SELECT id
                FROM team_lineups
                WHERE round_id = ? AND team_match_id = ? AND team_id = ?
                """,
                (int(round_id), int(team_match_id), int(team_id)),
            ).fetchone()
            if not lineup:
                return
            connection.execute(
                """
                INSERT INTO team_lineup_boards (
                    lineup_id, board_number, player_id, color, role, created_at
                ) VALUES (?, ?, ?, ?, 'reserve', ?)
                ON CONFLICT(lineup_id, board_number) DO UPDATE SET
                    player_id = excluded.player_id,
                    color = excluded.color,
                    role = excluded.role
                """,
                (int(lineup["id"]), int(board_number), int(player_id), color, self.now()),
            )

    def create_team_substitution_event(
        self,
        tournament_id: int,
        round_id: int,
        team_match_id: int,
        team_board_id: int,
        team_id: int,
        board_number: int,
        color: str,
        out_player_id: int | None,
        in_player_id: int,
        reason: str = "",
        requires_correction: bool = False,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO team_substitution_events (
                    tournament_id, round_id, team_match_id, team_board_id, team_id,
                    board_number, color, out_player_id, in_player_id, reason,
                    requires_correction, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(round_id),
                    int(team_match_id),
                    int(team_board_id),
                    int(team_id),
                    int(board_number),
                    color,
                    out_player_id,
                    int(in_player_id),
                    reason.strip(),
                    1 if requires_correction else 0,
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_team_substitution_events(self, tournament_id: int, round_id: int | None = None) -> list[dict[str, Any]]:
        conditions = ["tse.tournament_id = ?"]
        params: list[Any] = [int(tournament_id)]
        if round_id is not None:
            conditions.append("tse.round_id = ?")
            params.append(int(round_id))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    tse.*,
                    r.number AS round_number,
                    tm.match_number,
                    team.name AS team_name,
                    out_player.name AS out_player_name,
                    in_player.name AS in_player_name
                FROM team_substitution_events tse
                JOIN rounds r ON r.id = tse.round_id
                JOIN team_matches tm ON tm.id = tse.team_match_id
                JOIN teams team ON team.id = tse.team_id
                LEFT JOIN players out_player ON out_player.id = tse.out_player_id
                JOIN players in_player ON in_player.id = tse.in_player_id
                WHERE {' AND '.join(conditions)}
                ORDER BY tse.created_at ASC, tse.id ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def add_point_adjustment(
        self,
        tournament_id: int,
        *,
        round_number: int = 0,
        player_id: int | None = None,
        team_id: int | None = None,
        aat_type: str = "",
        match_points: float = 0.0,
        game_points: float = 0.0,
        reason: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO point_adjustments (
                    tournament_id, round_number, player_id, team_id,
                    aat_type, match_points, game_points, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(round_number or 0),
                    int(player_id) if player_id else None,
                    int(team_id) if team_id else None,
                    str(aat_type or "").strip(),
                    float(match_points or 0.0),
                    float(game_points or 0.0),
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_point_adjustments(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pa.*, p.name AS player_name, t.name AS team_name
                FROM point_adjustments pa
                LEFT JOIN players p ON p.id = pa.player_id
                LEFT JOIN teams t ON t.id = pa.team_id
                WHERE pa.tournament_id = ?
                ORDER BY pa.round_number ASC, pa.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_point_adjustment(self, adjustment_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM point_adjustments WHERE id = ?", (int(adjustment_id),)
            )

    def add_prohibited_pairing(
        self,
        tournament_id: int,
        player_a_id: int,
        player_b_id: int,
        *,
        first_round: int = 1,
        last_round: int = 0,
        reason: str = "",
    ) -> int:
        """Registra uma proibição de pareamento entre dois jogadores.

        `last_round=0` significa "até a última rodada" (proibição aberta)."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO prohibited_pairings (
                    tournament_id, player_a_id, player_b_id,
                    first_round, last_round, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(player_a_id),
                    int(player_b_id),
                    int(first_round or 1),
                    int(last_round or 0),
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_prohibited_pairings(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pp.*, pa.name AS player_a_name, pb.name AS player_b_name
                FROM prohibited_pairings pp
                LEFT JOIN players pa ON pa.id = pp.player_a_id
                LEFT JOIN players pb ON pb.id = pp.player_b_id
                WHERE pp.tournament_id = ?
                ORDER BY pp.first_round ASC, pp.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_prohibited_pairing(self, prohibition_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM prohibited_pairings WHERE id = ?", (int(prohibition_id),)
            )

    def add_prohibited_team_pairing(
        self,
        tournament_id: int,
        team_a_id: int,
        team_b_id: int,
        *,
        first_round: int = 1,
        last_round: int = 0,
        reason: str = "",
    ) -> int:
        """Registra uma proibição de pareamento entre duas equipes.

        `last_round=0` significa "até a última rodada" (proibição aberta)."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO prohibited_team_pairings (
                    tournament_id, team_a_id, team_b_id,
                    first_round, last_round, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(tournament_id),
                    int(team_a_id),
                    int(team_b_id),
                    int(first_round or 1),
                    int(last_round or 0),
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_prohibited_team_pairings(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pp.*, ta.name AS team_a_name, tb.name AS team_b_name
                FROM prohibited_team_pairings pp
                LEFT JOIN teams ta ON ta.id = pp.team_a_id
                LEFT JOIN teams tb ON tb.id = pp.team_b_id
                WHERE pp.tournament_id = ?
                ORDER BY pp.first_round ASC, pp.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_prohibited_team_pairing(self, prohibition_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM prohibited_team_pairings WHERE id = ?", (int(prohibition_id),)
            )

    def add_requested_bye(
        self,
        tournament_id: int,
        player_id: int,
        round_number: int,
        bye_type: str = "H",
        *,
        reason: str = "",
    ) -> int:
        """Registra um bye solicitado (F/H/Z) de um jogador numa rodada.

        Sobrescreve o tipo caso já exista solicitação para o mesmo jogador/rodada."""
        normalized = str(bye_type or "H").strip().upper()
        if normalized not in {"F", "H", "Z"}:
            raise ValueError("Tipo de bye inválido (use F, H ou Z).")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO requested_byes (
                    tournament_id, player_id, round_number, bye_type, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tournament_id, player_id, round_number)
                DO UPDATE SET bye_type = excluded.bye_type, reason = excluded.reason
                """,
                (
                    int(tournament_id),
                    int(player_id),
                    int(round_number),
                    normalized,
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_requested_byes(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, p.name AS player_name
                FROM requested_byes rb
                LEFT JOIN players p ON p.id = rb.player_id
                WHERE rb.tournament_id = ?
                ORDER BY rb.round_number ASC, rb.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_requested_byes_for_round(
        self, tournament_id: int, round_number: int
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, p.name AS player_name
                FROM requested_byes rb
                LEFT JOIN players p ON p.id = rb.player_id
                WHERE rb.tournament_id = ? AND rb.round_number = ?
                ORDER BY rb.id ASC
                """,
                (int(tournament_id), int(round_number)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_requested_bye(self, requested_bye_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM requested_byes WHERE id = ?", (int(requested_bye_id),)
            )

    def add_requested_team_bye(
        self,
        tournament_id: int,
        team_id: int,
        round_number: int,
        bye_type: str = "H",
        *,
        reason: str = "",
    ) -> int:
        """Registra um bye solicitado (F/H/Z) de uma equipe numa rodada.

        Sobrescreve o tipo caso já exista solicitação para a mesma equipe/rodada."""
        normalized = str(bye_type or "H").strip().upper()
        if normalized not in {"F", "H", "Z"}:
            raise ValueError("Tipo de bye inválido (use F, H ou Z).")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO requested_team_byes (
                    tournament_id, team_id, round_number, bye_type, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tournament_id, team_id, round_number)
                DO UPDATE SET bye_type = excluded.bye_type, reason = excluded.reason
                """,
                (
                    int(tournament_id),
                    int(team_id),
                    int(round_number),
                    normalized,
                    str(reason or "").strip(),
                    self.now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_requested_team_byes(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, t.name AS team_name
                FROM requested_team_byes rb
                LEFT JOIN teams t ON t.id = rb.team_id
                WHERE rb.tournament_id = ?
                ORDER BY rb.round_number ASC, rb.id ASC
                """,
                (int(tournament_id),),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_requested_team_byes_for_round(
        self, tournament_id: int, round_number: int
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT rb.*, t.name AS team_name
                FROM requested_team_byes rb
                LEFT JOIN teams t ON t.id = rb.team_id
                WHERE rb.tournament_id = ? AND rb.round_number = ?
                ORDER BY rb.id ASC
                """,
                (int(tournament_id), int(round_number)),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def delete_requested_team_bye(self, requested_bye_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM requested_team_byes WHERE id = ?", (int(requested_bye_id),)
            )

    def update_team_match_summary(
        self,
        team_match_id: int,
        result: str,
        white_match_points: float,
        black_match_points: float,
        white_game_points: float,
        black_game_points: float,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE team_matches
                SET result = ?, white_match_points = ?, black_match_points = ?,
                    white_game_points = ?, black_game_points = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    result.strip(),
                    float(white_match_points),
                    float(black_match_points),
                    float(white_game_points),
                    float(black_game_points),
                    self.now(),
                    team_match_id,
                ),
            )

    def create_round_with_pairings(
        self,
        tournament_id: int,
        round_number: int,
        pairings: list[dict[str, Any]],
        pairing_engine_version: str = "albericus-swiss-1",
        ruleset_version: str = "albericus-2026-phase0",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rounds (
                    tournament_id, number, status, pairing_engine_version,
                    ruleset_version, created_at
                )
                VALUES (?, ?, 'generated', ?, ?, ?)
                """,
                (tournament_id, round_number, pairing_engine_version, ruleset_version, self.now()),
            )
            round_id = int(cursor.lastrowid)
            for pairing in pairings:
                connection.execute(
                    """
                    INSERT INTO pairings (
                        round_id, board_number, white_player_id, black_player_id,
                        result, is_bye, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        pairing["board_number"],
                        pairing["white_player_id"],
                        pairing.get("black_player_id"),
                        pairing.get("result", ""),
                        1 if pairing.get("is_bye") else 0,
                        self.now(),
                    ),
                )
            return round_id

    def list_rounds(self, tournament_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM rounds
                WHERE tournament_id = ?
                ORDER BY number DESC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_round_by_number(
        self,
        tournament_id: int,
        round_number: int,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM rounds
                WHERE tournament_id = ? AND number = ?
                """,
                (tournament_id, round_number),
            ).fetchone()
            return dict(row) if row else None

    def get_round(self, round_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_latest_round(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM rounds
                WHERE tournament_id = ?
                ORDER BY number DESC
                LIMIT 1
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_pairings_for_round(self, round_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.*,
                    white.name AS white_name,
                    white.surname AS white_surname,
                    white.given_name AS white_given_name,
                    white.rating AS white_rating,
                    white.club AS white_club,
                    white.fide_id AS white_fide_id,
                    white.cbx_id AS white_cbx_id,
                    white.lbx_id AS white_lbx_id,
                    black.name AS black_name,
                    black.surname AS black_surname,
                    black.given_name AS black_given_name,
                    black.rating AS black_rating,
                    black.club AS black_club,
                    black.fide_id AS black_fide_id,
                    black.cbx_id AS black_cbx_id,
                    black.lbx_id AS black_lbx_id
                FROM pairings p
                JOIN players white ON white.id = p.white_player_id
                LEFT JOIN players black ON black.id = p.black_player_id
                WHERE p.round_id = ?
                ORDER BY p.board_number ASC
                """,
                (round_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_pairings_for_tournament(
        self,
        tournament_id: int,
        closed_only: bool = False,
    ) -> list[dict[str, Any]]:
        status_filter = "AND r.status = 'closed'" if closed_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    p.*,
                    r.number AS round_number,
                    r.status AS round_status
                FROM pairings p
                JOIN rounds r ON r.id = p.round_id
                WHERE r.tournament_id = ?
                {status_filter}
                ORDER BY r.number ASC, p.board_number ASC
                """,
                (tournament_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def update_pairing_result(self, pairing_id: int, result: str) -> None:
        """Grava o resultado da mesa e encerra o adiamento (ARB-02).

        Resultado lancado E a resolucao do adiamento: deixar a marca de pe
        significaria a mesa aparecer como adiada com placar preenchido, que e
        um estado que nao existe no salao.
        """
        with self.connect() as connection:
            connection.execute(
                "UPDATE pairings SET result = ?, postponed = 0, postponed_note = '' "
                "WHERE id = ?",
                (result, pairing_id),
            )

    def set_pairing_postponed(
        self,
        pairing_id: int,
        postponed: bool,
        note: str = "",
    ) -> None:
        """Marca/desmarca a mesa como adiada, com o combinado como nota."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE pairings SET postponed = ?, postponed_note = ? WHERE id = ?",
                (1 if postponed else 0, str(note or "").strip() if postponed else "", pairing_id),
            )

    def list_postponed_pairings(self, round_id: int) -> list[dict[str, Any]]:
        """Mesas adiadas da rodada, para o painel e para o fechamento."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.*,
                    white.name AS white_player_name,
                    white.surname AS white_player_surname,
                    white.given_name AS white_player_given_name,
                    black.name AS black_player_name,
                    black.surname AS black_player_surname,
                    black.given_name AS black_player_given_name
                FROM pairings p
                LEFT JOIN players white ON white.id = p.white_player_id
                LEFT JOIN players black ON black.id = p.black_player_id
                WHERE p.round_id = ? AND p.postponed = 1
                ORDER BY p.board_number ASC
                """,
                (round_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def swap_pairing_colors(self, pairing_id: int) -> None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT white_player_id, black_player_id, is_bye
                FROM pairings
                WHERE id = ?
                """,
                (pairing_id,),
            ).fetchone()
            if not row or row["is_bye"] or row["black_player_id"] is None:
                return
            connection.execute(
                """
                UPDATE pairings
                SET white_player_id = ?, black_player_id = ?
                WHERE id = ?
                """,
                (row["black_player_id"], row["white_player_id"], pairing_id),
            )

    def update_pairing_players(
        self,
        updates: list[tuple[int, int, int | None]],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                UPDATE pairings
                SET white_player_id = ?, black_player_id = ?
                WHERE id = ?
                """,
                [
                    (white_player_id, black_player_id, pairing_id)
                    for pairing_id, white_player_id, black_player_id in updates
                ],
            )

    def close_round(self, round_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE rounds
                SET status = 'closed',
                    closed_at = CASE WHEN closed_at = '' THEN ? ELSE closed_at END
                WHERE id = ?
                """,
                (self.now(), round_id),
            )

    def delete_round(self, round_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM rounds WHERE id = ?", (round_id,))

    def _ensure_tournament_settings(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO tournament_settings (tournament_id, pairing_system, tiebreak_engine, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (tournament_id, default_pairing_system(), default_tiebreak_engine(), self.now()),
        )

    def _ensure_round_schedule(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
        rounds_count: int,
    ) -> None:
        now = self.now()
        for round_number in range(1, max(rounds_count, 0) + 1):
            connection.execute(
                """
                INSERT OR IGNORE INTO round_schedule (
                    tournament_id, round_number, date, time, updated_at
                ) VALUES (?, ?, '', '', ?)
                """,
                (tournament_id, round_number, now),
            )

    def _late_entry_starting_points(
        self,
        connection: sqlite3.Connection,
        tournament_id: int,
    ) -> float:
        settings = connection.execute(
            """
            SELECT late_entry_points
            FROM tournament_settings
            WHERE tournament_id = ?
            """,
            (tournament_id,),
        ).fetchone()
        if not settings or not float(settings["late_entry_points"] or 0):
            return 0.0
        closed_rounds = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM rounds
            WHERE tournament_id = ? AND status = 'closed'
            """,
            (tournament_id,),
        ).fetchone()
        return round(float(settings["late_entry_points"] or 0) * int(closed_rounds["total"] or 0), 2)
