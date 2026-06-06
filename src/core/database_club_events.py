"""Mixin do dominio de eventos do clube da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class ClubEventMixin(_DatabaseInfra):
    def create_club_event(
        self,
        club_id: int = 1,
        tournament_id: int | None = None,
        title: str = "",
        event_type: str = "other",
        event_date: str = "",
        start_time: str = "",
        end_time: str = "",
        location: str = "",
        status: str = "planned",
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO club_events (
                    club_id, tournament_id, title, event_type, event_date,
                    start_time, end_time, location, status, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(club_id or 1),
                    tournament_id,
                    title.strip(),
                    event_type.strip(),
                    event_date.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    location.strip(),
                    status.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_club_event(
        self,
        event_id: int,
        club_id: int = 1,
        tournament_id: int | None = None,
        title: str = "",
        event_type: str = "other",
        event_date: str = "",
        start_time: str = "",
        end_time: str = "",
        location: str = "",
        status: str = "planned",
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE club_events
                SET club_id = ?, tournament_id = ?, title = ?, event_type = ?,
                    event_date = ?, start_time = ?, end_time = ?, location = ?,
                    status = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(club_id or 1),
                    tournament_id,
                    title.strip(),
                    event_type.strip(),
                    event_date.strip(),
                    start_time.strip(),
                    end_time.strip(),
                    location.strip(),
                    status.strip(),
                    notes.strip(),
                    self.now(),
                    event_id,
                ),
            )

    def get_club_event(self, event_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    e.*,
                    c.name AS club_name,
                    t.name AS tournament_name
                FROM club_events e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN tournaments t ON t.id = e.tournament_id
                WHERE e.id = ?
                """,
                (event_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_club_event_by_tournament(self, tournament_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    e.*,
                    c.name AS club_name,
                    t.name AS tournament_name
                FROM club_events e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN tournaments t ON t.id = e.tournament_id
                WHERE e.tournament_id = ?
                ORDER BY e.updated_at DESC, e.id DESC
                LIMIT 1
                """,
                (tournament_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_club_events(
        self,
        start_date: str = "",
        end_date: str = "",
        club_id: int | None = None,
        status: str = "",
        include_canceled: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if start_date:
            conditions.append("e.event_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("e.event_date <= ?")
            params.append(end_date)
        if club_id:
            conditions.append("e.club_id = ?")
            params.append(club_id)
        if status:
            conditions.append("e.status = ?")
            params.append(status)
        if not include_canceled:
            conditions.append("e.status <> 'canceled'")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    e.*,
                    c.name AS club_name,
                    t.name AS tournament_name
                FROM club_events e
                LEFT JOIN clubs c ON c.id = e.club_id
                LEFT JOIN tournaments t ON t.id = e.tournament_id
                {where}
                ORDER BY
                    CASE WHEN e.event_date = '' THEN 1 ELSE 0 END,
                    e.event_date ASC,
                    e.start_time ASC,
                    e.id ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)
