# Spec e Roadmap - Painel do Árbitro

> Documento executivo para evoluir o fluxo operacional de arbitragem do
> Albericus em torneios presenciais com mais de 100 jogadores.
>
> Revisão: 2026-07-29 (auditoria arbitral completa dos módulos de torneio;
> novos EPICs F a J na seção 5 e Sprints 7 a 12 na seção 7).

## 1. Objetivo

O Painel do Árbitro deve funcionar como centro de comando do torneio. A tela
precisa mostrar exceções, indicar a próxima ação correta e reduzir navegação
durante chamada, lançamento de resultados, fechamento de rodada e publicação.

Meta operacional:

- operar torneios individuais com 100 a 200 jogadores sem degradação perceptivel;
- localizar mesas pendentes em até 2 cliques;
- lançar resultados sequenciais apenas com teclado;
- impedir fechamento quando houver pendência bloqueante;
- manter o desktop e o SQLite local como autoridade do torneio.

## 2. Princípios

1. O painel orienta a decisão; não decide pelo árbitro.
2. QR, relógio, sincronização e portal live são auxiliares.
3. Ação crítica continua passando pelos serviços existentes, com auditoria e
   backup quando aplicável.
4. O fluxo principal precisa funcionar offline.
5. Documentos impressos continuam necessários para contingência presencial.
6. Ganho operacional deve ser medido em torneios simulados com pelo menos 120
   jogadores.

## 3. Baseline Validado

### 3.1 Núcleo existente

Já existem:

- geração e pré-visualização de rodadas;
- fechamento auditavel;
- snapshots de emparceiramento e classificação;
- chamada inicial com presentes e ausentes;
- lançamento rápido por botões e atalhos `1`, `0`, `-`, `Delete` e `Enter`;
- seleção automática da primeira mesa sem resultado;
- fila QR com aprovação ou rejeição;
- pendências de sincronização e alertas de relógio;
- correções auditadas;
- publicação HTML e portal live;
- validação e exportação TRF16;
- TRF25 mantido como formato em evolução;
- motor Gacrux (Otto Milvang, homologado FIDE) como padrão de emparceiramento
  (`pairing_system = gacrux_swiss`) e de desempates (`tiebreak_engine = gacrux`,
  com adversário virtual FIDE e regras por data de vigência), com fallback para
  o motor próprio `albericus-swiss-1`;
- byes solicitados F/H/Z, W.O. (`1F-0F`, `0F-1F`, `0F-0F`), pareamentos
  proibidos manuais (registro 260), aceleração Haley/custom, ajustes de pontos
  (`point_adjustments`, registro 299) e diagnósticos de pareamento com prova de
  otimalidade em campos pequenos.

### 3.2 Benchmark atual

Benchmarks locais:

| Operação | Resultado |
|---|---:|
| Inserir 801 jogadores | 3,8451 s |
| Pré-visualizar primeira rodada com 801 jogadores | 0,0309 s |
| Gerar primeira rodada com 801 jogadores | 0,0910 s |
| Carregar dashboard arbitral com 801 jogadores | 0,0216 s |
| Emparceiramentos gerados para 801 jogadores | 401 |
| Mesas pendentes para 801 jogadores | 400 + 1 bye |
| Mesas pendentes exibidas inline | primeiras 20 |
| Gerar 60 súmulas PDF para 121 jogadores | 0,1075 s |
| Gerar 400 súmulas PDF para 801 jogadores | 0,4028 s |
| Gerar lista de chamada PDF para 801 jogadores | 0,1055 s / 22 páginas |
| Gerar mural PDF com QR para 60 mesas | 2,4005 s / 4 páginas |
| Gerar mural PDF com QR para 400 mesas + 1 bye | 15,4840 s / 27 páginas |
| Gerar 200 cartões de mesa PDF sem QR | 0,0811 s / 50 páginas |
| Gerar 60 cartões de mesa PDF com QR | 2,6519 s / 15 páginas |
| Calcular tabela cruzada com 801 jogadores / 1 rodada | 0,0473 s |
| Exportar tabela cruzada HTML com 801 jogadores / 1 rodada | 0,0661 s |
| Filtrar 1.000 pendências por decisão e mesa | 1,4220 ms |
| Lançar resultado inline com recarga do painel / 801 jogadores | 49,7582 ms |
| Carregar dashboard com limite inline de 50 mesas / 801 jogadores | 22,2493 ms médio / 25,7239 ms máximo |
| Carregar dashboard com relógio e limite inline de 50 mesas / 801 jogadores | 24,7673 ms médio / 29,9365 ms máximo |
| Calcular tabela cruzada por equipes / 801 jogadores, 200 equipes, 400 tabuleiros | 125,4967 ms médio / 155,0487 ms máximo |
| Calcular resumo de taxas de rating / 801 jogadores | 11,5755 ms médio / 16,5495 ms máximo |
| Exportar taxas de rating XLSX / 801 jogadores | 409,6342 ms |
| Pré-visualizar atualização oficial / 801 jogadores | 877,1279 ms médio / 934,8669 ms máximo |
| Confirmar atualização oficial / 700 alterações | 4.249,0223 ms |
| Piloto automatizado: carregar painel / 801 jogadores | 23,0215 ms |
| Piloto automatizado: lançar resultado e recarregar painel / 801 jogadores | 49,4234 ms médio |
| Piloto automatizado: mural PDF com QR em lote / 400 mesas | 3,7016 s / 27 páginas |
| Piloto automatizado: criar backup final / 801 jogadores | 19,6087 ms / 4.890.624 bytes |
| Piloto automatizado: restaurar em segunda instalação / 801 jogadores | 699,9135 ms / 1 rodada e 401 mesas |
| Piloto automatizado: continuidade local com rede bloqueada | 860,8958 ms / fluxo crítico validado |
| Piloto automatizado: rajada QR concorrente | 2.846,3054 ms / 20 envios recebidos e aprovados |
| Piloto automatizado: inscrição de última hora / 801 + 1 jogadores | 117,0289 ms / histórico e prévia validados |
| Piloto automatizado: importar base oficial FIDE local | 146,0958 ms / 700 registros |
| Piloto automatizado: comparar ratings oficiais antes da rodada 1 | 882,3479 ms / sem persistir |
| Piloto automatizado: confirmar correções oficiais selecionadas | 4.325,6951 ms / 700 alterações |
| Piloto automatizado: localizar e lançar mesa 400 pelo painel | 73,5168 ms / fora do recorte inline |

O gargalo prioritário não é processamento. E reduzir cliques, troca de tela e
conferência manual.

## 4. Estado da Interface

### 4.1 Entregue nesta iteração

| ID | Entrega | Status |
|---|---|---|
| UX-01 | Cards clicáveis para rodadas, pendentes, byes, ausentes e correções | Concluído |
| UX-02 | Botão de próximo passo recomendado | Concluído |
| UX-03 | Alertas operacionais com cor por severidade | Concluído |
| UX-04 | Ações agrupadas em Rodada, Configuração arbitral e Publicação | Concluído |
| UX-05 | Auto-refresh opcional do painel com intervalo configurável | Concluído |
| UX-06 | Lista inline configurável entre 10 e 50 mesas aguardando resultado | Concluído |
| UX-07 | Central de pendências com primeira linha pré-selecionada | Concluído |
| UX-08 | Central de pendências com cor por severidade e número legível da rodada | Concluído |
| UX-09 | Chamada inicial com busca e 14 linhas visíveis | Concluído |
| DOC-01 | Súmula de mesa PDF individual e por equipes | Concluído |
| DOC-02 | Folha de mural PDF com QR por mesa aberta | Concluído |
| DOC-03 | Lista de chamada PDF por ranking inicial | Concluído |
| DOC-04 | Cartões de mesa PDF por intervalo com QR opcional | Concluído |
| CLS-01 | Tabela cruzada individual com quatro formatos | Concluído |
| CLS-02 | Tabela cruzada por equipes com detalhe de tabuleiros | Concluído |
| PNL-01 | Filtros, busca e contador na Central de pendências | Concluído |
| PNL-02 | Lançamento inline de resultados no Painel do árbitro | Concluído |
| PNL-03 | Relógio local da rodada no Painel do árbitro | Concluído |
| PNL-04 | Preferências operacionais persistidas no Painel do árbitro | Concluído |
| FED-01 | Relatório de taxas de rating por base oficial | Concluído |
| FED-02 | Pré-visualização e confirmação da atualização oficial | Concluído |

Arquivos centrais:

- `src/ui/screens/pairings.py`
- `src/services/pairing_service.py`
- `src/ui/app.py`

### 4.2 Fluxo recomendado atual

Antes da primeira rodada:

1. Abrir `Rodadas`.
2. Usar a busca da chamada inicial.
3. Marcar somente ausentes.
4. Pré-visualizar e gerar a rodada.

Durante a rodada:

1. Abrir `Painel do arbitro`.
2. Conferir o próximo passo recomendado.
3. Ajustar auto-refresh, intervalo e quantidade de mesas inline conforme a operação.
4. Lançar resultados pela lista inline com botões ou teclado.
5. Resolver QR, sync e relógio na `Central de pendencias`.
6. Fechar somente quando o painel indicar que a rodada está pronta.

### 4.3 Aprofundamento 2026-06-02 (UX + docs)

Iteração net-new sobre o painel já completo, partindo do gancho da seção 10
(novo requisito operacional). Quatro entregas:

| ID | Entrega | Status |
|---|---|---|
| UX-10 | Alertas operacionais **clicáveis**: cada alerta pula ao contexto exato (pendências bloqueantes, fechar rodada, aprovar QR, ausentes, correções, prévia) | Concluído |
| UX-11 | **Barra de progresso da rodada** no topo do painel (`X/N mesas resolvidas (Y%)`), atualizada com o auto-refresh | Concluído |
| DOC-05 | **Pacote da rodada** em um clique: mural + súmulas + cartões numa pasta (`ExportService.export_round_package`), isolando erros | Concluído |
| DOC-06 | **Ata final do torneio** (`ExportService.export_tournament_minutes`): documento único de encerramento (dados, classificação final, premiação, taxas, árbitros e assinaturas) | Concluído |

Implementação:

- `individual_round_dashboard_metrics`/`team_round_dashboard_metrics` passam a
  expor `total_results`/`resolved_results`; `arbitration_dashboard` calcula
  `round_progress_percent` e devolve `alerts_detailed` (texto + severidade +
  ação), mantendo `alerts` (strings) em sincronia para retrocompatibilidade;
- o painel (`pairings.py`) renderiza alertas como botões-link que disparam a
  ação certa e desenha a barra de progresso; novos botões `Pacote da rodada
  (PDF)` e `Ata final (PDF)` no grupo Publicação;
- `export_round_package` reaproveita mural/sumulas/cartoes existentes;
  `export_tournament_minutes` compõe as secoes já existentes (classificação,
  premiação, taxas) com cabeçalho e árbitros;
- `Ata final` também disponível no hub de Relatórios (CSV/XLSX/PDF);
- 6 testes novos (métricas puras de progresso, alertas estruturados, progresso
  após lançamento, pacote da rodada e ata); gate completo verde.

### 4.4 Ideias net-new 2026-06-02 (segunda leva)

| ID | Entrega | Status |
|---|---|---|
| DOC-07 | **Ata por categoria**: seção "Vencedores por categoria" (top 3 de cada categoria) na ata final | Concluído |
| DOC-08 | **Boletim/press-release da rodada** (`ExportService.export_round_bulletin`): cabeçalho + resultados + classificação (top 10) + destaques (líder, decisivas/empates, maior zebra) | Concluído |
| UX-12 | **Checklist de fechamento** (`PairingService.closing_checklist`): itens com OK/X e ação por item; dialogo no painel com `Fechar rodada` habilitado só quando tudo está OK | Concluído |
| DOC-09 | **Pacote da rodada para equipes**: `export_round_package` ciente de equipes (mural = confrontos, súmulas por tabuleiro, cartões pelo total de tabuleiros de `team_boards`) | Concluído |

Implementação:

- `_category_winners_section` agrupa `pairing_service.standings` por `category`
  (individual); entra na ata e protege contra torneios sem categorias;
- `_round_bulletin_sections` reaproveita `_pairings_section` e o layout da
  classificação (top 10); `_bulletin_highlights_section` calcula os destaques a
  partir dos resultados/ratings da rodada;
- `closing_checklist` deriva do `arbitration_dashboard` e reaproveita o mapa de
  ações dos alertas clicáveis; o painel ganhou os botões `Checklist de
  fechamento` (grupo Rodada) e `Boletim da rodada (PDF)` (grupo Publicação);
- `export_round_package` conta os tabuleiros de equipes por `list_team_boards`
  (os tabuleiros ficam fora da tabela `pairings`), gerando cartões corretos;
- 6 testes novos; gate completo verde (429 passed). Sem mudança de schema.

### 4.5 Ideias net-new 2026-06-02 (terceira leva)

| ID | Entrega | Status |
|---|---|---|
| DOC-10 | **Poster/diploma do pódio** (`ExportService.export_podium`): A4 com top 3 (jogadores ou equipes) + campeões por categoria | Concluído |
| DOC-11 | **Boletim da rodada pelo hub de Relatórios**, escolhendo a rodada (reusa o seletor de rodada existente) | Concluído |
| UX-13 | **Checklist de fechamento especifico para equipes**: item de escalacoes/ordem de tabuleiro via `validate_roster_policy` | Concluído |

Implementação:

- `_podium_data` reúne top 3 (`standings`/`team_standings`) + campeões por
  categoria; `_write_podium_poster_pdf` desenha o pôster A4 com `reportlab`;
  opção `Podio (poster)` no hub (PDF) e botão `Podio (PDF)` no painel;
- o hub ganhou `Boletim da rodada` ligado ao seletor de rodada (além do botão do
  painel, que usa a rodada atual);
- `closing_checklist` detecta equipes e acrescenta o item de escalações
  (`TeamService.validate_roster_policy`, import lazy para evitar ciclo); o
  dialogo do painel mapeia a ação `lineups` para a tela de Equipes;
- 3 testes novos (dados do pódio, geração do PDF, checklist de equipes com
  `lineups`); gate completo verde (432 passed). Sem mudança de schema.

## 5. Requisitos Pendentes

### EPIC A - Documentos operacionais impressos

Prioridade: muito alta.

#### DOC-01 - Súmula de mesa PDF

Status: concluído em 2026-05-31.

Problema:

- o sistema não gerava a folha física de anotação por tabuleiro.

Escopo:

- criar `ExportService.export_scoresheets(round_id, file_path)`;
- gerar uma súmula por mesa individual;
- não gerar súmula para bye;
- incluir torneio, rodada, mesa, nomes, ratings, IDs oficiais, clubes, campo de
  resultado, grade de lances e assinaturas;
- em torneio por equipes, gerar uma súmula por tabuleiro do match.

Critérios de aceite:

- [x] rodada com 121 jogadores gera PDF em menos de 5 segundos;
- [x] PDF abre corretamente;
- [x] bye não gera página inútil;
- [x] torneio por equipes gera uma página por tabuleiro;
- [x] teste automatizado valida quantidade de páginas e textos principais.

Implementação:

- `ExportService.export_scoresheets(round_id, file_path)`;
- botões `Exportar sumulas` e `Imprimir sumulas` na tela `Rodadas`;
- uma página A4 por mesa, com 60 lances, dados oficiais, resultado e assinaturas.

#### DOC-02 - Folha de emparceiramento de mural com QR

Status: concluído em 2026-05-31.

Problema:

- a exportação atual e genérica e o QR aparece apenas no HTML.

Escopo:

- criar PDF A4 legível para afixação;
- incluir rodada, mesa, brancas, pretas, rating e QR;
- incluir QR somente para rodada aberta;
- oferecer exportar e imprimir na tela `Rodadas`.

Critérios de aceite:

- [x] PDF de 60 mesas fica legível em impressão A4;
- [x] QR abre a mesa correta;
- [x] rodada fechada não gera QR ativo;
- [x] testes validam presença e ausência condicional do QR;
- [x] benchmark valida 60 mesas em 2,4005 s e 4 páginas;
- [x] baseline adicional valida 400 mesas + 1 bye em 15,4840 s e 27 páginas.

Implementação:

- PDF A4 vertical especializado para torneios individuais;
- até 15 mesas por página, com mesa, nomes, ratings e QR;
- QR emitido somente para mesa sem bye em rodada aberta;
- emissão de tokens QR dos documentos feita em lote transacional, com
  auditoria agregada por rodada;
- `Exportar rodada` preserva CSV/XLSX e gera o mural quando escolhido PDF;
- `Imprimir rodada` gera diretamente o mural PDF;
- torneios por equipes mantém o relatório existente.

#### DOC-03 - Lista de chamada imprimível

Status: concluído em 2026-05-31.

Problema:

- a chamada existe na tela, mas precisa de contingência em papel.

Escopo:

- criar PDF ordenado pelo ranking inicial;
- incluir número inicial, nome, rating, clube, categoria e coluna de assinatura;
- manter exportação CSV/XLSX atual.

Critérios de aceite:

- [x] ordenação igual a utilizada no TRF do torneio;
- [x] PDF suporta pelo menos 200 jogadores;
- [x] teste valida ordem e cabeçalhos;
- [x] benchmark valida 801 jogadores em 0,1055 s e 22 páginas.

Implementação:

- PDF A4 vertical especializado com cabeçalho repetido, página atual, total de
  inscritos e coluna de assinatura;
- ranking inicial compartilhado com a tela de chamada: rating TRF, nome de
  emparceiramento e ID como desempate;
- marcar ausência não renumera jogadores;
- CSV e XLSX continuam disponíveis pela exportação existente.

#### DOC-04 - Cartões de mesa

Status: concluído em 2026-05-31.

Problema:

- numeração e sinalização de tabuleiros ainda dependem de material externo.

Escopo:

- gerar cartões imprimíveis com número da mesa;
- opcionalmente incluir QR da mesa e identificação da rodada.

Critérios de aceite:

- [x] gerar cartões para intervalo configurável;
- [x] layout legível a distancia;
- [x] identificação opcional da rodada;
- [x] QR opcional somente para mesa válida de rodada individual aberta;
- [x] benchmark valida 200 cartões sem QR em 0,0811 s;
- [x] benchmark valida 60 cartões com QR em 2,6519 s.

