# Roadmap — Revisão Geral Suíço

> **Fonte executiva:** `ESPEC_REVISAO_GERAL_SUICO.md` (v2). Cada item aponta para um `RGS-NN`; o requisito e o critério de aceite moram **só** na spec. Este arquivo define **a ordem** e **o porquê**.
> **Versão:** v2, 2026-11-26. A sequência foi corrigida depois da 5ª revisão.

## Princípios de sequência

1. **Primeiro o que o árbitro recebe.** O `.exe` tem de ser o programa testado (Fase 0).
2. **A ferramenta de verificação antes da mudança.** O self-test e o replay nascem na Fase 0 e são o portão de todas as fases (*Build the Lever*).
3. **O dado antes da tela.** As transações e as datas (Fase 1) vêm antes dos fluxos novos (Fase 2), que gravam em cima delas.
4. **Um RGS por PR, teste primeiro.** Cada commit diz por quê, o que mudou e como foi provado.
5. **O que a spec, seção 8, declara sólido ganha teste de caracterização antes de ser tocado.**

## Visão geral

| Fase | Tema | RGS | Release | Esforço estimado |
|---|---|---|---|---|
| **0** | O `.exe` é o programa testado + ferramentas de verificação | 05, 02, 01, 03 (contenção), 04, 37, replay | **hotfix** | 1,5–2 semanas |
| **1** | Datas únicas, gravação atômica, concorrência | 06, 33, 07, 08 (+WAL), 09, 11, 36, 10, 12, 35 | +1 | 3–4 semanas |
| **2** | Árbitro prático: a ação onde está o objeto | 26, 20, 34, 21, 22, 23, 25 | +2 | 2–3 semanas |
| **3** | Conformidade FIDE do emparceiramento | 03 (definitivo), 13, 15, 19, 16, 17, 18, 14, **24** | +3 | 2–3 semanas |
| **4** | Polimento e dívida | 27, 28, 29, 30, 31, 32 | contínuo | — |

A estimativa é para uma pessoa com o agente; `Database.transaction()` sozinha toca 258 blocos de conexão, e por isso a Fase 1 é a mais longa.

**Por que o RGS-24 (entrada tardia) está na Fase 3:** com 0,5 ponto de entrada, o Gacrux só aceita depois do RGS-03 definitivo. Fazer a tela antes entregaria um botão que falha.

---

## Fase 0 — Contenção

**Objetivo verificável:** `Albericus.exe --self-test` retorna 0. O replay dos torneios de `exports/` roda e registra a linha de base de divergências.

| Passo | Item | Entrega | Prova |
|---|---|---|---|
| F0.1 | RGS-05 | `--self-test <dir>` → `selftest.json` + código de saída; `build.bat` falha com `errorlevel`, sem `pause` | Com o código atual: saída ≠ 0, `i18n` e `gacrux` falhos (o teste vermelho da fase) |
| F0.2 | RGS-37 | Marcador `-m gacrux` e CI/DoD rodando pareamento e desempate com o motor padrão | A suíte `-m gacrux` roda; os cenários do RGS-03 aparecem vermelhos |
| F0.3 | Replay | `scripts/replay_torneio.py` (spec §11) | A linha de base gravada em `docs/REPLAY_BASELINE.md` |
| F0.4 | RGS-02 | `resource_path()` única para recursos empacotados | Passo `i18n` verde |
| F0.5 | RGS-01 | Gacrux como subprocesso `--gacrux` do próprio `.exe`; scripts como `datas`; medir onefile × onedir (decisão D1) | Passos `gacrux` verdes; 0 eventos `tiebreak_engine_fallback` |
| F0.6 | — | **Pedido ao árbitro:** `app.log`, `.db` e versão do executável | Resolve as hipóteses α/β/γ (spec §1.1); o TRF dele entra no replay |
| F0.7 | RGS-03 contenção | `assert_trf_scores_consistent` depois de `reconcile_scores`; recusa clara; oferta do motor reserva com auditoria | Os cenários do RGS-03 viram mensagem ou geração, nunca exceção crua |
| F0.8 | RGS-04 | `report_callback_exception` → log + diálogo | O teste do spy |
| F0.9 | — | Nota de release com **contorno até a Fase 1**: "para corrigir resultado use a tela Rodadas (desbloqueio na hora); evite *mudanças perigosas*; se uma data aparecer estranha (ex.: 20/26/1113), redigite antes de salvar; evite bye de 0,5 até a versão +3" | Texto revisado pelo árbitro |

