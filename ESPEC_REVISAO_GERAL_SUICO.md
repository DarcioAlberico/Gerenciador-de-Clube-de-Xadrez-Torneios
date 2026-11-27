# Especificação — Revisão Geral Suíço

> **Status:** proposta **v2** (2026-11-26). A v1 foi reescrita depois da revisão adversarial; o Anexo A traz o que mudou e por quê.
> **Roadmap:** `ROADMAP_REVISAO_GERAL_SUICO.md`.
> **Base analisada:**
> - branch `fix/diploma-categoria-e-ata-equipes` @ `95fbdef` (2026-08-06);
> - executável `dist/Albericus.exe` de 2026-11-11 08:03;
> - banco `albericus_auto_shutdown_20261111_080728.db`;
> - `%LOCALAPPDATA%\Albericus\logs\app.log`.
>
> **Gatilho:** relato do árbitro Rodrigo Oliver sobre o torneio de 13/11/2026.

## 0. Por que este documento existe

O relato do árbitro, em resumo:

- O motor "teve 100% de precisão no gerenciamento do torneio".
- Ao errar um resultado, ele habilitou **"mudanças perigosas"**. Aí "dava um bug nas datas e o programa parava de funcionar"; com algumas tentativas, deu certo.
- A interface precisa ficar **mais prática** para editar resultado errado, acrescentar bye, tirar quem sai e incluir quem entra.

Este documento transforma o relato e cinco revisões independentes (seção 9) em requisitos verificáveis. Cada achado tem:

- um ID `RGS-NN`;
- a evidência (`arquivo:linha`, log ou execução);
- a causa-raiz;
- o requisito;
- o critério de aceite, escrito como teste **que falharia contra uma implementação vazia**.

Regra da casa: **nada some calado, nada fica meio gravado, e o que funciona não se mexe** (seção 8).

**Severidade:**
- **P0** impede o torneio, ou o `.exe` distribuído não é o programa testado.
- **P1** corrompe dado, viola regra FIDE, afeta prêmio ou derruba a operação.
- **P2** atrito operacional (a queixa "mais prático").
- **P3** polimento ou dívida.

**Marcação de evidência:**
- **[E]** executado e visto falhar;
- **[L]** lido no código, caminho completo;
- **[H]** hipótese, falta reproduzir.

---

## 1. O incidente: hipóteses, não fatos [H]

> Até o retorno do F0.6 (log, `.db` e versão do executável do árbitro), **nada nesta seção vale como [L]**. As peças estão confirmadas uma a uma; a sequência que as liga, não.

### 1.1 Qual executável o árbitro usou?

As premissas não fecham entre si:
- O `.exe` de 11/11 **não consegue parear** com o motor padrão, porque o Gacrux não está nele (RGS-01).
- O árbitro relata 100% de precisão.

Então vale uma de três coisas:

| Hipótese | Se verdadeira | Consequência para a spec |
|---|---|---|
| **(α)** Usou outro build: o `Albericus.zip` de 02/06, um build posterior ou o código-fonte | O Gacrux funcionou | O RGS-01 não explica o incidente, mas continua P0 para o próximo usuário |
| **(β)** O torneio estava no motor reserva (`fide_dutch`) | Os 100% são do motor próprio | A seção 8, item 1, ("Gacrux no caminho feliz") não tem prova de campo; o RGS-18 sobe de importância |
| **(γ)** O build tinha ARB-01 (commit `587d333`, 30/07) ou não | Se não tinha, a única rota de correção era "mudanças perigosas" | Explica o passo 1 abaixo |

### 1.2 Sequência mais provável (cada peça confirmada isoladamente)

1. **O árbitro errou um resultado numa rodada já fechada.**
   - No código atual, a tela Rodadas já oferece desbloqueio na hora: são 2 diálogos e 2 motivos (`pairing_results/view.py:809-866`).
   - Mas a mensagem do serviço ainda manda para *"habilite mudanças perigosas nas configurações do torneio"* (`pairing_service.py:2221-2224`), e a opção continua visível na aba Regras.
   - Ele escolheu essa rota, por (γ) ou por ser a mais curta para quem não quer escrever dois motivos. **[L]**
2. **Em Configurações, marcou a caixa e clicou Salvar.** Salvar revalida e regrava o formulário **inteiro**: torneio, datas, agenda, regras estruturais, prêmios, categorias e colunas (`tournament_settings_ui.py:800-994`). **[L]**
3. **Qualquer data fora do padrão aparece como lixo e é apagada ou corrompida.** O motivo: `MaskedDateEntry.insert()` não aplica a máscara de validação, e `get()` devolve `""` para data inválida (`support.py:477-487`, `:717-726`). Casos executados **[E]**:
   - `2026-11-13 08:00` aparece como `20/26/1113` e vira vazio;
   - `2010/05/12` vira `0512-10-20` (**corrompido**);
   - `1/2/2026` e `1985` viram vazio.
   - Datas em `dd/mm/aaaa` (7 torneios no `.db` real) são convertidas **corretamente**: não são a causa.
4. **A gravação não é atômica.** `save_profile` faz 3 gravações, cada uma com conexão e commit próprios (`tournament_service.py:223-228`). Depois, a tela grava prêmios, categorias e colunas em separado. **[E]**
   - Uma linha de prêmio em branco mostra *"Informe o nome de cada prêmio."*, mas `allow_dangerous_changes=1` **já foi gravado**.
   - O árbitro acha que nada salvou e tenta de novo: são as "algumas tentativas".
5. **"Parava de funcionar".** Candidatos:
   - **(a)** A seta ↓ na agenda abre o calendário com `grab_set()` global em `+0+0`, e a janela passa a ignorar cliques (`support.py:589`, `:634-711`). **[E parcial]**
   - **(b)** Só sob (α): a correção recalcula na thread da UI o retrato de cada rodada fechada posterior, com um subprocesso do Gacrux para cada uma. **[L]**
   - **(c)** Uma exceção num callback do Tk some sem rastro: `console=False` e não existe `report_callback_exception`. **[L]**

---

## 2. P0 — o executável distribuído não é o programa testado

