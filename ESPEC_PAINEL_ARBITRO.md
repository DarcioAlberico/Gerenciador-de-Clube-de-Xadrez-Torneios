# Spec e Roadmap - Painel do Arbitro

> Documento executivo para evoluir o fluxo operacional de arbitragem do
> Albericus em torneios presenciais com mais de 100 jogadores.
>
> Revisao: 2026-07-29 (auditoria arbitral completa dos modulos de torneio;
> novos EPICs F a J na secao 5 e Sprints 7 a 12 na secao 7).

## 1. Objetivo

O Painel do Arbitro deve funcionar como centro de comando do torneio. A tela
precisa mostrar excecoes, indicar a proxima acao correta e reduzir navegacao
durante chamada, lancamento de resultados, fechamento de rodada e publicacao.

Meta operacional:

- operar torneios individuais com 100 a 200 jogadores sem degradacao perceptivel;
- localizar mesas pendentes em ate 2 cliques;
- lancar resultados sequenciais apenas com teclado;
- impedir fechamento quando houver pendencia bloqueante;
- manter o desktop e o SQLite local como autoridade do torneio.

## 2. Principios

1. O painel orienta a decisao; nao decide pelo arbitro.
2. QR, relogio, sincronizacao e portal live sao auxiliares.
3. Acao critica continua passando pelos servicos existentes, com auditoria e
   backup quando aplicavel.
4. O fluxo principal precisa funcionar offline.
5. Documentos impressos continuam necessarios para contingencia presencial.
6. Ganho operacional deve ser medido em torneios simulados com pelo menos 120
   jogadores.

## 3. Baseline Validado

### 3.1 Nucleo existente

Ja existem:

- geracao e pre-visualizacao de rodadas;
- fechamento auditavel;
- snapshots de emparceiramento e classificacao;
- chamada inicial com presentes e ausentes;
- lancamento rapido por botoes e atalhos `1`, `0`, `-`, `Delete` e `Enter`;
- selecao automatica da primeira mesa sem resultado;
- fila QR com aprovacao ou rejeicao;
- pendencias de sincronizacao e alertas de relogio;
- correcoes auditadas;
- publicacao HTML e portal live;
- validacao e exportacao TRF16;
- TRF25 mantido como formato em evolucao;
- motor Gacrux (Otto Milvang, homologado FIDE) como padrao de emparceiramento
  (`pairing_system = gacrux_swiss`) e de desempates (`tiebreak_engine = gacrux`,
  com adversario virtual FIDE e regras por data de vigencia), com fallback para
  o motor proprio `albericus-swiss-1`;
- byes solicitados F/H/Z, W.O. (`1F-0F`, `0F-1F`, `0F-0F`), pareamentos
  proibidos manuais (registro 260), aceleracao Haley/custom, ajustes de pontos
  (`point_adjustments`, registro 299) e diagnosticos de pareamento com prova de
  otimalidade em campos pequenos.

### 3.2 Benchmark atual

Benchmarks locais:

| Operacao | Resultado |
|---|---:|
| Inserir 801 jogadores | 3,8451 s |
| Pre-visualizar primeira rodada com 801 jogadores | 0,0309 s |
| Gerar primeira rodada com 801 jogadores | 0,0910 s |
| Carregar dashboard arbitral com 801 jogadores | 0,0216 s |
| Emparceiramentos gerados para 801 jogadores | 401 |
| Mesas pendentes para 801 jogadores | 400 + 1 bye |
| Mesas pendentes exibidas inline | primeiras 20 |
| Gerar 60 sumulas PDF para 121 jogadores | 0,1075 s |
| Gerar 400 sumulas PDF para 801 jogadores | 0,4028 s |
| Gerar lista de chamada PDF para 801 jogadores | 0,1055 s / 22 paginas |
| Gerar mural PDF com QR para 60 mesas | 2,4005 s / 4 paginas |
| Gerar mural PDF com QR para 400 mesas + 1 bye | 15,4840 s / 27 paginas |
| Gerar 200 cartoes de mesa PDF sem QR | 0,0811 s / 50 paginas |
| Gerar 60 cartoes de mesa PDF com QR | 2,6519 s / 15 paginas |
| Calcular tabela cruzada com 801 jogadores / 1 rodada | 0,0473 s |
| Exportar tabela cruzada HTML com 801 jogadores / 1 rodada | 0,0661 s |
| Filtrar 1.000 pendencias por decisao e mesa | 1,4220 ms |
| Lancar resultado inline com recarga do painel / 801 jogadores | 49,7582 ms |
| Carregar dashboard com limite inline de 50 mesas / 801 jogadores | 22,2493 ms medio / 25,7239 ms maximo |
| Carregar dashboard com relogio e limite inline de 50 mesas / 801 jogadores | 24,7673 ms medio / 29,9365 ms maximo |
| Calcular tabela cruzada por equipes / 801 jogadores, 200 equipes, 400 tabuleiros | 125,4967 ms medio / 155,0487 ms maximo |
| Calcular resumo de taxas de rating / 801 jogadores | 11,5755 ms medio / 16,5495 ms maximo |
| Exportar taxas de rating XLSX / 801 jogadores | 409,6342 ms |
| Pre-visualizar atualizacao oficial / 801 jogadores | 877,1279 ms medio / 934,8669 ms maximo |
| Confirmar atualizacao oficial / 700 alteracoes | 4.249,0223 ms |
| Piloto automatizado: carregar painel / 801 jogadores | 23,0215 ms |
| Piloto automatizado: lancar resultado e recarregar painel / 801 jogadores | 49,4234 ms medio |
| Piloto automatizado: mural PDF com QR em lote / 400 mesas | 3,7016 s / 27 paginas |
| Piloto automatizado: criar backup final / 801 jogadores | 19,6087 ms / 4.890.624 bytes |
| Piloto automatizado: restaurar em segunda instalacao / 801 jogadores | 699,9135 ms / 1 rodada e 401 mesas |
| Piloto automatizado: continuidade local com rede bloqueada | 860,8958 ms / fluxo critico validado |
| Piloto automatizado: rajada QR concorrente | 2.846,3054 ms / 20 envios recebidos e aprovados |
| Piloto automatizado: inscricao de ultima hora / 801 + 1 jogadores | 117,0289 ms / historico e previa validados |
| Piloto automatizado: importar base oficial FIDE local | 146,0958 ms / 700 registros |
| Piloto automatizado: comparar ratings oficiais antes da rodada 1 | 882,3479 ms / sem persistir |
| Piloto automatizado: confirmar correcoes oficiais selecionadas | 4.325,6951 ms / 700 alteracoes |
| Piloto automatizado: localizar e lancar mesa 400 pelo painel | 73,5168 ms / fora do recorte inline |

O gargalo prioritario nao e processamento. E reduzir cliques, troca de tela e
conferencia manual.

## 4. Estado da Interface

### 4.1 Entregue nesta iteracao

| ID | Entrega | Status |
|---|---|---|
| UX-01 | Cards clicaveis para rodadas, pendentes, byes, ausentes e correcoes | Concluido |
| UX-02 | Botao de proximo passo recomendado | Concluido |
| UX-03 | Alertas operacionais com cor por severidade | Concluido |
| UX-04 | Acoes agrupadas em Rodada, Configuracao arbitral e Publicacao | Concluido |
| UX-05 | Auto-refresh opcional do painel com intervalo configuravel | Concluido |
| UX-06 | Lista inline configuravel entre 10 e 50 mesas aguardando resultado | Concluido |
| UX-07 | Central de pendencias com primeira linha pre-selecionada | Concluido |
| UX-08 | Central de pendencias com cor por severidade e numero legivel da rodada | Concluido |
| UX-09 | Chamada inicial com busca e 14 linhas visiveis | Concluido |
| DOC-01 | Sumula de mesa PDF individual e por equipes | Concluido |
| DOC-02 | Folha de mural PDF com QR por mesa aberta | Concluido |
| DOC-03 | Lista de chamada PDF por ranking inicial | Concluido |
| DOC-04 | Cartoes de mesa PDF por intervalo com QR opcional | Concluido |
| CLS-01 | Tabela cruzada individual com quatro formatos | Concluido |
| CLS-02 | Tabela cruzada por equipes com detalhe de tabuleiros | Concluido |
| PNL-01 | Filtros, busca e contador na Central de pendencias | Concluido |
| PNL-02 | Lancamento inline de resultados no Painel do arbitro | Concluido |
| PNL-03 | Relogio local da rodada no Painel do arbitro | Concluido |
| PNL-04 | Preferencias operacionais persistidas no Painel do arbitro | Concluido |
| FED-01 | Relatorio de taxas de rating por base oficial | Concluido |
| FED-02 | Pre-visualizacao e confirmacao da atualizacao oficial | Concluido |

Arquivos centrais:

- `src/ui/screens/pairings.py`
- `src/services/pairing_service.py`
- `src/ui/app.py`

### 4.2 Fluxo recomendado atual

Antes da primeira rodada:

1. Abrir `Rodadas`.
2. Usar a busca da chamada inicial.
3. Marcar somente ausentes.
4. Pre-visualizar e gerar a rodada.

Durante a rodada:

1. Abrir `Painel do arbitro`.
2. Conferir o proximo passo recomendado.
3. Ajustar auto-refresh, intervalo e quantidade de mesas inline conforme a operacao.
4. Lancar resultados pela lista inline com botoes ou teclado.
5. Resolver QR, sync e relogio na `Central de pendencias`.
6. Fechar somente quando o painel indicar que a rodada esta pronta.

### 4.3 Aprofundamento 2026-06-02 (UX + docs)

Iteracao net-new sobre o painel ja completo, partindo do gancho da secao 10
(novo requisito operacional). Quatro entregas:

| ID | Entrega | Status |
|---|---|---|
| UX-10 | Alertas operacionais **clicaveis**: cada alerta pula ao contexto exato (pendencias bloqueantes, fechar rodada, aprovar QR, ausentes, correcoes, previa) | Concluido |
| UX-11 | **Barra de progresso da rodada** no topo do painel (`X/N mesas resolvidas (Y%)`), atualizada com o auto-refresh | Concluido |
| DOC-05 | **Pacote da rodada** em um clique: mural + sumulas + cartoes numa pasta (`ExportService.export_round_package`), isolando erros | Concluido |
| DOC-06 | **Ata final do torneio** (`ExportService.export_tournament_minutes`): documento unico de encerramento (dados, classificacao final, premiacao, taxas, arbitros e assinaturas) | Concluido |

Implementacao:

- `individual_round_dashboard_metrics`/`team_round_dashboard_metrics` passam a
  expor `total_results`/`resolved_results`; `arbitration_dashboard` calcula
  `round_progress_percent` e devolve `alerts_detailed` (texto + severidade +
  acao), mantendo `alerts` (strings) em sincronia para retrocompatibilidade;
- o painel (`pairings.py`) renderiza alertas como botoes-link que disparam a
  acao certa e desenha a barra de progresso; novos botoes `Pacote da rodada
  (PDF)` e `Ata final (PDF)` no grupo Publicacao;
- `export_round_package` reaproveita mural/sumulas/cartoes existentes;
  `export_tournament_minutes` compoe as secoes ja existentes (classificacao,
  premiacao, taxas) com cabecalho e arbitros;
- `Ata final` tambem disponivel no hub de Relatorios (CSV/XLSX/PDF);
- 6 testes novos (metricas puras de progresso, alertas estruturados, progresso
  apos lancamento, pacote da rodada e ata); gate completo verde.

### 4.4 Ideias net-new 2026-06-02 (segunda leva)

| ID | Entrega | Status |
|---|---|---|
| DOC-07 | **Ata por categoria**: secao "Vencedores por categoria" (top 3 de cada categoria) na ata final | Concluido |
| DOC-08 | **Boletim/press-release da rodada** (`ExportService.export_round_bulletin`): cabecalho + resultados + classificacao (top 10) + destaques (lider, decisivas/empates, maior zebra) | Concluido |
| UX-12 | **Checklist de fechamento** (`PairingService.closing_checklist`): itens com OK/X e acao por item; dialogo no painel com `Fechar rodada` habilitado so quando tudo esta OK | Concluido |
| DOC-09 | **Pacote da rodada para equipes**: `export_round_package` ciente de equipes (mural = confrontos, sumulas por tabuleiro, cartoes pelo total de tabuleiros de `team_boards`) | Concluido |

Implementacao:

- `_category_winners_section` agrupa `pairing_service.standings` por `category`
  (individual); entra na ata e protege contra torneios sem categorias;
- `_round_bulletin_sections` reaproveita `_pairings_section` e o layout da
  classificacao (top 10); `_bulletin_highlights_section` calcula os destaques a
  partir dos resultados/ratings da rodada;
- `closing_checklist` deriva do `arbitration_dashboard` e reaproveita o mapa de
  acoes dos alertas clicaveis; o painel ganhou os botoes `Checklist de
  fechamento` (grupo Rodada) e `Boletim da rodada (PDF)` (grupo Publicacao);
- `export_round_package` conta os tabuleiros de equipes por `list_team_boards`
  (os tabuleiros ficam fora da tabela `pairings`), gerando cartoes corretos;
- 6 testes novos; gate completo verde (429 passed). Sem mudanca de schema.

### 4.5 Ideias net-new 2026-06-02 (terceira leva)

| ID | Entrega | Status |
|---|---|---|
| DOC-10 | **Poster/diploma do podio** (`ExportService.export_podium`): A4 com top 3 (jogadores ou equipes) + campeoes por categoria | Concluido |
| DOC-11 | **Boletim da rodada pelo hub de Relatorios**, escolhendo a rodada (reusa o seletor de rodada existente) | Concluido |
| UX-13 | **Checklist de fechamento especifico para equipes**: item de escalacoes/ordem de tabuleiro via `validate_roster_policy` | Concluido |

Implementacao:

- `_podium_data` reune top 3 (`standings`/`team_standings`) + campeoes por
  categoria; `_write_podium_poster_pdf` desenha o poster A4 com `reportlab`;
  opcao `Podio (poster)` no hub (PDF) e botao `Podio (PDF)` no painel;
- o hub ganhou `Boletim da rodada` ligado ao seletor de rodada (alem do botao do
  painel, que usa a rodada atual);
- `closing_checklist` detecta equipes e acrescenta o item de escalacoes
  (`TeamService.validate_roster_policy`, import lazy para evitar ciclo); o
  dialogo do painel mapeia a acao `lineups` para a tela de Equipes;
