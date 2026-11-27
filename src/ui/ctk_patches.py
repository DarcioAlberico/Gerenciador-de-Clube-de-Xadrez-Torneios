"""Remendos locais do CustomTkinter, aplicados uma vez na partida do app.

**RGS-28 — ``DropdownMenu.destroy`` não sai do ``ScalingTracker`` (CTk 5.2.2).**

O ``DropdownMenu`` (o menu suspenso de todo ``CTkOptionMenu`` e
``CTkComboBox``) se registra no ``ScalingTracker`` ao nascer, mas o ``destroy``
dele chama só ``tkinter.Menu.destroy`` e ``CTkAppearanceModeBaseClass.destroy``
— falta ``CTkScalingBaseClass.destroy``, que é quem tira o callback de escala
do registro global. Toda tela remontada deixa para trás o callback de um menu
morto. Na próxima ``ctk.set_widget_scaling`` esse callback reconfigura um
``tkinter.Menu`` que o Tcl já apagou, sai ``TclError: invalid command name``
e o ``update_scaling_callbacks_all`` aborta no meio: parte dos widgets fica na
escala velha e, em ``AlbericusApp._apply_app_settings``, as preferências do
painel do árbitro que vêm depois da escala deixam de ser lidas.

O remendo acrescenta ao ``destroy`` original exatamente a chamada que falta.
Fica restrito às versões em que o defeito foi conferido: numa versão nova do
CustomTkinter ele **não** se aplica, e o teste ``test_ui_rgs28_scaling`` diz
se a correção oficial chegou ou se o remendo precisa ser revisto.
"""
from __future__ import annotations

import logging

import customtkinter as ctk

logger = logging.getLogger("src.ui.ctk_patches")

# Versões em que o defeito foi reproduzido (o 5.2.2 é a fixada no projeto).
VERSOES_COM_DEFEITO_DO_DROPDOWN = frozenset({"5.2.2"})

_MARCA = "_albericus_rgs28_patch"


def aplicar_patches_ctk(versao: str | None = None) -> bool:
    """Aplica os remendos que valem para a versão instalada. Idempotente.

    Devolve ``True`` se o remendo do ``DropdownMenu`` está ativo depois da
    chamada. ``versão`` existe para o teste da guarda; o app usa a instalada.
    """
    versao = versao if versao is not None else str(getattr(ctk, "__version__", ""))
    if versao not in VERSOES_COM_DEFEITO_DO_DROPDOWN:
        logger.info(
            "CustomTkinter %s: remendo RGS-28 do DropdownMenu nao se aplica", versao
        )
        return False

    from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu
    from customtkinter.windows.widgets.scaling import CTkScalingBaseClass

    if getattr(DropdownMenu.destroy, _MARCA, False):
        return True

    destroy_original = DropdownMenu.destroy

    def destroy(self: DropdownMenu) -> None:
        destroy_original(self)
        # A chamada que o 5.2.2 esqueceu: tira o callback de escala do registro.
        CTkScalingBaseClass.destroy(self)

    setattr(destroy, _MARCA, True)
    destroy.__doc__ = destroy_original.__doc__
    DropdownMenu.destroy = destroy  # type: ignore[method-assign]
    return True