A suíte local passa: cerca de 1 140 testes, 0 falhas (`-k "not ui"`). Isso prova **menos** do que parece, por dois motivos:
- `tests/conftest.py:17-18` força `fide_dutch` + `albericus`, então a suíte quase não exercita o motor **padrão** (só 9 arquivos usam `gacrux_swiss`);
- nenhum teste roda o build congelado.

### RGS-01 · O Gacrux não roda no `.exe` **[E]**

**Evidência:**
- O `pyi-archive_viewer` mostra que o `.exe` contém `src.services.pairing.gacrux.berger`, mas **não** contém `pairingchecker`, `pairingdutch` nem `tiebreakchecker`. Eles são chamados como script (`gacrux_engine.py:95-118`, `gacrux_tiebreak_engine.py:174-186`), nunca importados.
- No build congelado, `sys.executable` é o próprio `Albericus.exe`.
- Os scripts usam imports de topo relativos à própria pasta (`import version`, `from helpers import *`: `pairingchecker.py:16-24`). `import src.services.pairing.gacrux.pairingchecker` falha com `ModuleNotFoundError: version`, então `collect_submodules` **não resolve**.
- Não existe `main(argv)`: o argparse lê o `sys.argv` global (`commonmain.py:117`).

**Efeito:**
- Com o padrão `pairing_system=gacrux_swiss` (`database_tournament_core.py:28`), a geração de rodada falha com `AppError("Motor Gacrux nao encontrado")`.
- O desempate cai para o motor próprio. Isso **não é silencioso**: há evento `tiebreak_engine_fallback`, faixa e modo estrito (`pairing_service.py:2946-2972`, `:2998-3017`). Mas no modo padrão (não estrito) a classificação é **publicada** pelo motor reserva, que não segue o C.07 §16 (RGS-18).
- Log de 11/11 08:04:27: *"Motor gacrux de desempate falhou no torneio 20; usando o motor próprio."*

**Requisito:**
- O Gacrux roda como **subprocesso do próprio `.exe`**: `Albericus.exe --gacrux pairing|tiebreak <args>`.
- `app.py` trata esse modo **antes de importar `src.ui`**, insere a pasta `gacrux/` em `sys.path` e despacha para o script com `sys.argv` montado.
- Os arquivos `.py` do Gacrux entram no `albericus.spec` como `datas`, e o tempo máximo do subprocesso continua valendo.
- **Medir o custo por chamada.** No onefile, cada filho reextrai cerca de 100 MB. Se passar de 1 s, migrar o build para **onedir**.
- Thread em processo está **descartada**: ela não pode ser morta no tempo máximo, e o Gacrux tem estado de módulo.

**Aceite:** dentro do `.exe` (via RGS-05):
- criar torneio de 8 jogadores, gerar 3 rodadas com `gacrux_swiss`, fechar cada uma;
- `tiebreak_engine_report(t).used == "gacrux"`;
- **0** eventos `tiebreak_engine_fallback` no banco.

### RGS-02 · Os textos não são encontrados no `.exe` **[E]**

**Evidência:**
- `i18n\pt_BR.json` está empacotado, mas `src/ui/i18n.py:43-44` procura em `Path(sys.executable).parent`.
- Log: *"Catálogo de textos não encontrado: …\dist\i18n\pt_BR.json"*, seguido de dezenas de *"Chave de texto ausente"*. Na tela, barra lateral, jogadores e o Cancelar dos diálogos aparecem como chave.

**Requisito:**
- Uma **única** `resource_path()` para recursos **empacotados** (a de `support.py:176`, que trata `sys._MEIPASS`).
- `src/core/database.py:306-308` usa o mesmo padrão `sys.executable`. **Conferir** se ali a intenção é a pasta de **dados** (portátil, ao lado do `.exe`), o que está certo, ou um recurso, o que é bug; documentar a diferença no docstring.
- Catálogo não encontrado no build congelado é erro fatal com diálogo.

**Aceite:**
- Teste unitário com `sys.frozen=True` e `sys._MEIPASS` simulados: o catálogo carrega.
- O RGS-05 confere que `t("nav.group.tournament") != "nav.group.tournament"`.

### RGS-03 · O Gacrux quebra quando os pontos não batem com o sistema de pontos que ele deduz **[E]**

**Evidência** (reproduzido em 2026-11-26, 5 jogadores, motor padrão):
- `bye_points=0,5`, o exemplo da própria tela: R1 ok, **R2 falha** com `KeyError: 'D'` (`gacrux/tiebreak.py:514`).
- Ajuste de pontos de −0,5: R2 falha com `TypeError`.
- `bye_points=0`: o Gacrux pareia quem teve PAB **com 1 ponto** enquanto a classificação mostra 0. Grupo errado, sem erro.
- Entrada tardia com 0,5: o pareamento sai, o desempate quebra e cai no motor reserva (com evento).

**Causa:**
- O TRF do motor escreve o PAB sempre como `U` (`export_federation.py:668`, `:887`), que o Gacrux conta como 1.
- `reconcile_scores` (`gacrux_trf.py:158-175`) converte déficit positivo em células de bye, mas diferença negativa só gera aviso.
- O leitor deduz o sistema de pontos pelos pontos declarados (`scoresystem.py:237`) e quebra.
- Não há fallback no pareamento: o `AppError` chega cru ao árbitro (`gacrux_engine.py:132-160`).

**Regra:** C.04.1 / C.04.3. Os grupos de pontuação usam a pontuação oficial do torneio.

**Requisito (definitivo, Fase 3):**
- O TRF de pareamento emite o **registro 162** (sistema de pontos) com o valor do PAB igual a `bye_points`.
- Os ajustes vão no **registro 299**. O Gacrux lê os registros 162 a 202, 240, 299 e 320 (`trf2json.py:43-71`). Alternativa: alimentar o Gacrux com o TRF25 que o projeto já exporta.
- A checagem `assert_trf_scores_consistent` roda **depois** de `reconcile_scores`; antes disso ela quebraria a entrada tardia, que hoje funciona.

**Requisito (contenção, Fase 0):**
- A mesma checagem recusa o TRF inconsistente com a mensagem *"O motor FIDE não aceita bye de 0,5 / ajuste de pontos nesta versão"*.
- A recusa oferece **"Parear com o motor reserva (não homologado)"** com auditoria. Nunca um `KeyError` cru.

