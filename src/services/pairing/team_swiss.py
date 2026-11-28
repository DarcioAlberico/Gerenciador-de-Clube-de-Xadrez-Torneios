"""Helpers puros do emparceiramento por equipes."""

from __future__ import annotations

from typing import Any

from src.domain.numbers import setting_number
from src.services.constants import AppError
from src.services.pairing.constraints import (
    COLOR_HARD_VIOLATION_PENALTY,
    choose_team_bye,
    color_hard_violation,
    choose_team_colors,
    team_pair_penalty,
    team_pairing_order_key,
)
from src.services.pairing.fide_dutch import colors_admissible
from src.services.pairing.round_search import (
    bracket_pairing,
    enforce_absolute,
    greedy_pairs,
    optimal_pairs,
    score_group_pairs,
)


class TeamWithoutPlayersError(AppError):
    """Equipe ativa sem nenhum jogador presente (EQ-02.4): pede a decisão do árbitro.

    Nada é gravado. O árbitro escolhe: tirar a equipe da rodada (bye Z
    solicitado) ou confirmar o W.O. do confronto inteiro
    (``generate_next_round(..., forfeit_empty_teams=True)``).
    """

    def __init__(self, team_names: list[str]) -> None:
        self.team_names = list(team_names)
        nomes = ", ".join(self.team_names)
        super().__init__(
            f"Sem nenhum jogador presente: {nomes}. Registre um bye Z para a equipe "
            "nesta rodada ou confirme o W.O. do confronto inteiro."
        )


def _starter_board(assignment: dict[str, Any], boards_count: int) -> int | None:
    """Tabuleiro declarado do titular, se estiver entre 1 e `boards_count`."""
    if assignment.get("role") != "starter" or not assignment.get("board_number"):
        return None
    board_number = int(assignment["board_number"])
    return board_number if 1 <= board_number <= boards_count else None


def team_seed(assignments: list[dict[str, Any]], boards_count: int) -> int:
    """Semente da equipe: média dos ratings dos titulares declarados por tabuleiro.

    Uma só conta (EQ-01.3) para a geração, o todos-contra-todos e o TRF25. Conta
    o titular DECLARADO, presente ou não: a semente mede a equipe inscrita, não
    a escalação da rodada — e é calculada uma vez, quando o TPN é atribuído.
    """
    ratings = [
        int(assignment.get("player_rating") or 0)
        for assignment in assignments
        if _starter_board(assignment, boards_count)
    ]
    return round(sum(ratings) / max(boards_count, 1))


def team_lineup(
    assignments: list[dict[str, Any]],
    boards_count: int,
) -> dict[int, int | None]:
    """Escalação proposta da rodada: tabuleiro → player_id, ou None (vaga) (EQ-02).

    O pareamento de EQUIPES não depende dela; ela só monta os tabuleiros. A
    regra segue a ordem declarada: o titular presente senta no próprio
    tabuleiro; no lugar do ausente senta a reserva presente seguinte (ordem do
    cadastro). Sem reserva, os de baixo sobem e as vagas ficam no fim — o
    tabuleiro vazio sai por W.O. (`team_match_payload`).
    """
    titulares: dict[int, dict[str, Any]] = {}
    for assignment in assignments:
        board_number = _starter_board(assignment, boards_count)
        if board_number:
            titulares[board_number] = assignment
    sentados = {id(item) for item in titulares.values()}
    reservas = sorted(
        (
            item
            for item in assignments
            if id(item) not in sentados and item.get("player_status") == "active"
        ),
        key=lambda item: (int(item.get("board_number") or 9999), int(item.get("id") or 0)),
    )

    escalados: list[int] = []
    for board_number in range(1, boards_count + 1):
        titular = titulares.get(board_number)
        if titular and titular.get("player_status") == "active":
            escalados.append(int(titular["player_id"]))
        elif reservas:
            escalados.append(int(reservas.pop(0)["player_id"]))
    vagas: list[int | None] = [None] * (boards_count - len(escalados))
    return dict(enumerate([*escalados, *vagas], start=1))


