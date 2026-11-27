"""Regras PURAS das ações na linha do jogador (RGS-22, RGS-23, RGS-24).

Três perguntas que o árbitro faz apontando para um jogador, e que antes não
tinham resposta numa linha:

- **quanto do regulamento de bye ele já usou** ("1 de 2 byes usados; último
  permitido na R5") — o saldo da `bye_policy`, sem duplicar a regra;
- **qual W.O. lançar** quando a rodada da ausência já foi gerada e ele tem mesa;
- **em que rodada entra quem chega tarde**, e com quantos pontos.

Sobre a entrada tardia (RGS-24): as rodadas 1…N−1 do entrante **não são
gravadas** em lugar nenhum. Elas são células derivadas — o exportador TRF as
escreve como `Z`/`H`/`F` a partir dos ``starting_points`` (`reconcile_scores`,
em `gacrux_trf.py`). Por isso o valor por rodada só pode ser 0, ½ ou 1: é o que
uma célula consegue dizer ao motor. Nada entra em rodada fechada e o limite de
byes solicitados fica intacto — a `bye_policy` (seção 8 da espec) não muda.

Sem banco e sem Tk: quem grava é o serviço, quem desenha é a tela.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.services.pairing.bye_policy import ByePolicy, count_limited
from src.services.pairing.incidents import forfeit_result

# Valores por rodada que uma célula do TRF representa: Z (0), H (½), F (1).
LATE_ENTRY_CELL_POINTS = (0.0, 0.5, 1.0)


def bye_balance(policy: ByePolicy, byes: Sequence[Mapping[str, Any]]) -> str:
    """O saldo do jogador numa linha, na língua do salão.

    Conta só o que a política conta (F e H — o Z não entra no limite, ver
    ``count_limited``), e diz a última rodada aceita quando o regulamento tem.
    """
    usados = count_limited(byes)
    if policy.max_requested_byes:
        plural = "" if policy.max_requested_byes == 1 else "s"
        saldo = f"{usados} de {policy.max_requested_byes} bye{plural} usado{plural}"
    elif not policy.last_requested_bye_round:
        quantos = "nenhum usado" if not usados else (
            "1 usado" if usados == 1 else f"{usados} usados"
        )
        return f"Sem limite de byes; {quantos}"
    else:
        saldo = f"{usados} bye usado" if usados == 1 else f"{usados} byes usados"
    if policy.last_requested_bye_round:
        return f"{saldo}; último permitido na R{policy.last_requested_bye_round}"
    return saldo


def walkover_result(pairing: Mapping[str, Any], player_id: int) -> str:
    """O W.O. CONTRA quem faltou: ``0F-1F`` se ele era das brancas."""
    return forfeit_result(int(pairing.get("white_player_id") or 0) == int(player_id))


@dataclass(frozen=True)
class LateEntryPlan:
    """Onde e com quanto o entrante tardio começa. ``error`` vazio = pode."""

    entry_round: int
    rounds_count: int
    per_round_points: float
    missed_rounds: list[int] = field(default_factory=list)
    error: str = ""

    @property
    def starting_points(self) -> float:
        return round(self.per_round_points * len(self.missed_rounds), 2)


def late_entry_points_error(per_round_points: float) -> str:
    """Por que este valor por rodada não serve. ``""`` quando serve."""
    if any(abs(float(per_round_points) - valor) < 1e-9 for valor in LATE_ENTRY_CELL_POINTS):
        return ""
    return (
        "Pontos por rodada perdida precisam ser 0, ½ ou 1: é o que o arquivo do "
        "motor FIDE consegue registrar (bye Z, H ou F). Ajuste o valor em "
        "Configurações do torneio."
    )


def _entry_round(latest_round_number: int, join_open_round: bool) -> int:
    """A seguinte à última gerada; com "jogar já" e rodada aberta, a própria aberta."""
    if join_open_round and latest_round_number > 0:
        return latest_round_number
    return latest_round_number + 1


def _no_round_left_error(entry_round: int, rounds_count: int) -> str:
    if rounds_count and entry_round > rounds_count:
        return (
            f"O torneio já gerou todas as rodadas ({rounds_count}): não há rodada para "
            "o jogador entrar."
        )
    return ""


def late_entry_plan(
    *,
    latest_round_number: int,
    rounds_count: int,
    per_round_points: float,
    join_open_round: bool = False,
    latest_round_open: bool = False,
) -> LateEntryPlan:
    """A rodada de entrada é a seguinte à última GERADA (RGS-10/RGS-24).

    Rodada gerada já foi pareada: quem chega durante a R4 não entra nela — entra
    na R5, e a R4 conta como perdida, igual às anteriores.

    ``join_open_round`` é o "jogar já nesta rodada" do Modo Amistoso (MA-04):
    com a última rodada ABERTA, ela é a de entrada e será refeita com o aluno
    (``FriendlyModeService.late_entry``). Sem rodada aberta, nada muda.
    """
    entrada = _entry_round(int(latest_round_number or 0), join_open_round and latest_round_open)
    total = int(rounds_count or 0)
    pontos = float(per_round_points or 0.0)
    erro = late_entry_points_error(pontos) or _no_round_left_error(entrada, total)
    return LateEntryPlan(
        entry_round=entrada,
        rounds_count=total,
        per_round_points=pontos,
        missed_rounds=list(range(1, entrada)),
        error=erro,
    )