- 3 testes novos (dados do podio, geracao do PDF, checklist de equipes com
  `lineups`); gate completo verde (432 passed). Sem mudanca de schema.

## 5. Requisitos Pendentes

### EPIC A - Documentos operacionais impressos

Prioridade: muito alta.

#### DOC-01 - Sumula de mesa PDF

Status: concluido em 2026-05-31.

Problema:

- o sistema nao gerava a folha fisica de anotacao por tabuleiro.

Escopo:

- criar `ExportService.export_scoresheets(round_id, file_path)`;
- gerar uma sumula por mesa individual;
- nao gerar sumula para bye;
- incluir torneio, rodada, mesa, nomes, ratings, IDs oficiais, clubes, campo de
  resultado, grade de lances e assinaturas;
- em torneio por equipes, gerar uma sumula por tabuleiro do match.

Criterios de aceite:

- [x] rodada com 121 jogadores gera PDF em menos de 5 segundos;
- [x] PDF abre corretamente;
- [x] bye nao gera pagina inutil;
- [x] torneio por equipes gera uma pagina por tabuleiro;
- [x] teste automatizado valida quantidade de paginas e textos principais.

Implementacao:

- `ExportService.export_scoresheets(round_id, file_path)`;
- botoes `Exportar sumulas` e `Imprimir sumulas` na tela `Rodadas`;
- uma pagina A4 por mesa, com 60 lances, dados oficiais, resultado e assinaturas.

#### DOC-02 - Folha de emparceiramento de mural com QR

Status: concluido em 2026-05-31.

Problema:

- a exportacao atual e generica e o QR aparece apenas no HTML.

Escopo:

- criar PDF A4 legivel para afixacao;
- incluir rodada, mesa, brancas, pretas, rating e QR;
- incluir QR somente para rodada aberta;
- oferecer exportar e imprimir na tela `Rodadas`.

Criterios de aceite:

- [x] PDF de 60 mesas fica legivel em impressao A4;
- [x] QR abre a mesa correta;
- [x] rodada fechada nao gera QR ativo;
- [x] testes validam presenca e ausencia condicional do QR;
- [x] benchmark valida 60 mesas em 2,4005 s e 4 paginas;
- [x] baseline adicional valida 400 mesas + 1 bye em 15,4840 s e 27 paginas.

Implementacao:

- PDF A4 vertical especializado para torneios individuais;
- ate 15 mesas por pagina, com mesa, nomes, ratings e QR;
- QR emitido somente para mesa sem bye em rodada aberta;
- emissao de tokens QR dos documentos feita em lote transacional, com
  auditoria agregada por rodada;
- `Exportar rodada` preserva CSV/XLSX e gera o mural quando escolhido PDF;
- `Imprimir rodada` gera diretamente o mural PDF;
- torneios por equipes mantem o relatorio existente.

#### DOC-03 - Lista de chamada imprimivel

Status: concluido em 2026-05-31.

Problema:

- a chamada existe na tela, mas precisa de contingencia em papel.

Escopo:

- criar PDF ordenado pelo ranking inicial;
- incluir numero inicial, nome, rating, clube, categoria e coluna de assinatura;
- manter exportacao CSV/XLSX atual.

Criterios de aceite:

- [x] ordenacao igual a utilizada no TRF do torneio;
- [x] PDF suporta pelo menos 200 jogadores;
- [x] teste valida ordem e cabecalhos;
- [x] benchmark valida 801 jogadores em 0,1055 s e 22 paginas.

Implementacao:

- PDF A4 vertical especializado com cabecalho repetido, pagina atual, total de
  inscritos e coluna de assinatura;
- ranking inicial compartilhado com a tela de chamada: rating TRF, nome de
  emparceiramento e ID como desempate;
- marcar ausencia nao renumera jogadores;
- CSV e XLSX continuam disponiveis pela exportacao existente.

#### DOC-04 - Cartoes de mesa

Status: concluido em 2026-05-31.

Problema:

- numeracao e sinalizacao de tabuleiros ainda dependem de material externo.

Escopo:

- gerar cartoes imprimiveis com numero da mesa;
- opcionalmente incluir QR da mesa e identificacao da rodada.

Criterios de aceite:

- [x] gerar cartoes para intervalo configuravel;
- [x] layout legivel a distancia;
- [x] identificacao opcional da rodada;
- [x] QR opcional somente para mesa valida de rodada individual aberta;
- [x] benchmark valida 200 cartoes sem QR em 0,0811 s;
- [x] benchmark valida 60 cartoes com QR em 2,6519 s.

Implementacao:

- `ExportService.export_table_cards(file_path, start_board, end_board, round_id, include_qr)`;
- quatro cartoes por pagina A4, com numero de mesa em destaque;
- intervalo limitado a 500 cartoes por arquivo;
- botao `Exportar cartoes` na tela `Rodadas`;
- dialogo de intervalo e confirmacao opcional de QR.

### EPIC B - Classificacao e conferencia

Prioridade: muito alta.

#### CLS-01 - Tabela cruzada individual

Status: concluido em 2026-05-31.

Problema:

- falta uma visao matriz jogador x rodada para conferencia rapida.

Escopo:

- criar `PairingService.crosstable(tournament_id)`;
- uma linha por jogador;
- uma coluna por rodada com adversario, cor e resultado;
- adicionar pontos e desempates ao final;
- exportar CSV, XLSX, PDF e HTML.

Criterios de aceite:

- [x] fixture round-robin de 6 jogadores confere integralmente;
- [x] soma dos resultados equivale a classificacao;
- [x] bye, WO e ausencia ficam distintos;
- [x] servico puro possui testes unitarios;
- [x] benchmark valida 801 jogadores em 0,0473 s;
- [x] CSV, XLSX, PDF e HTML exportam corretamente.

Implementacao:

- `PairingService.crosstable(tournament_id)` usa a classificacao como fonte
  unica dos resultados fechados;
- uma linha por jogador e uma coluna por rodada fechada;
- celula compacta com posicao do adversario, cor (`B` ou `P`) e resultado;
- `BYE`, `1F-0F`, `0F-1F`, `0F-0F` e ausencia (`-`) permanecem distintos;
- `ExportService.export_crosstable(tournament_id, file_path)`;
- botao `Exportar tabela cruzada` na tela `Classificacao`;
- relatorio `Tabela cruzada` no centro de exportacoes.

#### CLS-02 - Tabela cruzada por equipes

Status: concluido em 2026-05-31.

Problema:

- a operacao por equipes exige conferencia de match points e game points.

Escopo:

- criar matriz equipe x rodada;
- incluir adversario, resultado do match, MP e GP;
- permitir detalhar tabuleiros.

Criterios de aceite:

- [x] torneio de equipes com reservas preserva historico por tabuleiro;
- [x] total de MP e GP confere com classificacao.

Implementacao:

- `PairingService.team_crosstable(tournament_id)` cria uma linha por equipe e
  uma celula por rodada fechada;
- celula compacta com posicao do adversario, lado (`B` ou `P`), resultado,
  match points (`MP`) e game points (`GP`);
- payload mantem os tabuleiros fechados para conferencia detalhada, inclusive
  quando uma reserva foi escalada;
- exportacao automatica em CSV, XLSX, PDF e HTML pelo fluxo existente;
- tela `Classificacao` oferece `Exportar tabela cruzada` e
  `Detalhar tabuleiros`;
- benchmark com 801 jogadores, 200 equipes e 400 tabuleiros: 125,4967 ms em
  media.

### EPIC C - Painel de excecoes avancado

Prioridade: alta.

#### PNL-01 - Filtros na Central de pendencias

Status: concluido em 2026-05-31.

Problema:

- filas extensas misturam QR, sincronizacao e relogio.

Escopo:

- filtros `Todas`, `Decisao`, `QR`, `Sync` e `Relogio`;
- busca por mesa, titulo ou detalhe;
- contador atualizado conforme filtro.

Criterios de aceite:

- [x] arbitro localiza uma pendencia por mesa em ate 2 interacoes;
- [x] filtros nao alteram o estado da pendencia;
- [x] testes de UI cobrem filtro e busca;
- [x] benchmark valida filtro e busca em 1.000 pendencias em 1,4220 ms.

Implementacao:

- `PairingService.filter_arbitration_issues(issues, issue_filter, query)` puro;
- filtros `Todas`, `Decisao`, `QR`, `Sync` e `Relogio`;
- busca local por mesa, titulo, detalhe e payload;
- contador `Exibindo N de total`;
- primeira pendencia visivel continua pre-selecionada;
- nenhuma consulta adicional ou mutacao ocorre ao filtrar.

#### PNL-02 - Lancamento inline pelo painel

Status: concluido em 2026-05-31.

Problema:

- o painel mostra mesas pendentes, mas o registro ainda exige abrir `Rodadas`.

Escopo:

- selecionar mesa na lista inline;
- registrar `1-0`, `1/2-1/2`, `0-1` ou limpar;
- delegar obrigatoriamente para `PairingService.update_result`;
- preservar confirmacoes e auditoria de rodada fechada.

Criterios de aceite:

- [x] resultado aparece no painel sem troca de tela;
- [x] proxima pendencia e selecionada automaticamente;
- [x] atalhos continuam funcionando na tela `Rodadas`;
- [x] testes cobrem individual e bloqueio em rodada fechada;
- [x] benchmark valida 49,7582 ms por lancamento com recarga em 801 jogadores.

Implementacao:

- payload inline inclui ID persistido da mesa;
- primeira mesa pendente fica pre-selecionada;
- busca numerica localiza exatamente a mesa mesmo fora do recorte inline;
- botoes `1-0`, `1/2`, `0-1` e `Limpar`;
- atalhos `1`, `-`, `0`, `Backspace` e `Delete`;
- toda alteracao delega para `PairingService.update_result`;
- painel recarrega apos salvar e seleciona a proxima pendencia;
- bloqueio de rodada fechada continua centralizado no servico.
- piloto com 801 jogadores localiza e lanca a mesa 400 em 73,5168 ms.

#### PNL-03 - Relogio da rodada

Status: concluido em 2026-05-31.

Problema:

- o painel nao mostra duracao da rodada atual.

Escopo:

- persistir ou derivar horario de abertura;
- mostrar inicio e tempo decorrido;
- atualizar junto com o auto-refresh.

Criterios de aceite:

- [x] duracao e exibida sem depender de internet;
- [x] rodada fechada mostra duracao final.

Implementacao:

- horario de abertura derivado de `rounds.created_at`, ja persistido na geracao;
- `rounds.closed_at` adicionado na migracao `v33`;
- rodadas legadas fechadas recebem `closed_at = created_at` para manter valor
  estavel sem inventar duracao;
- card `Tempo rodada` mostra inicio local, estado e duracao `HH:MM:SS`;
- rodada aberta recalcula duracao junto com o auto-refresh do painel;
- rodada fechada usa `closed_at` e preserva a duracao final;
- benchmark com 801 jogadores e 50 mesas inline: 24,7673 ms em media.

#### PNL-04 - Preferencias operacionais persistidas

Status: concluido em 2026-05-31.

Problema:

- auto-refresh e quantidade de mesas inline voltam ao padrao ao reiniciar.

Escopo:

- persistir auto-refresh;
- permitir intervalo entre 10 e 120 segundos;
- permitir limite inline entre 10 e 50 mesas.

Criterios de aceite:

- [x] preferencias sobrevivem ao reinicio;
- [x] valores invalidos voltam ao padrao seguro.

Implementacao:

- preferencias locais salvas em `app_settings`, sem migracao de schema;
- defaults compativeis: auto-refresh ligado, intervalo de 15 segundos e 20 mesas;
- recargas manuais substituem o agendamento anterior para evitar ticks duplicados;
- benchmark com 801 jogadores e limite de 50 mesas: 22,2493 ms em media.

### EPIC D - Dados oficiais e prestacao de contas

Prioridade: media.

#### FED-01 - Relatorio de taxas de rating

Status: concluido em 2026-05-31.

Problema:

- nao existe resumo financeiro para homologacao e prestacao de contas.

Escopo:

- contar jogadores rated e nao rated;
- permitir taxa configuravel;
- separar FIDE, CBX e LBX quando aplicavel;
- exportar PDF e XLSX.

Criterios de aceite:

- [x] totais conferem com inscritos;
- [x] relatorio identifica claramente a base utilizada.

Implementacao:

- taxas unitarias configuraveis por torneio para FIDE, CBX e LBX;
- calculo separado por base: inscritos identificados, rated, nao rated, taxa
  unitaria e subtotal;
- cada base cobra separadamente os inscritos identificados nela, inclusive
  quando um jogador possui IDs em mais de uma base;
- resumo geral informa inscritos, rated em alguma base e jogadores sem ID
  oficial;
- detalhamento lista IDs e ratings utilizados para conferencia;
- centro de exportacoes oferece `Taxas de rating` em XLSX e PDF;
- benchmark com 801 jogadores: resumo em 11,5755 ms e XLSX em 409,6342 ms.

#### FED-02 - Pre-visualizacao de atualizacao oficial

Status: concluido em 2026-05-31.

Problema:

- a importacao oficial atual atualiza os inscritos sem tela de comparacao.

Escopo:

- mostrar antes/depois de nome, clube, titulo e ratings;
- permitir confirmar atualizacao em lote;
- manter jogadores sem correspondencia separados.

Criterios de aceite:

- [x] nenhuma alteracao e persistida antes da confirmacao;
- [x] importacao de lista continua funcionando offline por arquivo;
- [x] teste cobre confirmacao e cancelamento.

Implementacao:

- o botao `Comparar ratings oficiais` abre a pre-visualizacao sem gravar dados;
- a comparacao exibe antes/depois de nome, clube, titulo, rating principal,
  rating nacional e rating internacional;
- correspondencias sem mudanca e jogadores sem correspondencia ficam
  identificados separadamente;
- divergencias ficam pre-selecionadas para agilizar o fluxo, com contador e
  opcoes para limpar ou restaurar a selecao;
- a confirmacao recalcula o plano com a base oficial atual e aplica em lote
  somente as divergencias selecionadas;
- o fluxo de importacao offline FIDE, CBX e LBX por arquivo permanece
  disponivel;
- benchmark com 801 inscritos, 700 correspondencias alteradas e 101 sem
  correspondencia: pre-visualizacao em 877,1279 ms medios e confirmacao em
  4.249,0223 ms.

### EPIC E - Inscricoes e importacao flexivel

Prioridade: alta.

