"""Formulário canônico: ritmo puro + pilha sobre o grid (F5.4 / P3-12).

Dois blocos com propósitos diferentes. O primeiro exercita
[`form_layout`](../src/ui/form_layout.py) **sem abrir janela** — é a parte que
decide espaço, e o teste dela é aritmética. O segundo abre uma janela de
verdade, porque o que a ``FormStack`` promete só existe no grid: linha que
avança sozinha, rótulo acima do campo, seção separando grupos.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components.fields import (
    FIELD_HEIGHT,
    field_has_error,
    set_field_error,
)
from src.ui.components.form import FormStack, form_of
from src.ui.form_layout import (
    FORM_PADX,
    FORM_PANEL_WIDTH,
    field_gap,
    panel_padding,
    row_padding,
    section_gap,
)
from src.ui.screens.tournament_players.state import PLAYER_FIELDS, PLAYER_SECTIONS
from src.ui.theme import THEME_FIELD_BG


class RitmoVerticalTest(unittest.TestCase):
    """A parte pura: quanto respiro cada tipo de linha recebe."""

    def test_primeira_linha_nao_ganha_respiro_de_cima(self) -> None:
        # Margem dupla no topo e o defeito classico de empilhar sem olhar a
        # posicao: o painel ja tem a sua, somar a do campo dobraria so ali.
        topo, _base = row_padding("field", first=True)
        self.assertEqual(0, topo)

    def test_secao_abre_mais_que_campo(self) -> None:
        # E essa diferenca — nao regua, nao cor — que faz o grupo ser lido
        # como grupo. Se as duas fossem iguais, a secao viraria so um rotulo
        # em negrito no meio da coluna.
        topo_secao, _ = row_padding("section")
        topo_campo, _ = row_padding("field")
        self.assertGreater(topo_secao, topo_campo)
        self.assertEqual(section_gap(), topo_secao)
        self.assertEqual(field_gap(), topo_campo)

    def test_campo_nao_tem_base_porque_a_mensagem_e_o_rodape(self) -> None:
        # O labeled_field reserva a linha de mensagem de erro sob o campo;
        # somar pady embaixo empurraria a mensagem para longe do campo dela.
        _topo, base = row_padding("field")
        self.assertEqual(0, base)

    def test_largura_de_painel_e_uma_so(self) -> None:
        self.assertEqual(300, FORM_PANEL_WIDTH)
        self.assertEqual((FORM_PADX, 12), panel_padding())

    def test_todo_tipo_de_linha_tem_regra(self) -> None:
        for kind in ("field", "section", "widget", "note"):
            with self.subTest(kind=kind):
                topo, base = row_padding(kind)  # type: ignore[arg-type]
                self.assertGreaterEqual(topo, 0)
                self.assertGreaterEqual(base, 0)


class SecoesDeJogadoresTest(unittest.TestCase):
    """O agrupamento do cadastro é dado puro — e precisa cobrir tudo."""

    def test_secoes_cobrem_exatamente_os_campos_do_cadastro(self) -> None:
        # Campo fora de secao seria campo que some da tela: a montagem
        # percorre as SECOES, nao a lista de campos.
        agrupados = [chave for _titulo, campos in PLAYER_SECTIONS for chave in campos]
        self.assertEqual(sorted(PLAYER_FIELDS), sorted(agrupados))
        self.assertEqual(len(agrupados), len(set(agrupados)), "campo repetido em duas secoes")


def _topo(widget: object) -> int:
    """``pady`` de cima de um widget já posicionado. O Tk devolve ``(24, 4)``
    como tupla ou como string dependendo da versão — normalizamos aqui."""
    pady = widget.grid_info()["pady"]  # type: ignore[attr-defined]
    if isinstance(pady, (tuple, list)):
        return int(pady[0])
    texto = str(pady).strip("() ")
    return int(texto.split(",")[0].split(" ")[0])


@pytest.mark.gui
class FormStackTest(unittest.TestCase):
    """A pilha sobre o grid — o que só a janela real prova."""

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
        self.painel = ctk.CTkFrame(self.root)
        self.addCleanup(self.painel.destroy)

    def test_linhas_avancam_sozinhas_e_nao_se_sobrepoem(self) -> None:
        # O bug que a aritmetica manual causou de verdade na tela de
        # Jogadores: tres botoes empilhados POR CIMA dos seletores, na mesma
        # celula, porque a soma de linhas errou por tres.
        pilha = FormStack(self.painel)
        pilha.section("Grupo")
        a = pilha.text("Campo A", placeholder="a")
        b = pilha.text("Campo B", placeholder="b")
        linhas = [int(w.master.grid_info()["row"]) for w in (a, b)]
        self.assertEqual(len(set(linhas)), 2, "dois campos na mesma linha")
        self.assertLess(linhas[0], linhas[1])

    def test_rotulo_fica_acima_do_campo_na_mesma_caixa(self) -> None:
        pilha = FormStack(self.painel)
        campo = pilha.text("Nome", placeholder="Ex.: Ana")
        caixa = campo.master
        rotulo = [w for w in caixa.winfo_children() if isinstance(w, ctk.CTkLabel)][0]
        self.assertEqual(0, int(rotulo.grid_info()["row"]))
        self.assertEqual(1, int(campo.grid_info()["row"]))

    def test_secao_recebe_mais_respiro_que_campo_no_grid(self) -> None:
        pilha = FormStack(self.painel)
        pilha.text("Primeiro", placeholder="x")
        campo = pilha.text("Segundo", placeholder="y")
        titulo = pilha.section("Depois")
        self.assertGreater(_topo(titulo), _topo(campo.master))

    def test_form_of_devolve_a_mesma_pilha(self) -> None:
        # Duas pilhas sobre o mesmo grid e como o formulario se desalinha
        # calado: cada uma acha que a proxima linha e a 0.
        pilha = FormStack(self.painel)
        self.assertIs(pilha, form_of(self.painel))
        pilha.text("Campo", placeholder="x")
        self.assertEqual(pilha.row, form_of(self.painel).row)

    def test_campos_nascem_com_a_anatomia_da_f52(self) -> None:
        pilha = FormStack(self.painel)
        campo = pilha.text("Ritmo", placeholder="Ex.: 90'+30\"")
        self.assertEqual(FIELD_HEIGHT, campo.cget("height"))
        self.assertEqual("Ex.: 90'+30\"", campo.cget("placeholder_text"))
        # E a linha de mensagem da F5.3 esta ligada: o erro escreve sob o campo.
        set_field_error(campo, "Formato invalido.")
        self.assertTrue(field_has_error(campo))
        mensagens = [
            w.cget("text")
            for w in campo.master.winfo_children()
            if isinstance(w, ctk.CTkLabel)
        ]
        self.assertIn("Formato invalido.", mensagens)

    def test_select_usa_anatomia_de_campo(self) -> None:
        pilha = FormStack(self.painel)
        seletor = pilha.select("Escopo", ["A", "B"])
        self.assertEqual(list(THEME_FIELD_BG), list(seletor.cget("fg_color")))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
