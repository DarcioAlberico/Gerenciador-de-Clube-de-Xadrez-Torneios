---
name: gacrux
description: >-
  Referência e operação do motor Gacrux / TieBreakServer da FIDE (Otto Milvang,
  v1.9.52) para xadrez: pareamento Suíço Holandês e cálculo/verificação de
  tiebreaks. Use ao montar ou explicar comandos de pairingchecker.py,
  tiebreakchecker.py, tournamentgenerator.py ou chessserver.py; verificar
  pareamentos (-c) ou rankings; interpretar a saída JSON/JCH
  (pairingResult / tiebreakResult); decifrar a sintaxe de tiebreaks
  (PTS, BH, SB, DE, ARO, KS, PS...); converter TRF-16/25 <-> JCH; diagnosticar
  códigos de status; ou integrar o Gacrux ao Albericus (GacruxEngine).
---

# Gacrux — Motor FIDE de Pareamento e Tiebreak

> **Skill de referência.** Especialista no ecossistema **Gacrux / TieBreakServer**,
> a suíte oficial de CLI/API da FIDE (autor: **Otto Milvang**, `sjakk@milvang.no`)
> para pareamento (Sistema Holandês), verificação e cálculo de tiebreaks.
>
> **Versão verificada neste repositório:** `1.9.52` (2026-06-07) —
> ver `src/services/pairing/gacrux/version.py`.
> Fonte vendorizada em `src/services/pairing/gacrux/` + manual em `gacrux_manual.pdf`.
> Os fatos abaixo foram conferidos no código-fonte, não apenas na documentação.

---

## 🎯 Papel e objetivo

Auxiliar desenvolvedores, árbitros e organizadores a:
- construir comandos CLI corretos;
- interpretar saídas JSON/JCH e texto;
- diagnosticar divergências de pareamento e tiebreak;
- integrar o Gacrux em sistemas maiores (ex.: o **Albericus**).

Todos os programas são Python (`python <programa>.py [opções]`, requer **Python ≥ 3.8**).
Entrada/saída padrão é **stdin/stdout** quando `-i`/`-o` são omitidos ou recebem `-`.

---

## ⚡ Cheat sheet

| Ferramenta | Para quê | Flags-chave |
|---|---|---|
| **`pairingchecker.py`** | Gerar / analisar / verificar pareamento | `-p` parear · `-a` analisar · `-c` verificar · `-m dutch` · `-n <rodada>` |
| **`tiebreakchecker.py`** | Calcular / verificar tiebreaks e ranking | `-t <lista>` · `-c` verificar · `-s` suíço · `-p` round-robin · `-r` ordenar · `-u <rating>` |
| **`tournamentgenerator.py`** | Gerar torneios sintéticos (TRF) p/ teste | `-g <qtd>` · `-p <jogadores>` · `-n <rodadas>` · `-r` rating · `-s` estatísticas |
| **`chessserver.py`** | API web via stdin/stdout JSON | serviços `convert` · `pairing` · `tiebreak` |

```bash
# Sintaxe base
python pairingchecker.py  -i torneio.trf [opções]
python tiebreakchecker.py -i torneio.trf [opções]
```

---

## ⚠️ Flags SOBREPOSTAS (a maior fonte de erro)

As mesmas letras significam coisas **diferentes** em cada programa. Confira sempre:

| Flag | `pairingchecker.py` | `tiebreakchecker.py` | `tournamentgenerator.py` |
|---|---|---|---|
| `-p` | **parear** (`--pairing`) | **round-robin** (`--pre-determined`) | **jogadores** (`--players`) |
| `-t` | **cor do topo** (`--top-color` w\|b) | **lista de tiebreaks** (`--tiebreak`) | **cor do topo** (`--top-color`) |
| `-u` | **não-pareados** (`--unpaired`, lista de SNos) | **rating de unrated** (`--unrated`, número) | — |
| `-n` | rodada atual | rodada-alvo do cálculo | **nº de rodadas** (`--number-of-rounds`) |
| `-s` | — | **regras suíças** (`--swiss`) | **estatísticas** (byes/forfeits) |
| `-r` | ordem de classificação | ordem de classificação | **rating** (lista) |

> Na dúvida, rode `python <programa>.py -h` ou consulte o `README.md`/`gacrux_manual.pdf`.

---

## 🦋 Parâmetros COMUNS (todas as ferramentas)

Definidos em `commonmain.py` — valem para todos os programas.

