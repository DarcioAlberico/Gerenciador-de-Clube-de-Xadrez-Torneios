"""Opções do seletor de plano de um lançamento financeiro (puro).

A lista de planos do combo vinha só de `list_membership_plans(active_only=True)`.
Parece razoável — não se cria cobrança nova num plano desativado — mas o combo
também é usado para EDITAR uma cobrança que já existe, e aí o plano dela pode ter
sido inativado depois. Como o rótulo não estava na lista, o seletor caía em "Sem
plano" e qualquer "Salvar lançamento" gravava `plan_id = NULL` sem aviso.

O estrago não era só o recibo perder o plano. A trava anti-duplicação de
mensalidade é `(member_id, plan_id, reference_period)`: com a cobrança órfã, ela
deixa de reconhecer o que já existe, e o mesmo sócio recebe uma SEGUNDA cobrança
da mesma referência assim que o plano for reativado.

Aqui o plano do lançamento aberto entra na lista mesmo inativo, marcado como
tal — o árbitro vê que aquele plano não aceita cobrança nova, e o dado não se
perde por causa disso.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

NO_PLAN_LABEL = "Sem plano"
INACTIVE_SUFFIX = " (inativo)"


def plan_label(plan: Mapping[str, Any], *, inactive: bool = False) -> str:
    rotulo = f"{plan['id']} - {plan.get('name', '')} ({plan.get('amount', '')})"
    return f"{rotulo}{INACTIVE_SUFFIX}" if inactive else rotulo


def plan_options(
    active_plans: Sequence[Mapping[str, Any]],
    current_plan: Mapping[str, Any] | None = None,
) -> tuple[list[str], dict[str, int | None]]:
    """`(rótulos, rótulo -> id)` para o seletor de plano.

    `current_plan` é o plano do lançamento aberto. Se ele não estiver entre os
    ativos, entra assim mesmo, marcado `(inativo)`: cobrança existente não pode
    perder o plano só porque ele saiu de linha.
    """
    rotulos: list[str] = [NO_PLAN_LABEL]
    mapa: dict[str, int | None] = {NO_PLAN_LABEL: None}

    for plano in active_plans:
        rotulo = plan_label(plano)
        rotulos.append(rotulo)
        mapa[rotulo] = int(plano["id"])

    if current_plan is not None:
        atual = int(current_plan["id"])
        if atual not in mapa.values():
            rotulo = plan_label(current_plan, inactive=True)
            rotulos.append(rotulo)
            mapa[rotulo] = atual

    return rotulos, mapa


def selected_label(mapa: Mapping[str, int | None], plan_id: int | None) -> str:
    """Rótulo correspondente ao plano do lançamento, ou "Sem plano"."""
    if not plan_id:
        return NO_PLAN_LABEL
    return next(
        (rotulo for rotulo, identificador in mapa.items() if identificador == int(plan_id)),
        NO_PLAN_LABEL,
    )
