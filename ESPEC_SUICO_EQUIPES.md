# Especificação — Suíço por equipes

> **Status:** proposta **v1** (2026-11-26). Nasce do RGS-30 (`ESPEC_REVISAO_GERAL_SUICO.md`, seção 6), que pediu spec própria para equipes.
> **Roadmap:** Fase 4 de `ROADMAP_REVISAO_GERAL_SUICO.md` (RGS-30). Nada aqui está implementado.
> **Base analisada:** árvore de trabalho da branch `fix/rgs-fase0-exe` em 2026-11-26. Os números de linha de `pairing_service.py` podem andar: o arquivo está sendo editado por outras frentes; o nome do método vale mais que a linha.

## 0. Por que este documento existe

A revisão geral do Suíço olhou o caminho individual. O caminho de equipes tem motor próprio (`src/services/pairing/team_swiss.py`, chamado por `PairingService._generate_next_team_round`) e três defeitos que a revisão anotou sem detalhar:

1. a **semente** da equipe é recalculada a cada rodada;
2. um **titular ausente** no tabuleiro 1 (ou em qualquer tabuleiro) derruba a geração da rodada **do torneio inteiro**;
3. o confronto perdido por **W.O.** conta como confronto já jogado (e como cor e flutuação).

Mesma regra da casa da revisão geral: **nada some calado, nada fica meio gravado, e o que funciona não se mexe.** Antes de tocar o motor de equipes: teste de caracterização do caminho feliz (equipes completas, todos os confrontos jogados).

**Marcação de evidência** (a mesma da revisão geral):
- **[E]** executado e visto falhar (aqui: as funções puras chamadas direto, em 2026-11-26);
- **[L]** lido no código, caminho completo;
- **[H]** hipótese ou regra FIDE ainda não conferida no texto literal.

**Referência FIDE.** No Handbook vigente (desde 01/02/2026): C.04.1 (regras básicas), C.04.2 (regras gerais de condução, inclusive números de emparceiramento) e **C.04.6 — Swiss Team Pairing System (TPS)**. Onde este documento cita o C.04.6 sem marcação, a frase foi conferida em trecho publicado; o resto está marcado **[H]** e precisa de leitura do texto literal antes de virar teste.

---

## 1. Achados

### EQ-01 · A semente da equipe é recalculada a cada rodada **[E]** — P1

- **Evidência:**
  - `team_swiss.py:18-46` (`team_starter_roster`): a semente é `round(soma dos ratings dos titulares ATIVOS / boards_count)` (linha 45), calculada na hora.
  - `pairing_service.py` `_team_next_round_plan` (≈ l. 1895) chama `_team_starter_rosters` (≈ l. 1971-1984) **em toda rodada**, lendo `list_team_players(active_only=True)` e `players.rating` do momento.
  - A semente entra na ordem de pareamento: `constraints.py:184-196` (`team_pairing_order_key`, terceiro critério), `team_swiss.py:308-311` (ordem da R1) e `team_swiss.py:253-256` (o todos-contra-todos por equipes refaz o círculo a cada rodada — o próprio docstring, l. 242-246, admite o defeito).
  - Não existe onde guardar a semente: a tabela `teams` (`database_schema.py:433-445`) não tem número de emparceiramento nem rating de semente.
  - O TRF25 usa **outra** conta para o mesmo número: `trf25.py:662-682` (`_prepare_teams`) faz a média só dos titulares com rating, inclui inativos e usa o rating de exportação (`_trf_rating`). O TPN do arquivo pode não ser a ordem que o motor usou.
