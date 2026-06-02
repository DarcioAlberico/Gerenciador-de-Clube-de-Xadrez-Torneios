"""Geração em lote multi-destino de listas (Fase J).

Replica o "Criar listas diferentes de uma vez" do Swiss-Manager: o usuário
escolhe vários **relatórios** e vários **formatos/destinos** e o Albericus gera
tudo de uma vez numa pasta (e, opcionalmente, site HTML + impressão).

Módulo **puro**: só o registro declarativo dos relatórios elegíveis ao lote
(report_key → rótulo, formatos válidos, método do ``ExportService`` e args extra).
A execução fica no ``BatchExportService``. TRF/JSON/site têm fluxo dedicado e
ficam de fora do registro per-formato.
"""

from __future__ import annotations

from typing import Any

# report_key -> especificação. ``team`` indica disponibilidade:
#   "both" (individual e equipes), "individual" ou "team".
BATCH_REPORTS: dict[str, dict[str, Any]] = {
    "completo": {
        "label": "Completo",
        "method": "export_complete",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "both",
    },
    "classificacao": {
        "label": "Classificacao",
        "method": "export_standings",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "both",
    },
    "tabela_cruzada": {
        "label": "Tabela cruzada",
        "method": "export_crosstable",
        "formats": ("csv", "xlsx", "pdf", "html"),
        "team": "both",
    },
    "jogadores": {
        "label": "Jogadores",
        "method": "export_players",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "both",
    },
    "desempates": {
        "label": "Desempates",
        "method": "export_tiebreak_report",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "both",
    },
    "rating_fide": {
        "label": "Rating FIDE",
        "method": "export_fide_rating_report",
        "extra_args": ("fide",),
        "formats": ("csv", "xlsx", "pdf"),
        "team": "individual",
    },
    "premiacao": {
        "label": "Premiacao",
        "method": "export_prize_report",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "individual",
    },
    "estatistica_federacoes": {
        "label": "Estatistica de federacoes",
        "method": "export_federation_statistics",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "individual",
    },
    "estatistica_partidas": {
        "label": "Estatistica de partidas",
        "method": "export_game_statistics",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "individual",
    },
    "fichas": {
        "label": "Fichas individuais",
        "method": "export_player_cards",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "individual",
    },
    "normas_fide": {
        "label": "Normas FIDE",
        "method": "export_norm_report",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "individual",
    },
    "equipes": {
        "label": "Equipes",
        "method": "export_teams",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "team",
    },
    "escalacoes_equipes": {
        "label": "Escalacoes equipes",
        "method": "export_team_lineups",
        "formats": ("csv", "xlsx", "pdf"),
        "team": "team",
    },
}


def available_report_keys(is_team: bool) -> list[str]:
    """Chaves elegíveis ao lote para o tipo de torneio (preserva a ordem do registro)."""
    wanted = "team" if is_team else "individual"
    return [key for key, spec in BATCH_REPORTS.items() if spec["team"] in ("both", wanted)]