**Aceite:**
- Teste parametrizado com `bye_points ∈ {0, 0,5, 1}` × {sem ajuste, ajuste ±0,5, entrada tardia 0,5} × 4 rodadas, marcado `-m gacrux`.
- **Na Fase 0:** cada caso gera com o Gacrux **ou** a mensagem de contenção, sem exceção crua.
- **Na Fase 3:** todos geram pelo Gacrux, e os pontos lidos no JSON do Gacrux são iguais aos de `standings()`.

### RGS-04 · Exceção em callback do Tk some sem rastro **[L]**

- **Evidência:** `albericus.spec:36` define `console=False`, e não existe `report_callback_exception`.
- **Requisito:** `AlbericusApp.report_callback_exception` grava `logger.exception` e abre o diálogo de erro inesperado já existente, com ID. *(A varredura dos 67 `except Exception: pass` fica no RGS-32, não neste hotfix.)*
- **Aceite:** um teste chama `app.report_callback_exception(RuntimeError, err, tb)`. Uma linha `ERROR` contendo `RuntimeError` vai ao log e o diálogo é criado (verificado pelo *spy* do diálogo).

### RGS-05 · Não existe teste do build congelado **[L]**

**Requisito:**
- `Albericus.exe --self-test <dir>` roda sem janela e grava `<dir>/selftest.json` (com `console=False` não há stdout). O arquivo tem um item por passo: i18n, banco temporário migrado, torneio sintético com 8 jogadores e 3 rodadas pelo Gacrux, desempate pelo Gacrux, exportação de 1 PDF e 1 TRF.
- Sai com código ≠ 0 se algum passo falhar.
- O `build.bat` roda o self-test, sai com `errorlevel` e não tem `pause`.

**Aceite:** com o código **anterior** à F0.2 e com o self-test já incluído, o build sai com código ≠ 0 e o JSON marca `i18n` e `gacrux` como falhos. Depois das correções, o código de saída é 0.

---

## 3. P1 — integridade de dados

### RGS-06 · Campo de data apaga e corrompe em silêncio **[E]**

**Evidência:** seção 1.2, passo 3.

**Requisito, o domínio primeiro.** Um módulo puro `src/domain/dates.py`:

`parse_date(texto, *, permite_ano=False) -> DataVazia | Data(date) | Ano(int) | DataInvalida(texto, motivo)`

| Entrada | Resultado |
|---|---|
| `""` | `DataVazia` |
| `aaaa-mm-dd` | `Data` |
| `aaaa-mm-dd[ T]HH:MM[:SS]` | `Data` (a hora é descartada) |
| `dd/mm/aaaa`, `d/m/aaaa`, `dd-mm-aaaa` | `Data` |
| `aaaa/mm/dd` | `Data` |
| `aaaa` | `Ano`, **somente** com `permite_ano=True` (uso: `players.birth_date`, que segue a lista FIDE: `fide_list.py:11-18`, `export_federation.py:576-581`) |
| ano com 2 dígitos, data impossível, lixo | `DataInvalida` (não se adivinha século) |

**Requisito, o widget:**
- `MaskedDateEntry` usa `parse_date` no `insert`.
- Valor inválido aparece **como está gravado**, com borda de erro, nunca a máscara mutilada.
- Ganha `value()` tri-estado e `has_invalid()`. O `get()` mantém o contrato.
- Todo formulário com data consulta `has_invalid()` antes de salvar e **recusa**, destacando o campo.

**Requisito, os dados legados:**
- **Sem `CHECK` e sem reconstruir tabela.** O SQLite não faz `ADD CHECK`, e reconstruir com `foreign_keys=ON` (`database.py:440`) dispara o `ON DELETE CASCADE` (`database_schema.py:1101`).
- Na abertura, um relatório "Datas a revisar" lista os valores que `parse_date` não aceita, com atalho para o cadastro.
- Normalização para ISO só dos convertíveis, numa migração com backup antes. Ano sozinho em `birth_date` fica como está.

**Aceite:**
- `test_dates.py` com a tabela acima, linha a linha.
- **Teste de UI:** carregar `2010/05/12` e salvar sem tocar → banco com `2010-05-12`.
- **Teste de UI:** data incompleta → salvar recusado; banco inalterado.

### RGS-33 · "Atualizar" um jogador apaga o ano de nascimento **[L]** *(novo na v2)*

- **Evidência:** o cadastro do jogador usa `MaskedDateEntry` (`tournament_players/view.py:151`), e `get()` de `1985` devolve `""`. Jogador importado da lista FIDE (só ano) perde o nascimento ao corrigir o rating. Isso muda a **categoria por idade** e, com ela, o **prêmio**.
- **Requisito:** o campo de nascimento usa `parse_date(..., permite_ano=True)` e mostra `1985` como ano.
- **Aceite:** editar o rating de um jogador com `birth_date="1985"` mantém `"1985"`, e a categoria não muda.

### RGS-07 · Regras de data diferentes em cada fronteira **[E]**

**Evidência:**
- `_normalize_optional_date` (`tournament_service.py:667`) aceita o formato brasileiro; `_validated_schedule` (`:796`) aceita só ISO.
- `cutoff_date`, `category_reference_date` e `team_lineup_deadline` são texto livre (`tournament_settings_ui.py:278`, `:639`).
- A importação TRF aceita datas impossíveis: `2026.02.30` vira `2026-02-30` (`trf_import.py:36-46`).

**Requisito:**
- Toda fronteira usa `parse_date`: UI, serviço, TRF, XLSX, Google Forms e `result_server`.
- O registro 132 continua `AA/MM/DD`, **como manda o TRF16** (`trf_import.py:72`).
- Data impossível é **recusada** com linha e coluna do arquivo.

**Aceite:**
- Importar TRF com `2026.02.30` dá erro citando a linha.
- Registro 132 `26/11/13` dá `2026-11-13`.
- Um teste-varredura reprova `strptime`/`date.fromisoformat` fora de `domain/dates.py`, com lista fechada de exceções justificadas.

### RGS-08 · Salvar configurações grava pela metade **[E]**

**Evidência:** seção 1.2, passo 4. A importação TRF tem o mesmo problema (`import_service.py:348-408`).

