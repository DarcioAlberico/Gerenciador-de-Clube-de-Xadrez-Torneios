
**Regra de Ouro:**
- `models/` → nunca contém lógica.
- `services/` → nunca toca na UI. Recebe dados, aplica regras, retorna structs/dicts.
- `ui/screens/` → nunca calcula classificação, emparceira ou gera PDF. Apenas chama service e renderiza.

## 🗺️ Roadmap de Implementação (Fases)

| Fase | Foco | Entregas Principais | Status |
|------|------|---------------------|--------|
| 1 | Base & MVP | BD, Membros, Torneio (Suíço básico), Dashboard, Permissões, Exportação | ✅ Implementado |
| 2 | Clube Operacional | Financeiro, Agenda, Inventário, Comunicação básica, Relatórios fixos | 🟡 Em progresso |
| 3 | Ensino & Avanço | Módulo 6 completo (PDF aluno/professor, histórico, coleções), DRE financeiro, Auditoria completa, PGN import | 🔜 Próximo corte |
| 4 | Integrações & Escala | Lichess/Chess.com API, WhatsApp/Email real, Backup nuvem, PyInstaller, Temas claros/escuros | 🔜 Futuro |

## 🧩 Detalhamento dos 10 Módulos

### 1. 📊 Dashboard
- **Arquivos:** `ui/screens/dashboard_screen.py`, `services/dashboard_service.py`
- **Funcionalidades:** Painel operacional com membros ativos, eventos do dia, alertas financeiros/comunicação, torneios recentes, atalhos rápidos, indicador de backup.
- **Regra:** Apenas leitura. Consome caches dos outros módulos. Atualiza a cada 30s ou em eventos.
- **Dependências:** Todos os módulos (leituras agregadas).

### 2. 👥 Membros
- **Arquivos:** `models/member.py`, `services/member_service.py`, `ui/screens/members/list.py`, `ui/screens/members/profile.py`, `ui/screens/members/register.py`, `ui/screens/members/transfers.py`
- **Funcionalidades:** CRUD, filtros avançados, responsáveis, rating interno, categorias/planos, frequência, títulos/conquistas, transferências formais, desligamento (soft delete preservando histórico de torneios).
- **Regra:** Exclusão remove vínculos dependentes, mas mantém `member_id` nulo em inscrições passadas. Rating só atualiza pós-torneio.
- **Dependências:** Torneios, Financeiro, Ensino, Inventário.

### 3. 🏆 Torneios & Competições
- **Arquivos:**
  - `models/tournament.py`, `models/round.py`, `models/pairing.py`, `models/player_round_stats.py`
  - `services/tournament_service.py`, `services/pairing_service.py`, `services/standings_service.py`
  - `ui/screens/tournaments/list.py`, `ui/screens/tournaments/bracket.py`, `ui/screens/tournaments/results.py`, `ui/screens/tournaments/standings.py`, `ui/screens/tournaments/certificates.py`
- **Funcionalidades:** Criação, formatos (Suíço, Rodízio, Eliminatório), inscrições, emparceiramento automático, lançamento de resultados, tabela de classificação com desempates (Buchholz, SB, Confronto), atualização de rating, diplomas, export para federações.
- **Status atual:** exportação Chess-Results/TRF16 implementada para torneios individuais e por equipes, com validação local de dados oficiais. Upload direto para Chess-Results fica fora do escopo até existir API pública utilizável.
- **Regra de Emparceiramento:** Penalidade por repetição, equilíbrio de cores, limite de 1 bye/torneio, transação atômica ao fechar rodada.
- **Dependências:** Membros, Comunicação, Relatórios, Financeiro (taxas).

### 4. 📅 Agenda & Eventos
- **Arquivos:** `models/event.py`, `services/event_service.py`, `ui/screens/events/calendar.py`, `ui/screens/events/form.py`, `ui/screens/events/rsvp.py`, `ui/screens/events/rooms.py`
- **Funcionalidades:** Calendário mensal, criação de sessões/aulas/palestras, RSVP, reserva de salas, convites exportáveis, eventos recorrentes.
- **Regra:** Bloqueio de conflito de sala/instrutor. Confirmação automática por e-mail/portal.
- **Dependências:** Membros, Comunicação, Inventário (espaços), Ensino.

