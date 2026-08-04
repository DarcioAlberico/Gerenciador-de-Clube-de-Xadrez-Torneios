"""Rating: tabelas do Elo, regulamento como dado e relatório (FED-07).

Divisão: `tables` só tem a matemática do Elo; `regulation` descreve um
regulamento (K, piso, estreia) como DADO; `profiles` guarda os perfis por base e
ritmo e escolhe o do torneio; `kfactor` e `initial` aplicam o regulamento; e
`report` monta as linhas. Nenhum módulo daqui toca em banco.
"""

from __future__ import annotations

from src.services.rating.initial import InitialRating, initial_rating
from src.services.rating.kfactor import k_factor
from src.services.rating.profiles import (
    BASE_LABELS,
    CBX,
    FIDE,
    REGULATIONS,
    SPEED_CHOICES,
    editable_fields,
    parse_regulation_overrides,
    regulation_for,
    regulation_from_settings,
    resolve_speed,
    serialize_regulation_overrides,
)
from src.services.rating.regulation import RatingRegulation
from src.services.rating.report import (
    build_report_rows,
    collect_rated_games,
    player_rating_for,
    player_rating_for_type,
)
from src.services.rating.tables import (
    MAX_RATING_DIFF,
    fide_dp,
    fide_expected_score,
    fide_performance,
)

__all__ = [
    "BASE_LABELS",
    "CBX",
    "FIDE",
    "MAX_RATING_DIFF",
    "REGULATIONS",
    "SPEED_CHOICES",
    "InitialRating",
    "RatingRegulation",
    "build_report_rows",
    "collect_rated_games",
    "editable_fields",
    "fide_dp",
    "fide_expected_score",
    "fide_performance",
    "initial_rating",
    "k_factor",
    "parse_regulation_overrides",
    "player_rating_for",
    "player_rating_for_type",
    "regulation_for",
    "regulation_from_settings",
    "resolve_speed",
    "serialize_regulation_overrides",
]
