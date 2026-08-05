"""Ordem do ranking inicial (starting rank) — fonte única.

Três lugares montavam essa ordem por conta própria, todos pela mesma chave
(`-_trf_rating`, que é o rating FIDE na frente) e todos **ignorando o
`initial_order` do torneio**: o exportador TRF16, o exportador TRF25 e o
`GacruxEngine`, que é o motor de pareamento PADRÃO.

O efeito não era cosmético. Como o Gacrux recebe o TRF e devolve pares por
NÚMERO DE ORDEM, um torneio declarado "ordem pelo rating nacional" era pareado
pela ordem do rating FIDE — adversário e cor diferentes na mesa 1, em silêncio,
enquanto o motor próprio (`_seeding`) fazia o certo. O mesmo torneio dava dois
pareamentos conforme o motor.

Aqui a ordem é uma só. Duas decisões conservadoras, ambas deliberadas:

- **a ordem padrão não muda de comportamento.** `rating` é o valor DEFAULT da
  coluna, e não uma escolha do árbitro: quem nunca abriu a configuração não
  declarou nada. Nesses casos continua valendo a convenção do arquivo FIDE
  (internacional na frente), e o TRF de todo torneio existente sai idêntico ao
  de antes. Ordem escolhida de propósito passa a ser obedecida;
- **o registro 172 só afirma o que dá para justificar.** A spec do TRF25 lista
  os códigos (`FIDE`, `NRO`, `FIDON`, `NIDOF`, `HBFN`, `LBFN`, `OTHER`) mas não
  define o significado de todos. Os que não se sabe viram `OTHER`, que é o
  código que a própria spec oferece para isso.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from src.services.constants import player_pairing_name
from src.services.pairing.constraints import select_rating_for_order

# Ordens em que o arquivo segue a convenção FIDE (internacional na frente).
# `""` e `rating` entram aqui porque `rating` é o DEFAULT da coluna: quem não
# escolheu nada não declarou nada.
FIDE_RATING_ORDERS = frozenset({"", "rating", "international_rating"})

# `initial_order` -> método do registro 172 do TRF25. Só o que se pode
# justificar; o resto é `OTHER` de propósito (ver o docstring do módulo).
TRF_METHOD_BY_ORDER: dict[str, str] = {
    "": "FIDE",
    "rating": "FIDE",
    "international_rating": "FIDE",
    "national_rating": "NRO",
}
DEFAULT_TRF_METHOD = "OTHER"

# Ordens que o programa aceita mas não sabe montar sozinho.
UNSUPPORTED_ORDERS = frozenset({"manual"})


def normalized_order(initial_order: object) -> str:
    return str(initial_order or "").strip().lower()


def uses_fide_rating(initial_order: object) -> bool:
    """A ordem é a convenção do arquivo FIDE (internacional na frente)?"""
    return normalized_order(initial_order) in FIDE_RATING_ORDERS


def starting_rank_rating(
    player: Mapping[str, Any],
    initial_order: object,
    *,
    fide_rating: Callable[[Mapping[str, Any]], int],
) -> int:
    """Rating que decide a posição do jogador no ranking inicial.

    `fide_rating` é injetado porque a regra de fallback do arquivo (internacional
    ou principal ou nacional) mora no exportador — este módulo não conhece TRF.
    """
    order = normalized_order(initial_order)
    if uses_fide_rating(order) or order in UNSUPPORTED_ORDERS:
        return int(fide_rating(player) or 0)
    return int(
        select_rating_for_order(
            order,
            rating=int(player.get("rating") or 0),
            national=int(player.get("national_rating") or 0),
            international=int(player.get("international_rating") or 0),
        )
        or 0
    )


def order_players(
    players: Sequence[Mapping[str, Any]],
    initial_order: object,
    *,
    fide_rating: Callable[[Mapping[str, Any]], int],
) -> list[Mapping[str, Any]]:
    """Jogadores na ordem do ranking inicial — 1º elemento é o SNo 1.

    O desempate (nome e depois id) é o mesmo que os três lugares já usavam, para
    que a ordem continue estável entre execuções e entre arquivo e pareamento.
    """
    return sorted(
        players,
        key=lambda player: (
            -starting_rank_rating(player, initial_order, fide_rating=fide_rating),
            player_pairing_name(player).casefold(),
            int(player.get("id") or 0),
        ),
    )


def start_rank_by_player_id(
    players: Sequence[Mapping[str, Any]],
    initial_order: object,
    *,
    fide_rating: Callable[[Mapping[str, Any]], int],
) -> dict[int, int]:
    """`id do jogador -> número de ordem (1-based)`."""
    return {
        int(player["id"]): index
        for index, player in enumerate(
            order_players(players, initial_order, fide_rating=fide_rating), start=1
        )
    }


def trf_starting_rank_method(initial_order: object) -> str:
    """Código do registro 172 correspondente à ordem inicial do torneio."""
    return TRF_METHOD_BY_ORDER.get(normalized_order(initial_order), DEFAULT_TRF_METHOD)


def unsupported_order_warning(initial_order: object) -> str | None:
    """Aviso para a ordem que o programa aceita mas não sabe montar.

    `manual` é o caso: não existe lugar onde o árbitro grave a ordem manual do
    Suíço, então o ranking inicial cai no rating. Dizer isso é melhor do que
    deixar o árbitro achar que a ordem dele foi usada.
    """
    if normalized_order(initial_order) not in UNSUPPORTED_ORDERS:
        return None
    return (
        "Ordem inicial 'manual' nao tem onde ser gravada: o ranking inicial "
        "(SNo do TRF e seeding do pareamento) segue o rating. Use outra ordem "
        "ou ajuste os ratings para refletir a ordem desejada."
    )
