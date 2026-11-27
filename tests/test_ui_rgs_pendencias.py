"""Pendências de tela da revisão geral do suíço (fases 0–4).

- RGS-21: o Ctrl+Z desfaz o último lançamento com o foco em **qualquer lugar**
  da tela de Rodadas — menos numa caixa de texto, onde o Ctrl+Z é do campo —
  e não sobrevive à tela.
- RGS-25: "Fechar rodada" do painel de arbitragem passa pela **mesma**
  confirmação da tela de Rodadas (checklist; Esc não fecha; item reprovado vai
  para a faixa de regra).
"""
from __future__ import annotations

from typing import Any
from unittest import mock

import customtkinter as ctk
import pytest

from tests.test_ui_rgs21_25_rodadas import _botao, _RodadasBase, _textos

pytestmark = pytest.mark.gui


class _Pendencias(_RodadasBase):
    def _tecla_em(self, widget: Any, sequencia: str) -> None:
        self.app.focus_force()
        widget.focus_set()
        self.app.update()
        widget.event_generate(sequencia)
        self.app.update()

    def _lancar_1_0_na_primeira_mesa(self) -> int:
        self._abrir_rodadas()
        mesa = self._mesas()[0]
        self._selecionar_mesa(0)
        self._tecla("1")
        self.assertEqual("1-0", self.db.get_pairing(int(mesa["id"]))["result"])
        return int(mesa["id"])


class CtrlZNaTelaDeRodadasTest(_Pendencias):
    def test_ctrl_z_com_o_foco_fora_da_tabela_desfaz(self) -> None:
        mesa = self._lancar_1_0_na_primeira_mesa()
        fora_da_tabela = self.app._round_progress_label
        self._tecla_em(fora_da_tabela, "<Control-z>")
        self.assertEqual("", self.db.get_pairing(mesa)["result"])
        self.assertEqual(2, len(self._eventos("result_updated")))

    def test_ctrl_z_na_tabela_continua_desfazendo_uma_vez_so(self) -> None:
        mesa = self._lancar_1_0_na_primeira_mesa()
        self._tecla("<Control-z>")
        self._tecla("<Control-z>")
        self.assertEqual("", self.db.get_pairing(mesa)["result"])
        self.assertEqual(2, len(self._eventos("result_updated")))

    def test_ctrl_z_numa_caixa_de_texto_e_do_campo(self) -> None:
        mesa = self._lancar_1_0_na_primeira_mesa()
        campo = ctk.CTkEntry(self.app.content)
        campo.grid(row=9, column=0)
        caixa = ctk.CTkTextbox(self.app.content, undo=True)
        caixa.grid(row=10, column=0)
        self.app.update()
        self._tecla_em(campo._entry, "<Control-z>")
        self._tecla_em(caixa._textbox, "<Control-z>")
        self.assertEqual("1-0", self.db.get_pairing(mesa)["result"])
        self.assertEqual(1, len(self._eventos("result_updated")))

    def test_ctrl_z_nao_vaza_para_outra_tela(self) -> None:
        mesa = self._lancar_1_0_na_primeira_mesa()
        self.app.show_standings()
        self.app.update()
        self._tecla_em(self.app.content, "<Control-z>")
        self.assertEqual("1-0", self.db.get_pairing(mesa)["result"])
        # A ligação morreu com a tela: nada de Ctrl+Z sobrando na janela.
        self.assertEqual("", str(self.app.bind("<Control-z>")).strip())

    def test_teclas_de_resultado_numa_caixa_de_texto_sao_do_campo(self) -> None:
        # "1", "0", "-", BackSpace e Enter ligados na janela não podem lançar
        # nem apagar o resultado da mesa selecionada enquanto se digita.
        mesa = self._lancar_1_0_na_primeira_mesa()
        campo = ctk.CTkEntry(self.app.content)
        campo.grid(row=9, column=0)
        self.app.update()
        for tecla in ("0", "-", "<BackSpace>", "<Delete>", "<Return>"):
            self._tecla_em(campo._entry, tecla)
        self.assertEqual("1-0", self.db.get_pairing(mesa)["result"])
        self.assertEqual(1, len(self._eventos("result_updated")))

    def test_reabrir_a_tela_nao_duplica_o_desfazer(self) -> None:
        self._abrir_rodadas()
        mesa = self._lancar_1_0_na_primeira_mesa()
        self._tecla_em(self.app._round_progress_label, "<Control-z>")
        self.assertEqual("", self.db.get_pairing(mesa)["result"])
        self.assertEqual(2, len(self._eventos("result_updated")))


