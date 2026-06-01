"""Serviço de layout de listas (spec E7 — Fase F).

CRUD validado das colunas configuráveis por torneio/lista. Mantém o banco como
autoridade; layout vazio = colunas padrão.
"""

from __future__ import annotations

from typing import Any

from src.core.database import Database
from src.services.constants import AppError
from src.services.list_layouts import (
    LAYOUT_REGISTRIES,
    normalize_columns,
    resolve_columns,
)


class ListLayoutService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def available_columns(self, report_key: str = "standings") -> list[tuple[str, str]]:
        registry = LAYOUT_REGISTRIES.get(report_key)
        if registry is None:
            raise AppError("Lista sem layout configuravel.")
        return list(registry.items())

    def get_columns(self, tournament_id: int, report_key: str = "standings") -> dict[str, Any]:
        registry = LAYOUT_REGISTRIES.get(report_key)
        if registry is None:
            raise AppError("Lista sem layout configuravel.")
        selected = resolve_columns(
            self.db.get_report_layout_columns(tournament_id, report_key), report_key
        )
        return {"selected": selected, "available": list(registry.items())}

    def save_columns(
        self,
        tournament_id: int,
        columns: list[str],
        report_key: str = "standings",
    ) -> list[str]:
        if report_key not in LAYOUT_REGISTRIES:
            raise AppError("Lista sem layout configuravel.")
        if not self.db.get_tournament(tournament_id):
            raise AppError("Selecione um torneio valido.")
        cleaned = normalize_columns(columns, report_key)
        if not cleaned:
            raise AppError("Selecione ao menos uma coluna para a lista.")
        self.db.save_report_layout(tournament_id, report_key, cleaned)
        return cleaned

    def reset(self, tournament_id: int, report_key: str = "standings") -> None:
        """Volta ao layout padrão (armazena seleção vazia)."""
        self.db.save_report_layout(tournament_id, report_key, [])
