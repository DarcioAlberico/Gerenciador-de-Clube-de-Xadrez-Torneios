"""Testes das factories de campo (``src/ui/components/fields.py`` — F5.2).

Duas famílias: contratos puros (escala fechada, alinhamento com os botões,
placeholder obrigatório — nada disso abre janela) e anatomia real dos widgets
(marcada ``gui``: precisa de display, como ``test_ui_busy.py``).
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components import buttons
from src.ui.components.fields import (
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
from src.ui.theme import THEME_FIELD_BG, THEME_FIELD_BORDER, THEME_FIELD_TEXT


class ContratosPurosTest(unittest.TestCase):
    def test_campo_e_botao_tem_a_mesma_altura(self) -> None:
        """O aceite da F5.2: campo e botão alinham na mesma linha. Se alguém
        mudar a altura de um dos lados, este teste aponta o outro."""
        self.assertEqual(buttons._DEFAULT_HEIGHT, FIELD_HEIGHT)

    def test_escala_de_larguras_e_fechada_e_crescente(self) -> None:
        self.assertEqual((120, 240, 360), (FIELD_SM, FIELD_MD, FIELD_LG))

    def test_placeholder_e_obrigatorio(self) -> None:
        """P3-6: campo de texto sem dica de formato não pode nem nascer."""
        with self.assertRaises(TypeError):
            text_field(object())  # type: ignore[call-arg]


@pytest.mark.gui
class AnatomiaDosCamposTest(unittest.TestCase):
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

    def test_text_field_nasce_com_a_anatomia_unica(self) -> None:
        campo = text_field(self.root, placeholder="Ex.: Aberto Primavera")
        self.assertEqual(FIELD_HEIGHT, campo.cget("height"))
        self.assertEqual(FIELD_MD, campo.cget("width"))
        self.assertEqual(FIELD_RADIUS, campo.cget("corner_radius"))
        self.assertEqual("Ex.: Aberto Primavera", campo.cget("placeholder_text"))
        campo.destroy()

    def test_select_field_tem_anatomia_de_campo_nao_de_botao(self) -> None:
        """P3-5: corpo no fundo de campo do tema (tokens vivos), não no accent."""
        campo = select_field(self.root, values=["1-0", "0-1"])
        self.assertEqual(list(THEME_FIELD_BG), list(campo.cget("fg_color")))
        self.assertEqual(list(THEME_FIELD_TEXT), list(campo.cget("text_color")))
        self.assertEqual(list(THEME_FIELD_BORDER), list(campo.cget("button_color")))
        self.assertEqual(FIELD_HEIGHT, campo.cget("height"))
        campo.destroy()

    def test_text_area_nasce_com_borda_visivel(self) -> None:
        """P3-5: o CTkTextbox de fábrica tem border_width=0 e some no painel."""
        area = text_area(self.root)
        self.assertEqual(1, area.cget("border_width"))
        # O cget do CTkTextbox nao repassa opcoes do tk.Text interno; o wrap
        # so e visivel perguntando ao proprio Text.
        self.assertEqual("word", str(area._textbox.cget("wrap")))
        area.destroy()

    def test_date_field_devolve_o_masked_date_entry_na_escala(self) -> None:
        from src.ui.support import MaskedDateEntry

        campo = date_field(self.root)
        self.assertIsInstance(campo, MaskedDateEntry)
        self.assertEqual(FIELD_SM, campo.cget("width"))
        self.assertEqual(FIELD_HEIGHT, campo.cget("height"))
        campo.destroy()

    def test_labeled_field_une_rotulo_e_campo(self) -> None:
        box, campo = labeled_field(
            self.root, "Local", lambda parent: text_field(parent, placeholder="Clube")
        )
        rotulos = [w for w in box.winfo_children() if isinstance(w, ctk.CTkLabel)]
        self.assertEqual(1, len(rotulos))
        self.assertEqual("Local", rotulos[0].cget("text"))
        self.assertIs(box, campo.master)
        self.assertEqual(1, int(campo.grid_info()["row"]))
        box.destroy()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
