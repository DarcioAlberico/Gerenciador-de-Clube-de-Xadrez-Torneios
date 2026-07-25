"""Testes do indicador de tarefa em andamento (``src/ui/components/busy.py``).

O ponto delicado é a **contagem**: várias ações longas podem correr juntas e a
barra só pode sumir quando a última terminar. Raiz Tk única por classe, pelo
mesmo motivo documentado em ``test_ui_dialogs.py``.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk

from src.ui.components.busy import BusyIndicator
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)


class BusyIndicatorTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        # Cancelar os after pendentes ANTES de destruir: a animacao da barra
        # continua agendada e atrapalha a criacao da raiz do proximo arquivo.
        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        self.indicador = BusyIndicator(self.root)
        self.indicador.grid_config(row=0, column=0)

    def tearDown(self) -> None:
        self.indicador.reset()
        try:
            self.indicador.bar.destroy()
        except TclError:  # pragma: no cover
            pass

    def test_nasce_ocioso_e_invisivel(self) -> None:
        self.assertFalse(self.indicador.is_running)
        self.assertEqual(0, self.indicador.active_count)
        self.assertFalse(self.indicador.bar.winfo_ismapped())

    def test_start_mostra_e_stop_esconde(self) -> None:
        self.indicador.start()
        self.root.update()
        self.assertTrue(self.indicador.is_running)
        self.assertTrue(self.indicador.bar.winfo_ismapped())

        self.indicador.stop()
        self.root.update()
        self.assertFalse(self.indicador.is_running)
        self.assertFalse(self.indicador.bar.winfo_ismapped())

    def test_tarefas_simultaneas_so_somem_na_ultima(self) -> None:
        self.indicador.start()
        self.indicador.start()
        self.indicador.start()
        self.assertEqual(3, self.indicador.active_count)

        self.indicador.stop()
        self.indicador.stop()
        self.root.update()
        self.assertTrue(self.indicador.is_running, "duas de tres terminaram: ainda ha trabalho")
        self.assertTrue(self.indicador.bar.winfo_ismapped())

        self.indicador.stop()
        self.root.update()
        self.assertFalse(self.indicador.is_running)
        self.assertFalse(self.indicador.bar.winfo_ismapped())

    def test_stop_sem_start_nao_deixa_contador_negativo(self) -> None:
        self.indicador.stop()
        self.assertEqual(0, self.indicador.active_count)

        # e o proximo start ainda funciona normalmente
        self.indicador.start()
        self.root.update()
        self.assertTrue(self.indicador.bar.winfo_ismapped())

    def test_reset_zera_mesmo_com_tarefas_pendentes(self) -> None:
        self.indicador.start()
        self.indicador.start()
        self.indicador.reset()
        self.root.update()
        self.assertEqual(0, self.indicador.active_count)
        self.assertFalse(self.indicador.bar.winfo_ismapped())

    def test_sobrevive_ao_widget_destruido(self) -> None:
        """Uma tarefa pode terminar depois da tela morrer — não pode explodir."""
        self.indicador.start()
        self.indicador.bar.destroy()
        self.indicador.stop()  # nao deve levantar
        self.assertFalse(self.indicador.is_running)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
