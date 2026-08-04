"""Classificação por categoria (puro).

A classificação por categoria agrupava pela categoria PRINCIPAL do jogador, e
uma pessoa só tem uma principal. O efeito prático: a jogadora Sub-10 aparecia
no Sub-10 e em lugar nenhum mais — não existia classificação feminina, mesmo
com "Feminino" cadastrado como marca.

Aqui o agrupamento usa TODAS as categorias premiáveis do jogador, e por isso a
mesma pessoa entra em quantas classificações o edital lhe der direito.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def categories_of(row: Mapping[str, Any]) -> list[str]:
    """Categorias de uma linha de classificação, sem repetição.

    A **principal vem junto**, e não só a lista calculada: uma categoria que o
    árbitro escreveu à mão ("Absoluto", "Convidados") não sai de faixa nenhuma
    e sumiria da classificação por categoria se olhássemos apenas o que o motor
    deduziu. Ela vem primeiro porque é a que o árbitro escolheu.

    Base anterior ao ORG-01 não tem `categories` e continua agrupando pela
    principal, que é o que ela sempre teve.
    """
    names: list[str] = []
    primary = str(row.get("category") or "").strip()
    if primary:
        names.append(primary)
    raw = str(row.get("categories") or "")
    names.extend(part.strip() for part in raw.replace(",", ";").split(";") if part.strip())
    return list(dict.fromkeys(names))


def group_by_category(
    standings: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    """Classificação agrupada por categoria, preservando a ordem geral."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in standings:
        for name in categories_of(row):
            groups.setdefault(name, []).append(row)
    return groups


def category_standings(
    standings: Sequence[Mapping[str, Any]], category: str
) -> list[dict[str, Any]]:
    """Classificação de UMA categoria, renumerada de 1 em diante.

    A posição geral continua na linha (`overall_position`): o árbitro precisa
    das duas para conferir o pódio da categoria contra a classificação.
    """
    wanted = str(category or "").strip().casefold()
    if not wanted:
        return []
    ranked: list[dict[str, Any]] = []
    for row in standings:
        if wanted not in {name.casefold() for name in categories_of(row)}:
            continue
        item = dict(row)
        item["overall_position"] = row.get("position")
        item["position"] = len(ranked) + 1
        ranked.append(item)
    return ranked


def category_names(standings: Sequence[Mapping[str, Any]]) -> list[str]:
    """Categorias presentes na classificação, em ordem alfabética."""
    return sorted(group_by_category(standings), key=str.casefold)
