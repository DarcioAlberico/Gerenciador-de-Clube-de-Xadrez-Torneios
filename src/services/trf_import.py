"""Importação de torneios do Swiss-Manager via arquivo TRF (spec E9 — Fase H).

Parser puro do formato FIDE/Krause TRF16 (linhas de cabeçalho 0X2 + linhas de
jogador 001), no mesmo layout de colunas que o `TRF16Exporter` gera — o que
garante round-trip e também lê TRFs exportados pelo Swiss-Manager.

Nesta fase importamos **cabeçalho do torneio + jogadores**. As células de rodada
são extraídas (campo `rounds`) e ficam disponíveis para uma reconstrução futura
de rodadas/resultados; aqui ainda não são aplicadas.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.results_registry import code_from_trf_letter
from src.services.trf_layout import (
    BIRTH as _BIRTH,
    CELL_COLOR as _CELL_COLOR,
    CELL_OPPONENT as _CELL_OPPONENT,
    CELL_RESULT as _CELL_RESULT,
    FEDERATION as _FEDERATION,
    FIDE_ID as _FIDE_ID,
    NAME as _NAME,
    RATING as _RATING,
    SEX as _SEX,
    START_RANK as _START_RANK,
    TITLE as _TITLE,
    cell_blocks as _cell_blocks,
    field as _slice,
)


def _trf_date_to_iso(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or raw.startswith("0000"):
        return ""
    normalized = raw.replace(".", "/").replace("\\", "/").replace("-", "/")
    parts = normalized.split("/")
    if len(parts) == 3 and len(parts[0]) == 4 and parts[0].isdigit():
        year, month, day = parts
        if month.isdigit() and day.isdigit():
            return f"{year}-{int(month):02d}-{int(day):02d}"
    return ""


def _split_name(raw_name: str) -> tuple[str, str, str]:
    """'Sobrenome, Nome' -> (display, surname, given)."""
    name = str(raw_name or "").strip()
    if "," in name:
        surname, given = (part.strip() for part in name.split(",", 1))
        display = f"{given} {surname}".strip()
        return display or name, surname, given
    return name, "", ""


def _parse_round_cells(line: str) -> list[dict[str, str]]:
    cells: list[dict[str, str]] = []
    for block in _cell_blocks(line):
        opponent = block[_CELL_OPPONENT[0]:_CELL_OPPONENT[1]].strip()
        color = block[_CELL_COLOR:_CELL_COLOR + 1].strip()
        result = block[_CELL_RESULT:_CELL_RESULT + 1].strip()
        if not opponent and not color and not result:
            break
        cells.append({"opponent_rank": opponent, "color": color, "result": result})
    return cells


def parse_trf(content: str) -> dict[str, Any]:
    """Lê um TRF e devolve cabeçalho + jogadores (com células de rodada brutas)."""
    header: dict[str, str] = {}
    players: list[dict[str, Any]] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\r\n")
        if len(line) < 3:
            continue
        code = line[:3]
        rest = line[4:].strip() if len(line) > 4 else ""
        if code == "012":
            header["name"] = rest
        elif code == "022":
            header["location"] = rest
        elif code == "032":
            header["federation"] = rest
        elif code == "042":
            header["start_date"] = _trf_date_to_iso(rest)
        elif code == "052":
            header["end_date"] = _trf_date_to_iso(rest)
        elif code == "122":
            header["time_control"] = rest
        elif code == "001":
            rounds = _parse_round_cells(line)
            display, surname, given = _split_name(_slice(line, _NAME))
            try:
                rating = int(_slice(line, _RATING) or 0)
            except ValueError:
                rating = 0
            try:
                start_rank = int(_slice(line, _START_RANK) or 0)
            except ValueError:
                start_rank = len(players) + 1
            players.append(
                {
                    "start_rank": start_rank,
                    "name": display,
                    "surname": surname,
                    "given_name": given,
                    "sex": _slice(line, _SEX),
                    "title": _slice(line, _TITLE),
                    "rating": rating,
                    "federation_id": _slice(line, _FEDERATION),
                    "fide_id": _slice(line, _FIDE_ID),
                    "birth_date": _trf_date_to_iso(_slice(line, _BIRTH)),
                    "rounds": rounds,
                }
            )

    players.sort(key=lambda item: item["start_rank"])
    rounds_count = max((len(player["rounds"]) for player in players), default=0)
    return {
        "name": header.get("name", "").strip(),
        "location": header.get("location", ""),
        "federation": header.get("federation", ""),
        "start_date": header.get("start_date", ""),
        "end_date": header.get("end_date", ""),
        "time_control": header.get("time_control", ""),
        "rounds_count": rounds_count,
        "players": players,
    }


# O `½` não é letra do TRF: entra porque arquivos gerados por outros programas
# aparecem com ele no lugar do `=`, e recusar a linha inteira por causa de um
# caractere seria pior do que aceitá-lo.
_ALIASES = {"½": "="}


def _decode_game(color: str, code: str) -> str:
    """Resultado Albericus (perspectiva das brancas) a partir da célula do jogador.

    As letras vêm do registro de resultados (ARB-02), que é o mesmo que o
    exportador usa: um código novo passa a ser lido e escrito de uma vez. Era um
    par de dicionários escritos à mão, e o `W`/`D`/`L` — que o TRF já trazia —
    voltava como "sem resultado".
    """
    letra = str(code or "").strip()
    letra = _ALIASES.get(letra, letra)
    return code_from_trf_letter(letra, is_white=color.lower() != "b")


def _trf_bye_result(code: str) -> str:
    """Bye alocado/solicitado -> resultado Albericus. 'Z'/'-'/vazio = não pareado."""
    upper = (code or "").upper()
    if upper in ("U", "F"):
        return "F"
    if upper == "H":
        return "H"
    return ""


def build_trf_rounds(
    players: Sequence[Mapping[str, Any]],
    rank_to_id: Mapping[int, int],
) -> list[tuple[int, list[dict[str, Any]]]]:
    """Reconstrói rodadas (pareamentos + resultados) a partir das células TRF.

    Devolve (numero_da_rodada, pareamentos) apenas para rodadas com ao menos um
    jogo/bye reconhecido. Cada jogo é criado uma única vez (deduplicado pelos
    dois jogadores). Códigos 'Z'/'-' (não pareado) não viram pareamento.
    """
    by_rank = {int(player["start_rank"]): player for player in players}
    max_rounds = max((len(player["rounds"]) for player in players), default=0)

    rounds: list[tuple[int, list[dict[str, Any]]]] = []
    for round_index in range(1, max_rounds + 1):
        pairings: list[dict[str, Any]] = []
        processed: set[int] = set()
        board = 1
        for rank in sorted(by_rank):
            if rank in processed:
                continue
            player = by_rank[rank]
            if len(player["rounds"]) < round_index:
                continue
            player_id = rank_to_id.get(rank)
            if not player_id:
                continue
            cell = player["rounds"][round_index - 1]
            opponent_raw = str(cell.get("opponent_rank") or "")
            opponent_rank = int(opponent_raw) if opponent_raw.isdigit() else 0

            if opponent_rank <= 0:
                bye_result = _trf_bye_result(cell.get("result", ""))
                if bye_result:
                    pairings.append(
                        {
                            "board_number": board,
                            "white_player_id": player_id,
                            "black_player_id": None,
                            "result": bye_result,
                            "is_bye": 1,
                        }
                    )
                    board += 1
                processed.add(rank)
                continue

            if opponent_rank in processed:
                continue
            opponent_id = rank_to_id.get(opponent_rank)
            if not opponent_id:
                processed.add(rank)
                continue

            color = str(cell.get("color") or "").lower()
            result = _decode_game(color, str(cell.get("result") or ""))
            if color == "b":
                white_id, black_id = opponent_id, player_id
            else:
                white_id, black_id = player_id, opponent_id
            pairings.append(
                {
                    "board_number": board,
                    "white_player_id": white_id,
                    "black_player_id": black_id,
                    "result": result,
                    "is_bye": 0,
                }
            )
            board += 1
            processed.add(rank)
            processed.add(opponent_rank)

        if pairings:
            rounds.append((round_index, pairings))
    return rounds
