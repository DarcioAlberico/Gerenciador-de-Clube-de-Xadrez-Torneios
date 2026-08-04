"""Perfis de regulamento por base e ritmo, e como o torneio escolhe o seu.

FIDE sai preenchido e conferido contra o B.02 em vigor desde 2024. CBX sai com
a forma certa e os valores marcados como NÃO conferidos: o regulamento nacional
não está publicado em lugar que o programa consiga ler, e inventar número de
regulamento é pior do que admitir que não se sabe. O árbitro edita os valores na
configuração do torneio, e o relatório diz que eles vieram dali.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from src.services.rating.regulation import RatingRegulation
from src.services.time_control import BLITZ, RAPID, STANDARD, classify_speed

FIDE = "fide"
CBX = "cbx"

BASE_LABELS = {FIDE: "FIDE", CBX: "CBX"}

_FIDE_SOURCE = "FIDE Handbook B.02, edicao em vigor desde 2024"
_CBX_SOURCE = "forma do B.02 com valores a CONFERIR no regulamento da CBX"


def _fide(code: str, label: str, *, source: str = _FIDE_SOURCE, confirmed: bool = True) -> RatingRegulation:
    """Perfil FIDE. As faixas de K são as mesmas nos três ritmos (B.02 7.3.3)."""
    return RatingRegulation(
        code=code,
        label=label,
        source=source,
        confirmed=confirmed,
        k_new=40,
        k_new_games=30,
        k_youth=40,
        k_youth_max_rating=2300,
        k_top=10,
        k_top_rating=2400,
        k_default=20,
        k_games_cap=700,
        rating_floor=1400,
        initial_min_games=5,
        initial_max_rating=2200,
        initial_dummy_opponents=2,
        initial_dummy_rating=1800,
    )


REGULATIONS: dict[tuple[str, str], RatingRegulation] = {
    (FIDE, STANDARD): _fide("fide_standard", "FIDE standard"),
    # O B.02 aplica as MESMAS faixas de K aos três ritmos; a regra de estreia do
    # rápido/blitz não foi conferida na edição vigente, então o perfil sai
    # marcado como não conferido em vez de afirmar o que não se leu.
    (FIDE, RAPID): _fide(
        "fide_rapid",
        "FIDE rápido",
        source=f"{_FIDE_SOURCE}; regra de estreia por analogia — CONFERIR",
        confirmed=False,
    ),
    (FIDE, BLITZ): _fide(
        "fide_blitz",
        "FIDE blitz",
        source=f"{_FIDE_SOURCE}; regra de estreia por analogia — CONFERIR",
        confirmed=False,
    ),
    (CBX, STANDARD): RatingRegulation(
        code="cbx_standard",
        label="CBX standard",
        source=_CBX_SOURCE,
        confirmed=False,
        k_new=40,
        k_new_games=30,
        k_youth=40,
        k_youth_max_rating=2300,
        # Único valor que se achou publicado: K=10 acima de 2300.
        k_top=10,
        k_top_rating=2300,
        k_default=20,
        k_games_cap=0,
        rating_floor=1400,
        initial_min_games=5,
        initial_max_rating=2200,
        initial_dummy_opponents=2,
        initial_dummy_rating=1800,
    ),
}
REGULATIONS[(CBX, RAPID)] = REGULATIONS[(CBX, STANDARD)]
REGULATIONS[(CBX, BLITZ)] = REGULATIONS[(CBX, STANDARD)]

SPEED_CHOICES = ("", STANDARD, RAPID, BLITZ)


def resolve_speed(time_control: object, override: object = "") -> tuple[str, str]:
    """`(ritmo, origem)`. A declaração do árbitro ganha do texto do ritmo.

    Origem entra no relatório porque muda o que o árbitro deve conferir: ritmo
    lido do texto pode estar lendo um campo mal preenchido; ritmo declarado é
    responsabilidade de quem declarou; e o padrão é o que se usa quando não há
    nem uma coisa nem outra.
    """
    declared = str(override or "").strip().lower()
    if declared in (STANDARD, RAPID, BLITZ):
        return declared, "declarado na configuração"
    detected = classify_speed(time_control)
    if detected:
        return detected, "deduzido do ritmo de jogo"
    return STANDARD, "padrão (ritmo de jogo não reconhecido)"


def regulation_for(
    base: str, speed: str, overrides: Mapping[str, Any] | None = None
) -> RatingRegulation:
    """Regulamento da base no ritmo, já com o que o árbitro editou aplicado."""
    key = (str(base or FIDE).strip().lower(), str(speed or STANDARD).strip().lower())
    regulation = REGULATIONS.get(key) or REGULATIONS[(FIDE, STANDARD)]
    return regulation.with_overrides(overrides) if overrides else regulation


def editable_fields() -> list[str]:
    """Parâmetros do regulamento que o árbitro pode editar."""
    reference = REGULATIONS[(FIDE, STANDARD)]
    return [
        name
        for name in vars(reference)
        if name not in ("code", "label", "source", "confirmed")
    ]


def parse_regulation_overrides(raw: object) -> dict[str, dict[str, int]]:
    """Lê a coluna `rating_regulation` (JSON por base). Lixo vira vazio.

    Vazio é a resposta segura: sem ajuste, vale o perfil publicado, e o árbitro
    vê no relatório de onde vieram os números.
    """
    if isinstance(raw, Mapping):
        data: Any = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return {}
    if not isinstance(data, Mapping):
        return {}

    allowed = set(editable_fields())
    parsed: dict[str, dict[str, int]] = {}
    for base, values in data.items():
        if not isinstance(values, Mapping):
            continue
        campos: dict[str, int] = {}
        for name, value in values.items():
            if name not in allowed or str(value).strip() == "":
                continue
            try:
                campos[str(name)] = int(str(value).strip())
            except (TypeError, ValueError):
                continue
        if campos:
            parsed[str(base).strip().lower()] = campos
    return parsed


def serialize_regulation_overrides(raw: object) -> str:
    """Forma canônica da coluna: `""` quando não há ajuste nenhum."""
    parsed = parse_regulation_overrides(raw)
    if not parsed:
        return ""
    return json.dumps(parsed, sort_keys=True, ensure_ascii=False)


def regulation_from_settings(
    settings: Mapping[str, Any] | None, base: str, speed: str
) -> RatingRegulation:
    """Regulamento do torneio: perfil da base/ritmo + ajustes salvos."""
    overrides = parse_regulation_overrides((settings or {}).get("rating_regulation"))
    return regulation_for(base, speed, overrides.get(str(base or FIDE).strip().lower()))
