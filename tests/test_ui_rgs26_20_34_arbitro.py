"""Fase 2 — árbitro prático, aceite de UI (RGS-26, RGS-20, RGS-34).

Cada teste conta as **ações** do árbitro (``invoke`` de botão, tecla gerada)
e confere o banco pelos eventos de auditoria, como pede a ESPEC §5:

- RGS-26: a recusa de uma correção vira faixa fixa (fechar + ação sugerida)
  e continua na tela depois de 10 s; toast só para sucesso.
- RGS-20: corrigir rodada fechada em ≤ 3 ações, sem criar a tela de
  Configurações; 1 desbloqueio, 1 correção e 1 cascata com o MESMO motivo;
  reverter devolve o resultado original com 1 correção nova.
- RGS-34: excluir rodada com resultados pede motivo e diz quantos somem.

Os diálogos do app são bloqueantes (``wait_window``): a interação é agendada
com ``after`` antes de abrir, como em ``test_ui_dialogs``.
"""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from tkinter import TclError
from typing import Any, Callable

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import AppError, PairingService, TournamentService
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)
from tests.support.login import entrar_como_admin
from tests.support.ui_input import type_into

pytestmark = pytest.mark.gui

MOTIVO = "Súmula da mesa 1 diverge do lançado"


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
        if isinstance(filho, (ctk.CTkLabel, ctk.CTkCheckBox, ctk.CTkButton))
    )


class _ArbitroBase(unittest.TestCase):
    """Torneio de 6 jogadores: R1 e R2 fechadas, R3 gerada sem resultados."""

    RODADAS_FECHADAS = 2
    GERAR_SEGUINTE = True

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Árbitro prático", "rounds_count": "5", "bye_points": "1"}
        )
        servico = PairingService(self.db)
        for indice in range(6):
            self.db.create_player(
                self.tournament_id, name=f"Jogador {indice + 1}", rating=2000 - indice * 40
            )
        self.round_ids: list[int] = []
        for _ in range(self.RODADAS_FECHADAS):
            rodada = servico.generate_next_round(self.tournament_id)
            self.round_ids.append(int(rodada["id"]))
            for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
                servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
            servico.close_round(self.tournament_id, int(rodada["id"]))
        if self.GERAR_SEGUINTE:
            self.round_ids.append(int(servico.generate_next_round(self.tournament_id)["id"]))

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
        # Geração em segundo plano roda na hora: o teste confere o banco.
        self.app._run_background = self._run_now
        self.telas_de_configuracoes = 0
        original = self.app.show_tournament_settings

        def contar_configuracoes(*a: Any, **kw: Any) -> None:
            self.telas_de_configuracoes += 1
            original(*a, **kw)

        self.app.show_tournament_settings = contar_configuracoes
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

    def _abrir_rodadas(self, numero: int) -> None:
        self.app.show_pairings()
        self.app.update()
        rotulo = next(r for r in self.app.round_option_map if r.startswith(f"Rodada {numero} "))
        self.app.round_option.set(rotulo)
        self.app._load_selected_round_pairings()
        self.app.update()

    def _selecionar_mesa(self, indice: int = 0) -> str:
        item = self.app.pairing_tree.get_children()[indice]
        self.app.pairing_tree.selection_set(item)
        self.app.pairing_tree.focus(item)
        self.app.pairing_tree.focus_set()
        self.app.update()
        return item


class FaixaDeErroDeRegraTest(_ArbitroBase):
    """RGS-26: erro de regra não pode sumir em 5 s."""

    def test_recusa_de_correcao_cria_faixa_que_continua_la_depois_de_10s(self) -> None:
        mesa = self.db.get_pairings_for_round(self.round_ids[0])[0]
        try:
            # Rodada fechada, sem desbloqueio: o serviço recusa.
            self.app.pairing_service.update_result(
                self.tournament_id, int(mesa["id"]), "0-1", MOTIVO
            )
            self.fail("a correção sem desbloqueio deveria ser recusada")
        except AppError as exc:
            self.app._show_error(exc)
        self.app.update()

        faixa = self.app.rule_banner.current
        self.assertIsNotNone(faixa, "a recusa não criou a faixa")
        self.assertEqual([], self.app.toasts.active, "erro de regra não vai para toast")
        texto = _textos(faixa)
        self.assertIn("fechada", texto)
        # A ação sugerida vem junto, e ela não manda mais ligar "mudanças perigosas".
        self.assertIn("Corrigir resultado", texto)
        self.assertNotIn("perigosas", texto.casefold())

        limite = time.monotonic() + 10.2
        while time.monotonic() < limite:
            self.app.update()
            time.sleep(0.05)

        self.assertIs(faixa, self.app.rule_banner.current)
        self.assertTrue(faixa.winfo_exists() and faixa.winfo_ismapped(), "a faixa sumiu sozinha")

        fechar = _botao(faixa, "Fechar")
        self.assertIsNotNone(fechar, "a faixa precisa de um botão de fechar")
        fechar.invoke()
        self.app.update()
        self.assertIsNone(self.app.rule_banner.current)

    def test_sucesso_continua_em_toast(self) -> None:
        self.app._show_info("Rodada fechada.")
        self.app.update()
        self.assertEqual(1, len(self.app.toasts.active))
        self.assertIsNone(self.app.rule_banner.current)

    def test_nova_recusa_substitui_a_anterior(self) -> None:
        self.app._show_error(AppError("Primeira recusa."))
        self.app._show_error(AppError("Segunda recusa.", suggestion="Faça outra coisa."))
        self.app.update()
        faixas = [
            w for w in _walk(self.app)
            if getattr(w, "_rule_banner", False) and w.winfo_exists()
        ]
        self.assertEqual(1, len(faixas))
        self.assertIn("Segunda recusa.", _textos(faixas[0]))
        self.assertIn("Faça outra coisa.", _textos(faixas[0]))