- **Execução:** dois titulares 2000/1900 → semente 1950; o rating do tabuleiro 1 sobe para 2100 (atualização de lista no meio do evento) → semente 2000. Com um titular desistente, a semente nem sai (ver EQ-02).
- **Causa-raiz:** a semente é derivada, não é dado do torneio. Qualquer mudança de rating, de status ou de escalação reordena as equipes.
- **Regra:** o C.04.6 manda o regulamento da competição dizer como cada equipe recebe o seu TPN (senão, decide o árbitro-chefe), e o C.04.2 proíbe mudar número de emparceiramento depois que a 4ª rodada foi pareada (salvo correção). O TPN é atribuído **antes** da R1 e fica.
- **Requisito:**
  1. Ao gerar a R1, gravar por equipe o **TPN** e o **rating de semente** usado (coluna ou tabela própria, com migração por versão — RGS-29).
  2. Da R2 em diante, a ordem usa o TPN gravado; nenhuma leitura de rating ou de escalação muda a ordem.
  3. Uma só função de semente (`team_seed(...)`), usada pela geração, pelo todos-contra-todos e pelo `_prepare_teams` do TRF25. A fórmula padrão continua a de hoje (média dos titulares por tabuleiro); outra fórmula, se vier, é configuração do torneio e não muda depois da R1.
  4. Equipe inscrita depois da R1 recebe TPN pela regra de entrada tardia (C.04.2), sem renumerar as outras depois da R4.
  5. Corrigir o TPN depois da R1 é ação de árbitro, com motivo e auditoria (mesmo modelo de correção do RGS).
- **Aceite:**
  - torneio de 6 equipes, R1 gerada; subir o rating do tabuleiro 1 da 6ª equipe para o maior do evento; a R2 sai **igual** à de um torneio idêntico sem a mudança de rating;
  - o TPN do registro 310/320 do TRF25 é o mesmo número que o motor usou (teste que compara os dois);
  - o todos-contra-todos por equipes não muda os confrontos futuros quando uma equipe fica inativa (o calendário é sorteado e guardado, como o individual desde a PAR-01).

### EQ-02 · Um titular ausente derruba a geração do torneio inteiro **[E]** — P0

- **Evidência:**
  - `team_swiss.py:31-34`: titular com `player_status != "active"` é ignorado;
  - `team_swiss.py:40-43`: falta de titular ativo em **qualquer** tabuleiro exigido levanta `AppError("Equipe X sem titular ativo no tabuleiro N.")`;
  - `pairing_service.py` `_team_next_round_plan` (≈ l. 1895): a checagem roda para **todas** as equipes antes de parear; uma equipe incompleta impede a rodada de todas as outras;
  - reserva ativa não é promovida: a escalação nasce do cadastro fixo de titulares (`team_match_payload`, `team_swiss.py:163-193`) e só depois vira escalação editável (`create_team_lineups_from_round`, `database_tournament_core.py:2167`).
- **Execução:** tabuleiro 1 desistente, tabuleiro 2 ativo, uma reserva ativa → `AppError: Equipe X sem titular ativo no tabuleiro 1.` A reserva não foi usada.
- **Causa-raiz:** o pareamento de **equipes** depende da escalação de **jogadores**. No Suíço por equipes a ordem de equipes sai de pontos e TPN; quem senta em cada tabuleiro é escalação, decidida depois, pelo capitão, a partir da ordem de tabuleiros declarada.
- **Regra [H]:** a prática dos regulamentos FIDE de equipes (Olimpíada e campeonatos por equipes) é: a ordem de tabuleiros é declarada antes do evento; a cada rodada o capitão escala N jogadores **respeitando essa ordem** (reservas sobem); faltando gente, os tabuleiros vazios são os de baixo e saem por W.O. Conferir no regulamento da competição; o C.04.6 em si não trata da escalação.
- **Requisito:**
  1. A geração de rodada por equipes **não** depende de escalação completa. Equipe com menos jogadores ativos que tabuleiros continua sendo pareada.
  2. A escalação proposta segue a ordem declarada: titulares ativos e, no lugar do ausente, a reserva ativa seguinte, sem inverter a ordem relativa.
  3. Se não houver jogadores para todos os tabuleiros, os tabuleiros vazios ficam **no fim** e já nascem marcados como W.O. daquele tabuleiro (`-/+` ou `+/-` conforme a cor), visíveis ao árbitro antes de fechar.
  4. Equipe sem **nenhum** jogador ativo não é pareada sem confirmação: o árbitro escolhe entre retirar a equipe da rodada (bye Z solicitado) ou registrar W.O. do confronto inteiro.
  5. O aviso de escalação incompleta aparece na prévia da rodada e no painel do árbitro (ação `ACTION_LINEUPS`), nunca como erro que impede as outras equipes.
