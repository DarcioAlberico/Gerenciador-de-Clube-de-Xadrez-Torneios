"""RGS-06 / RGS-33 / RGS-12 — o campo de data (`MaskedDateEntry`).

Casos executados na spec (seção 1.2, passo 3), todos com o widget antigo:

- `2026-11-13 08:00` aparecia como `20/26/1113` e virava vazio;
- `2010/05/12` virava `0512-10-20` (corrompido);
- `1/2/2026` e `1985` viravam vazio.

E o calendário abria com a seta ↓, com `grab_set()` global: a janela passava a
ignorar cliques (RGS-12).

A posição do popup tem teste puro; o resto precisa de janela de verdade.
"""
from __future__ import annotations

import unittest
from datetime import date
from tkinter import TclError, Toplevel

import customtkinter as ctk
import pytest

from src.domain.dates import Ano, Data, DataInvalida, DataVazia
from src.ui.components.fields import field_has_error
from src.ui.support import clamp_popup_position


class PosicaoDoPopupTest(unittest.TestCase):
    """RGS-12: o popup fica dentro da tela (era `+0+0` no teste, e saía da
    borda em campo perto do rodapé)."""

    def test_cabe_abaixo_do_campo(self) -> None:
        self.assertEqual((100, 232), clamp_popup_position(100, 200, 30, 250, 260, 1920, 1080))

    def test_sem_espaco_abaixo_abre_acima(self) -> None:
        # Campo no rodapé: 1000 + 30 + 260 passa de 1080.
        self.assertEqual((100, 738), clamp_popup_position(100, 1000, 30, 250, 260, 1920, 1080))

    def test_borda_direita_puxa_para_dentro(self) -> None:
        self.assertEqual((1670, 232), clamp_popup_position(1800, 200, 30, 250, 260, 1920, 1080))

    def test_nunca_negativo(self) -> None:
        self.assertEqual((0, 0), clamp_popup_position(-50, 5, 30, 250, 2000, 1920, 1080))


