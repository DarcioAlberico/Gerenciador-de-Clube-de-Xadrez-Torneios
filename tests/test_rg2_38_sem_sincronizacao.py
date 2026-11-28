"""RG2-38 — a sincronização com dispositivos sai inteira (D5, decidida pelo dono em 2026-11-28).

Era meia funcionalidade: hash sem chave, segredo do dispositivo nunca
conferido, evento remoto gravado por fora do ``PairingService`` — e **todo**
evento de auditoria gravava uma linha em ``sync_outbox`` (416 pendentes no
banco real, com a sincronização desligada). *Subtract before you add*: sai a
fila, os dispositivos, a tela e o acoplamento com a auditoria.

O histórico das migrações (a v27 criava as tabelas) fica: é história. A v61
apaga as tabelas e as chaves de configuração de quem já as tinha.
"""
from __future__ import annotations

import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.core.database import Database
from tests.support.core_service_base import CoreServiceTestCase

RAIZ = Path(__file__).resolve().parents[1]
SIMBOLOS = re.compile(
    r"SyncService|sync_service|sync_outbox|apply_remote_event|register_device|revoke_device|"
    r"list_devices|sync_pending|local_device_id|sync_server_url|sync_enabled|ensure_local_device|"
    r"update_device_status|remote_rejected|outbox_rejected|sync_conflicts|SyncAuditMixin"
)
# A migração antiga cria as tabelas (v27) e a nova as apaga (v61): história, não funcionalidade.
HISTORIA = {RAIZ / "src" / "database" / "migrations" / "legacy_migrations.py", Path(__file__).resolve()}


def _tabelas(caminho: Path) -> set[str]:
    with closing(sqlite3.connect(caminho)) as conexao:
        return {linha[0] for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


class SemSincronizacaoTest(CoreServiceTestCase):
    def test_banco_novo_nao_tem_fila_nem_dispositivos(self) -> None:
        self.assertFalse({"sync_outbox", "devices"} & _tabelas(self.db.db_path))

    def test_auditar_nao_cria_fila(self) -> None:
        self.db.create_audit_event(action="result_updated", tournament_id=self.tournament_id)
        self.assertNotIn("sync_outbox", _tabelas(self.db.db_path))
        self.assertNotIn("local_device_id", self.db.get_app_settings())

    def test_nenhum_simbolo_de_sincronizacao_em_src_tests_e_scripts(self) -> None:
        achados = []
        for pasta in ("src", "tests", "scripts"):
            for arquivo in sorted((RAIZ / pasta).rglob("*.py")):
                if arquivo.resolve() in HISTORIA:
                    continue
                for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1):
                    if SIMBOLOS.search(linha):
                        achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()}")
        self.assertEqual([], achados)


class MigracaoV61Test(unittest.TestCase):
    def test_banco_antigo_perde_a_fila_e_as_chaves(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "albericus.db"
            Database(caminho, backup_dir=Path(pasta) / "backups")
            with closing(sqlite3.connect(caminho)) as conexao:
                conexao.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS devices (id INTEGER PRIMARY KEY, device_id TEXT);
                    CREATE TABLE IF NOT EXISTS sync_outbox (id INTEGER PRIMARY KEY, status TEXT);
                    INSERT INTO sync_outbox (status) VALUES ('pending'), ('pending');
                    INSERT OR REPLACE INTO app_settings (key, value, updated_at)
                        VALUES ('local_device_id', 'x', ''), ('sync_enabled', '1', ''), ('sync_server_url', 'http://s', '');
                    PRAGMA user_version = 60;
                    """
                )
            Database(caminho, backup_dir=Path(pasta) / "backups")
            self.assertFalse({"sync_outbox", "devices"} & _tabelas(caminho))
            with closing(sqlite3.connect(caminho)) as conexao:
                chaves = {linha[0] for linha in conexao.execute("SELECT key FROM app_settings")}
                versao = conexao.execute("PRAGMA user_version").fetchone()[0]
            self.assertFalse({"local_device_id", "sync_enabled", "sync_server_url"} & chaves)
            self.assertEqual(Database.SCHEMA_VERSION, versao)
            self.assertGreaterEqual(versao, 61)


if __name__ == "__main__":
    unittest.main()
