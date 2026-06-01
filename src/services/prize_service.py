"""Serviço de premiação (spec E4 — Fase C).

Faz a ponte entre o motor puro (`prizes.allocate_prizes`), a classificação
final (via PairingService) e a persistência dos prêmios cadastrados. Mantém o
desktop/SQLite como autoridade: a lista de prêmios é só um cálculo derivado da
classificação e do cadastro de prêmios.
"""

from __future__ import annotations

from typing import Any

from src.core.database import Database
from src.services.constants import AppError
from src.services.prizes import PRIZE_KINDS, allocate_prizes


class PrizeService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_prizes(self, tournament_id: int) -> list[dict[str, Any]]:
        return self.db.list_tournament_prizes(tournament_id)

    def replace_prizes(
        self,
        tournament_id: int,
        prizes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not self.db.get_tournament(tournament_id):
            raise AppError("Selecione um torneio valido.")
        cleaned = [self._validated_prize(prize) for prize in prizes]
        self.db.replace_tournament_prizes(tournament_id, cleaned)
        return self.db.list_tournament_prizes(tournament_id)

    @staticmethod
    def _validated_prize(prize: dict[str, Any]) -> dict[str, Any]:
        kind = str(prize.get("kind") or "overall").strip()
        if kind not in PRIZE_KINDS:
            raise AppError("Tipo de premio invalido.")
        label = str(prize.get("label") or "").strip()
        if not label:
            raise AppError("Informe o nome de cada premio.")
        category = str(prize.get("category") or "").strip()
        if kind == "category" and not category:
            raise AppError("Premio de categoria exige o nome da categoria.")
        try:
            rank_from = int(prize.get("rank_from") or 1)
            rank_to = int(prize.get("rank_to") or rank_from)
        except (TypeError, ValueError) as exc:
            raise AppError("Faixa de colocacao do premio invalida.") from exc
        if rank_from < 1 or rank_to < rank_from:
            raise AppError("Faixa de colocacao do premio invalida.")
        try:
            amount = float(str(prize.get("amount") or "0").replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise AppError("Valor do premio invalido.") from exc
        if amount < 0:
            raise AppError("Valor do premio nao pode ser negativo.")
        return {
            "kind": kind,
            "label": label,
            "category": category if kind == "category" else "",
            "rank_from": rank_from,
            "rank_to": rank_to,
            "amount": round(amount, 2),
        }

    def allocate(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        if tournament.get("competition_type") == "team":
            raise AppError("Distribuicao de premios disponivel apenas para torneios individuais.")
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
        )
        allocation["tournament"] = tournament
        return allocation
