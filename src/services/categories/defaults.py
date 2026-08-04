"""O conjunto padrão de categorias — o comportamento histórico, como dado.

Um torneio sem categorias cadastradas tem de continuar se comportando como
antes do ORG-01: as mesmas faixas, os mesmos nomes, a mesma classificação. Por
isso o padrão não é "nenhuma categoria", e sim ESTA lista — que é a tradução
literal das constantes que viviam em `core/categories.py`.

A novidade é o Feminino: ele existia só como tag de prêmio e nunca gerou
classificação. Aqui ele é categoria, e por isso sai da tabela do padrão.
"""

from __future__ import annotations

from src.services.categories.definition import AGE, RATING, SEX, CategoryDefinition

# (rótulo, idade máxima) — máximo INCLUSIVO, como o edital escreve.
DEFAULT_AGE_BANDS = (
    ("Sub-08", 8),
    ("Sub-10", 10),
    ("Sub-12", 12),
    ("Sub-14", 14),
    ("Sub-16", 16),
    ("Sub-18", 18),
    ("Sub-20", 20),
)

# (rótulo, idade mínima) para as faixas de veterano.
DEFAULT_SENIOR_BANDS = (
    ("S50+", 50),
    ("S65+", 65),
)

# (rótulo, rating máximo) — máximo EXCLUSIVO: "Sub-1400" recusa 1400.
DEFAULT_RATING_BANDS = (
    ("Sub-1400", 1400),
    ("Sub-1800", 1800),
    ("Sub-2200", 2200),
)

# Faixas de sobra do comportamento antigo: quem não é de base nem veterano era
# "Adulto", e quem passava do último corte de rating era "Aberto". Elas viram
# faixas explicitas para que um torneio sem configuracao continue produzindo os
# MESMOS nomes de categoria de antes do ORG-01.
ADULT_CATEGORY = "Adulto"
ADULT_RANGE = (21, 49)
OPEN_RATING_CATEGORY = "Aberto"
OPEN_RATING_FLOOR = 2200

FEMALE_CATEGORY = "Feminino"


def default_categories() -> list[CategoryDefinition]:
    """As categorias de um torneio que não configurou nenhuma."""
    definitions: list[CategoryDefinition] = []
    position = 0

    for label, limit in DEFAULT_AGE_BANDS:
        definitions.append(
            CategoryDefinition(name=label, kind=AGE, max_value=limit, position=position)
        )
        position += 1

    definitions.append(
        CategoryDefinition(
            name=ADULT_CATEGORY,
            kind=AGE,
            min_value=ADULT_RANGE[0],
            max_value=ADULT_RANGE[1],
            position=position,
        )
    )
    position += 1

    for label, floor in DEFAULT_SENIOR_BANDS:
        definitions.append(
            CategoryDefinition(name=label, kind=AGE, min_value=floor, position=position)
        )
        position += 1

    for label, limit in DEFAULT_RATING_BANDS:
        definitions.append(
            CategoryDefinition(name=label, kind=RATING, max_value=limit, position=position)
        )
        position += 1

    definitions.append(
        CategoryDefinition(
            name=OPEN_RATING_CATEGORY,
            kind=RATING,
            min_value=OPEN_RATING_FLOOR,
            position=position,
        )
    )
    position += 1

    definitions.append(
        CategoryDefinition(name=FEMALE_CATEGORY, kind=SEX, sex="F", position=position)
    )
    return definitions
