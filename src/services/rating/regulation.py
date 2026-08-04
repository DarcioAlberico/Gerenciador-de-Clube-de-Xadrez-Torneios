"""O regulamento de rating como DADO (FED-07).

Um regulamento de rating é um punhado de números: quanto vale K em cada
situação, qual o piso, quantas partidas fazem um rating inicial e até onde ele
pode ir. Enquanto isso vivia espalhado em `if`s, "usar o regulamento da CBX"
significava reescrever o cálculo. Aqui é preencher um formulário.

Cada perfil declara de ONDE vieram seus números (`source`) e se eles foram
conferidos no regulamento vigente (`confirmed`). O relatório mostra isso ao
árbitro: um número que ninguém conferiu não pode se passar por regulamento.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping


@dataclass(frozen=True)
class RatingRegulation:
    """Parâmetros de um regulamento de rating para um ritmo."""

    code: str
    label: str
    source: str
    confirmed: bool

    # Fator K. A ordem de aplicação está em `kfactor.py`, que é quem sabe
    # combinar estas faixas; aqui só moram os números.
    k_new: int
    k_new_games: int
    k_youth: int
    k_youth_max_rating: int
    k_top: int
    k_top_rating: int
    k_default: int
    # Teto de K x n no período de rating (0 = sem teto).
    k_games_cap: int

    # Piso: abaixo disso o rating não é publicado.
    rating_floor: int

    # Rating inicial de quem ainda não tem rating.
    initial_min_games: int
    initial_max_rating: int
    initial_dummy_opponents: int
    initial_dummy_rating: int

    def with_overrides(self, overrides: Mapping[str, Any]) -> "RatingRegulation":
        """Aplica os valores que o árbitro editou, ignorando o que veio vazio."""
        changes: dict[str, Any] = {}
        for field_name, current in vars(self).items():
            if field_name in ("code", "label", "source", "confirmed"):
                continue
            raw = overrides.get(field_name)
            if raw is None or str(raw).strip() == "":
                continue
            try:
                changes[field_name] = int(str(raw).strip())
            except (TypeError, ValueError):
                continue
        if not changes:
            return self
        return replace(self, **changes)

    def as_dict(self) -> dict[str, Any]:
        return dict(vars(self))
