"""Fator K conforme o regulamento escolhido (puro).

Devolve K **e de onde ele veio**. O árbitro que vê "K = 40" numa planilha não
tem como saber se foi por o jogador ser novo, por ser sub-18 ou por alguém ter
digitado 40 no cadastro — e as três coisas se conferem de maneiras diferentes.
"""

from __future__ import annotations

from src.services.rating.regulation import RatingRegulation

OVERRIDE = "cadastro do jogador"
NEW_PLAYER = "jogador novo"
YOUTH = "sub-18"
TOP = "rating alto"
DEFAULT = "padrão"
CAPPED = "teto de K x n"


def k_factor(
    regulation: RatingRegulation,
    rating: int,
    *,
    games_played: int | None = None,
    birth_year: int | None = None,
    tournament_year: int | None = None,
    k_override: int | None = None,
    games: int = 0,
) -> tuple[int, str]:
    """`(K, origem)` para o jogador, no regulamento dado.

    `games_played` é o total de partidas já ratadas do jogador; `None` significa
    desconhecido, e aí a regra do jogador novo simplesmente não se aplica — era
    exatamente esse o defeito do FED-07: o relatório nunca passava esse número,
    então K = 40 de novato nunca disparava.
    """
    value = int(rating or 0)

    if k_override:
        try:
            return _capped(regulation, int(k_override), games, OVERRIDE)
        except (TypeError, ValueError):
            pass

    if games_played is not None and int(games_played) < regulation.k_new_games:
        return _capped(regulation, regulation.k_new, games, NEW_PLAYER)

    if _is_youth(birth_year, tournament_year) and value < regulation.k_youth_max_rating:
        return _capped(regulation, regulation.k_youth, games, YOUTH)

    if value >= regulation.k_top_rating:
        return _capped(regulation, regulation.k_top, games, TOP)

    return _capped(regulation, regulation.k_default, games, DEFAULT)


def _is_youth(birth_year: int | None, tournament_year: int | None) -> bool:
    """Sub-18 até o FIM DO ANO do aniversário de 18 (B.02), não até o dia.

    O código antigo usava `< 18`, que tira o K de desenvolvimento do jogador no
    ano em que ele completa 18 — um ano antes da hora.
    """
    if not birth_year or not tournament_year:
        return False
    return (int(tournament_year) - int(birth_year)) <= 18


def _capped(regulation: RatingRegulation, k: int, games: int, reason: str) -> tuple[int, str]:
    """Teto de K x n no período (B.02).

    O regulamento fala do período de rating inteiro; aqui só se conhece o
    torneio, então o teto praticamente nunca morde — mas quando morder, morde
    para menos, que é o lado seguro.
    """
    cap = int(regulation.k_games_cap or 0)
    count = int(games or 0)
    if cap <= 0 or count <= 0 or k * count <= cap:
        return int(k), reason
    return max(1, cap // count), CAPPED
