"""Mixin do dominio de arbitros (referees) da Database.

Extraido de ``src.core.database`` como 1o passo da decomposicao da God Class
em mixins por dominio. Os metodos preservam comportamento; a fachada
``Database`` herda deste mixin. Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class RefereesMixin(_DatabaseInfra):
    def list_referees(self, active_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM referees"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query).fetchall()]

    def get_referee(self, referee_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM referees WHERE id = ?", (referee_id,)).fetchone()
            return dict(row) if row else None

    def insert_referee(self, data: dict[str, Any]) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO referees (name, phone, email, federation_id, fide_id, cbx_id, category, active, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    data.get("name", ""),
                    data.get("phone", ""),
                    data.get("email", ""),
                    data.get("federation_id", ""),
                    data.get("fide_id", ""),
                    data.get("cbx_id", ""),
                    data.get("category", ""),
                    data.get("active", 1),
                    data.get("notes", ""),
                ),
            )
            return cursor.lastrowid or 0

    def update_referee(self, referee_id: int, data: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE referees
                SET name = ?, phone = ?, email = ?, federation_id = ?, fide_id = ?, cbx_id = ?, category = ?, active = ?, notes = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    data.get("name", ""),
                    data.get("phone", ""),
                    data.get("email", ""),
                    data.get("federation_id", ""),
                    data.get("fide_id", ""),
                    data.get("cbx_id", ""),
                    data.get("category", ""),
                    data.get("active", 1),
                    data.get("notes", ""),
                    referee_id,
                ),
            )

    def list_tournament_referees(self, tournament_id: int) -> list[dict[str, Any]]:
        query = """
            SELECT tr.*, r.name, r.fide_id, r.cbx_id, r.category
            FROM tournament_referees tr
            JOIN referees r ON tr.referee_id = r.id
            WHERE tr.tournament_id = ?
            ORDER BY tr.role, r.name
        """
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, (tournament_id,)).fetchall()]

    def assign_tournament_referee(self, tournament_id: int, referee_id: int, role: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tournament_referees (tournament_id, referee_id, role, created_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (tournament_id, referee_id, role),
            )

    def remove_tournament_referee(self, tournament_id: int, referee_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM tournament_referees WHERE tournament_id = ? AND referee_id = ?",
                (tournament_id, referee_id),
            )
