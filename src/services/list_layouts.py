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


def normalize_column_specs(raw: Any, report_key: str) -> list[dict[str, Any]]:
    """Normaliza colunas para [{"key", "width"}], retrocompatível.

    Aceita itens como string (largura 0 = auto) ou dict {"key","width"}. Mantém
    só códigos conhecidos, remove duplicados e preserva a ordem. Largura é um
    inteiro >= 0 (0 = automática).
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
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in items:
        if isinstance(entry, dict):
            key = str(entry.get("key") or "").strip()
            try:
                width = int(entry.get("width") or 0)
            except (TypeError, ValueError):
                width = 0
        else:
            key, width = str(entry).strip(), 0
        if key in registry and key not in seen:
            seen.add(key)
            result.append({"key": key, "width": max(0, width)})
    return result


def normalize_columns(raw: Any, report_key: str) -> list[str]:
    """Apenas os códigos das colunas (compatibilidade)."""
    return [spec["key"] for spec in normalize_column_specs(raw, report_key)]


def resolve_column_specs(raw: Any, report_key: str) -> list[dict[str, Any]]:
    """Specs efetivas (com largura): a seleção normalizada ou o padrão (largura 0)."""
    specs = normalize_column_specs(raw, report_key)
    if specs:
        return specs
    return [{"key": key, "width": 0} for key in LAYOUT_DEFAULTS.get(report_key, [])]


def resolve_columns(raw: Any, report_key: str) -> list[str]:
    """Colunas efetivas (apenas códigos): a seleção ou o padrão."""
    return [spec["key"] for spec in resolve_column_specs(raw, report_key)]


def serialize_columns(columns: list[Any]) -> str:
    """Serializa colunas (lista de códigos ou de {key,width}) como JSON de specs."""
    specs: list[dict[str, Any]] = []
    for column in columns:
        if isinstance(column, dict):
            key = str(column.get("key") or "").strip()
            try:
                width = int(column.get("width") or 0)
            except (TypeError, ValueError):
                width = 0
        else:
            key, width = str(column).strip(), 0
        if key:
            specs.append({"key": key, "width": max(0, width)})
    return json.dumps(specs, ensure_ascii=False)
