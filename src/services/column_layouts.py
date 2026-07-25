"""Largura das colunas das tabelas de tela — regras puras (B-1 / P2-9).

Sem Tk, sem banco: só decide **qual é a tabela**, **o que vale a pena guardar**
e **que largura aplicar**. A persistência fica em `ColumnLayoutService` e a
aplicação em `AlbericusApp._make_tree`.

Três decisões que valem registro:

1. **Identidade da tabela sai dos dados, não de um rótulo digitado.** São ~59
   chamadas de `_make_tree`; exigir uma chave em cada uma seria 59 chances de
   errar e de duas telas colidirem em silêncio. A chave é um hash de códigos +
   títulos das colunas: duas tabelas com as mesmas colunas *e* os mesmos títulos
   são, para o usuário, a mesma tabela — compartilhar largura é o esperado.
2. **Guarda-se o desvio, não a largura.** Se amanhã o padrão de uma coluna
   mudar, quem nunca arrastou aquela coluna acompanha o padrão novo; só quem
   escolheu uma largura mantém a escolha.
3. **Largura tem piso e teto.** Uma coluna de 3px é uma coluna perdida, e o
   usuário não tem como saber que ela ainda está lá — o piso existe para o
   arrasto não conseguir esconder dado.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

# Piso e teto de largura, em pixels. O piso protege contra a coluna sumir num
# arrasto; o teto contra um valor absurdo vindo de banco editado à mão.
MIN_COLUMN_WIDTH = 40
MAX_COLUMN_WIDTH = 900


def layout_key(columns: Iterable[str], headings: Mapping[str, str] | None = None) -> str:
    """Identidade estável da tabela: hash curto de códigos + títulos.

    Determinístico entre execuções (``hashlib``, não ``hash()``, que é
    randomizado por processo — largura salva não sobreviveria ao reinício).
    """
    headings = headings or {}
    # JSON como material do hash porque ele ja resolve a ambiguidade de
    # concatenacao: sem delimitador, ("ab", "c") e ("a", "bc") virariam o
    # mesmo texto e duas tabelas diferentes dividiriam a mesma preferencia.
    material = json.dumps(
        [[code, headings.get(code, "")] for code in columns], ensure_ascii=False
    )
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]


def clamp_width(value: Any) -> int:
    """Converte para inteiro dentro de [piso, teto]; 0 quando não é número."""
    try:
        width = int(value)
    except (TypeError, ValueError):
        return 0
    if width <= 0:
        return 0
    return max(MIN_COLUMN_WIDTH, min(MAX_COLUMN_WIDTH, width))


def normalize_widths(raw: Any) -> dict[str, int]:
    """Lê o que veio do banco (JSON ou dict) e devolve larguras confiáveis.

    Banco corrompido, JSON de outra versão ou chave estranha viram ausência de
    preferência — nunca exceção: uma tabela abrir com a largura padrão é um
    incômodo, abrir com erro é um chamado.
    """
    data: Any = raw
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return {}
    if not isinstance(data, dict):
        return {}
    widths: dict[str, int] = {}
    for column, value in data.items():
        code = str(column).strip()
        width = clamp_width(value)
        if code and width:
            widths[code] = width
    return widths


def deviations(defaults: Mapping[str, int], current: Mapping[str, int]) -> dict[str, int]:
    """O que o usuário mexeu: só as colunas que saíram do padrão."""
    changed: dict[str, int] = {}
    for column, value in current.items():
        width = clamp_width(value)
        if width and width != clamp_width(defaults.get(column, 0)):
            changed[str(column)] = width
    return changed


def effective_widths(
    columns: Iterable[str],
    defaults: Mapping[str, int],
    saved: Mapping[str, int],
    fallback: int = 100,
) -> dict[str, int]:
    """Largura final de cada coluna: a salva quando existe, senão o padrão."""
    resolved: dict[str, int] = {}
    for column in columns:
        chosen = clamp_width(saved.get(column, 0))
        if not chosen:
            chosen = clamp_width(defaults.get(column, 0)) or fallback
        resolved[column] = chosen
    return resolved


def serialize_widths(widths: Mapping[str, int]) -> str:
    """JSON estável (chaves ordenadas) para gravar no banco."""
    limpo = {str(k): clamp_width(v) for k, v in widths.items()}
    return json.dumps(
        {k: v for k, v in sorted(limpo.items()) if v}, ensure_ascii=False
    )