def team_seed_order_key(team: dict[str, Any], seed_ratings: dict[int, int]) -> tuple[int, str]:
    """Ordem da semente: mais forte primeiro, nome como desempate (EQ-01)."""
    return (-int(seed_ratings[int(team["id"])]), str(team["name"]).casefold())


def assign_team_pairing_numbers(
    teams: list[dict[str, Any]],
    seed_ratings: dict[int, int],
) -> dict[int, int]:
    """TPN de cada equipe: o gravado fica; quem não tem recebe o próximo (EQ-01).

    Na R1 ninguém tem TPN e a numeração sai da semente — a mesma ordem que a R1
    sempre usou. Depois, o número gravado não muda mais: rating novo, status ou
    escalação não reordenam ninguém. Equipe sem TPN (inscrita depois) recebe o
    número seguinte ao maior, em ordem de semente — o C.04.2 permite numerar o
    entrante tardio assim e proíbe renumerar depois da R4.
    """
    numbers = {
        int(team["id"]): int(team["pairing_number"])
        for team in teams
        if team.get("pairing_number")
    }
    pending = sorted(
        (team for team in teams if int(team["id"]) not in numbers),
        key=lambda team: team_seed_order_key(team, seed_ratings),
    )
    following = max(numbers.values(), default=0)
    for team in pending:
        following += 1
        numbers[int(team["id"])] = following
    return numbers


def pairing_strengths(pairing_numbers: dict[int, int]) -> dict[int, int]:
    """TPN como "força" para o motor: maior = mais forte, logo a ordem do TPN.

    Todo critério do motor que usa semente (`team_pairing_order_key`, cor e bye
    alocado) compara força; com `-TPN` a comparação é exatamente a do número
    gravado, e não a de um rating que pode ter mudado.
    """
    return {team_id: -number for team_id, number in pairing_numbers.items()}


def tpn_from_first_round(matches: list[dict[str, Any]], method: str) -> dict[int, int]:
    """TPN lido da R1 JÁ GERADA (migração de torneio em andamento, EQ-01).

    É a inversa de `first_round_team_matches` (Suíço: o confronto k põe a
    k-ésima de cima contra a k-ésima de baixo, cores alternadas; o bye alocado
    é a última) e de `round_robin_team_matches` (rodada 1 do círculo). Não
    recalcula nada: lê a ordem que a R1 usou. Byes solicitados (F/H/Z) não
    têm posição na R1 e ficam de fora — recebem o próximo número depois.
    """
    paired = [m for m in matches if not m.get("is_bye")]
    allocated_bye = [
        int(m["white_team_id"])
        for m in matches
        if m.get("is_bye") and str(m.get("result") or "BYE").strip().upper() == "BYE"
    ]
    ordered = sorted(paired, key=lambda m: int(m.get("match_number") or 0))
    if method == "round_robin":
        total = 2 * len(ordered) + (2 if allocated_bye else 0)
        position: dict[int, int] = {}
        if allocated_bye:
            position[allocated_bye[0]] = 0
        for index, match in enumerate(ordered, start=1 if allocated_bye else 0):
            white, black = int(match["white_team_id"]), int(match["black_team_id"])
            superior, inferior = (white, black) if index == 0 else (black, white)
            position[superior] = index
            position[inferior] = total - 1 - index
        return {team_id: index + 1 for team_id, index in position.items()}

    half = len(ordered)
    numbers: dict[int, int] = {}
    for k, match in enumerate(ordered, start=1):
        white, black = int(match["white_team_id"]), int(match["black_team_id"])
        upper, lower = (white, black) if k % 2 == 1 else (black, white)
        numbers[upper] = k
        numbers[lower] = half + k
    for team_id in allocated_bye[:1]:
        numbers[team_id] = 2 * half + 1
    return numbers


