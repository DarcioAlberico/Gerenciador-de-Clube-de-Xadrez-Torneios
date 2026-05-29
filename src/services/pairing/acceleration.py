"""Aceleração de pareamento (pontos fictícios) — funções puras.

A aceleração só altera o *score de pareamento* (os grupos de pontuação que o
motor Suíço usa para emparelhar); jamais toca nos pontos reais, na classificação
ou nos desempates. Por isso o motor recebe um *standings efetivo* com o bônus
somado, enquanto o standings real fica intacto.

Esquema implementado: **clássico** (top-metade da lista inicial ganha +1 ponto
fictício nas rodadas 1 e 2). Não é Baku — o registro 192 não recebe `_BAKU`.
"""

from __future__ import annotations

from typing import Any

# Esquema clássico: rodadas com bônus e valor do bônus por jogador.
CLASSIC_ACCELERATION_ROUNDS = (1, 2)
CLASSIC_ACCELERATION_BONUS = 1.0


def classic_upper_half_size(total_players: int) -> int:
    """Tamanho da metade superior que recebe o bônus (piso de N/2)."""
    return max(int(total_players), 0) // 2


def classic_acceleration_bonus(start_rank: int, total_players: int, round_number: int) -> float:
    """Bônus fictício de um jogador na aceleração clássica.

    `start_rank` é o ranking inicial 1-based (1 = cabeça de chave). Devolve
    `CLASSIC_ACCELERATION_BONUS` para a metade superior nas rodadas 1 e 2; 0.0
    caso contrário.
    """
    if int(round_number) not in CLASSIC_ACCELERATION_ROUNDS:
        return 0.0
    if start_rank <= 0:
        return 0.0
    return CLASSIC_ACCELERATION_BONUS if start_rank <= classic_upper_half_size(total_players) else 0.0


def accelerated_standings(
    standings: dict[int, dict[str, Any]],
    seeding: list[int],
    round_number: int,
    method: str,
) -> dict[int, dict[str, Any]]:
    """Standings efetivo de pareamento com o bônus de aceleração somado.

    `seeding` é a lista de `player_id` na ordem de ranking inicial (1 = cabeça
    de chave); seu comprimento define o total para o corte da metade. Quando o
    método não é acelerado, devolve o standings original sem cópia.
    """
    if method != "accelerated" or not seeding:
        return standings

    total = len(seeding)
    effective: dict[int, dict[str, Any]] = {}
    for index, player_id in enumerate(seeding, start=1):
        item = dict(standings.get(player_id, {}))
        bonus = classic_acceleration_bonus(index, total, round_number)
        if bonus:
            item["points"] = float(item.get("points", 0.0) or 0.0) + bonus
        effective[player_id] = item
    for player_id, item in standings.items():
        effective.setdefault(player_id, item)
    return effective
