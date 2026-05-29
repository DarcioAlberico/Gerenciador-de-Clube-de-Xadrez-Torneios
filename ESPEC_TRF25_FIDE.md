# Especificação TRF25 (FIDE) — referência de implementação

Fonte primária: **TRF25 Final Draft** (FIDE Technical Commission, jan/2025).
PDF: <http://tec.fide.com/wp-content/uploads/2025/01/TRF25-FinalDraft.pdf>
Título interno do documento: *"TRF Extensions to support Acceleration, Tie-Breaks
and Team Pairing (plus recommendations for National Rating Support and
In-Tournament Data Exchange)"*.

Status do draft (verificado em 2026-05-29): continua sendo *final draft*, mas as
posições de campo estão estáveis. Este documento consolida o layout exato para o
projeto implementar contra um alvo fixo. As **tabelas de códigos** (tipo de
torneio para o 192; tie-breaks para 202/212) estão em anexos separados ainda não
capturados — ver seção "Pendências".

Convenções FIDE:
- Cada linha termina com CR. Linhas iniciadas por `###` são comentários.
- Posições são 1-based, inclusivas (`5 - 8` = colunas 5,6,7,8).
- Colunas **R** e **P** marcam relevância para Rating e Pairing: ■ obrigatório,
  □ aviso se errado, (vazio) ignorado.
- Formato `11.5` = ponto com casa decimal; `1111.5` idem com mais dígitos.
- Texto azul no PDF = TRF16 (já implementado); preto/vermelho = extensões TRF25.

---

## 1. Seção de Torneio (registros `??2`)

Posições 1-3 = identificador; texto livre a partir da posição 5, salvo onde há
layout posicional.

| Código | Descrição | Layout / conteúdo | Novo? |
|--------|-----------|-------------------|-------|
| 012 | Tournament Name | texto livre (pos. 5+) — **obrig.** R/P | TRF16 |
| 022 | City | texto livre — **obrig.** R | TRF16 |
| 032 | Federation | texto livre — **obrig.** R | TRF16 |
| 042 | Date of start | texto livre | TRF16 |
| 052 | Date of end | texto livre | TRF16 |
| 062 | Number of players | texto livre | TRF16 |
| 072 | Number of rated players | texto livre | TRF16 |
| 082 | Number of teams | só em torneio por equipes | TRF16 |
| 092 | Type of tournament | texto livre (legado; ver 192) | TRF16 |
| 102 | Chief Arbiter | texto livre — **obrig.** R | TRF16 |
| 112 | Deputy Chief Arbiter | uma linha por árbitro | TRF16 |
| 122 | Allotted times per moves/game | texto livre | TRF16 |
| 132 | Dates of the round | datas posicionais (abaixo) | TRF16 |
| 142 | Number of rounds | **obrig. só para ITDX** | **TRF25** |
| 152 | Initial-colour | `W`/`B`; obrig. só se difere da cor do 1º tabuleiro do top seed | **TRF25** |
| 162 | Scoring point system (individuais) | layout posicional (§1.1) | **TRF25** |
| 172 | Encoded Starting Rank Method | layout posicional (§1.2) | **TRF25** |
| 192 | Encoded Type Of Tournament | código da *Tournament-Type Code Table* — **obrig. P** | **TRF25** |
| 202 | Tie-breaks para desempatar | lista CSV de códigos (alt. a 212) | **TRF25** |
| 212 | Tie-breaks para classificação | lista CSV + código extra `PTS` — **obrig. P** | **TRF25** |
| 222 | Encoded Time Control | gramática de tempo (§1.3) | **TRF25** |
| 352 | Colour sequence dos tabuleiros (equipes) | ex.: `WBWBWB` — **obrig. P** | **TRF25** |
| 362 | Scoring point system (equipes) | layout posicional (§1.4) | **TRF25** |

