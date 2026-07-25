"""Serviço de largura de colunas por usuário (B-1 / P2-9).

Cola entre as regras puras de :mod:`src.services.column_layouts` e a
persistência do :class:`~src.core.database_ui_prefs.UiPrefsMixin`.

**Nada aqui pode derrubar a tela.** Uma tabela abrir com a largura padrão é um
incômodo de um arrasto; uma tabela não abrir é um chamado. Por isso leitura e
escrita engolem falha de banco e seguem — o registro fica no log.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from src.core.database import Database
from src.services.column_layouts import (
    deviations,
    effective_widths,
    layout_key,
    normalize_widths,
    serialize_widths,
)

logger = logging.getLogger(__name__)


class ColumnLayoutService:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def key_for(columns: Iterable[str], headings: Mapping[str, str] | None = None) -> str:
        """Identidade da tabela — ver ``column_layouts.layout_key``."""
        return layout_key(columns, headings)

    def widths_for(
        self,
        user_id: int,
        table_key: str,
        columns: Iterable[str],
        defaults: Mapping[str, int],
        fallback: int = 100,
    ) -> dict[str, int]:
        """Largura a aplicar em cada coluna: a escolhida, senão o padrão."""
        return effective_widths(columns, defaults, self._saved(user_id, table_key), fallback)

    def remember(
        self,
        user_id: int,
        table_key: str,
        defaults: Mapping[str, int],
        current: Mapping[str, Any],
    ) -> dict[str, int]:
        """Guarda só o que saiu do padrão. Devolve o que ficou guardado."""
        changed = deviations(defaults, {str(k): v for k, v in current.items()})
        try:
            self.db.save_column_layout(user_id, table_key, serialize_widths(changed))
        except Exception:
            logger.exception("Falha ao guardar largura de colunas (%s)", table_key)
        return changed

    def reset(self, user_id: int) -> int:
        """Volta todas as tabelas do usuário à largura padrão."""
        try:
            return self.db.clear_column_layouts(user_id)
        except Exception:
            logger.exception("Falha ao limpar larguras de colunas")
            return 0

    def _saved(self, user_id: int, table_key: str) -> dict[str, int]:
        try:
            return normalize_widths(self.db.get_column_layout(user_id, table_key))
        except Exception:
            logger.exception("Falha ao ler largura de colunas (%s)", table_key)
            return {}
