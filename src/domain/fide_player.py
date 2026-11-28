"""O que a FIDE lê de um jogador — um leitor só para cada campo.

Cada exportação tinha a sua cópia, e as cópias divergiram:

- **rating FIDE** (RG2-11): o TRF, o 072, as normas e o IT3 liam
  ``international_rating or rating or national_rating``. O atalho é legítimo na
  ordem inicial (quem não tem FIDE entra pelo rating do clube), mas no campo FIDE
  ele punha o rating do clube onde a FIDE lê o dela.
- **federação efetiva** (RG2-12): o TRF punha a federação do torneio em quem
  não tinha ``federation_id``; as normas descartavam a vazia — e o candidato com
  7 adversários "sem federação" (brasileiros de fato) passava no limite da
  própria federação com 0.
- **sexo** (RG2-29): o TRF saía ``f`` (``sex[:1].lower()``) onde a FIDE pede
  ``w``; a leitura é a das categorias (``normalized_sex``: ``F``/``W``/
  "Feminino" → ``F``), e a escrita para a FIDE é ``trf_sex``.
- **texto ASCII** (RG2-29): o TRF só tirava as marcas combinantes; ``Ø``, ``Ł``,
  ``ß`` e ``æ`` não se decompõem e passavam inteiros num arquivo UTF-8 — quem lê
  contando bytes via rating, federação e FIDE ID fora do lugar.

| Leitor | Usado em | Não usar em |
|---|---|---|
| ``fide_rating`` | TRF 001/072, aviso "sem rating FIDE", normas, IT3 | ordem inicial |
| ``seed_rating`` | ordem inicial, listas e atas do clube | qualquer campo FIDE |
| ``effective_federation`` | TRF 001 e avisos, normas, IT3 | — |
| ``trf_sex`` | coluna 10 da linha 001 | o cadastro (que guarda ``F``/``M``) |
| ``fide_ascii`` | todo texto do TRF16 e do TRF25 | PDF e tela (lá o nome vai como é) |
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import Any

from src.services.categories.matching import normalized_sex

_TRF_SEX = {"F": "w", "M": "m"}

# Letras que o NFKD não decompõe em base + marca. A grafia segue o costume das
# listas da FIDE ("Oster", "Lukasz", "Strasse").
_TRANSLITERATION = str.maketrans(
    {
        "Ø": "O", "ø": "o", "Ł": "L", "ł": "l", "ß": "ss", "Æ": "Ae", "æ": "ae",
        "Œ": "Oe", "œ": "oe", "Þ": "Th", "þ": "th", "Đ": "D", "đ": "d", "Ð": "D",
        "ð": "d", "ı": "i", "Ħ": "H", "ħ": "h", "Ŀ": "L", "ŀ": "l", "ĸ": "k",
        "Ŋ": "N", "ŋ": "n", "ſ": "s",
    }
)


def _int(value: Any) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def fide_rating(player: Mapping[str, Any]) -> int:
    """Rating FIDE do jogador: só ``international_rating``; 0 quando não tem."""
    return _int(player.get("international_rating"))


def effective_federation(player: Mapping[str, Any], settings: Mapping[str, Any] | None) -> str:
    """Federação do jogador para a FIDE: a dele, senão a do torneio; maiúscula."""
    own = str(player.get("federation_id") or "").strip()
    fallback = str((settings or {}).get("federation") or "").strip()
    return (own or fallback).upper()


def trf_sex(value: Any) -> str:
    """Sexo na coluna 10 do TRF: ``w`` ou ``m``; vazio quando o cadastro não diz."""
    return _TRF_SEX.get(normalized_sex(value), "")


def fide_ascii(value: Any) -> str:
    """Texto para o TRF: transliterado, sem acento, espaços colapsados e só ASCII.

    O que não tem tradução (um ideograma) vira ``?``: a linha nunca tem mais
    bytes que caracteres, e as colunas contadas em bytes ficam no lugar.
    """
    text = str(value if value is not None else "").translate(_TRANSLITERATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text.encode("ascii", "replace").decode("ascii")


def seed_rating(player: Mapping[str, Any]) -> int:
    """Rating para ordenar e mostrar no clube: FIDE, senão o do clube, senão o nacional."""
    return (
        _int(player.get("international_rating"))
        or _int(player.get("rating"))
        or _int(player.get("national_rating"))
    )
