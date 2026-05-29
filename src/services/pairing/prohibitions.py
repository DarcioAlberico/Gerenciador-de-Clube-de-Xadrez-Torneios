"""Proibições de pareamento (arbitrais) — funções puras.

Uma proibição impede que dois jogadores sejam emparelhados num intervalo de
rodadas. O motor Suíço já trata `played_pairs` como bloqueio absoluto (ver
`fide_dutch.search_dutch_pairing`/`dutch_bracket_pairing`): basta unir os pares
proibidos da rodada a esse conjunto para que jamais sejam pareados — o mesmo
mecanismo que impede revanches.

Corresponde ao registro 260 do TRF25 (ESPEC §5.2).
"""

from __future__ import annotations

from typing import Any


def prohibition_applies(prohibition: dict[str, Any], round_number: int) -> bool:
    """Verdadeiro se a proibição vale para `round_number`.

    `first_round` é 1-based; `last_round=0` significa "sem fim" (até a última
    rodada do torneio)."""
    first = int(prohibition.get("first_round") or 1)
    last = int(prohibition.get("last_round") or 0)
    if round_number < first:
        return False
    if last and round_number > last:
        return False
    return True


def prohibited_pairs_for_round(
    prohibitions: list[dict[str, Any]],
    round_number: int,
) -> set[frozenset[int]]:
    """Conjunto de pares `{player_a, player_b}` proibidos nesta rodada.

    Pares com IDs ausentes ou idênticos são ignorados (uma proibição precisa de
    dois jogadores distintos para significar algo)."""
    pairs: set[frozenset[int]] = set()
    for prohibition in prohibitions:
        if not prohibition_applies(prohibition, round_number):
            continue
        a = int(prohibition.get("player_a_id") or 0)
        b = int(prohibition.get("player_b_id") or 0)
        if a and b and a != b:
            pairs.add(frozenset((a, b)))
    return pairs