Contexto: hoje a importacao depende de colunas padronizadas
(`ImportService.import_players`, `import_online_registrations`,
`preview_online_registrations` por arquivo ou URL CSV do Google Sheets/Forms) e
de modelos fixos gerados em XLSX (`ExportService.export_player_import_template`
e `export_online_registration_template`). Na pratica o arbitro recebe planilhas
antigas e formularios fora do padrao, com colunas em qualquer ordem, nomes
diferentes (`Nome completo`, `Atleta`, `Jogador`), datas em formatos variados e
campos faltando. Falta (a) um formulario de coleta ja padronizado para
distribuir e (b) uma tela que importe planilhas nao padronizadas mapeando cada
coluna para o campo correto.

#### REG-01 - Gerador de formulario de inscricao padronizado (Google Forms)

Status: concluido em 2026-06-03.

Problema:

- o sistema gera apenas modelo XLSX/CSV; o arbitro monta o Google Forms na mao,
  com perguntas e ordem divergentes, gerando colunas que nao batem com o
  importador.

Escopo:

- gerar a definicao de um Google Forms padronizado a partir dos campos canonicos
  do Albericus (nome de emparceiramento, nome completo, data de nascimento,
  sexo, federacao, clube/cidade, categoria, IDs oficiais FIDE/CBX/LBX, ratings,
  e-mail e telefone), respeitando obrigatoriedade e tipo de cada campo;
- criar o formulario **ao vivo** na conta do arbitro via API do Google Forms
  (OAuth de app desktop), devolvendo o link de resposta pronto para enviar aos
  jogadores que se inscrevem sozinhos;
- manter um **fallback offline** quando faltarem credencial/bibliotecas/internet:
  gerar um script Apps Script colavel mais a definicao reutilizavel
  (`.json`) e um passo a passo de publicacao;
- oferecer ainda a opcao mais simples (sem OAuth): **link pre-preenchido** a
  partir de um formulario ja existente — o arbitro configura uma vez o link
  pre-preenchido (de onde se extrai a URL base e o `entry.*` do campo do
  torneio) e o sistema monta/compartilha o link com o nome do torneio ja
  preenchido, abrindo no navegador para enviar aos jogadores;
- garantir que o CSV de respostas do formulario gerado seja importavel
  diretamente pelo fluxo `import_online_registrations` existente (colunas ja no
  padrao);
- incluir o link/QR do formulario no material de divulgacao do torneio.

Criterios de aceite:

- [x] clicar no botao cria o formulario na conta do arbitro e devolve o link de
  resposta (quando a credencial OAuth esta configurada);
- [x] o formulario cobre todos os campos padronizados com tipo e obrigatoriedade
  corretos;
- [x] o CSV de respostas do formulario gerado importa sem mapeamento manual;
- [x] ha fallback (script Apps Script) quando faltam credencial/bibliotecas/
  internet, sem quebrar o fluxo;
- [x] alternativa sem OAuth: configurar um formulario existente e
  gerar/compartilhar o link pre-preenchido com o nome do torneio;
- [x] teste valida que os cabecalhos do formulario casam com o importador
  padronizado.

Implementacao:

- criacao **ao vivo** como caminho principal: `GoogleFormsService`
  (`src/services/google_forms_service.py`) cria o formulario na conta do arbitro
  via API do Google Forms (OAuth de app desktop, token cacheado em
  `config/google_forms_token.json`) e devolve o link de resposta para enviar aos
  jogadores; `build_form_requests` (funcao pura) monta o `batchUpdate`
  (descricao + uma pergunta por campo, com tipo data/escolha/texto e
  obrigatoriedade);
- **fallback automatico** para o script Apps Script
  (`ExportService.export_registration_form`) quando faltam bibliotecas Google,
  credencial OAuth ou internet/autorizacao: gera `.gs` (com passo a passo e a
  funcao `criarFormularioInscricao`) e `.json` (definicao reutilizavel);
- as perguntas vem de `REGISTRATION_FORM_QUESTIONS`, com titulos identicos aos
  cabecalhos aceitos por `_online_registration_payload`, garantindo importacao
  sem mapeamento tanto no modo ao vivo quanto no script; `Sexo` vira multipla
  escolha `M`/`F`;
- dependencias Google sao **opcionais e importadas lazy** (o modulo importa sem
  elas); adicionadas ao `requirements.txt` como opcionais;
- link pre-preenchido (sem OAuth): `ExportService.parse_prefill_link`,
  `build_registration_prefill_url`, `registration_form_config`,
  `save_registration_form_config` e `registration_prefill_url`; a config (URL
  base + `entry.*` do torneio) fica em `app_settings`, sem migracao de schema;
- UI: botao `Gerar formulario (Google Forms)` tenta a API e, se
  indisponivel/falhar, oferece gerar o script; `Configurar formulario (link)`
  analisa o link pre-preenchido e escolhe o campo do torneio; `Compartilhar
  inscricao (link)` monta e exibe o link (copiar/abrir) com o torneio
  preenchido; dialogos com link de resposta/edicao no modo ao vivo;
- guia de configuracao (OAuth e link pre-preenchido) em
  `docs/GUIA_GOOGLE_FORMS.md`;
- distribuicao para a comunidade: padrao sem OAuth (link pre-preenchido +
  script, sem teto de usuarios); para "Entrar com o Google" a todos,
  `client_secret_path` aceita credencial **embarcada** em
  `assets/google_client_secret.json` (precedencia: app_settings > config do
  usuario > embarcada), gitignored; checklist de empacotamento e verificacao do
  app (escopo sensivel, sem CASA) em `docs/DISTRIBUICAO_E_VERIFICACAO_GOOGLE.md`;
- 16 testes (payload puro e orquestracao da API mockada, disponibilidade/
  credencial, precedencia da credencial embarcada, compatibilidade dos titulos
  com o importador, e parse/montagem/config do link pre-preenchido).

#### REG-02 - Assistente de importacao com mapeamento de colunas

Status: concluido em 2026-06-03.

Problema:

- planilhas antigas (CSV/XLS/XLSX) e respostas de formularios nao padronizados
  nao importam porque as colunas nao correspondem ao modelo fixo; hoje so resta
  editar a planilha na mao antes de importar.

Escopo:

- criar `ImportService.inspect_source(file_path_or_url)` que le o arquivo
  (CSV/XLS/XLSX e URL CSV publicada) e devolve cabecalhos detectados, as
  primeiras N linhas de amostra e um palpite de mapeamento por heuristica
  (sinonimos por campo: `nome|atleta|jogador`, `nascimento|idade|data nasc`,
  `id fide|fide id`, `rating|elo`, etc.);
- criar tela/dialogo de mapeamento: para cada campo canonico do Albericus, um
  seletor da coluna de origem (ou "ignorar"), com pre-visualizacao das primeiras
  linhas atualizando ao trocar o mapeamento;
- suportar transformacoes minimas por campo: idade -> ano de nascimento
  aproximado, normalizacao de data, divisao de "Sobrenome, Nome", trim e
  vazio -> nulo;
- reaproveitar o preview de status existente
  (`pronta`/`duplicada`/`erro` por linha) apos o mapeamento, sem persistir antes
  da confirmacao;
- salvar o mapeamento como perfil reutilizavel (`import_mappings`) por
  origem/nome, para reimportar o mesmo formato sem refazer o de-para;
- aceitar apenas formatos tabulares (CSV/XLS/XLSX e URL CSV publicada);
  PDF/imagem digitalizada de formulario nao e suportado.

Criterios de aceite:

- [x] planilha com colunas fora de ordem e nomes divergentes importa apos o
  mapeamento, sem editar o arquivo de origem;
- [x] heuristica acerta o mapeamento obvio (nome, rating, ID) na maioria das
  colunas reconheciveis;
- [x] nenhuma linha e persistida antes da confirmacao no preview;
- [x] perfil de mapeamento salvo reaplica corretamente o de-para numa segunda
  importacao do mesmo formato;
- [x] `inspect_source` e a normalizacao sao servico puro com testes
  (cabecalhos, amostra, palpite, idade->nascimento, "Sobrenome, Nome").

Implementacao:

- `ImportService.inspect_source(source, sample_size=5)` le CSV/XLS/XLSX e URL
  CSV publicada (helpers `_read_tabular`/`_tabular_from_*` extraidos dos leitores
  existentes) e devolve cabecalhos, amostra das primeiras linhas, definicao dos
  campos canonicos (`REGISTRATION_IMPORT_FIELDS`) e palpite por heuristica
  (`_suggest_mapping`, casamento exato e por substring sem reutilizar coluna);
- `_apply_mapping` renomeia cada coluna para a chave canonica (reconhecida por
  `_pick`), converte idade em ano de nascimento (`_birth_year_from_age`) e divide
  "Sobrenome, Nome"; `preview_mapped_registrations`/`import_mapped_registrations`
  reaproveitam `_build_registration_rows` e `_persist_ready_rows`, mantendo o
  preview de status (`pronto`/`duplicado`/`erro`) sem persistir antes da
  confirmacao;
- perfis reutilizaveis em `app_settings` (`import_mapping_profiles`, sem migracao
  de schema): `list_mapping_profiles`, `save_mapping_profile`,
  `delete_mapping_profile`;
- UI: botoes `Importar com mapeamento` e `Importar link com mapeamento` na tela
  `Jogadores`; dialogo com seletor de coluna por campo, perfis (aplicar/salvar/
  excluir) e botao `Pre-visualizar e importar` que reusa o preview de inscricoes
  online (agora parametrizado por um importador);
- 9 testes novos (inspecao, heuristica, idade->nascimento, split de nome,
  preview/import com mapeamento, nome nao mapeado, perfis).

### EPIC F - Conformidade de desempates e classificacao

Prioridade: bloqueante. Origem: auditoria arbitral de 2026-07-29 (analise dos
modulos de gestao de torneio sob otica de arbitro FIDE). Estes itens podem
produzir classificacao publicada incorreta.

#### TBK-01 - Ajustes de pontos aplicados na classificacao

Status: CONCLUIDO (2026-07-30).

Como ficou:

- modulo puro `src/services/pairing/point_adjustments.py`: agrega as linhas de
  `point_adjustments` por competidor (`AdjustmentTotal`), escreve o texto que
  explica o total e define o marcador visual unico (`*`) mais a legenda;
- `calculate_player_standings`/`calculate_team_standings` recebem `adjustments=`
  e somam **depois** dos desempates: a penalidade e decisao sobre o punido, nao
  sobre a forca de quem o enfrentou — Buchholz/SB/performance seguem medindo o
  tabuleiro, que e tambem o que o Gacrux mede;
- ordenacao com o Gacrux ativo: os pontos ja ajustados entram na frente e o rank
  do motor vira o desempate de quem ficou com a mesma soma. Sem ajuste no
  torneio a chave e a de antes, byte a byte. Em equipes o prefixo reordenado vai
  ate o ultimo criterio que um ajuste pode mover (MP/GP);
- **por que o ajuste nao vai ao motor:** no individual o Gacrux recebe TRF-16,
  que nao tem registro 299; no de equipes o TRF-25 tem, mas o
  `parse_trf_abnormal` do motor le o 299 como redefinicao do sistema de pontos,
  nao como penalidade nominal. Vale a primeira saida prevista no escopo
  ("pontos ajustados");
- `PairingService.standings`/`team_standings` alimentam o parametro — e como
  todo consumidor (tela, PDF, XLSX, site, portal, podio, ata, premiacao) passa
  por eles, o numero corrigido chega a todos sem tocar em cada saida;
- ata final ganha a secao "Ajustes de pontos do arbitro (TRF25 §7.3)" com
  rodada, competidor, tipo, MP, GP, motivo e data — omitida quando nao ha
  ajuste;
- lancar, excluir e restaurar um ajuste geram evento em `audit_events` com o
  motivo, que e de onde o `export_tournament_audit` monta o relatorio de
  auditoria. Falha de auditoria nao desfaz a decisao ja gravada.

Criterios de aceite: todos atendidos; 25 testes novos em
`tests/test_core_point_adjustments.py` (individual e equipes, nos dois motores)
e 3 em `tests/test_ui_arbitration.py` (trilha de auditoria).

Problema original:

- `point_adjustments` (penalidades e bonus do arbitro) so alimenta o registro
  299 do TRF25 (`federation_exporters/trf25.py:436`);
  `calculate_player_standings` e `calculate_team_standings` ignoram a tabela.
  Uma deducao de -0,5 aplicada pelo arbitro nao aparece na classificacao da
  tela, no site HTML, no portal live, no boletim, no podio nem na ata final.
  A tabela do sistema contradiz a decisao arbitral em todos os documentos.

Escopo:

- somar ajustes de MP e GP em `calculate_player_standings` e
  `calculate_team_standings` antes da ordenacao;
- marcador visual na classificacao (asterisco com motivo) e nota nos
  documentos exportados;
- manter coerencia com o motor Gacrux quando ativo (pontos ajustados ou
  registro 299 no TRF usado pelo subprocesso).

Criterios de aceite:

- [x] penalidade de -0,5 reordena a classificacao na tela e em todas as
  exportacoes;
- [x] o ajuste aparece com motivo na ata final e no relatorio de auditoria;
- [x] testes cobrem ajuste individual e por equipes nos dois motores de
  desempate.

#### TBK-02 - Fallback do motor de desempates visivel

Status: CONCLUIDO (2026-07-30).

Como ficou:

- modulo puro `src/services/pairing/tiebreak_engine.py`: `EngineReport` com tres
  estados que nao se confundem — **normal** (`used == configured`),
  **degradado** (`fallback`: o Gacrux falhou e o motor proprio assumiu, a tabela
  esta publicada mas nao e a configurada) e **bloqueado** (`blocked`: modo
  estrito barrou, nada foi publicado). Os textos das tres portas (faixa da tela,
  evento de auditoria, pendencia do painel) saem do mesmo lugar;
- `_run_tiebreak_engine` no `PairingService` unifica os caminhos individual e de
  equipes: guarda o retrato, registra evento de auditoria e, em modo estrito,
  levanta `AppError` em vez de degradar;
- **a falha entra no cache junto com o sucesso**, e isso resolve dois problemas
  de uma vez: antes um motor quebrado era re-executado a cada `standings()` —
  dezenas de subprocessos por tela — e agora o motor roda uma vez por ESTADO do
  torneio, o que tambem faz o arbitro receber um aviso por estado em vez de uma
  enxurrada. Fechar rodada nova gera evento novo (ele precisa saber que
  aconteceu de novo); repintar a tela nao gera nenhum;
