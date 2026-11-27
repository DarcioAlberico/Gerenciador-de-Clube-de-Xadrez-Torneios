# Especificação — Revisão Geral 2

> **Status:** proposta **v2** (2026-11-27). A v1 passou pela 10ª revisão (crítico adversarial); o Anexo A traz o que mudou e por quê.
> **Roadmap:** `ROADMAP_REVISAO_GERAL_2.md`.
> **Base analisada:** branch `fix/rgs-fase0-exe` @ `71e4195` **mais** a árvore de trabalho não commitada (≈335 arquivos: o trabalho da Revisão Geral Suíço e a passada de acentos). Cópia de segurança dessa árvore: `refs/backup/antes-rg2` (`0140e7d`).
> **Antecessora:** `ESPEC_REVISAO_GERAL_SUICO.md` (RGS-01..37). Nada daqui repete um RGS feito; quando um RGS ficou incompleto, o item diz qual.

## 0. Por que este documento existe

A Revisão Geral Suíço nasceu de um incidente. Esta não: é uma varredura preventiva do programa inteiro, pedida pelo dono, depois de 37 itens entregues e antes de commitá-los. A pergunta é: **o que ainda faz o árbitro, o professor ou o clube ver um resultado errado como se fosse certo?**

Dez revisões independentes (seção 9) produziram cerca de 115 achados brutos. Este documento consolida os que sobreviveram à conferência em **47 requisitos** `RG2-NN` (42 da v1 e 5 da 10ª revisão). Cada um tem:

- a evidência (`arquivo:linha`, saída de script ou de teste);
- o cenário concreto de falha;
- a causa-raiz em uma frase;
- o requisito;
- o critério de aceite, escrito como teste **que falharia contra uma implementação vazia**.

Regra da casa, herdada: **nada some calado, nada fica meio gravado, e o que funciona não se mexe** (seção 8).

**Severidade:**
- **P0** impede o torneio, ou o `.exe` distribuído não é o programa testado.
- **P1** corrompe dado, viola regra FIDE, afeta prêmio ou derruba a operação.
- **P2** atrito operacional, ou falha que só aparece em caminho menos usado.
- **P3** polimento ou dívida.

**Marcação de evidência:**
- **[E]** executado e visto falhar (script em `docs/revisao_geral_2/repro/rN/`, citado como `rN/arquivo`);
- **[E²]** executado por um revisor **e** reproduzido de novo na consolidação;
- **[L]** lido no código, caminho completo;
- **[H]** hipótese, falta reproduzir.

**Não há P0.** O `.exe` é o testado (RGS-05 entregue), a suíte inteira passa e nenhum achado impede um torneio de acontecer. O que há é **17 P1**: o torneio acontece, mas um número sai errado. A v1 tinha 20; a 10ª revisão rebaixou quatro (RG2-04, 10, 18, 19) e trouxe um novo (RG2-46).

**Banco real de referência.** A 10ª revisão rodou cenários contra uma cópia de `albericus_auto_shutdown_20261111_080728.db`: um único usuário (`admin`); 163 de 300 jogadores com `rating` e sem FIDE ID; 615.661 linhas em `official_players` (3 retratos da lista); 416 eventos pendentes em `sync_outbox`. Esses números calibram as severidades abaixo.

---

## 1. Linha de base executada (revisão 1)

| Medida | Valor |
|---|---|
| Gate `-Fast` (compilação, ruff, mypy, convenções de UI, acentuação) | **verde** (1869 textos, lista fechada de 267 palavras) |
| Suíte completa (`pytest`, com janela) | **2409 passaram, 5 pulados, 0 falhas** |
| Cobertura de linhas de `src/` (sem Gacrux) | **66,5 %** |
| Funções com CRAP ≥ 10 (crapper) | **431 de 3450** |
| Pares com semelhança ≥ 0,8 e ≥ 150 tokens (dryer) | **38** |

**O que a linha de base diz.** A suíte verde não protege os importadores: `import_rating_list_csv` (cobertura 2 %), `_member_payload_from_row` (3 %), `_import_member_rows` (3 %), `import_official_excel` (1 %, CRAP 1211). É exatamente onde as revisões 5, 6 e 7 acharam dado errado entrando calado (RG2-13, RG2-14, RG2-30). E a duplicação mais alta do código de domínio — `team_swiss.dutch_team_bracket_pairing` é 0,96 igual a `fide_dutch.dutch_bracket_pairing` — está no ponto em que a revisão 3 achou o suíço por equipes repetindo confronto (RG2-07): a cópia divergiu do original.

---

## 2. P1 — o número sai errado

> A numeração da v1 foi mantida para não quebrar as referências. Quatro itens desta seção foram rebaixados a P2 pela 10ª revisão (RG2-04, 10, 18, 19) e ficam aqui, marcados; o RG2-46 (P1) está na seção 5A.

### RG2-01 · A retenção de backups apaga o banco vivo e os backups de segurança · P1 · [E]
- **Origem:** R2.1, R2.5, R2.10.
- **Evidência:** `src/core/database.py:1125` `list_backups` faz `glob(f"*{suffix}")` — qualquer `.db` da pasta; `prune_backups` (`:1140`) só confere o sufixo antes do `unlink`; a ordem é por `modified_at` em texto com resolução de segundo (`:1137`). `src/ui/screens/settings.py:290-319` aceita qualquer pasta. Script `r2/prune_live.py`: `banco vivo existe? False`; `r2/retention.py`: apaga `before_restore` e `before_schema_migration` antes dos demais.
- **Cenário:** o usuário aponta "Pasta de backups" para a pasta do `albericus.db`. Ao fechar, `auto_shutdown` → retenção → o banco de trabalho (mtime mais antigo) é apagado. Sem esse erro de configuração, um torneio de 9 rodadas gera ≥ 18 backups com retenção 10: o único retrato pré-migração some no primeiro dia.
- **Causa-raiz:** a retenção trata como backup todo arquivo com o sufixo, num balde só.
- **Requisito:** a poda só considera arquivos `"{stem}_*"` criados pelo Albericus; nunca toca `db_path`; recusa `backup_dir == db_path.parent` ao salvar; `before_schema_migration`, `before_restore` e `normalizar_datas` ficam fora da cota comum (cota própria de 3); ordena por `st_mtime_ns` e desempata pelo nome.
- **Aceite:** com `backup_dir = db_path.parent` e 3 backups, `prune_backups(1)` mantém `db_path`; com 12 backups comuns e 1 `before_schema_migration`, `prune_backups(10)` mantém o de migração; 3 backups no mesmo segundo → o último criado sobrevive.
- **Nuance (R10):** a retenção só roda dentro de `create_backup` (manual ou ao fechar, `security_service.py:256-259`), nunca depois de `backup_before`, e nunca para quem não é admin — ver RG2-44. Os dois itens andam juntos, e com o RG2-31 (cada backup real tem 110 MB por causa da lista FIDE).

### RG2-02 · Enter na tabela de Rodadas grava o resultado em duas mesas · P1 · [E²]
- **Origem:** R4.1 (regressão do RGS-21); reproduzido na consolidação.
- **Evidência:** `src/ui/screens/pairing_results/view.py:377` liga `<Return>` na tabela a `_save_selected_result()` sem devolver `"break"`; `view.py:726` liga `<Return>` também no nível da tela. Sonda `r4/test_probe_r4.py::test_enter_na_tabela_grava_duas_vezes`: `['1/2-1/2', '1/2-1/2', '', '']`, 2 eventos `result_updated`.
- **Cenário:** mesa 1 selecionada, "½-½", Enter → mesas 1 **e 2** ficam ½-½. O primeiro salvamento move o cursor para a próxima pendente e o segundo binding grava de novo. Com W.O. a confirmação aparece duas vezes (a segunda nomeando outra mesa); em rodada fechada o diálogo "Corrigir resultado" abre duas vezes. O Ctrl+Z desfaz só o segundo.
- **Causa-raiz:** o handler da tabela não interrompe a propagação do evento.
- **Requisito:** todo handler de tecla da tabela que grava devolve `"break"`. Um teste varre os `bind(` de `pairing_results/` e reprova handler de gravação sem `"break"` quando há binding da mesma sequência num ancestral.
- **Aceite:** teste de janela — Enter na mesa 1 gera exatamente 1 `result_updated`; a mesa 2 continua `""`; `confirm_walkover` é chamado 1 vez.

### RG2-03 · A auto-atualização do painel do árbitro muda a mesa-alvo e rouba o foco · P1 · [E²]
- **Origem:** R4.2; reproduzido (`seleção após tick: 0 (antes 2)`).
- **Evidência:** `src/ui/screens/pairing_arbitration/refresh.py:59-66` remonta o painel a cada 15 s (ligado por padrão); `pending.py:201` seleciona a primeira mesa; `pending.py:206` faz `focus_set()` na tabela; `pending.py:144` recria a busca só com a consulta aplicada.
- **Cenário:** (a) o árbitro seleciona a mesa 3 e olha a súmula; passa o tick; ele tecla "1" e o 1-0 vai para a **mesa 1**, sem confirmação. (b) Ele clica na busca para digitar "15"; o tick leva o foco para a tabela; o "1" grava 1-0 na primeira mesa e o texto digitado some.
- **Causa-raiz:** o refresh é uma remontagem completa, sem preservar seleção, foco e rascunho.
- **Requisito:** o tick preserva o `pairing_id` selecionado, o widget com foco e o texto da busca; nunca chama `focus_set` quando veio do agendamento; pula o tick enquanto houver diálogo aberto ou foco num campo de texto do painel; mostra "atualiza em N s".
- **Aceite:** selecionar a 3ª mesa e focar a busca, rodar `_tick()`: a seleção continua no mesmo `pairing_id`, `focus_get()` continua no campo, e `<Key-1>` não grava nada.