**Fora da Fase 0, de propósito:** o leitor de pontos do Gacrux (Fase 3), a varredura dos 67 `except: pass` (RGS-32) e qualquer mudança de tela.

### Andamento da Fase 0 (2026-11-26, branch `fix/rgs-fase0-exe`)

| Passo | Estado | Prova |
|---|---|---|
| F0.1 RGS-05 | **feito** | `src/selftest.py`; `app.py --self-test <pasta>`; `build.bat` sai com o código do autoteste, sem `pause`. No `.exe` gerado: 5/5 passos, código 0 |
| F0.2 RGS-37 | **feito** | Marcador `gacrux` no `pyproject.toml`; 5 arquivos marcados; `pytest -m gacrux` verde. Achado no caminho: `test_stress_10k_tournaments.py` desligava o log da suíte inteira na importação (agora só no próprio módulo) |
| F0.3 Replay | pendente | Só há 1 TRF em `exports/`; depende do F0.6 e do `bbpPairings` |
| F0.4 RGS-02 | **feito** | `src/core/resources.py` (`bundled_resource`), usado por `i18n` e `support.resource_path`. O teste simula o congelado **antes** de importar o `i18n`: vermelho com o código antigo, verde com o novo |
| F0.5 RGS-01 | **feito** | `gacrux_runner.py`: `[python, script]` no desenvolvimento, `[Albericus.exe, --gacrux, pairing\|tiebreak]` no `.exe`. Scripts do Gacrux em `datas`; imports externos (incl. `networkx`, que também faltava) varridos do código no `.spec`. **D1 decidida: onefile** (≈0,55 s por rodada no `.exe`, abaixo de 1 s) |
| F0.6 | **aguarda o árbitro** | — |
| F0.7 RGS-03 contenção | **feito** | `GacruxScoreMismatch` antes do motor; a tela oferece "Parear com o motor reserva" e grava `pairing_engine_fallback` **depois** da rodada salva. Matriz bye {0, 0,5, 1} × {sem ajuste, ±0,5, entrada tardia} × 4 rodadas: bye 1 sem ajuste e entrada tardia saem 100% Gacrux; os demais recusam da R2 em diante. Achado: bye **0** também quebrava (R3), não só 0,5. *Superado pelo F3.1: esses casos agora saem pelo Gacrux* |
| F0.8 RGS-04 | **feito** | `AlbericusApp.report_callback_exception` → log com traceback + diálogo |
| F0.9 | rascunho | `NOTA_RELEASE_RGS_FASE0.md`, para revisão do árbitro |

---

## Fase 1 — Datas, atomicidade e concorrência

**Objetivo verificável:**
- o teste do incidente (F1.12) passa;
- nenhuma data muda sem ser digitada;
- nenhuma gravação de configuração, correção, fechamento ou importação fica pela metade.