Implementação:

- `ExportService.export_table_cards(file_path, start_board, end_board, round_id, include_qr)`;
- quatro cartões por página A4, com número de mesa em destaque;
- intervalo limitado a 500 cartões por arquivo;
- botão `Exportar cartoes` na tela `Rodadas`;
- dialogo de intervalo e confirmação opcional de QR.

### EPIC B - Classificação e conferência

Prioridade: muito alta.

#### CLS-01 - Tabela cruzada individual

Status: concluído em 2026-05-31.

Problema:

- falta uma visão matriz jogador x rodada para conferência rápida.

Escopo:

- criar `PairingService.crosstable(tournament_id)`;
- uma linha por jogador;
- uma coluna por rodada com adversário, cor e resultado;
- adicionar pontos e desempates ao final;
- exportar CSV, XLSX, PDF e HTML.

Critérios de aceite:

- [x] fixture round-robin de 6 jogadores confere integralmente;
- [x] soma dos resultados equivale a classificação;
- [x] bye, WO e ausência ficam distintos;
- [x] serviço puro possui testes unitários;
- [x] benchmark valida 801 jogadores em 0,0473 s;
- [x] CSV, XLSX, PDF e HTML exportam corretamente.

Implementação:

- `PairingService.crosstable(tournament_id)` usa a classificação como fonte
  única dos resultados fechados;
- uma linha por jogador e uma coluna por rodada fechada;
- célula compacta com posição do adversário, cor (`B` ou `P`) e resultado;
- `BYE`, `1F-0F`, `0F-1F`, `0F-0F` e ausência (`-`) permanecem distintos;
- `ExportService.export_crosstable(tournament_id, file_path)`;
- botão `Exportar tabela cruzada` na tela `Classificacao`;
- relatório `Tabela cruzada` no centro de exportações.

#### CLS-02 - Tabela cruzada por equipes

Status: concluído em 2026-05-31.

Problema:

- a operação por equipes exige conferência de match points e game points.

Escopo:

- criar matriz equipe x rodada;
- incluir adversário, resultado do match, MP e GP;
- permitir detalhar tabuleiros.

Critérios de aceite:

- [x] torneio de equipes com reservas preserva histórico por tabuleiro;
- [x] total de MP e GP confere com classificação.

Implementação:

- `PairingService.team_crosstable(tournament_id)` cria uma linha por equipe e
  uma célula por rodada fechada;
- célula compacta com posição do adversário, lado (`B` ou `P`), resultado,
  match points (`MP`) e game points (`GP`);
- payload mantém os tabuleiros fechados para conferência detalhada, inclusive
  quando uma reserva foi escalada;
- exportação automática em CSV, XLSX, PDF e HTML pelo fluxo existente;
- tela `Classificacao` oferece `Exportar tabela cruzada` e
  `Detalhar tabuleiros`;
- benchmark com 801 jogadores, 200 equipes e 400 tabuleiros: 125,4967 ms em
  media.

### EPIC C - Painel de exceções avançado

Prioridade: alta.

#### PNL-01 - Filtros na Central de pendências

Status: concluído em 2026-05-31.

Problema:

- filas extensas misturam QR, sincronização e relógio.

Escopo:

- filtros `Todas`, `Decisao`, `QR`, `Sync` e `Relogio`;
- busca por mesa, título ou detalhe;
- contador atualizado conforme filtro.

Critérios de aceite:

- [x] árbitro localiza uma pendência por mesa em até 2 interações;
- [x] filtros não alteram o estado da pendência;
- [x] testes de UI cobrem filtro e busca;
- [x] benchmark valida filtro e busca em 1.000 pendências em 1,4220 ms.

Implementação:

- `PairingService.filter_arbitration_issues(issues, issue_filter, query)` puro;
- filtros `Todas`, `Decisao`, `QR`, `Sync` e `Relogio`;
- busca local por mesa, título, detalhe e payload;
- contador `Exibindo N de total`;
- primeira pendência visível continua pré-selecionada;
- nenhuma consulta adicional ou mutação ocorre ao filtrar.

#### PNL-02 - Lançamento inline pelo painel

Status: concluído em 2026-05-31.

Problema:

- o painel mostra mesas pendentes, mas o registro ainda exige abrir `Rodadas`.

Escopo:

- selecionar mesa na lista inline;
- registrar `1-0`, `1/2-1/2`, `0-1` ou limpar;
- delegar obrigatoriamente para `PairingService.update_result`;
- preservar confirmações e auditoria de rodada fechada.

Critérios de aceite:

- [x] resultado aparece no painel sem troca de tela;
- [x] próxima pendência e selecionada automaticamente;
- [x] atalhos continuam funcionando na tela `Rodadas`;
- [x] testes cobrem individual e bloqueio em rodada fechada;
- [x] benchmark valida 49,7582 ms por lançamento com recarga em 801 jogadores.

Implementação:

- payload inline inclui ID persistido da mesa;
- primeira mesa pendente fica pré-selecionada;
- busca numérica localiza exatamente a mesa mesmo fora do recorte inline;
- botões `1-0`, `1/2`, `0-1` e `Limpar`;
- atalhos `1`, `-`, `0`, `Backspace` e `Delete`;
- toda alteração delega para `PairingService.update_result`;
- painel recarrega após salvar e seleciona a próxima pendência;
- bloqueio de rodada fechada continua centralizado no serviço.
- piloto com 801 jogadores localiza e lança a mesa 400 em 73,5168 ms.

#### PNL-03 - Relógio da rodada

Status: concluído em 2026-05-31.

Problema:

- o painel não mostra duração da rodada atual.

Escopo:

- persistir ou derivar horário de abertura;
- mostrar início e tempo decorrido;
- atualizar junto com o auto-refresh.

Critérios de aceite:

- [x] duração e exibida sem depender de internet;
- [x] rodada fechada mostra duração final.

Implementação:

- horário de abertura derivado de `rounds.created_at`, já persistido na geração;
- `rounds.closed_at` adicionado na migração `v33`;
- rodadas legadas fechadas recebem `closed_at = created_at` para manter valor
  estável sem inventar duração;
- card `Tempo rodada` mostra início local, estado e duração `HH:MM:SS`;
- rodada aberta recalcula duração junto com o auto-refresh do painel;
- rodada fechada usa `closed_at` e preserva a duração final;
- benchmark com 801 jogadores e 50 mesas inline: 24,7673 ms em média.

#### PNL-04 - Preferências operacionais persistidas

Status: concluído em 2026-05-31.

Problema:

- auto-refresh e quantidade de mesas inline voltam ao padrão ao reiniciar.

Escopo:

- persistir auto-refresh;
- permitir intervalo entre 10 e 120 segundos;
- permitir limite inline entre 10 e 50 mesas.

Critérios de aceite:

- [x] preferências sobrevivem ao reinicio;
- [x] valores inválidos voltam ao padrão seguro.

Implementação:

- preferências locais salvas em `app_settings`, sem migração de schema;
- defaults compatíveis: auto-refresh ligado, intervalo de 15 segundos e 20 mesas;
- recargas manuais substituem o agendamento anterior para evitar ticks duplicados;
- benchmark com 801 jogadores e limite de 50 mesas: 22,2493 ms em média.

### EPIC D - Dados oficiais e prestação de contas

Prioridade: média.

#### FED-01 - Relatório de taxas de rating

Status: concluído em 2026-05-31.

Problema:

- não existe resumo financeiro para homologação e prestação de contas.

Escopo:

- contar jogadores rated e não rated;
- permitir taxa configurável;
- separar FIDE, CBX e LBX quando aplicável;
- exportar PDF e XLSX.

Critérios de aceite:

- [x] totais conferem com inscritos;
- [x] relatório identifica claramente a base utilizada.

Implementação:

- taxas unitárias configuráveis por torneio para FIDE, CBX e LBX;
- cálculo separado por base: inscritos identificados, rated, não rated, taxa
  unitária e subtotal;
- cada base cobra separadamente os inscritos identificados nela, inclusive
  quando um jogador possui IDs em mais de uma base;
- resumo geral informa inscritos, rated em alguma base e jogadores sem ID
  oficial;
- detalhamento lista IDs e ratings utilizados para conferência;
- centro de exportações oferece `Taxas de rating` em XLSX e PDF;
- benchmark com 801 jogadores: resumo em 11,5755 ms e XLSX em 409,6342 ms.

#### FED-02 - Pré-visualização de atualização oficial

Status: concluído em 2026-05-31.

Problema:

- a importação oficial atual atualiza os inscritos sem tela de comparação.

Escopo:

- mostrar antes/depois de nome, clube, título e ratings;
- permitir confirmar atualização em lote;
- manter jogadores sem correspondência separados.

Critérios de aceite:

- [x] nenhuma alteração e persistida antes da confirmação;
- [x] importação de lista continua funcionando offline por arquivo;
- [x] teste cobre confirmação e cancelamento.

Implementação:

- o botão `Comparar ratings oficiais` abre a pré-visualização sem gravar dados;
- a comparação exibe antes/depois de nome, clube, título, rating principal,
  rating nacional e rating internacional;
- correspondências sem mudança e jogadores sem correspondência ficam
  identificados separadamente;
- divergências ficam pré-selecionadas para agilizar o fluxo, com contador e
  opções para limpar ou restaurar a seleção;
- a confirmação recalcula o plano com a base oficial atual e aplica em lote
  somente as divergências selecionadas;
- o fluxo de importação offline FIDE, CBX e LBX por arquivo permanece
  disponível;
- benchmark com 801 inscritos, 700 correspondências alteradas e 101 sem
  correspondência: pré-visualização em 877,1279 ms médios e confirmação em
  4.249,0223 ms.

### EPIC E - Inscrições e importação flexível

Prioridade: alta.

Contexto: hoje a importação depende de colunas padronizadas
(`ImportService.import_players`, `import_online_registrations`,
`preview_online_registrations` por arquivo ou URL CSV do Google Sheets/Forms) e
de modelos fixos gerados em XLSX (`ExportService.export_player_import_template`
e `export_online_registration_template`). Na pratica o árbitro recebe planilhas
antigas e formulários fora do padrão, com colunas em qualquer ordem, nomes
diferentes (`Nome completo`, `Atleta`, `Jogador`), datas em formatos variados e
campos faltando. Falta (a) um formulário de coleta já padronizado para
distribuir e (b) uma tela que importe planilhas não padronizadas mapeando cada
coluna para o campo correto.

#### REG-01 - Gerador de formulário de inscrição padronizado (Google Forms)

Status: concluído em 2026-06-03.

Problema:

- o sistema gera apenas modelo XLSX/CSV; o árbitro monta o Google Forms na mao,
  com perguntas e ordem divergentes, gerando colunas que não batem com o
  importador.

Escopo:

- gerar a definição de um Google Forms padronizado a partir dos campos canônicos
  do Albericus (nome de emparceiramento, nome completo, data de nascimento,
  sexo, federação, clube/cidade, categoria, IDs oficiais FIDE/CBX/LBX, ratings,
  e-mail e telefone), respeitando obrigatoriedade e tipo de cada campo;
- criar o formulário **ao vivo** na conta do árbitro via API do Google Forms
  (OAuth de app desktop), devolvendo o link de resposta pronto para enviar aos
  jogadores que se inscrevem sozinhos;
- manter um **fallback offline** quando faltarem credencial/bibliotecas/internet:
  gerar um script Apps Script colavel mais a definição reutilizável
  (`.json`) e um passo a passo de publicação;
- oferecer ainda a opção mais simples (sem OAuth): **link pré-preenchido** a
  partir de um formulário já existente — o árbitro configura uma vez o link
  pré-preenchido (de onde se extrai a URL base e o `entry.*` do campo do
  torneio) e o sistema monta/compartilha o link com o nome do torneio já
  preenchido, abrindo no navegador para enviar aos jogadores;
- garantir que o CSV de respostas do formulário gerado seja importável
  diretamente pelo fluxo `import_online_registrations` existente (colunas já no
  padrão);
- incluir o link/QR do formulário no material de divulgação do torneio.

Critérios de aceite:

- [x] clicar no botão cria o formulário na conta do árbitro e devolve o link de
  resposta (quando a credencial OAuth está configurada);
- [x] o formulário cobre todos os campos padronizados com tipo e obrigatoriedade
  corretos;
- [x] o CSV de respostas do formulário gerado importa sem mapeamento manual;
- [x] há fallback (script Apps Script) quando faltam credencial/bibliotecas/
  internet, sem quebrar o fluxo;
- [x] alternativa sem OAuth: configurar um formulário existente e
  gerar/compartilhar o link pré-preenchido com o nome do torneio;
- [x] teste valida que os cabeçalhos do formulário casam com o importador
  padronizado.

Implementação:

- criação **ao vivo** como caminho principal: `GoogleFormsService`
  (`src/services/google_forms_service.py`) cria o formulário na conta do árbitro
  via API do Google Forms (OAuth de app desktop, token cacheado em
  `config/google_forms_token.json`) e devolve o link de resposta para enviar aos
  jogadores; `build_form_requests` (função pura) monta o `batchUpdate`
  (descrição + uma pergunta por campo, com tipo data/escolha/texto e
  obrigatoriedade);
- **fallback automático** para o script Apps Script
  (`ExportService.export_registration_form`) quando faltam bibliotecas Google,
  credencial OAuth ou internet/autorizacao: gera `.gs` (com passo a passo e a
  função `criarFormularioInscricao`) e `.json` (definição reutilizável);
- as perguntas vem de `REGISTRATION_FORM_QUESTIONS`, com títulos idênticos aos
  cabeçalhos aceitos por `_online_registration_payload`, garantindo importação
  sem mapeamento tanto no modo ao vivo quanto no script; `Sexo` vira múltipla
  escolha `M`/`F`;
- dependências Google são **opcionais e importadas lazy** (o módulo importa sem
  elas); adicionadas ao `requirements.txt` como opcionais;
- link pré-preenchido (sem OAuth): `ExportService.parse_prefill_link`,
  `build_registration_prefill_url`, `registration_form_config`,
  `save_registration_form_config` e `registration_prefill_url`; a config (URL
  base + `entry.*` do torneio) fica em `app_settings`, sem migração de schema;
- UI: botão `Gerar formulario (Google Forms)` tenta a API e, se
  indisponivel/falhar, oferece gerar o script; `Configurar formulario (link)`
  analisa o link pré-preenchido e escolhe o campo do torneio; `Compartilhar
  inscrição (link)` monta e exibe o link (copiar/abrir) com o torneio
  preenchido; diálogos com link de resposta/edicao no modo ao vivo;
- guia de configuração (OAuth e link pré-preenchido) em
  `docs/GUIA_GOOGLE_FORMS.md`;
- distribuição para a comunidade: padrão sem OAuth (link pré-preenchido +
  script, sem teto de usuários); para "Entrar com o Google" a todos,
  `client_secret_path` aceita credencial **embarcada** em
  `assets/google_client_secret.json` (precedência: app_settings > config do
  usuário > embarcada), gitignored; checklist de empacotamento e verificação do
  app (escopo sensível, sem CASA) em `docs/DISTRIBUICAO_E_VERIFICACAO_GOOGLE.md`;
- 16 testes (payload puro e orquestração da API mockada, disponibilidade/
  credencial, precedência da credencial embarcada, compatibilidade dos títulos
  com o importador, e parse/montagem/config do link pré-preenchido).

#### REG-02 - Assistente de importação com mapeamento de colunas

Status: concluído em 2026-06-03.

Problema:

- planilhas antigas (CSV/XLS/XLSX) e respostas de formulários não padronizados
  não importam porque as colunas não correspondem ao modelo fixo; hoje só resta
  editar a planilha na mao antes de importar.

Escopo:

- criar `ImportService.inspect_source(file_path_or_url)` que lê o arquivo
  (CSV/XLS/XLSX e URL CSV publicada) e devolve cabeçalhos detectados, as
  primeiras N linhas de amostra e um palpite de mapeamento por heurística
  (sinônimos por campo: `nome|atleta|jogador`, `nascimento|idade|data nasc`,
  `id fide|fide id`, `rating|elo`, etc.);
- criar tela/dialogo de mapeamento: para cada campo canônico do Albericus, um
  seletor da coluna de origem (ou "ignorar"), com pré-visualização das primeiras
  linhas atualizando ao trocar o mapeamento;
- suportar transformações mínimas por campo: idade -> ano de nascimento
  aproximado, normalização de data, divisão de "Sobrenome, Nome", trim e
  vazio -> nulo;
- reaproveitar o preview de status existente
  (`pronta`/`duplicada`/`erro` por linha) após o mapeamento, sem persistir antes
  da confirmação;
- salvar o mapeamento como perfil reutilizável (`import_mappings`) por
  origem/nome, para reimportar o mesmo formato sem refazer o de-para;
- aceitar apenas formatos tabulares (CSV/XLS/XLSX e URL CSV publicada);
  PDF/imagem digitalizada de formulário não é suportado.

Critérios de aceite:

- [x] planilha com colunas fora de ordem e nomes divergentes importa após o
  mapeamento, sem editar o arquivo de origem;
- [x] heurística acerta o mapeamento óbvio (nome, rating, ID) na maioria das
  colunas reconhecíveis;
- [x] nenhuma linha e persistida antes da confirmação no preview;
- [x] perfil de mapeamento salvo reaplica corretamente o de-para numa segunda
  importação do mesmo formato;
- [x] `inspect_source` e a normalização são serviço puro com testes
  (cabeçalhos, amostra, palpite, idade->nascimento, "Sobrenome, Nome").

Implementação:

- `ImportService.inspect_source(source, sample_size=5)` lê CSV/XLS/XLSX e URL
  CSV publicada (helpers `_read_tabular`/`_tabular_from_*` extraídos dos leitores
  existentes) e devolve cabeçalhos, amostra das primeiras linhas, definição dos
  campos canônicos (`REGISTRATION_IMPORT_FIELDS`) e palpite por heurística
  (`_suggest_mapping`, casamento exato e por substring sem reutilizar coluna);
