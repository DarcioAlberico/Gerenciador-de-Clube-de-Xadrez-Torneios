from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class FederationExportFormat:
    code: str
    label: str
    extension: str


class FederationExporter(Protocol):
    format: FederationExportFormat

    def validate(self, tournament_id: int) -> list[str]:
        ...

    def export(self, tournament_id: int, file_path: str | Path) -> list[str]:
        ...

    def validation_report_rows(self, tournament_id: int) -> list[list[object]]:
        ...
