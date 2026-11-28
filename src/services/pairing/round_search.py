"""Motor único de busca do suíço do Albericus — jogador ou equipe (RG2-07b).

Havia duas cópias do pareamento holandês: a de jogadores (``fide_dutch``) e a
de equipes (``team_swiss``), 0,96 iguais segundo o dryer. A de equipes divergiu
e passou a tratar o critério absoluto C.04.1 "não repetir confronto" como
CUSTO no resto do grupo: o interclubes repetia confronto quando havia
alternativa (RG2-07). Aqui fica a busca, uma vez só, parametrizada pelo que
muda entre os dois competidores — pontuação, ordem, cor e custo do par.

A busca exata, com o bye como nó, entra no commit seguinte.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

Competitor = dict[str, Any]
Pair = tuple[Competitor, Competitor]
PairCost = Callable[[Competitor, Competitor], float]


def _ident(competitor: Competitor) -> int:
    return int(competitor["id"])


def pair_key(first: Competitor, second: Competitor) -> frozenset[int]:
    return frozenset((_ident(first), _ident(second)))


def greedy_pairs(items: Sequence[Competitor], cost: PairCost) -> list[Pair]:
    """Cada um, na ordem, com o adversário de menor custo que sobrou."""
    pending = list(items)
    pairs: list[Pair] = []
    while pending:
        first = pending.pop(0)
        second = min(pending, key=lambda candidate: cost(first, candidate))
        pending.remove(second)
        pairs.append((first, second))
    return pairs


def optimal_pairs(items: Sequence[Competitor], cost: PairCost) -> list[Pair]:
    """Pareamento perfeito de menor custo total, por busca exaustiva com poda.

    Serve aos grupos pequenos; acima do limite de cada motor, quem chama usa a
    busca gulosa (equipes) ou em feixe (jogadores).
    """
    by_id = {_ident(item): item for item in items}
    cache: dict[tuple[int, int], float] = {}

    def penalty(first_id: int, second_id: int) -> float:
        key = (first_id, second_id)
        if key not in cache:
            cache[key] = cost(by_id[first_id], by_id[second_id])
        return cache[key]

    best_cost = float("inf")
    best: list[tuple[int, int]] = []
    seen: dict[tuple[int, ...], float] = {}

    def search(remaining: tuple[int, ...], selected: list[tuple[int, int]], current: float) -> None:
        nonlocal best_cost, best
        if current >= best_cost or current >= seen.get(remaining, float("inf")):
            return
        seen[remaining] = current
        if not remaining:
            best_cost = current
            best = selected[:]
            return
        first_id = remaining[0]
        for second_id in sorted(remaining[1:], key=lambda other: penalty(first_id, other)):
            search(
                tuple(item for item in remaining[1:] if item != second_id),
                selected + [(first_id, second_id)],
                current + penalty(first_id, second_id),
            )

    search(tuple(by_id), [], 0.0)
    if not best:
        return greedy_pairs(items, cost)
    return [(by_id[first], by_id[second]) for first, second in best]


def search_bracket(
    pairable: Sequence[Competitor],
    played_pairs: set[frozenset[int]],
    admissible: Callable[[Competitor, Competitor], bool] | None = None,
) -> list[Pair] | None:
    """S1 contra S2 do grupo, sem repetir confronto; ``admissible`` recusa o par.

    É a busca holandesa estrita: ``admissible`` é a cor absoluta (C.3) quando o
    chamador quer exigi-la; ``None`` aceita qualquer par não jogado.
    """
    if not pairable:
        return []
    half = len(pairable) // 2
    s1 = list(pairable[:half])
    s2 = list(pairable[half:])

    def solve(index: int, available: list[Competitor], current: list[Pair]) -> list[Pair] | None:
        if index == len(s1):
            return current
        first = s1[index]
        for position, second in enumerate(available):
            if pair_key(first, second) in played_pairs:
                continue
            if admissible is not None and not admissible(first, second):
                continue
            found = solve(index + 1, available[:position] + available[position + 1:], current + [(first, second)])
            if found is not None:
                return found
        return None

    return solve(0, s2, [])


def bracket_pairing(
    group: Sequence[Competitor],
    played_pairs: set[frozenset[int]],
    *,
    admissible: Callable[[Competitor, Competitor], bool],
    solve: Callable[[list[Competitor]], list[Pair]],
) -> tuple[list[Pair], list[Competitor]]:
    """Pares do grupo de pontuação e quem flutua para o grupo seguinte.

    Três passes, cada um tentando com cada vez mais flutuantes (sempre os do
    fim do grupo): a busca estrita com ``admissible``; a busca sem a cor; e o
    ótimo de custo (``solve``), aceito só se não repete confronto. Nada serve:
    o grupo inteiro desce.
    """
    members = list(group)
    size = len(members)

    def splits() -> Iterable[tuple[list[Competitor], list[Competitor]]]:
        for floaters_count in range(size % 2, size + 1, 2):
            if floaters_count == size:
                break
            if floaters_count:
                yield members[:-floaters_count], members[-floaters_count:]
            else:
                yield members, []

    for rule in (admissible, None):
        for pairable, floaters in splits():
            found = search_bracket(pairable, played_pairs, rule)
            if found is not None:
                return found, floaters
    for pairable, floaters in splits():
        found = solve(pairable)
        if all(pair_key(first, second) not in played_pairs for first, second in found):
            return found, floaters
    return [], members


def score_group_pairs(
    pending: Sequence[Competitor],
    *,
    score_of: Callable[[Competitor], float],
    order_key: Callable[[Competitor], Any],
    bracket: Callable[[list[Competitor]], tuple[list[Pair], list[Competitor]]],
    leftover: Callable[[list[Competitor]], list[Pair]],
) -> list[Pair]:
    """Grupos de pontuação de cima para baixo; o que flutua desce para o seguinte.

    Os flutuantes que descem têm pontuação maior que os nativos do grupo e
    entram pelo topo (reordena-se o grupo), senão voltariam a flutuar a cada
    grupo. O que sobra no fim é pareado por ``leftover``.
    """
    groups: dict[float, list[Competitor]] = {}
    for competitor in pending:
        groups.setdefault(float(score_of(competitor)), []).append(competitor)
    pairs: list[Pair] = []
    floaters: list[Competitor] = []
    for score in sorted(groups, reverse=True):
        group = sorted(groups[score] + floaters, key=order_key)
        group_pairs, floaters = bracket(group)
        pairs.extend(group_pairs)
    if floaters:
        pairs.extend(leftover(floaters))
    return pairs
