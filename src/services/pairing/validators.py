"""Validadores e localizadores puros usados por PairingService."""

from __future__ import annotations

from typing import Any

from src.services.constants import AppError


def plan_pairing_player_swap(
    pairings: list[dict[str, Any]],
    source_pairing: dict[str, Any],
    target_slot: dict[str, Any] | None,
    color: str,
    source_player_id: int,
    replacement_player_id: int,
) -> list[tuple[int, int, int | None]]:
    """Calcula o plano de atualização para uma troca manual de jogador.

    Aplica a substituição na mesa de origem e, se o substituto já jogava em
    outra mesa, espelha a troca lá. Valida que nenhuma mesa fique com o mesmo
    jogador dos dois lados ou sem brancas. Retorna apenas as mesas afetadas
    como tuplas (pairing_id, white_player_id, black_player_id).
    """
    updates: dict[int, dict[str, int | None]] = {
        int(pairing["id"]): {
            "white": int(pairing["white_player_id"]),
            "black": int(pairing["black_player_id"]) if pairing["black_player_id"] else None,
        }
        for pairing in pairings
    }
    updates[int(source_pairing["id"])][color] = int(replacement_player_id)
    if target_slot:
        updates[int(target_slot["pairing"]["id"])][target_slot["color"]] = int(source_player_id)

    for values in updates.values():
        black_player_id = values["black"]
        if black_player_id is not None and values["white"] == black_player_id:
            raise AppError("Uma mesa nao pode ter o mesmo jogador dos dois lados.")

    affected_ids = {int(source_pairing["id"])}
    if target_slot:
        affected_ids.add(int(target_slot["pairing"]["id"]))

    pairing_updates: list[tuple[int, int, int | None]] = []
    for pairing_id, values in updates.items():
        if pairing_id not in affected_ids:
            continue
        if values["white"] is None:
            raise AppError("Uma mesa precisa ter jogador de brancas.")
        pairing_updates.append((pairing_id, values["white"], values["black"]))
    return pairing_updates


def plan_team_board_player_swap(
    boards: list[dict[str, Any]],
    affected_board_ids: set[int],
    team_board_id: int,
    target_slot: dict[str, Any] | None,
    color: str,
    source_player_id: int,
    replacement_player_id: int,
) -> list[tuple[int, int | None, int | None]]:
    """Calcula o plano de atualização para troca manual de jogador em tabuleiro.

    Diferente das mesas individuais, um tabuleiro pode ficar sem jogador de um
    lado; a validação de jogador duplicado cobre apenas os tabuleiros afetados.
    """
    updates: dict[int, dict[str, int | None]] = {
        int(board["id"]): {
            "white": int(board["white_player_id"]) if board["white_player_id"] else None,
            "black": int(board["black_player_id"]) if board["black_player_id"] else None,
        }
        for board in boards
    }
    updates[int(team_board_id)][color] = int(replacement_player_id)
    if target_slot:
        updates[int(target_slot["board"]["id"])][target_slot["color"]] = int(source_player_id)

    for board_id in affected_board_ids:
        values = updates[board_id]
        if values["white"] is not None and values["white"] == values["black"]:
            raise AppError("Um tabuleiro nao pode ter o mesmo jogador dos dois lados.")

    return [
        (board_id, updates[board_id]["white"], updates[board_id]["black"])
        for board_id in affected_board_ids
    ]


def find_player_slot(pairings: list[dict[str, Any]], player_id: int) -> dict[str, Any] | None:
    for pairing in pairings:
        if int(pairing["white_player_id"]) == int(player_id):
            return {"pairing": pairing, "color": "white"}
        if pairing["black_player_id"] and int(pairing["black_player_id"]) == int(player_id):
            return {"pairing": pairing, "color": "black"}
    return None


def find_team_board_player_slot(boards: list[dict[str, Any]], player_id: int) -> dict[str, Any] | None:
    for board in boards:
        if board.get("white_player_id") and int(board["white_player_id"]) == int(player_id):
            return {"board": board, "color": "white"}
        if board.get("black_player_id") and int(board["black_player_id"]) == int(player_id):
            return {"board": board, "color": "black"}
    return None
