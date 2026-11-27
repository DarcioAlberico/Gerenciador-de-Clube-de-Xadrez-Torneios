"""Restricoes e preferencias puras de emparceiramento."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.services.constants import player_pairing_name


COLOR_HARD_VIOLATION_PENALTY = 100_000
COLOR_PREFERENCE_PENALTIES = {
    "absolute": 250,
    "strong": 80,
    "mild": 20,
    "none": 0,
}


@dataclass(frozen=True)
class ColorPreference:
    due_color: str | None
    strength: str
    color_imbalance: int
    repeated_color: str | None
    played_games: int

    @property
    def is_absolute(self) -> bool:
        return self.strength == "absolute"


def would_make_three_colors(player_id: int, color: str, histories: dict[int, list[str]]) -> bool:
    history = histories.get(int(player_id), [])
    return len(history) >= 2 and history[-2:] == [color, color]


def is_color_valid_fide(player_id: int, color: str, histories: dict[int, list[str]]) -> bool:
    history = [item for item in histories.get(player_id, []) if item in {"W", "B"}]
    white_count = history.count("W")
    black_count = history.count("B")
    next_white = white_count + (1 if color == "W" else 0)
    next_black = black_count + (1 if color == "B" else 0)
    if abs(next_white - next_black) > 2:
        return False
    if len(history) >= 2 and history[-2:] == [color, color]:
        return False
    return True


def color_hard_violation(player_id: int, color: str, histories: dict[int, list[str]]) -> int:
    return 0 if is_color_valid_fide(player_id, color, histories) else 1


def topscorer_ids(
    standings: dict[int, dict[str, Any]],
    *,
    round_number: int,
    rounds_total: int,
) -> set[int]:
    """Quem e "topscorer" na rodada a ser pareada (FIDE C.04.3, A.7).

    Topscorer e quem tem MAIS de 50% do máximo possível — e o conceito só existe
    na ÚLTIMA rodada do torneio. Ele importa por causa do C.3, o único critério
    de cor ABSOLUTO: dois NÃO-topscorers com a mesma preferência absoluta de cor
    não podem se enfrentar. Dois topscorers podem — e é exatamente o que a última
    rodada costuma exigir, quando os dois líderes precisam se enfrentar e ambos
    devem a mesma cor.

    Sem isso, o motor próprio tratava a cor como absoluta para todo mundo e podia
    recusar (ou piorar) o pareamento que decide o torneio. O motor FIDE (Gacrux),
    que hoje e o padrão, já aplica o C.3 corretamente.
    """
    if rounds_total <= 0 or int(round_number) != int(rounds_total):
        return set()
    # Na rodada R cada jogador disputou R-1 partidas: o máximo possível e R-1.
    limite = (int(round_number) - 1) / 2.0
    return {
        int(player_id)
        for player_id, item in standings.items()
        if float(item.get("points", 0.0) or 0.0) > limite
    }


def color_preference(player_id: int, histories: dict[int, list[str]]) -> ColorPreference:
    """Perfil de preferência de cor no estilo BBP/FIDE Dutch.

    ``due_color`` e a cor que melhora o histórico do jogador; ``strength`` indica
    se a preferência e absoluta, forte, leve ou inexistente.
    """
    history = [item for item in histories.get(int(player_id), []) if item in {"W", "B"}]
    if not history:
        return ColorPreference(None, "none", 0, None, 0)

    white_count = history.count("W")
    black_count = history.count("B")
    signed_balance = white_count - black_count
    lower_color = "B" if signed_balance > 0 else "W"
    last_color = history[-1]
    streak = 1
    for color in reversed(history[:-1]):
        if color != last_color:
            break
        streak += 1

    repeated_color = last_color if streak > 1 else None
    if abs(signed_balance) > 1:
        return ColorPreference(lower_color, "absolute", signed_balance, repeated_color, len(history))
    if repeated_color is not None:
        return ColorPreference(_opposite_color(repeated_color), "absolute", signed_balance, repeated_color, len(history))
    if signed_balance:
        return ColorPreference(lower_color, "strong", signed_balance, None, len(history))
    return ColorPreference(_opposite_color(last_color), "mild", signed_balance, None, len(history))


def color_assignment_cost(
    player_id: int,
    color: str,
    histories: dict[int, list[str]],
) -> tuple[int, int]:
    return (
        color_hard_violation(player_id, color, histories),
        assignment_color_penalty(player_id, color, histories),
    )


def rank_by_player_id(standings: dict[int, dict[str, Any]]) -> dict[int, int]:
    return {
        int(player_id): int(item.get("position", 0) or 0)
        for player_id, item in standings.items()
    }


def select_rating_for_order(
    initial_order: str,
    *,
    rating: int,
    national: int,
    international: int,
    default: int | None = None,
) -> int:
    """Rating correspondente a uma ordem inicial (``initial_order``).

    Fonte única da regra, compartilhada pelo seeding de pareamento e pela
    importação de ratings oficiais. ``default`` cobre as ordens sem regra
    específica ("rating"/"manual"/desconhecida): o seeding usa o próprio
    ``rating`` do jogador (``default=None``); a importação oficial passa o
    melhor rating disponível. Os demais ramos são idênticos para ambos.
    """
    if initial_order == "national_rating":
        return national or rating
    if initial_order == "international_rating":
        return international or rating
    if initial_order == "international_then_national":
        return international or national or rating
    if initial_order == "max_rating":
        return max(national, international, rating)
    return rating if default is None else default


def rating_for_initial_order(player: dict[str, Any], initial_order: str) -> int:
    return select_rating_for_order(
        initial_order,
        rating=int(player.get("rating") or 0),
        national=int(player.get("national_rating") or 0),
        international=int(player.get("international_rating") or 0),
    )


# Ordem dos títulos FIDE na ordem inicial (C.04.2): GM, IM, WGM, FM, WIM, CM,
# WFM, WCM e, por último, sem título. Aceita também o dialeto do TRF (campo
# 011-013 da linha 001: `g`, `m`, `wg`...), que é como o jogador importado vem.
TITLE_SEEDING_ORDER: tuple[tuple[str, ...], ...] = (
    ("GM", "G"),
    ("IM", "M"),
    ("WGM", "WG"),
    ("FM", "F"),
    ("WIM", "WM"),
    ("CM", "C"),
    ("WFM", "WF"),
    ("WCM", "WC"),
)
_TITLE_RANK = {alias: rank for rank, aliases in enumerate(TITLE_SEEDING_ORDER) for alias in aliases}


def title_seeding_rank(title: Any) -> int:
    """Posição do título na ordem inicial (0 = GM); sem título fica por último."""
    return _TITLE_RANK.get(str(title or "").strip().upper(), len(TITLE_SEEDING_ORDER))


def seeding_key(player: dict[str, Any], initial_order: str = "rating") -> tuple[Any, ...]:
    """Chave ÚNICA da ordem inicial (RGS-13): o nº 1 é o primeiro desta chave.

    FIDE C.04.2: força (o rating que `initial_order` escolhe), depois título
    FIDE, depois ordem alfabética — salvo regulamento. O nome é o de
    pareamento ("Sobrenome, Nome"), o mesmo que o TRF grava; o `id` só
    garante uma ordem total entre homônimos.

    Usada pela numeração do TRF (logo, pelo Gacrux), pelo motor reserva e
    pela aceleração. Antes eram três ordens: o TRF numerava pelo primeiro
    rating não nulo e ignorava `initial_order`, e os dois motores desempatavam
    o rating só pelo nome — "Alpha" sem título passava à frente de "Zeta" GM.
    """
    nome = player_pairing_name(player) or str(player.get("name") or "")
    return (
        -rating_for_initial_order(player, initial_order),
        title_seeding_rank(player.get("title")),
        nome.casefold(),
        int(player.get("id") or 0),
    )


def seeding_order(
    players: list[dict[str, Any]],
    settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Jogadores na ordem inicial do torneio (índice 0 = nº 1)."""
    initial_order = str((settings or {}).get("initial_order") or "rating")
    return sorted(players, key=lambda player: seeding_key(player, initial_order))


