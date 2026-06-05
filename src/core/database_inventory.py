"""Mixin do dominio de inventario (itens, emprestimos, manutencoes) da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class InventoryMixin(_DatabaseInfra):
    def create_inventory_item(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inventory_items (
                    club_id, code, name, item_type, quantity_total,
                    condition_status, storage_location, acquisition_date,
                    acquisition_value, active, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("club_id") or 1),
                    str(data.get("code", "")).strip(),
                    str(data.get("name", "")).strip(),
                    str(data.get("item_type", "other")).strip() or "other",
                    int(data.get("quantity_total", 1) or 1),
                    str(data.get("condition_status", "good")).strip() or "good",
                    str(data.get("storage_location", "")).strip(),
                    str(data.get("acquisition_date", "")).strip(),
                    float(data.get("acquisition_value", 0.0) or 0.0),
                    int(data.get("active", 1) or 0),
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_inventory_item(self, item_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE inventory_items
                SET club_id = ?, code = ?, name = ?, item_type = ?,
                    quantity_total = ?, condition_status = ?, storage_location = ?,
                    acquisition_date = ?, acquisition_value = ?, active = ?,
                    notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("club_id") or 1),
                    str(data.get("code", "")).strip(),
                    str(data.get("name", "")).strip(),
                    str(data.get("item_type", "other")).strip() or "other",
                    int(data.get("quantity_total", 1) or 1),
                    str(data.get("condition_status", "good")).strip() or "good",
                    str(data.get("storage_location", "")).strip(),
                    str(data.get("acquisition_date", "")).strip(),
                    float(data.get("acquisition_value", 0.0) or 0.0),
                    int(data.get("active", 1) or 0),
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    item_id,
                ),
            )

    def get_inventory_item(self, item_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    i.*,
                    c.name AS club_name,
                    COALESCE((
                        SELECT SUM(l.quantity)
                        FROM inventory_loans l
                        WHERE l.item_id = i.id AND l.status = 'open'
                    ), 0) AS borrowed_quantity,
                    (
                        i.quantity_total - COALESCE((
                            SELECT SUM(l.quantity)
                            FROM inventory_loans l
                            WHERE l.item_id = i.id AND l.status = 'open'
                        ), 0)
                    ) AS available_quantity,
                    (
                        SELECT COUNT(*)
                        FROM inventory_maintenance m
                        WHERE m.item_id = i.id AND m.status IN ('open', 'in_progress')
                    ) AS open_maintenance_count
                FROM inventory_items i
                LEFT JOIN clubs c ON c.id = i.club_id
                WHERE i.id = ?
                """,
                (item_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_inventory_items(
        self,
        search: str = "",
        club_id: int | None = None,
        item_type: str = "",
        condition_status: str = "",
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if search:
            conditions.append(
                """
                (
                    i.code LIKE ? OR i.name LIKE ? OR i.storage_location LIKE ?
                    OR i.notes LIKE ?
                )
                """
            )
            params.extend([f"%{search.strip()}%"] * 4)
        if club_id:
            conditions.append("i.club_id = ?")
            params.append(club_id)
        if item_type:
            conditions.append("i.item_type = ?")
            params.append(item_type.strip())
        if condition_status:
            conditions.append("i.condition_status = ?")
            params.append(condition_status.strip())
        if active_only:
            conditions.append("i.active = 1")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    i.*,
                    c.name AS club_name,
                    COALESCE((
                        SELECT SUM(l.quantity)
                        FROM inventory_loans l
                        WHERE l.item_id = i.id AND l.status = 'open'
                    ), 0) AS borrowed_quantity,
                    (
                        i.quantity_total - COALESCE((
                            SELECT SUM(l.quantity)
                            FROM inventory_loans l
                            WHERE l.item_id = i.id AND l.status = 'open'
                        ), 0)
                    ) AS available_quantity,
                    (
                        SELECT COUNT(*)
                        FROM inventory_maintenance m
                        WHERE m.item_id = i.id AND m.status IN ('open', 'in_progress')
                    ) AS open_maintenance_count
                FROM inventory_items i
                LEFT JOIN clubs c ON c.id = i.club_id
                {where}
                ORDER BY i.active DESC, i.item_type ASC, i.name COLLATE NOCASE ASC, i.id ASC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_inventory_item_active(self, item_id: int, active: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE inventory_items
                SET active = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(active), self.now(), item_id),
            )

    def inventory_item_open_loan_quantity(self, item_id: int, exclude_loan_id: int | None = None) -> int:
        conditions = ["item_id = ?", "status = 'open'"]
        params: list[Any] = [item_id]
        if exclude_loan_id:
            conditions.append("id <> ?")
            params.append(exclude_loan_id)
        where = " AND ".join(conditions)
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT COALESCE(SUM(quantity), 0) AS total
                FROM inventory_loans
                WHERE {where}
                """,
                params,
            ).fetchone()
            return int(row["total"] or 0) if row else 0

    def create_inventory_loan(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inventory_loans (
                    item_id, member_id, quantity, loan_date, due_date, return_date,
                    status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("item_id") or 0),
                    int(data.get("member_id") or 0),
                    int(data.get("quantity", 1) or 1),
                    str(data.get("loan_date", "")).strip(),
                    str(data.get("due_date", "")).strip(),
                    str(data.get("return_date", "")).strip(),
                    str(data.get("status", "open")).strip() or "open",
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_inventory_loan(self, loan_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE inventory_loans
                SET item_id = ?, member_id = ?, quantity = ?, loan_date = ?,
                    due_date = ?, return_date = ?, status = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("item_id") or 0),
                    int(data.get("member_id") or 0),
                    int(data.get("quantity", 1) or 1),
                    str(data.get("loan_date", "")).strip(),
                    str(data.get("due_date", "")).strip(),
                    str(data.get("return_date", "")).strip(),
                    str(data.get("status", "open")).strip() or "open",
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    loan_id,
                ),
            )

    def get_inventory_loan(self, loan_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    l.*,
                    i.name AS item_name,
                    i.code AS item_code,
                    i.item_type,
                    m.name AS member_name,
                    c.name AS club_name
                FROM inventory_loans l
                JOIN inventory_items i ON i.id = l.item_id
                JOIN members m ON m.id = l.member_id
                LEFT JOIN clubs c ON c.id = i.club_id
                WHERE l.id = ?
                """,
                (loan_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_inventory_loans(
        self,
        item_id: int | None = None,
        member_id: int | None = None,
        status: str = "",
        include_closed: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if item_id:
            conditions.append("l.item_id = ?")
            params.append(item_id)
        if member_id:
            conditions.append("l.member_id = ?")
            params.append(member_id)
        if status:
            conditions.append("l.status = ?")
            params.append(status.strip())
        if not include_closed:
            conditions.append("l.status = 'open'")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    l.*,
                    i.name AS item_name,
                    i.code AS item_code,
                    i.item_type,
                    m.name AS member_name,
                    c.name AS club_name
                FROM inventory_loans l
                JOIN inventory_items i ON i.id = l.item_id
                JOIN members m ON m.id = l.member_id
                LEFT JOIN clubs c ON c.id = i.club_id
                {where}
                ORDER BY
                    CASE l.status WHEN 'open' THEN 1 ELSE 2 END,
                    l.due_date ASC,
                    l.loan_date DESC,
                    l.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)

    def create_inventory_maintenance(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inventory_maintenance (
                    item_id, opened_date, resolved_date, status, description,
                    cost, vendor, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(data.get("item_id") or 0),
                    str(data.get("opened_date", "")).strip(),
                    str(data.get("resolved_date", "")).strip(),
                    str(data.get("status", "open")).strip() or "open",
                    str(data.get("description", "")).strip(),
                    float(data.get("cost", 0.0) or 0.0),
                    str(data.get("vendor", "")).strip(),
                    str(data.get("notes", "")).strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_inventory_maintenance(self, maintenance_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE inventory_maintenance
                SET item_id = ?, opened_date = ?, resolved_date = ?, status = ?,
                    description = ?, cost = ?, vendor = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(data.get("item_id") or 0),
                    str(data.get("opened_date", "")).strip(),
                    str(data.get("resolved_date", "")).strip(),
                    str(data.get("status", "open")).strip() or "open",
                    str(data.get("description", "")).strip(),
                    float(data.get("cost", 0.0) or 0.0),
                    str(data.get("vendor", "")).strip(),
                    str(data.get("notes", "")).strip(),
                    self.now(),
                    maintenance_id,
                ),
            )

    def get_inventory_maintenance(self, maintenance_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    mt.*,
                    i.name AS item_name,
                    i.code AS item_code,
                    i.item_type,
                    c.name AS club_name
                FROM inventory_maintenance mt
                JOIN inventory_items i ON i.id = mt.item_id
                LEFT JOIN clubs c ON c.id = i.club_id
                WHERE mt.id = ?
                """,
                (maintenance_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_inventory_maintenance(
        self,
        item_id: int | None = None,
        status: str = "",
        include_closed: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if item_id:
            conditions.append("mt.item_id = ?")
            params.append(item_id)
        if status:
            conditions.append("mt.status = ?")
            params.append(status.strip())
        if not include_closed:
            conditions.append("mt.status IN ('open', 'in_progress')")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    mt.*,
                    i.name AS item_name,
                    i.code AS item_code,
                    i.item_type,
                    c.name AS club_name
                FROM inventory_maintenance mt
                JOIN inventory_items i ON i.id = mt.item_id
                LEFT JOIN clubs c ON c.id = i.club_id
                {where}
                ORDER BY
                    CASE mt.status
                        WHEN 'open' THEN 1
                        WHEN 'in_progress' THEN 2
                        ELSE 3
                    END,
                    mt.opened_date DESC,
                    mt.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)
