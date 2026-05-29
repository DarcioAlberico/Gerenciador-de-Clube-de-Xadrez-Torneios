"""Helpers puros do emparceiramento por equipes."""

from __future__ import annotations

from typing import Any

from src.services.constants import AppError
from src.services.pairing.constraints import (
    choose_team_bye,
    choose_team_colors,
    greedy_team_pairs,
    is_color_valid_fide,
    optimal_team_pairs,
    team_pairing_order_key,
)


def team_starter_roster(
    team_name: str,
    assignments: list[dict[str, Any]],
    boards_count: int,
) -> tuple[dict[int, int], int]:
    """Extrai os titulares ativos de uma equipe e seu seed rating médio.

    Retorna o mapa tabuleiro→player_id e a média (arredondada) dos ratings.
    Levanta AppError se faltar titular ativo em qualquer tabuleiro exigido.
    """
    starters: dict[int, int] = {}
    ratings: dict[int, int] = {}
    for assignment in assignments:
        if assignment.get("role") != "starter" or not assignment.get("board_number"):
            continue
        if assignment.get("player_status") != "active":
            continue
        board_number = int(assignment["board_number"])
        if 1 <= board_number <= boards_count:
            starters[board_number] = int(assignment["player_id"])
            ratings[board_number] = int(assignment.get("player_rating") or 0)

    missing = [board for board in range(1, boards_count + 1) if board not in starters]
    if missing:
        missing_text = ", ".join(str(board) for board in missing)
        raise AppError(f"Equipe {team_name} sem titular ativo no tabuleiro {missing_text}.")

    seed_rating = round(sum(ratings.values()) / max(boards_count, 1))
    return starters, seed_rating


def team_bye_summary(
    match: dict[str, Any],
    *,
    win_points: float,
    boards_count: int,
) -> dict[str, Any]:
    """Resumo de fechamento para um confronto de bye (vitória administrativa)."""
    return {
        "team_match_id": int(match["id"]),
        "result": "BYE",
        "white_match_points": win_points,
        "black_match_points": 0.0,
        "white_game_points": float(boards_count),
        "black_game_points": 0.0,
    }


def team_match_summary(
    match: dict[str, Any],
    boards: list[dict[str, Any]],
    white_team_player_ids: set[int],
    black_team_player_ids: set[int],
    result_points: dict[str, tuple[float, float]],
    *,
    win_points: float,
    loss_points: float,
    draw_points: float,
) -> dict[str, Any]:
    """Soma os pontos de partida de um confronto fechado de equipes.

    Atribui os pontos de cada tabuleiro à equipe correta (tabuleiros pares
    têm as cores invertidas) e converte o placar de jogo em pontos de match.
    """
    white_game_points = 0.0
    black_game_points = 0.0
    for board in boards:
        white_points, black_points = result_points[str(board["result"])]
        if board.get("white_player_id") in white_team_player_ids:
            white_game_points += white_points
        elif board.get("white_player_id") in black_team_player_ids:
            black_game_points += white_points

        if board.get("black_player_id") in white_team_player_ids:
            white_game_points += black_points
        elif board.get("black_player_id") in black_team_player_ids:
            black_game_points += black_points

    if white_game_points > black_game_points:
        match_result = "1-0"
        white_match_points, black_match_points = win_points, loss_points
    elif black_game_points > white_game_points:
        match_result = "0-1"
        white_match_points, black_match_points = loss_points, win_points
    else:
        match_result = "1/2-1/2"
        white_match_points = black_match_points = draw_points

    return {
        "team_match_id": int(match["id"]),
        "result": match_result,
        "white_match_points": white_match_points,
        "black_match_points": black_match_points,
        "white_game_points": round(white_game_points, 2),
        "black_game_points": round(black_game_points, 2),
    }


