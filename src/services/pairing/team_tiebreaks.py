"""Classificação e desempates de EQUIPES (spec §10, TBK-05).

Módulo puro: recebe as linhas já lidas do banco (confrontos fechados, resultados
de tabuleiro, ajustes do árbitro) e devolve a classificação ordenada. Não abre
conexão, não conhece a UI.

Os quatro critérios históricos (match points, game points, Buchholz sobre match
points e vitórias) conviviam com o individual em `tiebreaks.py`. A TBK-05 trouxe
os desempates que faltavam para representar um regulamento olímpico — Sonneborn-
Berger olímpico, confronto direto, Buchholz de game points e board count — e com
eles o domínio de equipes ganhou tamanho para morar sozinho.

Sobre o motor próprio: ele é LEGADO e não homologável desde a TBK-03. As
fórmulas daqui valem para jogos DISPUTADOS; o adversário virtual da FIDE (jogos
não disputados, byes) é implementado só no Gacrux, que é o motor padrão. Byes,
portanto, não entram no Buchholz, no SB nem no board count deste módulo.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.services.constants import RESULT_POINTS
from src.services.pairing.point_adjustments import AdjustmentTotal, adjustment_note
from src.services.pairing.tiebreak_criteria import (
    DEFAULT_TEAM_TIEBREAKS,
    TEAM_TIEBREAKS,
    criterion_param,
    dedup_codes,
    higher_is_better,
)


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _team_param(code: str, params: dict[str, Any], key: str) -> Any:
    return criterion_param(code, params, key, TEAM_TIEBREAKS)


# ---------------------------------------------------------------------------
# Tabuleiros (board count)
# ---------------------------------------------------------------------------


def fold_board_points(board_rows: list[dict[str, Any]] | None) -> dict[int, dict[int, float]]:
    """Linhas de tabuleiro → ``{team_id: {nº do tabuleiro: pontos}}``.

    Cada linha traz a equipe de QUEM JOGOU cada cor (`white_team_id` /
    `black_team_id` do jogador, não do confronto): tabuleiros pares têm as cores
    invertidas e um jogador pode ter sido substituído, então perguntar ao elenco
    é o que mantém a soma por tabuleiro igual à soma de game points do confronto.
    """
    points: dict[int, dict[int, float]] = {}
    for row in board_rows or []:
        result = str(row.get("result") or "")
        if result not in RESULT_POINTS:
            continue
        board = int(row.get("board_number") or 0)
        if board <= 0:
            continue
        white_points, black_points = RESULT_POINTS[result]
        for team_key, earned in (("white_team_id", white_points), ("black_team_id", black_points)):
            team_id = row.get(team_key)
            if team_id is None:
                continue
            por_tabuleiro = points.setdefault(int(team_id), {})
            por_tabuleiro[board] = round(por_tabuleiro.get(board, 0.0) + float(earned), 2)
    return points


def _board_count(team_stat: dict[str, Any]) -> float:
    """Soma do número do tabuleiro vezes os pontos nele obtidos.

    MENOR é melhor, e o critério só faz sentido depois dos game points: entre
    duas equipes com o mesmo total, ganha quem pontuou nos tabuleiros de cima.
    Isolado ele premiaria quem pontuou pouco — por isso o registro declara
    `higher_is_better=False` e nunca é o primeiro critério de um regulamento.
    """
    return round(
        sum(
            float(board) * float(points)
            for board, points in dict(team_stat.get("board_points") or {}).items()
        ),
        2,
    )


# ---------------------------------------------------------------------------
# Critérios sobre os confrontos
# ---------------------------------------------------------------------------


def _olympic_sonneborn_berger(
    team_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    cut_low: int = 0,
) -> float:
    """Σ (match points do adversário × game points feitos contra ele).

    É o Sonneborn-Berger dos regulamentos por equipes (`EMGSB` do Gacrux): a
    força do adversário conta em match points, e o peso é o placar do confronto
    em pontos de tabuleiro. O SB "de match points dos dois lados" (`SB`/`EMMSB`
    do Gacrux) é outro critério, e não é o que o regulamento olímpico pede.

    ``cut_low`` descarta os piores confrontos pela MESMA regra do Gacrux: menor
    pontuação do adversário primeiro, produto como desempate.
    """
    jogos = [
        {
            "score": float(stats[int(record["opponent_id"])]["match_points_raw"]),
            "value": float(stats[int(record["opponent_id"])]["match_points_raw"])
            * float(record["game_points"]),
        }
        for record in team_stat["match_results"]
        if record.get("opponent_id") and int(record["opponent_id"]) in stats
    ]
    for _ in range(max(0, int(cut_low))):
        if not jogos:
            break
        jogos.sort(key=lambda jogo: (jogo["score"], jogo["value"]))
        jogos = jogos[1:]
    return round(sum(jogo["value"] for jogo in jogos), 2)


def _buchholz_game_points(
    team_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> float:
    """Soma dos game points totais dos adversários enfrentados (`BH:GP`)."""
    return round(
        sum(
            float(stats[opponent_id]["game_points_raw"])
            for opponent_id in team_stat["opponents"]
            if opponent_id in stats
        ),
        2,
    )


def _tied_team_ids(team_stat: dict[str, Any], stats: dict[int, dict[str, Any]]) -> list[int]:
    """Quem está empatado em match points com esta equipe, ela incluída."""
    match_points = float(team_stat["match_points_raw"])
    return [
        int(other["team_id"])
        for other in stats.values()
        if float(other["match_points_raw"]) == match_points
    ]


def _direct_encounter_score(
    team_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
) -> float:
    """Match points obtidos contra as equipes empatadas.

    Vale a mesma condição do individual (TBK-03): só se aplica se TODAS as
    equipes empatadas se enfrentaram. Com três empatadas em que A jogou contra B
    e contra C mas B e C não se enfrentaram, "quem ganhou de quem" não é uma
    ordem. Zero para o grupo inteiro é neutro — decide o critério seguinte, que
    é o que a regra manda quando o confronto direto não pode ser usado.
    """
    grupo = _tied_team_ids(team_stat, stats)
    if len(grupo) < 2:
        return 0.0
    for team_id in grupo:
        adversarios = set(stats[team_id]["opponents"])
        if any(other != team_id and other not in adversarios for other in grupo):
            return 0.0
    empatadas = set(grupo)
    return round(
        sum(
            float(record["match_points"])
            for record in team_stat["match_results"]
            if record.get("opponent_id") and int(record["opponent_id"]) in empatadas
        ),
        2,
    )


def team_tiebreak_value(
    code: str,
    team_stat: dict[str, Any],
    stats: dict[int, dict[str, Any]],
    params: dict[str, Any] | None = None,
) -> float:
    """Valor de um critério de equipe, calculado sob demanda.

    Só os critérios que dependem de estrutura (confrontos, tabuleiros); os
    quatro históricos já vivem como campo do próprio `team_stat`.
    """
    params = params or {}
    if code == "sonneborn_berger":
        return _olympic_sonneborn_berger(
            team_stat, stats, int(_team_param(code, params, "cut_low") or 0)
        )
    if code == "buchholz_game_points":
        return _buchholz_game_points(team_stat, stats)
    if code == "direct_encounter":
        return _direct_encounter_score(team_stat, stats)
    if code == "board_count":
        return _board_count(team_stat)
    return 0.0


# ---------------------------------------------------------------------------
# Ordenação
# ---------------------------------------------------------------------------


def team_standing_value(item: dict[str, Any], criterion: str) -> float:
    """Valor EXIBIDO de um critério (o número que aparece na classificação)."""
    if criterion in TEAM_TIEBREAKS:
        return _as_float(item.get(criterion, 0.0))
    return _as_float(item.get("match_points", 0.0))


def team_ordering_value(item: dict[str, Any], criterion: str) -> float:
    """Valor ORDENÁVEL de um critério: sempre "maior é melhor".

    O board count é o único critério em que o número menor classifica melhor;
    invertê-lo aqui deixa quem ordena com uma única regra (`-valor`) em vez de
    uma exceção espalhada por cada chave de ordenação.
    """
    valor = team_standing_value(item, criterion)
    return valor if higher_is_better(criterion, TEAM_TIEBREAKS) else -valor


# Critérios que a tabela de classificação por equipes já mostra em coluna fixa.
_TEAM_COLUMNS_ALWAYS_SHOWN = ("match_points", "game_points", "wins", "buchholz")


def extra_team_columns(standings: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Critérios configurados que a tabela fixa não mostra: ``(código, rótulo)``.

    Um desempate que decide o campeonato e não aparece em lugar nenhum não é
    utilizável: o árbitro precisa mostrar o número quando alguém perguntar por
    que a ordem é aquela. A tabela nasceu com quatro colunas porque eram os
    quatro critérios que existiam (TBK-05); as demais entram pela sequência
    configurada, na ordem em que desempatam.
    """
    ordem = next((list(item.get("team_tiebreak_order") or []) for item in standings), [])
    return [
        (code, TEAM_TIEBREAKS[code].label)
        for code in ordem
        if code in TEAM_TIEBREAKS and code not in _TEAM_COLUMNS_ALWAYS_SHOWN
    ]