def team_lineup_warnings(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int | None]],
) -> list[dict[str, Any]]:
    """Equipes com escalação incompleta na rodada (EQ-02.5): aviso, nunca erro.

    `empty` marca a equipe sem NENHUM jogador presente — a única que pede
    confirmação do árbitro antes de gerar (EQ-02.4).
    """
    avisos: list[dict[str, Any]] = []
    for team in teams:
        lineup = rosters.get(int(team["id"]), {})
        vagas = [board for board, player_id in sorted(lineup.items()) if player_id is None]
        if not vagas:
            continue
        avisos.append(
            {
                "team_id": int(team["id"]),
                "team_name": str(team.get("name") or team["id"]),
                "empty_boards": vagas,
                # Equipe DESATIVADA no todos-contra-todos já é decisão do
                # árbitro (perde por W.O.): não pede confirmação de novo.
                "empty": len(vagas) == len(lineup) and bool(team.get("active", 1)),
            }
        )
    return avisos


def _empty_seat_result(white_player_id: int | None, black_player_id: int | None) -> str:
    """Tabuleiro com vaga já nasce com o W.O. de quem não tem jogador."""
    if white_player_id is None and black_player_id is None:
        return "0F-0F"
    if white_player_id is None:
        return "0F-1F"
    if black_player_id is None:
        return "1F-0F"
    return ""


def team_bye_points(
    bye_type: Any,
    *,
    win_points: float,
    draw_points: float,
    loss_points: float,
    boards_count: int,
) -> tuple[float, float]:
    """Match/game points de um bye de equipe conforme o tipo FIDE (§6.1).

    Convenção do projeto, proporcional ao bye individual (F=1.0/H=0.5/Z=0.0):
    - F (full) e `BYE` (bye alocado): vitória cheia → win_points e boards game points;
    - H (half): empate → draw_points e metade dos game points (boards/2);
    - Z (zero): derrota → loss_points e zero game points.
    """
    code = str(bye_type or "").strip().upper()
    if code == "H":
        return draw_points, boards_count / 2.0
    if code == "Z":
        return loss_points, 0.0
    return win_points, float(boards_count)


def team_bye_summary(
    match: dict[str, Any],
    *,
    win_points: float,
    boards_count: int,
    draw_points: float = 0.0,
    loss_points: float = 0.0,
) -> dict[str, Any]:
    """Resumo de fechamento de um confronto de bye, pontuado pelo tipo (F/H/Z).

    O tipo vem do `result` do confronto (gravado na geração); `BYE` = bye
    alocado pelo pareamento, tratado como vitória cheia (comportamento histórico).
    """
    match_points, game_points = team_bye_points(
        match.get("result"),
        win_points=win_points,
        draw_points=draw_points,
        loss_points=loss_points,
        boards_count=boards_count,
    )
    return {
        "team_match_id": int(match["id"]),
        "result": str(match.get("result") or "BYE"),
        "white_match_points": match_points,
        "black_match_points": 0.0,
        "white_game_points": game_points,
        "black_game_points": 0.0,
    }


