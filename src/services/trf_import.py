"""Importação de torneios do Swiss-Manager via arquivo TRF (spec E9 — Fase H).

Parser puro do formato FIDE/Krause TRF16 (linhas de cabeçalho 0X2 + linhas de
jogador 001), no mesmo layout de colunas que o `TRF16Exporter` gera — o que
garante round-trip e também lê TRFs exportados pelo Swiss-Manager.

Nesta fase importamos **cabeçalho do torneio + jogadores**. As células de rodada
são extraídas (campo `rounds`) e ficam disponíveis para uma reconstrução futura
de rodadas/resultados; aqui ainda não são aplicadas.
"""

from __future__ import annotations

from typing import Any

# Offsets fixos da linha 001 (idênticos ao layout escrito pelo TRF16Exporter,
# que segue o padrão FIDE Krause).
_START_RANK = (4, 8)
_SEX = (9, 10)
_TITLE = (10, 13)
_NAME = (14, 47)
_RATING = (48, 52)
_FEDERATION = (53, 56)
_FIDE_ID = (57, 68)
_BIRTH = (69, 79)
_ROUND_CELLS_START = 91
_ROUND_CELL_WIDTH = 10


def _slice(line: str, bounds: tuple[int, int]) -> str:
    return line[bounds[0]:bounds[1]].strip()


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
    index = _ROUND_CELLS_START
    while index + _ROUND_CELL_WIDTH - 2 <= len(line):
        block = line[index:index + _ROUND_CELL_WIDTH]
        opponent = block[0:4].strip()
        color = block[5:6].strip()
        result = block[7:8].strip()
        if not opponent and not color and not result:
            break
        cells.append({"opponent_rank": opponent, "color": color, "result": result})
        index += _ROUND_CELL_WIDTH
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
