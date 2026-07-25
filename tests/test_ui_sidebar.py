"""Testes da sidebar de navegação (``src/ui/components/sidebar.py``).

Cobre o que a barra promete: espelhar o registro único, navegar pelo
``Navigator``, destacar o destino ativo e — o ponto que quase passou batido —
encolher quando a janela não tem largura para ela.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk

from src.ui.components.sidebar import MODE_FULL, MODE_HIDDEN, MODE_RAIL, Sidebar
from src.ui.navigation import DESTINATIONS, Navigator
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)


class HostFalso:
    """Aplicação de mentira: registra as telas abertas."""

    def __init__(self) -> None:
        self.abertas: list[str] = []

    def __getattr__(self, nome: str):
        if not nome.startswith("show_"):
            raise AttributeError(nome)
        return lambda: self.abertas.append(nome)


class SidebarTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.geometry("600x500+80+80")
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
        self.host = HostFalso()
        self.navigator = Navigator(self.host)
        self.sidebar = Sidebar(self.root, navigator=self.navigator)
        self.sidebar.frame.grid(row=0, column=0, sticky="nsw")
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.sidebar.frame.destroy()
        except TclError:  # pragma: no cover
            pass
        self.root.update()

    # -- espelho do registro ----------------------------------------------

    def test_tem_um_item_por_destino(self) -> None:
        self.assertEqual(len(DESTINATIONS), len(self.sidebar.items))
        for destino in DESTINATIONS:
            self.assertIn(destino.method, self.sidebar.items)

    def test_rotulos_vem_do_registro(self) -> None:
        botao = self.sidebar.items["show_pairings"]
        self.assertIn("Rodadas", botao.cget("text"))

    # -- navegação ---------------------------------------------------------

    def test_clique_navega_pelo_navigator(self) -> None:
        self.sidebar.items["show_standings"].invoke()
        self.assertEqual(["show_standings"], self.host.abertas)
        self.assertEqual("show_standings", self.navigator.current)

    def test_destaque_segue_a_navegacao_mesmo_sem_clique_na_barra(self) -> None:
        """Abrir a tela por atalho ou por botão da tela também acende o item."""
        self.navigator.subscribe(self.sidebar.highlight)
        self.navigator.go("members")
        self.assertEqual("show_members", self.sidebar.active)

    def test_destaque_e_exclusivo(self) -> None:
        self.navigator.subscribe(self.sidebar.highlight)
        self.navigator.go("members")
        self.navigator.go("finance")
        self.assertEqual("show_finance", self.sidebar.active)
        self.assertEqual(
            "transparent", self.sidebar.items["show_members"].cget("fg_color"),
            "o item anterior tem de apagar",
        )

    def test_tela_fora_do_registro_nao_acende_nada(self) -> None:
        self.navigator.subscribe(self.sidebar.highlight)
        self.navigator.go("club")
        self.sidebar.highlight("show_alguma_tela_de_detalhe")
        for botao in self.sidebar.items.values():
            self.assertEqual("transparent", botao.cget("fg_color"))

    # -- modo responsivo ---------------------------------------------------

    def test_rail_esconde_rotulos_e_mantem_os_itens(self) -> None:
        self.sidebar.set_mode(MODE_RAIL)
        self.root.update()
        self.assertEqual(MODE_RAIL, self.sidebar.mode)
        self.assertEqual("", self.sidebar.items["show_pairings"].cget("text"))
        self.assertTrue(
            self.sidebar.frame.winfo_ismapped(), "no rail a barra continua visivel"
        )

    def test_hidden_tira_a_barra_da_tela(self) -> None:
        self.sidebar.set_mode(MODE_HIDDEN)
        self.root.update()
        self.assertFalse(self.sidebar.frame.winfo_ismapped())

    def test_volta_de_hidden_para_full_restaura_rotulos(self) -> None:
        self.sidebar.set_mode(MODE_HIDDEN)
        self.root.update()
        self.sidebar.set_mode(MODE_FULL)
        self.root.update()
        self.assertTrue(self.sidebar.frame.winfo_ismapped())
        self.assertIn("Rodadas", self.sidebar.items["show_pairings"].cget("text"))

    def test_set_mode_repetido_e_inerte(self) -> None:
        self.sidebar.set_mode(MODE_RAIL)
        self.sidebar.set_mode(MODE_RAIL)
        self.assertEqual(MODE_RAIL, self.sidebar.mode)

    def test_destaque_sobrevive_a_troca_de_modo(self) -> None:
        self.navigator.subscribe(self.sidebar.highlight)
        self.navigator.go("pairings")
        self.sidebar.set_mode(MODE_RAIL)
        self.root.update()
        self.assertEqual("show_pairings", self.sidebar.active)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
