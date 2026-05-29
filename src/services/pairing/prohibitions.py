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
    key_a: str = "player_a_id",
    key_b: str = "player_b_id",
) -> set[frozenset[int]]:
    """Conjunto de pares `{a, b}` proibidos nesta rodada.

    `key_a`/`key_b` selecionam as colunas de entidade — `player_a_id`/`player_b_id`
    para indivíduos, `team_a_id`/`team_b_id` para equipes. Pares com IDs ausentes
    ou idênticos são ignorados (uma proibição precisa de duas entidades distintas
    para significar algo). O motor une o resultado a `played_pairs`, tanto no
    Suíço individual quanto no por equipes — mesmo mecanismo de bloqueio absoluto."""
    pairs: set[frozenset[int]] = set()
    for prohibition in prohibitions:
        if not prohibition_applies(prohibition, round_number):
            continue
        a = int(prohibition.get(key_a) or 0)
        b = int(prohibition.get(key_b) or 0)
        if a and b and a != b:
            pairs.add(frozenset((a, b)))
    return pairs
