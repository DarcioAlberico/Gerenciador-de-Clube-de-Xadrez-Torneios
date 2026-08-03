"""Scheveningen com escala persistida — funções puras (PAR-03).

Cada jogador do grupo A enfrenta todos do grupo B. Como no rodízio, isso é um
CALENDÁRIO: quem joga com quem em cada rodada é decidido na distribuição dos
números, não a cada geração.

O que havia antes recalculava a escala a cada rodada a partir da lista de
jogadores ATIVOS, ordenada por ranking. Uma desistência tirava alguém da lista,
todos os índices seguintes andavam uma casa — e os confrontos das rodadas que
ainda faltavam viravam outros, sem aviso. Pior: com um a menos, os dois grupos
deixavam de ter o mesmo tamanho e a geração passava a ser recusada, travando o
torneio em vez de tolerar a ausência.

Agora o grupo (`players.scheveningen_group`) e o número dentro do grupo
(`players.scheveningen_number`) são atribuídos uma vez e guardados. Quem desiste
mantém a cadeira: a mesa é gerada e sai por W.O.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.constants import AppError
from src.services.pairing.fixed_calendar import (
    late_entry_warning as _late_entry_warning,
    rounds_mismatch_warning as _rounds_mismatch_warning,
    withdrawn_on_board_warning as _withdrawn_on_board_warning,
)

GROUP_A = "A"
GROUP_B = "B"
GROUPS = (GROUP_A, GROUP_B)

FORMAT_NAME = "Scheveningen"


def normalize_group(value: Any) -> str:
    grupo = str(value or "").strip().upper()
    return grupo if grupo in GROUPS else ""


def assign_scale(
    ordered_player_ids: Sequence[int],
    groups_by_player: Mapping[int, Any] | None = None,
) -> dict[int, tuple[str, int]]:
    """Escala do torneio: `{player_id: (grupo, numero)}`.

    Respeita a divisão manual quando ela existe nos DOIS grupos (é o caso do
    confronto entre clubes, ou entre juniores e veteranos, onde o grupo não sai
    do ranking); senão parte o campo pela ordem inicial: metade de cima no A,
    metade de baixo no B. Os números seguem a ordem recebida dentro de cada
    grupo.
    """
    manual = {
        int(player_id): normalize_group(grupo)
        for player_id, grupo in (groups_by_player or {}).items()
        if normalize_group(grupo)
    }
    ids = [int(player_id) for player_id in ordered_player_ids]
    grupo_a = [player_id for player_id in ids if manual.get(player_id) == GROUP_A]
    grupo_b = [player_id for player_id in ids if manual.get(player_id) == GROUP_B]

    if not (grupo_a and grupo_b):
        if len(ids) % 2 == 1:
            raise AppError(
                "Scheveningen exige numero par de jogadores (dois grupos iguais)."
            )
        metade = len(ids) // 2
        grupo_a, grupo_b = ids[:metade], ids[metade:]
    elif len(grupo_a) != len(grupo_b):
        raise AppError("Scheveningen: os grupos A e B devem ter o mesmo numero de jogadores.")
    elif len(grupo_a) + len(grupo_b) != len(ids):
        raise AppError(
            "Scheveningen: todos os jogadores precisam estar no grupo A ou no B "
            "quando a divisao e manual."
        )

    escala: dict[int, tuple[str, int]] = {}
    for grupo, membros in ((GROUP_A, grupo_a), (GROUP_B, grupo_b)):
        for numero, player_id in enumerate(membros, start=1):
            escala[int(player_id)] = (grupo, numero)
    return escala


def group_size(scale: Mapping[int, tuple[str, int]]) -> int:
    return sum(1 for grupo, _numero in scale.values() if grupo == GROUP_A)


def calendar_rounds(scale: Mapping[int, tuple[str, int]]) -> int:
    """Cada jogador do A enfrenta cada um do B: uma rodada por membro do grupo."""
    return group_size(scale)


def scheveningen_pairings_from_scale(
    scale: Mapping[int, tuple[str, int]],
    round_number: int,
) -> list[dict[str, Any]]:
    """Mesas da rodada a partir da escala guardada.

    Na rodada `r`, o número `i` do grupo A joga com o `((i + r - 2) % n) + 1` do
    B — a mesma rotação de sempre, agora sobre números fixos. As cores alternam
    com a paridade de `i + r`, para nenhum grupo ficar sempre com as brancas.
    """
    total = group_size(scale)
    if total < 1:
        raise AppError("Scheveningen: a escala do torneio ainda nao foi montada.")
    if round_number < 1 or round_number > total:
        raise AppError(
            f"Scheveningen: o calendario tem {total} rodada(s) e a rodada "
            f"{round_number} esta fora dele."
        )
    por_numero = {
        (grupo, numero): int(player_id) for player_id, (grupo, numero) in scale.items()
    }
    pairings: list[dict[str, Any]] = []
    for numero in range(1, total + 1):
        jogador = por_numero.get((GROUP_A, numero))
        adversario = por_numero.get((GROUP_B, ((numero + round_number - 2) % total) + 1))
        if jogador is None or adversario is None:
            continue
        if (numero + round_number) % 2 == 0:
            brancas, pretas = jogador, adversario
        else:
            brancas, pretas = adversario, jogador
        pairings.append(
            {
                "board_number": len(pairings) + 1,
                "white_player_id": brancas,
                "black_player_id": pretas,
                "result": "",
                "is_bye": 0,
            }
        )
    return pairings


def missing_from_scale(
    scale: Mapping[int, tuple[str, int]],
    player_ids: Sequence[int],
) -> list[int]:
    escalados = {int(player_id) for player_id in scale}
    return [int(player_id) for player_id in player_ids if int(player_id) not in escalados]


def late_entry_warning(names: Sequence[str]) -> str:
    return _late_entry_warning(names, formato=FORMAT_NAME)


def withdrawn_on_board_warning(names: Sequence[str]) -> str:
    return _withdrawn_on_board_warning(names, formato=FORMAT_NAME)


def rounds_mismatch_warning(configured: int, calendar: int) -> str:
    return _rounds_mismatch_warning(configured, calendar, formato=FORMAT_NAME)
