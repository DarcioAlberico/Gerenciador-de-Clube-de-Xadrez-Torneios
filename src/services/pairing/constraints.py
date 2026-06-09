"""Restricoes e preferencias puras de emparceiramento."""

from __future__ import annotations

from typing import Any


COLOR_HARD_VIOLATION_PENALTY = 100_000


def would_make_three_colors(player_id: int, color: str, histories: dict[int, list[str]]) -> bool:
    history = histories.get(int(player_id), [])
    return len(history) >= 2 and history[-2:] == [color, color]


def is_color_valid_fide(player_id: int, color: str, histories: dict[int, list[str]]) -> bool:
    history = [item for item in histories.get(player_id, []) if item in {"W", "B"}]
    white_count = history.count("W")
    black_count = history.count("B")
    next_white = white_count + (1 if color == "W" else 0)
    next_black = black_count + (1 if color == "B" else 0)
    if abs(next_white - next_black) > 2:
        return False
    if len(history) >= 2 and history[-2:] == [color, color]:
        return False
    return True


def color_hard_violation(player_id: int, color: str, histories: dict[int, list[str]]) -> int:
    return 0 if is_color_valid_fide(player_id, color, histories) else 1


def color_assignment_cost(
    player_id: int,
    color: str,
    histories: dict[int, list[str]],
) -> tuple[int, int]:
    return (
        color_hard_violation(player_id, color, histories),
        assignment_color_penalty(player_id, color, histories),
    )


def rank_by_player_id(standings: dict[int, dict[str, Any]]) -> dict[int, int]:
    return {
        int(player_id): int(item.get("position", 0) or 0)
        for player_id, item in standings.items()
    }


def select_rating_for_order(
    initial_order: str,
    *,
    rating: int,
    national: int,
    international: int,
    default: int | None = None,
) -> int:
    """Rating correspondente a uma ordem inicial (``initial_order``).

    Fonte unica da regra, compartilhada pelo seeding de pareamento e pela
    importacao de ratings oficiais. ``default`` cobre as ordens sem regra
    especifica ("rating"/"manual"/desconhecida): o seeding usa o proprio
    ``rating`` do jogador (``default=None``); a importacao oficial passa o
    melhor rating disponivel. Os demais ramos sao identicos para ambos.
    """
    if initial_order == "national_rating":
        return national or rating
    if initial_order == "international_rating":
        return international or rating
    if initial_order == "international_then_national":
        return international or national or rating
    if initial_order == "max_rating":
        return max(national, international, rating)
    return rating if default is None else default


def rating_for_initial_order(player: dict[str, Any], initial_order: str) -> int:
    return select_rating_for_order(
        initial_order,
        rating=int(player.get("rating") or 0),
        national=int(player.get("national_rating") or 0),
        international=int(player.get("international_rating") or 0),
    )


def pairing_order_key(
    player: dict[str, Any],
    standings: dict[int, dict[str, Any]],
) -> tuple[float, float, float, float, int, int, str]:
    standing = standings.get(player["id"], {})
    return (
        -float(standing.get("points", 0.0) or 0.0),
        -float(standing.get("buchholz", 0.0) or 0.0),
        -float(standing.get("buchholz_median", 0.0) or 0.0),
        -float(standing.get("sonneborn_berger", 0.0) or 0.0),
        -int(standing.get("wins", 0) or 0),
        -int(player["rating"] or 0),
        player["name"].casefold(),
    )


def team_pairing_order_key(
    team: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    seed_ratings: dict[int, int],
) -> tuple[float, float, int, str]:
    team_id = int(team["id"])
    standing = standings.get(team_id, {})
    return (
        -float(standing.get("match_points", 0.0) or 0.0),
        -float(standing.get("game_points", 0.0) or 0.0),
        -int(seed_ratings.get(team_id, 0)),
        str(team["name"]).casefold(),
    )


def choose_bye_player(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    bye_player_ids: set[int],
) -> dict[str, Any]:
    candidates = [player for player in players if player["id"] not in bye_player_ids]
    if not candidates:
        candidates = players
    return min(
        candidates,
        key=lambda player: (
            standings.get(player["id"], {}).get("points", 0.0),
            int(player["rating"] or 0),
            player["name"].casefold(),
        ),
    )


def choose_team_bye(
    teams: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    bye_team_ids: set[int],
    seed_ratings: dict[int, int],
) -> dict[str, Any]:
    candidates = [team for team in teams if int(team["id"]) not in bye_team_ids]
    if not candidates:
        candidates = teams
    return min(
        candidates,
        key=lambda team: (
            float(standings.get(int(team["id"]), {}).get("match_points", 0.0) or 0.0),
            float(standings.get(int(team["id"]), {}).get("game_points", 0.0) or 0.0),
            seed_ratings.get(int(team["id"]), 0),
            str(team["name"]).casefold(),
        ),
    )