### RG2-04 · Permissão existe só em parte da tela; os serviços não checam nada · P2 · [E]
- **Origem:** R4.3 [E], R7.3 [L], R10 (rebaixado de P1: o banco real tem um usuário só; o cenário exige instalação com vários papéis).
- **Evidência:** só `src/services/security_service.py` chama `require_permission`. A aba "Árbitro" (`src/ui/app.py:605`) não exige permissão; `pairing_arbitration/pending.py:277` (resultado), `:298` (adiar), `registry.py:184,197` (byes, ajustes de pontos, proibições), `issues.py:237-262` e `pairing_results/qr.py:64,74` (aprovar/rejeitar QR) gravam direto. `TournamentService.delete_tournament` (`tournament_service.py:206`), `finance_service.py:280,347` e os deletes de membros não checam. A permissão `delete_records` não é usada em lugar nenhum. Sonda `r4`: logado como `viewer`, lança 1-0, adia mesa e cria ajuste de +1 ponto — tudo gravado — enquanto a tela de Rodadas recusa.
- **Cenário:** um monitor com papel `viewer` muda a classificação (e o prêmio) por um ajuste de pontos.
- **Causa-raiz:** a matriz de `src/config/permissions.py` é aplicada handler a handler, na apresentação; a extração do painel (B-6) não levou a checagem.
- **Requisito:** **a regra mora no serviço** (*Boundary Discipline*), e o operador mora **num lugar só**: um provedor de operador dentro de `Database`, definido por `SecurityService.login` (o mesmo que conserta RG2-43). Os métodos de escrita chamam `require_permission` lendo esse provedor — nenhum serviço muda de assinatura (27 são montados só com `db`, `tests/support/core_service_base.py:42-66`). `delete_records` vale só para registros globais (membro, torneio, finanças); "excluir rodada" continua exigindo `tournament_write` (§8). Fluxos do sistema — backup automático, retenção, reconciliação, migração, `--self-test`, `--gacrux` — rodam sem operador e ficam isentos. A tela continua desabilitando o botão, só como conforto.
- **Definição de "método que grava"** (para a varredura): método público de `src/services/` que chama `self.db.(create|update|delete|replace|save|add|close|set)_*` ou abre `self.db.transaction()`, descoberto por AST, não por lista à mão.
- **Aceite:** com operador `viewer`, `update_result`, `postpone`, `add_point_adjustment`, `approve_submission`, `delete_tournament` e `delete_transaction` levantam `AppError("Permissão negada…")` e o banco não muda; com `arbiter`, `delete_generated_round` continua funcionando; a varredura por AST não encontra método que grava sem checagem.

### RG2-05 · Excluir um bye já usado não tem regra nem rastro, e o saldo zera · P1 · [E²]
- **Origem:** R4.4; reproduzido.
- **Evidência:** `src/ui/screens/pairing_arbitration/controller.py:238` chama `db.delete_requested_bye` direto. Sonda: mesa da R2 continua "H"; saldo "1 usado" → "nenhum usado"; nenhum evento de remoção. `request_bye` conta o limite por `list_requested_byes` (`pairing_service.py:1049`).
- **Cenário:** com limite de byes no regulamento, o jogador recebe um bye acima do limite; a tela de Rodadas passa a tratar o H como "fora do padrão".
- **Causa-raiz:** a exclusão não passa pelo serviço.
- **Requisito:** `PairingService.cancel_requested_bye(bye_id, reason)` — recusa se a rodada do bye já foi gerada ou fechada; sem rodada, exige motivo e audita (`requested_bye_removed`). A tela só chama o serviço.
- **Aceite:** com a rodada já gerada, excluir levanta `AppError` e o saldo continua "1 usado"; sem rodada, excluir cria o evento.

### RG2-06 · Jogador ausente do resultado do motor de desempate vai para o 1º lugar · P1 · [E]
- **Origem:** R3.2 [E], R6.1 [E], R6.6 [L].
- **Evidência:** `src/services/pairing/tiebreaks.py:467` usa `int(item.get("_gacrux_rank") or 0)` — rank ausente vale 0, que vem antes do rank 1. `gacrux_tiebreak_engine.py:107` monta o TRF com `players(up_to_round=rounds)` (exclui `entry_round` maior que as rodadas fechadas), enquanto `standings()` sem `up_to_round` lista todos (`pairing_service.py:4109`). `gacrux_tiebreak_engine.py:244-253` descarta sem conferir competidor sem `cid` mapeável e aceita `{"tiebreakResult": {}}` como sucesso; `gacrux_tiebreak_map.py:258-262` troca valor ilegível por `0.0`. Script `r3/late.py`: `[('Tardio', 1.0), ('J2', 2.0), ('J0', 1.0), …]`.
- **Cenário:** um entrante tardio inscrito durante a R2 aparece em **1º** na classificação ao vivo, impressa ou publicada, durante a R2 e a R3. Uma saída vazia do motor faz a tela rotular "Desempates FIDE (Gacrux)" sobre o cálculo próprio.
- **Causa-raiz:** o conjunto de jogadores da classificação difere do conjunto do TRF de desempate, e a resposta do motor não é conferida contra o pedido.
- **Requisito:** (1) `GacruxTiebreakEngine.run` confere a resposta: um competidor por jogador **pedido**, `tiebreakScore` com o tamanho de `code_order`, valores numéricos — senão `AppError`, que aciona o fallback **já auditado** (TBK-02). (2) Na chave de ordenação, quem não tem rank do motor vai depois de todos os ranqueados com a mesma pontuação (`(−pontos, rank or inf, …)`), e o fato é registrado em log. (3) Só na **tela** de classificação, o entrante cuja rodada de entrada ainda não começou aparece numa seção "Entram na rodada N". `standings()` **não muda de recorte**: TRF (`export_federation.py:788`), tabela cruzada (`pairing_service.py:4412`), certificados, site e rating (`rating_service.py:819`) leem dele (R10, objeção 3).
- **Aceite:** no cenário de `late.py`, J2 (2,0) fica em 1º e o tardio vem depois de todos os de 2,0; com a saída do motor trocada por `{"tiebreakResult": {}}`, `run` levanta `AppError` e o evento de fallback é gravado; o TRF exportado no mesmo cenário é igual byte a byte ao de antes da mudança.

### RG2-07 · O suíço por equipes repete confronto quando havia pareamento sem repetição · P1 · [E]
- **Origem:** R3.1; reforçado pelo dryer (revisão 1); números refeitos na R10.
- **Evidência:** `src/services/pairing/team_swiss.py:597-674` (`dutch_team_bracket_pairing`): os flutuantes são fixados em `group[-k:]` e `return [], group` empurra o grupo inteiro para o resto (a linha `:671` já recusa repetição no 3º passe — a causa não é ela); `:736-756` (`optimal_team_pairs`/`greedy_team_pairs`) pareiam o resto só penalizando repetição; o bye é escolhido antes de qualquer teste de viabilidade (`constraints.py:271-288`) e, quando todas já tiveram bye, `candidates = teams` — 2º PAB calado. Script `r3/team_stress.py 0 10` (7 equipes × 6 rodadas, força bruta como oráculo), reproduzido duas vezes pela R10: repetição evitável em **3 de 10** sementes (0, 2, 7); na semente 5 repete **sem** alternativa em vez de recusar; **3 cores iguais seguidas** nas sementes 3, 4 e 6 [E]. O individual pelo Gacrux, no mesmo teste, ficou em 0.
- **Cenário:** interclubes comum; na R4 ou R5, o mesmo par de equipes se enfrenta de novo.
- **Causa-raiz:** a cópia de equipes do pareamento holandês (dryer: 0,96 com `fide_dutch.dutch_bracket_pairing`) divergiu e trata o critério absoluto C.04.1 "não repetir" como custo no resto. *Uma decisão, um lugar:* não se conserta a cópia — elimina-se.
- **Requisito, em duas partes (R10, objeção 11):**
  - **RG2-07a (P1, hotfix):** uma guarda **depois** do pareamento de equipes recusa a rodada que repete confronto ou dá 2º PAB, com mensagem C.04.1 e a oferta de ajuste manual auditado. Pequena, não mexe no motor.
  - **RG2-07b (P2, Fase 3):** um só motor de busca por grupo, parametrizado por "competidor" (jogador ou equipe), com repetição **proibida** e o bye como mais um nó da busca; junto com RG2-23 e os pares do dryer em RG2-42. A cor por equipe segue C.04.6 [conferir o texto: 3 cores iguais seguidas].
- **Aceite:** (a) com as sementes 0, 2, 5 e 7, a guarda recusa a rodada repetida em vez de gravá-la; (b) teste `-m gacrux`/lento com 7 equipes × 6 rodadas e sementes fixas: nenhuma repetição quando o oráculo acha alternativa; nenhum 2º PAB; 3 equipes × 4 rodadas termina em erro claro.

### RG2-08 · Fechar rodada por equipes não é idempotente nem atômico (RGS-11 incompleto) · P1 · [E]
- **Origem:** R2.4.
- **Evidência:** `src/services/pairing_service.py:3422-3529` — sem guarda "já fechada" e sem `transaction()`, ao contrário do individual (`:2816`, `:2848`). Script `r2/team_close.py`: 2 eventos `team_round_closed` e 2 backups no duplo clique; falha injetada no retrato → `rodada 2 status: closed | retratos: [1]`.
- **Cenário:** duplo clique em "Fechar rodada" duplica backup e auditoria; uma falha entre `close_round` e `create_standings_snapshot` deixa a rodada fechada sem retrato, que a reconciliação não conserta.
- **Causa-raiz:** o RGS-11 cobriu só o caminho individual.
- **Requisito:** o fechamento por equipes usa a mesma guarda e a mesma transação do individual — de preferência **o mesmo método**, com o passo específico de equipes injetado.
- **Aceite:** dois fechamentos → 1 evento e 1 backup; falha injetada no retrato → a rodada continua `generated`.