- `_apply_mapping` renomeia cada coluna para a chave canônica (reconhecida por
  `_pick`), converte idade em ano de nascimento (`_birth_year_from_age`) e divide
  "Sobrenome, Nome"; `preview_mapped_registrations`/`import_mapped_registrations`
  reaproveitam `_build_registration_rows` e `_persist_ready_rows`, mantendo o
  preview de status (`pronto`/`duplicado`/`erro`) sem persistir antes da
  confirmação;
- perfis reutilizáveis em `app_settings` (`import_mapping_profiles`, sem migração
  de schema): `list_mapping_profiles`, `save_mapping_profile`,
  `delete_mapping_profile`;
- UI: botões `Importar com mapeamento` e `Importar link com mapeamento` na tela
  `Jogadores`; dialogo com seletor de coluna por campo, perfis (aplicar/salvar/
  excluir) e botão `Pre-visualizar e importar` que reusa o preview de inscrições
  online (agora parametrizado por um importador);
- 9 testes novos (inspeção, heurística, idade->nascimento, split de nome,
  preview/import com mapeamento, nome não mapeado, perfis).

### EPIC F - Conformidade de desempates e classificação

Prioridade: bloqueante. Origem: auditoria arbitral de 2026-07-29 (analise dos
módulos de gestão de torneio sob ótica de árbitro FIDE). Estes itens podem
produzir classificação publicada incorreta.

#### TBK-01 - Ajustes de pontos aplicados na classificação

Status: CONCLUÍDO (2026-07-30).

Como ficou:

- módulo puro `src/services/pairing/point_adjustments.py`: agrega as linhas de
  `point_adjustments` por competidor (`AdjustmentTotal`), escreve o texto que
  explica o total e define o marcador visual único (`*`) mais a legenda;
- `calculate_player_standings`/`calculate_team_standings` recebem `adjustments=`
  e somam **depois** dos desempates: a penalidade e decisão sobre o punido, não
  sobre a forca de quem o enfrentou — Buchholz/SB/performance seguem medindo o
  tabuleiro, que e também o que o Gacrux mede;
- ordenação com o Gacrux ativo: os pontos já ajustados entram na frente e o rank
  do motor vira o desempate de quem ficou com a mesma soma. Sem ajuste no
  torneio a chave e a de antes, byte a byte. Em equipes o prefixo reordenado vai
  até o último critério que um ajuste pode mover (MP/GP);
- **por que o ajuste não vai ao motor:** no individual o Gacrux recebe TRF-16,
  que não tem registro 299; no de equipes o TRF-25 tem, mas o
  `parse_trf_abnormal` do motor lê o 299 como redefinição do sistema de pontos,
  não como penalidade nominal. Vale a primeira saída prevista no escopo
  ("pontos ajustados");
- `PairingService.standings`/`team_standings` alimentam o parâmetro — e como
  todo consumidor (tela, PDF, XLSX, site, portal, pódio, ata, premiação) passa
  por eles, o número corrigido chega a todos sem tocar em cada saída;
- ata final ganha a seção "Ajustes de pontos do árbitro (TRF25 §7.3)" com
  rodada, competidor, tipo, MP, GP, motivo e data — omitida quando não há
  ajuste;
- lançar, excluir e restaurar um ajuste geram evento em `audit_events` com o
  motivo, que e de onde o `export_tournament_audit` monta o relatório de
  auditoria. Falha de auditoria não desfaz a decisão já gravada.

Critérios de aceite: todos atendidos; 25 testes novos em
`tests/test_core_point_adjustments.py` (individual e equipes, nos dois motores)
e 3 em `tests/test_ui_arbitration.py` (trilha de auditoria).

Problema original:

- `point_adjustments` (penalidades e bônus do árbitro) só alimenta o registro
  299 do TRF25 (`federation_exporters/trf25.py:436`);
  `calculate_player_standings` e `calculate_team_standings` ignoram a tabela.
  Uma dedução de -0,5 aplicada pelo árbitro não aparece na classificação da
  tela, no site HTML, no portal live, no boletim, no pódio nem na ata final.
  A tabela do sistema contradiz a decisão arbitral em todos os documentos.

Escopo:

- somar ajustes de MP e GP em `calculate_player_standings` e
  `calculate_team_standings` antes da ordenação;
- marcador visual na classificação (asterisco com motivo) e nota nos
  documentos exportados;
- manter coerência com o motor Gacrux quando ativo (pontos ajustados ou
  registro 299 no TRF usado pelo subprocesso).

Critérios de aceite:

- [x] penalidade de -0,5 reordena a classificação na tela e em todas as
  exportações;
- [x] o ajuste aparece com motivo na ata final e no relatório de auditoria;
- [x] testes cobrem ajuste individual e por equipes nos dois motores de
  desempate.

#### TBK-02 - Fallback do motor de desempates visível

Status: CONCLUÍDO (2026-07-30).

Como ficou:

- módulo puro `src/services/pairing/tiebreak_engine.py`: `EngineReport` com três
  estados que não se confundem — **normal** (`used == configured`),
  **degradado** (`fallback`: o Gacrux falhou e o motor próprio assumiu, a tabela
  está publicada mas não é a configurada) e **bloqueado** (`blocked`: modo
  estrito barrou, nada foi publicado). Os textos das três portas (faixa da tela,
  evento de auditoria, pendência do painel) saem do mesmo lugar;
- `_run_tiebreak_engine` no `PairingService` unifica os caminhos individual e de
  equipes: guarda o retrato, registra evento de auditoria e, em modo estrito,
  levanta `AppError` em vez de degradar;
- **a falha entra no cache junto com o sucesso**, e isso resolve dois problemas
  de uma vez: antes um motor quebrado era re-executado a cada `standings()` —
  dezenas de subprocessos por tela — e agora o motor roda uma vez por ESTADO do
  torneio, o que também faz o árbitro receber um aviso por estado em vez de uma
  enxurrada. Fechar rodada nova gera evento novo (ele precisa saber que
  aconteceu de novo); repintar a tela não gera nenhum;
- `reset_tiebreak_engine` no botão "Recalcular": falha cacheada não pode prender
  o torneio numa falha passageira. Antes o botão só repintava;
- faixa **permanente** acima da tabela de classificação, inclusive no estado
  normal — aviso que só aparece no erro ensina o árbitro a não olhar para aquele
  canto. Degradado/bloqueado acrescentam o detalhe (adversário virtual, ordem
  dos empatados) e o botão de recalculo;
- pendência no painel do árbitro reusando a porta dos eventos de sync
  (`_audit_issue`), com cartão "Desempate" e filtro próprio na Central;
- **o modo estrito barra a PUBLICAÇÃO, não o torneio.** Escrever o bloqueio
  dentro de `standings()` sem mais nada pararia o evento: pareamento, prévia,
  snapshot de fechamento e diagnóstico do painel também leem a classificação, e
  todos só precisam da ORDEM POR PONTOS, que os dois motores calculam igual.
  `standings`/`team_standings` (publicáveis) levantam; `_standings`/
  `_team_standings` com `honor_strict=False` degradam para o motor próprio. O
  retrato e o registro são os mesmos nos dois caminhos — quem falha e o motor, e
  o modo estrito do torneio e que diz se bloqueia; `honor_strict` só decide se
  ESTE chamador recebe a exceção. Sem isso, um uso interno que chegasse primeiro
  cacharia "degradado" e a publicação seguinte leria o cache e degradaria em
  silêncio, que e exatamente o bug que a TBK-02 fecha;
- pela mesma razão a pendência entra como `attention`, e não `decision`:
  severidade `decision` **bloqueia o fechamento da rodada**
  (`_blocking_arbitration_issues_for_round`), o que recriaria a mesma armadilha
  por outro caminho. `audit_issue` ganhou o parâmetro, com o padrão antigo
  preservado para os eventos de sync, onde bloquear e correto;
- **reentrância não é fallback**: a chamada aninhada vinda do export do TRF
  (`_GACRUX_TIEBREAK_INFLIGHT`) usa o motor próprio sem registrar, sem alertar e
  sem valer o modo estrito — senão o export que o próprio motor pediu ficaria
  impossível;
- configuração `tiebreak_strict` ("Falhar em vez de degradar") em
  `tournament_settings` (schema v45), nascendo DESLIGADA inclusive nas bases
  existentes: barrar a classificação e decisão do árbitro do torneio, não padrão
  que uma migração imponha.

Critérios de aceite: todos atendidos; 27 testes novos em
`tests/test_core_tiebreak_engine.py` (retrato, faixa, fallback, modo estrito,
equipes, persistência da configuração e — os que mais valeram — gerar e fechar
rodada com o motor caído em modo estrito) e 1 em
`tests/test_pairing_gacrux_tiebreak.py` (motor real de pe não alerta nada —
guarda contra alarme falso).

Problema original:

- se o subprocesso Gacrux falha, `pairing_service.py:1591-1597` apenas loga um
  warning e a classificação passa a ser calculada pelo motor próprio, que não
  aplica o adversário virtual. O mesmo torneio pode publicar duas
  classificações diferentes entre rodadas sem nenhum aviso ao árbitro.

Escopo:

- badge permanente na tela de classificação indicando o motor efetivamente
  usado no último cálculo;
- evento de auditoria e alerta no painel quando ocorrer fallback;
- opção de configuração "falhar em vez de degradar" para torneios FIDE-rated.

Critérios de aceite:

- [x] fallback gera alerta visível e evento de auditoria;
- [x] classificação exibe o motor usado;
- [x] em modo estrito, falha do Gacrux bloqueia a publicação em vez de trocar
  de motor silenciosamente.

#### TBK-03 - Jogos não disputados conforme FIDE no motor próprio

Status: CONCLUÍDO (2026-07-30), pela SEGUNDA saída do escopo.

**A escolha: rebaixar, não reimplementar.** O escopo dava duas saídas —
implementar o adversário virtual da FIDE no motor próprio ou rebaixa-lo
formalmente a legado. Foi rebaixado, e a razão e de engenharia: as regras de
desempate da FIDE são versionadas por data de vigência (o próprio Gacrux carrega
`rulesversion`, com ramos `16.4.1`/`16.4.2` para 2026-02-01), e o Gacrux e o motor
padrão desde o PR #66. Uma segunda implementação da mesma norma versionada
tenderia a divergir a cada revisão — e duas respostas "oficiais" diferentes e
exatamente o problema que a TBK-02 existe para impedir. Melhor uma implementação
conforme e a outra honestamente rotulada.

Como ficou:

- `LEGACY_ENGINE_NOTE` e `LEGACY_ENGINE_CHOICE_HINT` em `tiebreak_engine.py`,
  ao lado da razão da escolha. Sai por três portas: a **faixa** da classificação
  (reusando o vocabulário da TBK-02 — motor próprio escolhido de propósito agora
  rende tom `warning`, não `ok`), o **relatório de desempates** (o aviso vai no
  topo, antes dos números, porque e o documento que alguém usa para conferir a
  ordem final) e a **tela de configuração**, no `help_text` do seletor de motor —
  que e onde a decisão acontece;
- **`wins` deixou de contar W.O.** O critério e o `WON` da FIDE, "vitórias no
  tabuleiro", e o Gacrux exige `played and opponent > 0`. Antes o Albericus
  contava a vitória por W.O., então trocar de motor no meio do torneio reordenava
  os empatados. Há teste de paridade com o motor real, num torneio COM W.O. e COM
  bye — a restrição "sem W.O." do teste antigo caiu;
- **confronto direto só quando todos os empatados se enfrentaram**, como a FIDE
  exige. Com três empatados em que A jogou com B e com C mas B e C não se
  enfrentaram, "quem ganhou de quem" não é uma ordem — e um pedaço de uma. Antes
  o critério somava os jogos que existiam e produzia um número com aparência de
  resultado; agora e zero para o grupo inteiro, e o desempate seguinte decide.

**Um item da auditoria NÃO se confirmou, e vale registrar.** O relatório pedia
trocar o divisor do limiar de Koya pelas rodadas CONFIGURADAS do torneio, no lugar
das jogadas. O Gacrux usa as jogadas (`compute_koya`: `maxgames = rounds`, onde
`rounds` e o `-n` do subprocesso), então a mudança pedida afastaria os dois
motores. Medido no cenário em que os dois divisores divergem — 3 rodadas fechadas
de 7 configuradas — os valores já batem. Nada foi alterado, e um teste guarda a
equivalência para que ninguém "conserte" isso depois.

Critérios de aceite:

- [x] fixture com W.O. e byes produz o mesmo Buchholz/SB nos dois motores **ou o
  motor próprio exibe aviso de não conformidade** — pela segunda alternativa, com
  teste que registra a divergência de Buchholz como fato (e não impressão), para
  o dia em que alguém pensar em promover o motor próprio de volta;
- [x] confronto direto só e aplicado quando todos os empatados se enfrentaram;
- [x] teste de paridade `wins` x `WON` sem restrição de "sem W.O.".

**Um defeito de componente apareceu no caminho.** O `help_text` do seletor de
motor foi a primeira ajuda longa escrita no app, e o `labeled_field` montava a
linha de apoio **sem quebra de linha**. Como o painel do formulário e um
`CTkScrollableFrame` (cresce para caber o conteúdo), o texto alargou o formulário
inteiro e empurrou os controles para fora da janela — o guarda de layout da B-8
pegou em cinco larguras. O conserto foi no componente, não no texto: a linha de
apoio quebra na largura da coluna do formulário. Detalhe que custou duas
tentativas: seguir a largura medida com `<Configure>` **realimenta o problema**
(container mais largo -> quebra maior -> rotulo mais largo -> container mais
largo). A largura e fixa de propósito.

Cobertura: 16 testes em `tests/test_core_tbk03.py` e 1 em `tests/test_ui_fields.py`
(a ajuda longa não pode alargar a caixa do campo). Um teste da TBK-02 foi
ajustado: a faixa do motor próprio deixou de ser tom `ok`.

Problema original:

- no motor próprio (`pairing/tiebreaks.py`), W.O. contam como partida real em
  Buchholz, Sonneborn-Berger, ARO e performance (`:697-700`), e byes não
  entram no Buchholz (`_opponent_points:232-237`) — contraria as FIDE
  Tie-Break Regulations (adversário virtual, art. 16);
- o parâmetro `unplayed="self"` (`:246-251`) e inalcancavel pela UI;
- `_direct_encounter_score` (`:281-291`) aplica confronto direto sem verificar
  se todos os empatados se enfrentaram (condição obrigatória FIDE) e não
  redefine o grupo de empate após cada critério;
- `wins` conta vitórias por W.O.; o `WON` do Gacrux conta só partidas jogadas —
  trocar de motor no meio do torneio muda a ordem dos empatados;
- `_koya_score` usa como total a maior rodada com jogo registrado
  (`:726-729`), não o total de rodadas do torneio.

Escopo:

- implementar o adversário virtual e o tratamento de rodadas não jogadas no
  motor próprio, alinhado a versão das regras vigente pela data do torneio
  (mesmo critério do Gacrux); ou
- rebaixar formalmente o motor próprio a "modo legado, não homologavel", com
  aviso na configuração e no relatório de desempates;
- corrigir confronto direto, `wins` e Koya em qualquer um dos caminhos.

Critérios de aceite:

- [x] fixture com W.O. e byes produz o mesmo Buchholz/SB nos dois motores (ou
  o motor próprio exibe aviso de não conformidade) — pela segunda alternativa;
- [x] confronto direto só e aplicado quando todos os empatados se enfrentaram;
- [x] teste de paridade `wins` x `WON` sem restrição de "sem W.O.".

#### TBK-04 - Parâmetros de critérios editáveis e registro 212 fiel

Status: CONCLUÍDO (2026-07-30).

Como ficou:

- **os parâmetros passam a viver no REGISTRO**, e não na tela: `TiebreakParam`
  declara chave, rotulo, padrão e faixa (ou lista de opções) ao lado do critério
  em `PLAYER_TIEBREAKS`. Três leitores, uma definição — a tela desenha o que o
  registro declara, o motor próprio lê em `player_tiebreak_value` e o mapa do
  Gacrux traduz para modificador. O `needs_cut: bool` que existia era declarado e
  nunca lido; morreu;
- `normalize_criterion_params` valida **na porta de entrada** (o
  `parse_*_tiebreak_sequence`): valor fora da faixa volta para dentro, texto sem
  número volta ao padrão, chave desconhecida e descartada — e o que chega a quem
  calcula vem sempre completo. Nunca levanta: um desempate que recusa a
  configuração no meio do torneio seria pior que um que ignora um número
  datilografado errado, e a tela valida antes de qualquer forma;
- **limiar do Koya** virou parâmetro (era 50% cravado); corte do Buchholz
  (`cut_low`/`cut_high`), `unplayed` e corte do ARO já eram lidos pelo motor
  próprio e agora são alcançáveis;
- **os parâmetros chegam ao motor FIDE.** `specifier_with_params` traduz para os
  modificadores do Gacrux, cuja sintaxe está em `gacrux/tiebreak.py` (laço que lê
  `comp[1:]`): `/C<n>` = corta os n piores, `/M<n>` = corta n de cada ponta,
  `/L<n>` = limiar do Koya em porcentagem. Parâmetro no valor padrão **não** vira
  modificador — `BH` e `BH/C1` são a mesma coisa para o motor, e o mais curto e o
  que o árbitro reconhece no arquivo;
- **registro 212 fiel.** Era a lista fixa `PTS,BH,BH/M1,SB,WIN`, escrita quando o
  projeto ainda não tinha sequencia configurável — e por isso o arquivo enviado a
  federação declarava critérios diferentes dos que o motor usava. Agora sai da
  mesma `tiebreak_sequence` que calcula a classificação, traduzida pelo mapa. Dois
  ganhos de tabela: os parâmetros viram modificador no arquivo (`BH/C2`,
  `KS/L60`) e o `WIN` virou **`WON`** — o motor sempre contou vitórias no
  tabuleiro (ver TBK-03), então declarar `WIN` era declarar outro critério;
- **o editor devolve os parâmetros**, com uma segunda linha por critério (e não
  ao lado dos botões de ordenação, que levaria a tela de volta ao gargalo de
  largura da B-8). Os valores são guardados fora do `_render` — que destrói e
  recria os widgets a cada subir/descer —, senão ordenar apagaria o corte que o
  árbitro acabou de escolher. Há teste para exatamente isso.

