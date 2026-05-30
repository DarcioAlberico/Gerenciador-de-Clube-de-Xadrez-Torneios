"""Helpers puros de desempate (spec §10).

Funções aqui não tocam o banco — recebem dicts já preparados pelo serviço
e devolvem estruturas explicáveis. PairingService delega para elas.
"""

from __future__ import annotations

import math
from typing import Any

from src.services.constants import (
    REQUESTED_BYE_POINTS,
    RESULT_POINTS,
    player_full_name,
)


def performance_components(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Componentes do critério de Performance (média de rating dos rivais)."""
    rated_games = [
        {
            "opponent_id": int(opponent_id),
            "opponent_name": stats[opponent_id]["name"],
            "opponent_rating": int(stats[opponent_id]["rating"] or 0),
            "earned": round(float(earned), 2),
        }
        for opponent_id, earned in player_stat["earned_against"]
        if opponent_id in stats and int(stats[opponent_id]["rating"] or 0) > 0
    ]
    score = round(sum(float(item["earned"]) for item in rated_games), 2)
    games = len(rated_games)
    average_rating = round(
        sum(int(item["opponent_rating"]) for item in rated_games) / games,
        2,
    ) if games else 0.0
    return {
        "label": "Performance",
        "value": player_stat["performance"] if player_stat["performance"] != "" else None,
        "formula": "Media de rating dos adversarios ajustada pelo percentual de score.",
        "games": rated_games,
        "score": score,
        "average_rating": average_rating,
        "total": player_stat["performance"],
    }


def performance_rating(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> int | str:
    games = len(player_stat["earned_against"])
    if not games:
        return ""

    opponent_ratings = [
        int(stats[opponent_id]["rating"] or 0)
        for opponent_id, _earned in player_stat["earned_against"]
        if opponent_id in stats and int(stats[opponent_id]["rating"] or 0) > 0
    ]
    if not opponent_ratings:
        return ""

    score = sum(float(earned) for _opponent_id, earned in player_stat["earned_against"])
    average_rating = sum(opponent_ratings) / len(opponent_ratings)
    diff: float
    if score <= 0:
        diff = -800
    elif score >= games:
        diff = 800
    else:
        diff = 400 * math.log10(score / (games - score))
        diff = max(min(diff, 800), -800)
    return int(round(average_rating + diff))


def team_standing_value(item: dict[str, Any], criterion: str) -> float:
    if criterion == "wins":
        return float(item.get("wins", 0) or 0)
    if criterion == "game_points":
        return float(item.get("game_points", 0.0) or 0.0)
    return float(item.get("match_points", 0.0) or 0.0)


def flatten_tiebreak_components(standings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in standings:
        for criterion, components in dict(item.get("tiebreak_components") or {}).items():
            rows.append(
                {
                    "player_id": int(item["player_id"]),
                    "player_name": item.get("name", ""),
                    "criterion": criterion,
                    "value": components.get("value"),
                    "components": components,
                }
            )
    return rows


def tiebreak_narrative_from_standings(
    standings: list[dict[str, Any]],
    player_id: int,
) -> dict[str, Any]:
    target = next(
        (row for row in standings if int(row.get("player_id") or 0) == int(player_id)),
        None,
    )
    if target is None:
        return {"lines": ["Jogador não encontrado na classificação."], "decisive": None}

    position = int(target.get("position") or 0)
    points = float(target.get("points") or 0)
    name = target.get("name") or ""
    components = target.get("tiebreak_components") or {}

    tied_group = [
        row for row in standings
        if float(row.get("points") or 0) == points
        and int(row.get("player_id") or 0) != int(player_id)
    ]
    tied_names = [row.get("name") or "?" for row in tied_group]

    def pluralize(n: int, singular: str, plural: str) -> str:
        return singular if n == 1 else plural

    lines: list[str] = [
        f"{position}º — {name} — {points:g} {pluralize(int(points), 'ponto', 'pontos')}",
        "",
        "Por que está nesta posição?",
        "",
    ]

    if not tied_group:
        lines.append(f"• Pontos: único com {points:g}. Sem necessidade de desempate.")
        return {"lines": lines, "tied_group_size": 1, "decisive": None}

    if len(tied_names) == 1:
        lines.append(f"• Pontos: empate com {tied_names[0]}.")
    elif len(tied_names) == 2:
        lines.append(f"• Pontos: empate com {tied_names[0]} e {tied_names[1]}.")
    else:
        lines.append(
            "• Pontos: empate com " + ", ".join(tied_names[:-1]) + f" e {tied_names[-1]}."
        )

    criteria_order = [
        "buchholz",
        "buchholz_median",
        "sonneborn_berger",
        "direct_encounter",
        "wins",
        "performance",
    ]
    ordinals = ["1º", "2º", "3º", "4º", "5º", "6º"]

    decisive: str | None = None
    for index, key in enumerate(criteria_order):
        comp = components.get(key) or {}
        value = comp.get("value")
        label = comp.get("label", key)
        if value in (None, "", 0) and key not in {"wins"}:
            continue

        others: list[tuple[str, Any]] = []
        for row in tied_group:
            other_comp = (row.get("tiebreak_components") or {}).get(key) or {}
            other_value = other_comp.get("value")
            if other_value in (None, ""):
                continue
            others.append((row.get("name") or "?", other_value))

        if not others:
            continue

        ordinal = ordinals[index] if index < len(ordinals) else f"{index + 1}º"
        lines.append(f"• {ordinal} desempate ({label}): {value}.")
        for other_name, other_value in others:
            lines.append(f"     – {other_name}: {other_value}")

        all_different = all(value != other_value for _, other_value in others)
        if all_different:
            decisive = key
            lines.append("")
            lines.append(f"Decidido por: {label}.")
            break

    if decisive is None:
        lines.append("")
        lines.append("Empate persistente em todos os critérios disponíveis.")

    return {
        "lines": lines,
        "tied_group_size": len(tied_group) + 1,
        "decisive": decisive,
    }


def order_player_standings(stats: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_stats = sorted(
        stats.values(),
        key=lambda item: (
            -item["points"],
            -item["buchholz"],
            -item["buchholz_median"],
            -item["sonneborn_berger"],
            -item["wins"],
            -item["rating"],
            item["name"].casefold(),
        ),
    )

    for index, item in enumerate(ordered_stats, start=1):
        item["position"] = index
    return ordered_stats


def calculate_player_standings(
    tournament: dict[str, Any],
    players: list[dict[str, Any]],
    closed_pairings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = {}
    for player in players:
        stats[player["id"]] = {
            "player_id": player["id"],
            "name": player_full_name(player),
            "club": player["club"],
            "rating": int(player["rating"] or 0),
            "category": player["category"],
            "age_category": player.get("age_category", ""),
            "rating_category": player.get("rating_category", ""),
            "prize_tags": player.get("prize_tags", ""),
            "active": int(player["active"]),
            "player_status": player.get("player_status", "active"),
            "starting_points": float(player.get("starting_points", 0.0) or 0.0),
            "points": float(player.get("starting_points", 0.0) or 0.0),
            "wins": 0,
            "buchholz": 0.0,
            "buchholz_median": 0.0,
            "sonneborn_berger": 0.0,
            "white_count": 0,
            "black_count": 0,
            "byes": 0,
            "opponents": [],
            "earned_against": [],
            "games": [],
            "performance": "",
        }

    for pairing in closed_pairings:
        white_id = pairing["white_player_id"]
        black_id = pairing["black_player_id"]
        result = pairing["result"]

        if white_id not in stats:
            continue

        if pairing["is_bye"]:
            bye_points = REQUESTED_BYE_POINTS.get(
                str(result or "").strip().upper(),
                float(tournament["bye_points"]),
            )
            stats[white_id]["points"] += bye_points
            stats[white_id]["byes"] += 1
            stats[white_id]["games"].append(
                {
                    "round": int(pairing.get("round_number") or 0),
                    "color": "bye",
                    "opponent_id": None,
                    "opponent_name": "BYE",
                    "result": result,
                    "earned": bye_points,
                }
            )
            continue

        if not black_id or black_id not in stats or result not in RESULT_POINTS:
            continue

        white_points, black_points = RESULT_POINTS[result]
        stats[white_id]["points"] += white_points
        stats[black_id]["points"] += black_points
        stats[white_id]["white_count"] += 1
        stats[black_id]["black_count"] += 1
        stats[white_id]["opponents"].append(black_id)
        stats[black_id]["opponents"].append(white_id)
        stats[white_id]["earned_against"].append((black_id, white_points))
        stats[black_id]["earned_against"].append((white_id, black_points))
        stats[white_id]["games"].append(
            {
                "round": int(pairing.get("round_number") or 0),
                "color": "white",
                "opponent_id": int(black_id),
                "opponent_name": stats[black_id]["name"],
                "result": result,
                "earned": white_points,
            }
        )
        stats[black_id]["games"].append(
            {
                "round": int(pairing.get("round_number") or 0),
                "color": "black",
                "opponent_id": int(white_id),
                "opponent_name": stats[white_id]["name"],
                "result": result,
                "earned": black_points,
            }
        )
        if white_points == 1.0 and black_points == 0.0:
            stats[white_id]["wins"] += 1
        if black_points == 1.0 and white_points == 0.0:
            stats[black_id]["wins"] += 1

    for player_stat in stats.values():
        opponent_scores = [
            stats[opponent_id]["points"]
            for opponent_id in player_stat["opponents"]
            if opponent_id in stats
        ]
        player_stat["buchholz"] = round(sum(opponent_scores), 2)
        if len(opponent_scores) >= 3:
            ordered = sorted(opponent_scores)
            player_stat["buchholz_median"] = round(sum(ordered[1:-1]), 2)
        else:
            player_stat["buchholz_median"] = player_stat["buchholz"]

        sb = 0.0
        for opponent_id, earned in player_stat["earned_against"]:
            sb += stats[opponent_id]["points"] * earned
        player_stat["sonneborn_berger"] = round(sb, 2)
        player_stat["performance"] = performance_rating(player_stat, stats)
        player_stat["tiebreak_components"] = player_tiebreak_components(player_stat, stats)

    return order_player_standings(stats)


def calculate_team_standings(
    settings: dict[str, Any],
    teams: list[dict[str, Any]],
    closed_matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = {}
    for team in teams:
        team_id = int(team["id"])
        stats[team_id] = {
            "team_id": team_id,
            "name": team["name"],
            "club": team.get("club", ""),
            "captain": team.get("captain", ""),
            "active": int(team.get("active", 0) or 0),
            "match_points": 0.0,
            "game_points": 0.0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "byes": 0,
            "matches": 0,
            "buchholz": 0.0,
            "opponents": [],
        }

    for match in closed_matches:
        white_team_id = int(match["white_team_id"])
        black_team_id = int(match["black_team_id"]) if match.get("black_team_id") else None
        if white_team_id not in stats:
            continue
        if match.get("is_bye"):
            stats[white_team_id]["match_points"] += float(match.get("white_match_points", 0.0) or 0.0)
            stats[white_team_id]["game_points"] += float(match.get("white_game_points", 0.0) or 0.0)
            stats[white_team_id]["wins"] += 1
            stats[white_team_id]["byes"] += 1
            continue
        if black_team_id is None or black_team_id not in stats:
            continue

        white_match_points = float(match.get("white_match_points", 0.0) or 0.0)
        black_match_points = float(match.get("black_match_points", 0.0) or 0.0)
        stats[white_team_id]["match_points"] += white_match_points
        stats[black_team_id]["match_points"] += black_match_points
        stats[white_team_id]["game_points"] += float(match.get("white_game_points", 0.0) or 0.0)
        stats[black_team_id]["game_points"] += float(match.get("black_game_points", 0.0) or 0.0)
        stats[white_team_id]["matches"] += 1
        stats[black_team_id]["matches"] += 1
        stats[white_team_id]["opponents"].append(black_team_id)
        stats[black_team_id]["opponents"].append(white_team_id)

        if white_match_points > black_match_points:
            stats[white_team_id]["wins"] += 1
            stats[black_team_id]["losses"] += 1
        elif black_match_points > white_match_points:
            stats[black_team_id]["wins"] += 1
            stats[white_team_id]["losses"] += 1
        else:
            stats[white_team_id]["draws"] += 1
            stats[black_team_id]["draws"] += 1

    for team_stat in stats.values():
        team_stat["match_points"] = round(float(team_stat["match_points"]), 2)
        team_stat["game_points"] = round(float(team_stat["game_points"]), 2)
        team_stat["buchholz"] = round(
            sum(
                float(stats[opponent_id]["match_points"])
                for opponent_id in team_stat["opponents"]
                if opponent_id in stats
            ),
            2,
        )

    primary = str(settings.get("team_standing_primary", "match_points") or "match_points")
    secondary = str(settings.get("team_standing_secondary", "game_points") or "game_points")
    ordered_stats = sorted(
        stats.values(),
        key=lambda item: (
            -team_standing_value(item, primary),
            -team_standing_value(item, secondary),
            -float(item["buchholz"]),
            -int(item["wins"]),
            str(item["name"]).casefold(),
        ),
    )
    for index, item in enumerate(ordered_stats, start=1):
        item["position"] = index
    return ordered_stats


def player_tiebreak_components(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Componentes brutos dos critérios de desempate de um jogador.

    Retorna um dict indexado por código de critério: buchholz, buchholz_median,
    sonneborn_berger, direct_encounter, wins, performance.
    """
    opponent_rows = []
    opponent_scores = []
    for opponent_id in player_stat["opponents"]:
        if opponent_id not in stats:
            continue
        score = float(stats[opponent_id]["points"])
        opponent_scores.append(score)
        opponent_rows.append(
            {
                "opponent_id": int(opponent_id),
                "opponent_name": stats[opponent_id]["name"],
                "points": round(score, 2),
            }
        )

    ordered_scores = sorted(opponent_scores)
    if len(ordered_scores) >= 3:
        median_used = ordered_scores[1:-1]
        cut_low = ordered_scores[0]
        cut_high = ordered_scores[-1]
    else:
        median_used = ordered_scores
        cut_low = None
        cut_high = None

    sb_rows = []
    for opponent_id, earned in player_stat["earned_against"]:
        if opponent_id not in stats:
            continue
        opponent_points = float(stats[opponent_id]["points"])
        sb_rows.append(
            {
                "opponent_id": int(opponent_id),
                "opponent_name": stats[opponent_id]["name"],
                "opponent_points": round(opponent_points, 2),
                "earned": round(float(earned), 2),
                "contribution": round(opponent_points * float(earned), 2),
            }
        )

    tied_opponents = [
        game
        for game in player_stat["games"]
        if game.get("opponent_id") in stats
        and float(stats[int(game["opponent_id"])]["points"]) == float(player_stat["points"])
    ]
    direct_score = round(sum(float(game.get("earned") or 0.0) for game in tied_opponents), 2)
    performance = performance_components(player_stat, stats)

    return {
        "buchholz": {
            "label": "Buchholz",
            "value": player_stat["buchholz"],
            "formula": "Soma dos pontos finais dos adversarios enfrentados.",
            "opponents": opponent_rows,
            "total": player_stat["buchholz"],
        },
        "buchholz_median": {
            "label": "Buchholz mediano",
            "value": player_stat["buchholz_median"],
            "formula": "Soma dos pontos dos adversarios com corte do menor e maior valor quando ha 3 ou mais jogos.",
            "used_scores": [round(value, 2) for value in median_used],
            "cut_low": cut_low,
            "cut_high": cut_high,
            "total": player_stat["buchholz_median"],
        },
        "sonneborn_berger": {
            "label": "Sonneborn-Berger",
            "value": player_stat["sonneborn_berger"],
            "formula": "Pontos do adversario multiplicados pelo resultado obtido contra ele.",
            "opponents": sb_rows,
            "total": player_stat["sonneborn_berger"],
        },
        "direct_encounter": {
            "label": "Confronto direto",
            "value": direct_score,
            "formula": "Pontos marcados contra adversarios que terminaram empatados em pontos.",
            "games": tied_opponents,
            "total": direct_score,
        },
        "wins": {
            "label": "Vitorias",
            "value": int(player_stat["wins"]),
            "formula": "Quantidade de partidas vencidas no tabuleiro.",
            "games": [game for game in player_stat["games"] if float(game.get("earned") or 0.0) == 1.0],
            "total": int(player_stat["wins"]),
        },
        "performance": performance,
    }