**Requisito:**
- `Database.transaction()`: context manager reentrante, com conexão por thread (`threading.local`). Os métodos `db.*` reutilizam a conexão aberta e, sem transação, mantêm o comportamento atual (abrir, gravar, fechar). Isso permite migrar caso a caso.
- Caso de uso `save_tournament_configuration(perfil, premios, categorias, colunas)`: **valida tudo primeiro** sem tocar no banco e grava tudo numa transação, precedida de backup.
- `PRAGMA journal_mode=WAL` e `busy_timeout=5000`, porque a thread do RGS-10 e o `result_server` gravam e leem ao mesmo tempo.

**Aceite:**
- Falha injetada em cada gravação → todas as tabelas envolvidas com `SELECT *` idêntico ao anterior, **exceto** 1 evento `backup_created` (`database.py:1004-1011`).
- Prêmio em branco → nenhuma coluna de `tournament_settings` muda.

### RGS-09 · Auditoria registrada antes da ação, e laço de confirmações **[E]**

**Evidência:**
- `_audit_schedule_loss` (`tournament_service.py:202`) e o evento estrutural (`:736`) gravam **antes** das recusas de `:211-221`.
- Reduzir rodadas junto com uma mudança de `initial_order` entra no laço "Confirme…" → "Informe o motivo…": `rounds_count` nunca muda, e cada volta grava mais um `schedule_rounds_reduced` falso (`tournament_settings_ui.py:954-980`).

**Requisito:**
- `plan_tournament_configuration(...) -> list[Confirmacao]`, uma função pura que devolve **todas** as confirmações necessárias.
- A tela mostra **um** diálogo com elas.
- A auditoria entra na transação do RGS-08.

**Aceite:**
- O cenário combinado salva em 1 tentativa, com exatamente 1 evento de cada tipo.
- Cancelar → 0 eventos.

### RGS-10 · Correção de resultado não é atômica, trava a UI e reconcilia com dado futuro **[L]**

**Evidência:**
- `pairing_service.py:2013-2027`, `:2295-2338`. A sequência é resultado → auditoria → cascata → retratos, cada passo numa conexão própria, sem backup.
- O retrato N é recalculado por `_standings(up_to_round=N)` (`:2808-2830`), que **não corta** os ajustes por `round_number` (a coluna existe: `database_schema.py:1092`), inclui quem entrou depois de N e usa o `player_status` **atual** (`tiebreaks.py:515`). *(Achado novo na v2.)*

**Requisito:**
1. Resultado, auditoria, cascata e a marca `standings_snapshots.reconcile_pending=1` numa transação, com backup antes. A coluna nova entra por migração.
2. Uma thread de trabalho reconcilia os retratos pendentes, comunica a UI só via `after()` e é idempotente e retomável: o app, ao abrir, termina as pendências.
3. O retrato N usa **só** os ajustes com `round_number ≤ N`, os jogadores inscritos até N e o status vigente na rodada N (`status_at_round(N)`, a partir do histórico ARB-05).
4. As guardas globais `_GACRUX_TIEBREAK_INFLIGHT` e `_GACRUX_TIEBREAK_CACHE` (`pairing_service.py:193`, `:2866`, `:2937`) passam a ser seguras para threads: reentrância por `threading.local` e cache com `Lock`. Sem isso, a classificação pedida pela UI durante a reconciliação sai pelo motor reserva.

**Aceite:**
- Com `_standings` instrumentado, `update_result` numa rodada fechada retorna com **0** chamadas a `_standings`. O trabalhador termina com N retratos gravados e `reconcile_pending=0`.
- Falha injetada no 3º retrato → reabrir o app termina a reconciliação.
- Jogador inscrito na R4 não aparece no retrato reconciliado da R3.
- Ajuste da R5 não altera o retrato da R3.

### RGS-11 · Fechar rodada não é idempotente **[E]**

- **Evidência:** `pairing_service.py:2029-2081` não checa o status.
  - Um segundo clique gera 2 `round_closed`.
  - O snapshot é regravado com `ON CONFLICT DO UPDATE` sem histórico.
  - O backup tem resolução de segundos (`src/core/database.py:949`).
  - O status `closed` é gravado antes do snapshot.
- **Requisito:** rodada já fechada → no-op. Status e snapshot numa transação. Backup com nome único.
- **Aceite:** chamar `close_round` 2× → exatamente 1 `round_closed`, 1 snapshot e **1** backup.

### RGS-12 · Calendário que congela a janela **[E parcial]**

- **Evidência:** `support.py:589` (a seta ↓ abre), `:641-711` (`overrideredirect` + `grab_set()`); geometria `+0+0` no teste.
- **Requisito:**
  - Abrir só por F4, Alt+↓ ou um botão de calendário visível.
  - Sem grab global: o calendário fecha ao perder o foco, ao clicar fora e no Esc.
  - A posição fica limitada à tela.
- **Aceite (UI):**
  - a seta ↓ no campo **não** cria `Toplevel`;
  - com o calendário aberto, `grab_current()` é `None`;
  - um clique em outro campo destrói o popup.

### RGS-35 · "Ausente" perde prêmio como se fosse desistente **[L]** *(novo na v2)*

- **Evidência:** `prizes.py:53` define `WITHDRAWN_STATUSES = {"withdrawn", "desistente", "absent", "ausente", "expelled"}`. Com `prize_exclude_withdrawn` ligado, quem faltou **a uma rodada** (status "ausente" pendente) fica sem o prêmio que ganhou.
- **Requisito:** a exclusão vale só para desistência definitiva e expulsão, avaliadas no **fim** do torneio. O ausente concorre.
- **Aceite:** jogador "ausente" na última rodada e 1º colocado → recebe o prêmio com `prize_exclude_withdrawn=1`.

---

## 4. P1 — conformidade FIDE do emparceiramento

### RGS-13 · Ordem inicial e título **[E]**

**Evidência:**
- O TRF do Gacrux numera pelo primeiro rating não nulo (internacional, depois rating, depois nacional) e ignora `initial_order` (`export_federation.py:636-642`, `trf16.py:59-66`, `gacrux_engine.py:56-63`).
- Os dois motores desempatam rating só por nome (`pairing_service.py:1692-1708`, `fide_dutch.py:23-28`).
- Com `initial_order=national_rating`: o Gacrux deu A-C/D-B; o motor próprio, o correto B-D/C-A.

