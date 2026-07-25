"""Componentes de UI reutilizáveis do Albericus.

Catálogo canônico (ESPEC_UI_UX §4.4): uma implementação por componente, importada
explicitamente pelas telas (sem ``import *``). Fundação da modularização da camada
de UI — telas migradas passam a montar a interface a partir daqui.
"""
from __future__ import annotations

from .buttons import danger_button, primary_button, secondary_button
from .dialogs import alert_dialog, confirm_dialog, tri_state_dialog
from .donation import show_donation_modal
from .empty_state import EmptyState
from .menu_button import menu_button
from .tooltip import Tooltip

__all__ = [
    "primary_button",
    "secondary_button",
    "danger_button",
    "menu_button",
    "confirm_dialog",
    "tri_state_dialog",
    "alert_dialog",
    "Tooltip",
    "EmptyState",
    "show_donation_modal",
]
