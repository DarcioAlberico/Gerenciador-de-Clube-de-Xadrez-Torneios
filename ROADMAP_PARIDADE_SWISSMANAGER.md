# Roadmap de Implantação: Paridade com Swiss-Manager

Sequência de execução das lacunas especificadas em
[`ESPEC_PARIDADE_SWISSMANAGER.md`](ESPEC_PARIDADE_SWISSMANAGER.md), derivadas do
[`relatório de comparação`](docs/RELATORIO_SWISSMANAGER_VS_ALBERICUS.md).

As fases são pequenas e incrementais, na linha dos roadmaps já entregues. Cada
fase é independentemente testável e não altera emparceiramento/resultados
existentes.

## Definição de pronto (geral)

Uma fase só está pronta quando:

- tem migração de banco compatível com bancos antigos (backup antes de alterar);
- tem testes automatizados do serviço principal (em `tests/`);
- registra auditoria quando altera estado crítico;
- sequência/relatório vazio reproduz o comportamento atual (regressão);
- tem mensagem clara ao árbitro quando bloqueia/avisa;
- está documentada no README e/ou neste roadmap quando afeta operação;
- passa `.\scripts\check_quality.ps1` (compila, `ruff`, `mypy`, testes).

## Visão de fases

| Fase | Tema | Itens (spec) | Prioridade |
|---|---|---|---|
| A | Desempates configuráveis + completos ✅ | E1, E2 | P0 (feito) |
| B | Variação de Elo FIDE ✅ | E3 | P1 (feito) |
| C | Distribuição de prêmios ✅ | E4 | P1 (feito) |
| D | Estatísticas e fichas FIDE ✅ | E6 | P2 (feito) |
| E | Normas e títulos (assistente) ✅ | E5 | P2 (feito) |
| F | Editor de listas/colunas ✅ | E7 | P3 (feito) |
| G | Scheveningen ✅ | E8 | P3 (feito) |
| H | Importação de Swiss-Manager ✅ | E9 | P3 (feito) |
| I | Mudar tipo / dividir torneio ✅ | E10 | P4 (feito) |

Status: **todas as fases A–I implementadas.** A–C entregaram o maior valor
arbitral; D–E consolidaram o perfil FIDE; F–I foram os refinamentos e
conveniências.

---

## Fase A — Desempates configuráveis e completos (E1 + E2)

**Status: implementada (schema v35).** Maior valor/menor risco: muda como a
classificação é **ordenada e explicada**, sem tocar no pareamento.

### Implementação entregue

- Registro de critérios `PLAYER_TIEBREAKS`/`TEAM_TIEBREAKS` e ordenação dinâmica
  em `src/services/pairing/tiebreaks.py`. Sequência vazia reproduz a ordem
  histórica byte a byte (pontos sempre primário; rating/nome técnicos finais).
- Novos critérios: Buchholz Cut-1/Cut-2 (param `unplayed: real|self`),
  progressivo, progressivo dos adversários, Koya, ARO/ARO cortado, partidas e
  vitórias com pretas, partidas jogadas, confronto direto escalar. Todos puros.
- Persistência: `tournament_settings.tiebreak_sequence` e
  `team_tiebreak_sequence` (migração v35, retrocompatível; coluna vazia mantém o
  comportamento anterior). `PairingService.standings/team_standings` leem e
  aplicam a sequência; `TournamentService._validated_settings` valida/normaliza.
