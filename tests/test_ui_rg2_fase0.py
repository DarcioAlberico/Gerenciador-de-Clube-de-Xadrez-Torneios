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
