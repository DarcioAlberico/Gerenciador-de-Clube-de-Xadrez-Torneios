"""Política PURA de byes solicitados (ARB-04).

Um bye solicitado é o jogador avisando que não jogará uma rodada. Até aqui ele
era gravado direto da tela no banco (`db.add_requested_bye`), sem passar por
serviço nenhum — e o que se validava era o FORMATO do formulário (tem alvo? tem
rodada? o tipo é F/H/Z?). Não havia onde uma política morar, e por isso quatro
coisas davam errado em silêncio:

- pedido para rodada já gerada ou fechada era aceito e **nunca aplicado**;
- pedido de jogador inativo era descartado na hora de parear, sem avisar;
- não havia limite por jogador, que todo regulamento tem;
- não havia última rodada permitida — o meio-ponto na rodada final é o caso que
  os regulamentos proíbem primeiro, porque decide classificação sem jogo.

Aqui só as regras e os textos. Quem grava é o serviço; quem desenha é a tela.

Sobre o `disable_bye`: ele NÃO entra aqui. Aquela flag desativa o bye ALOCADO
(o PAB, que o sistema dá a quem sobra num número ímpar), e um bye solicitado é
outra coisa — o jogador avisou que faltaria. Conflatar os dois quebraria o
torneio que exige número par de presentes mas aceita ausência avisada, que é
justamente o regulamento mais comum.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.services.constants import REQUESTED_BYE_POINTS

# Tipos de bye que contam para o limite. O zero-ponto (`Z`) não conta: ele não
# dá ponto nenhum, então limitá-lo seria punir quem avisou que faltaria em vez
# de simplesmente não aparecer.
LIMITED_BYE_TYPES = frozenset({"F", "H"})


@dataclass(frozen=True)
class ByePolicy:
    """Regras do torneio para bye solicitado. ``0`` significa "sem limite"."""

    max_requested_byes: int = 0
    last_requested_bye_round: int = 0

    @classmethod
    def from_settings(cls, settings: Mapping[str, Any] | None) -> "ByePolicy":
        dados = settings or {}
        return cls(
            max_requested_byes=_as_int(dados.get("max_requested_byes")),
            last_requested_bye_round=_as_int(dados.get("last_requested_bye_round")),
        )

    @property
    def has_limits(self) -> bool:
        return bool(self.max_requested_byes or self.last_requested_bye_round)

    def describe(self) -> str:
        """Uma linha para a tela e para a ata. ``""`` quando não há limite."""
        partes = []
        if self.max_requested_byes:
            plural = "" if self.max_requested_byes == 1 else "s"
            partes.append(f"maximo de {self.max_requested_byes} bye{plural} por jogador")
        if self.last_requested_bye_round:
            partes.append(f"ultima rodada permitida: {self.last_requested_bye_round}")
        return "; ".join(partes)


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def request_error(
    policy: ByePolicy,
    *,
    bye_type: str,
    round_number: int,
    rounds_count: int,
    round_status: str | None,
    player_active: bool,
    existing_byes: Sequence[Mapping[str, Any]] = (),
    editing_existing: bool = False,
) -> str:
    """Por que ESTE pedido não pode ser aceito. ``""`` quando pode.

    ``round_status`` é ``None`` quando a rodada ainda não existe — o único caso
    em que o bye tem como ser aplicado. ``existing_byes`` são os pedidos que o
    jogador já tem no torneio (o da própria rodada é ignorado na contagem, senão
    corrigir o tipo de um bye existente esbarraria no limite).
    """
    if str(bye_type or "").strip().upper() not in REQUESTED_BYE_POINTS:
        return "Tipo de bye invalido (use F, H ou Z)."
    if round_number <= 0:
        return "Informe a rodada do bye."
    if rounds_count and round_number > rounds_count:
        return (
            f"O torneio tem {rounds_count} rodada(s): nao existe rodada {round_number}."
        )
    if not player_active:
        return (
            "Jogador inativo nao recebe bye solicitado. Reative o jogador antes de "
            "registrar o pedido — senao o bye seria descartado na geracao da rodada, "
            "sem aviso."
        )
    if round_status == "closed":
        return (
            f"A rodada {round_number} ja foi fechada. Um bye so vale antes de a rodada "
            "ser gerada; para mexer no que ja aconteceu, use a correcao com motivo."
        )
    if round_status is not None:
        return (
            f"A rodada {round_number} ja foi gerada, e o pareamento dela ja esta feito. "
            "O bye precisa ser registrado ANTES de gerar a rodada, senao ele e aceito "
            "e nunca aplicado."
        )
    if policy.last_requested_bye_round and round_number > policy.last_requested_bye_round:
        return (
            f"O regulamento do torneio aceita bye solicitado ate a rodada "
            f"{policy.last_requested_bye_round}."
        )
    if policy.max_requested_byes:
        usados = count_limited(existing_byes, skip_round=round_number if editing_existing else None)
        conta = str(bye_type or "").strip().upper() in LIMITED_BYE_TYPES
        if conta and usados >= policy.max_requested_byes:
            plural = "" if policy.max_requested_byes == 1 else "s"
            return (
                f"O jogador ja usou {usados} de {policy.max_requested_byes} bye{plural} "
                "permitido(s) no torneio."
            )
    return ""


def count_limited(
    byes: Sequence[Mapping[str, Any]],
    skip_round: int | None = None,
) -> int:
    """Quantos byes do jogador contam para o limite (F e H; `Z` não conta)."""
    return sum(
        1
        for item in byes
        if str(item.get("bye_type") or "").strip().upper() in LIMITED_BYE_TYPES
        and (skip_round is None or int(item.get("round_number") or 0) != int(skip_round))
    )


def discarded_warning(discarded: Sequence[Mapping[str, Any]]) -> str:
    """Aviso dos byes que a geração da rodada teve de descartar. ``""`` se nenhum.

    Descartar em silêncio é o defeito: o jogador avisou que faltaria, o árbitro
    registrou, e na hora de parear o pedido sumia porque o jogador estava
    inativo. Quem lê o aviso decide — reativar o jogador ou aceitar a ausência.
    """
    nomes = [str(item.get("player_name") or f"#{item.get('player_id')}") for item in discarded]
    if not nomes:
        return ""
    quantos = len(nomes)
    plural = "bye solicitado foi descartado" if quantos == 1 else "byes solicitados foram descartados"
    return (
        f"{quantos} {plural} nesta rodada porque o jogador esta inativo: "
        + ", ".join(nomes)
        + "."
    )