**Regra:** C.04.2: ordem por rating, depois título, depois alfabética, salvo regulamento.

**Requisito:** uma `seeding_key(player, initial_order)` única, usada pelo TRF, pelos dois motores e pela aceleração.

**Aceite:**
- Dois jogadores com 2000 ("Alpha" sem título e "Zeta" GM): Zeta é o nº 1 nos dois motores.
- Com `national_rating`, os dois motores dão o mesmo emparceiramento.

### RGS-14 · Cor do tabuleiro 1 na R1 não se reproduz **[E]** — *P2 (reclassificado na v2)*

**Evidência:**
- Sem o registro 152, o Gacrux sorteia com `random.random()` (`pairing.py:142`), e o `XXC` é ignorado (`trf2json.py:958-960`).
- 6 planos deram B, P, P, B, B, B.
- O sorteio é permitido; o defeito é a **prévia divergir da geração**. O comentário de `trf16_records.py:76` está errado.

**Requisito:**
- A cor é sorteada uma vez (ou escolhida), gravada em `tournament_settings.initial_color` e enviada como `152 W|B`.
- A prévia e a geração usam o mesmo valor.

**Aceite:** 20 prévias e a geração dão a mesma cor; trocar a configuração antes da R1 troca a cor.

### RGS-15 · Proibição de emparceiramento derruba a rodada para o motor reserva **[L]**

- **Evidência:** `pairing_service.py:1381-1390`. O Gacrux lê o registro 260 (`trf2json.py:58`, `:988`).
- **Requisito:** emitir o registro 260 e manter o Gacrux.
- **Aceite:** com 1 proibição, a rodada sai pelo Gacrux (`report.used == "gacrux"`) e respeita a proibição.

### RGS-16 · Ajuste manual de mesa sem trilha e sem verificação **[L]**

**Evidência:**
- `pairing_service.py:2493-2560` não audita e permite pôr jogador na mesa de bye ou num reencontro.
- O verificador do Gacrux nunca roda em modo de checagem.

**Regra:** C.04.2: alteração manual é registrada.

**Requisito:**
- Depois de toda geração, `pairingchecker -c` (modo de verificação) compara a rodada gravada com a que o Dutch produziria.
- Em rodada **editada à mão**, a divergência é esperada: ela é registrada no evento `pairing_manual_adjustment`, com antes, depois e motivo obrigatório, e não bloqueia.
- Em rodada **gerada**, a divergência é bug: aviso bloqueante.

**Aceite:**
- Ajuste sem motivo → recusado.
- Ajuste com motivo → 1 evento com a divergência do checker anexada.
- Rodada gerada → checker sem divergência.

### RGS-17 · Falso "bye repetido" bloqueia o fechamento **[E]**

- **Evidência:** `diagnostics.py:52-56`. Quando `avoidable is True` (`:159`), quem teve PAB e pediu Z/H depois trava `close_round`.
- **Requisito:** só acusar quando o bye **atual** for PAB (`U`).
- **Aceite:** o cenário fecha; um PAB repetido de verdade continua bloqueando.

### RGS-18 · Motor reserva fora do holandês **[E/L]**

**Evidência:**
- Grupo ordenado por Buchholz/SB antes do número de pareamento (`constraints.py:168-181`).
- PAB da R1 para o cabeça de chave quando os ratings empatam (`fide_dutch.py:42-48`).
- W.O. não impede o PAB (`histories.py:110-119`).
- Empate de cor dá brancas ao maior rating (`constraints.py:287-294`).
- O desempate não segue o C.07 §16 (`tiebreaks.py:558-569`).

**Decisão:** o motor próprio é **reserva**. Corrigir PAB, W.O. antes do PAB e cor E.4; rotular *"motor reserva — não homologado FIDE"*; exigir confirmação para usá-lo. Reescrevê-lo como holandês completo está fora do escopo. **Sob a hipótese (β) da seção 1.1, reavaliar.**

**Aceite:** um teste por item corrigido; o seletor mostra o rótulo; uma rodada pareada pelo reserva mostra aviso persistente.

### RGS-36 · Cache do desempate Gacrux ignora pontos de bye, ajustes e pontos iniciais **[L]** — *P1, Fase 1 (separado do RGS-18 na v2)*

- **Evidência:** a chave de `_GACRUX_TIEBREAK_CACHE` (`pairing_service.py:2878-2895`, `:2937`) não inclui `starting_points`, `bye_points` nem ajustes. Mudar um deles serve a classificação antiga.
- **Requisito:** a chave inclui todo dado que entra no TRF do desempate. Melhor ainda: a chave é o hash do próprio TRF gerado.
- **Aceite:** mudar `bye_points` com o torneio em andamento muda a classificação já na chamada seguinte.

### RGS-19 · A saída do Gacrux não é conferida **[L]**

- **Evidência:** `gacrux_engine.py:171-191` pula em silêncio um número sem mapeamento.
- **Requisito:** cada jogador a parear aparece exatamente uma vez e nenhum ausente aparece; senão, `AppError` com o TRF no log.
- **Aceite:** um JSON com jogador duplicado ou faltante é recusado.

---

## 5. P2 — a interface "mais prática"

**Princípio:** a ação mora onde está o objeto. Resultado se corrige na mesa; retirada, retorno e bye, na linha do jogador. **Nenhuma tarefa de rodada abre a tela de Configurações.**

| Tarefa | Hoje | Alvo (máximo de ações, testado) |
|---|---|---|
| Lançar resultado | 1 tecla por mesa | 1 tecla, mais W.O. por tecla e Desfazer |
| Corrigir resultado em rodada fechada | cerca de 7 cliques e 2 motivos, ou a rota pelas Configurações | **3 ações:** menu/atalho, resultado, motivo + Enter |
| Bye solicitado | cerca de 8 cliques, lista sem busca | **4 ações:** menu, tipo, motivo, Enter |
| Retirar / reintegrar | 7 cliques ou mais com rolagem; reintegrar **não tem saída** | **4 ações:** menu, escopo, motivo, Enter |
| Entrada tardia | formulário + aviso impreciso | 1 tela |