def float_penalty(
    player_id: int,
    direction: str,
    float_histories: dict[int, list[str]],
) -> int:
    history = float_histories.get(player_id, [])
    penalty = history.count(direction) * 25
    if history[-2:] == [direction, direction]:
        penalty += 300
    elif history[-1:] == [direction]:
        penalty += 120
    return penalty


def assignment_color_penalty(
    player_id: int,
    color: str,
    histories: dict[int, list[str]],
) -> int:
    history = [item for item in histories.get(player_id, []) if item in {"W", "B"}]
    white_count = history.count("W")
    black_count = history.count("B")
    next_white = white_count + (1 if color == "W" else 0)
    next_black = black_count + (1 if color == "B" else 0)
    penalty = abs(next_white - next_black) * 12

    if history[-2:] == [color, color]:
        penalty += 250
    elif history[-1:] == [color]:
        penalty += 20

    if white_count - black_count >= 2 and color == "W":
        penalty += 120
    if black_count - white_count >= 2 and color == "B":
        penalty += 120

    return penalty


def choose_colors(
    player: dict[str, Any],
    opponent: dict[str, Any],
    histories: dict[int, list[str]],
) -> tuple[int, int]:
    player_id = player["id"]
    opponent_id = opponent["id"]
    first_hard, first_penalty = color_assignment_cost(player_id, "W", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "B", histories)
    first_hard += opponent_hard
    first_penalty += opponent_penalty

    second_hard, second_penalty = color_assignment_cost(player_id, "B", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "W", histories)
    second_hard += opponent_hard
    second_penalty += opponent_penalty

    if (first_hard, first_penalty) < (second_hard, second_penalty):
        return player_id, opponent_id
    if (second_hard, second_penalty) < (first_hard, first_penalty):
        return opponent_id, player_id

    if int(player["rating"] or 0) >= int(opponent["rating"] or 0):
        return player_id, opponent_id
    return opponent_id, player_id


def choose_team_colors(
    team: dict[str, Any],
    opponent: dict[str, Any],
    histories: dict[int, list[str]],
    seed_ratings: dict[int, int],
) -> tuple[int, int]:
    team_id = int(team["id"])
    opponent_id = int(opponent["id"])
    first_hard, first_penalty = color_assignment_cost(team_id, "W", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "B", histories)
    first_hard += opponent_hard
    first_penalty += opponent_penalty

    second_hard, second_penalty = color_assignment_cost(team_id, "B", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "W", histories)
    second_hard += opponent_hard
    second_penalty += opponent_penalty

    if (first_hard, first_penalty) < (second_hard, second_penalty):
        return team_id, opponent_id
    if (second_hard, second_penalty) < (first_hard, first_penalty):
        return opponent_id, team_id
    if seed_ratings.get(team_id, 0) >= seed_ratings.get(opponent_id, 0):
        return team_id, opponent_id
    return opponent_id, team_id


