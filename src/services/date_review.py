"""Datas legadas: relatório "Datas a revisar" e normalização para ISO (RGS-06).

Antes da regra única (`src.domain.dates`), cada fronteira gravava a data no
formato que aceitava: o banco real tem `dd/mm/aaaa`, ISO com hora e, em alguns
campos, texto que não é data. A spec descarta `CHECK` e reconstrução de tabela
(o SQLite não faz `ADD CHECK`, e reconstruir com `foreign_keys=ON` dispara o
`ON DELETE CASCADE`). O caminho é outro:

- **normalizar** o que a regra converte — sempre com backup antes, e só quando
  há o que converter (rodar de novo não faz nada: é idempotente);
- **relatar** o que ela recusa, sem tocar: quem decide o valor certo é gente.

Ano sozinho no nascimento é dado válido (a lista da FIDE só publica o ano) e
não entra em nenhuma das duas listas.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.dates import Ano, Data, DataInvalida, DataVazia, parse_date, storage_text

logger = logging.getLogger(__name__)

__all__ = [
    "DATE_COLUMNS",
    "DateColumn",
    "DateToReview",
    "NormalizationResult",
    "dates_to_review",
    "format_report",
    "normalize_legacy_dates",
]


@dataclass(frozen=True)
class DateColumn:
    table: str
    column: str
    label: str
    allows_year: bool = False
    # Coluna que identifica a linha para quem lê o relatório (nome do jogador,
    # do torneio...). Vazio = só o número da linha.
    name_column: str = ""


# A base oficial (`official_players`, `official_rating_snapshots`) fica de
# fora de propósito: é cópia da lista da federação, refeita a cada importação e
# sem tela de edição. No banco real de 11/11 ela tinha 11.768 nascimentos como
# `0000-00-00` e `0012-12-06` — um relatório com isso esconderia o que o
# árbitro pode e deve corrigir.
#
# Catálogo das colunas de data. Coluna ou tabela ausente (banco antigo) é
# pulada: o relatório não pode impedir o app de abrir.
DATE_COLUMNS: tuple[DateColumn, ...] = (
    DateColumn("tournaments", "start_date", "Torneio: data inicial", name_column="name"),
    DateColumn("tournaments", "end_date", "Torneio: data final", name_column="name"),
    DateColumn("tournament_settings", "cutoff_date", "Torneio: Data de corte"),
    DateColumn("tournament_settings", "category_reference_date", "Torneio: data de referência da idade", True),
    DateColumn("tournament_settings", "team_lineup_deadline", "Torneio: prazo de escalação"),
    DateColumn("tournament_categories", "reference_date", "Categoria: data de referência", True, "name"),
    DateColumn("round_schedule", "date", "Agenda de rodadas: data"),
    DateColumn("players", "birth_date", "Jogador: nascimento", True, "name"),
    DateColumn("members", "birth_date", "Sócio: nascimento", True, "name"),
    DateColumn("member_class_enrollments", "start_date", "Matrícula: início"),
    DateColumn("member_class_enrollments", "end_date", "Matrícula: fim"),
    DateColumn("training_lists", "target_date", "Lista de treino: data alvo", name_column="name"),
    DateColumn("training_sessions", "session_date", "Aula: data", name_column="title"),
    DateColumn("exercise_attempts", "attempt_date", "Tentativa de exercício: data"),
    DateColumn("payments", "due_date", "Pagamento: vencimento", name_column="description"),
    DateColumn("payments", "payment_date", "Pagamento: data de pagamento", name_column="description"),
    DateColumn("club_events", "event_date", "Evento: data", name_column="title"),
    DateColumn("inventory_items", "acquisition_date", "Inventário: aquisição", name_column="name"),
    DateColumn("inventory_loans", "loan_date", "Empréstimo: data"),
    DateColumn("inventory_loans", "due_date", "Empréstimo: devolução prevista"),
    DateColumn("inventory_loans", "return_date", "Empréstimo: devolução"),
    DateColumn("inventory_maintenance", "opened_date", "Manutenção: abertura"),
    DateColumn("inventory_maintenance", "resolved_date", "Manutenção: conclusão"),
)


@dataclass(frozen=True)
class DateToReview:
    table: str
    column: str
    label: str
    row_id: int
    name: str
    value: str
    reason: str


@dataclass(frozen=True)
class NormalizationResult:
    converted: int
    backup_path: Path | None
    to_review: tuple[DateToReview, ...]


@dataclass(frozen=True)
class _Conversion:
    table: str
    column: str
    row_id: int
    new_value: str


def _columns_of(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _scan(db: Any) -> tuple[list[DateToReview], list[_Conversion]]:
    revisar: list[DateToReview] = []
    converter: list[_Conversion] = []
    with db.connect() as connection:
        cache: dict[str, set[str]] = {}
        for spec in DATE_COLUMNS:
            colunas = cache.setdefault(spec.table, _columns_of(connection, spec.table))
            if spec.column not in colunas:
                continue
            nome = spec.name_column if spec.name_column in colunas else ""
            seletor = f", {nome}" if nome else ""
            linhas = connection.execute(
                f"SELECT rowid, {spec.column}{seletor} FROM {spec.table} "
                f"WHERE {spec.column} IS NOT NULL AND TRIM({spec.column}) <> ''"
            ).fetchall()
            for linha in linhas:
                row_id, bruto = int(linha[0]), str(linha[1])
                resultado = parse_date(bruto, permite_ano=spec.allows_year)
                if isinstance(resultado, DataInvalida):
                    revisar.append(
                        DateToReview(
                            spec.table,
                            spec.column,
                            spec.label,
                            row_id,
                            str(linha[2] or "") if nome else "",
                            bruto,
                            resultado.motivo,
                        )
                    )
                elif isinstance(resultado, (Data, Ano, DataVazia)):
                    novo = storage_text(resultado)
                    if novo != bruto:
                        converter.append(_Conversion(spec.table, spec.column, row_id, novo))
    return revisar, converter


def dates_to_review(db: Any) -> list[DateToReview]:
    """Valores gravados que a regra única recusa. Não altera nada."""
    return _scan(db)[0]


def normalize_legacy_dates(db: Any) -> NormalizationResult:
    """Converte para ISO o que a regra aceita, com backup antes. Idempotente.

    Sem nada a converter, não há backup nem escrita. As conversões vão numa
    conexão só: ou entram todas, ou nenhuma.
    """
    revisar, converter = _scan(db)
    if not converter:
        return NormalizationResult(0, None, tuple(revisar))
    backup = db.backup_before("normalizar_datas")
    with db.connect() as connection:
        for item in converter:
            connection.execute(
                f"UPDATE {item.table} SET {item.column} = ? WHERE rowid = ?",
                (item.new_value, item.row_id),
            )
    logger.info("Datas legadas normalizadas para ISO: %s (backup em %s)", len(converter), backup)
    return NormalizationResult(len(converter), Path(backup), tuple(revisar))


def format_report(itens: list[DateToReview] | tuple[DateToReview, ...]) -> str:
    """Texto do relatório "Datas a revisar" (vazio quando não há nada)."""
    if not itens:
        return ""
    linhas = [
        f"{len(itens)} data(s) gravada(s) que o programa não consegue ler.",
        "Elas continuam como estão. Corrija cada uma no cadastro indicado:",
        "",
    ]
    for item in itens:
        quem = f" — {item.name}" if item.name else f" — registro {item.row_id}"
        linhas.append(f"• {item.label}{quem}: \"{item.value}\" ({item.reason})")
    return "\n".join(linhas)