def team_match_summary(
    match: dict[str, Any],
    boards: list[dict[str, Any]],
    white_team_player_ids: set[int],
    black_team_player_ids: set[int],
    result_points: dict[str, tuple[float, float]],
    *,
    win_points: float,
    loss_points: float,
    draw_points: float,
) -> dict[str, Any]:
    """Soma os pontos de partida de um confronto fechado de equipes.

    Atribui os pontos de cada tabuleiro à equipe correta (tabuleiros pares
    têm as cores invertidas) e converte o placar de jogo em pontos de match.
    """
    white_game_points = 0.0
    black_game_points = 0.0
    for board in boards:
        resultado = str(board.get("result") or "")
        if resultado not in result_points:
            # Era `result_points[...]` cru: um tabuleiro em branco ou com código
            # desconhecido subia como KeyError, que a tela mostrava como "erro
            # inesperado" com código de log — para uma situação previsível e que
            # o árbitro resolve sozinho (PAR-04).
            raise AppError(
                f"Tabuleiro {board.get('board_number', '?')} do confronto tem "
                f"resultado inválido ({resultado or 'em branco'}). "
                "Preencha todos os tabuleiros antes de fechar a rodada."
            )
        white_points, black_points = result_points[resultado]
        if board.get("white_player_id") in white_team_player_ids:
            white_game_points += white_points
        elif board.get("white_player_id") in black_team_player_ids:
            black_game_points += white_points

        if board.get("black_player_id") in white_team_player_ids:
            white_game_points += black_points
        elif board.get("black_player_id") in black_team_player_ids:
            black_game_points += black_points

    if white_game_points > black_game_points:
        match_result = "1-0"
        white_match_points, black_match_points = win_points, loss_points
    elif black_game_points > white_game_points:
        match_result = "0-1"
        white_match_points, black_match_points = loss_points, win_points
    else:
        match_result = "1/2-1/2"
        white_match_points = black_match_points = draw_points

    return {
        "team_match_id": int(match["id"]),
        "result": match_result,
        "white_match_points": white_match_points,
        "black_match_points": black_match_points,
        "white_game_points": round(white_game_points, 2),
        "black_game_points": round(black_game_points, 2),
    }


def team_match_payload(
    match_number: int,
    white_team_id: int,
    black_team_id: int,
    rosters: dict[int, dict[int, int | None]],
    boards_count: int,
) -> dict[str, Any]:
    boards = []
    for board_number in range(1, boards_count + 1):
        if board_number % 2 == 1:
            white_player_id = rosters[white_team_id].get(board_number)
            black_player_id = rosters[black_team_id].get(board_number)
        else:
            white_player_id = rosters[black_team_id].get(board_number)
            black_player_id = rosters[white_team_id].get(board_number)
        boards.append(
            {
                "board_number": board_number,
                "white_player_id": white_player_id,
                "black_player_id": black_player_id,
                "result": _empty_seat_result(white_player_id, black_player_id),
            }
        )
    return {
        "match_number": match_number,
        "white_team_id": white_team_id,
        "black_team_id": black_team_id,
        "result": "",
        "is_bye": 0,
        "boards": boards,
    }


def team_bye_payload(
    match_number: int,
    team_id: int,
    settings: dict[str, Any],
    boards_count: int,
    bye_type: str = "BYE",
) -> dict[str, Any]:
    """Confronto de bye de equipe. `bye_type` ∈ {BYE (alocado), F, H, Z}.

    O tipo é gravado em `result` e define os pontos; o fechamento recalcula
    pelo mesmo `result` (ver team_bye_summary)."""
    match_points, game_points = team_bye_points(
        bye_type,
        win_points=setting_number(settings, "team_match_win_points", 2.0),
        draw_points=setting_number(settings, "team_match_draw_points", 1.0),
        loss_points=float(settings.get("team_match_loss_points", 0.0) or 0.0),
        boards_count=boards_count,
    )
    return {
        "match_number": match_number,
        "white_team_id": team_id,
        "black_team_id": None,
        "result": str(bye_type or "BYE").strip().upper(),
        "white_match_points": match_points,
        "black_match_points": 0.0,
        "white_game_points": game_points,
        "black_game_points": 0.0,
        "is_bye": 1,
        "boards": [],
    }