def pairing_order_key(
    player: dict[str, Any],
    standings: dict[int, dict[str, Any]],
) -> tuple[float, float, float, float, int, int, str]:
    standing = standings.get(player["id"], {})
    return (
        -float(standing.get("points", 0.0) or 0.0),
        -float(standing.get("buchholz", 0.0) or 0.0),
        -float(standing.get("buchholz_median", 0.0) or 0.0),
        -float(standing.get("sonneborn_berger", 0.0) or 0.0),
        -int(standing.get("wins", 0) or 0),
        -int(player["rating"] or 0),
        player["name"].casefold(),
    )


def team_pairing_order_key(
    team: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    seed_ratings: dict[int, int],
) -> tuple[float, float, int, str]:
    team_id = int(team["id"])
    standing = standings.get(team_id, {})
    return (
        -float(standing.get("match_points", 0.0) or 0.0),
        -float(standing.get("game_points", 0.0) or 0.0),
        -int(seed_ratings.get(team_id, 0)),
        str(team["name"]).casefold(),
    )


def choose_bye_player(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    bye_player_ids: set[int],
) -> dict[str, Any]:
    candidates = [player for player in players if player["id"] not in bye_player_ids]
    if not candidates:
        candidates = players
    return min(
        candidates,
        key=lambda player: (
            standings.get(player["id"], {}).get("points", 0.0),
            int(player["rating"] or 0),
            player["name"].casefold(),
        ),
    )