### RGS-20 · "Corrigir resultado…" num diálogo único **[L]**

**Requisito:**
- Clique direito, Shift+F10 ou Ctrl+E numa mesa (em Rodadas e no Painel) abre **um** diálogo com mesa, jogadores, resultado atual e o novo resultado em botões (`1-0`, `½`, `0-1`, `+/-`, `-/+`, `-/-`).
- O motivo tem uma linha, sugestões ("erro de digitação", "súmula diverge", "decisão de apelação") e Enter confirma.
- Se a rodada estiver fechada, o diálogo avisa *"A rodada 3 será desbloqueada por 15 min só para esta correção"*. O **mesmo motivo** serve ao desbloqueio e à correção: valida pela regra **mais estrita** das duas (`correction_reason_error`, hoje igual a `unlock_reason_error`: mínimo de 5 caracteres), e um teste fixa que as duas continuem iguais.
- **Cascata:**
  - com a rodada seguinte aberta e sem resultados, o diálogo oferece "Reparear rodada 4";
  - com resultados lançados, avisa que reparear apagaria N resultados e manda para o fluxo de exclusão com motivo (RGS-34).
- **Desfazer a correção:** o histórico da mesa mostra a correção, e "Reverter esta correção…" reaplica o resultado anterior **pelo mesmo fluxo**, com motivo e auditoria.
- A mensagem de `pairing_service.py:2221` **para de citar "mudanças perigosas"**. A opção sai da aba Regras e vai para "Avançado", **gravando sozinha** (RGS-08).

**Aceite (UI, contando eventos):**
- corrigir uma rodada fechada com ≤ 3 ações e **sem** criar a tela de Configurações;
- o banco recebe 1 desbloqueio, 1 correção e 1 evento de cascata, os três com o mesmo motivo;
- reverter gera 1 nova correção, e o resultado volta ao original.

### RGS-34 · Excluir rodada gerada apaga resultados sem motivo **[L]** *(novo na v2)*

- **Evidência:** `delete_generated_round` (`pairing_service.py:2454-2475`) exclui rodada não fechada **com resultados lançados**; faz backup, mas não pede motivo e usa um texto de auditoria fixo.
- **Requisito:**
  - Se houver ao menos 1 resultado, a exclusão exige motivo e mostra "N resultados serão apagados".
  - O evento guarda os resultados apagados no `before`.
- **Aceite:** excluir com 3 resultados sem motivo → recusado; com motivo → evento contendo os 3 resultados.

### RGS-21 · Desfazer, contador e W.O. por tecla em Rodadas **[L]**

**Requisito:**
- Toast *"Mesa 7 → 1-0 · Desfazer (Ctrl+Z)"*; o `toast.py` já suporta ação.
- Desfazer restaura e audita.
- Contador "32/40 lançadas".
- Teclas `w`/`p`/`a` com a confirmação de `pairing_arbitration/pending.py:314-340`.

**Aceite:** lançar e desfazer → resultado anterior no banco e 2 eventos.

### RGS-22 · Retirar / reintegrar na linha do jogador **[E/L]**

**Evidência:**
- Reintegrar um desistente exige motivo (`participation.py:78-86`), que a tela nunca pede (`tournament_players/view.py:351-356`).
- "Atualizar" grava o status direto (`state.py:208` → `db.update_player`), **sem o histórico ARB-05**.
- O pareamento lê o `active` **atual** (`pairing_service.py:1300`): não existe "retorno automático".

**Requisito:** menu na linha do jogador (Pareamento, Classificação, Jogadores):
- **"Faltar só à rodada N…"**: é um **bye Z solicitado** via `bye_policy`, que não conta no limite (`bye_policy.py:139-146`). **O status não muda.** Se a rodada N já foi gerada e o jogador está numa mesa sem resultado, o diálogo oferece "lançar W.O. na mesa 7?".
- **"Retirar do torneio…"**: desistência definitiva com motivo e "vale a partir da rodada N" (`participation.py:90-100`).
- **"Reintegrar…"**: motivo e "volta na rodada N".
- Toda mudança de status passa pelo serviço de participação; `db.update_player` deixa de aceitar `status`.
- Os status ganham descrição: Desistente, Ausente, "Não emparceirado".

**Aceite:**
- "Faltar só à R4" → bye Z na R4, status inalterado, o jogador pareado na R5.
- Reintegrar desistente pela tela → status ativo e 1 evento de histórico.
- `db.update_player(..., status=...)` → `TypeError`.

### RGS-23 · Bye solicitado em poucos passos **[L]**

**Requisito:**
- Na linha do jogador: "Bye na próxima rodada… (H ½ / Z 0)", com o saldo da política ("1 de 2 byes usados; último permitido na R5").
- Os seletores de jogador do painel (byes, ajustes, proibições) viram combobox com busca.
- Se a rodada já foi gerada, o diálogo explica e oferece W.O.

**Aceite:** com 100 jogadores, digitar "sil" deixa no máximo 5 opções, e Enter grava o bye do jogador certo.

### RGS-24 · Assistente de entrada tardia **[L]**

**Requisito:**
- Botão "Entrada tardia…" em Rodadas e no Painel: nome, rating (busca FIDE/CBX), "entra na rodada N" e os pontos de `late_entry_points`.
- As rodadas 1…N−1 aparecem como **células derivadas** (Z/H no TRF, como `reconcile_scores` já faz). **Nada é gravado em rodada fechada** e o limite de byes não é consumido; a `bye_policy` (seção 8) fica intacta.
- O texto atual ("foge ao regulamento", sem acento) é substituído.
- Se a rodada N já foi gerada, o jogador entra na N+1.

**Aceite:** inscrever após a R3 fechada → a R4 o inclui, a classificação mostra os pontos configurados, e nenhuma linha nova aparece em `pairings` das rodadas 1–3. *Requer o RGS-03 definitivo (Fase 3) para a entrada tardia com 0,5 pelo Gacrux.*

### RGS-25 · Botão primário com estado e confirmação de fechamento **[L]**

- **Evidência:** "Fechar rodada" fica em "Mais", sem confirmação (`view.py:77`, `:958-967`).
- **Requisito:** botão primário em três estados: "Lançar resultados (32/40)" → "Fechar rodada 3" (confirmação com pendências) → "Gerar rodada 4".
- **Aceite:** a sequência dos três rótulos num teste de UI; Esc na confirmação não fecha.

