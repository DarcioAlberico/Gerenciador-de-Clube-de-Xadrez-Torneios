"""RG2-37 na tela de login: primeiro acesso, senha sem ``strip`` e espera depois de errar."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError

import pytest

from src.core.database import Database
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import cancel_pending_callbacks, create_tk_window, release_dead_ctk_windows


@pytest.mark.gui
class TelaDeLoginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:  # pragma: no cover - ambiente sem display
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.update_idletasks()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            cancel_pending_callbacks(self.app)
            try:
                self.app.destroy()
            except TclError:  # pragma: no cover
                pass
            release_dead_ctk_windows()
        self.temp_dir.cleanup()

    def _entrar(self, usuario: str, senha: str) -> None:
        self.app.username_entry.delete(0, "end")
        self.app.username_entry.insert(0, usuario)
        self.app.password_entry.delete(0, "end")
        self.app.password_entry.insert(0, senha)
        self.app._try_login()

    def _na_tela_de_login(self) -> bool:
        return bool(self.app.login_frame.winfo_exists())

    def test_banco_novo_pede_a_senha_do_administrador(self) -> None:
        self.assertEqual("Definir senha do administrador", self.app.first_access_button.cget("text"))
        self._entrar("admin", "admin")
        self.assertTrue(self._na_tela_de_login())
        self.assertIn("Defina primeiro a senha", self.app.login_error_label.cget("text"))

    def test_senha_com_espaco_entra_como_foi_definida(self) -> None:
        self.app.security_service.set_first_password("admin", " Torre 2026 ")
        self._entrar("admin", " Torre 2026 ")
        self.assertFalse(self.app.login_frame.winfo_exists())
        self.assertEqual("admin", self.app.security_service.current_operator()["name"])

    def test_tres_erros_mostram_a_espera(self) -> None:
        self.app.security_service.set_first_password("admin", "Torre#2026")
        for _ in range(3):
            self._entrar("admin", "errada")
        self.assertIn("Aguarde", self.app.login_error_label.cget("text"))
        self.assertTrue(self._na_tela_de_login())


if __name__ == "__main__":
    unittest.main()