@pytest.mark.gui
class CampoDeDataTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        from tests.support.ctk_cleanup import create_tk_window

        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.geometry("400x300+100+100")
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        from tests.support.ctk_cleanup import cancel_pending_callbacks, release_dead_ctk_windows

        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        from src.ui.support import MaskedDateEntry

        self.MaskedDateEntry = MaskedDateEntry
        self.campo = MaskedDateEntry(self.root)
        self.campo.pack()
        self.root.update()

    def tearDown(self) -> None:
        self.campo._close_calendar()
        self.campo.destroy()

    def _texto_na_tela(self, campo: object = None) -> str:
        alvo = campo or self.campo
        return str(alvo._entry.get())  # type: ignore[attr-defined]

    def _tecla(self, keysym: str, campo: object = None) -> None:
        alvo = (campo or self.campo)._entry  # type: ignore[attr-defined]
        alvo.focus_force()
        self.root.update()
        alvo.event_generate("<KeyPress>", keysym=keysym, when="now")
        self.root.update()

    def _popups(self) -> list[Toplevel]:
        encontrados: list[Toplevel] = []
        pendentes = list(self.root.winfo_children())
        while pendentes:
            widget = pendentes.pop()
            # Só o que está na tela: o tkcalendar cria um Toplevel de dica
            # (tooltip) recolhido dentro do próprio calendário.
            if isinstance(widget, Toplevel) and widget.winfo_ismapped():
                encontrados.append(widget)
            pendentes.extend(widget.winfo_children())
        return encontrados

    # -- RGS-06: insert com parse_date ----------------------------------
    def test_formatos_aceitos_viram_data_brasileira(self) -> None:
        casos = {
            "2010/05/12": ("12/05/2010", "2010-05-12"),
            "2026-11-13 08:00": ("13/11/2026", "2026-11-13"),
            "1/2/2026": ("01/02/2026", "2026-02-01"),
            "13/11/2026": ("13/11/2026", "2026-11-13"),
        }
        for gravado, (tela, iso) in casos.items():
            with self.subTest(gravado=gravado):
                self.campo.delete(0, "end")
                self.campo.insert(0, gravado)
                self.assertEqual(tela, self._texto_na_tela())
                self.assertEqual(iso, self.campo.get())
                self.assertEqual(Data(date.fromisoformat(iso)), self.campo.value())
                self.assertFalse(self.campo.has_invalid())
                self.assertFalse(field_has_error(self.campo))

    def test_valor_invalido_aparece_como_gravado_com_borda_de_erro(self) -> None:
        for gravado in ("2026-02-30", "13/11/26", "lixo"):
            with self.subTest(gravado=gravado):
                self.campo.delete(0, "end")
                self.campo.insert(0, gravado)
                self.assertEqual(gravado, self._texto_na_tela())
                self.assertTrue(self.campo.has_invalid())
                self.assertTrue(field_has_error(self.campo))
                self.assertIsInstance(self.campo.value(), DataInvalida)
                # O contrato do get() não muda: só devolve data válida.
                self.assertEqual("", self.campo.get())

    def test_ano_sozinho_sem_permissao_e_invalido(self) -> None:
        self.campo.insert(0, "1985")
        self.assertEqual("1985", self._texto_na_tela())
        self.assertTrue(self.campo.has_invalid())

    def test_vazio_e_valido(self) -> None:
        self.campo.insert(0, "")
        self.assertEqual(DataVazia(), self.campo.value())
        self.assertFalse(self.campo.has_invalid())
        self.assertEqual("", self.campo.get())

    def test_digitacao_incompleta_e_invalida(self) -> None:
        for tecla in "120520":
            self._tecla(tecla)
        self.assertEqual("12/05/20", self._texto_na_tela())
        self.assertTrue(self.campo.has_invalid())
        self.assertEqual("", self.campo.get())

    def test_digitar_sobre_valor_invalido_recomeca(self) -> None:
        self.campo.insert(0, "2026-02-30")
        self._tecla("1")
        self.assertEqual("1", self._texto_na_tela())
        self.campo.delete(0, "end")
        self.campo.insert(0, "lixo")
        self._tecla("BackSpace")
        self.assertEqual("", self._texto_na_tela())
        self.assertFalse(self.campo.has_invalid())

    # -- RGS-33: nascimento aceita só o ano ------------------------------
    def test_nascimento_mostra_o_ano(self) -> None:
        campo = self.MaskedDateEntry(self.root, permite_ano=True)
        try:
            campo.insert(0, "1985")
            self.assertEqual("1985", self._texto_na_tela(campo))
            self.assertEqual("1985", campo.get())
            self.assertEqual(Ano(1985), campo.value())
            self.assertFalse(campo.has_invalid())
            campo.delete(0, "end")
            campo.insert(0, "1985-03-07")
            self.assertEqual("1985-03-07", campo.get())
        finally:
            campo.destroy()

    # -- RGS-12: calendário ------------------------------------------------
    def test_seta_para_baixo_nao_abre_o_calendario(self) -> None:
        self._tecla("Down")
        self.assertEqual([], self._popups())
        self.assertIsNone(self.campo._cal_popup)

    def test_f4_abre_sem_grab_e_esc_fecha(self) -> None:
        self._tecla("F4")
        self.assertEqual(1, len(self._popups()))
        self.assertIsNone(self.root.grab_current())
        self.campo._cal_popup.event_generate("<Escape>", when="now")
        self.root.update()
        self.assertEqual([], self._popups())

    def test_alt_seta_abre(self) -> None:
        self.campo._entry.focus_force()
        self.root.update()
        self.campo._entry.event_generate("<Alt-KeyPress-Down>", when="now")
        self.root.update()
        self.assertEqual(1, len(self._popups()))

    def test_botao_visivel_abre(self) -> None:
        botao = self.campo.calendar_button
        self.assertTrue(botao.winfo_ismapped())
        botao.invoke()
        self.root.update()
        self.assertEqual(1, len(self._popups()))
        self.assertIsNone(self.root.grab_current())

    def test_clique_em_outro_campo_fecha(self) -> None:
        outro = ctk.CTkEntry(self.root)
        outro.pack()
        try:
            self._tecla("F4")
            self.assertEqual(1, len(self._popups()))
            outro._entry.focus_force()
            self.root.update()
            outro._entry.event_generate("<Button-1>", when="now")
            self.root.update()
            self.assertEqual([], self._popups())
        finally:
            outro.destroy()

    def test_clique_fora_sem_foco_fecha(self) -> None:
        rotulo = ctk.CTkLabel(self.root, text="fora")
        rotulo.pack()
        try:
            self._tecla("F4")
            rotulo._label.event_generate("<Button-1>", when="now")
            self.root.update()
            self.assertEqual([], self._popups())
        finally:
            rotulo.destroy()

    def test_escolher_dia_grava_e_fecha(self) -> None:
        self.campo.insert(0, "2026-11-13")
        self._tecla("F4")
        self.campo._calendar.selection_set(date(2026, 11, 20))
        self.campo._calendar.event_generate("<<CalendarSelected>>", when="now")
        self.root.update()
        self.assertEqual("2026-11-20", self.campo.get())
        self.assertEqual([], self._popups())


if __name__ == "__main__":
    unittest.main()
