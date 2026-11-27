# Revisão do modo amistoso

> **Roadmap.** Fonte executiva: `ESPEC_REVISAO_MODO_AMISTOSO.md`. Cada item aponta para um `MA-NN`, e o requisito completo mora na spec. Este arquivo define **a ordem**, **o porquê**, o critério de pronto e a prova.
> **Versão:** v8, 2026-11-27: a v1, cinco revisões, as decisões D1 e D2 do usuário e o acento em comentário e docstring (histórico no fim).

## Princípios de sequência

1. **Primeiro o dono da regra.** O módulo do modo e o preset (MA-01, MA-14.1) nascem antes de qualquer correção, porque todas leem dele.
2. **Depois o que perde dado ou mente.** Primeiro re-emparceirar, porque a entrada tardia "já nesta rodada" o reaproveita. Depois entrada tardia e súmula (Onda 1).
3. **Depois a fronteira com o oficial:** perfil FIDE e submissão de rating (Onda 2).
4. **Depois o conforto do professor** (Onda 3), e **por fim a coerência** com o resto do app (Onda 4).
5. **Teste primeiro, na camada de serviço.** O teste de tela só cobre o que é tela.
6. **Sem schema novo.** Nenhuma onda precisa de migração depois da v59 (rev. 2).
7. **Sem commit:** o usuário pede quando quiser.

## Visão geral

| Onda | Tema | Itens | Prioridade |
|---|---|---|---|
| **0** | Dono da regra | MA-01, MA-14.1 | P1 |
| **1** | Nada some, nada mente | MA-03, MA-04, MA-05 | P1 |
| **2** | Fronteira com o oficial | MA-02, MA-06 | P1 |
| **3** | Professor | MA-08, MA-10, MA-11, MA-07, MA-09 | P2 |
| **4** | Coerência | MA-12, MA-13, MA-14.2 | P3 |

**Decisões do usuário (2026-11-27):**
- **D1:** o nome visível continua "Modo Livre" (MA-12).
- **D2:** antes de o torneio amistoso contar para o rating interno do clube, o app pergunta (MA-06).

---

## Onda 0 — Dono da regra

| ID | Prior. | Entrega | Critério de pronto | Prova (teste) |
|---|---|---|---|---|
| MA-01 | P1 | `src/services/friendly_mode.py`: rótulo, `is_friendly`, preset, `profile_conflict`, `late_tolerance_line`; `FriendlyModeService.create` | A UI não tem o literal "Modo Livre"; a criação usa o preset | `tests/test_friendly_mode.py`: preset aplicado; varredura do literal em `src/ui` |
| MA-14.1 | P1 | Preset grava `late_entry_points = 0.5` | Assistente do RGS-24 e tela de jogadores propõem o mesmo valor | torneio criado → `late_entry_points == 0.5` |

## Onda 1 — Nada some, nada mente

| ID | Prior. | Entrega | Critério de pronto | Prova (teste) |
|---|---|---|---|---|
| MA-03 | P1 | `PairingService.repair_open_round`: atômico, com motivo do RGS-34, motor reserva e submissões QR no `before` | Falha na geração não apaga a rodada; o serviço recusa torneio oficial | falha → rodada intacta; motivo exigido com resultado; evento `round_repaired`; QR pendente contado |
| MA-04 | P1 | Entrada tardia amistosa pelo plano do assistente; "jogar já nesta rodada" em transação única (`FriendlyModeService.late_entry`) | Um só plano; evento gravado; falha não deixa aluno meio inscrito | R2 fechada + R3 aberta: "próxima" → `entry_round=4`; "já" → `entry_round=3` e numa mesa; falha → nada gravado |
| MA-05 | P1 | `late_tolerance_line`, derivada de `free_mode`, na súmula | A súmula amistosa não diz "perde a hora marcada" | linha por modo: amistoso 0, amistoso 15 min, oficial |

## Onda 2 — Fronteira com o oficial