### 5. 💰 Financeiro
- **Arquivos:** `models/finance.py`, `services/finance_billing.py`, `services/finance_ledger.py`, `ui/screens/finance/dashboard.py`, `ui/screens/finance/billing.py`, `ui/screens/finance/receipts.py`, `ui/screens/finance/dre.py`
- **Funcionalidades:** Planos recorrentes, geração em lote de mensalidades, régua de cobrança, taxas de torneio, lançamento de receitas/despesas, patrocinadores, premiação, recibos, DRE simplificado.
- **Regra:** Prevenção de duplicidade, imutabilidade de lançamentos fechados, auditoria de estornos, separação clara caixa/competência.
- **Dependências:** Membros, Torneios, Eventos, Relatórios.

### 6. 📚 Ensino & Treinamento (Biblioteca Pedagógica)
- **Arquivos:** `models/education.py`, `services/exercise_catalog.py`, `services/training_lists.py`, `services/pdf_generator.py`, `ui/screens/education/library.py`, `ui/screens/education/collections.py`, `ui/screens/education/usage_history.py`
- **Funcionalidades:** Acervo (posições FEN/PGN, textos, partidas, quizzes), metadados (fase, tema, nível, tags), coleções/apostilas, geração de PDF (aluno sem gabarito / professor com solução), histórico de uso por turma, alerta de repetição (183 dias), importação PGN futura.
- **Regra:** Contexto de dificuldade por turma. Exportação reusa infraestrutura de relatórios. PGN importado em fase 3 com `python-chess`.
- **Dependências:** Membros (tentativas), Eventos (aulas), Dashboard.

### 7. 📦 Patrimônio & Material
- **Arquivos:** `models/asset.py`, `services/asset_inventory.py`, `services/asset_loans.py`, `ui/screens/assets/catalog.py`, `ui/screens/assets/loans.py`, `ui/screens/assets/maintenance.py`, `ui/screens/assets/depreciation.py`
- **Funcionalidades:** Cadastro de peças/tabuleiros/relógios/livros, empréstimo/devolução, manutenção, compras, layout de salas, relatório patrimonial com depreciação simples.
- **Regra:** Cálculo automático de disponibilidade. Alerta de atraso na devolução. Histórico de condição.
- **Dependências:** Membros, Eventos, Financeiro.

### 8. 📢 Comunicação
- **Arquivos:** `models/communication.py`, `services/message_service.py`, `services/portal_service.py`, `ui/screens/messages/broadcast.py`, `ui/screens/messages/templates.py`, `ui/screens/messages/inbox.py`, `ui/screens/portal/publisher.py`
- **Funcionalidades:** Envio em massa (email/WhatsApp/SMS), templates, mural interno, agendamento para redes, caixa de entrada, métricas de engajamento, portal HTML estático para clube/turma.
- **Regra:** Logs de envio e status (entregue/lido/falhou). Portal gerado estaticamente via `ExportService`. Integrações externas opcionais e configuráveis.
- **Dependências:** Todos os módulos (gatilhos de alertas).

### 9. 📈 Relatórios & Estatísticas
- **Arquivos:** `services/report_engine.py`, `ui/screens/reports/builder.py`, `ui/screens/reports/scheduler.py`
- **Funcionalidades:** Crescimento de membros, desempenho em torneios, DRE financeiro, frequência, progresso pedagógico, curvas de rating, exportação agendada, pacotes por turma.
- **Regra:** Consultas parametrizadas, cache de resultados pesados, permissão de exportação validada, logs de geração.
- **Dependências:** Leitura cruzada de todos os módulos.

