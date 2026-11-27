"""Aceleração de pareamento (pontos fictícios) — funções puras.

A aceleração só altera o *score de pareamento* (os grupos de pontuação que o
motor Suíço usa para emparelhar); jamais toca nos pontos reais, na classificação
ou nos desempates. Por isso o motor recebe um *standings efetivo* com o bônus
somado, enquanto o standings real fica intacto.

Esquemas selecionáveis (codificados na coluna `acceleration_method`):

    "none"                              sem aceleração
    "classic" / "accelerated"           clássico (Haley): metade superior ganha
                                        +1 ponto fictício nas rodadas 1-2
    "custom:rounds=N;bonus=B;upper=F"   parametrizável: primeiras N rodadas, bônus
                                        B por jogador, fração F do campo (0..1)
    "baku"                              FIDE C.04.7 (RGS-30): o bônus depende do
                                        campo inicial e do total de rodadas, então
                                        não passa por `acceleration_bonus` — ver
                                        `baku_virtual_points`.

Baku — redação conferida no FIDE Handbook em 2026-11-26:
https://handbook.fide.com/chapter/C0407202602 ("FIDE-approved Accelerated
Systems", C.04.7, aprovado pelo Conselho em 28/10/2025, aplicado desde
01/02/2026; até 31/01/2026 era C.04.5.1). Resumo dos artigos:

- 1.1: vale para pontuação em que a vitória vale dois empates e a derrota vale
  zero;
- 1.2: antes da R1 a lista ordenada se divide em GA, "the first half of the
  participants, rounded up to the nearest even number" (2 × ⌈N/4⌉, que é também
  o número de pareamento do último do GA), e GB, o resto;
- 1.3: com entrada tardia, o último participante do GA continua o mesmo da
  rodada anterior; o GA pode ficar ímpar e o número dele pode mudar;
- 1.4.1: "accelerated rounds" são as da primeira metade do torneio
  (arredondada para cima);
- 1.4.2–1.4.3: antes da primeira metade das aceleradas (arredondada para cima,
  como no exemplo) cada um do GA recebe VP igual aos pontos de uma vitória;
  nas aceleradas restantes, metade disso; GB nunca recebe; depois, zero;
- 1.4.4: exemplo, 9 rodadas → 5 aceleradas, VP 1 nas R1–R3 e 0,5 nas R4–R5;
- 1.5: score de pareamento = pontos da classificação + VP. O VP forma os grupos
  de pontuação e ordena as mesas; nunca entra na classificação.

Equipes (EQ-07): o C.04.7 fala de equipes. O prefácio trata o "jogo" como o
match numa competição por equipes, e o Exemplo 2 de 1.4.4 é uma competição de
11 rodadas por match points (2 MP a vitória, 1 o empate): GA recebe 2 MP
virtuais nas R1–R3 e 1 MP nas R4–R6. A nota do exemplo diz que, com game
points como score principal, Baku não pode ser usado. Ver
`baku_team_accelerated_ids`.
"""

from __future__ import annotations

import math
from typing import Any, Collection, Sequence

from src.services.constants import AppError

# Esquema clássico: rodadas com bônus e valor do bônus por jogador.
CLASSIC_ACCELERATION_ROUNDS = (1, 2)
CLASSIC_ACCELERATION_BONUS = 1.0
CLASSIC_UPPER_FRACTION = 0.5

BAKU_TEAM_GAME_POINTS_REFUSED = (
    "A aceleração de Baku (FIDE C.04.7) não vale quando os game points são o "
    "score principal (nota do Exemplo 2 de 1.4.4). Use match points como "
    "critério principal ou escolha outra aceleração."
)

BAKU_SCORING_REFUSED = (
    "A aceleração de Baku (FIDE C.04.7) só vale quando a vitória vale dois "
    "empates e a derrota vale zero. Este torneio pontua vitória {win:g}, empate "
    "{draw:g} e derrota {loss:g}; escolha outra aceleração ou ajuste a pontuação."
)


def baku_group_a_size(total_players: int) -> int:
    """Tamanho do GA antes da R1: 2 × ⌈N/4⌉ (C.04.7 1.2)."""
    return 2 * math.ceil(max(int(total_players), 0) / 4)


def baku_accelerated_rounds(total_rounds: int) -> int:
    """Rodadas aceleradas: a primeira metade, arredondada para cima (1.4.1)."""
    return math.ceil(max(int(total_rounds), 0) / 2)


def baku_full_point_rounds(total_rounds: int) -> int:
    """Rodadas com VP inteiro: a primeira metade das aceleradas, para cima (1.4.2)."""
    return math.ceil(baku_accelerated_rounds(total_rounds) / 2)


