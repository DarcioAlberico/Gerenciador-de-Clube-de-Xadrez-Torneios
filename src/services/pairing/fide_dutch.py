"""Helpers puros do emparceiramento suíço individual."""

from __future__ import annotations

from typing import Any

from src.services.constants import AppError
from src.services.pairing.constraints import (
    choose_bye_player,
    choose_colors,
    greedy_player_pairs,
    is_color_valid_fide,
    optimal_player_pairs,
    pairing_order_key,
    rank_by_player_id,
)


def first_round_pairings(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        players,
        key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
    )
    pairable = ordered[:]
    bye_player = None
    if len(pairable) % 2 == 1:
        bye_player = min(
            pairable,
            key=lambda player: (int(player["rating"] or 0), player["name"].casefold()),
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


def round_robin_pairings(
    players: list[dict[str, Any]],
    next_number: int,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    ordered = sorted(
        players,
        key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
    )
    if len(ordered) % 2 == 1:
        ordered.append({"id": -1, "name": "BYE", "is_dummy": True})

    players_count = len(ordered)
    if next_number > players_count - 1:
        raise AppError("O numero maximo de rodadas do torneio ja foi atingido.")

    round_number = next_number
    rotated = [ordered[0]]
    for index in range(1, players_count):
        shift = round_number - 1
        rotated_index = ((index - 1 - shift) % (players_count - 1)) + 1
        rotated.append(ordered[rotated_index])

    upper = rotated[: players_count // 2]
    lower = rotated[players_count // 2:]
    lower.reverse()

    pairings: list[dict[str, Any]] = []
    board = 1
    for index in range(players_count // 2):
        if (round_number % 2 == 1 and index == 0) or (round_number % 2 == 0 and index > 0):
            white, black = upper[index], lower[index]
        else:
            white, black = lower[index], upper[index]

        if white["id"] == -1 or black["id"] == -1:
            real_player = black if white["id"] == -1 else white
            pairings.append(
                {
                    "board_number": board,
                    "white_player_id": real_player["id"],
                    "black_player_id": None,
                    "result": "1-0" if not settings.get("disable_bye") else "",
                    "is_bye": 1,
                }
            )
        else:
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

    return pairings


def scheveningen_pairings(
    players: list[dict[str, Any]],
    next_number: int,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Sistema Scheveningen: cada jogador do grupo A enfrenta todos do grupo B.

    Os grupos são as metades por ranking inicial (top = A, base = B), exige
    número par de jogadores. Em N rodadas (N = jogadores por grupo) cada par
    A×B se enfrenta exatamente uma vez; as cores alternam para equilibrar.
    """
    ordered = sorted(
        players,
        key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
    )
    if len(ordered) % 2 == 1:
        raise AppError("Scheveningen exige numero par de jogadores (dois grupos iguais).")

    per_group = len(ordered) // 2
    if next_number > per_group:
        raise AppError("O numero maximo de rodadas do Scheveningen ja foi atingido.")

    group_a = ordered[:per_group]
    group_b = ordered[per_group:]

    pairings: list[dict[str, Any]] = []
    for index in range(per_group):
        opponent = group_b[(index + next_number - 1) % per_group]
        player = group_a[index]
        if (index + next_number) % 2 == 0:
            white_id, black_id = player["id"], opponent["id"]
        else:
            white_id, black_id = opponent["id"], player["id"]
        pairings.append(
            {
                "board_number": index + 1,
                "white_player_id": white_id,
                "black_player_id": black_id,
                "result": "",
                "is_bye": 0,
            }
        )
    return pairings


def knockout_pairings(
    players: list[dict[str, Any]],
    next_number: int,
    settings: dict[str, Any],
    previous_pairings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ordered = sorted(
        players,
        key=lambda player: (-int(player["rating"] or 0), player["name"].casefold()),
    )

    if next_number == 1:
        active_players = ordered[:]
    else:
        if previous_pairings is None:
            raise AppError("Rodada anterior não encontrada.")

        active_players_set = set()
        seed_map = {int(player["id"]): index for index, player in enumerate(ordered)}

        for pairing in previous_pairings:
            if pairing["is_bye"]:
                active_players_set.add(int(pairing["white_player_id"]))
                continue

            white_id = int(pairing["white_player_id"])
            black_id = int(pairing["black_player_id"])

            if pairing["result"] == "1-0":
                active_players_set.add(white_id)
            elif pairing["result"] == "0-1":
                active_players_set.add(black_id)
            else:
                white_index = seed_map.get(white_id, 9999)
                black_index = seed_map.get(black_id, 9999)
                active_players_set.add(white_id if white_index < black_index else black_id)

        active_players = [player for player in ordered if int(player["id"]) in active_players_set]

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
        pairings.append(
            {
                "board_number": board,
                "white_player_id": player["id"],
                "black_player_id": None,
                "result": "1-0" if not settings.get("disable_bye") else "",
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
            best_pairs = greedy_player_pairs(
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
        bye_player = choose_bye_player(pending, standings, bye_player_ids)
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

    player_pairs = []
    floaters = []

    for group in score_groups(pending, standings):
        group.extend(floaters)
        floaters = []

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
            leftover_pairs = greedy_player_pairs(
                floaters,
                standings,
                histories,
                float_histories,
                played_pairs,
                ranks,
                **pairing_kwargs,
            )
        player_pairs.extend(leftover_pairs)

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
