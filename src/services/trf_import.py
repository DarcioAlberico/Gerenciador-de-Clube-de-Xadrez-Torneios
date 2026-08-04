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

__all__ = ["BYE_RESULTS", "build_trf_rounds", "parse_trf"]


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


def _parse_round_dates(line: str) -> list[str]:
    """Datas do registro 132 (`YY/MM/DD`), na geometria das células de rodada."""
    datas: list[str] = []
    for bloco in _cell_blocks(line):
        crua = bloco.strip()
        if not crua:
            datas.append("")
            continue
        partes = crua.split("/")
        if len(partes) == 3 and len(partes[0]) == 2:
            crua = f"20{partes[0]}/{partes[1]}/{partes[2]}"
        datas.append(_trf_date_to_iso(crua))
    return datas


def _parse_team_line(line: str, code: str) -> dict[str, Any] | None:
    """Equipe do registro 013 (legado) ou 310 (TRF25): nome + start-ranks.

    O 013 traz o nome em largura fixa e os start-ranks de 4 em 4 a partir da
    coluna 37; o 310 tem o nome deslocado (o registro comeca com o TPN). Sem
    nome nao ha equipe — e a linha e ignorada em vez de virar "Equipe vazia".
    """
    inicio_nome, inicio_ranks = (4, 36) if code == "013" else (8, 40)
    nome = line[inicio_nome:inicio_ranks].strip()
    if not nome:
        return None
    ranks: list[int] = []
    for indice in range(inicio_ranks, len(line), 5):
        bruto = line[indice:indice + 4].strip()
        if bruto.isdigit():
            ranks.append(int(bruto))
    return {"name": nome, "start_ranks": ranks}


def parse_trf(content: str) -> dict[str, Any]:
    """Lê um TRF e devolve cabeçalho + jogadores (com células de rodada brutas)."""
    header: dict[str, str] = {}
    players: list[dict[str, Any]] = []
    deputies: list[str] = []
    round_dates: list[str] = []
    teams: list[dict[str, Any]] = []

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
        elif code == "102":
            header["chief_arbiter"] = rest
        elif code == "112":
            deputies.append(rest)
        elif code == "122":
            header["time_control"] = rest
        elif code == "132":
            round_dates = _parse_round_dates(line)
        elif code in ("013", "310"):
            equipe = _parse_team_line(line, code)
            if equipe:
                teams.append(equipe)
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
        "rounds_count": max(rounds_count, len(round_dates)),
        "players": players,
        # Tudo abaixo era LIDO e jogado fora (FED-04): o arquivo trazia arbitro,
        # calendario e equipes, e a importacao criava um torneio sem nada disso.
        "chief_arbiter": header.get("chief_arbiter", ""),
        "deputy_arbiters": deputies,
        "round_dates": round_dates,
        "teams": teams,
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


# Letra do TRF para a rodada sem adversário -> resultado gravado no Albericus.
# `U` (bye alocado pelo pareamento) e `F` (bye de ponto inteiro concedido) eram a
# MESMA coisa na importação, e viravam `F`: um TRF do Swiss-Manager com `U`
# inflava a pontuação em todo torneio cujo `bye_points` não fosse 1,0, porque o
# `F` vale ponto cheio por definição e o `U` vale o que o regulamento disser.
# `Z` (ausência conhecida, zero ponto) era simplesmente DESCARTADO — a rodada
# sumia do histórico do jogador, e o TRF exportado depois não a trazia de volta.
BYE_RESULTS: dict[str, str] = {
    "U": "BYE",  # alocado: pontua por `bye_points`, como o bye do próprio motor
    "F": "F",    # ponto inteiro
    "H": "H",    # meio ponto
    "Z": "Z",    # zero ponto, mas REGISTRADO
    "-": "Z",    # ausência sem adversário: mesma coisa
}


def _trf_bye_result(code: str) -> str:
    """Rodada sem adversário -> resultado Albericus. Vazio = não pareado."""
    return BYE_RESULTS.get((code or "").strip().upper(), "")


def build_trf_rounds(
    players: Sequence[Mapping[str, Any]],
    rank_to_id: Mapping[int, int],
) -> list[tuple[int, list[dict[str, Any]]]]:
    """Reconstrói rodadas (pareamentos + resultados) a partir das células TRF.

    Devolve (numero_da_rodada, pareamentos) apenas para rodadas que tiveram
    JOGO — pelo menos uma mesa com dois jogadores. Cada jogo é criado uma única
    vez (deduplicado pelos dois jogadores).

    A exigência do jogo é o que separa rodada JOGADA de declaração de ausência
    (FED-04): num TRF de torneio em andamento, um `0000 - Z` na próxima rodada
    quer dizer "este jogador não será pareado nela", e não "esta rodada
    aconteceu". Tratar a segunda como a primeira criava uma rodada fantasma e
    empurrava o torneio importado uma rodada à frente.
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

        if any(not pairing["is_bye"] for pairing in pairings):
            rounds.append((round_index, pairings))
    return rounds
