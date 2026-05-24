from __future__ import annotations

import logging
import sqlite3
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
        """Verifica a versão atual do banco e roda as migrações em lote se necessário."""
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
            
            migration(connection)
            connection.execute(f"PRAGMA user_version = {target_version}")
            logger.info("Banco atualizado para a versão %s", target_version)

        if current_version == self.db.SCHEMA_VERSION:
            legacy._ensure_current_schema(connection)
