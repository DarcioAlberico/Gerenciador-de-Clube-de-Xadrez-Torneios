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
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping


class _DatabaseInfra:
    # Atributos de instancia definidos no __init__ da fachada Database:
    db_path: Path

    if TYPE_CHECKING:
        # connect() real e um @contextmanager sem anotacao de retorno; o mypy o
        # trata de forma permissiva (connection ~ Any). Declaramos com Any aqui
        # para os mixins enxergarem o mesmo que enxergavam dentro de Database —
        # mantendo a extracao neutra (sem forcar mudancas no codigo movido).
        def connect(self) -> AbstractContextManager[Any]: ...

        def _insert(self, table: str, values: Mapping[str, Any]) -> int: ...

        def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]: ...

        def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None: ...

        def _update(self, table: str, row_id: int, values: Mapping[str, Any]) -> None: ...

        def _delete(self, table: str, row_id: int) -> None: ...

        @staticmethod
        def now() -> str: ...

        @staticmethod
        def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]: ...

        # Config/base que permanece na fachada Database e e usada por mixins:
        def get_app_settings(self) -> dict[str, Any]: ...

        def save_app_settings(self, settings: dict[str, Any]) -> None: ...

        def _get_connection(self) -> AbstractContextManager[Any]: ...

        # Metodos de outros mixins chamados cross-dominio (fornecidos pela fachada):
        def get_club(self, club_id: int = 1) -> dict[str, Any] | None: ...

        def create_player(
            self,
            tournament_id: int,
            name: str,
            club: str = "",
            rating: int = 0,
            category: str = "",
            federation_id: str = "",
            fide_id: str = "",
            birth_date: str = "",
            member_id: int | None = None,
            surname: str = "",
            given_name: str = "",
            title: str = "",
            sex: str = "",
            cbx_id: str = "",
            lbx_id: str = "",
            national_rating: int = 0,
            international_rating: int = 0,
            rapid_rating: int = 0,
            blitz_rating: int = 0,
            games_played: int = 0,
            player_status: str = "active",
            starting_points: float | None = None,
        ) -> int: ...