### 132 — Dates of the round (formato `YY/MM/DD`)
| Posição | Conteúdo |
|---------|----------|
| 92 - 99   | data rodada 1 |
| 102 - 109 | data rodada 2 |
| 112 - 119 | data rodada 3 |
| … (+10 por rodada) | … |

### 1.1 — 162 Scoring point system (individuais)
Obrigatório só quando o sistema difere do padrão. Pares (símbolo, pontos)
repetidos a cada 9 colunas.
| Posição | Conteúdo |
|---------|----------|
| 6     | símbolo: `W`/`D`/`L`/`A`/`P`/`X` |
| 7 - 10 | pontos do símbolo na pos. 6 (formato `11.5`) |
| 15    | (opc.) outro símbolo |
| 16 - 19 | pontos do símbolo na pos. 15 |
| 24    | (opc.) outro símbolo |
| 25 - 28 | pontos do símbolo na pos. 24 |
| … (e assim por diante) | … |

Símbolos e padrões: `W` win/forfeit-win/full-point-bye = 1.0; `D` draw/half-point-bye
= 0.5; `L` loss OTB = 0.0; `A` absence (zero-point-bye / forfeit loss) = 0.0;
`P` pairing-allocated-bye = igual a W; `X` unknown (jogo adiado) = igual a D.

### 1.2 — 172 Encoded Starting Rank Method
Obrigatório só se houver registros NRS (National Rating Support).
| Posição | Conteúdo |
|---------|----------|
| 5 - 7  | código FIDE da federação dos registros NRS |
| 9 - 13 | método (3-5 chars): `FIDE`, `NRO`, `FIDON`, `NIDOF`, `HBFN`, `LBFN`, `OTHER` |

### 1.3 — 222 Encoded Time Control
Gramática: `d[:d]` ou `Wd[:d]-Bd[:d]` (W/B = tempo de brancas/pretas).
`d` é um *Time Period Descriptor*: `(std) => M/S`, `(all) => S`, `(inc) => S+I`,
onde S=segundos do período, M=lances do período, I=incremento por lance.
Exemplos: `90'+30"` → `5400+30`; `100'/40+15'+30"` → `40/6000+30:900+30`;
Armageddon (B 5', P 4') → `W300-B240`.

### 1.4 — 362 Scoring point system (equipes)
Obrigatório só quando difere do padrão.
| Posição | Conteúdo |
|---------|----------|
| 5 - 6  | `TW`/`TD`/`TL` (team win/draw/loss) |
| 7 - 10 | pontos do símbolo 5-6 (formato `11.5`) |
| 14 - 15 | (opc.) outro símbolo |
| 16 - 19 | pontos do símbolo 14-15 |
| 23 - 24 | (opc.) último símbolo |
| 25 - 28 | pontos do símbolo 23-24 |

Padrões: `TW`=2.0, `TD`=1.0, `TL`=0.0.

---

## 2. Seção de Jogador (registro `001`) — **igual ao TRF16**

| Posição | Conteúdo | R/P |
|---------|----------|-----|
| 1 - 3   | `001` | ■/■ |
| 5 - 8   | Starting-rank number (1–9999) | ■/■ |
| 10      | Sexo `m`/`w` | □ |
| 11 - 13 | Título (`GM`,`IM`,`WGM`,`FM`,`WIM`,`CM`,`WFM`,`WCM`) | □ |
| 15 - 47 | Nome `Sobrenome, Nome` | □ |
| 49 - 52 | Rating FIDE | □ |
| 54 - 56 | Federação FIDE | □ |
| 58 - 68 | Nº FIDE (inclui 3 dígitos de reserva) | ■ |
| 70 - 79 | Nascimento `YYYY/MM/DD` | □ |
| 81 - 84 | Pontos (formato `11.5`) | ■ |
| 86 - 89 | Rank (empates permitidos) | ■/■ |

