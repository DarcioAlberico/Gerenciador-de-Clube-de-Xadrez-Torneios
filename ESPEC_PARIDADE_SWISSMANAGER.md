# Especificação: Paridade com Swiss-Manager

Especificação técnica das lacunas identificadas em
[`docs/RELATORIO_SWISSMANAGER_VS_ALBERICUS.md`](docs/RELATORIO_SWISSMANAGER_VS_ALBERICUS.md).
A ordem de execução está em
[`ROADMAP_PARIDADE_SWISSMANAGER.md`](ROADMAP_PARIDADE_SWISSMANAGER.md).

## Princípios (herdados do projeto)

1. O desktop + SQLite local continuam a autoridade do torneio.
2. Toda alteração de estado crítico gera auditoria e, quando aplicável, backup.
3. Conformidade FIDE é **assistência ao árbitro**, nunca homologação automática.
4. Cada entrega tem migração compatível com bancos antigos e testes do serviço.
5. Nada quebra emparceiramento ou resultados já existentes.

Convenção de versão de banco: cada item abaixo que toca schema avança
`schema_version` em uma unidade e registra a migração em
`src/database/migrations/legacy_migrations.py`, com backup automático antes de
alterar bancos antigos (padrão já usado nas etapas anteriores).

---

## E1 — Desempates configuráveis (P0)

### Problema

Hoje a ordem de desempate é fixa em
`src/services/pairing/tiebreaks.py::order_player_standings`
(pontos → Buchholz → Buchholz mediano → Sonneborn-Berger → ...). O Swiss-Manager
permite ao árbitro escolher **quais** critérios e **em que ordem**, com
parâmetros (ex.: Buchholz com corte). O regulamento de cada torneio define isso,
então precisa ser por torneio.

### Modelo de dados

Adicionar à tabela `tournament_settings`:

```sql
ALTER TABLE tournament_settings ADD COLUMN tiebreak_sequence TEXT NOT NULL DEFAULT '';
```

- `tiebreak_sequence`: JSON com lista ordenada de critérios. Vazio = usar o
  padrão atual (retrocompatível). Exemplo:

```json
[
  {"code": "points",            "params": {}},
  {"code": "direct_encounter",  "params": {}},
  {"code": "buchholz_cut1",     "params": {"cut_low": 1, "cut_high": 0}},
  {"code": "buchholz",          "params": {}},
  {"code": "sonneborn_berger",  "params": {}},
  {"code": "wins",              "params": {}}
]
```

Equipes: adicionar `team_tiebreak_sequence TEXT NOT NULL DEFAULT ''` com a mesma
ideia (match points, game points, Sonneborn-Berger por equipes, Buchholz por
equipes, confronto direto).

### Serviço

Em `tiebreaks.py`:

- Criar um **registro de critérios** `TIEBREAK_REGISTRY: dict[str, Criterion]`,
  cada um com: `code`, `label`, `direction` (sempre desc), `needs_params`,
  função `compute(player_stat, stats, params) -> float` e
  `explain(...) -> dict` (para o relatório de desempates já existente).
- `order_player_standings(stats, sequence=None)`: se `sequence` vier, monta a
  chave de ordenação dinamicamente a partir do registro; senão usa o default.
- `calculate_player_standings(...)` passa a calcular **sob demanda** apenas os
  critérios presentes na sequência (mais performance em torneios grandes).
- Manter `player_tiebreak_components` cobrindo todos os critérios do registro,
  para o "Por que esta posição?" continuar explicável.

`PairingService`/`TournamentService` leem `tiebreak_sequence` das settings e
repassam para os helpers puros.

### UI

Na tela `Config. torneio` (`src/ui/screens/tournaments.py`), aba de desempates:

- Lista ordenável (mover para cima/baixo) de critérios disponíveis x ativos.
- Para `buchholz_cut*`: campos numéricos de corte (descartar N piores / N
  melhores).
- Botão "Restaurar padrão FIDE" (sequência recomendada).
- Validação: pelo menos `points` como primeiro critério; impedir duplicados.

### Critérios de aceite

- Dois torneios com sequências diferentes produzem ordens diferentes a partir
  do mesmo conjunto de resultados.
- Sequência vazia reproduz **exatamente** a classificação atual (teste de
  regressão sobre fixtures existentes).