### 10. ⚙️ Configurações & Segurança
- **Arquivos:** `config/settings.py`, `config/permissions.py`, `services/security_service.py`, `services/backup_service.py`, `ui/screens/settings/club.py`, `ui/screens/settings/roles.py`, `ui/screens/settings/backup.py`, `ui/screens/settings/audit.py`
- **Funcionalidades:** Dados do clube, matriz de perfis (Admin, Arbitragem, Professor, Assistente, Consulta), bloqueio real via `SecurityService.require_permission()`, auditoria de alterações/backups, retenção configurável, documentos do clube, identidade visual.
- **Regra:** Negativas de acesso geram `permission_denied` na auditoria. Barra de status mostra operador/perfil ativo. Backup criptografado e versionado.
- **Dependências:** Global.

## 🛡️ Camadas Transversais (Cross-Cutting)

| Camada | Arquivo(s) | Função |
|--------|------------|--------|
| Banco de Dados | `database/connection.py`, `database/schema.py`, `database/migrations/v*.sql` | SQLite com FK, transações atômicas, migrações automáticas, versionamento de schema. |
| Permissões | `config/permissions.py`, `services/security_service.py` | Matriz RBAC, validação em serviço, desabilitação UI pré-clique, auditoria. |
| Exportação | `utils/export_csv.py`, `utils/export_excel.py`, `utils/export_pdf.py` | Reuso de templates, geração de listas sem/com gabarito, relatórios federativos. |
| Logs | `utils/logger.py`, `logs/app.log` | Eventos técnicos e de negócio, rotação, não quebra o app em falha de log. |
| Testes | `tests/test_pairing.py`, `tests/test_finance.py`, `tests/test_export.py` | Unitários por serviço, integração DB, mocks de UI, cobertura mínima 80%. |
| Empacotamento | `build.spec`, `requirements.txt`, `app.py` | PyInstaller `--onefile --windowed`, inclusão de `data/`, `config/`, `templates/`. |

## ✅ Diretrizes de Desenvolvimento (Para Manter a Modularidade)

- **Nunca misture camadas:** `ui` chama `service`, `service` usa `model/repository`. Proibido SQL ou regra de negócio na UI.
- **Um arquivo, uma responsabilidade:** Se `tournament_service.py` passar de 400 linhas, quebre em `tournament_crud_service.py`, `pairing_service.py`, `standings_service.py`.
- **Injeção leve de dependências:** Passe serviços instanciados para as telas. Evite imports cíclicos.
- **Eventos síncronos para UI:** Use `after()` do Tkinter ou filas internas para atualizar dashboard sem travar a interface.
- **Validação dupla:** UI valida formato, serviço valida regras de negócio e integridade.
- **Teste antes de integrar:** Cada módulo deve ter `tests/test_<modulo>.py` rodando isoladamente antes de ser ligado à UI principal.

## 🚀 Próximos Passos Imediatos

1. **Validar a estrutura de pastas** no repositório atual e criar os arquivos vazios conforme o mapeamento.
2. **Implementar `SecurityService` centralizado** antes de qualquer nova tela, garantindo que permissões sejam validadas por padrão.
3. **Consolidar o Módulo 6** (Fase 2) com geração de PDF dual (aluno/professor) e alerta de repetição de 183 dias, conforme já parcialmente implementado.
4. **Criar suite de testes** para emparceiramento cobrindo os cenários de penalidade, cores e byes descritos no `PASSO_A_PASSO`.
5. **Validar TRF16 em ambiente real Swiss-Manager/Chess-Results** usando torneios individuais e por equipes exportados pelo Albericus.
6. **Documentar migrações** (`database/migrations/`) para garantir que atualizações de schema não quebrem bases existentes.

> Este plano está pronto para ser adotado como documento mestre de arquitetura. Se desejar, posso gerar: o template base de cada arquivo, o script de migração v16 para v17, a matriz completa de permissões por perfil em JSON/Python, ou um exemplo funcional de `pairing_service.py`. Basta indicar por onde prefere começar. ♟️
