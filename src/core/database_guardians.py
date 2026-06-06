"""Mixin do dominio de responsaveis (guardians) da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class GuardianMixin(_DatabaseInfra):
    def create_guardian(
        self,
        name: str,
        phone: str = "",
        email: str = "",
        document: str = "",
        address: str = "",
        notes: str = "",
        active: int = 1,
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO guardians (
                    name, phone, email, document, address, notes, active,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    phone.strip(),
                    email.strip(),
                    document.strip(),
                    address.strip(),
                    notes.strip(),
                    int(active),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_guardian(
        self,
        guardian_id: int,
        name: str,
        phone: str = "",
        email: str = "",
        document: str = "",
        address: str = "",
        notes: str = "",
        active: int = 1,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE guardians
                SET name = ?, phone = ?, email = ?, document = ?, address = ?,
                    notes = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    phone.strip(),
                    email.strip(),
                    document.strip(),
                    address.strip(),
                    notes.strip(),
                    int(active),
                    self.now(),
                    guardian_id,
                ),
            )

    def get_guardian(self, guardian_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    g.*,
                    (SELECT COUNT(*) FROM member_guardians mg WHERE mg.guardian_id = g.id) AS members_count,
                    (
                        SELECT COUNT(*)
                        FROM member_guardians mg
                        JOIN members m ON m.id = mg.member_id
                        WHERE mg.guardian_id = g.id AND m.status = 'active'
                    ) AS active_members_count
                FROM guardians g
                WHERE g.id = ?
                """,
                (guardian_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_guardians(self, active_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE g.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    g.*,
                    (SELECT COUNT(*) FROM member_guardians mg WHERE mg.guardian_id = g.id) AS members_count,
                    (
                        SELECT COUNT(*)
                        FROM member_guardians mg
                        JOIN members m ON m.id = mg.member_id
                        WHERE mg.guardian_id = g.id AND m.status = 'active'
                    ) AS active_members_count
                FROM guardians g
                {where}
                ORDER BY g.active DESC, g.name COLLATE NOCASE ASC, g.id ASC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_guardian_active(self, guardian_id: int, active: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE guardians
                SET active = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(active), self.now(), guardian_id),
            )

    def link_guardian_to_member(
        self,
        member_id: int,
        guardian_id: int,
        relationship: str = "",
        primary_contact: int = 0,
        emergency_contact: int = 0,
        notes: str = "",
    ) -> None:
        now = self.now()
        with self.connect() as connection:
            if primary_contact:
                connection.execute(
                    """
                    UPDATE member_guardians
                    SET primary_contact = 0, updated_at = ?
                    WHERE member_id = ? AND guardian_id <> ?
                    """,
                    (now, member_id, guardian_id),
                )
            connection.execute(
                """
                INSERT INTO member_guardians (
                    member_id, guardian_id, relationship, primary_contact,
                    emergency_contact, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(member_id, guardian_id) DO UPDATE SET
                    relationship = excluded.relationship,
                    primary_contact = excluded.primary_contact,
                    emergency_contact = excluded.emergency_contact,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    member_id,
                    guardian_id,
                    relationship.strip(),
                    int(primary_contact),
                    int(emergency_contact),
                    notes.strip(),
                    now,
                    now,
                ),
            )

    def unlink_guardian_from_member(self, member_id: int, guardian_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM member_guardians
                WHERE member_id = ? AND guardian_id = ?
                """,
                (member_id, guardian_id),
            )

    def list_member_guardians(self, member_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    mg.*,
                    g.name AS guardian_name,
                    g.phone AS guardian_phone,
                    g.email AS guardian_email,
                    g.document AS guardian_document,
                    g.address AS guardian_address,
                    g.active AS guardian_active
                FROM member_guardians mg
                JOIN guardians g ON g.id = mg.guardian_id
                WHERE mg.member_id = ?
                ORDER BY mg.primary_contact DESC, g.name COLLATE NOCASE ASC
                """,
                (member_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_guardian_members(self, guardian_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    mg.*,
                    m.name AS member_name,
                    m.phone AS member_phone,
                    m.email AS member_email,
                    m.birth_date AS member_birth_date,
                    m.category AS member_category,
                    m.member_type,
                    m.status AS member_status,
                    c.name AS club_name,
                    ac.class_id AS active_class_id,
                    cl.name AS active_class_name
                FROM member_guardians mg
                JOIN members m ON m.id = mg.member_id
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                WHERE mg.guardian_id = ?
                ORDER BY
                    m.status ASC,
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """,
                (guardian_id,),
            ).fetchall()
            return self.rows_to_dicts(rows)

    def list_members_without_guardians(self, active_only: bool = True) -> list[dict[str, Any]]:
        status_filter = "AND m.status = 'active'" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    m.*,
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
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM member_guardians mg
                    WHERE mg.member_id = m.id
                )
                {status_filter}
                ORDER BY
                    COALESCE(NULLIF(TRIM(m.surname), ''), m.name) COLLATE NOCASE ASC,
                    m.name COLLATE NOCASE ASC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)