Bloco por rodada (repete a cada 10 colunas a partir de 92):
| Posição | Conteúdo |
|---------|----------|
| 92 - 95 | id do oponente (starting-rank, até 4 dígitos); `0000`/branco = bye/não pareado |
| 97 | cor: `w`/`b`/`-` (`-`/branco = bye) |
| 99 | resultado (tabela abaixo) |
| 102-105 / 107 / 109 | id / cor / resultado da rodada 2 |
| 112-115 / 117 / 119 | rodada 3 … e assim por diante |

Resultado (pos. 99, **case-insensitive**):
- Não jogado: `-` forfeit loss, `+` forfeit win.
- Menos de 1 lance (não ratável): `W` win, `D` draw, `L` loss.
- Jogo normal: `1` win, `=` draw, `0` loss.
- Bye (não ratável): `H` half-point, `F` full-point, `U` pairing-allocated
  (≤1 por rodada), `Z`/branco zero-point (ausência conhecida / rest round).

> **Importante:** TRF25 **não** acrescenta campos de tie-break/TPR à linha 001.
> O comentário antigo do scaffold `trf25.py` ("tiebreaks e TPR na linha 001")
> está **incorreto** — tie-breaks ficam nos registros de torneio 202/212, e os
> resultados por tabuleiro/equipe nos registros 801/802. Corrigir o scaffold.

---

## 3. National Rating Support (registro federativo `XXX`)

Mesma estrutura estática do 001, mas pos. 1-3 = código FIDE de 3 letras da
federação que registrará o torneio no sistema nacional.
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | código FIDE da federação de rating — ■ R |
| 5 - 8   | starting-rank (liga ao 001 correspondente) — ■ R |
| 10 / 11-13 / 15-47 | sexo / classificação / nome nacionais (opc. se = 001) |
| 49 - 52 | rating nacional — ■ R |
| 54 - 56 | origem nacional |
| 58 - 68 | nº nacional |
| 70 - 79 | nascimento (opc. se = 001) |

---

## 4. Seção de Equipe

### 4.1 — Registro `013` (legado, *to be phased out*)
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `013` — ■/■ |
| 5 - 36  | nome da equipe — ■/■ |
| 37 - 40 | 1º jogador (starting-rank do 001) |
| 42 - 45 | 2º jogador |
| 47 - 50 | 3º jogador |
| 52 - 55 | 4º jogador (+5 colunas por jogador) |
| … 72-75 = 8º; 102-105 = 14º … | … |

### 4.2 — Registro `310` (novo, substitui o 013)
| Posição | Conteúdo | R/P |
|---------|----------|-----|
| 1 - 3   | `310` | ■/■ |
| 5 - 7   | Team Pairing Number (1–999) | ■/■ |
| 9 - 40  | Team Name | ■/■ |
| 42 - 46 | Team Nickname `AAAAA` (usado nos 801/802) | |
| 48 - 53 | Strength Factor `111111` | |
| 55 - 60 | Match Points `1111.5` (fim do torneio) | ■ |
| 62 - 67 | Game Points `1111.5` (fim do torneio) | ■ |
| 69 - 71 | Team Rank (empates permitidos) | ■/■ |
| 74 - 77 | 1º jogador (starting-rank do 001) | ■/■ |
| 79 - 82 | 2º jogador |
| 84 - 87 | 3º jogador |
| 89 - 92 | 4º jogador (+5 colunas por jogador) |
| … 109-112 = 8º; 139-142 = 14º … | … |

Exemplo:
```
### SSS NNN...                              FFFFF EEEEEE MMMMMM GGGGGG RRR PPP1 PPP2 ...
310 1   India                              IND   2486   15.0   28.0   11  1    5    ...
```

---

## 5. Registros de pontuação especial / pareamento

### 5.1 — `250` Accelerated Round (ind. e equipes)
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `250` |
| 5 - 8   | match points fictícios `11.5` (só equipes; vazio=0.0) |
| 10 - 13 | game points fictícios `11.5` (ind.: ≠0.0; equipes: pode ser vazio) |
| 15 - 17 | primeira rodada com os pontos |
| 19 - 21 | última rodada |
| 23 - 26 | primeiro jogador/equipe |
| 28 - 31 | último jogador/equipe |

