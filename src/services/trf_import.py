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

from src.domain.dates import DataInvalida, ResultadoData, parse_trf_date, parse_trf_round_date, storage_text
from src.services.categories.matching import normalized_sex
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
    ROUND_CELL_WIDTH as _ROUND_CELL_WIDTH,
    ROUND_CELLS_START as _ROUND_CELLS_START,
    SEX as _SEX,
    START_RANK as _START_RANK,
    TITLE as _TITLE,
    cell_blocks as _cell_blocks,
    field as _slice,
)

__all__ = ["BYE_RESULTS", "TrfDateError", "TrfError", "build_trf_rounds", "parse_trf"]


class TrfError(ValueError):
    """Linha do TRF que não dá para importar sem inventar dado (RG2-13).

    Rank inicial ilegível virava ``len(players)+1`` e colidia com outro; rank
    repetido sobrescrevia o primeiro. Agora a importação para e diz a linha.
    """


class TrfDateError(TrfError):
    """Data que o arquivo traz e o calendário não tem (RGS-07).

    `2026.02.30` virava `2026-02-30` no banco. Agora a importação para e diz
    onde está o erro, em linha e colunas (1-based, como num editor de texto).
    """

    def __init__(self, linha: int, coluna_inicio: int, coluna_fim: int, texto: str, motivo: str) -> None:
        self.linha = linha
        self.colunas = (coluna_inicio, coluna_fim)
        super().__init__(
            f"TRF linha {linha}, colunas {coluna_inicio}-{coluna_fim}: "
            f"data inválida \"{texto}\" ({motivo})"
        )


def _trf_date(resultado: ResultadoData, linha: int, inicio: int, fim: int) -> str:
    """Texto gravável, ou `TrfDateError` com o lugar exato no arquivo."""
    if isinstance(resultado, DataInvalida):
        raise TrfDateError(linha, inicio, fim, resultado.texto, resultado.motivo)
    return storage_text(resultado)


def _header_date(line: str, numero: int) -> str:
    """Data dos registros 042/052: o valor começa na coluna 5."""
    bruto = line[4:]
    valor = bruto.strip()
    inicio = 5 + (len(bruto) - len(bruto.lstrip()))
    return _trf_date(parse_trf_date(valor), numero, inicio, max(inicio, inicio + len(valor) - 1))


def _split_name(raw_name: str) -> tuple[str, str, str]:
    """'Sobrenome, Nome' -> (display, surname, given)."""
    name = str(raw_name or "").strip()
    if "," in name:
        surname, given = (part.strip() for part in name.split(",", 1))
        display = f"{given} {surname}".strip()
        return display or name, surname, given
    return name, "", ""


def _parse_round_cells(line: str) -> list[dict[str, str]]:
    """Células da linha 001 até a última preenchida (RG2-13).

    Célula em branco no meio é "não pareado nesta rodada" (o entrante tardio
    tem a R1 em branco) e fica na lista, na posição da rodada; a leitura parava
    nela e o jogador perdia todas as rodadas seguintes. Só as brancas do fim
    saem — são preenchimento da linha, não rodadas.
    """
    cells: list[dict[str, str]] = []
    for block in _cell_blocks(line):
        opponent = block[_CELL_OPPONENT[0]:_CELL_OPPONENT[1]].strip()
        color = block[_CELL_COLOR:_CELL_COLOR + 1].strip()
        result = block[_CELL_RESULT:_CELL_RESULT + 1].strip()
        cells.append({"opponent_rank": opponent, "color": color, "result": result})
    while cells and not any(cells[-1].values()):
        cells.pop()
    return cells


def _start_rank(line: str, numero: int, vistos: dict[int, int]) -> int:
    """Rank inicial da linha 001; ilegível ou repetido levanta ``TrfError``."""
    bruto = _slice(line, _START_RANK)
    if not bruto.isdigit() or int(bruto) <= 0:
        raise TrfError(
            f"TRF linha {numero}, colunas {_START_RANK[0] + 1}-{_START_RANK[1]}: "
            f"rank inicial ilegível \"{bruto}\"."
        )
    rank = int(bruto)
    if rank in vistos:
        raise TrfError(f"TRF linha {numero}: o rank {rank} já aparece na linha {vistos[rank]}.")
    vistos[rank] = numero
    return rank


def _declared_rounds(rest: str) -> int:
    """Total de rodadas do 142 (TRF25) ou do XXR (TRF16); 0 quando ilegível."""
    texto = rest.strip()
    return int(texto) if texto.isdigit() else 0


