# Revisão do modo amistoso

> **Status:** **v8** (2026-11-27): a v1, cinco revisões, as decisões D1 e D2 do usuário e o acento em comentário e docstring (seção 9). Andamento da implementação: seção 11.
> **Roadmap:** `ROADMAP_REVISAO_MODO_AMISTOSO.md`.
> **Base analisada:** árvore de trabalho em 2026-11-27, com o trabalho ainda não commitado da Revisão Geral do Suíço (schema v59). Os números de linha andam; o nome do método vale mais que a linha.
> **Nome no código:** o "Modo Amistoso" é o que o app chama de **Modo Livre**: menu "Torneio | Livre", marca `tournament_settings.free_mode` e mixin `FreeTournamentMixin` (`src/ui/screens/free_tournament.py`). O comentário do mixin já o chamava de "Modo Escolar Amistoso".

## 0. Por que este documento existe

O Modo Amistoso é o modo mais livre do Albericus. Foi pensado para a escola: o professor abre o torneio na hora, os alunos chegam e saem, e o importante é jogar. Hoje ele é um aviso modal mais três ferramentas soltas:

1. o aviso "Modo Livre Ativado", que cria um torneio com 5 rodadas e liga a marca `free_mode`;
2. "Re-emparceirar (Modo Livre)": apaga a rodada aberta e gera de novo;
3. a entrada tardia com 0 ou 0,5 ponto por rodada já encerrada.

O aviso promete três coisas:

- entrada tardia a qualquer momento;
- emparceiramentos e ajustes manuais;
- ausência de punições estritas por atraso.

A análise abaixo mostra que nenhuma das três promessas é cumprida por inteiro. Ela foi feita de três pontos de vista: árbitro FIDE, programador sênior e professor que organiza o torneio na escola.

Regra da casa, a mesma da revisão geral: **nada some calado, nada fica meio gravado, e o que funciona não se mexe** (seção 8).

**Severidade:**
- **P0:** impede o evento.
- **P1:** perde dado, mente para o usuário ou deixa o torneio amistoso vazar para o rating oficial.
- **P2:** atrito para o professor.
- **P3:** polimento.

**Marcação de evidência:**
- **[E]:** executado e visto acontecer. Script de sondagem com o motor próprio, 2026-11-27.
- **[L]:** lido no código, caminho completo.
- **[H]:** hipótese.

---

## 1. Três pontos de vista

### 1.1 Árbitro FIDE

- O torneio amistoso **não é homologável** e não pode virar rating FIDE ou CBX por engano. Hoje nada impede isso: nenhuma exportação lê `free_mode`, e o perfil pode ser trocado para "FIDE-rated" em silêncio (MA-02, MA-06).
- A súmula impressa no Modo Amistoso diz **"Tolerância: zero (perde a hora marcada)"**. Isso contradiz o aviso, que promete "ausência de punições estritas por atraso" (MA-05).
- O Modo Amistoso pode flexibilizar as regras **de condução** do torneio: entrada, rodada refeita, atraso. Não flexibiliza o **motor**: o pareamento continua o holandês, e cada exceção fica na auditoria. Assim o professor pode mostrar à direção ou aos pais o que aconteceu.
- A entrada tardia só aceita 0, ½ ou 1 por rodada perdida. É o que o TRF consegue registrar como bye Z/H/F (`late_entry_points_error`). O Modo Amistoso respeita o mesmo limite.

### 1.2 Programador sênior

- **Duas regras de entrada tardia.** O assistente oficial (`register_late_entry`) conta as rodadas **geradas**, valida o valor e grava o evento `late_entry_registered`. O caminho do Modo Amistoso conta as rodadas **encerradas**, não valida e não audita. A mesma decisão mora em dois lugares, e os dois discordam (MA-04).
- **O re-emparceiramento não é atômico.** Ele apaga a rodada e depois gera, em dois passos sem transação. Se a geração falha, a rodada some (MA-03).
- **A regra do modo vive na tela.** `_is_free_mode` está no mixin de UI. O serviço de pareamento aceita o re-emparceiramento de qualquer torneio, e só a tela barra (MA-03).
- Os testes de Modo Livre trocam o serviço por um dublê (`mock`). O bloqueio por falta de motivo do RGS-34 passou sem que nenhum teste notasse.

### 1.3 Professor (usuário escolar)