Critérios de aceite:

- [x] alterar a sequencia no editor muda o 212 exportado;
- [x] parâmetros persistem no JSON e são aplicados pelos dois motores;
- [x] teste valida o 212 contra a sequencia configurada (inclusive ponta a ponta,
  lendo a linha 212 do arquivo exportado).

Fica pendente do escopo original: **expor critérios já suportados pelo Gacrux e
ainda não registrados** (`BH/M2` como critério próprio, `SB` cortado, brancas
jogadas, `SNO`, sorteio). O `BH/M2` já é alcançável por parâmetro
(`buchholz_cut2` com corte simétrico); os demais são critérios novos no registro,
sem defeito associado — entram quando um regulamento pedir.

**O 212 de EQUIPES mudou mais do que o individual**, e vale registrar o que era
errado nele: a lista fixa `PTS,BH:MP,WIN` usava o `PTS` genérico onde o primário
de equipes e o match points, **omitia o game points** (que o motor sempre usou) e
declarava `WIN`. Agora sai `MPTS,GPTS,BH,WON` — literalmente o plano que vai ao
`tiebreakchecker`. O `BH` herda o primário no `parse_tiebreak` do Gacrux, então
equivale ao antigo `BH:MP` sem precisar declarar o tipo de ponto.

Cobertura: 26 testes em `tests/test_core_tbk04.py` e 4 em `tests/test_ui_fields.py`
(o editor). Dois testes existentes do 212 foram atualizados — o individual
(`WIN` -> `WON`) e o de equipes.

Problema original:

- `TiebreakSequenceEditor.get_sequence` devolve sempre `params: {}`
  (`tournament_widgets.py:42-43`): cortes de Buchholz além de C1/C2/M1, limiar
  do Koya, corte do ARO e `unplayed` não são configuráveis pelo árbitro;
- o registro 212 do TRF25 e hardcoded como `PTS,BH,BH/M1,SB,WIN`
  (`trf25.py:591-601`), ignorando `tiebreak_sequence` — o arquivo enviado a
  federação declara critérios diferentes dos usados (e usa `WIN` onde o motor
  usa `WON`).

Escopo:

- editor de sequencia com parâmetros por critério (corte, limiar, unplayed);
- gerar o 212 a partir de `tiebreak_sequence`/`team_tiebreak_sequence` via
  `gacrux_tiebreak_map`;
- expor critérios já suportados pelo Gacrux e ainda não registrados
  (`BH/M2`, `SB` cortado, brancas jogadas, `SNO`, sorteio).

Critérios de aceite:

- [x] alterar a sequencia no editor muda o 212 exportado;
- [x] parâmetros persistem no JSON e são aplicados pelos dois motores;
- [x] teste valida o 212 contra a sequencia configurada.

#### TBK-05 - Desempates de equipes completos

Status: CONCLUÍDO (2026-07-31). Fecha a Sprint 8.

Como ficou:

- **os quatro critérios que faltavam foram registrados** e valem nos dois
  motores. Cada um tem uma definição só, no registro, e três leitores (tela,
  motor próprio, mapa do Gacrux) — a mesma forma da TBK-04:

  | critério | o que e | Gacrux |
  |---|---|---|
  | `sonneborn_berger` | match points do adversário x game points feitos contra ele | `EMGSB` |
  | `direct_encounter` | match points contra as equipes empatadas | `DE` |
  | `buchholz_game_points` | soma dos game points dos adversários | `BH:GP` |
  | `board_count` | soma do número do tabuleiro x pontos nele obtidos | `BC` |

- **o SB olímpico não é o SB de match points.** O `SB` puro do Gacrux usa match
  points dos DOIS lados; o regulamento olímpico pesa a forca do adversário em
  match points e o placar do confronto em pontos de tabuleiro, que e o `EMGSB`.
  No fixture dos testes a diferença e 14,0 contra 4,0 para a mesma equipe — não
  e detalhe de arredondamento, e outro critério. O corte (`EMGSB/C1`, que alguns
  regulamentos pedem) e parâmetro, e descarta pela mesma regra do motor FIDE:
  menor pontuação do adversário primeiro, produto como desempate;
- **`higher_is_better` entrou no registro** por causa do board count, o único
  critério em que o número MENOR classifica melhor (o ponto vale mais no
  tabuleiro de cima). Fica declarado ao lado do critério, e não numa lista de
  exceções na hora de ordenar: quem ordena pergunta, em vez de saber de cor;
- **o board count precisa do resultado POR TABULEIRO**, que a classificação não
  tinha: entrou `list_team_board_results` e o repasse até o cálculo. A equipe de
  cada cor sai do ELENCO do jogador, e não da paridade do tabuleiro — tabuleiros
  pares invertem as cores e um jogador pode ter sido substituído; e a mesma regra
  que `team_match_result` usa para somar os game points, então a soma por
  tabuleiro fecha com o placar do confronto. A consulta só roda quando o board
  count está na sequencia (nenhum torneio por padrão);
- **divida da TBK-04 paga**: `_gacrux_player_tiebreaks`/`_gacrux_team_tiebreaks`
  montavam a lista só com os CÓDIGOS, então o corte configurado chegava ao
  registro 212 do arquivo FIDE mas **não ao cálculo em execução** — o arquivo
  declarava um critério e a tela mostrava outro número. A sequencia agora vai
  inteira, e a chave de cache virou assinatura (código + parâmetros), senão
  mudar só o corte devolveria o cálculo velho;
- **os dois registros compartilham códigos com significados diferentes**
  (`sonneborn_berger` de equipes aceita corte, o individual não; `buchholz` de
  equipes soma match points). `criterion_params` adivinhava o registro e
  devolvia os parâmetros do critério errado — passou a receber o registro;
- **a classificação publicada mostra o número que decidiu.** A tabela de equipes
  (tela e relatório) tinha quatro colunas fixas porque eram os quatro critérios
  que existiam; os configurados que não tem coluna entram agora, na ordem em que
  desempatam. Um desempate que decide o campeonato e não aparece em lugar nenhum
  não é utilizável numa apelação;
- **modularizacao**: o domínio de equipes saiu de `tiebreaks.py` (1284 linhas,
  individual + equipes) para `team_tiebreaks.py`, e a DECLARAÇÃO dos critérios
  (dataclasses, os dois registros, parâmetros, parse/serialize da sequencia) para
  `tiebreak_criteria.py`. Grafo de dependência sem ciclo: declaração <- cálculo.

Uma ressalva medida e assumida: o `DE` do Gacrux devolve uma POSIÇÃO dentro do
grupo empatado (0 quando não separa) e o do Albericus devolve os pontos feitos
contra os empatados, como no individual. Os números não se comparam; a ORDEM
sim, e e ela que o teste de paridade exige. No modo Gacrux o número exibido
continua sendo o do motor, como manda a TBK-02.

Byes não entram no Buchholz, no SB nem no board count do motor próprio: o
adversário virtual da FIDE só existe no Gacrux, que e a razão de o motor próprio
ser legado desde a TBK-03. Por isso os testes de paridade usam um fixture SEM
bye — com bye estariam comparando duas definições diferentes, e não a mesma
conta.

Critérios de aceite:

- [x] campeonato por equipes com regulamento olímpico (MP, DE, SB olímpico)
  ordena corretamente (e igual nos dois motores);
- [x] paridade com o Gacrux testada para os novos critérios, rodando o motor de
  verdade — valores para `EMGSB`, `EMGSB/C1`, `BH:GP` e `BC`; ordem para o `DE`.

Cobertura: 43 testes em `tests/test_core_tbk05.py`.

Problema original:

- só existem 4 critérios de equipes (match points, game points, Buchholz sobre
  MP, vitórias). Faltam os desempates usuais de regulamento FIDE/CBX por
  equipes: Sonneborn-Berger olímpico, confronto direto entre equipes, Buchholz
  de game points e board count/Berlin.

Escopo:

- registrar os critérios adicionais em `tiebreaks.py` e mapear no
  `gacrux_tiebreak_map` (TRF-25 já transporta equipes);
- disponibilizar no editor de sequencia por equipes.

Critérios de aceite:

- [x] campeonato por equipes com regulamento olímpico (MP, DE, SB olímpico)
  ordena corretamente;
- [x] paridade com o Gacrux testada para os novos critérios.

### EPIC G - Fluxo arbitral em salão

Prioridade: muito alta. Origem: auditoria arbitral de 2026-07-29.

#### ARB-01 - Correção com motivo, desbloqueio pontual e alerta de cascata

Status: CONCLUÍDO (2026-07-30). Fecha a Sprint 7.

Como ficou:

- módulo puro `src/services/pairing/corrections.py`: valida motivo (mínimo de 5
  caracteres — "ok" numa ata de apelação vale tanto quanto o campo vazio),
  calcula expiração, decide a permissão (`UnlockState`) e descobre as rodadas que
  a correção contamina. O "agora" chega como parâmetro, então a expiração e
  testavel sem esperar quinze minutos;
- `update_result(..., reason)` exige o motivo quando a rodada está fechada. **O
  motivo e checado ANTES da permissão**: quem chegou sem motivo precisa saber
  disso mesmo com a rodada desbloqueada, senão desbloqueia, tenta de novo sem
  nomear a razão e leva um recado sobre outra coisa;
- **desbloqueio pontual** (`correction_unlocks`, schema v46): permissão de UMA
  rodada, com justificativa e prazo de 15 min, que morre sozinha. Substitui o
  habito de ligar `allow_dangerous_changes` e esquecer — o interruptor global
  continua valendo, porque não se tira um caminho que torneios em andamento já
  usam, mas fica em segundo lugar e a tela diz que ele e o amplo. O diálogo de
  correção abre dizendo de onde vem a permissão e até quando ela vale, porque
  numa segunda correção da mesma súmula o árbitro já entra direto nele.
  `revoke_round_correction_unlock` existe e e testado, mas **sem botão**: a janela
  expira sozinha em 15 minutos, e um controle para reduzir esse prazo a mao seria
  ruído — quando fizer falta (ARB-03, incidentes), o serviço já está pronto;
- **cascata**: correção com rodada posterior já pareada (inclusive apenas
  gerada — o pareamento dela nasceu do placar antigo) gera evento
  `result_correction_cascade` e pendência `attention` no painel, com o recado
  dizendo o que fazer, não só o que houve. `attention` e não `decision` porque
  quem decide se repareia e o árbitro, e travar o fechamento não ajudaria;
- **retratos reconciliados**: `standings_snapshots` faz upsert por (torneio,
  rodada), então regravar apagaria a prova documental. O retrato antigo vai para
  `standings_snapshot_history` com data, hash e motivo; a linha viva passa a ser
  a reconciliada; e um evento `standings_snapshot_reconciled` guarda os dois
  hashes. Os `tiebreak_components` da rodada são regravados junto;
- para reconciliar sem plantar um segundo erro no lugar do primeiro, nasceu o
  corte `up_to_round` em `_standings`/`_team_standings` (e `current_round` no
  caminho Gacrux, que entra na chave do cache): o retrato da rodada 3 recebe a
  classificação **como estava depois da rodada 3**, não a de hoje;
- na tela, o "Alterar mesmo assim?" virou duas perguntas, porque são duas
  decisões: *abrir a rodada* (permissão, com prazo) e *o que aconteceu* (o
  registro). Nasce o quinto tipo de dialogo, `reason_dialog`, que usa a MESMA
  função pura de validação do serviço — a tela não reescreve a regra, só a
  aplica antes de o árbitro perder o clique;
- seção "Correções em rodada fechada" na ata final, com rodada, `1-0 -> 0-1`,
  operador, motivo e data. A trilha de auditoria e tela de diagnóstico; quem
  revisa uma apelação lê a ata. A seção sai da própria trilha, para não existirem
  duas versões do mesmo fato — e sai omitida quando não houve correção;
- o lançamento rápido do painel recusa rodada fechada com o recado DELE, e não
  com o do serviço: a faixa inline não tem campo de motivo, então pedir um seria
  mandar o árbitro preencher o que a tela não oferece. Ela aponta para a tela
  Rodadas, onde vivem o desbloqueio e o motivo.

Critérios de aceite: todos atendidos. Cobertura: 42 testes em
`tests/test_core_corrections.py` (motivo, expiração, permissão, cascata,
retratos, ata, individual e equipes), 5 em `tests/test_ui_dialogs.py` (o
`reason_dialog`) e 2 em `tests/test_ui_arbitration.py` (a recusa do lançamento
inline). Cinco testes existentes que corrigiam rodada fechada sem motivo foram
ajustados — e reforçados: um deles virou um par, um cobrando a falta de permissão
com motivo presente e o outro a falta de motivo com permissão presente.

Problema original:

- o motivo da correção em rodada fechada e hardcoded
  (`pairing_service.py:1062`, "Correção em rodada fechada."), descumprindo o
  critério de aceite da Fase 0 do roadmap;
- `allow_dangerous_changes` e um toggle global do torneio: ligado uma vez,
  todas as rodadas fechadas ficam editáveis até alguém lembrar de desligar;
- corrigir a rodada N com a rodada N+1 já pareada não gera alerta nem sugere
  repareamento;
- `standings_snapshots` e `tiebreak_components` nunca são reconciliados após
  correção — a prova documental de uma apelação fica permanentemente errada.

Escopo:

- campo de motivo obrigatório no dialogo de correção;
- desbloqueio por ação, com justificativa e expiração, no lugar do toggle
  global (ou complementando-o);
- pendência de severidade `attention` quando há rodada posterior pareada sobre
  o resultado corrigido;
- regravar ou anotar como "superado" o snapshot das rodadas afetadas.

Critérios de aceite:

- [x] correção sem motivo e rejeitada;
- [x] correção com rodada posterior gera alerta de cascata no painel;
- [x] snapshot divergente fica marcado e um novo snapshot reconciliado e
  gravado com auditoria.

#### ARB-02 - Resultados arbitrais completos no painel

Status: CONCLUÍDO (2026-07-31). Abre a Sprint 9.

Como ficou:

- **um REGISTRO de códigos de resultado** (`results_registry.py`), porque o que um
  resultado E estava espalhado por seis lugares: `RESULT_POINTS`,
  `WALKOVER_RESULTS`, `FINAL_RESULTS`, o `_trf_player_result` do exportador, o
  `_count_result` dos resumos e os filtros de `fide_rating`. Enquanto os códigos
  se dividiam em "jogada" e "W.O.", conjuntos soltos davam conta; a família nova
  se distingue por uma propriedade que nenhum deles expressa. Agora cada código
  declara pontos, `played`, `rated` e as letras TRF, e os recortes derivam:

  | família | played | rated | letras TRF | códigos |
  |---|---|---|---|---|
  | normal | sim | sim | `1` `=` `0` | `1-0`, `0-1`, `1/2-1/2` |
  | decisão do árbitro | sim | **não** | `W` `D` `L` | `1U-0U`, `0U-1U`, `1/2U-1/2U` |
  | W.O./forfait | **não** | não | `+` `-` | `1F-0F`, `0F-1F`, `0F-0F` |

- **`W`/`D`/`L`: partida DISPUTADA e não ratavel.** E o jogo decidido por
  reclamação, por posição ilegal irrecuperável ou por apelação. Sem esses
  códigos o árbitro escolhia entre mentir no rating (lançar `1-0`) ou mentir no
  Buchholz e no pareamento (lançar W.O., que a FIDE trata como partida não
  disputada, e que desde a TBK-03 não conta como vitória). Como a partida
  aconteceu, ela conta como confronto, entra no Buchholz e no SB e vale `WON` —
  só não entra no relatório de rating. A importação TRF passou a LER as letras
  também: eram dois dicionários escritos a mao, e `W`/`D`/`L` voltava como "sem
  resultado";
- **W.O. no painel**, com botão e atalho (`w`, `p`, `a` — letras, e não números,
  porque passam por confirmação: um dedo torto no teclado numérico não pode
  lançar ausência). A confirmação nomeia a mesa e os dois jogadores, porque o
  erro que ela precisa pegar e o de mesa errada, não o de código errado;
- **partida adiada** (schema **v47**: `pairings.postponed` + `postponed_note`).
  Uma mesa adiada e uma pendência ESPERADA; sem a marca, ela e a mesa esquecida
  eram a mesma linha em branco, travando a rodada com o mesmo recado. Agora o
  fechamento nomeia as mesas adiadas em vez de mandar "preencha todos os
  resultados", o painel mostra "Adiada — sábado 14h" na coluna de contexto (que
  no individual vivia vazia) e lançar o resultado desfaz o adiamento — adiada
  com placar preenchido e um estado que não existe no salão. A nota e OPCIONAL:
  adiar sem saber quando ainda é melhor do que a mesa parecer esquecida.

A pendência do painel e `attention`, e não `decision`: a decisão o árbitro já
tomou — foi ele quem adiou. Quem impede o fechamento e a mesa sem resultado, com
o recado próprio; marcar como bloqueante faria a mesma coisa aparecer duas vezes,
com dois textos diferentes.

Critérios de aceite:

- [x] W.O. lançável pelo painel com confirmação e auditoria;
- [x] rodada com partida adiada exibe pendência especifica (e o recado do
  fechamento nomeia as mesas);
- [x] `W`/`D`/`L` exportam corretamente no TRF16 — e são lidos na importação.

Cobertura: 32 testes em `tests/test_core_arb02.py`.

Problema original:

- W.O. (`1F-0F`, `0F-1F`, `0F-0F`) só pode ser lançado na tela `Rodadas`; o
  lançamento inline do painel (`pairing_arbitration/pending.py:37`) oferece só
  1-0, 1/2 e 0-1 — justamente no momento em que o árbitro está em pe no salão;
- não existe estado "partida adiada/suspensa" nem os códigos TRF `W`/`D`/`L`
  (jogo decidido sem lance ratavel, ex.: resultado por decisão do árbitro).

Escopo:

- botões e atalhos de W.O. no lançamento inline (com confirmação);
- estado `adiada` que não bloqueia o restante do painel mas impede fechar a
  rodada até resolução;
