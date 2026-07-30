"""Ajustes de pontos do árbitro (TRF25 §7.3) somados à classificação.

Módulo **puro**: recebe as linhas da tabela ``point_adjustments`` como elas vêm
do banco e devolve o total por competidor mais o texto que explica o total.
Quem lê o banco é o ``PairingService``; quem ordena é o ``tiebreaks.py``.

Por que o ajuste é aplicado aqui e não pelo motor de desempate: o Gacrux não
conhece a tabela. No individual ele recebe um TRF-16, que **não tem** registro
299; no de equipes o TRF-25 tem, mas o parser do motor (``parse_trf_abnormal``)
trata o registro como redefinição do sistema de pontos, não como penalidade
nominal. Então o ajuste é somado pelo Albericus **por cima** do que o motor
devolveu — que é a primeira das duas saídas previstas na TBK-01.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class AdjustmentEntry:
    """Um lançamento do árbitro, já normalizado."""

    round_number: int
    aat_type: str
    match_points: float
    game_points: float
    reason: str


@dataclass(frozen=True)
class AdjustmentTotal:
    """Soma dos lançamentos de um competidor, com os lançamentos que a formam."""

    match_points: float
    game_points: float
    entries: tuple[AdjustmentEntry, ...]

    def moves_standings(self) -> bool:
        """Há delta de pontos? Lançamento só de tipo (W/D/L…) não move nada."""
        return bool(self.match_points) or bool(self.game_points)


def aggregate_player_adjustments(
    rows: Iterable[Mapping[str, Any]],
) -> dict[int, AdjustmentTotal]:
    """``{player_id: AdjustmentTotal}``. Só game points contam no individual.

    Match points são grandeza de equipe — o próprio formulário do painel já os
    zera para jogador (``AdjustmentForm.match_points``), e aqui a regra é
    repetida para que a classificação não dependa de quem preencheu a linha.
    """
    return _aggregate(rows, "player_id", keep_match_points=False)


def aggregate_team_adjustments(
    rows: Iterable[Mapping[str, Any]],
) -> dict[int, AdjustmentTotal]:
    """``{team_id: AdjustmentTotal}``. Equipes usam match points e game points."""
    return _aggregate(rows, "team_id", keep_match_points=True)


def _aggregate(
    rows: Iterable[Mapping[str, Any]],
    target_key: str,
    *,
    keep_match_points: bool,
) -> dict[int, AdjustmentTotal]:
    match_totals: dict[int, float] = {}
    game_totals: dict[int, float] = {}
    entries: dict[int, list[AdjustmentEntry]] = {}

    for row in rows:
        target_id = int(row.get(target_key) or 0)
        if not target_id:
            continue
        match_points = float(row.get("match_points") or 0.0) if keep_match_points else 0.0
        game_points = float(row.get("game_points") or 0.0)
        match_totals[target_id] = match_totals.get(target_id, 0.0) + match_points
        game_totals[target_id] = game_totals.get(target_id, 0.0) + game_points
        entries.setdefault(target_id, []).append(
            AdjustmentEntry(
                round_number=int(row.get("round_number") or 0),
                aat_type=str(row.get("aat_type") or "").strip().upper(),
                match_points=match_points,
                game_points=game_points,
                reason=str(row.get("reason") or "").strip(),
            )
        )

    return {
        target_id: AdjustmentTotal(
            match_points=round(match_totals[target_id], 2),
            game_points=round(game_totals[target_id], 2),
            entries=tuple(items),
        )
        for target_id, items in entries.items()
    }


def format_signed(value: float) -> str:
    """Pontos com sinal e vírgula decimal: ``-0,5``, ``+1``, ``+2,25``."""
    rounded = round(float(value or 0.0), 2)
    text = f"{rounded:+.2f}".rstrip("0").rstrip(".")
    if text in ("+", "-"):  # -0.001 arredonda para -0.00
        text = "+0"
    return text.replace(".", ",")


def describe_entry(entry: AdjustmentEntry) -> str:
    """Um lançamento em uma linha: ``-0,5 (rodada 3): celular tocou``.

    A unidade (MP/GP) só é escrita quando há match points — isto é, em torneio
    por equipes. No individual "pontos" é inequívoco e o rótulo seria ruído.
    """
    if entry.match_points:
        delta = f"{format_signed(entry.match_points)} MP"
        if entry.game_points:
            delta += f" / {format_signed(entry.game_points)} GP"
    elif entry.game_points:
        delta = format_signed(entry.game_points)
    else:
        delta = f"tipo {entry.aat_type}" if entry.aat_type else "sem efeito nos pontos"

    if entry.round_number:
        delta += f" (rodada {entry.round_number})"
    return f"{delta}: {entry.reason}" if entry.reason else delta


def adjustment_note(total: AdjustmentTotal | None) -> str:
    """Todos os lançamentos de um competidor em uma linha, separados por ``;``."""
    if total is None:
        return ""
    return "; ".join(describe_entry(entry) for entry in total.entries)


# --- Marcador visual ------------------------------------------------------- #
#
# Definidos aqui, e não em cada tela/relatório, porque a classificação sai por
# muitas portas (tela, PDF, XLSX, CSV, site público, portal ao vivo, ata) e o
# leitor precisa reconhecer o mesmo sinal em todas. Cada porta formata o número
# do seu jeito; o que se compartilha é o sinal e a legenda.

ADJUSTMENT_MARK = "*"
ADJUSTMENT_LEGEND = (
    "* pontuação ajustada por decisão do árbitro (TRF25 §7.3)."
)


def mark_adjusted(text: Any, delta: float) -> str:
    """``"4,5"`` → ``"4,5 *"`` quando houve ajuste; devolve o texto tal qual se não."""
    return f"{text} {ADJUSTMENT_MARK}" if delta else str(text)


def has_adjustment(item: Mapping[str, Any]) -> bool:
    """A linha da classificação (jogador ou equipe) carrega ajuste do árbitro?"""
    return bool(
        float(item.get("adjustment_points") or 0.0)
        or float(item.get("adjustment_match_points") or 0.0)
        or float(item.get("adjustment_game_points") or 0.0)
    )