- Criar o torneio pede só o nome e fixa 5 rodadas. A turma já existe no cadastro, mas os alunos têm de ser inscritos um a um, ou por outra tela (MA-08).
- A pergunta da entrada tardia usa "Sim" e "Não" para responder "0,5 ou zero?". O texto explica qual botão é qual ("Sim = 0,5 por rodada"), e a pergunta tem um erro de acento: "esta entrando" (MA-10).

---

## 2. Achados

### MA-01 · A política do modo não tem dono **[L]** — P1

- **Evidência:**
  - o que o modo muda está espalhado: `_start_free_tournament` fixa `rounds_count=5` e `bye_points=1`; `_is_free_mode` está na UI; o rótulo "Modo Livre" aparece em `app.py` (`_set_current_tournament`), em `pairing_results/view.py` e no diálogo;
  - nenhum serviço sabe responder "este torneio é amistoso?".
- **Requisito:**
  1. Um módulo `src/services/friendly_mode.py` concentra a regra:
     - o rótulo visível do modo;
     - o predicado `is_friendly(settings)`;
     - o preset de criação.
     
     *(rev. 2)* ~~os textos que dependem do modo~~: cada texto fica na sua tela. O módulo guarda só o que é **decisão**: rótulo, predicado, preset, conflito de perfil e linha de atraso.
  2. A UI só consulta esse módulo.
- **Aceite:** teste do módulo. Criar pelo serviço liga `free_mode` e aplica o preset. Um teste de varredura garante que o literal "Modo Livre" não aparece fora do módulo em `src/ui`.

### MA-02 · Torneio amistoso aceita o perfil "FIDE-rated" em silêncio **[E]** — P1

- **Evidência:** `save_tournament_settings(tid, {"tournament_profile": "fide"})` num torneio com `free_mode=1` grava os dois (sondagem E5).
- **Regra:** um torneio que flexibiliza entrada, rodada e atraso não cumpre o regulamento de rating da FIDE.
- **Requisito:**
  1. `free_mode=1` e `tournament_profile='fide'` são **mutuamente exclusivos**.
  2. Salvar o perfil FIDE num torneio amistoso é recusado com mensagem clara. Ligar o modo num torneio FIDE também.
  3. *(rev. 2)* Uma só função pura decide a recusa: `friendly_mode.profile_conflict(free_mode, profile)`.
  4. *(implementação)* A camada `Database` não levanta `AppError`, então a função entra nos **serviços**:
     - `TournamentService._prepare_profile`, o caminho de Configurações;
     - `FriendlyModeService.set_enabled`, o caminho de ligar o modo.
     
     `db.set_free_mode` continua sendo a gravação crua.
- **Aceite:**
  - perfil FIDE em torneio amistoso → `AppError`, e nada é gravado;
  - `FriendlyModeService.set_enabled(True)` em torneio de perfil FIDE → `AppError`.

### MA-03 · Re-emparceirar perde a rodada ou fica bloqueado **[E]** — P1

- **Evidência:**
  - com 1 resultado lançado, `free_mode_repair_round` chama `delete_generated_round` sem motivo, e o RGS-34 recusa (sondagem E1). A ferramenta fica inútil justamente quando alguma mesa já terminou;
  - quando a geração falha depois de apagar (por exemplo, com menos de 2 alunos ativos), a rodada some e nada a recoloca (sondagem E2: "rodadas restantes: []");
  - o caminho não oferece o motor reserva quando o Gacrux recusa (`GacruxRefusal`), ao contrário da geração normal (`_offer_reserve_engine`).
- **Causa-raiz:** são dois passos separados, sem transação, numa função de tela.
- **Requisito:**
  1. `PairingService.repair_open_round(tournament_id, round_id, reason="", reserve_engine=False)`:
     - só em torneio amistoso;
     - apaga e gera **numa única** `db.transaction()`. Qualquer falha desfaz tudo;
     - com resultado lançado, exige motivo pela mesma regra do RGS-34;
     - grava o evento `round_repaired` com os resultados apagados.
  2. A tela pede o motivo só quando há resultado, já preenchido com uma sugestão. Na recusa do Gacrux, oferece o motor reserva.
  3. *(rev. 3)* `pairings → result_submissions` é `ON DELETE CASCADE`. Submissões por QR ainda não revisadas somem junto com a rodada. A confirmação diz quantas são, e o evento guarda essas submissões no `before`.
