"""Categorias de competição — fachada do pacote ``src.services.categories``.

As faixas viviam aqui como constantes (Sub-08 a Sub-20, S50+/S65+, cortes de
1400/1800/2200) e por isso um edital fora do padrão não tinha onde caber. Na
`ORG-01` elas viraram DADO por torneio; este módulo continua sendo o ponto de
entrada de quem já o importava — banco de membros e de jogadores.

Quem chama sem passar `definitions` recebe o conjunto padrão, que reproduz
exatamente o comportamento anterior: é o caso do cadastro de membros, que não
pertence a torneio nenhum.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from src.services.categories import (
    AGE,
    RATING,
    CategoryDefinition,
    age_in_year,
    awardable_names,
    birth_year,
    category_of_kind,
    default_categories,
    primary_category,
    reference_year_of,
)
from src.services.categories.defaults import (
    ADULT_CATEGORY,
    DEFAULT_AGE_BANDS,
    DEFAULT_RATING_BANDS,
    DEFAULT_SENIOR_BANDS,
    OPEN_RATING_CATEGORY,
)

SENIOR_65_CATEGORY = "S65+"
SENIOR_50_CATEGORY = "S50+"

AGE_CATEGORY_LIMITS = DEFAULT_AGE_BANDS
RATING_CATEGORY_LIMITS = DEFAULT_RATING_BANDS

AGE_CATEGORY_VALUES = {
    ADULT_CATEGORY,
    *(label for label, _limit in DEFAULT_SENIOR_BANDS),
    *(label for label, _limit in DEFAULT_AGE_BANDS),
}
RATING_CATEGORY_VALUES = {
    OPEN_RATING_CATEGORY,
    *(label for label, _limit in DEFAULT_RATING_BANDS),
}
AUTO_CATEGORY_VALUES = {*AGE_CATEGORY_VALUES, *RATING_CATEGORY_VALUES}


def birth_year_from_date(value: Any) -> int | None:
    return birth_year(value)


def year_from_date(value: Any) -> int | None:
    return birth_year(value)


def reference_year(tournament: Mapping[str, Any] | None = None) -> int:
    if tournament:
        for key in ("start_date", "end_date", "created_at"):
            year = year_from_date(tournament.get(key))
            if year:
                return year
    return date.today().year


def age_category(birth_date: Any, year: int) -> str:
    """Categoria etária no conjunto padrão (compatibilidade)."""
    return category_of_kind(
        default_categories(), AGE, player={"birth_date": birth_date}, reference_year=year
    )


def rating_category(rating: Any) -> str:
    """Categoria de rating no conjunto padrão (compatibilidade)."""
    try:
        value = int(rating or 0)
    except (TypeError, ValueError):
        return ""
    return category_of_kind(
        default_categories(), RATING, player={}, reference_year=date.today().year, rating=value
    )


def special_prize_tags(
    *,
    sex: Any = "",
    member_type: Any = "",
    city: Any = "",
    player_club: Any = "",
    tournament_location: Any = "",
    tournament_club_name: Any = "",
    tournament_club_city: Any = "",
) -> str:
    """Marcas do jogador que não vêm de faixa: feminino, sócio e local.

    Continua aqui porque marca não é faixa: ela sai do cadastro (sexo, tipo de
    sócio, cidade) e não de um intervalo. As categorias do tipo `tag` consomem
    o que esta função produz.
    """
    from src.services.categories.matching import normalized_sex

    tags = []
    if normalized_sex(sex) == "F":
        tags.append("Feminino")

    if str(member_type or "").strip().casefold() == "socio":
        tags.append("Socio do Clube")

    local_sources = {
        str(tournament_location or "").strip().casefold(),
        str(tournament_club_name or "").strip().casefold(),
        str(tournament_club_city or "").strip().casefold(),
    }
    local_sources.discard("")
    candidate_values = {
        str(city or "").strip().casefold(),
        str(player_club or "").strip().casefold(),
    }
    candidate_values.discard("")
    if local_sources and candidate_values and local_sources.intersection(candidate_values):
        tags.append("Melhor Local")

    return "; ".join(dict.fromkeys(tags))


def competition_category_payload(
    *,
    birth_date: Any = "",
    rating: Any = 0,
    category: Any = "",
    year: int | None = None,
    sex: Any = "",
    member_type: Any = "",
    city: Any = "",
    player_club: Any = "",
    tournament_location: Any = "",
    tournament_club_name: Any = "",
    tournament_club_city: Any = "",
    definitions: Sequence[CategoryDefinition] | None = None,
    reference_date: Any = "",
) -> dict[str, str]:
    """Categorias do jogador: a principal, as por dimensão e as premiáveis.

    `definitions` vazio significa o conjunto padrão — é o cadastro de membros,
    que não pertence a torneio nenhum e por isso não tem edital.
    """
    rules = list(definitions) if definitions else default_categories()
    resolved_year = reference_year_of(reference_date) or year or date.today().year

    tags = special_prize_tags(
        sex=sex,
        member_type=member_type,
        city=city,
        player_club=player_club,
        tournament_location=tournament_location,
        tournament_club_name=tournament_club_name,
        tournament_club_city=tournament_club_city,
    )
    player = {"birth_date": birth_date, "sex": sex, "prize_tags": tags}
    try:
        rating_value = int(rating or 0)
    except (TypeError, ValueError):
        rating_value = 0

    return {
        "category": primary_category(
            rules, player, reference_year=resolved_year, rating=rating_value, current=category
        ),
        "age_category": category_of_kind(
            rules, AGE, player=player, reference_year=resolved_year, rating=rating_value
        ),
        "rating_category": category_of_kind(
            rules, RATING, player=player, reference_year=resolved_year, rating=rating_value
        ),
        "categories": "; ".join(
            awardable_names(
                rules, player=player, reference_year=resolved_year, rating=rating_value
            )
        ),
        "prize_tags": tags,
    }


__all__ = [
    "ADULT_CATEGORY",
    "AGE_CATEGORY_LIMITS",
    "AGE_CATEGORY_VALUES",
    "AUTO_CATEGORY_VALUES",
    "OPEN_RATING_CATEGORY",
    "RATING_CATEGORY_LIMITS",
    "RATING_CATEGORY_VALUES",
    "SENIOR_50_CATEGORY",
    "SENIOR_65_CATEGORY",
    "age_category",
    "age_in_year",
    "birth_year_from_date",
    "competition_category_payload",
    "rating_category",
    "reference_year",
    "special_prize_tags",
    "year_from_date",
]