1. **F1.1 RGS-06 (domínio).** `src/domain/dates.py` com `parse_date` e a tabela de casos, **antes** de mexer no widget.
2. **F1.2 RGS-06 + RGS-33 (widget).** `MaskedDateEntry` com `parse_date`, `permite_ano` no nascimento e `has_invalid()`; os formulários recusam salvar.
3. **F1.3 RGS-06 (dados legados).** Relatório "Datas a revisar" na abertura e normalização dos convertíveis com backup. **Rodar na cópia do `.db` de 11/11** e anexar o relatório ao PR.
4. **F1.4 RGS-07.** Todas as fronteiras com `parse_date`; o 132 continua `AA/MM/DD`; teste-varredura.
5. **F1.5 RGS-08 (base).** `Database.transaction()` reentrante por thread, com WAL e `busy_timeout`; o comportamento antigo continua como padrão.
6. **F1.6 RGS-08 (caso de uso).** `save_tournament_configuration` valida tudo e grava tudo, com backup. A importação TRF passa a usar a mesma transação.
7. **F1.7 RGS-09.** `plan_tournament_configuration` + diálogo único + auditoria na transação.
8. **F1.8 RGS-11.** `close_round` idempotente e atômico; backup com nome único.
9. **F1.9 RGS-36.** Chave do cache Gacrux = hash do TRF.
10. **F1.10 RGS-10.** Correção atômica com backup; `reconcile_pending`; trabalhador idempotente; retrato N só com dados ≤ N; guardas do Gacrux seguras para threads.
11. **F1.11 RGS-12 + RGS-35.** Calendário sem grab; o "ausente" volta a concorrer a prêmio.
12. **F1.12 Teste do incidente.**
    - **Preparação:** torneio com `birth_date="2010/05/12"` e `"1985"`, agenda com `2026-11-13 08:00` e prêmio em branco.
    - **Passos:** fechar a R1, ligar *mudanças perigosas* e salvar.
    - **Esperado:** recusa clara, **nenhuma** coluna alterada.
    - **Depois:** corrigir pela tela Rodadas → 1 correção e retratos reconciliados.

**Risco principal:** a `transaction()`. Mitigação: conexão por thread opcional e migração caso a caso, começando pelos 3 caminhos da spec (configuração, correção e fechamento).

**Andamento da Fase 1 (2026-11-26):**

| Passo | Estado | Prova |
|---|---|---|
| F1.1 RGS-06 domínio | **feito** | `src/domain/dates.py`: `parse_date` → `DataVazia \| Data \| Ano \| DataInvalida`; `tests/test_dates.py` |
| F1.2 RGS-06 + 33 widget | **feito** | `MaskedDateEntry.value()`/`has_invalid()`/`permite_ano`; os formulários recusam salvar; `test_ui_date_entry.py`, `test_ui_rgs_date_forms.py` |
| F1.3 dados legados | **feito no código**; falta rodar no `.db` de 11/11 (F0.6) | `services/date_review.py` (relatório + normalização com backup); a tela inicial mostra "N datas a revisar"; `test_rgs06_legacy_dates.py` |
| F1.4 RGS-07 | **feito** | Fronteiras com `parse_date`; o 132 continua `AA/MM/DD`; varredura com lista fechada de exceções em `test_rgs07_date_boundaries.py` |
| F1.5 RGS-08 base | **feito** | `Database.transaction()` reentrante (BEGIN IMMEDIATE / SAVEPOINT), conexão por thread, WAL, `busy_timeout` 5000; backup e restauração pela API de backup do SQLite; `test_rgs08_transacao.py` |
| F1.6 + F1.7 RGS-08/09 | **feito** | `services/tournament_configuration.py` (`plan_tournament_configuration`), `save_tournament_configuration` valida e grava tudo com backup; diálogo único; importação TRF numa transação; `test_rgs08_09_configuracao.py` |
| F1.8 RGS-11 | **feito** | `close_round` idempotente e atômico; backup com nome único; `test_rgs11_fechar_rodada.py` |
| F1.9 RGS-36 | **feito** | Chave do cache = sha256 do TRF; `inflight` por thread; `test_rgs36_cache_gacrux.py` |
| F1.10 RGS-10 | **feito** | `_commit_result` atômico; `reconcile_pending_snapshots` + `snapshot_reconciler.py` idempotente; retrato N só com dados ≤ N (`standings_cut.py`, `players.entry_round`); schema v56; `test_rgs10_correcao_atomica.py`, `test_ui_rgs10_reconciliacao.py` |
| F1.11 RGS-12 + 35 | **feito** | Calendário sem grab (F4, Alt+↓, ▾); "ausente" concorre a prêmio; `test_rgs35_prize_absent.py` |
| F1.12 teste do incidente | **feito** | `test_ui_rgs08_09_configuracao.py`: recusa clara, nenhuma coluna alterada, correção pela tela Rodadas reconcilia os retratos |

---