- **Risco aceito (rev. 3):** a transação segura a escrita do banco enquanto o Gacrux roda, cerca de 0,5 s no `.exe`. Outra thread que grave nesse intervalo, como o servidor de QR, espera até `BUSY_TIMEOUT_MS` (5 s). Durante o re-emparceiramento a rodada inteira está sendo refeita, então ninguém deveria estar submetendo resultado dela.
- **Aceite:**
  - geração que falha → a rodada original continua lá, com os resultados;
  - 1 submissão QR pendente → aparece na contagem e no `before` do evento *(rev. 3)*;
  - 1 resultado e sem motivo → recusado; com motivo → nova rodada e 1 evento com o resultado apagado;
  - torneio oficial → `AppError` no serviço, não só na tela.

### MA-04 · Duas regras de entrada tardia que discordam **[E]** — P1

- **Evidência:**
  - `free_mode_late_entry_starting_points` conta as rodadas **encerradas** e multiplica por 0,5 ou 0;
  - `create_player` grava `entry_round = última gerada + 1`;
  - com a R3 aberta, o aluno recebe 1,0 ponto (2 × 0,5) e `entry_round=4`, então a R3 fica sem ponto. Se o professor re-emparceira a R3, o aluno joga a R3 com `entry_round=4` (sondagem E3);
  - o caminho não grava auditoria nem valida o valor por rodada.
- **Requisito:**
  1. A entrada tardia amistosa passa pelo **mesmo plano** do assistente (`late_entry_plan`), com `per_round_points` 0 ou 0,5. Mesma validação e mesmo evento `late_entry_registered`.
  2. A conta de pontos sai do mixin. *(rev. 2)* `free_mode_late_entry_starting_points` deixa de calcular: só pergunta o valor por rodada e devolve o plano.
  3. *(rev. 3)* A sondagem E3 mostrou o risco real: o aluno inscrito com a rodada aberta e depois re-emparceirado **joga** uma rodada que o cadastro diz que ele perdeu. A regra passa a ser uma de duas, sempre coerente:
     - **"Entrar já nesta rodada"**: `entry_round` = a rodada aberta, pontos só das rodadas anteriores. A inscrição e o re-emparceiramento correm **numa única transação** (`FriendlyModeService.late_entry`). Se o re-emparceiramento falha, o aluno também não fica inscrito;
     - **"Entrar na próxima"**: o plano do assistente (`entry_round` = última gerada + 1), sem tocar na rodada aberta.
     
     Para isso, `late_entry_plan` ganha `join_open_round`.
- **Aceite:**
  - aluno inscrito após a R2 fechada e com a R3 aberta, "na próxima" → `entry_round=4` e `starting_points = 3 × valor`;
  - "já nesta rodada" → `entry_round=3`, `starting_points = 2 × valor`, e o aluno está numa mesa da R3;
  - re-emparceiramento que falha → nenhum jogador novo e a R3 intacta;
  - 1 evento `late_entry_registered`.

### MA-05 · A súmula do Modo Amistoso promete W.O. na hora **[L]** — P1

- **Evidência:** `export_renderers.py` imprime "Tolerância: zero (perde a hora marcada)" quando `late_tolerance_minutes=0`, e esse é o padrão de todo torneio, inclusive o amistoso. O texto também está sem acento.
- **Requisito (v1):** ~~coluna própria `friendly_late_policy`, migração v60~~.
- **Requisito (rev. 2, simplificado):** nada de coluna nova. A política sai da marca que já existe:
  - em torneio amistoso **sem** tolerância configurada, a súmula imprime "Atraso: sem W.O. automático (Modo Amistoso)";
  - com tolerância configurada, imprime os minutos, como no oficial.
  
  O texto vem de `friendly_mode.late_tolerance_line(free_mode, minutos)`. A linha do torneio oficial não muda: o acento que falta em "Tolerância" fica como acompanhamento fora deste escopo.
- **Aceite:**
  - súmula amistosa com tolerância 0 → a linha não diz "zero" nem "perde a hora marcada";
  - amistosa com 15 min → "15 min";
  - oficial → o texto de hoje.

### MA-06 · Torneio amistoso pode ser submetido para rating **[L]** — P1

- **Evidência:** o TRF16 no modo submissão (`submission=True`, `settings_reports_ui.py`) não lê `free_mode`, e nenhuma outra exportação lê.
- **Requisito:** no modo submissão, torneio amistoso é recusado com mensagem clara. No modo normal (o arquivo de trabalho), o arquivo sai com um aviso.
- **Aceite:** `export_chess_results_trf(..., submission=True)` em torneio amistoso → `AppError` que cita o Modo Amistoso; `submission=False` → arquivo gerado e aviso na lista.
- **Decisão D2 (usuário, 2026-11-27): perguntar.** Antes de o torneio amistoso contar para o **rating interno** do clube, a tela pergunta, com os botões "Contar no rating" e "Não contar". O serviço (`InternalRatingService.apply_tournament_ratings`) recusa o amistoso sem `friendly_confirmed=True`; o torneio oficial conta sem perguntar. *(rev. 1; decidida na v7)*
- **Aceite D2:** amistoso sem a resposta → `AppError` com a pergunta; com `friendly_confirmed=True` → aplica; oficial → aplica sem pergunta. Na tela, "Não contar" avisa e não aplica.

