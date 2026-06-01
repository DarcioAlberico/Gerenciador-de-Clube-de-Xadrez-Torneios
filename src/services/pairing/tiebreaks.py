"""Helpers puros de desempate (spec §10).

Funções aqui não tocam o banco — recebem dicts já preparados pelo serviço
e devolvem estruturas explicáveis. PairingService delega para elas.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from src.services.constants import (
    REQUESTED_BYE_POINTS,
    RESULT_POINTS,
    player_full_name,
)


# ---------------------------------------------------------------------------
# Registro de critérios de desempate configuráveis (spec E1/E2).
#
# Cada critério tem rótulo + fórmula curta. A ORDEM dos critérios é configurável
# por torneio (tabela tournament_settings.tiebreak_sequence). Quando nenhuma
# sequência é informada, usa-se DEFAULT_PLAYER_TIEBREAKS, que reproduz EXATAMENTE
# a classificação histórica: pontos (sempre primeiro), Buchholz, Buchholz
# mediano, Sonneborn-Berger, vitórias, e por fim rating/nome como criténos
# técnicos finais.
#
# `points`, `rating` e `name` são aplicados FORA da sequência (pontos sempre em
# primeiro; rating/nome sempre por último), por isso não aparecem no registro.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TiebreakCriterion:
    code: str
    label: str
    formula: str
    needs_cut: bool = False


PLAYER_TIEBREAKS: dict[str, TiebreakCriterion] = {
    "buchholz": TiebreakCriterion(
        "buchholz", "Buchholz", "Soma dos pontos finais dos adversários enfrentados."
    ),
    "buchholz_cut1": TiebreakCriterion(
        "buchholz_cut1",
        "Buchholz Cut-1",
        "Buchholz descartando o adversário de menor pontuação.",
        needs_cut=True,
    ),
    "buchholz_cut2": TiebreakCriterion(
        "buchholz_cut2",
        "Buchholz Cut-2",
        "Buchholz descartando os dois adversários de menor pontuação.",
        needs_cut=True,
    ),
    "buchholz_median": TiebreakCriterion(
        "buchholz_median",
        "Buchholz mediano",
        "Buchholz descartando o maior e o menor adversário (3+ jogos).",
    ),
    "sonneborn_berger": TiebreakCriterion(
        "sonneborn_berger",
        "Sonneborn-Berger",
        "Pontos do adversário multiplicados pelo resultado obtido contra ele.",
    ),
    "direct_encounter": TiebreakCriterion(
        "direct_encounter",
        "Confronto direto",
        "Pontos marcados contra adversários empatados em pontos.",
    ),
    "wins": TiebreakCriterion(
        "wins", "Vitórias", "Número de partidas vencidas no tabuleiro."
    ),
    "cumulative": TiebreakCriterion(
        "cumulative",
        "Progressivo",
        "Soma das pontuações acumuladas após cada rodada.",
    ),
    "cumulative_opp": TiebreakCriterion(
        "cumulative_opp",
        "Progressivo dos adversários",
        "Soma do progressivo de todos os adversários enfrentados.",
    ),
    "koya": TiebreakCriterion(
        "koya",
        "Sistema Koya",
        "Pontos obtidos contra adversários com ao menos 50% dos pontos.",
    ),
    "aro": TiebreakCriterion(
        "aro",
        "Rating médio dos adversários",
        "Média de rating dos adversários ranqueados.",
    ),
    "aroc": TiebreakCriterion(
        "aroc",
        "Rating médio (cortado)",
        "Média de rating dos adversários descartando os extremos.",
    ),
    "performance": TiebreakCriterion(
        "performance", "Performance", "Rating performance estimado no torneio."
    ),
    "black_games": TiebreakCriterion(
        "black_games", "Partidas com pretas", "Número de partidas jogadas com as pretas."
    ),
    "black_wins": TiebreakCriterion(
        "black_wins", "Vitórias com pretas", "Número de vitórias jogando de pretas."
    ),
    "games_played": TiebreakCriterion(
        "games_played", "Partidas jogadas", "Número de partidas disputadas no tabuleiro."
    ),
}

DEFAULT_PLAYER_TIEBREAKS: list[str] = [
    "buchholz",
    "buchholz_median",
    "sonneborn_berger",
    "wins",
]

TEAM_TIEBREAKS: dict[str, TiebreakCriterion] = {
    "match_points": TiebreakCriterion(
        "match_points", "Match points", "Pontos de confronto da equipe (vitória/empate/derrota)."
    ),
    "game_points": TiebreakCriterion(
        "game_points", "Game points", "Soma dos pontos de tabuleiro da equipe."
    ),
    "buchholz": TiebreakCriterion(
        "buchholz", "Buchholz (equipes)", "Soma dos match points dos adversários da equipe."
    ),
    "wins": TiebreakCriterion(
        "wins", "Vitórias (equipes)", "Número de confrontos vencidos pela equipe."
    ),
}

DEFAULT_TEAM_TIEBREAKS: list[str] = ["match_points", "game_points", "buchholz", "wins"]


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dedup_codes(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        if code and code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def _parse_tiebreak_sequence(
    raw: Any,
    registry: dict[str, TiebreakCriterion],
    drop: set[str],
) -> list[dict[str, Any]]:
    """Normaliza uma sequência de desempates vinda do banco/UI.

    Aceita string JSON ou lista; cada item pode ser um código (str) ou um dict
    {"code", "params"}. Descarta códigos desconhecidos, duplicados e os de
    `drop`. Sequência inválida/vazia retorna [] (= usar o padrão).
    """
    if not raw:
        return []
    items: Any = raw
    if isinstance(raw, str):
        try:
            items = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in items:
        if isinstance(entry, str):
            code, params = entry.strip(), {}
        elif isinstance(entry, dict):
            code = str(entry.get("code") or "").strip()
            raw_params = entry.get("params")
            params = dict(raw_params) if isinstance(raw_params, dict) else {}
        else:
            continue
        if code in drop or code not in registry or code in seen:
            continue
        seen.add(code)
        result.append({"code": code, "params": params})
    return result


def parse_player_tiebreak_sequence(raw: Any) -> list[dict[str, Any]]:
    return _parse_tiebreak_sequence(raw, PLAYER_TIEBREAKS, drop={"points"})


def parse_team_tiebreak_sequence(raw: Any) -> list[dict[str, Any]]:
    return _parse_tiebreak_sequence(raw, TEAM_TIEBREAKS, drop=set())


def serialize_tiebreak_sequence(sequence: list[dict[str, Any]]) -> str:
    return json.dumps(
        [{"code": item["code"], "params": item.get("params", {})} for item in sequence],
        ensure_ascii=False,
    )


def _resolve_player_codes(sequence: list[dict[str, Any]] | None) -> list[tuple[str, dict[str, Any]]]:
    if sequence:
        return [(item["code"], item.get("params", {})) for item in sequence]
    return [(code, {}) for code in DEFAULT_PLAYER_TIEBREAKS]


def _resolve_team_codes(
    settings: dict[str, Any],
    sequence: list[dict[str, Any]] | None,
) -> list[str]:
    if sequence:
        codes = [item["code"] for item in sequence if item.get("code") in TEAM_TIEBREAKS]
        if codes:
            return _dedup_codes(codes)
    primary = str(settings.get("team_standing_primary", "match_points") or "match_points")
    secondary = str(settings.get("team_standing_secondary", "game_points") or "game_points")
    return _dedup_codes([primary, secondary, "buchholz", "wins"])


def _opponent_points(player_stat: dict[str, Any], stats: dict[int, dict[str, Any]]) -> list[float]:
    return [
        float(stats[opponent_id]["points"])
        for opponent_id in player_stat["opponents"]
        if opponent_id in stats
    ]


def _buchholz_with_cut(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    cut_low: int,
    cut_high: int,
    unplayed: str = "real",
) -> float:
    scores = _opponent_points(player_stat, stats)
    if unplayed == "self":
        own = float(player_stat["points"])
        scores = scores + [own] * int(player_stat.get("byes", 0) or 0)
    if not scores:
        return 0.0
    ordered = sorted(scores)
    low = max(0, int(cut_low))
    high = max(0, int(cut_high))
    if low + high >= len(ordered):
        return 0.0
    kept = ordered[low: len(ordered) - high] if high else ordered[low:]
    return round(sum(kept), 2)


def _average_rating_opponents(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    cut: int = 0,
) -> float:
    ratings = [
        int(stats[opponent_id]["rating"] or 0)
        for opponent_id in player_stat["opponents"]
        if opponent_id in stats and int(stats[opponent_id]["rating"] or 0) > 0
    ]
    if not ratings:
        return 0.0
    ordered = sorted(ratings)
    trim = max(0, int(cut))
    if trim and len(ordered) > 2 * trim:
        ordered = ordered[trim: len(ordered) - trim]
    return round(sum(ordered) / len(ordered), 2)


def _direct_encounter_score(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> float:
    points = float(player_stat["points"])
    total = 0.0
    for game in player_stat["games"]:
        opponent_id = game.get("opponent_id")
        if opponent_id in stats and float(stats[opponent_id]["points"]) == points:
            total += float(game.get("earned") or 0.0)
    return round(total, 2)


def _cumulative_score(player_stat: dict[str, Any]) -> float:
    running = float(player_stat.get("starting_points", 0.0) or 0.0)
    total = 0.0
    for game in sorted(player_stat["games"], key=lambda item: int(item.get("round") or 0)):
        running += float(game.get("earned") or 0.0)
        total += running
    return round(total, 2)


def _koya_score(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    rounds_total: int,
) -> float:
    threshold = 0.5 * float(rounds_total or 0)
    total = 0.0
    for opponent_id, earned in player_stat["earned_against"]:
        if opponent_id in stats and float(stats[opponent_id]["points"]) >= threshold:
            total += float(earned)
    return round(total, 2)


def _black_wins(player_stat: dict[str, Any]) -> int:
    return sum(
        1
        for game in player_stat["games"]
        if game.get("color") == "black" and float(game.get("earned") or 0.0) == 1.0
    )


def player_tiebreak_value(
    code: str,
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    params: dict[str, Any],
    rounds_total: int,
) -> float:
    """Valor escalar ordenável (maior = melhor) de um critério para um jogador.

    Lê de campos canônicos já calculados quando existem (buchholz, mediano, SB,
    vitórias, performance) para garantir consistência total com a classificação
    histórica; calcula os critérios novos sob demanda.
    """
    if code == "points":
        return float(player_stat["points"])
    if code == "buchholz":
        return float(player_stat["buchholz"])
    if code == "buchholz_median":
        return float(player_stat["buchholz_median"])
    if code == "sonneborn_berger":
        return float(player_stat["sonneborn_berger"])
    if code == "wins":
        return float(player_stat["wins"])
    if code == "performance":
        perf = player_stat.get("performance")
        return float(perf) if isinstance(perf, (int, float)) else 0.0
    if code in ("buchholz_cut1", "buchholz_cut2"):
        default_low = 1 if code == "buchholz_cut1" else 2
        cut_low = int(params.get("cut_low", default_low))
        cut_high = int(params.get("cut_high", 0))
        unplayed = str(params.get("unplayed", "real"))
        return _buchholz_with_cut(player_stat, stats, cut_low, cut_high, unplayed)
    if code == "aro":
        return _average_rating_opponents(player_stat, stats, cut=0)
    if code == "aroc":
        return _average_rating_opponents(player_stat, stats, cut=int(params.get("cut", 1)))
    if code == "direct_encounter":
        return _direct_encounter_score(player_stat, stats)
    if code == "cumulative":
        return float(player_stat.get("cumulative", 0.0) or 0.0)
    if code == "cumulative_opp":
        return float(player_stat.get("cumulative_opp", 0.0) or 0.0)
    if code == "koya":
        return _koya_score(player_stat, stats, rounds_total)
    if code == "black_games":
        return float(player_stat.get("black_count", 0) or 0)
    if code == "black_wins":
        return float(_black_wins(player_stat))
    if code == "games_played":
        return float(len(player_stat["opponents"]))
    return 0.0


def _ordering_value(item: dict[str, Any], code: str) -> float:
    values = item.get("tiebreak_values")
    if isinstance(values, dict) and code in values:
        return _as_float(values[code])
    if code == "points":
        return float(item.get("points", 0.0) or 0.0)
    return _as_float(item.get(code, 0.0))


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
    # Performance só faz sentido sobre adversários COM rating. O percentual
    # (score/games) e a média precisam usar o MESMO conjunto — senão jogos
    # contra não-ranqueados inflariam/deflacionariam a performance sem alterar
    # a média (definição padrão FIDE: ambos sobre os jogos ranqueados).
    rated = [
        (int(stats[opponent_id]["rating"] or 0), float(earned))
        for opponent_id, earned in player_stat["earned_against"]
        if opponent_id in stats and int(stats[opponent_id]["rating"] or 0) > 0
    ]
    if not rated:
        return ""

    games = len(rated)
    score = sum(earned for _rating, earned in rated)
    average_rating = sum(rating for rating, _earned in rated) / games
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
    if criterion == "buchholz":
        return float(item.get("buchholz", 0.0) or 0.0)
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

    configured_order = [
        str(code) for code in (target.get("tiebreak_order") or []) if str(code) in components
    ]
    criteria_order = configured_order or [
        "buchholz",
        "buchholz_median",
        "sonneborn_berger",
        "direct_encounter",
        "wins",
        "performance",
    ]

    def ordinal(index: int) -> str:
        return f"{index + 1}º"

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

        lines.append(f"• {ordinal(index)} desempate ({label}): {value}.")
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


def order_player_standings(
    stats: dict[int, dict[str, Any]],
    sequence: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Ordena a classificação por pontos + sequência de desempates configurável.

    Pontos são sempre o critério primário e rating/nome os critérios técnicos
    finais. `sequence` vazia/None usa DEFAULT_PLAYER_TIEBREAKS, reproduzindo a
    classificação histórica byte a byte.
    """
    codes = [code for code, _params in _resolve_player_codes(sequence)]

    def sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        head = (-float(item.get("points", 0.0) or 0.0),)
        mids = tuple(-_ordering_value(item, code) for code in codes)
        tail = (-float(item.get("rating", 0) or 0), str(item.get("name", "")).casefold())
        return head + mids + tail

    ordered_stats = sorted(stats.values(), key=sort_key)
    for index, item in enumerate(ordered_stats, start=1):
        item["position"] = index
    return ordered_stats


