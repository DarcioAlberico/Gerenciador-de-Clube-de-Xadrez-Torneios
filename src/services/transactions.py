"""``@atomic``: o método de serviço inteiro numa transação (RG2-25).

Para o método curto, que só fala com o banco: validação e gravações entram na
mesma ``Database.transaction()`` (reentrante, RGS-08) — ou grava tudo, ou nada.
Uma recusa (``AppError``) antes da primeira gravação não deixa nada para trás.

Não serve para método que espera rede, subprocesso ou o motor de pareamento:
``transaction()`` abre com ``BEGIN IMMEDIATE`` e seguraria a escrita do banco
o tempo todo. Ali, a transação cerca só o trecho das gravações.

A varredura ``tests/test_rg2_25_transacoes.py`` reconhece este decorador.
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["atomic"]


def atomic(method: F) -> F:
    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        with self.db.transaction():
            return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