### MA-07 · Não dá para ligar ou desligar o modo num torneio que já existe **[L]** — P2 *(rev. 1)*

- **Evidência:** `set_free_mode` só é chamado em `_start_free_tournament`, e Configurações não tem o controle. O professor que criou o torneio pelo caminho comum não tem as ferramentas amistosas. Quem abriu pelo Modo Livre e quer voltar ao oficial também não tem como.
- **Requisito:**
  1. `FriendlyModeService.set_enabled(tournament_id, enabled, actor)` grava a marca e o evento `free_mode_changed` (antes e depois) numa transação.
  2. Ligar respeita o MA-02 (perfil FIDE recusa).
  3. Configurações do torneio ganha a caixa "Modo Amistoso (escolar)", e o cabeçalho se atualiza.
- **Aceite:** ligar e desligar → 2 eventos; ligar em torneio FIDE → recusado e sem evento.

### MA-09 · Não existe "mais uma rodada" **[L]** — P2 *(rev. 1)*

- **Evidência:** `_individual_next_round_plan` recusa com "O número máximo de rodadas do torneio já foi atingido." Na escola é comum sobrar tempo de aula. Hoje o professor tem de achar o número de rodadas em Configurações.
- **Requisito:**
  1. `FriendlyModeService.add_round(tournament_id, actor)`, só no Modo Amistoso: `rounds_count + 1`, com o evento `friendly_round_added`.
  2. Na tela, quando a geração recusa por limite de rodadas num torneio amistoso, o app oferece "Adicionar mais uma rodada e gerar".
- **Aceite:**
  - torneio amistoso de 1 rodada com a R1 fechada → `add_round` → a R2 é gerada;
  - torneio oficial → `AppError`.

### MA-08 · Criar o torneio da turma pede trabalho demais **[L]** — P2

- **Evidência:** `_start_free_tournament` só pede o nome e cria um torneio avulso (`standalone`). O vínculo com a turma (`scope="class"`) e "Inscrever todos os ativos" (`register_active_members_in_tournament`) existem, mas em outras telas.
- **Requisito:** a criação amistosa pede nome, número de rodadas e, se quiser, a turma. Com turma, o torneio nasce `scope="class"` e já inscreve os alunos ativos.
- *(rev. 4)* Ninguém digita o que o app já sabe (WCAG 3.3.7, entrada redundante):
  - o nome já vem preenchido ("Torneio Amistoso dd/mm/aaaa");
  - as rodadas vêm com 5;
  - a turma é uma lista com "Nenhuma" como primeira opção.
  
  Número de rodadas inválido mostra o que digitar ("de 1 a 30"), e Enter cria.
- **Aceite:** criar com uma turma de 3 alunos ativos e 1 inativo → torneio `class`, com 3 jogadores e `free_mode=1`. *(rev. 4)* Rodadas "0" → `AppError` com a faixa válida.

### MA-10 · "Sim/Não" para escolher pontos **[L]** — P2

- **Evidência:** o diálogo de entrada tardia usa "Sim" e "Não", e o texto precisa explicar qual botão é qual. Tem também o erro "esta entrando".
- **Requisito:** botões que dizem o que fazem: "Dar 0,5 por rodada", "Começar com zero" e "Cancelar". O texto ganha acento correto.
- *(rev. 4)* Com uma rodada aberta, uma segunda pergunta, também com verbos: "Jogar já nesta rodada", "Esperar a próxima" e "Cancelar". São no máximo duas perguntas por aluno. O texto diz o efeito em números: "entra com 1 ponto (2 rodadas × 0,5)". Esc cancela (WCAG 2.1.2), e o estado não depende de cor.
- **Aceite:** os textos dos botões e a mensagem, verificados no teste da tela. *(rev. 4)* A mensagem traz o total de pontos.

### MA-11 · O aviso promete o que o modo não faz **[L]** — P2 *(rev. 4)*

