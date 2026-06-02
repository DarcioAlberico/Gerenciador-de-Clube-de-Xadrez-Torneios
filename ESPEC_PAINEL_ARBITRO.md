# Spec e Roadmap - Painel do Arbitro

> Documento executivo para evoluir o fluxo operacional de arbitragem do
> Albericus em torneios presenciais com mais de 100 jogadores.
>
> Revisao: 2026-05-31.

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
- TRF25 mantido como formato em evolucao.

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

## 6. Fora de Escopo

Nao iniciar sem requisito externo concreto:

- aceleracao de Baku enquanto a formula aplicavel nao estiver publicada;
- submissao automatica para federacao sem API publica;
- decisao automatica de WO ou queda de seta;
- plugin de hardware sem equipamento alvo;
- PGN com lances sem captura de lances;
- app Android/iOS nativo.

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