def _consistency_warnings(players: Sequence[Mapping[str, Any]]) -> list[str]:
    """O que o arquivo traz e a importação não consegue honrar, dito por linha.

    Antes isso sumia calado: o jogo com adversário que não existe, o jogo que
    só um dos lados registra e a letra de resultado desconhecida.
    """
    by_rank = {int(player["start_rank"]): player for player in players}
    avisos: list[str] = []
    for player in players:
        quem = f"{player['name']} (rank {player['start_rank']}, linha {player['line']})"
        for indice, cell in enumerate(player["rounds"], start=1):
            bruto = str(cell.get("opponent_rank") or "")
            letra = str(cell.get("result") or "")
            if bruto and not bruto.isdigit():
                avisos.append(f"{quem}, rodada {indice}: adversário ilegível \"{bruto}\" — a rodada não entra.")
                continue
            adversario_rank = int(bruto or 0)
            if adversario_rank <= 0:
                if letra and not _trf_bye_result(letra):
                    avisos.append(f"{quem}, rodada {indice}: resultado \"{letra}\" desconhecido — a rodada não entra.")
                continue
            adversario = by_rank.get(adversario_rank)
            if adversario is None:
                avisos.append(
                    f"{quem}, rodada {indice}: aponta para o rank {adversario_rank}, "
                    "que não está no arquivo — o jogo não entra."
                )
                continue
            volta = adversario["rounds"][indice - 1] if len(adversario["rounds"]) >= indice else {}
            if str(volta.get("opponent_rank") or "").lstrip("0") != str(player["start_rank"]):
                avisos.append(
                    f"{quem}, rodada {indice}: joga com o rank {adversario_rank}, mas a linha "
                    f"{adversario['line']} ({adversario['name']}) não aponta de volta — confira o jogo."
                )
            if letra and not _decode_game(str(cell.get("color") or ""), letra):
                avisos.append(f"{quem}, rodada {indice}: resultado \"{letra}\" desconhecido — a mesa entra sem resultado.")
    return avisos


def _parse_round_dates(line: str, numero: int) -> list[str]:
    """Datas do registro 132 (`YY/MM/DD`, como manda o TRF16), na geometria das
    células de rodada."""
    datas: list[str] = []
    for indice, bloco in enumerate(_cell_blocks(line)):
        inicio = _ROUND_CELLS_START + indice * _ROUND_CELL_WIDTH + 1
        datas.append(
            _trf_date(parse_trf_round_date(bloco), numero, inicio, inicio + _ROUND_CELL_WIDTH - 1)
        )
    return datas


def _parse_team_line(line: str, code: str) -> dict[str, Any] | None:
    """Equipe do registro 013 (legado) ou 310 (TRF25): nome + start-ranks.

    O 013 traz o nome em largura fixa e os start-ranks de 4 em 4 a partir da
    coluna 37; o 310 tem o nome deslocado (o registro começa com o TPN). Sem
    nome não há equipe — e a linha e ignorada em vez de virar "Equipe vazia".
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
    """Lê um TRF e devolve cabeçalho + jogadores (com células de rodada brutas).

    ``warnings`` traz, por linha, o que a importação não vai conseguir honrar
    (RG2-13); rank ilegível ou repetido levanta ``TrfError``.
    """
    header: dict[str, str] = {}
    players: list[dict[str, Any]] = []
    deputies: list[str] = []
    round_dates: list[str] = []
    teams: list[dict[str, Any]] = []
    declared_rounds = 0
    vistos: dict[int, int] = {}

    for numero, raw_line in enumerate(content.splitlines(), start=1):
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
            header["start_date"] = _header_date(line, numero)
        elif code == "052":
            header["end_date"] = _header_date(line, numero)
        elif code == "102":
            header["chief_arbiter"] = rest
        elif code == "112":
            deputies.append(rest)
        elif code == "122":
            header["time_control"] = rest
        elif code == "132":
            round_dates = _parse_round_dates(line, numero)
        elif code in ("142", "XXR"):
            declared_rounds = _declared_rounds(rest)
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
            start_rank = _start_rank(line, numero, vistos)
            players.append(
                {
                    "line": numero,
                    "start_rank": start_rank,
                    "name": display,
                    "surname": surname,
                    "given_name": given,
                    "sex": normalized_sex(_slice(line, _SEX)),
                    "title": _slice(line, _TITLE),
                    "rating": rating,
                    "federation_id": _slice(line, _FEDERATION),
                    "fide_id": _slice(line, _FIDE_ID),
                    # Nascimento aceita só o ano (`1985`, `1985/00/00`): é o
                    # que a lista da FIDE publica e o que o TRF permite.
                    "birth_date": _trf_date(
                        parse_trf_date(_slice(line, _BIRTH), permite_ano=True),
                        numero,
                        _BIRTH[0] + 1,
                        _BIRTH[1],
                    ),
                    "rounds": rounds,
                }
            )

    players.sort(key=lambda item: item["start_rank"])
    rounds_count = max((len(player["rounds"]) for player in players), default=0)
    # O total do torneio vem do 142/XXR quando o arquivo o declara: num torneio
    # em andamento (D8), as células só contam as rodadas já pareadas.
    total = max(declared_rounds, rounds_count) if declared_rounds else max(rounds_count, len(round_dates))
    return {
        "name": header.get("name", "").strip(),
        "location": header.get("location", ""),
        "federation": header.get("federation", ""),
        "start_date": header.get("start_date", ""),
        "end_date": header.get("end_date", ""),
        "time_control": header.get("time_control", ""),
        "rounds_count": total,
        "players": players,
        "warnings": _consistency_warnings(players),
        # Tudo abaixo era LIDO e jogado fora (FED-04): o arquivo trazia árbitro,
        # calendário e equipes, e a importação criava um torneio sem nada disso.
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
