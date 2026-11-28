"""Fase 2 — Rodadas, aceite de UI (RGS-21, RGS-25) e caracterização da §8 item 10.

Cada teste conta as **ações** do árbitro (tecla gerada, ``invoke`` de botão) e
confere o banco pelos eventos de auditoria, como pede a ESPEC §5:

- §8 item 10 (sólido, caracterização ANTES de mexer): lançamento por teclado,
  confirmação de W.O. que nomeia mesa e jogadores, aviso de edição de BYE e
  geração em segundo plano.
- RGS-21: toast "Mesa 1 → 1-0" com Desfazer (Ctrl+Z); desfazer devolve o
  resultado anterior e audita (2 eventos); contador "N/M lançadas"; teclas
  ``w``/``p``/``a`` com a mesma confirmação de W.O. do painel.
- RGS-25: botão primário em três estados — "Lançar resultados (N/M)" →
  "Fechar rodada N" (confirmação com as pendências; Esc não fecha) →
  "Gerar rodada N+1".

Os diálogos do app são bloqueantes (``wait_window``): a interação é agendada
com ``after`` antes de abrir, como em ``test_ui_rgs26_20_34_arbitro``.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from tkinter import TclError
from typing import Any, Callable
from unittest import mock

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import PairingService, TournamentService
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)
from tests.support.login import entrar_como_admin

pytestmark = pytest.mark.gui


def _walk(widget: Any) -> list[Any]:
    filhos = list(widget.winfo_children())
    for filho in list(filhos):
        filhos.extend(_walk(filho))
    return filhos


def _botao(widget: Any, texto: str) -> ctk.CTkButton | None:
    for filho in _walk(widget):
        if isinstance(filho, ctk.CTkButton) and filho.cget("text") == texto:
            return filho
    return None


def _textos(widget: Any) -> str:
    return "\n".join(
        str(filho.cget("text"))
        for filho in _walk(widget)
        if isinstance(filho, (ctk.CTkLabel, ctk.CTkButton))
    )


class _RodadasBase(unittest.TestCase):
    """Torneio de 6 jogadores, 3 rodadas; a R1 gerada e sem resultados."""

    JOGADORES = 6
    RODADAS = "3"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Rodadas", "rounds_count": self.RODADAS, "bye_points": "1"}
        )
        for indice in range(self.JOGADORES):
            self.db.create_player(
                self.tournament_id, name=f"Jogador {indice + 1}", rating=2000 - indice * 40
            )
        self.servico = PairingService(self.db)
        self.round_id = int(self.servico.generate_next_round(self.tournament_id)["id"])

        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.current_tournament_id = self.tournament_id
        entrar_como_admin(self.app.security_service)
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()
        self.app.geometry("1400x900+0+0")
        self.app._run_background = self._run_now
        self._agendados: list[str] = []
        self._falha: BaseException | None = None
        self.app.update()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            for job in self._agendados:
                try:
                    self.app.after_cancel(job)
                except Exception:
                    pass
            cancel_pending_callbacks(self.app)
            self.app.destroy()
            release_dead_ctk_windows()
        self.temp_dir.cleanup()
        if self._falha is not None:
            raise AssertionError(f"acao agendada falhou: {self._falha!r}") from self._falha

    @staticmethod
    def _run_now(task: Callable[[], Any], on_success: Callable[[Any], None] | None = None, **_kw: Any) -> None:
        resultado = task()
        if on_success is not None:
            on_success(resultado)

    # -- utilitários --------------------------------------------------------

    def _eventos(self, acao: str) -> list[dict[str, Any]]:
        return self.db.list_audit_events(self.tournament_id, action=acao, limit=100)

    def _modal(self) -> ctk.CTkToplevel:
        abertos = [
            w for w in self.app.winfo_children()
            if isinstance(w, ctk.CTkToplevel) and w.winfo_exists()
        ]
        self.assertTrue(abertos, "nenhum diálogo aberto")
        return abertos[-1]

    def _quando_abrir(self, acao: Callable[[ctk.CTkToplevel], None], delay: int = 300) -> None:
        def executar() -> None:
            dialogo = None
            try:
                dialogo = self._modal()
                acao(dialogo)
            except BaseException as exc:  # noqa: BLE001 - relançado no tearDown
                self._falha = exc
                if dialogo is not None:
                    try:
                        dialogo.destroy()
                    except Exception:
                        pass

        self._agendados.append(self.app.after(delay, executar))

    def _abrir_rodadas(self) -> None:
        self.app.show_pairings()
        self.app.update()

    def _selecionar_mesa(self, indice: int = 0) -> str:
        item = self.app.pairing_tree.get_children()[indice]
        self.app.pairing_tree.selection_set(item)
        self.app.pairing_tree.focus(item)
        self.app.pairing_tree.focus_set()
        self.app.update()
        return item

    def _tecla(self, sequencia: str) -> None:
        tree = self.app.pairing_tree
        self.app.focus_force()
        tree.focus_set()
        self.app.update()
        tree.event_generate(sequencia)
        self.app.update()

    def _mesas(self) -> list[dict[str, Any]]:
        return self.db.get_pairings_for_round(self.round_id)


class LancamentoPorTecladoCaracterizacaoTest(_RodadasBase):
    """§8 item 10 — o que já funciona e não pode mudar."""

    def test_tecla_1_lanca_e_avanca_para_a_mesa_seguinte(self) -> None:
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self._tecla("1")

        self.assertEqual("1-0", self._mesas()[0]["result"])
        filhos = self.app.pairing_tree.get_children()
        self.assertEqual(filhos[1], self.app.pairing_tree.selection()[0])

    def test_confirmacao_de_wo_no_painel_nomeia_mesa_e_jogadores(self) -> None:
        mesa = self._mesas()[0]
        self.app.show_arbitration_panel()
        self.app.update()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False) as pergunta:
            self.app._save_arbitration_panel_result("1F-0F")
        mensagem = pergunta.call_args.args[2]
        self.assertIn("mesa 1", mensagem)
        self.assertIn(str(mesa["white_name"]), mensagem)
        self.assertIn(str(mesa["black_name"]), mensagem)
        self.assertEqual("", self.db.get_pairing(int(mesa["id"]))["result"])

    def test_aviso_de_editar_bye_aparece_pela_tecla(self) -> None:
        db_bye = TournamentService(self.db).create_tournament(
            {"name": "Com bye", "rounds_count": "3", "bye_points": "1"}
        )
        for indice in range(3):
            self.db.create_player(db_bye, name=f"Ímpar {indice + 1}", rating=1800 - indice * 10)
        rodada = int(self.servico.generate_next_round(db_bye)["id"])
        self.app.current_tournament_id = db_bye
        self._abrir_rodadas()
        indice_bye = next(
            i for i, item in enumerate(self.app.pairing_tree.get_children())
            if self.app.pairing_detail_map[item].get("is_bye")
        )
        self._selecionar_mesa(indice_bye)
        with mock.patch.object(self.app, "_prompt_bye_edit_warning", return_value="cancel") as aviso:
            self._tecla("1")
        aviso.assert_called_once_with("BYE", "1-0")
        bye = next(p for p in self.db.get_pairings_for_round(rodada) if p["is_bye"])
        self.assertEqual("BYE", bye["result"])

    def test_geracao_vai_para_segundo_plano_com_o_botao_ocupado(self) -> None:
        for mesa in self._mesas():
            self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.servico.close_round(self.tournament_id, self.round_id)
        self._abrir_rodadas()
        chamadas: list[dict[str, Any]] = []
        self.app._run_background = lambda task, **kw: chamadas.append({"task": task, **kw})
        self.app._generate_round()

        self.assertEqual(1, len(chamadas), "a geração deve passar por _run_background")
        self.assertIs(self.app._generate_round_button, chamadas[0]["busy_widget"])
        self.assertIsNotNone(chamadas[0]["busy_widget"])
        # Nada foi gerado na thread da tela: a tarefa só roda quando o fundo a chama.
        self.assertEqual(1, len(self.db.list_rounds(self.tournament_id)))


class DesfazerContadorEWoTest(_RodadasBase):
    """RGS-21: Desfazer, contador e W.O. por tecla em Rodadas."""

    def _toast(self) -> Any:
        ativos = self.app.toasts.active
        self.assertTrue(ativos, "o lançamento devia mostrar um toast")
        return ativos[-1]

    def test_lancar_e_desfazer_por_ctrl_z_volta_o_anterior_com_2_eventos(self) -> None:
        self._abrir_rodadas()
        mesa = self._mesas()[0]
        self._selecionar_mesa(0)
        acoes = ["tecla 1"]
        self._tecla("1")

        texto = _textos(self._toast())
        self.assertIn(f"Mesa {mesa['board_number']} → 1-0", texto)
        self.assertIn("Desfazer (Ctrl+Z)", texto)
        self.assertEqual("1-0", self.db.get_pairing(int(mesa["id"]))["result"])

        acoes.append("Ctrl+Z")
        self._tecla("<Control-z>")

        self.assertEqual(2, len(acoes))
        self.assertEqual("", self.db.get_pairing(int(mesa["id"]))["result"])
        eventos = self._eventos("result_updated")
        self.assertEqual(2, len(eventos))
        self.assertTrue(json.loads(eventos[0]["after_json"])["undo"])
        # Desfeito, não há o que desfazer de novo: Ctrl+Z não grava um 3º evento.
        self._tecla("<Control-z>")
        self.assertEqual(2, len(self._eventos("result_updated")))

    def test_botao_do_toast_desfaz_e_devolve_o_resultado_anterior(self) -> None:
        mesa = self._mesas()[0]
        self.servico.update_result(self.tournament_id, int(mesa["id"]), "0-1")
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self._tecla("1")
        self.assertEqual("1-0", self.db.get_pairing(int(mesa["id"]))["result"])

        _botao(self._toast(), "Desfazer (Ctrl+Z)").invoke()
        self.app.update()

        self.assertEqual("0-1", self.db.get_pairing(int(mesa["id"]))["result"])
        self.assertEqual(3, len(self._eventos("result_updated")))

    def test_contador_de_lancadas_acompanha_o_lancamento(self) -> None:
        self._abrir_rodadas()
        self.assertEqual("0/3 lançadas", self.app._round_progress_label.cget("text"))
        self._selecionar_mesa(0)
        self._tecla("1")
        self.assertEqual("1/3 lançadas", self.app._round_progress_label.cget("text"))
        self._tecla("<Control-z>")
        self.assertEqual("0/3 lançadas", self.app._round_progress_label.cget("text"))

    def test_tecla_w_confirma_nomeando_mesa_e_jogadores_e_lanca(self) -> None:
        self._abrir_rodadas()
        mesa = self._mesas()[0]
        self._selecionar_mesa(0)
        vistos: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            vistos.append(_textos(dialogo))
            _botao(dialogo, "Sim").invoke()

        self._quando_abrir(no_dialogo)
        self._tecla("w")

        self.assertIn("Confirmar W.O.", vistos[0])
        self.assertIn("mesa 1", vistos[0])
        self.assertIn(str(mesa["white_name"]), vistos[0])
        self.assertIn(str(mesa["black_name"]), vistos[0])
        self.assertEqual("1F-0F", self.db.get_pairing(int(mesa["id"]))["result"])

    def test_esc_na_confirmacao_de_wo_nao_lanca_nem_avanca(self) -> None:
        self._abrir_rodadas()
        mesa = self._mesas()[0]
        item = self._selecionar_mesa(0)
        vistos: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            vistos.append(_textos(dialogo))
            dialogo.focus_force()
            dialogo.update()
            dialogo.event_generate("<Escape>")

        self._quando_abrir(no_dialogo)
        self._tecla("a")

        self.assertEqual(1, len(vistos), "a tecla a devia pedir confirmação")
        self.assertEqual("", self.db.get_pairing(int(mesa["id"]))["result"])
        self.assertEqual([], self._eventos("result_updated"))
        self.assertEqual(item, self.app.pairing_tree.selection()[0])

    def test_teclas_p_e_a_lancam_os_outros_wo(self) -> None:
        self._abrir_rodadas()
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True):
            self._selecionar_mesa(0)
            self._tecla("p")
            self._selecionar_mesa(1)
            self._tecla("a")
        mesas = self._mesas()
        self.assertEqual(("0F-1F", "0F-0F"), (mesas[0]["result"], mesas[1]["result"]))


class BotaoPrimarioDaRodadaTest(_RodadasBase):
    """RGS-25: Lançar resultados (N/M) → Fechar rodada N → Gerar rodada N+1."""

    def _primario(self) -> ctk.CTkButton:
        botao = self.app._round_primary_button
        self.assertTrue(botao.winfo_exists())
        return botao

    def test_sequencia_dos_tres_rotulos_e_esc_nao_fecha(self) -> None:
        self._abrir_rodadas()
        rotulos = [self._primario().cget("text")]
        acoes: list[str] = []

        # "Lançar resultados" leva à primeira mesa pendente, com o foco na tabela.
        self.app.pairing_tree.selection_set(self.app.pairing_tree.get_children()[2])
        acoes.append("Lançar resultados")
        self._primario().invoke()
        self.app.update()
        self.assertEqual(self.app.pairing_tree.get_children()[0], self.app.pairing_tree.selection()[0])
        for _ in range(3):
            acoes.append("tecla 1")
            self._tecla("1")
        rotulos.append(self._primario().cget("text"))

        # Esc na confirmação NÃO fecha.
        vistos: list[str] = []

        def esc(dialogo: Any) -> None:
            vistos.append(_textos(dialogo))
            dialogo.focus_force()
            dialogo.update()
            dialogo.event_generate("<Escape>")

        self._quando_abrir(esc)
        self._primario().invoke()
        self.app.update()
        self.assertEqual("generated", self.db.get_round(self.round_id)["status"])
        self.assertEqual("Fechar rodada 1", self._primario().cget("text"))
        self.assertIn("Resultados lançados (3/3)", vistos[0])

        def confirmar(dialogo: Any) -> None:
            _botao(dialogo, "Fechar rodada 1").invoke()

        self._quando_abrir(confirmar)
        acoes.append("Fechar rodada 1")
        self._primario().invoke()
        acoes.append("confirmar")
        self.app.update()
        self.assertEqual("closed", self.db.get_round(self.round_id)["status"])
        self.assertEqual(1, len(self._eventos("round_closed")))
        rotulos.append(self._primario().cget("text"))

        acoes.append("Gerar rodada 2")
        self._primario().invoke()
        self.app.update()
        self.assertEqual(2, len(self.db.list_rounds(self.tournament_id)))
        rotulos.append(self._primario().cget("text"))

        self.assertEqual(
            ["Lançar resultados (0/3)", "Fechar rodada 1", "Gerar rodada 2", "Lançar resultados (0/3)"],
            rotulos,
        )
        self.assertEqual(7, len(acoes), acoes)

    def test_fechar_rodada_nao_mora_mais_no_menu_mais(self) -> None:
        self._abrir_rodadas()
        itens = [
            item[0]
            for widget in _walk(self.app.content)
            for item in (getattr(widget, "_menu_items", None) or ())
            if item
        ]
        self.assertNotIn("Fechar rodada", itens)

    def test_pendencia_bloqueante_vai_para_a_faixa_sem_confirmacao(self) -> None:
        for mesa in self._mesas():
            self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self._abrir_rodadas()
        self.assertEqual("Fechar rodada 1", self._primario().cget("text"))
        itens = [
            {"label": "Resultados lançados (3/3)", "ok": True, "action": "pending_results"},
            {"label": "Sem resultados QR aguardando aprovação", "ok": False, "action": "qr_pending"},
        ]
        with mock.patch.object(self.app.pairing_service, "closing_checklist", return_value=itens), \
                mock.patch("src.ui.components.dialogs.confirm_dialog") as pergunta:
            self._primario().invoke()
            self.app.update()
        pergunta.assert_not_called()
        faixa = self.app.rule_banner.current
        self.assertIsNotNone(faixa)
        self.assertIn("Sem resultados QR aguardando aprovação", _textos(faixa))
        self.assertEqual("generated", self.db.get_round(self.round_id)["status"])

    def test_ultima_rodada_fechada_leva_a_classificacao(self) -> None:
        for _ in range(3):
            rodada = self.db.list_rounds(self.tournament_id)[0]
            for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
                self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
            self.servico.close_round(self.tournament_id, int(rodada["id"]))
            if int(rodada["number"]) < 3:
                self.servico.generate_next_round(self.tournament_id)
        self._abrir_rodadas()
        self.assertEqual("Ver classificação final", self._primario().cget("text"))
        self._primario().invoke()
        self.app.update()
        self.assertTrue(hasattr(self.app, "standings_tree") and self.app.standings_tree.winfo_exists())
