"""Construtores puros de registros TRF25 (geometria de coluna fixa).

Estas funções não tocam no Database nem no ExportService: recebem primitivos já
normalizados (texto sem acento, números) e devolvem a linha TRF25 exata, com cada
campo posicionado na coluna correta conforme `ESPEC_TRF25_FIDE.md`. O exporter é
responsável por buscar os dados e normalizá-los antes de chamar daqui.

Posições na spec FIDE são 1-based e inclusivas (ex.: `5 - 7` = colunas 5,6,7).
"""

from __future__ import annotations

import unicodedata


def _place(parts: list[tuple[int, str]]) -> str:
    """Posiciona cada `(coluna_inicial_1based, texto)` na linha, preenchendo
    lacunas com espaços. Cada texto já deve vir com a largura final do campo."""
    line = ""
    for start, text in parts:
        idx = start - 1
        if len(line) < idx:
            line += " " * (idx - len(line))
        line += text
    return line


def trf_ascii(value: object) -> str:
    """Remove acentos/diacríticos e colapsa espaços (igual ao TRF16)."""
    text = unicodedata.normalize("NFKD", str(value if value is not None else ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def _fixed(value: object, width: int) -> str:
    """Texto truncado/justificado à esquerda na largura do campo."""
    return trf_ascii(value)[:width].ljust(width)


def _points(value: float, width: int = 6) -> str:
    """Pontos no formato `1111.5` (uma casa decimal), justificado à direita."""
    return f"{float(value or 0.0):>{width}.1f}"[-width:]


def tournament_line(code: str, value: object) -> str:
    """Registro simples `CCC <texto livre a partir da coluna 5>`."""
    text = trf_ascii(value)
    return f"{code} {text}".rstrip() + "\r\n"


def record_310(
    team_pairing_number: int,
    team_name: str,
    nickname: str,
    strength_factor: int,
    match_points: float,
    game_points: float,
    team_rank: int,
    player_start_ranks: list[int],
) -> str:
    """Registro 310 — equipe (substitui o 013). Layout §4.2 da ESPEC."""
    parts: list[tuple[int, str]] = [
        (1, "310"),
        (5, f"{int(team_pairing_number):>3d}"),
        (9, _fixed(team_name, 32)),
        (42, _fixed(nickname, 5)),
        (48, f"{int(strength_factor):>6d}" if strength_factor else " " * 6),
        (55, _points(match_points)),
        (62, _points(game_points)),
        (69, f"{int(team_rank):>3d}"),
    ]
    column = 74
    for start_rank in player_start_ranks:
        parts.append((column, f"{int(start_rank):>4d}"))
        column += 5
    return _place(parts).rstrip() + "\r\n"
