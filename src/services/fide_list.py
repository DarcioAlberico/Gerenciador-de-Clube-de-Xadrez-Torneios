"""Leitor da lista de rating da FIDE (texto de largura fixa) — puro (FED-05).

A lista oficial (`standard_rating_list.txt`, dentro do ZIP) é um arquivo de
COLUNAS FIXAS. O leitor vivia dentro do método que baixa o ZIP, e por isso três
defeitos passavam sem teste possível:

- a linha só era aceita com 120 caracteres, mas o ano de nascimento mora nas
  colunas 127-131: as linhas entre 120 e 131 entravam **sem nascimento**;
- linha malformada era descartada em silêncio (a lista de erros existia e nunca
  recebia nada), então "importados: 8.000" podia ser "lidos: 12.000";
- o ano de nascimento — o único dado de data que a FIDE publica — era gravado
  como está, e o exportador TRF o considerava data inválida, o que fazia TODO
  jogador importado disparar aviso de nascimento no arquivo da federação.

O ano continua sendo gravado como ANO (`"1985"`): é o que a FIDE tem, é o que o
TRF aceita no campo 70-79 (a spec permite `YYYY`) e é a forma que
`categories.birth_year_from_date` já lê. Quem passou a ceder foi a validação do
TRF, que tratava ano-só como data quebrada.
"""

from __future__ import annotations

from typing import Any, Iterable

# Colunas (fatias 0-based) do arquivo da FIDE. Conferidas contra o leitor
# anterior, que rodava em produção; o cabeçalho da lista traz os mesmos campos
# nesta ordem: ID, Name, Fed, Sex, Tit, WTit, OTit, FOA, SRtng, SGm, SK, B-day.
ID_NUMBER = (0, 15)
NAME = (15, 76)
FEDERATION = (76, 80)
SEX = (80, 84)
TITLE = (84, 89)
RATING = (113, 119)
BIRTH_YEAR = (126, 131)

# A linha precisa alcançar o ano de nascimento para ser lida por inteiro. O
# corte antigo (120) ficava ANTES desse campo.
MIN_LINE_LENGTH = BIRTH_YEAR[1]

# Teto de erros relatados: a lista tem centenas de milhares de linhas e um
# arquivo truncado geraria um relatório impossível de ler.
MAX_REPORTED_ERRORS = 20


def _field(line: str, bounds: tuple[int, int]) -> str:
    return line[bounds[0]:bounds[1]].strip()


def is_header(line: str) -> bool:
    """A primeira linha do arquivo é o cabeçalho de colunas."""
    return _field(line, ID_NUMBER).upper().startswith("ID")


def birth_year(line: str) -> str:
    """Ano de nascimento como ANO (`"1985"`), ou `""` quando não há.

    A FIDE publica só o ano. Guardar `1985-01-01` inventaria um dia e um mês que
    ninguém informou — e é exatamente o tipo de dado que depois vira aniversário
    errado num certificado.
    """
    valor = _field(line, BIRTH_YEAR)
    return valor if valor.isdigit() and len(valor) == 4 else ""


def parse_line(line: str) -> dict[str, Any] | None:
    """Um jogador da lista, ou `None` quando a linha não descreve um."""
    if len(line.rstrip("\r\n")) < MIN_LINE_LENGTH or is_header(line):
        return None
    fide_id = _field(line, ID_NUMBER)
    name = _field(line, NAME)
    if not fide_id or not name:
        return None
    rating_bruto = _field(line, RATING)
    rating = int(rating_bruto) if rating_bruto.isdigit() else 0
    return {
        "external_id": fide_id,
        "fide_id": fide_id,
        "cbx_id": "",
        "name": name,
        "surname": "",
        "given_name": "",
        "title": _field(line, TITLE),
        "sex": _field(line, SEX),
        "federation": _field(line, FEDERATION),
        "club": "",
        "birth_date": birth_year(line),
        "national_rating": 0,
        "international_rating": rating,
        "standard_rating": rating,
        "rapid_rating": 0,
        "blitz_rating": 0,
    }


def parse_rating_list(lines: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Lê a lista inteira: `(jogadores, erros)`.

    Toda linha recusada vira erro — curta demais, sem ID ou sem nome. O silêncio
    de antes fazia um arquivo truncado parecer uma importação bem-sucedida.
    """
    jogadores: list[dict[str, Any]] = []
    erros: list[str] = []
    ignoradas = 0
    for numero, linha in enumerate(lines, start=1):
        limpa = linha.rstrip("\r\n")
        if not limpa.strip() or is_header(limpa):
            continue
        jogador = parse_line(limpa)
        if jogador is None:
            ignoradas += 1
            if len(erros) < MAX_REPORTED_ERRORS:
                erros.append(f"Linha {numero}: fora do layout da lista FIDE; ignorada.")
            continue
        jogadores.append(jogador)
    if ignoradas > MAX_REPORTED_ERRORS:
        erros.append(f"... e mais {ignoradas - MAX_REPORTED_ERRORS} linha(s) ignorada(s).")
    return jogadores, erros
