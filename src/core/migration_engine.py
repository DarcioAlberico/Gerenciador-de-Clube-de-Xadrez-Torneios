from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.database.migrations.legacy_migrations import LegacyMigrations

if TYPE_CHECKING:
    from src.core.database import Database

logger = logging.getLogger(__name__)

class MigrationEngine:
    """Motor central para gerenciar atualizações e esquemas de Banco de Dados."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def run_migrations(self, connection: sqlite3.Connection) -> None:
        """Verifica a versão atual do banco e roda as migrações em lote se necessário.

        RGS-29: cada versão roda na sua própria transação, junto com o
        `PRAGMA user_version`. Uma falha no meio desfaz a versão inteira: o
        banco fica na versão anterior, sem coluna pela metade, e a próxima
        abertura repete a migração do zero.
        """
        current_version = self.db._schema_user_version(connection)

        if current_version > self.db.SCHEMA_VERSION:
            raise RuntimeError(
                "Banco criado por uma versão mais nova do Albericus. "
                "Atualize o aplicativo antes de abrir este arquivo."
            )

        legacy = LegacyMigrations(self.db)
        migrations = legacy._schema_migrations()

        for target_version in range(current_version + 1, self.db.SCHEMA_VERSION + 1):
            migration = migrations.get(target_version)
            if migration is None:
                raise RuntimeError(f"Migração de banco ausente para a versão {target_version}.")

            def migrar_versao(conexao: sqlite3.Connection, migration=migration, versao=target_version) -> None:
                migration(conexao)
                conexao.execute(f"PRAGMA user_version = {versao}")

            self._em_transacao(connection, migrar_versao)
            logger.info("Banco atualizado para a versão %s", target_version)

        if current_version == self.db.SCHEMA_VERSION:
            self._em_transacao(connection, legacy._ensure_current_schema)

    def _em_transacao(
        self,
        connection: sqlite3.Connection,
        passo: Callable[[sqlite3.Connection], None],
    ) -> None:
        """Roda `passo` numa transação própria: grava tudo no fim, ou nada."""
        if connection is self.db._active_connection():
            # Dentro de `Database.transaction()` (restaurar backup no meio de
            # uma transação): um COMMIT aqui gravaria a transação de fora pela
            # metade. A versão vira SAVEPOINT dela.
            with self.db._savepoint(connection):
                passo(connection)
            return
        if connection.in_transaction:
            # Algo anterior (o CREATE TABLE inicial) deixou gravação pendente:
            # ela fecha antes, para não entrar junto com esta versão.
            connection.commit()
        # IMMEDIATE: reserva a escrita já na abertura, como `Database.transaction`.
        connection.execute("BEGIN IMMEDIATE")
        try:
            passo(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
