"""A leitura única de número digitado ou importado (RG2-46, RG2-14, RG2-27, RG2-10).

Cada fronteira tinha a sua, e todas erravam do mesmo jeito:

- ``float("1.500".replace(",", "."))`` lia o ponto de milhar brasileiro como
  decimal — mensalidade "1.500" virava R$ 1,50, prêmio "1.000" virava R$ 1,00,
  rating "1.850" virava 1;
- texto inválido virava 0 calado (o jogador entrava sem rating, sem erro);
- ``"nan"`` e ``"inf"`` passavam;
- ``valor or padrão`` transformava o 0 legítimo em 1 (bye valendo 0 →
  "Dividir em 2" → os grupos davam 1 ponto no PAB).

Aqui ficam as **únicas** leituras. O teste-varredura
(``tests/test_rg2_numeric_boundary.py``) reprova ``float(str(x).replace(",", "."))``
e ``.get("…points…") or <número ≠ 0>`` em ``src/services``.

| Leitor | Vazio | Aceita | Recusa (``NumberError``) |
|---|---|---|---|
| ``parse_decimal_br`` (dinheiro) | ``None`` | "1.500" → 1500; "1.500,50"; "1,5"; "1 500"; "1.5" e "1500.0" → decimal | "1.5000" (pede "1,5" ou "1.500"); "nan"; "inf"; lixo |
| ``parse_rating`` | ``None`` | "1.850", "1 850", "1850", 1850.0 da planilha | "1,850", "abc", negativo, quebrado |
| ``parse_decimal`` (nota, percentual, opacidade) | ``None`` | "8,5" e "8.5" (ponto **é** decimal: não há milhar) | não finito; lixo |
| ``parse_points`` | ``None`` | o que ``parse_decimal`` aceita | negativo, fora de múltiplo de 0,5, fora da faixa |
| ``setting_number`` | o padrão | o número gravado, inclusive 0 | valor gravado que não é número |
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection
from decimal import Decimal
from typing import Any

__all__ = [
    "BYE_POINTS",
    "NumberError",
    "parse_decimal",
    "parse_decimal_br",
    "parse_points",
    "parse_rating",
    "setting_number",
]

BYE_POINTS: tuple[float, ...] = (0.0, 0.5, 1.0)
"""Faixa do bye e dos pontos por rodada perdida na entrada tardia (RG2-27)."""

_MILHAR_PONTO = r"\d{1,3}(?:\.\d{3})+"
_MILHAR_ESPACO = r"\d{1,3}(?: \d{3})+"
_BR = re.compile(
    rf"(?P<sinal>[-+]?)(?P<inteiro>{_MILHAR_PONTO}|{_MILHAR_ESPACO}|\d+)(?:,(?P<frac>\d+))?",
    re.ASCII,
)
_PONTO_DECIMAL_CURTO = re.compile(r"(?P<sinal>[-+]?)(?P<inteiro>\d+)\.(?P<frac>\d{1,2})", re.ASCII)
_PONTO_DECIMAL = re.compile(r"[-+]?\d+\.\d+", re.ASCII)
_ZEROS_DE_PLANILHA = re.compile(r"(?P<inteiro>\d+)[.,]0+", re.ASCII)
_SIMPLES = re.compile(r"(?P<sinal>[-+]?)(?P<inteiro>\d+)(?:[.,](?P<frac>\d+))?", re.ASCII)


class NumberError(ValueError):
    """Número que não se lê. ``str(erro)`` é a frase para o usuário, com o texto como veio."""

    def __init__(self, texto: str, motivo: str) -> None:
        self.texto = texto
        self.motivo = motivo
        super().__init__(f'"{texto}": {motivo}')


def _texto(valor: object) -> str:
    return str(valor).replace(" ", " ").strip()


def _numero_pronto(valor: object) -> float | None:
    """Número que já chega numérico (planilha, payload interno); ``None`` se é texto."""
    if isinstance(valor, bool):
        raise NumberError(str(valor), "não é um número.")
    if isinstance(valor, (int, float, Decimal)):
        numero = float(valor)
        if not math.isfinite(numero):
            raise NumberError(str(valor), "não é um número finito.")
        return numero
    return None


def _decimal(sinal: str, inteiro: str, frac: str | None) -> float:
    digitos = re.sub(r"[ .]", "", inteiro)
    return float(Decimal(f"{sinal or ''}{digitos}.{frac or '0'}"))


def parse_decimal_br(valor: object) -> float | None:
    """Dinheiro e quantias: vírgula é decimal; ponto (ou espaço) seguido de 3 dígitos é milhar.

    Ponto seguido de 1 ou 2 dígitos ("1.5", "1500.0") é decimal: não pode ser
    milhar, e é como a tela mostra o valor gravado para editar — recusar
    impediria salvar de novo um campo que o usuário nem tocou.
    """
    if valor is None:
        return None
    pronto = _numero_pronto(valor)
    if pronto is not None:
        return pronto
    texto = _texto(valor)
    if not texto:
        return None
    achado = _BR.fullmatch(texto)
    if achado:
        return _decimal(achado["sinal"], achado["inteiro"], achado["frac"])
    if curto := _PONTO_DECIMAL_CURTO.fullmatch(texto):
        return _decimal(curto["sinal"], curto["inteiro"], curto["frac"])
    if _PONTO_DECIMAL.fullmatch(texto):
        raise NumberError(texto, 'use vírgula para decimal e ponto só para milhar — por exemplo "1,5" ou "1.500".')
    raise NumberError(texto, 'não é um número (exemplos: "1.500", "1.500,50", "1,5").')


def parse_rating(valor: object) -> int | None:
    """Rating: inteiro não negativo; ponto ou espaço de milhar aceitos ("1.850", "1 850")."""
    if valor is None:
        return None
    pronto = _numero_pronto(valor)
    if pronto is None:
        texto = _texto(valor)
        if not texto:
            return None
        achado = _BR.fullmatch(texto)
        if achado and not achado["sinal"] and not achado["frac"]:
            pronto = _decimal("", achado["inteiro"], None)
        elif zeros := _ZEROS_DE_PLANILHA.fullmatch(texto):
            pronto = float(zeros["inteiro"])
        else:
            raise NumberError(texto, 'rating inválido (exemplos: "1850", "1.850").')
    if pronto < 0 or not pronto.is_integer():
        raise NumberError(_texto(valor), "o rating é um inteiro não negativo.")
    return int(pronto)


def _br(numero: float) -> str:
    return str(int(numero)) if float(numero).is_integer() else f"{numero:g}".replace(".", ",")


def _faixa(permitidos: Collection[float] | None) -> str:
    if permitidos is None:
        return "um múltiplo de 0,5, maior ou igual a 0"
    return "; ".join(_br(valor) for valor in sorted(permitidos))


def parse_decimal(valor: object) -> float | None:
    """Decimal sem milhar (nota, percentual, opacidade, pontos): vírgula **ou** ponto decimal."""
    if valor is None:
        return None
    pronto = _numero_pronto(valor)
    if pronto is not None:
        return pronto
    texto = _texto(valor)
    if not texto:
        return None
    achado = _SIMPLES.fullmatch(texto)
    if not achado:
        raise NumberError(texto, 'não é um número (exemplos: "8,5", "8.5", "12").')
    return _decimal(achado["sinal"], achado["inteiro"], achado["frac"])


def parse_points(valor: object, permitidos: Collection[float] | None) -> float | None:
    """Pontos: ``parse_decimal`` + ≥ 0, múltiplo de 0,5 e, se dada, dentro de ``permitidos``.

    Toda recusa traz a faixa na mensagem.
    """
    faixa = _faixa(permitidos)
    try:
        pontos = parse_decimal(valor)
    except NumberError as exc:
        raise NumberError(exc.texto, f"use {faixa}.") from exc
    if pontos is None:
        return None
    if pontos < 0 or not (pontos * 2).is_integer() or (permitidos is not None and pontos not in permitidos):
        raise NumberError(_texto(valor), f"use {faixa}.")
    return pontos


def setting_number(row: Any, key: str, default: float) -> float:
    """O número gravado em ``row[key]``; só ``None``, ``""`` e chave ausente viram ``default``.

    Substitui ``row.get(key) or default``, que lia o 0 gravado como ausente.
    Funciona com ``dict`` e com ``sqlite3.Row``.
    """
    if row is None:
        return float(default)
    try:
        valor = row[key]
    except (KeyError, IndexError):
        return float(default)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return float(default)
    try:
        numero = parse_decimal(valor)
    except NumberError as exc:
        raise NumberError(exc.texto, f"o valor gravado em {key} não é um número.") from exc
    return float(default) if numero is None else numero
