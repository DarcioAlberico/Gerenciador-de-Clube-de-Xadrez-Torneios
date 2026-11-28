"""RGS-08 / RGS-09 — aceite de UI da tela de Configurações.

- Salvar chama o serviço UMA vez: prêmio em branco recusa e nenhuma tabela
  muda (antes, `allow_dangerous_changes=1` já estava gravado quando a tela
  mostrava "Informe o nome de cada prêmio").
- Reduzir rodadas (agenda marcada) junto com uma troca de ordem inicial depois
  da R1 abre UM diálogo com as duas confirmações e salva na primeira tentativa,
  com exatamente 1 evento de cada tipo (antes: laço "Confirme…" → "Informe o
  motivo…", e cada volta gravava um `schedule_rounds_reduced` falso).
- Cancelar o diálogo → 0 eventos, nada gravado.

F1.12 — o teste do incidente (ESPEC §1.2) mora aqui também: datas fora do
padrão, prêmio em branco, R1 fechada, ligar "mudanças perigosas" e salvar.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError
from typing import Any

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import PairingService, TournamentService
from src.services.tournament_configuration import (
    TIPO_AGENDA_PERDIDA,
    TIPO_MUDANCA_ESTRUTURAL,
    TIPO_MUDANCAS_PERIGOSAS,
    Confirmacao,
)
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import cancel_pending_callbacks, create_tk_window, release_dead_ctk_windows
from tests.support.login import entrar_como_admin
from tests.test_rgs08_09_configuracao import _eventos, _retrato

pytestmark = pytest.mark.gui


class _TelaDeConfiguracoes(unittest.TestCase):
    RODADAS = "5"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.db = Database(base_path / "albericus.db", backup_dir=base_path / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Configurações", "rounds_count": self.RODADAS, "bye_points": "1"}
        )
        self.preparar()
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.current_tournament_id = self.tournament_id
        self.errors: list[str] = []
        self.dialogos: list[list[Confirmacao]] = []
        self.resposta_do_dialogo: str | None = None
        self.app._show_error = lambda error, *a, **kw: self.errors.append(str(error))
        self.app._show_toast = lambda *a, **kw: None
        self.app._show_info = lambda *a, **kw: None

        def dialogo(confirmacoes: list[Confirmacao]) -> str | None:
            self.dialogos.append(list(confirmacoes))
            return self.resposta_do_dialogo

        self.app._confirm_configuration = dialogo
        entrar_como_admin(self.app.security_service)
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            cancel_pending_callbacks(self.app)
            self.app.destroy()
            release_dead_ctk_windows()
        self.temp_dir.cleanup()

    def preparar(self) -> None:
        """Estado do banco antes de a tela abrir."""

    # -- utilitários ---------------------------------------------------------
    def _sql(self, sql: str, *params: object) -> None:
        with self.db.connect() as conexao:
            conexao.execute(sql, params)

    def _fechar_r1(self, jogadores: int = 4) -> None:
        servico = PairingService(self.db)
        for indice in range(jogadores):
            self.db.create_player(self.tournament_id, name=f"Jogador {indice + 1}", rating=2000 - indice * 50)
        rodada = servico.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                self.db.update_pairing_result(int(pairing["id"]), "1-0")
        servico.close_round(self.tournament_id, int(rodada["id"]))

    @classmethod
    def _walk(cls, widget: object):
        yield widget
        for child in widget.winfo_children():  # type: ignore[attr-defined]
            yield from cls._walk(child)

    def _campo(self, rotulo: str, tipo: type) -> Any:
        for widget in self._walk(self.app.content):
            if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == rotulo:
                for irmao in widget.master.winfo_children():
                    if isinstance(irmao, tipo):
                        return irmao
        self.fail(f"Campo {rotulo!r} nao encontrado")

    def _caixa(self, texto: str) -> ctk.CTkCheckBox:
        for widget in self._walk(self.app.content):
            if isinstance(widget, ctk.CTkCheckBox) and widget.cget("text") == texto:
                return widget
        self.fail(f"Caixa {texto!r} nao encontrada")

    def _click(self, texto: str) -> None:
        for widget in reversed(list(self._walk(self.app.content))):
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == texto:
                widget.invoke()
                self.app.update()
                return
        self.fail(f"Botao {texto!r} nao encontrado")

    def _abrir(self) -> None:
        self.app.show_tournament_settings()
        self.app.update()


class SalvarTudoOuNadaTest(_TelaDeConfiguracoes):
    def preparar(self) -> None:
        self._fechar_r1()
        self.db.save_round_schedule(
            self.tournament_id,
            [{"round_number": n, "date": f"2026-06-0{n}", "time": "09:00"} for n in range(1, 6)],
        )

    def _reduzir_e_trocar_ordem(self) -> None:
        rodadas = self._campo("Rodadas", ctk.CTkEntry)
        rodadas.delete(0, "end")
        rodadas.insert(0, "3")
        ordem = self._campo("Ordem inicial", ctk.CTkOptionMenu)
        ordem.set("Rating nacional")

    def test_cenario_combinado_um_dialogo_uma_tentativa_um_evento_de_cada(self) -> None:
        """Aceite do RGS-09."""
        self._abrir()
        self._reduzir_e_trocar_ordem()
        self.resposta_do_dialogo = "Edital corrigido pela federação"

        self._click("Salvar")

        self.assertEqual([], self.errors)
        self.assertEqual(1, len(self.dialogos))
        self.assertEqual(
            {TIPO_AGENDA_PERDIDA, TIPO_MUDANCA_ESTRUTURAL}, {item.tipo for item in self.dialogos[0]}
        )
        self.assertEqual(3, self.db.get_tournament(self.tournament_id)["rounds_count"])
        self.assertEqual("national_rating", self.db.get_tournament_settings(self.tournament_id)["initial_order"])
        self.assertEqual(1, _eventos(self.db.db_path, "schedule_rounds_reduced"))
        self.assertEqual(1, _eventos(self.db.db_path, "tournament_structural_change"))

    def test_cancelar_nao_grava_nada(self) -> None:
        antes = _retrato(self.db.db_path)
        backups = _eventos(self.db.db_path, "backup_created")
        self._abrir()
        self._reduzir_e_trocar_ordem()
        self.resposta_do_dialogo = None

        self._click("Salvar")

        self.assertEqual([], self.errors)
        self.assertEqual(1, len(self.dialogos))
        self.assertEqual(antes, _retrato(self.db.db_path))
        self.assertEqual(backups, _eventos(self.db.db_path, "backup_created"))
        self.assertEqual(0, _eventos(self.db.db_path, "schedule_rounds_reduced"))
        self.assertEqual(0, _eventos(self.db.db_path, "tournament_structural_change"))

    def test_premio_em_branco_recusa_sem_gravar_coluna_nenhuma(self) -> None:
        """Aceite do RGS-08, pela tela."""
        self.db.replace_tournament_prizes(
            self.tournament_id,
            [{"kind": "overall", "label": "", "rank_from": 1, "rank_to": 1, "amount": 0}],
        )
        antes = _retrato(self.db.db_path)
        self._abrir()
        organizador = self._campo("Organizador", ctk.CTkEntry)
        organizador.delete(0, "end")
        organizador.insert(0, "Clube Novo")

        self._click("Salvar")

        self.assertEqual(1, len(self.errors), self.errors)
        self.assertIn("Prêmio 1", self.errors[0])
        self.assertEqual([], self.dialogos)
        self.assertEqual(antes, _retrato(self.db.db_path))


class IncidenteF112Test(_TelaDeConfiguracoes):
    """F1.12 — a sequência mais provável do incidente (ESPEC §1.2)."""

    def preparar(self) -> None:
        self._fechar_r1()
        jogadores = self.db.list_players(self.tournament_id, active_only=False)
        self._sql("UPDATE players SET birth_date = '2010/05/12' WHERE id = ?", jogadores[0]["id"])
        self._sql("UPDATE players SET birth_date = '1985' WHERE id = ?", jogadores[1]["id"])
        self.db.save_round_schedule(self.tournament_id, [{"round_number": 1, "date": "", "time": ""}])
        self._sql(
            "UPDATE round_schedule SET date = '2026-11-13 08:00' WHERE tournament_id = ? AND round_number = 1",
            self.tournament_id,
        )
        self.db.replace_tournament_prizes(
            self.tournament_id,
            [{"kind": "overall", "label": "", "rank_from": 1, "rank_to": 1, "amount": 0}],
        )

    def test_ligar_mudancas_perigosas_e_salvar_recusa_sem_mudar_coluna_nenhuma(self) -> None:
        antes = _retrato(self.db.db_path)
        self._abrir()
        # RGS-20: a opção mora em "Avançado" e grava sozinha, com o diálogo do
        # mesmo plano de confirmações. Cancelado, nada é gravado e a caixa volta.
        caixa = self._caixa("Permitir mudanças perigosas")
        self.resposta_do_dialogo = None
        caixa.toggle()
        self.app.update()
        self.assertEqual(1, len(self.dialogos))
        self.assertEqual({TIPO_MUDANCAS_PERIGOSAS}, {item.tipo for item in self.dialogos[0]})
        self.assertEqual(0, caixa.get())

        self._click("Salvar")

        # Recusa clara: diz QUAL prêmio e o que falta, e não pede confirmação
        # de algo que não vai ser salvo.
        self.assertEqual(1, len(self.errors), self.errors)
        self.assertIn("Prêmio 1", self.errors[0])
        self.assertIn("nome", self.errors[0])
        self.assertEqual(1, len(self.dialogos), "o Salvar não pede confirmação nenhuma")
        # Nenhuma coluna de nenhuma tabela mudou — nem a flag, nem as datas.
        self.assertEqual(antes, _retrato(self.db.db_path))
        self.assertEqual(0, self.db.get_tournament_settings(self.tournament_id)["allow_dangerous_changes"])
        # `2010/05/12` já chega aqui como `2010-05-12`: a abertura do app
        # normaliza as datas convertíveis, com backup (RGS-06, F1.3). O ano
        # sozinho fica como está — e o salvar recusado não mexe em nenhum dos dois.
        nascimentos = {
            str(j["birth_date"]) for j in self.db.list_players(self.tournament_id, active_only=False)
        }
        self.assertTrue({"2010-05-12", "1985"} <= nascimentos, nascimentos)

    # -- "Depois: corrigir pela tela Rodadas" (F1.12, segunda metade) ---------
    MOTIVO = "Súmula da mesa 1 trocada na digitação"

    def _corrigir_pela_tela_rodadas(self) -> None:
        """O caminho certo: corrigir na tela Rodadas — RGS-20, um diálogo e UM motivo."""
        from src.ui.screens.pairing_results import correction as dialogo_correcao

        def responder(_janela: Any, contexto: Any, confirmar: Any) -> dict[str, Any]:
            saida = confirmar(contexto.preselect, self.MOTIVO, None)
            return {**saida, "result": contexto.preselect, "reason": self.MOTIVO, "repair": False}

        original = dialogo_correcao.correction_dialog
        dialogo_correcao.correction_dialog = responder
        self.addCleanup(setattr, dialogo_correcao, "correction_dialog", original)
        self.app._show_warning = lambda *a, **kw: None

        self.app.show_pairings()
        self.app.update()
        item = self.app.pairing_tree.get_children()[0]
        self.app.pairing_tree.selection_set(item)
        self.app.update()
        mesa = self.app.pairing_detail_map[item]
        self.app.result_option.set("0-1" if mesa["result"] == "1-0" else "1-0")
        self.app._save_selected_result()
        self.app.update()

    def test_depois_corrigir_pela_tela_rodadas_gera_uma_correcao(self) -> None:
        self._abrir()
        self._click("Salvar")
        self.assertEqual(1, len(self.errors), self.errors)

        self._corrigir_pela_tela_rodadas()

        self.assertEqual(1, len(self.errors), self.errors)
        self.assertEqual(1, _eventos(self.db.db_path, "result_corrected"))
        self.assertEqual(0, self.db.get_tournament_settings(self.tournament_id)["allow_dangerous_changes"])

    def test_depois_corrigir_pela_tela_rodadas_reconcilia_os_retratos(self) -> None:
        if getattr(self.app.pairing_service, "on_snapshots_pending", None) is None:
            self.skipTest(
                "RGS-10 em andamento: o trabalhador de reconciliação dos retratos "
                "(`reconcile_pending_snapshots`) ainda não está ligado à tela "
                "(`PairingService.on_snapshots_pending` é None no app)."
            )
        self._corrigir_pela_tela_rodadas()
        self.assertEqual(1, _eventos(self.db.db_path, "result_corrected"))
        for _ in range(100):
            if not self.db.list_pending_standings_snapshots(self.tournament_id):
                break
            self.app.update()
            self.app.after(50)
        self.assertEqual([], self.db.list_pending_standings_snapshots(self.tournament_id))
        self.assertEqual(1, _eventos(self.db.db_path, "standings_snapshot_reconciled"))