- **Evidência:** o aviso lista "Ausência de punições estritas por atraso", e a súmula diz o contrário (MA-05). Não diz que o torneio não vale rating, nem que dá para pôr mais uma rodada.
- **Requisito:** o aviso lista só o que existe depois desta revisão, em linguagem de professor:
  - "Alunos entram a qualquer momento, já na rodada em andamento ou na próxima.";
  - "Refaça a rodada com quem está presente e ajuste mesas à mão.";
  - "Súmula sem W.O. automático por atraso.";
  - "Mais uma rodada quando sobrar tempo.";
  - "Não vale rating FIDE nem CBX.".
- **Aceite:** teste da tela com os cinco itens, e a frase antiga sobre punições ausente.

---

### MA-12 · O nome do modo colide com o perfil padrão **[L]** — P3 *(rev. 5)*

- **Evidência:**
  - todo torneio nasce com o perfil `free`, cujo rótulo é "Livre/Escolar" (`constants.py`, `TOURNAMENT_PROFILES`), inclusive os oficiais;
  - o painel do torneio (`tournaments/pages.py`) mostra "Perfil: Livre/Escolar" num torneio em **Modo Oficial**;
  - o menu diz "Torneio | Livre", o aviso diz "Modo Livre", e o usuário e o comentário do código dizem "Modo Amistoso".
- **Requisito:**
  1. O painel do torneio mostra também a linha "Modo: Amistoso" ou "Modo: Oficial", lida de `friendly_mode`.
  2. **Decisão D1 (usuário, 2026-11-27): continua "Modo Livre".** O nome visível não muda. Se um dia mudar, é uma linha (`FRIENDLY_MODE_LABEL`, MA-01).
- **Aceite:** painel de torneio oficial → "Modo: Oficial"; amistoso → o rótulo do módulo.

### MA-13 · A barra de Rodadas não acompanha a marca **[L]** — P3 *(rev. 5)*

- **Evidência:** o item "Re-emparceirar (Modo Livre)" entra no menu "Mais" quando a barra é **montada** (`pairing_results/view.py`, `_round_more_items`). Ligar o modo (MA-07) ou trocar de torneio não refaz o menu.
- **Requisito:** os itens do modo ("Re-emparceirar", "Mais uma rodada") ficam sempre no menu e conferem a marca **no clique**. Em torneio oficial, o serviço recusa com a mensagem do modo (MA-03, MA-09). Isso combina com a regra da revisão geral: a ação não some, explica por que não vale.
- **Aceite:** menu montado com torneio oficial, depois o modo é ligado → o clique em "Re-emparceirar" funciona sem remontar a tela.

### MA-14 · Preset, manual e convenções **[L]** — P3 *(rev. 5)*

- **Evidência:**
  - o assistente "Entrada tardia…" do RGS-24, em Rodadas e no Painel, lê `late_entry_points`, que nasce 0 em todo torneio. No Modo Amistoso, o caminho da tela de jogadores pergunta 0,5. São duas respostas padrão para a mesma pergunta;
  - o README descreve escolas e turmas, mas não o Modo Amistoso.
- **Requisito:**
  1. O preset de criação (MA-01) grava `late_entry_points = 0.5`, o meio ponto pedagógico. O assistente e a tela de jogadores passam a propor o mesmo valor.
  2. O README ganha uma seção curta "Modo Amistoso (escolar)" com o que o modo faz e o que não faz.
  3. Nenhum método público novo na `Database`: as regras novas moram em serviços, então o snapshot `tests/fixtures/database_public_api.txt` não muda. Se mudar, o snapshot é atualizado no mesmo item.
- **Aceite:** torneio criado pelo modo → `late_entry_points == 0.5`; README com a seção.

---

## 7. Glossário (um sentido por termo)

- **Modo Amistoso:** o torneio com `free_mode=1`, aberto pelo menu "Torneio | Livre". No app, o rótulo visível é "Modo Livre".
- **Perfil do torneio:** `tournament_profile` (`free`, `club` ou `fide`). Só o `fide` muda alguma coisa (registro 092 e avisos do TRF). O perfil "Livre/Escolar" é o padrão de **todo** torneio e **não** liga o Modo Amistoso.
- **Re-emparceirar:** refazer a rodada aberta com quem está presente.
- **Entrada tardia:** a definição da revisão geral, com 0 ou ½ por rodada perdida no Modo Amistoso.

---

## 8. O que está sólido e não deve mudar

