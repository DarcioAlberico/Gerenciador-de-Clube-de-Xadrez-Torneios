"""Testes da reestilização sem rebuild (``src/ui/restyle.py``).

O que precisa ficar protegido: quem seguia o padrão do tema **acompanha** a
troca, quem tem cor própria (um botão de perigo) **não é repintado por cima**, e
nenhum widget é recriado no caminho.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components.buttons import danger_button
from src.ui.restyle import COLOR_OPTIONS, restyle, snapshot_defaults
from src.ui.theme import (
    THEME_DANGER,
    THEME_PANEL_BG,
    apply_accent_preset,
    apply_bg_preset,
    apply_frame_bg_preset,
)
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)

# Esta suite abre janela: precisa de display real. Ver o marcador 'gui'
# no pyproject — o gate sem display roda com -m 'not gui'.
pytestmark = pytest.mark.gui

def cor_desenhada(widget) -> str:
    """Cor efetivamente pintada — cget diria o que foi pedido, não o que apareceu."""
    caminhos = widget.tk.splitlist(widget.tk.call("winfo", "children", str(widget)))
    for caminho in caminhos:
        filho = widget.nametowidget(caminho)
        if type(filho).__name__ == "CTkCanvas":
            for item in filho.find_all():
                fill = filho.itemcget(item, "fill")
                if fill:
                    return fill
    return ""


class RestyleTest(unittest.TestCase):
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
        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        self.painel = ctk.CTkFrame(self.root, fg_color=THEME_PANEL_BG)
        self.painel.pack(fill="both", expand=True, padx=10, pady=10)
        self.botao_tema = ctk.CTkButton(self.painel, text="Segue o tema")
        self.botao_tema.pack(pady=6)
        self.botao_perigo = danger_button(self.painel, "Excluir", lambda: None)
        self.botao_perigo.pack(pady=6)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.painel.destroy()
        except TclError:  # pragma: no cover
            pass
        # devolve o tema ao padrao: os tokens sao globais do processo
        apply_accent_preset("blue")
        apply_bg_preset("slate")
        apply_frame_bg_preset("slate")
        self.root.update()

    def test_token_mutado_e_repintado(self) -> None:
        antes = snapshot_defaults()
        apply_frame_bg_preset("carbon")
        restyle(self.root, antes)
        self.root.update()
        self.assertEqual(THEME_PANEL_BG[0], cor_desenhada(self.painel))

    def test_quem_seguia_o_tema_acompanha_o_accent(self) -> None:
        anterior = cor_desenhada(self.botao_tema)
        antes = snapshot_defaults()
        apply_accent_preset("emerald")
        restyle(self.root, antes)
        self.root.update()
        atual = cor_desenhada(self.botao_tema)
        self.assertNotEqual(anterior, atual)
        self.assertEqual(ctk.ThemeManager.theme["CTkButton"]["fg_color"][0], atual)

    def test_cor_propria_nao_e_atropelada(self) -> None:
        """O botão de perigo tem de continuar vermelho depois da troca."""
        antes = snapshot_defaults()
        apply_accent_preset("emerald")
        restyle(self.root, antes)
        self.root.update()
        self.assertEqual(THEME_DANGER[0], cor_desenhada(self.botao_perigo))

    def test_nada_e_recriado(self) -> None:
        identidades = (id(self.painel), id(self.botao_tema), id(self.botao_perigo))
        antes = snapshot_defaults()
        apply_accent_preset("violet")
        restyle(self.root, antes)
        self.root.update()
        self.assertEqual(
            identidades, (id(self.painel), id(self.botao_tema), id(self.botao_perigo))
        )
        self.assertTrue(self.painel.winfo_exists())

    def test_conteudo_de_entrada_sobrevive(self) -> None:
        entrada = ctk.CTkEntry(self.painel)
        entrada.pack()
        entrada.insert(0, "nao pode sumir")
        self.root.update()
        restyle(self.root, snapshot_defaults())
        self.root.update()
        self.assertEqual("nao pode sumir", entrada.get())

    def test_devolve_a_contagem_de_widgets_tocados(self) -> None:
        tocados = restyle(self.root, snapshot_defaults())
        self.assertGreaterEqual(tocados, 3, "raiz, painel e botoes ao menos")

    def test_sem_retrato_anterior_apenas_repinta(self) -> None:
        """Sem o retrato, ninguém 'seguia o padrão antigo': só repinta."""
        apply_accent_preset("emerald")
        anterior = cor_desenhada(self.botao_tema)
        restyle(self.root)  # sem previous_defaults
        self.root.update()
        self.assertEqual(anterior, cor_desenhada(self.botao_tema))

    def test_widget_destruido_no_meio_nao_derruba(self) -> None:
        orfao = ctk.CTkButton(self.painel, text="vai morrer")
        orfao.pack()
        self.root.update()
        orfao.destroy()
        self.assertGreater(restyle(self.root, snapshot_defaults()), 0)

    def test_catalogo_cobre_as_classes_usadas_no_app(self) -> None:
        for classe in ("CTkFrame", "CTkButton", "CTkLabel", "CTkEntry",
                       "CTkOptionMenu", "CTkProgressBar", "CTkScrollableFrame"):
            self.assertIn(classe, COLOR_OPTIONS)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
