"""Testes da tela de login em duas faixas (F3.6) e da versão exibida.

A parte de versão é pura e roda sem janela. A parte de tela precisa da
``AlbericusApp`` **antes** do login — por isso não cabe em ``test_ui_layout``,
cujo ``setUp`` já entra no sistema.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tkinter import TclError
from unittest import mock

import customtkinter as ctk
import pytest

from src.core.database import Database
from src.core.version import APP_NAME, APP_SITE, APP_TAGLINE, APP_VERSION, app_title, version_label
from src.ui.app import AlbericusApp
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)


class VersaoTest(unittest.TestCase):
    """Sem Tk: a versão passou a ter fonte única (antes só existia no título)."""

    def test_titulo_usa_a_versao(self) -> None:
        self.assertIn(APP_VERSION, app_title())
        self.assertIn(APP_NAME, app_title())

    def test_rotulo_sem_schema(self) -> None:
        self.assertEqual(f"v{APP_VERSION}", version_label())

    def test_rotulo_com_schema_ajuda_o_suporte(self) -> None:
        rotulo = version_label(43)
        self.assertIn(f"v{APP_VERSION}", rotulo)
        self.assertIn("banco v43", rotulo)


@pytest.mark.gui
class LoginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        try:
            self.app = create_tk_window(lambda: AlbericusApp(db=self.db))
        except TclError as exc:  # pragma: no cover - ambiente sem display
            self.temp_dir.cleanup()
            self.skipTest(f"Tk indisponivel: {exc}")
        self.app.update()

    def tearDown(self) -> None:
        cancel_pending_callbacks(self.app)
        try:
            self.app.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()
        self.temp_dir.cleanup()

    def _rotulos(self) -> list[str]:
        return [
            str(w.cget("text"))
            for w in self._andar(self.app.login_frame)
            if isinstance(w, ctk.CTkLabel)
        ]

    def _botao(self, texto: str) -> ctk.CTkButton:
        for widget in self._andar(self.app.login_frame):
            if isinstance(widget, ctk.CTkButton) and texto in str(widget.cget("text")):
                return widget
        self.fail(f"botao {texto!r} nao encontrado")

    @classmethod
    def _andar(cls, widget):
        yield widget
        for filho in widget.winfo_children():
            yield from cls._andar(filho)

    # -- marca ------------------------------------------------------------

    def test_faixa_de_marca_mostra_nome_proposito_e_versao(self) -> None:
        rotulos = " | ".join(self._rotulos())
        self.assertIn(APP_NAME, rotulos)
        self.assertIn(APP_TAGLINE, rotulos)
        self.assertIn(f"v{APP_VERSION}", rotulos, "a versao tem de aparecer para o usuario")
        self.assertIn(APP_SITE, rotulos)

    def test_versao_do_banco_aparece_junto(self) -> None:
        rotulos = " | ".join(self._rotulos())
        self.assertIn(f"banco v{self.db.SCHEMA_VERSION}", rotulos)

    def test_layout_e_dividido_em_duas_colunas(self) -> None:
        """O aceite da F3.6: marca e formulário lado a lado, não empilhados."""
        colunas = {
            filho.grid_info().get("column")
            for filho in self.app.login_frame.winfo_children()
            if filho.grid_info()
        }
        self.assertEqual({0, 1}, colunas)

    # -- formulário -------------------------------------------------------

    def test_campos_vazios_avisam_sem_tentar_entrar(self) -> None:
        with mock.patch.object(self.app.security_service, "login") as tentativa:
            self._botao("Entrar").invoke()
            self.app.update()
        tentativa.assert_not_called()
        self.assertIn("Preencha", self.app.login_error_label.cget("text"))

    def test_credencial_invalida_avisa_e_limpa_a_senha(self) -> None:
        self.app.username_entry.insert(0, "ninguem")
        self.app.password_entry.insert(0, "errada")
        self._botao("Entrar").invoke()
        self.app.update()
        self.assertIn("inválidas", self.app.login_error_label.cget("text"))
        self.assertEqual("", self.app.password_entry.get(), "senha errada nao pode ficar no campo")
        self.assertTrue(self.app.login_frame.winfo_exists(), "a tela de login continua")

    def test_login_valido_entra_e_abre_a_tela_inicial(self) -> None:
        self.app.username_entry.insert(0, "admin")
        self.app.password_entry.insert(0, "admin")
        self._botao("Entrar").invoke()
        self.app.update()
        self.assertFalse(self.app.login_frame.winfo_exists(), "a tela de login sai")
        self.assertEqual("show_home", self.app.navigator.current)

    def test_enter_no_usuario_pula_para_a_senha(self) -> None:
        self.app.username_entry.focus_force()
        self.app.username_entry.event_generate("<Return>", when="now")
        # O foco recai no Entry interno do CTkEntry, entao a comparacao e pelo
        # caminho Tk: o widget focado tem de estar DENTRO do campo de senha.
        self.assertTrue(
            str(self.app.focus_lastfor()).startswith(str(self.app.password_entry)),
            f"foco ficou em {self.app.focus_lastfor()}",
        )

    # -- primeiro acesso --------------------------------------------------

    def test_ajuda_de_primeiro_acesso_orienta_sem_dar_senha(self) -> None:
        with mock.patch("src.ui.app.alert_dialog") as dialogo:
            self._botao("Primeiro acesso").invoke()
        dialogo.assert_called_once()
        texto = " ".join(str(arg) for arg in dialogo.call_args.args).lower()
        self.assertIn("responsável pelo clube", texto)
        self.assertIn("gerenciar usuários", texto, "tem de dizer ONDE se cadastra um operador")
        # Nao pode entregar credencial: senha na tela de login e convite a nunca
        # troca-la. ("administrador" e permitido; "admin/admin" nao.)
        for vazamento in ("admin/admin", "admin / admin", "senha padrão", "senha padrao"):
            self.assertNotIn(vazamento, texto, f"nao pode revelar credencial ({vazamento})")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