1. A marca dedicada `free_mode` (migração v42) e o padrão 0 para torneios legados.
2. A preferência "Não mostrar novamente" do aviso (`free_mode_notice_hidden`), gravada nas duas saídas.
3. O motor de pareamento: o Modo Amistoso não troca o holandês.
4. O ajuste manual de mesa com motivo e auditoria (RGS-16): já vale em qualquer modo.
5. A regra de motivo do RGS-34 para apagar rodada com resultado.
6. *(rev. 3)* Duplicar ou dividir um torneio amistoso copia a marca (`database_tournament_core.py`, `free_mode = src.free_mode`). É o desejado: a cópia de um evento escolar continua escolar.
7. *(rev. 3)* Desligar o modo de um torneio que já tem entrantes com 0,5 por rodada não inválida nada: ½ é valor aceito pelo TRF (bye H).

**Riscos de regressão explícitos (rev. 3):**
- os testes antigos de Modo Livre (`tests/test_ui_layout.py`) trocam o serviço por dublês. Os novos testam o serviço de verdade, e os antigos são ajustados só no que a interface mudou;
- `prepare_late_entry` do caminho **oficial** não muda de comportamento.

---

## 9. Revisões

| # | Lente | O que acrescentou ou mudou |
|---|---|---|
| v1 | Três pontos de vista (árbitro FIDE, programador sênior, professor) | MA-01 a MA-06, MA-08, MA-10 |
| rev. 1 | **Lacunas:** o que o professor precisa e o modo não tem | MA-07 (ligar e desligar com auditoria), MA-09 (mais uma rodada), decisão D2 (rating interno) |
| rev. 2 | **Simplificações:** tirar antes de pôr | MA-05 sem coluna nova nem migração v60 (deriva de `free_mode`); MA-04 usa o plano do assistente, e a conta do mixin some; MA-02 e MA-07 dividem uma função pura; o MA-01 deixa de guardar textos |
| rev. 3 | **Riscos:** o que pode quebrar ao mudar | MA-03 conta e guarda as submissões QR que somem em cascata; trava de escrita durante o Gacrux registrada como risco aceito; MA-04 ganha "entrar já nesta rodada" em transação única (corrige a incoerência E3); §8 ganha a cópia da marca e os riscos de regressão |
| rev. 4 | **Usabilidade escolar** (professor e criança; WCAG 2.2: 2.1.2, 3.3.3, 3.3.7) | MA-11 (aviso honesto); MA-10 com segunda pergunta e o total de pontos na mensagem; MA-08 com campos preenchidos e erro que diz a faixa válida |
| rev. 5 | **Coerência com o resto do app** | MA-12 (nome e painel; decisão D1), MA-13 (menu confere a marca no clique), MA-14 (preset de 0,5 alinha o assistente do RGS-24, README, snapshot da API) |
| v7 | **Decisões do usuário** | D1: continua "Modo Livre". D2: o rating interno pergunta antes de contar o amistoso (serviço recusa sem a resposta) |
| v8 | **Acento em comentário e docstring** | O usuário confirmou ("Continua"): comentário e docstring também levam acento. Só log e identificador ficam ASCII |

---

## 10. Definição de pronto (vale para cada MA)

1. Teste que **falha pelo motivo certo**, escrito antes da mudança. Na camada de serviço sempre que der; teste de tela só para o que é tela.
2. Correção na causa.
3. Verde: `check_quality.ps1 -Fast`, as suítes afetadas e, no fim da onda, `-m "not gui"` e `-m gui`.
4. Método público novo da `Database` entra em `tests/fixtures/database_public_api.txt`.
5. Texto visível com acento; palavra nova na lista de `scripts/check_ui_accents.py` quando o gate pedir.

---

## 11. Andamento da implementação (2026-11-27)

A tabela por onda mora no roadmap. Aqui fica o que a implementação decidiu além do texto de cada MA.

- **Arquivos novos:**
  - `src/services/friendly_mode.py`: regra do modo e `FriendlyModeService`;
  - `tests/test_friendly_mode.py`: serviço, sem tela;
  - `tests/test_ui_friendly_mode.py`: telas, marcador `gui`.
- **Sem migração.** Schema continua v59. Nenhum método público novo na `Database`: `create_player` só ganhou o parâmetro `entry_round`, e o snapshot lista nomes.
- **API nova dos serviços:**
  - `PairingService.repair_open_round` e `repair_open_round_preview`;
  - `late_entry_plan` e `register_late_entry` com `join_open_round`;
  - `FriendlyModeService`: `create`, `school_classes`, `set_enabled`, `add_round` e `late_entry`.