def _resolve_team_codes(
    settings: dict[str, Any],
    sequence: list[dict[str, Any]] | None,
) -> list[tuple[str, dict[str, Any]]]:
    if sequence:
        codes = [
            (item["code"], dict(item.get("params") or {}))
            for item in sequence
            if item.get("code") in TEAM_TIEBREAKS
        ]
        if codes:
            vistos: set[str] = set()
            unicos: list[tuple[str, dict[str, Any]]] = []
            for code, params in codes:
                if code not in vistos:
                    vistos.add(code)
                    unicos.append((code, params))
            return unicos
    primary = str(settings.get("team_standing_primary", "match_points") or "match_points")
    secondary = str(settings.get("team_standing_secondary", "game_points") or "game_points")
    return [
        (code, {})
        for code in dedup_codes([primary, secondary, "buchholz", "wins"])
        if code in TEAM_TIEBREAKS
    ]


_ADJUSTABLE_TEAM_CODES = ("match_points", "game_points")


def _apply_team_adjustments(
    stats: dict[int, dict[str, Any]],
    adjustments: Mapping[int, AdjustmentTotal] | None,
) -> None:
    """Soma os ajustes do árbitro aos pontos de cada equipe (TBK-01).

    Espelha `_apply_player_adjustments`, com as duas grandezas de equipe: match
    points e game points. Os desempates que medem a força dos adversários
    (Buchholz, SB) são calculados antes — mesma razão do individual: a
    penalidade é uma decisão sobre aquela equipe, não sobre quem a enfrentou.
    """
    adjustments = adjustments or {}
    for team_stat in stats.values():
        total = adjustments.get(int(team_stat["team_id"]))
        match_delta = float(total.match_points) if total else 0.0
        game_delta = float(total.game_points) if total else 0.0
        team_stat["adjustment_match_points"] = match_delta
        team_stat["adjustment_game_points"] = game_delta
        team_stat["adjustment_note"] = adjustment_note(total)
        if match_delta:
            team_stat["match_points"] = round(float(team_stat["match_points"]) + match_delta, 2)
        if game_delta:
            team_stat["game_points"] = round(float(team_stat["game_points"]) + game_delta, 2)