def choose_team_bye(
    teams: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    bye_team_ids: set[int],
    seed_ratings: dict[int, int],
) -> dict[str, Any]:
    candidates = [team for team in teams if int(team["id"]) not in bye_team_ids]
    if not candidates:
        candidates = teams
    return min(
        candidates,
        key=lambda team: (
            float(standings.get(int(team["id"]), {}).get("match_points", 0.0) or 0.0),
            float(standings.get(int(team["id"]), {}).get("game_points", 0.0) or 0.0),
            seed_ratings.get(int(team["id"]), 0),
            str(team["name"]).casefold(),
        ),
    )


def float_penalty(
    player_id: int,
    direction: str,
    float_histories: dict[int, list[str]],
) -> int:
    history = float_histories.get(player_id, [])
    penalty = history.count(direction) * 25
    if history[-2:] == [direction, direction]:
        penalty += 300
    elif history[-1:] == [direction]:
        penalty += 120
    return penalty


def assignment_color_penalty(
    player_id: int,
    color: str,
    histories: dict[int, list[str]],
) -> int:
    preference = color_preference(player_id, histories)
    next_balance = preference.color_imbalance + (1 if color == "W" else -1)
    penalty = abs(next_balance) * 12

    if preference.due_color is not None and color != preference.due_color:
        penalty += COLOR_PREFERENCE_PENALTIES[preference.strength]

    return penalty


def _opposite_color(color: str) -> str:
    return "B" if color == "W" else "W"


def choose_colors(
    player: dict[str, Any],
    opponent: dict[str, Any],
    histories: dict[int, list[str]],
    ranking: Mapping[int, tuple[Any, ...]] | None = None,
    initial_color: str = "W",
) -> tuple[int, int]:
    """(brancas, pretas) da mesa. Preferências primeiro; no empate, C.04.3 E.3–E.5.

    `ranking` e a ordem de classificação do holandês: `{player_id: (-pontos,
    numero_de_pareamento)}` — menor e melhor. Sem ele (equipes, avaliação de
    custo) o empate continua indo ao maior rating, como antes.
    `initial_color` e a cor inicial do torneio (RGS-14), a do E.5.
    """
    player_id = player["id"]
    opponent_id = opponent["id"]
    first_hard, first_penalty = color_assignment_cost(player_id, "W", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "B", histories)
    first_hard += opponent_hard
    first_penalty += opponent_penalty

    second_hard, second_penalty = color_assignment_cost(player_id, "B", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "W", histories)
    second_hard += opponent_hard
    second_penalty += opponent_penalty

    if (first_hard, first_penalty) < (second_hard, second_penalty):
        return player_id, opponent_id
    if (second_hard, second_penalty) < (first_hard, first_penalty):
        return opponent_id, player_id

    if ranking is not None:
        return _colors_by_ranking(
            int(player_id), int(opponent_id), histories, ranking, initial_color or INITIAL_COLOR
        )
    if int(player["rating"] or 0) >= int(opponent["rating"] or 0):
        return player_id, opponent_id
    return opponent_id, player_id


