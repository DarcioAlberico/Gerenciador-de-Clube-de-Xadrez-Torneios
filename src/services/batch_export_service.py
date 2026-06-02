"""Serviço de geração em lote multi-destino (Fase J).

Executa o registro declarativo de :mod:`batch_export`: para cada relatório
escolhido × formato escolhido, chama o método do ``ExportService`` e grava na
pasta de destino. Isola erros (um relatório que falha não aborta os demais) e
oferece destinos extra: site HTML e impressão (via callback do UI).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.services.batch_export import BATCH_REPORTS, available_report_keys
from src.services.constants import AppError

if TYPE_CHECKING:
    from src.services.export_service import ExportService

logger = logging.getLogger(__name__)


class BatchExportService:
    def __init__(self, export_service: "ExportService") -> None:
        self.export_service = export_service

    @staticmethod
    def _safe_name(name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "torneio").strip()).strip("_")
        return slug or "torneio"

    def _tournament(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.export_service.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        return tournament

    def available_reports(self, tournament_id: int) -> list[dict[str, Any]]:
        tournament = self._tournament(tournament_id)
        is_team = tournament.get("competition_type") == "team"
        return [
            {"key": key, "label": BATCH_REPORTS[key]["label"], "formats": list(BATCH_REPORTS[key]["formats"])}
            for key in available_report_keys(is_team)
        ]

    def run_batch(
        self,
        tournament_id: int,
        report_keys: list[str],
        formats: list[str],
        dest_dir: str | Path,
        *,
        also_html: bool = False,
        printer_cb: Callable[[Path], None] | None = None,
    ) -> dict[str, Any]:
        tournament = self._tournament(tournament_id)
        is_team = tournament.get("competition_type") == "team"
        available = set(available_report_keys(is_team))
        requested_formats = [str(fmt).lower().strip() for fmt in formats]
        if not report_keys:
            raise AppError("Selecione ao menos um relatorio para o lote.")
        if not requested_formats:
            raise AppError("Selecione ao menos um formato para o lote.")

        directory = Path(dest_dir)
        directory.mkdir(parents=True, exist_ok=True)
        safe = self._safe_name(str(tournament.get("name") or ""))

        generated: list[str] = []
        errors: list[str] = []
        skipped: list[str] = []

        for key in report_keys:
            spec = BATCH_REPORTS.get(key)
            if spec is None:
                skipped.append(f"{key}: relatorio desconhecido")
                continue
            if key not in available:
                skipped.append(f"{spec['label']}: indisponivel para este tipo de torneio")
                continue
            valid_formats = [fmt for fmt in requested_formats if fmt in spec["formats"]]
            if not valid_formats:
                skipped.append(f"{spec['label']}: nenhum formato compativel selecionado")
                continue
            method = getattr(self.export_service, spec["method"])
            extra_args = tuple(spec.get("extra_args", ()))
            for fmt in valid_formats:
                path = directory / f"{safe}_{key}.{fmt}"
                try:
                    method(tournament_id, path, *extra_args)
                    generated.append(str(path))
                    if printer_cb is not None and fmt == "pdf":
                        printer_cb(path)
                except Exception as exc:  # isola: um relatorio ruim nao para o lote
                    errors.append(f"{spec['label']} ({fmt}): {exc}")

        if also_html:
            try:
                index_path = self.export_service.export_site(tournament_id, directory / f"{safe}_site")
                generated.append(str(index_path))
            except Exception as exc:
                errors.append(f"Site HTML: {exc}")

        logger.info(
            "Lote do torneio %s: %s gerados, %s erros, %s ignorados",
            tournament_id,
            len(generated),
            len(errors),
            len(skipped),
        )
        return {"generated": generated, "errors": errors, "skipped": skipped, "count": len(generated)}
