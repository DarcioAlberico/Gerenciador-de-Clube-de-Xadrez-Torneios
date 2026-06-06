"""Mixin do dominio de clubes da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class ClubMixin(_DatabaseInfra):
    def get_club(self, club_id: int = 1) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM clubs
                WHERE id = ?
                """
                ,
                (club_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_clubs(self, active_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    c.*,
                    (SELECT COUNT(*) FROM members m WHERE m.club_id = c.id) AS members_count,
                    (SELECT COUNT(*) FROM classes cl WHERE cl.club_id = c.id AND cl.active = 1) AS active_classes_count,
                    (SELECT COUNT(*) FROM tournaments t WHERE t.club_id = c.id) AS tournaments_count
                FROM clubs c
                {where}
                ORDER BY c.active DESC, c.name COLLATE NOCASE ASC, c.id ASC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def save_club(
        self,
        name: str,
        kind: str = "club",
        city: str = "",
        address: str = "",
        phone: str = "",
        email: str = "",
        notes: str = "",
        active: int = 1,
        club_id: int | None = 1,
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            existing = None
            if club_id:
                existing = connection.execute("SELECT id FROM clubs WHERE id = ?", (club_id,)).fetchone()
            if existing:
                saved_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE clubs
                    SET name = ?, kind = ?, city = ?, address = ?, phone = ?, email = ?,
                        notes = ?, active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name.strip(),
                        kind.strip() or "club",
                        city.strip(),
                        address.strip(),
                        phone.strip(),
                        email.strip(),
                        notes.strip(),
                        int(active),
                        now,
                        saved_id,
                    ),
                )
                return saved_id
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO clubs (
                        name, kind, city, address, phone, email, notes, active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name.strip(),
                        kind.strip() or "club",
                        city.strip(),
                        address.strip(),
                        phone.strip(),
                        email.strip(),
                        notes.strip(),
                        int(active),
                        now,
                        now,
                    ),
                )
                return int(cursor.lastrowid)

    def club_summary(self, club_id: int | None = None) -> dict[str, Any]:
        member_filter = "WHERE club_id = ?" if club_id else ""
        tournament_filter = "WHERE club_id = ?" if club_id else ""
        active_member_filter = "WHERE status = 'active'"
        if club_id:
            active_member_filter += " AND club_id = ?"
        running_tournament_filter = "WHERE status = 'running'"
        if club_id:
            running_tournament_filter += " AND club_id = ?"
        class_filter = "WHERE active = 1"
        if club_id:
            class_filter += " AND club_id = ?"
        params = [club_id] if club_id else []
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    (SELECT COUNT(*) FROM members {active_member_filter}) AS active_members,
                    (SELECT COUNT(*) FROM members {member_filter}) AS total_members,
                    (SELECT COUNT(*) FROM tournaments {tournament_filter}) AS total_tournaments,
                    (SELECT COUNT(*) FROM tournaments {running_tournament_filter}) AS running_tournaments,
                    (SELECT COUNT(*) FROM clubs WHERE active = 1) AS active_clubs,
                    (SELECT COUNT(*) FROM classes {class_filter}) AS active_classes
                """,
                tuple(params + params + params + params + params),
            ).fetchone()
            return dict(row)
