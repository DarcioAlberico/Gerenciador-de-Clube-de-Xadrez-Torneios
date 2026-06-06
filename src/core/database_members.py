"""Mixin do dominio de membros (socios) da Database.

Membros, presencas, titulos e historico de rating interno. Extraido de
``src.core.database`` na decomposicao da God Class. Usa get_club (clubes) e
create_player (nucleo de torneios) via fachada. Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra
from .categories import competition_category_payload


class MemberMixin(_DatabaseInfra):
    def create_member_presence(
        self, member_id: int, presence_date: str, event_type: str, notes: str = ""
    ) -> int:
        with self._get_connection() as conn:
            now = self.now()
            cursor = conn.execute(
                """
                INSERT INTO member_presences (
                    member_id, presence_date, event_type, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (member_id, presence_date, event_type, notes, now, now),
            )
            return cursor.lastrowid

    def list_member_presences(self, member_id: int) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, member_id, presence_date, event_type, notes, created_at, updated_at
                FROM member_presences
                WHERE member_id = ?
                ORDER BY presence_date DESC, id DESC
                """,
                (member_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_member_presence(self, presence_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM member_presences WHERE id = ?", (presence_id,))

    def create_member_title(
        self, member_id: int, title_name: str, date_earned: str, issuer: str, notes: str = ""
    ) -> int:
        with self._get_connection() as conn:
            now = self.now()
            cursor = conn.execute(
                """
                INSERT INTO member_titles (
                    member_id, title_name, date_earned, issuer, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (member_id, title_name, date_earned, issuer, notes, now, now),
            )
            return cursor.lastrowid

    def list_member_titles(self, member_id: int) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, member_id, title_name, date_earned, issuer, notes, created_at, updated_at
                FROM member_titles
                WHERE member_id = ?
                ORDER BY date_earned DESC, id DESC
                """,
                (member_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_member_title(self, title_id: int) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM member_titles WHERE id = ?", (title_id,))

    def create_member(
        self,
        name: str,
        surname: str = "",
        club_id: int = 1,
        learning_level_id: int | None = None,
        city: str = "",
        phone: str = "",
        email: str = "",
        document: str = "",
        birth_date: str = "",
        rating: int = 0,
        category: str = "",
        member_type: str = "socio",
        status: str = "active",
        guardian_name: str = "",
        guardian_phone: str = "",
        notes: str = "",
        lichess_username: str = "",
        chesscom_username: str = "",
        online_blitz_rating: int = 0,
        online_rapid_rating: int = 0,
    ) -> int:
        club = self.get_club(int(club_id or 1))
        category_payload = competition_category_payload(
            birth_date=birth_date,
            rating=rating,
            category=category,
            city=city,
            member_type=member_type,
            tournament_club_city=club.get("city", "") if club else "",
            tournament_club_name=club.get("name", "") if club else "",
        )
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO members (
                    club_id, learning_level_id, name, surname, city, phone, email, document, birth_date, rating,
                    category, age_category, rating_category, prize_tags,
                    member_type, status, guardian_name, guardian_phone,
                    notes, lichess_username, chesscom_username, online_blitz_rating, online_rapid_rating, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(club_id or 1),
                    learning_level_id,
                    name.strip(),
                    surname.strip(),
                    city.strip(),
                    phone.strip(),
                    email.strip(),
                    document.strip(),
                    birth_date.strip(),
                    int(rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    member_type.strip(),
                    status.strip(),
                    guardian_name.strip(),
                    guardian_phone.strip(),
                    notes.strip(),
                    lichess_username.strip(),
                    chesscom_username.strip(),
                    int(online_blitz_rating or 0),
                    int(online_rapid_rating or 0),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_member(
        self,
        member_id: int,
        name: str,
        surname: str = "",
        club_id: int = 1,
        learning_level_id: int | None = None,
        city: str = "",
        phone: str = "",
        email: str = "",
        document: str = "",
        birth_date: str = "",
        rating: int = 0,
        category: str = "",
        member_type: str = "socio",
        status: str = "active",
        guardian_name: str = "",
        guardian_phone: str = "",
        notes: str = "",
        departure_date: str = "",
        departure_reason: str = "",
        transfer_notes: str = "",
        lichess_username: str = "",
        chesscom_username: str = "",
        online_blitz_rating: int = 0,
        online_rapid_rating: int = 0,
    ) -> None:
        club = self.get_club(int(club_id or 1))
        category_payload = competition_category_payload(
            birth_date=birth_date,
            rating=rating,
            category=category,
            city=city,
            member_type=member_type,
            tournament_club_city=club.get("city", "") if club else "",
            tournament_club_name=club.get("name", "") if club else "",
        )
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE members
                SET club_id = ?, learning_level_id = ?, name = ?, surname = ?, city = ?, phone = ?, email = ?, document = ?,
                    birth_date = ?, rating = ?, category = ?, age_category = ?,
                    rating_category = ?, prize_tags = ?, member_type = ?,
                    status = ?, guardian_name = ?, guardian_phone = ?,
                    notes = ?, lichess_username = ?, chesscom_username = ?, online_blitz_rating = ?, online_rapid_rating = ?, departure_date = ?, departure_reason = ?, transfer_notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(club_id or 1),
                    learning_level_id,
                    name.strip(),
                    surname.strip(),
                    city.strip(),
                    phone.strip(),
                    email.strip(),
                    document.strip(),
                    birth_date.strip(),
                    int(rating or 0),
                    category_payload["category"],
                    category_payload["age_category"],
                    category_payload["rating_category"],
                    category_payload["prize_tags"],
                    member_type.strip(),
                    status.strip(),
                    guardian_name.strip(),
                    guardian_phone.strip(),
                    notes.strip(),
                    lichess_username.strip(),
                    chesscom_username.strip(),
                    int(online_blitz_rating or 0),
                    int(online_rapid_rating or 0),
                    departure_date.strip(),
                    departure_reason.strip(),
                    transfer_notes.strip(),
                    self.now(),
                    member_id,
                ),
            )

    def get_member(self, member_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    m.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    ll.description AS learning_level_description,
                    ll.display_order AS learning_level_order,
                    ll.active AS learning_level_active,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name,
                    (
                        SELECT COUNT(*)
                        FROM member_guardians mg
                        WHERE mg.member_id = m.id
                    ) AS guardians_count
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN learning_levels ll ON ll.id = m.learning_level_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE m.id = ?
                ORDER BY ac.updated_at DESC, ac.id DESC
                LIMIT 1
                """,
                (member_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_members(
        self,
        active_only: bool = False,
        club_id: int | None = None,
        class_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if active_only:
            conditions.append("m.status = 'active'")
        if club_id:
            conditions.append("m.club_id = ?")
            params.append(club_id)
        if class_id:
            conditions.append("ac.class_id = ?")
            params.append(class_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
                    c.name AS club_name,
                    ll.name AS learning_level_name,
                    ll.display_order AS learning_level_order,
                    ll.active AS learning_level_active,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN learning_levels ll ON ll.id = m.learning_level_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                {where}
                ORDER BY
                    m.status ASC,
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_members_for_tournament(
        self,
        tournament_id: int,
        active_only: bool = True,
        include_out_of_scope: bool = False,
    ) -> list[dict[str, Any]]:
        status_filter = "AND m.status = 'active'" if active_only else ""
        with self.connect() as connection:
            tournament = connection.execute(
                "SELECT club_id, class_id FROM tournaments WHERE id = ?",
                (tournament_id,),
            ).fetchone()
            scope_filter = ""
            params: list[Any] = [tournament_id]
            if not include_out_of_scope and tournament and tournament["class_id"]:
                scope_filter = "AND ac.class_id = ?"
                params.append(int(tournament["class_id"]))
            elif not include_out_of_scope and tournament and tournament["club_id"]:
                scope_filter = "AND m.club_id = ?"
                params.append(int(tournament["club_id"]))
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
                    p.id AS registered_player_id,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name,
                    (
                        SELECT COUNT(*)
                        FROM member_guardians mg
                        WHERE mg.member_id = m.id
                    ) AS guardians_count
                FROM members m
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                LEFT JOIN players p
                    ON p.member_id = m.id AND p.tournament_id = ?
                WHERE 1 = 1
                {status_filter}
                {scope_filter}
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_member_tournament_players(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.*,
                    t.name AS tournament_name,
                    t.location AS tournament_location,
                    t.start_date AS tournament_start_date,
                    t.end_date AS tournament_end_date,
                    t.rounds_count AS tournament_rounds_count,
                    t.status AS tournament_status,
                    t.created_at AS tournament_created_at
                FROM players p
                JOIN tournaments t ON t.id = p.tournament_id
                WHERE p.member_id = ?
                ORDER BY
                    t.start_date DESC,
                    t.created_at DESC,
                    t.id DESC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_member_tournament_results(
        self,
        member_id: int,
        tournament_id: int,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            player = connection.execute(
                """
                SELECT id
                FROM players
                WHERE member_id = ? AND tournament_id = ?
                """,
                (member_id, tournament_id),
            ).fetchone()
            if not player:
                return []

            rows = connection.execute(
                """
                SELECT
                    p.*,
                    r.number AS round_number,
                    r.status AS round_status,
                    white.name AS white_name,
                    white.surname AS white_surname,
                    white.given_name AS white_given_name,
                    white.rating AS white_rating,
                    black.name AS black_name,
                    black.surname AS black_surname,
                    black.given_name AS black_given_name,
                    black.rating AS black_rating
                FROM pairings p
                JOIN rounds r ON r.id = p.round_id
                JOIN players white ON white.id = p.white_player_id
                LEFT JOIN players black ON black.id = p.black_player_id
                WHERE r.tournament_id = ?
                    AND (p.white_player_id = ? OR p.black_player_id = ?)
                ORDER BY r.number ASC, p.board_number ASC
                """,
                (tournament_id, player["id"], player["id"]),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_member_rating_history(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    h.*,
                    t.name AS tournament_name,
                    t.start_date AS tournament_start_date,
                    p.name AS player_name
                FROM internal_rating_history h
                LEFT JOIN tournaments t ON t.id = h.tournament_id
                LEFT JOIN players p ON p.id = h.player_id
                WHERE h.member_id = ?
                ORDER BY h.created_at DESC, h.id DESC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def record_internal_rating_update(
        self,
        member_id: int,
        tournament_id: int,
        player_id: int,
        old_rating: int,
        new_rating: int,
        performance: int,
        points: float,
        games: int,
        reason: str = "tournament_performance",
    ) -> bool:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO internal_rating_history (
                    member_id, tournament_id, player_id, old_rating, new_rating,
                    performance, points, games, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_id,
                    tournament_id,
                    player_id,
                    int(old_rating or 0),
                    int(new_rating or 0),
                    int(performance or 0),
                    float(points or 0.0),
                    int(games or 0),
                    reason.strip() or "tournament_performance",
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.execute(
                """
                UPDATE members
                SET rating = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(new_rating or 0), now, member_id),
            )
            return True

    def set_member_status(self, member_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE members
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.strip(), self.now(), member_id),
            )

    def get_player_by_member(
        self,
        tournament_id: int,
        member_id: int,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM players
                WHERE tournament_id = ? AND member_id = ?
                """,
                (tournament_id, member_id),
            ).fetchone()
            return dict(row) if row else None

    def create_player_from_member(self, tournament_id: int, member_id: int) -> int:
        member = self.get_member(member_id)
        if not member:
            raise ValueError("Membro nao encontrado.")

        club = self.get_club(int(member.get("club_id") or 1))
        club_name = club["name"] if club and club["name"] else member["city"]
        given_name = str(member.get("name") or "").strip()
        surname = str(member.get("surname") or "").strip()
        tournament_name = " ".join(part for part in [given_name, surname] if part)
        return self.create_player(
            tournament_id=tournament_id,
            name=tournament_name,
            club=club_name,
            rating=int(member["rating"] or 0),
            category=member["category"],
            birth_date=member["birth_date"],
            member_id=member_id,
            surname=surname,
            given_name=given_name,
        )
