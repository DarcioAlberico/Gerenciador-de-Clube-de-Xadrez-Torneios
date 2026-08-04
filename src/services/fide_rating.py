"""Variação de rating — fachada do pacote ``src.services.rating``.

Funções puras que estimam Ro, K, n, W, We, ΔElo, Rc e Rp a partir dos jogadores
e dos emparceiramentos. É **estimativa de apoio ao árbitro**, não homologação:
a federação continua sendo a autoridade do rating.

O motor foi para ``src/services/rating`` na FED-07, quando o regulamento deixou
de ser `if`s no meio do cálculo e virou DADO (faixas de K, piso, regra de
estreia) por base e por ritmo. Este módulo continua sendo o ponto de importação
do resto do sistema.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.rating import (
    MAX_RATING_DIFF,
    build_report_rows,
    fide_dp,
    fide_expected_score,
    fide_performance,
    k_factor,
    player_rating_for,
    player_rating_for_type,
    regulation_for,
)
from src.services.time_control import STANDARD

__all__ = [
    "MAX_RATING_DIFF",
    "build_fide_report_rows",
    "fide_dp",
    "fide_expected_score",
    "fide_k_factor",
    "fide_performance",
    "player_rating_for",
    "player_rating_for_type",
]


def fide_k_factor(
    rating: int,
    *,
    games_played: int | None = None,
    birth_year: int | None = None,
    tournament_year: int | None = None,
    k_override: int | None = None,
) -> int:
    """Fator K no regulamento FIDE standard (só o número, sem a origem)."""
    return k_factor(
        regulation_for("fide", STANDARD),
        rating,
        games_played=games_played,
        birth_year=birth_year,
        tournament_year=tournament_year,
        k_override=k_override,
    )[0]


def build_fide_report_rows(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = "fide",
    *,
    tournament_year: int | None = None,
    speed: str = STANDARD,
) -> list[dict[str, Any]]:
    """Linhas do relatório de variação de rating (ritmo standard por padrão)."""
    return build_report_rows(
        players,
        closed_pairings,
        rating_type,
        tournament_year=tournament_year,
        speed=speed,
    )