### RGS-26 · Erro de regra não pode sumir em 5 s **[L]**

- **Evidência:** `support.py:344`.
- **Requisito:** `AppError` de regra aparece em faixa fixa, com fechar e a ação sugerida; o toast fica só para sucesso.
- **Aceite:** uma recusa de correção cria a faixa, e ela continua lá depois de 10 s.

---

## 6. P3 — polimento e dívida

| ID | Achado | Requisito |
|---|---|---|
| RGS-27 | Texto ASCII ao lado de acentuado ("Permitir mudanças perigosas" sob "Permissões e visibilidade"; "Pré-visualizar próxima rodada"); status cru: "Rodada 3 - closed" (`view.py:396`) | Textos de tela no `pt_BR.json`; um teste com lista fechada de palavras sem acento em `src/ui`; status traduzido |
| RGS-28 | `DropdownMenu.destroy` não sai do `ScalingTracker` (CTk 5.2.2), então `set_widget_scaling` aborta e as configurações do painel não carregam (`app.py:912-930`) | Patch local; teste que reconstrói a tela 10× e muda a escala |
| RGS-29 | `ALTER TABLE` de migração em autocommit (`migration_engine.py:33-39`) | Migração por versão em transação explícita *(o WAL foi para o RGS-08)* |
| RGS-30 | Suíço por equipes (semente recalculada, titular ausente derruba a geração, W.O. conta como confronto); Baku: a fórmula está no Handbook C.04.5, ao contrário do que diz o ROADMAP | Spec própria; corrigir o ROADMAP |
| RGS-31 | O laço de atualização do painel morre calado (`refresh.py:56-61`) | Religar no `finally`, com log |
| RGS-32 | 67 `except Exception: pass` | Converter para `logger.debug(exc_info=True)` ou justificar; teste reprova um `pass` novo sem comentário |
| RGS-37 | A suíte padrão não exercita o Gacrux (`conftest.py:17-18`) | Marcador `-m gacrux`, rodando pareamento e desempate com o motor padrão em CI e no DoD |

---

## 7. Glossário (um sentido por termo)

- **PAB** — bye atribuído pelo **emparceiramento** ao jogador que sobra. Vale `bye_points`. Nunca 2×, nem para quem venceu por W.O. No TRF é `U`.
- **Bye solicitado** — pedido do jogador antes da geração: **H** (½), **Z** (0) ou **F** (1, se o regulamento permitir). Não impede o PAB, exceto o F.
- **W.O.** — partida não jogada: `+/-`, `-/+`, `-/-`. Não conta como confronto nem como cor.
- **Faltar a uma rodada** — bye Z solicitado; o status não muda.
- **Retirada (desistência)** — saída definitiva até ser reintegrado, com motivo; vale a partir da rodada N.
- **Ausente** — status operacional de quem não compareceu; **não** é desistência e **não** perde prêmio (RGS-35).
- **Entrada tardia** — inscrição depois da R1; as rodadas anteriores são células derivadas Z/H e o jogador recebe `late_entry_points`.
- **Correção** — mudança de resultado em rodada fechada, com motivo, desbloqueio pontual, auditoria e reconciliação.
- **Desbloqueio pontual** — permissão de uma rodada, com prazo (15 min por padrão, máximo 240) e motivo.
- **Mudanças perigosas** — permissão do torneio inteiro, sem prazo. Legado em "Avançado".
- **Retrato (snapshot)** — classificação gravada no fechamento da rodada, a que foi publicada. Reconciliado só com dados até aquela rodada.
- **Cascata** — rodadas posteriores pareadas sobre um resultado que mudou.
- **Motor reserva** — `fide_dutch`, não homologado, usado só com confirmação.

---

## 8. O que está sólido e não deve mudar

Antes de tocar qualquer item abaixo: teste de caracterização.

1. **Gacrux no caminho feliz** (bye 1,0, sem ajuste, sem proibição): coincidiu com o `bbpPairings.exe` no mesmo TRF, num cenário de bancada. *A prova de campo depende da seção 1.1.*
2. **Política de bye solicitado** (`bye_policy.py`): limites, última rodada, recusa para rodada gerada ou jogador inativo.
3. **Tipos de bye** F/H/Z/U e o efeito no PAB; letras no TRF.
4. **W.O.:** não conta como confronto nem para cor.
5. **Ausência, retirada e retorno no pareamento:** a lista `-u`, as rodadas ausentes como Z, o histórico ARB-05.
6. **Preferências de cor do motor próprio:** absoluta, forte e leve; diferença ±2; três cores iguais seguidas; exceção dos líderes na última rodada.
7. **Todos-contra-todos e Scheveningen:** calendário sorteado e guardado.
8. **Modelo de correção** (`corrections.py`): motivo, desbloqueio com prazo, cascata, retratos substituídos com histórico. Muda o **fluxo de tela**, não o modelo.
9. **Fallback do desempate auditado** (evento + faixa + modo estrito).
10. **Lançamento por teclado,** confirmação de W.O. que nomeia mesa e jogadores, aviso de edição de BYE, geração em segundo plano.
11. **Tempo máximo no subprocesso do Gacrux,** com o erro mostrado.

**Riscos de regressão explícitos:**
- `Database.transaction()` toca 258 blocos `with self.connect()`; a migração é caso a caso, com o comportamento antigo como padrão (RGS-08).
- Gacrux como subprocesso do `.exe`: o estado de módulo fica isolado por processo, e isso é desejável (RGS-01).
- A normalização de datas não toca `birth_date` que seja só ano (RGS-06).

---

## 9. As cinco revisões