| ID | Prior. | Entrega | Critério de pronto | Prova (teste) |
|---|---|---|---|---|
| MA-02 | P1 | `profile_conflict` em `save_tournament_settings` e `set_free_mode` | As duas direções recusam | `AppError` nos dois sentidos, nada gravado |
| MA-06 | P1 | TRF16 em modo submissão recusa torneio amistoso; o modo normal avisa. D2: o rating interno pergunta antes de contar o amistoso | Submissão recusa, normal gera com aviso; rating interno sem resposta recusa | `submission=True` → `AppError`; normal → aviso na lista; rating interno: amistoso sem `friendly_confirmed` → `AppError`, oficial aplica |

## Onda 3 — Professor

| ID | Prior. | Entrega | Critério de pronto | Prova (teste) |
|---|---|---|---|---|
| MA-08 | P2 | Criação com nome, rodadas e turma; inscreve os alunos ativos | Turma de 3 ativos e 1 inativo → 3 jogadores | serviço: escopo `class`, 3 jogadores, `free_mode=1`; rodadas 0 → erro com a faixa válida |
| MA-10 | P2 | Botões com verbo; segunda pergunta com rodada aberta; total de pontos na mensagem | Sem "Sim/Não"; acento correto | teste de tela dos textos |
| MA-11 | P2 | Aviso com os cinco itens reais | A frase de punições sai | teste de tela do aviso |
| MA-07 | P2 | `FriendlyModeService.set_enabled` e caixa em Configurações | Ligar e desligar auditados; FIDE recusa | 2 eventos; recusa sem evento |
| MA-09 | P2 | `FriendlyModeService.add_round` e oferta na tela | R1 fechada de 1 → R2 gerada | `rounds_count` +1, evento, oficial recusa |

## Onda 4 — Coerência

| ID | Prior. | Entrega | Critério de pronto | Prova (teste) |
|---|---|---|---|---|
| MA-12 | P3 | Linha "Modo:" no painel do torneio (D1 pendente) | Oficial mostra "Modo: Oficial" | teste da função de linhas do painel |
| MA-13 | P3 | Itens do modo sempre no menu, conferidos no clique | Ligar o modo não exige remontar a tela | teste de tela: menu montado com oficial, depois ligado |
| MA-14.2 | P3 | Seção "Modo Amistoso (escolar)" no README | Seção presente | revisão do texto; gate de acentos |

---

## Andamento