- `reset_tiebreak_engine` no botao "Recalcular": falha cacheada nao pode prender
  o torneio numa falha passageira. Antes o botao so repintava;
- faixa **permanente** acima da tabela de classificacao, inclusive no estado
  normal — aviso que so aparece no erro ensina o arbitro a nao olhar para aquele
  canto. Degradado/bloqueado acrescentam o detalhe (adversario virtual, ordem
  dos empatados) e o botao de recalculo;
- pendencia no painel do arbitro reusando a porta dos eventos de sync
  (`_audit_issue`), com cartao "Desempate" e filtro proprio na Central;
- **o modo estrito barra a PUBLICACAO, nao o torneio.** Escrever o bloqueio
  dentro de `standings()` sem mais nada pararia o evento: pareamento, previa,
  snapshot de fechamento e diagnostico do painel tambem leem a classificacao, e
  todos so precisam da ORDEM POR PONTOS, que os dois motores calculam igual.
  `standings`/`team_standings` (publicaveis) levantam; `_standings`/
  `_team_standings` com `honor_strict=False` degradam para o motor proprio. O
  retrato e o registro sao os mesmos nos dois caminhos — quem falha e o motor, e
  o modo estrito do torneio e que diz se bloqueia; `honor_strict` so decide se
  ESTE chamador recebe a excecao. Sem isso, um uso interno que chegasse primeiro
  cacharia "degradado" e a publicacao seguinte leria o cache e degradaria em
  silencio, que e exatamente o bug que a TBK-02 fecha;
- pela mesma razao a pendencia entra como `attention`, e nao `decision`:
  severidade `decision` **bloqueia o fechamento da rodada**
  (`_blocking_arbitration_issues_for_round`), o que recriaria a mesma armadilha
  por outro caminho. `audit_issue` ganhou o parametro, com o padrao antigo
  preservado para os eventos de sync, onde bloquear e correto;
- **reentrancia nao e fallback**: a chamada aninhada vinda do export do TRF
  (`_GACRUX_TIEBREAK_INFLIGHT`) usa o motor proprio sem registrar, sem alertar e
  sem valer o modo estrito — senao o export que o proprio motor pediu ficaria
  impossivel;
- configuracao `tiebreak_strict` ("Falhar em vez de degradar") em
  `tournament_settings` (schema v45), nascendo DESLIGADA inclusive nas bases
  existentes: barrar a classificacao e decisao do arbitro do torneio, nao padrao
  que uma migracao imponha.

Criterios de aceite: todos atendidos; 27 testes novos em
`tests/test_core_tiebreak_engine.py` (retrato, faixa, fallback, modo estrito,
equipes, persistencia da configuracao e — os que mais valeram — gerar e fechar
rodada com o motor caido em modo estrito) e 1 em
`tests/test_pairing_gacrux_tiebreak.py` (motor real de pe nao alerta nada —
guarda contra alarme falso).

Problema original:

- se o subprocesso Gacrux falha, `pairing_service.py:1591-1597` apenas loga um
  warning e a classificacao passa a ser calculada pelo motor proprio, que nao
  aplica o adversario virtual. O mesmo torneio pode publicar duas
  classificacoes diferentes entre rodadas sem nenhum aviso ao arbitro.

Escopo:

- badge permanente na tela de classificacao indicando o motor efetivamente
  usado no ultimo calculo;
- evento de auditoria e alerta no painel quando ocorrer fallback;
- opcao de configuracao "falhar em vez de degradar" para torneios FIDE-rated.

Criterios de aceite:

- [x] fallback gera alerta visivel e evento de auditoria;
- [x] classificacao exibe o motor usado;
- [x] em modo estrito, falha do Gacrux bloqueia a publicacao em vez de trocar
  de motor silenciosamente.

#### TBK-03 - Jogos nao disputados conforme FIDE no motor proprio

Status: CONCLUIDO (2026-07-30), pela SEGUNDA saida do escopo.

**A escolha: rebaixar, nao reimplementar.** O escopo dava duas saidas —
implementar o adversario virtual da FIDE no motor proprio ou rebaixa-lo
formalmente a legado. Foi rebaixado, e a razao e de engenharia: as regras de
desempate da FIDE sao versionadas por data de vigencia (o proprio Gacrux carrega
`rulesversion`, com ramos `16.4.1`/`16.4.2` para 2026-02-01), e o Gacrux e o motor
padrao desde o PR #66. Uma segunda implementacao da mesma norma versionada
tenderia a divergir a cada revisao — e duas respostas "oficiais" diferentes e
exatamente o problema que a TBK-02 existe para impedir. Melhor uma implementacao
conforme e a outra honestamente rotulada.

Como ficou:

- `LEGACY_ENGINE_NOTE` e `LEGACY_ENGINE_CHOICE_HINT` em `tiebreak_engine.py`,
  ao lado da razao da escolha. Sai por tres portas: a **faixa** da classificacao
  (reusando o vocabulario da TBK-02 — motor proprio escolhido de proposito agora
  rende tom `warning`, nao `ok`), o **relatorio de desempates** (o aviso vai no
  topo, antes dos numeros, porque e o documento que alguem usa para conferir a
  ordem final) e a **tela de configuracao**, no `help_text` do seletor de motor —
  que e onde a decisao acontece;
- **`wins` deixou de contar W.O.** O criterio e o `WON` da FIDE, "vitorias no
  tabuleiro", e o Gacrux exige `played and opponent > 0`. Antes o Albericus
  contava a vitoria por W.O., entao trocar de motor no meio do torneio reordenava
  os empatados. Ha teste de paridade com o motor real, num torneio COM W.O. e COM
  bye — a restricao "sem W.O." do teste antigo caiu;
- **confronto direto so quando todos os empatados se enfrentaram**, como a FIDE
  exige. Com tres empatados em que A jogou com B e com C mas B e C nao se
  enfrentaram, "quem ganhou de quem" nao e uma ordem — e um pedaco de uma. Antes
  o criterio somava os jogos que existiam e produzia um numero com aparencia de
  resultado; agora e zero para o grupo inteiro, e o desempate seguinte decide.

**Um item da auditoria NAO se confirmou, e vale registrar.** O relatorio pedia
trocar o divisor do limiar de Koya pelas rodadas CONFIGURADAS do torneio, no lugar
das jogadas. O Gacrux usa as jogadas (`compute_koya`: `maxgames = rounds`, onde
`rounds` e o `-n` do subprocesso), entao a mudanca pedida afastaria os dois
motores. Medido no cenario em que os dois divisores divergem — 3 rodadas fechadas
de 7 configuradas — os valores ja batem. Nada foi alterado, e um teste guarda a
equivalencia para que ninguem "conserte" isso depois.

Criterios de aceite:

- [x] fixture com W.O. e byes produz o mesmo Buchholz/SB nos dois motores **ou o
  motor proprio exibe aviso de nao conformidade** — pela segunda alternativa, com
  teste que registra a divergencia de Buchholz como fato (e nao impressao), para
  o dia em que alguem pensar em promover o motor proprio de volta;
- [x] confronto direto so e aplicado quando todos os empatados se enfrentaram;
- [x] teste de paridade `wins` x `WON` sem restricao de "sem W.O.".

**Um defeito de componente apareceu no caminho.** O `help_text` do seletor de
motor foi a primeira ajuda longa escrita no app, e o `labeled_field` montava a
linha de apoio **sem quebra de linha**. Como o painel do formulario e um
`CTkScrollableFrame` (cresce para caber o conteudo), o texto alargou o formulario
inteiro e empurrou os controles para fora da janela — o guarda de layout da B-8
pegou em cinco larguras. O conserto foi no componente, nao no texto: a linha de
apoio quebra na largura da coluna do formulario. Detalhe que custou duas
tentativas: seguir a largura medida com `<Configure>` **realimenta o problema**
(container mais largo -> quebra maior -> rotulo mais largo -> container mais
largo). A largura e fixa de proposito.

Cobertura: 16 testes em `tests/test_core_tbk03.py` e 1 em `tests/test_ui_fields.py`
(a ajuda longa nao pode alargar a caixa do campo). Um teste da TBK-02 foi
ajustado: a faixa do motor proprio deixou de ser tom `ok`.

Problema original:

- no motor proprio (`pairing/tiebreaks.py`), W.O. contam como partida real em
  Buchholz, Sonneborn-Berger, ARO e performance (`:697-700`), e byes nao
  entram no Buchholz (`_opponent_points:232-237`) — contraria as FIDE
  Tie-Break Regulations (adversario virtual, art. 16);
- o parametro `unplayed="self"` (`:246-251`) e inalcancavel pela UI;
- `_direct_encounter_score` (`:281-291`) aplica confronto direto sem verificar
  se todos os empatados se enfrentaram (condicao obrigatoria FIDE) e nao
  redefine o grupo de empate apos cada criterio;
- `wins` conta vitorias por W.O.; o `WON` do Gacrux conta so partidas jogadas —
  trocar de motor no meio do torneio muda a ordem dos empatados;
- `_koya_score` usa como total a maior rodada com jogo registrado
  (`:726-729`), nao o total de rodadas do torneio.

Escopo:

- implementar o adversario virtual e o tratamento de rodadas nao jogadas no
  motor proprio, alinhado a versao das regras vigente pela data do torneio
  (mesmo criterio do Gacrux); ou
- rebaixar formalmente o motor proprio a "modo legado, nao homologavel", com
  aviso na configuracao e no relatorio de desempates;
- corrigir confronto direto, `wins` e Koya em qualquer um dos caminhos.

Criterios de aceite:

- [x] fixture com W.O. e byes produz o mesmo Buchholz/SB nos dois motores (ou
  o motor proprio exibe aviso de nao conformidade) — pela segunda alternativa;
- [x] confronto direto so e aplicado quando todos os empatados se enfrentaram;
- [x] teste de paridade `wins` x `WON` sem restricao de "sem W.O.".

#### TBK-04 - Parametros de criterios editaveis e registro 212 fiel

Status: CONCLUIDO (2026-07-30).

Como ficou:

- **os parametros passam a viver no REGISTRO**, e nao na tela: `TiebreakParam`
  declara chave, rotulo, padrao e faixa (ou lista de opcoes) ao lado do criterio
  em `PLAYER_TIEBREAKS`. Tres leitores, uma definicao — a tela desenha o que o
  registro declara, o motor proprio le em `player_tiebreak_value` e o mapa do
  Gacrux traduz para modificador. O `needs_cut: bool` que existia era declarado e
  nunca lido; morreu;
- `normalize_criterion_params` valida **na porta de entrada** (o
  `parse_*_tiebreak_sequence`): valor fora da faixa volta para dentro, texto sem
  numero volta ao padrao, chave desconhecida e descartada — e o que chega a quem
  calcula vem sempre completo. Nunca levanta: um desempate que recusa a
  configuracao no meio do torneio seria pior que um que ignora um numero
  datilografado errado, e a tela valida antes de qualquer forma;
- **limiar do Koya** virou parametro (era 50% cravado); corte do Buchholz
  (`cut_low`/`cut_high`), `unplayed` e corte do ARO ja eram lidos pelo motor
  proprio e agora sao alcancaveis;
- **os parametros chegam ao motor FIDE.** `specifier_with_params` traduz para os
  modificadores do Gacrux, cuja sintaxe esta em `gacrux/tiebreak.py` (laco que le
  `comp[1:]`): `/C<n>` = corta os n piores, `/M<n>` = corta n de cada ponta,
  `/L<n>` = limiar do Koya em porcentagem. Parametro no valor padrao **nao** vira
  modificador — `BH` e `BH/C1` sao a mesma coisa para o motor, e o mais curto e o
  que o arbitro reconhece no arquivo;
- **registro 212 fiel.** Era a lista fixa `PTS,BH,BH/M1,SB,WIN`, escrita quando o
  projeto ainda nao tinha sequencia configuravel — e por isso o arquivo enviado a
  federacao declarava criterios diferentes dos que o motor usava. Agora sai da
  mesma `tiebreak_sequence` que calcula a classificacao, traduzida pelo mapa. Dois
  ganhos de tabela: os parametros viram modificador no arquivo (`BH/C2`,
  `KS/L60`) e o `WIN` virou **`WON`** — o motor sempre contou vitorias no
  tabuleiro (ver TBK-03), entao declarar `WIN` era declarar outro criterio;
- **o editor devolve os parametros**, com uma segunda linha por criterio (e nao
  ao lado dos botoes de ordenacao, que levaria a tela de volta ao gargalo de
  largura da B-8). Os valores sao guardados fora do `_render` — que destroi e
  recria os widgets a cada subir/descer —, senao ordenar apagaria o corte que o
  arbitro acabou de escolher. Ha teste para exatamente isso.

Criterios de aceite:

- [x] alterar a sequencia no editor muda o 212 exportado;
- [x] parametros persistem no JSON e sao aplicados pelos dois motores;
- [x] teste valida o 212 contra a sequencia configurada (inclusive ponta a ponta,
  lendo a linha 212 do arquivo exportado).

Fica pendente do escopo original: **expor criterios ja suportados pelo Gacrux e
ainda nao registrados** (`BH/M2` como criterio proprio, `SB` cortado, brancas
jogadas, `SNO`, sorteio). O `BH/M2` ja e alcancavel por parametro
(`buchholz_cut2` com corte simetrico); os demais sao criterios novos no registro,
sem defeito associado — entram quando um regulamento pedir.

**O 212 de EQUIPES mudou mais do que o individual**, e vale registrar o que era
errado nele: a lista fixa `PTS,BH:MP,WIN` usava o `PTS` generico onde o primario
de equipes e o match points, **omitia o game points** (que o motor sempre usou) e
declarava `WIN`. Agora sai `MPTS,GPTS,BH,WON` — literalmente o plano que vai ao
`tiebreakchecker`. O `BH` herda o primario no `parse_tiebreak` do Gacrux, entao
equivale ao antigo `BH:MP` sem precisar declarar o tipo de ponto.

Cobertura: 26 testes em `tests/test_core_tbk04.py` e 4 em `tests/test_ui_fields.py`
(o editor). Dois testes existentes do 212 foram atualizados — o individual
(`WIN` -> `WON`) e o de equipes.

Problema original:

- `TiebreakSequenceEditor.get_sequence` devolve sempre `params: {}`
  (`tournament_widgets.py:42-43`): cortes de Buchholz alem de C1/C2/M1, limiar
  do Koya, corte do ARO e `unplayed` nao sao configuraveis pelo arbitro;
