"""Distribuição de prêmios (spec E4 — Fase C).

Funções puras, sem banco: recebem a classificação final e a lista de prêmios e
devolvem a alocação por jogador. Implementa divisão entre empatados por pontos,
as políticas de combinação geral×categoria (best_only / cumulative / hort) e a
dedução de imposto do organizador.

Prêmios `overall` e `category` são alocados automaticamente a partir da
classificação; `special` e `board` são listados como prêmios manuais (a
definição do ganhador depende de critério externo / dados de equipe).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

PRIZE_KINDS = {
    "overall": "Geral (colocação)",
    "category": "Categoria",
    "special": "Especial (manual)",
    "board": "Tabuleiro (equipes)",
}

PRIZE_POLICIES = {
    "best_only": "Apenas o maior prêmio",
    "cumulative": "Acumular geral + categoria",
    "hort": "Sistema Hort (combinação)",
}

AUTO_KINDS = {"overall", "category"}
MANUAL_KINDS = {"special", "board"}


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


def _allocate_band(
    ranked_players: Sequence[Mapping[str, Any]],
    position_amounts: dict[int, float],
) -> dict[int, float]:
    """Divide os valores das posições, repartindo empates (mesma pontuação).

    `ranked_players` já vem na ordem da classificação; cada jogador ocupa a
    posição 1..N nesta lista. Jogadores com a MESMA pontuação formam um grupo
    que soma os prêmios das posições ocupadas e divide igualmente (regra de
    rateio de prêmios empatados).
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
        pooled = sum(position_amounts.get(position + offset, 0.0) for offset in range(len(group)))
        if pooled > 0:
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
    if policy == "hort":
        # Interpretação comum do Sistema Hort: o jogador recebe o maior entre o
        # prêmio de colocação e a média entre colocação e categoria — premiando
        # quem teria um prêmio de colocação pequeno mas boa categoria.
        return max(overall, (overall + category) / 2.0)
    return max(overall, category)  # best_only


def allocate_prizes(
    standings: Sequence[Mapping[str, Any]],
    prizes: Sequence[Mapping[str, Any]],
    policy: str = "best_only",
    tax_percent: float = 0.0,
) -> dict[str, Any]:
    """Aloca os prêmios sobre a classificação final.

    Retorna alocação por jogador (bruto/líquido), prêmios manuais e os totais.
    """
    policy = policy if policy in PRIZE_POLICIES else "best_only"
    tax = max(0.0, min(100.0, float(tax_percent or 0.0)))
    ordered = sorted(standings, key=lambda item: int(item.get("position") or 0))

    overall_prizes = [p for p in prizes if str(p.get("kind")) == "overall"]
    category_prizes = [p for p in prizes if str(p.get("kind")) == "category"]
    manual_prizes = [p for p in prizes if str(p.get("kind")) in MANUAL_KINDS]

    overall_shares = _allocate_band(ordered, _position_amounts(overall_prizes))

    category_shares: dict[int, float] = {}
    categories: dict[str, list[Mapping[str, Any]]] = {}
    for prize in category_prizes:
        categories.setdefault(_norm_category(prize.get("category")), []).append(prize)
    for category_key, prizes_in_category in categories.items():
        if not category_key:
            continue
        ranked = [item for item in ordered if _norm_category(item.get("category")) == category_key]
        for pid, share in _allocate_band(ranked, _position_amounts(prizes_in_category)).items():
            category_shares[pid] = category_shares.get(pid, 0.0) + share

    by_id = {int(item["player_id"]): item for item in ordered}
    allocations: list[dict[str, Any]] = []
    total_gross = 0.0
    for pid in by_id:
        overall = round(overall_shares.get(pid, 0.0), 2)
        category = round(category_shares.get(pid, 0.0), 2)
        gross = round(_combine(overall, category, policy), 2)
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
        "tax_percent": tax,
        "allocations": allocations,
        "manual_prizes": [
            {
                "kind": str(prize.get("kind")),
                "label": str(prize.get("label") or ""),
                "category": str(prize.get("category") or ""),
                "amount": round(float(prize.get("amount") or 0.0), 2),
            }
            for prize in manual_prizes
        ],
        "winners": len(allocations),
        "total_gross": total_gross,
        "total_tax": round(total_gross - total_net, 2),
        "total_net": total_net,
    }
