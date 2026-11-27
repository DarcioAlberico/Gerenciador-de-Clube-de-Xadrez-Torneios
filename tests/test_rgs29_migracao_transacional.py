"""RGS-29: cada versão de migração grava junto com o `PRAGMA user_version`, ou nada.

Antes, o `ALTER TABLE` rodava em autocommit (`migration_engine.py`): uma falha
no meio da migração deixava colunas pela metade e a versão antiga, e a nova
tentativa tropeçava na coluna que já existia (ou pulava o dado que faltou).
"""

from __future__ import annotations

import ast
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from src.core.database import Database
from src.database.migrations import legacy_migrations
from src.database.migrations.legacy_migrations import LegacyMigrations


class MigracaoTransacionalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        base = Path(self._dir.name)
        self.db_path = base / "torneio.db"
        self.backup_dir = base / "backups"
        Database(self.db_path, backup_dir=self.backup_dir)
        self.versao_atual = Database.SCHEMA_VERSION
        self.versao_nova = Database.SCHEMA_VERSION + 1

    def _colunas(self, tabela: str) -> set[str]:
        with closing(sqlite3.connect(self.db_path)) as conexao:
            return {str(linha[1]) for linha in conexao.execute(f"PRAGMA table_info({tabela})")}

    def _tabelas(self) -> set[str]:
        with closing(sqlite3.connect(self.db_path)) as conexao:
            return {
                str(linha[0])
                for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }

    def _versao(self) -> int:
        with closing(sqlite3.connect(self.db_path)) as conexao:
            return int(conexao.execute("PRAGMA user_version").fetchone()[0])

    def _abrir_com_migracao(self, migracao) -> None:
        originais = LegacyMigrations._schema_migrations

        def migracoes(self_legacy):
            mapa = originais(self_legacy)
            mapa[self.versao_nova] = lambda conexao: migracao(self_legacy, conexao)
            return mapa

        with mock.patch.object(Database, "SCHEMA_VERSION", self.versao_nova), mock.patch.object(
            LegacyMigrations, "_schema_migrations", migracoes
        ):
            Database(self.db_path, backup_dir=self.backup_dir)

    def test_falha_no_meio_nao_deixa_coluna_nem_versao_nova_e_a_repeticao_funciona(self) -> None:
        def migracao_que_quebra(_legacy, conexao: sqlite3.Connection) -> None:
            conexao.execute("ALTER TABLE tournament_settings ADD COLUMN rgs29_a TEXT NOT NULL DEFAULT ''")
            conexao.execute("UPDATE tournament_settings SET rgs29_a = 'x'")
            raise RuntimeError("falha simulada no meio da migracao")

        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            self._abrir_com_migracao(migracao_que_quebra)

        self.assertEqual(self.versao_atual, self._versao())
        self.assertNotIn("rgs29_a", self._colunas("tournament_settings"))

        def migracao_boa(_legacy, conexao: sqlite3.Connection) -> None:
            # Sem guarda de "coluna ja existe": só passa se a tentativa anterior
            # não deixou nada para trás.
            conexao.execute("ALTER TABLE tournament_settings ADD COLUMN rgs29_a TEXT NOT NULL DEFAULT ''")

        self._abrir_com_migracao(migracao_boa)
        self.assertEqual(self.versao_nova, self._versao())
        self.assertIn("rgs29_a", self._colunas("tournament_settings"))

    def test_script_de_varias_instrucoes_tambem_e_desfeito(self) -> None:
        def migracao_com_script(_legacy, conexao: sqlite3.Connection) -> None:
            legacy_migrations._executar_script(
                conexao,
                """
                CREATE TABLE IF NOT EXISTS rgs29_t1 (id INTEGER PRIMARY KEY, nome TEXT DEFAULT 'a;b');
                CREATE TABLE IF NOT EXISTS rgs29_t2 (id INTEGER PRIMARY KEY);
                CREATE TRIGGER IF NOT EXISTS rgs29_gatilho AFTER INSERT ON rgs29_t1
                BEGIN
                    INSERT INTO rgs29_t2 (id) VALUES (NEW.id);
                END;
                INSERT INTO rgs29_t1 (id) VALUES (1);
                """,
            )
            raise RuntimeError("falha depois do script")

        with self.assertRaisesRegex(RuntimeError, "falha depois do script"):
            self._abrir_com_migracao(migracao_com_script)

        self.assertEqual(self.versao_atual, self._versao())
        self.assertFalse({"rgs29_t1", "rgs29_t2"} & self._tabelas())

    def test_script_executa_instrucoes_com_ponto_e_virgula_em_literal_e_gatilho(self) -> None:
        with closing(sqlite3.connect(":memory:")) as conexao:
            legacy_migrations._executar_script(
                conexao,
                """
                CREATE TABLE t1 (id INTEGER PRIMARY KEY, nome TEXT DEFAULT 'a;b');
                CREATE TABLE t2 (id INTEGER PRIMARY KEY); CREATE TABLE t3 (id INTEGER);
                CREATE TRIGGER g AFTER INSERT ON t1 BEGIN INSERT INTO t2 (id) VALUES (NEW.id); END;
                INSERT INTO t1 (id) VALUES (7);
                -- comentario final sem instrucao
                """,
            )
            self.assertEqual("a;b", conexao.execute("SELECT nome FROM t1").fetchone()[0])
            self.assertEqual(7, conexao.execute("SELECT id FROM t2").fetchone()[0])

    def test_migracoes_nao_usam_executescript(self) -> None:
        """`executescript` faz COMMIT implicito e quebraria a transacao da versao."""
        arvore = ast.parse(Path(legacy_migrations.__file__).read_text(encoding="utf-8"))
        chamadas = [
            no.lineno
            for no in ast.walk(arvore)
            if isinstance(no, ast.Attribute) and no.attr in {"executescript", "commit"}
        ]
        self.assertEqual([], chamadas)


if __name__ == "__main__":
    unittest.main()
