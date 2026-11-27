"""EQ-01.5 na tela de Equipes: corrigir o TPN trocando o número de duas equipes.

O árbitro seleciona a equipe, abre "Trocar TPN", escolhe a outra equipe e
escreve o motivo. Sem motivo o diálogo avisa e não troca nada; com motivo a
troca vai ao serviço (que audita) e a tabela mostra os números novos.
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
from src.services.tournament_service import TeamService
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)

pytestmark = pytest.mark.gui


def _walk(widget: Any) -> list[Any]:
    filhos = list(widget.winfo_children())
    for filho in list(filhos):
        filhos.extend(_walk(filho))
    return filhos


def _botao(widget: Any, texto: str) -> ctk.CTkButton:
    for filho in _walk(widget):
        if isinstance(filho, ctk.CTkButton) and filho.cget("text") == texto:
            return filho
    raise AssertionError(f"Botão {texto!r} não encontrado")


class TrocaDeTpnNaTelaDeEquipesTest(unittest.TestCase):
    MOTIVO = "Rating da inscrição estava errado"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        torneios = TournamentService(self.db)
        equipes = TeamService(self.db)
        self.tid = torneios.create_tournament(
            {"name": "Equipes", "competition_type": "team", "rounds_count": "3", "bye_points": "1"}
        )
        self.db.save_tournament_settings(self.tid, {"team_boards_count": "1"})
        self.equipes: list[int] = []
        for indice in range(4):
            team_id = equipes.create_team(self.tid, {"name": f"Equipe {indice + 1}"})
            jogador = self.db.create_player(self.tid, name=f"Jogador {indice + 1}", rating=2000 - indice * 50)
            equipes.add_player(team_id, jogador, board_number="1", role="starter")
            self.equipes.append(team_id)
        servico = PairingService(self.db)
        rodada = servico.generate_next_round(self.tid)
        for match in self.db.list_team_matches_for_round(int(rodada["id"])):
            for board in self.db.list_team_boards(int(match["id"])):
                servico.update_result(self.tid, int(board["id"]), "1-0")
        servico.close_round(self.tid, int(rodada["id"]))

        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.current_tournament_id = self.tid
        self.app.security_service.login("admin", "admin")
        if hasattr(self.app, "login_frame"):
            self.app.login_frame.destroy()
            self.app._build_menu()
            self.app._build_statusbar()
            self.app._build_content()
        self.app.geometry("1400x900+0+0")
        self.app.update()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            cancel_pending_callbacks(self.app)
            self.app.destroy()
            release_dead_ctk_windows()
        self.temp_dir.cleanup()

    def _tpn(self, team_id: int) -> int:
        return int(self.db.get_team(team_id)["pairing_number"])

    def _abrir_troca(self) -> ctk.CTkToplevel:
        self.app.show_teams()
        self.app.update()
        arvore = self.app.team_tree
        linha = next(
            item for item in arvore.get_children()
            if int(arvore.item(item, "values")[0]) == self.equipes[0]
        )
        arvore.selection_set(linha)
        self.app.update()
        _botao(self.app.content, "Trocar TPN").invoke()
        self.app.update()
        dialogos = [w for w in self.app.winfo_children() if isinstance(w, ctk.CTkToplevel) and w.winfo_exists()]
        self.assertTrue(dialogos, "o diálogo de troca de TPN não abriu")
        return dialogos[-1]

    def _preencher(self, dialogo: Any, outra: int, motivo: str) -> None:
        escolha = next(w for w in _walk(dialogo) if isinstance(w, ctk.CTkOptionMenu))
        opcao = next(v for v in escolha.cget("values") if f"Equipe {self.equipes.index(outra) + 1}" in v)
        escolha.set(opcao)
        caixa = next(w for w in _walk(dialogo) if isinstance(w, ctk.CTkTextbox))
        caixa.insert("1.0", motivo)

    def test_troca_com_motivo_grava_e_mostra_o_tpn_novo(self) -> None:
        a, b = self.equipes[0], self.equipes[1]
        self.assertEqual((1, 2), (self._tpn(a), self._tpn(b)))
        dialogo = self._abrir_troca()
        self._preencher(dialogo, b, self.MOTIVO)
        _botao(dialogo, "Trocar TPN").invoke()
        self.app.update()
        self.assertEqual((2, 1), (self._tpn(a), self._tpn(b)))
        eventos = [
            e for e in self.db.list_audit_events(self.tid, limit=50)
            if e["action"] == "team_pairing_number_corrected"
        ]
        self.assertEqual([self.MOTIVO], [e["reason"] for e in eventos])
        arvore = self.app.team_tree
        tpn_na_tabela = {
            int(arvore.item(item, "values")[0]): int(arvore.item(item, "values")[1])
            for item in arvore.get_children()
        }
        self.assertEqual(2, tpn_na_tabela[a])
        self.assertEqual(1, tpn_na_tabela[b])

    def test_sem_motivo_o_dialogo_avisa_e_nada_muda(self) -> None:
        a, b = self.equipes[0], self.equipes[1]
        dialogo = self._abrir_troca()
        self._preencher(dialogo, b, "   ")
        _botao(dialogo, "Trocar TPN").invoke()
        self.app.update()
        self.assertTrue(dialogo.winfo_exists())
        textos = " ".join(
            str(w.cget("text")) for w in _walk(dialogo) if isinstance(w, ctk.CTkLabel)
        )
        self.assertIn("motivo", textos)
        self.assertEqual((1, 2), (self._tpn(a), self._tpn(b)))
        dialogo.close()
