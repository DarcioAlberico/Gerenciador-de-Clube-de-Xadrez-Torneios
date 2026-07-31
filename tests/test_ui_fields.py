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
    FORM_TEXT_WIDTH,
    clear_field_error,
    date_field,
    field_has_error,
    labeled_field,
    select_field,
    set_field_error,
    set_field_warning,
    text_area,
    text_field,
)
from src.ui.theme import (
    THEME_ACCENT,
    THEME_DANGER,
    THEME_FIELD_BG,
    THEME_FIELD_BORDER,
    THEME_FIELD_TEXT,
    THEME_PANEL_BG,
    THEME_WARNING_TEXT,
)


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

    def test_labeled_field_une_rotulo_campo_e_linha_de_mensagem(self) -> None:
        box, campo = labeled_field(
            self.root, "Local", lambda parent: text_field(parent, placeholder="Clube")
        )
        rotulos = [w for w in box.winfo_children() if isinstance(w, ctk.CTkLabel)]
        # Rotulo (linha 0) + linha de mensagem reservada (linha 2).
        self.assertEqual(2, len(rotulos))
        self.assertEqual("Local", rotulos[0].cget("text"))
        self.assertIs(box, campo.master)
        self.assertEqual(1, int(campo.grid_info()["row"]))
        box.destroy()

    def test_ajuda_longa_quebra_em_vez_de_alargar_o_formulario(self) -> None:
        """TBK-03: o painel do formulário é rolável e cresce para caber o texto.

        Uma linha de apoio sem quebra alargava o formulário inteiro e empurrava
        os controles para fora da janela — foi o guarda de layout da B-8 que
        pegou. O teste compara com um texto curto: a caixa não pode ficar mais
        larga por causa da ajuda.
        """
        longa = (
            "FIDE (Gacrux) é o motor homologado e o padrão. O Albericus (próprio) "
            "é legado: não aplica o adversário virtual da FIDE em jogos não "
            "disputados, então não serve para publicar classificação oficial."
        )
        curta, _ = labeled_field(
            self.root, "Motor", lambda p: text_field(p, placeholder="x"), help_text="Curta."
        )
        comprida, _ = labeled_field(
            self.root, "Motor", lambda p: text_field(p, placeholder="x"), help_text=longa
        )
        self.root.update()
        self.assertLessEqual(
            comprida.winfo_reqwidth(),
            max(curta.winfo_reqwidth(), FORM_TEXT_WIDTH) + 4,
            "a ajuda longa alargou a caixa do campo",
        )
        dica = [w for w in comprida.winfo_children() if isinstance(w, ctk.CTkLabel)][-1]
        self.assertEqual(FORM_TEXT_WIDTH, int(dica.cget("wraplength")))
        curta.destroy()
        comprida.destroy()