- o registro 212 do TRF25 e hardcoded como `PTS,BH,BH/M1,SB,WIN`
  (`trf25.py:591-601`), ignorando `tiebreak_sequence` — o arquivo enviado a
  federacao declara criterios diferentes dos usados (e usa `WIN` onde o motor
  usa `WON`).

Escopo:

- editor de sequencia com parametros por criterio (corte, limiar, unplayed);
- gerar o 212 a partir de `tiebreak_sequence`/`team_tiebreak_sequence` via
  `gacrux_tiebreak_map`;
- expor criterios ja suportados pelo Gacrux e ainda nao registrados
  (`BH/M2`, `SB` cortado, brancas jogadas, `SNO`, sorteio).

Criterios de aceite:

- [x] alterar a sequencia no editor muda o 212 exportado;
- [x] parametros persistem no JSON e sao aplicados pelos dois motores;
- [x] teste valida o 212 contra a sequencia configurada.

#### TBK-05 - Desempates de equipes completos

Status: CONCLUIDO (2026-07-31). Fecha a Sprint 8.

Como ficou:

- **os quatro criterios que faltavam foram registrados** e valem nos dois
  motores. Cada um tem uma definicao so, no registro, e tres leitores (tela,
  motor proprio, mapa do Gacrux) — a mesma forma da TBK-04:

  | criterio | o que e | Gacrux |
  |---|---|---|
  | `sonneborn_berger` | match points do adversario x game points feitos contra ele | `EMGSB` |
  | `direct_encounter` | match points contra as equipes empatadas | `DE` |
  | `buchholz_game_points` | soma dos game points dos adversarios | `BH:GP` |
  | `board_count` | soma do numero do tabuleiro x pontos nele obtidos | `BC` |

- **o SB olimpico nao e o SB de match points.** O `SB` puro do Gacrux usa match
  points dos DOIS lados; o regulamento olimpico pesa a forca do adversario em
  match points e o placar do confronto em pontos de tabuleiro, que e o `EMGSB`.
  No fixture dos testes a diferenca e 14,0 contra 4,0 para a mesma equipe — nao
  e detalhe de arredondamento, e outro criterio. O corte (`EMGSB/C1`, que alguns
  regulamentos pedem) e parametro, e descarta pela mesma regra do motor FIDE:
  menor pontuacao do adversario primeiro, produto como desempate;
- **`higher_is_better` entrou no registro** por causa do board count, o unico
  criterio em que o numero MENOR classifica melhor (o ponto vale mais no
  tabuleiro de cima). Fica declarado ao lado do criterio, e nao numa lista de
  excecoes na hora de ordenar: quem ordena pergunta, em vez de saber de cor;
- **o board count precisa do resultado POR TABULEIRO**, que a classificacao nao
  tinha: entrou `list_team_board_results` e o repasse ate o calculo. A equipe de
  cada cor sai do ELENCO do jogador, e nao da paridade do tabuleiro — tabuleiros
  pares invertem as cores e um jogador pode ter sido substituido; e a mesma regra
  que `team_match_result` usa para somar os game points, entao a soma por
  tabuleiro fecha com o placar do confronto. A consulta so roda quando o board
  count esta na sequencia (nenhum torneio por padrao);
- **divida da TBK-04 paga**: `_gacrux_player_tiebreaks`/`_gacrux_team_tiebreaks`
  montavam a lista so com os CODIGOS, entao o corte configurado chegava ao
  registro 212 do arquivo FIDE mas **nao ao calculo em execucao** — o arquivo
  declarava um criterio e a tela mostrava outro numero. A sequencia agora vai
  inteira, e a chave de cache virou assinatura (codigo + parametros), senao
  mudar so o corte devolveria o calculo velho;
- **os dois registros compartilham codigos com significados diferentes**
  (`sonneborn_berger` de equipes aceita corte, o individual nao; `buchholz` de
  equipes soma match points). `criterion_params` adivinhava o registro e
  devolvia os parametros do criterio errado — passou a receber o registro;
- **a classificacao publicada mostra o numero que decidiu.** A tabela de equipes
  (tela e relatorio) tinha quatro colunas fixas porque eram os quatro criterios
  que existiam; os configurados que nao tem coluna entram agora, na ordem em que
  desempatam. Um desempate que decide o campeonato e nao aparece em lugar nenhum
  nao e utilizavel numa apelacao;
- **modularizacao**: o dominio de equipes saiu de `tiebreaks.py` (1284 linhas,
  individual + equipes) para `team_tiebreaks.py`, e a DECLARACAO dos criterios
  (dataclasses, os dois registros, parametros, parse/serialize da sequencia) para
  `tiebreak_criteria.py`. Grafo de dependencia sem ciclo: declaracao <- calculo.

Uma ressalva medida e assumida: o `DE` do Gacrux devolve uma POSICAO dentro do
grupo empatado (0 quando nao separa) e o do Albericus devolve os pontos feitos
contra os empatados, como no individual. Os numeros nao se comparam; a ORDEM
sim, e e ela que o teste de paridade exige. No modo Gacrux o numero exibido
continua sendo o do motor, como manda a TBK-02.

Byes nao entram no Buchholz, no SB nem no board count do motor proprio: o
adversario virtual da FIDE so existe no Gacrux, que e a razao de o motor proprio
ser legado desde a TBK-03. Por isso os testes de paridade usam um fixture SEM
bye — com bye estariam comparando duas definicoes diferentes, e nao a mesma
conta.

Criterios de aceite:

- [x] campeonato por equipes com regulamento olimpico (MP, DE, SB olimpico)
  ordena corretamente (e igual nos dois motores);
- [x] paridade com o Gacrux testada para os novos criterios, rodando o motor de
  verdade — valores para `EMGSB`, `EMGSB/C1`, `BH:GP` e `BC`; ordem para o `DE`.

Cobertura: 43 testes em `tests/test_core_tbk05.py`.

Problema original:

- so existem 4 criterios de equipes (match points, game points, Buchholz sobre
  MP, vitorias). Faltam os desempates usuais de regulamento FIDE/CBX por
  equipes: Sonneborn-Berger olimpico, confronto direto entre equipes, Buchholz
  de game points e board count/Berlin.

Escopo:

- registrar os criterios adicionais em `tiebreaks.py` e mapear no
  `gacrux_tiebreak_map` (TRF-25 ja transporta equipes);
- disponibilizar no editor de sequencia por equipes.

Criterios de aceite:

- [x] campeonato por equipes com regulamento olimpico (MP, DE, SB olimpico)
  ordena corretamente;
- [x] paridade com o Gacrux testada para os novos criterios.

### EPIC G - Fluxo arbitral em salao

Prioridade: muito alta. Origem: auditoria arbitral de 2026-07-29.

#### ARB-01 - Correcao com motivo, desbloqueio pontual e alerta de cascata

Status: CONCLUIDO (2026-07-30). Fecha a Sprint 7.

Como ficou:

- modulo puro `src/services/pairing/corrections.py`: valida motivo (minimo de 5
  caracteres — "ok" numa ata de apelacao vale tanto quanto o campo vazio),
  calcula expiracao, decide a permissao (`UnlockState`) e descobre as rodadas que
  a correcao contamina. O "agora" chega como parametro, entao a expiracao e
  testavel sem esperar quinze minutos;
- `update_result(..., reason)` exige o motivo quando a rodada esta fechada. **O
  motivo e checado ANTES da permissao**: quem chegou sem motivo precisa saber
  disso mesmo com a rodada desbloqueada, senao desbloqueia, tenta de novo sem
  nomear a razao e leva um recado sobre outra coisa;
- **desbloqueio pontual** (`correction_unlocks`, schema v46): permissao de UMA
  rodada, com justificativa e prazo de 15 min, que morre sozinha. Substitui o
  habito de ligar `allow_dangerous_changes` e esquecer — o interruptor global
  continua valendo, porque nao se tira um caminho que torneios em andamento ja
  usam, mas fica em segundo lugar e a tela diz que ele e o amplo. O diálogo de
  correcao abre dizendo de onde vem a permissao e ate quando ela vale, porque
  numa segunda correcao da mesma sumula o arbitro ja entra direto nele.
  `revoke_round_correction_unlock` existe e e testado, mas **sem botao**: a janela
  expira sozinha em 15 minutos, e um controle para reduzir esse prazo a mao seria
  ruido — quando fizer falta (ARB-03, incidentes), o servico ja esta pronto;
- **cascata**: correcao com rodada posterior ja pareada (inclusive apenas
  gerada — o pareamento dela nasceu do placar antigo) gera evento
  `result_correction_cascade` e pendencia `attention` no painel, com o recado
  dizendo o que fazer, nao so o que houve. `attention` e nao `decision` porque
  quem decide se repareia e o arbitro, e travar o fechamento nao ajudaria;
- **retratos reconciliados**: `standings_snapshots` faz upsert por (torneio,
  rodada), entao regravar apagaria a prova documental. O retrato antigo vai para
  `standings_snapshot_history` com data, hash e motivo; a linha viva passa a ser
  a reconciliada; e um evento `standings_snapshot_reconciled` guarda os dois
  hashes. Os `tiebreak_components` da rodada sao regravados junto;
- para reconciliar sem plantar um segundo erro no lugar do primeiro, nasceu o
  corte `up_to_round` em `_standings`/`_team_standings` (e `current_round` no
  caminho Gacrux, que entra na chave do cache): o retrato da rodada 3 recebe a
  classificacao **como estava depois da rodada 3**, nao a de hoje;
- na tela, o "Alterar mesmo assim?" virou duas perguntas, porque sao duas
  decisoes: *abrir a rodada* (permissao, com prazo) e *o que aconteceu* (o
  registro). Nasce o quinto tipo de dialogo, `reason_dialog`, que usa a MESMA
  funcao pura de validacao do servico — a tela nao reescreve a regra, so a
  aplica antes de o arbitro perder o clique;
- secao "Correcoes em rodada fechada" na ata final, com rodada, `1-0 -> 0-1`,
  operador, motivo e data. A trilha de auditoria e tela de diagnostico; quem
  revisa uma apelacao le a ata. A secao sai da propria trilha, para nao existirem
  duas versoes do mesmo fato — e sai omitida quando nao houve correcao;
- o lancamento rapido do painel recusa rodada fechada com o recado DELE, e nao
  com o do servico: a faixa inline nao tem campo de motivo, entao pedir um seria
  mandar o arbitro preencher o que a tela nao oferece. Ela aponta para a tela
  Rodadas, onde vivem o desbloqueio e o motivo.

Criterios de aceite: todos atendidos. Cobertura: 42 testes em
`tests/test_core_corrections.py` (motivo, expiracao, permissao, cascata,
retratos, ata, individual e equipes), 5 em `tests/test_ui_dialogs.py` (o
`reason_dialog`) e 2 em `tests/test_ui_arbitration.py` (a recusa do lancamento
inline). Cinco testes existentes que corrigiam rodada fechada sem motivo foram
ajustados — e reforcados: um deles virou um par, um cobrando a falta de permissao
com motivo presente e o outro a falta de motivo com permissao presente.

Problema original:

- o motivo da correcao em rodada fechada e hardcoded
  (`pairing_service.py:1062`, "Correcao em rodada fechada."), descumprindo o
  criterio de aceite da Fase 0 do roadmap;
- `allow_dangerous_changes` e um toggle global do torneio: ligado uma vez,
  todas as rodadas fechadas ficam editaveis ate alguem lembrar de desligar;
- corrigir a rodada N com a rodada N+1 ja pareada nao gera alerta nem sugere
  repareamento;
- `standings_snapshots` e `tiebreak_components` nunca sao reconciliados apos
  correcao — a prova documental de uma apelacao fica permanentemente errada.

Escopo:

- campo de motivo obrigatorio no dialogo de correcao;
- desbloqueio por acao, com justificativa e expiracao, no lugar do toggle
  global (ou complementando-o);
- pendencia de severidade `attention` quando ha rodada posterior pareada sobre
  o resultado corrigido;
- regravar ou anotar como "superado" o snapshot das rodadas afetadas.

Criterios de aceite:

- [x] correcao sem motivo e rejeitada;
- [x] correcao com rodada posterior gera alerta de cascata no painel;
- [x] snapshot divergente fica marcado e um novo snapshot reconciliado e
  gravado com auditoria.

#### ARB-02 - Resultados arbitrais completos no painel

Status: CONCLUIDO (2026-07-31). Abre a Sprint 9.

Como ficou:

- **um REGISTRO de codigos de resultado** (`results_registry.py`), porque o que um
  resultado E estava espalhado por seis lugares: `RESULT_POINTS`,
  `WALKOVER_RESULTS`, `FINAL_RESULTS`, o `_trf_player_result` do exportador, o
  `_count_result` dos resumos e os filtros de `fide_rating`. Enquanto os codigos
  se dividiam em "jogada" e "W.O.", conjuntos soltos davam conta; a familia nova
  se distingue por uma propriedade que nenhum deles expressa. Agora cada codigo
  declara pontos, `played`, `rated` e as letras TRF, e os recortes derivam:

  | familia | played | rated | letras TRF | codigos |
  |---|---|---|---|---|
  | normal | sim | sim | `1` `=` `0` | `1-0`, `0-1`, `1/2-1/2` |
  | decisao do arbitro | sim | **nao** | `W` `D` `L` | `1U-0U`, `0U-1U`, `1/2U-1/2U` |
  | W.O./forfait | **nao** | nao | `+` `-` | `1F-0F`, `0F-1F`, `0F-0F` |

- **`W`/`D`/`L`: partida DISPUTADA e nao ratavel.** E o jogo decidido por
  reclamacao, por posicao ilegal irrecuperavel ou por apelacao. Sem esses
  codigos o arbitro escolhia entre mentir no rating (lancar `1-0`) ou mentir no
  Buchholz e no pareamento (lancar W.O., que a FIDE trata como partida nao
  disputada, e que desde a TBK-03 nao conta como vitoria). Como a partida
  aconteceu, ela conta como confronto, entra no Buchholz e no SB e vale `WON` —
  so nao entra no relatorio de rating. A importacao TRF passou a LER as letras
  tambem: eram dois dicionarios escritos a mao, e `W`/`D`/`L` voltava como "sem
  resultado";