| Flag | Longo | Descrição | Default |
|---|---|---|---|
| `-i` | `--input-file` | Arquivo de entrada (`-` = stdin) | `-` |
| `-o` | `--output-file` | Arquivo de saída (`-` = stdout) | `-` |
| `-f` | `--input-format` | `TRF` (FIDE TRF-16/25) · `JSON` (Chess-JSON / "JCH") · `TS` (Tournament Service) | `TRF` |
| `-F` | `--output-format` | `JSON` · `TRF` · `TXT` | `JSON` |
| `-b` | `--encoding` | `ascii`, `utf-8`, `latin-1`, `cp1252`… | auto |
| `-e` | `--tournament-number` | Nº do torneio em arquivos multi-evento (1,2,3…); **`0` = passthrough/todos** | `1` |
| `-c` | `--check` | **Modo verificação**: compara o cálculo do Gacrux com o que está no arquivo | off |
| `-n` | `--current-round` | Rodada atual/alvo (sobrepõe o valor do arquivo) | `-1` |
| `-N` | `--number-of-rounds` | Total de rodadas (sobrepõe o arquivo) | `0` |
| `-r` | `--rank` | Imprime/ordena em ordem de classificação | off |
| `-d` | `--delimiter` | Saída TXT: `T`=tab · `B`=espaço · `S`=`;` · `C`=`,`. Prefixo `@` adiciona linha de status. **Sem `-d` ⇒ saída JSON** | JSON |
| `-D` | `--decimal-point` | `P`=ponto · `C`=vírgula | `.` |
| `-G` | `--game-score` | Sistema de pontos por jogo (avançado/equipes) — `W:1.0,D:0.5,L:0,Z:0,P:1.0,U:0.5` | — |
| `-M` | `--match-score` | Sistema de pontos por match (avançado/equipes) | — |
| `-x` | `--experimental` | Palavras-chave (`weighted`, `DUMP`…) | — |
| `-v` | `--verbose` | Verboso/debug (repetível: `-vv`) | `0` |
| `-V` | `--version` | Imprime a versão e sai | — |

> ℹ️ O formato Chess-JSON é chamado de **JCH** na documentação, mas o token aceito
> pelo engine na flag `-f` é literalmente `JSON`.
> ℹ️ `-G`/`-M` têm rótulos de ajuda trocados entre si na fonte; o que vale é o nome
> longo (`--game-score` / `--match-score`) e o parsing. Use só em competições por equipes.

---

## 🔢 Códigos de status (`status.code` no JSON)

| Código | Significado |
|---|---|
| `0` | **OK** — operação concluída (e, em `-c`, confere com o arquivo) |
| `1` | OK, mas **`check` divergente**: o cálculo do Gacrux difere do arquivo |
| `2` | OK, mas **sem operação legal** (ex.: nenhum pareamento possível) |
| `200`/`201`/`202` | Equivalentes web de `0`/`1`/`2` |
| `4xx` | **Erro de entrada/cliente** — `401` falha de leitura · `402` falta `--input-file` · `403` falta `--output-file`/formato inválido · `405` não abriu o arquivo |
| `5xx` | **Erro interno** — `500` linha de comando inválida · `501` nº de torneio inválido · `502` erro lendo · `503` erro escrevendo · `510` erro de programa |

> A dica `@` no `-d` faz a 1ª linha do TXT trazer o código de status — útil para scripts.

---

## 🧩 As ferramentas em detalhe

### A. `pairingchecker.py` — pareamento (Sistema Holandês)

Flags próprias (além das comuns):

| Flag | Longo | Descrição |
|---|---|---|
| `-p` | `--pairing` | Gera o pareamento (da próxima rodada, ou de `-n`) |
| `-a` | `--analysis` | Analisa os critérios de qualidade do pareamento |
| `-c` | `--check` | Verifica o pareamento do arquivo contra o cálculo do Gacrux |
| `-m` | `--method` | `dutch` (Holandês). `berger` (round-robin) **não implementado** |
| `-t` | `--top-color` | Cor no tabuleiro 1: `w` ou `b` |
| `-K` | `--maxmeets` | Máximo de vezes que dois jogadores podem se enfrentar |
| `-u` | `--unpaired` | Lista de SNos que **não** devem ser pareados na rodada |
| `-T` | `--exchange` | Modo de teste: troca pares |

```bash
# Verificar TODAS as rodadas de um TRF (relatório no terminal)
python pairingchecker.py -i torneio.trf -c -d T

# Gerar o pareamento da rodada 5 em JSON
python pairingchecker.py -i torneio.trf -o r5.json -p -n 5 -m dutch -F JSON

# Verificar + analisar + parear a rodada 3, com relatório textual detalhado
python pairingchecker.py -i torneio.trf -c -a -p -n 3 -d T
```

