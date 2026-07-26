"""Dobra para ASCII — a fronteira entre o que o usuário lê e o que a máquina lê.

Existe por causa da B-7. Os cabeçalhos das exportações passaram a ser acentuados
("Classificação", "Premiação"), mas **os mesmos construtores de seção** alimentam
o pacote Access, onde o texto vira nome de coluna de CSV lido por um driver ODBC
com `schema.ini` — ali acento é risco de importação, não é polimento.

Em vez de manter duas listas de cabeçalhos (que divergem no primeiro descuido),
há **uma lista acentuada** e esta dobra aplicada no ponto de entrega que precisa
de ASCII. A regra fica visível no código: quem exporta para máquina chama
``to_ascii``; quem exporta para gente, não.
"""
from __future__ import annotations

import unicodedata
from typing import Iterable


def to_ascii(text: str) -> str:
    """Remove acentos preservando a letra base ("Classificação" → "Classificacao").

    Decomposição NFKD separa a letra do acento; descartar os combinantes deixa a
    letra. Caractere sem equivalente ASCII (um emoji, por exemplo) some — o que
    é o comportamento desejado num arquivo que precisa ser ASCII.
    """
    decomposto = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch)).encode(
        "ascii", "ignore"
    ).decode("ascii")


def headers_to_ascii(headers: Iterable[str]) -> list[str]:
    """Cabeçalhos de uma tabela, prontos para um consumidor que exige ASCII."""
    return [to_ascii(header) for header in headers]
