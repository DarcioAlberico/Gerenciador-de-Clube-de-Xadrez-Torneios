"""Serviço da ponte com o Chess-Results.com (Fase J).

Orquestra a ponte descrita em :mod:`chess_results`: prepara o pacote de envio
(TRF16 + passos + URL) e importa inscrições publicadas (CSV). Sem upload
automático — o Chess-Results não tem API pública (ver módulo puro).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.database import Database
from src.services.chess_results import (
    CHESS_RESULTS_REGISTER_URL,
    build_upload_steps,
    normalize_results_url,
    parse_entries_csv,
)
from src.services.constants import AppError

if TYPE_CHECKING:
    from src.services.export_service import ExportService

logger = logging.getLogger(__name__)


class ChessResultsService:
    def __init__(self, db: Database, export_service: "ExportService") -> None:
        self.db = db
        self.export_service = export_service

    @staticmethod
    def _safe_name(name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "torneio").strip()).strip("_")
        return slug or "torneio"

    def prepare_upload(self, tournament_id: int, dest_dir: str | Path) -> dict[str, Any]:
        """Gera o TRF16 na pasta indicada e devolve passos + URL da ponte."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio valido.")
        directory = Path(dest_dir)
        directory.mkdir(parents=True, exist_ok=True)
        trf_path = directory / f"{self._safe_name(tournament.get('name', ''))}_chess_results_trf16.trf"
        warnings = self.export_service.export_chess_results_trf(tournament_id, trf_path)
        logger.info("Pacote Chess-Results preparado para o torneio %s em %s", tournament_id, trf_path)
        return {
            "trf_path": str(trf_path),
            "steps": build_upload_steps(tournament, trf_path.name),
            "register_url": CHESS_RESULTS_REGISTER_URL,
            "published_url": self.get_published_url(tournament_id),
            "warnings": list(warnings or []),
        }

    def import_entries(self, tournament_id: int, file_path: str | Path) -> dict[str, Any]:
        """Importa inscrições/lista publicada do Chess-Results (CSV) como jogadores."""
        if not self.db.get_tournament(tournament_id):
            raise AppError("Selecione um torneio valido.")
        path = Path(file_path)
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")

        payloads, errors = parse_entries_csv(content)
        imported = 0
        player_ids: list[int] = []
        for payload in payloads:
            try:
                player_ids.append(int(self.db.create_player(tournament_id=tournament_id, **payload)))
                imported += 1
            except Exception as exc:  # uma linha ruim não aborta as demais
                errors.append(f"{payload.get('name', '?')}: {exc}")

        logger.info(
            "%s inscricoes do Chess-Results importadas para o torneio %s (%s erros)",
            imported,
            tournament_id,
            len(errors),
        )
        return {"imported": imported, "errors": errors, "player_ids": player_ids}

    def get_published_url(self, tournament_id: int) -> str:
        settings = self.db.get_tournament_settings(tournament_id) or {}
        return str(settings.get("chess_results_url") or "")

    def set_published_url(self, tournament_id: int, url: str) -> str:
        if not self.db.get_tournament(tournament_id):
            raise AppError("Selecione um torneio valido.")
        normalized = normalize_results_url(url)
        if url.strip() and not normalized:
            raise AppError("Informe uma URL valida do Chess-Results (chess-results.com/...).")
        self.db.set_chess_results_url(tournament_id, normalized)
        return normalized
