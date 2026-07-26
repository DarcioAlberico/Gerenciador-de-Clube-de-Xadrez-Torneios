"""Filtros de arquivo dos diálogos de importação/exportação (B-6).

Dado puro: sem Tk, sem catálogo. Os rótulos aqui nomeiam **formatos**
("CSV", "Excel"), não frases de interface — por isso não passam pela B-3; o que
mudaria numa versão em inglês é "Todos os arquivos", e ele vem de ``t()``.

Existir separado evita o que havia antes: a mesma lista de quatro filtros
copiada em cinco chamadas de `askopenfilename`, com uma delas já divergindo.
"""
from __future__ import annotations

from ...i18n import t

FileTypes = list[tuple[str, str]]


def _all_files() -> tuple[str, str]:
    return (t("file.all"), "*.*")


def spreadsheets() -> FileTypes:
    """Planilhas e CSV — a importação de jogadores aceita os três formatos."""
    return [
        (t("file.spreadsheets"), "*.csv;*.xls;*.xlsx"),
        ("CSV", "*.csv"),
        ("Excel", "*.xls;*.xlsx"),
        _all_files(),
    ]


def spreadsheets_flat() -> FileTypes:
    """Planilhas e CSV sem os filtros separados (diálogos mais curtos)."""
    return [(t("file.spreadsheets"), "*.csv;*.xls;*.xlsx"), _all_files()]


def csv_only() -> FileTypes:
    return [("CSV", "*.csv"), _all_files()]


def excel_or_csv() -> FileTypes:
    """Salvar modelo: Excel primeiro, porque é o padrão sugerido."""
    return [("Excel", "*.xlsx"), ("CSV", "*.csv"), _all_files()]


def apps_script() -> FileTypes:
    return [(t("file.apps_script"), "*.gs"), _all_files()]
