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
    "baku"                              **guardado** — a fórmula exata da FIDE não
                                        está documentada na nossa especificação;
                                        não aplica bônus e não emite registro 250
                                        nem sufixo `_BAKU`, para nunca enganar o
                                        árbitro. Ver `BAKU_NOT_IMPLEMENTED`.

Para ativar Baku de verdade: implementar a fórmula em `_baku_bonus` e remover a
guarda em `acceleration_spec`/`scheme_emits_250`.
"""

from __future__ import annotations

from typing import Any

# Esquema clássico: rodadas com bônus e valor do bônus por jogador.
CLASSIC_ACCELERATION_ROUNDS = (1, 2)
CLASSIC_ACCELERATION_BONUS = 1.0
CLASSIC_UPPER_FRACTION = 0.5

BAKU_NOT_IMPLEMENTED = (
    "Aceleração de Baku selecionada, mas a fórmula exata da FIDE não está "
    "implementada nesta versão. Nenhum bônus foi aplicado e o registro 250 não "
    "foi emitido (para não enganar o árbitro). Use aceleração clássica/custom ou "
    "o formato TRF16 para envio oficial."
)


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
        # Guardado: sem fórmula oficial, não aplicamos bônus nem emitimos 250.
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
    """True se o esquema deve emitir o registro 250 no TRF25.

    Baku fica de fora enquanto a fórmula não estiver implementada.
    """
    return scheme_applies_bonus(method)


def scheme_is_baku(method: str) -> bool:
    return acceleration_spec(method)["scheme"] == "baku"


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
    upper = upper_share_size(total_players, spec.get("upper_fraction", CLASSIC_UPPER_FRACTION))
    if upper <= 0:
        return 0.0
    return float(spec.get("bonus", 0.0) or 0.0) if start_rank <= upper else 0.0


def classic_acceleration_bonus(start_rank: int, total_players: int, round_number: int) -> float:
    """Bônus fictício na aceleração clássica (compat). Ver `acceleration_bonus`."""
    return acceleration_bonus(
        start_rank,
        total_players,
        round_number,
        acceleration_spec("classic"),
    )


def accelerated_standings(
    standings: dict[int, dict[str, Any]],
    seeding: list[int],
    round_number: int,
    method: str,
) -> dict[int, dict[str, Any]]:
    """Standings efetivo de pareamento com o bônus de aceleração somado.

    `seeding` é a lista de `player_id` na ordem de ranking inicial (1 = cabeça
    de chave); seu comprimento define o total para o corte da metade. Quando o
    esquema não soma bônus (none/baku), devolve o standings original sem cópia.
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