- **Eventos de auditoria novos:** `round_repaired`, `free_mode_changed` e `friendly_round_added`. O `late_entry_registered` passa a valer também no modo.
- **Telas:**
  - aviso com `NOTICE_ITEMS`;
  - diálogo de criação (nome, rodadas, turma);
  - entrada tardia com duas perguntas, pelo serviço;
  - re-emparceirar com prévia, motivo e motor reserva;
  - "Mais uma rodada" no menu e na geração;
  - caixa do modo em Configurações → Avançado;
  - linha "Modo" no painel do torneio.
- **Decisões do usuário (v7):**
  - **D1:** continua "Modo Livre";
  - **D2:** o rating interno pergunta antes de contar o amistoso (`internal_rating_question`, `free_mode_confirm_internal_rating`), nas duas telas que aplicam o rating.
- **Acentos (v7):** a súmula oficial imprime "Tolerância", e os textos de `src/`, dos scripts e dos documentos foram acentuados (Anexo B, itens 12 a 15).
- **Acentos (v8):** comentários e docstrings de `src/`, `scripts/` e `tests/` acentuados (Anexo B, itens 23 a 26); o gate de acentos passou a cobrar verbo com pronome ("gravá-lo").

---

## Anexo A — Sondagem executada (2026-11-27)

Script fora do repositório, com o motor próprio (`fide_dutch`), sobre um banco temporário:

| # | Cenário | Resultado |
|---|---|---|
| E1 | Re-emparceirar com 1 resultado lançado | Recusado: "1 resultado será apagado. Informe o motivo…" |
| E2 | Re-emparceirar com 1 aluno ativo | A geração falha **depois** de apagar; rodadas restantes: nenhuma |
| E3 | Entrada tardia amistosa com R2 fechada e R3 aberta | `starting_points=1.0`, `entry_round=4`; depois de re-emparceirar, o aluno joga a R3 |
| E5 | Perfil `fide` em torneio amistoso | Gravado: `profile=fide`, `free_mode=1`; `late_tolerance_minutes=0` |
| E6 | 4 alunos, 5 rodadas, motor próprio | As 5 rodadas saem (o motor próprio repete confronto com penalidade) |

---

## Anexo B — Log de ações desta revisão

