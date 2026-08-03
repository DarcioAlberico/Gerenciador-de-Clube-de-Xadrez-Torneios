"""Calendário de rodízio (todos contra todos) — funções puras (PAR-01).

O rodízio não é um pareamento: é um CALENDÁRIO. Ele é decidido uma vez, quando os
números de rodízio são sorteados/atribuídos, e a partir daí cada rodada só é lida
da tabela de Berger (FIDE Handbook C.05, Anexo 1).

O que havia antes recalculava o círculo a cada rodada a partir da lista de
jogadores ATIVOS ordenada por rating. Duas consequências, ambas silenciosas:
desativar um jogador (ou corrigir um rating) no meio do evento embaralhava todos
os confrontos futuros dos OUTROS — revanches e confrontos que sumiam —, e não
havia como conferir o calendário contra a tabela publicada da FIDE.

A tabela vem de `gacrux/berger.py` (Otto Milvang, o mesmo autor do motor FIDE que
o projeto já usa para parear e desempatar). É a implementação de referência do
Anexo 1, e manter uma segunda seria repetir o erro que a TBK-03 documentou: duas
implementações da mesma norma divergem na primeira revisão. O acoplamento é a um
módulo SEM dependências (nenhum `import` no arquivo) e está preso por teste — as
tabelas de 6 e 8 jogadores conferidas contra o Handbook.

Este módulo não lê banco: recebe os números já atribuídos e devolve as mesas.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.constants import AppError
from src.services.pairing.fixed_calendar import (
    late_entry_warning as _late_entry_warning,
    rounds_mismatch_warning as _rounds_mismatch_warning,
    withdrawn_on_board_warning as _withdrawn_on_board_warning,
)
from src.services.pairing.gacrux.berger import bergertables

# Fração de partidas que o desistente precisa ter jogado para os resultados dele
# valerem (FIDE C.05). Abaixo disso o regulamento manda anular — decisão que este
# módulo DETECTA e relata, mas não executa: anular reescreve a classificação
# publicada e teria de valer também no motor FIDE de desempate.
FIDE_WITHDRAWAL_THRESHOLD = 0.5


def table_size(field_size: int) -> int:
    """Tamanho da tabela: campo ímpar ganha o número fantasma (o bye)."""
    size = max(int(field_size), 0)
    return size + size % 2


def calendar_rounds(field_size: int, *, double: bool = False) -> int:
    """Quantas rodadas o calendário tem (o dobro, com returno)."""
    size = table_size(field_size)
    if size < 2:
        return 0
    return (size - 1) * (2 if double else 1)


def berger_round(field_size: int, round_number: int, *, double: bool = False) -> list[tuple[int, int]]:
    """Pares `(número das brancas, número das pretas)` de uma rodada.

    Números vão de 1 a `table_size`; o último número, quando o campo é ímpar, é o
    fantasma — quem cai com ele recebe o bye. No returno (rodadas a partir da
    `size`), a mesma rodada do turno volta com as cores trocadas.
    """
    size = table_size(field_size)
    total = calendar_rounds(field_size, double=double)
    if size < 2 or round_number < 1 or round_number > total:
        raise AppError(
            f"Todos contra todos: o calendario tem {total} rodada(s) e a rodada "
            f"{round_number} esta fora dele."
        )
    returno = round_number > size - 1
    base = round_number - (size - 1) if returno else round_number
    pairing = bergertables(size)["pairing"][base]
    pares = [
        (int(pairing[board]["white"]), int(pairing[board]["black"]))
        for board in sorted(pairing)
    ]
    return [(black, white) for white, black in pares] if returno else pares


def round_robin_pairings_from_numbers(
    numbers_by_player: Mapping[int, int],
    round_number: int,
    *,
    double: bool = False,
) -> list[dict[str, Any]]:
    """Mesas da rodada a partir dos números de rodízio persistidos.

    O bye sai como bye DE VERDADE (`is_bye`, resultado `BYE`), e não como um
    `1-0`: o `1-0` só pontuava certo porque o padrão de `bye_points` é 1,0, e
    aparecia como vitória em tudo que lê o resultado — TRF, tabela cruzada e
    contagem de vitórias.
    """
    player_by_number = {int(number): int(player) for player, number in numbers_by_player.items()}
    field_size = len(player_by_number)
    pairings: list[dict[str, Any]] = []
    for white_number, black_number in berger_round(field_size, round_number, double=double):
        white_id = player_by_number.get(white_number)
        black_id = player_by_number.get(black_number)
        if white_id is None and black_id is None:
            continue
        if white_id is None or black_id is None:
            pairings.append(
                {
                    "board_number": len(pairings) + 1,
                    "white_player_id": black_id if white_id is None else white_id,
                    "black_player_id": None,
                    "result": "BYE",
                    "is_bye": 1,
                }
            )
            continue
        pairings.append(
            {
                "board_number": len(pairings) + 1,
                "white_player_id": white_id,
                "black_player_id": black_id,
                "result": "",
                "is_bye": 0,
            }
        )
    return pairings


def assign_numbers(ordered_player_ids: Sequence[int]) -> dict[int, int]:
    """Números de rodízio 1..N na ordem recebida (1 = primeiro da ordem inicial)."""
    return {int(player_id): index for index, player_id in enumerate(ordered_player_ids, start=1)}


def missing_from_calendar(
    numbers_by_player: Mapping[int, int],
    player_ids: Sequence[int],
) -> list[int]:
    """Jogadores inscritos DEPOIS do sorteio — ficam de fora do calendário."""
    numerados = {int(player_id) for player_id in numbers_by_player}
    return [int(player_id) for player_id in player_ids if int(player_id) not in numerados]


def late_entry_warning(names: Sequence[str]) -> str:
    return _late_entry_warning(names, formato="rodizio")


def withdrawn_on_board_warning(names: Sequence[str]) -> str:
    return _withdrawn_on_board_warning(names, formato="rodizio")


def rounds_mismatch_warning(configured: int, calendar: int, *, double: bool) -> str:
    turno = "com returno" if double else "de turno unico"
    return _rounds_mismatch_warning(configured, calendar, formato=f"rodizio {turno}")


def annulment_candidates(
    played_by_player: Mapping[int, int],
    scheduled_rounds: int,
    withdrawn_player_ids: Sequence[int],
) -> list[int]:
    """Desistentes que jogaram menos da metade — a FIDE manda anular os resultados.

    Só a DETECÇÃO: anular muda a classificação publicada (e teria de valer também
    dentro do motor FIDE de desempate, que recalcula tudo pelo arquivo TRF), então
    quem decide é o árbitro, com o regulamento na mão.
    """
    if scheduled_rounds <= 0:
        return []
    limite = FIDE_WITHDRAWAL_THRESHOLD * float(scheduled_rounds)
    return [
        int(player_id)
        for player_id in withdrawn_player_ids
        if float(played_by_player.get(int(player_id), 0)) < limite
    ]


def annulment_warning(names: Sequence[str], scheduled_rounds: int) -> str:
    quem = ", ".join(names)
    return (
        f"Desistencia com menos de metade das partidas jogadas: {quem} (calendario "
        f"de {scheduled_rounds} rodada(s)). A regra FIDE do rodizio (C.05) manda "
        "anular os resultados de quem desiste antes da metade; o Albericus NAO "
        "anula sozinho, porque isso reescreve a classificacao publicada — a "
        "decisao e sua, com o regulamento do evento."
    )
