"""Layout configurável de listas (spec E7 — Fase F).

Por enquanto cobre a lista de **classificação**: o usuário escolhe quais colunas
exibir e em que ordem. Funções puras; a persistência fica no banco
(`report_layouts`) e a aplicação em `ExportService._standings_section`.
Layout vazio reproduz exatamente as colunas padrão (regressão).
"""

from __future__ import annotations

import json
from typing import Any

# Colunas disponíveis para a classificação individual: código -> rótulo.
# O código é a chave lida diretamente de cada item da classificação.
STANDINGS_COLUMNS: dict[str, str] = {
    "position": "Pos",
    "name": "Nome",
    "category": "Categoria",
    "age_category": "Categoria idade",
    "rating_category": "Categoria rating",
    "prize_tags": "Tags premiacao",
    "points": "Pts",
    "buchholz": "Buchholz",
    "buchholz_median": "Buchholz M",
    "sonneborn_berger": "SB",
    "wins": "Vitorias",
    "performance": "Performance",
    "rating": "Rating",
    "club": "Clube",
    "white_count": "Brancas",
    "black_count": "Pretas",
    "byes": "Byes",
}

# Ordem/colunas padrão = comportamento histórico do relatório de classificação.
DEFAULT_STANDINGS_COLUMNS: list[str] = [
    "position",
    "name",
    "category",
    "age_category",
    "rating_category",
    "prize_tags",
    "points",
    "buchholz",
    "buchholz_median",
    "sonneborn_berger",
    "wins",
    "performance",
    "rating",
    "club",
]

LAYOUT_REGISTRIES = {"standings": STANDINGS_COLUMNS}
LAYOUT_DEFAULTS = {"standings": DEFAULT_STANDINGS_COLUMNS}


def normalize_columns(raw: Any, report_key: str) -> list[str]:
    """Normaliza uma seleção de colunas (JSON ou lista) para um report_key.

    Mantém só códigos conhecidos, remove duplicados e preserva a ordem. Entrada
    inválida/vazia retorna [] (o chamador então usa o padrão).
    """
    registry = LAYOUT_REGISTRIES.get(report_key)
    if registry is None:
        return []
    items: Any = raw
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            items = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if not isinstance(items, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for entry in items:
        code = str(entry).strip()
        if code in registry and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def resolve_columns(raw: Any, report_key: str) -> list[str]:
    """Colunas efetivas: a seleção normalizada ou o padrão quando vazia."""
    return normalize_columns(raw, report_key) or list(LAYOUT_DEFAULTS.get(report_key, []))


def serialize_columns(columns: list[str]) -> str:
    return json.dumps(list(columns), ensure_ascii=False)