## Fase 2 — Árbitro prático

**Objetivo verificável:** um teste de UI por tarefa da spec §5 conta as ações (`invoke`/teclas) e respeita o máximo da tabela. Nenhuma das tarefas cria a tela de Configurações.

1. **F2.1 RGS-26.** Faixa fixa para erro de regra, com ação sugerida. Os diálogos seguintes recusam por ela.
2. **F2.2 RGS-20.** "Corrigir resultado…" (menu de contexto/Shift+F10/Ctrl+E, um motivo, cascata com "Reparear" e "Reverter esta correção…"). "Mudanças perigosas" vai para "Avançado", gravando sozinha.
3. **F2.3 RGS-34.** Excluir rodada com resultados exige motivo e guarda os resultados no evento. *(Pré-requisito do "Reparear" com resultados lançados.)*
4. **F2.4 RGS-21.** Desfazer (Ctrl+Z), contador e W.O. por tecla.
5. **F2.5 RGS-22.** Menu do jogador: "Faltar só à rodada N…" (bye Z), "Retirar do torneio…" e "Reintegrar…"; `db.update_player` sem `status`.
6. **F2.6 RGS-23.** Bye solicitado na linha do jogador; combobox com busca nos seletores.
7. **F2.7 RGS-25.** Botão primário com estado e confirmação de fechamento.
8. **F2.8 Sessão com o árbitro.** Ele executa as tarefas num torneio de teste sem instrução. O que travar vira item antes do release.

**Andamento da Fase 2 (2026-11-26):**

| Passo | Estado | Prova |
|---|---|---|
| F2.1 RGS-26 | **feito** | `components/rule_banner.py`; `AppError(..., suggestion=)`; chaves `banner.rule.*` |
| F2.2 RGS-20 | **feito** | `pairing_results/correction.py`: clique direito/Shift+F10/Ctrl+E abrem "Corrigir resultado…" direto; um motivo; cascata com "Reparear"; "Reverter esta correção…"; "Mudanças perigosas" na aba "Avançado", gravando sozinha. `test_rgs20_34_correcao.py`, `test_ui_rgs26_20_34_arbitro.py` |
| F2.3 RGS-34 | **feito** | `round_deletion_preview` + `delete_generated_round(round_id, reason)`: com resultados exige motivo e guarda os resultados no evento |
| F2.5 RGS-22 | **feito** | `screens/player_actions/`: menu da linha do jogador (clique direito, Shift+F10, tecla Menu) nas telas de jogadores, classificação e chamada inicial; "Faltar só à rodada N…", "Retirar do torneio…" (escopo + "vale a partir da rodada N"), "Reintegrar…"; `db.update_player` recusa `status`/`active` (`TypeError`); desistência exige motivo no serviço. `test_rgs22_24_linha_do_jogador.py`, `test_ui_rgs22_24_linha_do_jogador.py` |
| F2.6 RGS-23 | **feito** | "Bye na próxima rodada… (H ½ / Z 0)" com saldo ("1 de 2 byes usados"); com a rodada já gerada oferece o W.O.; `components/search_combo.py` nos seletores de byes, ajustes e proibições (busca sem acento, Enter grava) |
| F2.8 sessão com o árbitro | **aguarda o árbitro** | — |
| F2.4 RGS-21 | **feito** | Toast "Mesa 1 → 1-0" com "Desfazer (Ctrl+Z)"; `PairingService.undo_result` reaplica o anterior pelo `update_result` (2º evento com `undo`) e recusa se a mesa mudou ou a rodada fechou; contador "N/M lançadas"; `w`/`p`/`a` na tabela com a confirmação de W.O. do painel (`pending.confirm_walkover`). Tecla que não gravou (W.O. cancelado, aviso de BYE) não avança. `tests/test_rgs21_25_rodadas.py`, `tests/test_ui_rgs21_25_rodadas.py` |
| F2.7 RGS-25 | **feito** | Botão primário "Lançar resultados (N/M)" → "Fechar rodada N" → "Gerar rodada N+1" ("Ver classificação final" na última); "Fechar rodada" saiu de "Mais"; a confirmação lista o checklist de fechamento, Esc/"Voltar" não fecham; item reprovado vai para a faixa de regra com "Resolver". Caracterização da §8 item 10 antes da mudança |

