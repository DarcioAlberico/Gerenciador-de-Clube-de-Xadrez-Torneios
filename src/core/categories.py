from __future__ import annotations

from datetime import date
from typing import Any, Mapping

AGE_CATEGORY_LIMITS = (
    (8, "Sub-08"),
    (10, "Sub-10"),
    (12, "Sub-12"),
    (14, "Sub-14"),
    (16, "Sub-16"),
    (18, "Sub-18"),
    (20, "Sub-20"),
)
RATING_CATEGORY_LIMITS = (
    (1400, "Sub-1400"),
    (1800, "Sub-1800"),
    (2200, "Sub-2200"),
)
SENIOR_65_CATEGORY = "S65+"
SENIOR_50_CATEGORY = "S50+"
ADULT_CATEGORY = "Adulto"
OPEN_RATING_CATEGORY = "Aberto"

AGE_CATEGORY_VALUES = {
    ADULT_CATEGORY,
    SENIOR_50_CATEGORY,
    SENIOR_65_CATEGORY,
    *(label for _limit, label in AGE_CATEGORY_LIMITS),
}
RATING_CATEGORY_VALUES = {
    OPEN_RATING_CATEGORY,
    *(label for _limit, label in RATING_CATEGORY_LIMITS),
}
AUTO_CATEGORY_VALUES = {
    *AGE_CATEGORY_VALUES,
    *RATING_CATEGORY_VALUES,
}


def birth_year_from_date(value: Any) -> int | None:
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


def year_from_date(value: Any) -> int | None:
    return birth_year_from_date(value)


def reference_year(tournament: Mapping[str, Any] | None = None) -> int:
    if tournament:
        for key in ("start_date", "end_date", "created_at"):
            year = year_from_date(tournament.get(key))
            if year:
                return year
    return date.today().year


def age_category(birth_date: Any, year: int) -> str:
    birth_year = birth_year_from_date(birth_date)
    if not birth_year:
        return ""
    age = year - birth_year
    if age < 0:
        return ""
    for limit, label in AGE_CATEGORY_LIMITS:
        if age <= limit:
            return label
    if age >= 65:
        return SENIOR_65_CATEGORY
    if age >= 50:
        return SENIOR_50_CATEGORY
    return ADULT_CATEGORY


def rating_category(rating: Any) -> str:
    try:
        value = int(rating or 0)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    for limit, label in RATING_CATEGORY_LIMITS:
        if value < limit:
            return label
    return OPEN_RATING_CATEGORY


def resolved_primary_category(current_category: Any, computed_age: str, computed_rating: str) -> str:
    category = str(current_category or "").strip()
    if not category:
        return computed_age or computed_rating
    if category in AGE_CATEGORY_VALUES and computed_age:
        return computed_age
    if category in RATING_CATEGORY_VALUES and computed_rating:
        return computed_rating
    return category


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
    tags = []
    sex_value = str(sex or "").strip().casefold()
    if sex_value in {"f", "fem", "feminino", "female", "w", "woman"}:
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
) -> dict[str, str]:
    reference = year or date.today().year
    computed_age = age_category(birth_date, reference)
    computed_rating = rating_category(rating)
    return {
        "category": resolved_primary_category(category, computed_age, computed_rating),
        "age_category": computed_age,
        "rating_category": computed_rating,
        "prize_tags": special_prize_tags(
            sex=sex,
            member_type=member_type,
            city=city,
            player_club=player_club,
            tournament_location=tournament_location,
            tournament_club_name=tournament_club_name,
            tournament_club_city=tournament_club_city,
        ),
    }