### RG2-09 · Excluir jogador de torneio por equipes apaga o jogador de um tabuleiro já jogado · P1 · [E]
- **Origem:** R2.2.
- **Evidência:** `pairing_service.py:3715-3729` confere só `count_player_pairings`, que olha a tabela `pairings` (`database_tournament_core.py:1985-1995`). `team_boards` tem `ON DELETE SET NULL` (`database_schema.py:503-504`) e `team_substitution_events.in_player_id` tem `CASCADE` (`:557`). Script `r2/team_delete.py`: tabuleiro depois `{'white_player_id': None, …, 'result': '1-0'}`.
- **Causa-raiz:** a guarda "já jogou" ignora `team_boards` e `team_lineup_boards`.
- **Requisito:** a contagem de participação inclui `team_boards` (brancas e pretas), `team_lineup_boards` e `team_substitution_events`; quem jogou só pode ser retirado, não excluído.
- **Aceite:** o cenário do script levanta `AppError` e o tabuleiro mantém o `player_id`.

### RG2-10 · `valor or padrão` transforma 0 em 1 nos pontos · P2 · [E]
- **Origem:** R2.3 [E], R3.7 [L], R10 (rebaixado: só o caminho da divisão é realista; empate ou vitória de equipe valendo 0 não é configuração plausível). Entra no PR único de **fronteira numérica** com RG2-14, 27 e 46.
- **Evidência:** `tournament_service.py:586` (`bye_points or 1.0` ao dividir torneio; script `r2/split_bye.py`: mãe 0,0 → filhos 1,0); `team_match_draw_points … or 1.0` em `database_tournament_core.py:541`, `pairing_service.py:2560,3446,3482` e `team_swiss.py:380` (o mesmo para vitória 0). A divisão (`:573-619`) faz ~8 gravações por grupo sem transação e não copia `rapid_rating`, `blitz_rating`, `games_played`.
- **Cenário:** torneio com bye valendo 0 → "Dividir em 2" → os grupos dão 1 ponto no PAB: classificação e prêmio mudam. Uma falha no grupo B deixa o grupo A pela metade.
- **Causa-raiz:** o idioma `x or default` aplicado a número que pode legitimamente ser 0.
- **Requisito:** um leitor único `setting_number(row, key, default)` que trata como ausente só `None` e `""`; a divisão roda numa transação e copia os ratings rápido/blitz e `games_played`. Um teste-varredura reprova `.get("…points…") or <número ≠ 0>` em `src/`.
- **Aceite:** com bye 0, os filhos ficam com `bye_points == 0.0`; empate de equipe salvo como 0 é lido 0,0; falha injetada no 2º `create_tournament` → nenhum filho existe.

### RG2-11 · O rating do clube sai como rating FIDE (TRF, normas, IT3) · P1 · [E]
- **Origem:** R5.1, R5.2.
- **Evidência:** `src/services/export_federation.py:629-635` — `_trf_rating = international_rating or rating or national_rating`, usado na linha 001 colunas 49-52 (`:876`), no registro 072 (`trf16.py:174`, `trf25.py:227`) e no aviso "sem rating FIDE" (`trf16.py:382`). `src/services/rating/report.py:25-27` termina a cadeia (FIDE, STANDARD) em `("rating", "geral")`, e as normas a usam (`norms/report.py:62-64`), assim como o IT3 (`export_federation.py:197`). Script `r5/t1`: jogadora sem FIDE e com 1650 do clube sai `1650` na coluna FIDE, e o 072 conta 4 ratados de 4; reimportar grava `international_rating=1650` (`import_service.py:400-401`) — o dado falso vira permanente. `r5/t6 B`: 9 adversários "GM" sem FIDE com 2500 local → Ra 2500 e **norma de GM atingida**.
- **Alcance real (R10):** no banco real, **163 de 300** jogadores têm `rating` e não têm FIDE ID — todos sairiam com rating na coluna FIDE do TRF. A parte de normas é a mesma causa, mas o cenário (9 "GM" sem FIDE) não acontece na prática: **P1 para TRF/072, P2 para normas e IT3**.
- **Causa-raiz:** um mesmo atalho serve à ordem inicial (onde o fallback é legítimo) e ao campo FIDE (onde não é).
- **Requisito:** `fide_rating(player)` devolve só `international_rating` e é o único leitor usado em 001/072, normas e IT3; o atalho fica restrito ao número inicial. B.01 1.4.6: adversário sem rating FIDE conta 1400 [conferir o texto oficial].
- **Aceite:** jogador com `rating=1650` e `international_rating=0` sai com colunas 49-52 vazias e não entra no 072; o cenário `t6 B` dá `unrated_opponents=9` e nenhuma norma.

### RG2-12 · Normas: federação vazia escapa dos limites de federação · P1 · [E]
- **Origem:** R5.3.
- **Evidência:** `src/services/norms/opponents.py:133,180-182` descartam federação vazia; `norms/evaluation.py:128-137` usa `own=""` e `own_count` fica 0. O TRF, ao contrário, cai na federação do torneio (`export_federation.py:877-880`). Script `r5/t6 A`: candidato e 7 dos 9 adversários sem `federation_id`, mais 1 ARG e 1 URY → "IM atingida" com 0 adversários da própria federação.
- **Causa-raiz:** duas regras para "federação efetiva", uma no TRF e outra nas normas.
- **Requisito:** `effective_federation(player, settings) = federation_id or settings.federation`, única, usada no TRF, nas normas e no IT3.
- **Aceite:** o cenário `t6 A` dá `own_federation_opponents=7` e reprova no limite de 1.4.4.

### RG2-13 · A importação de TRF perde jogos e fecha rodadas sem resultado, sem avisar · P1 · [E]
- **Origem:** R6.2, R5.4, R5.5.
- **Evidência:** `src/services/trf_import.py:86-87` faz `break` na primeira célula vazia (branco = bye 0 ou não pareado, `ESPEC_TRF25_FIDE.md:129,140`); `:306-330` descarta jogo com adversário inexistente ou assimétrico; letra desconhecida vira `""` (`results_registry.py:146`); `start_rank` ilegível vira `len(players)+1` (`trf_import.py:166-169`) e colide em `rank_to_id` (`import_service.py:406`); `import_service.py:409-418` fecha **toda** rodada e `trf_import.py:194,202` ignora 142/XXR para o total. Scripts `r5/t1`, `r5/t7`: entrante tardio perde a R2; torneio de 5 rodadas em andamento nasce com `rounds_count=2`, "encerrado".
- **Causa-raiz:** o parser descarta o que não entende, e o importador não distingue rodada completa de rodada pareada.
- **Atenuante (R10):** o 132 resgata o total quando traz todas as datas (`trf_import.py:207`). A parte "torneio em andamento" é P1 **se** importar torneio em andamento for uso suportado — decisão **D8**; a parte "perde jogos calado" é P1 em qualquer caso.
- **Requisito:** `parse_trf` devolve `(torneio, avisos)`; célula vazia é guardada como "não pareado" e a leitura segue até o fim da linha; rank duplicado ou ilegível levanta `AppError` (tudo já roda numa transação); só fecha a rodada cujas mesas têm todas resultado final; `rounds_count` vem de 142/XXR quando existir. A tela mostra os avisos antes de confirmar.
- **Aceite:** o round-trip de `t7` dá `rounds_count==5` e a R2 aberta; a linha com R1 em branco devolve 2 células; TRF em que o jogador 3 aponta para o rank 9 devolve um aviso que **cita o rank 9 e a linha do jogador 3**.

### RG2-14 · A importação de rating converte "1.850" em 1 e texto inválido em 0 · P1 · [E]
- **Origem:** R6.3.
- **Evidência:** `src/services/import_service.py:1156-1162` (`_parse_optional_int`), usada em `:590, :593, :735, :738, :1017, :1028`: `'1.850'` → 1; `'1,850'`, `'abc'`, `'2 000'` → 0. Como `rating = max(nacional, internacional)` (`:749`, `:1041`), o jogador entra com 1 ou 0, sem erro de linha. Os campos `rating`/`elo` já fazem certo (`:744-746`).
- **Causa-raiz:** "vazio" e "inválido" caem no mesmo 0, e `float("1.850")` lê o ponto de milhar brasileiro como decimal.
- **Requisito:** um `parse_rating(text) -> int | None | Erro` único na fronteira: vazio → `None`; ponto ou espaço como separador de milhar aceito ("1.850", "1 850" → 1850); resto vira erro da linha. Compartilha o núcleo com `parse_decimal_br` (RG2-46) e `parse_points` (RG2-27): um PR de **fronteira numérica**.
- **Aceite:** CSV com `rating_nacional="1.850"` importa 1850; `"abc"` gera erro na linha e o jogador não é criado com 0.

### RG2-15 · A categoria gravada no jogador não acompanha o edital nem as datas · P1 · [E]
- **Origem:** R8.1, R8.4.
- **Evidência:** a categoria é calculada só em `create_player`/`update_player` (`database_tournament_core.py:1121,1272,1380`) e a classificação lê a coluna gravada (`tiebreaks.py:512`); `replace_tournament_categories` (`:600-635`) só regrava a tabela de categorias. A inscrição a partir do membro (`database_members.py:521-541`) repassa `category` do membro (calculada no ano corrente) e não passa sexo — `members` não tem `sex` (`database_schema.py:56-85`); `categories/assignment.py:126-134` trata esse valor como manual. Scripts `r8/t1..t3`: Ana (2015, F) inscrita antes do edital continua "Sub-12; Sub-1400; Feminino" depois de cadastrar "Sub-11"; Bia (2014) inscrita do cadastro sai "Sub-12" (categoria inexistente no edital) e sem Feminino; o Modo Livre (`friendly_mode.py:191-195`) inscreve turmas assim.
- **Causa-raiz:** dado derivado gravado sem invalidação.
- **Requisito:** a categoria é **derivada**: `refresh_player_categories(tid)` roda na mesma transação de `replace_tournament_categories`, da mudança de `category_reference_date` e de `start_date`. O gancho da **D3** é concreto: com rodada fechada, pede confirmação e audita; se existe emissão de certificado do torneio (`certificate_issuances`) ou o torneio está encerrado, recusa. Os retratos por rodada (`create_standings_snapshot`) **ficam com a categoria da época** — são retratos — e a spec do RGS-10 não muda. A inscrição do membro não repassa valor de `AUTO_CATEGORY_VALUES`. O sexo do membro é o RG2-47, item próprio.
- **Aceite:** inscrever, regravar o edital → `categories == "Sub-11; Feminino"`; inscrever Bia do cadastro com edital Sub-13 → `category == "Sub-13"` (o Feminino depende do RG2-47); com um certificado emitido, regravar o edital levanta `AppError`.

