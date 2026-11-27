"""Ajustes do TRF que alimenta o motor Gacrux — funções puras (PAR-02).

O Gacrux recebe o torneio como TRF-16 e **recalcula tudo a partir das células de
rodada da linha 001**. Duas decisões que o Albericus toma fora das células não
chegavam nele, e sumiam sem aviso justamente porque o Gacrux é o motor padrão:

- a **aceleração** (pontos fictícios de pareamento) só existia no motor próprio;
- os **pontos de entrada tardia** (`starting_points`) aparecem no campo de pontos
  da linha 001, mas as rodadas anteriores à inscrição saem como `0000 - Z`
  (zero ponto). O entrante tardio era pareado num grupo de pontuação diferente
  do que a classificação publica.

- o **valor do PAB** (`bye_points`) e os **ajustes de pontos** do árbitro: o
  `U` valia sempre 1 ponto e o ajuste nem aparecia nas células (RGS-03).

Este módulo não lê banco nem arquivo: recebe as **linhas** do TRF já geradas pelo
exportador e devolve as linhas ajustadas mais os avisos do que não deu para
representar. Quem faz I/O é o `GacruxEngine`.

Dialeto: a tabela de letras é a do parser que vai ler o arquivo
(`gacrux/trf2json.py`, `self.results`, resolvida em `gacrux/scoresystem.py`,
`default_score["game"]`) — é ele quem define o que cada célula vale, e não a
nossa leitura da spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, Iterable, Mapping, Sequence

from src.services.federation_exporters.trf25_records import (
    record_162,
    record_250,
    record_260,
    record_299,
)
from src.services.pairing.prohibitions import prohibited_pairs_for_round
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

# Valores de PAB que o Gacrux representa: ele lê o `P` do registro 162 e o traduz
# para o código W/D/L/Z de MESMO valor (`scoresystem.update_gamescore`). Outro
# valor não tem tradução e derruba o motor — recusamos antes (RGS-03).
REPRESENTABLE_PAB_POINTS: tuple[float, ...] = (0.0, 0.5, 1.0)

# Sistema de pontos individual padrão FIDE (TRF25 §1.1), sem o PAB.
STANDARD_GAME_POINTS: tuple[tuple[str, float], ...] = (
    ("W", 1.0), ("D", 0.5), ("L", 0.0), ("A", 0.0),
)


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


def cell_points(cell: str, pab_points: float = 1.0) -> float:
    """Pontos da célula na leitura do Gacrux, com o PAB valendo `pab_points`."""
    letter = (cell[CELL_RESULT] if len(cell) > CELL_RESULT else " ").upper()
    if letter == "U":
        return float(pab_points)
    return TRF_LETTER_POINTS.get(letter, 0.0)


def implied_points(line: str, pab_points: float = 1.0) -> float:
    """Pontos que o Gacrux vai somar lendo as células desta linha."""
    return round(sum(cell_points(cell, pab_points) for cell in cell_blocks(line)), 2)


def with_declared_points(line: str, points: float) -> str:
    """Linha 001 com o campo de pontos (81-84) trocado por `points`."""
    start, end = POINTS
    return line[:start] + f"{float(points):>4.1f}"[-(end - start):] + line[end:]


# ---------------------------------------------------------------------------- #
# Sistema de pontos e ajustes (RGS-03)
# ---------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PairingScore:
    """O que o arquivo do pareamento diz ao motor sobre a pontuação.

    - `pab_points`: valor do PAB, que vai no registro 162 (TRF25 §1.1, `P`);
    - `adjustments`: start-rank -> pontos que o Gacrux soma pelos 299 desta
      rodada; as células da linha 001 ficam só com o resto;
    - `adjustment_lines`: os registros 299 (TRF25 §7.3), sem quebra de linha.
    """

    pab_points: float = 1.0
    adjustments: Mapping[int, float] = dataclass_field(default_factory=dict)
    adjustment_lines: tuple[str, ...] = ()

    @property
    def pab_representable(self) -> bool:
        return any(
            abs(float(self.pab_points) - value) <= _TOLERANCE
            for value in REPRESENTABLE_PAB_POINTS
        )

    def records(self) -> list[str]:
        """Registros 162 e 299 que entram no arquivo do pareamento.

        PAB sem representação sai do 162 (fica o padrão do motor): só serve
        enquanto ninguém recebeu PAB — depois disso `reconcile_scores` recusa.
        """
        pab = float(self.pab_points) if self.pab_representable else None
        return [score_system_record(pab), *self.adjustment_lines]


def score_system_record(pab_points: float | None) -> str:
    """Registro 162 (sem quebra de linha) com o PAB valendo `pab_points`.

    Sai SEMPRE no arquivo do pareamento, mesmo no padrão: com o 162 o Gacrux usa
    o sistema declarado; sem ele, DEDUZ o sistema das células e dos pontos da
    linha 001 — e foi essa dedução que quebrou com o bye de 0,5 (`KeyError`).
    `X` (resultado desconhecido) vale um empate, como no padrão da TRF25.
    `pab_points=None` omite o `P`.
    """
    pab = [] if pab_points is None else [("P", float(pab_points))]
    return record_162([*STANDARD_GAME_POINTS, *pab, ("X", 0.5)]).rstrip("\r\n")


def pairing_score(
    pab_points: float,
    adjustment_rows: Iterable[Mapping[str, Any]],
    rank_by_player: Mapping[int, int],
    round_number: int,
) -> PairingScore:
    """Monta o `PairingScore` para parear `round_number`.

    `adjustment_rows` são as linhas da tabela `point_adjustments`; só as de
    jogador contam (o pareamento é individual). Um ajuste só chega ao motor se
    for de rodada já disputada (o Gacrux soma o 299 a partir da rodada dele) e
    se o valor couber no campo `[-]11.5` do registro; os outros ficam fora — a
    classificação continua contando com eles, e a checagem acusa a diferença.
    """
    totals: dict[int, float] = {}
    lines: list[str] = []
    for row in adjustment_rows:
        rank = rank_by_player.get(int(row.get("player_id") or 0))
        points = round(float(row.get("game_points") or 0.0), 2)
        played_round = int(row.get("round_number") or 0)
        if not rank or abs(points) <= _TOLERANCE:
            continue
        if played_round >= int(round_number) or not _fits_299(points):
            continue
        totals[rank] = round(totals.get(rank, 0.0) + points, 2)
        lines.append(record_299("", 0.0, points, played_round, [rank]).rstrip("\r\n"))
    return PairingScore(
        pab_points=float(pab_points),
        adjustments=totals,
        adjustment_lines=tuple(lines),
    )


def _fits_299(points: float) -> bool:
    """O valor sobrevive ao campo `[-]11.5` (4 colunas, uma casa decimal)?"""
    return abs(round(points, 1) - points) <= _TOLERANCE and -9.9 <= points <= 99.9


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


def reconcile_scores(
    lines: Sequence[str],
    score: PairingScore | None = None,
) -> tuple[list[str], list[str]]:
    """Faz o que o Gacrux soma bater com os pontos declarados na linha 001.

    O exportador já escreve na linha 001 os pontos da CLASSIFICAÇÃO (que incluem
    `starting_points`, o valor do PAB e ajustes de pontos), mas o Gacrux ignora
    esse campo e soma as células — com o PAB valendo `score.pab_points` (162) —
    mais os ajustes do 299 (`score.adjustments`). O que sobra vira células de
    bye nas rodadas anteriores à inscrição.

    Com o 162 no arquivo, o Gacrux confere o campo de pontos contra a soma das
    células e PARA se divergirem; por isso, quando há ajuste, o campo passa a
    declarar só a parte das células (o 299 leva o resto).

    Devolve as linhas ajustadas e os avisos do que sobrou por representar —
    déficit negativo (o motor pareia com MAIS pontos do que a classificação
    mostra) ou déficit que não cabe nas rodadas de ausência.
    """
    score = score or PairingScore()
    patched: list[str] = []
    warnings: list[str] = []
    for line in lines:
        if not is_player_line(line):
            patched.append(line)
            continue
        if not score.pab_representable and _has_pab_cell(line):
            warnings.append(_pab_warning(line, score.pab_points))
            patched.append(line)
            continue
        adjustment = float(score.adjustments.get(start_rank(line), 0.0))
        target = round(declared_points(line) - adjustment, 2)
        if abs(adjustment) > _TOLERANCE:
            line = with_declared_points(line, target)
        deficit = round(target - implied_points(line, score.pab_points), 2)
        if abs(deficit) <= _TOLERANCE:
            patched.append(line)
            continue
        gaps = entry_gap_rounds(line)
        letters = compensation_letters(deficit, len(gaps)) if deficit > 0 else None
        if letters is None:
            warnings.append(_divergence_warning(line, deficit, score, adjustment))
            patched.append(line)
            continue
        patched.append(with_round_cells(line, dict(zip(gaps, letters))))
    return patched, warnings


def rebased_score_lines(
    lines: Sequence[str],
    score: PairingScore,
    starting_points_by_rank: Mapping[int, float],
) -> tuple[list[str], list[str]]:
    """Linhas do TRF com o placar que a classificação conta, pelas CÉLULAS.

    Serve ao TRF do DESEMPATE (RGS-03) e ao da VERIFICAÇÃO (RGS-16).

    É a mesma reconciliação do pareamento (162 + 299 + rodadas de ausência),
    com uma diferença: o campo de pontos que o exportador escreve é o de HOJE,
    e o TRF do desempate pode estar recortado numa rodada anterior (retrato).
    Por isso o alvo de cada linha 001 é recalculado a partir das células do
    recorte — PAB pelo `score.pab_points` —, mais os ajustes de rodada já
    disputada (`score.adjustments`) e os pontos de entrada tardia.

    Devolve as linhas com os registros 162/299 no fim e os avisos do que o
    arquivo não consegue representar (o chamador recusa o Gacrux com eles).
    """
    rebased: list[str] = []
    for line in lines:
        if line[:3] in {"162", "299"}:
            continue
        if is_player_line(line):
            rank = start_rank(line)
            target = (
                implied_points(line, score.pab_points)
                + float(score.adjustments.get(rank, 0.0))
                + float(starting_points_by_rank.get(rank, 0.0) or 0.0)
            )
            line = with_declared_points(line, round(target, 2))
        rebased.append(line)
    patched, warnings = reconcile_scores(rebased, score)
    return [*patched, *score.records()], warnings


def _has_pab_cell(line: str) -> bool:
    return any(
        len(cell) > CELL_RESULT and cell[CELL_RESULT].upper() == "U"
        for cell in cell_blocks(line)
    )


def _pab_warning(line: str, pab_points: float) -> str:
    return (
        f"{player_label(line) or f'SNo {start_rank(line)}'} recebeu o bye alocado "
        f"pelo pareamento (PAB), que neste torneio vale {float(pab_points):g} ponto(s); "
        "o motor FIDE só representa PAB de 0, 0.5 ou 1 ponto (registro 162)."
    )


def _divergence_warning(
    line: str,
    deficit: float,
    score: PairingScore,
    adjustment: float,
) -> str:
    seen = implied_points(line, score.pab_points) + adjustment
    return (
        f"Gacrux vai parear {player_label(line) or f'SNo {start_rank(line)}'} com "
        f"{seen:g} ponto(s), e a classificação mostra {seen + deficit:g} "
        f"(diferença de {deficit:+g}). O arquivo TRF não consegue dizer esta "
        "diferença ao motor: ela não cabe nas rodadas de ausência do jogador nem "
        "num ajuste de pontos de rodada já disputada (registro 299)."
    )


# ---------------------------------------------------------------------------- #
# Aceleração
# ---------------------------------------------------------------------------- #


def bonus_is_expressible(bonus: float) -> bool:
    """O bônus configurado sobrevive à viagem pelo registro 250?"""
    return any(abs(float(bonus) - value) <= _TOLERANCE for value in EXPRESSIBLE_BONUSES)


def rank_ranges(start_ranks: Iterable[int]) -> list[tuple[int, int]]:
    """Agrupa start-ranks em faixas contíguas `[primeiro, último]`.

    O registro 250 fala por FAIXA de competidor. Desde o RGS-13 o start-rank do
    TRF É a ordem inicial (`seeding_key`), então a metade acelerada sai
    contígua; as faixas continuam calculadas, não assumidas — o conjunto
    acelerado da rodada é só de quem está sendo pareado nela.
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
        f"Aceleração de {bonus:g} ponto(s) não é representável no arquivo do motor "
        "FIDE (o registro 250 só transporta 0,5 ou 1,0). Esta rodada foi pareada "
        "pelo motor próprio, que aplica o bônus configurado."
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


