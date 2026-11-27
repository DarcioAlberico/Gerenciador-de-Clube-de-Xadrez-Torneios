"""A regra única de data do Albericus (RGS-06 / RGS-07).

Cada fronteira tinha a sua: o campo da tela aceitava uma coisa, o serviço outra,
a importação TRF uma terceira — e o que uma aceitava a outra apagava em
silêncio (`2010/05/12` virava `0512-10-20`; `1985` virava vazio). Aqui fica a
**única** leitura de data de usuário ou de arquivo. O teste-varredura
(`tests/test_rgs07_date_boundaries.py`) reprova `strptime`/`fromisoformat` fora
deste módulo.

`parse_date` devolve um de quatro resultados, e só eles:

- `DataVazia()` — nada informado;
- `Data(date)` — data completa é possível;
- `Ano(int)` — só o ano, e só quando o campo permite (`players.birth_date`: a
  lista da FIDE publica apenas o ano);
- `DataInvalida(texto, motivo)` — o resto, com o texto como veio e o porquê.

Os quatro são `dataclass(frozen=True)` que se validam ao nascer: não existe
`Ano(85)`, `Data("2026-11-13")` nem `DataInvalida` sem motivo.

Tabela (ver `tests/test_dates.py`):

| Entrada                          | Resultado                               |
|----------------------------------|-----------------------------------------|
| `""`                             | `DataVazia`                             |
| `aaaa-mm-dd`                     | `Data`                                  |
| `aaaa-mm-dd[ T]HH:MM[:SS]`       | `Data` (a hora é validada e descartada) |
| `dd/mm/aaaa`, `d/m/aaaa`, `dd-mm-aaaa` | `Data`                            |
| `aaaa/mm/dd`                     | `Data`                                  |
| `aaaa` (e `aaaa-00-00`)          | `Ano`, só com `permite_ano=True`        |
| ano com 2 dígitos, impossível, lixo | `DataInvalida` (não se adivinha século) |
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Union

__all__ = [
    "Ano",
    "Data",
    "DataInvalida",
    "DataVazia",
    "DateError",
    "ResultadoData",
    "is_iso_date",
    "normalize_date",
    "parse_date",
    "parse_trf_date",
    "parse_trf_round_date",
    "storage_text",
]

ANO_MINIMO = 1000
ANO_MAXIMO = 9999


@dataclass(frozen=True)
class DataVazia:
    """Nada informado. É um valor válido: campo de data opcional fica vazio."""


@dataclass(frozen=True)
class Data:
    valor: date

    def __post_init__(self) -> None:
        if not isinstance(self.valor, date):
            raise TypeError("Data exige um datetime.date.")

    @property
    def iso(self) -> str:
        return self.valor.isoformat()


@dataclass(frozen=True)
class Ano:
    valor: int

    def __post_init__(self) -> None:
        if isinstance(self.valor, bool) or not isinstance(self.valor, int):
            raise TypeError("Ano exige um inteiro.")
        if not ANO_MINIMO <= self.valor <= ANO_MAXIMO:
            raise ValueError(f"Ano fora da faixa {ANO_MINIMO}-{ANO_MAXIMO}: {self.valor}.")


@dataclass(frozen=True)
class DataInvalida:
    texto: str
    motivo: str

    def __post_init__(self) -> None:
        if not str(self.motivo or "").strip():
            raise ValueError("DataInvalida exige motivo.")


ResultadoData = Union[DataVazia, Data, Ano, DataInvalida]


class DateError(ValueError):
    """Data recusada numa fronteira. ``str()`` traz o texto e o motivo."""

    def __init__(self, invalida: DataInvalida) -> None:
        self.invalida = invalida
        super().__init__(f"Data inválida \"{invalida.texto}\": {invalida.motivo}")


# --- formas aceitas ----------------------------------------------------------
# Ano com 4 dígitos e sem zero à esquerda: `0512-10-20` é o que a máscara antiga
# produzia ao corromper `2010/05/12`, e não pode voltar a ser data válida.
_ANO = r"([1-9]\d{3})"
_MES_DIA = r"(\d{1,2})"
_HORA = r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?"

_ANO_PRIMEIRO = re.compile(rf"^{_ANO}([-/]){_MES_DIA}\2{_MES_DIA}{_HORA}$")
_DIA_PRIMEIRO = re.compile(rf"^{_MES_DIA}([-/]){_MES_DIA}\2{_ANO}$")
_SO_ANO = re.compile(rf"^{_ANO}$")
_ANO_ZERADO = re.compile(rf"^{_ANO}([-/.])0{{1,2}}(?:\2)0{{1,2}}$")
_ANO_CURTO = re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2}$|^\d{2}$")

_MOTIVO_IMPOSSIVEL = "esta data não existe no calendário."
_MOTIVO_HORA = "hora impossível."
_MOTIVO_ANO_CURTO = "ano com 2 dígitos; informe o ano completo (aaaa)."
_MOTIVO_SO_ANO = "informe dia, mês e ano (dd/mm/aaaa)."
_MOTIVO_FORMATO = "formato não reconhecido; use dd/mm/aaaa."


def _montar(texto: str, ano: str, mes: str, dia: str) -> ResultadoData:
    try:
        return Data(date(int(ano), int(mes), int(dia)))
    except ValueError:
        return DataInvalida(texto, _MOTIVO_IMPOSSIVEL)


def _hora_possivel(hora: str | None, minuto: str | None, segundo: str | None) -> bool:
    if hora is None:
        return True
    return int(hora) <= 23 and int(minuto or 0) <= 59 and int(segundo or 0) <= 59


def parse_date(texto: object, *, permite_ano: bool = False) -> ResultadoData:
    """Lê uma data de usuário ou de arquivo. Nunca levanta: o erro é um valor."""
    bruto = "" if texto is None else str(texto).strip()
    if not bruto:
        return DataVazia()

    # Antes da data completa: `1985-00-00` casaria como data impossível.
    casou = _SO_ANO.match(bruto) or _ANO_ZERADO.match(bruto)
    if casou:
        if permite_ano:
            return Ano(int(casou.group(1)))
        return DataInvalida(bruto, _MOTIVO_SO_ANO)

    casou = _ANO_PRIMEIRO.match(bruto)
    if casou:
        ano, _sep, mes, dia, hora, minuto, segundo = casou.groups()
        if not _hora_possivel(hora, minuto, segundo):
            return DataInvalida(bruto, _MOTIVO_HORA)
        return _montar(bruto, ano, mes, dia)

    casou = _DIA_PRIMEIRO.match(bruto)
    if casou:
        dia, _sep, mes, ano = casou.groups()
        return _montar(bruto, ano, mes, dia)

    if _ANO_CURTO.match(bruto):
        return DataInvalida(bruto, _MOTIVO_ANO_CURTO)
    return DataInvalida(bruto, _MOTIVO_FORMATO)


def storage_text(resultado: ResultadoData) -> str:
    """Texto gravado no banco: ISO, o ano (`"1985"`) ou vazio.

    `DataInvalida` não tem forma gravável: levanta `DateError`.
    """
    if isinstance(resultado, DataVazia):
        return ""
    if isinstance(resultado, Data):
        return resultado.iso
    if isinstance(resultado, Ano):
        return str(resultado.valor)
    raise DateError(resultado)


def normalize_date(texto: object, *, permite_ano: bool = False) -> str:
    """`parse_date` + `storage_text`: o atalho das fronteiras que gravam."""
    return storage_text(parse_date(texto, permite_ano=permite_ano))


def is_iso_date(texto: object) -> bool:
    """Data completa já na forma canônica `aaaa-mm-dd`.

    Para quem valida e grava o texto como veio: aceitar `13/11/2026` ali
    gravaria data fora do padrão.
    """
    bruto = "" if texto is None else str(texto).strip()
    resultado = parse_date(bruto)
    return isinstance(resultado, Data) and resultado.iso == bruto


# --- TRF16 ---------------------------------------------------------------------
_SEPARADORES_TRF = re.compile(r"[.\\]\s*")


def parse_trf_date(texto: object, *, permite_ano: bool = False) -> ResultadoData:
    """Data de campo TRF (042, 052, nascimento do 001): `YYYY/MM/DD`.

    Arquivos de outros programas trazem `.` ou `\\` como separador. Zeros
    (`0000/00/00`) são "não informado". Nascimento só com o ano é aceito com
    `permite_ano` (o TRF permite `YYYY` no campo).
    """
    bruto = "" if texto is None else str(texto).strip()
    if not bruto or set(bruto) <= set("0/.-\\ "):
        return DataVazia()
    normalizado = _SEPARADORES_TRF.sub("/", bruto)
    resultado = parse_date(normalizado, permite_ano=permite_ano)
    if isinstance(resultado, DataInvalida):
        return DataInvalida(bruto, resultado.motivo)
    return resultado


_DATA_132 = re.compile(r"^(\d{2})/(\d{1,2})/(\d{1,2})$")


def parse_trf_round_date(texto: object) -> ResultadoData:
    """Data de rodada do registro 132: `YY/MM/DD`, como manda o TRF16.

    O século aqui não é adivinhação: o formato define dois dígitos de ano, e o
    registro só existe para torneios deste século.
    """
    bruto = "" if texto is None else str(texto).strip()
    if not bruto:
        return DataVazia()
    casou = _DATA_132.match(bruto)
    if casou:
        ano, mes, dia = casou.groups()
        return _montar(bruto, f"20{ano}", mes, dia)
    return parse_trf_date(bruto)