### RG2-16 · "Apenas o maior prêmio" não repassa o prêmio e soma categorias · P1 · [E]
- **Origem:** R8.2, R8.9.
- **Evidência:** `src/services/prizes.py:139-143` (`max`), `:146-176` (`by_policy` soma todas as categorias), `:207-214`. Script `r8/t1` (reproduzido pela R10): geral 1º = 100; 1º Sub-12, 1º Sub-1400, 1º Feminino = 50 cada; o jogador 1 está nas três categorias → leva **150**, os 100 do geral não vão para ninguém, o 2º fica com 0: distribui 150 de 250. `test_politica_do_torneio_vale_para_a_categoria` não confere a próxima jogadora. Além disso, prêmio de categoria com nome inexistente ("Sub12", "Socio") é aceito (`prize_service.py:58-60`; `prizes.py:154-160` compara só com `casefold`) e nunca é alocado.
- **Causa-raiz:** cada faixa é calculada isoladamente e a política é aplicada depois, por jogador, sem repasse.
- **Requisito:** alocação sequencial: percorre os prêmios não cumulativos na ordem da decisão **D1** e dá cada um ao melhor elegível que ainda não tem prêmio; prêmios `cumulative` ficam fora da trava; o resultado traz `undistributed` e o relatório mostra "anunciado × distribuído". **Empate (Hort ou divisão igual, §8):** o grupo empatado que ocupa várias faixas divide primeiro o bolo dessas faixas, como hoje (`prizes.py:113-138`); a trava "um prêmio por jogador" se aplica depois, sobre o que cada um recebeu. Prêmio de categoria inexistente é recusado na gravação (comparação por `tag_key`).
- **Aceite:** no cenário de `r8/t1`, com a D1 recomendada: J1 = 100 (geral), J2 = 50 (Sub-12), J3 = 50 (Sub-1400), Feminino `undistributed` = 50 (nenhuma elegível sem prêmio); distribuído + não distribuído = 250; com dois empatados no 1º e Hort, a soma dos dois é igual à de hoje; `replace_prizes` com "Sub12" levanta `AppError`.

### RG2-17 · Duplicar torneio perde categorias e regras, e copia "arquivado" · P1 · [E]
- **Origem:** R8.3, R9.1.
- **Evidência:** `src/core/database_tournament_core.py:172-360` não copia `tournament_categories` nem `prize_tie_split`, `prize_exclude_withdrawn`, `category_reference_date`, `late_tolerance_minutes`; `:264` copia `archived`; e copia `fide_event_id` — a nova edição iria à FIDE com o ID do evento antigo (R10). Script `r8/t4`: duplicar a edição arquivada de 2025 → `cats []`, prêmio "Sub-11" que nunca será alocado, Hort volta a "igual", e o torneio novo nasce arquivado (some de `list_tournaments()`). O único teste do fluxo, `tests/test_dup_check_tmp.py`, só faz `print`.
- **Causa-raiz:** a cópia é uma lista de colunas escrita à mão, que não acompanhou ORG-01..04.
- **Requisito:** a duplicação copia as colunas por **lista de exclusão**, não de inclusão, e copia as categorias. A lista de exclusão: `id`, datas de criação/início/fim, `status`, `archived` (→ 0), `fide_event_id`, `chess_results_url`, `cutoff_date`, `initial_color` (o RGS-14 sorteia de novo) e `parent_tournament_id`. `test_dup_check_tmp.py` vira `test_tournament_duplicate.py`, com asserções.
- **Aceite:** depois de duplicar, categorias e esses ajustes são iguais à origem, `archived == 0` e o torneio aparece na lista; adicionar uma coluna nova a `tournaments` sem tratá-la não quebra a cópia (o teste compara todas as colunas, menos a lista de exclusão).

### RG2-18 · Categoria "até X" não pode aceitar quem está abaixo · P2 · [E] · funcionalidade, depende de D2
- **Origem:** R8.5; reclassificado pela R10 (de P1-bug para P2-funcionalidade).
- **Evidência:** `src/services/categories/assignment.py:63-84` (`narrowest_by_kind`) escolhe **de propósito** uma categoria por dimensão; `src/core/categories.py:182-185`. Script `r8/t2`: menino de 2017 com 1300 fica só com "Sub-10; Sub-1400"; os prêmios Sub-12 e Sub-1800 vão para o 2º. O docstring promete "se o edital deixar", mas não há como configurar. Aceitar mais novos é **opção de edital**, não regra FIDE/CBX — e vale igualmente para rating (o de 1300 também não leva o Sub-1800).
- **Requisito:** cada categoria tem "aceita quem está abaixo" (idade e rating, separados); padrão desligado — o comportamento atual — até a **D2**; a elegibilidade para prêmio e a classificação por categoria consideram todas as faixas que aceitam o jogador. Entra depois do RG2-16 (a trava de um prêmio por jogador fica mais importante com mais faixas por jogador).
- **Aceite:** com a opção ligada no Sub-12 e no Sub-1800, o 1º do cenário leva os dois — ou um só, pela trava do RG2-16; com a opção desligada, o resultado é idêntico ao de hoje.

### RG2-19 · O portal ao vivo serve qualquer torneio, e o modo vem do cliente · P2 · [L]
- **Origem:** R7.1; rebaixado pela R10 ("dados privados" exagerava).
- **Evidência:** `src/services/result_server.py:12` (bind `0.0.0.0`); `:58-68` lê `mode` da query string e `tournament_id` do caminho, sem conferir se foi publicado. O que cada modo acrescenta (R10): `privado` só o `contact_email` e os `comments` **do torneio** (`export_web.py:130-133`); `clube` só `fide_id`/`cbx_id` (`:219-221`), que são públicos. Nenhum telefone, nascimento ou e-mail de jogador sai.
- **Cenário:** um pai na Wi-Fi do torneio troca o id na URL e lê a lista de um torneio **não publicado** — nomes e categoria etária de menores de outra turma.
- **Causa-raiz:** o servidor não sabe o que foi publicado, e o nível de privacidade é parâmetro do cliente.
- **Requisito:** id diferente do publicado → 404; o modo é fixado em `publish_tournament` e a query é ignorada para clientes da rede (o modo `privado` só responde a `127.0.0.1`); o portal continua na rede local quando publicado (é para os pais na Wi-Fi — **D4** revista); cabeçalhos `Cache-Control: no-store` e `X-Frame-Options`. Anda junto com o RG2-45 (o QR aponta para `localhost`). Para testar, o app FastAPI sai de dentro de `start()` (`result_server.py:37`) para uma fábrica `build_app(server)`.
- **Aceite:** `TestClient(build_app(...))`: publicar o torneio 1 em modo público; `GET /api/tournaments/1/public?mode=privado` vindo de um IP da rede não contém `contact_email`; `GET /api/tournaments/2/public` → 404.

### RG2-20 · Exportar CSV/XLSX executa fórmula vinda do nome do jogador · P1 · [E]
- **Origem:** R7.2, R5.10 (duas lentes, independentes).
- **Evidência:** `src/services/export_writers.py:102-106` (CSV), `:140-144`, `:174-178` (XLSX). `_write_xlsx` com `=HYPERLINK("http://x","clique")` grava `data_type 'f'`; o CSV grava `=cmd|calc!A1` cru. Nomes chegam do Google Forms.
- **Causa-raiz:** texto vai cru para `sheet.append` e `csv.writer`.
- **Requisito:** neutralizar na fronteira de saída, **sem estragar telefone** (R10, objeção 8: "+55 11…" ganharia um `'` literal no XLSX e voltaria como `'+55` na reimportação):
  - XLSX: texto que começa com `= + - @ \t \r` é gravado com `data_type = 's'` (string), **sem alterar o texto**;
  - CSV: o texto ganha `'` na frente, e os importadores do Albericus retiram um `'` inicial seguido de `= + - @`;
  - números não mudam.
- **Aceite:** exportar `=1+1` e reabrir com openpyxl → `data_type == 's'` e valor `=1+1`; exportar o telefone `+55 11 9999` em XLSX e reimportar → `+55 11 9999`; no CSV a célula `=1+1` começa com `'` e o rating 1850 continua numérico.

---

## 3. P2 — FIDE, federação e importação

### RG2-21 · A verificação holandesa (RGS-16) deixa de rodar depois de uma entrada tardia com pontos · P2 · [E]
- **Origem:** R3.3 (regressão RGS-24 × RGS-16).
- **Evidência:** `src/services/pairing/gacrux_trf.py:259` — `with_round_cells` termina em `patched.rstrip()`, que come a coluna de resultado da rodada recém-gerada (`   4 w  `). Gacrux `-c` → `code 502 "Error reading file"`; `pairing_check_unverified` da R3 à R7 em 3 de 3 sementes; sem o `rstrip`, 0 problemas (`r3/stress_patched.py`).
- **Causa-raiz:** o `rstrip` reescreve a geometria da linha 001 (o exportador já evita isso com `ljust`).
- **Requisito:** a linha 001 recomposta mantém o comprimento até o fim da última célula; teste unitário de `with_round_cells`, `reconcile_scores` e `rebased_score_lines` com célula pendente.
- **Aceite:** gerar a R3 com entrante de 0,5 → evento `pairing_check` "confere" e nenhum `pairing_check_unverified`.

