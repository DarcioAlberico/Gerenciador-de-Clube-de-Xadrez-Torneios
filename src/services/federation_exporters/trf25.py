"""Exportador TRF25 — scaffold sobre TRF16.

Status (2026-05-28): TRF25 ainda é um *final draft* publicado pela FIDE
Technical Commission. Esta implementação **não** é uma exportação TRF25
completa. Ela existe para:

1. Reservar o code 'trf25' no registry sem conflitar com 'trf16'.
2. Permitir que UI/relatórios diferenciem o destino pretendido (CBX/FIDE
   poderá pedir TRF25 quando o draft virar especificação final).
3. Documentar explicitamente, via warnings de validação, que o arquivo
   gerado hoje é equivalente ao TRF16 — para nunca enganar o árbitro.

## O que falta para um TRF25 completo

Quando o draft for finalizado e a especificação completa estiver disponível,
estes pontos precisam ser implementados (sobrescrevendo `export`):

- **Linha TC** (team championship): bloco explícito de match-points e
  game-points por rodada para torneios por equipes.
- **Extensão de tiebreaks**: campos adicionais nas linhas 001 (jogador)
  com valores de Buchholz, Sonneborn-Berger e desempates configurados,
  permitindo que o programa de rating reproduza a classificação.
- **TPR e ratings de performance**: campo opcional na linha 001.
- **Linhas XXR / XXC** (extensões): identificadores e parâmetros do
  pareamento, conforme draft "TRF 2025 extensions for team pairing and
  tie-breaks".
- **Datas estendidas** em outro formato (verificar draft).
- **Rodadas com horário** quando aplicável.

Fontes:
- https://tec.fide.com/2025/01/09/trf25-final-draft/
- https://tec.fide.com/2024/09/04/draft-trf-2025-extensions-for-team-pairing-and-tie-breaks/

Até lá, exportar via este código devolve o mesmo conteúdo do TRF16,
sinalizado por um warning obrigatório no retorno de `validate()` e
`export()`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.services.federation_exporters.base import FederationExportFormat
from src.services.federation_exporters.trf16 import TRF16Exporter


TRF25_SCAFFOLD_WARNING = (
    "TRF25: extensões da FIDE (linhas TC, tiebreaks no 001, XXR/XXC) "
    "ainda não implementadas — arquivo gerado é equivalente a TRF16. "
    "Use TRF16 para envio oficial até a especificação ser finalizada."
)


class TRF25Exporter(TRF16Exporter):
    """Scaffold de exportador TRF25; hoje delega tudo ao TRF16."""

    format = FederationExportFormat(
        code="trf25",
        label="FIDE TRF25 (draft — equivalente a TRF16)",
        extension="trf",
    )

    def export(self, tournament_id: int, file_path: str | Path) -> list[str]:
        warnings = super().export(tournament_id, file_path)
        return [TRF25_SCAFFOLD_WARNING, *warnings]

    def validate(self, tournament_id: int) -> list[str]:
        warnings = super().validate(tournament_id)
        return [TRF25_SCAFFOLD_WARNING, *warnings]
