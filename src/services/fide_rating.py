"""Cálculo de variação de rating FIDE (spec E3 — Fase B).

Funções puras, sem dependência de banco: recebem listas de jogadores e
emparceiramentos e devolvem as linhas do relatório (Ro, K, n, W, We, ΔElo, Rc,
Rp). Implementa a tabela oficial de expectativa FIDE, a regra dos 400 e o
desenvolvimento (fator K). É uma **estimativa de apoio ao árbitro**, não uma
homologação oficial — a federação continua sendo a autoridade do rating.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.constants import RESULT_POINTS, player_full_name

MAX_RATING_DIFF = 400

# Apenas partidas jogadas no tabuleiro contam para rating; WO/forfait (1F-0F,
# 0F-1F, 0F-0F), byes e partidas sem resultado são excluídos.
_RATED_RESULTS = {"1-0", "0-1", "1/2-1/2"}

# Tabela FIDE de expectativa (jogador de MAIOR rating), por faixa de diferença
# de rating. Pares (limite_superior_inclusivo, p_do_maior). Diferenças são
# limitadas a 400 (regra dos 400), então a tabela termina em 0.92.
_EXPECTANCY: list[tuple[int, float]] = [
    (3, 0.50), (10, 0.51), (17, 0.52), (25, 0.53), (32, 0.54), (39, 0.55),
    (46, 0.56), (53, 0.57), (61, 0.58), (68, 0.59), (76, 0.60), (83, 0.61),
    (91, 0.62), (98, 0.63), (106, 0.64), (113, 0.65), (121, 0.66), (129, 0.67),
    (137, 0.68), (145, 0.69), (153, 0.70), (162, 0.71), (170, 0.72), (179, 0.73),
    (188, 0.74), (197, 0.75), (206, 0.76), (215, 0.77), (225, 0.78), (235, 0.79),
    (245, 0.80), (256, 0.81), (267, 0.82), (278, 0.83), (290, 0.84), (302, 0.85),
    (315, 0.86), (328, 0.87), (344, 0.88), (357, 0.89), (374, 0.90), (391, 0.91),
    (400, 0.92),
]

# Tabela FIDE p -> dp (percentual de pontos -> diferença de rating) para a
# performance. Definida para p em [0.50, 1.00]; abaixo de 0.50 usa simetria.
_DP: dict[int, int] = {
    100: 800, 99: 677, 98: 589, 97: 538, 96: 501, 95: 470, 94: 444, 93: 422,
    92: 401, 91: 383, 90: 366, 89: 351, 88: 336, 87: 322, 86: 309, 85: 296,
    84: 284, 83: 273, 82: 262, 81: 251, 80: 240, 79: 230, 78: 220, 77: 211,
    76: 202, 75: 193, 74: 184, 73: 175, 72: 166, 71: 158, 70: 149, 69: 141,
    68: 133, 67: 125, 66: 117, 65: 110, 64: 102, 63: 95, 62: 87, 61: 80,
    60: 72, 59: 65, 58: 57, 57: 50, 56: 43, 55: 36, 54: 29, 53: 21, 52: 14,
    51: 7, 50: 0,
}


def fide_expected_score(rating: int, opponent_rating: int) -> float:
    """Pontuação esperada de `rating` contra `opponent_rating` (regra dos 400)."""
    diff = int(rating) - int(opponent_rating)
    capped = max(-MAX_RATING_DIFF, min(MAX_RATING_DIFF, diff))
    magnitude = abs(capped)
    probability = 0.92
    for upper, p_high in _EXPECTANCY:
        if magnitude <= upper:
            probability = p_high
            break
    return probability if capped >= 0 else round(1.0 - probability, 2)


def fide_dp(score_percent: float) -> int:
    """Diferença de rating correspondente a um percentual de pontos (p -> dp)."""
    pct = max(0.0, min(1.0, float(score_percent)))
    key = int(round(pct * 100))
    if key >= 50:
        return _DP[key]
    return -_DP[100 - key]


def fide_performance(average_opponent_rating: float, score: float, games: int) -> int:
    """Rating performance (Rp) = média dos adversários + dp(percentual)."""
    if games <= 0:
        return 0
    return int(round(float(average_opponent_rating) + fide_dp(float(score) / games)))


def fide_k_factor(
    rating: int,
    *,
    games_played: int | None = None,
    birth_year: int | None = None,
    tournament_year: int | None = None,
    k_override: int | None = None,
) -> int:
    """Coeficiente de desenvolvimento (fator K) FIDE, com override opcional.

    Regras: 40 para sub-18 com rating < 2300 ou jogador novo (< 30 partidas);
    10 a partir de 2400; 20 nos demais casos. `games_played`/`birth_year`
    costumam ser desconhecidos no desktop, então as regras dependentes deles só
    se aplicam quando informados.
    """
    if k_override:
        try:
            return int(k_override)
        except (TypeError, ValueError):
            pass
    value = int(rating or 0)
    if (
        birth_year
        and tournament_year
        and (int(tournament_year) - int(birth_year)) < 18
        and value < 2300
    ):
        return 40
    if games_played is not None and int(games_played) < 30:
        return 40
    if value >= 2400:
        return 10
    return 20


def player_rating_for_type(player: Mapping[str, Any], rating_type: str) -> int:
    """Rating do jogador para o tipo de relatório (fide/cbx).

    FIDE usa o rating internacional; CBX o nacional. Em ambos, recai sobre o
    rating principal quando o campo específico está vazio, para o relatório ser
    útil em bases que só preenchem `rating`.
    """
    if str(rating_type) == "cbx":
        primary = int(player.get("national_rating") or 0)
    else:
        primary = int(player.get("international_rating") or 0)
    return primary if primary > 0 else int(player.get("rating") or 0)


def _birth_year(player: Mapping[str, Any]) -> int | None:
    raw = str(player.get("birth_date") or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return None


def build_fide_report_rows(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = "fide",
    *,
    tournament_year: int | None = None,
) -> list[dict[str, Any]]:
    """Linhas do relatório de variação de rating FIDE.

    Considera apenas partidas efetivamente jogadas (exclui byes, WO e partidas
    sem resultado) e contra adversários COM rating na base escolhida. Jogadores
    sem rating recebem apenas a performance (sem variação).
    """
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
            continue  # WO/forfait/bye/sem resultado não contam para rating
        white_points, black_points = RESULT_POINTS[result]
        games[int(white_id)].append((int(black_id), white_points))
        games[int(black_id)].append((int(white_id), black_points))

    rows: list[dict[str, Any]] = []
    for pid, player in by_id.items():
        ro = rating_by_id[pid]
        rated_games = [(opp, earned) for opp, earned in games[pid] if rating_by_id.get(opp, 0) > 0]
        games_rated = len(rated_games)
        if games_rated == 0:
            continue

        score = round(sum(earned for _opp, earned in rated_games), 2)
        average_opponent = round(
            sum(rating_by_id[opp] for opp, _earned in rated_games) / games_rated, 1
        )
        rp = fide_performance(average_opponent, score, games_rated)

        row: dict[str, Any] = {
            "player_id": pid,
            "name": player_full_name(player),
            "rating_type": str(rating_type),
            "ro": ro,
            "games_rated": games_rated,
            "score": score,
            "average_opponent": average_opponent,
            "rp": rp,
            "n_over_400": 0,
            "k": 0,
            "we": None,
            "delta": None,
            "rc": None,
        }

        if ro > 0:
            row["we"] = round(
                sum(fide_expected_score(ro, rating_by_id[opp]) for opp, _earned in rated_games), 2
            )
            row["n_over_400"] = sum(
                1 for opp, _earned in rated_games if abs(ro - rating_by_id[opp]) > MAX_RATING_DIFF
            )
            row["k"] = fide_k_factor(
                ro,
                birth_year=_birth_year(player),
                tournament_year=tournament_year,
                k_override=player.get("k_factor"),
            )
            row["delta"] = round(row["k"] * (score - row["we"]), 2)
            row["rc"] = int(round(ro + row["delta"]))

        rows.append(row)

    rows.sort(key=lambda item: (-(int(item["ro"]) if item["ro"] else 0), str(item["name"]).casefold()))
    return rows
