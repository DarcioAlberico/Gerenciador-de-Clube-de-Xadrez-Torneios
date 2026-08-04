"""Constantes do Handbook B.01 da FIDE — só regulamento, nada de torneio.

Fonte: *FIDE Title Regulations* em vigor desde 1 de janeiro de 2024, seção 1.4
(https://handbook.fide.com/chapter/B012024). Este módulo guarda os números e as
frações do regulamento e os converte em limites inteiros para um número de
partidas. Quem monta a lista de adversários mora em ``opponents``; quem julga,
em ``evaluation``.

A escolha de deixar o regulamento isolado num módulo é deliberada: quando a
FIDE mudar um limiar (e ela muda — o não ratado valia 1000 antes de 2024), o
conserto é aqui, num arquivo que não sabe o que é torneio.
"""

from __future__ import annotations

from dataclasses import dataclass

# 1.4.6.4 — adversário sem rating conta como 1400 (era 1000 até 2023).
UNRATED_RATING = 1400

# 1.4.1 — mínimo de partidas para uma norma. O piso de 7 vale só para
# campeonatos por equipes (Olimpíada e mundiais/continentais de equipes), que o
# Albericus não exporta como norma individual — fica documentado, não aplicado.
MIN_GAMES = 9
TEAM_EVENT_MIN_GAMES = 7

# 1.4.8.2 — pontuação mínima de 35% em qualquer norma.
MIN_SCORE_RATIO = 0.35

# 1.4.3 — os adversários devem vir de pelo menos duas federações além da do
# candidato.
MIN_OTHER_FEDERATIONS = 2

# 1.4.5 — títulos que contam como "title holder" (TH) para o piso de 50%.
# CM e WCM ficam de fora POR REGULAMENTO; NM e WNM são títulos nacionais e
# nunca foram título FIDE. Era exatamente essa a falha do motor antigo: com
# CM/WCM/NM/WNM valendo como titulado, um open cheio de CMs indicava norma.
TITLE_HOLDER_TITLES = frozenset({"GM", "IM", "FM", "WGM", "WIM", "WFM"})

# Títulos reconhecidos que NÃO contam como TH — listados para o relatório poder
# dizer ao árbitro por que aquele adversário não entrou na conta.
NON_COUNTING_TITLES = frozenset({"CM", "WCM", "NM", "WNM"})

FIDE_TITLES = TITLE_HOLDER_TITLES | NON_COUNTING_TITLES


@dataclass(frozen=True)
class NormRequirement:
    """Limiares de uma norma (1.4.5, 1.4.6.2 e 1.4.8.1)."""

    code: str
    label: str
    performance: int
    min_average_opponent: int
    rating_floor: int
    level_titles: frozenset[str]
    level_label: str


NORM_REQUIREMENTS: dict[str, NormRequirement] = {
    "GM": NormRequirement(
        code="GM",
        label="Grande Mestre (GM)",
        performance=2600,
        min_average_opponent=2380,
        rating_floor=2200,
        level_titles=frozenset({"GM"}),
        level_label="GM",
    ),
    "IM": NormRequirement(
        code="IM",
        label="Mestre Internacional (IM)",
        performance=2450,
        min_average_opponent=2230,
        rating_floor=2050,
        level_titles=frozenset({"GM", "IM"}),
        level_label="GM ou IM",
    ),
    "WGM": NormRequirement(
        code="WGM",
        label="Grande Mestra (WGM)",
        performance=2400,
        min_average_opponent=2180,
        rating_floor=2000,
        level_titles=frozenset({"GM", "IM", "WGM"}),
        level_label="GM, IM ou WGM",
    ),
    "WIM": NormRequirement(
        code="WIM",
        label="Mestra Internacional (WIM)",
        performance=2250,
        min_average_opponent=2030,
        rating_floor=1850,
        level_titles=frozenset({"GM", "IM", "WGM", "WIM"}),
        level_label="GM, IM, WGM ou WIM",
    ),
}

WOMEN_ONLY_NORMS = ("WGM", "WIM")
OPEN_NORMS = ("GM", "IM")


def normalized_title(title: object) -> str:
    return str(title or "").strip().upper()


def is_title_holder(title: object) -> bool:
    """1.4.5 — o adversário conta para o piso de 50% de titulados?"""
    return normalized_title(title) in TITLE_HOLDER_TITLES


def holds_level_title(title: object, requirement: NormRequirement) -> bool:
    """1.4.5 — o adversário conta para o mínimo de titulados DO NÍVEL da norma."""
    return normalized_title(title) in requirement.level_titles


def applicable_norms(sex: object) -> tuple[str, ...]:
    """Normas avaliáveis para o candidato: WGM/WIM só para jogadoras."""
    if str(sex or "").strip().upper() == "F":
        return OPEN_NORMS + WOMEN_ONLY_NORMS
    return OPEN_NORMS


# --- Limites proporcionais ao número de partidas (Anexo do B.01) -------------
#
# O Anexo publica uma tabela por número de rodadas; ela é a aplicação das
# frações do texto, com o arredondamento que cada uma pede. Guardamos a
# derivação, não a tabela copiada — assim 9, 11 e 13 rodadas saem certas e 15,
# 17 e 19 também.


def min_title_holders(games: int) -> int:
    """1.4.5 — pelo menos 50% dos adversários titulados (arredonda para cima)."""
    return (max(int(games), 0) + 1) // 2


def min_level_title_holders(games: int) -> int:
    """1.4.5 — pelo menos 1/3, com mínimo de 3, titulados do nível da norma."""
    return max(3, (max(int(games), 0) + 2) // 3)


def max_own_federation(games: int) -> int:
    """1.4.4 — no máximo 3/5 dos adversários da federação do candidato."""
    return 3 * max(int(games), 0) // 5


def max_single_federation(games: int) -> int:
    """1.4.4 — no máximo 2/3 dos adversários de uma mesma federação."""
    return 2 * max(int(games), 0) // 3


def max_unrated(games: int) -> int:
    """1.4.6 — no máximo 20% de (adversários + 1) sem rating."""
    return (max(int(games), 0) + 1) // 5


def limits_for(games: int) -> dict[str, int]:
    """Todos os limites de uma vez, para relatório e conferência."""
    return {
        "games": max(int(games), 0),
        "min_title_holders": min_title_holders(games),
        "min_level_title_holders": min_level_title_holders(games),
        "max_own_federation": max_own_federation(games),
        "max_single_federation": max_single_federation(games),
        "max_unrated": max_unrated(games),
        "min_other_federations": MIN_OTHER_FEDERATIONS,
    }


def limits_table(first: int = MIN_GAMES, last: int = 13) -> list[dict[str, int]]:
    """Tabela do Anexo para o intervalo de partidas pedido."""
    return [limits_for(games) for games in range(int(first), int(last) + 1)]