### 5.2 — `260` Prohibited pairings (ind. e equipes)
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `260` |
| 5 - 7   | primeira rodada em que não podem se enfrentar |
| 9 - 11  | última rodada |
| 13 - 16 | jogador/equipe 1 |
| 18 - 21 | jogador/equipe 2 |
| 23 - 26 | jogador/equipe 3 (opc.) … |

---

## 6. Seção de Byes

### 6.1 — `240` Full/Half/Zero-Point-Bye (ind. e equipes)
Máx. 1 registro por tipo por rodada.
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `240` |
| 5       | tipo: `F`/`H`/`Z` |
| 7 - 9   | rodada |
| 11 - 14 | jogador/equipe 1 |
| 16 - 19 | jogador/equipe 2 |
| 21 - 24 | jogador/equipe 3 … |

Exemplo: `240 H 003 026 047` (equipes 26 e 47 com HPB na rodada 3).

### 6.2 — `320` Pairing-Allocated-Bye (só equipes, 1 registro por torneio)
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `320` |
| 5 - 8   | PAB match points `11.5` |
| 10 - 13 | PAB game points `11.5` |
| 15 - 17 | TPN do PAB na rodada 1 (vazio/`000` se ninguém) |
| 19 - 21 | rodada 2 (+4 colunas por rodada) |
| … 47-49 = rodada 9 … | … |

---

## 7. Registros de jogos não jogados (equipes)

### 7.1 — `330` Forfeited matches
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `330` |
| 5 - 6   | tipo: `+-` (branca vence), `-+` (preta vence), `--` (duplo forfeit) |
| 8 - 10  | rodada |
| 12 - 14 | TPN da equipe de brancas |
| 16 - 18 | TPN da equipe de pretas |

> Nota FIDE: jogadores presentes devem constar no 001 com `XXXX C +`
> (`XXXX`=0000 ou jogador da equipe ausente; `C`=`w`/`b`/`-`).

### 7.2 — `300` Out-Of-(default)Order
Equipe que joga fora da ordem padrão definida no 310.
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `300` |
| 5 - 7   | rodada `111` |
| 9 - 11  | TPN da equipe OOdO |
| 13 - 15 | TPN do oponente |
| 17 - 20 | jogador do tabuleiro 1 (ou `0000`/vazio) |
| 22 - 25 | tabuleiro 2 (+5 colunas por tabuleiro) |
| … 47-50 = tabuleiro 7 … | … |

### 7.3 — `299` Abnormal Assignment points (ind. e equipes)
Usado quando os pontos atribuídos diferem dos padrões dos sistemas 162/362.
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `299` |
| 5       | tipo (AAT): `W`/`D`/`L` (→362 TW/TD/TL), `F`/`H`/`Z` (→240), `+`/`-` (→330), branco (penalidade/bônus, pode ser negativo) |
| 8 - 11  | match points `[-]11.5` (só equipes) |
| 14 - 17 | game points (equipes) ou pontos (indivíduos) `[-]11.5` |
| 20 - 22 | rodada (`000`/vazio = todas) |
| 24 - 27 | jogador/equipe 1 (`000`/vazio = todos) |
| 29 - 32 | jogador/equipe 2 |
| 34 - 37 | jogador/equipe 3 … |

---

## 8. Registros informativos de equipe (`801` / `802`)

Recomendados (não obrigatórios) para legibilidade humana.