- **Aceite:**
  - 4 equipes, o tabuleiro 1 da equipe C desiste: a rodada é gerada; o tabuleiro 1 da C é a reserva ativa, e a ordem dos demais não muda;
  - mesma situação sem reserva: a rodada é gerada, o último tabuleiro da C sai como W.O., e a prévia lista o aviso;
  - nenhuma linha nova em `team_matches` quando a geração é cancelada na confirmação do item 4.

### EQ-03 · Confronto perdido por W.O. conta como confronto jogado **[E]** — P1

- **Evidência:**
  - `histories.py:10-16` (`team_played_pairs`): todo confronto que não é bye entra no conjunto de pares já jogados — não há olhar para os resultados dos tabuleiros;
  - `histories.py:27-40` (`team_color_histories`): o W.O. conta como cor jogada;
  - `histories.py:43-81` (`team_float_histories`): o W.O. conta como flutuação normal dos dois lados;
  - consumidos em `pairing_service.py` `_team_played_pairs`/`_team_color_histories` (≈ l. 3649-3659) e em `_swiss_team_matches` (≈ l. 1996-2007);
  - o caminho **individual** já trata o W.O. como partida não jogada para as três coisas: `histories.py:84-99` (`played_pairs`), `:122-144` (`color_histories`), `:147-225` (`float_histories`);
  - a detecção de "confronto inteiro por W.O." já existe, conservadora, no exportador: `trf25.py:988-1000` (`_team_match_forfeit_802`: todos os tabuleiros com resultado de forfeit).
- **Execução:** um confronto 10×20 da R1 com resultado de match `1-0` → `team_played_pairs = {10, 20}`, cores `W`/`B`, flutuação `=` para os dois — idêntico a um confronto jogado. Como `team_match_summary` (`team_swiss.py:102-160`) converte `+/-` em pontos comuns, um confronto 100% W.O. vira um `1-0` indistinguível.
- **Causa-raiz:** o histórico de equipes olha só a linha de `team_matches`; a informação de W.O. está nos tabuleiros e não sobe.
- **Regra:** glossário da revisão geral (seção 7): **W.O. não conta como confronto nem como cor**. Para equipes, a unidade é o **confronto**: só o confronto **inteiro** não jogado (todos os tabuleiros por W.O., inclusive duplo) deixa de contar. W.O. parcial (alguns tabuleiros) é confronto jogado. **[H]** conferir no texto literal do C.04.6 se o TPS diz o mesmo sobre repetição de adversário; se divergir, vale o C.04.6 e este item se ajusta.
- **Requisito:**
  1. Uma função pura `team_match_unplayed(match, boards) -> bool` (mesma regra do `_team_match_forfeit_802`), usada pelo histórico **e** pelo exportador — uma regra, um lugar.
  2. Confronto inteiro por W.O.: fora de `team_played_pairs`, fora do histórico de cor; na flutuação, quem pontuou sem jogar conta como *downfloat* e o outro lado não flutua (como no individual, PAR-04).
  3. Os pontos de match e de jogo do W.O. continuam valendo na classificação (nada muda em `team_match_summary`).
- **Aceite:**
  - R1: A vence B por W.O. em todos os tabuleiros; R2 com A e B sozinhos no mesmo grupo de pontuação e sem outro par possível → A×B é pareado de novo;
  - mesma R1 com um só tabuleiro jogado → A×B **não** se repete;
  - a cor de A e B na R2 não leva em conta a R1 por W.O.

### EQ-04 · Vencedor por W.O. ainda pode receber o bye do pareamento **[L]** — P2

- **Evidência:** `histories.py:19-24` (`team_bye_ids`) só registra quem teve bye; `choose_team_bye` (`constraints.py`) não sabe de quem venceu por W.O.
- **Regra:** C.04.6 — equipe que já recebeu o bye alocado pelo pareamento, ou que **venceu um confronto por W.O.**, não recebe o bye alocado.
- **Requisito:** `team_bye_ids` passa a incluir o vencedor de confronto inteiro por W.O. (mesma função do EQ-03.1). O mesmo vale para o bye solicitado F (ponto cheio), na redação vigente.
- **Aceite:** 5 equipes; R1 com A vencendo por W.O.; R2 com A sozinha no último grupo → o bye vai para outra equipe.

---

