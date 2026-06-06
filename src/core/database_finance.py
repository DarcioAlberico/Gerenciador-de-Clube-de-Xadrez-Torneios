"""Mixin do dominio de financeiro (planos, pagamentos, transacoes, patrocinios) da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class FinanceMixin(_DatabaseInfra):
    def create_membership_plan(
        self,
        name: str,
        amount: float = 0.0,
        billing_cycle: str = "monthly",
        active: int = 1,
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO membership_plans (
                    name, amount, billing_cycle, active, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    float(amount or 0.0),
                    billing_cycle.strip(),
                    int(active),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_membership_plan(
        self,
        plan_id: int,
        name: str,
        amount: float = 0.0,
        billing_cycle: str = "monthly",
        active: int = 1,
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE membership_plans
                SET name = ?, amount = ?, billing_cycle = ?, active = ?,
                    notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    float(amount or 0.0),
                    billing_cycle.strip(),
                    int(active),
                    notes.strip(),
                    self.now(),
                    plan_id,
                ),
            )

    def get_membership_plan(self, plan_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM membership_plans
                WHERE id = ?
                """,
                (plan_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_membership_plans(self, active_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE p.active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    p.*,
                    (SELECT COUNT(*) FROM payments py WHERE py.plan_id = p.id) AS payments_count
                FROM membership_plans p
                {where}
                ORDER BY p.active DESC, p.name COLLATE NOCASE ASC, p.id ASC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def set_membership_plan_active(self, plan_id: int, active: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE membership_plans
                SET active = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(active), self.now(), plan_id),
            )

    def create_payment(
        self,
        member_id: int,
        plan_id: int | None = None,
        description: str = "",
        reference_period: str = "",
        due_date: str = "",
        payment_date: str = "",
        amount: float = 0.0,
        status: str = "pending",
        method: str = "",
        notes: str = "",
    ) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO payments (
                    member_id, plan_id, description, reference_period, due_date,
                    payment_date, amount, status, method, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_id,
                    plan_id,
                    description.strip(),
                    reference_period.strip(),
                    due_date.strip(),
                    payment_date.strip(),
                    float(amount or 0.0),
                    status.strip(),
                    method.strip(),
                    notes.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_payment(
        self,
        payment_id: int,
        member_id: int,
        plan_id: int | None = None,
        description: str = "",
        reference_period: str = "",
        due_date: str = "",
        payment_date: str = "",
        amount: float = 0.0,
        status: str = "pending",
        method: str = "",
        notes: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE payments
                SET member_id = ?, plan_id = ?, description = ?,
                    reference_period = ?, due_date = ?, payment_date = ?,
                    amount = ?, status = ?, method = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    member_id,
                    plan_id,
                    description.strip(),
                    reference_period.strip(),
                    due_date.strip(),
                    payment_date.strip(),
                    float(amount or 0.0),
                    status.strip(),
                    method.strip(),
                    notes.strip(),
                    self.now(),
                    payment_id,
                ),
            )

    def create_financial_transaction(self, **kwargs: Any) -> int:
        return self._insert(
            "financial_transactions",
            {**kwargs, "created_at": self.now(), "updated_at": self.now()},
        )

    def update_financial_transaction(self, transaction_id: int, **kwargs: Any) -> None:
        self._update("financial_transactions", transaction_id, {**kwargs, "updated_at": self.now()})

    def delete_financial_transaction(self, transaction_id: int) -> None:
        self._delete("financial_transactions", transaction_id)

    def get_financial_transaction(self, transaction_id: int) -> dict[str, Any] | None:
        return self._fetch_one(
            "SELECT * FROM financial_transactions WHERE id = ?",
            (transaction_id,)
        )

    def list_financial_transactions(self, start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
        query = "SELECT * FROM financial_transactions"
        params: list[Any] = []
        conditions: list[str] = []
        
        if start_date:
            conditions.append("transaction_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("transaction_date <= ?")
            params.append(end_date)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY transaction_date DESC"
        with self.connect() as conn:
            return self.rows_to_dicts(conn.execute(query, tuple(params)).fetchall())

    def create_sponsor(self, **kwargs: Any) -> int:
        return self._insert(
            "sponsors",
            {**kwargs, "created_at": self.now(), "updated_at": self.now()},
        )

    def update_sponsor(self, sponsor_id: int, **kwargs: Any) -> None:
        self._update("sponsors", sponsor_id, {**kwargs, "updated_at": self.now()})

    def delete_sponsor(self, sponsor_id: int) -> None:
        self._delete("sponsors", sponsor_id)

    def get_sponsor(self, sponsor_id: int) -> dict[str, Any] | None:
        return self._fetch_one(
            "SELECT * FROM sponsors WHERE id = ?",
            (sponsor_id,)
        )

    def list_sponsors(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM sponsors ORDER BY name ASC")

    def get_payment(self, payment_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    py.*,
                    m.name AS member_name,
                    m.status AS member_status,
                    m.member_type,
                    m.category AS member_category,
                    c.name AS club_name,
                    cl.name AS active_class_name,
                    p.name AS plan_name,
                    p.billing_cycle AS plan_billing_cycle
                FROM payments py
                JOIN members m ON m.id = py.member_id
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                LEFT JOIN membership_plans p ON p.id = py.plan_id
                WHERE py.id = ?
                ORDER BY ac.updated_at DESC, ac.id DESC
                LIMIT 1
                """,
                (payment_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_payments(
        self,
        start_date: str = "",
        end_date: str = "",
        member_id: int | None = None,
        status: str = "",
        include_canceled: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if start_date:
            conditions.append("py.due_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("py.due_date <= ?")
            params.append(end_date)
        if member_id:
            conditions.append("py.member_id = ?")
            params.append(member_id)
        if status:
            conditions.append("py.status = ?")
            params.append(status)
        if not include_canceled:
            conditions.append("py.status <> 'canceled'")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    py.*,
                    m.name AS member_name,
                    m.status AS member_status,
                    m.member_type,
                    m.category AS member_category,
                    c.name AS club_name,
                    cl.name AS active_class_name,
                    p.name AS plan_name,
                    p.billing_cycle AS plan_billing_cycle
                FROM payments py
                JOIN members m ON m.id = py.member_id
                LEFT JOIN clubs c ON c.id = m.club_id
                LEFT JOIN member_class_enrollments ac
                    ON ac.member_id = m.id AND ac.status = 'active'
                LEFT JOIN classes cl ON cl.id = ac.class_id
                LEFT JOIN membership_plans p ON p.id = py.plan_id
                {where}
                ORDER BY py.due_date DESC, py.id DESC
                """,
                params,
            ).fetchall()
            return self.rows_to_dicts(rows)
