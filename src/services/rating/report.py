"""Linhas do relatório de variação de rating (puro).

Recebe jogadores e emparceiramentos como mapas e devolve Ro, K, n, W, We, ΔElo,
Rc e Rp — agora conforme o REGULAMENTO escolhido (base + ritmo), e não mais com
os números da FIDE standard costurados no código. É **estimativa de apoio ao
árbitro**, não homologação: a federação continua sendo a autoridade do rating.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.constants import RESULT_POINTS, player_full_name
from src.services.rating.initial import initial_rating
from src.services.rating.kfactor import k_factor
from src.services.rating.profiles import FIDE, regulation_for
from src.services.rating.regulation import RatingRegulation
from src.services.rating.tables import MAX_RATING_DIFF, fide_expected_score, fide_performance
from src.services.results_registry import RATED_RESULTS as _RATED_RESULTS
from src.services.time_control import BLITZ, RAPID, STANDARD

# Coluna de rating por base e ritmo, em ordem de preferência. A primeira que
# tiver valor vence; a origem entra na linha para o árbitro saber o que foi
# usado — rápido sem lista de rápidas cairia no standard em silêncio, e um
# delta calculado contra a lista errada parece certo.
_RATING_COLUMNS: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    (FIDE, STANDARD): (("international_rating", "standard"), ("rating", "geral")),
    (FIDE, RAPID): (
        ("rapid_rating", "rápido"),
        ("international_rating", "standard (sem rating rápido)"),
        ("rating", "geral"),
    ),
    (FIDE, BLITZ): (
        ("blitz_rating", "blitz"),
        ("international_rating", "standard (sem rating blitz)"),
        ("rating", "geral"),
    ),
}
_NATIONAL_COLUMNS = (("national_rating", "nacional"), ("rating", "geral"))


def player_rating_for(player: Mapping[str, Any], base: str, speed: str = STANDARD) -> tuple[int, str]:
    """`(rating, origem)` do jogador na base e no ritmo pedidos."""
    key = (str(base or FIDE).strip().lower(), str(speed or STANDARD).strip().lower())
    columns = _RATING_COLUMNS.get(key)
    if columns is None:
        columns = _NATIONAL_COLUMNS if key[0] != FIDE else _RATING_COLUMNS[(FIDE, STANDARD)]
    for column, origin in columns:
        value = int(player.get(column) or 0)
        if value > 0:
            return value, origin
    return 0, ""


def player_rating_for_type(player: Mapping[str, Any], rating_type: str) -> int:
    """Compatibilidade: rating na base, sempre no ritmo standard."""
    return player_rating_for(player, rating_type, STANDARD)[0]


def _birth_year(player: Mapping[str, Any]) -> int | None:
    raw = str(player.get("birth_date") or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return None


def _games_played(player: Mapping[str, Any]) -> int | None:
    """Partidas já ratadas do jogador; `None` quando ninguém informou.

    Zero é "desconhecido", não "estreante": a coluna nasce vazia para todo mundo,
    e tratar isso como estreia daria K = 40 ao plantel inteiro.
    """
    value = int(player.get("games_played") or 0)
    return value if value > 0 else None


def collect_rated_games(
    players_by_id: Mapping[int, Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
) -> dict[int, list[tuple[int, float]]]:
    """Partidas rateáveis por jogador: `(adversário, pontos)`."""
    games: dict[int, list[tuple[int, float]]] = {pid: [] for pid in players_by_id}
    for pairing in closed_pairings:
        if pairing.get("is_bye"):
            continue
        white_id = pairing.get("white_player_id")
        black_id = pairing.get("black_player_id")
        result = pairing.get("result")
        if white_id not in players_by_id or not black_id or black_id not in players_by_id:
            continue
        if result not in _RATED_RESULTS:
            continue  # WO/forfait/bye/sem resultado nao contam para rating
        white_points, black_points = RESULT_POINTS[result]
        games[int(white_id)].append((int(black_id), white_points))
        games[int(black_id)].append((int(white_id), black_points))
    return games


def build_report_rows(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = FIDE,
    *,
    tournament_year: int | None = None,
    speed: str = STANDARD,
    regulation: RatingRegulation | None = None,
) -> list[dict[str, Any]]:
    """Linhas do relatório de variação de rating no regulamento pedido."""
    rules = regulation or regulation_for(rating_type, speed)
    by_id: dict[int, Mapping[str, Any]] = {int(player["id"]): player for player in players}
    rating_by_id: dict[int, int] = {}
    source_by_id: dict[int, str] = {}
    for pid, player in by_id.items():
        rating_by_id[pid], source_by_id[pid] = player_rating_for(player, rating_type, speed)

    games = collect_rated_games(by_id, closed_pairings)

    rows: list[dict[str, Any]] = []
    for pid, player in by_id.items():
        ro = rating_by_id[pid]
        rated_games = [(opp, earned) for opp, earned in games[pid] if rating_by_id.get(opp, 0) > 0]
        games_rated = len(rated_games)
        if games_rated == 0:
            continue

        score = round(sum(earned for _opp, earned in rated_games), 2)
        opponent_ratings = [rating_by_id[opp] for opp, _earned in rated_games]
        average_opponent = round(sum(opponent_ratings) / games_rated, 1)
        rp = fide_performance(average_opponent, score, games_rated)

        row: dict[str, Any] = {
            "player_id": pid,
            "name": player_full_name(player),
            "rating_type": str(rating_type),
            "speed": str(speed),
            "ro": ro,
            "rating_source": source_by_id[pid],
            "games_played": player.get("games_played") or 0,
            "games_rated": games_rated,
            "score": score,
            "average_opponent": average_opponent,
            "rp": rp,
            "n_over_400": 0,
            "k": 0,
            "k_reason": "",
            "we": None,
            "delta": None,
            "rc": None,
            "rc_calculated": None,
            "below_floor": False,
            "initial_rating": None,
            "initial_reason": "",
        }

        if ro > 0:
            row["we"] = round(
                sum(fide_expected_score(ro, rating_by_id[opp]) for opp, _earned in rated_games), 2
            )
            row["n_over_400"] = sum(
                1 for opp, _earned in rated_games if abs(ro - rating_by_id[opp]) > MAX_RATING_DIFF
            )
            row["k"], row["k_reason"] = k_factor(
                rules,
                ro,
                games_played=_games_played(player),
                birth_year=_birth_year(player),
                tournament_year=tournament_year,
                k_override=player.get("k_factor"),
                games=games_rated,
            )
            row["delta"] = round(row["k"] * (score - row["we"]), 2)
            calculated = int(round(ro + row["delta"]))
            row["rc_calculated"] = calculated
            # O piso é aplicado ao valor publicado (e sinalizado), em vez de
            # deixar sair um rating que a federação não publicaria.
            row["rc"] = max(calculated, int(rules.rating_floor or 0))
            row["below_floor"] = calculated < int(rules.rating_floor or 0)
        else:
            estimate = initial_rating(rules, opponent_ratings, score)
            row["initial_rating"] = estimate.rating if estimate.publishable else None
            row["initial_reason"] = estimate.reason

        rows.append(row)

    rows.sort(key=lambda item: (-(int(item["ro"]) if item["ro"] else 0), str(item["name"]).casefold()))
    return rows