## 2. O que está sólido e não deve mudar

Caracterizar antes de mexer:

1. Pontuação do confronto (`team_match_summary`): cores invertidas nos tabuleiros pares, match points configuráveis, erro claro para tabuleiro em branco.
2. Bye de equipe por tipo F/H/Z/BYE (`team_bye_points`, `team_bye_payload`) e as letras no 802.
3. Byes solicitados recusados no todos-contra-todos por equipes (o calendário é fixo).
4. Penalidade de flutuação repetida (PAR-04) e proibições de pareamento (registro 260).
5. Os indicadores de forfeit do 330/802 continuam conservadores (só W.O. do confronto inteiro).

## 3. Fora de escopo

- Motor FIDE oficial para equipes (Gacrux/bbp não pareiam equipes hoje; o motor é o próprio).
- Desempates de equipes (ficam com a frente de desempate).
- Aceleração em torneio por equipes: depende da aceleração de Baku individual (ver `ROADMAP_ARBITRAGEM_XADREZ.md`, correção do RGS-30). **Feita depois, como EQ-07 (ver §6).**

## 4. Ordem sugerida

1. **EQ-02** primeiro: é o único que **impede** o torneio.
2. **EQ-03** e **EQ-04** juntos: a mesma função `team_match_unplayed`.
3. **EQ-01** por último: precisa de migração (RGS-29) e muda a ordem das equipes da R2 em diante. Torneio em andamento: gravar o TPN a partir da ordem da R1 já gerada, não recalcular.

## 5. Definição de pronto

A mesma da revisão geral (seção 10): teste que falha pelo motivo certo antes da mudança; correção na causa; suíte completa verde (com UI) e `-m gacrux`; changelog com o ID (`EQ-NN`, referência RGS-30).

---

## 6. Andamento (2026-11-26)

Testes novos em `tests/test_eq_suico_equipes.py`. Cada um foi escrito antes da mudança e visto falhar pelo motivo esperado (vermelho), depois passou (verde).

### §2 — caracterização

- `CaminhoFelizTest`: 6 equipes, 3 rodadas completas. Os confrontos foram fixados com o código de antes das mudanças e não mudaram com elas.
- Os itens 1 a 5 da §2 já tinham teste: `test_pairing_pure`, `test_core_par04`, `test_core_teams` (bye por tipo, 802/240/320) e `test_core_federation` (330/802). Todos seguem verdes.

### EQ-02 — feito

- **Vermelho:** `AppError: Equipe Equipe 3 sem titular ativo no tabuleiro 1.` nos três testes de serviço. Nos testes puros faltavam `team_lineup` e `team_seed`.
- **Causa e correção:** `team_starter_roster` misturava duas coisas, a escalação e a semente, e levantava erro. Agora são duas funções puras em `team_swiss.py`:
  - `team_lineup`: o titular presente senta no seu tabuleiro. No lugar do ausente entra a reserva presente seguinte, na ordem do cadastro. Sem reserva, os de baixo sobem e as vagas ficam no fim.
  - `team_seed`: a semente.
- O tabuleiro vazio já nasce como W.O. (`team_match_payload`, que devolve `0F-1F`, `1F-0F` ou `0F-0F`).
- Equipe ativa sem nenhum jogador: `TeamWithoutPlayersError`, levantado antes de qualquer gravação. `generate_next_round(..., forfeit_empty_teams=True)` confirma o W.O. do confronto inteiro.
- O aviso de escalação incompleta aparece:
  - na prévia, como alerta "Escalação incompleta" no confronto e em `warnings` no topo;
  - no checklist do árbitro (ação `lineups`), pelo novo aviso `lineup_incomplete` em `TeamService.validate_roster_policy`.
- **TRF:** o jogador que venceu um tabuleiro vazio sai como `0000 - F`, e a vitória conta nos pontos da linha 001 (`export_federation._trf_empty_seat_pairing`). Antes a mesa era descartada e a equipe perdia um ponto de jogo no desempate do Gacrux.
- **Testes:** `EscalacaoPuraTest`, `EscalacaoServicoTest`, `TrfDoDesempateDeEquipesTest::test_ponto_do_tabuleiro_vazio_chega_ao_jogador_no_trf` e, com `-m gacrux`, `test_gacrux_conta_o_ponto_do_tabuleiro_vazio`.