# ---------------------------------------------------------------------------- #
# Proibições (RGS-15)
# ---------------------------------------------------------------------------- #


def prohibition_records(
    prohibitions: Iterable[Mapping[str, Any]],
    round_number: int,
    rank_by_player: Mapping[int, int],
) -> list[str]:
    """Registros 260 (sem quebra de linha) das proibições que valem na rodada.

    TRF25 §5.2. O Gacrux marca cada par do registro como `canmeet = False`
    (`crosstable.list_edges`) — o mesmo bloqueio absoluto de um reencontro.
    Sai sempre `first = last = round_number`: o Gacrux lê `lastRound = 0`
    como "só a primeira rodada", e no Albericus `last_round = 0` é "até o
    fim"; o arquivo é gerado a cada rodada, então basta a rodada pareada.
    Proibição com jogador que não está no arquivo fica de fora.
    """
    records: list[str] = []
    seen: set[tuple[int, int]] = set()
    for pair in sorted(
        prohibited_pairs_for_round(list(prohibitions), int(round_number)),
        key=lambda item: sorted(item),
    ):
        ranks = sorted(int(rank_by_player.get(int(pid), 0)) for pid in pair)
        if len(ranks) != 2 or not all(ranks) or tuple(ranks) in seen:
            continue
        seen.add((ranks[0], ranks[1]))
        records.append(record_260(int(round_number), int(round_number), ranks).rstrip("\r\n"))
    return records
