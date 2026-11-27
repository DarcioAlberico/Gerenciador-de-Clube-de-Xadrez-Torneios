# Roadmap — Revisão Geral 2

> **Fonte executiva:** `ESPEC_REVISAO_GERAL_2.md` (v2). Cada passo aponta para um `RG2-NN`; o requisito e o critério de aceite moram **só** na spec. Este arquivo define **a ordem** e **o porquê**.
> **Versão:** v2, 2026-11-27. A sequência foi corrigida depois da 10ª revisão (spec, Anexo A, objeção 11).

## Princípios de sequência

1. **Primeiro, o que já foi feito vira commit.** A RG2 não começa por cima de 335 arquivos soltos (spec §7.1).
2. **Primeiro o número errado, depois o atrito.** P1 antes de P2; dentro dos P1, o que o árbitro vê durante o torneio antes do que só aparece depois (exportação, norma).
3. **Hotfix só com correção pequena.** A Fase 0 tem itens de poucas linhas, sem migração e sem tela nova. Onde o P1 precisa de redesenho, o hotfix entra como **guarda** e o redesenho vai para a fase (RG2-07a × 07b).
4. **Uma decisão, um lugar.** Onde a causa-raiz é uma cópia que divergiu, elimina-se a cópia: o motor de equipes (07b), `fide_rating` (11), `effective_federation` (12), o operador corrente (04 + 43), os leitores de número (10, 14, 27, 46) e de texto (30).
5. **A regra no serviço antes da tela.** Transações (Fase 1) e permissões (Fase 2) vêm antes dos fluxos que gravam em cima delas.
6. **Um RG2 por PR, teste vermelho primeiro.** Exceção declarada: a fronteira numérica (10, 14, 27, 46) é um PR só, porque é um núcleo só. Cada commit diz por quê, o que mudou e como foi provado. O que a spec §8 declara sólido ganha teste de caracterização antes de ser tocado.

## Visão geral

| Fase | Tema | RG2 | Release | Esforço estimado |
|---|---|---|---|---|
| **−1** | Commitar a Revisão Geral Suíço | 42 (`.gitattributes`), D7 | — | 1–2 dias |
| **0** | Hotfix: o número errado na frente do árbitro | 02, 03, 05, 06, 07a, 01 + 44 + 31, 20 | **hotfix** | 1–1,5 semana |
| **1** | Fronteira numérica, gravação atômica, dado derivado | 46 + 14 + 27 + 10, 08, 09, 25, 26, 28, 17, 15, 47, 34 | +1 | 3 semanas |
| **2** | Operador único, permissão no serviço, portal | 43 + 04, 37, 38, 19 + 45 | +1 | 2 semanas |
| **3** | FIDE, federação e importação | 11, 12, 21, 22, 24, 13, 30, 29, 07b + 23 | +2 | 3–4 semanas |
| **4** | Premiação e organização | 16 → 18 → 33, 35, 39 | +3 | 1–2 semanas |
| **5** | Árbitro prático | 36 | +3 | 1 semana |
| **6** | Silêncio, segredos, dívida | 32, 40, 41, 42 (resto) | contínuo | — |

P1 por fase: Fase 0 = 01, 02, 03, 05, 06, 07a, 20; Fase 1 = 46, 14, 08, 09, 15, 17; Fase 3 = 11 (TRF), 12, 13; Fase 4 = 16. Os 17 P1 terminam na release +2, menos o 16 (+3, depende da D1).

---

## Fase −1 — Entregar o que já foi feito

**Objetivo verificável:** `git status` limpo; gate completo verde em **cada** commit; `build.bat` verde; `Albericus.exe --self-test` = 0.

| Passo | Entrega | Prova |
|---|---|---|
| F−1.1 | Decisão D7 com o dono | — |
| F−1.2 | `.gitattributes` com `eol` explícito, num commit próprio | `git diff` sem avisos LF→CRLF |
| F−1.3 | 6 commits: acentos → `.exe` → migrações v56–v59 → pareamento → UI/i18n → testes | Gate completo verde em cada commit |
| F−1.4 | `test_dup_check_tmp.py` sai do commit de testes (vira RG2-17) | `git ls-files tests/*tmp*` vazio |
| F−1.5 | `build.bat` + `--self-test` no `.exe` do último commit | Código 0 |

---

## Fase 0 — Hotfix

**Objetivo verificável:** os cenários desta fase, cada um com seu teste vermelho → verde; gate completo verde; `--self-test` = 0.

