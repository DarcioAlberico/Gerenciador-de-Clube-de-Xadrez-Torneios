"""Tela de Árbitros — piloto da migração para View / Controller / State (F1.5).

O padrão que as telas-monstro devem seguir (backlog **B-6**):

- [`state.py`](state.py) — dado puro (`dataclass`), sem Tk e sem banco;
- [`controller.py`](controller.py) — decide e conversa com o serviço, sem Tk;
- [`view.py`](view.py) — monta widgets e faz a ponte, sem regra.

O ganho concreto: a regra da tela é testável sem abrir janela, e o estado
deixou de morar num `{"value": None}` ao lado dos widgets.

O import de fora continua sendo ``from .screens.referees import
RefereePagesMixin`` — a fatia interna não vazou para quem chama.
"""
from __future__ import annotations

from .controller import RefereesController
from .state import CAMPOS_TEXTO, CATEGORIAS, RefereeForm, RefereeRow
from .view import RefereePagesMixin

__all__ = [
    "RefereePagesMixin",
    "RefereesController",
    "RefereeForm",
    "RefereeRow",
    "CAMPOS_TEXTO",
    "CATEGORIAS",
]