def team_match_payload(
    match_number: int,
    white_team_id: int,
    black_team_id: int,
    rosters: dict[int, dict[int, int]],
    boards_count: int,
) -> dict[str, Any]:
    boards = []
    for board_number in range(1, boards_count + 1):
        if board_number % 2 == 1:
            white_player_id = rosters[white_team_id][board_number]
            black_player_id = rosters[black_team_id][board_number]
        else:
            white_player_id = rosters[black_team_id][board_number]
            black_player_id = rosters[white_team_id][board_number]
        boards.append(
            {
                "board_number": board_number,
                "white_player_id": white_player_id,
                "black_player_id": black_player_id,
                "result": "",
            }
        )
    return {
        "match_number": match_number,
        "white_team_id": white_team_id,
        "black_team_id": black_team_id,
        "result": "",
        "is_bye": 0,
        "boards": boards,
    }


def team_bye_payload(
    match_number: int,
    team_id: int,
    settings: dict[str, Any],
    boards_count: int,
) -> dict[str, Any]:
    return {
        "match_number": match_number,
        "white_team_id": team_id,
        "black_team_id": None,
        "result": "BYE",
        "white_match_points": float(settings.get("team_match_win_points", 2.0) or 2.0),
        "black_match_points": 0.0,
        "white_game_points": float(boards_count),
        "black_game_points": 0.0,
        "is_bye": 1,
        "boards": [],
    }


def first_round_team_matches(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int]],
    seed_ratings: dict[int, int],
    boards_count: int,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    ordered = sorted(
        teams,
        key=lambda team: (-seed_ratings[int(team["id"])], str(team["name"]).casefold()),
    )
    pairable = ordered[:]
    bye_team = None
    if len(pairable) % 2 == 1:
        bye_team = min(
            pairable,
            key=lambda team: (seed_ratings[int(team["id"])], str(team["name"]).casefold()),
        )
        pairable.remove(bye_team)

    half = len(pairable) // 2
    upper = pairable[:half]
    lower = pairable[half:]
    matches: list[dict[str, Any]] = []
    for index, team in enumerate(upper, start=1):
        opponent = lower[index - 1]
        if index % 2 == 1:
            white_team_id = int(team["id"])
            black_team_id = int(opponent["id"])
        else:
            white_team_id = int(opponent["id"])
            black_team_id = int(team["id"])
        matches.append(
            team_match_payload(
                index,
                white_team_id,
                black_team_id,
                rosters,
                boards_count,
            )
        )

    if bye_team:
        matches.append(team_bye_payload(len(matches) + 1, int(bye_team["id"]), settings, boards_count))
    return matches