---

## Fase 3 — Conformidade FIDE

**Objetivo verificável:**
- o replay encolhe para **zero** divergências não justificadas nos cenários de bye 0, 0,5 e 1, ajuste de pontos, entrada tardia, ordem nacional, título empatado e proibição;
- a cor da R1 se reproduz.

1. **F3.1 RGS-03 definitivo.** Registro 162 (PAB = `bye_points`) e 299 (ajustes), ou TRF25; a checagem continua depois de `reconcile_scores`.
2. **F3.2 RGS-13.** `seeding_key` única, com título.
3. **F3.3 RGS-15.** Registro 260; o Gacrux continua sendo o motor quando há proibição.
4. **F3.4 RGS-19.** Conferência da saída do Gacrux.
5. **F3.5 RGS-16.** `pairingchecker -c` depois de toda geração; ajuste manual com motivo e auditoria.
6. **F3.6 RGS-17.** Falso "bye repetido".
7. **F3.7 RGS-18.** Motor reserva: PAB, W.O. antes do PAB, cor E.4, rótulo e confirmação. **Se o F0.6 confirmar a hipótese β, este item sobe para a Fase 1.**
8. **F3.8 RGS-14.** Cor inicial gravada e registro 152.
9. **F3.9 RGS-24.** Assistente de entrada tardia, agora que o Gacrux aceita os pontos de entrada.

**Andamento da Fase 3 (2026-11-26):**

| Passo | Estado | Prova |
|---|---|---|
| F3.1 RGS-03 definitivo | **feito** | `gacrux_trf.py`: registro 162 (PAB = `bye_points`), 299 (ajustes), pontos rebaseados; patch vendorizado em `gacrux/trf2json.py` e `gacrux/tiebreak.py` (aprovado pelo dono, D6). Bye 0/0,5 e ajuste manual saem pelo Gacrux, sem motor reserva. `test_rgs03_definitivo.py`, `test_rgs03_desempate_gacrux.py` |
| F3.2 RGS-13 | **feito** | `constraints.seeding_key`/`seeding_order` (rating, título, alfabético — C.04.2); `test_rgs13_seeding.py`. Faltam 2 pontos de chamada: `export_sections` e a divisão por grupos em `tournament_service` |
| F3.3 RGS-15 | **feito** | Registro 260 (primeira = última = rodada pareada); o Gacrux segue como motor; `test_rgs15_proibicao_gacrux.py` |
| F3.4 RGS-19 | **feito** | `pairings_from_gacrux` confere a saída (todos pareados uma vez, nada inventado); `test_rgs19_saida_gacrux.py` |
| F3.5 RGS-16 | **feito** | `pairing_check.py` após toda geração (eventos `pairing_check`/`pairing_check_divergence`); ajuste manual exige motivo (`pairing_manual_adjustment`); `test_rgs16_verificacao_pareamento.py` |
| F3.6 RGS-17 | **feito** | "Bye repetido" só para PAB atual; `test_rgs17_bye_repetido.py` |
| F3.7 RGS-18 | **feito** | Motor reserva: W.O. não recebe PAB, cor E.3–E.5, rótulo "motor reserva — não homologado FIDE", confirmação e evento `pairing_reserve_engine`; `test_rgs18_*.py` |
| F3.8 RGS-14 | **feito** | `pairing/initial_color.py`; cor sorteada e gravada na criação (schema v57); campo "Cor inicial" nas Configurações; registro 152; `test_rgs14_cor_inicial.py`. Falta: o TRF25 ainda omite o 152 antes da R1 |
| F3.9 RGS-24 | **feito** | Assistente "Entrada tardia…": ID FIDE/CBX + busca na base oficial, pontos por rodada perdida (0, ½, 1), "Entra na rodada N"; R4 com entrante de 0,5 sai pelo Gacrux (teste `gacrux`) |
| Replay (objetivo da fase) | **pendente** | Depende dos arquivos do árbitro (F0.3/F0.6) |