- UI: editor ordenável (subir/descer, adicionar, remover, "Restaurar padrão
  FIDE") na aba de `Config. torneio` para o individual
  (`TiebreakSequenceEditor`). O "Por que esta posição?" segue a ordem
  configurada.
- Testes: regressão (sequência vazia = ordem atual), valor manual de cada
  critério novo, bye/WO no Buchholz, flip de ordem entre sequências,
  persistência/threading ponta a ponta e migração v35. Gate completo
  (compile + ruff + mypy + pytest) verde.
- **Equipes:** o cálculo e a persistência (`team_tiebreak_sequence`) aceitam
  sequência configurável e agora há **editor ordenável dedicado a equipes** na
  seção *Desempates por equipes* de `Config. torneio` (reusa o
  `TiebreakSequenceEditor` com `TEAM_TIEBREAKS`). Os menus *critério
  principal/secundário* permanecem (alimentam o TRF25 reg.192 e o fallback de
  ordenação quando a sequência está vazia).

Detalhamento original abaixo.

### Sprint A1 — Registro de critérios e cálculo dinâmico

1. Criar `TIEBREAK_REGISTRY` em `src/services/pairing/tiebreaks.py` com os
   critérios atuais (points, buchholz, buchholz_median, sonneborn_berger,
   direct_encounter, wins, performance), cada um com `code`, `label`,
   `compute`, `explain`.
2. Refatorar `order_player_standings(stats, sequence=None)` para montar a chave
   de ordenação a partir do registro quando `sequence` vier; manter default.
3. Garantir que `calculate_player_standings` continue calculando os campos
   atuais (sem regressão) e que `player_tiebreak_components` use o registro.
4. **Testes**: rodar as fixtures existentes com `sequence=None` e confirmar
   classificação idêntica byte a byte (regressão).

### Sprint A2 — Novos critérios

1. Implementar no registro: `buchholz_cut1`, `buchholz_cut2`, `aro`, `aroc`,
   `cumulative`, `cumulative_opp`, `koya`, `black_games`, `black_wins`,
   `games_played`.
2. Implementar o parâmetro `unplayed` (virtual/real/self) para Buchholz e
   ajustar partidas não jogadas (bye/WO/ausência) conforme FIDE (default
   "virtual opponent").
3. **Testes**: uma fixture por critério com resultado manual documentado no
   teste; caso dedicado de bye+WO no Buchholz.

### Sprint A3 — Persistência e UI

1. Migração `schema_version++`: `tournament_settings.tiebreak_sequence TEXT
   DEFAULT ''` e `team_tiebreak_sequence TEXT DEFAULT ''`.
2. `TournamentService` lê/grava a sequência (JSON) e valida (points primeiro,
   sem duplicado).
3. Aba **Desempates** em `Config. torneio` (`tournaments.py`): lista ordenável
   (subir/descer), campos de corte para Buchholz, botão "Restaurar padrão FIDE".
4. Classificação e relatório de desempate passam a respeitar a ordem configurada.
5. **Testes**: dois torneios com sequências distintas → ordens distintas;
   sequência vazia → comportamento atual; migração de banco antigo.

**Pronto quando**: árbitro escolhe os desempates pela UI, a classificação
reflete a escolha, o "Por que esta posição?" explica na ordem certa e bancos
antigos não mudam de resultado.

---

## Fase B — Variação de Elo FIDE (E3)

**Status: implementada (schema v36).**

### Implementação entregue

- Núcleo puro em `src/services/fide_rating.py`: tabela oficial de expectativa
  FIDE + **regra dos 400**, `fide_k_factor` (10/20/40, override por jogador,
  sub-18 < 2300), performance via tabela `p→dp`, e `build_fide_report_rows`
  (Ro, K, n, W, We, ΔElo, Rc, Rp por jogador). Conta só partidas jogadas no
  tabuleiro (exclui bye/WO/forfait) e contra adversários **com rating**;
  jogador sem rating recebe apenas Rp.
- Persistência: tabela `fide_rating_reports` (idempotente por torneio+base) e
  coluna opcional `players.k_factor` (migração v36, retrocompatível, sem alterar
  classificações). `FideRatingService` (compute/save/get) + métodos de banco.
- UI/exportação: opção **`Rating FIDE`** na tela `Relatorios`, exportável em
  CSV/XLSX/PDF (colunas Ro, K, n, Pts, We, ΔElo, Rc, Rp, >400), com aviso de
  estimativa e snapshot persistido para reimpressão.
- Testes: expectativa + regra dos 400, fator K, ΔElo manual (2–3 jogadores),
  adversário sem rating, exclusão de bye/WO, idempotência da persistência,
  exportação e migração v36. Gate completo verde (ruff + mypy + pytest).
- **Decisão de escopo:** a coluna `tournament_settings.fide_rating_evaluation`
  prevista na spec foi dispensada — a base (FIDE/CBX) é escolhida no momento do
  relatório (`rating_type`), evitando coluna sem leitor. O esqueleto já suporta
  CBX além de FIDE.

Detalhamento original abaixo.

### Sprint B1 — Núcleo de cálculo

1. Novo módulo `src/services/fide_rating_service.py` (funções puras de
   expectativa Elo: tabela `p(d)`, `expected_score` com regra dos 400).
2. `k_factor(player)` com regras 40/20/10 e override `players.k_factor`.
3. `compute_tournament_report(tournament_id, rating_type)` somando We/W/ΔElo/Rc/Rp
   por jogador, ignorando adversário sem rating e partidas não jogadas.
4. **Testes**: 2–3 jogadores com ratings conhecidos batendo ΔElo manual,
   incluindo regra dos 400 e sem-rating.

### Sprint B2 — Persistência, UI e exportação

1. Migração: tabela `fide_rating_reports`, coluna `players.k_factor`,
   `tournament_settings.fide_rating_evaluation`.
2. Ação "Relatório de rating FIDE" em `Classificação`/`Relatórios`, idempotente.
3. Exportação CSV/XLSX/PDF (colunas Ro, K, n, W, We, ΔElo, Rc, Rp) via
   `export_service`.
4. Texto fixo de "estimativa de apoio, não homologação".
5. **Testes**: recálculo não duplica; exportação com cabeçalho correto.

**Pronto quando**: o árbitro gera um relatório de variação de Elo conferível e
exportável, com aviso de conformidade.

---

## Fase C — Distribuição de prêmios (E4)

**Status: implementada (schema v37).**

### Implementação entregue

- Motor puro em `src/services/prizes.py`: `allocate_prizes(standings, prizes,
  policy, tax_percent)` com **divisão igual entre empatados por pontos**,
  políticas `best_only` / `cumulative` / `hort`, prêmios geral + categoria
  alocados automaticamente, dedução de imposto e prêmios `special`/`board`
  listados como manuais.
- Persistência: tabela `tournament_prizes` (CRUD via `replace_tournament_prizes`)
  + `tournament_settings.prize_policy` e `prize_tax_percent` (migração v37,
  retrocompatível). `PrizeService` (list/replace/allocate) em
  `src/services/prize_service.py`, wired em `app.py`/`support.py`/`core/services.py`.
- UI: seção **Premiação** em `Config. torneio` com política, imposto e o editor
  de prêmios em linhas (`PrizeEditor`, com botão próprio "Salvar premios").
- Exportação: opção **`Premiacao`** na tela `Relatorios` →
  `export_prize_report` (CSV/XLSX/PDF) com resumo, premiação por jogador e
  prêmios manuais.
- Testes: empate dividido, `best_only` sem dupla contagem, `cumulative`,
  `hort`, imposto, prêmios manuais, persistência+validação do serviço,
  exportação e migração v37. Gate completo verde (ruff + mypy + pytest).
- **Decisões de escopo:** o `prize_policy` é **global** por torneio (a coluna
  `cumulative` por prêmio da spec foi dispensada para evitar duas fontes de
  verdade); `currency` foi omitida (real único, formatado). O Hort usa a
  interpretação `max(geral, (geral+categoria)/2)`, documentada no módulo. A
  divisão de empates segue a regra usual de **prêmios em dinheiro divididos por
  pontuação** (desempates decidem troféus, não o rateio do dinheiro). Prêmios de
  tabuleiro (`board`, equipes) e especiais ficam como manuais nesta fase.

Detalhamento original abaixo.

### Sprint C1 — Modelo e motor

1. Migração: tabela `tournament_prizes`,
   `tournament_settings.prize_policy` e `prize_tax_percent`.
2. `src/services/prize_service.py`:
   - `allocate(tournament_id)` com políticas `best_only`, `cumulative`, `hort`;
   - divisão igualitária entre empatados;
   - dedução de imposto.
3. Usa a classificação final (com desempates da Fase A) para posição/categoria.
4. **Testes**: total distribuído = soma dos prêmios − imposto; sem dupla
   contagem em `best_only`; casos Hort e cumulative manuais.

### Sprint C2 — UI e saída

1. Aba **Prêmios** em `Config. torneio`: CRUD (geral/categoria/tabuleiro/especial),
   faixas de colocação, valores, política, imposto.
2. Lista "Premiação" exportável (CSV/XLSX/PDF) e opção de incluir no site
   HTML/portal.
3. **Testes**: CRUD persiste; lista de premiação confere com a alocação.

**Pronto quando**: árbitro cadastra prêmios e gera a lista de premiação correta
para conferência e publicação.

---

## Fase D — Estatísticas e fichas FIDE (E6)

**Status: implementada (sem mudança de schema).**

### Implementação entregue

- `export_service.py`: `export_federation_statistics` (jogadores, % e pontos por
  federação), `export_game_statistics` (vitórias de brancas/empates/pretas, WO e
  byes, com %) e `export_player_cards` (resumo por jogador com V/E/D, cores e
  performance + resultados rodada a rodada). Tudo derivado da classificação e
  dos pareamentos, sem nova tabela.
- As fichas usam **seções planas** (resumo + rodada a rodada) em vez de uma
  seção por jogador, evitando explosão de abas no XLSX em torneios grandes.
- UI: opções `Estatistica de federacoes`, `Estatistica de partidas` e `Fichas
  individuais` no hub de `Relatorios`, exportáveis em CSV/XLSX/PDF.
- Restrito a torneios individuais (mensagem clara para equipes).
- Testes: contagem de resultados, agrupamento por federação, resumo/rodadas das
  fichas, exportação e bloqueio para equipes. Gate completo verde.

Detalhamento original abaixo.

1. `report_engine.py`: relatórios de **estatística de federações** e de
   **estatística de partidas** (brancas/empates/pretas/WO/bye).
2. **Fichas individuais** (uma por jogador) com adversários, cores, resultados,
   Rp; layout próximo ao FIDE.
3. Exportação reaproveitando `export_service`. Sem mudança de schema.
4. **Testes**: contagens batem com fixture de 8 jogadores.

**Pronto quando**: as três saídas são geradas e conferem com a contagem manual.

---

## Fase E — Normas e títulos FIDE — assistente (E5)

**Status: implementada (sem mudança de schema).**

### Implementação entregue

- Motor puro `src/services/fide_norms.py`: `TITLE_NORM_REQUIREMENTS` (GM/IM e,
  para jogadoras, WGM/WIM, com limiares parametrizados) + `build_norm_report`
  com indicadores (performance, partidas válidas, federações dos adversários,
  adversários titulados ≈ 1/3, média de rating) e **veredito por título** com a
  lista do que falta. Reaproveita `fide_performance`/`player_rating_for_type`.
- `NormAssistantService` (`evaluate_tournament` / `evaluate`) em
  `rating_service.py`, wired em app/support/core.services.
- UI/export: opção **`Normas FIDE`** no hub de `Relatorios` →
  `export_norm_report` (CSV/XLSX/PDF) com aviso de estimativa, resumo por
  jogador e detalhe por título (pendências).
- Restrito a individual. Testes: veredito atende/não atende, candidato a GM
  ponta a ponta, serviço+export e bloqueio para equipes. Gate verde.
- **Escopo:** é **assistente informativo**, não homologação (texto explícito).
- **Formulário de árbitro (IA/FA):** `export_arbiter_norm_report` reúne os dados
  do torneio (local, datas, ritmo, federação, FIDE Event-ID, jogadores/rated) e
  os árbitros designados (`list_tournament_referees`, com fallback para
  `chief_arbiter`/`arbiters` da configuração), com colunas de função, FIDE ID,
  norma e assinatura, como base para o formulário oficial FIDE. Opção
  `Formulario de arbitro (IA/FA)` no hub de `Relatorios`; teste de geração.

Detalhamento original abaixo.

1. Tabela de limiares por título em `constants.py` (parametrizável).
2. `src/services/norm_assistant_service.py`: `evaluate(tournament_id, player_id)`
   retorna Rp, rating médio dos adversários, nº de partidas, federações
   distintas, titulados enfrentados e **veredito textual** por título.
3. UI: "Relatório de norma (estimativa)" na ficha do jogador; formulário
   IA/FA pré-preenchido (XLSX) usando os modelos do SM como referência de layout.
4. Texto explícito de "apoio, não certificação oficial".
5. **Testes**: jogador que atende GM → "atende" com números certos; quem não
   atende → lista o que falta.

**Pronto quando**: o assistente informa norma de forma transparente, sempre como
estimativa.

---

## Fase F — Editor de listas/colunas (E7)

**Status: implementada (schema v38).**

### Implementação entregue

- Módulo puro `src/services/list_layouts.py`: registro `STANDINGS_COLUMNS`
  (17 colunas), `DEFAULT_STANDINGS_COLUMNS` (= comportamento histórico) e
  `normalize_columns`/`resolve_columns` (layout vazio → padrão).
- Persistência: tabela `report_layouts` (por torneio, `report_key`) com
  migração v38; `db.get_report_layout_columns`/`save_report_layout`.
  `ListLayoutService` (get/save/reset com validação) wired em
  app/support/core.services.
- `ExportService._standings_section` passou a ser **dirigido por layout**: usa as
  colunas salvas (ou as padrão), aplicando a CSV/XLSX/PDF da classificação.
- UI: editor `ColumnLayoutEditor` (mostrar/ocultar + ordem, com "Restaurar
  padrão") na seção **Colunas da classificacao** de `Config. torneio`, com botão
  próprio "Salvar colunas".
- Testes: colunas padrão inalteradas (regressão), layout altera as colunas,
  normalização/validação, reset e migração v38. Gate verde.
- **Larguras de coluna:** o layout guarda largura por coluna (JSON
  `{key, width}`, retrocompatível); o `ColumnLayoutEditor` tem campo de largura
  por coluna e o export XLSX aplica as larguras explícitas (vazio = automático).
  Testes cobrem persistência das larguras e aplicação no XLSX.
- **Escopo:** cobre a **classificação** (lista mais usada); o registro é
  extensível a outras listas. A geração em lote multi-destino fica como
  incremento futuro.

Detalhamento original abaixo.

1. Modelo `report_layouts` (JSON por tipo de lista; global ou por torneio).
2. Camada de layout sobre `export_service` (seleção/ordem/largura de colunas,
   bordas, quebra de página, dados do torneio no topo).
3. UI: editor simples de colunas (mostrar/ocultar, ordem, largura %).
4. Opcional: geração em lote multi-destino (impressão + HTML + texto).
5. **Testes**: dois layouts → saídas distintas; layout vazio → saída atual.

**Pronto quando**: o usuário customiza colunas das listas sem alterar o código.

---

## Fase G — Sistema Scheveningen (E8)

**Status: implementada.** `scheveningen_pairings` puro em `fide_dutch.py` (grupos
= metades por ranking inicial; exige número par; N rodadas com todos os
cruzamentos A×B e cores alternadas), integrado em `generate_next_round` quando
`pairing_method == "scheveningen"`, opção adicionada a `PAIRING_METHODS`
(selecionável em `Config. torneio`). **Grupos manuais** (campo
`players.scheveningen_group` A/B, migração v40, atribuível na tela de jogadores)
têm prioridade; sem atribuição, caem nas metades por ranking. Testes cobrem
todos os cruzamentos A×B, grupos manuais (que não são as metades), exigência de
grupos do mesmo tamanho e rejeição de campo ímpar.

Detalhamento original abaixo.

1. `scheveningen_pairings(group_a, group_b, rounds)` em `fide_dutch.py`
   (individual) e equivalente em `team_swiss.py`.
2. `tournament_settings.pairing_method` aceita `scheveningen`.
3. UI: escolher os dois grupos na configuração.
4. **Testes**: grade 4×4 → 4 rodadas com todos os cruzamentos A×B e cores
   equilibradas.

**Pronto quando**: um torneio Scheveningen roda do início ao fim.

---

## Fase H — Importação de Swiss-Manager (E9)

**Status: implementada (parcial, documentada).** Parser puro `trf_import.py` do
formato FIDE/Krause TRF16 (cabeçalho + linhas 001 por colunas fixas, o mesmo
layout do `TRF16Exporter` — garante round-trip e lê TRFs do Swiss-Manager).
`ImportService.import_trf` cria um **novo torneio + jogadores** (nome, rating,
federação, FIDE ID, nascimento, título, sexo) **e reconstrói as rodadas jogadas**
(`build_trf_rounds`: mapeia start_rank→player_id, deduplica jogos, decodifica os
códigos TRF 1/0/=/+/-/U/H/Z, cria as rodadas fechadas com `create_round_with_pairings`
+ `close_round`). Botão `Importar TRF (Swiss-Manager)` na tela de torneios.
Testes: round-trip de jogadores+cabeçalho, reconstrução de rodada com
classificação idêntica à original, e rejeição de arquivo sem jogadores. O
torneio importado fica pronto para classificação/tabela cruzada/exportações.

Detalhamento original abaixo.

1. Parser do export **XML** do SM (jogadores, equipes, escalações).
2. Reuso do leitor **TRF16** existente para importar resultados por rodada de um
   TRF gerado pelo SM.
3. Estudo (documentado) sobre ler `.TUN` direto — provável manter só XML/TRF.
4. **Testes**: importar XML/TRF de exemplo recria jogadores e rodadas conferíveis.

**Pronto quando**: dá para migrar um torneio do SM via XML/TRF.

---

## Fase I — Mudar tipo / dividir torneio (E10)

**Status: implementada (schema v39).** `TournamentService.change_tournament_type`
troca o método de pareamento (via `db.update_pairing_method`), **bloqueado após a
primeira rodada**; o mesmo bloqueio foi adicionado ao `save_profile` (só dispara
quando o método é explicitamente alterado com rodadas existentes).
`split_tournament` reparte os jogadores em N torneios-filho por ranking inicial
(A = mais fortes), vinculados por `tournaments.parent_tournament_id` (migração
v39); bloqueado se já houver rodada e exige jogadores suficientes. UI: botão
`Dividir` na tela de torneios. Testes cobrem bloqueio pós-R1, partição por
ranking, vínculo ao pai, estados inválidos e migração v39.

Detalhamento original abaixo.

1. "Mudar tipo" (RR ⇄ Suíço) antes da R1: troca `pairing_method`, regenera
   ranking inicial, **bloqueado após a R1** com mensagem clara.
2. "Dividir torneio": `tournaments.parent_tournament_id` opcional, grupos
   A/B/C como torneios vinculados, classificação consolidável.
3. **Testes**: conversão antes da R1 preserva inscritos; bloqueio após R1.

**Pronto quando**: as duas operações são seguras e auditadas.

---

## Itens fora do roadmap (registro)

Mantidos fora por decisão de produto, com justificativa em
[`ESPEC_PARIDADE_SWISSMANAGER.md`](ESPEC_PARIDADE_SWISSMANAGER.md):

- Integração **Chess-Results.com** (upload/online/registro) — offline-first;
  ponte é o TRF16.
- **Listas de rating estrangeiras** — foco FIDE/CBX/LBX (Brasil).
- **Álbuns de fotos (FTP)**, **salvar em Access**, **listagens de Olimpíada** —
  nicho.

## Sequência recomendada de entrega

1. **Fase A** (desempates) — destrava conformidade de classificação e é base de C.
2. **Fase B** (Elo FIDE) — valor alto para árbitros e jogadores.
3. **Fase C** (prêmios) — fecha o ciclo "fim de torneio".
4. **Fases D/E** — perfil FIDE (estatísticas, fichas, normas).
5. **Fases F–I** — refinamentos e conveniências, sob demanda.
