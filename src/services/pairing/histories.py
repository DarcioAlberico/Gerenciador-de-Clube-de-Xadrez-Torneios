"""Helpers puros para historicos usados no emparceiramento."""

from __future__ import annotations

from typing import Any, Mapping

from src.services.constants import REQUESTED_BYE_POINTS, RESULT_POINTS, WALKOVER_RESULTS


TeamBoards = Mapping[int, list[dict[str, Any]]]


def team_match_unplayed(match: Mapping[str, Any], boards: list[Mapping[str, Any]]) -> bool:
    """Confronto de equipes que NÃO foi jogado: todos os tabuleiros por W.O. (EQ-03).

    A unidade e o confronto: só o confronto INTEIRO sem jogo (W.O. em todos os
    tabuleiros, inclusive a dupla ausência) deixa de contar como confronto,
    como cor e como flutuação. W.O. parcial e confronto jogado. E a mesma regra
    que o TRF25 usa para o 330 e o indicador do 802 — uma regra, um lugar.
    """
    if match.get("is_bye") or not match.get("black_team_id"):
        return False
    resultados = [str(board.get("result") or "").strip().upper() for board in boards]
    return bool(resultados) and all(resultado in WALKOVER_RESULTS for resultado in resultados)


def _team_unplayed(match: Mapping[str, Any], boards_by_match: TeamBoards | None) -> bool:
    if not boards_by_match:
        return False
    return team_match_unplayed(match, boards_by_match.get(int(match.get("id") or 0), []))


def _team_forfeit_winner(match: Mapping[str, Any]) -> int | None:
    """Quem pontuou sem jogar num confronto inteiro por W.O. (None: ninguem)."""
    white_points = float(match.get("white_match_points") or 0.0)
    black_points = float(match.get("black_match_points") or 0.0)
    if white_points > black_points:
        return int(match["white_team_id"])
    if black_points > white_points:
        return int(match["black_team_id"])
    return None


def team_played_pairs(
    matches: list[dict[str, Any]],
    boards_by_match: TeamBoards | None = None,
) -> set[frozenset[int]]:
    """Pares de equipes que JOGARAM. Confronto inteiro por W.O. pode se repetir."""
    played: set[frozenset[int]] = set()
    for match in matches:
        if match["is_bye"] or not match["black_team_id"]:
            continue
        if _team_unplayed(match, boards_by_match):
            continue
        played.add(frozenset((int(match["white_team_id"]), int(match["black_team_id"]))))
    return played


def team_bye_ids(
    matches: list[dict[str, Any]],
    boards_by_match: TeamBoards | None = None,
) -> set[int]:
    """Quem não recebe mais o bye alocado (C.04.6 [C2], EQ-04 e EQ-05).

    Quem já teve o bye alocado ou o bye de ponto cheio (F) e quem VENCEU um
    confronto inteiro por W.O. — pontuou sem jogar, como no individual
    (RGS-18). Bye solicitado H ou Z não bloqueia: a mesma regra do individual
    (`_blocks_pairing_allocated_bye`), uma regra, um lugar.
    """
    blocked = {
        int(match["white_team_id"])
        for match in matches
        if match["is_bye"] and _blocks_pairing_allocated_bye(match.get("result"))
    }
    for match in matches:
        if _team_unplayed(match, boards_by_match):
            winner = _team_forfeit_winner(match)
            if winner is not None:
                blocked.add(winner)
    return blocked


def team_color_histories(
    matches: list[dict[str, Any]],
    boards_by_match: TeamBoards | None = None,
) -> dict[int, list[str]]:
    histories: dict[int, list[str]] = {}
    for match in matches:
        white_team_id = int(match["white_team_id"])
        black_team_id = int(match["black_team_id"]) if match["black_team_id"] else None
        histories.setdefault(white_team_id, [])
        if match["is_bye"]:
            histories[white_team_id].append("BYE")
            continue
        if black_team_id:
            histories.setdefault(black_team_id, [])
        if _team_unplayed(match, boards_by_match):
            continue  # W.O. não conta como cor (EQ-03)
        histories[white_team_id].append("W")
        if black_team_id:
            histories[black_team_id].append("B")
    return histories