class FecharRodadaNoPainelTest(_Pendencias):
    def _modal(self) -> ctk.CTkToplevel:
        # O painel tem tooltips (também CTkToplevel): o diálogo é o que tem "Voltar".
        abertos = [
            w for w in self.app.winfo_children()
            if isinstance(w, ctk.CTkToplevel) and w.winfo_exists() and _botao(w, "Voltar") is not None
        ]
        self.assertTrue(abertos, "nenhuma confirmação aberta")
        return abertos[-1]

    def _lancar_todas(self) -> None:
        for mesa in self._mesas():
            self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")

    def _botao_fechar_do_painel(self) -> ctk.CTkButton:
        self.app.show_arbitration_panel()
        self.app.update()
        botao = _botao(self.app.content, "Fechar rodada")
        self.assertIsNotNone(botao, "o painel devia ter a ação rápida 'Fechar rodada'")
        return botao

    def test_pede_a_mesma_confirmacao_e_esc_nao_fecha(self) -> None:
        self._lancar_todas()
        self._abrir_rodadas()
        vistos: list[str] = []

        def esc(dialogo: Any) -> None:
            vistos.append(_textos(dialogo))
            dialogo.focus_force()
            dialogo.update()
            dialogo.event_generate("<Escape>")

        botao = self._botao_fechar_do_painel()
        self._quando_abrir(esc)
        botao.invoke()
        self.app.update()
        self.assertEqual("generated", self.db.get_round(self.round_id)["status"])
        self.assertTrue(vistos, "o painel fechou sem confirmar")
        self.assertIn("Resultados lançados (3/3)", vistos[0])

        def voltar(dialogo: Any) -> None:
            _botao(dialogo, "Voltar").invoke()

        botao = self._botao_fechar_do_painel()
        self._quando_abrir(voltar)
        botao.invoke()
        self.app.update()
        self.assertEqual("generated", self.db.get_round(self.round_id)["status"])

        def confirmar(dialogo: Any) -> None:
            _botao(dialogo, "Fechar rodada 1").invoke()

        botao = self._botao_fechar_do_painel()
        self._quando_abrir(confirmar)
        botao.invoke()
        self.app.update()
        self.assertEqual("closed", self.db.get_round(self.round_id)["status"])
        self.assertEqual(1, len(self._eventos("round_closed")))
        self.assertIsNone(self.app.rule_banner.current)

    def test_item_reprovado_vai_para_a_faixa_sem_confirmacao(self) -> None:
        self._lancar_todas()
        itens = [
            {"label": "Resultados lançados (3/3)", "ok": True, "action": "pending_results"},
            {"label": "Sem resultados QR aguardando aprovação", "ok": False, "action": "qr_pending"},
        ]
        botao = self._botao_fechar_do_painel()
        with mock.patch.object(self.app.pairing_service, "closing_checklist", return_value=itens), \
                mock.patch("src.ui.components.dialogs.confirm_dialog") as pergunta:
            botao.invoke()
            self.app.update()
        pergunta.assert_not_called()
        faixa = self.app.rule_banner.current
        self.assertIsNotNone(faixa)
        self.assertIn("Sem resultados QR aguardando aprovação", _textos(faixa))
        self.assertEqual("generated", self.db.get_round(self.round_id)["status"])


class ChecklistDoPainelEUmPassoSoTest(_Pendencias):
    """O "Checklist" do painel já é a confirmação: fechar por ele não pergunta de novo.

    Antes, o "Fechar rodada" do checklist abria a confirmação da tela de
    Rodadas com a mesma lista — dois diálogos seguidos para um gesto só.
    """

    def _lancar_todas(self) -> None:
        for mesa in self._mesas():
            self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")

    def _checklist(self) -> ctk.CTkToplevel:
        self.app.show_arbitration_panel()
        self.app.update()
        dialogo = self.app._open_closing_checklist_dialog()
        self.assertIsNotNone(dialogo)
        self.app.update()
        return dialogo

    def test_fechar_pelo_checklist_nao_abre_segunda_confirmacao(self) -> None:
        self._lancar_todas()
        dialogo = self._checklist()
        self.assertIn("trava os resultados", _textos(dialogo))
        with mock.patch("src.ui.components.dialogs.confirm_dialog") as pergunta:
            _botao(dialogo, "Fechar rodada").invoke()
            self.app.update()
        pergunta.assert_not_called()
        self.assertEqual("closed", self.db.get_round(self.round_id)["status"])
        self.assertEqual(1, len(self._eventos("round_closed")))

    def test_checklist_com_pendencia_nao_deixa_fechar(self) -> None:
        dialogo = self._checklist()
        self.assertEqual("disabled", _botao(dialogo, "Fechar rodada").cget("state"))


del _RodadasBase  # a base não tem teste próprio: não coletar duas vezes
