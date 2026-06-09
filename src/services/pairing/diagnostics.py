"""Diagnosticos puros para qualidade de emparceiramento individual."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.services.pairing.constraints import color_hard_violation, is_color_valid_fide


AbsoluteQuality = tuple[int, int, int]


def pairing_diagnostics(
    pairings: list[dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_player_ids: set[int],
    *,
    players: list[dict[str, Any]] | None = None,
    standings: dict[int, dict[str, Any]] | None = None,
    max_exact_players: int = 17,
) -> list[dict[str, Any]]:
    """Retorna alertas sobre repeticao, bye repetido e violacao dura de cor.

    Quando o campo cabe na busca exata, cada alerta recebe ``avoidable``:
    True quando havia pareamento alternativo com menos violacoes absolutas do
    mesmo tipo, False quando a violacao era inevitavel pelo historico atual.
    Em campos maiores o valor fica None, pois a prova exata seria cara demais.
    """
    players_by_id = {int(player["id"]): player for player in players or []}
    current_quality = _current_absolute_quality(pairings, histories, played_pairs, bye_player_ids)
    active_ids = _active_player_ids(pairings, players)
    bye_candidate_ids = _bye_candidate_ids(active_ids, standings, bye_player_ids)
    best_quality = (
        _best_absolute_quality(active_ids, histories, played_pairs, bye_player_ids, bye_candidate_ids)
        if any(current_quality) and active_ids and len(active_ids) <= max_exact_players
        else None
    )

    diagnostics: list[dict[str, Any]] = []
    for pairing in pairings:
        white_id = _optional_int(pairing.get("white_player_id"))
        black_id = _optional_int(pairing.get("black_player_id"))
        board_number = _optional_int(pairing.get("board_number")) or 0
        pairing_id = _optional_int(pairing.get("id"))
        if white_id is None:
            continue

        if pairing.get("is_bye"):
            if white_id in bye_player_ids:
                diagnostics.append(
                    _diagnostic(
                        kind="bye_repeat",
                        board_number=board_number,
                        pairing_id=pairing_id,
                        player_ids=[white_id],
                        title="Bye repetido",
                        detail=(
                            f"{_player_label(white_id, players_by_id)} ja tinha recebido bye; "
                            f"{_avoidability_text(_avoidable(current_quality, best_quality, 0))}."
                        ),
                        avoidable=_avoidable(current_quality, best_quality, 0),
                        current_quality=current_quality,
                        best_quality=best_quality,
                    )
                )
            continue

        if black_id is None:
            continue

        if frozenset((white_id, black_id)) in played_pairs:
            diagnostics.append(
                _diagnostic(
                    kind="opponent_repeat",
                    board_number=board_number,
                    pairing_id=pairing_id,
                    player_ids=[white_id, black_id],
                    title="Confronto repetido",
                    detail=(
                        f"{_player_label(white_id, players_by_id)} x "
                        f"{_player_label(black_id, players_by_id)} ja ocorreu; "
                        f"{_avoidability_text(_avoidable(current_quality, best_quality, 1))}."
                    ),
                    avoidable=_avoidable(current_quality, best_quality, 1),
                    current_quality=current_quality,
                    best_quality=best_quality,
                )
            )

        for player_id, color in ((white_id, "W"), (black_id, "B")):
            if is_color_valid_fide(player_id, color, histories):
                continue
            diagnostics.append(
                _diagnostic(
                    kind="hard_color",
                    board_number=board_number,
                    pairing_id=pairing_id,
                    player_ids=[player_id],
                    title="Violacao dura de cor",
                    detail=(
                        f"{_player_label(player_id, players_by_id)} receberia "
                        f"{_color_name(color)}; {_hard_color_reason(player_id, color, histories)}. "
                        f"{_avoidability_text(_avoidable(current_quality, best_quality, 2))}."
                    ),
                    avoidable=_avoidable(current_quality, best_quality, 2),
                    current_quality=current_quality,
                    best_quality=best_quality,
                )
            )

    diagnostics.sort(key=lambda item: (int(item.get("board_number") or 0), str(item.get("kind") or "")))
    return diagnostics


def _diagnostic(
    *,
    kind: str,
    board_number: int,
    pairing_id: int | None,
    player_ids: list[int],
    title: str,
    detail: str,
    avoidable: bool | None,
    current_quality: AbsoluteQuality,
    best_quality: AbsoluteQuality | None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "severity": "decision" if avoidable is True else "attention",
        "board_number": board_number,
        "pairing_id": pairing_id,
        "player_ids": player_ids,
        "title": title,
        "detail": detail,
        "avoidable": avoidable,
        "current_quality": {
            "bye_repeat": current_quality[0],
            "opponent_repeat": current_quality[1],
            "hard_color": current_quality[2],
        },
        "best_quality": None
        if best_quality is None
        else {
            "bye_repeat": best_quality[0],
            "opponent_repeat": best_quality[1],
            "hard_color": best_quality[2],
        },
    }


def _current_absolute_quality(
    pairings: list[dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_player_ids: set[int],
) -> AbsoluteQuality:
    bye_repeats = 0
    repeats = 0
    hard_colors = 0
    for pairing in pairings:
        white_id = _optional_int(pairing.get("white_player_id"))
        black_id = _optional_int(pairing.get("black_player_id"))
        if white_id is None:
            continue
        if pairing.get("is_bye"):
            bye_repeats += 1 if white_id in bye_player_ids else 0
            continue
        if black_id is None:
            continue
        repeats += 1 if frozenset((white_id, black_id)) in played_pairs else 0
        hard_colors += color_hard_violation(white_id, "W", histories)
        hard_colors += color_hard_violation(black_id, "B", histories)
    return bye_repeats, repeats, hard_colors


def _best_absolute_quality(
    player_ids: tuple[int, ...],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_player_ids: set[int],
    bye_candidate_ids: set[int] | None,
) -> AbsoluteQuality:
    ids = tuple(sorted(set(player_ids)))
    full_mask = (1 << len(ids)) - 1
    inf: AbsoluteQuality = (1_000_000, 1_000_000, 1_000_000)

    @lru_cache(maxsize=None)
    def solve(mask: int, bye_used: bool) -> AbsoluteQuality:
        if mask == 0:
            return (0, 0, 0)

        remaining_count = mask.bit_count()
        best = inf
        if remaining_count % 2 == 1:
            if bye_used:
                return inf
            rest = mask
            while rest:
                bit = rest & -rest
                index = bit.bit_length() - 1
                player_id = ids[index]
                if bye_candidate_ids is not None and player_id not in bye_candidate_ids:
                    rest ^= bit
                    continue
                child = solve(mask ^ bit, True)
                candidate = (
                    child[0] + (1 if player_id in bye_player_ids else 0),
                    child[1],
                    child[2],
                )
                best = min(best, candidate)
                rest ^= bit
            return best

        first_bit = mask & -mask
        first_index = first_bit.bit_length() - 1
        first_player_id = ids[first_index]
        rest = mask ^ first_bit
        candidate_bits = rest
        while candidate_bits:
            bit = candidate_bits & -candidate_bits
            opponent_index = bit.bit_length() - 1
            opponent_id = ids[opponent_index]
            child = solve(rest ^ bit, bye_used)
            candidate = (
                child[0],
                child[1] + (1 if frozenset((first_player_id, opponent_id)) in played_pairs else 0),
                child[2] + _minimal_pair_hard_color(first_player_id, opponent_id, histories),
            )
            best = min(best, candidate)
            candidate_bits ^= bit
        return best

    return solve(full_mask, False)


def _bye_candidate_ids(
    player_ids: tuple[int, ...],
    standings: dict[int, dict[str, Any]] | None,
    bye_player_ids: set[int],
) -> set[int] | None:
    if len(player_ids) % 2 == 0 or standings is None:
        return None
    candidates = [player_id for player_id in player_ids if player_id not in bye_player_ids]
    if not candidates:
        candidates = list(player_ids)
    min_score = min(
        float(standings.get(player_id, {}).get("points", 0.0) or 0.0)
        for player_id in candidates
    )
    return {
        player_id
        for player_id in candidates
        if float(standings.get(player_id, {}).get("points", 0.0) or 0.0) == min_score
    }


def _minimal_pair_hard_color(
    player_id: int,
    opponent_id: int,
    histories: dict[int, list[str]],
) -> int:
    first = color_hard_violation(player_id, "W", histories) + color_hard_violation(
        opponent_id, "B", histories
    )
    second = color_hard_violation(player_id, "B", histories) + color_hard_violation(
        opponent_id, "W", histories
    )
    return min(first, second)


def _active_player_ids(
    pairings: list[dict[str, Any]],
    players: list[dict[str, Any]] | None,
) -> tuple[int, ...]:
    if players is not None:
        return tuple(int(player["id"]) for player in players)
    ids: list[int] = []
    for pairing in pairings:
        white_id = _optional_int(pairing.get("white_player_id"))
        black_id = _optional_int(pairing.get("black_player_id"))
        if white_id is not None:
            ids.append(white_id)
        if black_id is not None:
            ids.append(black_id)
    return tuple(ids)


def _avoidable(
    current_quality: AbsoluteQuality,
    best_quality: AbsoluteQuality | None,
    index: int,
) -> bool | None:
    if best_quality is None:
        return None
    return current_quality[index] > best_quality[index]


def _avoidability_text(avoidable: bool | None) -> str:
    if avoidable is True:
        return "a busca exata encontrou alternativa melhor"
    if avoidable is False:
        return "a busca exata indica que era inevitavel"
    return "campo grande demais para prova exata neste diagnostico"


def _hard_color_reason(player_id: int, color: str, histories: dict[int, list[str]]) -> str:
    history = [item for item in histories.get(int(player_id), []) if item in {"W", "B"}]
    white_count = history.count("W")
    black_count = history.count("B")
    next_white = white_count + (1 if color == "W" else 0)
    next_black = black_count + (1 if color == "B" else 0)
    reasons = []
    if len(history) >= 2 and history[-2:] == [color, color]:
        reasons.append(f"seria a terceira { _color_name(color).lower() } seguida")
    if abs(next_white - next_black) > 2:
        reasons.append(f"saldo de cores iria para {next_white - next_black:+d}")
    return "; ".join(reasons) if reasons else "restricao absoluta FIDE violada"


def _color_name(color: str) -> str:
    return "brancas" if color == "W" else "pretas"


def _player_label(player_id: int, players_by_id: dict[int, dict[str, Any]]) -> str:
    player = players_by_id.get(int(player_id), {})
    name = str(player.get("name") or "").strip()
    if name:
        return name
    given_name = str(player.get("given_name") or "").strip()
    surname = str(player.get("surname") or "").strip()
    combined = " ".join(part for part in (given_name, surname) if part).strip()
    return combined or f"ID {int(player_id)}"


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
