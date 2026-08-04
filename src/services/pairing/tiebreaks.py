"""Helpers puros de desempate INDIVIDUAL (spec §10).

Funções aqui não tocam o banco — recebem dicts já preparados pelo serviço
e devolvem estruturas explicáveis. PairingService delega para elas.

O que cada critério É (rótulo, fórmula, parâmetros) vive em
`tiebreak_criteria.py`; a classificação por equipes vive em `team_tiebreaks.py`.
Aqui só se calcula o individual.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.services.constants import (
    REQUESTED_BYE_POINTS,
    RESULT_POINTS,
    WALKOVER_RESULTS,
    player_full_name,
)
from src.services.fide_rating import fide_performance
from src.services.pairing.point_adjustments import AdjustmentTotal, adjustment_note
from src.services.pairing.tiebreak_criteria import (
    DEFAULT_PLAYER_TIEBREAKS,
    PLAYER_TIEBREAKS,
    criterion_param,
)


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_player_codes(sequence: list[dict[str, Any]] | None) -> list[tuple[str, dict[str, Any]]]:
    if sequence:
        return [(item["code"], item.get("params", {})) for item in sequence]
    return [(code, {}) for code in DEFAULT_PLAYER_TIEBREAKS]


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


def _tied_group_ids(player_stat: dict[str, Any], stats: dict[int, dict[str, Any]]) -> list[int]:
    """Quem está empatado em pontos com este jogador, ele incluído."""
    points = float(player_stat["points"])
    return [
        int(other["player_id"])
        for other in stats.values()
        if float(other["points"]) == points
    ]


def _direct_encounter_applies(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> bool:
    """O confronto direto só vale se TODOS os empatados se enfrentaram.

    É condição da FIDE, e não detalhe: com três empatados em que A jogou contra
    B e contra C mas B e C não se enfrentaram, "quem ganhou de quem" não é uma
    ordem — é um pedaço de uma. Antes o critério era aplicado assim mesmo, e
    somava só os jogos que existiam, o que produzia um número com aparência de
    resultado.
    """
    grupo = _tied_group_ids(player_stat, stats)
    if len(grupo) < 2:
        return False
    for player_id in grupo:
        adversarios = set(stats[player_id]["opponents"])
        if any(other != player_id and other not in adversarios for other in grupo):
            return False
    return True


def _direct_encounter_score(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> float:
    """Pontos feitos contra os empatados. ``0`` quando o critério não se aplica.

    Zero para todo o grupo é neutro: o desempate seguinte decide, que é o que a
    regra manda quando o confronto direto não pode ser usado.
    """
    if not _direct_encounter_applies(player_stat, stats):
        return 0.0
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
    threshold_percent: float = 50.0,
) -> float:
    """Pontos contra adversários acima do limiar (padrão FIDE: 50%).

    O divisor é o total de rodadas **jogadas**, e é assim de propósito: é o que
    o Gacrux usa (`compute_koya`: `maxgames = rounds`). A auditoria pedia trocar
    pelas rodadas configuradas do torneio — medido, isso afastaria os dois
    motores. Ver `tests/test_core_tbk03.py::KoyaParidadeTest`.
    """
    threshold = (float(threshold_percent) / 100.0) * float(rounds_total or 0)
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


# Critério de desempate -> campo canônico em player_stat. Usado para sobrescrever
# os valores históricos pelos do motor FIDE (Gacrux) quando ele é o motor ativo,
# mantendo intacto o restante do contrato de saída da classificação.
_CODE_TO_CANONICAL_FIELD: dict[str, str] = {
    "buchholz": "buchholz",
    "buchholz_median": "buchholz_median",
    "sonneborn_berger": "sonneborn_berger",
    "wins": "wins",
    "performance": "performance",
    "cumulative": "cumulative",
}


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
        return _buchholz_with_cut(
            player_stat,
            stats,
            int(criterion_param(code, params, "cut_low")),
            int(criterion_param(code, params, "cut_high")),
            str(criterion_param(code, params, "unplayed")),
        )
    if code == "aro":
        return _average_rating_opponents(player_stat, stats, cut=0)
    if code == "aroc":
        return _average_rating_opponents(
            player_stat, stats, cut=int(criterion_param(code, params, "cut"))
        )
    if code == "direct_encounter":
        return _direct_encounter_score(player_stat, stats)
    if code == "cumulative":
        return float(player_stat.get("cumulative", 0.0) or 0.0)
    if code == "cumulative_opp":
        return float(player_stat.get("cumulative_opp", 0.0) or 0.0)
    if code == "koya":
        return _koya_score(
            player_stat, stats, rounds_total, criterion_param(code, params, "threshold")
        )
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
        "formula": "Media de rating dos adversarios + dp da tabela FIDE (regra dos 400).",
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
    # Tabela oficial FIDE (percentual p -> dp) + regra dos 400, reaproveitando
    # fide_performance — a MESMA fonte usada pelo relatório de rating e pelas
    # normas (fide_rating.py) e equivalente ao TPR do motor Gacrux. Antes daqui
    # usava-se uma aproximação logarítmica, que divergia da FIDE na faixa média.
    return fide_performance(average_rating, score, games)


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

    Quando o motor FIDE (Gacrux) já forneceu o ranking (`_gacrux_rank` presente),
    ele é a fonte de verdade: o cid/SNo que o Gacrux usa para desempatar empates
    finais embute a ordem rating→nome, então basta ordenar por esse rank (com
    rating/nome como critério técnico final defensivo).

    Exceção: quando o árbitro lançou ajuste de pontos (TBK-01), o rank do Gacrux
    está desatualizado — o motor não conhece a tabela `point_adjustments`. Aí os
    pontos **já ajustados** entram na frente e o rank do motor vira o desempate
    de quem ficou com a mesma soma. Sem ajuste no torneio a chave é a de antes,
    byte a byte: PTS é o primeiro critério do Gacrux, então acrescentar os
    pontos à frente não reordenaria nada — mas também não se paga o risco.
    """
    if any("_gacrux_rank" in item for item in stats.values()):
        adjusted = any(float(item.get("adjustment_points") or 0.0) for item in stats.values())

        def gacrux_key(item: dict[str, Any]) -> tuple[Any, ...]:
            head = (-float(item.get("points", 0.0) or 0.0),) if adjusted else ()
            return head + (
                int(item.get("_gacrux_rank") or 0),
                -float(item.get("rating", 0) or 0),
                str(item.get("name", "")).casefold(),
            )

        ordered_stats = sorted(stats.values(), key=gacrux_key)
        for index, item in enumerate(ordered_stats, start=1):
            item["position"] = index
        return ordered_stats

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
    gacrux_tiebreaks: dict[int, dict[str, Any]] | None = None,
    adjustments: Mapping[int, AdjustmentTotal] | None = None,
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
            # Todas as categorias premiáveis (ORG-01). A classificação por
            # categoria agrupava só pela principal, e por isso a jogadora
            # Sub-10 nunca aparecia numa classificação feminina.
            "categories": player.get("categories", ""),
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
        # `wins` = WON da FIDE: vitórias **no tabuleiro**. W.O. é partida pareada
        # e não jogada, então não conta — nem aqui nem no Gacrux, que exige
        # `played and opponent > 0`. Antes contava, e por isso trocar de motor no
        # meio do torneio reordenava os empatados (TBK-03).
        if result not in WALKOVER_RESULTS:
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

    # Escalares ordenáveis dos critérios ativos + componentes explicáveis.
    #
    # No modo Gacrux (`gacrux_tiebreaks` informado), os valores FIDE substituem
    # os campos canônicos (buchholz, SB, performance…) e os tiebreak_values dos
    # critérios da sequência; quem não tem equivalente no Gacrux (ex.:
    # cumulative_opp) mantém o cálculo próprio. A ordenação passa a seguir o rank
    # do Gacrux (ver order_player_standings).
    gacrux_tiebreaks = gacrux_tiebreaks or {}
    for player_stat in stats.values():
        gx = gacrux_tiebreaks.get(int(player_stat["player_id"]))
        gx_scores = gx.get("scores") if gx else None
        if gx:
            for code, field in _CODE_TO_CANONICAL_FIELD.items():
                if gx_scores and code in gx_scores:
                    player_stat[field] = gx_scores[code]
            player_stat["_gacrux_rank"] = int(gx.get("rank") or 0)

        player_stat["tiebreak_values"] = {
            code: (
                gx_scores[code]
                if gx_scores and code in gx_scores
                else player_tiebreak_value(code, player_stat, stats, params, rounds_total)
            )
            for code, params in codes
        }
        player_stat["tiebreak_order"] = [code for code, _params in codes]
        player_stat["tiebreak_components"] = player_tiebreak_components(
            player_stat, stats, codes=codes, rounds_total=rounds_total,
            value_override=gx_scores,
        )

    _apply_player_adjustments(stats, adjustments)
    return order_player_standings(stats, sequence)