### RG2-22 · Sem pareamento legal possível, o árbitro recebe um traceback · P2 · [E]
- **Origem:** R3.4.
- **Evidência:** `gacrux_engine.py:282-284` sobe `AppError` cru com o stderr quando `returncode != 0`, em vez de `GacruxRefusal`; `generate_next_round(reserve_engine=True)` relança. Script `r3/two.py`: 2 jogadores na R2 → `Traceback … RuntimeError: Gacrux: 2 nó(s) sem par`; o reserva idem; 3 jogadores, R4 idem.
- **Requisito:** a falha de viabilidade vira `GacruxOutputRejected` com o texto C.04.1 ("não existe pareamento que respeite os critérios absolutos"); o motor reserva não é oferecido nesse caso (também não há pareamento legal) — oferece-se "encerrar o torneio aqui" ou "rever ausências".
- **Aceite:** no caso de 2 jogadores, a mensagem não contém "Traceback" e a exceção é `GacruxRefusal`.

### RG2-23 · O pareamento por equipes ignora "pontos de tabuleiro" como critério principal · P2 · [L]
- **Origem:** R3.5.
- **Evidência:** `team_swiss.py:716` e `constraints.py:238-250` agrupam por `match_points`; nenhum lê `team_standing_primary`, que a classificação (`team_tiebreaks.py:272`) e o TRF25 respeitam.
- **Requisito:** grupos e ordenação usam a chave do critério principal configurado (entra junto com RG2-07, no motor único).
- **Aceite:** com `team_standing_primary=game_points`, duas equipes com os mesmos match points e game points diferentes ficam em grupos diferentes.

### RG2-24 · Scheveningen e eliminatória são desempatados com regras de suíço · P2 · [L]
- **Origem:** R3.6.
- **Evidência:** `gacrux_tiebreak_engine.py:103` — `swiss = pairing_method != "round_robin"` manda `-s` para sistemas pré-determinados; no Gacrux a flag muda o adversário virtual e o confronto direto (`gacrux/tiebreak.py:784,1043,1073,1588`). C.07 §16 [de memória: conferir].
- **Requisito:** `swiss = pairing_method == "swiss"`.
- **Aceite:** `prepare()` com `pairing_method="scheveningen"` gera `-p` nos argumentos.

### RG2-25 · Operações de várias gravações fora de transação · P2 · [E]
- **Origem:** R2.8 [E], R4.5 [E].
- **Evidência:** `pairing_service.py:960-982` (`set_player_participation`: status, evento e auditoria separados; `r2/partial.py`: `status gravado: withdrawn | eventos: 0`); `:1584-1636` (geração individual: rodada, retrato, auditoria, marca do motor reserva, status; `rodadas gravadas: [(1,'generated')] | status torneio: draft | eventos round_generated: 0`); [L] `forfeit_absent_player` (`:1258-1267`), `qr_result_service.approve_submission` (`:157-174`), `rating_service.apply_tournament_ratings` (`:817-819`). Na tela, "Todos presentes" (`pairing_results/initial_call.py:210-232`) para no primeiro desistente e deixa metade aplicada.
- **Cenário:** a rodada do motor reserva fica sem o aviso "não homologado" (RGS-18), que mora só no evento; o retrato por rodada, que lê os eventos, erra.
- **Requisito:** `with self.db.transaction():` em cada uma; "Todos presentes" pula os `withdrawn` (e diz quantos) e aplica numa transação. Extensão do teste do RGS-08: os métodos públicos com ≥ 2 chamadas de gravação são **descobertos por AST** (mesma definição do RG2-04), não listados à mão, e o teste reprova o que grava duas vezes fora de `transaction()`.
- **Aceite:** com falha injetada, nenhum estado parcial; "Todos presentes" com um desistente ativa os demais sem erro.

### RG2-26 · Configurações salvas que somem em silêncio · P2 · [E]
- **Origem:** R2.6.
- **Evidência:** `allowed_keys` em `src/core/database.py:1297-1336` não inclui `import_mapping_profiles` (gravado em `import_service.py:311,319`) nem `registration_form_prefill_base`/`registration_form_tournament_entry` (`export_players.py:238`). Script `r2/settings_drop.py`: `perfis depois de salvar: {}`.
- **Requisito:** as chaves entram na lista e chave desconhecida levanta `ValueError` (erro de programação, visível no teste).
- **Aceite:** `save_mapping_profile` seguido de `list_mapping_profiles` devolve o perfil; `save_app_settings({"x_inexistente": 1})` levanta.

### RG2-27 · Pontos de bye e de entrada tardia sem faixa de valores · P2 · [E]
- **Origem:** R2.7.
- **Evidência:** `tournament_service.py:676-681` só recusa negativo; `:821` não confere nada. `r2/points.py`, `points2.py`: bye `inf`, `0,3`, `7` gravados; `late_entry_points` `-1`, `inf`, `0,25` gravados; `nan` estoura `IntegrityError` cru.
- **Requisito:** `parse_points(text, allowed)` único na fronteira (`math.isfinite`, múltiplo de 0,5, faixa {0; 0,5; 1} para bye e por rodada perdida); substitui os `float(str(x).replace(",", "."))` de `tournament_service.py:677,821,861,875`.
- **Aceite:** os quatro casos levantam `AppError` com a faixa na mensagem.

### RG2-28 · Excluir torneio não faz backup nem deixa rastro · P2 · [L]
- **Origem:** R2.9.
- **Evidência:** `tournament_service.py:206-211`, `database_tournament_core.py:362-364`; `audit_events` tem `ON DELETE CASCADE` (`database_schema.py:814`).
- **Requisito:** `backup_before("delete_tournament", tid)` e evento em `audit_logs` (global), com nome e contagens; a confirmação diz o nome e o número de rodadas jogadas.
- **Aceite:** depois de `delete_tournament`, existe `*before_delete_tournament_t{id}*.db` e um registro de auditoria global.

### RG2-29 · Exportações para a FIDE: sexo, ASCII, fontes e TRF25 · P2 · [E]
- **Origem:** R5.6, R5.8, R5.9, R5.12.
- **Evidência:**
  - sexo sai `f` (`export_federation.py:873`, `sex[:1].lower()`), a spec pede `m`/`w` (`ESPEC_TRF25_FIDE.md:116`); as normas só reconhecem `F` (`norms/handbook.py:119`) e a importação grava `w` (`trf_import.py:176`) — jogadora vinda de Swiss-Manager nunca é avaliada para WGM/WIM;
  - o "ASCII" do TRF (`export_federation.py:564-570`, `trf25_records.py:31-35`) só tira marcas combinantes: `Øster`, `Łukasz` passam e o arquivo é UTF-8 (`trf16.py:72`) — um leitor que conta bytes desloca rating, FED e ID [H no impacto];
  - nenhum PDF registra fonte TTF: "Łukasz Ćwik Şahin Nguyễn" vira "■ukasz ■wik ■ahin Nguy■n" — o IT3, que exige estrangeiros, inclusive;
  - TRF25 individual sai com `082 0` (`trf25.py:229`), o 102 sem FIDE ID do árbitro (`:231-233` × `trf16.py:184-188`) e sem `_file_problems`; grava direto no destino (`:220`).
- **Requisito:** `normalized_sex` único (F→`w` na saída; `w`/`F` → feminino na leitura); tabela de transliteração (Ø→O, Ł→L, ß→ss, æ→ae…) + `encode("ascii","replace")` na linha 001; DejaVuSans empacotada e registrada nos escritores de PDF (diploma inclusive, revendo `ESPEC_DIPLOMAS.md:56`); o TRF25 reaproveita as linhas do TRF16 e grava em temporário + troca.
- **Aceite:** `sex="F"` sai `w` na coluna 10 e `applicable_norms("w")` inclui WGM; "Łukasz Øster" sai **"Lukasz Oster"** na linha 001 (não "?ukasz") e o FIDE ID fica nas colunas 58-68 contadas em bytes; o texto extraído do PDF contém "Łukasz"; TRF25 individual não tem 082.

### RG2-30 · Importadores de CSV só leem UTF-8 e leem sem teto · P2 · [E]
- **Origem:** R7.6 [L], R5.7 [E].
- **Evidência:** `import_service.py:782,828` e `rating_service.py:70,482` abrem com `utf-8-sig` sem alternativa (o TRF tem, `import_service.py:337-341`); `:800-801,851` fazem `response.read()` sem limite. `r5/t8`: CSV do Excel PT-BR (cp1252) com "João" → `UnicodeDecodeError` cru.
- **Requisito:** um `read_text_file(path)` único: `utf-8-sig` → `cp1252` → `AppError`; download com teto (10 MB) e `csv.Error` capturado.
- **Aceite:** o arquivo cp1252 importa "João"; byte inválido gera `AppError`, não `UnicodeDecodeError`.

### RG2-31 · Cada importação da lista FIDE acumula uma cópia inteira no banco · P2 · [E]
- **Origem:** R5.11; medido no banco real pela R10.
- **Evidência:** `database_tournament_core.py:886-914`; não existe `DELETE FROM official_*` em `src/`; parse inteiro em memória (`fide_list.py:95-117`). `r5/t3`: ≈ 168 B por jogador por importação. **Banco real:** 110 MB, dos quais 615.661 linhas em `official_players` (3 retratos); 10 backups ≈ 1,1 GB. Não é conforto: é o que torna a retenção (RG2-01) e o backup lentos e grandes.
- **Requisito:** a importação substitui o snapshot anterior da mesma fonte (guarda os 2 últimos), numa transação, com `executemany` em lotes; uma vez, depois da limpeza, `VACUUM` com aviso.
- **Aceite:** duas importações seguidas deixam ≤ 2 snapshots e `official_players` com no máximo duas listas; o banco real copiado cai para menos da metade do tamanho.

