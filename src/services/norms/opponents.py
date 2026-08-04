"""Adversários de norma: quais partidas contam e com que rating elas contam.

Puro: recebe jogadores e emparceiramentos fechados como mapas e devolve, por
jogador, a lista de adversários de norma. Nenhum acesso a banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.services.norms.handbook import UNRATED_RATING, NormRequirement, normalized_title

# 1.4.2 — só conta partida jogada no tabuleiro. W.O., bye e resultado atribuído
# ficam de fora (é a mesma regra do relatório de rating).
PLAYED_RESULTS = ("1-0", "0-1", "1/2-1/2")
_RESULT_POINTS: dict[str, tuple[float, float]] = {
    "1-0": (1.0, 0.0),
    "0-1": (0.0, 1.0),
    "1/2-1/2": (0.5, 0.5),
}


@dataclass(frozen=True)
class NormOpponent:
    """Uma partida válida do candidato, do ponto de vista da norma."""

    player_id: int
    name: str
    federation: str
    title: str
    rating: int
    round_number: int
    color: str
    points: float

    @property
    def is_unrated(self) -> bool:
        return self.rating <= 0

    @property
    def rating_for_norm(self) -> int:
        """1.4.6.4 — sem rating conta como 1400 (antes do piso da norma)."""
        return self.rating if self.rating > 0 else UNRATED_RATING


def _color_of(pairing: Mapping[str, Any], player_id: int) -> str:
    return "b" if int(pairing.get("white_player_id") or 0) != player_id else "w"


def played_games(
    closed_pairings: Sequence[Mapping[str, Any]],
    known_ids: Iterable[int],
) -> list[dict[str, Any]]:
    """Partidas jogadas entre dois jogadores conhecidos, normalizadas."""
    valid_ids = set(int(pid) for pid in known_ids)
    games: list[dict[str, Any]] = []
    for pairing in closed_pairings:
        if pairing.get("is_bye"):
            continue
        white_id = pairing.get("white_player_id")
        black_id = pairing.get("black_player_id")
        result = str(pairing.get("result") or "")
        if result not in _RESULT_POINTS:
            continue
        if white_id is None or black_id is None:
            continue
        if int(white_id) not in valid_ids or int(black_id) not in valid_ids:
            continue
        white_points, black_points = _RESULT_POINTS[result]
        games.append(
            {
                "round_number": int(pairing.get("round_number") or 0),
                "white_id": int(white_id),
                "black_id": int(black_id),
                "white_points": white_points,
                "black_points": black_points,
            }
        )
    return games


def unrated_without_points(
    games: Sequence[Mapping[str, Any]],
    rating_by_id: Mapping[int, int],
) -> set[int]:
    """1.4.2 — não ratados que zeraram contra ratados (partidas descartáveis).

    A regra existe para round-robin: um não ratado que perdeu de todo mundo com
    rating não gera partida válida para norma. Devolvemos o conjunto; quem
    decide aplicá-lo é o chamador, que sabe o sistema do torneio.
    """
    scored: dict[int, float] = {}
    for game in games:
        white_id, black_id = int(game["white_id"]), int(game["black_id"])
        for player_id, opponent_id, points in (
            (white_id, black_id, float(game["white_points"])),
            (black_id, white_id, float(game["black_points"])),
        ):
            if rating_by_id.get(player_id, 0) > 0:
                continue
            if rating_by_id.get(opponent_id, 0) <= 0:
                continue
            scored[player_id] = scored.get(player_id, 0.0) + points
    return {player_id for player_id, points in scored.items() if points <= 0}


def collect_opponents(
    players_by_id: Mapping[int, Mapping[str, Any]],
    closed_pairings: Sequence[Mapping[str, Any]],
    rating_by_id: Mapping[int, int],
    *,
    name_of: Any,
    excluded_ids: Iterable[int] = (),
) -> dict[int, list[NormOpponent]]:
    """Adversários de norma por jogador, em ordem de rodada."""
    discarded = {int(pid) for pid in excluded_ids}
    result: dict[int, list[NormOpponent]] = {pid: [] for pid in players_by_id}

    for game in played_games(closed_pairings, players_by_id):
        white_id, black_id = int(game["white_id"]), int(game["black_id"])
        for player_id, opponent_id, points, color in (
            (white_id, black_id, float(game["white_points"]), "w"),
            (black_id, white_id, float(game["black_points"]), "b"),
        ):
            if opponent_id in discarded:
                continue
            opponent = players_by_id[opponent_id]
            result[player_id].append(
                NormOpponent(
                    player_id=opponent_id,
                    name=name_of(opponent),
                    federation=str(opponent.get("federation_id") or "").strip().upper(),
                    title=normalized_title(opponent.get("title")),
                    rating=int(rating_by_id.get(opponent_id, 0) or 0),
                    round_number=int(game["round_number"]),
                    color=color,
                    points=points,
                )
            )

    for opponents in result.values():
        opponents.sort(key=lambda item: (item.round_number, item.player_id))
    return result


def adjusted_ratings(
    opponents: Sequence[NormOpponent], requirement: NormRequirement
) -> list[int]:
    """1.4.6 — ratings dos adversários como a norma os conta.

    Duas correções, nesta ordem: sem rating vira 1400 e, do que ficar abaixo do
    piso da norma, **um só** adversário sobe até o piso — o de menor rating.
    Subir todos era o erro que fazia qualquer open indicar norma; não subir
    nenhum seria severo demais com quem enfrentou um adversário fraco.
    """
    values = [opponent.rating_for_norm for opponent in opponents]
    below = [index for index, value in enumerate(values) if value < requirement.rating_floor]
    if below:
        lowest = min(below, key=lambda index: values[index])
        values[lowest] = requirement.rating_floor
    return values


def average_rating(values: Sequence[int]) -> int:
    """Ra — média dos adversários, ARREDONDADA ao inteiro.

    Inteiro porque é assim que a FIDE calcula e é assim que o IT3 pede o campo;
    exibir uma casa decimal daria a impressão de precisão que o regulamento não
    usa. Meio ponto sobe (o `round` do Python arredonda para o par).
    """
    if not values:
        return 0
    return int(sum(values) / len(values) + 0.5)


def federation_counts(opponents: Sequence[NormOpponent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for opponent in opponents:
        if not opponent.federation:
            continue
        counts[opponent.federation] = counts.get(opponent.federation, 0) + 1
    return counts