def baku_virtual_points(
    total_players: int,
    total_rounds: int,
    round_number: int,
    start_rank: int,
    late_entrants_above: int = 0,
    *,
    win_points: float = 1.0,
    draw_points: float = 0.5,
    loss_points: float = 0.0,
) -> float:
    """VP de Baku de um jogador numa rodada (FIDE C.04.7). Função pura.

    `total_players` é o N da lista antes da R1 (sem os entrantes tardios);
    `start_rank` é o número de pareamento ATUAL (1 = cabeça de chave);
    `late_entrants_above` conta os entrantes tardios que ficaram acima do último
    do GA. Ele continua o mesmo (1.3): o número dele passa a ser
    `2 × ⌈N/4⌉ + late_entrants_above`, e o GA pode ficar ímpar.

    Recusa (AppError) pontuação em que a vitória não vale dois empates ou a
    derrota não vale zero (1.1).
    """
    win, draw, loss = float(win_points), float(draw_points), float(loss_points)
    if abs(win - 2 * draw) > 1e-9 or abs(loss) > 1e-9 or win <= 0:
        raise AppError(BAKU_SCORING_REFUSED.format(win=win, draw=draw, loss=loss))
    rnd = int(round_number)
    if rnd < 1 or rnd > baku_accelerated_rounds(total_rounds):
        return 0.0
    last_of_ga = baku_group_a_size(total_players) + max(int(late_entrants_above), 0)
    if not 1 <= int(start_rank) <= last_of_ga:
        return 0.0
    return win if rnd <= baku_full_point_rounds(total_rounds) else win / 2


def baku_initial_field(
    seeding: Sequence[int],
    initial_ids: Collection[int],
) -> tuple[int, int]:
    """`(N, late_entrants_above)` de `baku_virtual_points` a partir das listas.

    `seeding` é a lista de `player_id` na ordem de pareamento atual, com os
    entrantes tardios; `initial_ids` são os que estavam na lista antes da R1.
    O último do GA é o `2 × ⌈N/4⌉`-ésimo dos iniciais; contam-se os tardios
    acima dele.
    """
    iniciais = {int(player_id) for player_id in initial_ids}
    ordem = [int(player_id) for player_id in seeding]
    na_lista = [player_id for player_id in ordem if player_id in iniciais]
    tamanho = min(baku_group_a_size(len(na_lista)), len(na_lista))
    if not tamanho:
        return len(na_lista), 0
    ultimo = ordem.index(na_lista[tamanho - 1])
    acima = sum(1 for player_id in ordem[:ultimo] if player_id not in iniciais)
    return len(na_lista), acima


def baku_accelerated_player_ids(
    seeding: Sequence[int],
    initial_ids: Collection[int],
    total_rounds: int,
    round_number: int,
    *,
    win_points: float = 1.0,
    draw_points: float = 0.5,
    loss_points: float = 0.0,
) -> tuple[list[int], float]:
    """Quem do `seeding` recebe VP nesta rodada, e quanto (todos o mesmo).

    Ver `baku_initial_field`; a decisão é `baku_virtual_points`. A pontuação
    padrão é a individual (1 / ½ / 0); equipes passam os match points.
    """
    total, acima = baku_initial_field(seeding, initial_ids)
    acelerados: list[int] = []
    bonus = 0.0
    for rank, player_id in enumerate(seeding, start=1):
        vp = baku_virtual_points(
            total, total_rounds, round_number, rank, acima,
            win_points=win_points, draw_points=draw_points, loss_points=loss_points,
        )
        if vp:
            acelerados.append(int(player_id))
            bonus = vp
    return acelerados, bonus


def baku_team_accelerated_ids(
    tpn_order: Sequence[int],
    initial_ids: Collection[int],
    total_rounds: int,
    round_number: int,
    *,
    primary_score: str,
    win_points: float,
    draw_points: float,
    loss_points: float,
) -> tuple[list[int], float]:
    """Baku no Suíço por equipes (EQ-07): quem recebe VP, e quanto.

    `tpn_order` são os `team_id` na ordem do TPN gravado (EQ-01), e
    `initial_ids` as equipes inscritas até a R1. O GA é `2 × ⌈N/4⌉` pelo TPN,
    e o VP é o valor de uma vitória de MATCH (metade disso na segunda parte
    das aceleradas) — o Exemplo 2 do C.04.7 1.4.4. Recusa (AppError) game
    points como score principal e pontuação de match em que a vitória não vale
    dois empates ou a derrota não vale zero (1.1).
    """
    if str(primary_score or "match_points") == "game_points":
        raise AppError(BAKU_TEAM_GAME_POINTS_REFUSED)
    return baku_accelerated_player_ids(
        tpn_order, initial_ids, total_rounds, round_number,
        win_points=win_points, draw_points=draw_points, loss_points=loss_points,
    )