def round_robin_team_matches(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int]],
    seed_ratings: dict[int, int],
    boards_count: int,
    settings: dict[str, Any],
    round_number: int,
) -> list[dict[str, Any]]:
    """Todos contra todos por equipes (Berger), rodada a rodada.

    Rotação de círculo: a primeira equipe fica parada e as demais giram, o que
    garante que cada par se encontre exatamente uma vez. Número ímpar de equipes
    ganha uma equipe fantasma, e quem cai com ela recebe o bye da rodada.

    O círculo sai do TPN GRAVADO (EQ-01): quem chama passa `seed_ratings` como a
    força derivada do TPN (`pairing_strengths`) e o campo inteiro que recebeu
    TPN, inclusive a equipe desativada no meio do evento — que perde por W.O.
    (escalação vazia), sem remexer os confrontos das outras. Antes o círculo
    era refeito a cada rodada a partir da lista de equipes ATIVAS.

    A cor da EQUIPE alterna com a paridade da rodada — sem isso, a primeira
    equipe (a que não gira) jogaria de brancas em todas as rodadas. As cores dos
    tabuleiros dentro do confronto continuam saindo do `team_match_payload`, que
    inverte a cada tabuleiro par.
    """
    ordered = sorted(teams, key=lambda team: team_seed_order_key(team, seed_ratings))
    if len(ordered) % 2 == 1:
        ordered.append({"id": -1, "name": "BYE"})

    total = len(ordered)
    if round_number > total - 1:
        raise AppError(
            "Todos contra todos por equipes: o número máximo de rodadas "
            f"({total - 1}) já foi atingido."
        )

    girado = [ordered[0]]
    for index in range(1, total):
        deslocamento = round_number - 1
        girado.append(ordered[((index - 1 - deslocamento) % (total - 1)) + 1])

    superior = girado[: total // 2]
    inferior = girado[total // 2:]
    inferior.reverse()

    matches: list[dict[str, Any]] = []
    for index in range(total // 2):
        if (round_number % 2 == 1 and index == 0) or (round_number % 2 == 0 and index > 0):
            branca, preta = superior[index], inferior[index]
        else:
            branca, preta = inferior[index], superior[index]

        if int(branca["id"]) == -1 or int(preta["id"]) == -1:
            folga = preta if int(branca["id"]) == -1 else branca
            matches.append(
                team_bye_payload(len(matches) + 1, int(folga["id"]), settings, boards_count)
            )
            continue
        matches.append(
            team_match_payload(
                len(matches) + 1,
                int(branca["id"]),
                int(preta["id"]),
                rosters,
                boards_count,
            )
        )
    return matches


def first_round_team_matches(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int]],
    seed_ratings: dict[int, int],
    boards_count: int,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    ordered = sorted(teams, key=lambda team: team_seed_order_key(team, seed_ratings))
    pairable = ordered[:]
    bye_team = None
    if len(pairable) % 2 == 1:
        bye_team = min(
            pairable,
            key=lambda team: (seed_ratings[int(team["id"])], str(team["name"]).casefold()),
        )
        pairable.remove(bye_team)

    half = len(pairable) // 2
    upper = pairable[:half]
    lower = pairable[half:]
    matches: list[dict[str, Any]] = []
    for index, team in enumerate(upper, start=1):
        opponent = lower[index - 1]
        if index % 2 == 1:
            white_team_id = int(team["id"])
            black_team_id = int(opponent["id"])
        else:
            white_team_id = int(opponent["id"])
            black_team_id = int(team["id"])
        matches.append(
            team_match_payload(
                index,
                white_team_id,
                black_team_id,
                rosters,
                boards_count,
            )
        )

    if bye_team:
        matches.append(team_bye_payload(len(matches) + 1, int(bye_team["id"]), settings, boards_count))
    return matches


def baku_first_round_team_matches(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int]],
    seed_ratings: dict[int, int],
    boards_count: int,
    settings: dict[str, Any],
    accelerated_ids: set[int] | list[int],
) -> list[dict[str, Any]]:
    """R1 com Baku (C.04.7, EQ-07): o GA e o GB são dois grupos de pontuação.

    Com o VP, o GA começa com os pontos de uma vitória e o GB com zero; cada
    grupo é pareado como a R1 de sempre (metade de cima × metade de baixo, cor
    alternada pelo TPN). O GA tem tamanho par (2 × ⌈N/4⌉), então a paridade
    do TPN se mantém no GB. Se um bye solicitado deixa o GA ímpar, o último
    dele desce para o GB, como o flutuante de um grupo ímpar. O bye alocado,
    se houver, sai do fim do GB.
    """
    acelerados = {int(team_id) for team_id in accelerated_ids}
    ordered = sorted(teams, key=lambda team: team_seed_order_key(team, seed_ratings))
    grupo_a = [team for team in ordered if int(team["id"]) in acelerados]
    grupo_b = [team for team in ordered if int(team["id"]) not in acelerados]
    if len(grupo_a) % 2 == 1:
        grupo_b.insert(0, grupo_a.pop())
    matches: list[dict[str, Any]] = []
    for grupo in (grupo_a, grupo_b):
        if not grupo:
            continue
        for match in first_round_team_matches(grupo, rosters, seed_ratings, boards_count, settings):
            matches.append({**match, "match_number": len(matches) + 1})
    return matches


