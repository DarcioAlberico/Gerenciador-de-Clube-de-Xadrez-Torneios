from __future__ import annotations

from src.services.federation_exporters.base import FederationExporter


class FederationExporterRegistry:
    def __init__(self) -> None:
        self._exporters: dict[str, FederationExporter] = {}

    def register(self, exporter: FederationExporter) -> None:
        self._exporters[exporter.format.code] = exporter

    def get(self, code: str) -> FederationExporter:
        return self._exporters[code]

    def list_formats(self) -> list[str]:
        return sorted(self._exporters)
