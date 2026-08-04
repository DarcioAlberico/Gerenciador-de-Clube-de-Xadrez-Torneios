"""Julgamento de uma norma: indicadores do B.01 aplicados a um candidato.

Puro. Cada indicador carrega a cláusula que o originou — o árbitro precisa
poder conferir no Handbook o número que o programa cobrou dele.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from src.services.fide_rating import fide_performance
from src.services.norms import handbook
from src.services.norms.handbook import NormRequirement
from src.services.norms.opponents import (
    NormOpponent,
    adjusted_ratings,
    average_rating,
    federation_counts,
)

MINIMUM = "min"
MAXIMUM = "max"


@dataclass(frozen=True)
class Indicator:
    """Um requisito conferível: o que o regulamento pede e o que houve."""

    name: str
    rule: str
    required: float
    actual: float
    limit: str = MINIMUM

    @property
    def ok(self) -> bool:
        if self.limit == MAXIMUM:
            return self.actual <= self.required
        return self.actual >= self.required

    def as_text(self) -> str:
        if self.limit == MAXIMUM:
            return (
                f"{self.name} admite no máximo {_number(self.required)} "
                f"(obtido {_number(self.actual)}) — B.01 {self.rule}"
            )
        return (
            f"{self.name} requer {_number(self.required)} "
            f"(obtido {_number(self.actual)}) — B.01 {self.rule}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "rule": self.rule,
            "required": self.required,
            "actual": self.actual,
            "limit": self.limit,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class NormEvaluation:
    """Resultado da avaliação de UMA norma para UM candidato."""

    title: str
    label: str
    games: int
    score: float
    average_opponent: int
    performance: int
    title_holders: int
    level_title_holders: int
    other_federations: int
    own_federation_opponents: int
    largest_federation_opponents: int
    unrated_opponents: int
    indicators: list[Indicator] = field(default_factory=list)

    @property
    def meets(self) -> bool:
        return all(indicator.ok for indicator in self.indicators)

    @property
    def missing(self) -> list[str]:
        return [indicator.as_text() for indicator in self.indicators if not indicator.ok]

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "label": self.label,
            "meets": self.meets,
            "games": self.games,
            "score": self.score,
            "average_opponent": self.average_opponent,
            "performance": self.performance,
            "title_holders": self.title_holders,
            "level_title_holders": self.level_title_holders,
            "other_federations": self.other_federations,
            "own_federation_opponents": self.own_federation_opponents,
            "largest_federation_opponents": self.largest_federation_opponents,
            "unrated_opponents": self.unrated_opponents,
            "indicators": [indicator.as_dict() for indicator in self.indicators],
            "missing": self.missing,
        }


def _number(value: float) -> str:
    return str(int(value)) if float(value) == int(value) else f"{float(value):.2f}"


def evaluate_norm(
    candidate_federation: str,
    candidate_opponents: Sequence[NormOpponent],
    requirement: NormRequirement,
) -> NormEvaluation:
    """Avalia uma norma. `candidate_federation` fica FORA da conta de federações."""
    opponents = list(candidate_opponents)
    games = len(opponents)
    score = round(sum(opponent.points for opponent in opponents), 2)

    ratings = adjusted_ratings(opponents, requirement)
    average_opponent = average_rating(ratings)
    performance = fide_performance(average_opponent, score, games)

    own = str(candidate_federation or "").strip().upper()
    counts = federation_counts(opponents)
    other_federations = sorted(code for code in counts if code != own)

    title_holders = sum(1 for opponent in opponents if handbook.is_title_holder(opponent.title))
    level_holders = sum(
        1 for opponent in opponents if handbook.holds_level_title(opponent.title, requirement)
    )
    unrated = sum(1 for opponent in opponents if opponent.is_unrated)
    own_count = counts.get(own, 0) if own else 0
    largest = max(counts.values(), default=0)

    indicators = [
        Indicator("Partidas válidas", "1.4.1", handbook.MIN_GAMES, games),
        Indicator(
            "Pontuação mínima (35%)",
            "1.4.8.2",
            round(handbook.MIN_SCORE_RATIO * games, 2),
            score,
        ),
        Indicator("Performance (Rp)", "1.4.8.1", requirement.performance, performance),
        Indicator(
            "Média dos adversários (Ra)",
            "1.4.8.1",
            requirement.min_average_opponent,
            average_opponent,
        ),
        Indicator(
            "Adversários titulados (50%)",
            "1.4.5",
            handbook.min_title_holders(games),
            title_holders,
        ),
        Indicator(
            f"Adversários {requirement.level_label} (1/3, mín. 3)",
            "1.4.5",
            handbook.min_level_title_holders(games),
            level_holders,
        ),
        Indicator(
            "Federações além da do candidato",
            "1.4.3",
            handbook.MIN_OTHER_FEDERATIONS,
            len(other_federations),
        ),
        Indicator(
            "Adversários da federação do candidato",
            "1.4.4",
            handbook.max_own_federation(games),
            own_count,
            MAXIMUM,
        ),
        Indicator(
            "Adversários de uma mesma federação",
            "1.4.4",
            handbook.max_single_federation(games),
            largest,
            MAXIMUM,
        ),
        Indicator(
            "Adversários sem rating",
            "1.4.6",
            handbook.max_unrated(games),
            unrated,
            MAXIMUM,
        ),
    ]

    return NormEvaluation(
        title=requirement.code,
        label=requirement.label,
        games=games,
        score=score,
        average_opponent=average_opponent,
        performance=performance,
        title_holders=title_holders,
        level_title_holders=level_holders,
        other_federations=len(other_federations),
        own_federation_opponents=own_count,
        largest_federation_opponents=largest,
        unrated_opponents=unrated,
        indicators=indicators,
    )


def evaluate_norms(
    candidate_federation: str,
    sex: object,
    opponents: Sequence[NormOpponent],
) -> list[NormEvaluation]:
    """Todas as normas aplicáveis ao candidato, na ordem GM, IM, WGM, WIM."""
    return [
        evaluate_norm(candidate_federation, opponents, handbook.NORM_REQUIREMENTS[code])
        for code in handbook.applicable_norms(sex)
    ]