# Cor inicial quando ninguém informa outra. A do torneio e sorteada e gravada
# (`tournament_settings.initial_color`, RGS-14) e chega aqui pelo argumento.
INITIAL_COLOR = "W"


def _colors_by_ranking(
    player_id: int,
    opponent_id: int,
    histories: dict[int, list[str]],
    ranking: Mapping[int, tuple[Any, ...]],
    initial_color: str = INITIAL_COLOR,
) -> tuple[int, int]:
    """Empate das preferências de cor: C.04.3 E.3, E.4 e E.5 (RGS-18).

    E.3 — alternar a partir da rodada mais recente em que um teve brancas e o
    outro pretas (só partidas jogadas: C.04.2, W.O. e bye não tem cor);
    E.4 — atender a preferência do mais bem classificado (pontos, depois
    número de pareamento); E.5 — sem preferência, o mais bem classificado
    recebe a cor inicial se o número dele e ímpar, e a oposta se e par.
    Antes o empate ia ao maior rating, que não é critério de cor na FIDE.
    """
    played_a = [color for color in histories.get(player_id, []) if color in {"W", "B"}]
    played_b = [color for color in histories.get(opponent_id, []) if color in {"W", "B"}]
    for color_a, color_b in zip(reversed(played_a), reversed(played_b)):
        if color_a != color_b:
            return (player_id, opponent_id) if color_a == "B" else (opponent_id, player_id)

    worst = (float("inf"),)
    higher, lower = sorted(
        (player_id, opponent_id), key=lambda pid: (tuple(ranking.get(pid, worst)), pid)
    )
    due = color_preference(higher, histories).due_color
    if due is None:
        number = int((ranking.get(higher) or (0, 0))[-1] or 0)
        due = initial_color if number % 2 == 1 else _opposite_color(initial_color)
    return (higher, lower) if due == "W" else (lower, higher)


def choose_team_colors(
    team: dict[str, Any],
    opponent: dict[str, Any],
    histories: dict[int, list[str]],
    seed_ratings: dict[int, int],
) -> tuple[int, int]:
    team_id = int(team["id"])
    opponent_id = int(opponent["id"])
    first_hard, first_penalty = color_assignment_cost(team_id, "W", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "B", histories)
    first_hard += opponent_hard
    first_penalty += opponent_penalty

    second_hard, second_penalty = color_assignment_cost(team_id, "B", histories)
    opponent_hard, opponent_penalty = color_assignment_cost(opponent_id, "W", histories)
    second_hard += opponent_hard
    second_penalty += opponent_penalty

    if (first_hard, first_penalty) < (second_hard, second_penalty):
        return team_id, opponent_id
    if (second_hard, second_penalty) < (first_hard, first_penalty):
        return opponent_id, team_id
    if seed_ratings.get(team_id, 0) >= seed_ratings.get(opponent_id, 0):
        return team_id, opponent_id
    return opponent_id, team_id


