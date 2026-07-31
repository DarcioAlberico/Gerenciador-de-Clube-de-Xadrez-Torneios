"""Registro DECLARATIVO dos códigos de resultado de uma partida (ARB-02).

O que um resultado É — quantos pontos vale, se a partida foi disputada, se entra
no rating e como sai no TRF — estava espalhado por seis lugares: `RESULT_POINTS`,
`WALKOVER_RESULTS`, `FINAL_RESULTS`, o `_trf_player_result` do exportador, o
`_count_result` dos resumos e os filtros de `fide_rating`. Enquanto os códigos se
dividiam em "jogada" e "W.O.", conjuntos soltos davam conta.

A ARB-02 trouxe os códigos `W`/`D`/`L` do TRF — **partida disputada que não entra
no rating** (resultado por decisão do árbitro) —, e eles se distinguem por uma
propriedade que nenhum daqueles conjuntos expressa. Daí o registro: uma definição
por código, e quem precisa de um recorte o deriva.

Este módulo não importa nada do projeto de propósito: `constants.py` o importa
para manter os nomes públicos de sempre, e `constants` é importado por quase tudo.

Referência das letras: `gacrux/trf2json.py`, tabela `self.results` — é o parser
FIDE que o Albericus usa como motor, então é ele quem define o dialeto.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResultCode:
    """Um código de resultado de mesa, com tudo o que se pergunta sobre ele.

    ``played`` distingue partida disputada de W.O.; ``rated`` distingue o que
    entra no cálculo de rating. Os dois juntos dão as três famílias do TRF:

    | família              | played | rated | letras TRF |
    |----------------------|--------|-------|------------|
    | normal               | sim    | sim   | `1` `=` `0` |
    | decisão do árbitro   | sim    | não   | `W` `D` `L` |
    | W.O./forfait         | não    | não   | `+` `-`     |
    """

    code: str
    label: str
    white_points: float
    black_points: float
    played: bool
    rated: bool
    trf_white: str
    trf_black: str

    @property
    def is_walkover(self) -> bool:
        return not self.played


# Ordem = ordem de oferta na tela: primeiro os três de sempre, depois os
# arbitrais. O código vazio (sem resultado) não mora aqui — ele é a ausência de
# um, e quem pergunta usa `RESULT_CODES.get(code)`.
_CODES: tuple[ResultCode, ...] = (
    ResultCode("1-0", "Brancas vencem", 1.0, 0.0, True, True, "1", "0"),
    ResultCode("0-1", "Pretas vencem", 0.0, 1.0, True, True, "0", "1"),
    ResultCode("1/2-1/2", "Empate", 0.5, 0.5, True, True, "=", "="),
    # Decisão do árbitro (TRF `W`/`D`/`L`): a partida ACONTECEU — conta para
    # Buchholz, Sonneborn-Berger e vitórias como qualquer outra — mas não é
    # ratável, porque o resultado não saiu dos lances. É o caso do jogo decidido
    # por reclamação, por posição ilegal irrecuperável ou por decisão de
    # apelação. Sem estes códigos, o árbitro era obrigado a escolher entre
    # mentir no rating (lançando 1-0) ou mentir no pareamento e no Buchholz
    # (lançando W.O., que a FIDE trata como partida não disputada).
    ResultCode("1U-0U", "Brancas vencem (decisão do árbitro)", 1.0, 0.0, True, False, "W", "L"),
    ResultCode("0U-1U", "Pretas vencem (decisão do árbitro)", 0.0, 1.0, True, False, "L", "W"),
    ResultCode("1/2U-1/2U", "Empate (decisão do árbitro)", 0.5, 0.5, True, False, "D", "D"),
    # W.O./forfait: a dupla foi PAREADA mas NAO jogou. Pela FIDE C.04.2 (regra
    # 3.5, efetiva 01/02/2026) "two paired participants, who did not play their
    # game or match, may be paired together in a future round" — logo um W.O.
    # não conta como "já se enfrentaram" para a regra de não-repetição (e o
    # motor Gacrux, rules 2026-02-01, já os repareia). Ver played_pairs().
    ResultCode("1F-0F", "Brancas vencem por W.O.", 1.0, 0.0, False, False, "+", "-"),
    ResultCode("0F-1F", "Pretas vencem por W.O.", 0.0, 1.0, False, False, "-", "+"),
    ResultCode("0F-0F", "Dupla ausência", 0.0, 0.0, False, False, "-", "-"),
)

RESULT_CODES: dict[str, ResultCode] = {item.code: item for item in _CODES}

# --------------------------------------------------------------------------- #
# Recortes derivados. Os nomes são os de sempre — `constants.py` os reexporta —,
# mas agora ninguém precisa lembrar de acrescentar um código novo em cada um.
# --------------------------------------------------------------------------- #

# Inclui o "" (sem resultado) na frente: é o que a tela oferece para limpar.
RESULT_VALUES: list[str] = [""] + [item.code for item in _CODES]

RESULT_POINTS: dict[str, tuple[float, float]] = {
    item.code: (item.white_points, item.black_points) for item in _CODES
}

WALKOVER_RESULTS: set[str] = {item.code for item in _CODES if item.is_walkover}

UNRATED_RESULTS: set[str] = {item.code for item in _CODES if item.played and not item.rated}

RATED_RESULTS: set[str] = {item.code for item in _CODES if item.rated}

PLAYED_RESULTS: set[str] = {item.code for item in _CODES if item.played}

RESULT_LABELS: dict[str, str] = {item.code: item.label for item in _CODES}


def result_points(code: str) -> tuple[float, float] | None:
    item = RESULT_CODES.get(code)
    return (item.white_points, item.black_points) if item else None


def is_rated_result(code: str) -> bool:
    """A partida entra no cálculo de rating (FIDE/CBX)?

    Só as três normais. W.O. não foi jogada; decisão do árbitro foi jogada mas
    não é ratável.
    """
    item = RESULT_CODES.get(code)
    return bool(item and item.rated)


def is_played_result(code: str) -> bool:
    """Houve partida no tabuleiro? (`W`/`D`/`L` contam; W.O. não.)"""
    item = RESULT_CODES.get(code)
    return bool(item and item.played)


def trf_letters(code: str) -> tuple[str, str] | None:
    """Letras TRF ``(brancas, pretas)`` do código, ou ``None`` se desconhecido."""
    item = RESULT_CODES.get(code)
    return (item.trf_white, item.trf_black) if item else None


def code_from_trf_letter(letter: str, *, is_white: bool) -> str:
    """Letra TRF de UM lado → código de mesa. ``""`` quando não se reconhece.

    A letra descreve um jogador; o código descreve a mesa. Ler a linha das
    brancas ou a das pretas tem de dar o mesmo código, e é por isso que o
    inverso não é uma tabela só.
    """
    alvo = str(letter or "").strip()
    if not alvo:
        return ""
    for item in _CODES:
        if (item.trf_white if is_white else item.trf_black) == alvo:
            return item.code
    return ""