### 8.1 — `801` (registro de comprimento **variável**)
Os tamanhos dos campos dependem de parâmetros calculados (VND/VNC):
`$T`=dígitos p/ nº de equipes, `$M`=dígitos p/ match points máx,
`$G`=dígitos p/ game points máx (+2), `$B`=nº de tabuleiros (=len do 352),
`$C`=máx. de componentes. RID = posição do jogador no roster (`1-9`, depois
`A-Z` para 10-35, `*` para 36+).
Layout por rodada (TIPR): TPN do oponente, cor, resultados tabuleiro-a-tabuleiro
(símbolos do campo 99 do 001), e RIDs dos jogadores por tabuleiro. As fórmulas
exatas de posição estão no PDF (pág. 10) — implementar só se 801 for adotado.

### 8.2 — `802` (versão curta, comprimento **fixo**)
Substitui componentes/resultados-por-tabuleiro por game points do match.
| Posição | Conteúdo |
|---------|----------|
| 1 - 3   | `802` |
| 5 - 7   | Team Pairing Number |
| 9 - 13  | Team Nickname (dup. do 310) |
| 15 - 20 | match points totais (dup. do 310) |
| 22 - 27 | game points totais (dup. do 310) |
| 29 - 31 | rodada 1: oponente (TPN) ou tipo de bye (`PAB`/`FPB`/`HPB`/`ZPB`) |
| 33      | rodada 1: cor `w`/`b` (vazio se bye) |
| 35 - 38 | rodada 1: GP |
| 39      | rodada 1: indicador de forfeit (`f`/`F` ou vazio) |
| 42-44 / 46 / 48-51 / 52 | rodada 2 (mesma estrutura, +13 colunas por rodada) |
| … | … |

Exemplo:
```
### TTT NNNNN MMMMMM GGGGGG T01 C GGGGf T02 C GGGGf ...
802 3   GEO   19.0   32.5   FPB     4.0 16  w 2.5   ...
```

---

## 9. Mapa de implementação para o projeto

O que o **TRF16Exporter** já cobre (manter): registros 012–132, linha 001
completa, linha de equipe 013.

O que o **TRF25Exporter** precisa **adicionar** (sobrescrevendo `export`):

1. **Migrar 013 → 310** com match points, game points, rank, strength factor e
   nickname da equipe (dados já existentes nas tabelas de standings/teams).
2. **162 / 362** — sistemas de pontuação, só quando o torneio usa valores não
   padrão (o projeto já tem `win_points`/`draw_points`/`loss_points` e
   `RESULT_POINTS`). Emitir só se divergirem do padrão FIDE.
3. **192** — tipo de torneio codificado (depende da *Tournament-Type Code Table*;
   ver Pendências). Obrigatório (P=■).
4. **212** — lista de tie-breaks usados na classificação (o projeto já calcula
   tiebreaks via `pairing/tiebreaks.py`); mapear nossos componentes para os
   códigos FIDE (ver Pendências). Obrigatório (P=■).
5. **352** — sequência de cores dos tabuleiros (equipes). Obrigatório (P=■).
6. **142 / 152 / 222** — nº de rodadas, cor inicial, time control codificado
   (campos diretos do torneio).
7. **240 / 320 / 330 / 300 / 299** — byes, PAB, forfeits, out-of-order e ajustes
   anormais de pontos (equipes). Mapear dos eventos já registrados.
8. **801/802** — opcionais; priorizar 802 (fixo) sobre 801 (variável).

**Correção necessária no scaffold** [`trf25.py`](src/services/federation_exporters/trf25.py):
o docstring afirma que TRF25 adiciona "tiebreaks e TPR na linha 001" e fala em
"linhas TC/XXR/XXC" — nomenclatura que **não existe** nesta spec. Os nomes reais
são os registros numéricos acima (310, 162, 362, 192, 202/212, 352, 222, etc.).
Atualizar o comentário antes de implementar.

---

## 10. Anexo A — Tournament-Type Code Table (registro 192)

Fonte: <http://tec.fide.com/wp-content/uploads/2024/09/TournamentTypeCodeTable092.pdf>
(o título cita "092", mas o argumento migrou para o registro **192** no TRF25).

