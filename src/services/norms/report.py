"""Relatório de indicadores de norma por jogador (puro).

Mantém a assinatura de ``build_norm_report`` que o resto do sistema já usa e
devolve, por jogador, o resumo mais a avaliação de cada norma aplicável.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.services.constants import player_full_name
from src.services.fide_rating import fide_performance, player_rating_for_type
from src.services.norms.evaluation import NormEvaluation, evaluate_norms
from src.services.norms.opponents import (
    NormOpponent,
    average_rating,
    collect_opponents,
    played_games,
    unrated_without_points,
)

_ROUND_ROBIN_SYSTEMS = ("round_robin", "berger", "todos contra todos", "round-robin")


@dataclass(frozen=True)
class NormCandidate:
    """Um par (jogador, norma) com os adversários que o sustentam.

    É o que o certificado IT3 precisa e o relatório em dicionário não entrega:
    lá a avaliação já virou texto.
    """

    player: Mapping[str, Any]
    opponents: list[NormOpponent]
    evaluation: NormEvaluation


def _slug(value: object) -> str:
    return str(value or "").strip().casefold().replace(" ", "_").replace("-", "_")


def is_round_robin(pairing_system: object) -> bool:
    value = _slug(pairing_system)
    return bool(value) and any(_slug(marker) in value for marker in _ROUND_ROBIN_SYSTEMS)


def collect_tournament_opponents(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = "fide",
    *,
    pairing_system: object = "",
    name_of: Any = player_full_name,
) -> tuple[dict[int, Mapping[str, Any]], dict[int, list[NormOpponent]]]:
    """Jogadores indexados e seus adversários de norma.

    `name_of` existe porque o IT3 é formulário da FIDE e quer "Sobrenome, Nome",
    enquanto o relatório de tela quer o nome como se fala.
    """
    players_by_id: dict[int, Mapping[str, Any]] = {int(player["id"]): player for player in players}
    rating_by_id = {
        pid: player_rating_for_type(player, rating_type) for pid, player in players_by_id.items()
    }

    excluded: set[int] = set()
    if is_round_robin(pairing_system):
        # 1.4.2 — em round-robin, partida contra não ratado que zerou contra
        # ratados não conta para norma.
        excluded = unrated_without_points(
            played_games(closed_pairings, players_by_id), rating_by_id
        )

    opponents = collect_opponents(
        players_by_id,
        closed_pairings,
        rating_by_id,
        name_of=name_of,
        excluded_ids=excluded,
    )
    return players_by_id, opponents


def summarize(
    player: Mapping[str, Any],
    opponents: Sequence[NormOpponent],
    evaluations: Sequence[NormEvaluation],
) -> dict[str, Any]:
    """Linha de resumo do jogador — ratings reais, sem o piso de nenhuma norma."""
    games = len(opponents)
    score = round(sum(opponent.points for opponent in opponents), 2)
    average_opponent = average_rating([opponent.rating_for_norm for opponent in opponents])
    own = str(player.get("federation_id") or "").strip().upper()
    federations = {opponent.federation for opponent in opponents if opponent.federation}
    federations.discard(own)

    return {
        "player_id": int(player["id"]),
        "name": player_full_name(player),
        "sex": str(player.get("sex") or "").strip().upper(),
        "federation": own,
        "title": str(player.get("title") or "").strip().upper(),
        "performance": fide_performance(average_opponent, score, games),
        "games": games,
        "score": score,
        "average_opponent": average_opponent,
        # Federações dos ADVERSÁRIOS, sem a do candidato (B.01 1.4.3).
        "federations": len(federations),
        # A contagem de titulados (1.4.5) não depende da norma; qualquer
        # avaliação serve, e sem nenhuma o jogador não tem partida válida.
        "titled_opponents": evaluations[0].title_holders if evaluations else 0,
        "unrated_opponents": sum(1 for opponent in opponents if opponent.is_unrated),
        "titles": [evaluation.as_dict() for evaluation in evaluations],
        "achieved": [evaluation.label for evaluation in evaluations if evaluation.meets],
    }


def build_norm_report(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = "fide",
    *,
    pairing_system: object = "",
) -> list[dict[str, Any]]:
    """Indicadores de norma por jogador (somente quem jogou partidas válidas)."""
    players_by_id, opponents_by_id = collect_tournament_opponents(
        players, closed_pairings, rating_type, pairing_system=pairing_system
    )

    report: list[dict[str, Any]] = []
    for player_id, player in players_by_id.items():
        opponents = opponents_by_id.get(player_id, [])
        if not opponents:
            continue
        evaluations = evaluate_norms(
            str(player.get("federation_id") or ""), player.get("sex"), opponents
        )
        report.append(summarize(player, opponents, evaluations))

    report.sort(key=lambda item: (-int(item["performance"]), str(item["name"]).casefold()))
    return report


def norm_candidates(
    players: Sequence[Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_type: str = "fide",
    *,
    pairing_system: object = "",
    achieved_only: bool = True,
    player_id: int | None = None,
    title: str | None = None,
    name_of: Any = player_full_name,
) -> list[NormCandidate]:
    """Candidatos a norma, um por par (jogador, norma).

    Com `achieved_only`, só quem cumpre todos os indicadores; sem ele, o par
    sai mesmo incompleto — é assim que o árbitro imprime o IT3 de quem ficou
    perto e quer ver, no papel, o que faltou.
    """
    players_by_id, opponents_by_id = collect_tournament_opponents(
        players, closed_pairings, rating_type, pairing_system=pairing_system, name_of=name_of
    )
    wanted_title = str(title or "").strip().upper()

    candidates: list[NormCandidate] = []
    for pid, player in players_by_id.items():
        if player_id is not None and pid != int(player_id):
            continue
        opponents = opponents_by_id.get(pid, [])
        if not opponents:
            continue
        for evaluation in evaluate_norms(
            str(player.get("federation_id") or ""), player.get("sex"), opponents
        ):
            if wanted_title and evaluation.title != wanted_title:
                continue
            if achieved_only and not evaluation.meets:
                continue
            candidates.append(NormCandidate(player, list(opponents), evaluation))

    candidates.sort(
        key=lambda item: (
            -int(item.evaluation.performance),
            player_full_name(item.player).casefold(),
            item.evaluation.title,
        )
    )
    return candidates
