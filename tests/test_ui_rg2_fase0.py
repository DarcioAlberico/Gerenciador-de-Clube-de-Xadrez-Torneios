"""Revisão Geral 2, Fase 0 — aceite de UI do hotfix.

- RG2-02: Enter na tabela de Rodadas grava **uma** mesa, não duas; a W.O.
  pergunta uma vez; em rodada fechada o diálogo "Corrigir resultado" abre uma
  vez. Uma varredura confere que nenhuma tecla da tabela deixa o evento subir
  até o atalho da tela.
- RG2-03: o tick da auto-atualização do painel do árbitro preserva a mesa
  selecionada, o foco e o texto da busca.

A base (`_RodadasBase`) é a dos testes de aceite da RGS-21/25: as ações são
teclas geradas, e o banco é conferido pelos eventos de auditoria.
"""
from __future__ import annotations

from unittest import mock

import pytest

from src.ui.screens.pairing_arbitration import pending
from src.ui.screens.pairing_results import correction
from tests.test_ui_rgs21_25_rodadas import _RodadasBase

pytestmark = pytest.mark.gui


class EnterGravaUmaMesaTest(_RodadasBase):
    """RG2-02 — o handler da tabela interrompe a propagação do evento."""

    JOGADORES = 8

    def test_enter_na_mesa_1_grava_so_a_mesa_1(self) -> None:
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self.app.result_option.set("1/2-1/2")
        antes = len(self._eventos("result_updated"))

        self._tecla("<Return>")

        self.assertEqual(1, len(self._eventos("result_updated")) - antes)
        resultados = [mesa["result"] for mesa in self._mesas()]
        self.assertEqual(["1/2-1/2", "", "", ""], resultados)

    def test_enter_com_wo_pergunta_uma_vez(self) -> None:
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self.app.result_option.set("1F-0F")

        with mock.patch.object(pending, "confirm_walkover", return_value=True) as confirmar:
            self._tecla("<Return>")

        self.assertEqual(1, confirmar.call_count)
        self.assertEqual("", self._mesas()[1]["result"])

    def test_varredura_nenhuma_tecla_da_tabela_sobe_ate_a_tela(self) -> None:
        """Toda sequência ligada na tabela **e** na tela para na tabela.

        O atalho da tela pergunta `_pairing_shortcuts_active()` antes de
        gravar; se a pergunta acontece, o evento escapou da tabela.
        """
        self._abrir_rodadas()
        tree = self.app.pairing_tree
        da_tabela = set(tree.bind())
        da_tela = set(self.app.bind())
        compartilhadas = sorted(da_tabela & da_tela)
        self.assertIn("<Key-Return>", compartilhadas)

        escaparam = []
        for sequencia in compartilhadas:
            self._selecionar_mesa(0)
            with (
                mock.patch.object(pending, "confirm_walkover", return_value=False),
                mock.patch.object(self.app, "_pairing_shortcuts_active", return_value=False) as tela,
            ):
                self._tecla(sequencia)
            if tela.called:
                escaparam.append(sequencia)

        self.assertEqual([], escaparam)


class AutoAtualizacaoPreservaOArbitroTest(_RodadasBase):
    """RG2-03 — o tick não muda a mesa-alvo nem rouba o foco."""

    JOGADORES = 8

    def _painel(self) -> None:
        self.app.show_arbitration_panel()
        self.app.update()
        self.app.focus_force()
        self.app.update()

    def _tick(self) -> None:
        self.app._arbitration_auto_refresh()._tick()
        self.app.update()

    def _mesa_selecionada(self) -> int:
        tabela = self.app.arbitration_pending_tree
        return int(self.app.arbitration_pending_row_map[tabela.selection()[0]])

    def test_tick_mantem_a_mesa_selecionada_e_o_foco_na_tabela(self) -> None:
        self._painel()
        tabela = self.app.arbitration_pending_tree
        terceira = tabela.get_children()[2]
        tabela.selection_set(terceira)
        tabela.focus(terceira)
        tabela.focus_set()
        self.app.update()
        alvo = self._mesa_selecionada()

        self._tick()

        self.assertIsNot(tabela, self.app.arbitration_pending_tree, "o tick não remontou")
        self.assertEqual(alvo, self._mesa_selecionada())
        self.assertEqual(self.app.arbitration_pending_tree, self.app.focus_get())

    def test_tick_com_foco_na_busca_nao_tira_o_foco_nem_o_texto(self) -> None:
        self._painel()
        busca = self.app.arbitration_pending_query_entry
        busca.insert(0, "15")
        busca._entry.focus_set()
        self.app.update()

        self._tick()

        foco = self.app.focus_get()
        self.assertEqual(busca._entry, foco)
        self.assertEqual("15", self.app.arbitration_pending_query_entry.get())
        foco.event_generate("<Key-1>")
        self.app.update()
        self.assertEqual(["", "", "", ""], [mesa["result"] for mesa in self._mesas()])

    def test_tick_com_dialogo_aberto_espera_e_reagenda(self) -> None:
        self._painel()
        tabela = self.app.arbitration_pending_tree
        visto: dict[str, object] = {}

        def no_dialogo(dialogo: object) -> None:
            self._tick()
            visto["mesma_tabela"] = self.app.arbitration_pending_tree is tabela
            visto["reagendado"] = self.app._arbitration_refresh_job is not None
            dialogo.close()  # type: ignore[attr-defined]

        self._quando_abrir(no_dialogo)
        self.app._arbitration_panel_view().pending.correct_selected()

        self.assertEqual({"mesma_tabela": True, "reagendado": True}, visto)

    def test_tick_guarda_rascunho_da_busca_quando_o_foco_esta_fora_dela(self) -> None:
        self._painel()
        self.app.arbitration_pending_query_entry.insert(0, "Jog")
        self.app.arbitration_pending_tree.focus_set()
        self.app.update()

        self._tick()

        self.assertEqual("Jog", self.app.arbitration_pending_query_entry.get())

    def test_tick_sem_foco_na_tabela_nao_chama_focus_set(self) -> None:
        self._painel()
        self.app.arbitration_pending_tree.focus_set()
        self.app.update()
        self.app.arbitration_pending_tree.selection_set(())
        self.app.focus_set()  # o foco sai da tabela: fica na janela
        self.app.update()

        with mock.patch("tkinter.Misc.focus_set") as focar:
            self._tick()

        self.assertFalse(focar.called)


class EnterEmRodadaFechadaTest(_RodadasBase):
    """RG2-02 — o diálogo de correção abre uma vez só."""

    def test_enter_em_rodada_fechada_abre_um_dialogo(self) -> None:
        for mesa in self._mesas():
            self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.servico.close_round(self.tournament_id, self.round_id)
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self.app.result_option.set("0-1")

        with mock.patch.object(correction, "correction_dialog", return_value=None) as dialogo:
            self._tecla("<Return>")

        self.assertEqual(1, dialogo.call_count)
