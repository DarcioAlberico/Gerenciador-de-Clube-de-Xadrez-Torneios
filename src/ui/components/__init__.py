"""Componentes de UI reutilizáveis do Albericus.

Catálogo canônico (ESPEC_UI_UX §4.4): uma implementação por componente, importada
explicitamente pelas telas (sem ``import *``). Fundação da modularização da camada
de UI — telas migradas passam a montar a interface a partir daqui.
"""
from __future__ import annotations

from .busy import BusyIndicator
from .buttons import danger_button, neutral_button, primary_button, secondary_button
from .debounce import Debounced, debounce
from .dialogs import alert_dialog, confirm_dialog, tri_state_dialog
from .donation import show_donation_modal
from .empty_state import EmptyState
from .fields import (
    FIELD_HEIGHT,
    FIELD_LG,
    FIELD_MD,
    FIELD_RADIUS,
    FIELD_SM,
    date_field,
    labeled_field,
    select_field,
    text_area,
    text_field,
)
from .menu_button import menu_button
from .toast import ToastStack
from .tooltip import Tooltip
from .tree import ThemedTreeview
from .wrap_row import WrapRow

__all__ = [
    "primary_button",
    "secondary_button",
    "neutral_button",
    "danger_button",
    "text_field",
    "select_field",
    "text_area",
    "date_field",
    "labeled_field",
    "FIELD_HEIGHT",
    "FIELD_RADIUS",
    "FIELD_SM",
    "FIELD_MD",
    "FIELD_LG",
    "menu_button",
    "confirm_dialog",
    "tri_state_dialog",
    "alert_dialog",
    "Tooltip",
    "EmptyState",
    "Debounced",
    "debounce",
    "BusyIndicator",
    "ThemedTreeview",
    "ToastStack",
    "WrapRow",
    "show_donation_modal",
]