---

## Fase 4 — Polimento e dívida (contínuo)

- RGS-27: acentos e status traduzido.
- RGS-28: patch do `ScalingTracker`.
- RGS-29: migração transacional.
- RGS-31 e RGS-32: falhas silenciosas restantes.
- RGS-30: equipes e Baku, com spec própria. Corrigir o `ROADMAP_ARBITRAGEM_XADREZ.md` sobre a fórmula de Baku (Handbook C.04.5).

**Andamento da Fase 4 (2026-11-26):**

| Item | Estado | Prova |
|---|---|---|
| RGS-27 | **feito** | Status da rodada traduzido (`round_option_label`, "Rodada 3 - encerrada"); ~260 literais acentuados em `src/ui`; lista fechada de 130 palavras no gate `check_ui_accents.py`; `test_rgs27_acentos.py` |
| RGS-28 | **feito** | `ui/ctk_patches.py` (só no CTk 5.2.2); `test_ui_rgs28_scaling.py` |
| RGS-29 | **feito** | Migração por versão numa transação; `_executar_script` no lugar de `executescript`; `test_rgs29_migracao_transacional.py` |
| RGS-31 | **feito** | `refresh._tick` religa no `finally`, com log; `test_rgs31_auto_refresh.py` |
| RGS-32 | **feito** | 63 blocos: 18 viraram `logger.debug(..., exc_info=True)`, 45 ficaram com justificativa na linha; `test_rgs32_falhas_silenciosas.py` reprova `pass` novo sem comentário |
| RGS-30 equipes | **feito** | EQ-01..04 em `pairing/team_swiss.py` e `histories.team_match_unplayed`; migração v58 (`teams.pairing_number`, `seed_rating`, `entry_round`; TPN de torneio em andamento lido da R1); desempate de equipes com 162/299; equipe tardia fora do retrato (`standings_cut.teams_as_of_round`); a tela oferece "Confirmar o W.O." quando uma equipe não tem ninguém presente. `tests/test_eq_suico_equipes.py`; andamento em `ESPEC_SUICO_EQUIPES.md` §6. Depois: H/Z de equipe não bloqueia o PAB (C.04.6 2.1.2, EQ-05); equipe tardia no todos-contra-todos fica fora do calendário, com aviso (EQ-06); "Trocar TPN" com motivo e auditoria, só entre rodadas e fora do todos-contra-todos (EQ-01.5) |
| RGS-30 Baku | **feito (individual e equipes)** | Conferido em https://handbook.fide.com/chapter/C0407202602 (C.04.7, desde 01/02/2026). `acceleration.baku_virtual_points` (GA = 2×⌈N/4⌉, VP só no score de pareamento); 250 no TRF16 e no TRF25 + `_BAKU` no 192; o Gacrux recebe o 250 de **todas** as rodadas aceleradas já jogadas (antes só o da rodada pareada — afetava também a Haley). R1–R4 iguais ao bbpPairings com 16 jogadores (`tests/test_rgs30_baku.py`). **Equipes (EQ-07):** o C.04.7 trata o match como unidade (Exemplo 2 de 1.4.4: 2 MP virtuais na 1ª metade, 1 MP na 2ª); com game points como score principal o Baku é recusado. `acceleration.baku_team_accelerated_ids`, `team_swiss.baku_first_round_team_matches`; aceleração clássica em equipes avisa que não se aplica. O TRF25 de equipes declara o 250 em match points sobre o GA pelo TPN e o `_BAKU` no 192 (`acceleration.baku_applies_to_team_swiss`, a mesma regra do motor; `BakuDeEquipesNoTrf25Test`) |

**Pendências fechadas depois das fases (2026-11-26):**

