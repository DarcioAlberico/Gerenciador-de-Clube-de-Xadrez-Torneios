"""Texto que uma planilha leria como fórmula — a decisão mora aqui (RG2-20).

Nomes, clubes e observações chegam de formulário (Google Forms) e saem em CSV
e XLSX. Uma célula que começa com ``=``, ``+``, ``-``, ``@``, tabulação ou
retorno de carro é fórmula para o Excel e o LibreOffice: ``=HYPERLINK(...)``
abre um site, ``=cmd|...`` pede para executar um programa.

- XLSX: a célula é gravada como texto (``data_type = "s"``) com o texto
  intacto — o telefone "+55 11 …" continua "+55 11 …".
- CSV: não há tipo de célula; o texto ganha um ``'`` na frente (a convenção que
  as planilhas entendem como "isto é texto"). O importador do Albericus retira
  esse ``'`` ao ler, e o dado volta igual.
- Números não mudam.
"""
from __future__ import annotations

from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def looks_like_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(FORMULA_PREFIXES)


def csv_cell(value: Any) -> Any:
    """O valor como vai para o CSV: texto que parece fórmula ganha ``'``."""
    return "'" + value if looks_like_formula(value) else value


def unguard_csv_cell(value: Any) -> Any:
    """Desfaz ``csv_cell``: tira o ``'`` só quando ele protege uma fórmula."""
    if isinstance(value, str) and value.startswith("'") and looks_like_formula(value[1:]):
        return value[1:]
    return value


def csv_row(row: list[Any]) -> list[Any]:
    return [csv_cell(value) for value in row]
