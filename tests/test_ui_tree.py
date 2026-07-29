"""Testes da tabela temada (``src/ui/components/tree.py`` — F5.5).

Tudo aqui abre janela (marcador ``gui``): zebra, ordenação e estado vazio são
comportamento de widget. A raiz é única por classe, como em ``test_ui_busy.py``.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui import theme
from src.ui.components import EmptyState
from src.ui.components.tree import _ZEBRA_EVEN, _ZEBRA_ODD, ThemedTreeview

pytestmark = pytest.mark.gui


class ThemedTreeviewTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        from tests.support.ctk_cleanup import create_tk_window

        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        from tests.support.ctk_cleanup import (
            cancel_pending_callbacks,
            release_dead_ctk_windows,
        )

        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        self.tree = ThemedTreeview(self.root, columns=["nome", "rating"], show="headings")
        self.tree.heading("nome", text="Nome")
        self.tree.heading("rating", text="Rating")
        self.tree.enable_sorting()

    def tearDown(self) -> None:
        try:
            self.tree.destroy()
        except TclError:  # pragma: no cover
            pass

    # ------------------------------------------------------------- valores
    def test_none_vira_celula_vazia(self) -> None:
        """P3-9: o "None" literal vazando em coluna de tabela."""
        iid = self.tree.insert("", "end", values=("Ana", None))
        self.assertEqual("", self.tree.set(iid, "rating"))
        iid2 = self.tree.insert("", "end", values=("None", 1500))
        self.assertEqual("", self.tree.set(iid2, "nome"))

    # --------------------------------------------------------------- zebra
    def test_linhas_de_topo_alternam_a_zebra(self) -> None:
        a = self.tree.insert("", "end", values=("A", 1))
        b = self.tree.insert("", "end", values=("B", 2))
        c = self.tree.insert("", "end", values=("C", 3))
        self.assertIn(_ZEBRA_ODD, self.tree.item(a, "tags"))
        self.assertIn(_ZEBRA_EVEN, self.tree.item(b, "tags"))
        self.assertIn(_ZEBRA_ODD, self.tree.item(c, "tags"))

    def test_tag_semantica_vem_antes_da_zebra(self) -> None:
        """A tag da tela define a cor; a zebra entra por último (menor prioridade)."""
        iid = self.tree.insert("", "end", values=("A", 1), tags=("registrado",))
        tags = list(self.tree.item(iid, "tags"))
        self.assertEqual(["registrado", _ZEBRA_ODD], tags)

    def test_excluir_reaplica_a_alternancia(self) -> None:
        a = self.tree.insert("", "end", values=("A", 1))
        b = self.tree.insert("", "end", values=("B", 2))
        self.tree.delete(a)
        self.assertIn(_ZEBRA_ODD, self.tree.item(b, "tags"))

    # ----------------------------------------------------------- ordenação
    def test_ordena_numerico_com_vazios_ao_fim(self) -> None:
        alto = self.tree.insert("", "end", values=("Alto", "1820"))
        vazio = self.tree.insert("", "end", values=("Sem rating", ""))
        baixo = self.tree.insert("", "end", values=("Baixo", "990"))
        self.tree.sort_by("rating")
        self.assertEqual([baixo, alto, vazio], list(self.tree.get_children("")))
        self.tree.sort_by("rating")  # segundo clique inverte
        self.assertEqual([alto, baixo, vazio], list(self.tree.get_children("")))

    def test_ordena_texto_sem_caixa(self) -> None:
        b = self.tree.insert("", "end", values=("bruno", 1))
        a = self.tree.insert("", "end", values=("Ana", 2))
        self.tree.sort_by("nome")
        self.assertEqual([a, b], list(self.tree.get_children("")))

    def test_cabecalho_ganha_seta_e_zebra_acompanha_a_nova_ordem(self) -> None:
        self.tree.insert("", "end", values=("B", "2"))
        primeiro_apos = self.tree.insert("", "end", values=("A", "1"))
        self.tree.sort_by("rating")
        self.assertTrue(str(self.tree.heading("rating", "text")).endswith("▲"))
        self.assertEqual("Nome", str(self.tree.heading("nome", "text")))
        self.assertIn(_ZEBRA_ODD, self.tree.item(primeiro_apos, "tags"))

    # -------------------------------------------------------- estado vazio
    def test_estado_vazio_aparece_e_some_com_as_linhas(self) -> None:
        overlay = EmptyState(self.root, title="Nenhum registro")
        self.tree.attach_empty_state(overlay)
        self.root.update_idletasks()
        self.assertTrue(overlay.winfo_manager())
        iid = self.tree.insert("", "end", values=("A", 1))
        self.assertFalse(overlay.winfo_manager())
        self.tree.delete(iid)
        self.assertTrue(overlay.winfo_manager())

    # ------------------------------------------------------------ listeners
    def test_destruir_desinscreve_do_tema(self) -> None:
        arvore = ThemedTreeview(self.root, columns=["x"], show="headings")
        callback = arvore._apply_zebra_colors
        self.assertIn(callback, theme._listeners)
        arvore.destroy()
        self.root.update_idletasks()
        self.assertNotIn(callback, theme._listeners)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