def baku_acceleration_blocks(
    total_players: int,
    total_rounds: int,
    late_entrants_above: int = 0,
) -> list[tuple[float, int, int, int, int]]:
    """Os blocos do registro 250 do torneio: `(vp, 1ª rodada, última, 1º, último)`.

    Derivado de `baku_virtual_points` rodada a rodada — o arquivo declara
    exatamente o que o pareamento aplica.
    """
    last_of_ga = baku_group_a_size(total_players) + max(int(late_entrants_above), 0)
    blocks: list[tuple[float, int, int, int, int]] = []
    for rnd in range(1, max(int(total_rounds), 0) + 1):
        vp = baku_virtual_points(total_players, total_rounds, rnd, 1, late_entrants_above)
        if not vp or last_of_ga <= 0:
            continue
        if blocks and blocks[-1][0] == vp and blocks[-1][2] == rnd - 1:
            blocks[-1] = (vp, blocks[-1][1], rnd, 1, last_of_ga)
        else:
            blocks.append((vp, rnd, rnd, 1, last_of_ga))
    return blocks


def classic_upper_half_size(total_players: int) -> int:
    """Tamanho da metade superior que recebe o bônus (piso de N/2)."""
    return max(int(total_players), 0) // 2


def upper_share_size(total_players: int, fraction: float) -> int:
    """Quantos jogadores do topo recebem bônus dada uma fração (0..1)."""
    return int(max(int(total_players), 0) * float(fraction))


def acceleration_spec(method: str) -> dict[str, Any]:
    """Interpreta a coluna `acceleration_method` num spec de esquema.

    Devolve sempre um dict com `scheme` e, quando aplicável, `round_count`,
    `bonus` e `upper_fraction`. Entradas desconhecidas caem em `none`.
    """
    raw = str(method or "none").strip()
    if not raw or raw.lower() == "none":
        return {"scheme": "none"}

    head, _, rest = raw.partition(":")
    head = head.strip().lower()

    if head in ("accelerated", "classic"):
        return {
            "scheme": "classic",
            "round_count": max(CLASSIC_ACCELERATION_ROUNDS),
            "bonus": CLASSIC_ACCELERATION_BONUS,
            "upper_fraction": CLASSIC_UPPER_FRACTION,
        }

    if head == "baku":
        # FIDE C.04.7: o VP depende do campo e das rodadas — `baku_virtual_points`.
        return {"scheme": "baku"}

    if head == "custom":
        spec: dict[str, Any] = {
            "scheme": "custom",
            "round_count": max(CLASSIC_ACCELERATION_ROUNDS),
            "bonus": CLASSIC_ACCELERATION_BONUS,
            "upper_fraction": CLASSIC_UPPER_FRACTION,
        }
        for token in rest.split(";"):
            token = token.strip()
            if not token or "=" not in token:
                continue
            key, _, value = token.partition("=")
            key = key.strip().lower()
            value = value.strip()
            try:
                if key in ("rounds", "round_count"):
                    spec["round_count"] = max(int(float(value)), 0)
                elif key == "bonus":
                    spec["bonus"] = float(value)
                elif key in ("upper", "upper_fraction"):
                    spec["upper_fraction"] = max(0.0, min(1.0, float(value)))
            except (TypeError, ValueError):
                continue
        return spec

    return {"scheme": "none"}


def scheme_applies_bonus(method: str) -> bool:
    """True se o esquema realmente soma bônus ao standings de pareamento."""
    return acceleration_spec(method)["scheme"] in ("classic", "custom")


def scheme_emits_250(method: str) -> bool:
    """True se o esquema de bônus FIXO emite o registro 250 (clássico/custom).

    Baku emite o seu próprio 250, em blocos (`baku_acceleration_blocks`).
    """
    return scheme_applies_bonus(method)


def scheme_is_baku(method: str) -> bool:
    return acceleration_spec(method)["scheme"] == "baku"


def baku_applies_to_team_swiss(settings: dict[str, Any]) -> bool:
    """O Suíço por equipes pareia com Baku (EQ-07)? A regra do motor e do TRF25.

    Só no Suíço (o todos-contra-todos tem calendário fixo) e com match points
    como score principal: com game points o C.04.7 não permite Baku, e o motor
    recusa a rodada (`baku_team_accelerated_ids`).
    """
    return (
        scheme_is_baku(str(settings.get("acceleration_method") or "none"))
        and str(settings.get("team_pairing_method") or "swiss") != "round_robin"
        and str(settings.get("team_standing_primary") or "match_points") != "game_points"
    )


