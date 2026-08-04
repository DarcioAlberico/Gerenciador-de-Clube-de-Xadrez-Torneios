"""Rating inicial de quem ainda não tem rating (B.02 8.2) — puro.

O relatório antigo simplesmente não calculava: jogador sem rating saía só com
performance, e o árbitro não tinha o número que a federação vai publicar.

A conta não é a performance pura. O B.02 8.2.2 acrescenta **dois adversários
fictícios de 1800, com empate contra cada um** — é o freio que impede um Ru
absurdo de quem enfrentou pouca gente, e é a diferença entre o número certo e
uma performance disfarçada de rating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.services.rating.regulation import RatingRegulation
from src.services.rating.tables import fide_performance

NOT_ENOUGH_GAMES = "partidas insuficientes"
ZERO_SCORE = "zerou contra ratados (8.2.1)"
BELOW_FLOOR = "abaixo do piso"
CAPPED = "limitado ao teto de rating inicial"
PUBLISHED = "estimado"


@dataclass(frozen=True)
class InitialRating:
    """Estimativa de rating inicial e por que ela vale (ou não)."""

    games: int
    score: float
    average_opponent: int
    rating: int
    publishable: bool
    reason: str


def initial_rating(
    regulation: RatingRegulation,
    opponent_ratings: Sequence[int],
    score: float,
) -> InitialRating:
    """Ru a partir das partidas contra adversários COM rating."""
    ratings = [int(value) for value in opponent_ratings if int(value or 0) > 0]
    games = len(ratings)
    points = round(float(score), 2)

    if games < regulation.initial_min_games:
        return InitialRating(games, points, 0, 0, False, NOT_ENOUGH_GAMES)
    if points <= 0:
        # 8.2.1 — zerar na estreia não gera rating; o resultado é desprezado.
        return InitialRating(games, points, 0, 0, False, ZERO_SCORE)

    dummies = max(int(regulation.initial_dummy_opponents or 0), 0)
    total_games = games + dummies
    total_score = points + dummies * 0.5
    average = int(
        (sum(ratings) + dummies * int(regulation.initial_dummy_rating or 0)) / total_games + 0.5
    )

    rating = fide_performance(average, total_score, total_games)
    reason = PUBLISHED
    if regulation.initial_max_rating and rating > regulation.initial_max_rating:
        rating = int(regulation.initial_max_rating)
        reason = CAPPED
    if rating < regulation.rating_floor:
        return InitialRating(games, points, average, rating, False, BELOW_FLOOR)
    return InitialRating(games, points, average, rating, True, reason)