def search_dutch_team_pairing(
    pairable: list[dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    strict_colors: bool,
    seed_ratings: dict[int, int],
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
            if frozenset((int(p1["id"]), int(p2["id"]))) in played_pairs:
                continue

            if strict_colors:
                white_id, _black_id = choose_team_colors(p1, p2, histories, seed_ratings)
                p1_color = "W" if white_id == int(p1["id"]) else "B"
                p2_color = "W" if white_id == int(p2["id"]) else "B"

                if not is_color_valid_fide(int(p1["id"]), p1_color, histories) or not is_color_valid_fide(
                    int(p2["id"]), p2_color, histories
                ):
                    p1_color_rev = "B" if p1_color == "W" else "W"
                    p2_color_rev = "B" if p2_color == "W" else "W"
                    if not is_color_valid_fide(int(p1["id"]), p1_color_rev, histories) or not is_color_valid_fide(
                        int(p2["id"]), p2_color_rev, histories
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


def dutch_team_bracket_pairing(
    group: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    seed_ratings: dict[int, int],
    *,
    max_exhaustive_pairing_teams: int,
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
        best_pairs = search_dutch_team_pairing(
            pairable,
            histories,
            played_pairs,
            strict_colors=True,
            seed_ratings=seed_ratings,
        )
        if best_pairs is not None:
            return best_pairs, floaters

    for num_floaters in range(n % 2, n + 1, 2):
        if num_floaters == n:
            break
        pairable = group[:-num_floaters] if num_floaters else group
        floaters = group[-num_floaters:] if num_floaters else []
        best_pairs = search_dutch_team_pairing(
            pairable,
            histories,
            played_pairs,
            strict_colors=False,
            seed_ratings=seed_ratings,
        )
        if best_pairs is not None:
            return best_pairs, floaters

    for num_floaters in range(n % 2, n + 1, 2):
        if num_floaters == n:
            break
        pairable = group[:-num_floaters] if num_floaters else group
        floaters = group[-num_floaters:] if num_floaters else []
        if len(pairable) <= max_exhaustive_pairing_teams:
            best_pairs = optimal_team_pairs(
                pairable,
                standings,
                played_pairs,
                rank_by_team_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            )
        else:
            best_pairs = greedy_team_pairs(
                pairable,
                standings,
                played_pairs,
                rank_by_team_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
            )

        if all(frozenset((int(p1["id"]), int(p2["id"]))) not in played_pairs for p1, p2 in best_pairs):
            return best_pairs, floaters

    return [], group


def swiss_team_matches(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int]],
    seed_ratings: dict[int, int],
    boards_count: int,
    settings: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_team_ids: set[int],
    *,
    max_exhaustive_pairing_teams: int,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
) -> list[dict[str, Any]]:
    rank_by_team_id = {
        int(team_id): int(item.get("position", 0) or 0)
        for team_id, item in standings.items()
    }
    pending = sorted(
        teams,
        key=lambda team: team_pairing_order_key(team, standings, seed_ratings),
    )

    bye_team = None
    if len(pending) % 2 == 1:
        bye_team = choose_team_bye(pending, standings, bye_team_ids, seed_ratings)
        pending.remove(bye_team)

    score_groups: dict[float, list[dict[str, Any]]] = {}
    for team in pending:
        score = float(standings.get(int(team["id"]), {}).get("match_points", 0.0) or 0.0)
        score_groups.setdefault(score, []).append(team)

    team_pairs = []
    floaters = []

    for score in sorted(score_groups.keys(), reverse=True):
        group = score_groups[score]
        group.extend(floaters)
        floaters = []

        group = sorted(group, key=lambda team: team_pairing_order_key(team, standings, seed_ratings))

        group_pairs, group_floaters = dutch_team_bracket_pairing(
            group,
            standings,
            histories,
            played_pairs,
            rank_by_team_id,
            seed_ratings,
            max_exhaustive_pairing_teams=max_exhaustive_pairing_teams,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
        )
        team_pairs.extend(group_pairs)
        floaters.extend(group_floaters)

    if floaters:
        pairing_kwargs = {
            "repeat_pairing_penalty": repeat_pairing_penalty,
            "score_group_float_penalty": score_group_float_penalty,
            "score_diff_penalty": score_diff_penalty,
        }
        if len(floaters) <= max_exhaustive_pairing_teams:
            leftover_pairs = optimal_team_pairs(
                floaters,
                standings,
                played_pairs,
                rank_by_team_id,
                **pairing_kwargs,
            )
        else:
            leftover_pairs = greedy_team_pairs(
                floaters,
                standings,
                played_pairs,
                rank_by_team_id,
                **pairing_kwargs,
            )
        team_pairs.extend(leftover_pairs)

    team_pairs = sorted(
        team_pairs,
        key=lambda pair: min(
            rank_by_team_id.get(int(pair[0]["id"]), 0),
            rank_by_team_id.get(int(pair[1]["id"]), 0),
        ),
    )

    matches = []
    for match_number, (team, opponent) in enumerate(team_pairs, start=1):
        white_team_id, black_team_id = choose_team_colors(team, opponent, histories, seed_ratings)
        matches.append(
            team_match_payload(
                match_number,
                white_team_id,
                black_team_id,
                rosters,
                boards_count,
            )
        )
    if bye_team:
        matches.append(team_bye_payload(len(matches) + 1, int(bye_team["id"]), settings, boards_count))
    return matches
