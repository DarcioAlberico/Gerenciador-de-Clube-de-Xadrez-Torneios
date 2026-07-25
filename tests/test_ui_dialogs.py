"""Testes do componente de diálogos temáticos (``src/ui/components/dialogs.py``).

Os diálogos são **bloqueantes** (``wait_window`` dentro do construtor), então cada
teste agenda a interação com ``after`` antes de abrir o diálogo: o callback roda
dentro do laço de eventos do próprio modal, clica/tecla, e o construtor retorna.

Cobre o que o mock de ``confirm_dialog`` nas telas não cobre: retorno de cada
botão, teclado (Esc/Enter), a proteção contra Enter reflexo em ação destrutiva e
a preservação do *grab* ao abrir um modal sobre outro.

A raiz Tk é única para a classe — criar e destruir um ``CTk`` por teste deixa o
interpretador Tcl instável no Windows ("Can't find a usable tk.tcl" no root
seguinte). Cada teste limpa os próprios ``after`` e diálogos remanescentes.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components.dialogs import alert_dialog, confirm_dialog, tri_state_dialog
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)

# Esta suite abre janela: precisa de display real. Ver o marcador 'gui'
# no pyproject — o gate sem display roda com -m 'not gui'.
pytestmark = pytest.mark.gui

def _find_button(widget, text: str) -> ctk.CTkButton | None:
    """Primeiro ``CTkButton`` com o rótulo dado, em profundidade."""
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


class DialogsTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel para teste de dialogos: {exc}") from exc
        cls.root.geometry("400x300+80+80")
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        self._agendados: list[str] = []

    def tearDown(self) -> None:
        for job in self._agendados:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        for window in list(self.root.winfo_children()):
            if isinstance(window, ctk.CTkToplevel):
                try:
                    window.destroy()
                except Exception:
                    pass
        release_dead_ctk_windows()

    # -- utilitários ------------------------------------------------------

    def _dialog(self) -> ctk.CTkToplevel:
        """Diálogo aberto mais recente (o topo da pilha de modais)."""
        abertos = [w for w in self.root.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        self.assertTrue(abertos, "nenhum dialogo aberto")
        return abertos[-1]

    def _quando_abrir(self, acao, delay: int = 250) -> None:
        """Agenda ``acao(dialogo)`` para rodar com o modal já na tela."""
        self._agendados.append(self.root.after(delay, lambda: acao(self._dialog())))

    def _clicar(self, texto: str, delay: int = 250) -> None:
        def acao(dialog: ctk.CTkToplevel) -> None:
            botao = _find_button(dialog, texto)
            self.assertIsNotNone(botao, f"botao '{texto}' nao encontrado no dialogo")
            botao.invoke()

        self._quando_abrir(acao, delay)

    def _teclar(self, tecla: str, delay: int = 250) -> None:
        def acao(dialog: ctk.CTkToplevel) -> None:
            dialog.focus_force()
            dialog.event_generate(tecla)

        self._quando_abrir(acao, delay)

    # -- confirm_dialog ---------------------------------------------------

    def test_confirmar_retorna_true(self) -> None:
        self._clicar("Sim")
        self.assertTrue(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    def test_cancelar_retorna_false(self) -> None:
        self._clicar("Não")
        self.assertFalse(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    def test_rotulo_de_cancelar_e_acentuado(self) -> None:
        rotulos: dict[str, bool] = {}

        def acao(dialog: ctk.CTkToplevel) -> None:
            rotulos["acentuado"] = _find_button(dialog, "Não") is not None
            dialog.event_generate("<Escape>")

        self._quando_abrir(acao)
        confirm_dialog(self.root, "Confirmar", "Prosseguir?")
        self.assertTrue(rotulos.get("acentuado"), "o rotulo padrao deve ser 'Não', acentuado")

    def test_escape_retorna_false(self) -> None:
        self._teclar("<Escape>")
        self.assertFalse(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    def test_enter_confirma_dialogo_comum(self) -> None:
        self._teclar("<Return>")
        self.assertTrue(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    # -- proteção de ação destrutiva --------------------------------------

    def test_enter_nao_confirma_dialogo_destrutivo(self) -> None:
        """Enter reflexo não pode disparar exclusão: deve ser inerte."""
        def acao(dialog: ctk.CTkToplevel) -> None:
            dialog.focus_force()
            dialog.event_generate("<Return>")
            dialog.update()
            self.assertTrue(
                dialog.winfo_exists(),
                "Enter fechou o dialogo destrutivo — deveria ser inerte",
            )
            _find_button(dialog, "Não").invoke()

        self._quando_abrir(acao)
        self.assertFalse(confirm_dialog(self.root, "Excluir", "Excluir tudo?", danger=True))

    def test_destrutivo_ainda_confirma_pelo_botao(self) -> None:
        """A proteção do Enter não pode inutilizar a confirmação explícita."""
        self._clicar("Sim")
        self.assertTrue(confirm_dialog(self.root, "Excluir", "Excluir tudo?", danger=True))

    # -- tri_state_dialog -------------------------------------------------

    def test_tri_state_sim_nao_cancelar(self) -> None:
        self._clicar("Sim")
        self.assertIs(True, tri_state_dialog(self.root, "Tri", "Escolha"))
        self._clicar("Não")
        self.assertIs(False, tri_state_dialog(self.root, "Tri", "Escolha"))
        self._clicar("Cancelar")
        self.assertIsNone(tri_state_dialog(self.root, "Tri", "Escolha"))

    def test_tri_state_escape_cancela(self) -> None:
        self._teclar("<Escape>")
        self.assertIsNone(tri_state_dialog(self.root, "Tri", "Escolha"))

    # -- alert_dialog e modalidade ----------------------------------------

    def test_alerta_fecha_no_ok_e_libera_o_grab(self) -> None:
        self._clicar("OK")
        alert_dialog(self.root, "Erro", "Falhou", kind="error")
        self.assertIsNone(self.root.grab_current(), "grab deveria ser liberado ao fechar")

    def test_modal_sobre_modal_devolve_o_grab_ao_pai(self) -> None:
        estado: dict[str, object] = {}

        def sobre_o_alerta(pai: ctk.CTkToplevel) -> None:
            self._clicar("Sim", delay=200)
            estado["aninhado"] = confirm_dialog(pai, "Aninhado", "Sobre outro modal?")
            estado["grab"] = self.root.grab_current()
            _find_button(pai, "OK").invoke()

        self._quando_abrir(sobre_o_alerta)
        alert_dialog(self.root, "Pai", "Alerta pai")

        self.assertIs(True, estado["aninhado"])
        self.assertIsNotNone(estado["grab"], "o modal pai deveria reaver o grab")
        self.assertIsNone(self.root.grab_current(), "nenhum grab deveria sobrar no fim")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
