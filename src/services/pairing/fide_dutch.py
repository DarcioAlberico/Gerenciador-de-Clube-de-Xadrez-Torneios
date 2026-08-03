"""Helpers puros do emparceiramento suíço individual."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from src.services.constants import AppError
from src.services.pairing.constraints import (
    choose_bye_player,
    choose_colors,
    color_hard_violation,
    greedy_player_pairs,
    is_color_valid_fide,
    optimal_player_pairs,
    pairing_order_key,
    pair_penalty,
    rank_by_player_id,
    rating_for_initial_order,
)


def _initial_order_key(player: dict[str, Any], settings: dict[str, Any] | None) -> tuple[int, str]:
    initial_order = str((settings or {}).get("initial_order") or "rating")
    return (
        -rating_for_initial_order(player, initial_order),
        str(player.get("name") or "").casefold(),
    )


def first_round_pairings(
    players: list[dict[str, Any]],
    settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ordered = sorted(
        players,
        key=lambda player: _initial_order_key(player, settings),
    )
    pairable = ordered[:]
    bye_player = None
    if len(pairable) % 2 == 1:
        bye_player = min(
            pairable,
            key=lambda player: (
                -_initial_order_key(player, settings)[0],
                str(player.get("name") or "").casefold(),
            ),
        )
        pairable.remove(bye_player)

    half = len(pairable) // 2
    upper = pairable[:half]
    lower = pairable[half:]
    pairings: list[dict[str, Any]] = []

    board = 1
    for index, player in enumerate(upper):
        opponent = lower[index]
        if index % 2 == 0:
            white_id = player["id"]
            black_id = opponent["id"]
        else:
            white_id = opponent["id"]
            black_id = player["id"]
        pairings.append(
            {
                "board_number": board,
                "white_player_id": white_id,
                "black_player_id": black_id,
                "result": "",
                "is_bye": 0,
            }
        )
        board += 1

    if bye_player:
        pairings.append(
            {
                "board_number": board,
                "white_player_id": bye_player["id"],
                "black_player_id": None,
                "result": "BYE",
                "is_bye": 1,
            }
        )
    return pairings


# O round-robin individual morava aqui e recalculava o circulo a cada rodada a
# partir da lista de ATIVOS ordenada por rating — o defeito que a PAR-01
# consertou. O calendario agora sai da tabela de Berger (FIDE C.05, Anexo 1) em
# `pairing/round_robin.py`, a partir de numeros sorteados UMA vez e guardados.
# Nao ha versao "simples" aqui de proposito: duas implementacoes do mesmo
# calendario divergiriam, e a que ficasse esquecida seria a que alguem usaria.


# O Scheveningen tambem morava aqui e recalculava a escala a cada rodada a
# partir da lista de ATIVOS: uma desistencia deslocava todos os indices
# seguintes (os confrontos que faltavam viravam outros) e desigualava os
# grupos, o que passava a RECUSAR a geracao. A escala agora e guardada no
# jogador (grupo + numero) e o calendario sai dela, em `pairing/scheveningen.py`.


def knockout_pairings(
    players: list[dict[str, Any]],
    next_number: int,
    settings: dict[str, Any],
    advancing_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Chave da fase, a partir de QUEM avancou (PAR-03).

    Quem avancou nao se decide mais aqui: vinha de dois `if` que promoviam o
    melhor numero inicial em qualquer resultado que nao fosse `1-0`/`0-1` — o
    empate, a dupla ausencia, a mesa em branco e ate o W.O. e a decisao do
    arbitro. Agora e o servico quem responde, lendo o placar e as decisoes
    registradas (`pairing/knockout.py`), e esta funcao so monta a chave.
    """
    ordered = sorted(
        players,
        key=lambda player: _initial_order_key(player, settings),
    )

    if next_number == 1:
        active_players = ordered[:]
    else:
        if advancing_ids is None:
            raise AppError("Rodada anterior não encontrada.")
        avancaram = {int(player_id) for player_id in advancing_ids}
        active_players = [player for player in ordered if int(player["id"]) in avancaram]

    if len(active_players) == 1:
        raise AppError("O torneio já tem um vencedor. Não é possível gerar mais rodadas.")

    players_count = len(active_players)
    bracket_size = 1
    while bracket_size < players_count:
        bracket_size *= 2

    if bracket_size != players_count:
        byes_count = bracket_size - players_count
        bye_players = active_players[:byes_count]
        playing_players = active_players[byes_count:]
    else:
        bye_players = []
        playing_players = active_players[:]

    pairings: list[dict[str, Any]] = []
    board = 1

    half = len(playing_players) // 2
    for index in range(half):
        p1 = playing_players[index]
        p2 = playing_players[len(playing_players) - 1 - index]
        if index % 2 == 0:
            white, black = p1, p2
        else:
            white, black = p2, p1

        pairings.append(
            {
                "board_number": board,
                "white_player_id": white["id"],
                "black_player_id": black["id"],
                "result": "",
                "is_bye": 0,
            }
        )
        board += 1

    for player in bye_players:
        # Bye de verdade, como no Suico e no rodizio (PAR-01/03): gravado como
        # `1-0` ele pontuava certo por acaso (o padrao de `bye_points` e 1,0) e
        # aparecia como VITORIA em tudo que le o resultado.
        pairings.append(
            {
                "board_number": board,
                "white_player_id": player["id"],
                "black_player_id": None,
                "result": "BYE",
                "is_bye": 1,
            }
        )
        board += 1

    return pairings