| # | Ação | Por quê |
|---|---|---|
| 1 | Busca por "amistoso"/"friendly"/`free_mode` em `src/` e `tests/`; mapa do código por um subagente de leitura | Achar onde o modo vive. O nome no código é "Modo Livre" |
| 2 | Sondagem E1–E6 num banco temporário (Anexo A) | Trocar hipótese por evidência **[E]** antes de escrever requisito |
| 3 | v1 da spec e do roadmap, nos três pontos de vista | Pedido da tarefa |
| 4 | Revisões 1 a 5: lacunas, simplificações, riscos, usabilidade escolar, coerência | Pedido da tarefa; cada uma registrada na seção 9 |
| 5 | Onda 0: o teste do literal falhou primeiro pelo import, depois pelas 11 ocorrências em `src/ui` | Dono único da regra antes de corrigir |
| 6 | Onda 1: testes de serviço vermelhos (`repair_open_round` ausente; `join_open_round` ausente; súmula com "perde a hora marcada"), depois verdes | TDD por item |
| 7 | Correção de um padrão de motivo que escondia o RGS-34 no "jogar já" | Um teste mostrou o resultado anotado apagado sem motivo |
| 8 | Correção do import de `FRIENDLY_MODE_LABEL` em `pairing_results/view.py` | 15 testes de tela quebraram; o `import *` escondia o nome do ruff |
| 9 | Onda 2: recusa do perfil FIDE em `_prepare_profile` e em `set_enabled`; bloqueio no TRF16 em submissão; nota da D2 no rating interno | Fronteira com o oficial |
| 10 | Ondas 3 e 4: telas com testes `gui` próprios | MA-07 a MA-13 |
| 11 | Ferramentas crapper/dryer/mutator: não existiam no projeto | Instaladas na v7 (item 18) |
| 12 | D1 e D2 respondidas pelo usuário: continua "Modo Livre"; o rating interno pergunta | Fim das pendências. D2 com teste vermelho primeiro (`internal_rating_question` ausente), depois serviço que recusa sem `friendly_confirmed` e a pergunta nas duas telas |
| 13 | Acentos em `src/`: varredura de todo literal de texto (fora docstring, log, chave, comparação), 257 literais trocados por regra de palavra e 31 trocas de contexto ("esta" → "está", "e" → "é") revisadas uma a uma | Pedido do usuário. Comentário e nome de variável ficam ASCII, como manda a convenção do projeto (`scripts/check_ui_accents.py`) |
| 14 | Acentos nos scripts (437 literais: mensagens dos gates, manual gerado, piloto, diplomas de exemplo) e na ajuda do `check_quality.ps1` | O usuário lê essas mensagens no terminal |
| 15 | Acentos nos documentos Markdown (cerca de 5 mil palavras, só na prosa: código, link e caminho protegidos) e 42 trocas "e"/"esta" de alta precisão | Pedido do usuário |
| 16 | A troca "Socio do Clube" → "Sócio do Clube" quebraria categoria já cadastrada: a marca de prêmio passou a casar sem acento (`tag_key`), com teste vermelho primeiro | Correção na causa: a marca é escrita à mão, e acento não muda quem ela é |
| 17 | Lista fechada do gate de acentos: 209 → 267 palavras | As palavras corrigidas não voltam |
| 18 | Ferramentas do ub-mode: `coverage`, `radon` e `pytest-timeout` no extra `dev` (o `uv.lock` só ganhou entradas); `scripts/crap.py` (crapper), `scripts/dry.py` (dryer) e `scripts/mutate.py` (mutator, item 21), com `tests/test_quality_tools.py` | O projeto não tinha nenhuma das três |
| 19 | Dryer no código do modo: nenhum par ≥ 0,8 | O único par 1,0 perto do modo (`_late_entry_starting_points`, banco × migração) já existia |
| 20 | Crapper: 11 funções ≥ 10. Divididas (`repair_open_round`, `late_entry_plan` ×2, `register_late_entry`, `apply_tournament_ratings`, `create_player`, `add_round`, três de tela) e cobertas (`EntradaTardiaTest` de tela, teto de rodadas) | Meta do ub-mode: CRAP < 10 |
| 21 | Mutator: o `mutmut` 2.5 no Windows deu como sobrevivente um mutante que nem compila (conferido à mão). Trocado por `scripts/mutate.py`: mutação pela AST, cache de bytecode próprio por mutante e restauração garantida do arquivo | Resultado em que dá para confiar |
| 22 | `friendly_mode.py`: 104 mutantes; 29 sobreviveram na primeira rodada. `BordasTest` (teto de 30 rodadas, 5 por padrão, tolerância de 1 min, limite de rodadas, "1 aluno", turma inativa, ligar o que já está ligado, "jogar já" sem rodada) deixou 5, todos equivalentes na prática (`or 0` em campo que o banco sempre preenche; `name or ""`; padrão do motor reserva, que o motor de teste não distingue) | Cobrir o descoberto, matar os sobreviventes |
| 23 | Comentários e docstrings: 3.333 trocas pelo mapa de 671 palavras sem homógrafo, em 182 arquivos, só em trecho português (mais palavras-guia em PT que em EN) e com `código`, aspas, caminho e URL protegidos. Conferido por token: nenhum token de código mudou | Pedido do usuário (v8). Antes deles, `scripts/check_ui_accents.py` dizia que comentário ficava ASCII; agora só o log fica |
| 24 | Mapa extra de 151 palavras achadas pelo dicionário PT ("destruído", "holandês", "diálogo", "rótulo"...): 392 trocas. Ficaram de fora termos técnicos (cache, index, macOS, radon) e nomes de tema (sepia, indigo). "a mão" virou "à mão" nas 12 locuções (escrito à mão, montada à mão) | Revisão das candidatas uma a uma |
| 25 | "e" → "é" e "esta" → "está" só por regra de contexto ("não e", "que e", "já e", "esta sendo", "esta em"): 133 trocas revisadas; 2 falsas desfeitas à mão ("feio e impossível", "ela e a mesa esquecida"). Na etapa do mapa, 1 desfeita à mão: "SO" (sistema operacional) tinha virado "SÓ". O que a regra não decide sozinha ficou | Precisão antes de cobertura |
| 26 | Verbo com pronome: 9 acentuados à mão ("trocá-la", "incluí-la", "recebê-lo"); dois estavam na tela ("sem gravá-lo", "preenchê-lo"). O gate de acentos agora cobra essa forma e não confunde mais o "la" de "trocá-la" com "lá" (testes vermelhos primeiro em `test_rgs27_acentos.py` e `test_ui_accents_lint.py`) | Fechar a fresta pela qual "grava-lo" chegou à tela |
| 27 | Verificação da v8: gate `-Fast` OK; `-m "not gui"` 2101 passaram e 4 pularam; `-m gui` 308 passaram e 1 pulou; `-m gacrux` 94 passaram | Nada commitado |
