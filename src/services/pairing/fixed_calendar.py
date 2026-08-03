"""Avisos dos formatos de CALENDÁRIO FIXO — rodízio e Scheveningen (PAR-01/03).

Os dois têm a mesma natureza: o confronto de cada rodada é decidido uma vez, na
distribuição dos números, e não se recalcula. Daí saem as mesmas três notícias
para o árbitro — alguém entrou depois do sorteio, alguém saiu e a mesa continua
de pé, e o número de rodadas configurado não fecha com o calendário —, que
estavam escritas duas vezes com a palavra do formato trocada.
"""

from __future__ import annotations

from typing import Sequence


def late_entry_warning(names: Sequence[str], *, formato: str) -> str:
    quem = ", ".join(names)
    return (
        f"Fora do calendario do {formato}: {quem}. Os numeros foram distribuidos "
        "quando a primeira rodada foi gerada e o calendario e fixo — incluir "
        "alguem agora mudaria os confrontos de todo mundo. Quem entra depois joga "
        "o proximo torneio, ou o calendario e refeito antes da rodada 1."
    )


def withdrawn_on_board_warning(names: Sequence[str], *, formato: str) -> str:
    quem = ", ".join(names)
    return (
        f"Mesa(s) com jogador fora do torneio: {quem}. No {formato} o calendario "
        "nao se recalcula, entao a mesa e gerada e o resultado sai por W.O. "
        "(ausencia). Lance o W.O. na mesa para fechar a rodada."
    )


def rounds_mismatch_warning(configured: int, calendar: int, *, formato: str) -> str:
    return (
        f"O {formato} deste campo tem {calendar} rodada(s), e o torneio esta "
        f"configurado com {configured}. Ajuste as rodadas do torneio para o "
        "calendario fechar."
    )