---

## 4. P2 — organização, clube e árbitro

### RG2-32 · Falhas silenciosas que o teste do RGS-32 não pega · P2 · [L]
- **Origem:** R6.4, R6.5, R6.7–R6.12.
- **Evidência e requisito, um por linha:**
  - `export_federation.py:245-249` — `except Exception: continue` tira uma rodada do pacote Access → capturar `AppError`, logar e devolver `warnings`.
  - `access_export.py:92-121` — `.accdb` parcial fica no disco e a conexão não fecha → `try/finally`, apagar o parcial, `logger.warning`.
  - `tiebreak_criteria.py:308-336` — sequência corrompida ou código desconhecido vira o padrão calado (`pairing_service.py:4126`) → devolver descartes e auditar.
  - `rating_service.py:380-382` — JSON de federações corrompido some e o próximo `add_foreign_federation` (`:393-401`) **sobrescreve** → abortar o `add`.
  - `rating/kfactor.py:39-43` — K inválido volta ao regulamento → validar na gravação.
  - `pairing/arbitration.py:129-136` — `round_id` ilegível bloqueia todas as rodadas sem log → `logger.warning`.
  - `ui/screens/tournaments/pages.py:915-916` — "Confirmar" do ritmo engole a exceção (`debug`) → `_show_error`.
  - `export_web.py:703-704` (QR some do site), `import_service.py:645-657` (nível inexistente → `None`), `member_service.py:466-472` (rating online inválido → 0), `rating_service.py:442` (`errors="replace"`) → aviso na lista de erros da operação.
- **Requisito geral:** `tests/test_rgs32_falhas_silenciosas.py` passa a reprovar também `except …: return None/[]/{}/0/False` e `except …: continue` sem justificativa na linha. A justificativa tem forma fixa — `# silencioso: <por quê> (<quem trata>)` — para que "um comentário qualquer" não passe; os 45 blocos já justificados pelo RGS-32 ganham a forma fixa no mesmo PR.
- **Aceite:** um teste por linha acima, observando o aviso (`caplog`, `warnings` do retorno ou `AppError`).

### RG2-33 · Prêmio indivisível e diploma por categoria divergem da premiação · P2 · [L]
- **Origem:** R8.6, R8.7.
- **Evidência:** `prizes.py:41-45,109-129` só conhecem `equal` e `hort`; `certificate_service.py:318-326,1007-1014,1025` usa só a categoria principal, ignora `prize_exclude_withdrawn` e dá 1º e 2º a empatados.
- **Requisito:** `tie_split="tiebreak"` (cada um recebe o valor da própria posição); o diploma `category_award` lê a **mesma** alocação da premiação (RG2-16), não recalcula.
- **Aceite:** empate em 5 pontos com 500/300 no modo "desempate decide" → 500 e 300; o diploma "1º Feminino" sai para quem recebeu o prêmio Feminino.

### RG2-34 · Desativar ou editar membro apaga dados · P2 · [E]
- **Origem:** R8.8.
- **Evidência:** `member_service.py:168-195` (desativar não repassa `lichess_username`, `chesscom_username` e ratings online) e `:427-496` (o payload de edição não tem `departure_*`); o UPDATE completo está em `database_members.py:154-230`. Script `r8`: `joaolx/1700` vira `''/0` ao desativar; mudar o telefone apaga o motivo de saída.
- **Requisito:** UPDATE parcial — só as colunas presentes no payload.
- **Aceite:** desativar e depois editar o telefone preserva os quatro campos e `departure_reason`.

### RG2-35 · Desligar o Modo Livre depois de jogado libera rating e TRF sem pergunta · P2 · [L]
- **Origem:** R8.10.
- **Evidência:** `friendly_mode.py:219-247` (`set_enabled` não olha rodadas); `trf16.py:64` e `rating_service.py:810-814` consultam só a marca atual.
- **Requisito:** com rodada gerada, desligar exige motivo; "já foi amistoso" (do evento `free_mode_changed`) mantém a pergunta antes do rating e o aviso no TRF.
- **Aceite:** desligar com R1 fechada e chamar `apply_tournament_ratings()` sem confirmação levanta `AppError`.

### RG2-36 · Fluxos do árbitro ainda com atrito · P2 · [L]
- **Origem:** R4.6–R4.10 e melhorias da R4.
- **Itens:**
  1. "Retirar do torneio…" com mesa aberta não avisa nem oferece W.O. (`player_actions/dialogs.py`; `set_player_participation`, `pairing_service.py:934`) → mostrar a mesa e oferecer "Lançar W.O. e retirar" (o `ByeDialog` já faz).
  2. A tabela de Rodadas não tem o menu do jogador (`view.py:386`) → no clique direito da mesa, "Corrigir resultado…" e os submenus "Brancas: …" / "Pretas: …" com `PlayerActions.menu_items`. É a queixa original do árbitro.
  3. Lançamento pelo painel sem "Desfazer" (`pending.py:277-296`) → o mesmo toast de `view.py:990`.
  4. Duplo clique numa mesa do painel abre Rodadas na primeira pendente (`pending.py:185`) → abrir na mesa clicada.
  5. "Trocar jogador" sem busca e, por equipes, sem motivo (`pairing_results/swaps.py`) → `search_combo` e motivo (RGS-16).
  6. "Rejeitar" QR sem confirmação (`qr.py:148`, `issues.py:244`).
  7. Depois de salvar, o cursor vai para a primeira pendente pelo botão e para a próxima linha pelo teclado → unificar em "próxima linha".
- **Aceite (um teste de janela por item):**
  1. retirar um jogador com mesa aberta mostra "A mesa X da rodada N continua sem resultado"; com a opção marcada, a mesa recebe o forfeit;
  2. clique direito numa mesa mostra "Retirar do torneio…" das brancas e abre o `WithdrawDialog` dele;
  3. depois de lançar 1-0 pelo painel existe um toast com ação, e a ação devolve `""`;
  4. duplo clique na mesa 5 do painel → `pairing_tree.selection()` aponta para a mesa 5;
  5. sem motivo, "Aplicar" na troca por equipes recusa;
  6. "Rejeitar" QR abre confirmação; cancelar não muda o envio;
  7. salvar pelo botão e pelo teclado deixam o cursor na mesma linha seguinte.

### RG2-37 · Contas do aplicativo: senha padrão e normalização · P2 · [L]
- **Origem:** R7.5, R7.12.
- **Evidência:** `legacy_migrations.py:783-796` cria `admin`/`admin` quando não há administrador, sem troca obrigatória; `ui/app.py:394` faz `strip()` na senha do login e `security_service.py:69-75` grava sem `strip()` — senha com espaço na ponta nunca entra; papel não validado contra `ROLE_PERMISSIONS`; sem atraso após falhas; login falho não é auditado (`security_service.py:61`).
- **Requisito:** em **banco novo**, o primeiro acesso exige definir a senha do admin, e o fluxo de troca na tela de login entra no mesmo item; banco existente não é marcado (o banco real só tem `admin`: marcar sem o fluxo trancaria o dono fora — R10, objeção 9). Nenhum `strip()` na senha; papel validado; atraso progressivo e auditoria de falha.
- **Aceite:** em banco novo, `login("admin", "admin")` devolve `False` até a senha ser definida pela tela; um banco existente migrado continua entrando com a senha que tinha; `create_user("x", " abc ", "viewer")` + `login("x", " abc ")` → `True`; papel inexistente → `AppError`.

### RG2-38 · Sincronização: meio funcionalidade, sem autenticação, com fila que só cresce · P2 · [L]/[E]
- **Origem:** R7.4, R2 (melhoria 5); corrigido pela R10 (não é código morto).
- **Evidência:** `sync_service.py:163-168` aceita `payload_hash` vazio e usa SHA-256 sem chave; `secret_hash` (`database_sync_audit.py:130`) nunca é conferido; `apply_remote_event` (`:109`) não tem chamador em `src/` e grava por `db.update_pairing_result` direto, por fora do `PairingService`. **Mas:** a tela de Integrações usa `register_device`, `list_devices`, `revoke_device` e `sync_pending` (`ui/screens/integrations.py:89,147,198,220,238,298`); **todo** evento de auditoria grava uma linha em `sync_outbox` (`database_sync_audit.py:461-476`) — 416 pendentes no banco real, com a sincronização desligada [E]; `test_core_arbitration.py` (≈ 20 chamadas) e `test_core_qr_portal.py:24` usam `apply_remote_event`.
- **Requisito:** a **D5** decide a funcionalidade inteira — fila, dispositivos, tela, alertas do painel e o acoplamento com a auditoria. *Subtract before you add:* se sair, sai tudo (inclusive a gravação em `sync_outbox` a cada evento e os testes que a exercitam); se ficar, HMAC com o segredo do dispositivo, passagem pelo `PairingService` e a fila só grava com um dispositivo registrado.
- **Aceite:** removida — nenhum símbolo de sync em `src/` e `tests/`, e auditar um evento não cria linha em `sync_outbox`; mantida — `payload_hash=""` → `rejected` e, sem dispositivo, a fila não cresce.

---

## 5. P3 — polimento e dívida