def pair_penalty(
    player: dict[str, Any],
    opponent: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> float:
    player_id = player["id"]
    opponent_id = opponent["id"]
    player_score = float(standings.get(player_id, {}).get("points", 0.0) or 0.0)
    opponent_score = float(standings.get(opponent_id, {}).get("points", 0.0) or 0.0)
    score_diff = abs(player_score - opponent_score)
    penalty = score_diff * score_diff_penalty

    if score_diff:
        penalty += score_group_float_penalty
        if player_score < opponent_score:
            penalty += float_penalty(player_id, "up", float_histories)
            penalty += float_penalty(opponent_id, "down", float_histories)
        else:
            penalty += float_penalty(player_id, "down", float_histories)
            penalty += float_penalty(opponent_id, "up", float_histories)

    rank_distance = abs(
        rank_by_player_id.get(player_id, 0)
        - rank_by_player_id.get(opponent_id, 0)
    )
    penalty += rank_distance * (4 if not score_diff else 1)

    if frozenset((player_id, opponent_id)) in played_pairs:
        penalty += repeat_pairing_penalty

    white_a, _black_a = choose_colors(player, opponent, histories)
    if white_a == player_id:
        hard_violations = color_hard_violation(player_id, "W", histories)
        hard_violations += color_hard_violation(opponent_id, "B", histories)
        color_penalty = assignment_color_penalty(player_id, "W", histories)
        color_penalty += assignment_color_penalty(opponent_id, "B", histories)
    else:
        hard_violations = color_hard_violation(player_id, "B", histories)
        hard_violations += color_hard_violation(opponent_id, "W", histories)
        color_penalty = assignment_color_penalty(player_id, "B", histories)
        color_penalty += assignment_color_penalty(opponent_id, "W", histories)

    return penalty + hard_violations * COLOR_HARD_VIOLATION_PENALTY + color_penalty


def team_pair_penalty(
    team: dict[str, Any],
    opponent: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> float:
    team_id = int(team["id"])
    opponent_id = int(opponent["id"])
    team_score = float(standings.get(team_id, {}).get("match_points", 0.0) or 0.0)
    opponent_score = float(standings.get(opponent_id, {}).get("match_points", 0.0) or 0.0)
    score_diff = abs(team_score - opponent_score)
    penalty = score_diff * score_diff_penalty
    if score_diff:
        penalty += score_group_float_penalty

    rank_distance = abs(rank_by_team_id.get(team_id, 0) - rank_by_team_id.get(opponent_id, 0))
    penalty += rank_distance * (4 if not score_diff else 1)

    if frozenset((team_id, opponent_id)) in played_pairs:
        penalty += repeat_pairing_penalty
    return penalty


def greedy_player_pairs(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pending = players[:]
    pairs = []
    while pending:
        player = pending.pop(0)
        opponent = min(
            pending,
            key=lambda candidate: pair_penalty(
                player,
                candidate,
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            ),
        )
        pending.remove(opponent)
        pairs.append((player, opponent))
    return pairs


def optimal_player_pairs(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    player_by_id = {int(player["id"]): player for player in players}
    penalty_cache: dict[tuple[int, int], float] = {}

    def penalty(player_id: int, opponent_id: int) -> float:
        key = (player_id, opponent_id)
        if key not in penalty_cache:
            penalty_cache[key] = pair_penalty(
                player_by_id[player_id],
                player_by_id[opponent_id],
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            )
        return penalty_cache[key]

    best_cost = float("inf")
    best_pairs: list[tuple[int, int]] = []
    seen_costs: dict[tuple[int, ...], float] = {}

    def search(
        remaining: tuple[int, ...],
        selected_pairs: list[tuple[int, int]],
        current_cost: float,
    ) -> None:
        nonlocal best_cost, best_pairs
        if current_cost >= best_cost:
            return
        if current_cost >= seen_costs.get(remaining, float("inf")):
            return
        seen_costs[remaining] = current_cost
        if not remaining:
            best_cost = current_cost
            best_pairs = selected_pairs[:]
            return

        player_id = remaining[0]
        candidates = sorted(remaining[1:], key=lambda candidate_id: penalty(player_id, candidate_id))
        for opponent_id in candidates:
            next_remaining = tuple(
                item_id for item_id in remaining[1:] if item_id != opponent_id
            )
            search(
                next_remaining,
                selected_pairs + [(player_id, opponent_id)],
                current_cost + penalty(player_id, opponent_id),
            )

    search(tuple(player_by_id), [], 0.0)
    if not best_pairs:
        return greedy_player_pairs(
            players,
            standings,
            histories,
            float_histories,
            played_pairs,
            rank_by_player_id,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
    return [(player_by_id[player_id], player_by_id[opponent_id]) for player_id, opponent_id in best_pairs]


def greedy_team_pairs(
    teams: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pending = teams[:]
    pairs = []
    while pending:
        team = pending.pop(0)
        opponent = min(
            pending,
            key=lambda candidate: team_pair_penalty(
                team,
                candidate,
                standings,
                played_pairs,
                rank_by_team_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            ),
        )
        pending.remove(opponent)
        pairs.append((team, opponent))
    return pairs


def optimal_team_pairs(
    teams: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    team_by_id = {int(team["id"]): team for team in teams}
    penalty_cache: dict[tuple[int, int], float] = {}

    def penalty(team_id: int, opponent_id: int) -> float:
        key = (team_id, opponent_id)
        if key not in penalty_cache:
            penalty_cache[key] = team_pair_penalty(
                team_by_id[team_id],
                team_by_id[opponent_id],
                standings,
                played_pairs,
                rank_by_team_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            )
        return penalty_cache[key]

    best_cost = float("inf")
    best_pairs: list[tuple[int, int]] = []
    seen_costs: dict[tuple[int, ...], float] = {}

    def search(
        remaining: tuple[int, ...],
        selected_pairs: list[tuple[int, int]],
        current_cost: float,
    ) -> None:
        nonlocal best_cost, best_pairs
        if current_cost >= best_cost:
            return
        if current_cost >= seen_costs.get(remaining, float("inf")):
            return
        seen_costs[remaining] = current_cost
        if not remaining:
            best_cost = current_cost
            best_pairs = selected_pairs[:]
            return

        team_id = remaining[0]
        candidates = sorted(remaining[1:], key=lambda candidate_id: penalty(team_id, candidate_id))
        for opponent_id in candidates:
            next_remaining = tuple(item_id for item_id in remaining[1:] if item_id != opponent_id)
            search(
                next_remaining,
                selected_pairs + [(team_id, opponent_id)],
                current_cost + penalty(team_id, opponent_id),
            )

    search(tuple(team_by_id), [], 0.0)
    if not best_pairs:
        return greedy_team_pairs(
            teams,
            standings,
            played_pairs,
            rank_by_team_id,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
    return [(team_by_id[team_id], team_by_id[opponent_id]) for team_id, opponent_id in best_pairs]
