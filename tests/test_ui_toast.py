"""Testes da pilha de toasts (``src/ui/components/toast.py``).

O que importa aqui: empilhamento, o botão de ação (``Desfazer``) e a dispensa —
inclusive a corrida entre clicar na ação e o timer de expiração chegar depois.
Raiz Tk única por classe, pelo motivo documentado em ``test_ui_dialogs.py``.
"""
from __future__ import annotations

import time
import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components.toast import DURATION_MS, UNDO_DURATION_MS, ToastStack
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)

# Esta suite abre janela: precisa de display real. Ver o marcador 'gui'
# no pyproject — o gate sem display roda com -m 'not gui'.
pytestmark = pytest.mark.gui

def _find_button(widget, text: str) -> ctk.CTkButton | None:
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


class ToastStackTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.geometry("500x400+80+80")
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        cancel_pending_callbacks(cls.root)  # timers de expiracao dos toasts
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        self.stack = ToastStack(self.root)

    def tearDown(self) -> None:
        self.stack.clear()
        self.root.update()

    def _bombear(self, segundos: float) -> None:
        """Roda o laço de eventos por um tempo, para os ``after`` vencerem."""
        limite = time.time() + segundos
        while time.time() < limite:
            self.root.update()
            time.sleep(0.01)

    def test_mostra_e_empilha_na_ordem(self) -> None:
        primeiro = self.stack.show("Primeiro")
        segundo = self.stack.show("Segundo")
        self.root.update()

        self.assertEqual([primeiro, segundo], self.stack.active)
        # o mais recente fica embaixo (mais perto da statusbar)
        self.assertGreater(primeiro.winfo_y(), 0)
        self.assertGreater(segundo.winfo_y(), primeiro.winfo_y())

    def test_sem_acao_nao_tem_botao(self) -> None:
        toast = self.stack.show("Salvo.", kind="success")
        self.root.update()
        self.assertIsNone(_find_button(toast, "Desfazer"))

    def test_acao_dispara_callback_e_fecha_o_toast(self) -> None:
        cliques: list[str] = []
        toast = self.stack.show(
            "Bye removido.", kind="success", action=("Desfazer", lambda: cliques.append("undo"))
        )
        self.root.update()

        botao = _find_button(toast, "Desfazer")
        self.assertIsNotNone(botao, "toast com acao deve ter o botao")
        botao.invoke()
        self.root.update()

        self.assertEqual(["undo"], cliques)
        self.assertEqual([], self.stack.active, "o toast deve sumir ao acionar a acao")

    def test_toast_com_acao_dura_mais(self) -> None:
        self.assertGreater(UNDO_DURATION_MS, DURATION_MS)

    def test_expira_sozinho(self) -> None:
        self.stack.show("Efemero", duration_ms=120)
        self.root.update()
        self.assertEqual(1, len(self.stack.active))

        self._bombear(0.6)
        self.assertEqual([], self.stack.active, "o toast deveria ter expirado")

    def test_timer_apos_o_clique_nao_quebra(self) -> None:
        """Corrida real: a pessoa clica em Desfazer e o timer vence depois."""
        toast = self.stack.show(
            "Removido.", duration_ms=120, action=("Desfazer", lambda: None)
        )
        self.root.update()
        _find_button(toast, "Desfazer").invoke()
        self.assertEqual([], self.stack.active)

        self._bombear(0.5)  # o after chega para um toast ja destruido
        self.assertEqual([], self.stack.active)

    def test_clear_remove_todos(self) -> None:
        self.stack.show("A")
        self.stack.show("B")
        self.stack.show("C")
        self.root.update()
        self.assertEqual(3, len(self.stack.active))

        self.stack.clear()
        self.root.update()
        self.assertEqual([], self.stack.active)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