def _apply_player_adjustments(
    stats: dict[int, dict[str, Any]],
    adjustments: Mapping[int, AdjustmentTotal] | None,
) -> None:
    """Soma os ajustes do árbitro ao total de cada jogador (TBK-01).

    Roda **depois** dos desempates de propósito, e a razão é de mérito: a
    penalidade é uma decisão sobre aquele jogador, não sobre a força de quem o
    enfrentou. Buchholz, Sonneborn-Berger e performance continuam medindo
    pontos conquistados no tabuleiro — que é também o que o Gacrux mede, já que
    ele não recebe a tabela de ajustes. Só a soma que ordena muda.

    Todo jogador recebe os campos (zerados quando não há ajuste): a tela e os
    relatórios leem sem `get` defensivo e sem saber se o torneio tem ajustes.
    """
    adjustments = adjustments or {}
    for player_stat in stats.values():
        total = adjustments.get(int(player_stat["player_id"]))
        delta = float(total.game_points) if total else 0.0
        player_stat["adjustment_points"] = delta
        player_stat["adjustment_note"] = adjustment_note(total)
        if not delta:
            continue
        player_stat["points"] = round(float(player_stat["points"]) + delta, 2)
        # Sequência exótica que declare `points` como critério: o valor cacheado
        # em tiebreak_values é anterior ao ajuste e ordenaria pelo número velho.
        values = player_stat.get("tiebreak_values")
        if isinstance(values, dict) and "points" in values:
            values["points"] = player_stat["points"]