### EQ-03 e EQ-04 — feitos

- **Vermelho:** `team_played_pairs` continha {A, B} depois de um W.O. inteiro, e `team_match_unplayed` não existia.
- **Correção:** a função pura `histories.team_match_unplayed(match, boards)` decide, num lugar só, se um confronto foi jogado. É não jogado o confronto em que todos os tabuleiros terminaram por W.O., inclusive a dupla ausência. Ela é usada:
  - pelos quatro históricos (`team_played_pairs`, `team_color_histories`, `team_float_histories` e `team_bye_ids`), que recebem `boards_by_match`;
  - pelo TRF25 (`_forfeit_records_330` e `_team_match_forfeit_802`). A constante `_FORFEIT_RESULTS`, que duplicava a regra, saiu.
- No confronto inteiro por W.O.:
  - quem pontuou recebe *downfloat* e o outro lado não flutua;
  - o vencedor entra em `team_bye_ids` e não recebe o bye alocado (EQ-04).
- O serviço lê os tabuleiros uma vez (`PairingService._team_closed_history`). `team_match_summary` não mudou: o W.O. continua valendo pontos.
- **Testes:** `ConfrontoNaoJogadoPuroTest` (inclui o aceite do EQ-04 com 5 equipes) e `ConfrontoNaoJogadoServicoTest`:
  - W.O. inteiro: sem alerta de repetição na R2 e sem cor da R1;
  - W.O. parcial: o confronto conta como jogado.

### EQ-01 — feito, com migração v58

- **Vermelho:**
  - a R2 mudou depois de subir o rating do tabuleiro 1 da 6ª equipe;
  - o TPN do 310 era `{1: 2, 2: 3, 3: 4, 4: 1}`, mas o motor usou `{1: 1, 2: 2, 3: 3, 4: 4}`;
  - o todos-contra-todos mudava quando uma equipe era desativada;
  - faltavam `assign_team_pairing_numbers` e `tpn_from_first_round`.
- **Dados:** `teams.pairing_number`, `teams.seed_rating` e `teams.entry_round` (este para o E6), no schema e na **v58** (`legacy_migrations._migrate_to_v58`; `Database.SCHEMA_VERSION = 58`).
- **Correção:**
  - `assign_team_pairing_numbers` mantém o TPN gravado e dá o número seguinte a quem não tem, na ordem da semente. O entrante tardio vai para o fim, sem renumerar ninguém (C.04.2).
  - A geração grava TPN e semente junto com a rodada, numa transação (`Database.save_team_pairing_numbers`, que só grava onde o TPN está vazio). A prévia não grava.
  - O motor recebe `pairing_strengths` (−TPN): ordem, cor e bye seguem o número gravado, não o rating de hoje.
  - O todos-contra-todos monta o círculo com o campo que tem TPN, inclusive a equipe desativada. Ela perde por W.O. e os outros confrontos não mudam.
  - `TRF25._prepare_teams` ordena pelo mesmo TPN e usa `team_seed` (ou a semente gravada) como *strength factor*.
- **Migração de torneio em andamento:** `tpn_from_first_round` é a inversa exata da R1 do Suíço e da R1 do círculo, conferida por ida e volta com 2 a 7 equipes. A migração lê a R1 já gerada e não recalcula. A semente usada fica vazia, porque não se sabe qual era. É idempotente: só preenche torneios sem nenhum TPN.
- **Testes:** `NumeroDeEmparceiramentoPuroTest`, `NumeroDeEmparceiramentoServicoTest` (os três aceites) e `MigracaoTpnTest` (v57 → v58 com rating mudado depois da R1; a segunda execução não muda nada).

### E5 — TRF do desempate de equipes com 162 e 299

