"""O que a FIDE lê de um jogador — um leitor só para cada campo.

Cada exportação tinha a sua cópia, e as cópias divergiram:

- **rating FIDE** (RG2-11): o TRF, o 072, as normas e o IT3 liam
  ``international_rating or rating or national_rating``. O atalho é legítimo na
  ordem inicial (quem não tem FIDE entra pelo rating do clube), mas no campo FIDE
  ele punha o rating do clube onde a FIDE lê o dela.

| Leitor | Usado em | Não usar em |
|---|---|---|
| ``fide_rating`` | TRF 001/072, aviso "sem rating FIDE", normas, IT3 | ordem inicial |
| ``seed_rating`` | ordem inicial, listas e atas do clube | qualquer campo FIDE |
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _int(value: Any) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def fide_rating(player: Mapping[str, Any]) -> int:
    """Rating FIDE do jogador: só ``international_rating``; 0 quando não tem."""
    return _int(player.get("international_rating"))


def seed_rating(player: Mapping[str, Any]) -> int:
    """Rating para ordenar e mostrar no clube: FIDE, senão o do clube, senão o nacional."""
    return (
        _int(player.get("international_rating"))
        or _int(player.get("rating"))
        or _int(player.get("national_rating"))
    )