- suportar códigos `W`/`D`/`L` no modelo de resultado e no TRF16.

Critérios de aceite:

- [x] W.O. lançável pelo painel com confirmação e auditoria;
- [x] rodada com partida adiada exibe pendência especifica;
- [x] `W`/`D`/`L` exportam corretamente no TRF16.

#### ARB-03 - Registro disciplinar de incidentes

Status: CONCLUÍDO (2026-07-31). Fecha a Sprint 9.

Como ficou:

- **tabela `incidents`** (schema **v50**) com catálogo de infrações FIDE:
  celular (11.3.2), lance ilegal (7.5), atraso além da tolerância (6.7), conduta
  (12.2), anotação (8.1), resultado combinado (11.1), queda de seta contestada
  (6.2) e "outro". Era tudo papel — a tabela do manual operacional;
- **o catálogo nomeia o ARTIGO, e não a sanção.** A FIDE deixa a sanção a cargo
  do árbitro (11.3.2 e a exceção histórica, e mesmo ela tem margem em rápidas),
  então cada infração traz a sanção SUGERIDA e o árbitro escolhe. O que o sistema
  garante e que a escolha fique registrada;
- **a decisão chega na classificação.** Dedução cria o `point_adjustment`
  vinculado (`adjustment_id`), que desde a TBK-01 move a ordem; partida perdida
  lança o resultado na mesa. Uma decisão disciplinar que não chega na tabela e um
  bilhete;
- **partida perdida e W.O. (`1F-0F`), e não o `1U-0U` da ARB-02.** Quem perde por
  regulamento NÃO JOGOU a partida aos olhos da FIDE — o adversário não ganha uma
  vitória no tabuleiro nem a partida entra no rating. São duas coisas parecidas
  que a ARB-02 acabou de separar, e usar a errada aqui desfaria aquilo;
- **queda de seta e ausência BLOQUEIAM o fechamento** até a decisão ser
  registrada (eram `attention`, e a rodada fechava com a pergunta em aberto).
  Registrado o incidente que aponta para o evento (`clock_event_id`), o alerta
  volta a ser informativo: a decisão existe e está na ata. Aviso de tempo crítico
  continua sendo só aviso;
- **anexo disciplinar na ata**, com rodada, mesa, jogador, artigo, decisão,
  observações e **reincidência marcada** — que e o número que o catálogo existe
  para produzir: no papel, a segunda advertência do mesmo artigo ao mesmo jogador
  não era encontravel por ninguém.

Os vínculos (`adjustment_id`, `clock_event_id`, `pairing_id`) são OPCIONAIS de
propósito: advertência não mexe em ponto nem em mesa, e exigir os três
transformaria o registro de uma conversa em burocracia que ninguém preenche no
meio da rodada. O que e exigido está na validação: partida perdida sem mesa e
dedução sem valor são recusadas, e "outro" exige descrição — e ela que a ata
cita no lugar do artigo.

Critérios de aceite:

- [x] incidente com dedução reflete na classificação (via TBK-01);
- [x] relatório de incidentes sai na ata final;
- [x] queda de seta registrada exige decisão antes de fechar a rodada.

Cobertura: 27 testes em `tests/test_core_arb03.py`.

Fica pendente do escopo original: a **ficha do jogador** com as reincidências
como TELA. O dado existe e sai na ata (`incident_repeat_offenders`); o que falta
e a visualização por jogador, que e trabalho de UI sem regra nova.

Problema original:

- não existe módulo de incidentes disciplinares: celular (art. 11.3.2), lance
  ilegal (7.5), atraso/default time (6.7), conduta (12.x). O registro hoje e
  em papel (tabela do manual operacional). `point_adjustments` existe mas não
  tem catálogo de infrações nem vínculo com o jogador reincidente.

Escopo:

- tabela `incidents` com catálogo de infrações FIDE, jogador, rodada/mesa,
  decisão do árbitro, observações;
- vínculo opcional com `point_adjustments` (dedução) e com o resultado
  (partida perdida);
- ficha do jogador com reincidências; relatório de incidentes do torneio
  (anexo da ata final);
- alertas de relógio `flag_fall`/`absence` promoviveis a pendência bloqueante
  até decisão registrada.

Critérios de aceite:

- [x] incidente com dedução reflete na classificação (depende de TBK-01);
- [x] relatório de incidentes sai na ata final;
- [x] queda de seta registrada exige decisão antes de fechar a rodada.

#### ARB-04 - Política de byes solicitados

Status: CONCLUÍDO (2026-07-31).

Como ficou:

- **a causa dos quatro defeitos era a mesma**: o bye solicitado era gravado
  DIRETO da tela no banco (`db.add_requested_bye`), sem passar por serviço. O que
  se validava era o FORMATO do formulário (tem alvo? tem rodada? o tipo e F/H/Z?)
  — não havia onde uma política morar. Agora há
  `PairingService.request_bye()`, com auditoria, e a tela chama o serviço;
- **módulo puro `bye_policy.py`** com as regras e os textos. `ByePolicy` lê as
  duas configurações novas (schema **v48**): `max_requested_byes` e
  `last_requested_bye_round`, ambas com padrão `0` = SEM LIMITE, que e o
  comportamento que os torneios existentes sempre tiveram;
- **rodada já gerada e recusada**, e o recado diz por que: o pareamento daquela
  rodada já está feito, então o bye seria "aceito e nunca aplicado" — que era
  exatamente o defeito. Rodada fechada idem, apontando para a correção com
  motivo (ARB-01);
- **jogador inativo e recusado NA HORA DO PEDIDO**, com o motivo. Sobra um único
  caminho para o descarte — o jogador que sai DEPOIS de pedir —, e esse agora
  AVISA: evento de auditoria, log e pendência `attention` no painel. A geração
  segue: barrar a rodada por um pedido que ficou para trás seria trocar um
  silêncio ruim por uma parada pior;
- **o bye de zero ponto (`Z`) não conta para o limite.** Limita-lo puniria quem
  AVISOU que faltaria, em vez de simplesmente não aparecer — e ele não da ponto
  nenhum. Corrigir o tipo de um bye já existente também não esbarra no limite.

