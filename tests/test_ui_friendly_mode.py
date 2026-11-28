"""Telas do Modo Amistoso (Modo Livre no app) — Ondas 3 e 4 da revisão.

`ESPEC_REVISAO_MODO_AMISTOSO.md`: MA-07 (caixa em Configurações), MA-08
(criação com turma), MA-09 (mais uma rodada), MA-11 (aviso honesto), MA-12
(linha "Modo:" no painel) e MA-13 (menu que confere a marca no clique).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError
from typing import Any
from unittest import mock

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import TournamentService
from src.services import friendly_mode
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)
from tests.support.login import entrar_como_admin

pytestmark = pytest.mark.gui

ROTULO = friendly_mode.FRIENDLY_MODE_LABEL


def _walk(widget: Any):
    yield widget
    for filho in widget.winfo_children():
        yield from _walk(filho)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tournament_id = TournamentService(self.db).create_tournament(
            {"name": "Oficial", "rounds_count": "3", "bye_points": "1"}
        )
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        entrar_como_admin(self.app.security_service)
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()
        self.app.current_tournament_id = self.tournament_id
        self.mensagens: list[str] = []
        self.app._show_toast = lambda msg, *a, **kw: self.mensagens.append(msg)
        self.app._show_info = self.mensagens.append
        self.erros: list[str] = []
        self.app._show_error = lambda exc: self.erros.append(str(exc))

    def tearDown(self) -> None:
        try:
            cancel_pending_callbacks(self.app)
            self.app.destroy()
        except Exception:
            pass
        release_dead_ctk_windows()
        self.temp_dir.cleanup()


class MenuDaRodadaTest(_Base):
    """MA-13: os itens do modo existem sempre e conferem a marca no clique."""

    def test_itens_existem_em_torneio_oficial(self) -> None:
        rotulos = [item[0] for item in self.app._round_more_menu_items() if item]
        self.assertIn(f"Re-emparceirar ({ROTULO})", rotulos)
        self.assertIn(f"Mais uma rodada ({ROTULO})", rotulos)

    def test_clique_em_oficial_explica_e_ligado_depois_funciona(self) -> None:
        self.app.free_mode_add_round()
        self.assertTrue(any(ROTULO in erro for erro in self.erros), self.erros)
        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, True)
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True):
            self.app.free_mode_add_round()
        self.assertEqual(4, int(self.db.get_tournament(self.tournament_id)["rounds_count"]))


class MaisUmaRodadaTest(_Base):
    """MA-09: gerar no limite de rodadas oferece mais uma, só no modo."""

    def setUp(self) -> None:
        super().setUp()
        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, True)
        self.app.db.get_latest_round = lambda _tid: {"id": 1, "number": 3, "status": "closed"}

    def test_aceita_e_adiciona(self) -> None:
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as pergunta:
            seguir = self.app.free_mode_offer_extra_round(self.tournament_id)
        self.assertTrue(seguir)
        self.assertIn("Adicionar", pergunta.call_args.kwargs["confirm_text"])
        self.assertEqual(4, int(self.db.get_tournament(self.tournament_id)["rounds_count"]))

    def test_recusa_nao_gera(self) -> None:
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False):
            self.assertFalse(self.app.free_mode_offer_extra_round(self.tournament_id))
        self.assertEqual(3, int(self.db.get_tournament(self.tournament_id)["rounds_count"]))

    def test_oficial_nao_pergunta(self) -> None:
        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, False)
        with mock.patch("src.ui.components.dialogs.confirm_dialog") as pergunta:
            self.assertTrue(self.app.free_mode_offer_extra_round(self.tournament_id))
        pergunta.assert_not_called()


class AvisoTest(_Base):
    """MA-11: o aviso lista o que o modo faz de verdade."""

    def test_cinco_itens_reais(self) -> None:
        dialogo = self.app.show_free_tournament_mode()
        self.app.update()
        try:
            textos = " | ".join(
                str(w.cget("text")) for w in _walk(dialogo) if isinstance(w, ctk.CTkLabel)
            )
            for item in friendly_mode.NOTICE_ITEMS:
                self.assertIn(item, textos)
            self.assertEqual(5, len(friendly_mode.NOTICE_ITEMS))
            self.assertNotIn("punições", textos)
        finally:
            dialogo.destroy()


class CriacaoTest(_Base):
    """MA-08: nome e rodadas preenchidos, turma opcional, erro que diz a faixa."""

    def test_preenchido_e_valida_as_rodadas(self) -> None:
        recebido: list[dict] = []
        dialogo = self.app._build_friendly_tournament_dialog(recebido.append)
        self.app.update()
        try:
            self.assertTrue(self.app._friendly_name_entry.get().startswith("Torneio Amistoso "))
            self.assertEqual("5", self.app._friendly_rounds_entry.get())
            self.assertEqual("Nenhuma", self.app._friendly_class_menu.get())
            self.app._friendly_rounds_entry.delete(0, "end")
            self.app._friendly_rounds_entry.insert(0, "0")
            self.app._friendly_submit()
            self.assertEqual([], recebido)
            self.assertIn("de 1 a", self.app._friendly_error_label.cget("text"))
            self.app._friendly_rounds_entry.delete(0, "end")
            self.app._friendly_rounds_entry.insert(0, "4")
            self.app._friendly_submit()
            self.assertEqual("4", recebido[0]["rounds_count"])
            self.assertIsNone(recebido[0]["class_id"])
        finally:
            if dialogo.winfo_exists():
                dialogo.destroy()

    def test_iniciar_cria_pelo_servico(self) -> None:
        self.app._ask_friendly_tournament = lambda: {
            "name": "Festival Escolar",
            "rounds_count": "4",
            "class_id": None,
        }
        tid = self.app._start_free_tournament(None)
        self.assertEqual("Festival Escolar", self.db.get_tournament(tid)["name"])
        self.assertEqual(4, int(self.db.get_tournament(tid)["rounds_count"]))
        self.assertTrue(self.app._is_free_mode(tid))


class ConfiguracoesTest(_Base):
    """MA-07: ligar e desligar o modo em Configurações grava na hora, auditado."""

    def test_caixa_liga_e_desliga(self) -> None:
        self.app.show_tournament_settings()
        self.app.update()
        caixa = self.app._friendly_mode_check
        caixa.toggle()
        self.app.update()
        self.assertTrue(self.app._is_free_mode(self.tournament_id))
        caixa.toggle()
        self.app.update()
        self.assertFalse(self.app._is_free_mode(self.tournament_id))
        self.assertEqual(2, len(self.db.list_audit_events(self.tournament_id, action="free_mode_changed")))
        self.assertIn("Modo Oficial", self.app.tournament_label.cget("text"))

    def test_perfil_fide_recusa_e_desmarca(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"tournament_profile": "fide"})
        self.app.show_tournament_settings()
        self.app.update()
        caixa = self.app._friendly_mode_check
        caixa.toggle()
        self.app.update()
        self.assertFalse(self.app._is_free_mode(self.tournament_id))
        self.assertEqual(0, caixa.get())
        self.assertTrue(any("FIDE" in erro for erro in self.erros), self.erros)


class EntradaTardiaTest(_Base):
    """MA-04: o aluno que chega depois, pela tela, até o banco."""

    def setUp(self) -> None:
        super().setUp()
        from src.services.pairing_service import PairingService

        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, True)
        for i in range(4):
            self.db.create_player(self.tournament_id, name=f"Aluno {i + 1}", rating=1000 + i)
        self.rodada = PairingService(self.db).generate_next_round(self.tournament_id)

    def jogadores_da_rodada(self) -> set[str]:
        ultima = self.db.get_latest_round(self.tournament_id)
        ids = set()
        for mesa in self.db.get_pairings_for_round(int(ultima["id"])):
            ids |= {mesa.get("white_player_id"), mesa.get("black_player_id")}
        return {p["name"] for p in self.db.list_players(self.tournament_id) if p["id"] in ids}

    def test_jogar_ja_refaz_a_rodada_com_a_aluna(self) -> None:
        with mock.patch.object(self.app, "_confirm_or_cancel", return_value=True) as pergunta:
            self.assertTrue(self.app.free_mode_add_player(self.tournament_id, {"name": "Aluna Nova"}))
        self.assertEqual(1, pergunta.call_count)  # R1 aberta: não perdeu rodada, não pergunta pontos
        self.assertIn("Aluna Nova", self.jogadores_da_rodada())

    def test_esperar_a_proxima_nao_mexe_na_rodada(self) -> None:
        with mock.patch.object(self.app, "_confirm_or_cancel", return_value=False):
            self.assertTrue(self.app.free_mode_add_player(self.tournament_id, {"name": "Aluna Nova"}))
        self.assertNotIn("Aluna Nova", self.jogadores_da_rodada())

    def test_recusa_do_motor_oferece_o_reserva(self) -> None:
        from src.services.pairing.gacrux_engine import GacruxRefusal

        recusa = GacruxRefusal(1, [], "Recusado")
        with (
            mock.patch.object(self.app, "_confirm_or_cancel", return_value=True),
            mock.patch("src.ui.screens.free_tournament.FriendlyModeService") as servico,
            mock.patch.object(self.app, "_accept_reserve_engine", return_value=True),
        ):
            servico.return_value.late_entry.side_effect = [recusa, {"player_id": 9}]
            self.assertTrue(self.app.free_mode_add_player(self.tournament_id, {"name": "Aluna"}))
        self.assertTrue(servico.return_value.late_entry.call_args.kwargs["reserve_engine"])

    def test_recusa_do_motor_sem_reserva_nao_inscreve(self) -> None:
        from src.services.pairing.gacrux_engine import GacruxRefusal

        with (
            mock.patch.object(self.app, "_confirm_or_cancel", return_value=True),
            mock.patch("src.ui.screens.free_tournament.FriendlyModeService") as servico,
            mock.patch.object(self.app, "_accept_reserve_engine", return_value=False),
        ):
            servico.return_value.late_entry.side_effect = GacruxRefusal(1, [], "Recusado")
            self.assertFalse(self.app.free_mode_add_player(self.tournament_id, {"name": "Aluna"}))

    def test_cancelar_o_motivo_nao_inscreve(self) -> None:
        for mesa in self.db.get_pairings_for_round(int(self.rodada["id"])):
            self.db.update_pairing_result(mesa["id"], "1-0")
        with (
            mock.patch.object(self.app, "_confirm_or_cancel", return_value=True),
            mock.patch("src.ui.components.dialogs.reason_dialog", return_value=None) as motivo,
        ):
            self.assertFalse(self.app.free_mode_add_player(self.tournament_id, {"name": "Aluna Nova"}))
        self.assertIn("2 resultados anotados", motivo.call_args.args[2])
        self.assertNotIn("Aluna Nova", {p["name"] for p in self.db.list_players(self.tournament_id)})


class RatingInternoTest(_Base):
    """D2: antes de o amistoso contar para o rating interno, a tela pergunta."""

    def test_oficial_nao_pergunta(self) -> None:
        with mock.patch("src.ui.components.dialogs.confirm_dialog") as pergunta:
            self.assertTrue(self.app.free_mode_confirm_internal_rating(self.tournament_id))
        pergunta.assert_not_called()

    def test_amistoso_pergunta_com_botoes_que_dizem_o_que_fazem(self) -> None:
        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, True)
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=True) as pergunta:
            self.assertTrue(self.app.free_mode_confirm_internal_rating(self.tournament_id))
        self.assertIn("rating interno", pergunta.call_args.args[2])
        self.assertEqual(friendly_mode.INTERNAL_RATING_YES, pergunta.call_args.kwargs["confirm_text"])
        self.assertEqual(friendly_mode.INTERNAL_RATING_NO, pergunta.call_args.kwargs["cancel_text"])

    def test_nao_contar_avisa_e_nao_aplica(self) -> None:
        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, True)
        with mock.patch("src.ui.components.dialogs.confirm_dialog", return_value=False):
            self.assertFalse(self.app.free_mode_confirm_internal_rating(self.tournament_id))
        self.assertTrue(any("não foi atualizado" in m for m in self.mensagens), self.mensagens)


class PainelDoTorneioTest(_Base):
    """MA-12: o painel diz o modo, não só o perfil (que é 'Livre/Escolar' em todos)."""

    def valor_da_linha(self, rotulo: str) -> str:
        self.app.show_tournament_dashboard()
        self.app.update()
        textos = [str(w.cget("text")) for w in _walk(self.app.content) if isinstance(w, ctk.CTkLabel)]
        return textos[textos.index(rotulo) + 1]

    def test_linha_modo(self) -> None:
        self.assertEqual(friendly_mode.OFFICIAL_MODE_LABEL, self.valor_da_linha("Modo"))
        friendly_mode.FriendlyModeService(self.db).set_enabled(self.tournament_id, True)
        self.assertEqual(ROTULO, self.valor_da_linha("Modo"))


if __name__ == "__main__":
    unittest.main()