def team_float_histories(
    matches: list[dict[str, Any]],
    boards_by_match: TeamBoards | None = None,
) -> dict[int, list[str]]:
    """Flutuações por equipe, na ordem das rodadas (PAR-04).

    O Suíço por equipes penalizava float repetido no individual e não aqui: a
    mesma equipe podia descer de grupo três rodadas seguidas sem que o motor
    notasse. Os match points de cada confronto já estão gravados, então o
    histórico sai deles — bye conta como downfloat quando pontua, igual ao
    individual. Confronto inteiro por W.O. (EQ-03): quem pontuou sem jogar
    conta como downfloat e o outro lado não flutua, como no individual.
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
        if _team_unplayed(match, boards_by_match):
            winner = _team_forfeit_winner(match)
            if winner is not None:
                histories[winner].append("down")
        elif scores[white_id] < scores[black_id]:
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
    """Pares que efetivamente JOGARAM entre si (regra de não-repeticao).

    Partidas por W.O./forfait (``WALKOVER_RESULTS``) são ignoradas: pela FIDE
    C.04.2 (3.5) jogadores que foram pareados mas não jogaram a partida PODEM
    voltar a se enfrentar. Assim a deteccao de ``opponent_repeat`` e o próprio
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
    """Quem NÃO pode mais receber o PAB (FIDE C.04.1, critério absoluto).

    "Um participante que já recebeu um PAB, ou já marcou, sem jogar, os pontos
    de uma vitória, não recebe o PAB" — o PAB, o bye de ponto inteiro (`F`) e
    a VITÓRIA POR W.O. (RGS-18). O W.O. a favor ficava de fora: o motor reserva
    podia dar o PAB a quem já tinha ganho um ponto sem jogar.
    """
    blocked: set[int] = set()
    for pairing in pairings:
        if pairing["is_bye"]:
            if _blocks_pairing_allocated_bye(pairing.get("result")):
                blocked.add(pairing["white_player_id"])
            continue
        winner = _forfeit_winner(pairing)
        if winner is not None:
            blocked.add(winner)
    return blocked


def _forfeit_winner(pairing: dict[str, Any]) -> int | None:
    """Quem venceu por W.O. nesta mesa (None se nao foi W.O. com vencedor)."""
    result = str(pairing.get("result") or "").strip().upper()
    if result not in WALKOVER_RESULTS or not pairing.get("black_player_id"):
        return None
    white_points, black_points = RESULT_POINTS.get(result, (0.0, 0.0))
    if white_points > black_points:
        return pairing["white_player_id"]
    if black_points > white_points:
        return pairing["black_player_id"]
    return None


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
    """Sequência de cores por jogador (W/B/BYE) para preferência de cor.

    Partidas por W.O./forfait (``WALKOVER_RESULTS``) NÃO entram na sequência:
    pela FIDE C.04.2 (3.4) "only played games count" quando a sequência de cores
    importa. Sem isso, a cor de um jogo não jogado inflaria o saldo/streak e
    geraria violação dura de cor (``hard_color``) onde o Gacrux não vê nenhuma.
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
    """Sequência de flutuações por jogador (up/down/=/bye).

    Partida NÃO JOGADA não produz flutuação por diferença de pontos: quem pontuou
    sem jogar (W.O. a favor, bye que vale ponto) conta como DOWNFLOAT, e quem
    perdeu por W.O. não conta nada. E a regra do motor FIDE — `compute_flt` do
    Gacrux compara os pontos só quando `played`, e no ramo "dutch" da `d` a quem
    ganhou ponto sem jogar (PAR-04).

    Antes, o W.O. entrava como flutuação normal dos DOIS lados enquanto a cor e a
    não-repeticao já o excluíam: o mesmo jogo contava de três jeitos diferentes.
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
            # e o downfloat só entra quando o bye PONTUOU — bye de zero ponto não
            # e flutuação para ninguém.
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
            # Não jogada: quem pontuou sem jogar conta como downfloat; o outro
            # lado não flutua. Ver o docstring — e o ramo "dutch" do Gacrux.
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