Sobre o `disable_bye`, o escopo dava duas saídas ("cobrir também os byes
solicitados ou renomear a flag"): foi **renomeada** (rotulo "Desativar bye
alocado (PAB)"). São coisas diferentes — aquela flag desativa o bye que o sistema
DA a quem sobra num número ímpar, e um bye solicitado e o jogador AVISANDO que
faltaria. Juntar as duas quebraria o regulamento mais comum, que exige número par
de presentes mas aceita ausência avisada.

Fica pendente do escopo original: **prazo de solicitação** por data. Ele existe
hoje na forma que resolve o defeito — o pedido vale enquanto a rodada não foi
gerada —, e um prazo em horas exigiria relógio de torneio, que o sistema não tem.
Fica também o bye ALOCADO que repete quando todos já receberam (hoje só alerta):
e regra de motor de pareamento, e não de política de bye.

Critérios de aceite:

- [x] pedido acima do limite ou fora do prazo e rejeitado com mensagem clara;
- [x] bye para rodada fechada e impossível (e para rodada já gerada também);
- [x] testes cobrem os limites e o descarte avisado.

Cobertura: 24 testes em `tests/test_core_arb04.py`.

Problema original:

- não há limite de byes por jogador, nem proibição de bye de meio ponto nas
  últimas rodadas (regra comum de regulamento), nem validação contra rodada já
  fechada (o bye e aceito e nunca aplicado, silenciosamente);
- byes de jogadores inativos são descartados sem aviso
  (`pairing_service.py:742-746`);
- `disable_bye` não impede byes solicitados (`:754-774`);
- o bye alocado pode repetir quando todos já receberam, virando só alerta.

Escopo:

- configurações por torneio: máximo de byes H por jogador, última rodada
  permitida, prazo de solicitação;
- rejeitar (com mensagem) bye para rodada fechada ou jogador inativo;
- fazer `disable_bye` cobrir também os byes solicitados ou renomear a flag.

Critérios de aceite:

- [x] pedido acima do limite ou fora do prazo e rejeitado com mensagem clara;
- [x] bye para rodada fechada e impossível;
- [x] testes cobrem os limites e o descarte avisado.

#### ARB-05 - Retirada e reentrada com histórico por rodada

Status: CONCLUÍDO (2026-07-31).

Como ficou:

- **tabela `player_status_events`** (schema **v49**), append-only: torneio,
  jogador, rodada de vigência, estado, motivo e autor. O campo
  `players.player_status` CONTINUA existindo — ele e o estado corrente, que o
  pareamento já lê; o que faltava era o rastro, e um campo único apaga o
  anterior a cada mudança;
- **a mudança vale da PRÓXIMA rodada.** A rodada em andamento já foi pareada:
  tirar alguém agora não desfaz a mesa dele — isso e resultado (W.O.) ou
  correção. E também a leitura do salão ("a partir da 4 ele não joga mais");
- **módulo puro `participation.py`** responde o que o histórico guarda:
  `status_at_round`, `absence_rounds`, `history_lines` e um `summarize` que
  agrupa faixas ("Fora R3-R5"). Quem grava e
  `PairingService.set_player_participation()`, com auditoria; as DUAS telas que
  mexiam no estado (cadastro de jogadores e chamada inicial) passaram a chamar o
  serviço em vez de `db.set_player_status` cru;
- **reentrada de quem DESISTIU exige motivo**, e a de quem só faltou não. Voltar
  um desistente e decisão arbitral e vai para a ata; voltar quem faltou uma
  rodada e rotina de salão. Repetir o estado atual e recusado;
- **seção própria na ata**: "Desistências, ausências e reentradas", com situação
  final, rodadas fora e o histórico com os motivos.

Sobre o TRF, e vale registrar porque o escopo pedia a distinção: **o arquivo não
tem código para separar "desistiu" de "faltou"**. As duas viram `0000 - Z` (não
pareado, zero ponto), e isso está CERTO — o que a FIDE distingue e `Z` de `-`
(pareado e não compareceu, que e forfeit e exige mesa), e essa distinção o
sistema já fazia por construção. A diferença entre desistência e ausência e do
REGULAMENTO, não do arquivo, e por isso ela mora na ata. Há teste para as duas
afirmações.

Critérios de aceite:

- [x] jogador que sai e volta e pareado corretamente e o histórico mostra as
  rodadas de ausência;
- [x] TRF diferencia os casos que o formato permite diferenciar (`Z` x `-`), e a
  ata carrega a distinção que o formato não tem;
- [x] auditoria registra quem/quando/motivo.

Cobertura: 22 testes em `tests/test_core_arb05.py`.

Problema original:

- `player_status` e um campo único sem histórico: `withdrawn` e `absent`
  produzem o mesmo efeito (`active = 0`) e não há rastro de "saiu na rodada 3,
  voltou na 5". No TRF tudo vira `0000 - Z`, sem distinção entre desistência,
  ausência e bye zero solicitado.

Escopo:

- registrar eventos de retirada/reentrada por rodada (tabela própria ou
  `audit_events` estruturado);
- pareamento exclui o jogador nas rodadas de ausência e o reinclui na volta;
- exportação TRF diferencia `Z` (ausência anunciada) de `-` (forfeit) conforme
  o caso; ata final lista desistências com rodada.

Critérios de aceite:

- [x] jogador que sai e volta e pareado corretamente e o histórico mostra as
  rodadas de ausência;
- [x] TRF e tabela cruzada diferenciam os casos;
- [x] auditoria registra quem/quando/motivo.

### EPIC H - Motores de pareamento (correções)

Prioridade: alta. Origem: auditoria arbitral de 2026-07-29.

#### PAR-01 - Round-robin com tabela persistida e returno

Status: FEITO (2026-08-01) — com a anulação dos 50% entregue como AVISO, não
como automatismo (ver "Fica pendente").

Problema:

- `round_robin_pairings` recalculava o circulo a cada rodada a partir da lista
  ATIVA ordenada por rating: desativar um jogador ou editar um rating no meio
  do evento mudava todo o calendário restante (revanches e confrontos perdidos);
- o bye do rodízio gravava `result = "1-0"` e só pontuava certo porque
  `bye_points` tem padrão 1.0 — e aparecia como VITÓRIA em tudo que lê o
  resultado (TRF, tabela cruzada, contagem de vitórias);
- não havia duplo turno (returno), formato padrão de fechados e torneios de
  norma, nem tabelas de Berger (FIDE C.05).

Como ficou:

- **o rodízio deixou de ser um pareamento e virou um CALENDÁRIO**. Os números
  de rodízio são atribuídos UMA vez (tabela `round_robin_numbers`, schema v51),
  na geração da primeira rodada, pela ordem inicial do torneio; daqui para a
  frente cada rodada e só lida da tabela de Berger. Desativar um jogador ou
  corrigir um rating no meio do evento não mexe em confronto nenhum;
- **a tabela de Berger vem da implementação de referência** (`gacrux/berger.py`,
  Otto Milvang — o mesmo autor do motor FIDE que já pareia e desempata aqui).
  Manter uma segunda implementação da mesma norma repetiria o erro que a TBK-03
  documentou. O acoplamento e a um módulo SEM dependências e está preso por
  teste: as tabelas de 6 e 8 jogadores conferidas contra o Handbook;
- **quem desistiu continua com mesa**. No rodízio não existe "tirar da rotação"
  sem desmanchar o torneio: a mesa e gerada e o resultado sai por W.O., com
  aviso ao árbitro dizendo isso. Quem se inscreve DEPOIS do sorteio fica fora do
  calendário — também com aviso, em vez de entrar e deslocar todo mundo;
- **returno** (`round_robin_double`): o calendário roda duas vezes e a volta
  repete a ida com as cores trocadas. O aviso de rodadas configuradas x rodadas
  do calendário evita o torneio que para no meio;
- **bye de verdade** (`is_bye`, resultado `BYE`), como no Suíço;
- **a prévia não sorteia**: `_individual_next_round_plan` só grava com
  `persist=True`, que e a geração. Uma prévia que sorteasse o calendário mudaria
  o torneio sem gerar rodada nenhuma;
- a versão antiga em `fide_dutch.py` foi REMOVIDA, e não deixada como fallback:
  duas implementações do mesmo calendário divergem, e a esquecida e a que alguém
  usaria.

Arquivos: `pairing/round_robin.py` (novo, puro), `pairing/fide_dutch.py`,
`pairing_service.py`, `core/database_schema.py`, `core/database_tournament_core.py`,
`database/migrations/legacy_migrations.py` (v51), `services/constants.py`,
`ui/screens/tournament_settings_ui.py`.

Critérios de aceite:

- [x] desativar jogador não altera os confrontos futuros dos demais;
- [x] fixture Berger de 6 e 8 jogadores confere com a tabela FIDE;
- [x] returno inverte cores corretamente.

Fica pendente:

- **anulação dos 50% (FIDE C.05)**: o sistema DETECTA quem desistiu antes da
  metade e avisa, mas não anula. Anular reescreve a classificação publicada —
  os pontos dos ADVERSÁRIOS mudam — e teria de valer também dentro do motor FIDE
  de desempate, que recalcula tudo pelo arquivo TRF. E o mesmo argumento da
  TBK-03: duas implementações da mesma norma divergem. Merece tarefa própria;
- **rodízio por EQUIPES** (`round_robin_team_matches`) continua recalculando o
  circulo a cada rodada, com o mesmo defeito que este item consertou no
  individual. A tabela `round_robin_numbers` e de jogadores; o caminho de
  equipes pede a sua.

#### PAR-02 - Aceleração e entrada tardia no caminho Gacrux

Status: FEITO (2026-07-31).

Problema:

- aceleração só era aplicada no motor próprio; com `pairing_system =
  gacrux_swiss` (padrão) ela era silenciosamente ignorada, sem aviso;
- `starting_points` de entrada tardia não chegava ao Gacrux: o TRF-16 exporta as
  rodadas ausentes como `0000 - Z` (0 ponto), então o Gacrux pareava o entrante
  tardio com pontuação diferente da classificação publicada.

Como ficou:

- **o motor lê células, não o campo de pontos**. Esse e o eixo da correção: a
  linha 001 já levava os pontos da CLASSIFICAÇÃO (que incluem `starting_points`
  e os ajustes da TBK-01), mas o Gacrux ignora esse campo e soma as células de
  rodada. A diferença entre os dois e exatamente o que não chegava ao motor —
  e agora e medida, no próprio arquivo, e materializada em células de bye nas
  rodadas anteriores a inscrição (`H` de preferência, `F` só quando o deficit
  não cabe em meios pontos). O que não da para representar — diferença negativa,
  ou que não cabe nas rodadas de ausência — vira aviso, nunca silêncio;
- **só o PREFIXO de rodadas sem pareamento e reescrito**. Um `0000 - Z` no meio
  do torneio e bye de zero ponto pedido ao árbitro (ARB-04) ou rodada de
  retirada (ARB-05); reescreve-lo seria desfazer uma decisão dele;
- **aceleração viaja como registro 250**, um por faixa contigua de start-rank.
  A faixa e calculada, e não assumida: com ordem inicial que não seja a do
  start-rank do TRF (que sai por rating), a metade acelerada e picada. Nas
  rodadas do esquema, o conjunto acelerado e o mesmo do motor próprio;
- **bônus que o 250 não transporta cai no motor próprio COM AVISO**. O Gacrux
  converte os pontos do registro em um código de resultado e de volta em pontos:
  só 1,0 e 0,5 sobrevivem a viagem, o resto viraria zero em silêncio — que e o
  defeito que esta tarefa existe para matar. `baku` continua sem bônus em
  nenhum motor, e agora avisa no pareamento (não só na exportação TRF25);
- **os avisos chegam ao árbitro em três portas**: a prévia da próxima rodada
  (antes de gerar, contados em `alerts_count`), o log e o evento de auditoria
  `pairing_warning` (depois, para quem for conferir a rodada meses depois);
- **o arquivo oficial não muda**. O ajuste vive no TRF temporário que alimenta o
  motor; o TRF16 de envio a federação continua saindo do exportador, intocado;
- modularizacao: a geometria da linha 001 estava duplicada entre `trf_import.py`
  e o novo ajuste. Virou `services/trf_layout.py`, com os dois lendo de lá.

Arquivos: `pairing/gacrux_trf.py` (novo, puro), `services/trf_layout.py` (novo),
`pairing/gacrux_engine.py`, `pairing/acceleration.py`, `pairing_service.py`,
`pairing/previews.py`, `ui/screens/pairing_results/state.py`.

Critérios de aceite:

- [x] configurar aceleração com Gacrux gera aviso ou aplica de fato;
- [x] entrante tardio e pareado com os pontos exibidos na classificação;
- [x] teste compara pareamento Gacrux x classificação com entrada tardia.

Fica pendente (backlog, fora do escopo desta tarefa): o motor de DESEMPATE
(`GacruxTiebreakEngine`) exporta o seu próprio TRF e continua somando as células
cruas, então Buchholz & cia. ainda enxergam o entrante tardio com os pontos que
ele fez no tabuleiro. E o mesmo defeito da TBK-01 com `point_adjustments`, já
anotado em `tiebreaks.py`; a correção e a mesma função pura, mas mexe em valores
de desempate homologados e pede a sua própria tarefa.

#### PAR-03 - Knockout e Scheveningen maduros

Status: FEITO (2026-08-01).

Problema:

- no mata-mata, empate, duplo W.O. ou resultado vazio promoviam o melhor seed
  silenciosamente, sem desempate nem registro do critério. E o W.O. e o
  resultado por decisão do árbitro (`1F-0F`, `1U-0U`), que TEM vencedor, caiam
  na mesma vala: o avanço saia do ranking, e não do placar;
- Scheveningen exigia grupos exatamente iguais e recalculava a escala a cada
  rodada — desistência deslocava os confrontos futuros e ainda desigualava os
  grupos, o que passava a RECUSAR a geração.

Como ficou:

- **quem avança sai dos PONTOS do resultado**, e não de uma lista de códigos:
  `board_winner` usa `RESULT_POINTS`, então W.O. e decisão arbitral decidem a
  mesa como qualquer vitória. Empate, dupla ausência e mesa em branco não
  decidem — e agora PARAM a geração da próxima fase com a lista das mesas;
- **o desempate e registrado, não simulado**. O sistema não joga o blitz nem o
  armagedom: ele guarda quem passou e por que critério (mini-match, rápidas,
  blitz, armagedom, critério do regulamento, decisão do árbitro), com motivo
  obrigatório nos dois últimos — são os que não se explicam sozinhos. Tabela
  `knockout_advancements` (schema v52), evento de auditoria e dialogo na tela de
  rodadas;
- **a chave explica cada avanço** (`knockout_bracket` + "Chave do mata-mata" no
  menu da rodada): fase a fase, com o motivo ao lado de quem passou e a mesa sem
  decisão aparecendo como pendência em vez de sumir;
- **disputa de 3o lugar** opcional (`knockout_third_place`): os dois perdedores
  da semifinal jogam na mesma rodada da final. Quem vence ali não volta a chave
  principal — o filtro e "avançou também na fase anterior", sem coluna nova;
- **Scheveningen com escala guardada**: grupo e número passam a morar no jogador
  (`scheveningen_group` já existia, `scheveningen_number` e novo). Quem desiste
  mantém a cadeira e a mesa sai por W.O., com aviso — os mesmos avisos do rodízio,
  agora num módulo compartilhado (`pairing/fixed_calendar.py`);
- **bye do mata-mata virou bye de verdade**, como no rodízio (PAR-01);
- as duas versões antigas em `fide_dutch.py` foram REMOVIDAS.

Arquivos: `pairing/knockout.py` e `pairing/scheveningen.py` (novos, puros),
`pairing/fixed_calendar.py` (novo), `pairing/fide_dutch.py`, `pairing_service.py`,
`core/database_schema.py`, `core/database_tournament_core.py`,
`database/migrations/legacy_migrations.py` (v52), `services/constants.py`,
`ui/screens/pairing_results/knockout.py` (novo), `.../state.py`, `.../view.py`,
`ui/screens/tournament_settings_ui.py`.

Critérios de aceite:

- [x] empate em KO exige decisão registrada antes de gerar a próxima fase;
- [x] a chave exibe por que cada jogador avançou;
- [x] Scheveningen sobrevive a desistência sem corromper confrontos passados.

Fica pendente: substituto no lugar do desistente (o escopo dizia "bye ou
substituto"); hoje a mesa sai por W.O., que e a saída que não inventa um jogador
que o regulamento talvez não autorize.

#### PAR-04 - Dividas técnicas do núcleo de pareamento

Status: FEITO (2026-08-03) — os quatro itens pontuais em 2026-07-30; os três de
motor (topscorers C.3, flutuação em jogo não disputado e float repetido por
equipes) em 2026-08-03.

Como ficou (parte pontual):

- **`TEAM_PAIRING_METHODS` duplicado**: a segunda atribuição (só `swiss`)
  apagava a primeira em silêncio, e por isso o round-robin por equipes era
  recusado pela validação e sumia do menu. A linha morreu, e ficou no lugar um
  comentário dizendo por que não se redefine ali. Um teste lê o próprio
  `constants.py` e falha se a constante voltar a ser atribuída duas vezes — o
  defeito era invisível para quem lia só o topo do arquivo;
- **round-robin por equipes de fato pareando**: a geração de rodada por equipes
  nunca lia `team_pairing_method` (só a exportação e o motor de desempate liam),
  então destravar a constante sozinha teria deixado o árbitro escolher um método
  que o motor ignorava — uma mentira em vez de uma limitação. Nasce
  `round_robin_team_matches` (puro, em `team_swiss.py`): mesma rotação Berger do
  round-robin individual, equipe fantasma quando o número e ímpar, cor de equipe
  alternando com a paridade da rodada (sem isso a equipe que não gira jogaria
  sempre de brancas), e os tabuleiros saindo do `team_match_payload` que já
  existia. Bye SOLICITADO e recusado nesse modo: tirar uma equipe da rotação
  desloca todo mundo e faz pares se repetirem — num calendário fixo quem não
  comparece perde por W.O., não "folga", e a recusa e explicita porque o
  silêncio aqui pareava a rodada errada sem ninguém ver;
- **troca de cores com auditoria**: `swap_pairing_colors` era chamado direto do
  `db` pela tela — a ÚNICA mutação de rodada sem passar pelo serviço e, portanto,
  sem trilha. Agora há `PairingService.swap_pairing_colors`, espelhando o de
  equipes, com as guardas (rodada fechada, mesa de outro torneio, bye, resultado
  já lançado) e evento `pairing_colors_swapped`. O caminho de equipes já passava
  pelo serviço mas também não auditava: ganhou `team_board_colors_swapped`;
- **`pending` acumulado no fechamento por equipes**: era uma lista única para
  todos os confrontos, então um tabuleiro em branco no primeiro confronto fazia
  todos os seguintes pularem o sumario. A pendência passou a ser por confronto;
- **`KeyError` cru em `team_match_summary`**: tabuleiro em branco ou com código
  desconhecido subia como `KeyError`, que a tela mostrava como "erro inesperado"
  com código de log — para uma situação previsível que o árbitro resolve sozinho.
  Virou `AppError` dizendo qual tabuleiro e o que fazer.

Achado no caminho, fora da lista da auditoria: **`Dialog(self, ...)` em
`swaps.py`**, onde `self` e o objeto de ações e não a janela — o mesmo defeito que
a extração da B-6 encontrou no `qr.py` e que aqui tinha passado. "Trocar jogador"
(individual e equipes) não abria.

Problema (itens pontuais confirmados na auditoria):

- `TEAM_PAIRING_METHODS` definido duas vezes (`constants.py:111` e `:123`); a
  segunda definição sobrescreve a primeira e torna o round-robin por equipes
  inalcancavel (validação rejeita e o menu só mostra Suíço);
- `swap_pairing_colors` e chamado direto da UI (`pairing_results_ui.py:1415`)
  sem passar pelo `PairingService` — única mutação de rodada sem auditoria;
- `pending` acumulado fora do laço em `_close_team_round`
  (`pairing_service.py:1170,1190`) pula confrontos completos do sumario;
- `team_match_summary` levanta `KeyError` bruto com resultado inválido
  (`team_swiss.py:121`);
- critério absoluto C.3 (topscorers) inexistente no motor próprio (cor e
  sempre soft);
- `float_histories` conta W.O. como float enquanto cor e repetição os
  excluem — tratamento inconsistente do mesmo jogo;
- `team_pair_penalty` não penaliza float repetido no Suíço por equipes.

Escopo e critérios de aceite:

- [x] round-robin por equipes volta a ser selecionável (ou e removido da
  constante com changelog) — **selecionável E pareando**;
- [x] troca de cores passa pelo serviço com evento de auditoria;
- [x] fechamento de equipes reporta todos os confrontos completos mesmo com
  pendência anterior;
- [x] resultado inválido em equipes vira `AppError` legível;
- [x] topscorers (C.3) respeitado nas rodadas finais do motor próprio, com
  teste.

Como ficou (parte de motor, 2026-08-03):

- **C.3 com topscorers**: `topscorer_ids` implementa a A.7 — o conceito só existe
  na ÚLTIMA rodada, e topscorer e quem tem MAIS de 50% do que já foi disputado
  (na rodada R, mais de `(R-1)/2`). A exceção entra onde o C.3 de fato mora: na
  BUSCA ESTRITA (`search_dutch_pairing`), que decide o que PODE ser pareado.
  Dois topscorers com a mesma preferência absoluta de cor deixam de ser um par
  proibido — que e o que a rodada decisiva costuma exigir.
  **O que NÃO mudou, de propósito**: o custo de qualidade. A violação de cor
  continua cara no `pair_penalty` para todos, topscorer ou não; o C11 manda
  MINIMIZAR violações, e zerar o custo faria o motor parar de evita-las quando
  havia alternativa. A primeira versão zerava, e a fixture grande do BBP
  (`issue_7`) acusou na hora — pareamento legal, porem pior;
- **flutuação em jogo não disputado**: `float_histories` dava flutuação normal
  aos DOIS lados de um W.O., enquanto cor e não-repetição já o excluíam — o mesmo
  jogo contava de três jeitos. A regra passou a ser a do motor FIDE
  (`compute_flt` do Gacrux, ramo `dutch`): compara pontuação só quando a partida
  foi JOGADA; quem pontuou sem jogar (W.O. a favor, bye que vale ponto) conta
  como DOWNFLOAT; quem perdeu por W.O. (ou levou bye de zero ponto) não flutua;
- **float repetido por equipes**: `team_pair_penalty` ganhou o mesmo
  `float_penalty` do individual, alimentado por `team_float_histories` (novo,
  puro) — os match points de cada confronto já estavam gravados. Sem isso a mesma
  equipe podia descer de grupo rodada após rodada sem o motor preferir outra.

Nota de escopo: os três valem para o MOTOR PRÓPRIO, que desde o PR #66 não é mais
o padrão de pareamento (quem pareia e o Gacrux, que já aplica todas as três). São
consertos do caminho legado — e e por isso que a paridade com o motor homologado
e o critério usado em cada um deles.

Cobertura da parte pontual: 18 testes em `tests/test_core_par04.py` — Berger de
equipes (cada par uma vez, bye rotativo, cores alternando, calendário cheio),
round-robin ponta a ponta pelo serviço (inclusive a recusa do bye solicitado),
troca de cores com trilha nos dois modos e com as quatro recusas, sumario com
recado legível e o fechamento que não descarta mais confronto completo.

### EPIC I - Submissão federativa (FIDE e CBX)

Prioridade: alta. Origem: auditoria arbitral de 2026-07-29.

#### FED-03 - TRF16 de campo completo

Status: FEITO (2026-08-03).

Como ficou:

- **`XXR` e `XXC`** (extensões do dialeto TRF16) passam a sair junto do `142`;
  a cor inicial NÃO e chutada — sai da rodada 1 já pareada, e só cai em `white1`
  quando ainda não há rodada, que e o que o motor faz;
- **`XXA` continua NÃO sendo emitido, de propósito.** O parser da implementação
  de referência monta os valores do `XXA` com as chaves `matchScore`/`gameScore`
  e depois os lê como `matchResult`/`gameResult` — `KeyError` garantido em
  qualquer torneio que traga o registro (achado da PAR-02). A aceleração sai no
  **250**, que o mesmo parser lê certo; ele subiu do TRF25 para o TRF16, porque
  vale para os dois. O motor de pareamento remove o 250 do exportador antes de
  escrever o dele, que e por rodada;
- **`082` só em torneio por equipes**: "082 0" descrevia um torneio por equipes
  com zero equipes;
- **`092` no vocabulário das federações** (`Individual: Swiss-System`), em vez do
  texto proprietário montado com o campo livre `system`;
- **FIDE Event-ID e FIDE ID dos árbitros** passam a sair. O Event-ID **não tem
  registro padrão em nenhum dos dois dialetos** (a FIDE o pede no portal, fora do
  arquivo): vai como `XXE`, na família de extensão, que quem não conhece ignora —
  conferido contra o parser de referência. O ID do árbitro entra entre parênteses
  no 102/112, casado pelo nome com a lista de árbitros do torneio;
- **mesa pareada sem resultado sai em BRANCO**, e não como `Z`: `Z` e "ausência
  conhecida, zero ponto", e dizer isso de um jogo que ainda vai acontecer e
  mentir sobre o torneio. Junto veio um defeito de coluna: o `rstrip()` da linha
  comia a última célula quando ela era uma mesa sem resultado, e a célula sumia
  para quem lê por coluna — inclusive para o motor;
- **modo submissão** (`export(..., submission=True)`, item próprio no menu de
  exportação): resultado pendente, FIDE ID repetido e mesa que não confere entre
  as duas linhas 001 BLOQUEIAM a geração, com a lista de pendências. No modo
  normal — o do dia do evento — o arquivo sai e as mesmas pendências viram aviso;
- **reciprocidade oponente/cor** conferida sobre o ARQUIVO PRONTO: se o 5 diz
  "rodada 3, adversário 12, brancas", a linha do 12 tem de dizer "rodada 3,
  adversário 5, pretas". E a checagem que só o arquivo permite;
- **células de rodada iguais nos dois formatos**: o TRF25 emitia também as
  rodadas configuradas e o TRF16 só as geradas. Agora os dois emitem o que JÁ
  ACONTECEU, e o total do torneio vai no 142/XXR — são números diferentes com
  significados diferentes. Emitir célula de rodada futura, alias, faz o motor
  FIDE tratar o jogador como resolvido naquela rodada e não parear ninguém (foi
  o que a suite acusou na primeira tentativa de unificar por cima).

Problema:

- o TRF16 não emite os códigos de extensão de facto `XXR` (total de rodadas),
  `XXC` (cor inicial) e `XXA` (aceleração) — emite `142` no lugar de `XXR`,
  que e registro TRF25; motores/validadores que esperam o dialeto TRF16 ficam
  sem o total de rodadas;
- `FIDE Event-ID` e validado mas nunca exportado; FIDE ID dos árbitros não sai
  nos registros 102/112;
- partida pareada sem resultado exporta como `Z` (ausência conhecida) —
  semanticamente errado; `082 0` sai em torneio individual; `092` usa texto
  proprietário;
- nenhuma validação de jogador e bloqueante (FIDE ID ausente/duplicado,
  federação, nascimento) — o arquivo sai mesmo assim;
- TRF16 e TRF25 divergem no número de células de rodada emitidas para o mesmo
  torneio.

Escopo:

- emitir `XXR`/`XXC`/`XXA` no TRF16; restringir `082` a equipes; `092`
  compatível com Swiss-Manager/Chess-Results;
- exportar FIDE Event-ID e FIDE ID de árbitros;
- modo "submissão": validações criticas bloqueiam a geração (com lista clara
  de pendências); resultado pendente impede exportar ou exige confirmação;
- validação cruzada de reciprocidade oponente/cor antes de exportar.

Critérios de aceite:

- [x] TRF16 gerado passa no validador do Gacrux e abre no Swiss-Manager — o
  arquivo continua sendo o que alimenta o motor a cada rodada, e a suite de
  pareamento (que roda o Gacrux de verdade) e a prova;
- [x] modo submissão bloqueia arquivo com FIDE ID duplicado ou resultado
  pendente;
- [x] fixture compara TRF16 x TRF25 do mesmo torneio (mesmo número de rodadas).

#### FED-04 - Round-trip TRF fiel

Status: FEITO (2026-08-03).

Como ficou:

- **`U` deixou de ser `F`**. O bye ALOCADO pelo pareamento (`U`) vale o que o
  regulamento do torneio disser (`bye_points`); o `F` vale ponto inteiro por
  definição. Trata-los como a mesma coisa inflava a pontuação de todo TRF de
  Swiss-Manager importado num torneio cujo `bye_points` não fosse 1,0;
- **`Z` preservado**: a ausência conhecida virava NADA, e a rodada sumia do
  histórico do jogador — o TRF exportado depois já não dizia o que o arquivo
  original dizia. Agora ela volta como bye de zero ponto, que e o que ela e;
- **`W`/`D`/`L` já voltavam** desde a ARB-02 (o registro de resultados fez a
  decodificacao virar tabela única); o item da auditoria estava resolvido antes
  desta tarefa;
- **árbitro, calendário e equipes** eram lidos e jogados fora. O 102/112 vira
  árbitro-chefe e adjuntos, o 132 vira o calendário de rodadas, e o 013/310 vira
  equipe de verdade, com o tabuleiro saindo da ORDEM dos start-ranks na linha
  (que e como o TRF declara a ordem de forca). Equipe cujos jogadores o arquivo
  não traz e ignorada — melhor equipe menor do que jogador inventado;
- **round-trip com teste**: exportar -> importar -> exportar devolve as mesmas
  células de rodada, jogador por jogador;
- **rodada sem jogo não é rodada jogada**: preservar o `Z` fez aparecer um efeito
  colateral que a fixture do bbpPairings pegou na hora. Num TRF de torneio EM
  ANDAMENTO, um `0000 - Z` na próxima rodada quer dizer "este jogador não será
  pareado nela" — e uma declaração, e não um resultado. Tratar aquilo como rodada
  jogada criava uma rodada fantasma e empurrava o torneio importado uma rodada a
  frente. A regra passou a ser: só e rodada quem teve pelo menos uma mesa com
  dois jogadores.

Problema:

- a importação TRF trata `U` e `F` como o mesmo bye de ponto inteiro
  (`trf_import.py:149-151`) — importar do Swiss-Manager pode inflar pontuação
  quando `bye_points` difere de 1.0; `Z` e descartado (ausência some do
  histórico); `W`/`D`/`L` não são decodificados; árbitros, datas de rodada,
  equipes e todos os registros TRF25 são ignorados.

Escopo:

- distinguir `U` (bye alocado, pontua por `bye_points`) de `F`;
- preservar `Z` e decodificar `W`/`D`/`L`;
- importar árbitros, datas (132) e seção de equipes;
- teste de round-trip export -> import -> export byte-comparavel para os
  campos suportados.

Critérios de aceite:

- [x] TRF do próprio Albericus reimporta sem perda de byes/ausencias;
- [x] TRF do Swiss-Manager com bye `U` pontua conforme configuração;
- [x] round-trip coberto por teste automatizado.

#### FED-05 - Lista FIDE: data de nascimento e robustez do download

Status: FEITO (2026-08-03).

Como ficou:

- **quem estava errado era a VALIDAÇÃO, não o dado**. A FIDE publica só o ANO de
  nascimento, e o TRF aceita `YYYY` no campo 70-79 — mas `_trf_date_is_valid`
  exigia data completa, então todo jogador vindo da lista disparava "sem data de
  nascimento valida" e envenenava o arquivo do plantel inteiro. O ano continua
  gravado como ano (completar com 01/01 inventaria um aniversario que ninguém
  informou, e ele reapareceria num certificado); `YYYY-00-00`, que e como outros
  programas dizem "só o ano", e lido como a mesma coisa;
- **o leitor virou módulo puro** (`services/fide_list.py`), com as colunas
  documentadas. Isso permitiu testar com fixture o que só o download exercitava,
  e ai apareceram os dois defeitos de robustez: a linha era aceita a partir de
  120 caracteres enquanto o ano mora em 127-131 (o jogador entrava SEM
  nascimento), e a linha malformada era descartada em silêncio — a lista de erros
  existia e nunca recebia nada, então arquivo truncado parecia importação
  completa. Agora há um teto de erros relatados, com resumo do que sobrou;
- **rede**: `https`, tempo maior, e `HTTPError`/`URLError`/ZIP inválido viram
  mensagem que diz o que fazer (baixar do site e importar por arquivo) em vez de
  `URLError` cru na tela. As linhas ignoradas aparecem no aviso de conclusão.

Problema:

- a importação da lista FIDE grava só o ANO em `birth_date`
  (`rating_service.py:333,351`): o campo 70-79 do 001 sai inválido e todo
  jogador importado dispara o aviso de nascimento — envenena o TRF do plantel
  inteiro;
- download da FIDE sem tratamento de erro (`:310`, `URLError` cru na UI), URL
  em `http://`, `errors` sempre vazio (linha malformada nunca é reportada),
  corte de linha em 120 chars lê nascimento em 126-131.

Escopo:

- armazenar ano como ano (campo próprio ou `YYYY-00-00` documentado) e emitir
  o 001 com ano quando for o único dado (formato aceito pela FIDE);
- tratar falha de rede com mensagem, `https`, e reportar linhas ignoradas.

Critérios de aceite:

- [x] importar lista FIDE não gera avisos falsos de nascimento no TRF;
- [x] falha de download mostra erro amigável;
- [x] teste do parser de largura fixa com fixture real.

#### FED-06 - Normas FIDE corretas e certificados IT

Status: FEITO (2026-08-04).

Como ficou:

- **o regulamento virou módulo**. `src/services/norms/handbook.py` guarda os
  números do B.01 (seção 1.4, edição de 2024) e MAIS NADA — não sabe o que e
  torneio. `opponents` decide que partida conta e com que rating, `evaluation`
  julga uma norma, `report` monta o relatório, `it3` descreve o certificado e
  `it3_pdf` desenha. `fide_norms.py` virou fachada: ninguém precisou trocar
  import.
- **titulado passou a ser por NÍVEL**. CM e WCM saem por texto expresso do
  1.4.5; NM e WNM nunca foram título FIDE. Além do piso de 50% de titulados, a
  norma cobra 1/3 (mínimo 3) do SEU nível: GM exige GMs, IM exige GM ou IM, e
  assim por diante. Nove FMs cumprem os 50% e não cumprem o 1/3 de GM — que era
  exatamente o open que o motor antigo aprovava.
- **o piso de rating ajustado (1.4.6) sobe UM adversário, o mais fraco.** Subir
  todos era generoso demais (qualquer open indicaria norma); não subir nenhum
  seria severo demais com quem enfrentou um adversário abaixo do piso. Como o
  piso e por norma (2200/2050/2000/1850), o **Ra e o Rp são calculados por
  norma**, e não uma vez por jogador — foi a mudança estrutural do item.
- **a tabela do Anexo não foi copiada, foi derivada.** As frações do texto
  (50%, 1/3, 3/5, 2/3, 20% de n+1) com o arredondamento de cada uma reproduzem
  a tabela publicada de 9 a 13 rodadas — o teste compara com o Anexo. Assim 15,
  17 e 19 rodadas também saem certas.
- **IT3 preenchido em PDF**, um por norma detectada, com o torneio, o candidato,
  a tabela de adversários rodada a rodada (título, federação, rating real,
  rating usado pela norma, cor e resultado) e o fechamento com Ra, Rp e as
  contagens. Rótulos em inglês porque o formulário e entregue a FIDE; o aviso de
  que isto e apoio, e não homologação, sai em português. Sem norma atingida o
  export avisa em vez de gerar papel em branco.

Fora do entregue (de propósito):

- **IT1 e IT2 continuam sem formulário próprio.** O IT1 e registro do torneio
  ANTES do evento (não há dado no sistema para preencher) e o apoio ao IT2 e o
  relatório `Rating FIDE`, que já existe — a correção do que ele calcula (K,
  piso, ritmo) e o `FED-07`, e emitir o formulário com número errado seria
  pior do que não emitir.
- **O IT3 ficou fora da exportação em lote.** O lote isola falhas, mas a
  ausência de norma não é falha: sairia uma linha de erro em quase todo
  torneio, e erro que e o caso normal vira ruído que ninguém lê.

Armadilhas anotadas:

- a federação do candidato saia na conta de federações por um `add` explicito —
  o código antigo somava a própria federação ao conjunto dos adversários;
- `unrated = 1400` e da edição de 2024 (era 1000 antes), e por isso mora no
  módulo do regulamento, não espalhado no cálculo;
- em round-robin, partida contra não ratado que zerou contra ratados não conta
  (1.4.2) — a exclusão só se aplica quando o método de pareamento e round-robin,
  então o relatório precisa das configurações do torneio, que antes não lia.

Problema:

- `_has_title` conta CM/WCM/NM/WNM como "titulado" (`fide_norms.py:21,33-34`);
  o Handbook exige contagem por nível (norma de GM: mínimo de GMs e de
  titulados IM+) — um torneio cheio de CMs pode indicar norma indevida;
- a contagem de federações inclui a federação do próprio candidato
  (`:122-124`); faltam limites de mesma federação e de não ratados, piso de
  rating de adversário, e a tabela proporcional de 7 a 13 rodadas
  (`min_games` fixo em 9);
- não existem certificados IT1/IT2/IT3 — sem o IT3 o árbitro não consegue
  submeter a norma que o próprio sistema diz ter sido atingida.

Escopo:

- corrigir os indicadores conforme o Handbook B.01 (títulos) vigente;
- gerar IT3 preenchido (PDF) por norma detectada, e apoio ao IT2/relatorio de
  rating;
- manter o texto "assistência ao árbitro, não homologação".

Critérios de aceite:

- [x] fixture de norma valida os indicadores — e a tabela do Anexo do B.01 (9 a
  13 rodadas) e conferida contra os limites derivados. O campo de teste e
  SINTÉTICO de propósito: o que precisa ser exercitado e a fronteira de cada
  regra (o terceiro GM, o quinto titulado, a segunda federação), e num torneio
  real esses números caem onde caem;
- [x] IT3 sai preenchido com os dados do torneio e do candidato;
- [x] federação do candidato fora da contagem de federações.

#### FED-07 - Rating: K correto, piso e ritmo

Status: FEITO (2026-08-04). Schema v53.

Como ficou:

- **o regulamento virou DADO** (`src/services/rating/regulation.py`): faixas de
  K, piso, teto de K x n e regra de estreia são campos de um `RatingRegulation`,
  e cada perfil declara de ONDE vieram seus números e se alguém os conferiu. O
  perfil FIDE sai conferido contra o B.02 (edição em vigor desde 2024); o da CBX
  sai com a forma certa e marcado como NÃO conferido — o regulamento nacional
  não está publicado em lugar que o programa consiga ler, e inventar número de
  regulamento e pior do que admitir que não se sabe. O árbitro edita os valores
  em `Config. torneio -> Oficial`, e o relatório diz que vieram dali.
- **um interpretador de ritmo só** (`src/services/time_control.py`). O registro
  222 do TRF25 e a classificação standard/rapido/blitz liam o mesmo texto por
  caminhos diferentes; agora leem pelo mesmo. Dois interpretadores acabariam
  discordando, e o arquivo da federação diria um ritmo enquanto o relatório
  calculava por outro.
- **cada ritmo usa a SUA lista.** `players` ganhou `rapid_rating` e
  `blitz_rating` (o snapshot da lista oficial já guardava os três; só o standard
  chegava ao jogador do torneio). Faltando o rating do ritmo, o relatório cai no
  standard e AVISA, com a contagem de quantos jogadores — trocar de lista calado
  produz um ΔElo que parece certo e não e.
- **K = 40 de jogador novo passou a disparar.** A regra existia e o relatório
  nunca passava `games_played`: o argumento ficava `None` e a regra caia fora
  sozinha. A coluna nova começa em `0`, que aqui e DESCONHECIDO e não estreante
  — tratar o plantel inteiro como estreante daria K = 40 a todo mundo.
- **sub-18 saia um ano antes**: o B.02 da o K de desenvolvimento até o FIM DO
  ANO do aniversario de 18, e o código usava `< 18`.
- **piso e rating inicial**: Rc abaixo do piso sai no piso, sinalizado; quem não
  tem rating recebe a estimativa do 8.2.2, que NÃO e a performance — a conta
  acrescenta dois adversários fictícios de 1800 empatados, tem teto de 2200,
  mínimo de 5 partidas e descarta quem zerou na estreia (8.2.1).
- o relatório passou a mostrar a origem do Ro e o MOTIVO de cada K: "K = 40" sem
  motivo não se confere.

Fora do entregue (de propósito):

- **o arquivo de submissão da CBX.** O formato aceito não está publicado; sem
  ele, gerar arquivo seria adivinhar o layout de quem recebe. O que da para
  fazer sem o documento — modelar o regulamento — está feito.
- **`SGm` da lista da FIDE não vira `games_played`.** A coluna publica as
  partidas do PERÍODO de rating, não o total da vida do jogador; usá-la na regra
  das 30 partidas daria K = 40 a mestres. `games_played` e preenchido pelo
  árbitro ou por fonte que publique o total.
- **o teto de K x n e aplicado ao torneio**, não ao período de rating inteiro,
  que e o que o B.02 descreve: o programa só conhece o torneio. Praticamente
  nunca morde, e quando morde e para menos.

Problema:

- K=40 de jogador novo nunca dispara (`build_fide_report_rows` não passa
  `games_played`, `fide_rating.py:202-207`); regra dos 400 apenas reportada;
  sem piso de rating; sem distinção standard/rapid/blitz (lista, K e relatório
  usam um único rating); não há cálculo de rating inicial de não ratado;
- o relatório CBX e o algoritmo FIDE com outra coluna — o regulamento CBX
  (K, piso, não ratados) não está modelado e não existe arquivo de submissão
  CBX.

Escopo:

- passar `games_played` ao K e aplicar piso configurável;
- classificar o torneio em standard/rapid/blitz a partir do controle de tempo
  estruturado (ver ORG-03) e usar a lista/K corretos;
- modelar o regulamento CBX de rating e gerar o relatório de submissão no
  formato aceito pela CBX.

Critérios de aceite:

- [x] jogador com menos de 30 partidas recebe K=40 no relatório;
- [x] torneio rápido usa rating rápido dos inscritos;
- [~] relatório CBX documentado contra o regulamento vigente — o regulamento da
  CBX não está publicado em formato legível pelo programa (o site expõe só a
  busca de rating e o Caderno de Regulamento de Torneios não traz a formula).
  Em vez de afirmar números que ninguém conferiu, o perfil CBX e editável e sai
  marcado como NÃO conferido, e o relatório repete a marca. Fecha quando o
  regulamento for obtido: e preencher o perfil.

### EPIC J - Organização do torneio (categorias, prêmios, agenda)

Prioridade: média-alta. Origem: auditoria arbitral de 2026-07-29. Itens com
intersecção com `ESPEC_PARIDADE_SWISSMANAGER.md` (E4/E10) — detalhar lá quando
virar implementação.

#### ORG-01 - Categorias configuráveis por torneio

Status: FEITO (2026-08-04). Schema v54.

Como ficou:

- **a categoria virou DADO** (`src/services/categories/`): nome, tipo (idade,
  rating, sexo, marca, aberta), faixa e data de referência numa tabela por
  torneio. `definition` descreve, `matching` decide quem pertence, `defaults`
  guarda o conjunto anterior e `assignment` combina os dois. `core/categories.py`
  virou fachada — ninguém precisou trocar import.
- **torneio SEM categoria cadastrada continua igual.** A lista vazia significa
  "use o padrão", e o padrão e a tradução literal das constantes antigas —
  inclusive `Adulto` (21-49) e `Aberto` (2200+), que eram fallbacks implícitos e
  quase se perderam. Um teste compara as doze faixas de idade e os nove cortes
  de rating contra o cálculo antigo, fronteira por fronteira.
- **máximo INCLUSIVO em idade, EXCLUSIVO em rating.** "Sub-12" aceita quem
  completa 12; "Sub-1400" recusa 1400. E como o edital escreve e como o programa
  já se comportava (`age <= limite`, `rating < limite`); igualar os dois
  obrigaria o árbitro a digitar 1399, que e onde o erro de digitação mora.
- **"Feminino" virou categoria** e a classificação por categoria passou a
  agrupar por TODAS as categorias premiáveis do jogador. Era só isso que faltava
  para a classificação feminina existir: a jogadora Sub-10 aparecia no Sub-10 e
  em lugar nenhum mais, porque o agrupamento usava a categoria PRINCIPAL e
  principal só tem uma.
- **duas perguntas separadas**: de quais categorias o jogador PARTICIPA (todas,
  para a classificação filtravel) e quais são AS DELE (a mais estreita de cada
  dimensão — Sub-10, Sub-1400, Feminino — em `players.categories`). Guardar as
  seis faixas etárias que um menino de 10 anos satisfaz encheria a tela sem
  dizer nada.
- **idade e a COMPLETADA no ano de referência**, não a do dia: a FIDE só publica
  o ano de nascimento e metade dos cadastros também, e a idade exata daria duas
  contas diferentes no mesmo torneio conforme o jogador tivesse data completa ou
  não. A data de referência (do torneio ou da categoria) escolhe o ano.
- UI: editor de categorias na aba `Premiacao`, com botão "Usar faixas padrão"
  para partir das treze e mexer em duas.

Armadilhas anotadas:

- **a categoria escrita a mao só cede para o cálculo da SUA dimensão.** Um
  "Sub-18" gravado em cadastro sem data de nascimento continua "Sub-18"; a
  primeira versão deixava virar faixa de rating e quebrou quatro testes.
- **o agrupamento tem de incluir a categoria principal**, e não só a lista
  calculada: nome que o árbitro inventou ("Absoluto", "Convidados") não sai de
  faixa nenhuma e sumiria da classificação por categoria.
- o snapshot de API pública (`tests/fixtures/database_public_api.txt`) precisa
  ser regenerado a cada método novo do `Database` — e o trecho de regeneração
  que estava documentado APAGAVA o cabeçalho do arquivo (o teste ignora linhas
  `#` e ninguém via). Corrigido junto.

Fora do entregue (de propósito):

- **a alocação de prêmio multi-categoria e o `ORG-02`.** E literalmente o
  problema descrito lá ("prêmio Feminino nunca é alocado automaticamente"): este
  item entrega a CLASSIFICAÇÃO por categoria, e o alocador continua casando pela
  categoria primaria até o próximo item.
- **o campo de texto livre `Categorias` continua existindo**, e não foi migrado
  para linhas: adivinhar categoria a partir de texto solto inventa categoria que
  ninguém cadastrou.

Problema:

- faixas etárias (Sub-08..20, S50+, S65+) e de rating (1400/1800/2200) são
  hardcoded em `core/categories.py:6-19`; um edital com Sub-07/09/11/13,
  Veterano 60+, ou cortes 1600/2000 não é configurável;
- "Feminino" e tag de prêmio, não categoria — não existe classificação
  feminina nem prêmio feminino automático;
- a data de referência da idade não é parametrizável (usa o ano do torneio;
  FIDE/CBX usam 1o de janeiro).

Escopo:

- tabela de categorias por torneio (nome, tipo idade/rating/sexo/tag, faixas,
  data de referência);
- jogador pode pertencer a múltiplas categorias premiáveis;
- classificação filtravel por categoria e seção na ata/podio.

Critérios de aceite:

- [x] edital com faixas fora do padrão e configurável sem texto livre;
- [x] classificação feminina sai automaticamente quando configurada;
- [x] data de referência altera o cálculo de idade nos testes.

#### ORG-02 - Premiação conforme edital

Status: FEITO (2026-08-04). Schema v55.

Como ficou:

- **prêmio de categoria casa com TODAS as categorias do jogador** (ORG-01):
  Sub-12, Sub-1800 e Feminino são três disputas, e o alocador só enxergava a
  principal. E só isso que faltava para o prêmio Feminino ser alocado sozinho.
- **política POR PRÊMIO** (`tournament_prizes.cumulative`): o edital típico soma
  o Feminino ao geral mesmo dizendo "apenas o maior prêmio" para o resto, e não
  havia como dizer isso. `currency` também entrou, como a spec E4 prévia.
- **o "Sistema Hort" mudou de lugar, porque não era o Sistema Hort.** O que
  existia combinava geral com categoria (`max(geral, (geral+categoria)/2)`) — uma
  "interpretação comum" que não confere com fonte nenhuma. O Hort e regra de
  rateio entre EMPATADOS: cada um recebe 50% do prêmio da própria posição no
  desempate mais 50% do bolo dividido por igual. Como a classificação já chega
  ordenada pelo desempate, a ordem dentro do grupo empatado E a ordem que o Hort
  pede. A soma fecha com o bolo — há teste para isso.
- **migração honesta**: torneio em `prize_policy = 'hort'` virou `best_only` com
  `prize_tie_split = 'hort'`. E a leitura mais fiel de quem escolheu "Sistema
  Hort" — e agora ele de fato o e.
- **excluir desistentes** e opcional e vem DESLIGADO: ligar por padrão mudaria a
  premiação de todo torneio já existente.

Fora do entregue (de propósito):

- **alocação automática de prêmio por TABULEIRO em equipes.** Ela depende de uma
  classificação por tabuleiro que o programa não calcula; prêmio de tabuleiro
  segue manual, como o `special`. Nenhum critério de aceite do item depende
  disso.

Problema:

- o alocador só casa prêmio de categoria com a categoria primaria única do
  jogador (`prizes.py:128` x `categories.py:101`): prêmio "Feminino" nunca e
  alocado automaticamente e um Sub-12/Sub-1400 concorre a um só;
- o Sistema Hort implementado e uma "interpretação comum" não auditavel
  contra o Swiss-Manager (`prizes.py:90-98`);
- desistentes/W.O. não são excluídos da alocação; prêmios por equipe e
  tabuleiro são apenas manuais; a spec E4 prévia `currency` e `cumulative`
  por prêmio e a tabela não os tem.

Escopo:

- alocar também por `age_category`, `rating_category` e `prize_tags`;
- política por prêmio (acumula ou não) e moeda;
- opção de excluir desistentes; alocação automática por equipes;
- documentar a formula Hort adotada e validar contra caso conhecido do
  Swiss-Manager.

Critérios de aceite:

- [x] prêmio Feminino e alocado automaticamente;
- [x] jogador multi-categoria segue a política configurada;
- [x] fixture de premiação conhecida (edital real) confere — open com geral
  1o/2o/3o, melhor Feminino e melhor Sub-14 somando ao geral, dois empatados no
  topo e rateio Hort: a soma fecha com a bolsa anunciada.

#### ORG-03 - Agenda e controle de tempo estruturados

Status: FEITO (2026-08-04). Schema v55.

Como ficou:

- **o ritmo passou a entender a grafia do edital**: `90'+30"`, `90+30` e a forma
  compacta `40/90+30` viram a mesma gramática interna, no MESMO interpretador que
  o registro 222 do TRF25 e a classificação standard/rapid/blitz já usavam
  (`services/time_control.py`, da FED-07). Detalhe que muda número: depois de
  `40/90`, um `+30` SEM marca e o 2o período em MINUTOS; só `+30"` e incremento.
  Lido como incremento, o mesmo texto daria 210 minutos em vez de 120.
- **a agenda ganhou local, ritmo e dia de descanso por rodada.** Dia de descanso
  e LINHA da agenda: sem ele, a data seguinte parece rodada atrasada.
- **reduzir rodadas com agenda preenchida pede confirmação** e registra evento de
  auditoria (`schedule_rounds_reduced`) com as datas perdidas. Antes o
  `_validated_schedule` fazia `continue` e apagava data já publicada em silêncio.
- **tolerância de atraso configurável**, visível no painel do árbitro e impressa
  na súmula de mesa. Quem declara ausência e o árbitro de sala, e o número vivia
  só no edital. O padrão e `0` — perde a hora marcada, como a FIDE desde 2018.

Armadilha anotada:

- **local e ritmo por rodada foram para uma SEGUNDA LINHA da agenda**, e não para
  mais duas colunas. Seis colunas não cabem na janela de 800px que o
  `test_ui_layout` cobre — e o que estourava nem era a agenda: era o editor de
  colunas ao lado, empurrado pela largura que a agenda impunha a aba. Raspar
  pixel das colunas não resolveu (12px viraram 43px quando os campos ficaram
  menores que o conteúdo); o conserto foi mudar a forma.

Problema:

- `round_schedule` só tem data e hora; faltam local, ritmo por rodada, dia de
  descanso e tolerância de atraso (default time);
- `_validated_schedule` descarta silenciosamente rodadas acima do total
  (`tournament_service.py:626-627`) — reduzir rodadas apaga datas publicadas;
- `time_control` e texto livre: não classifica o evento em
  standard/rapid/blitz (necessário para lista e K de rating — FED-07), não
  alimenta o `222` do TRF25 em grafias comuns (`90'+30"`) e não valida contra
  os mínimos de norma.

Escopo:

- controle de tempo estruturado (fases, incremento) com apresentação livre;
- agenda com ritmo/local por rodada e dias de descanso;
- aviso (não descarte) ao reduzir rodadas com agenda preenchida;
- tolerância de atraso configurável exibida no painel da rodada.

Critérios de aceite:

- [x] `90'+30"` classifica como standard e gera `222` válido;
- [x] reduzir rodadas exige confirmação quando há agenda;
- [x] tolerância aparece no painel e na súmula.

#### ORG-04 - Configuração honesta (flags mortas e bloqueios pos-R1)

Status: FEITO (2026-08-04). Sem mudança de schema.

Como ficou:

- **seis flags inertes saíram da tela e do registro**, com decisão por flag:
  `accelerated_system` (a aceleração de verdade e `acceleration_method`; a flag
  fazia o árbitro acreditar que tinha acelerado o torneio),
  `allow_public_registration` e `allow_player_result_edit` (não existe inscrição
  publica nem edição direta — o envio por QR sempre passou pela fila de
  aprovação), `hide_color_names`, `show_opponents_in_standings` e
  `calculate_performance` (a performance sempre foi calculada; a flag só
  aparecia como linha no relatório, dizendo "Sim" sem consequência).
- **as COLUNAS ficam no banco.** Derrubar coluna no SQLite custa reescrever a
  tabela, e o que fazia mal era a opção na TELA, não o campo parado.
- **rede contra a próxima flag morta**: um teste varre `src/` e reprova qualquer
  flag do registro que não seja lida fora do esquema, da migração e da
  persistência. E o que faltava para as seis nunca terem sido notadas.
- **mudança estrutural depois da rodada 1 exige motivo e vira auditoria**
  (`tournament_structural_change`): ordem inicial, aceleração e sequencia de
  desempates (individual e por equipes). Antes dava para trocar qualquer uma no
  meio do torneio sem aviso e sem rastro — e a classificação publicada mudava
  sozinha entre uma rodada e outra. Salvar a tela sem mexer nesses campos
  continua sendo rotina: o que exige motivo e a MUDANÇA, não o salvamento.
- **`archived` passou a arquivar**: `list_tournaments()` exclui arquivados por
  padrão e `include_archived=True` os traz de volta.

Fora do entregue (de propósito):

- **`tournaments.system`** (o legado dessincronizado de `pairing_method`) não foi
  removido: ele aparece em relatório, no site público e no TRF, e trocar a fonte
  desse texto e mudança de conteúdo publicado — item próprio, não rabo de um
  item de limpeza.

Problema:

- flags exibidas na UI sem nenhum consumidor: `accelerated_system` (o árbitro
  marca e acredita ter acelerado o torneio), `allow_public_registration`,
  `allow_player_result_edit`, `hide_color_names`,
  `show_opponents_in_standings`; `calculate_performance` e só rotulo;
  `archived` não filtra a lista de torneios;
- é possível trocar `initial_order`, aceleração e sequencia de desempates no
  meio do torneio sem aviso nem auditoria;
- `tournaments.system` (default `'Suico'`) e legado dessincronizado de
  `pairing_method`.

Escopo:

- remover ou implementar cada flag morta (decisão por flag, com changelog);
- mudanças estruturais após a rodada 1 exigem confirmação com motivo e geram
  evento de auditoria;
- `archived` passa a ocultar da lista padrão.

Critérios de aceite:

- [x] nenhuma opção visível na UI e inerte — com teste que varre `src/` e
  reprova flag do registro sem consumidor;
- [x] trocar desempates com torneio em andamento gera auditoria;
- [x] torneio arquivado some da lista padrão e reaparece com filtro.

## 6. Fora de Escopo

Não iniciar sem requisito externo concreto:

- aceleração de Baku enquanto a formula aplicável não estiver publicada;
- submissão automática para federação sem API pública;
- decisão automática de WO ou queda de seta;
- plugin de hardware sem equipamento alvo;
- PGN com lances sem captura de lances;
- app Android/iOS nativo;
- importação de formulários em PDF/imagem digitalizada (REG-02 trata apenas
  formatos tabulares; OCR não será implementado).

## 7. Roadmap Priorizado

### Sprint 1 - Papel e contingência

Objetivo: permitir operar o torneio mesmo com indisponibilidade de rede ou
celulares.

Entregas:

1. [x] `DOC-01` Súmula de mesa PDF.
2. [x] `DOC-03` Lista de chamada imprimível.
3. [x] Teste de desempenho com 801 jogadores.

### Sprint 2 - Publicação de rodada

Objetivo: reduzir trabalho manual para afixar emparceiramentos.

Entregas:

1. [x] `DOC-02` Folha de mural com QR.
2. [x] `DOC-04` Cartões de mesa.
3. [x] Integração com exportar e imprimir em `Rodadas`.

### Sprint 3 - Conferência esportiva

Objetivo: oferecer a visão padrão para conferência de resultados.

Entregas:

1. [x] `CLS-01` Tabela cruzada individual.
2. [x] Exportações CSV, XLSX, PDF e HTML.
3. [x] Fixture round-robin conhecida.

### Sprint 4 - Painel de alta velocidade

Objetivo: resolver exceções sem navegar entre telas.

Entregas:

1. [x] `PNL-01` Filtros e busca na Central de pendências.
2. [x] `PNL-02` Lançamento inline pelo painel.
3. [x] `PNL-04` Preferências operacionais persistidas.

### Sprint 5 - Equipes e refinamentos

Objetivo: completar operação presencial avançada.

Entregas:

1. [x] `CLS-02` Tabela cruzada por equipes.
2. [x] `PNL-03` Relógio da rodada.
3. [x] `FED-01` Relatório de taxas.
4. [x] `FED-02` Pré-visualização de atualização oficial.

### Sprint 6 - Inscrições e importação flexível

Objetivo: reduzir o trabalho manual de receber inscrições em formatos diversos e
padronizar a coleta na origem.

Entregas:

1. [x] `REG-01` Gerador de formulário de inscrição padronizado (Google Forms).
2. [x] `REG-02` Assistente de importação com mapeamento de colunas.
3. [x] Perfis de mapeamento reutilizáveis e testes do serviço puro.

### Sprint 7 - Classificação correta (bloqueantes)

Objetivo: eliminar os casos em que a classificação publicada pode contradizer
a decisão arbitral ou mudar sem aviso.

Entregas:

1. [x] `TBK-01` Ajustes de pontos aplicados na classificação.
2. [x] `TBK-02` Fallback do motor de desempates visível.
3. [x] `ARB-01` Correção com motivo, desbloqueio pontual e alerta de cascata.
4. [x] Correções pontuais de `PAR-04` com risco imediato: troca de cores via
   serviço com auditoria e `TEAM_PAIRING_METHODS` duplicado (mais o `pending`
   acumulado e o `KeyError` do sumario de equipes).

**Sprint 7 CONCLUÍDA (2026-07-30).**

### Sprint 8 - Conformidade de desempates

Objetivo: alinhar o motor próprio (ou rebaixa-lo formalmente) e dar ao árbitro
controle real sobre os critérios.

Entregas:

1. [x] `TBK-03` Jogos não disputados conforme FIDE no motor próprio
   (pela segunda saída: motor próprio rebaixado a legado, não homologavel).
2. [x] `TBK-04` Parâmetros de critérios editáveis e registro 212 fiel.
3. [x] `TBK-05` Desempates de equipes completos.

**Sprint 8 CONCLUÍDA (2026-07-31).**

### Sprint 9 - Fluxo arbitral em salão

Objetivo: cobrir as situações reais de arbitragem que hoje exigem contorno.

Entregas:

1. [x] `ARB-02` Resultados arbitrais completos no painel (W.O. inline,
   adiada, W/D/L).
2. [x] `ARB-04` Política de byes solicitados.
3. [x] `ARB-05` Retirada e reentrada com histórico por rodada.
4. [x] `ARB-03` Registro disciplinar de incidentes.

**Sprint 9 CONCLUÍDA (2026-07-31).**

### Sprint 10 - Motores de pareamento

Objetivo: tornar RR/KO/Scheveningen confiáveis e fechar as lacunas do caminho
Gacrux.

Entregas:

1. [x] `PAR-02` Aceleração e entrada tardia no caminho Gacrux.
2. [x] `PAR-01` Round-robin com tabela persistida e returno.
3. [x] `PAR-03` Knockout e Scheveningen maduros.
4. [x] `PAR-04` Demais dividas técnicas do núcleo.

**Sprint 10 CONCLUÍDA (2026-08-03).**

### Sprint 11 - Submissão federativa (CONCLUÍDA em 2026-08-04)

Objetivo: arquivo enviavel sem retrabalho e normas confiáveis.

Entregas:

1. [x] `FED-05` Lista FIDE: data de nascimento e robustez do download.
2. [x] `FED-03` TRF16 de campo completo.
3. [x] `FED-04` Round-trip TRF fiel.
4. [x] `FED-06` Normas FIDE corretas e certificados IT.
5. [x] `FED-07` Rating: K correto, piso e ritmo (arquivo de submissão CBX
   aguarda o regulamento).

### Sprint 12 - Organização do torneio (CONCLUÍDA em 2026-08-04)

Objetivo: edital real configurável sem texto livre nem contorno manual.

Entregas:

1. [x] `ORG-01` Categorias configuráveis por torneio.
2. [x] `ORG-02` Premiação conforme edital.
3. [x] `ORG-03` Agenda e controle de tempo estruturados.
4. [x] `ORG-04` Configuração honesta (flags mortas e bloqueios pos-R1).

## 8. Definição de Pronto

Uma entrega só está pronta quando:

- usa serviços de aplicação, sem escrita crítica direta pela UI;
- registra auditoria quando altera estado do torneio;
- gera backup antes de operação destrutiva ou publicação crítica;
- funciona offline no fluxo principal;
- possui testes automatizados;
- não quebra torneios individuais existentes;
- considera torneios por equipes quando o requisito se aplicar;
- exibe erro claro para o árbitro;
- passa `pytest`, `ruff`, compilação e `git diff --check`;
- possui benchmark quando impactar operação com 100+ jogadores;
- atualiza README ou manual quando alterar o fluxo do operador.

## 9. Matriz de Testes Mínima

| Cenário | Quantidade | Objetivo |
|---|---:|---|
| Individual pequeno | 8 jogadores / 3 rodadas | regressão funcional |
| Individual médio | 51 jogadores / 6 rodadas | bye e volume ímpar |
| Individual grande | 121 jogadores / 7 rodadas | desempenho e impressão |
| Individual alto volume | 801 jogadores / 10 rodadas | limite operacional |
| Equipes | 8 equipes / 4 tabuleiros | lineup, reservas e GP/MP |
| QR | 20 submissões simultâneas simuladas | fila e aprovação |
| Pendências mistas | QR + sync + relógio | filtros e bloqueio |

## 10. Ordem Recomendada para Início

**Atualizado em 2026-08-04: as Sprints 1 a 12 estão TODAS concluídas.** Os EPICs
A a J desta spec foram entregues; a auditoria arbitral de 2026-07-29, que gerou
os EPICs F a J, está integralmente coberta.

Histórico da ordem executada:

1. **Sprints 1-6** (papel, prévia, painel, desempates explicáveis, QR,
   inscrições) — entregues até 2026-06-03.
2. **Sprint 7 (bloqueantes)** — `TBK-01`, `TBK-02`, `ARB-01`, `PAR-04` parcial —
   2026-07-30.
3. **Sprint 8 (desempates conformes)** — `TBK-03`, `TBK-04`, `TBK-05` —
   2026-07-30/31.
4. **Sprint 9 (fluxo de salão)** — `ARB-02`, `ARB-04`, `ARB-05`, `ARB-03` —
   2026-07-31.
5. **Sprint 10 (motores secundários)** — `PAR-02`, `PAR-01`, `PAR-03`,
   `PAR-04` — 2026-07-31/08-01.
6. **Sprint 11 (submissão federativa)** — `FED-05`, `FED-03`, `FED-04`,
   `FED-06`, `FED-07` — 2026-08-03/04.
7. **Sprint 12 (organização)** — `ORG-01`, `ORG-02`, `ORG-03`, `ORG-04` —
   2026-08-04.

### O que vem depois

Não há item de conformidade pendente por decisão própria. As duas fontes de
trabalho novo são:

1. **Teste piloto presencial.** Continua sendo a recomendação mais forte: o
   ensaio automatizado (`docs/PILOTO_OPERACIONAL_BASELINE.md`) cobre volume,
   rede caída e concorrência, mas não cobre o salão. Um torneio real produz o
   próximo backlog melhor do que qualquer auditoria de código.
2. **Documento externo que destrave item bloqueado.** Três itens estão prontos
   para receber a fonte: o regulamento de rating da CBX (o perfil já é editável
   e sai marcado como NÃO conferido), o formato do arquivo de submissão da CBX e
   a formula de aceleração de Baku.

Ficaram registrados como itens próprios, com o motivo, em "Fora de Escopo" e no
backlog do `ROADMAP_ARBITRAGEM_XADREZ.md`: alocação automática de prêmio por
tabuleiro em equipes e a remoção do legado `tournaments.system`.
