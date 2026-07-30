"""Exportações e impressões da rodada em curso (B-6).

Cinco entregas, cada uma com a mesma coreografia: montar o caminho padrão,
perguntar onde salvar, garantir a extensão e mandar para o background. Eram 148
linhas dentro da tela; aqui são uma classe com dono, e o padrão fica visível —
o que também deixa claro o que **falta** nelas (nenhuma passa `busy_widget`,
dívida registrada na linha de base da F5.9).

O caminho padrão carrega o número da rodada no nome (`..._rodada_3.xlsx`):
exportar duas rodadas seguidas sem isso sobrescreveria a primeira, e o árbitro
só descobriria ao abrir o arquivo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...support import AppError, filedialog


class RoundExportActions:
    """As exportações da rodada, montadas sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def pairings_path(self, suffix: str = ".xlsx") -> Path:
        host = self.host
        tournament = host.db.get_tournament(host.current_tournament_id) if host.current_tournament_id else None
        safe_name = host._safe_filename(str(tournament.get("name") if tournament else "torneio"), "torneio")
        round_data = host.db.get_round(host.current_round_id) if host.current_round_id else None
        round_number = int(round_data["number"]) if round_data else 0
        return host._default_export_dir() / f"{safe_name}_rodada_{round_number}{suffix}"

    def require_round(self) -> int:
        host = self.host
        if not host.current_round_id:
            raise AppError("Selecione uma rodada.")
        return int(host.current_round_id)

    def export_pairings(self) -> None:
        host = self.host
        try:
            round_id = self.require_round()
            default_path = self.pairings_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar rodada",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel", "*.xlsx"),
                    ("CSV", "*.csv"),
                    ("PDF", "*.pdf"),
                    ("Todos os arquivos", "*.*"),
                ],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() not in {".csv", ".xlsx", ".pdf"}:
                path = path.with_suffix(".xlsx")
            host._run_background(
                lambda: host.export_service.export_pairings(round_id, path),
                lambda _result: host._show_info(f"Rodada exportada:\n{path}"),
                "Exportando rodada...",
            )
        except Exception as exc:
            host._show_error(exc)

    def print_pairings(self) -> None:
        host = self.host
        try:
            round_id = self.require_round()
            path = self.pairings_path(".pdf")
            host._run_background(
                lambda: host.export_service.export_pairings(round_id, path),
                lambda _result: host._print_document(path),
                "Preparando impressao...",
            )
        except Exception as exc:
            host._show_error(exc)

    def scoresheets_path(self) -> Path:
        return self.pairings_path(".pdf").with_name(
            f"{self.pairings_path('.pdf').stem}_sumulas.pdf"
        )

    def table_cards_path(self) -> Path:
        return self.pairings_path(".pdf").with_name(
            f"{self.pairings_path('.pdf').stem}_cartoes.pdf"
        )

    def export_scoresheets(self) -> None:
        host = self.host
        try:
            round_id = self.require_round()
            default_path = self.scoresheets_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar sumulas de mesa",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() != ".pdf":
                path = path.with_suffix(".pdf")
            host._run_background(
                lambda: host.export_service.export_scoresheets(round_id, path),
                lambda _result: host._show_info(f"Sumulas exportadas:\n{path}"),
                "Exportando sumulas...",
            )
        except Exception as exc:
            host._show_error(exc)

    def print_scoresheets(self) -> None:
        host = self.host
        try:
            round_id = self.require_round()
            path = self.scoresheets_path()
            host._run_background(
                lambda: host.export_service.export_scoresheets(round_id, path),
                lambda _result: host._print_document(path),
                "Preparando sumulas para impressao...",
            )
        except Exception as exc:
            host._show_error(exc)

    def export_table_cards(self) -> None:
        host = self.host
        try:
            round_id = self.require_round()
            pairings = host.db.get_pairings_for_round(round_id)
            suggested_end = max((int(pairing["board_number"]) for pairing in pairings), default=1)
            value = host._ask_string(
                "Cartoes de mesa",
                f"Informe o intervalo de mesas (ex.: 1-{suggested_end}):",
            )
            if value is None:
                return
            normalized = value.strip().replace(" ", "")
            parts = normalized.split("-", maxsplit=1)
            if len(parts) != 2:
                raise AppError("Informe o intervalo no formato inicio-fim, por exemplo: 1-60.")
            start_board, end_board = (int(part) for part in parts)
            include_qr = host._confirm_action(
                "Cartoes de mesa",
                "Incluir QR de envio de resultado para as mesas da rodada aberta?",
            )
            default_path = self.table_cards_path()
            file_path = filedialog.asksaveasfilename(
                title="Exportar cartoes de mesa",
                initialdir=str(default_path.parent),
                initialfile=default_path.name,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
            )
            if not file_path:
                return
            path = Path(file_path)
            if path.suffix.lower() != ".pdf":
                path = path.with_suffix(".pdf")
            host._run_background(
                lambda: host.export_service.export_table_cards(
                    path,
                    start_board,
                    end_board,
                    round_id=round_id,
                    include_qr=include_qr,
                ),
                lambda _result: host._show_info(f"Cartoes de mesa exportados:\n{path}"),
                "Exportando cartoes de mesa...",
            )
        except ValueError:
            host._show_error("Informe o intervalo no formato inicio-fim, por exemplo: 1-60.")
        except Exception as exc:
            host._show_error(exc)