def _adjusted_team_prefix(
    codes: list[str],
    stats: dict[int, dict[str, Any]],
) -> list[str]:
    """Critérios que precisam ser reordenados por cima do rank do Gacrux.

    Sem ajuste no torneio, nenhum: o rank do motor continua sendo a ordem. Com
    ajuste, o prefixo vai até o ÚLTIMO critério que um ajuste pode mover (match
    points ou game points) — os critérios do meio entram com o valor do próprio
    Gacrux, então quando nada muda a ordem resultante é a dele. Do prefixo em
    diante o rank decide, que é onde ele continua valendo.
    """
    if not any(
        float(item.get("adjustment_match_points") or 0.0)
        or float(item.get("adjustment_game_points") or 0.0)
        for item in stats.values()
    ):
        return []
    last = max(
        (index for index, code in enumerate(codes) if code in _ADJUSTABLE_TEAM_CODES),
        default=-1,
    )
    return codes[: last + 1]


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------


def calculate_team_standings(
    settings: dict[str, Any],
    teams: list[dict[str, Any]],
    closed_matches: list[dict[str, Any]],
    sequence: list[dict[str, Any]] | None = None,
    gacrux_tiebreaks: dict[int, dict[str, Any]] | None = None,
    adjustments: Mapping[int, AdjustmentTotal] | None = None,
    board_results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = {}
    board_points = fold_board_points(board_results)
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
            # Um registro por confronto disputado, na ordem das rodadas: é o que
            # os critérios da TBK-05 precisam e que a soma de totais não guarda
            # (contra QUEM cada game point foi feito).
            "match_results": [],
            "board_points": dict(board_points.get(team_id, {})),
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
        white_game_points = float(match.get("white_game_points", 0.0) or 0.0)
        black_game_points = float(match.get("black_game_points", 0.0) or 0.0)
        stats[white_team_id]["match_points"] += white_match_points
        stats[black_team_id]["match_points"] += black_match_points
        stats[white_team_id]["game_points"] += white_game_points
        stats[black_team_id]["game_points"] += black_game_points
        stats[white_team_id]["matches"] += 1
        stats[black_team_id]["matches"] += 1
        stats[white_team_id]["opponents"].append(black_team_id)
        stats[black_team_id]["opponents"].append(white_team_id)
        round_number = int(match.get("round_number") or 0)
        stats[white_team_id]["match_results"].append({
            "round": round_number,
            "opponent_id": black_team_id,
            "match_points": white_match_points,
            "game_points": white_game_points,
        })
        stats[black_team_id]["match_results"].append({
            "round": round_number,
            "opponent_id": white_team_id,
            "match_points": black_match_points,
            "game_points": black_game_points,
        })

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
        # Totais NO TABULEIRO, antes de qualquer ajuste do árbitro: é o que os
        # critérios de força dos adversários usam (e o que o Gacrux enxerga,
        # já que ele não recebe a tabela de ajustes).
        team_stat["match_points_raw"] = team_stat["match_points"]
        team_stat["game_points_raw"] = team_stat["game_points"]

    for team_stat in stats.values():
        team_stat["buchholz"] = round(
            sum(
                float(stats[opponent_id]["match_points_raw"])
                for opponent_id in team_stat["opponents"]
                if opponent_id in stats
            ),
            2,
        )

    codes = _resolve_team_codes(settings, sequence)
    for team_stat in stats.values():
        for code, params in codes:
            if code in ("match_points", "game_points", "buchholz", "wins"):
                continue
            team_stat[code] = team_tiebreak_value(code, team_stat, stats, params)

    # Modo Gacrux: sobrescreve os valores canônicos de equipe pelos do motor FIDE
    # e segue o rank do Gacrux (mesma estratégia do individual; ver
    # calculate_player_standings).
    gacrux_tiebreaks = gacrux_tiebreaks or {}
    for team_stat in stats.values():
        gx = gacrux_tiebreaks.get(int(team_stat["team_id"]))
        gx_scores = gx.get("scores") if gx else None
        if gx:
            for code in TEAM_TIEBREAKS:
                if gx_scores and code in gx_scores:
                    team_stat[code] = gx_scores[code]
            team_stat["_gacrux_rank"] = int(gx.get("rank") or 0)

    _apply_team_adjustments(stats, adjustments)

    plain_codes = [code for code, _params in codes]
    if any("_gacrux_rank" in item for item in stats.values()):
        prefix = _adjusted_team_prefix(plain_codes, stats)
        ordered_stats = sorted(
            stats.values(),
            key=lambda item: tuple(-team_ordering_value(item, code) for code in prefix)
            + (int(item.get("_gacrux_rank") or 0), str(item["name"]).casefold()),
        )
    else:
        ordered_stats = sorted(
            stats.values(),
            key=lambda item: tuple(-team_ordering_value(item, code) for code in plain_codes)
            + (str(item["name"]).casefold(),),
        )
    for index, item in enumerate(ordered_stats, start=1):
        item["team_tiebreak_order"] = list(plain_codes)
        item["position"] = index
    return ordered_stats
