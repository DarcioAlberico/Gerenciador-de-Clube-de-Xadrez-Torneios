"""RGS-10 na tela: o login liga o trabalhador, que termina a pendência deixada
por uma sessão anterior e avisa a tela só pelo ``after()``."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.services import PairingService
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)


def _torneio_com_correcao_pendente(db: Database) -> int:
    service = PairingService(db)
    tournament_id = db.create_tournament("Torneio RGS-10", rounds_count=5)
    for index in range(4):
        db.create_player(tournament_id, name=f"Jogador {index + 1}", rating=2000 - index * 50)
    round_ids = []
    for _ in range(3):
        round_id = int(service.generate_next_round(tournament_id)["id"])
        round_ids.append(round_id)
        for pairing in db.get_pairings_for_round(round_id):
            service.update_result(tournament_id, int(pairing["id"]), "1-0")
        service.close_round(tournament_id, round_id)
    service.unlock_round_for_correction(tournament_id, round_ids[0], "Reclamacao do jogador")
    mesa = db.get_pairings_for_round(round_ids[0])[0]
    # Sem ninguém ouvindo: a pendência fica no banco, como num app fechado.
    service.update_result(tournament_id, int(mesa["id"]), "0-1", "Sumula trocada pelo arbitro")
    return tournament_id


@pytest.mark.gui
class ReconciliacaoNaAberturaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.tournament_id = _torneio_com_correcao_pendente(self.db)
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:  # pragma: no cover - ambiente sem display
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.update()

    def tearDown(self) -> None:
        reconciler = getattr(self.app, "snapshot_reconciler", None)
        if reconciler is not None:
            reconciler.wait(30)
        cancel_pending_callbacks(self.app)
        try:
            self.app.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()
        self.temp_dir.cleanup()

    def _entrar(self) -> None:
        # RG2-37: banco novo nasce com o admin sem senha; o primeiro acesso a define.
        self.app.security_service.set_first_password("admin", "admin")
        self.app.username_entry.insert(0, "admin")
        self.app.password_entry.insert(0, "admin")
        botao = next(
            w
            for w in self._andar(self.app.login_frame)
            if isinstance(w, ctk.CTkButton) and "Entrar" in str(w.cget("text"))
        )
        botao.invoke()
        self.app.update()

    @classmethod
    def _andar(cls, widget):
        for filho in widget.winfo_children():
            yield filho
            yield from cls._andar(filho)

    def test_login_termina_a_reconciliacao_pendente(self) -> None:
        self.assertEqual(3, len(self.db.list_pending_standings_snapshots(self.tournament_id)))
        self._entrar()

        reconciler = self.app.snapshot_reconciler
        self.assertTrue(reconciler.wait(60))
        self.assertEqual([], self.db.list_pending_standings_snapshots(self.tournament_id))
        self.assertEqual(reconciler.start, self.app.pairing_service.on_snapshots_pending)

        # O aviso chega pelo after(): só aparece depois que o laço do Tk roda.
        prazo = time.monotonic() + 10
        texto = ""
        while time.monotonic() < prazo:
            self.app.update()
            texto = str(self.app.status_label.cget("text"))
            if "reconciliado" in texto:
                break
        self.assertIn("3 retratos de classificação reconciliados", texto)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