- **W.O. no painel**, com botao e atalho (`w`, `p`, `a` — letras, e nao numeros,
  porque passam por confirmacao: um dedo torto no teclado numerico nao pode
  lancar ausencia). A confirmacao nomeia a mesa e os dois jogadores, porque o
  erro que ela precisa pegar e o de mesa errada, nao o de codigo errado;
- **partida adiada** (schema **v47**: `pairings.postponed` + `postponed_note`).
  Uma mesa adiada e uma pendencia ESPERADA; sem a marca, ela e a mesa esquecida
  eram a mesma linha em branco, travando a rodada com o mesmo recado. Agora o
  fechamento nomeia as mesas adiadas em vez de mandar "preencha todos os
  resultados", o painel mostra "Adiada — sabado 14h" na coluna de contexto (que
  no individual vivia vazia) e lancar o resultado desfaz o adiamento — adiada
  com placar preenchido e um estado que nao existe no salao. A nota e OPCIONAL:
  adiar sem saber quando ainda e melhor do que a mesa parecer esquecida.

A pendencia do painel e `attention`, e nao `decision`: a decisao o arbitro ja
tomou — foi ele quem adiou. Quem impede o fechamento e a mesa sem resultado, com
o recado proprio; marcar como bloqueante faria a mesma coisa aparecer duas vezes,
com dois textos diferentes.

Criterios de aceite:

- [x] W.O. lancavel pelo painel com confirmacao e auditoria;
- [x] rodada com partida adiada exibe pendencia especifica (e o recado do
  fechamento nomeia as mesas);
- [x] `W`/`D`/`L` exportam corretamente no TRF16 — e sao lidos na importacao.

Cobertura: 32 testes em `tests/test_core_arb02.py`.

Problema original:

- W.O. (`1F-0F`, `0F-1F`, `0F-0F`) so pode ser lancado na tela `Rodadas`; o
  lancamento inline do painel (`pairing_arbitration/pending.py:37`) oferece so
  1-0, 1/2 e 0-1 — justamente no momento em que o arbitro esta em pe no salao;
- nao existe estado "partida adiada/suspensa" nem os codigos TRF `W`/`D`/`L`
  (jogo decidido sem lance ratavel, ex.: resultado por decisao do arbitro).

Escopo:

- botoes e atalhos de W.O. no lancamento inline (com confirmacao);
- estado `adiada` que nao bloqueia o restante do painel mas impede fechar a
  rodada ate resolucao;
- suportar codigos `W`/`D`/`L` no modelo de resultado e no TRF16.

Criterios de aceite:

- [x] W.O. lancavel pelo painel com confirmacao e auditoria;
- [x] rodada com partida adiada exibe pendencia especifica;
- [x] `W`/`D`/`L` exportam corretamente no TRF16.

#### ARB-03 - Registro disciplinar de incidentes

Status: CONCLUIDO (2026-07-31). Fecha a Sprint 9.

Como ficou:

- **tabela `incidents`** (schema **v50**) com catalogo de infracoes FIDE:
  celular (11.3.2), lance ilegal (7.5), atraso alem da tolerancia (6.7), conduta
  (12.2), anotacao (8.1), resultado combinado (11.1), queda de seta contestada
  (6.2) e "outro". Era tudo papel — a tabela do manual operacional;
- **o catalogo nomeia o ARTIGO, e nao a sancao.** A FIDE deixa a sancao a cargo
  do arbitro (11.3.2 e a excecao historica, e mesmo ela tem margem em rapidas),
  entao cada infracao traz a sancao SUGERIDA e o arbitro escolhe. O que o sistema
  garante e que a escolha fique registrada;
- **a decisao chega na classificacao.** Deducao cria o `point_adjustment`
  vinculado (`adjustment_id`), que desde a TBK-01 move a ordem; partida perdida
  lanca o resultado na mesa. Uma decisao disciplinar que nao chega na tabela e um
  bilhete;
- **partida perdida e W.O. (`1F-0F`), e nao o `1U-0U` da ARB-02.** Quem perde por
  regulamento NAO JOGOU a partida aos olhos da FIDE — o adversario nao ganha uma
  vitoria no tabuleiro nem a partida entra no rating. Sao duas coisas parecidas
  que a ARB-02 acabou de separar, e usar a errada aqui desfaria aquilo;
- **queda de seta e ausencia BLOQUEIAM o fechamento** ate a decisao ser
  registrada (eram `attention`, e a rodada fechava com a pergunta em aberto).
  Registrado o incidente que aponta para o evento (`clock_event_id`), o alerta
  volta a ser informativo: a decisao existe e esta na ata. Aviso de tempo critico
  continua sendo so aviso;
- **anexo disciplinar na ata**, com rodada, mesa, jogador, artigo, decisao,
  observacoes e **reincidencia marcada** — que e o numero que o catalogo existe
  para produzir: no papel, a segunda advertencia do mesmo artigo ao mesmo jogador
  nao era encontravel por ninguem.

Os vinculos (`adjustment_id`, `clock_event_id`, `pairing_id`) sao OPCIONAIS de
proposito: advertencia nao mexe em ponto nem em mesa, e exigir os tres
transformaria o registro de uma conversa em burocracia que ninguem preenche no
meio da rodada. O que e exigido esta na validacao: partida perdida sem mesa e
deducao sem valor sao recusadas, e "outro" exige descricao — e ela que a ata
cita no lugar do artigo.

Criterios de aceite:

- [x] incidente com deducao reflete na classificacao (via TBK-01);
- [x] relatorio de incidentes sai na ata final;
- [x] queda de seta registrada exige decisao antes de fechar a rodada.

Cobertura: 27 testes em `tests/test_core_arb03.py`.

Fica pendente do escopo original: a **ficha do jogador** com as reincidencias
como TELA. O dado existe e sai na ata (`incident_repeat_offenders`); o que falta
e a visualizacao por jogador, que e trabalho de UI sem regra nova.

Problema original:

- nao existe modulo de incidentes disciplinares: celular (art. 11.3.2), lance
  ilegal (7.5), atraso/default time (6.7), conduta (12.x). O registro hoje e
  em papel (tabela do manual operacional). `point_adjustments` existe mas nao
  tem catalogo de infracoes nem vinculo com o jogador reincidente.

Escopo:

- tabela `incidents` com catalogo de infracoes FIDE, jogador, rodada/mesa,
  decisao do arbitro, observacoes;
- vinculo opcional com `point_adjustments` (deducao) e com o resultado
  (partida perdida);
- ficha do jogador com reincidencias; relatorio de incidentes do torneio
  (anexo da ata final);
- alertas de relogio `flag_fall`/`absence` promoviveis a pendencia bloqueante
  ate decisao registrada.

Criterios de aceite:

- [x] incidente com deducao reflete na classificacao (depende de TBK-01);
- [x] relatorio de incidentes sai na ata final;
- [x] queda de seta registrada exige decisao antes de fechar a rodada.

#### ARB-04 - Politica de byes solicitados

Status: CONCLUIDO (2026-07-31).

Como ficou:

- **a causa dos quatro defeitos era a mesma**: o bye solicitado era gravado
  DIRETO da tela no banco (`db.add_requested_bye`), sem passar por servico. O que
  se validava era o FORMATO do formulario (tem alvo? tem rodada? o tipo e F/H/Z?)
  — nao havia onde uma politica morar. Agora ha
  `PairingService.request_bye()`, com auditoria, e a tela chama o servico;
- **modulo puro `bye_policy.py`** com as regras e os textos. `ByePolicy` le as
  duas configuracoes novas (schema **v48**): `max_requested_byes` e
  `last_requested_bye_round`, ambas com padrao `0` = SEM LIMITE, que e o
  comportamento que os torneios existentes sempre tiveram;
- **rodada ja gerada e recusada**, e o recado diz por que: o pareamento daquela
  rodada ja esta feito, entao o bye seria "aceito e nunca aplicado" — que era
  exatamente o defeito. Rodada fechada idem, apontando para a correcao com
  motivo (ARB-01);
- **jogador inativo e recusado NA HORA DO PEDIDO**, com o motivo. Sobra um unico
  caminho para o descarte — o jogador que sai DEPOIS de pedir —, e esse agora
  AVISA: evento de auditoria, log e pendencia `attention` no painel. A geracao
  segue: barrar a rodada por um pedido que ficou para tras seria trocar um
  silencio ruim por uma parada pior;
- **o bye de zero ponto (`Z`) nao conta para o limite.** Limita-lo puniria quem
  AVISOU que faltaria, em vez de simplesmente nao aparecer — e ele nao da ponto
  nenhum. Corrigir o tipo de um bye ja existente tambem nao esbarra no limite.

