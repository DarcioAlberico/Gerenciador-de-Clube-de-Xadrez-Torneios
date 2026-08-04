"""Normas e títulos FIDE conforme o Handbook B.01.

Divisão dos módulos: ``handbook`` só tem regulamento, ``opponents`` decide que
partida conta e com que rating, ``evaluation`` julga uma norma, ``report``
monta o relatório do torneio e ``it3`` descreve o certificado. O desenho do PDF
mora em ``it3_pdf``, único módulo do pacote que toca em arquivo.
"""

from __future__ import annotations

from src.services.norms.evaluation import (
    Indicator,
    NormEvaluation,
    evaluate_norm,
    evaluate_norms,
)
from src.services.norms.handbook import (
    FIDE_TITLES,
    NORM_REQUIREMENTS,
    NormRequirement,
    applicable_norms,
    holds_level_title,
    is_title_holder,
    limits_for,
    limits_table,
)
from src.services.norms.it3 import DISCLAIMER, IT3Certificate, IT3Game, build_certificate
from src.services.norms.opponents import NormOpponent, adjusted_ratings, collect_opponents
from src.services.norms.report import (
    NormCandidate,
    build_norm_report,
    collect_tournament_opponents,
    is_round_robin,
    norm_candidates,
)

__all__ = [
    "DISCLAIMER",
    "FIDE_TITLES",
    "IT3Certificate",
    "IT3Game",
    "Indicator",
    "NORM_REQUIREMENTS",
    "NormCandidate",
    "NormEvaluation",
    "NormOpponent",
    "NormRequirement",
    "norm_candidates",
    "adjusted_ratings",
    "applicable_norms",
    "build_certificate",
    "build_norm_report",
    "collect_opponents",
    "collect_tournament_opponents",
    "evaluate_norm",
    "evaluate_norms",
    "holds_level_title",
    "is_round_robin",
    "is_title_holder",
    "limits_for",
    "limits_table",
]