### Swiss individual
`FIDE_DUTCH_2017` (Dutch antes de 2025-07-01), `FIDE_DUTCH_2025` (após
2025-06-30), `FIDE_DUTCH` (default por data), `FIDE_DUBOV`, `FIDE_BURSTEIN`, e as
variantes `_BAKU` (método de aceleração de Baku) de cada um. Também
`CUSTOM_SWISS`, `FIDE_DOUBLESWISS`(+`_BAKU`), `CUSTOM_DOUBLESWISS`.

### Pareamento predeterminado (individual)
`BERGER_ROUNDROBIN_Gn` (Berger, jogos repetidos n vezes), `BERGER_ROUNDROBIN`
(=G1), `BERGER_DOUBLEROUNDROBIN` (=G2), `FIDE_ROUNDROBIN`,
`FIDE_DOUBLEROUNDROBIN`, `CUSTOM_ROUNDROBIN`, `FIDE_SCHILLER_TxP` (T equipes de
P jogadores), `FIDE_SCHILLER` (=4x3), `CUSTOM_SCHILLER`, `FIDE_SCHEVENINGEN_Gn`,
`FIDE_SCHEVENINGEN` (=G1), `FIDE_DOUBLESCHEVENINGEN` (=G2),
`CUSTOM_SCHEVENINGEN`, `WORLDCUP_KNOCKOUT`, `CUSTOM_KNOCKOUT`.

### Swiss por equipes (a palavra `TEAM` está sempre no código)
Padrão: `FIDE_TEAM_<pref>_<score>`, onde:
- `<pref>` = `TYPEA` / `TYPEB` / (ausente = sem preferência de cor);
- `<score>` = `MP_GP` / `GP_MP` / `MP` / `GP` (primário_secundário; o secundário
  é usado na alocação de cores; quando só um, o outro não é usado).

Exemplos: `FIDE_TEAM_TYPEA_MP_GP`, `FIDE_TEAM_TYPEB_GP_MP`, `FIDE_TEAM_MP`.
`FIDE_TEAM` = default `FIDE_TEAM_TYPEA_MP_GP`. Cada combinação tem variante
`_BAKU`. Também `CUSTOM_TEAM_SWISS_MP`, `CUSTOM_TEAM_SWISS_GP`,
`CUSTOM_TEAM_SWISS`.

### Predeterminado / outros (equipes)
`BERGER_TEAM_ROUNDROBIN_Gn`, `BERGER_TEAM_ROUNDROBIN` (=G1),
`BERGER_TEAM_DOUBLEROUNDROBIN` (=G2), `FIDE_TEAM_ROUNDROBIN`,
`FIDE_TEAM_DOUBLEROUNDROBIN`, `CUSTOM_TEAM_ROUNDROBIN`, `CUSTOM_TEAM_KNOCKOUT`.

> **Mapa do projeto:** Suíço individual → `FIDE_DUTCH_2025` (ou `_2017` conforme
> a data do torneio); round-robin individual → `FIDE_ROUNDROBIN`; knockout →
> `WORLDCUP_KNOCKOUT`; suíço por equipes → `FIDE_TEAM_TYPEA_MP_GP` (MP primário,
> GP secundário — alinhado ao `team_match_summary` do projeto). Acrescentar
> `_BAKU` só se o torneio usar aceleração de Baku (registro 250).

---

## 11. Anexo B — Mandatory Tie-Breaks (registros 202/212)

Fonte: <http://tec.fide.com/wp-content/uploads/2024/09/MandatoryTieBreaks.pdf>

### Formato do "Rank Order Descriptor"
```
<Acrônimo>[:<TeamScore>][/<Variante>[/<Variante>...]]
```
- **`:` separa o team-score; `/` separa as variantes.** Tudo case-insensitive.
- **Team score** (só equipes, para tie-breaks normalmente individuais):
  `:MP` = calcular com Match Points; `:GP` = calcular com Game Points.