| Item | Prova |
|---|---|
| Seeding único (RGS-13) | Relatório da lista inicial, chamada inicial e divisão de grupos usam `seeding_order`; `tests/test_rgs_pendencias_pareamento.py` |
| Trocar cores exige motivo | `swap_pairing_colors(..., reason=)` → `pairing_manual_adjustment` (`kind="colors_swapped"`) |
| Entrante tardio fora do retrato | `TRF16Exporter.players(tid, up_to_round=)`; o TRF25 e o desempate usam a mesma lista |
| Saída vazia/inválida do Gacrux | `GacruxOutputRejected` (base `GacruxRefusal`) → a mesma oferta do motor reserva |
| TRF25: 152 antes da R1 | `tests/test_trf25_pendencias.py` |
| Ctrl+Z em toda a tela de Rodadas | Ligado na janela, desfeito com a tela; numa caixa de texto a tecla é do campo — vale também para 1/0/-/BackSpace/Enter (antes o BackSpace numa caixa apagava o resultado da mesa) |
| "Fechar rodada" no painel | A mesma confirmação da tela de Rodadas (`_confirm_round_closing`) |
| Criar torneio por perfil | Dentro de `db.transaction()` |
| Acentos nas mensagens dos serviços | O gate cobre `AppError`/`ValueError`/`PermissionError`, constantes em MAIÚSCULAS, `add_alert` e `bye_policy.py`; 466 literais corrigidos |
| Linha 001 do TRF no retrato | Pontos e posição até a rodada N (`_trf_player_standings(up_to_round=)`), TRF16 e TRF25; `tests/test_trf_retrato_001.py` |
| Acentos, 2ª varredura | Lista fechada de 136 → 200 palavras; o gate lê também `gacrux_engine.py` e `incidents.py`; avisos de validação do TRF e fórmulas do desempate corrigidos |
| Repetição após W.O. (EQ-03) | Conferida no texto: C.04.2 art. 3.5 ("did not play their game or match") e C.04.6 art. 2.1.1. Fica [H] só o que é "match não jogado" (W.O. em todos os tabuleiros) |
| Checklist do painel num passo só | O "Fechar rodada" do Checklist fecha sem abrir a segunda confirmação, e o checklist diz o que fechar faz (`_round_closing_effect`, o mesmo texto da confirmação). O botão continua desabilitado com item pendente; o serviço confere de novo. `ChecklistDoPainelEUmPassoSoTest` |
| Textos semeados com acento (schema v59) | Níveis de aprendizado, modelos de certificado e galeria: banco novo já nasce com acento; banco antigo migra só o campo que ainda é o padrão (`to_ascii(novo)`), o editado pelo usuário fica; `certificate_issuances.template_name` acompanha. O gate lê as sementes. `tests/test_seeds_acentuados.py` |

---

## Portões de release (todas as fases)

- [ ] `pytest` completo verde (com UI)
- [ ] `pytest -m gacrux` verde
- [ ] `Albericus.exe --self-test` = 0 **no executável que será distribuído**
- [ ] Replay sem divergência nova em relação à linha de base
- [ ] Migração testada sobre a cópia do `.db` real de 11/11, com backup antes
- [ ] Nota de release com os IDs RGS, em português correto

## Decisões em aberto

| # | Questão | Recomendação | Quem decide |
|---|---|---|---|
| D1 | Build onefile ou onedir? | Medir na F0.5: se o subprocesso `--gacrux` passar de 1 s por chamada no onefile, onedir | Dev |
| D2 | Remover "mudanças perigosas" de vez? | Não agora: "Avançado" + reavaliar depois da F2.8 | Dono do produto + árbitro |
| D3 | Reescrever o motor reserva como holandês completo? | Não, salvo se o F0.6 confirmar β | Dono do produto |
| D4 | Data com ano de 2 dígitos fora do registro 132? | Recusar e pedir correção | Árbitro |
| D5 | `prize_exclude_withdrawn`: ausente na última rodada concorre? | Sim (RGS-35); confirmar com o regulamento usual dos torneios do árbitro | Árbitro |
| D6 | Manter o patch no Gacrux vendorizado (`gacrux/trf2json.py`, `gacrux/tiebreak.py`) para ler os registros 162/299? | **Decidido em 2026-11-26: sim, aprovado pelo dono.** Ao atualizar o Gacrux, reaplicar o patch e rodar `pytest -m gacrux` | Dono do produto |
