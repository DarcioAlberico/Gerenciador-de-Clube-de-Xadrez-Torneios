"""Cor inicial do torneio (RGS-14).

C.04.3: a cor inicial — a do nº 1 na mesa 1 da R1 — é sorteada antes da
primeira rodada (ou definida pelo regulamento). O Albericus não sorteava: o
Gacrux, sem o registro 152, sorteava a CADA chamada (`random.random()`), e a
prévia da R1 saía com uma cor e a geração com outra; o motor reserva dava
sempre brancas.

Agora a cor é sorteada quando o torneio nasce (`draw_initial_color`), fica em
``tournament_settings.initial_color`` e é a mesma para a prévia, a geração, o
registro ``152`` do Gacrux e a R1 do motor reserva. O árbitro pode trocá-la
antes da R1.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from src.core.database_tournament_core import draw_initial_color, normalize_initial_color
from src.services.pairing.constraints import seeding_order

logger = logging.getLogger(__name__)

__all__ = [
    "color_from_first_round",
    "normalize_initial_color",
    "resolve_initial_color",
]


def color_from_first_round(db: Any, tournament_id: int, settings: Mapping[str, Any]) -> str:
    """Cor que a R1 já gravada deu ao nº 1 da mesa mais alta — '' se não há R1.

    Mesma leitura que o Gacrux faz das partidas quando não recebe o 152
    (`pairing.py`): a mesa jogada da R1 com o menor número de pareamento; a cor
    é a do jogador de número menor.
    """
    primeira = next((r for r in db.list_rounds(tournament_id) if int(r["number"]) == 1), None)
    if primeira is None:
        return ""
    jogadores = seeding_order(db.list_players(tournament_id, active_only=False), dict(settings))
    numero = {int(jogador["id"]): indice for indice, jogador in enumerate(jogadores, start=1)}
    melhor: tuple[int, str] | None = None
    for mesa in db.get_pairings_for_round(int(primeira["id"])):
        if mesa.get("is_bye") or not mesa.get("black_player_id"):
            continue
        branca = numero.get(int(mesa["white_player_id"]))
        preta = numero.get(int(mesa["black_player_id"]))
        if not branca or not preta:
            continue
        candidato = (min(branca, preta), "W" if branca < preta else "B")
        if melhor is None or candidato < melhor:
            melhor = candidato
    return melhor[1] if melhor else ""


def resolve_initial_color(
    db: Any, tournament_id: int, settings: Mapping[str, Any] | None = None
) -> str:
    """'W' ou 'B': a cor inicial que vale para o torneio.

    1. A gravada (sorteio da criação, ou escolha do árbitro).
    2. Torneio anterior à v57 que já tinha R1: a cor que a R1 deu (sem gravar —
       ela é fato do tabuleiro, não sorteio).
    3. Sem cor e sem R1 (torneio antigo cuja R1 foi excluída): sorteia AGORA e
       grava, com auditoria, para que a prévia e a geração seguintes leiam o
       mesmo valor.
    """
    ajustes = settings if settings is not None else (db.get_tournament_settings(tournament_id) or {})
    cor = normalize_initial_color(ajustes.get("initial_color"))
    if cor:
        return cor
    cor = color_from_first_round(db, tournament_id, ajustes)
    if cor:
        return cor
    cor = draw_initial_color()
    with db.transaction():
        db.save_tournament_settings(tournament_id, {"initial_color": cor})
        db.create_audit_event(
            action="initial_color_drawn",
            tournament_id=tournament_id,
            entity_type="tournament_settings",
            reason="Cor inicial sorteada antes da rodada 1 (C.04.3).",
            after={"initial_color": cor},
        )
    logger.info("Torneio %s: cor inicial sorteada (%s)", tournament_id, cor)
    return cor