- **Modificadores:** `/Cn` cut-n (`/C1`,`/C2`…); `/Mn` median-n (`/M1`,`/M2`…);
  `/L±n` limite Koya em ±n meio-pontos do 50% (`/L+1`,`/L-2`…); `/Kx` fator de
  normalização do SSSC (`/K4`,`/K5`…).
- **Opções:** `/P` jogos por W.O. contam como jogados contra o oponente previsto;
  `/F` usar Fore-Buchholz em vez de Buchholz.

### Acrônimos (Rank Order Names)
| Código | Nome | Escopo | Modif./opções permitidos |
|--------|------|--------|--------------------------|
| `PTS`  | pontos (individual) / pontos primários (equipe) | ambos | — (código sintético do 212; ver §1) |
| `DE`   | Direct Encounter | individual | `/P` |
| `BPG`  | Black Played Games | individual | — |
| `BWG`  | Black Won Games | individual | — |
| `REP`  | rating performance (variant) | individual | — |
| `SB`   | Sonneborn-Berger | individual | `/C1` `/C2` `/P` |
| `ARO`  | Average Rating of Opponents | individual | `/C1` `/C2` `/M1` `/M2` |
| `TPR`  | Tournament Performance Rating | individual | — |
| `PTP`  | Perfect Tournament Performance | individual | — |
| `APRO` / `APPO` | average perf. rating/points of opponents | individual | — |
| `WIN`  | nº de vitórias | ambos | `:MP` |
| `WON`  | vitórias OTB | ambos | `:MP` |
| `PS`   | Progressive Score / Sonneborn de pontos | ambos | `:MP`/`:GP` `/C1` `/C2` |
| `BH`   | Buchholz | ambos | `:MP`/`:GP` `/C1` `/C2` `/M1` `/M2` `/P` |
| `AOB`  | Average of Opponents' Buchholz | ambos | `:MP`/`:GP` `/F` |
| `FB`   | Fore Buchholz | ambos | `:MP`/`:GP` `/C1` `/C2` `/M1` `/M2` `/P` |
| `KS`   | Koya System | ambos | `:MP`/`:GP` `/Lx` |
| `BC`   | Board Count | equipes | — |
| `TBR`  | The Board Result | equipes | — |
| `BBE`  | Berger-By-Encounter (board) | equipes | — |
| `MPvGP`| Match Points vs Game Points | equipes | — |
| `EMMSB`/`EMGSB`/`EGMSB`/`EGGSB` | extended (M/G × M/G) Sonneborn-Berger | equipes | `/C1` `/C2` `/P` |
| `EDE`  | Extended Direct Encounter | equipes | `/P` |
| `EDEBT`/`EDEBB`/`EDET`/`EDEB` | EDE + BC/TBR/BBE (knockout) | equipes | `/P` |
| `SSSC` | Sum of Sonneborn-Berger Score Corrected | equipes | `/Kx` `/P` `/F` |

A lista completa de códigos válidos pré-compostos (ex.: `BH:MP/C1/P`,
`SB/C2/P`, `EGGSB/C1/P`, `SSSC/F/P/Kx`) está na pág. 3 do PDF; `x` = "qualquer
valor razoável deve ser implementado".

> **Mapa do projeto:** o `pairing/tiebreaks.py` já calcula Buchholz,
> Sonneborn-Berger e correlatos. Para o 212, montar a lista a partir da ordem de
> desempate configurada do torneio, sempre iniciando por `PTS`. Mapeamento
> mínimo: pontos→`PTS`, Buchholz→`BH` (Cut-1→`BH/C1`), SB→`SB`, confronto
> direto→`DE`. Em equipes, anexar `:MP` ou `:GP` conforme o score-base.

---

## 12. Anexo C — arquivo de exemplo (validação ponta-a-ponta)

Annex-3 (TRF25 montado à mão, "pode conter erros" segundo a FIDE):
<http://tec.fide.com/wp-content/uploads/2024/09/GrandMommysCup.txt>. Usar só como
referência visual de formatação; não como oráculo de validação.
