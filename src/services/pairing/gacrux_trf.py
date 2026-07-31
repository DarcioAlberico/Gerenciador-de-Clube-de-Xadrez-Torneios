"""Ajustes do TRF que alimenta o motor Gacrux — funções puras (PAR-02).

O Gacrux recebe o torneio como TRF-16 e **recalcula tudo a partir das células de
rodada da linha 001**. Duas decisões que o Albericus toma fora das células não
chegavam nele, e sumiam sem aviso justamente porque o Gacrux é o motor padrão:

- a **aceleração** (pontos fictícios de pareamento) só existia no motor próprio;
- os **pontos de entrada tardia** (`starting_points`) aparecem no campo de pontos
  da linha 001, mas as rodadas anteriores à inscrição saem como `0000 - Z`
  (zero ponto). O entrante tardio era pareado num grupo de pontuação diferente
  do que a classificação publica.

Este módulo não lê banco nem arquivo: recebe as **linhas** do TRF já geradas pelo
exportador e devolve as linhas ajustadas mais os avisos do que não deu para
representar. Quem faz I/O é o `GacruxEngine`.

Dialeto: a tabela de letras é a do parser que vai ler o arquivo
(`gacrux/trf2json.py`, `self.results`, resolvida em `gacrux/scoresystem.py`,
`default_score["game"]`) — é ele quem define o que cada célula vale, e não a
nossa leitura da spec.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from src.services.federation_exporters.trf25_records import record_250
from src.services.trf_layout import (
    CELL_OPPONENT,
    CELL_RESULT,
    NAME,
    POINTS,
    ROUND_CELL_WIDTH,
    START_RANK,
    cell_blocks,
    cell_start,
    field,
)

# Letra TRF -> pontos que o Gacrux atribui ao jogador daquela célula.
# `U` (pairing-allocated bye) cai no código de pontuação `P`, que por padrão vale
# uma vitória; `X`/`?` caem em `A`, que vale um empate.
TRF_LETTER_POINTS: dict[str, float] = {
    "1": 1.0, "+": 1.0, "F": 1.0, "W": 1.0, "U": 1.0,
    "=": 0.5, "H": 0.5, "D": 0.5, "X": 0.5, "?": 0.5,
    "0": 0.0, "-": 0.0, "L": 0.0, "Z": 0.0, "A": 0.0, " ": 0.0,
}

# Letras que representam ponto ganho SEM partida, para preencher rodadas de
# ausência. `H` primeiro: meio ponto é o que a maioria dos regulamentos concede
# ao entrante tardio, e a FIDE só considera "pontuou sem jogar" (critério de
# qualidade na atribuição do bye) quem ganhou o ponto inteiro.
COMPENSATION_LETTERS: tuple[tuple[str, float], ...] = (("H", 0.5), ("F", 1.0))

# Bônus de aceleração que o registro 250 consegue transportar. O Gacrux converte
# os pontos do registro em um CÓDIGO de resultado (`get_result`) e depois de volta
# em pontos: só o que casa com uma vitória ou um empate sobrevive à viagem — o
# resto vira zero em silêncio, que é exatamente o que a PAR-02 existe para
# impedir. Ver `gacrux/trf2json.parse_trf_accelerated`.
EXPRESSIBLE_BONUSES: tuple[float, ...] = (0.5, 1.0)

_TOLERANCE = 0.001


def is_player_line(line: str) -> bool:
    return line.startswith("001")


def start_rank(line: str) -> int:
    return _int_or_zero(field(line, START_RANK))


def player_label(line: str) -> str:
    """Nome do jogador na linha 001, para o aviso citar quem é."""
    return field(line, NAME)


def declared_points(line: str) -> float:
    """Pontos que a linha 001 declara — os mesmos da classificação publicada."""
    return _float_or_zero(field(line, POINTS))


def cell_points(cell: str) -> float:
    """Pontos da célula na leitura do Gacrux."""
    letter = cell[CELL_RESULT] if len(cell) > CELL_RESULT else " "
    return TRF_LETTER_POINTS.get(letter.upper(), 0.0)


def implied_points(line: str) -> float:
    """Pontos que o Gacrux vai somar lendo as células desta linha."""
    return round(sum(cell_points(cell) for cell in cell_blocks(line)), 2)


def entry_gap_rounds(line: str) -> list[int]:
    """Rodadas iniciais em que o jogador não estava no torneio.

    É o prefixo de células sem adversário e sem ponto (`0000 - Z`), que é como o
    exportador representa quem ainda não tinha se inscrito. Só o PREFIXO: um
    `0000 - Z` no meio do torneio é bye de zero ponto pedido ao árbitro (ARB-04)
    ou rodada de retirada (ARB-05), e reescrevê-lo seria desfazer uma decisão
    dele.
    """
    gaps: list[int] = []
    for number, cell in enumerate(cell_blocks(line), start=1):
        if _int_or_zero(cell[CELL_OPPONENT[0]:CELL_OPPONENT[1]]) != 0 or cell_points(cell) != 0.0:
            break
        gaps.append(number)
    return gaps


def compensation_letters(deficit: float, slots: int) -> list[str] | None:
    """Letras que somam `deficit` em até `slots` rodadas, ou None se não fecha.

    Prefere meios pontos (`H`) e só usa ponto inteiro (`F`) quando o déficit não
    cabe em meios — ver `COMPENSATION_LETTERS`.
    """
    if deficit <= _TOLERANCE or slots <= 0:
        return None
    (half_letter, half), (full_letter, full) = COMPENSATION_LETTERS
    for fulls in range(0, slots + 1):
        remaining = deficit - fulls * full
        if remaining < -_TOLERANCE:
            break
        halves = remaining / half
        if abs(halves - round(halves)) > _TOLERANCE:
            continue
        halves = int(round(halves))
        if fulls + halves <= slots:
            return [full_letter] * fulls + [half_letter] * halves
    return None


def with_round_cells(line: str, letters_by_round: dict[int, str]) -> str:
    """Linha 001 com as células das rodadas dadas trocadas por bye de `letra`."""
    if not letters_by_round:
        return line
    patched = line
    for number, letter in letters_by_round.items():
        start = cell_start(number)
        if start > len(patched):
            continue  # rodada que nem existe no arquivo
        patched = patched[:start] + f"0000 - {letter}  " + patched[start + ROUND_CELL_WIDTH:]
    return patched.rstrip()


def reconcile_scores(lines: Sequence[str]) -> tuple[list[str], list[str]]:
    """Faz as células baterem com os pontos declarados na linha 001.

    O exportador já escreve na linha 001 os pontos da CLASSIFICAÇÃO (que incluem
    `starting_points` e ajustes de pontos), mas o Gacrux ignora esse campo e soma
    as células. A diferença entre os dois é exatamente o que não chegava ao
    motor; aqui ela vira células de bye nas rodadas anteriores à inscrição.

    Devolve as linhas ajustadas e os avisos do que sobrou por representar —
    déficit negativo (o motor pareia com MAIS pontos do que a classificação
    mostra) ou déficit que não cabe nas rodadas de ausência.
    """
    patched: list[str] = []
    warnings: list[str] = []
    for line in lines:
        if not is_player_line(line):
            patched.append(line)
            continue
        deficit = round(declared_points(line) - implied_points(line), 2)
        if abs(deficit) <= _TOLERANCE:
            patched.append(line)
            continue
        gaps = entry_gap_rounds(line)
        letters = compensation_letters(deficit, len(gaps)) if deficit > 0 else None
        if letters is None:
            warnings.append(_divergence_warning(line, deficit))
            patched.append(line)
            continue
        patched.append(with_round_cells(line, dict(zip(gaps, letters))))
    return patched, warnings


def _divergence_warning(line: str, deficit: float) -> str:
    return (
        f"Gacrux vai parear {player_label(line) or f'SNo {start_rank(line)}'} com "
        f"{implied_points(line):g} ponto(s), e a classificacao mostra "
        f"{declared_points(line):g} (diferenca de {deficit:+g}). O motor FIDE soma "
        "as rodadas do arquivo TRF, e esta diferenca nao cabe nas rodadas de "
        "ausencia do jogador."
    )


# ---------------------------------------------------------------------------- #
# Aceleração
# ---------------------------------------------------------------------------- #


def bonus_is_expressible(bonus: float) -> bool:
    """O bônus configurado sobrevive à viagem pelo registro 250?"""
    return any(abs(float(bonus) - value) <= _TOLERANCE for value in EXPRESSIBLE_BONUSES)


def rank_ranges(start_ranks: Iterable[int]) -> list[tuple[int, int]]:
    """Agrupa start-ranks em faixas contíguas `[primeiro, último]`.

    O registro 250 fala por FAIXA de competidor, e a metade acelerada é contígua
    só quando a ordem inicial do torneio é a mesma do start-rank do TRF (que sai
    por rating). Com ordem inicial manual ou por rating nacional as faixas saem
    picadas — e é por isso que elas são calculadas, não assumidas.
    """
    ordered = sorted({int(rank) for rank in start_ranks if int(rank) > 0})
    ranges: list[tuple[int, int]] = []
    for rank in ordered:
        if ranges and rank == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], rank)
        else:
            ranges.append((rank, rank))
    return ranges


def acceleration_records(
    bonus: float,
    round_number: int,
    start_ranks: Iterable[int],
) -> list[str]:
    """Registros 250 (sem quebra de linha) que aceleram esta rodada.

    Só a rodada que está sendo pareada: o arquivo é gerado a cada rodada e o
    conjunto acelerado depende de quem está sendo pareado nela. Match points
    ficam em branco — são de equipes; o pareamento individual lê os game points.
    """
    if not bonus_is_expressible(bonus):
        return []
    return [
        record_250(0.0, float(bonus), int(round_number), int(round_number), [first, last]).rstrip("\r\n")
        for first, last in rank_ranges(start_ranks)
    ]


def acceleration_ignored_warning(bonus: float) -> str:
    return (
        f"Aceleracao de {bonus:g} ponto(s) nao e representavel no arquivo do motor "
        "FIDE (o registro 250 so transporta 0,5 ou 1,0). Esta rodada foi pareada "
        "pelo motor proprio, que aplica o bonus configurado."
    )


def _int_or_zero(text: str) -> int:
    try:
        return int(str(text).strip() or 0)
    except ValueError:
        return 0


def _float_or_zero(text: Any) -> float:
    try:
        return float(str(text).strip() or 0.0)
    except ValueError:
        return 0.0