def team_round_violations(
    matches: list[dict[str, Any]],
    played_pairs: set[frozenset[int]],
    bye_team_ids: set[int],
    names: dict[int, str] | None = None,
) -> list[str]:
    """O que a rodada de equipes fere dos critérios absolutos (FIDE C.04.1).

    Confronto já jogado (ou proibido, que chega no mesmo conjunto) e PAB para
    quem já recebeu um. É a guarda do RG2-07a: o motor de equipes trata a
    repetição como custo e escolhe o bye antes de testar o resto, então a
    rodada é conferida depois de pronta. Lista vazia: a rodada vale.
    """
    nome = (names or {}).get
    problemas: list[str] = []
    for match in matches:
        brancas = match.get("white_team_id")
        pretas = match.get("black_team_id")
        if match.get("is_bye") or not pretas:
            if brancas is not None and int(brancas) in bye_team_ids:
                problemas.append(
                    f"{nome(int(brancas)) or f'Equipe {brancas}'} receberia um segundo bye (PAB)"
                )
            continue
        if frozenset((int(brancas), int(pretas))) in played_pairs:
            problemas.append(
                f"{nome(int(brancas)) or f'Equipe {brancas}'} × "
                f"{nome(int(pretas)) or f'Equipe {pretas}'} já se enfrentaram"
            )
    return problemas


TEAM_SCORE_KEYS = ("match_points", "game_points")


def team_score_keys(settings: dict[str, Any]) -> tuple[str, str]:
    """(principal, secundário) do pareamento por equipes, pelo critério configurado.

    O pareamento agrupava sempre por match points, enquanto a classificação e
    o TRF25 respeitam ``team_standing_primary`` (RG2-23). Valor desconhecido
    fica no padrão: match points.
    """
    primary = str(settings.get("team_standing_primary") or "match_points")
    if primary not in TEAM_SCORE_KEYS:
        primary = "match_points"
    secondary = next(key for key in TEAM_SCORE_KEYS if key != primary)
    return primary, secondary


