"""Mixin de preferências de interface por usuário.

Hoje guarda só a largura das colunas das tabelas de tela (B-1 / P2-9). Fica
separado dos mixins de domínio porque não é dado do clube: some com o usuário e
não entra em backup de torneio, relatório ou exportação.

Acesso cru ao banco — as regras (o que guardar, que largura aplicar) são puras e
moram em :mod:`src.services.column_layouts`.
"""
from __future__ import annotations

from ._database_base import _DatabaseInfra


class UiPrefsMixin(_DatabaseInfra):
    def get_column_layout(self, user_id: int, table_key: str) -> str:
        """JSON cru das larguras, ou string vazia quando não há preferência."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT widths_json FROM ui_column_layouts WHERE user_id = ? AND table_key = ?",
                (int(user_id), str(table_key)),
            ).fetchone()
        return str(row["widths_json"]) if row and row["widths_json"] else ""

    def save_column_layout(self, user_id: int, table_key: str, widths_json: str) -> None:
        """Grava (ou substitui) as larguras da tabela para o usuário.

        Payload vazio **apaga** a linha em vez de guardar um dicionário vazio:
        "voltei ao padrão" e "nunca mexi" são o mesmo estado, e ter dois jeitos
        de escrevê-lo é convite a divergirem.
        """
        payload = str(widths_json or "").strip()
        with self.connect() as connection:
            if not payload or payload in ("{}", "[]"):
                connection.execute(
                    "DELETE FROM ui_column_layouts WHERE user_id = ? AND table_key = ?",
                    (int(user_id), str(table_key)),
                )
                return
            connection.execute(
                """
                INSERT INTO ui_column_layouts (user_id, table_key, widths_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, table_key)
                DO UPDATE SET widths_json = excluded.widths_json, updated_at = excluded.updated_at
                """,
                (int(user_id), str(table_key), payload, self.now()),
            )

    def clear_column_layouts(self, user_id: int) -> int:
        """Apaga todos os layouts do usuário. Devolve quantos saíram."""
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ui_column_layouts WHERE user_id = ?", (int(user_id),)
            )
            return int(cursor.rowcount or 0)