def pair_penalty(
    player: dict[str, Any],
    opponent: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    topscorers: frozenset[int] | set[int] = frozenset(),
) -> float:
    player_id = player["id"]
    opponent_id = opponent["id"]
    player_score = float(standings.get(player_id, {}).get("points", 0.0) or 0.0)
    opponent_score = float(standings.get(opponent_id, {}).get("points", 0.0) or 0.0)
    score_diff = abs(player_score - opponent_score)
    penalty = score_diff * score_diff_penalty

    if score_diff:
        penalty += score_group_float_penalty
        if player_score < opponent_score:
            penalty += float_penalty(player_id, "up", float_histories)
            penalty += float_penalty(opponent_id, "down", float_histories)
        else:
            penalty += float_penalty(player_id, "down", float_histories)
            penalty += float_penalty(opponent_id, "up", float_histories)

    rank_distance = abs(
        rank_by_player_id.get(player_id, 0)
        - rank_by_player_id.get(opponent_id, 0)
    )
    penalty += rank_distance * (4 if not score_diff else 1)

    if frozenset((player_id, opponent_id)) in played_pairs:
        penalty += repeat_pairing_penalty

    white_a, _black_a = choose_colors(player, opponent, histories)
    if white_a == player_id:
        hard_violations = color_hard_violation(player_id, "W", histories)
        hard_violations += color_hard_violation(opponent_id, "B", histories)
        color_penalty = assignment_color_penalty(player_id, "W", histories)
        color_penalty += assignment_color_penalty(opponent_id, "B", histories)
    else:
        hard_violations = color_hard_violation(player_id, "B", histories)
        hard_violations += color_hard_violation(opponent_id, "W", histories)
        color_penalty = assignment_color_penalty(player_id, "B", histories)
        color_penalty += assignment_color_penalty(opponent_id, "W", histories)

    # C.3 (FIDE C.04.3) e critério ABSOLUTO, e não vale entre dois topscorers
    # (A.7) — quem trata essa exceção e a busca estrita (`search_dutch_pairing`),
    # que decide o que PODE ser pareado. Aqui e custo de QUALIDADE (C11): a
    # violação de cor continua cara para todos, topscorer ou não, senão o motor
    # deixaria de EVITA-LA quando havia alternativa.
    return penalty + hard_violations * COLOR_HARD_VIOLATION_PENALTY + color_penalty


def team_pair_penalty(
    team: dict[str, Any],
    opponent: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    float_histories: dict[int, list[str]] | None = None,
) -> float:
    """Custo de um confronto por equipes.

    `float_histories` traz a penalidade de FLOAT REPETIDO, que o individual já
    tinha e aqui faltava (PAR-04): sem ela, a mesma equipe podia descer de grupo
    rodada após rodada sem que o motor preferisse outra.
    """
    team_id = int(team["id"])
    opponent_id = int(opponent["id"])
    team_score = float(standings.get(team_id, {}).get("match_points", 0.0) or 0.0)
    opponent_score = float(standings.get(opponent_id, {}).get("match_points", 0.0) or 0.0)
    score_diff = abs(team_score - opponent_score)
    penalty = score_diff * score_diff_penalty
    if score_diff:
        penalty += score_group_float_penalty
        if float_histories is not None:
            if team_score < opponent_score:
                penalty += float_penalty(team_id, "up", float_histories)
                penalty += float_penalty(opponent_id, "down", float_histories)
            else:
                penalty += float_penalty(team_id, "down", float_histories)
                penalty += float_penalty(opponent_id, "up", float_histories)

    rank_distance = abs(rank_by_team_id.get(team_id, 0) - rank_by_team_id.get(opponent_id, 0))
    penalty += rank_distance * (4 if not score_diff else 1)

    if frozenset((team_id, opponent_id)) in played_pairs:
        penalty += repeat_pairing_penalty
    return penalty