def player_tiebreak_components(
    player_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    codes: list[tuple[str, dict[str, Any]]] | None = None,
    rounds_total: int = 0,
    value_override: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Componentes brutos dos critérios de desempate de um jogador.

    Sempre retorna os seis critérios históricos (buchholz, buchholz_median,
    sonneborn_berger, direct_encounter, wins, performance) para compatibilidade
    com relatórios/exportações existentes. Quando `codes` é informado, acrescenta
    um componente explicável para cada critério ativo adicional (Buchholz Cut,
    progressivo, Koya, ARO, etc.).

    `value_override` (modo Gacrux) substitui o `value`/`total` exibido de cada
    critério pelo valor do motor FIDE — a fonte de verdade — preservando os
    detalhes (listas de adversários) do cálculo próprio apenas como ilustração.
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
            value = (value_override or {}).get(code)
            if value is None:
                value = player_tiebreak_value(code, player_stat, stats, params, rounds_total)
            criterion = PLAYER_TIEBREAKS[code]
            components[code] = {
                "label": criterion.label,
                "value": value,
                "formula": criterion.formula,
                "total": value,
            }

    # Modo Gacrux: o número exibido de cada critério é o do motor FIDE. Cobre os
    # critérios calculados localmente (ex.: confronto direto) cujo valor não vem
    # de um campo canônico já sobrescrito.
    if value_override:
        for code, override_value in value_override.items():
            if code in components:
                components[code]["value"] = override_value
                components[code]["total"] = override_value

    return components