def _enter(campo: Any) -> None:
    interno = getattr(campo, "_entry", campo)
    # focus_force: o diálogo é outra janela; sem o foco do sistema nela, a
    # tecla gerada não é entregue (ver tests/support/ui_input.py).
    interno.focus_force()
    interno.update()
    interno.event_generate("<Return>")


class CorrigirResultadoNaMesaTest(_ArbitroBase):
    """RGS-20: clique direito/Shift+F10/Ctrl+E → um diálogo → resultado → motivo + Enter."""

    def _clique_direito(self, item: str) -> None:
        tree = self.app.pairing_tree
        x, y, _w, _h = tree.bbox(item)
        tree.event_generate("<Button-3>", x=x + 5, y=y + 5)

    def _tecla(self, sequencia: str) -> None:
        tree = self.app.pairing_tree
        self.app.focus_force()
        tree.focus_set()
        self.app.update()
        tree.event_generate(sequencia)

    def test_corrigir_rodada_fechada_em_3_acoes_sem_abrir_configuracoes(self) -> None:
        self._abrir_rodadas(2)
        item = self.app.pairing_tree.get_children()[0]
        mesa = self.app.pairing_detail_map[item]
        self.assertEqual("1-0", mesa["result"])
        acoes: list[str] = []
        avisos: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            avisos.append(_textos(dialogo))
            acoes.append("resultado")
            dialogo.result_buttons["0-1"].invoke()
            acoes.append("motivo + Enter")
            type_into(dialogo.reason_entry, MOTIVO)
            _enter(dialogo.reason_entry)

        self._quando_abrir(no_dialogo)
        acoes.append("clique direito")
        self._clique_direito(item)
        self.app.update()

        self.assertLessEqual(len(acoes), 3, acoes)
        self.assertIn("A rodada 2 será desbloqueada por 15 min só para esta correção", avisos[0])
        self.assertEqual("0-1", self.db.get_pairing(int(mesa["id"]))["result"])
        desbloqueios = self._eventos("round_correction_unlocked")
        correcoes = self._eventos("result_corrected")
        cascatas = self._eventos("result_correction_cascade")
        self.assertEqual((1, 1, 1), (len(desbloqueios), len(correcoes), len(cascatas)))
        self.assertEqual(
            {MOTIVO}, {desbloqueios[0]["reason"], correcoes[0]["reason"], cascatas[0]["reason"]}
        )
        self.assertEqual(0, self.telas_de_configuracoes, "a correção não pode passar pelas Configurações")
        self.assertIsNone(self.app.rule_banner.current)

    def test_recusa_fica_no_dialogo_em_faixa_e_nada_e_gravado(self) -> None:
        self._abrir_rodadas(2)
        item = self._selecionar_mesa(0)
        mesa = self.app.pairing_detail_map[item]
        vistos: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            dialogo.result_buttons["0-1"].invoke()
            type_into(dialogo.reason_entry, "ok")
            _enter(dialogo.reason_entry)
            self.assertTrue(dialogo.winfo_exists(), "recusa não fecha o diálogo")
            self.assertIsNotNone(dialogo.banner, "recusa dentro do diálogo vai para a faixa")
            vistos.append(_textos(dialogo.banner))
            # O texto digitado continua lá para o árbitro completar.
            self.assertEqual("ok", dialogo.reason_entry.get())
            dialogo.close()

        self._quando_abrir(no_dialogo)
        self._tecla("<Control-e>")
        self.app.update()

        self.assertIn("5 caracteres", vistos[0])
        self.assertEqual("1-0", self.db.get_pairing(int(mesa["id"]))["result"])
        self.assertEqual([], self._eventos("round_correction_unlocked"))
        self.assertEqual([], self._eventos("result_corrected"))

    def test_tecla_de_resultado_em_rodada_fechada_abre_o_mesmo_dialogo(self) -> None:
        """"0" numa mesa fechada: o diálogo já vem com 0-1 marcado — falta o motivo."""
        self._abrir_rodadas(2)
        item = self._selecionar_mesa(0)
        mesa = self.app.pairing_detail_map[item]
        acoes: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            self.assertEqual("0-1", dialogo.selected)
            acoes.append("motivo + Enter")
            type_into(dialogo.reason_entry, MOTIVO)
            _enter(dialogo.reason_entry)

        self._quando_abrir(no_dialogo)
        acoes.append("tecla 0")
        self._tecla("0")
        self.app.update()

        self.assertEqual(2, len(acoes))
        self.assertEqual("0-1", self.db.get_pairing(int(mesa["id"]))["result"])
        self.assertEqual(1, len(self._eventos("round_correction_unlocked")))

    def test_reverter_esta_correcao_devolve_o_original_com_uma_correcao_nova(self) -> None:
        mesa = self.db.get_pairings_for_round(self.round_ids[1])[0]
        self.app.pairing_service.correct_result(self.tournament_id, int(mesa["id"]), "0-1", MOTIVO)
        self._abrir_rodadas(2)
        self._selecionar_mesa(0)
        historicos: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            historicos.append(_textos(dialogo))
            dialogo.revert_buttons[0].invoke()
            type_into(dialogo.reason_entry, "Árbitro conferiu a súmula de novo")
            _enter(dialogo.reason_entry)

        self._quando_abrir(no_dialogo)
        self._tecla("<Shift-F10>")
        self.app.update()

        self.assertIn("Correções desta mesa", historicos[0])
        self.assertIn(MOTIVO, historicos[0])
        self.assertEqual("1-0", self.db.get_pairing(int(mesa["id"]))["result"])
        correcoes = self._eventos("result_corrected")
        self.assertEqual(2, len(correcoes))
        self.assertEqual("Árbitro conferiu a súmula de novo", correcoes[0]["reason"])
        self.assertEqual(int(correcoes[1]["id"]), json.loads(correcoes[0]["after_json"])["reverts_event_id"])
        # O desbloqueio da primeira correção ainda vale: reverter não abre outro.
        self.assertEqual(1, len(self._eventos("round_correction_unlocked")))

    def test_reparear_rodada_seguinte_sem_resultados(self) -> None:
        self._abrir_rodadas(2)
        item = self._selecionar_mesa(0)
        antiga = self.round_ids[2]

        def no_dialogo(dialogo: Any) -> None:
            self.assertIsNotNone(dialogo.repair_check, "o diálogo devia oferecer Reparear rodada 3")
            self.assertEqual("Reparear rodada 3", dialogo.repair_check.cget("text"))
            dialogo.result_buttons["0-1"].invoke()
            dialogo.repair_check.select()
            type_into(dialogo.reason_entry, MOTIVO)
            _enter(dialogo.reason_entry)

        self._quando_abrir(no_dialogo)
        self._clique_direito(item)
        self.app.update()

        self.assertIsNone(self.db.get_round(antiga), "a rodada 3 antiga devia ter sido excluída")
        rodadas = {int(r["number"]): r for r in self.db.list_rounds(self.tournament_id)}
        self.assertIn(3, rodadas, "a rodada 3 devia ter sido gerada de novo")
        excluidas = self._eventos("round_deleted")
        self.assertEqual(1, len(excluidas))
        self.assertEqual(MOTIVO, excluidas[0]["reason"])

    def test_reparear_com_resultados_passa_pela_exclusao_com_motivo(self) -> None:
        for mesa in self.db.get_pairings_for_round(self.round_ids[2])[:2]:
            self.app.pairing_service.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self._abrir_rodadas(2)
        item = self._selecionar_mesa(0)
        textos: list[str] = []

        def na_exclusao(dialogo: Any) -> None:
            textos.append(_textos(dialogo))
            campo = next(w for w in _walk(dialogo) if isinstance(w, ctk.CTkTextbox))
            campo.insert("1.0", "Reparear depois da correção da rodada 2")
            _botao(dialogo, "Excluir rodada").invoke()

        def no_dialogo(dialogo: Any) -> None:
            textos.append(_textos(dialogo))
            dialogo.result_buttons["0-1"].invoke()
            dialogo.repair_check.select()
            type_into(dialogo.reason_entry, MOTIVO)
            self._quando_abrir(na_exclusao, delay=400)
            _enter(dialogo.reason_entry)

        self._quando_abrir(no_dialogo)
        self._clique_direito(item)
        self.app.update()

        self.assertIn("2 resultados serão apagados", textos[0])
        self.assertIn("2 resultados serão apagados", textos[1])
        excluidas = self._eventos("round_deleted")
        self.assertEqual(1, len(excluidas))
        self.assertEqual("Reparear depois da correção da rodada 2", excluidas[0]["reason"])
        self.assertEqual(2, len(json.loads(excluidas[0]["before_json"])["results"]))
        self.assertIsNone(self.db.get_round(self.round_ids[2]))