- O relatório/explicação de desempate mostra os critérios na ordem configurada.
- Migração cria a coluna e mantém torneios antigos com comportamento idêntico.

---

## E2 — Desempates adicionais (P0)

### Problema

O Albericus calcula: Buchholz, Buchholz mediano, Sonneborn-Berger, confronto
direto, vitórias e performance. Faltam critérios usados em regulamentos
brasileiros e pela FIDE.

### Critérios a adicionar (todos no `TIEBREAK_REGISTRY` de E1)

| Código | Nome | Definição |
|---|---|---|
| `buchholz_cut1` | Buchholz Cut-1 | Soma dos scores dos adversários descartando o(s) menor(es). Parametrizar `cut_low`/`cut_high`. (FIDE padrão atual.) |
| `buchholz_cut2` | Buchholz Cut-2 | Idem descartando os 2 menores |
| `aro` | Rating médio dos adversários | Média de rating dos oponentes (com regra para sem-rating) |
| `aroc` | ARO Cut | ARO descartando extremos |
| `cumulative` | Progressivo (Sonneborn cumulativo) | Soma das pontuações parciais após cada rodada |
| `cumulative_opp` | Progressivo dos adversários | Soma do progressivo dos oponentes |
| `koya` | Sistema Koya | Pontos contra quem fez ≥ 50% dos pontos |
| `black_games` | Nº de partidas com pretas | Critério de cor |
| `black_wins` | Vitórias com pretas | Critério de cor |
| `games_played` | Nº de partidas jogadas | Desempate técnico |

Notas de implementação:

