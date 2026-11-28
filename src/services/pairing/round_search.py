"""Motor único de busca do suíço do Albericus — jogador ou equipe (RG2-07b).

Havia duas cópias do pareamento holandês: a de jogadores (``fide_dutch``) e a
de equipes (``team_swiss``), 0,96 iguais segundo o dryer. A de equipes divergiu
e passou a tratar o critério absoluto C.04.1 "não repetir confronto" como
CUSTO no resto do grupo: o interclubes repetia confronto quando havia
alternativa (RG2-07). Aqui fica a busca, uma vez só, parametrizada pelo que
muda entre os dois competidores — pontuação, ordem, cor e custo do par.

Duas camadas:

- a **busca por grupo** (``score_group_pairs`` → ``bracket_pairing`` →
  ``search_bracket``/``optimal_pairs``) é a heurística holandesa de sempre;
- a **busca exata** (``legal_round``) é o pareamento perfeito de custo mínimo
  sobre o grafo dos pares PERMITIDOS, com o bye como mais um nó. Confronto já
  jogado (ou proibido) e PAB para quem já teve um não são arestas: não há como
  escolhê-los. Se não existe pareamento perfeito, não existe pareamento legal —
  e o árbitro recebe ``NoLegalPairingError`` com a regra, em vez de uma rodada
  ilegal gravada em silêncio.

A busca exata só entra quando a heurística devolve uma rodada que fere um
critério absoluto: o que era legal continua saindo igual (fixado em
``tests/test_rg2_07b_caracterizacao.py``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

import networkx as nx

from src.services.constants import AppError

Competitor = dict[str, Any]
Pair = tuple[Competitor, Competitor]
PairCost = Callable[[Competitor, Competitor], float]


class NoLegalPairingError(AppError):
    """Não existe pareamento que respeite os critérios absolutos (C.04.1)."""

    def __init__(self, round_number: int | None, competitor_label: str = "os jogadores") -> None:
        rodada = f"Rodada {round_number}: n" if round_number is not None else "N"
        self.round_number = round_number
        super().__init__(
            f"{rodada}ão existe pareamento que respeite os critérios absolutos da FIDE "
            f"(C.04.1): {competitor_label} que restam já se enfrentaram, ou o bye cairia "
            "em quem já recebeu um.\n\nA rodada não foi gerada. Você pode encerrar o torneio "
            "aqui ou rever as ausências (quem está ausente ou retirado) e gerar de novo."
        )


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


def round_violations(
    pairs: Iterable[Pair],
    bye: Competitor | None,
    played_pairs: set[frozenset[int]],
    bye_ids: set[int],
) -> int:
    """Quantos critérios absolutos a rodada fere: confronto repetido e 2º PAB."""
    total = sum(1 for first, second in pairs if pair_key(first, second) in played_pairs)
    if bye is not None and _ident(bye) in bye_ids:
        total += 1
    return total


_BYE_NODE = "bye"
# Pesos inteiros: o custo vira inteiro com esta escala antes da inversão.
_COST_SCALE = 100


def legal_round(
    competitors: Sequence[Competitor],
    played_pairs: set[frozenset[int]],
    bye_ids: set[int],
    *,
    pair_cost: PairCost,
    bye_cost: Callable[[Competitor], float],
) -> tuple[list[Pair], Competitor | None] | None:
    """Pareamento legal de menor custo, com o bye como nó (``None``: não há).

    Arestas só entre quem ainda não se enfrentou (``played_pairs`` traz também
    as proibições); com número ímpar, o nó "bye" liga só quem não recebeu PAB
    (``bye_ids``). O pareamento de cardinalidade máxima e menor custo
    (blossom de Edmonds, ``networkx.max_weight_matching``) é perfeito se e só
    se existe pareamento legal.
    """
    items = list(competitors)
    by_id = {_ident(item): item for item in items}
    need_bye = len(items) % 2 == 1
    edges: list[tuple[Any, Any, float]] = []
    for index, first in enumerate(items):
        for second in items[index + 1:]:
            if pair_key(first, second) not in played_pairs:
                edges.append((_ident(first), _ident(second), float(pair_cost(first, second))))
        if need_bye and _ident(first) not in bye_ids:
            edges.append((_ident(first), _BYE_NODE, float(bye_cost(first))))
    if not edges:
        return None if items else ([], None)
    ceiling = max(cost for _a, _b, cost in edges) + 1.0
    graph = nx.Graph()
    graph.add_nodes_from(by_id)
    if need_bye:
        graph.add_node(_BYE_NODE)
    for first_id, second_id, cost in edges:
        graph.add_edge(first_id, second_id, weight=int(round((ceiling - cost) * _COST_SCALE)))
    matching = nx.max_weight_matching(graph, maxcardinality=True)
    expected = (len(items) + (1 if need_bye else 0)) // 2
    if len(matching) != expected:
        return None
    pairs: list[Pair] = []
    bye: Competitor | None = None
    for first_id, second_id in matching:
        if _BYE_NODE in (first_id, second_id):
            bye = by_id[second_id if first_id == _BYE_NODE else first_id]
            continue
        first, second = by_id[first_id], by_id[second_id]
        # A ordem de cada par segue a lista de entrada (a de pareamento).
        if items.index(first) > items.index(second):
            first, second = second, first
        pairs.append((first, second))
    pairs.sort(key=lambda pair: items.index(pair[0]))
    return pairs, bye


def enforce_absolute(
    pairs: list[Pair],
    bye: Competitor | None,
    competitors: Sequence[Competitor],
    played_pairs: set[frozenset[int]],
    bye_ids: set[int],
    *,
    pair_cost: PairCost,
    bye_cost: Callable[[Competitor], float],
    competitor_label: str,
    hard_count: Callable[[Competitor, Competitor], int] | None = None,
) -> tuple[list[Pair], Competitor | None]:
    """A rodada da heurística, ou a da busca exata quando aquela fere C.04.1.

    Confronto repetido ou 2º PAB: vale a busca exata, e sem pareamento legal
    levanta ``NoLegalPairingError``. ``hard_count`` (cor absoluta, quando o
    competidor a trata como critério da rodada) só troca a rodada se a busca
    exata violar MENOS — a heurística legal fica como estava.
    """
    broken = round_violations(pairs, bye, played_pairs, bye_ids)
    soft = sum(hard_count(first, second) for first, second in pairs) if hard_count else 0
    if not broken and not soft:
        return pairs, bye
    exact = legal_round(competitors, played_pairs, bye_ids, pair_cost=pair_cost, bye_cost=bye_cost)
    if exact is None:
        if broken:
            raise NoLegalPairingError(None, competitor_label)
        return pairs, bye
    if broken or hard_count is None:
        return exact
    exact_soft = sum(hard_count(first, second) for first, second in exact[0])
    return exact if exact_soft < soft else (pairs, bye)
