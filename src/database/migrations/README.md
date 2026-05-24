# Banco de Dados: Arquitetura de Migrações (Schema)

Este diretório gerencia o ciclo de vida e a evolução estrutural do banco de dados do **Albericus**.

## Como o SQLite é versionado no Albericus
Utilizamos o `PRAGMA user_version` nativo do SQLite para rastrear a versão do banco. 
Quando o aplicativo inicia, o motor de migração compara a versão do arquivo `.db` com a constante `SCHEMA_VERSION` definida em `src/core/database.py`.
Se `user_version < SCHEMA_VERSION`, o sistema roda de forma sequencial os scripts necessários para alcançar a versão alvo.

## Como criar uma nova migração (Ex: Versão 22)

Sempre que você precisar adicionar uma nova tabela, coluna ou índice, siga os passos abaixo:

1. **Aumente a Versão Oficial**:
   Abra `src/core/database.py` e altere:
   ```python
   SCHEMA_VERSION = 22
   ```

2. **Crie a Rotina de Migração**:
   No arquivo `legacy_migrations.py` (ou em um novo arquivo de migração dentro desta pasta), registre o método da nova versão:
   ```python
   def _migrate_to_v22(self, connection: sqlite3.Connection) -> None:
       connection.execute("ALTER TABLE members ADD COLUMN new_feature TEXT DEFAULT ''")
   ```

3. **Mapeie a Migração no Motor**:
   No método `_schema_migrations` dentro de `legacy_migrations.py`, adicione a nova chave ao dicionário:
   ```python
   def _schema_migrations(self) -> dict[int, Callable[[sqlite3.Connection], None]]:
       return {
           # ... legados ...
           21: self._migrate_to_v21,
           22: self._migrate_to_v22, # Sua nova migração
       }
   ```

4. **Atualize o Script de Inicialização Rápida (Opcional)**:
   Se você adicionou uma tabela inteira nova, adicione o `CREATE TABLE` no grande script de `_create_tables` do `database.py`. Isso garante que novos bancos de dados nasçam já com a tabela, evitando rodar o `ALTER` desnecessariamente. Se fizer isso, adicione o teste em `_ensure_current_schema`.

## Atenção ao Backup!
Sempre que uma migração estrutural for detectada, o `MigrationEngine` tentará executar um backup automático na pasta `.albericus/backups/` antes de aplicar qualquer `ALTER TABLE`. Certifique-se de que suas querys em `_migrate_to_vX` são seguras e retro-compatíveis.