def acceleration_bonus(
    start_rank: int,
    total_players: int,
    round_number: int,
    spec: dict[str, Any],
) -> float:
    """Bônus fictício de um jogador dado um spec de esquema.

    `start_rank` é o ranking inicial 1-based (1 = cabeça de chave).
    """
    scheme = spec.get("scheme", "none")
    if scheme not in ("classic", "custom"):
        return 0.0
    round_count = int(spec.get("round_count", 0) or 0)
    if round_count <= 0:
        return 0.0
    rnd = int(round_number)
    if rnd < 1 or rnd > round_count:
        return 0.0
    if start_rank <= 0:
        return 0.0
    bonus = float(spec.get("bonus", 0.0) or 0.0)
    if bonus <= 0:
        return 0.0
    upper = upper_share_size(total_players, spec.get("upper_fraction", CLASSIC_UPPER_FRACTION))
    if upper <= 0:
        return 0.0
    return bonus if start_rank <= upper else 0.0


def classic_acceleration_bonus(start_rank: int, total_players: int, round_number: int) -> float:
    """Bônus fictício na aceleração clássica (compat). Ver `acceleration_bonus`."""
    return acceleration_bonus(
        start_rank,
        total_players,
        round_number,
        acceleration_spec("classic"),
    )


def accelerated_player_ids(
    seeding: list[int],
    round_number: int,
    method: str,
) -> list[int]:
    """Quem recebe bônus fictício nesta rodada, na ordem do `seeding`.

    Mesma conta de `accelerated_standings`, sem o standings: o caminho Gacrux
    precisa só de QUEM acelera, para traduzir em start-ranks do TRF.
    """
    spec = acceleration_spec(method)
    total = len(seeding)
    return [
        player_id
        for index, player_id in enumerate(seeding, start=1)
        if acceleration_bonus(index, total, round_number, spec)
    ]


def accelerated_standings(
    standings: dict[int, dict[str, Any]],
    seeding: list[int],
    round_number: int,
    method: str,
) -> dict[int, dict[str, Any]]:
    """Standings efetivo de pareamento com o bônus de aceleração somado.

    `seeding` é a lista de `player_id` na ordem de ranking inicial (1 = cabeça
    de chave); seu comprimento define o total para o corte da metade. Quando o
    esquema não soma bônus fixo (none/baku), devolve o standings original sem
    cópia. Baku chega ao motor próprio por `standings_with_virtual_points`.
    """
    spec = acceleration_spec(method)
    if spec["scheme"] not in ("classic", "custom") or not seeding:
        return standings

    total = len(seeding)
    effective: dict[int, dict[str, Any]] = {}
    for index, player_id in enumerate(seeding, start=1):
        item = dict(standings.get(player_id, {}))
        bonus = acceleration_bonus(index, total, round_number, spec)
        if bonus:
            item["points"] = float(item.get("points", 0.0) or 0.0) + bonus
        effective[player_id] = item
    for player_id, item in standings.items():
        effective.setdefault(player_id, item)
    return effective


def standings_with_virtual_points(
    standings: dict[int, dict[str, Any]],
    player_ids: Collection[int],
    bonus: float,
    *,
    score_key: str = "points",
) -> dict[int, dict[str, Any]]:
    """Standings de pareamento com `bonus` somado a `player_ids` (score de pareamento).

    É o plano de aceleração da rodada (quem e quanto) aplicado ao motor próprio;
    o standings real fica intacto. Sem acelerados ou sem bônus, devolve o
    original sem cópia. `score_key` é o score que o motor agrupa: `points` no
    individual, `match_points` no Suíço por equipes.
    """
    acelerados = {int(player_id) for player_id in player_ids}
    if not acelerados or not bonus:
        return standings
    effective: dict[int, dict[str, Any]] = {}
    for player_id, item in standings.items():
        if int(player_id) in acelerados:
            item = {**item, score_key: float(item.get(score_key, 0.0) or 0.0) + float(bonus)}
        effective[player_id] = item
    return effective


def team_acceleration_not_applied_warning(method: str, *, round_robin: bool = False) -> str:
    """Aviso de aceleração configurada que o pareamento por equipes não aplica.

    Nada some calado: o árbitro configurou é precisa saber que não veio. Por
    equipes só existe Baku (C.04.7, EQ-07), e no todos-contra-todos não há
    grupos de pontuação a acelerar.
    """
    if round_robin:
        return (
            "Aceleração configurada, mas o todos-contra-todos por equipes não usa "
            "grupos de pontuação: a rodada sai do calendário, sem pontos virtuais."
        )
    return (
        f"A aceleração \"{method}\" não se aplica ao Suíço por equipes; só a de "
        "Baku (FIDE C.04.7). Esta rodada foi pareada sem aceleração."
    )
