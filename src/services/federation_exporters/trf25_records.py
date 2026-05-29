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


def record_802(
    team_pairing_number: int,
    nickname: str,
    match_points: float,
    game_points: float,
    rounds: list[tuple[str, str, float | None, str]],
) -> str:
    """Registro 802 — resumo informativo de equipe (comprimento fixo). §8.2.

    Cada item de `rounds` é `(oponente, cor, game_points, forfeit)`:
    `oponente` = TPN do adversário ou código de bye (`PAB`/`FPB`/`HPB`/`ZPB`),
    `cor` ∈ {`w`,`b`,``}, `game_points` do match (None = vazio), `forfeit` ∈
    {`f`,`F`,``}. Rodadas vazias à direita somem no rstrip final.
    """
    parts: list[tuple[int, str]] = [
        (1, "802"),
        (5, f"{int(team_pairing_number):>3d}"),
        (9, _fixed(nickname, 5)),
        (15, _points(match_points, 6)),
        (22, _points(game_points, 6)),
    ]
    column = 29
    for opponent, colour, gp, forfeit in rounds:
        parts.append((column, str(opponent)[:3].ljust(3)))
        parts.append((column + 4, str(colour)[:1]))
        parts.append((column + 6, "    " if gp is None else _points(gp, 4)))
        parts.append((column + 10, str(forfeit)[:1]))
        column += 13
    return _place(parts).rstrip() + "\r\n"


def _signed_points(value: float, width: int) -> str:
    """Pontos com sinal opcional `[-]11.5`, justificado à direita."""
    return f"{float(value or 0.0):>{width}.1f}"[-width:]


def record_240(bye_type: str, round_number: int, entities: list[int]) -> str:
    """Registro 240 — full/half/zero-point-bye (ind. e equipes). Layout §6.1.

    `bye_type` ∈ {F, H, Z}; `entities` são starting-ranks (ind.) ou TPNs (equipes).
    Máx. 1 registro por tipo por rodada (responsabilidade do chamador).
    """
    parts: list[tuple[int, str]] = [
        (1, "240"),
        (5, str(bye_type)[:1].upper()),
        (7, f"{int(round_number):>3d}"),
    ]
    column = 11
    for entity in entities:
        parts.append((column, f"{int(entity):>4d}"))
        column += 5
    return _place(parts).rstrip() + "\r\n"


def record_320(match_points: float, game_points: float, tpn_by_round: list[int]) -> str:
    """Registro 320 — pairing-allocated-bye (só equipes, 1 por torneio). §6.2.

    `tpn_by_round[i]` é o TPN que recebeu o PAB na rodada i+1 (0 = ninguém).
    """
    parts: list[tuple[int, str]] = [
        (1, "320"),
        (5, _points(match_points, 4)),
        (10, _points(game_points, 4)),
    ]
    column = 15
    for tpn in tpn_by_round:
        parts.append((column, f"{int(tpn):>3d}" if tpn else "000"))
        column += 4
    return _place(parts).rstrip() + "\r\n"


def record_330(match_type: str, round_number: int, white_tpn: int, black_tpn: int) -> str:
    """Registro 330 — forfeited matches (equipes). §7.1.

    `match_type` ∈ {`+-` branca vence, `-+` preta vence, `--` duplo forfeit}.
    """
    parts: list[tuple[int, str]] = [
        (1, "330"),
        (5, str(match_type)[:2].ljust(2)),
        (8, f"{int(round_number):>3d}"),
        (12, f"{int(white_tpn):>3d}"),
        (16, f"{int(black_tpn):>3d}"),
    ]
    return _place(parts).rstrip() + "\r\n"


def record_300(
    round_number: int,
    team_tpn: int,
    opponent_tpn: int,
    board_player_ranks: list[int],
) -> str:
    """Registro 300 — out-of-(default)order (equipes). §7.2.

    `board_player_ranks[i]` é o starting-rank do jogador no tabuleiro i+1
    (0 = `0000`/vazio).
    """
    parts: list[tuple[int, str]] = [
        (1, "300"),
        (5, f"{int(round_number):>3d}"),
        (9, f"{int(team_tpn):>3d}"),
        (13, f"{int(opponent_tpn):>3d}"),
    ]
    column = 17
    for rank in board_player_ranks:
        parts.append((column, f"{int(rank):>4d}" if rank else "0000"))
        column += 5
    return _place(parts).rstrip() + "\r\n"


def record_162(symbol_points: list[tuple[str, float]]) -> str:
    """Registro 162 — sistema de pontuação individual. §1.1.

    Pares `(símbolo, pontos)` posicionados a cada 9 colunas: símbolo na 6/15/24…,
    pontos (`11.5`) logo em seguida. Emitir só quando diverge do padrão FIDE.
    """
    parts: list[tuple[int, str]] = [(1, "162")]
    column = 6
    for symbol, points in symbol_points:
        parts.append((column, str(symbol)[:1]))
        parts.append((column + 1, _points(points, 4)))
        column += 9
    return _place(parts).rstrip() + "\r\n"


def record_362(symbol_points: list[tuple[str, float]]) -> str:
    """Registro 362 — sistema de pontuação por equipes. §1.4.

    Pares `(símbolo de 2 letras TW/TD/TL, pontos)` a cada 9 colunas: símbolo na
    5-6/14-15/23-24, pontos (`11.5`) em 7-10/16-19/25-28. Padrão TW=2/TD=1/TL=0.
    """
    parts: list[tuple[int, str]] = [(1, "362")]
    column = 5
    for symbol, points in symbol_points:
        parts.append((column, str(symbol)[:2].ljust(2)))
        parts.append((column + 2, _points(points, 4)))
        column += 9
    return _place(parts).rstrip() + "\r\n"


def record_212(codes: list[str]) -> str:
    """Registro 212 — tie-breaks de classificação como CSV de descritores. §11.

    Os códigos já vêm prontos (ex.: `PTS`, `BH/M1`, `BH:MP`); aqui só se junta
    com vírgula. A lista deve sempre começar por `PTS`.
    """
    return tournament_line("212", ",".join(codes))


def record_299(
    aat_type: str,
    match_points: float,
    game_points: float,
    round_number: int,
    entities: list[int],
) -> str:
    """Registro 299 — abnormal assignment points (ind. e equipes). §7.3.

    `aat_type`: W/D/L (→362), F/H/Z (→240), +/- (→330) ou vazio (penalidade/
    bônus). `round_number` 0 = todas as rodadas; `entities` vazio = todos.
    Match points só se aplicam a equipes; para indivíduos use só `game_points`.
    """
    parts: list[tuple[int, str]] = [
        (1, "299"),
        (5, str(aat_type)[:1].upper() if aat_type else " "),
        (8, _signed_points(match_points, 4)),
        (14, _signed_points(game_points, 4)),
        (20, f"{int(round_number):>3d}" if round_number else "000"),
    ]
    column = 24
    for entity in entities:
        parts.append((column, f"{int(entity):>4d}" if entity else "000"))
        column += 5
    return _place(parts).rstrip() + "\r\n"
