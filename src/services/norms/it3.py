"""Modelo do certificado IT3 (norma de título) — puro, sem desenho e sem banco.

O IT3 é o formulário que a FIDE pede para submeter uma norma: identifica o
torneio, o candidato e lista partida a partida os adversários com título,
rating e resultado, fechando com Ra, Rp e as contagens que o B.01 cobra.

Os rótulos do formulário saem em inglês de propósito — o documento é entregue à
FIDE, e a IT3 oficial é em inglês. O aviso de que isto é apoio ao árbitro, e não
homologação, sai em português, porque é para quem opera o programa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.services.norms.evaluation import NormEvaluation
from src.services.norms.handbook import NORM_REQUIREMENTS
from src.services.norms.opponents import NormOpponent, adjusted_ratings

DISCLAIMER = (
    "Documento gerado pelo Albericus como APOIO ao árbitro: reúne os dados do "
    "torneio e os indicadores do Handbook B.01. A concessão da norma e do "
    "título é exclusiva da FIDE."
)

_RESULT_LABELS = {1.0: "1", 0.5: "½", 0.0: "0"}


@dataclass(frozen=True)
class IT3Game:
    """Uma linha da tabela de partidas do IT3."""

    round_number: int
    opponent_name: str
    federation: str
    title: str
    rating: int
    rating_used: int
    color: str
    result: str


@dataclass(frozen=True)
class IT3Certificate:
    """Certificado IT3 preenchido de um candidato para uma norma."""

    tournament_name: str
    location: str
    start_date: str
    end_date: str
    organizing_federation: str
    tournament_type: str
    time_control: str
    rounds: int
    event_id: str
    chief_arbiter: str
    candidate_name: str
    candidate_fide_id: str
    candidate_federation: str
    candidate_rating: int
    candidate_title: str
    norm_title: str
    norm_label: str
    score: float
    average_opponent: int
    performance: int
    title_holders: int
    level_title_holders: int
    level_label: str
    other_federations: int
    meets: bool
    games: list[IT3Game] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def game_count(self) -> int:
        return len(self.games)


def format_date(value: object) -> str:
    """`YYYY-MM-DD` vira `DD/MM/YYYY`; o resto passa como está."""
    text = str(value or "").strip()
    parts = text.split("-")
    if len(parts) == 3 and len(parts[0]) == 4 and all(part.isdigit() for part in parts):
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return text


def result_label(points: float) -> str:
    return _RESULT_LABELS.get(round(float(points) * 2) / 2, f"{float(points):g}")


def build_games(opponents: Sequence[NormOpponent], norm_title: str) -> list[IT3Game]:
    """Tabela de partidas com o rating que a norma usou em cada adversário."""
    requirement = NORM_REQUIREMENTS[norm_title]
    used = adjusted_ratings(opponents, requirement)
    return [
        IT3Game(
            round_number=opponent.round_number,
            opponent_name=opponent.name,
            federation=opponent.federation,
            title=opponent.title,
            rating=opponent.rating,
            rating_used=rating_used,
            color=opponent.color,
            result=result_label(opponent.points),
        )
        for opponent, rating_used in zip(opponents, used)
    ]


def build_certificate(
    tournament: Mapping[str, Any],
    settings: Mapping[str, Any],
    candidate: Mapping[str, Any],
    opponents: Sequence[NormOpponent],
    evaluation: NormEvaluation,
    *,
    candidate_name: str,
    candidate_rating: int,
    chief_arbiter: str = "",
    tournament_type: str = "",
    rounds: int = 0,
) -> IT3Certificate:
    requirement = NORM_REQUIREMENTS[evaluation.title]
    return IT3Certificate(
        tournament_name=str(tournament.get("name") or ""),
        location=str(tournament.get("location") or ""),
        start_date=format_date(tournament.get("start_date")),
        end_date=format_date(tournament.get("end_date")),
        organizing_federation=str(settings.get("federation") or "").strip().upper(),
        tournament_type=tournament_type,
        time_control=str(tournament.get("time_control") or ""),
        rounds=int(rounds or 0),
        event_id=str(settings.get("fide_event_id") or "").strip(),
        chief_arbiter=chief_arbiter,
        candidate_name=candidate_name,
        candidate_fide_id=str(candidate.get("fide_id") or "").strip(),
        candidate_federation=str(candidate.get("federation_id") or "").strip().upper(),
        candidate_rating=int(candidate_rating or 0),
        candidate_title=str(candidate.get("title") or "").strip().upper(),
        norm_title=evaluation.title,
        norm_label=evaluation.label,
        score=evaluation.score,
        average_opponent=evaluation.average_opponent,
        performance=evaluation.performance,
        title_holders=evaluation.title_holders,
        level_title_holders=evaluation.level_title_holders,
        level_label=requirement.level_label,
        other_federations=evaluation.other_federations,
        meets=evaluation.meets,
        games=build_games(opponents, evaluation.title),
        missing=list(evaluation.missing),
    )