class CorrigirResultadoNoPainelTest(_ArbitroBase):
    def test_ctrl_e_no_painel_abre_o_mesmo_dialogo(self) -> None:
        self.app.show_arbitration_panel()
        self.app.update()
        tabela = self.app.arbitration_pending_tree
        self.assertIsNotNone(tabela)
        item = tabela.get_children()[0]
        pairing_id = self.app.arbitration_pending_row_map[item]
        acoes: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            # Rodada aberta: não há desbloqueio nem motivo a pedir.
            self.assertFalse(dialogo.context.needs_reason)
            acoes.append("resultado")
            dialogo.result_buttons["1-0"].invoke()
            acoes.append("Enter")
            dialogo.event_generate("<Return>")

        self._quando_abrir(no_dialogo)
        acoes.append("Ctrl+E")
        self.app.focus_force()
        tabela.focus_set()
        self.app.update()
        tabela.event_generate("<Control-e>")
        self.app.update()

        self.assertLessEqual(len(acoes), 3)
        self.assertEqual("1-0", self.db.get_pairing(int(pairing_id))["result"])
        self.assertEqual([], self._eventos("round_correction_unlocked"))
        self.assertEqual(0, self.telas_de_configuracoes)


class MudancasPerigosasEmAvancadoTest(_ArbitroBase):
    """RGS-20: a opção sai da aba Regras, vai para "Avançado" e grava sozinha."""

    def test_opcao_mora_em_avancado_e_grava_ao_marcar(self) -> None:
        dialogos: list[Any] = []
        self.app._confirm_configuration = lambda confirmacoes: dialogos.append(confirmacoes) or ""
        self.app._show_error = lambda exc: self.fail(f"erro inesperado: {exc}")
        self.app.show_tournament_settings()
        self.app.update()

        abas = next(w for w in _walk(self.app.content) if isinstance(w, ctk.CTkTabview))
        caixas_regras = [
            w.cget("text") for w in _walk(abas.tab("Regras e desempates"))
            if isinstance(w, ctk.CTkCheckBox)
        ]
        self.assertNotIn("Permitir mudanças perigosas", caixas_regras)
        caixa = self.app._dangerous_changes_check
        self.assertIn(caixa, _walk(abas.tab("Avançado")))

        caixa.toggle()  # uma ação: marcar já grava
        self.app.update()

        self.assertEqual(1, len(dialogos), "um diálogo de confirmação, o do plano")
        self.assertEqual(1, int(self.db.get_tournament_settings(self.tournament_id)["allow_dangerous_changes"]))
        self.assertEqual(1, len(self._eventos("dangerous_changes_enabled")))