- **Adversário virtual / partidas não jogadas**: o SM oferece tratar
  bye/WO/ausência via "jogador virtual" (FIDE 13.15.x). Implementar o ajuste de
  Buchholz para partidas não jogadas como opção de parâmetro
  (`unplayed: "virtual" | "real" | "self"`), default FIDE atual ("virtual
  opponent").
- Tudo permanece em funções **puras** em `tiebreaks.py`, recebendo `stats` já
  montado. Sem acesso a banco.

### Critérios de aceite

- Fixtures pequenas com empates conhecidos validam cada critério contra cálculo
  manual documentado no teste.
- O tratamento de partidas não jogadas é coberto por teste dedicado (bye + WO).
- Cada critério aparece no relatório de desempates com sua fórmula.

---

## E3 — Relatório de variação de Elo FIDE (P1)

### Problema

`rating_service.py` atualiza um **rating interno** do clube a partir da
performance (`_next_rating = current + (perf - current) * weight`). Isso não é o
cálculo oficial FIDE de variação de rating (Rc = Ro + K·(W − We)), que o SM
produz em "Estatísticas de rating FIDE" e que acompanha o envio do torneio.

### Modelo de dados

Nova tabela (cálculo é derivável; persistir o relatório para auditoria/reimpressão):

```sql
CREATE TABLE IF NOT EXISTS fide_rating_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    rating_type TEXT NOT NULL DEFAULT 'fide',   -- fide | cbx | lbx
    ro INTEGER,            -- rating inicial
    k INTEGER,             -- fator K aplicado
    games_rated INTEGER,   -- nº de partidas válidas p/ rating
    score REAL,            -- pontos obtidos contra ranqueados
    we REAL,               -- score esperado (somatório dp)
    delta REAL,            -- ΔElo = K*(W - We)
    rc REAL,               -- rating calculado (Ro + Δ) p/ a lista
    rp INTEGER,            -- rating performance
    n_over_400 INTEGER,    -- nº de pares ajustados pela regra dos 400
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);
```

Adicionar a `tournament_settings`: `fide_rating_evaluation TEXT DEFAULT 'none'`
(`none | fide | cbx | lbx`) e por jogador um `k_factor` opcional
(`players.k_factor INTEGER`).

### Serviço (`FideRatingService`, novo módulo)

Implementar a tabela de expectativa FIDE (`p(d)` para diferenças de 0..400) e:

- `expected_score(rating_a, rating_b) -> float` com **regra dos 400** (diferenças
  acima de 400 tratadas como 400).
- `k_factor(player) -> int`: 40 (novos, < 30 partidas, ou sub-18 e < 2300),
  20 (rating < 2400), 10 (rating ≥ 2400 alguma vez). Permitir override manual
  (`players.k_factor`).
- `compute_tournament_report(tournament_id, rating_type) -> list[row]`: para cada
  jogador, somar `We` por adversário ranqueado, `W` real, ΔElo, Rc, Rp.
- Tratar **adversários sem rating** conforme regra (ignorar para FIDE) e
  partidas não jogadas (não contam para rating).
- Idempotente por `(tournament_id, player_id, rating_type)`.

> Atenção de conformidade: documentar que o valor é **estimativa de apoio**; a
> homologação oficial continua sendo da federação. Mesma postura já adotada para
> o TRF.

### UI

Na tela `Classificação`/`Relatórios`: ação "Relatório de rating FIDE" gerando
tabela e exportação CSV/XLSX/PDF, com colunas Ro, K, n, W, We, ΔElo, Rc, Rp.
Reaproveitar `export_service.py`.

### Critérios de aceite

- Caso de teste com 2–3 jogadores e ratings conhecidos bate ΔElo com cálculo
  manual (incluindo regra dos 400 e jogador sem rating).
- Recalcular o mesmo torneio não duplica linhas.
- Exportação abre em Excel com cabeçalho correto.

---

## E4 — Distribuição de prêmios (P1)

### Problema

`tournament_settings.prizes` é só texto livre. O SM tem diálogo de prêmios em
dinheiro: por colocação, por categoria, por tabuleiro, sistema **Hort** (mistura
colocação + categoria), divisão de prêmios empatados e dedução de imposto do
organizador.

### Modelo de dados

```sql
CREATE TABLE IF NOT EXISTS tournament_prizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- overall | category | board | special
    label TEXT NOT NULL,           -- ex.: "1o lugar", "Sub-12", "Melhor feminino"
    category TEXT DEFAULT '',      -- quando kind=category
    rank_from INTEGER,             -- faixa de colocação (1..N)
    rank_to INTEGER,
    amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'BRL',
    cumulative INTEGER NOT NULL DEFAULT 0,  -- jogador acumula geral+categoria?
    created_at TEXT NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);
```

Adicionar `tournament_settings.prize_policy TEXT DEFAULT 'best_only'`
(`best_only | hort | cumulative`) e `prize_tax_percent REAL DEFAULT 0`.

### Serviço (`PrizeService`, novo)

- `allocate(tournament_id) -> list[allocation]`: aplica a política sobre a
  classificação final.
  - `best_only`: cada jogador recebe **só o maior** prêmio a que tem direito.
  - `cumulative`: geral + categoria somam quando `cumulative=1`.
  - `hort`: divisão proporcional entre colocação e categoria (regra Hort).
  - Empates: dividir a soma das faixas igualmente entre os empatados (regra de
    "merge" do SM).
- Aplicar `prize_tax_percent` como dedução.
- Reutiliza a classificação final (com os desempates de E1/E2) para definir
  posição e categoria de cada jogador.

### UI

Aba "Prêmios" em `Config. torneio`: CRUD de prêmios, escolha de política,
imposto. Tela de resultado "Lista de prêmios" exportável (CSV/XLSX/PDF) e
opcional no site HTML/portal.

### Critérios de aceite

- Cenário com prêmio geral + categoria + empate confere a soma total distribuída
  = soma dos prêmios (menos imposto), sem dupla contagem em `best_only`.
- Hort e cumulative cobertos por testes com valores manuais.

---

## E5 — Normas e títulos FIDE (P2)

### Problema

Sem checagem de norma (IM/GM/WIM/WGM...) nem relatórios de norma de árbitro
(IA/FA). O SM tem "Informações de títulos FIDE", "FIDE Arbiter Norm Report" e os
modelos `IA1.xls`/`FA1.xls`/`titleform.xls`.

### Escopo realista (fase 1 do item)

Norma de jogador é regulamentada e complexa (média de rating dos adversários,
nº mínimo de partidas, distribuição de federações, performance mínima por
título). Implementar como **assistente informativo**, não homologação:

- `NormAssistantService.evaluate(tournament_id, player_id)` retorna:
  - performance (Rp) já calculada (E3),
  - rating médio dos adversários,
  - nº de partidas válidas, nº de federações distintas, nº de titulados
    enfrentados,
  - comparação com limiares por título (tabela parametrizável em
    `src/services/constants.py`),
  - **veredito textual**: "atende/ não atende / faltam X" — com aviso explícito
    de que é estimativa.

### Modelo de dados

Sem tabela nova obrigatória (cálculo on-the-fly). Opcional: persistir
`norm_reports` análogo a `fide_rating_reports` para reimpressão.

### UI

Em `Relatórios`/ficha do jogador: "Relatório de norma (estimativa)" exportável.
Para árbitros: formulário IA/FA pré-preenchido com dados do torneio (export
XLSX usando os modelos como referência de layout).

### Critérios de aceite

- Para um jogador fictício que claramente atende GM, o veredito é "atende" com
  os números corretos; para um que não atende, lista o que falta.
- Todo texto deixa claro que é apoio, não certificação oficial.

---

## E6 — Estatísticas e fichas no padrão FIDE (P2)

- **Estatística de federações**: tabela `FED → nº de jogadores/% pontos`.
- **Estatística de partidas**: total de partidas, % brancas/empates/pretas,
  WOs, byes.
- **Fichas individuais (layout FIDE)**: uma ficha por jogador com cabeçalho do
  torneio, adversários, cores, resultados, Rp.

Tudo derivável dos dados existentes; entrega é de **relatório/exportação**
(reaproveita `report_engine.py` + `export_service.py`). Sem mudança de schema.

Aceite: relatórios batem com a contagem manual em uma fixture de 8 jogadores.

---

## E7 — Editor de listas / colunas (P3)

Permitir configurar saída de listas como o SM (larguras de coluna, bordas,
quebra de página, dados do torneio no topo, gerar HTML+texto+impressão em lote).

- Modelo: `report_layouts` (JSON por tipo de lista, por torneio ou global).
- Serviço: camada de layout sobre `export_service` que aceita seleção/ordem de
  colunas e larguras.
- UI: editor simples de colunas (mostrar/ocultar, ordem, largura %).

Aceite: exportar a mesma lista com dois layouts distintos produz HTML/PDF
diferentes; layout vazio reproduz o atual.

---

## E8 — Sistema Scheveningen (P3)

Pareamento "todos de um grupo contra todos do outro" (individual e por equipes).

- Em `fide_dutch.py`/`team_swiss.py`: função `scheveningen_pairings(group_a,
  group_b, rounds)` gerando a grade fixa.
- `tournament_settings.pairing_method` aceita `scheveningen`.
- UI: na criação/configuração, escolher os dois grupos.

Aceite: grade Scheveningen 4x4 gera 4 rodadas com todos os cruzamentos A×B,
cores equilibradas; cobertura por teste.

---

## E9 — Importar XML/arquivos nativos do Swiss-Manager (P3)

Facilita migração de quem já usa SM.

- Parser de export XML do SM (jogadores, equipes, escalações) → modelos do
  Albericus.
- Estudo de viabilidade de ler `.TUN` diretamente (formato proprietário; provável
  ficar só no XML/TRF).
- Reuso: o Albericus já lê **TRF16**, então importar de volta um TRF do SM cobre
  boa parte (jogadores + resultados por rodada).

Aceite: importar um XML/TRF de exemplo do SM recria jogadores e rodadas
conferíveis contra o original.

---

## E10 — Mudar tipo / dividir torneio (P4)

- "Mudar tipo" (Round Robin ⇄ Suíço) antes da rodada 1: troca `pairing_method` e
  regenera ranking inicial, bloqueado após a primeira rodada.
- "Dividir torneio" (grupos A/B/C): modelar como torneios vinculados por um
  campo `parent_tournament_id` (opcional), com classificação consolidável.

Aceite: conversão antes da R1 não perde inscritos; bloqueio claro após R1.

---

## Fora de escopo (decisão de produto)

- Upload/integração **Chess-Results.com**, registro online, restrição de upload:
  mantém-se offline-first; a ponte é o **TRF16** para upload manual.
- **Listas de rating estrangeiras** (AUT/GER/CZE/POL/RUS/SLO/...): Albericus mira
  **FIDE + CBX + LBX**, suficiente para o Brasil.
- **Álbuns de fotos via FTP**, **salvar em Access**, **listagens de Olimpíada**:
  nicho, sem demanda local.

Esses itens ficam registrados para revisão futura, mas não entram no roadmap de
paridade.