- **Prova do defeito:** com 2 rodadas fechadas, `compute_teams(..., current_round=1)` (o retrato da R1) falhava com `Erro no calculo de desempates do Gacrux: Erro desconhecido`. A linha 001 do TRF25 trazia os pontos de HOJE, mas as células só iam até a R1.
- **Correção:** `GacruxTiebreakEngine.prepare_teams` passa o TRF25 pelo mesmo `_with_score_records` do individual (`pairing_score` + `rebased_score_lines`). Isso põe o 162, os 299 recortados e os pontos declarados iguais às células.
- O formato de equipes do Gacrux aceita o 162 (`trf2json` lê o 162 também em torneio por equipes).
- Os 299 de EQUIPE que o exportador emitia saem do arquivo do desempate, sem perda: o Gacrux só os acumula em `aatlist` e não os usa no desempate de equipes (`parse_trf_abnormal` aplica o 299 só quando `not teamTournament`). Quem aplica o ajuste é o Albericus (TBK-01, já recortado por rodada).
- **Numeração dos jogadores:** o mapa do desempate de equipes usa os jogadores DO ARQUIVO (`exporter.players(tid, up_to_round=N)`), como o `prepare` individual. Com a lista sem corte, uma reserva inscrita depois da R1 virava o n.º 1 no retrato da R1 e os pontos de entrada dela iam para outro jogador. Prova: `test_retrato_numera_os_jogadores_como_o_arquivo`, vermelho "O arquivo TRF não consegue dizer… diferença de +1", depois verde. As equipes não são cortadas no arquivo: o TPN é gravado, a equipe tardia fica no fim sem renumerar as outras, e o retrato a descarta em `_team_standings` (E6).
- **Conferência:** os cenários sem recorte (normal, bye H, ajuste) deram o mesmo resultado antes e depois.
- **Testes:** `TrfDoDesempateDeEquipesTest::test_retrato_da_r1_declara_os_pontos_das_celulas_da_r1` e, com `-m gacrux`, `test_gacrux_calcula_o_retrato_da_r1`.

### E6 — corte de entrante tardio de equipe

- **Vermelho:** a equipe inscrita depois da R1 aparecia no retrato da R1.
- **Correção:** `standings_cut.teams_as_of_round` aplica a mesma regra do jogador: entra quem foi inscrito até N (`entry_round` de 1 a N; `0` é desconhecido e entra) ou tem confronto até N. É aplicada em `_team_standings(up_to_round=N)`. `create_team` grava `entry_round` (1 + última rodada gerada), e a v58 preenche as equipes antigas, como a v56 fez com os jogadores.
- **Teste:** `EntranteTardioDeEquipeTest`.

### EQ-05 — bye solicitado H/Z não bloqueia o bye alocado