class ExcluirRodadaComResultadosTest(_ArbitroBase):
    """RGS-34 pela tela: o diálogo diz quantos somem e não aceita sem motivo."""

    def test_excluir_com_3_resultados_pede_motivo_e_guarda_os_resultados(self) -> None:
        for mesa in self.db.get_pairings_for_round(self.round_ids[2]):
            self.app.pairing_service.update_result(self.tournament_id, int(mesa["id"]), "0-1")
        self._abrir_rodadas(3)
        textos: list[str] = []

        def no_dialogo(dialogo: Any) -> None:
            textos.append(_textos(dialogo))
            botao = _botao(dialogo, "Excluir rodada")
            botao.invoke()  # sem motivo: recusa, o diálogo fica
            self.assertTrue(dialogo.winfo_exists())
            self.assertIsNotNone(self.db.get_round(self.round_ids[2]))
            campo = next(w for w in _walk(dialogo) if isinstance(w, ctk.CTkTextbox))
            campo.insert("1.0", "Pareamento gerado com o jogador errado")
            botao.invoke()

        self._quando_abrir(no_dialogo)
        _botao(self.app.content, "Excluir rodada").invoke()
        self.app.update()

        self.assertIn("3 resultados serão apagados", textos[0])
        self.assertIsNone(self.db.get_round(self.round_ids[2]))
        eventos = self._eventos("round_deleted")
        self.assertEqual(1, len(eventos))
        self.assertEqual("Pareamento gerado com o jogador errado", eventos[0]["reason"])
        self.assertEqual(3, len(json.loads(eventos[0]["before_json"])["results"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