### RG2-39 · Agenda e categorias aceitam o impossível · P3 · [E]/[L]
- `tournament_service.py:176-206` aceita idade 15 a 12, sexo em branco e marca vazia (R8.11 [E]) → recusar.
- `rest_day` só existe no banco e na tela (`tournament_settings_ui.py:862`); `generate_round_schedule` (`tournament_service.py:1068-1133`) ignora a folga; `_validated_schedule` (`:1001-1066`) aceita R3 antes da R2 (R8.12 [L]) → o gerador pula a folga e a validação exige ordem não decrescente.
- `update_tournament_details` apaga a agenda acima do total sem perguntar (`database_tournament_core.py:164-170`) — a proteção mora só no serviço.
- `reference_year` cai em `created_at` (`core/categories.py:63-69`) e erra o ano de torneio criado em dezembro para janeiro → avisar quando falta `start_date`.
- **Aceite:** um teste por linha.

### RG2-40 · Concorrência e limites · P3 · [L]/[H]
- O Gacrux roda dentro de `BEGIN IMMEDIATE` no fechamento (`pairing_service.py:2848-2860`), contra o próprio docstring de `:3337-3340` → calcular antes e conferir o estado dentro da transação (R2.11).
- Não há trava de instância única; `qr_result_service.submit_result` (`:110-142`) confere e insere sem transação nem `UNIQUE` → índice `UNIQUE(pairing_id) WHERE status='submitted'` e arquivo de trava ao lado do `.db` (R2.12).
- `submitter` sem limite de tamanho (`result_server.py:44`) → truncar em 80 (R7.8).
- **Aceite:** com `_standings` lento simulado (6 s), uma gravação de outra thread conclui; dois envios simultâneos da mesma mesa → 1 pendente.

### RG2-41 · Segredos e dados pessoais · P3 · [L]
- DPAPI que falha devolve o valor em claro, calado (`database.py:1230-1260`) → `AppError` ou aviso (R7.10).
- Chave HMAC do QR derivada de `operator_name + db_path` (`qr_result_service.py:262-265`) → `secrets.token_bytes(32)` por instalação, protegido por DPAPI (R7.7).
- `Listas Jogadores CBX/ListaJogadoresEmDiaCBX.xls` está versionado (`git ls-files`) → `.gitignore` + `git rm --cached`; avaliar o histórico (**D6**) (R7.11).
- O log de falha do verificador Gacrux (`gacrux_engine.py:~596`) grava o TRF inteiro, com nomes e IDs → gravar hash e caminho.
- PDF pedagógico passa texto do usuário ao `Paragraph` sem escape (`education_service.py:768-808`) → `xml.sax.saxutils.escape` (R7.9 [H]).

### RG2-42 · Higiene do repositório e dos testes · P3 · [E]/[L]
- `tests/test_dup_check_tmp.py` sem asserção (R9.1, coberto em RG2-17); testes sem `assert` explícito a conferir: `test_column_layouts.py:195`, `test_core_org04.py:156`, `test_ui_rgs28_scaling.py:102` (R9.2 [H]).
- `create_tournament` sorteia a cor inicial (RGS-14) e os testes de pareamento ficam não reprodutíveis → fixar `initial_color` nos testes.
- `.gitattributes` com `eol` explícito (o diff de hoje tem 40+ avisos LF→CRLF) — **antes** dos commits da D7, senão os 6 commits carregam ruído de fim de linha (R10).
- Os 38 pares do dryer (seção 1): eliminar os de domínio — `optimal_player_pairs`/`optimal_team_pairs` (0,99), `search_dutch_*` (0,92), `solve` (0,88), `_round_robin_round`/`_scheveningen_round` (0,89), `_requested_bye_records_240` (0,91), `show_rating_history` em duas telas (0,98), `fetch_lichess/chesscom_ratings` (1,00). Os ≈ 840 pares de `list_*` de SQL que só diferem no texto da consulta **ficam**: o dryer normaliza o texto para `S`, e ali a diferença é a consulta.
- Crapper: as funções com CRAP ≥ 100 (seção 1) são partidas ou testadas na fase em que forem tocadas; as de importação, já na Fase 3 (o teste delas é o aceite de RG2-13/14/30).

---

## 5A. Achados da 10ª revisão

### RG2-43 · A auditoria registra "Administrador" para qualquer usuário logado · P2 · [E]
- **Origem:** R10 (N1).
- **Evidência:** `database_sync_audit.py:99-103,416-418` leem o operador de `app_settings`; `security_service.py:56` guarda o usuário logado só em memória. `r10/actor.py`: logado como `monitor` (`viewer`), o `result_updated` sai com ator `'Administrador'` e papel `'admin'`, enquanto `audit_logs` diz `monitor`. `pairing_results/knockout.py:74` usa `host.current_user_name`, que não existe, e grava `""`.
- **Cenário:** numa apelação, a correção de resultado aparece como feita pelo admin.
- **Causa-raiz:** duas fontes de "quem é o operador".
- **Requisito:** o provedor de operador do `Database` (o mesmo do RG2-04), definido por `SecurityService.login`, é a única fonte; `app_settings` deixa de ser lido para isso.
- **Aceite:** login como `arb` (papel `arbiter`) e `update_result` → o evento tem ator `arb` e papel `arbiter`; o avanço de eliminatória grava o nome do operador.

### RG2-44 · Fechar o aplicativo logado como árbitro não faz backup · P2 · [E]
- **Origem:** R10 (N2).
- **Evidência:** `app.py:196-200` chama `create_backup("auto_shutdown")`, que exige `settings_write` (`security_service.py:257`); o papel `arbiter` não tem. O erro vai só para o log. `r10/shutdown_arbiter.py`: "Permissão negada", nenhum arquivo.
- **Cenário:** o árbitro fecha o programa depois da última rodada; não fica backup de fechamento.
- **Causa-raiz:** um fluxo do sistema passa pela permissão do usuário.
- **Requisito:** o fechamento chama `db.backup` + retenção (RG2-01) sem checar permissão; a permissão fica só no backup manual.
- **Aceite:** logado como `arbiter`, fechar cria `*auto_shutdown*.db`.

### RG2-45 · O QR impresso aponta para `localhost` · P2 · [L]
- **Origem:** R10 (N3).
- **Evidência:** `result_server.py:24` devolve `localhost` quando o bind é `0.0.0.0`; `pairing_results/qr.py:55-56` e `pairing_arbitration/exports.py:153` gravam esse endereço em `local_result_server_url`; `export_renderers.py:563,572` monta o QR a partir dele; não há tela para mudar o endereço. O documento de projeto espera `192.168…` (`sistema_arbitragem_xadrez_v2_revisado.md:388`).
- **Cenário:** o celular lê o QR da súmula, abre `http://localhost:8765/resultado` e falha.
- **Requisito:** ao publicar na rede, detectar o IP da rede local (e deixar escolher quando houver mais de um); o QR usa esse endereço. Anda junto com o RG2-19.
- **Aceite:** com bind `0.0.0.0`, a `url` não contém `localhost` e o QR gerado usa o IP escolhido.

### RG2-46 · Valor em dinheiro com ponto de milhar vira centavos · P1 · [E]
- **Origem:** R10 (N4); mesma causa do RG2-14.
- **Evidência:** `finance_service.py:468-471`, `prize_service.py:70`, `inventory_service.py:289`. `r10/money.py`: mensalidade `"1.500"` → 1,5; prêmio `"1.000"` → **1,0**; `"nan"` e `"inf"` aceitos.
- **Cenário:** o 1º prêmio digitado "1.000" vira R$ 1,00 no relatório de premiação.
- **Causa-raiz:** o ponto de milhar brasileiro lido como decimal.
- **Requisito:** `parse_decimal_br` único na fronteira, compartilhado com `parse_rating` (RG2-14) e `parse_points` (RG2-27): ponto como milhar quando seguido de exatamente 3 dígitos e há vírgula ou nada depois; vírgula como decimal; recusa valor não finito. Ambíguo ("1.5") → erro que pede "1,5" ou "1.500".
- **Aceite:** "1.500" → 1500,00; "1.500,50" → 1500,50; "1,5" → 1,50; "nan" → `AppError`.

### RG2-47 · O cadastro de membro não tem sexo · P2 · [L]
- **Origem:** separado do RG2-15 pela R10 (objeção 5).
- **Evidência:** `members` não tem `sex` (`database_schema.py:56-85`); a inscrição a partir do membro não passa sexo (`database_members.py:521-541`); o Modo Livre inscreve turmas inteiras assim (`friendly_mode.py:191-195`) — a classificação feminina dessas turmas sai vazia.
- **Requisito:** migração `members.sex` (vazio permitido); campo no formulário de membro, na importação CSV e no mapeamento do Google Forms; repassado na inscrição.
- **Aceite:** membro com `sex="F"` inscrito num torneio com categoria Feminino → `categories` contém "Feminino"; banco antigo migra com `sex` vazio e nada muda na classificação.

---

## 6. Decisões em aberto

| # | Questão | Recomendação | Quem decide |
|---|---|---|---|
| D1 | Ordem da alocação de prêmios não cumulativos (RG2-16) | Do maior valor para o menor; empate de valor → ordem do edital | Dono + árbitro |
| D2 | Categoria "até X" aceita quem está abaixo (RG2-18)? | Opção por categoria, **desligada** por padrão (o comportamento atual); o árbitro liga conforme o edital | Árbitro |
| D3 | Recalcular categoria depois da 1ª rodada fechada (RG2-15)? | Sim, com confirmação e auditoria; recusar se houver certificado emitido ou o torneio estiver encerrado | Árbitro |
| D4 | Portal na rede local (RG2-19, RG2-45)? | Sim quando publicado (é para os pais na Wi-Fi), só no modo público e só o torneio publicado; `privado` só nesta máquina | Dono |
| D5 | Sincronização (RG2-38): sai inteira ou fica completa? | Sai inteira — fila, dispositivos, tela e a gravação em `sync_outbox` a cada evento — salvo plano concreto de uso | Dono |
| D6 | Limpar o histórico git da lista CBX (RG2-41)? | Só se o repositório for público | Dono |
| D7 | Como commitar os ≈ 335 arquivos da Revisão Geral Suíço antes da RG2 | `.gitattributes` primeiro; depois 6 commits ordenados (seção 7.1); `build.bat` + `--self-test` no fim | Dono |
| D8 | Importar TRF de torneio **em andamento** é uso suportado (RG2-13)? | Sim: é o caminho para continuar no Albericus um torneio começado no Swiss-Manager | Dono + árbitro |

