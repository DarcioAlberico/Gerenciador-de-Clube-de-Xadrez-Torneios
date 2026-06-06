"""Mixin do dominio de niveis de aprendizado da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class LearningLevelMixin(_DatabaseInfra):
    def create_learning_level(
        self,
        name: str,
        description: str = "",
        display_order: int = 0,
        active: int = 1,
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO learning_levels (
                    name, description, display_order, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    description.strip(),
                    int(display_order or 0),
                    int(active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_learning_level(
        self,
        learning_level_id: int,
        name: str,
        description: str = "",
        display_order: int = 0,
        active: int = 1,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE learning_levels
                SET name = ?, description = ?, display_order = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    description.strip(),
                    int(display_order or 0),
                    int(active),
                    self.now(),
                    learning_level_id,
                ),
            )

    def get_learning_level(self, learning_level_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    ll.*,
                    (
                        SELECT COUNT(*)
                        FROM members m
                        WHERE m.learning_level_id = ll.id
                    ) AS members_count
                FROM learning_levels ll
                WHERE ll.id = ?
                """,
                (learning_level_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_learning_levels(self, active_only: bool = False) -> list[dict[str, Any]]:
        active_filter = "WHERE ll.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    ll.*,
                    (
                        SELECT COUNT(*)
                        FROM members m
                        WHERE m.learning_level_id = ll.id
                    ) AS members_count
                FROM learning_levels ll
                {active_filter}
                ORDER BY ll.active DESC, ll.display_order ASC, ll.name COLLATE NOCASE ASC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_learning_level_active(self, learning_level_id: int, active: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE learning_levels
                SET active = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(active), self.now(), learning_level_id),
            )
