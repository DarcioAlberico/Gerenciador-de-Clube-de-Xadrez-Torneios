"""Categorias configuráveis por torneio (ORG-01) — motor puro.

Divisão: `definition` descreve uma categoria como DADO, `matching` responde se
um jogador pertence a ela, `defaults` guarda o conjunto que reproduz o
comportamento anterior ao ORG-01, e `assignment` combina os dois para dizer de
quais categorias o jogador participa e quais são as dele. Nenhum módulo daqui
toca em banco.
"""

from __future__ import annotations

from src.services.categories.assignment import (
    awardable_names,
    category_of_kind,
    matching_categories,
    narrowest_by_kind,
    primary_category,
)
from src.services.categories.defaults import (
    DEFAULT_AGE_BANDS,
    DEFAULT_RATING_BANDS,
    DEFAULT_SENIOR_BANDS,
    FEMALE_CATEGORY,
    default_categories,
)
from src.services.categories.definition import (
    AGE,
    KIND_LABELS,
    KINDS,
    OPEN,
    RATING,
    SEX,
    TAG,
    CategoryDefinition,
    from_row,
    normalize,
)
from src.services.categories.rankings import (
    categories_of,
    category_names,
    category_standings,
    group_by_category,
)
from src.services.categories.matching import (
    age_in_year,
    birth_year,
    matches,
    normalized_sex,
    reference_year_of,
)

__all__ = [
    "AGE",
    "DEFAULT_AGE_BANDS",
    "DEFAULT_RATING_BANDS",
    "DEFAULT_SENIOR_BANDS",
    "FEMALE_CATEGORY",
    "KINDS",
    "KIND_LABELS",
    "OPEN",
    "RATING",
    "SEX",
    "TAG",
    "CategoryDefinition",
    "age_in_year",
    "awardable_names",
    "birth_year",
    "categories_of",
    "category_names",
    "category_of_kind",
    "category_standings",
    "default_categories",
    "from_row",
    "group_by_category",
    "matches",
    "matching_categories",
    "narrowest_by_kind",
    "normalize",
    "normalized_sex",
    "primary_category",
    "reference_year_of",
]
