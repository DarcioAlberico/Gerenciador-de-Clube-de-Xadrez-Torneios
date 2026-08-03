"""Helpers puros para historicos usados no emparceiramento."""

from __future__ import annotations

from typing import Any

from src.services.constants import REQUESTED_BYE_POINTS, WALKOVER_RESULTS


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


def team_float_histories(matches: list[dict[str, Any]]) -> dict[int, list[str]]:
    """Flutuacoes por equipe, na ordem das rodadas (PAR-04).

    O Suico por equipes penalizava float repetido no individual e nao aqui: a
    mesma equipe podia descer de grupo tres rodadas seguidas sem que o motor
    notasse. Os match points de cada confronto ja estao gravados, entao o
    historico sai deles — bye conta como downfloat quando pontua, igual ao
    individual.
    """
    histories: dict[int, list[str]] = {}
    scores: dict[int, float] = {}
    for match in sorted(matches, key=lambda item: int(item.get("round_number") or 0)):
        white_id = int(match["white_team_id"])
        black_id = int(match["black_team_id"]) if match.get("black_team_id") else None
        histories.setdefault(white_id, [])
        scores.setdefault(white_id, 0.0)
        white_points = float(match.get("white_match_points") or 0.0)

        if match.get("is_bye") or black_id is None:
            histories[white_id].append("bye")
            if white_points > 0:
                histories[white_id].append("down")
            scores[white_id] += white_points
            continue

        histories.setdefault(black_id, [])
        scores.setdefault(black_id, 0.0)
        if scores[white_id] < scores[black_id]:
            histories[white_id].append("up")
            histories[black_id].append("down")
        elif scores[white_id] > scores[black_id]:
            histories[white_id].append("down")
            histories[black_id].append("up")
        else:
            histories[white_id].append("=")
            histories[black_id].append("=")
        scores[white_id] += white_points
        scores[black_id] += float(match.get("black_match_points") or 0.0)
    return histories


def played_pairs(pairings: list[dict[str, Any]]) -> set[frozenset[int]]:
    """Pares que efetivamente JOGARAM entre si (regra de nao-repeticao).

    Partidas por W.O./forfait (``WALKOVER_RESULTS``) sao ignoradas: pela FIDE
    C.04.2 (3.5) jogadores que foram pareados mas nao jogaram a partida PODEM
    voltar a se enfrentar. Assim a deteccao de ``opponent_repeat`` e o proprio
    motor ficam alinhados ao Gacrux e a regra vigente (rules 2026-02-01).
    """
    played: set[frozenset[int]] = set()
    for pairing in pairings:
        if pairing["is_bye"] or not pairing["black_player_id"]:
            continue
        if str(pairing.get("result") or "").strip().upper() in WALKOVER_RESULTS:
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
    """Sequencia de cores por jogador (W/B/BYE) para preferencia de cor.

    Partidas por W.O./forfait (``WALKOVER_RESULTS``) NAO entram na sequencia:
    pela FIDE C.04.2 (3.4) "only played games count" quando a sequencia de cores
    importa. Sem isso, a cor de um jogo nao jogado inflaria o saldo/streak e
    geraria violacao dura de cor (``hard_color``) onde o Gacrux nao ve nenhuma.
    """
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
            if str(pairing.get("result") or "").strip().upper() in WALKOVER_RESULTS:
                continue
            histories[white_id].append("W")
            histories[black_id].append("B")
    return histories


def float_histories(
    pairings: list[dict[str, Any]],
    players: list[dict[str, Any]],
    bye_points: float,
    result_points: dict[str, tuple[float, float]],
) -> dict[int, list[str]]:
    """Sequencia de flutuacoes por jogador (up/down/=/bye).

    Partida NAO JOGADA nao produz flutuacao por diferenca de pontos: quem pontuou
    sem jogar (W.O. a favor, bye que vale ponto) conta como DOWNFLOAT, e quem
    perdeu por W.O. nao conta nada. E a regra do motor FIDE — `compute_flt` do
    Gacrux compara os pontos so quando `played`, e no ramo "dutch" da `d` a quem
    ganhou ponto sem jogar (PAR-04).

    Antes, o W.O. entrava como flutuacao normal dos DOIS lados enquanto a cor e a
    nao-repeticao ja o excluiam: o mesmo jogo contava de tres jeitos diferentes.
    """
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
            ganhos = REQUESTED_BYE_POINTS.get(
                str(pairing.get("result") or "").strip().upper(), bye_points
            )
            # `bye` continua marcado a parte (a escolha do bye usa esta marca),
            # e o downfloat so entra quando o bye PONTUOU — bye de zero ponto nao
            # e flutuacao para ninguem.
            histories[white_id].append("bye")
            if ganhos > 0:
                histories[white_id].append("down")
            scores[white_id] += ganhos
            continue

        if black_id is None:
            continue
        histories.setdefault(black_id, [])
        scores.setdefault(black_id, 0.0)

        if str(pairing.get("result") or "").strip().upper() in WALKOVER_RESULTS:
            # Nao jogada: quem pontuou sem jogar conta como downfloat; o outro
            # lado nao flutua. Ver o docstring — e o ramo "dutch" do Gacrux.
            pontos = result_points.get(str(pairing.get("result") or "").strip())
            if pontos:
                brancas, pretas = pontos
                if brancas > pretas:
                    histories[white_id].append("down")
                elif pretas > brancas:
                    histories[black_id].append("down")
                scores[white_id] += brancas
                scores[black_id] += pretas
            continue

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