Sobre o `disable_bye`, o escopo dava duas saidas ("cobrir tambem os byes
solicitados ou renomear a flag"): foi **renomeada** (rotulo "Desativar bye
alocado (PAB)"). Sao coisas diferentes — aquela flag desativa o bye que o sistema
DA a quem sobra num numero impar, e um bye solicitado e o jogador AVISANDO que
faltaria. Juntar as duas quebraria o regulamento mais comum, que exige numero par
de presentes mas aceita ausencia avisada.

Fica pendente do escopo original: **prazo de solicitacao** por data. Ele existe
hoje na forma que resolve o defeito — o pedido vale enquanto a rodada nao foi
gerada —, e um prazo em horas exigiria relogio de torneio, que o sistema nao tem.
Fica tambem o bye ALOCADO que repete quando todos ja receberam (hoje so alerta):
e regra de motor de pareamento, e nao de politica de bye.

Criterios de aceite:

- [x] pedido acima do limite ou fora do prazo e rejeitado com mensagem clara;
- [x] bye para rodada fechada e impossivel (e para rodada ja gerada tambem);
- [x] testes cobrem os limites e o descarte avisado.

Cobertura: 24 testes em `tests/test_core_arb04.py`.

Problema original:

- nao ha limite de byes por jogador, nem proibicao de bye de meio ponto nas
  ultimas rodadas (regra comum de regulamento), nem validacao contra rodada ja
  fechada (o bye e aceito e nunca aplicado, silenciosamente);
- byes de jogadores inativos sao descartados sem aviso
  (`pairing_service.py:742-746`);
- `disable_bye` nao impede byes solicitados (`:754-774`);
- o bye alocado pode repetir quando todos ja receberam, virando so alerta.

Escopo:

- configuracoes por torneio: maximo de byes H por jogador, ultima rodada
  permitida, prazo de solicitacao;
- rejeitar (com mensagem) bye para rodada fechada ou jogador inativo;
- fazer `disable_bye` cobrir tambem os byes solicitados ou renomear a flag.

Criterios de aceite:

- [x] pedido acima do limite ou fora do prazo e rejeitado com mensagem clara;
- [x] bye para rodada fechada e impossivel;
- [x] testes cobrem os limites e o descarte avisado.

#### ARB-05 - Retirada e reentrada com historico por rodada

Status: CONCLUIDO (2026-07-31).

Como ficou:

- **tabela `player_status_events`** (schema **v49**), append-only: torneio,
  jogador, rodada de vigencia, estado, motivo e autor. O campo
  `players.player_status` CONTINUA existindo — ele e o estado corrente, que o
  pareamento ja le; o que faltava era o rastro, e um campo unico apaga o
  anterior a cada mudanca;
- **a mudanca vale da PROXIMA rodada.** A rodada em andamento ja foi pareada:
  tirar alguem agora nao desfaz a mesa dele — isso e resultado (W.O.) ou
  correcao. E tambem a leitura do salao ("a partir da 4 ele nao joga mais");
- **modulo puro `participation.py`** responde o que o historico guarda:
  `status_at_round`, `absence_rounds`, `history_lines` e um `summarize` que
  agrupa faixas ("Fora R3-R5"). Quem grava e
  `PairingService.set_player_participation()`, com auditoria; as DUAS telas que
  mexiam no estado (cadastro de jogadores e chamada inicial) passaram a chamar o
  servico em vez de `db.set_player_status` cru;
- **reentrada de quem DESISTIU exige motivo**, e a de quem so faltou nao. Voltar
  um desistente e decisao arbitral e vai para a ata; voltar quem faltou uma
  rodada e rotina de salao. Repetir o estado atual e recusado;
- **secao propria na ata**: "Desistencias, ausencias e reentradas", com situacao
  final, rodadas fora e o historico com os motivos.

Sobre o TRF, e vale registrar porque o escopo pedia a distincao: **o arquivo nao
tem codigo para separar "desistiu" de "faltou"**. As duas viram `0000 - Z` (nao
pareado, zero ponto), e isso esta CERTO — o que a FIDE distingue e `Z` de `-`
(pareado e nao compareceu, que e forfeit e exige mesa), e essa distincao o
sistema ja fazia por construcao. A diferenca entre desistencia e ausencia e do
REGULAMENTO, nao do arquivo, e por isso ela mora na ata. Ha teste para as duas
afirmacoes.

Criterios de aceite:

- [x] jogador que sai e volta e pareado corretamente e o historico mostra as
  rodadas de ausencia;
- [x] TRF diferencia os casos que o formato permite diferenciar (`Z` x `-`), e a
  ata carrega a distincao que o formato nao tem;
- [x] auditoria registra quem/quando/motivo.

Cobertura: 22 testes em `tests/test_core_arb05.py`.

Problema original:

- `player_status` e um campo unico sem historico: `withdrawn` e `absent`
  produzem o mesmo efeito (`active = 0`) e nao ha rastro de "saiu na rodada 3,
  voltou na 5". No TRF tudo vira `0000 - Z`, sem distincao entre desistencia,
  ausencia e bye zero solicitado.

Escopo:

- registrar eventos de retirada/reentrada por rodada (tabela propria ou
  `audit_events` estruturado);
- pareamento exclui o jogador nas rodadas de ausencia e o reinclui na volta;
- exportacao TRF diferencia `Z` (ausencia anunciada) de `-` (forfeit) conforme
  o caso; ata final lista desistencias com rodada.

Criterios de aceite:

- [x] jogador que sai e volta e pareado corretamente e o historico mostra as
  rodadas de ausencia;
- [x] TRF e tabela cruzada diferenciam os casos;
- [x] auditoria registra quem/quando/motivo.

### EPIC H - Motores de pareamento (correcoes)

Prioridade: alta. Origem: auditoria arbitral de 2026-07-29.

#### PAR-01 - Round-robin com tabela persistida e returno

Status: pendente.

Problema:

- `round_robin_pairings` (`pairing/fide_dutch.py:89-147`) recalcula o circulo
  a cada rodada a partir da lista ativa ordenada por rating: desativar um
  jogador ou editar um rating no meio do evento muda todo o calendario
  restante (revanches e confrontos perdidos);
- o bye do rodizio grava `result = "1-0"` e so pontua certo porque
  `bye_points` default e 1.0 (`fide_dutch.py:131` x `tiebreaks.py:671`);
- nao ha duplo turno (returno), formato padrao de fechados e torneios de
  norma, nem tabelas de Berger (FIDE C.05).

Escopo:

- sortear/atribuir numeros de rodizio uma unica vez e persistir a tabela
  (Berger) na criacao do torneio;
- desistencia em RR segue a regra FIDE (anular ou manter resultados conforme
  percentual jogado), sem recalcular o calendario;
- opcao de duplo round-robin com cores invertidas no returno;
- bye do rodizio gravado como bye real (nao `1-0`).

Criterios de aceite:

- [ ] desativar jogador nao altera os confrontos futuros dos demais;
- [ ] fixture Berger de 6 e 8 jogadores confere com a tabela FIDE;
- [ ] returno inverte cores corretamente.

#### PAR-02 - Aceleracao e entrada tardia no caminho Gacrux

Status: pendente.

Problema:

- aceleracao so e aplicada no motor proprio (`pairing_service.py:1918`);
  com `pairing_system = gacrux_swiss` (padrao) ela e silenciosamente ignorada
  (`:767-769`), sem aviso;
- `starting_points` de entrada tardia nao chega ao Gacrux: o TRF-16 exporta as
  rodadas ausentes como `0000 - Z` (0 ponto) (`export_federation.py:713`),
  entao o Gacrux pareia o entrante tardio com pontuacao diferente da
  classificacao publicada.

Escopo:

- com aceleracao configurada + Gacrux: aplicar via TRF (XXA/250 quando o
  formato aceitar) ou cair no motor proprio com aviso explicito ao arbitro —
  nunca ignorar em silencio;
- transportar pontos de entrada tardia ao Gacrux (celulas de rodada coerentes
  com `starting_points`) ou avisar da divergencia.

Criterios de aceite:

- [ ] configurar aceleracao com Gacrux gera aviso ou aplica de fato;
- [ ] entrante tardio e pareado com os pontos exibidos na classificacao;
- [ ] teste compara pareamento Gacrux x classificacao com entrada tardia.

#### PAR-03 - Knockout e Scheveningen maduros

Status: pendente.

Problema:

- no mata-mata, empate, duplo W.O. ou resultado vazio promovem o melhor seed
  silenciosamente (`fide_dutch.py:234-241`), sem desempate nem registro do
  criterio;
- Scheveningen exige grupos exatamente iguais e recalcula a escala a cada
  rodada (`:150-203`) — desistencia quebra o formato.

Escopo:

- desempate de KO configuravel: mini-match, partidas rapidas/blitz, armagedom
  ou decisao manual do arbitro, com registro do criterio de avanco;
- disputa de 3o lugar opcional e visualizacao de chave;
- Scheveningen com escala persistida e tolerancia a desistencia (bye ou
  substituto).

Criterios de aceite:

- [ ] empate em KO exige decisao registrada antes de gerar a proxima fase;
- [ ] a chave exibe por que cada jogador avancou;
- [ ] Scheveningen sobrevive a desistencia sem corromper confrontos passados.

#### PAR-04 - Dividas tecnicas do nucleo de pareamento

Status: PARCIAL (2026-07-30) — os quatro itens pontuais entregues; resta o
topscorers (C.3), que e feature de motor e nao conserto.

Como ficou (parte pontual):

- **`TEAM_PAIRING_METHODS` duplicado**: a segunda atribuicao (so `swiss`)
  apagava a primeira em silencio, e por isso o round-robin por equipes era
  recusado pela validacao e sumia do menu. A linha morreu, e ficou no lugar um
  comentario dizendo por que nao se redefine ali. Um teste le o proprio
  `constants.py` e falha se a constante voltar a ser atribuida duas vezes — o
  defeito era invisivel para quem lia so o topo do arquivo;
- **round-robin por equipes de fato pareando**: a geracao de rodada por equipes
  nunca lia `team_pairing_method` (so a exportacao e o motor de desempate liam),
  entao destravar a constante sozinha teria deixado o arbitro escolher um metodo
  que o motor ignorava — uma mentira em vez de uma limitacao. Nasce
  `round_robin_team_matches` (puro, em `team_swiss.py`): mesma rotacao Berger do
  round-robin individual, equipe fantasma quando o numero e impar, cor de equipe
  alternando com a paridade da rodada (sem isso a equipe que nao gira jogaria
  sempre de brancas), e os tabuleiros saindo do `team_match_payload` que ja
  existia. Bye SOLICITADO e recusado nesse modo: tirar uma equipe da rotacao
  desloca todo mundo e faz pares se repetirem — num calendario fixo quem nao
  comparece perde por W.O., nao "folga", e a recusa e explicita porque o
  silencio aqui pareava a rodada errada sem ninguem ver;
- **troca de cores com auditoria**: `swap_pairing_colors` era chamado direto do
  `db` pela tela — a UNICA mutacao de rodada sem passar pelo servico e, portanto,
  sem trilha. Agora ha `PairingService.swap_pairing_colors`, espelhando o de
  equipes, com as guardas (rodada fechada, mesa de outro torneio, bye, resultado
  ja lancado) e evento `pairing_colors_swapped`. O caminho de equipes ja passava
  pelo servico mas tambem nao auditava: ganhou `team_board_colors_swapped`;
- **`pending` acumulado no fechamento por equipes**: era uma lista unica para
  todos os confrontos, entao um tabuleiro em branco no primeiro confronto fazia
  todos os seguintes pularem o sumario. A pendencia passou a ser por confronto;
- **`KeyError` cru em `team_match_summary`**: tabuleiro em branco ou com codigo
  desconhecido subia como `KeyError`, que a tela mostrava como "erro inesperado"
  com codigo de log — para uma situacao previsivel que o arbitro resolve sozinho.
  Virou `AppError` dizendo qual tabuleiro e o que fazer.

Achado no caminho, fora da lista da auditoria: **`Dialog(self, ...)` em
`swaps.py`**, onde `self` e o objeto de acoes e nao a janela — o mesmo defeito que
a extracao da B-6 encontrou no `qr.py` e que aqui tinha passado. "Trocar jogador"
(individual e equipes) nao abria.

Problema (itens pontuais confirmados na auditoria):

- `TEAM_PAIRING_METHODS` definido duas vezes (`constants.py:111` e `:123`); a
  segunda definicao sobrescreve a primeira e torna o round-robin por equipes
  inalcancavel (validacao rejeita e o menu so mostra Suico);
- `swap_pairing_colors` e chamado direto da UI (`pairing_results_ui.py:1415`)
  sem passar pelo `PairingService` — unica mutacao de rodada sem auditoria;
- `pending` acumulado fora do laco em `_close_team_round`
  (`pairing_service.py:1170,1190`) pula confrontos completos do sumario;
- `team_match_summary` levanta `KeyError` bruto com resultado invalido
  (`team_swiss.py:121`);
- criterio absoluto C.3 (topscorers) inexistente no motor proprio (cor e
  sempre soft);
- `float_histories` conta W.O. como float enquanto cor e repeticao os
  excluem — tratamento inconsistente do mesmo jogo;
- `team_pair_penalty` nao penaliza float repetido no Suico por equipes.

Escopo e criterios de aceite:

- [x] round-robin por equipes volta a ser selecionavel (ou e removido da
  constante com changelog) — **selecionavel E pareando**;
- [x] troca de cores passa pelo servico com evento de auditoria;
- [x] fechamento de equipes reporta todos os confrontos completos mesmo com
  pendencia anterior;
- [x] resultado invalido em equipes vira `AppError` legivel;
- [ ] topscorers (C.3) respeitado nas rodadas finais do motor proprio, com
  teste — **fica para o PAR-04 completo**: e regra de motor, nao conserto
  pontual, e o motor proprio deixou de ser o padrao de pareamento no PR #66
  (hoje quem pareia e o Gacrux, que ja aplica C.3). Junto com ele ficam os
  outros dois itens de motor: `float_histories` contando W.O. como float
  enquanto cor e repeticao o excluem, e `team_pair_penalty` sem penalizar float
  repetido no Suico por equipes.

Cobertura da parte pontual: 18 testes em `tests/test_core_par04.py` — Berger de
equipes (cada par uma vez, bye rotativo, cores alternando, calendario cheio),
round-robin ponta a ponta pelo servico (inclusive a recusa do bye solicitado),
troca de cores com trilha nos dois modos e com as quatro recusas, sumario com
recado legivel e o fechamento que nao descarta mais confronto completo.

### EPIC I - Submissao federativa (FIDE e CBX)

Prioridade: alta. Origem: auditoria arbitral de 2026-07-29.

#### FED-03 - TRF16 de campo completo

Status: pendente.

Problema:

- o TRF16 nao emite os codigos de extensao de facto `XXR` (total de rodadas),
  `XXC` (cor inicial) e `XXA` (aceleracao) — emite `142` no lugar de `XXR`,
  que e registro TRF25; motores/validadores que esperam o dialeto TRF16 ficam
  sem o total de rodadas;
- `FIDE Event-ID` e validado mas nunca exportado; FIDE ID dos arbitros nao sai
  nos registros 102/112;
- partida pareada sem resultado exporta como `Z` (ausencia conhecida) —
  semanticamente errado; `082 0` sai em torneio individual; `092` usa texto
  proprietario;
- nenhuma validacao de jogador e bloqueante (FIDE ID ausente/duplicado,
  federacao, nascimento) — o arquivo sai mesmo assim;
- TRF16 e TRF25 divergem no numero de celulas de rodada emitidas para o mesmo
  torneio.

Escopo:

- emitir `XXR`/`XXC`/`XXA` no TRF16; restringir `082` a equipes; `092`
  compativel com Swiss-Manager/Chess-Results;
- exportar FIDE Event-ID e FIDE ID de arbitros;
- modo "submissao": validacoes criticas bloqueiam a geracao (com lista clara
  de pendencias); resultado pendente impede exportar ou exige confirmacao;
- validacao cruzada de reciprocidade oponente/cor antes de exportar.

Criterios de aceite:

- [ ] TRF16 gerado passa no validador do Gacrux e abre no Swiss-Manager;
- [ ] modo submissao bloqueia arquivo com FIDE ID duplicado ou resultado
  pendente;
- [ ] fixture compara TRF16 x TRF25 do mesmo torneio (mesmo numero de rodadas).

#### FED-04 - Round-trip TRF fiel

Status: pendente.

Problema:

- a importacao TRF trata `U` e `F` como o mesmo bye de ponto inteiro
  (`trf_import.py:149-151`) — importar do Swiss-Manager pode inflar pontuacao
  quando `bye_points` difere de 1.0; `Z` e descartado (ausencia some do
  historico); `W`/`D`/`L` nao sao decodificados; arbitros, datas de rodada,
  equipes e todos os registros TRF25 sao ignorados.

Escopo:

- distinguir `U` (bye alocado, pontua por `bye_points`) de `F`;
- preservar `Z` e decodificar `W`/`D`/`L`;
- importar arbitros, datas (132) e secao de equipes;
- teste de round-trip export -> import -> export byte-comparavel para os
  campos suportados.

Criterios de aceite:

- [ ] TRF do proprio Albericus reimporta sem perda de byes/ausencias;
- [ ] TRF do Swiss-Manager com bye `U` pontua conforme configuracao;
- [ ] round-trip coberto por teste automatizado.

#### FED-05 - Lista FIDE: data de nascimento e robustez do download

Status: pendente.

Problema:

- a importacao da lista FIDE grava so o ANO em `birth_date`
  (`rating_service.py:333,351`): o campo 70-79 do 001 sai invalido e todo
  jogador importado dispara o aviso de nascimento — envenena o TRF do plantel
  inteiro;
- download da FIDE sem tratamento de erro (`:310`, `URLError` cru na UI), URL
  em `http://`, `errors` sempre vazio (linha malformada nunca e reportada),
  corte de linha em 120 chars le nascimento em 126-131.

Escopo:

- armazenar ano como ano (campo proprio ou `YYYY-00-00` documentado) e emitir
  o 001 com ano quando for o unico dado (formato aceito pela FIDE);
- tratar falha de rede com mensagem, `https`, e reportar linhas ignoradas.

Criterios de aceite:

- [ ] importar lista FIDE nao gera avisos falsos de nascimento no TRF;
- [ ] falha de download mostra erro amigavel;
- [ ] teste do parser de largura fixa com fixture real.

#### FED-06 - Normas FIDE corretas e certificados IT

Status: pendente.

Problema:

- `_has_title` conta CM/WCM/NM/WNM como "titulado" (`fide_norms.py:21,33-34`);
  o Handbook exige contagem por nivel (norma de GM: minimo de GMs e de
  titulados IM+) — um torneio cheio de CMs pode indicar norma indevida;
- a contagem de federacoes inclui a federacao do proprio candidato
  (`:122-124`); faltam limites de mesma federacao e de nao ratados, piso de
  rating de adversario, e a tabela proporcional de 7 a 13 rodadas
  (`min_games` fixo em 9);
- nao existem certificados IT1/IT2/IT3 — sem o IT3 o arbitro nao consegue
  submeter a norma que o proprio sistema diz ter sido atingida.

Escopo:

- corrigir os indicadores conforme o Handbook B.01 (titulos) vigente;
- gerar IT3 preenchido (PDF) por norma detectada, e apoio ao IT2/relatorio de
  rating;
- manter o texto "assistencia ao arbitro, nao homologacao".

Criterios de aceite:

- [ ] fixture de norma conhecida (torneio real) valida os indicadores;
- [ ] IT3 sai preenchido com os dados do torneio e do candidato;
- [ ] federacao do candidato fora da contagem de federacoes.

#### FED-07 - Rating: K correto, piso e ritmo

Status: pendente.

Problema:

- K=40 de jogador novo nunca dispara (`build_fide_report_rows` nao passa
  `games_played`, `fide_rating.py:202-207`); regra dos 400 apenas reportada;
  sem piso de rating; sem distincao standard/rapid/blitz (lista, K e relatorio
  usam um unico rating); nao ha calculo de rating inicial de nao ratado;
- o relatorio CBX e o algoritmo FIDE com outra coluna — o regulamento CBX
  (K, piso, nao ratados) nao esta modelado e nao existe arquivo de submissao
  CBX.

Escopo:

- passar `games_played` ao K e aplicar piso configuravel;
- classificar o torneio em standard/rapid/blitz a partir do controle de tempo
  estruturado (ver ORG-03) e usar a lista/K corretos;
- modelar o regulamento CBX de rating e gerar o relatorio de submissao no
  formato aceito pela CBX.

Criterios de aceite:

- [ ] jogador com menos de 30 partidas recebe K=40 no relatorio;
- [ ] torneio rapido usa rating rapido dos inscritos;
- [ ] relatorio CBX documentado contra o regulamento vigente.

### EPIC J - Organizacao do torneio (categorias, premios, agenda)

Prioridade: media-alta. Origem: auditoria arbitral de 2026-07-29. Itens com
interseccao com `ESPEC_PARIDADE_SWISSMANAGER.md` (E4/E10) — detalhar la quando
virar implementacao.

#### ORG-01 - Categorias configuraveis por torneio

Status: pendente.

Problema:

- faixas etarias (Sub-08..20, S50+, S65+) e de rating (1400/1800/2200) sao
  hardcoded em `core/categories.py:6-19`; um edital com Sub-07/09/11/13,
  Veterano 60+, ou cortes 1600/2000 nao e configuravel;
- "Feminino" e tag de premio, nao categoria — nao existe classificacao
  feminina nem premio feminino automatico;
- a data de referencia da idade nao e parametrizavel (usa o ano do torneio;
  FIDE/CBX usam 1o de janeiro).

Escopo:

- tabela de categorias por torneio (nome, tipo idade/rating/sexo/tag, faixas,
  data de referencia);
- jogador pode pertencer a multiplas categorias premiaveis;
- classificacao filtravel por categoria e secao na ata/podio.

Criterios de aceite:

- [ ] edital com faixas fora do padrao e configuravel sem texto livre;
- [ ] classificacao feminina sai automaticamente quando configurada;
- [ ] data de referencia altera o calculo de idade nos testes.

#### ORG-02 - Premiacao conforme edital

Status: pendente.

Problema:

- o alocador so casa premio de categoria com a categoria primaria unica do
  jogador (`prizes.py:128` x `categories.py:101`): premio "Feminino" nunca e
  alocado automaticamente e um Sub-12/Sub-1400 concorre a um so;
- o Sistema Hort implementado e uma "interpretacao comum" nao auditavel
  contra o Swiss-Manager (`prizes.py:90-98`);
- desistentes/W.O. nao sao excluidos da alocacao; premios por equipe e
  tabuleiro sao apenas manuais; a spec E4 previa `currency` e `cumulative`
  por premio e a tabela nao os tem.

Escopo:

- alocar tambem por `age_category`, `rating_category` e `prize_tags`;
- politica por premio (acumula ou nao) e moeda;
- opcao de excluir desistentes; alocacao automatica por equipes;
- documentar a formula Hort adotada e validar contra caso conhecido do
  Swiss-Manager.

Criterios de aceite:

- [ ] premio Feminino e alocado automaticamente;
- [ ] jogador multi-categoria segue a politica configurada;
- [ ] fixture de premiacao conhecida (edital real) confere.

#### ORG-03 - Agenda e controle de tempo estruturados

Status: pendente.

Problema:

- `round_schedule` so tem data e hora; faltam local, ritmo por rodada, dia de
  descanso e tolerancia de atraso (default time);
- `_validated_schedule` descarta silenciosamente rodadas acima do total
  (`tournament_service.py:626-627`) — reduzir rodadas apaga datas publicadas;
- `time_control` e texto livre: nao classifica o evento em
  standard/rapid/blitz (necessario para lista e K de rating — FED-07), nao
  alimenta o `222` do TRF25 em grafias comuns (`90'+30"`) e nao valida contra
  os minimos de norma.

Escopo:

- controle de tempo estruturado (fases, incremento) com apresentacao livre;
- agenda com ritmo/local por rodada e dias de descanso;
- aviso (nao descarte) ao reduzir rodadas com agenda preenchida;
- tolerancia de atraso configuravel exibida no painel da rodada.

Criterios de aceite:

- [ ] `90'+30"` classifica como standard e gera `222` valido;
- [ ] reduzir rodadas exige confirmacao quando ha agenda;
- [ ] tolerancia aparece no painel e na sumula.

#### ORG-04 - Configuracao honesta (flags mortas e bloqueios pos-R1)

Status: pendente.

Problema:

- flags exibidas na UI sem nenhum consumidor: `accelerated_system` (o arbitro
  marca e acredita ter acelerado o torneio), `allow_public_registration`,
  `allow_player_result_edit`, `hide_color_names`,
  `show_opponents_in_standings`; `calculate_performance` e so rotulo;
  `archived` nao filtra a lista de torneios;
- e possivel trocar `initial_order`, aceleracao e sequencia de desempates no
  meio do torneio sem aviso nem auditoria;
- `tournaments.system` (default `'Suico'`) e legado dessincronizado de
  `pairing_method`.

Escopo:

- remover ou implementar cada flag morta (decisao por flag, com changelog);
- mudancas estruturais apos a rodada 1 exigem confirmacao com motivo e geram
  evento de auditoria;
- `archived` passa a ocultar da lista padrao.

Criterios de aceite:

- [ ] nenhuma opcao visivel na UI e inerte;
- [ ] trocar desempates com torneio em andamento gera auditoria;
- [ ] torneio arquivado some da lista padrao e reaparece com filtro.

## 6. Fora de Escopo

Nao iniciar sem requisito externo concreto:

- aceleracao de Baku enquanto a formula aplicavel nao estiver publicada;
- submissao automatica para federacao sem API publica;
- decisao automatica de WO ou queda de seta;
- plugin de hardware sem equipamento alvo;
- PGN com lances sem captura de lances;
- app Android/iOS nativo;
- importacao de formularios em PDF/imagem digitalizada (REG-02 trata apenas
  formatos tabulares; OCR nao sera implementado).

## 7. Roadmap Priorizado

### Sprint 1 - Papel e contingencia

Objetivo: permitir operar o torneio mesmo com indisponibilidade de rede ou
celulares.

Entregas:

1. [x] `DOC-01` Sumula de mesa PDF.
2. [x] `DOC-03` Lista de chamada imprimivel.
3. [x] Teste de desempenho com 801 jogadores.

### Sprint 2 - Publicacao de rodada

Objetivo: reduzir trabalho manual para afixar emparceiramentos.

Entregas:

1. [x] `DOC-02` Folha de mural com QR.
2. [x] `DOC-04` Cartoes de mesa.
3. [x] Integracao com exportar e imprimir em `Rodadas`.

### Sprint 3 - Conferencia esportiva

Objetivo: oferecer a visao padrao para conferencia de resultados.

Entregas:

1. [x] `CLS-01` Tabela cruzada individual.
2. [x] Exportacoes CSV, XLSX, PDF e HTML.
3. [x] Fixture round-robin conhecida.

### Sprint 4 - Painel de alta velocidade

Objetivo: resolver excecoes sem navegar entre telas.

Entregas:

1. [x] `PNL-01` Filtros e busca na Central de pendencias.
2. [x] `PNL-02` Lancamento inline pelo painel.
3. [x] `PNL-04` Preferencias operacionais persistidas.

### Sprint 5 - Equipes e refinamentos

Objetivo: completar operacao presencial avancada.

Entregas:

1. [x] `CLS-02` Tabela cruzada por equipes.
2. [x] `PNL-03` Relogio da rodada.
3. [x] `FED-01` Relatorio de taxas.
4. [x] `FED-02` Pre-visualizacao de atualizacao oficial.

### Sprint 6 - Inscricoes e importacao flexivel

Objetivo: reduzir o trabalho manual de receber inscricoes em formatos diversos e
padronizar a coleta na origem.

Entregas:

1. [x] `REG-01` Gerador de formulario de inscricao padronizado (Google Forms).
2. [x] `REG-02` Assistente de importacao com mapeamento de colunas.
3. [x] Perfis de mapeamento reutilizaveis e testes do servico puro.

### Sprint 7 - Classificacao correta (bloqueantes)

Objetivo: eliminar os casos em que a classificacao publicada pode contradizer
a decisao arbitral ou mudar sem aviso.

Entregas:

1. [x] `TBK-01` Ajustes de pontos aplicados na classificacao.
2. [x] `TBK-02` Fallback do motor de desempates visivel.
3. [x] `ARB-01` Correcao com motivo, desbloqueio pontual e alerta de cascata.
4. [x] Correcoes pontuais de `PAR-04` com risco imediato: troca de cores via
   servico com auditoria e `TEAM_PAIRING_METHODS` duplicado (mais o `pending`
   acumulado e o `KeyError` do sumario de equipes).

**Sprint 7 CONCLUIDA (2026-07-30).**

### Sprint 8 - Conformidade de desempates

Objetivo: alinhar o motor proprio (ou rebaixa-lo formalmente) e dar ao arbitro
controle real sobre os criterios.

Entregas:

1. [x] `TBK-03` Jogos nao disputados conforme FIDE no motor proprio
   (pela segunda saida: motor proprio rebaixado a legado, nao homologavel).
2. [x] `TBK-04` Parametros de criterios editaveis e registro 212 fiel.
3. [x] `TBK-05` Desempates de equipes completos.

**Sprint 8 CONCLUIDA (2026-07-31).**

### Sprint 9 - Fluxo arbitral em salao

Objetivo: cobrir as situacoes reais de arbitragem que hoje exigem contorno.

Entregas:

1. [x] `ARB-02` Resultados arbitrais completos no painel (W.O. inline,
   adiada, W/D/L).
2. [x] `ARB-04` Politica de byes solicitados.
3. [x] `ARB-05` Retirada e reentrada com historico por rodada.
4. [x] `ARB-03` Registro disciplinar de incidentes.

**Sprint 9 CONCLUIDA (2026-07-31).**

### Sprint 10 - Motores de pareamento

Objetivo: tornar RR/KO/Scheveningen confiaveis e fechar as lacunas do caminho
Gacrux.

Entregas:

1. [ ] `PAR-02` Aceleracao e entrada tardia no caminho Gacrux.
2. [ ] `PAR-01` Round-robin com tabela persistida e returno.
3. [ ] `PAR-03` Knockout e Scheveningen maduros.
4. [ ] `PAR-04` Demais dividas tecnicas do nucleo.

### Sprint 11 - Submissao federativa

Objetivo: arquivo enviavel sem retrabalho e normas confiaveis.

Entregas:

1. [ ] `FED-05` Lista FIDE: data de nascimento e robustez do download.
2. [ ] `FED-03` TRF16 de campo completo.
3. [ ] `FED-04` Round-trip TRF fiel.
4. [ ] `FED-06` Normas FIDE corretas e certificados IT.
5. [ ] `FED-07` Rating: K correto, piso e ritmo.

### Sprint 12 - Organizacao do torneio

Objetivo: edital real configuravel sem texto livre nem contorno manual.

Entregas:

1. [ ] `ORG-01` Categorias configuraveis por torneio.
2. [ ] `ORG-02` Premiacao conforme edital.
3. [ ] `ORG-03` Agenda e controle de tempo estruturados.
4. [ ] `ORG-04` Configuracao honesta (flags mortas e bloqueios pos-R1).

## 8. Definicao de Pronto

Uma entrega so esta pronta quando:

- usa servicos de aplicacao, sem escrita critica direta pela UI;
- registra auditoria quando altera estado do torneio;
- gera backup antes de operacao destrutiva ou publicacao critica;
- funciona offline no fluxo principal;
- possui testes automatizados;
- nao quebra torneios individuais existentes;
- considera torneios por equipes quando o requisito se aplicar;
- exibe erro claro para o arbitro;
- passa `pytest`, `ruff`, compilacao e `git diff --check`;
- possui benchmark quando impactar operacao com 100+ jogadores;
- atualiza README ou manual quando alterar o fluxo do operador.

## 9. Matriz de Testes Minima

| Cenario | Quantidade | Objetivo |
|---|---:|---|
| Individual pequeno | 8 jogadores / 3 rodadas | regressao funcional |
| Individual medio | 51 jogadores / 6 rodadas | bye e volume impar |
| Individual grande | 121 jogadores / 7 rodadas | desempenho e impressao |
| Individual alto volume | 801 jogadores / 10 rodadas | limite operacional |
| Equipes | 8 equipes / 4 tabuleiros | lineup, reservas e GP/MP |
| QR | 20 submissoes simultaneas simuladas | fila e aprovacao |
| Pendencias mistas | QR + sync + relogio | filtros e bloqueio |

## 10. Ordem Recomendada para Inicio

Roadmap atual concluido ate `FED-02`, mais os aprofundamentos de 2026-06-02
(`UX-10`, `UX-11`, `DOC-05`, `DOC-06` — secao 4.3; `DOC-07`, `DOC-08`, `UX-12`,
`DOC-09` — secao 4.4; `DOC-10`, `DOC-11`, `UX-13` — secao 4.5).

Motivo:

- o painel cobre papel, publicacao, classificacao, operacao rapida, equipes e
  conferencia de dados oficiais;
- a operacionalizacao foi consolidada no guia imprimivel
  `docs/Manual_Operacional_Arbitragem.pdf`;
- o ensaio automatizado reproduzivel foi registrado em
  `docs/PILOTO_OPERACIONAL_BASELINE.md`;
- a proxima entrega deve partir de um teste piloto presencial e de um novo
  requisito operacional priorizado.

`EPIC E - Inscricoes e importacao flexivel` (`REG-01` formulario padronizado
Google Forms e `REG-02` assistente de importacao com mapeamento de colunas) foi
concluido em 2026-06-03 (secao 5, Sprint 6 da secao 7).

O "novo requisito operacional priorizado" chegou em 2026-07-29 com a auditoria
arbitral completa dos modulos de gestao de torneio (EPICs F a J na secao 5).
Ordem recomendada:

1. **Sprint 7 (bloqueantes)** — `TBK-01`, `TBK-02` e `ARB-01` corrigem casos em
   que a classificacao publicada pode estar errada ou mudar sem rastro; nenhum
   outro trabalho deve passar na frente.
2. **Sprint 8 (desempates)** — conformidade FIDE do motor proprio e controle
   real dos criterios pelo arbitro.
3. **Sprints 9-12** — fluxo de salao, motores secundarios, submissao
   federativa e organizacao, nesta ordem, salvo demanda de torneio real.

O teste piloto presencial continua recomendado e pode rodar em paralelo ao
Sprint 7.