| # | Lente | Achados | O que mudou por causa dela |
|---|---|---|---|
| 1 | **Árbitro internacional:** regra FIDE do motor (C.04, C.07) | RGS-03, 13 a 19 | O "100%" vale no caminho feliz; fora dele, o motor padrão quebra ou desvia |
| 2 | **Incidente e dados reais** (log, `.db`, `.exe`) | RGS-01, 02, 06, seção 1 | O `.exe` distribuído não é o programa testado: virou P0 com self-test |
| 3 | **UX operacional** (*click-path audit* das 5 tarefas) | RGS-20 a 28 | "Mudanças perigosas" é sintoma de fluxo: a ação vai para a mesa e para a linha do jogador |
| 4 | **Engenharia** (atomicidade, idempotência, falhas silenciosas) | RGS-04, 07 a 12, 29 | "Algumas tentativas" se explica por gravação parcial e auditoria antes da ação |
| 5 | **Crítico adversarial sobre a v1** | RGS-33 a 37; 2 evidências erradas; 3 requisitos perigosos | v1 (nota 5,5) → v2; ver o Anexo A |

---

## 10. Definição de pronto (vale para cada RGS)

1. Teste que **falha pelo motivo certo**, escrito antes da mudança. Quando o Tk real torna o teste honesto impraticável, registrar por quê e cobrir pela camada de serviço.
2. Correção na causa; uma guarda que só esconde o erro não conta.
3. Tudo verde: `pytest` completo (com UI) **e** `pytest -m gacrux` **e** o self-test do `.exe` (RGS-05).
4. Changelog com o ID.
5. P0 e P1: o replay (seção 11) sem divergência nova.

## 11. Torneio de replay (ferramenta da Fase 0, portão de toda fase)

Script `scripts/replay_torneio.py`. Para o TRF do torneio do árbitro (F0.6) e os torneios de `exports/`, para cada rodada *k*:

- **Pareamento:** regenerar a partir das rodadas 1..k−1, primeiro pelo Gacrux e depois pelo `bbpPairings` (com TRF no dialeto do bbp: `BBW`/`BBD`/`BBU`, `XXR`, `XXC`), e comparar com o real.
- **Desempate:** o Gacrux contra o valor publicado no retrato. O bbp **não** calcula desempate.

Critério: zero divergência, ou divergência justificada por ajuste manual registrado (RGS-16). A linha de base atual é registrada na F0 e só pode encolher.

---

## Anexo A — 5ª revisão (crítico adversarial) e como foi tratada

**Nota da v1: 5,5/10.** Defeitos aceitos e como foram resolvidos:

| # | Defeito apontado | Tratamento na v2 |
|---|---|---|
| 1 | A seção 1 conflitava com o RGS-01 (sem Gacrux no `.exe`, de onde vem o "100%"?) | Seção 1 inteira passa a [H]; hipóteses α/β/γ na 1.1; a 1.2.5(b) vale só sob α |
| 2 | RGS-01 impossível como escrito: imports de topo, sem `main(argv)`, thread não se mata | Subprocesso `--gacrux` do próprio `.exe`, `datas`, medição onefile/onedir; thread descartada |
| 3 | O `CHECK` de datas quebrava o nascimento só com ano (padrão FIDE) e exigia reconstruir tabela com CASCADE | Sem `CHECK`; `permite_ano`; relatório "Datas a revisar" |
| 4 | "Desempate cai em silêncio": **errado** (há evento e faixa) | Corrigido no RGS-01; o fallback auditado entrou na seção 8 |
| 5 | Registro 132 `13/11/26 → 2026-11-13`: **errado** (o TRF16 define AA/MM/DD) | RGS-07 corrigido |
| 6 | Lacunas: nascimento apagado ao editar, retrato reconciliado com dado futuro, desfazer correção, excluir rodada com resultados, ausente perdendo prêmio | RGS-33, RGS-10 (item 3), RGS-20, RGS-34, RGS-35 |
| 7 | Cache do Gacrux era P1 do motor **padrão**, não do reserva | RGS-36, na Fase 1 |
| 8 | Guardas globais do Gacrux sem segurança de thread | RGS-10, item 4 |
| 9 | "Retorno automático" não existe | "Faltar só à rodada N" = bye Z solicitado (RGS-22) |
| 10 | Z/H em rodada fechada violava a `bye_policy` | Células derivadas (RGS-24) |
| 11 | A suíte não exercita o Gacrux | RGS-37 + `-m gacrux` no DoD |
| 12 | Replay só na F3, mas exigido em toda fase; RGS-24 dependia do RGS-03 definitivo | Replay movido para a F0; dependência explícita no RGS-24 e no roadmap |
| 13 | WAL na Fase 4, mas necessário na Fase 1 | WAL/`busy_timeout` no RGS-08 |
| 14 | Critérios fracos (RGS-01, 05, 08, 10, 11, 23, Fase 2) | Reescritos com oráculos concretos |
| 15 | Escopo do hotfix inflado (67 `except: pass`) | Só `report_callback_exception` na F0; o resto no RGS-32 |
| 16 | Estimativas irreais | Revistas no roadmap |
| 17 | RGS-14 mal classificado (o sorteio é permitido) | Reclassificado para P2 |

## Anexo B — Log de ações desta revisão

| Ação | Por quê |
|---|---|
| Localizado o código em `C:\PythonCurso\Albericus`; `C:\Python-Chess2\Albericus` é a pasta de dados | Correção do usuário |
| Leitura de `corrections.py`, `pairing_service.py` 2100-2330, `save_profile`, `tournament_settings_ui` 140-1036, `MaskedDateEntry` | Rastrear "mudanças perigosas + datas" |
| Perfil dos formatos de data no `.db` de 11/11 | Achar os dados reais que disparam o bug |
| Simulação das funções puras do campo de data | Confirmar o RGS-06 |
| Leitura de erros do `app.log` (57 MB) | RGS-02, RGS-01, RGS-28 |
| `pyi-archive_viewer` no `.exe` | Provar o RGS-01 e o RGS-02 |
| `pytest -k "not ui"`: cerca de 1 140 aprovados, 4 pulados, 0 falhas | Linha de base |
| Revisões 1, 3 e 4 por agentes independentes, somente leitura | Lentes separadas, sem ancorar na hipótese |
| Reexecução do cenário `bye_points=0,5`: `KeyError 'D'` na R2 | Verificação própria do achado mais grave |
| Revisão 5 adversarial sobre a v1; conferência própria de 5 contra-afirmações dela (fallback auditado, desbloqueio na tela de Rodadas, registro 132, `conftest`, exclusão de rodada, status de prêmio) | Não aceitar a crítica sem prova |
| Reescrita para a v2 | Incorporar a revisão 5 |