- **Texto conferido (2026-11-26):**
  - C.04.6, art. 2.1.2 [C2] (https://handbook.fide.com/chapter/SwissTeamPairingSystem202602): não recebe o bye alocado a equipe que já recebeu o bye alocado, ou venceu um match por W.O. (ou recebeu o bye de ponto cheio, que a FIDE desaconselha).
  - C.04.1, art. 4 (https://handbook.fide.com/chapter/C0401202507): o mesmo para o individual, com "já marcou, sem jogar, os pontos de uma vitória".
  - Nenhum dos dois cita o bye solicitado de meio ponto ou de zero: H e Z não bloqueiam.
- **Vermelho:** `team_bye_ids` devolvia `{10, 20, 30, 40}` para byes BYE, F, H e Z; o esperado era `{10, 20}`. No serviço (3 equipes, a 3ª pede H na R1, as outras empatam), o bye alocado da R2 ia para a equipe 2 em vez da 3.
- **Correção:** `histories.team_bye_ids` usa a mesma regra do individual, `_blocks_pairing_allocated_bye`, que bloqueia `BYE`, `F`, `U` e vazio. Bye gravado sem tipo continua bloqueando.
- **Testes:** `ByeSolicitadoDeEquipeTest`, `ByeSolicitadoDeEquipeServicoTest`.

### EQ-06 — entrante tardio no todos-contra-todos por equipes

- **Vermelho:** a equipe inscrita depois da R1 recebia TPN no fim e entrava no círculo. A R2 trazia a equipe nova, e os confrontos de todo mundo mudavam (`KeyError` no teste, que só conhecia as 4 equipes da R1).
- **Correção:** `_team_next_round_plan` faz como o rodízio individual: a equipe sem TPN fica fora do calendário, sem receber número, com o mesmo aviso (`fixed_calendar.late_entry_warning`, formato "todos-contra-todos por equipes").
- O plano de equipes ganhou `warnings`:
  - a prévia os mostra no topo (`team_preview_payload`), antes dos avisos de escalação;
  - a geração os grava no evento `pairing_warning` (`_warn_pairing_notes`), como o individual.
- **Teste:** `EntranteTardioNoTodosContraTodosTest`. O calendário é o mesmo com e sem a equipe tardia, a prévia avisa, a equipe não recebe TPN e a trilha tem um `pairing_warning`.

### EQ-01.5 — correção de TPN pelo árbitro

- **Regra:**
  - C.04.6, art. 1.1.3: o TPN, uma vez definido, não deve mudar, salvo decisão do árbitro-chefe;
  - C.04.2, art. 2.3 (https://handbook.fide.com/chapter/GeneralHandlingRulesForSwissTournaments202602): por dado de ranking errado, o TPN não pode mudar depois que a 4ª rodada foi pareada.
- **Vermelho:** `TeamService` não tinha `swap_pairing_numbers`, e a tela de Equipes não tinha o botão "Trocar TPN".
- **Correção:**
  - `TeamService.swap_pairing_numbers(a, b, reason=)` troca os TPN das duas equipes. Trocar, e não digitar um número, mantém a numeração de 1 a N sem buraco nem repetição. A gravação é `Database.swap_team_pairing_numbers`, um único UPDATE.
  - Na mesma transação vai o evento `team_pairing_number_corrected`, com antes, depois, o motivo e a última rodada.
  - O motivo é obrigatório. A regra é `pairing_check.tpn_correction_reason_error`, a mesma checagem de `manual_adjustment_reason_error` com o recado do TPN.
- **Decisões [H]:**
  - **só entre rodadas:** a última rodada precisa estar fechada. A rodada aberta foi pareada com os números atuais, e corrigir no meio dela deixaria o número gravado diferente do que o motor usou;
  - **antes da R1 não há o que corrigir:** o TPN nasce na geração da R1;
  - **todos-contra-todos recusa:** o calendário saiu dos TPN da R1, e trocar depois repetiria confrontos;
  - **depois da R4 a troca não é bloqueada.** O C.04.2 2.3 limita a correção por dado de ranking, mas o C.04.6 1.1.3 deixa a decisão ao árbitro-chefe. O motivo gravado é o registro dessa decisão.
- **Tela:**
  - a tela de Equipes mostra a coluna **TPN**;
  - o botão **Trocar TPN** abre um diálogo para escolher a outra equipe e escrever o motivo;
  - o recado de erro (sem motivo, rodada aberta) aparece no próprio diálogo, sem fechá-lo (`_open_team_tpn_swap`).
- **Testes:**
  - `CorrecaoDeTpnTest` (serviço): troca e auditoria, a R2 usa o número novo, sem motivo, rodada aberta, antes da R1, todos-contra-todos;
  - `tests/test_ui_eq_tpn.py` (`gui`): troca pela tela e tabela atualizada; sem motivo, o diálogo avisa e nada muda.

### EQ-07 — Baku por equipes

- **Como era:** a aceleração ficava selecionável no torneio por equipes e era **ignorada em silêncio**, porque `_team_next_round_plan` não lia `acceleration_method`.
- **Texto conferido (2026-11-26), C.04.7** (https://handbook.fide.com/chapter/C0407202602). O texto **fala de equipes**:
  - o prefácio trata o match como a unidade de jogo numa competição por equipes;
  - o Exemplo 2 de 1.4.4 é "an 11-round team competition with matchpoints" (2 MP a vitória, 1 o empate). O GA recebe 2 MP virtuais nas R1–R3 e 1 MP nas R4–R6;
  - a nota do exemplo diz que, com game points como score principal, Baku não pode ser usado.
  - Por isso o VP **não é [H]**: é o valor de uma vitória de match na 1ª metade das aceleradas e o de um empate na 2ª.
- **Vermelho:**
  - não existia `baku_team_accelerated_ids`;
  - a R1 com Baku saía 1×5, 6×2, 3×7, 8×4, igual à R1 sem aceleração;
  - a R2 não juntava 1 e 4 (score de pareamento 4);
  - game points como principal não era recusado;
  - a aceleração clássica não avisava nada.
- **Correção:**
  - `acceleration.baku_team_accelerated_ids` decide quem recebe VP e quanto. O GA tem `2 × ⌈N/4⌉` equipes pela ordem do TPN gravado, entre as inscritas até a R1 (`teams_as_of_round`). O VP usa os match points do torneio. A função recusa game points como score principal e pontuação de match fora de 2:1:0 (C.04.7 1.1).
  - `baku_accelerated_player_ids` aceita a pontuação; o padrão continua 1 / ½ / 0.
  - R1: `team_swiss.baku_first_round_team_matches` pareia o GA e o GB como dois grupos. Cada grupo sai como a R1 de sempre, com a cor alternada pelo TPN. Se um bye solicitado deixa o GA ímpar, o último dele desce para o GB.
  - R2 em diante: `_swiss_team_matches` recebe o VP em `standings_with_virtual_points(..., score_key="match_points")`. Ele vale para os grupos, a ordem e o bye, nunca para a classificação.
  - O plano e o snapshot de entrada guardam `acceleration` (quem e quanto).
- **Avisos** (`team_acceleration_not_applied_warning`):
  - aceleração clássica ou personalizada em torneio por equipes: não se aplica, só Baku;
  - Baku no todos-contra-todos por equipes: não há grupos de pontuação a acelerar.
- **Testes:**
  - `BakuDeEquipesPuroTest`: o Exemplo 2 do Handbook e as duas recusas;
  - `BakuDeEquipesServicoTest`: R1 dentro do GA e do GB; o VP no pareamento da R2 e fora da classificação; a recusa com game points; o aviso da clássica.

### C.04.6 e a repetição de confronto depois de W.O. (EQ-03) — conferido em 2026-11-26

- **C.04.6** (https://handbook.fide.com/chapter/SwissTeamPairingSystem202602):
  - o art. 2.1.1 [C1] só remete às regras básicas: "Two participants shall not play against each other more than once" (C.04.1, art. 2). O texto não fala de match não jogado nem de W.O. nesse critério;
  - a única menção a W.O. é o art. 2.1.2 [C2] (bye);
  - a cor conta só o match "actually played" (art. 1.6.1) e os "played matches" (1.7);
  - o texto **não define** quando um match é "won by forfeit".
- **C.04.2, art. 3.5:** "Two paired participants, who did not play their game or match, may be paired together in a future round." O "or match" cobre equipes. O art. 3.4 diz que só jogos ou matches jogados contam para a sequência de cores.
- **Conclusão:**
  - o EQ-03 está de acordo com o texto: o match não jogado pode se repetir e não conta como cor;
  - fica **[H]** o critério de "match não jogado" (todos os tabuleiros por W.O.; W.O. parcial é match jogado), porque o Handbook não define. Ele segue o indicador conservador do 330/802.

### Pendências

- **Tela (frente de UI):**
  - ligar `TeamWithoutPlayersError` a um diálogo de confirmação que chame `generate_next_round(..., forfeit_empty_teams=True)`, como `_offer_reserve_engine` faz com `GacruxRefusal`;
  - hoje a tela mostra a mensagem, que já diz as duas saídas.
- ~~TRF25 de equipes com Baku~~ **feito (2026-11-27):** `_team_acceleration_records_250` emite o 250 em match points (colunas 5–8; game points em branco) sobre o GA pelo TPN, com os mesmos blocos do pareamento (`baku_acceleration_blocks`), e o 192 leva `_BAKU`. A regra de quando vale é uma só para o motor e o arquivo: `acceleration.baku_applies_to_team_swiss`. Vermelho: nenhum 250 e `FIDE_TEAM_TYPEA_MP_GP` sem sufixo. Teste: `BakuDeEquipesNoTrf25Test`.
- **[H] ainda aberto:**
  - o critério de "match não jogado" (ver acima);
  - a escalação com reserva no lugar do ausente e vagas no fim. A regra segue o aceite da EQ-02; o C.04.6 não trata de escalação.
- **Baku com entrante tardio de equipe:** a equipe tardia recebe TPN no fim, então nunca fica acima do último do GA. O caso do C.04.7 1.3 (GA ímpar) não acontece por equipes enquanto o TPN do entrante for sempre o seguinte.
