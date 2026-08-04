"""As categorias de um jogador (puro).

Duas perguntas diferentes, e o ORG-01 precisa das duas:

- **de quais categorias ele participa?** Todas as que casam — é o que a
  classificação filtrável usa, porque um Sub-10 pode disputar o Sub-12 se o
  edital deixar;
- **quais são as dele?** A mais estreita de cada dimensão — Sub-10, Sub-1400,
  Feminino. É o que vale como categoria premiável e o que vai para o cadastro
  do jogador. Guardar as seis faixas etárias que um menino de 10 anos satisfaz
  encheria a tela sem dizer nada.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.categories.definition import (
    AGE,
    OPEN,
    RATING,
    SEX,
    TAG,
    CategoryDefinition,
)
from src.services.categories.matching import matches

# Teto usado para medir uma faixa aberta ("50 anos ou mais"). Não é limite de
# idade de ninguém: serve só para dizer que S65+ é mais estreita que S50+.
_OPEN_END = 120


def _span(definition: CategoryDefinition) -> int:
    """Largura da faixa. Menor = mais específica."""
    if definition.kind == AGE:
        low = int(definition.min_value or 0)
        high = int(definition.max_value or 0) or _OPEN_END
        return max(high - low, 0)
    if definition.kind == RATING:
        low = int(definition.min_value or 0)
        high = int(definition.max_value or 0) or 4000
        return max(high - low, 0)
    return 0


def matching_categories(
    definitions: Sequence[CategoryDefinition],
    player: Mapping[str, Any],
    *,
    reference_year: int,
    rating: int = 0,
) -> list[CategoryDefinition]:
    """Todas as categorias que aceitam o jogador, na ordem cadastrada."""
    found = [
        definition
        for definition in definitions
        if definition.is_valid
        and matches(definition, player, reference_year=reference_year, rating=rating)
    ]
    return sorted(found, key=lambda item: (int(item.position or 0), item.name.casefold()))


def narrowest_by_kind(
    definitions: Sequence[CategoryDefinition],
    player: Mapping[str, Any],
    *,
    reference_year: int,
    rating: int = 0,
) -> list[CategoryDefinition]:
    """A categoria mais específica de cada dimensão, mais todas as marcas.

    Idade e rating rendem UMA cada (a mais estreita); sexo rende uma; marcas
    rendem todas, porque "Sócio" e "Melhor Local" não competem entre si.
    """
    found = matching_categories(
        definitions, player, reference_year=reference_year, rating=rating
    )
    chosen: list[CategoryDefinition] = []
    for kind in (AGE, RATING, SEX):
        candidates = [item for item in found if item.kind == kind]
        if candidates:
            chosen.append(min(candidates, key=lambda item: (_span(item), int(item.position or 0))))
    chosen.extend(item for item in found if item.kind in (TAG, OPEN))
    return sorted(chosen, key=lambda item: (int(item.position or 0), item.name.casefold()))


def awardable_names(definitions: Sequence[CategoryDefinition], **kwargs: Any) -> list[str]:
    """Nomes das categorias premiáveis do jogador, sem repetição."""
    return list(
        dict.fromkeys(
            item.name for item in narrowest_by_kind(definitions, **kwargs) if item.awards
        )
    )


def category_of_kind(
    definitions: Sequence[CategoryDefinition], kind: str, **kwargs: Any
) -> str:
    """Nome da categoria mais específica de uma dimensão (`""` se nenhuma)."""
    for item in narrowest_by_kind(definitions, **kwargs):
        if item.kind == kind:
            return item.name
    return ""


def primary_category(
    definitions: Sequence[CategoryDefinition],
    player: Mapping[str, Any],
    *,
    reference_year: int,
    rating: int = 0,
    current: Any = "",
) -> str:
    """Categoria principal do jogador — idade na frente do rating.

    Mantém a regra que já valia, inclusive no detalhe que é fácil perder: a
    categoria escrita à mão só cede para o cálculo **da sua própria dimensão**.
    Um "Sub-18" gravado num cadastro SEM data de nascimento continua "Sub-18" —
    deixá-lo virar a faixa de rating trocaria um dado que alguém informou por
    outro que o programa deduziu de outra coisa.
    """
    kwargs = {"player": player, "reference_year": reference_year, "rating": rating}
    computed_age = category_of_kind(definitions, AGE, **kwargs)
    computed_rating = category_of_kind(definitions, RATING, **kwargs)

    manual = str(current or "").strip()
    if not manual:
        return computed_age or computed_rating

    if manual in {item.name for item in definitions if item.kind == AGE} and computed_age:
        return computed_age
    if manual in {item.name for item in definitions if item.kind == RATING} and computed_rating:
        return computed_rating
    return manual