@pytest.mark.gui
class EstadosDoCampoTest(unittest.TestCase):
    """F5.3 / P3-4: foco, erro, aviso e desabilitado — visíveis e distintos."""

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
        self.box, self.campo = labeled_field(
            self.root,
            "Rodadas",
            lambda parent: text_field(parent, placeholder="Ex.: 7"),
            help_text="Entre 1 e 30.",
        )
        # Mapeado de verdade: o Tk nao entrega evento de foco a widget que nao
        # esta na tela (mesma familia da pegadinha registrada na B-4).
        self.box.pack(fill="x")
        self.root.update()
        self.hint = [w for w in self.box.winfo_children() if isinstance(w, ctk.CTkLabel)][-1]

    def tearDown(self) -> None:
        try:
            self.box.destroy()
        except TclError:  # pragma: no cover
            pass

    def test_repouso_usa_a_borda_do_tema(self) -> None:
        self.assertEqual(list(THEME_FIELD_BORDER), list(self.campo.cget("border_color")))
        self.assertEqual(1, self.campo.cget("border_width"))

    def test_foco_desenha_anel_no_accent(self) -> None:
        """P3-4: antes não havia UM binding de <FocusIn> no app inteiro."""
        self.campo._entry.event_generate("<FocusIn>")
        self.root.update_idletasks()
        self.assertEqual(list(THEME_ACCENT), list(self.campo.cget("border_color")))
        self.assertEqual(2, self.campo.cget("border_width"))

        self.campo._entry.event_generate("<FocusOut>")
        self.root.update_idletasks()
        self.assertEqual(list(THEME_FIELD_BORDER), list(self.campo.cget("border_color")))

    def test_erro_pinta_a_borda_e_escreve_sob_o_campo(self) -> None:
        set_field_error(self.campo, "Informe um numero inteiro.")
        self.assertTrue(field_has_error(self.campo))
        self.assertEqual(list(THEME_DANGER), list(self.campo.cget("border_color")))
        self.assertEqual("Informe um numero inteiro.", self.hint.cget("text"))

    def test_foco_nao_apaga_o_erro(self) -> None:
        """A precedência que justifica a máquina de estados: erro > foco."""
        set_field_error(self.campo, "Invalido.")
        self.campo._entry.event_generate("<FocusIn>")
        self.root.update_idletasks()
        self.assertEqual(list(THEME_DANGER), list(self.campo.cget("border_color")))

    def test_limpar_devolve_a_dica_original(self) -> None:
        set_field_error(self.campo, "Invalido.")
        clear_field_error(self.campo)
        self.assertFalse(field_has_error(self.campo))
        self.assertEqual("Entre 1 e 30.", self.hint.cget("text"))
        self.assertEqual(list(THEME_FIELD_BORDER), list(self.campo.cget("border_color")))

    def test_aviso_e_distinto_de_erro_e_nao_bloqueia(self) -> None:
        set_field_warning(self.campo, "Rodadas demais para o campo atual.")
        self.assertFalse(field_has_error(self.campo), "aviso nao e erro")
        self.assertEqual(list(THEME_WARNING_TEXT), list(self.campo.cget("border_color")))
        self.assertEqual("Rodadas demais para o campo atual.", self.hint.cget("text"))

    def test_desabilitado_perde_o_fundo_de_campo(self) -> None:
        """P3-4: o CTkEntry desabilitado só esmaece o texto — era indistinguível."""
        self.campo.configure(state="disabled")
        self.assertEqual(list(THEME_PANEL_BG), list(self.campo.cget("fg_color")))
        self.campo.configure(state="normal")
        self.assertEqual(list(THEME_FIELD_BG), list(self.campo.cget("fg_color")))

    def test_erro_sobrevive_a_reabilitacao(self) -> None:
        set_field_error(self.campo, "Invalido.")
        self.campo.configure(state="disabled")
        self.campo.configure(state="normal")
        self.assertEqual(list(THEME_DANGER), list(self.campo.cget("border_color")))

    def test_campo_de_data_usa_o_estado_unico(self) -> None:
        """A MaskedDateEntry era uma das três cópias locais (F5.3)."""
        campo = date_field(self.root)
        campo.insert(0, "99/99/9999")
        campo._on_blur()
        self.assertTrue(field_has_error(campo))
        self.assertEqual(list(THEME_DANGER), list(campo.cget("border_color")))
        campo.destroy()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


@pytest.mark.gui
class EditorDeDesempatesTest(unittest.TestCase):
    """TBK-04: o editor de sequência devolve os parâmetros configurados."""

    @classmethod
    def setUpClass(cls) -> None:
        from tests.support.ctk_cleanup import create_tk_window

        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.geometry("600x400+60+60")
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

    def _editor(self, codes, params=None):
        from src.services.pairing import DEFAULT_PLAYER_TIEBREAKS, PLAYER_TIEBREAKS
        from src.ui.screens.tournament_widgets import TiebreakSequenceEditor

        editor = TiebreakSequenceEditor(
            self.root, PLAYER_TIEBREAKS, DEFAULT_PLAYER_TIEBREAKS, codes, params
        )
        self.addCleanup(editor.destroy)
        self.root.update()
        return editor

    def test_sequencia_sai_com_os_parametros_e_nao_mais_vazia(self) -> None:
        editor = self._editor(["buchholz_cut1", "koya"])
        sequencia = editor.get_sequence()
        self.assertEqual(["buchholz_cut1", "koya"], [item["code"] for item in sequencia])
        self.assertEqual(
            {"cut_low": 1, "cut_high": 0, "unplayed": "real"}, sequencia[0]["params"]
        )
        self.assertEqual({"threshold": 50}, sequencia[1]["params"])

    def test_parametro_salvo_reabre_no_editor(self) -> None:
        editor = self._editor(["koya"], {"koya": {"threshold": 70}})
        self.assertEqual(70, editor.get_sequence()[0]["params"]["threshold"])

    def test_reordenar_nao_apaga_o_parametro_digitado(self) -> None:
        """`_render` destrói e recria os widgets a cada movimento de linha."""
        editor = self._editor(["buchholz_cut1", "koya"])
        campo = editor._param_widgets[("koya", "threshold")]
        campo.delete(0, "end")
        campo.insert(0, "80")
        editor._move(1, -1)  # sobe o Koya, o que dispara o _render
        self.root.update()

        sequencia = editor.get_sequence()
        self.assertEqual("koya", sequencia[0]["code"], "a ordem mudou")
        self.assertEqual(80, sequencia[0]["params"]["threshold"], "o parametro se perdeu")

    def test_criterio_sem_parametro_nao_rende_campo(self) -> None:
        editor = self._editor(["sonneborn_berger"])
        self.assertEqual({}, editor.get_sequence()[0]["params"])
        self.assertEqual({}, editor._param_widgets)
