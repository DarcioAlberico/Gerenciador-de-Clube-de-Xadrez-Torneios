"""Helpers puros para historicos usados no emparceiramento."""

from __future__ import annotations

from typing import Any

from src.services.constants import REQUESTED_BYE_POINTS


def team_played_pairs(matches: list[dict[str, Any]]) -> set[frozenset[int]]:
    played: set[frozenset[int]] = set()
    for match in matches:
        if match["is_bye"] or not match["black_team_id"]:
            continue
        played.add(frozenset((int(match["white_team_id"]), int(match["black_team_id"]))))
    return played


def team_bye_ids(matches: list[dict[str, Any]]) -> set[int]:
    return {
        int(match["white_team_id"])
        for match in matches
        if match["is_bye"]
    }


def team_color_histories(matches: list[dict[str, Any]]) -> dict[int, list[str]]:
    histories: dict[int, list[str]] = {}
    for match in matches:
        white_team_id = int(match["white_team_id"])
        black_team_id = int(match["black_team_id"]) if match["black_team_id"] else None
        histories.setdefault(white_team_id, [])
        if match["is_bye"]:
            histories[white_team_id].append("BYE")
            continue
        histories[white_team_id].append("W")
        if black_team_id:
            histories.setdefault(black_team_id, [])
            histories[black_team_id].append("B")
    return histories


def played_pairs(pairings: list[dict[str, Any]]) -> set[frozenset[int]]:
    played: set[frozenset[int]] = set()
    for pairing in pairings:
        if pairing["is_bye"] or not pairing["black_player_id"]:
            continue
        played.add(frozenset((pairing["white_player_id"], pairing["black_player_id"])))
    return played


def bye_player_ids(pairings: list[dict[str, Any]]) -> set[int]:
    return {
        pairing["white_player_id"]
        for pairing in pairings
        if pairing["is_bye"] and _blocks_pairing_allocated_bye(pairing.get("result"))
    }


def _blocks_pairing_allocated_bye(result: Any) -> bool:
    """True when a prior unplayed result blocks a future pairing-allocated bye.

    BBP/FIDE 2025 distinguish zero/half-point absences (Z/H), which count as
    unplayed games, from full-point byes and pairing-allocated byes. Z/H should
    influence C9 quality, but they do not make the player ineligible for the
    pairing-allocated bye.
    """
    code = str(result or "").strip().upper()
    return code in {"", "BYE", "U", "F"}


def color_histories(pairings: list[dict[str, Any]]) -> dict[int, list[str]]:
    histories: dict[int, list[str]] = {}
    for pairing in pairings:
        white_id = pairing["white_player_id"]
        black_id = pairing["black_player_id"]
        histories.setdefault(white_id, [])
        if pairing["is_bye"]:
            histories[white_id].append("BYE")
            continue
        if black_id:
            histories.setdefault(black_id, [])
            histories[white_id].append("W")
            histories[black_id].append("B")
    return histories


def float_histories(
    pairings: list[dict[str, Any]],
    players: list[dict[str, Any]],
    bye_points: float,
    result_points: dict[str, tuple[float, float]],
) -> dict[int, list[str]]:
    scores = {
        int(player["id"]): float(player.get("starting_points", 0.0) or 0.0)
        for player in players
    }
    histories: dict[int, list[str]] = {player_id: [] for player_id in scores}

    for pairing in pairings:
        white_id = int(pairing["white_player_id"])
        black_id = int(pairing["black_player_id"]) if pairing["black_player_id"] else None
        histories.setdefault(white_id, [])
        scores.setdefault(white_id, 0.0)

        if pairing["is_bye"]:
            histories[white_id].append("bye")
            scores[white_id] += REQUESTED_BYE_POINTS.get(
                str(pairing.get("result") or "").strip().upper(), bye_points
            )
            continue

        if black_id is None:
            continue
        histories.setdefault(black_id, [])
        scores.setdefault(black_id, 0.0)

        white_score = scores[white_id]
        black_score = scores[black_id]
        if white_score < black_score:
            histories[white_id].append("up")
            histories[black_id].append("down")
        elif white_score > black_score:
            histories[white_id].append("down")
            histories[black_id].append("up")
        else:
            histories[white_id].append("=")
            histories[black_id].append("=")

        result = pairing["result"]
        if result in result_points:
            white_points, black_points = result_points[result]
            scores[white_id] += white_points
            scores[black_id] += black_points
    return histories