| Passo | Item | Entrega | Por que nesta ordem |
|---|---|---|---|
| F0.1 | RG2-02 | `"break"` nos handlers de gravação da tabela + varredura | Uma linha; o árbitro aperta Enter em toda mesa |
| F0.2 | RG2-03 | O tick preserva seleção, foco e busca; pula com diálogo ou foco em campo | Ligado por padrão, a cada 15 s |
| F0.3 | RG2-06 | Conferência da resposta do motor + `rank or inf` + seção só na tela | A classificação publicada mostra o tardio em 1º |
| F0.4 | RG2-07a | Guarda pós-pareamento de equipes: recusa repetição e 2º PAB | O redesenho (07b) leva semanas; a guarda, horas |
| F0.5 | RG2-05 | `cancel_requested_bye` no serviço | Fecha um furo no limite de byes |
| F0.6 | RG2-01 + RG2-44 | Retenção só dos próprios backups, cota de segurança, `mtime_ns`; backup de fechamento sem checar permissão | Pode apagar o banco vivo; o árbitro fecha sem backup |
| F0.7 | RG2-31 | Snapshot da lista FIDE substituído + `VACUUM` único | Cada backup tem 110 MB; junto com a retenção |
| F0.8 | RG2-20 | Neutralizar fórmula (XLSX `data_type='s'`; CSV `'` + importador retira) | Duas lentes acharam; telefone preservado |
| F0.9 | — | Nota de release em linguagem de árbitro | Revisada pelo árbitro |

**Fora da Fase 0, de propósito:** RG2-04/43 (tocam todos os serviços), RG2-07b (redesenho), RG2-15/16 (dependem de D1 e D3), RG2-19/45 (dependem de D4), RG2-46 (o núcleo numérico é um PR de fronteira, não um remendo — mas é o **primeiro** da Fase 1).

---

## Fase 1 — Fronteira numérica, gravação atômica e dado derivado

**Objetivo verificável:** nenhum `float(str(x).replace(",", "."))` nem `or <número ≠ 0>` em `src/services` (varredura); toda operação pública com ≥ 2 gravações dentro de `transaction()` (varredura por AST); nenhum dado derivado gravado sem invalidação.

| Passo | Item | Entrega |
|---|---|---|
| F1.1 | RG2-46 + 14 + 27 + 10 | **Um PR:** `parse_decimal_br`, `parse_rating`, `parse_points`, `setting_number`; dinheiro, rating, pontos e ajustes passam por eles; varreduras |
| F1.2 | RG2-08 | Fechamento por equipes pelo mesmo caminho do individual |
| F1.3 | RG2-09 | Participação inclui tabuleiros de equipe; exclusão recusa |
| F1.4 | RG2-25 | Transação em participação, geração, W.O. de ausente, QR, rating, "Todos presentes"; varredura por AST |
| F1.5 | RG2-26 | Chaves faltantes + `ValueError` para chave desconhecida |
| F1.6 | RG2-28 | Backup e auditoria global antes de excluir torneio |
| F1.7 | RG2-17 | Duplicação por lista de exclusão + teste de todas as colunas |
| F1.8 | RG2-15 | `refresh_player_categories` com o gancho da D3 |
| F1.9 | RG2-47 | `members.sex` (migração v60), formulário, CSV, Google Forms |
| F1.10 | RG2-34 | UPDATE parcial de membro |

---

## Fase 2 — Operador único, permissão no serviço, portal

**Objetivo verificável:** a varredura por AST não acha método que grava sem checagem; com `viewer`, nenhuma gravação passa por nenhuma tela; todo evento de auditoria tem o operador logado.

| Passo | Item | Entrega |
|---|---|---|
| F2.1 | RG2-43 | Provedor de operador no `Database`, definido no login; `app_settings` deixa de ser a fonte |
| F2.2 | RG2-04 | `require_permission` lendo o provedor; isenções de sistema; `delete_records` só em globais |
| F2.3 | RG2-37 | Senha definida no primeiro acesso (banco novo), sem `strip`, papel validado, atraso e auditoria |
| F2.4 | RG2-38 | Sincronização: sai inteira ou fica completa (D5) |
| F2.5 | RG2-19 + 45 | Portal: só o publicado, modo fixado, IP da rede no QR, `build_app` (D4) |

**Por que o operador vem primeiro:** é um lugar só. Os métodos auditados criados antes (RG2-05, 28) passam a gravar o operador certo sem retrabalho.

---

## Fase 3 — FIDE, federação e importação

**Objetivo verificável:** TRF do banco real copiado sem rating local na coluna FIDE; round-trip TRF de torneio em andamento fiel (se D8 = sim); normas do cenário `t6` reprovadas; stress de equipes (7 × 6, sementes fixas) sem repetição evitável e sem 3 cores seguidas; importadores com cobertura ≥ 80 % (hoje 1–3 %).

| Passo | Item | Entrega |
|---|---|---|
| F3.1 | RG2-11 | `fide_rating` único em TRF, normas e IT3 |
| F3.2 | RG2-12 | `effective_federation` único |
| F3.3 | RG2-21 | Linha 001 sem `rstrip` + testes da célula pendente |
| F3.4 | RG2-22 | Inviabilidade vira `GacruxRefusal` com texto C.04.1 |
| F3.5 | RG2-24 | `swiss = method == "swiss"` |
| F3.6 | RG2-13 | `parse_trf` com avisos; rodada só fecha completa; 142/XXR (D8) |
| F3.7 | RG2-30 | `read_text_file` único + teto de download |
| F3.8 | RG2-29 | Sexo, transliteração, TTF, TRF25 alinhado ao TRF16 |
| F3.9 | RG2-07b + 23 | Motor único de busca por grupo para jogador e equipe, critério principal configurável; elimina os pares 0,99/0,96/0,92/0,88 do dryer |