### B. `tiebreakchecker.py` — tiebreaks e ranking

Flags próprias (além das comuns):

| Flag | Longo | Descrição |
|---|---|---|
| `-t` | `--tiebreak` | Lista de especificadores de tiebreak (ver sintaxe abaixo) |
| `-s` | `--swiss` | Usa regras de torneio **suíço** |
| `-p` | `--pre-determined` | Usa regras de pareamento **pré-definido** (round-robin) |
| `-u` | `--unrated` | Rating atribuído a jogadores sem rating |
| `-r` | `--rank` | Imprime na ordem de classificação |
| `-c` | `--check` | Verifica se o ranking do arquivo bate com o calculado |

Sem `-t`, a lista de tiebreaks é lida do próprio arquivo do torneio.

```bash
# Calcular ranking com tiebreaks e exportar CSV (vírgula), em ordem de classificação
python tiebreakchecker.py -i torneio.trf -s -r -d C -t PTS BH BH/C1 SB DE

# Verificar se os tiebreaks do arquivo conferem
python tiebreakchecker.py -i torneio.trf -c -t PTS BH SB DE

# W.O. contados como jogos + unrated valendo 1400
python tiebreakchecker.py -i torneio.trf -s -u 1400 -t PTS DE/P SB
```

### C. `tournamentgenerator.py` — torneios sintéticos (teste)

| Flag | Longo | Descrição |
|---|---|---|
| `-g` | `--generate` | Quantidade de torneios a gerar |
| `-p` | `--players` | Nº de jogadores |
| `-n` | `--number-of-rounds` | Nº de rodadas |
| `-t` | `--top-color` | Cor no tabuleiro 1 (`w`/`b`); alterna se omitido |
| `-r` | `--rating` | 3 números: `<rating mais alto> <passo> <sigma>` |
| `-s` | `--statistics` | 3 números: `<taxa zero-point-bye> <taxa half-point-bye> <taxa forfeit>` |
| `-x` | `--experimental` | Palavras-chave (`weighted`…) |

```bash
# 10000 torneios de 9 rodadas, 15 jogadores; cria a pasta e numera T0000..T9999
python tournamentgenerator.py -g 10000 -n 9 -p 15 \
  -r 2200 10 50.0 -s 0.02 0.10 0.04 \
  -o C:/temp/t_n9_p15/T%d.trf
```

### D. `chessserver.py` — API web (stdin → stdout, JSON)

Lê **um JSON em stdin** com uma chave `command` e devolve JSON em stdout.
Serviços (`service`): **`convert`**, **`pairing`**, **`tiebreak`**.

```jsonc
{
  "command": {
    "service": "tiebreak",
    "input_file": "torneio.trf",
    "input_format": "TRF",
    "base64": "<arquivo em base64>",   // ou "data": ["..."]
    "tournament_number": 1,
    "current_round": 5,
    "number_of_rounds": 9,
    // tiebreak:
    "tiebreak": ["PTS", "BH", "SB", "DE"],
    "swiss": true, "pre-determined": false, "unrated": 1400,
    // pairing:
    "pairing": true, "method": "dutch", "top_color": "white",
    "maxmeets": 1, "unpaired": [12, 30], "analysis": false
  }
}
```

> Atenção: o código lê `jsondata["command"]` (objeto único). O cabeçalho
> `filetype/options` que aparece no docstring é do schema antigo.

---

## 🏷️ Sintaxe dos especificadores de tiebreak (`-t`)

Formato completo: **`NOME[@ano][:PS][/MOD][/MOD]…`**

> Tudo vira maiúscula. Os separadores **`/`, `!` e `#` são equivalentes**.
> ⚠️ Nesta versão **`-` NÃO separa opções** (corrige a notação `-optlist` do README):
> cada modificador vai em seu próprio segmento — use `BH/C1/P`, não `BH/C1-P`.
> Modificadores **numéricos** (`C`,`M`,`L`,`U`,`K`,`V`) precisam do número colado e
> sozinhos no segmento (`C1`, `U1400`); flags sem número podem empilhar (`PF`, `CP`).

| Parte | Significado |
|---|---|
| `NOME` | Código do tiebreak (obrigatório) |
| `@ano` | Ano das regras FIDE p/ o critério: `@22`/`@2022` · `@24`/`@2024` · `@26`/`@2026` (padrão `@24`) |
| `:PS` | Sistema de pontos (equipes): `MP`=match (padrão) · `GP`=game · `MM`/`MG`/`GM`/`GG` (dupla pontuação) |
| `/MOD` | Um ou mais modificadores (tabela abaixo) |

**Modificadores (tokens):**

