"""Geometria da linha 001 do TRF (FIDE/Krause) — um lugar só.

O layout é ESCRITO por `federation_exporters/trf16.py` (`_trf_player_line`) e
lido por dois módulos independentes: a importação de TRF (`trf_import.py`) e o
ajuste do arquivo que alimenta o motor Gacrux (`pairing/gacrux_trf.py`). Cada um
tinha a sua cópia dos offsets, então mudar a linha exigia lembrar dos dois — e
quem esquecesse não ganharia erro nenhum, só campos lidos de lugar errado.

Os limites são fatias de `str` (0-based, fim exclusivo), não as colunas 1-based
da spec FIDE.
"""

from __future__ import annotations

Bounds = tuple[int, int]

START_RANK: Bounds = (4, 8)
SEX: Bounds = (9, 10)
TITLE: Bounds = (10, 13)
NAME: Bounds = (14, 47)
RATING: Bounds = (48, 52)
FEDERATION: Bounds = (53, 56)
FIDE_ID: Bounds = (57, 68)
BIRTH: Bounds = (69, 79)
POINTS: Bounds = (80, 84)
RANK: Bounds = (85, 89)

ROUND_CELLS_START = 91
ROUND_CELL_WIDTH = 10

# Dentro da célula `NNNN c r  `: adversário, cor e resultado.
CELL_OPPONENT: Bounds = (0, 4)
CELL_COLOR = 5
CELL_RESULT = 7


def field(line: str, bounds: Bounds) -> str:
    """Campo da linha 001, já sem espaços nas pontas."""
    return line[bounds[0]:bounds[1]].strip()


def cell_start(round_number: int) -> int:
    """Índice onde começa a célula da rodada (1 = primeira)."""
    return ROUND_CELLS_START + (int(round_number) - 1) * ROUND_CELL_WIDTH


def cell_blocks(line: str) -> list[str]:
    """Células da linha por POSIÇÃO — o índice na lista é que diz a rodada.

    Nada é filtrado: quem tem regra de parada (célula em branco, fim do torneio)
    aplica a sua. A última célula chega com 8 caracteres em vez de 10 porque o
    exportador dá `rstrip()` na linha, e a conta de parada já conta com isso.
    """
    blocks: list[str] = []
    index = ROUND_CELLS_START
    while index + ROUND_CELL_WIDTH - 2 <= len(line):
        blocks.append(line[index:index + ROUND_CELL_WIDTH])
        index += ROUND_CELL_WIDTH
    return blocks
