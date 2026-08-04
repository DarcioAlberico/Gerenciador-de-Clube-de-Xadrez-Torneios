"""Campos de adversários para os testes de norma (FED-06).

São campos SINTÉTICOS, montados em cima dos limiares do Handbook B.01 — e não
cópia de um torneio real. A escolha é deliberada: o que precisa ser testado é a
fronteira de cada regra (o terceiro GM, o quinto titulado, a segunda federação),
e num torneio real esses números caem onde caem. Cada função abaixo diz que
regra ela empurra até a borda.
"""

from __future__ import annotations

from typing import Sequence

from src.services.norms import NormOpponent


def opponent(
    index: int,
    *,
    title: str = "",
    rating: int = 2400,
    federation: str = "ARG",
    points: float = 0.0,
    name: str = "",
) -> NormOpponent:
    return NormOpponent(
        player_id=100 + index,
        name=name or f"Adversario {index:02d}",
        federation=federation,
        title=title,
        rating=rating,
        round_number=index,
        color="w" if index % 2 else "b",
        points=points,
    )


def gm_norm_opponents() -> list[NormOpponent]:
    """Nove partidas que fecham uma norma de GM, com folga mínima.

    3 GMs (mínimo exato de 1.4.5), 9 titulados, 3 federações — BRA, ARG e URU —
    com a do candidato (BRA) valendo 3 adversários, abaixo do teto de 5.
    Ra = 2400 e 7 pontos em 9 dão Rp = 2616.
    """
    titles = ["GM", "GM", "GM", "IM", "IM", "IM", "FM", "FM", "FM"]
    federations = ["BRA", "ARG", "URU"] * 3
    scores = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
    return [
        opponent(
            index + 1,
            title=title,
            rating=2400,
            federation=federation,
            points=points,
        )
        for index, (title, federation, points) in enumerate(zip(titles, federations, scores))
    ]


def weak_field_opponents() -> list[NormOpponent]:
    """Open doméstico: só CMs da mesma federação do candidato.

    É o caso que o motor antigo dava como norma — CM contava como titulado e a
    federação do próprio candidato entrava na conta de federações.
    """
    return [
        opponent(index + 1, title="CM", rating=2200, federation="BRA", points=points)
        for index, points in enumerate([1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    ]


def replace_opponent(
    opponents: Sequence[NormOpponent], position: int, **changes: object
) -> list[NormOpponent]:
    """Copia o campo trocando um adversário — para empurrar UMA regra por vez."""
    from dataclasses import replace

    updated = list(opponents)
    updated[position] = replace(updated[position], **changes)  # type: ignore[arg-type]
    return updated