| Token | Significado |
|---|---|
| `Cn` | **Corte**: descarta os *n* piores resultados (ex.: `BH/C1` = Buchholz Cut 1) |
| `Mn` | **Mediana**: descarta os *n* piores **e** *n* melhores (ex.: `BH/M1`) |
| `Ln` · `L+n` · `L-n` | **Limite** (Koya): `Ln` em **%** (ex.: `L50`); `L±n` em **pontos** |
| `Kn` | Limite (Koya) em pontos absolutos |
| `P` | Conta jogos **não jogados como jogados** (W.O./forfeits valem; ex.: `DE/P`) |
| `D` | Trata todo jogo não jogado como **empate** |
| `Unnnn` | **Rating** p/ jogadores sem rating (ex.: `U1400`); sem número usa o `-u` global |
| `F` | **Fore mode** (para frente), p/ Buchholz/SB |
| `R` | **Inverte** a ordem padrão do critério |
| `S` | Força regras de **suíço** (sobrepõe o default de round-robin) |
| `Vn` | **Versão das regras**: `V0`/`V2022` · `V1`/`V2024` · `V2`/`V2026` |
| `X` · `N` | Internos/experimentais (não publicados) |

**Versões de regras FIDE** (de `tiebreak.py`, selecionáveis por `@ano` ou `/Vn`):

| Índice | Vigência |
|---|---|
| `0` / 2022 | 2022-01-01 |
| `1` / 2024 | 2024-08-01 |
| `2` / 2026 | 2026-03-01 — *aprovada pelo Conselho FIDE em 02/02/2026* |

> Lista canônica também em `gacrux_manual.pdf` e
> <https://fide-tec.gacrux.no:9001/tbs/tiebreaklist.html>.

### Códigos de tiebreak suportados (de `tiebreak.py`)

**Mais usados:**

| Código | Tiebreak |
|---|---|
| `PTS` | Pontos (**padrão**) |
| `BH` | Buchholz *(aceita `/C1`, `/M1`…)* |
| `FB` | Fore/Forward Buchholz |
| `SB` | Sonneborn-Berger *(aceita `/C`)* |
| `DE` | Confronto direto / Direct Encounter *(aceita `/P`)* |
| `PS` | Progressivo / cumulativo *(aceita `/C`)* |
| `KS` | Koya *(aceita `/L`)* |
| `ARO` | Rating médio dos adversários *(aceita `/U####`)* |
| `TPR` | Performance no torneio *(rating)* |
| `WON` | Nº de partidas ganhas |
| `WIN` | Nº de vitórias |
| `SNO` | Nº de inscrição (starting number) |

**Demais códigos:** `MPTS`/`GPTS` (match/game points), `RANK`, `RND` (aleatório),
`RTG`/`RTNG` (rating inicial), `NUM` (partidas jogadas), `BPG` (jogos com pretas),
`BWG` (vitórias com pretas), `VUR` (rodadas não jogadas voluntárias), `REP`/`GE`,
`RIP`, `RFP`, `TOP` (top-scorer na última rodada), `COP`/`COD`/`CSQ` (cor:
preferência/diferença/sequência), `EDE`/`EDEC`/`EDET`/`EDEB` (confronto direto
estendido), `ABH`/`AFB` (Buchholz ajustado), `AOB` (média de Buchholz), `ESB`
(SB estendido), `PTP`/`APRO`/`APPO` (performances), `BC`/`TBR`/`BBE` (board count),
`SSSC`, `STD`, `ACC` (pontos + acelerados), `FLT`/`FLTD` (floats), `NUL`.

### Modificadores aceitos por cada tiebreak (canônico)

Da declaração `flag` de cada critério em `tiebreak.py` — os modificadores que
**fazem sentido** para cada tiebreak nesta versão. Os **universais** (`@ano`, `:PS`,
`R`, `Vn`, `S`) valem para qualquer critério; o parser aceita a sintaxe, mas só os
modificadores abaixo têm efeito real em cada um.

| Tiebreak | Modificadores próprios |
|---|---|
| `DE` — confronto direto | `P` |
| `SB` — Sonneborn-Berger | `C` (corte) |
| `ESB` + `EMMSB`/`EMGSB`/`EGMSB`/`EGGSB` — SB estendido | `C` (corte), `P` |
| `PS` — progressivo | `C` (corte) |
| `KS` — Koya | `L` / `K` (limite) |
| `BH` — Buchholz · `FB` — Fore Buchholz | `C` (corte), `M` (mediana) |
| `AOB` — média de Buchholz | `F` (fore) |
| `ARO` — rating médio dos adversários | `C`/`M` (corte/mediana), `U` (unrated) |
| `TPR` · `PTP` · `APRO` · `APPO` — performances | `U` (unrated) |
| `SSSC` — score strength combination | `P`, `K`, `F` |
| Demais (`PTS`, `WON`, `SNO`, `EDE*`, `BC`, `RANK`…) | — (só os universais) |

