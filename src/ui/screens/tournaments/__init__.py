"""Domínio Torneio na camada de UI.

Pacote criado pela B-6 seguindo o molde do piloto de Árbitros (F1.5):

- [`state.py`](state.py) — dado puro: regras do formulário e forma da linha;
- [`controller.py`](controller.py) — decide e fala com os serviços, sem Tk;
- [`view.py`](view.py) — monta widgets e faz a ponte;
- [`pages.py`](pages.py) — as outras telas do domínio, ainda no formato antigo.

O import externo continua o mesmo (`from .screens.tournaments import
TournamentPagesMixin`): quem consome não precisou saber da mudança.
"""
from __future__ import annotations

from ..tournament_players_ui import TournamentPlayersMixin
from ..tournament_settings_ui import TournamentSettingsMixin
from .pages import TournamentOtherPagesMixin
from .view import TournamentListMixin, TournamentListView

__all__ = ["TournamentPagesMixin", "TournamentListView"]


class TournamentPagesMixin(
    TournamentListMixin,
    TournamentOtherPagesMixin,
    TournamentPlayersMixin,
    TournamentSettingsMixin,
):
    """Mesma fachada de antes — agora composta em vez de escrita num arquivo só."""
