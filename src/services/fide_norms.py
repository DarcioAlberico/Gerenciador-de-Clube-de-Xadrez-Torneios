"""Assistente de normas/títulos FIDE — fachada do pacote ``src.services.norms``.

Funções de APOIO ao árbitro: a partir dos adversários enfrentados, conferem os
indicadores do Handbook B.01 (seção 1.4) e dizem o que falta para cada norma.
**Não é homologação** — a concessão de norma e título é exclusiva da FIDE.

O motor foi para ``src/services/norms`` na FED-06, quando os indicadores
passaram a seguir o Handbook de verdade (titulados por nível, piso de rating
ajustado, limites de federação e de não ratados). Este módulo continua sendo o
ponto de importação do resto do sistema.
"""

from __future__ import annotations

from src.services.norms import (
    NORM_REQUIREMENTS,
    NormEvaluation,
    build_norm_report,
    evaluate_norms,
    is_title_holder,
)
from src.services.norms.handbook import FIDE_TITLES, TITLE_HOLDER_TITLES

# Compatibilidade com o nome antigo do dicionário de limiares.
TITLE_NORM_REQUIREMENTS = NORM_REQUIREMENTS

__all__ = [
    "FIDE_TITLES",
    "NORM_REQUIREMENTS",
    "NormEvaluation",
    "TITLE_HOLDER_TITLES",
    "TITLE_NORM_REQUIREMENTS",
    "build_norm_report",
    "evaluate_norms",
    "is_title_holder",
]
