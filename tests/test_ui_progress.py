"""Véu de progresso local (``src/ui/components/progress.py`` — F5.9 / P3-11).

O que se cobra aqui é o que a barra de 6px da statusbar não dava: a espera
aparece **onde** a ação foi disparada, e o clique repetido não passa por ela.
O segundo ponto é o que fecha o bug do duplo clique disparando a operação duas
vezes — e é por isso que ele tem teste próprio, e não só inspeção visual.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components.progress import ProgressOverlay
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)

pytestmark = pytest.mark.gui


class ProgressOverlayTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
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
        self.painel = ctk.CTkFrame(self.root, width=300, height=200)
        self.painel.pack(fill="both", expand=True)
        self.addCleanup(self.painel.destroy)
        self.veu = ProgressOverlay(self.painel)
        self.addCleanup(self.veu.reset)
        self.root.update()

    def test_nasce_invisivel(self) -> None:
        self.assertFalse(self.veu.is_running)
        self.assertEqual(0, self.veu.active_count)

    def test_aparece_sobre_o_painel_da_acao(self) -> None:
        self.veu.start("Importando lista CBX...")
        self.root.update()
        self.assertTrue(self.veu.is_running)
        quadro = self.veu._frame
        self.assertIsNotNone(quadro)
        self.assertTrue(quadro.winfo_ismapped(), "o veu deveria estar visivel")
        self.assertIs(self.painel, quadro.master)

    def test_mostra_a_mensagem_da_tarefa(self) -> None:
        self.veu.start("Gerando lote multi-destino...")
        self.root.update()
        self.assertEqual("Gerando lote multi-destino...", self.veu._label.cget("text"))

    def test_o_botao_coberto_nao_recebe_mais_o_clique(self) -> None:
        """O ponto do véu (P3-11): o segundo clique acerta ele, não o botão.

        A garantia são **duas** propriedades, e o teste cobra as duas: o véu
        ocupa o alvo **inteiro** e fica **por cima**. O Tk entrega o evento ao
        widget mais ao topo sob o cursor, então as duas juntas bastam.

        Perguntar ``winfo_containing`` seria mais direto, e foi a primeira
        versão — mas ela depende de a janela estar visível na tela, e na suíte
        inteira o teste passava a depender de qual janela o sistema deixou por
        cima. ``winfo children`` devolve os filhos **em ordem de empilhamento**
        (o mais baixo primeiro), o que responde a mesma pergunta sem olhar para
        a tela.
        """
        botao = ctk.CTkButton(self.painel, text="Importar", command=lambda: None)
        botao.place(x=10, y=10)
        self.root.update()

        self.veu.start("Importando...")
        self.root.update()
        quadro = self.veu._frame

        self.assertEqual(
            (self.painel.winfo_width(), self.painel.winfo_height()),
            (quadro.winfo_width(), quadro.winfo_height()),
            "o veu precisa cobrir o painel inteiro",
        )
        empilhamento = list(self.painel.winfo_children())
        self.assertIs(quadro, empilhamento[-1], "o veu precisa ficar por cima")
        self.assertLess(empilhamento.index(botao), empilhamento.index(quadro))

    def test_duas_tarefas_mostram_um_veu_e_a_ultima_o_retira(self) -> None:
        # Mesma regra do BusyIndicator: start/stop em pares, e a primeira a
        # terminar nao pode apagar a espera da outra.
        self.veu.start("Primeira...")
        self.veu.start("Segunda...")
        self.root.update()
        self.assertEqual(2, self.veu.active_count)

        self.veu.stop()
        self.root.update()
        self.assertTrue(self.veu.is_running, "ainda ha tarefa rodando")
        self.assertTrue(self.veu._frame.winfo_ismapped())

        self.veu.stop()
        self.root.update()
        self.assertFalse(self.veu.is_running)
        self.assertFalse(self.veu._frame.winfo_ismapped())

    def test_stop_sem_start_nao_zera_contador_alheio(self) -> None:
        self.veu.start("Trabalhando...")
        self.veu.stop()
        self.veu.stop()  # extra: deve ser ignorado
        self.assertEqual(0, self.veu.active_count)

    def test_reset_retira_o_veu_mesmo_com_tarefas_penduradas(self) -> None:
        self.veu.start("A...")
        self.veu.start("B...")
        self.root.update()
        self.veu.reset()
        self.root.update()
        self.assertEqual(0, self.veu.active_count)
        self.assertFalse(self.veu._frame.winfo_ismapped())

    def test_reaparece_depois_de_escondido(self) -> None:
        # O quadro e reaproveitado entre tarefas; `place_forget` seguido de
        # `place` tem de devolve-lo a tela.
        self.veu.start("Uma vez...")
        self.veu.stop()
        self.root.update()
        self.veu.start("Outra vez...")
        self.root.update()
        self.assertTrue(self.veu._frame.winfo_ismapped())


class AlvoDoVeuTest(unittest.TestCase):
    """Qual painel o véu cobre — regra pequena, consequência grande.

    Não abre janela: a decisão é ``topo é a janela principal?``, e ela pode ser
    exercitada com dublês. Roda fora do ``gui`` de propósito.
    """

    class _Widget:
        def __init__(self, topo: object) -> None:
            self._topo = topo

        def winfo_toplevel(self) -> object:
            return self._topo

    class _App:
        content = "area-de-conteudo"

    def _alvo(self, widget: object) -> object:
        from src.ui.app import AlbericusApp

        app = self._App()
        return AlbericusApp._busy_target(app, widget)

    def test_sem_widget_cobre_a_area_de_conteudo(self) -> None:
        self.assertEqual("area-de-conteudo", self._alvo(None))

    def test_acao_disparada_da_janela_principal_cobre_o_conteudo(self) -> None:
        app = self._App()
        botao = self._Widget(app)
        from src.ui.app import AlbericusApp

        self.assertEqual("area-de-conteudo", AlbericusApp._busy_target(app, botao))

    def test_acao_disparada_de_um_modal_cobre_o_modal(self) -> None:
        # Cobrir a area de conteudo quando o clique veio de um dialogo deixaria
        # o dialogo livre para receber o segundo clique — que e exatamente o
        # que o veu existe para impedir.
        modal = object()
        self.assertIs(modal, self._alvo(self._Widget(modal)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
