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

from typing import Any, Mapping, Sequence

from src.services.categories import categories_of

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

# Status que não concorrem quando o edital exclui desistentes.
WITHDRAWN_STATUSES = {"withdrawn", "desistente", "absent", "ausente", "expelled"}


def _norm_category(value: Any) -> str:
    return str(value or "").strip().casefold()


def _prize_band(prize: Mapping[str, Any]) -> tuple[int, int, float]:
    rank_from = int(prize.get("rank_from") or 1)
    rank_to = int(prize.get("rank_to") or rank_from)
    if rank_to < rank_from:
        rank_from, rank_to = rank_to, rank_from
    return max(1, rank_from), max(1, rank_to), float(prize.get("amount") or 0.0)


def _position_amounts(prizes: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    """Mapa posição -> valor a partir das faixas (somando sobreposições)."""
    amounts: dict[int, float] = {}
    for prize in prizes:
        rank_from, rank_to, amount = _prize_band(prize)
        if amount <= 0:
            continue
        for position in range(rank_from, rank_to + 1):
            amounts[position] = amounts.get(position, 0.0) + amount
    return amounts


def is_withdrawn(row: Mapping[str, Any]) -> bool:
    status = str(row.get("player_status") or "").strip().casefold()
    if status in WITHDRAWN_STATUSES:
        return True
    return not int(row.get("active", 1) or 0)


def _allocate_band(
    ranked_players: Sequence[Mapping[str, Any]],
    position_amounts: dict[int, float],
    tie_split: str = "equal",
) -> dict[int, float]:
    """Divide os valores das posições entre os jogadores, tratando empates.

    `ranked_players` já vem na ordem da classificação — o que significa que a
    ordem DENTRO de um grupo empatado já é a ordem do desempate, e é dela que o
    Sistema Hort precisa.

    - `equal`: o grupo soma os prêmios das posições que ocupa e divide por igual;
    - `hort`: cada um recebe 50% do prêmio da SUA posição mais 50% do bolo
      dividido por igual. A soma dá o mesmo bolo — o Hort não cria nem destrói
      dinheiro, só reconhece o desempate sem entregar tudo ao primeiro.
    """
    shares: dict[int, float] = {}
    total = len(ranked_players)
    index = 0
    position = 1
    while index < total:
        end = index
        points = float(ranked_players[index].get("points") or 0.0)
        while end + 1 < total and float(ranked_players[end + 1].get("points") or 0.0) == points:
            end += 1
        group = ranked_players[index:end + 1]
        band = [position_amounts.get(position + offset, 0.0) for offset in range(len(group))]
        pooled = sum(band)
        if pooled > 0:
            if tie_split == "hort" and len(group) > 1:
                equal_half = (pooled * 0.5) / len(group)
                for offset, player in enumerate(group):
                    pid = int(player["player_id"])
                    shares[pid] = shares.get(pid, 0.0) + band[offset] * 0.5 + equal_half
            else:
                per_player = pooled / len(group)
                for player in group:
                    pid = int(player["player_id"])
                    shares[pid] = shares.get(pid, 0.0) + per_player
        position += len(group)
        index = end + 1
    return shares


def _combine(overall: float, category: float, policy: str) -> float:
    if policy == "cumulative":
        return overall + category
    return max(overall, category)  # best_only


def _category_shares(
    ordered: Sequence[Mapping[str, Any]],
    category_prizes: Sequence[Mapping[str, Any]],
    tie_split: str,
) -> tuple[dict[int, float], dict[int, float]]:
    """Prêmios de categoria, separados em "segue a política" e "sempre soma".

    O jogador entra na classificação de CADA categoria dele — Sub-12, Sub-1400 e
    Feminino são três disputas, e antes o alocador só enxergava a principal.
    """
    by_policy: dict[int, float] = {}
    always: dict[int, float] = {}

    grupos: dict[tuple[str, bool], list[Mapping[str, Any]]] = {}
    for prize in category_prizes:
        chave = (_norm_category(prize.get("category")), bool(prize.get("cumulative")))
        grupos.setdefault(chave, []).append(prize)

    for (category_key, cumulative), prizes_in_category in grupos.items():
        if not category_key:
            continue
        ranked = [
            item
            for item in ordered
            if category_key in {_norm_category(name) for name in categories_of(item)}
        ]
        alvo = always if cumulative else by_policy
        for pid, share in _allocate_band(
            ranked, _position_amounts(prizes_in_category), tie_split
        ).items():
            alvo[pid] = alvo.get(pid, 0.0) + share
    return by_policy, always


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

    overall_prizes = [p for p in prizes if str(p.get("kind")) == "overall"]
    category_prizes = [p for p in prizes if str(p.get("kind")) == "category"]
    manual_prizes = [p for p in prizes if str(p.get("kind")) in MANUAL_KINDS]

    overall_shares = _allocate_band(ordered, _position_amounts(overall_prizes), tie_split)
    category_by_policy, category_always = _category_shares(ordered, category_prizes, tie_split)

    by_id = {int(item["player_id"]): item for item in ordered}
    allocations: list[dict[str, Any]] = []
    total_gross = 0.0
    for pid in by_id:
        overall = round(overall_shares.get(pid, 0.0), 2)
        category_policy = round(category_by_policy.get(pid, 0.0), 2)
        category_always_value = round(category_always.get(pid, 0.0), 2)
        category = round(category_policy + category_always_value, 2)
        gross = round(_combine(overall, category_policy, policy) + category_always_value, 2)
        if gross <= 0:
            continue
        net = round(gross * (1.0 - tax / 100.0), 2)
        item = by_id[pid]
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
        "winners": len(allocations),
        "total_gross": total_gross,
        "total_tax": round(total_gross - total_net, 2),
        "total_net": total_net,
    }