def greedy_player_pairs(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    topscorers: frozenset[int] | set[int] = frozenset(),
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pending = players[:]
    pairs = []
    while pending:
        player = pending.pop(0)
        opponent = min(
            pending,
            key=lambda candidate: pair_penalty(
                player,
                candidate,
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
                topscorers=topscorers,
            ),
        )
        pending.remove(opponent)
        pairs.append((player, opponent))
    return pairs


def optimal_player_pairs(
    players: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    float_histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    rank_by_player_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    topscorers: frozenset[int] | set[int] = frozenset(),
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    player_by_id = {int(player["id"]): player for player in players}
    penalty_cache: dict[tuple[int, int], float] = {}

    def penalty(player_id: int, opponent_id: int) -> float:
        key = (player_id, opponent_id)
        if key not in penalty_cache:
            penalty_cache[key] = pair_penalty(
                player_by_id[player_id],
                player_by_id[opponent_id],
                standings,
                histories,
                float_histories,
                played_pairs,
                rank_by_player_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
                topscorers=topscorers,
            )
        return penalty_cache[key]

    best_cost = float("inf")
    best_pairs: list[tuple[int, int]] = []
    seen_costs: dict[tuple[int, ...], float] = {}

    def search(
        remaining: tuple[int, ...],
        selected_pairs: list[tuple[int, int]],
        current_cost: float,
    ) -> None:
        nonlocal best_cost, best_pairs
        if current_cost >= best_cost:
            return
        if current_cost >= seen_costs.get(remaining, float("inf")):
            return
        seen_costs[remaining] = current_cost
        if not remaining:
            best_cost = current_cost
            best_pairs = selected_pairs[:]
            return

        player_id = remaining[0]
        candidates = sorted(remaining[1:], key=lambda candidate_id: penalty(player_id, candidate_id))
        for opponent_id in candidates:
            next_remaining = tuple(
                item_id for item_id in remaining[1:] if item_id != opponent_id
            )
            search(
                next_remaining,
                selected_pairs + [(player_id, opponent_id)],
                current_cost + penalty(player_id, opponent_id),
            )

    search(tuple(player_by_id), [], 0.0)
    if not best_pairs:
        return greedy_player_pairs(
            players,
            standings,
            histories,
            float_histories,
            played_pairs,
            rank_by_player_id,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
            topscorers=topscorers,
        )
    return [(player_by_id[player_id], player_by_id[opponent_id]) for player_id, opponent_id in best_pairs]


def greedy_team_pairs(
    teams: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    float_histories: dict[int, list[str]] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pending = teams[:]
    pairs = []
    while pending:
        team = pending.pop(0)
        opponent = min(
            pending,
            key=lambda candidate: team_pair_penalty(
                team,
                candidate,
                standings,
                played_pairs,
                rank_by_team_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
                float_histories=float_histories,
            ),
        )
        pending.remove(opponent)
        pairs.append((team, opponent))
    return pairs


def optimal_team_pairs(
    teams: list[dict[str, Any]],
    standings: dict[int, dict[str, Any]],
    played_pairs: set[frozenset[int]],
    rank_by_team_id: dict[int, int],
    *,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    float_histories: dict[int, list[str]] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    team_by_id = {int(team["id"]): team for team in teams}
    penalty_cache: dict[tuple[int, int], float] = {}

    def penalty(team_id: int, opponent_id: int) -> float:
        key = (team_id, opponent_id)
        if key not in penalty_cache:
            penalty_cache[key] = team_pair_penalty(
                team_by_id[team_id],
                team_by_id[opponent_id],
                standings,
                played_pairs,
                rank_by_team_id,
                repeat_pairing_penalty=repeat_pairing_penalty,
                score_group_float_penalty=score_group_float_penalty,
                score_diff_penalty=score_diff_penalty,
                float_histories=float_histories,
            )
        return penalty_cache[key]

    best_cost = float("inf")
    best_pairs: list[tuple[int, int]] = []
    seen_costs: dict[tuple[int, ...], float] = {}

    def search(
        remaining: tuple[int, ...],
        selected_pairs: list[tuple[int, int]],
        current_cost: float,
    ) -> None:
        nonlocal best_cost, best_pairs
        if current_cost >= best_cost:
            return
        if current_cost >= seen_costs.get(remaining, float("inf")):
            return
        seen_costs[remaining] = current_cost
        if not remaining:
            best_cost = current_cost
            best_pairs = selected_pairs[:]
            return

        team_id = remaining[0]
        candidates = sorted(remaining[1:], key=lambda candidate_id: penalty(team_id, candidate_id))
        for opponent_id in candidates:
            next_remaining = tuple(item_id for item_id in remaining[1:] if item_id != opponent_id)
            search(
                next_remaining,
                selected_pairs + [(team_id, opponent_id)],
                current_cost + penalty(team_id, opponent_id),
            )

    search(tuple(team_by_id), [], 0.0)
    if not best_pairs:
        return greedy_team_pairs(
            teams,
            standings,
            played_pairs,
            rank_by_team_id,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
            float_histories=float_histories,
        )
    return [(team_by_id[team_id], team_by_id[opponent_id]) for team_id, opponent_id in best_pairs]