| Onda | Itens | Estado | Prova |
|---|---|---|---|
| 0 | MA-01, MA-14.1 | **feito** (2026-11-27) | `src/services/friendly_mode.py`; `tests/test_friendly_mode.py` (4): vermelho por import e depois pelas 11 ocorrências do literal em `src/ui`, verde após a troca; gate `-Fast` OK; `test_ui_layout -k "free or late_entry"` 16 verdes |
| 1 | MA-03, MA-04, MA-05 | **feito** (2026-11-27) | `ReemparceirarTest` (6), `EntradaTardiaTest` (6), `SumulaTest` (3): vermelhos por método ausente, `join_open_round` ausente e "perde a hora marcada", depois verdes. Testes de tela do re-emparceirar e da entrada tardia reescritos para o serviço real. Na primeira rodada das suítes afetadas, 15 testes de tela caíram por um import esquecido (`FRIENDLY_MODE_LABEL` em `pairing_results/view.py`); corrigido e reverificado |
| 2 | MA-02, MA-06 | **feito** (2026-11-27) | `FronteiraComOficialTest` (7): perfil FIDE recusado nos dois sentidos, TRF16 em submissão recusa, arquivo de trabalho avisa; D2 com a nota `note` em `apply_tournament_ratings`, mostrada nas duas telas de rating interno |
| 3 | MA-08, MA-10, MA-11, MA-07, MA-09 | **feito** (2026-11-27) | Serviço: `CriacaoComTurmaTest` (2), `MaisUmaRodadaTest` (2). Tela: `tests/test_ui_friendly_mode.py` com `CriacaoTest`, `AvisoTest`, `MaisUmaRodadaTest`, `ConfiguracoesTest` e `MenuDaRodadaTest`, mais as perguntas com verbo em `test_ui_layout` |
| 4 | MA-12, MA-13, MA-14.2 | **feito** (2026-11-27) | `PainelDoTorneioTest`, `MenuDaRodadaTest`; README com a seção "Modo Amistoso (escolar)"; gate `-Fast` OK (acentos: 1868 textos) |
| — | Verificação final | **verde** (2026-11-27) | Todas com código de saída 0: `-m "not gui"` 2077 passaram e 4 pularam; `-m gui` 300 passaram e 1 pulou; `-m gacrux` 94 passaram. Exe não regerado (opcional) |
| — | D1, D2 | **decididas** (2026-11-27) | D1: continua "Modo Livre", nada a mudar. D2: `internal_rating_question` + `friendly_confirmed` no serviço; `free_mode_confirm_internal_rating` nas duas telas; `FronteiraComOficialTest` (2) e `RatingInternoTest` (3) |
| v7 | Acentos | **feito** (2026-11-27) | `src/` (257 literais + 31 de contexto), scripts (437), documentos (cerca de 5 mil palavras + 134 de contexto); marca de prêmio casa sem acento (`tests/test_category_tag_accents.py`); lista fechada do gate 209 → 267; 33 testes que conferiam a frase antiga atualizados |
| v7 | Ferramentas do ub-mode | **feito** (2026-11-27) | `scripts/crap.py`, `scripts/dry.py`, `scripts/mutate.py` (o `mutmut` 2.5 erra no Windows); dryer sem par ≥ 0,8 no modo; CRAP < 10 nas funções do modo; mutação em `friendly_mode.py`: 99 de 104 mortos, 5 equivalentes |
| v7 | Verificação final | **verde** (2026-11-27) | Gate `-Fast` OK; `-m "not gui"` 2098 passaram e 4 pularam; `-m gui` 308 passaram e 1 pulou; `-m gacrux` 94 passaram. Exe não regerado |
| v8 | Acento em comentário e docstring | **feito** (2026-11-27) | `src/`, `scripts/`, `tests/`: 3.333 trocas pelo mapa, 392 pelo mapa extra, 133 de "e"/"esta" por contexto, 9 verbos com pronome; nenhum token de código mudou; gate cobra "gravá-lo" |
| v8 | Verificação | **verde** (2026-11-27) | Gate `-Fast` OK; `-m "not gui"` 2101 passaram e 4 pularam; `-m gui` 308 passaram e 1 pulou; `-m gacrux` 94 passaram |

## Histórico de revisões

| Versão | O que acrescentou ou mudou |
|---|---|
| v1 | Primeira ordem: dono da regra → dado → fronteira → professor (MA-01 a MA-06, MA-08, MA-10) |
| rev. 1 (lacunas) | Onda 3 ganha MA-07 e MA-09; D2 entra como pendência de MA-06 |
| rev. 2 (simplificações) | Sai a migração v60 do MA-05; MA-04 e MA-02 reaproveitam o que existe; nenhuma onda precisa de schema novo |
| rev. 3 (riscos) | O "entrar já" do MA-04 reaproveita o re-emparceiramento atômico, então o MA-03 vem **antes** do MA-04 na Onda 1; as submissões QR entram no critério do MA-03 |
| rev. 4 (usabilidade escolar) | Onda 3 ganha MA-11 (aviso honesto); MA-10 e MA-08 ganham critérios de acessibilidade |
| rev. 5 (coerência) | Nova Onda 4 (MA-12, MA-13, MA-14); o preset de 0,5 do MA-14 sobe para a Onda 0 junto do MA-01, porque o MA-04 depende dele; D1 pendente |
| v7 (decisões) | D1: continua "Modo Livre". D2: o rating interno pergunta. Acentos corrigidos no app, nos scripts e nos documentos; ferramentas do ub-mode instaladas |
| v8 | O usuário confirmou acento também em comentário e docstring; só log e identificador ficam ASCII |
