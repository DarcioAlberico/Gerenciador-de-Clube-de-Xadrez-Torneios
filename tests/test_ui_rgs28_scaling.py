"""RGS-28 — a escala da interface continua mudando depois de remontar telas.

No CustomTkinter 5.2.2, ``DropdownMenu.destroy`` (o menu de cada
``CTkOptionMenu``/``CTkComboBox``) não sai do ``ScalingTracker``. Cada tela
remontada deixa para trás o callback de escala de um menu já destruído; na
próxima ``set_widget_scaling`` esse callback reconfigura um ``tkinter.Menu``
morto, o Tcl responde ``invalid command name`` e a atualização da escala aborta
no meio — e, em ``_apply_app_settings``, aborta também a leitura das
preferências do painel do árbitro que vêm depois dela (o ``app.log`` de 11/11
tem 360 rastros disso).

O teste é de Tk de verdade de propósito: o defeito mora na interação entre o
``destroy`` do tkinter e o registro global do CustomTkinter, que um *mock*
apagaria.
"""
from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from tkinter import TclError

import customtkinter as ctk
import pytest
from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu
from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker

from src.core.database import Database
from src.core.services import TournamentService
from src.ui.app import AlbericusApp
from src.ui.ctk_patches import aplicar_patches_ctk
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)


class GuardaDeVersaoTest(unittest.TestCase):
    """Sem Tk: o remendo só vale onde o defeito foi conferido."""

    def test_versao_sem_o_defeito_nao_recebe_remendo(self) -> None:
        antes = DropdownMenu.destroy
        self.assertFalse(aplicar_patches_ctk("5.3.0"))
        self.assertIs(antes, DropdownMenu.destroy)

    def test_aplicar_duas_vezes_nao_empilha_o_remendo(self) -> None:
        self.assertTrue(aplicar_patches_ctk("5.2.2"))
        remendado = DropdownMenu.destroy
        self.assertTrue(aplicar_patches_ctk("5.2.2"))
        self.assertIs(remendado, DropdownMenu.destroy)


@pytest.mark.gui
class EscalaDepoisDeRemontarTelasTest(unittest.TestCase):
    REMONTAGENS = 10

    def setUp(self) -> None:
        self._escala_widget = ScalingTracker.widget_scaling
        self._escala_janela = ScalingTracker.window_scaling
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Escala", "rounds_count": "3", "bye_points": "1"}
        )
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:  # pragma: no cover - ambiente sem display
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.current_tournament_id = self.tournament_id
        self.app.security_service.login("admin", "admin")
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            cancel_pending_callbacks(self.app)
            try:
                self.app.destroy()
            except TclError:  # pragma: no cover
                pass
            release_dead_ctk_windows()
        # A escala é estado de classe do CustomTkinter: devolve o que havia,
        # sem disparar callbacks (a janela já morreu).
        ScalingTracker.widget_scaling = self._escala_widget
        ScalingTracker.window_scaling = self._escala_janela
        self.temp_dir.cleanup()

    def _remontar(self) -> None:
        # A tela de configurações tem CTkOptionMenu (modo de aparência,
        # escala...): cada remontagem destrói os menus suspensos da anterior.
        for _ in range(self.REMONTAGENS):
            self.app.show_app_settings()
            self.app.update_idletasks()

    def test_mudar_a_escala_depois_de_remontar_a_tela_dez_vezes(self) -> None:
        self._remontar()

        ctk.set_widget_scaling(1.1)
        ctk.set_window_scaling(1.1)

    def test_preferencias_do_painel_carregam_depois_de_remontar(self) -> None:
        """O sintoma do árbitro: o intervalo salvo não era lido."""
        self.db.save_app_settings(
            {
                "ui_scale_percent": "110",
                "arbitration_refresh_interval_seconds": "60",
                "arbitration_inline_tables_limit": "40",
            }
        )
        self._remontar()

        with self.assertNoLogs("src.ui", level=logging.ERROR):
            self.app._apply_app_settings()

        self.assertEqual(60, self.app._arbitration_refresh_interval_seconds)
        self.assertEqual(40, self.app._arbitration_inline_tables_limit)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
