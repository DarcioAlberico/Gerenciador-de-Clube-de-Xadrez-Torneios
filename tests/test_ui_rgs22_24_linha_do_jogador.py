"""RGS-22/23/24 na tela — menus da linha do jogador, diálogos e contagem de ações.

A espec fixa o alvo em AÇÕES (seção 5): bye "menu, tipo, motivo, Enter";
retirar/reintegrar "menu, escopo, motivo, Enter" — no máximo 4. Cada teste
aqui executa os passos numa lista (``self.acao``) e cobra o teto no fim. "Menu"
é escolher o item na lista que o clique direito desenha (``menu_items``); o
resto é o que o árbitro faz com o teclado no diálogo.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError
from typing import Any, Callable

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import TournamentService
from src.ui.app import AlbericusApp
from src.ui.components.search_combo import SearchCombo
from tests.support.ctk_cleanup import cancel_pending_callbacks, create_tk_window, release_dead_ctk_windows
from tests.support.login import entrar_como_admin

pytestmark = pytest.mark.gui

MAX_ACOES = 4


class _Base(unittest.TestCase):
    rounds = "7"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tid = TournamentService(self.db).create_tournament(
            {"name": "Linha do jogador", "rounds_count": self.rounds, "bye_points": "1"}
        )
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.current_tournament_id = self.tid
        self.errors: list[str] = []
        self.toasts: list[str] = []
        self.app._show_error = lambda error, *a, **kw: self.errors.append(str(error))
        self.app._show_toast = lambda message, *a, **kw: self.toasts.append(str(message))
        self.app._show_info = lambda *a, **kw: None
        entrar_como_admin(self.app.security_service)
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()
        self.service = self.app.pairing_service
        self.passos: list[str] = []

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            cancel_pending_callbacks(self.app)
            self.app.destroy()
            release_dead_ctk_windows()
        self.temp_dir.cleanup()

    # ---- apoio ------------------------------------------------------------- #

    def acao(self, nome: str, passo: Callable[[], Any]) -> Any:
        """Uma ação do árbitro. O teste cobra o teto de ações no fim."""
        self.passos.append(nome)
        resultado = passo()
        self.app.update()
        return resultado

    def jogadores(self, total: int, nomes: list[str] | None = None) -> list[int]:
        nomes = nomes or [f"Jogador {i:03d}" for i in range(total)]
        return [
            int(self.db.create_player(self.tid, name=nome, rating=2000 - i))
            for i, nome in enumerate(nomes)
        ]

    def jogar(self, rodadas: int) -> None:
        for _ in range(rodadas):
            rodada = self.service.generate_next_round(self.tid)
            for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
                if not mesa["is_bye"]:
                    self.service.update_result(self.tid, int(mesa["id"]), "1-0")
            self.service.close_round(self.tid, int(rodada["id"]))

    @staticmethod
    def item(itens: list, rotulo_comeca: str) -> Callable[[], Any]:
        for item in itens:
            if item is not None and item[0].startswith(rotulo_comeca):
                assert item[1] is not None, f"item inativo: {item[0]}"
                return item[1]
        raise AssertionError(f"item {rotulo_comeca!r} ausente em {itens}")

    def enter(self, dialogo: Any) -> None:
        """Enter no diálogo. O Tk descarta tecla enviada a um widget de janela
        não visível (a dos testes), então o evento vai ao toplevel — que é onde
        o `actions_bar` liga o Enter (os campos herdam pelos bindtags)."""
        dialogo.window.event_generate("<Return>", when="now")
        self.app.update()

    @classmethod
    def walk(cls, widget: Any):
        yield widget
        for filho in widget.winfo_children():
            yield from cls.walk(filho)


class JogadoresTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.ids = self.jogadores(6)
        self.app.show_players()
        self.app.update()
        self.tela = self.app._tournament_players_view

    def test_reintegrar_desistente_pela_tela(self) -> None:
        """Aceite: reintegrar pela tela → ativo e 1 evento de histórico."""
        alvo = self.ids[1]
        self.service.set_player_participation(self.tid, alvo, "withdrawn", "viagem")
        antes = len(self.service.participation_history(self.tid, alvo))
        acoes = self.tela.player_actions

        self.acao("menu", self.item(acoes.menu_items(alvo), "Reintegrar"))
        dialogo = acoes.last_dialog
        self.assertIn("rodada 1", dialogo.info_label.cget("text"))
        self.acao("motivo", lambda: dialogo.reason.insert(0, "apelação deferida"))
        self.acao("Enter", lambda: self.enter(dialogo))

        self.assertEqual([], self.errors)
        self.assertTrue(dialogo.done)
        self.assertEqual("active", self.db.get_player(alvo)["player_status"])
        self.assertEqual(antes + 1, len(self.service.participation_history(self.tid, alvo)))
        self.assertLessEqual(len(self.passos), MAX_ACOES, self.passos)

    def test_reintegrar_sem_motivo_fica_no_dialogo(self) -> None:
        alvo = self.ids[1]
        self.service.set_player_participation(self.tid, alvo, "withdrawn", "viagem")
        acoes = self.tela.player_actions
        self.item(acoes.menu_items(alvo), "Reintegrar")()
        self.app.update()
        dialogo = acoes.last_dialog
        self.enter(dialogo)
        self.assertFalse(dialogo.done)
        self.assertIn("motivo", dialogo.error_label.cget("text"))
        self.assertEqual("withdrawn", self.db.get_player(alvo)["player_status"])
        dialogo.window.close()

    def test_retirar_com_escopo_motivo_e_enter(self) -> None:
        alvo = self.ids[2]
        acoes = self.tela.player_actions

        self.acao("menu", self.item(acoes.menu_items(alvo), "Retirar do torneio"))
        dialogo = acoes.last_dialog
        self.acao("escopo", lambda: dialogo.scope_selector.set(dialogo.scope_labels["withdrawn"]))
        self.acao("motivo", lambda: dialogo.reason.insert(0, "lesão"))
        self.acao("Enter", lambda: self.enter(dialogo))

        self.assertEqual([], self.errors)
        jogador = self.db.get_player(alvo)
        self.assertEqual("withdrawn", jogador["player_status"])
        (evento,) = self.service.participation_history(self.tid, alvo)
        self.assertEqual("lesão", evento["reason"])
        self.assertLessEqual(len(self.passos), MAX_ACOES, self.passos)

    def test_atualizar_status_para_ativo_abre_reintegrar(self) -> None:
        """O botão antigo não tinha saída para o desistente: agora abre o diálogo."""
        alvo = self.ids[3]
        self.service.set_player_participation(self.tid, alvo, "withdrawn", "viagem")
        self.tela.reload()
        linha = next(
            i for i in self.tela.tree.get_children() if int(self.tela.tree.item(i, "values")[0]) == alvo
        )
        self.tela.tree.selection_set(linha)
        self.tela._on_select()
        self.tela.status_option.set("Ativo")
        dialogo = self.tela._update_status()
        self.app.update()
        self.assertEqual([], self.errors)
        self.assertEqual("ReinstateDialog", type(dialogo).__name__)
        dialogo.window.close()

    def test_atualizar_cadastro_nao_muda_status(self) -> None:
        alvo = self.ids[4]
        self.tela.reload()
        linha = next(
            i for i in self.tela.tree.get_children() if int(self.tela.tree.item(i, "values")[0]) == alvo
        )
        self.tela.tree.selection_set(linha)
        self.tela._on_select()
        self.tela.status_option.set("Desistente")
        self.tela._update_player()
        self.assertEqual([], self.errors)
        self.assertEqual("active", self.db.get_player(alvo)["player_status"])
        self.assertEqual([], self.service.participation_history(self.tid, alvo))

    def test_status_ganha_descricao(self) -> None:
        self.tela.status_option.set("Ausente")
        self.tela._describe_status()
        self.assertIn("prêmio", self.tela.status_note.cget("text"))

    def test_desistente_nao_recebe_bye_no_menu(self) -> None:
        alvo = self.ids[0]
        self.service.set_player_participation(self.tid, alvo, "withdrawn", "viagem")
        itens = {item[0]: item[1] for item in self.tela.player_actions.menu_items(alvo) if item}
        self.assertIsNone(next(cmd for rotulo, cmd in itens.items() if rotulo.startswith("Bye")))
        self.assertIsNotNone(next(cmd for rotulo, cmd in itens.items() if rotulo.startswith("Reintegrar")))


class ByeNaLinhaTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.ids = self.jogadores(6)

    def test_bye_na_proxima_rodada_com_saldo_em_4_acoes(self) -> None:
        self.db.save_tournament_settings(
            self.tid, {"max_requested_byes": 2, "last_requested_bye_round": 5}
        )
        alvo = self.ids[0]
        self.service.request_bye(self.tid, alvo, 3, "H", "casamento")
        self.app.show_players()
        self.app.update()
        acoes = self.app._tournament_players_view.player_actions

        self.acao("menu", self.item(acoes.menu_items(alvo), "Bye na próxima rodada"))
        dialogo = acoes.last_dialog
        self.assertIn("1 de 2 byes usados; último permitido na R5", dialogo.balance_label.cget("text"))
        self.assertEqual(1, dialogo.round_number)
        self.acao("tipo", lambda: dialogo.type_selector.set(dialogo.type_labels["H"]))
        self.acao("motivo", lambda: dialogo.reason.insert(0, "prova na faculdade"))
        self.acao("Enter", lambda: self.enter(dialogo))

        self.assertEqual([], self.errors)
        byes = {(b["round_number"], b["bye_type"]) for b in self.db.list_requested_byes(self.tid)}
        self.assertIn((1, "H"), byes)
        self.assertLessEqual(len(self.passos), MAX_ACOES, self.passos)

    def test_faltar_so_a_r4_pela_classificacao(self) -> None:
        """Aceite RGS-22 pela tela: bye Z na R4, status inalterado."""
        self.jogar(3)
        self.app.show_standings()
        self.app.update()
        alvo = self.ids[2]
        acoes = self.app.standings_player_actions

        self.acao("menu", self.item(acoes.menu_items(alvo), "Faltar só à rodada 4"))
        dialogo = acoes.last_dialog
        self.assertEqual("Z", dialogo.bye_type)
        self.acao("motivo", lambda: dialogo.reason.insert(0, "consulta médica"))
        self.acao("Enter", lambda: self.enter(dialogo))

        self.assertEqual([], self.errors)
        (bye,) = self.db.list_requested_byes(self.tid)
        self.assertEqual((4, "Z", alvo), (bye["round_number"], bye["bye_type"], bye["player_id"]))
        self.assertEqual("active", self.db.get_player(alvo)["player_status"])
        self.assertLessEqual(len(self.passos), MAX_ACOES, self.passos)

    def test_rodada_gerada_oferece_wo_na_mesa(self) -> None:
        rodada = self.service.generate_next_round(self.tid)
        alvo = self.ids[0]
        mesa = next(
            m for m in self.db.get_pairings_for_round(int(rodada["id"]))
            if alvo in (m["white_player_id"], m["black_player_id"])
        )
        self.app.show_players()
        self.app.update()
        acoes = self.app._tournament_players_view.player_actions

        self.acao("menu", self.item(acoes.menu_items(alvo), "Faltar só à rodada 1"))
        dialogo = acoes.last_dialog
        self.assertEqual("walkover", dialogo.mode)
        self.assertIn(f"mesa {mesa['board_number']}", dialogo.primary_button.cget("text"))
        self.acao("motivo", lambda: dialogo.reason.insert(0, "avisou que não vem"))
        self.acao("Enter", lambda: self.enter(dialogo))

        self.assertEqual([], self.errors)
        resultado = self.db.get_pairing(int(mesa["id"]))["result"]
        self.assertIn(resultado, ("0F-1F", "1F-0F"))
        self.assertEqual([], self.db.list_requested_byes(self.tid))

    def test_chamada_inicial_tem_o_menu(self) -> None:
        self.app.show_pairings()
        self.app.update()
        secao = self.app._initial_call_section
        itens = secao.player_actions.menu_items(self.ids[0])
        self.assertTrue(any(i and i[0].startswith("Faltar só à rodada 1") for i in itens))


class CadastroComBuscaTest(_Base):
    """Aceite RGS-23: 100 jogadores, "sil" deixa ≤ 5 opções, Enter grava o certo."""

    def test_sil_filtra_e_enter_grava_o_bye(self) -> None:
        nomes = [f"Jogador {i:03d}" for i in range(97)] + ["Ana Silva", "Basílio Costa", "Sílvio Rocha"]
        ids = self.jogadores(100, nomes)
        ana = ids[97]
        self.app.show_requested_byes()
        self.app.update()
        combos = [w for w in self.walk(self.app.content) if isinstance(w, SearchCombo)]
        self.assertEqual(1, len(combos))
        combo = combos[0]
        self.assertEqual(100, len(combo.all_options))

        combo._entry.focus_force()
        for letra in "sil":
            combo._entry.insert("end", letra)
            combo._entry.event_generate("<KeyRelease>", keysym=letra)
        self.app.update()

        self.assertLessEqual(len(combo.options), 5, combo.options)
        self.assertEqual(3, len(combo.options), "acento não esconde o Sílvio")
        combo._entry.event_generate("<Return>")
        self.app.update()

        self.assertEqual([], self.errors)
        (bye,) = self.db.list_requested_byes(self.tid)
        self.assertEqual(ana, int(bye["player_id"]))


class EntradaTardiaNaTelaTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.ids = self.jogadores(5)
        self.db.save_tournament_settings(self.tid, {"late_entry_points": 0.5})

    def test_assistente_em_uma_tela(self) -> None:
        self.jogar(3)
        dialogo = self.app.open_late_entry_dialog()
        self.app.update()
        self.assertIn("rodada 4", dialogo.plan_label.cget("text"))
        self.assertIn("1,5", dialogo.plan_label.cget("text"))
        dialogo.name.insert(0, "Tardio da Silva")
        dialogo.rating.insert(0, "1990")
        self.enter(dialogo)

        self.assertEqual([], self.errors)
        novo = next(p for p in self.db.list_players(self.tid, active_only=False) if p["name"] == "Tardio da Silva")
        self.assertEqual(4, int(novo["entry_round"]))
        self.assertEqual(1.5, float(novo["starting_points"]))
        self.assertEqual(1990, int(novo["rating"]))

    def test_botao_em_rodadas_e_no_painel(self) -> None:
        self.jogar(1)
        for abrir in (self.app.show_pairings, self.app.show_arbitration_panel):
            with self.subTest(tela=abrir.__name__):
                abrir()
                self.app.update()
                botoes = [
                    w for w in self.walk(self.app.content)
                    if isinstance(w, ctk.CTkButton) and w.cget("text") == "Entrada tardia…"
                ]
                self.assertEqual(1, len(botoes))
                antes = set(self.app.winfo_children())
                botoes[0].invoke()
                self.app.update()
                novos = [w for w in self.app.winfo_children() if w not in antes]
                janelas = [w for w in novos if isinstance(w, ctk.CTkToplevel)]
                self.assertEqual(["Entrada tardia"], [w.title() for w in janelas])
                for janela in janelas:
                    janela.close()
                self.app.update()

    def test_aviso_da_inscricao_comum_foi_substituido(self) -> None:
        """O "foge ao regulamento" (sem acento, impreciso) saiu da tela."""
        self.jogar(2)
        self.app._is_free_mode = lambda _tid: False
        perguntas: list[tuple[str, str]] = []
        self.app._confirm_action = lambda titulo, texto, **kw: perguntas.append((titulo, texto)) or True
        self.assertEqual((True, None), self.app.prepare_late_entry(self.tid))
        ((_titulo, texto),) = perguntas
        self.assertNotIn("foge", texto)
        self.assertIn("Já há 2 rodadas encerradas", texto)
        self.assertIn("ausência", texto)


if __name__ == "__main__":
    unittest.main()