def search_dutch_pairing(
    pairable: list[dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    strict_colors: bool,
) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
    if not pairable:
        return []

    half = len(pairable) // 2
    s1 = pairable[:half]
    s2 = pairable[half:]

    def solve(
        s1_idx: int,
        available_s2: list[dict[str, Any]],
        current_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
        if s1_idx == len(s1):
            return current_pairs

        p1 = s1[s1_idx]
        for index, p2 in enumerate(available_s2):
            if frozenset((p1["id"], p2["id"])) in played_pairs:
                continue

            if strict_colors:
                white_id, _black_id = choose_colors(p1, p2, histories)
                p1_color = "W" if white_id == p1["id"] else "B"
                p2_color = "W" if white_id == p2["id"] else "B"

                if not is_color_valid_fide(p1["id"], p1_color, histories) or not is_color_valid_fide(
                    p2["id"], p2_color, histories
                ):
                    p1_color_rev = "B" if p1_color == "W" else "W"
                    p2_color_rev = "B" if p2_color == "W" else "W"
                    if not is_color_valid_fide(p1["id"], p1_color_rev, histories) or not is_color_valid_fide(
                        p2["id"], p2_color_rev, histories
                    ):
                        continue

            next_pairs = solve(
                s1_idx + 1,
                available_s2[:index] + available_s2[index + 1:],
                current_pairs + [(p1, p2)],
            )
            if next_pairs is not None:
                return next_pairs
        return None

    return solve(0, s2, [])


def dutch_bracket_pairing(
    group: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    max_exhaustive_pairing_players: int,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    n = len(group)

    for num_floaters in range(n % 2, n + 1, 2):
        if num_floaters == n:
            break
        pairable = group[:-num_floaters] if num_floaters else group
        floaters = group[-num_floaters:] if num_floaters else []
        best_pairs = search_dutch_pairing(pairable, histories, played_pairs, strict_colors=True)
        if best_pairs is not None:
            return best_pairs, floaters

    for num_floaters in range(n % 2, n + 1, 2):
        if num_floaters == n:
            break
        pairable = group[:-num_floaters] if num_floaters else group
        floaters = group[-num_floaters:] if num_floaters else []
        best_pairs = search_dutch_pairing(pairable, histories, played_pairs, strict_colors=False)
        if best_pairs is not None:
            return best_pairs, floaters

    for num_floaters in range(n % 2, n + 1, 2):
        if num_floaters == n:
            break
        pairable = group[:-num_floaters] if num_floaters else group
        floaters = group[-num_floaters:] if num_floaters else []
        if len(pairable) <= max_exhaustive_pairing_players:
            best_pairs = optimal_player_pairs(
                pairable,
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            )
        else:
            best_pairs = beam_player_pairs(
                pairable,
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            )

        if all(frozenset((p1["id"], p2["id"])) not in played_pairs for p1, p2 in best_pairs):
            return best_pairs, floaters

    return [], group


def score_groups(players: list[dict[str, Any]], standings: dict[int, dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[float, list[dict[str, Any]]] = {}
    for player in players:
        score = float(standings.get(player["id"], {}).get("points", 0.0) or 0.0)
        groups.setdefault(score, []).append(player)
    return [
        sorted(groups[score], key=lambda player: pairing_order_key(player, standings))
        for score in sorted(groups.keys(), reverse=True)
    ]


def pairing_color_hard_violations(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    histories: dict[int, list[str]],
) -> int:
    violations = 0
    for player, opponent in pairs:
        white_id, _black_id = choose_colors(player, opponent, histories)
        if white_id == player["id"]:
            violations += color_hard_violation(player["id"], "W", histories)
            violations += color_hard_violation(opponent["id"], "B", histories)
        else:
            violations += color_hard_violation(player["id"], "B", histories)
            violations += color_hard_violation(opponent["id"], "W", histories)
    return violations


def _single_pair_quality(
    player: dict[str, Any],
    opponent: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    ranks: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> tuple[int, int, float]:
    repeat = 1 if frozenset((player["id"], opponent["id"])) in played_pairs else 0
    hard_violations = pairing_color_hard_violations([(player, opponent)], histories)
    penalty = pair_penalty(
        player,
        opponent,
        standings,
        histories,
        float_histories,
        played_pairs,
        ranks,
        repeat_pairing_penalty=repeat_pairing_penalty,
        score_group_float_penalty=score_group_float_penalty,
        score_diff_penalty=score_diff_penalty,
    )
    return repeat, hard_violations, penalty


def pairing_quality(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    ranks: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> tuple[int, int, float]:
    quality = (0, 0, 0.0)
    for player, opponent in pairs:
        pair_quality = _single_pair_quality(
            player,
            opponent,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
        quality = (
            quality[0] + pair_quality[0],
            quality[1] + pair_quality[1],
            quality[2] + pair_quality[2],
        )
    return quality


def beam_player_pairs(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    ranks: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    beam_width: int = 64,
    branch_width: int = 14,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if len(players) < 2:
        return []

    player_by_id = {int(player["id"]): player for player in players}
    quality_kwargs = {
        "repeat_pairing_penalty": repeat_pairing_penalty,
        "score_group_float_penalty": score_group_float_penalty,
        "score_diff_penalty": score_diff_penalty,
    }
    initial_remaining = tuple(int(player["id"]) for player in players)
    states: list[tuple[tuple[tuple[int, int], ...], tuple[int, ...], tuple[int, int, float]]] = [
        ((), initial_remaining, (0, 0, 0.0))
    ]

    for _ in range(len(players) // 2):
        expanded: dict[tuple[int, ...], tuple[tuple[tuple[int, int], ...], tuple[int, ...], tuple[int, int, float]]] = {}
        for selected_pairs, remaining, quality in states:
            if not remaining:
                expanded[remaining] = (selected_pairs, remaining, quality)
                continue
            player_id = remaining[0]
            player = player_by_id[player_id]
            ordered_candidates = sorted(
                remaining[1:],
                key=lambda candidate_id: _single_pair_quality(
                    player,
                    player_by_id[candidate_id],
                    standings,
                    histories,
                    float_histories,
                    played_pairs,
                    ranks,
                    **quality_kwargs,
                ),
            )
            for opponent_id in ordered_candidates[:branch_width]:
                opponent = player_by_id[opponent_id]
                pair_quality = _single_pair_quality(
                    player,
                    opponent,
                    standings,
                    histories,
                    float_histories,
                    played_pairs,
                    ranks,
                    **quality_kwargs,
                )
                next_remaining = tuple(item for item in remaining[1:] if item != opponent_id)
                next_quality = (
                    quality[0] + pair_quality[0],
                    quality[1] + pair_quality[1],
                    quality[2] + pair_quality[2],
                )
                next_state = (
                    selected_pairs + ((player_id, opponent_id),),
                    next_remaining,
                    next_quality,
                )
                previous = expanded.get(next_remaining)
                if previous is None or next_quality < previous[2]:
                    expanded[next_remaining] = next_state

        if not expanded:
            break
        states = sorted(expanded.values(), key=lambda state: state[2])[:beam_width]

    complete_states = [state for state in states if not state[1]]
    if not complete_states:
        return greedy_player_pairs(
            players,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
    best_pairs = min(complete_states, key=lambda state: state[2])[0]
    return [(player_by_id[player_id], player_by_id[opponent_id]) for player_id, opponent_id in best_pairs]


def improve_pairing_by_swaps(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    ranks: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Reduz repeticoes/cores por trocas locais sem explodir combinatoriamente."""
    current = list(pairs)
    if len(current) < 2:
        return current

    kwargs = {
        "repeat_pairing_penalty": repeat_pairing_penalty,
        "score_group_float_penalty": score_group_float_penalty,
        "score_diff_penalty": score_diff_penalty,
    }

    def pair_quality(pair: tuple[dict[str, Any], dict[str, Any]]) -> tuple[int, int, float]:
        return _single_pair_quality(
            pair[0], pair[1], standings, histories, float_histories, played_pairs, ranks, **kwargs
        )

    total_quality = pairing_quality(
        current,
        standings,
        histories,
        float_histories,
        played_pairs,
        ranks,
        **kwargs,
    )
    passes = 0
    improved = True
    while improved and passes < 6:
        passes += 1
        improved = False
        for first_index in range(len(current)):
            first_pair = current[first_index]
            first_quality = pair_quality(first_pair)
            for second_index in range(first_index + 1, len(current)):
                second_pair = current[second_index]
                second_quality = pair_quality(second_pair)
                old_local = (
                    first_quality[0] + second_quality[0],
                    first_quality[1] + second_quality[1],
                    first_quality[2] + second_quality[2],
                )
                a, b = first_pair
                c, d = second_pair
                for candidate_first, candidate_second in (
                    ((a, c), (b, d)),
                    ((a, d), (b, c)),
                ):
                    if len({
                        int(candidate_first[0]["id"]),
                        int(candidate_first[1]["id"]),
                        int(candidate_second[0]["id"]),
                        int(candidate_second[1]["id"]),
                    }) < 4:
                        continue
                    candidate_first_quality = pair_quality(candidate_first)
                    candidate_second_quality = pair_quality(candidate_second)
                    new_local = (
                        candidate_first_quality[0] + candidate_second_quality[0],
                        candidate_first_quality[1] + candidate_second_quality[1],
                        candidate_first_quality[2] + candidate_second_quality[2],
                    )
                    candidate_total = (
                        total_quality[0] - old_local[0] + new_local[0],
                        total_quality[1] - old_local[1] + new_local[1],
                        total_quality[2] - old_local[2] + new_local[2],
                    )
                    if candidate_total < total_quality:
                        current[first_index] = candidate_first
                        current[second_index] = candidate_second
                        total_quality = candidate_total
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
    return current


def _perfect_pair_rematches(
    players: tuple[dict[str, Any], ...],
) -> list[list[tuple[dict[str, Any], dict[str, Any]]]]:
    if not players:
        return [[]]

    first = players[0]
    rematches: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
    for index in range(1, len(players)):
        second = players[index]
        remaining = players[1:index] + players[index + 1:]
        for tail in _perfect_pair_rematches(remaining):
            rematches.append([(first, second), *tail])
    return rematches


def improve_pairing_by_group_rematches(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    ranks: dict[int, int],
    *,
    group_size: int,
    max_checked_rematches: int,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    current = list(pairs)
    if len(current) < group_size:
        return current

    kwargs = {
        "repeat_pairing_penalty": repeat_pairing_penalty,
        "score_group_float_penalty": score_group_float_penalty,
        "score_diff_penalty": score_diff_penalty,
    }
    total_quality = pairing_quality(
        current,
        standings,
        histories,
        float_histories,
        played_pairs,
        ranks,
        **kwargs,
    )
    checked = 0
    passes = 0
    while total_quality[:2] != (0, 0) and passes < 3:
        passes += 1
        bad_indices = [
            index for index, pair in enumerate(current)
            if _single_pair_quality(
                pair[0],
                pair[1],
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **kwargs,
            )[:2] != (0, 0)
        ]
        if not bad_indices:
            break

        yielded: set[tuple[int, ...]] = set()
        improved = False
        for bad_index in bad_indices:
            candidate_indices = sorted(
                (index for index in range(len(current)) if index != bad_index),
                key=lambda index: (abs(index - bad_index), index),
            )
            for others in combinations(candidate_indices, group_size - 1):
                combo = tuple(sorted((bad_index, *others)))
                if combo in yielded:
                    continue
                yielded.add(combo)
                old_pairs = [current[index] for index in combo]
                old_quality = pairing_quality(
                    old_pairs,
                    standings,
                    histories,
                    float_histories,
                    played_pairs,
                    ranks,
                    **kwargs,
                )
                local_players = tuple(player for pair in old_pairs for player in pair)
                for candidate_pairs in _perfect_pair_rematches(local_players):
                    checked += 1
                    if checked > max_checked_rematches:
                        return current
                    new_quality = pairing_quality(
                        candidate_pairs,
                        standings,
                        histories,
                        float_histories,
                        played_pairs,
                        ranks,
                        **kwargs,
                    )
                    candidate_total = (
                        total_quality[0] - old_quality[0] + new_quality[0],
                        total_quality[1] - old_quality[1] + new_quality[1],
                        total_quality[2] - old_quality[2] + new_quality[2],
                    )
                    if candidate_total < total_quality:
                        for index, pair in zip(combo, candidate_pairs):
                            current[index] = pair
                        total_quality = candidate_total
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            break
    return current


def rematch_search_limits(
    pair_count: int,
    bad_pair_count: int,
) -> tuple[tuple[tuple[int, int], ...], int]:
    if bad_pair_count > 6:
        if pair_count <= 20:
            return ((3, 8_000), (4, 12_000)), 20_000
        return ((3, 2_000), (4, 4_000)), 8_000
    if pair_count <= 12:
        return ((3, 80_000), (4, 120_000)), 500_000
    if pair_count <= 20:
        if bad_pair_count <= 2:
            return ((3, 20_000), (4, 30_000)), 60_000
        return ((3, 8_000), (4, 12_000)), 20_000
    if bad_pair_count <= 2:
        return ((3, 8_000), (4, 12_000)), 20_000
    return ((3, 2_000), (4, 4_000)), 8_000


def choose_bye_player_with_pairing_quality(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_player_ids: set[int],
    ranks: dict[int, int],
    *,
    max_exhaustive_pairing_players: int,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> dict[str, Any]:
    default_bye = choose_bye_player(players, standings, bye_player_ids)
    has_pairing_history = bool(played_pairs or bye_player_ids) or any(
        any(color in {"W", "B"} for color in history)
        for history in histories.values()
    )
    if not has_pairing_history:
        return default_bye

    candidates = [player for player in players if player["id"] not in bye_player_ids]
    if not candidates:
        candidates = players

    min_score = min(
        float(standings.get(player["id"], {}).get("points", 0.0) or 0.0)
        for player in candidates
    )
    tied_lowest = [
        player for player in candidates
        if float(standings.get(player["id"], {}).get("points", 0.0) or 0.0) == min_score
    ]
    if len(tied_lowest) < 2:
        return default_bye
    if len(players) <= 17:
        candidate_limit = len(tied_lowest)
    elif len(players) <= 31:
        candidate_limit = 4
    elif len(players) <= 64:
        candidate_limit = 3
    else:
        candidate_limit = 2
    if len(tied_lowest) > candidate_limit:
        tied_lowest = sorted(
            tied_lowest,
            key=lambda player: (
                int(player["rating"] or 0),
                str(player.get("name") or "").casefold(),
            ),
        )[:candidate_limit]

    quality_kwargs = {
        "repeat_pairing_penalty": repeat_pairing_penalty,
        "score_group_float_penalty": score_group_float_penalty,
        "score_diff_penalty": score_diff_penalty,
    }

    def unplayed_count(player_id: int) -> int:
        return sum(1 for item in float_histories.get(int(player_id), []) if item == "bye")

    unplayed_by_player = {int(player["id"]): unplayed_count(int(player["id"])) for player in tied_lowest}
    if len(set(unplayed_by_player.values())) > 1:
        min_unplayed = min(unplayed_by_player.values())
        tied_lowest = [
            player for player in tied_lowest
            if unplayed_by_player.get(int(player["id"]), 0) == min_unplayed
        ]
        prefer_bye_rank = True
    else:
        prefer_bye_rank = False

    def remaining_quality(bye_player: dict[str, Any]) -> tuple[Any, ...]:
        remaining = [player for player in players if int(player["id"]) != int(bye_player["id"])]
        if len(remaining) <= min(12, max_exhaustive_pairing_players):
            pairs = optimal_player_pairs(
                remaining,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
            )
        else:
            beam_width = 32 if len(players) <= 32 else 20
            branch_width = 10 if len(players) <= 32 else 8
            pairs = beam_player_pairs(
                remaining,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
                beam_width=beam_width,
                branch_width=branch_width,
            )
        quality = pairing_quality(
            pairs,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            **quality_kwargs,
        )
        bye_rank = (
            int(bye_player["rating"] or 0),
            str(bye_player.get("name") or "").casefold(),
        )
        if prefer_bye_rank:
            return (quality[0], quality[1], *bye_rank, quality[2])
        return (quality[0], quality[1], quality[2], *bye_rank)

    return min(tied_lowest, key=remaining_quality)


def swiss_pairings(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_player_ids: set[int],
    *,
    max_exhaustive_pairing_players: int,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[dict[str, Any]]:
    ranks = rank_by_player_id(standings)
    pending = sorted(
        players,
        key=lambda player: pairing_order_key(player, standings),
    )

    pairings: list[dict[str, Any]] = []
    board = 1

    if len(pending) % 2 == 1:
        bye_player = choose_bye_player_with_pairing_quality(
            pending,
            standings,
            histories,
            float_histories,
            played_pairs,
            bye_player_ids,
            ranks,
            max_exhaustive_pairing_players=max_exhaustive_pairing_players,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
        pending.remove(bye_player)
        pairings.append(
            {
                "board_number": 9999,
                "white_player_id": bye_player["id"],
                "black_player_id": None,
                "result": "BYE",
                "is_bye": 1,
            }
        )

    player_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    floaters: list[dict[str, Any]] = []

    for group in score_groups(pending, standings):
        group.extend(floaters)
        floaters = []
        # Os floaters que descem têm pontuação maior que os nativos do grupo;
        # reordenamos para que entrem pelo topo (como o pareamento por equipes
        # já faz). Sem isto eles caem no fim da lista e voltam a flutuar a cada
        # grupo, despencando até o fundo da tabela e gerando diferenças de
        # pontuação evitáveis (violação do downfloat mínimo FIDE C.04).
        group = sorted(group, key=lambda player: pairing_order_key(player, standings))

        group_pairs, group_floaters = dutch_bracket_pairing(
            group,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            max_exhaustive_pairing_players=max_exhaustive_pairing_players,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
        player_pairs.extend(group_pairs)
        floaters.extend(group_floaters)

    if floaters:
        pairing_kwargs = {
            "repeat_pairing_penalty": repeat_pairing_penalty,
            "score_group_float_penalty": score_group_float_penalty,
            "score_diff_penalty": score_diff_penalty,
        }
        if len(floaters) <= max_exhaustive_pairing_players:
            leftover_pairs = optimal_player_pairs(
                floaters,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **pairing_kwargs,
            )
        else:
            leftover_pairs = beam_player_pairs(
                floaters,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **pairing_kwargs,
            )
        player_pairs.extend(leftover_pairs)

    # Salvaguarda global para criterios absolutos FIDE. O pareamento por bracket
    # pode fechar grupos superiores cedo demais e empurrar o fundo da tabela para
    # repeticao de adversario ou violacao dura de cor; nesses casos re-pareia o
    # campo inteiro pelo otimo global e adota somente se melhorar esse quadro.
    quality_kwargs = {
        "repeat_pairing_penalty": repeat_pairing_penalty,
        "score_group_float_penalty": score_group_float_penalty,
        "score_diff_penalty": score_diff_penalty,
    }
    current_quality = pairing_quality(
        player_pairs,
        standings,
        histories,
        float_histories,
        played_pairs,
        ranks,
        **quality_kwargs,
    )
    if current_quality[:2] != (0, 0):
        if len(pending) <= max_exhaustive_pairing_players:
            global_pairs = optimal_player_pairs(
                pending,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
            )
        else:
            global_pairs = beam_player_pairs(
                pending,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
            )
        global_quality = pairing_quality(
            global_pairs,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            **quality_kwargs,
        )
        if global_pairs and global_quality < current_quality:
            player_pairs = global_pairs
            current_quality = global_quality

        improved_pairs = improve_pairing_by_swaps(
            player_pairs,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            **quality_kwargs,
        )
        improved_quality = pairing_quality(
            improved_pairs,
            standings,
            histories,
            float_histories,
            played_pairs,
            ranks,
            **quality_kwargs,
        )
        if improved_pairs and improved_quality < current_quality:
            player_pairs = improved_pairs
            current_quality = improved_quality

        bad_pair_count = sum(
            1
            for pair in player_pairs
            if _single_pair_quality(
                pair[0],
                pair[1],
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
            )[:2] != (0, 0)
        )
        rematch_limits, final_rematch_limit = rematch_search_limits(len(player_pairs), bad_pair_count)
        for group_size, max_checked_rematches in rematch_limits:
            if current_quality[:2] == (0, 0):
                break
            rematched_pairs = improve_pairing_by_group_rematches(
                player_pairs,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                group_size=group_size,
                max_checked_rematches=max_checked_rematches,
                **quality_kwargs,
            )
            rematched_quality = pairing_quality(
                rematched_pairs,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
            )
            if rematched_pairs and rematched_quality < current_quality:
                player_pairs = rematched_pairs
                current_quality = rematched_quality

        if current_quality[:2] != (0, 0):
            rematched_pairs = improve_pairing_by_group_rematches(
                player_pairs,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                group_size=4,
                max_checked_rematches=final_rematch_limit,
                **quality_kwargs,
            )
            rematched_quality = pairing_quality(
                rematched_pairs,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **quality_kwargs,
            )
            if rematched_pairs and rematched_quality < current_quality:
                player_pairs = rematched_pairs

    player_pairs = sorted(
        player_pairs,
        key=lambda pair: min(
            ranks.get(pair[0]["id"], 0),
            ranks.get(pair[1]["id"], 0),
        ),
    )
    for player, opponent in player_pairs:
        white_id, black_id = choose_colors(player, opponent, histories)
        pairings.append(
            {
                "board_number": board,
                "white_player_id": white_id,
                "black_player_id": black_id,
                "result": "",
                "is_bye": 0,
            }
        )
        board += 1

    normal_pairings = [pairing for pairing in pairings if not pairing["is_bye"]]
    bye_pairings = [pairing for pairing in pairings if pairing["is_bye"]]
    for index, pairing in enumerate(normal_pairings + bye_pairings, start=1):
        pairing["board_number"] = index
    return normal_pairings + bye_pairings


def append_requested_bye_pairings(
    pairings: list[dict[str, Any]],
    bye_by_player: dict[int, str],
) -> list[dict[str, Any]]:
    """Anexa pairings de bye solicitado (F/H/Z) ao final da rodada.

    O tipo é gravado em `result` (letra F/H/Z) para que o cálculo de
    pontuação e a exportação TRF reconheçam o bye solicitado e o distingam
    do bye alocado pelo pareamento (`U`)."""
    if not bye_by_player:
        return pairings
    result = list(pairings)
    next_board = max((int(p["board_number"]) for p in result), default=0) + 1
    for player_id in sorted(bye_by_player):
        bye_type = str(bye_by_player[player_id] or "H").strip().upper()
        result.append(
            {
                "board_number": next_board,
                "white_player_id": int(player_id),
                "black_player_id": None,
                "result": bye_type,
                "is_bye": 1,
            }
        )
        next_board += 1
    return result
