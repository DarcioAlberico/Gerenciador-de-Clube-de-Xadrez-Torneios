"""Distribuição de prêmios (spec E4 — Fase C; revisto na ORG-02).

Funções puras, sem banco: recebem a classificação final e a lista de prêmios e
devolvem a alocação por jogador. Trata a repartição entre empatados, a
combinação geral×categoria e a dedução de imposto do organizador.

Prêmios `overall` e `category` são alocados automaticamente a partir da
classificação; `special` e `board` são listados como prêmios manuais (a
definição do ganhador depende de critério externo / dados de equipe).

Duas correções da ORG-02 valem nota:

- **prêmio de categoria casa com TODAS as categorias do jogador**, e não só com
  a principal. Era por isso que o prêmio "Feminino" nunca era alocado sozinho e
  um Sub-12/Sub-1400 concorria a um só;
- **o "Sistema Hort" mudou de lugar.** O que existia aqui combinava geral com
  categoria e não é o Sistema Hort — o Hort é regra de rateio entre EMPATADOS:
  cada um recebe 50% do prêmio da própria posição no desempate mais 50% do bolo
  dividido por igual. Agora ele está onde deveria, e a soma continua fechando
  com o total dos prêmios da faixa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.services.categories import categories_of
from src.services.categories.matching import tag_key

PRIZE_KINDS = {
    "overall": "Geral (colocação)",
    "category": "Categoria",
    "special": "Especial (manual)",
    "board": "Tabuleiro (equipes)",
}

# Combinação geral × categoria. O `hort` saiu daqui: ele nunca foi política de
# combinação (ver o cabeçalho do módulo).
PRIZE_POLICIES = {
    "best_only": "Apenas o maior prêmio",
    "cumulative": "Acumular geral + categoria",
}

# Repartição entre jogadores EMPATADOS na faixa premiada.
PRIZE_TIE_SPLITS = {
    "equal": "Dividir por igual entre empatados",
    "hort": "Sistema Hort (50% da posição + 50% do bolo)",
}

AUTO_KINDS = {"overall", "category"}
MANUAL_KINDS = {"special", "board"}

# Status que não concorrem quando o edital exclui desistentes: só a saída
# DEFINITIVA (desistência) e a expulsão (RGS-35). Avaliado no fim do torneio,
# com o status que o jogador tem quando a premiação é calculada.
WITHDRAWN_STATUSES = {"withdrawn", "desistente", "expelled", "expulso"}

# Status que tiram o jogador do pareamento mas NÃO da premiação: "ausente" é
# quem faltou (glossário, seção 7), não quem desistiu. Como o banco grava
# `active = 0` para todo status diferente de "active", a bandeira sozinha não
# separa os dois — por isso estes status decidem antes dela.
COMPETING_OUT_STATUSES = {"absent", "ausente", "inactive"}


def _prize_band(prize: Mapping[str, Any]) -> tuple[int, int, float]:
    rank_from = int(prize.get("rank_from") or 1)
    rank_to = int(prize.get("rank_to") or rank_from)
    if rank_to < rank_from:
        rank_from, rank_to = rank_to, rank_from
    return max(1, rank_from), max(1, rank_to), float(prize.get("amount") or 0.0)


def is_withdrawn(row: Mapping[str, Any]) -> bool:
    status = str(row.get("player_status") or "").strip().casefold()
    if status in WITHDRAWN_STATUSES:
        return True
    if status in COMPETING_OUT_STATUSES:
        return False
    return not int(row.get("active", 1) or 0)


@dataclass
class _Unit:
    """Um prêmio de UMA posição numa disputa (o geral ou uma categoria)."""

    kind: str
    category: str
    key: str
    position: int
    amount: float
    order: int
    label: str
    priority: float = 0.0


def _competition_key(prize: Mapping[str, Any]) -> str:
    if str(prize.get("kind")) == "overall":
        return "overall"
    return "category:" + tag_key(prize.get("category"))


def _units(prizes: Sequence[Mapping[str, Any]]) -> dict[str, dict[int, _Unit]]:
    """Os prêmios do edital como unidades (disputa, posição), somando sobreposições.

    A prioridade de uma posição é o maior valor dela ou de qualquer posição
    abaixo na mesma disputa: assim a disputa é sempre percorrida de cima para
    baixo, mesmo num edital que pague mais ao 2º que ao 1º.
    """
    competitions: dict[str, dict[int, _Unit]] = {}
    for order, prize in enumerate(prizes):
        key = _competition_key(prize)
        if key == "category:":
            continue
        rank_from, rank_to, amount = _prize_band(prize)
        if amount <= 0:
            continue
        units = competitions.setdefault(key, {})
        for position in range(rank_from, rank_to + 1):
            unit = units.get(position)
            if unit is None:
                units[position] = _Unit(
                    kind=str(prize.get("kind")),
                    category=str(prize.get("category") or "").strip() if key != "overall" else "",
                    key=key,
                    position=position,
                    amount=amount,
                    order=order,
                    label=str(prize.get("label") or ""),
                )
            else:
                unit.amount += amount
    for units in competitions.values():
        best_below = 0.0
        for position in sorted(units, reverse=True):
            best_below = max(best_below, units[position].amount)
            units[position].priority = best_below
    return competitions


def _ranking_of(key: str, ordered: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if key == "overall":
        return list(ordered)
    wanted = key.split(":", 1)[1]
    return [item for item in ordered if wanted in {tag_key(name) for name in categories_of(item)}]


def _points(row: Mapping[str, Any]) -> float:
    return float(row.get("points") or 0.0)


@dataclass
class _Distribution:
    shares: dict[int, dict[str, float]] = field(default_factory=dict)
    awards: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    undistributed: list[_Unit] = field(default_factory=list)
    announced: float = 0.0


def _split(pooled: float, band: list[float], size: int, tie_split: str) -> list[float]:
    """O bolo de um grupo empatado: por igual, ou Hort (50% da posição + 50% do bolo)."""
    if tie_split == "hort" and size > 1:
        equal_half = (pooled * 0.5) / size
        return [band[offset] * 0.5 + equal_half for offset in range(size)]
    return [pooled / size] * size


def _distribute(
    competitions: dict[str, dict[int, _Unit]],
    ordered: Sequence[Mapping[str, Any]],
    tie_split: str,
    *,
    one_prize_each: bool,
    result: _Distribution,
) -> None:
    """Percorre os prêmios do maior para o menor (D1) e dá cada um ao seu dono.

    Com ``one_prize_each``, quem já recebeu prêmio de OUTRA disputa sai da fila
    desta: o prêmio desce para o próximo. Quem recebeu desta disputa continua
    ocupando a sua posição nela.
    """
    rankings = {key: _ranking_of(key, ordered) for key in competitions}
    queue = sorted(
        (unit for units in competitions.values() for unit in units.values()),
        key=lambda unit: (-unit.priority, unit.order, unit.position),
    )
    result.announced += sum(unit.amount for unit in queue)
    holder: dict[int, str] = {}
    won_here: dict[str, set[int]] = {key: set() for key in competitions}
    consumed: set[tuple[str, int]] = set()
    for unit in queue:
        if (unit.key, unit.position) in consumed:
            continue
        ranked = [
            row
            for row in rankings[unit.key]
            if not one_prize_each or holder.get(int(row["player_id"]), unit.key) == unit.key
        ]
        index = unit.position - 1
        if index >= len(ranked):
            consumed.add((unit.key, unit.position))
            result.undistributed.append(unit)
            continue
        first, last = index, index
        points = _points(ranked[index])
        while (
            first > 0
            and _points(ranked[first - 1]) == points
            and int(ranked[first - 1]["player_id"]) not in won_here[unit.key]
        ):
            first -= 1
        while last + 1 < len(ranked) and _points(ranked[last + 1]) == points:
            last += 1
        group = ranked[first:last + 1]
        units = competitions[unit.key]
        # As posições do grupo ainda estão livres: a disputa é percorrida de
        # cima para baixo, e quem ganhou nela fica à frente de quem não ganhou.
        band_units = [units.get(first + 1 + offset) for offset in range(len(group))]
        band = [item.amount if item else 0.0 for item in band_units]
        for offset, player in enumerate(group):
            consumed.add((unit.key, first + 1 + offset))
        for offset, (player, share) in enumerate(zip(group, _split(sum(band), band, len(group), tie_split))):
            pid = int(player["player_id"])
            holder[pid] = unit.key
            won_here[unit.key].add(pid)
            by_kind = result.shares.setdefault(pid, {})
            by_kind[unit.kind] = by_kind.get(unit.kind, 0.0) + share
            result.awards.setdefault(pid, []).append(
                {
                    "kind": unit.kind,
                    "category": unit.category,
                    "label": (band_units[offset] or unit).label,
                    "position": first + 1 + offset,
                    "amount": round(share, 2),
                }
            )


def allocate_prizes(
    standings: Sequence[Mapping[str, Any]],
    prizes: Sequence[Mapping[str, Any]],
    policy: str = "best_only",
    tax_percent: float = 0.0,
    *,
    tie_split: str = "equal",
    exclude_withdrawn: bool = False,
) -> dict[str, Any]:
    """Aloca os prêmios sobre a classificação final.

    Retorna alocação por jogador (bruto/líquido), prêmios manuais e os totais.
    """
    policy = policy if policy in PRIZE_POLICIES else "best_only"
    tie_split = tie_split if tie_split in PRIZE_TIE_SPLITS else "equal"
    tax = max(0.0, min(100.0, float(tax_percent or 0.0)))

    ordered = sorted(standings, key=lambda item: int(item.get("position") or 0))
    excluded = 0
    if exclude_withdrawn:
        antes = len(ordered)
        ordered = [item for item in ordered if not is_withdrawn(item)]
        excluded = antes - len(ordered)

    auto_prizes = [p for p in prizes if str(p.get("kind")) in AUTO_KINDS]
    manual_prizes = [p for p in prizes if str(p.get("kind")) in MANUAL_KINDS]
    locked = [p for p in auto_prizes if policy == "best_only" and not p.get("cumulative")]
    free = [p for p in auto_prizes if not (policy == "best_only" and not p.get("cumulative"))]

    distribution = _Distribution()
    _distribute(_units(locked), ordered, tie_split, one_prize_each=True, result=distribution)
    _distribute(_units(free), ordered, tie_split, one_prize_each=False, result=distribution)

    by_id = {int(item["player_id"]): item for item in ordered}
    allocations: list[dict[str, Any]] = []
    total_gross = 0.0
    for pid, item in by_id.items():
        shares = distribution.shares.get(pid, {})
        overall = round(shares.get("overall", 0.0), 2)
        category = round(shares.get("category", 0.0), 2)
        gross = round(overall + category, 2)
        if gross <= 0:
            continue
        net = round(gross * (1.0 - tax / 100.0), 2)
        allocations.append(
            {
                "player_id": pid,
                "name": item.get("name", ""),
                "position": int(item.get("position") or 0),
                "points": float(item.get("points") or 0.0),
                "category": item.get("category", ""),
                "categories": "; ".join(categories_of(item)),
                "overall": overall,
                "category_prize": category,
                "gross": gross,
                "net": net,
                "awards": distribution.awards.get(pid, []),
            }
        )
        total_gross += gross

    allocations.sort(key=lambda row: (-row["net"], row["position"]))
    total_gross = round(total_gross, 2)
    total_net = round(total_gross * (1.0 - tax / 100.0), 2)

    return {
        "policy": policy,
        "tie_split": tie_split,
        "tax_percent": tax,
        "excluded_withdrawn": excluded,
        "allocations": allocations,
        "manual_prizes": [
            {
                "kind": str(prize.get("kind")),
                "label": str(prize.get("label") or ""),
                "category": str(prize.get("category") or ""),
                "currency": str(prize.get("currency") or ""),
                "amount": round(float(prize.get("amount") or 0.0), 2),
            }
            for prize in manual_prizes
        ],
        "undistributed": [
            {
                "kind": unit.kind,
                "category": unit.category,
                "label": unit.label,
                "position": unit.position,
                "amount": round(unit.amount, 2),
            }
            for unit in sorted(distribution.undistributed, key=lambda unit: (unit.order, unit.position))
        ],
        "total_announced": round(distribution.announced, 2),
        "total_undistributed": round(sum(unit.amount for unit in distribution.undistributed), 2),
        "winners": len(allocations),
        "total_gross": total_gross,
        "total_tax": round(total_gross - total_net, 2),
        "total_net": total_net,
    }
