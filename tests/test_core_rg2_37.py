"""RG2-37 — contas do aplicativo: sem senha padrão, sem ``strip``, papel válido, atraso e auditoria.

Banco novo nascia com ``admin``/``admin``, sem troca obrigatória. A tela de
login fazia ``strip()`` na senha e o cadastro não — senha com espaço na ponta
nunca entrava. Papel não era validado; não havia atraso depois de errar, e o
login falho não ficava na auditoria.

Banco **existente** não é marcado: o banco real só tem ``admin``, e marcar sem
o fluxo trancaria o dono fora (R10, objeção 9).
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from src.core.database import Database
from src.services.constants import AppError
from src.services.security_service import SecurityService


class _BancoNovo(unittest.TestCase):
    def setUp(self) -> None:
        self.pasta = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.pasta.name) / "albericus.db", backup_dir=Path(self.pasta.name) / "b")
        self.seguranca = SecurityService(self.db)

    def tearDown(self) -> None:
        self.pasta.cleanup()


class PrimeiroAcessoTest(_BancoNovo):
    def test_banco_novo_nao_entra_com_admin_admin(self) -> None:
        self.assertTrue(self.seguranca.needs_first_password())
        self.assertFalse(self.seguranca.login("admin", "admin"))
        self.assertFalse(self.seguranca.login("admin", ""))

    def test_definir_a_senha_libera_o_login_uma_vez_so(self) -> None:
        self.seguranca.set_first_password("admin", "Torre#2026")
        self.assertFalse(self.seguranca.needs_first_password())
        self.assertTrue(self.seguranca.login("admin", "Torre#2026"))
        with self.assertRaises(AppError):
            self.seguranca.set_first_password("admin", "outra")

    def test_senha_vazia_no_primeiro_acesso_e_recusada(self) -> None:
        with self.assertRaises(AppError):
            self.seguranca.set_first_password("admin", "")


class BancoExistenteTest(unittest.TestCase):
    def test_banco_migrado_continua_entrando_com_a_senha_que_tinha(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "albericus.db"
            Database(caminho, backup_dir=Path(pasta) / "b")
            with closing(sqlite3.connect(caminho)) as conexao:
                conexao.execute(
                    "UPDATE users SET password_hash = ? WHERE username = 'admin'",
                    (SecurityService._hash_password("admin"),),
                )
                conexao.commit()
            seguranca = SecurityService(Database(caminho, backup_dir=Path(pasta) / "b"))
            self.assertFalse(seguranca.needs_first_password())
            self.assertTrue(seguranca.login("admin", "admin"))


class SenhaEPapelTest(_BancoNovo):
    def setUp(self) -> None:
        super().setUp()
        self.seguranca.set_first_password("admin", "Torre#2026")

    def test_senha_com_espaco_na_ponta_entra_como_foi_cadastrada(self) -> None:
        self.seguranca.create_user("x", " abc ", "viewer")
        self.assertTrue(self.seguranca.login("x", " abc "))
        self.assertFalse(self.seguranca.login("x", "abc"))

    def test_papel_inexistente_e_recusado(self) -> None:
        with self.assertRaisesRegex(AppError, "Papel"):
            self.seguranca.create_user("y", "abc", "chefe")

    def test_trocar_a_senha_confere_a_atual(self) -> None:
        with self.assertRaises(AppError):
            self.seguranca.change_password("admin", "errada", "Nova#1")
        self.seguranca.change_password("admin", "Torre#2026", "Nova#1")
        self.assertTrue(self.seguranca.login("admin", "Nova#1"))


class AtrasoEAuditoriaTest(_BancoNovo):
    def setUp(self) -> None:
        super().setUp()
        self.seguranca.set_first_password("admin", "Torre#2026")

    def test_login_falho_fica_na_auditoria(self) -> None:
        self.assertFalse(self.seguranca.login("admin", "errada"))
        (registro,) = self.db.list_audit_logs(action="login_failed")
        self.assertIn("admin", registro["description"])
        self.assertNotIn("errada", registro["description"])

    def test_tres_erros_pedem_espera_crescente_sem_travar_a_tela(self) -> None:
        agora = [1000.0]
        with mock.patch("src.services.security_service.monotonic", side_effect=lambda: agora[0]):
            for _ in range(3):
                self.assertFalse(self.seguranca.login("admin", "errada"))
            espera = self.seguranca.login_wait_seconds("admin")
            self.assertGreater(espera, 0)
            self.assertFalse(self.seguranca.login("admin", "Torre#2026"), "durante a espera nem a certa entra")
            agora[0] += espera + 1
            self.assertTrue(self.seguranca.login("admin", "Torre#2026"))
            self.assertEqual(0, self.seguranca.login_wait_seconds("admin"))


if __name__ == "__main__":
    unittest.main()
