"""Serviço de premiação (spec E4 — Fase C).

Faz a ponte entre o motor puro (`prizes.allocate_prizes`), a classificação
final (via PairingService) e a persistência dos prêmios cadastrados. Mantém o
desktop/SQLite como autoridade: a lista de prêmios é só um cálculo derivado da
classificação e do cadastro de prêmios.
"""

from __future__ import annotations

from typing import Any

from src.core.database import Database
from src.services.categories import categories_of, default_categories
from src.services.categories.matching import tag_key
from src.services.constants import AppError
from src.services.numeric_fields import money_field
from src.services.prizes import PRIZE_KINDS, allocate_prizes
from src.services.permissions import requires


def validated_prizes(prizes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prêmios limpos, sem gravar (RGS-08: a tela valida tudo antes de gravar).

    A mensagem diz QUAL linha está errada: "Informe o nome de cada prêmio"
    sozinho deixava o árbitro procurando a linha em branco.
    """
    limpos: list[dict[str, Any]] = []
    for posicao, prize in enumerate(prizes or [], start=1):
        try:
            limpos.append(PrizeService._validated_prize(prize))
        except AppError as exc:
            raise AppError(f"Prêmio {posicao}: {exc}") from exc
    return limpos


def known_categories(
    definitions: list[dict[str, Any]], players: list[dict[str, Any]]
) -> list[str]:
    """As categorias que um prêmio pode citar: as do edital e as escritas à mão.

    Edital vazio vale o conjunto padrão (ORG-01). A categoria escrita à mão no
    jogador ("Convidados") não está no edital, mas tem classificação.
    """
    names = [str(row["name"]) for row in definitions] or [item.name for item in default_categories()]
    for player in players:
        names.extend(categories_of(player))
    return list(dict.fromkeys(name for name in names if name.strip()))


def refuse_unknown_categories(prizes: list[dict[str, Any]], known: list[str]) -> None:
    """RG2-16: prêmio de categoria que não existe nunca acharia ganhador — calado.

    A comparação é a da marca (``tag_key``): sem acento e sem caixa.
    """
    keys = {tag_key(name) for name in known}
    for position, prize in enumerate(prizes, start=1):
        if prize["kind"] == "category" and tag_key(prize["category"]) not in keys:
            raise AppError(
                f"Prêmio {position}: a categoria \"{prize['category']}\" não existe neste torneio. "
                f"Categorias: {', '.join(known)}."
            )


class PrizeService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_prizes(self, tournament_id: int) -> list[dict[str, Any]]:
        return self.db.list_tournament_prizes(tournament_id)

    @requires("tournament_write")
    def replace_prizes(
        self,
        tournament_id: int,
        prizes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not self.db.get_tournament(tournament_id):
            raise AppError("Selecione um torneio válido.")
        cleaned = validated_prizes(prizes)
        refuse_unknown_categories(
            cleaned,
            known_categories(self.db.list_tournament_categories(tournament_id), self.db.list_players(tournament_id)),
        )
        self.db.replace_tournament_prizes(tournament_id, cleaned)
        return self.db.list_tournament_prizes(tournament_id)

    @staticmethod
    def _validated_prize(prize: dict[str, Any]) -> dict[str, Any]:
        kind = str(prize.get("kind") or "overall").strip()
        if kind not in PRIZE_KINDS:
            raise AppError("Tipo de prêmio inválido.")
        label = str(prize.get("label") or "").strip()
        if not label:
            raise AppError("Informe o nome do prêmio.")
        category = str(prize.get("category") or "").strip()
        if kind == "category" and not category:
            raise AppError("Prêmio de categoria exige o nome da categoria.")
        try:
            rank_from = int(prize.get("rank_from") or 1)
            rank_to = int(prize.get("rank_to") or rank_from)
        except (TypeError, ValueError) as exc:
            raise AppError("Faixa de colocação do prêmio inválida.") from exc
        if rank_from < 1 or rank_to < rank_from:
            raise AppError("Faixa de colocação do prêmio inválida.")
        amount = money_field(prize.get("amount"), "Valor do prêmio inválido.")
        if amount < 0:
            raise AppError("Valor do prêmio não pode ser negativo.")
        return {
            "kind": kind,
            "label": label,
            "category": category if kind == "category" else "",
            "rank_from": rank_from,
            "rank_to": rank_to,
            "amount": round(amount, 2),
            # Política POR PRÊMIO (ORG-02): o edital típico soma o prêmio
            # Feminino ao geral mesmo quando a política do torneio e "apenas o
            # maior", e antes isso não tinha como ser dito.
            "cumulative": 1 if prize.get("cumulative") else 0,
            "currency": str(prize.get("currency") or "").strip()[:8],
        }

    def allocate(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Distribuição de prêmios disponível apenas para torneios individuais.")
        settings = self.db.get_tournament_settings(tournament_id) or {}
        prizes = self.db.list_tournament_prizes(tournament_id)
        pairing_service = __import__(
            "src.services.pairing_service", fromlist=["PairingService"]
        ).PairingService(self.db)
        standings = pairing_service.standings(tournament_id)
        allocation = allocate_prizes(
            standings,
            prizes,
            policy=str(settings.get("prize_policy") or "best_only"),
            tax_percent=float(settings.get("prize_tax_percent") or 0.0),
            tie_split=str(settings.get("prize_tie_split") or "equal"),
            exclude_withdrawn=bool(settings.get("prize_exclude_withdrawn")),
        )
        allocation["tournament"] = tournament
        return allocation