---

## 7. Fora do código

### 7.1 O trabalho não commitado vem primeiro

A RG2 não começa por cima de 335 arquivos soltos: cada PR dela ficaria ilegível. O roadmap abre com a entrega do trabalho anterior em commits revisáveis (sugestão da R9): (a) acentuação pura, gerada por script; (b) infraestrutura do `.exe`; (c) migrações v56–v59 e `MigrationEngine`; (d) pareamento e Gacrux; (e) UI e i18n; (f) testes. Antes, `build.bat` e `--self-test` (o `.exe` testado é o do commit).

### 7.2 Pendências da RGS que continuam valendo
F0.3/F0.6 (replay com os arquivos do árbitro) e F2.8 (sessão com o árbitro) seguem abertas e não são repetidas aqui.

---

## 8. O que está sólido e não se mexe

As revisões olharam e não acharam problema em (cada um ganha teste de caracterização antes de ser tocado por outro item):

- `Database.transaction()`/`connect()` reentrantes com SAVEPOINT por thread; `MigrationEngine` por versão; migração dos backups reais v44 e v55 → v59 com `integrity_check` ok e 0 violações de FK (R2, R9).
- Pareamento individual pelo Gacrux: 8 sementes × 7 rodadas com bye H/Z, W.O., desistência e entrada tardia — zero reencontro, PAB repetido, 3 cores iguais ou diferença > 2 (R3).
- Ctrl+Z, W.O. por tecla, diálogo de correção, fechar e excluir rodada (R4).
- Subprocesso do Gacrux sem `shell`, SQL com `?`, sem `pickle`/`eval`, restauração confinada, `html.escape` no site, `_safe_name`, PBKDF2 210 mil (R7).
- Posições da linha 001, células, 132 e 013 do TRF16; tabelas B.02; limiares B.01 (R5).
- Hort, bordas de idade e rating, mensalidade idempotente, `date_review` (R8).
- Pares acentuados produtor/consumidor; registros de largura fixa sem acento (R9).

---

## 9. As dez revisões

| # | Lente | Quem | Saída |
|---|---|---|---|
| 1 | Linha de base executada: gate, suíte, cobertura, crapper, dryer | consolidação | seção 1 |
| 2 | Integridade de dados, transações, migrações, backup | agente independente | 12 achados (4 P1) |
| 3 | Emparceiramento e desempates (FIDE) | agente independente | 7 achados (2 P1) |
| 4 | Fluxos do árbitro na interface (click-path) | agente independente | 10 achados (4 P1) |
| 5 | Exportações, federação, rating, normas, certificados | agente independente | 12 achados (4 P1) |
| 6 | Falhas silenciosas | agente independente | 12 achados (3 P1) |
| 7 | Segurança e dados que entram de fora | agente independente | 12 achados (2 P1) |
| 8 | Organização, categorias, prêmios, clube | agente independente | 12 achados (5 P1) |
| 9 | Regressões no trabalho não commitado | agente independente | 2 achados (P3); nenhuma regressão grave |
| 10 | Crítico adversarial da v1, com o banco real copiado | agente independente | 12 P1 testados (0 refutados, 5 parciais), 12 objeções, 4 achados novos — Anexo A |

Cada agente recebeu só a lente, o escopo e as regras (somente leitura, evidência marcada), sem a hipótese dos outros. As sobreposições independentes reforçam o achado: "entrante tardio em 1º" (R3 e R6), "fórmula no CSV" (R5 e R7), "permissão só na tela" (R4 e R7), "`or 1.0`" (R2 e R3).

## Anexo A — 10ª revisão (crítico adversarial) e como foi tratada

O crítico testou 12 dos 20 P1 da v1 (scripts em `docs/revisao_geral_2/repro/r10/`: `actor.py`, `shutdown_arbiter.py`, `money.py`, `realdb.py`, `size.py`, `outbox.py`, `cols.py`). Nenhum caiu por inteiro; tentou derrubar RG2-01, 06, 07, 16 e 17 e não conseguiu, e procurou guarda no chamador para RG2-01 e no serviço para RG2-04 sem achar.

### Vereditos e o que mudou

| Item | Veredito | Tratamento na v2 |
|---|---|---|
| RG2-19 | Parcial: "dados privados" exagerava; o vazamento real é torneio não publicado | P1 → **P2**; D4 revista (o portal é para a rede); `build_app` para testar; junto com RG2-45 |
| RG2-04 | Parcial: confirmado no serviço, mas o banco real tem um usuário | P1 → **P2**; operador num provedor do `Database`; isenções de sistema; varredura por AST |
| RG2-11 | Confirmado no TRF (163/300 no banco real); exagerado nas normas | P1 no TRF/072, P2 em normas/IT3 |
| RG2-15 | Confirmado | Gancho concreto da D3; retratos ficam com a categoria da época; `members.sex` virou RG2-47 |
| RG2-16 | Confirmado (script era `t1`) | Regra de empate antes da trava; números exatos no aceite |
| RG2-18 | Parcial: escolha de projeto, não bug; a premissa da D2 sobre rating era falsa | P1 → **P2** funcionalidade; opção desligada por padrão |
| RG2-13 | Confirmado; o 132 atenua | D8 decide se torneio em andamento é suportado; aceite cita rank e linha |
| RG2-07 | Confirmado, 3/10 (não 5/10) + 1 sem alternativa; 3 cores seguidas [E] | Dividido em 07a (guarda, P1, hotfix) e 07b (motor único, P2) |
| RG2-10 | Parcial: só a divisão é realista | P1 → **P2**; PR de fronteira numérica |
| RG2-06 | Confirmado; requisito (2) excessivo | `standings()` não muda de recorte; a seção "Entram na rodada N" é só da tela |
| RG2-17 | Confirmado (script era `t4`) | Lista de exclusão completa (`fide_event_id` e outros) |
| RG2-01 | Confirmado, com nuance | Ligado ao RG2-44 e ao RG2-31 |

### Objeções aceitas

1. **Permissão no serviço** tiraria poder do árbitro e bloquearia fluxos do sistema → isenções explícitas e `delete_records` só para globais (RG2-04).
2. **Portal só local** mataria o portal e o QR → D4 revista (RG2-19, RG2-45).
3. **Recorte de `standings()`** afetaria TRF, tabela cruzada, certificados, site e rating → só a chave e a tela mudam (RG2-06).
4. **Prêmios × Hort** → empate divide primeiro, trava depois (RG2-16).
5. **Categorias × retratos** → retrato é retrato; gancho da D3 concreto (RG2-15).
6. **Duplicação levaria o `fide_event_id`** → lista de exclusão (RG2-17).
7. **Sincronização não é código morto** → D5 decide a funcionalidade inteira (RG2-38).
8. **Neutralizar célula estragaria telefone** → `data_type='s'` no XLSX, `'` só no CSV e retirado na importação (RG2-20).
9. **Senha obrigatória trancaria o dono fora** → só banco novo, fluxo de troca no mesmo item (RG2-37).
10. **Aceites fracos** → reescritos em RG2-29 (`Lukasz`, não `?ukasz`), 13 (cita rank e linha), 25 e 04 (AST), 32 (forma fixa), 19 (`build_app`), 36 (um aceite por item).
11. **Sequência** → 07 dividido; fronteira numérica num PR (10, 14, 27, 46); 04/43 antes de itens que criam métodos auditados (ou, como o provedor é central, eles se beneficiam sem retrabalho); 16 antes de 18 e 33; 31 junto com 01; `.gitattributes` antes da D7.
12. **Citações erradas** (`t4`/`t1`, `t5`/`t4`, "5 de 10") → corrigidas.

### Achados novos
RG2-43 (auditoria com operador errado), RG2-44 (sem backup ao fechar como árbitro), RG2-45 (QR com `localhost`), RG2-46 (dinheiro "1.000" → 1,00 — **P1**) e RG2-47 (sexo do membro, separado do RG2-15).

## Anexo B — Log de ações desta revisão

| Ação | Por quê |
|---|---|
| `refs/backup/antes-rg2` com a árvore inteira (índice temporário, sem tocar a árvore) | 335 arquivos não commitados; nada pode se perder durante a revisão |
| Gate `-Fast` + suíte completa com `coverage --source=src` | Linha de base executada antes de qualquer opinião |
| Crapper e dryer sobre `src/` sem Gacrux | Achar onde a falta de teste e a duplicação coincidem com os achados |
| 8 revisores independentes em paralelo, somente leitura, rascunhos no scratchpad | Lentes separadas, sem ancorar uma na outra |
| Reprodução própria de RG2-02, 03 e 05 (sondas da R4) e leitura de RG2-01, 06 e 11 | Não aceitar [E] de terceiros sem conferir os mais graves |
| Conferência de que a R9 não gravou backup na pasta real | O próprio revisor avisou do risco; últimos backups de 11/11 e 15/05 |
| Consolidação de ≈ 110 achados brutos em 42 requisitos (v1) | Duplicatas entre lentes viram um item com várias origens |
| 10ª revisão adversarial sobre a v1, com cópia do banco real | Testar severidade contra o uso real, não só contra o código |
| Reescrita para a v2: 4 rebaixamentos, 1 divisão (07a/07b), 5 itens novos, 8 aceites reescritos, D2/D4/D5/D7 revistas, D8 nova | Incorporar a 10ª revisão |
| Nenhuma mudança em `src/` ou `tests/` | O pedido foi análise, spec e roadmap; a implementação começa pela Fase −1, que depende da D7 |
