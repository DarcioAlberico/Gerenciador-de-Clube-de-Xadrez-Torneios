"""Assistente de normas/títulos FIDE (spec E5 — Fase E).

Funções puras de APOIO ao árbitro: estimam, a partir da performance e do perfil
dos adversários, se um jogador atingiu indicadores compatíveis com uma norma de
título. **Não é homologação** — a concessão de norma/título é exclusiva da FIDE
e segue o regulamento completo (Handbook 1.4x). Aqui implementamos os
indicadores verificáveis mais comuns, de forma transparente.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from src.services.constants import RESULT_POINTS, player_full_name
from src.services.fide_rating import fide_performance, player_rating_for_type

# Apenas partidas jogadas no tabuleiro contam (igual ao relatório de rating).
_RATED_RESULTS = {"1-0", "0-1", "1/2-1/2"}

FIDE_TITLES = {"GM", "IM", "FM", "CM", "WGM", "WIM", "WFM", "WCM", "NM", "WNM"}

# Requisitos por norma (aproximação documentada dos limiares FIDE). `min_titled`
# é derivado (≈ 1/3 dos adversários) em tempo de avaliação.
TITLE_NORM_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "GM": {"label": "Grande Mestre (GM)", "performance": 2600, "min_games": 9, "min_federations": 3, "min_avg_opponent": 2380},
    "IM": {"label": "Mestre Internacional (IM)", "performance": 2450, "min_games": 9, "min_federations": 3, "min_avg_opponent": 2230},
    "WGM": {"label": "Grande Mestra (WGM)", "performance": 2400, "min_games": 9, "min_federations": 3, "min_avg_opponent": 2180},
    "WIM": {"label": "Mestra Internacional (WIM)", "performance": 2250, "min_games": 9, "min_federations": 3, "min_avg_opponent": 2030},
}


def _has_title(player: Mapping[str, Any]) -> bool:
    return str(player.get("title") or "").strip().upper() in FIDE_TITLES


def _applicable_titles(player: Mapping[str, Any]) -> list[str]:
    titles = ["GM", "IM"]
    if str(player.get("sex") or "").strip().upper() == "F":
        titles += ["WGM", "WIM"]
    return titles


def evaluate_titles(
    player: Mapping[str, Any],
    performance: int,
    games: int,
    federations: int,
    titled_opponents: int,
    average_opponent: float,
) -> list[dict[str, Any]]:
    """Avalia, por título aplicável, os indicadores de norma do jogador."""
    required_titled = max(1, math.ceil(games / 3)) if games else 1
    evaluations: list[dict[str, Any]] = []
    for code in _applicable_titles(player):
        spec = TITLE_NORM_REQUIREMENTS[code]
        indicators = [
            {"name": "Performance", "required": spec["performance"], "actual": performance},
            {"name": "Partidas validas", "required": spec["min_games"], "actual": games},
            {"name": "Federacoes dos adversarios", "required": spec["min_federations"], "actual": federations},
            {"name": "Adversarios titulados", "required": required_titled, "actual": titled_opponents},
            {"name": "Media de rating dos adversarios", "required": spec["min_avg_opponent"], "actual": int(average_opponent)},
        ]
        for indicator in indicators:
            indicator["ok"] = indicator["actual"] >= indicator["required"]
        missing = [
            f"{indicator['name']} requer {indicator['required']} (obtido {indicator['actual']})"
            for indicator in indicators
            if not indicator["ok"]
        ]
        evaluations.append(
            {
                "title": code,
                "label": spec["label"],
                "meets": not missing,
                "indicators": indicators,
                "missing": missing,
            }
        )
    return evaluations


def build_norm_report(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = "fide",
) -> list[dict[str, Any]]:
    """Indicadores de norma por jogador (somente quem jogou partidas válidas)."""
    by_id: dict[int, Mapping[str, Any]] = {int(player["id"]): player for player in players}
    rating_by_id = {pid: player_rating_for_type(player, rating_type) for pid, player in by_id.items()}

    games: dict[int, list[tuple[int, float]]] = {pid: [] for pid in by_id}
    for pairing in closed_pairings:
        if pairing.get("is_bye"):
            continue
        white_id = pairing.get("white_player_id")
        black_id = pairing.get("black_player_id")
        result = pairing.get("result")
        if white_id not in by_id or not black_id or black_id not in by_id:
            continue
        if result not in _RATED_RESULTS:
            continue
        white_points, black_points = RESULT_POINTS[result]
        games[int(white_id)].append((int(black_id), white_points))
        games[int(black_id)].append((int(white_id), black_points))

    report: list[dict[str, Any]] = []
    for pid, player in by_id.items():
        rated = [(opp, earned) for opp, earned in games[pid] if rating_by_id.get(opp, 0) > 0]
        count = len(rated)
        if count == 0:
            continue
        score = round(sum(earned for _opp, earned in rated), 2)
        average_opponent = round(sum(rating_by_id[opp] for opp, _earned in rated) / count, 1)
        performance = fide_performance(average_opponent, score, count)

        opponent_federations = {
            str(by_id[opp].get("federation_id") or "").strip().upper()
            for opp, _earned in rated
            if str(by_id[opp].get("federation_id") or "").strip()
        }
        player_federation = str(player.get("federation_id") or "").strip().upper()
        if player_federation:
            opponent_federations.add(player_federation)
        titled_opponents = sum(1 for opp, _earned in rated if _has_title(by_id[opp]))

        evaluations = evaluate_titles(
            player, performance, count, len(opponent_federations), titled_opponents, average_opponent
        )
        achieved = [item["label"] for item in evaluations if item["meets"]]
        report.append(
            {
                "player_id": pid,
                "name": player_full_name(player),
                "sex": str(player.get("sex") or "").strip().upper(),
                "performance": performance,
                "games": count,
                "average_opponent": average_opponent,
                "federations": len(opponent_federations),
                "titled_opponents": titled_opponents,
                "titles": evaluations,
                "achieved": achieved,
            }
        )

    report.sort(key=lambda item: (-int(item["performance"]), str(item["name"]).casefold()))
    return report