def calculate_player_standings(
    tournament: dict[str, Any],
    players: list[dict[str, Any]],
    closed_pairings: list[dict[str, Any]],
    sequence: list[dict[str, Any]] | None = None,
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

    rounds_total = max(
        (int(game.get("round") or 0) for player_stat in stats.values() for game in player_stat["games"]),
        default=0,
    )
    codes = _resolve_player_codes(sequence)

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
        player_stat["cumulative"] = _cumulative_score(player_stat)

    # Critério progressivo dos adversários depende do progressivo já calculado.
    for player_stat in stats.values():
        player_stat["cumulative_opp"] = round(
            sum(
                float(stats[opponent_id]["cumulative"])
                for opponent_id in player_stat["opponents"]
                if opponent_id in stats
            ),
            2,
        )

    # Escalares ordenáveis dos critérios ativos (sem sobrescrever campos
    # canônicos como performance/wins) + componentes explicáveis.
    for player_stat in stats.values():
        player_stat["tiebreak_values"] = {
            code: player_tiebreak_value(code, player_stat, stats, params, rounds_total)
            for code, params in codes
        }
        player_stat["tiebreak_order"] = [code for code, _params in codes]
        player_stat["tiebreak_components"] = player_tiebreak_components(
            player_stat, stats, codes=codes, rounds_total=rounds_total
        )

    return order_player_standings(stats, sequence)


def calculate_team_standings(
    settings: dict[str, Any],
    teams: list[dict[str, Any]],
    closed_matches: list[dict[str, Any]],
    sequence: list[dict[str, Any]] | None = None,
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

    codes = _resolve_team_codes(settings, sequence)
    ordered_stats = sorted(
        stats.values(),
        key=lambda item: tuple(-team_standing_value(item, code) for code in codes)
        + (str(item["name"]).casefold(),),
    )
    for index, item in enumerate(ordered_stats, start=1):
        item["team_tiebreak_order"] = list(codes)
        item["position"] = index
    return ordered_stats


def player_tiebreak_components(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    codes: list[tuple[str, dict[str, Any]]] | None = None,
    rounds_total: int = 0,
) -> dict[str, dict[str, Any]]:
    """Componentes brutos dos critérios de desempate de um jogador.

    Sempre retorna os seis critérios históricos (buchholz, buchholz_median,
    sonneborn_berger, direct_encounter, wins, performance) para compatibilidade
    com relatórios/exportações existentes. Quando `codes` é informado, acrescenta
    um componente explicável para cada critério ativo adicional (Buchholz Cut,
    progressivo, Koya, ARO, etc.).
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

    components: dict[str, dict[str, Any]] = {
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

    if codes:
        for code, params in codes:
            if code in components or code not in PLAYER_TIEBREAKS:
                continue
            value = player_tiebreak_value(code, player_stat, stats, params, rounds_total)
            criterion = PLAYER_TIEBREAKS[code]
            components[code] = {
                "label": criterion.label,
                "value": value,
                "formula": criterion.formula,
                "total": value,
            }

    return components
