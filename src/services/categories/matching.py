"""Quem pertence a que categoria (puro).

Recebe a definição e o jogador como mapas e responde sim ou não. Não sabe o que
é banco, torneio nem prêmio.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.services.categories.definition import (
    AGE,
    OPEN,
    RATING,
    SEX,
    TAG,
    CategoryDefinition,
)

FEMALE_VALUES = {"F", "FEM", "FEMININO", "FEMALE", "W", "WOMAN"}
MALE_VALUES = {"M", "MASC", "MASCULINO", "MALE"}


def birth_year(value: Any) -> int | None:
    """Ano de nascimento a partir de `YYYY`, `YYYY-MM-DD` ou `DD/MM/YYYY`."""
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    for separator in ("-", "/"):
        parts = cleaned.split(separator)
        if len(parts) != 3:
            continue
        first, _middle, last = (part.strip() for part in parts)
        year = first if len(first) == 4 else last if len(last) == 4 else ""
        if year.isdigit():
            return int(year)
    if len(cleaned) >= 4 and cleaned[:4].isdigit():
        return int(cleaned[:4])
    return None


def reference_year_of(value: Any) -> int | None:
    """Ano de uma data de referência (`2026-01-01` -> 2026)."""
    return birth_year(value)


def age_in_year(birth_date: Any, reference: int) -> int | None:
    """Idade que o jogador COMPLETA no ano de referência.

    É a conta do edital de base ("nascidos em ou depois de"), e não a idade no
    dia: a FIDE só publica o ANO de nascimento, e metade dos cadastros também.
    Usar a idade exata daria duas contas diferentes para o mesmo torneio,
    conforme o jogador tivesse data completa ou não.
    """
    year = birth_year(birth_date)
    if not year or not reference:
        return None
    age = int(reference) - int(year)
    return age if age >= 0 else None


def normalized_sex(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in FEMALE_VALUES:
        return "F"
    if text in MALE_VALUES:
        return "M"
    return ""


def player_tags(player: Mapping[str, Any]) -> set[str]:
    raw = str(player.get("prize_tags") or "")
    return {part.strip().casefold() for part in raw.replace(",", ";").split(";") if part.strip()}


def matches(
    definition: CategoryDefinition,
    player: Mapping[str, Any],
    *,
    reference_year: int,
    rating: int = 0,
) -> bool:
    """O jogador pertence à categoria?

    `rating` vem de fora porque quem escolhe a base (FIDE, nacional ou o rating
    de inscrição) é o torneio, não a categoria.
    """
    if definition.kind == OPEN:
        return True

    if definition.kind == AGE:
        year = reference_year_of(definition.reference_date) or reference_year
        age = age_in_year(player.get("birth_date"), year)
        if age is None:
            return False
        # `max_value` INCLUSIVO: "Sub-12" aceita quem completa 12.
        if definition.min_value and age < definition.min_value:
            return False
        return not (definition.max_value and age > definition.max_value)

    if definition.kind == RATING:
        value = int(rating or 0)
        if value <= 0:
            return False
        if definition.min_value and value < definition.min_value:
            return False
        # `max_value` EXCLUSIVO: "Sub-1400" recusa quem tem exatamente 1400.
        return not (definition.max_value and value >= definition.max_value)

    if definition.kind == SEX:
        wanted = normalized_sex(definition.sex)
        return bool(wanted) and normalized_sex(player.get("sex")) == wanted

    if definition.kind == TAG:
        wanted = str(definition.tag or "").strip().casefold()
        return bool(wanted) and wanted in player_tags(player)

    return False
