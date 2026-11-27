"""Corte da classificação "como estava depois da rodada N" (RGS-10).

O retrato da rodada N é recalculado quando uma correção o inválida. Cortar só
os PAREAMENTOS por rodada não basta: o retrato reconciliado da R3 recebia o
ajuste de pontos lançado na R5, o jogador que se inscreveu na R4 e o status de
HOJE de quem desistiu depois — uma segunda informação errada no lugar da
primeira. Aqui fica a parte pura do corte; quem lê o banco é o serviço.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from src.services.pairing.participation import STATUS_ACTIVE, status_at_round


def adjustments_up_to_round(
    rows: Iterable[Mapping[str, Any]],
    round_number: int,
) -> list[Mapping[str, Any]]:
    """Só os ajustes com ``round_number <= N``.

    ``round_number = 0`` é o ajuste sem rodada (vale desde o início) e por isso
    entra em todo corte — o mesmo que acontecia antes com todos eles.
    """
    return [row for row in rows if int(row.get("round_number") or 0) <= int(round_number)]


def players_as_of_round(
    players: Sequence[Mapping[str, Any]],
    status_events: Iterable[Mapping[str, Any]],
    pairings: Iterable[Mapping[str, Any]],
    round_number: int,
) -> list[dict[str, Any]]:
    """Os jogadores do torneio como estavam na rodada N.

    - **Quem entra:** inscrito até N (``entry_round`` de 1 a N; ``0`` é
      desconhecido e entra, como antes) **ou** com mesa em alguma rodada até
      N — a mesa é prova de que ele estava lá, mesmo que a inscrição tenha
      sido acertada à mão depois.
    - **Com que status:** o vigente na rodada N pelo histórico ARB-05. Sem
      evento no histórico, o campo atual vale: é o que há (base antiga).
    """
    corte = int(round_number)
    com_mesa: set[int] = set()
    for pairing in pairings:
        if int(pairing.get("round_number") or 0) > corte:
            continue
        for chave in ("white_player_id", "black_player_id"):
            if pairing.get(chave):
                com_mesa.add(int(pairing[chave]))

    eventos: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for evento in status_events:
        eventos[int(evento.get("player_id") or 0)].append(evento)

    recorte: list[dict[str, Any]] = []
    for player in players:
        player_id = int(player["id"])
        entrada = int(player.get("entry_round") or 0)
        if entrada > corte and player_id not in com_mesa:
            continue
        linha = dict(player)
        historico = eventos.get(player_id)
        if historico:
            status = status_at_round(historico, corte)
            linha["player_status"] = status
            linha["active"] = 1 if status == STATUS_ACTIVE else 0
        recorte.append(linha)
    return recorte


def teams_as_of_round(
    teams: Sequence[Mapping[str, Any]],
    matches: Iterable[Mapping[str, Any]],
    round_number: int,
) -> list[dict[str, Any]]:
    """As equipes do torneio como estavam na rodada N (E6) — a regra do jogador.

    Entra quem foi inscrita até N (``entry_round`` de 1 a N; ``0`` é
    desconhecido e entra) **ou** tem confronto (ou bye) em alguma rodada até N.
    Equipe não tem histórico de status: o ``active`` atual vale.
    """
    corte = int(round_number)
    com_confronto: set[int] = set()
    for match in matches:
        if int(match.get("round_number") or 0) > corte:
            continue
        for chave in ("white_team_id", "black_team_id"):
            if match.get(chave):
                com_confronto.add(int(match[chave]))
    return [
        dict(team)
        for team in teams
        if int(team.get("entry_round") or 0) <= corte or int(team["id"]) in com_confronto
    ]
