"""Tipagem da infraestrutura compartilhada da Database para os mixins de dominio.

A God Class ``Database`` esta sendo decomposta em mixins por dominio. Cada mixin
usa metodos de infraestrutura (``connect``, ``_insert``, ``_fetch_all``...) cujos
corpos reais vivem na fachada ``Database``. Como o mypy cobre ``src/core``, os
mixins herdam de ``_DatabaseInfra`` para que o type-checker saiba que esses
metodos existem. As assinaturas ficam sob ``TYPE_CHECKING`` (em runtime a classe
e vazia); a resolucao real acontece via MRO na classe ``Database``.
"""
from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Mapping


class _DatabaseInfra:
    if TYPE_CHECKING:
        def connect(self) -> AbstractContextManager[sqlite3.Connection]: ...

        def _insert(self, table: str, values: Mapping[str, Any]) -> int: ...

        def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]: ...

        def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None: ...

        @staticmethod
        def now() -> str: ...