def swiss_team_matches(
    teams: list[dict[str, Any]],
    rosters: dict[int, dict[int, int]],
    seed_ratings: dict[int, int],
    boards_count: int,
    settings: dict[str, Any],
    standings: dict[int, dict[str, Any]],
    histories: dict[int, list[str]],
    played_pairs: set[frozenset[int]],
    bye_team_ids: set[int],
    *,
    max_exhaustive_pairing_teams: int,
    repeat_pairing_penalty: int,
    score_group_float_penalty: int,
    score_diff_penalty: int,
    float_histories: dict[int, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Suíço por equipes pelo motor único de busca (RG2-07b).

    A cópia holandesa de equipes (`dutch_team_bracket_pairing`) saiu: grupos,
    flutuantes e busca são os de `round_search`, com o que é de equipe — a
    pontuação, a ordem, a cor e o custo do confronto.
    """
    rank_by_team_id = {
        int(team_id): int(item.get("position", 0) or 0)
        for team_id, item in standings.items()
    }

    primary, secondary = team_score_keys(settings)

    def order_key(team: dict[str, Any]) -> Any:
        return team_pairing_order_key(team, standings, seed_ratings, primary=primary, secondary=secondary)

    pending = sorted(teams, key=order_key)

    bye_team = None
    if len(pending) % 2 == 1:
        bye_team = choose_team_bye(
            pending, standings, bye_team_ids, seed_ratings, primary=primary, secondary=secondary
        )
        pending.remove(bye_team)

    def cost(team: dict[str, Any], opponent: dict[str, Any]) -> float:
        return team_pair_penalty(
            team,
            opponent,
            standings,
            played_pairs,
            rank_by_team_id,
            repeat_pairing_penalty=repeat_pairing_penalty,
            score_group_float_penalty=score_group_float_penalty,
            score_diff_penalty=score_diff_penalty,
            float_histories=float_histories,
            score_key=primary,
        )

    def solve(group: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        return (optimal_pairs if len(group) <= max_exhaustive_pairing_teams else greedy_pairs)(group, cost)

    def colors(team: dict[str, Any], opponent: dict[str, Any]) -> tuple[int, int]:
        return choose_team_colors(team, opponent, histories, seed_ratings)

    admissible = colors_admissible(histories, colors)
    def score_of(team: dict[str, Any]) -> float:
        return float(standings.get(int(team["id"]), {}).get(primary, 0.0) or 0.0)

    team_pairs = score_group_pairs(
        pending,
        score_of=score_of,
        order_key=order_key,
        bracket=lambda group: bracket_pairing(group, played_pairs, admissible=admissible, solve=solve),
        leftover=solve,
    )

    # RG2-07b: confronto repetido, 2º PAB ou três cores iguais seguidas que a
    # heurística deixou passar vão à busca exata, com o bye como nó.
    def hard_colors(team: dict[str, Any], opponent: dict[str, Any]) -> int:
        white_id, black_id = colors(team, opponent)
        return color_hard_violation(white_id, "W", histories) + color_hard_violation(black_id, "B", histories)

    bye_order = {
        int(team["id"]): index
        for index, team in enumerate(
            sorted(
                teams,
                key=lambda team: (
                    score_of(team),
                    float(standings.get(int(team["id"]), {}).get(secondary, 0.0) or 0.0),
                    seed_ratings.get(int(team["id"]), 0),
                    str(team["name"]).casefold(),
                ),
            )
        )
    }
    team_pairs, bye_team = enforce_absolute(
        team_pairs,
        bye_team,
        sorted(teams, key=order_key),
        played_pairs,
        bye_team_ids,
        pair_cost=lambda team, opponent: cost(team, opponent)
        + COLOR_HARD_VIOLATION_PENALTY * hard_colors(team, opponent),
        bye_cost=lambda team: score_of(team) * score_diff_penalty + bye_order[int(team["id"])],
        competitor_label="as equipes",
        hard_count=hard_colors,
    )

    team_pairs = sorted(
        team_pairs,
        key=lambda pair: min(
            rank_by_team_id.get(int(pair[0]["id"]), 0),
            rank_by_team_id.get(int(pair[1]["id"]), 0),
        ),
    )

    matches = []
    for match_number, (team, opponent) in enumerate(team_pairs, start=1):
        white_team_id, black_team_id = colors(team, opponent)
        matches.append(
            team_match_payload(
                match_number,
                white_team_id,
                black_team_id,
                rosters,
                boards_count,
            )
        )
    if bye_team:
        matches.append(team_bye_payload(len(matches) + 1, int(bye_team["id"]), settings, boards_count))
    return matches
