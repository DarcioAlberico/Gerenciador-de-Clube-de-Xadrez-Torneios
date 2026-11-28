"""Ponte entre a leitura de número (``src.domain.numbers``) e a recusa do serviço.

O domínio levanta ``NumberError`` com o texto como veio; o serviço precisa de
``AppError`` com a frase do campo. Aqui fica essa tradução, uma vez só: cada
serviço diz o rótulo do campo e o que vale quando ele vem vazio.
"""
from __future__ import annotations

from collections.abc import Collection

from src.domain.numbers import NumberError, parse_decimal, parse_decimal_br, parse_points, parse_rating
from src.services.constants import AppError

__all__ = ["decimal_field", "money_field", "points_field", "rating_cell"]


def _recusa(mensagem: str, erro: NumberError) -> AppError:
    return AppError(f"{mensagem.rstrip('.')}: {erro}")


def money_field(valor: object, mensagem: str, *, vazio: float = 0.0) -> float:
    """Dinheiro (vírgula decimal, ponto de milhar), arredondado a centavos."""
    try:
        numero = parse_decimal_br(valor)
    except NumberError as exc:
        raise _recusa(mensagem, exc) from exc
    return round(vazio if numero is None else numero, 2)


def decimal_field(valor: object, mensagem: str, *, vazio: float) -> float:
    """Decimal sem milhar: percentual, nota, opacidade."""
    try:
        numero = parse_decimal(valor)
    except NumberError as exc:
        raise _recusa(mensagem, exc) from exc
    return vazio if numero is None else numero


def points_field(
    valor: object, mensagem: str, permitidos: Collection[float] | None, *, vazio: float
) -> float:
    """Pontos: múltiplo de 0,5, ≥ 0 e, se dada, dentro da faixa — que vai na mensagem."""
    try:
        pontos = parse_points(valor, permitidos)
    except NumberError as exc:
        raise _recusa(mensagem, exc) from exc
    return vazio if pontos is None else pontos


def rating_cell(valor: object, rotulo: str) -> tuple[int, str]:
    """Rating de uma célula importada: ``(rating, "")`` ou ``(0, erro da linha)``.

    Vazio é "sem rating" (0); inválido **não** vira 0 calado — devolve o erro,
    e quem importa decide pular a linha.
    """
    try:
        rating = parse_rating(valor)
    except NumberError as exc:
        return 0, f'{rotulo} inválido: "{exc.texto}" ({exc.motivo.rstrip(".")})'
    return (0 if rating is None else rating), ""