**Por que o 07b fica por último na fase:** é o maior e o único que mexe em pareamento; a guarda 07a já segura o P1 desde a Fase 0.

---

## Fase 4 — Premiação e organização

**Objetivo verificável:** "anunciado = distribuído + não distribuído" em todo torneio de teste; o diploma de categoria sai para quem recebeu o prêmio.

| Passo | Item | Entrega |
|---|---|---|
| F4.1 | RG2-16 | Alocação sequencial com empate antes da trava + `undistributed` + recusa de categoria inexistente (D1) |
| F4.2 | RG2-18 | "Aceita quem está abaixo" por categoria, desligado por padrão (D2) |
| F4.3 | RG2-33 | "Desempate decide" + diploma lendo a alocação |
| F4.4 | RG2-35 | Desligar Modo Livre depois de jogado exige motivo |
| F4.5 | RG2-39 | Agenda e categorias recusam o impossível |

**Por que 16 → 18 → 33:** a opção do 18 aumenta as faixas por jogador, o que só é seguro com a trava do 16; o diploma (33) lê a alocação do 16.

---

## Fase 5 — Árbitro prático

| Passo | Item | Entrega |
|---|---|---|
| F5.1 | RG2-36.2 | Menu do jogador na tabela de Rodadas (a queixa original) |
| F5.2 | RG2-36.1 | Retirar com mesa aberta oferece W.O. |
| F5.3 | RG2-36.3–7 | Desfazer no painel, duplo clique na mesa certa, busca na troca, confirmar rejeição de QR, cursor na próxima linha |
| F5.4 | — | Sessão com o árbitro (junto com a F2.8 da RGS) |

---

## Fase 6 — Contínuo

RG2-32 (falhas silenciosas, forma fixa da justificativa), RG2-40 (concorrência), RG2-41 (segredos), RG2-42 (dryer, crapper, testes sem `assert`, `initial_color` fixa nos testes). Cada item entra quando outra fase passar pelo mesmo arquivo.

---

## Portões de release (todas as fases)

1. Gate completo verde (`scripts/check_quality.ps1`), inclusive `-m gacrux`.
2. `build.bat` + `Albericus.exe --self-test` = 0 no `.exe` do commit.
3. Cada RG2 da release com o teste do critério de aceite, visto vermelho antes.
4. Para os itens de cálculo (06, 07, 11, 12, 15, 16, 46): o mutator (`scripts/mutate.py`) sobre a função alterada, sem sobrevivente sem justificativa.
5. Crapper: nenhuma função tocada pela release termina com CRAP ≥ 10 sem justificativa no PR.
6. Nota de release em linguagem de árbitro.

## Decisões que travam fases

| Decisão | Trava |
|---|---|
| D7 (commits) | Fase −1, e por consequência todas |
| D1, D2 | F4.1, F4.2 |
| D3 | F1.8 |
| D4 | F2.5 |
| D5 | F2.4 |
| D8 | F3.6 (parte "torneio em andamento") |

## Andamento

| Fase | Estado |
|---|---|
| −1 | **feita** em 2026-11-27 (D7 aprovada pelo dono), branch `fix/rgs-fase0-exe` — ver abaixo |
| 0–6 | não iniciadas |

### Fase −1 (2026-11-27)

Seis commits montados com índice temporário, sem tocar a árvore de trabalho; o último tem a mesma árvore que o disco (conferido). A cópia anterior fica em `refs/backup/antes-rg2`.

| Commit | Conteúdo | Prova |
|---|---|---|
| `chore(git)` | `.gitattributes` (`* text=auto eol=lf`) | Renormalizar não muda nenhum arquivo além dos já alterados |
| `style(acentos)` | 133 arquivos só de acento + as linhas só de acento de 92 arquivos com lógica (225 no total) | Ferramenta: tirando os diacríticos, cada arquivo fica igual ao pai; gate estático e suíte completa verdes na worktree do commit |
| `chore(qualidade)` | crapper, dryer, mutator, dependências de dev, marcador `gacrux` | Gate estático + `test_quality_tools.py` na worktree |
| `fix(rgs)` | Código e testes da Revisão Geral Suíço (RGS-01..37) e o gate de acentos rigoroso | Gate estático na worktree; o código é idêntico ao da suíte completa de hoje (2409 passaram) |
| `docs(rgs)` | Spec, roadmap e notas da RGS; README e manuais | — |
| `docs(rg2)` | Esta spec, este roadmap, a reprodução dos achados | — |

**Achados no caminho:** (1) a lista CBX `.xls` está versionada como **texto** (o `autocrlf` mexe nos bytes dela) — ficou fora do `.gitattributes` e entra no RG2-41; (2) o gate de acentos antigo tinha um falso positivo ("Grava" × "gravá-lo"), corrigido no gate novo — por isso as linhas com "gravá" vão no commit `fix(rgs)`, não no de acentos.