> **Exemplos válidos:** `BH/C1` · `BH/M1` · `SB/C2` · `KS/L50` · `DE/P` ·
> `ARO/U1400` · `PTS:GP` (pontos de jogo) · `BH@26/C1` (Buchholz Cut-1 pelas regras de 2026).

---

## 📦 Estrutura da saída JSON (JCH)

Envelope comum:

```jsonc
{
  "filetype": "...", "version": "1.0", "published": "...", "origin": "...",
  "options": { /* eco das flags */ },
  "status": { "code": 0, "info": [], "error": [] },
  // E UM destes, conforme a operação:
  "pairingResult":  { "pairs": [...], "roundpairing": [...], "current": N, "check": true },
  "tiebreakResult": { "check": false, "tiebreaks": [...], "competitors": [...] },
  "convertResult":  { /* arquivo Chess-JSON */ }
}
```

- **`pairingResult.pairs`** — lista de pares `[brancas_rank, pretas_rank]`.
  **`0` em qualquer lado = bye** (ex.: `[15, 0]` = SNo 15 ganhou bye).
- **`tiebreakResult.competitors[]`** — cada item: `cid` (SNo), `rank`, `tiebreakScore[]`
  (na ordem da lista `-t`), `boardPoints`, `tiebreakDetails[]`.

---

## 🩺 Diagnóstico de divergências de pareamento

Quando o pareamento de um torneio **diverge** do Gacrux:

```bash
python pairingchecker.py -i torneio.trf -c -a -p -n <rodada> -d T
```

O relatório textual mostra os **scorebrackets** rodada a rodada e onde as regras do
Sistema Holandês (sequência de qualidade) divergem entre o arquivo e o motor.
`status.code == 1` na saída sinaliza que o pareamento do arquivo **não confere** com
o calculado.

---

## 🔗 Integração com o Albericus

O Albericus já embute o Gacrux como motor de pareamento **homologado pela FIDE**:

- **Wrapper:** `GacruxEngine.pair_round()` em
  [gacrux_engine.py](src/services/pairing/gacrux_engine.py).
- **Fluxo:** exporta o estado do torneio para TRF-16 (via `TRF16Exporter`) → roda o
  `pairingchecker.py` → lê `pairingResult.pairs` → remapeia ranks ↔ `player_id`.
- **Comando real montado pelo wrapper:**
  ```
  python pairingchecker.py -i input.trf -o output.json -b utf-8 \
         -p -n <rodada> -m dutch -F JSON -v  [-u <SNos não pareados>]
  ```
- **Ranking 1-based** ordenado por `export_service._trf_rating` (desc) → nome → id;
  os jogadores fora de `to_pair` viram `-u` (não pareados); par com `0` = bye.

> ⚠️ **Backlog relacionado:** o SNo/ordenação usado aqui vem de `_trf_rating`,
> **não** de `initial_order` — ver memória `project_albericus_trf_initial_order_backlog`.
> Validar pareamentos/rankings do Albericus contra o Gacrux com `-c` é a forma
> canônica de checar paridade com a FIDE.

---

## 💡 Perguntas que esta skill resolve

- *"Como verifico se o pareamento da rodada 4 do meu `open.trf` está correto?"*
  → `python pairingchecker.py -i open.trf -c -p -a -n 4 -d T`
- *"Calcular ranking por Pontos, Buchholz Cut 1 e SB e salvar em CSV."*
  → `python tiebreakchecker.py -i t.trf -s -r -d C -t PTS BH/C1 SB`
- *"O que significa `status.code == 1`?"* → OK, mas o cálculo **difere** do arquivo.
- *"W.O. como jogos e unrated = 1400?"* → `-u 1400` + modificador `/P` (ex.: `DE/P`).
- *"Converter TRF para JCH?"* → serviço `convert` do `chessserver.py`, ou reexportar com `-F JSON`.

---

## 📚 Fontes

- Código vendorizado: `src/services/pairing/gacrux/` (autor **Otto Milvang**).
- Manual completo: `gacrux_manual.pdf` (raiz do projeto).
- `README.md` do pacote + lista canônica de tiebreaks:
  <https://fide-tec.gacrux.no:9001/tbs/tiebreaklist.html>.
- TRF FIDE: <https://www.fide.com/FIDE/handbook/C04Annex2_TRF16.pdf>.
