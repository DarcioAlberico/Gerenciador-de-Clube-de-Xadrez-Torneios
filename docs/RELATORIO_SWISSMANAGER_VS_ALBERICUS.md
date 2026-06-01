# Relatório: Swiss-Manager x Albericus

Comparação funcional, menu a menu, entre o **Swiss-Manager** instalado nesta
máquina e o estado atual do **Albericus**, com mapa de lacunas e prioridades.

Documentos relacionados:

- Especificação das lacunas: [`ESPEC_PARIDADE_SWISSMANAGER.md`](../ESPEC_PARIDADE_SWISSMANAGER.md)
- Roadmap de implantação: [`ROADMAP_PARIDADE_SWISSMANAGER.md`](../ROADMAP_PARIDADE_SWISSMANAGER.md)

---

## 1. Metodologia (como o teste foi feito)

O Swiss-Manager foi **executado de fato** nesta máquina e inspecionado por três
caminhos complementares:

1. **Execução real do binário.** `C:\Program Files (x86)\SwissManagerUniCode\SwissManager.exe`
   foi iniciado e respondeu normalmente. Versão identificada na barra de título:
   **Swiss-Manager 14.05.2018, Build 13.0.0.57**. Ao abrir, carregou um torneio
   de exemplo `Test_Team_Swiss_System.TUMx` (17 equipes, 80 jogadores, Rodada 1),
   confirmando o modo "Sistema Suíço por equipes". Captura em
   [`swissmanager_tela.png`](swissmanager_tela.png).
2. **Inventário dos menus pela tela** — barra de menus confirmada:
   `Arquivo · Introduzir · Emparceiramento · Informação · Visualizar · Rodada ·
   Listas · Especiais · Lista de rating · Internet · Janela · ?`.
3. **Extração do dicionário de interface.** O arquivo
   `SwissManagerLanguage_POR.Lan` (UTF-16) foi decodificado e produziu **665
   strings** de menus, diálogos e rótulos de opção em português. Isso permite
   enumerar opções que não aparecem sem abrir um torneio real (diálogos de dados
   do torneio, desempates, prêmios, normas FIDE, etc.).

Também foram inventariados os modelos em `Vorlagen\`: `tournamentReport.xls`
(relatório FIDE), `IA1.xls` e `FA1.xls` (formulários de norma de árbitro
internacional/FIDE), `titleform.xls` (pedido de título), `Excel_Template.xls`,
`Example1/2_Pairing_Cards.xls` (cartões de mesa) e `html_vorlage.htm` + `SM.CSS`
(publicação web).

O lado Albericus foi conferido **no código** (`src/`), não só pelo README:
`tournament_settings`, `pairing/` (motor Dutch, equipes, aceleração, desempates),
`rating_service`, `federation_exporters` (TRF16/TRF25) e telas de UI.

> Observação importante de escopo: o Swiss-Manager testado é a build de 2018
> (gratuita/registrada). A versão comercial atual tem itens adicionais
> (ex.: relatórios FIDE mais novos), mas a paridade abaixo usa o binário
> realmente instalado aqui.

---

## 2. Legenda de status

| Símbolo | Significado |
|---|---|
| ✅ | Já existe no Albericus, com profundidade comparável |
| 🟡 | Existe parcialmente / com simplificação relevante |
| ❌ | Não existe no Albericus |
| ⛔ | Fora de escopo por decisão de produto (offline-first / Brasil) |

---

## 3. Inventário menu a menu do Swiss-Manager

### 3.1 Menu `Arquivo`

| Opção do Swiss-Manager | O que faz | Albericus |
|---|---|---|
| Novo torneio | Cria torneio escolhendo o tipo (Suíço, Round Robin, Scheveningen, Suíço/RR por equipes) | 🟡 Cria torneio individual e por equipes; **sem Scheveningen** e o tipo round-robin é interno (não é um fluxo de criação dedicado) |
| Abrir / Salvar / Salvar como | Persistência em arquivos `.TUN/.TUR/.TUT/.TUM/.BAK` | ✅ Banco SQLite local + backups (modelo diferente, mesmo resultado) |
| Import players (XML) | Importa jogadores de XML | 🟡 Importa CSV/XLS/XLSX e Google Forms/Sheets; **não lê o XML nativo do SM** |
| Import Teams / Teamcompositions (XML) | Importa equipes e escalações de XML | 🟡 Tem equipes e escalações, mas a importação é manual/CSV |
| Sair | Encerra | ✅ |

### 3.2 Menu `Introduzir` (entrada de resultados)

| Opção | O que faz | Albericus |
|---|---|---|
| Resultados | Lança resultados (mouse, modo tabela cruzada, "selecionar próximo automaticamente", por tabuleiro) | ✅ Lançamento rápido por botões/atalhos, seleção automática da próxima mesa, painel do árbitro |
| Resultados especiais | WO, bye, partida suspensa, ½:½ "sem lance", 1U:0U, etc. | ✅ Suporta 1:0, 0:1, ½:½, 1F:0F, 0F:1F, 0F:0F e estados de partida |
| Local | Define sede/horário por rodada | ✅ Agenda de datas/horários por rodada (`round_schedule`) |
| Reordenar emparceiramento | Reordena mesas exibidas | 🟡 Há ajuste manual de mesa; reordenação visual livre é limitada |
| Sort players without rating randomly | Sorteio para jogadores sem rating no ranking inicial | 🟡 Ordenação inicial configurável, mas **sem o sorteio aleatório explícito** para sem-rating |

### 3.3 Menu `Emparceiramento`

| Opção | O que faz | Albericus |
|---|---|---|
| Menu de emparceiramentos | Escolha de motor (JaVaFo/FIDE Dutch, "Swiss-Manager engine"), checar último grupo, modo Olimpíada, aceleração, checar presença | 🟡 Motor Dutch próprio (`fide_dutch.py`), aceleração, chamada de presença; **não usa JaVaFo** nem expõe "motor alternativo" |
| Emparceirar com lista fixa | Pareamento por lista fixa (equipes) | ✅ Lista fixa/escalações de equipes |
| Emparceirar jogador / novo jogador manualmente | Pareamento manual | ✅ Ajuste manual de jogadores na mesa antes do fechamento |
| Excluir / Reativar jogador | Remove/reativa do pareamento mantendo inscrição | ✅ Status desistente/ausente/não emparceirado |
| Atribuir bye | Define quem recebe bye | ✅ Controle de bye + bye solicitado (`requested_byes`) |
| Equipes: emparceirar/excluir/reativar/bye | Operações equivalentes para equipes | ✅ Fluxo de equipes com troca de cor/tabuleiro |
| Emparceiramentos proibidos | Impede confrontos específicos | ✅ `prohibited_pairings` / `prohibited_team_pairings` |

### 3.4 Menu `Informação`

| Opção | O que faz | Albericus |
|---|---|---|
| Estado do torneio | Resumo do andamento | ✅ Painel do árbitro + dashboard |
| Jogador / Equipe / Bye | Fichas de informação | ✅ Relatórios/fichas de jogador e equipe |
| Estatísticas de federações | Quantos jogadores por FED | 🟡 Dados existem; **relatório dedicado não** |
| Estatísticas de partidas | Brancas/empate/pretas, % | 🟡 Há estatísticas no relatório; não no formato do SM |
| **Estatísticas de rating FIDE** | **Cálculo da variação de Elo** (We, K, Rc, ΔElo) por jogador e arquivo de envio | ❌ **Não existe** o cálculo oficial de variação Elo (só rating interno por performance) |
| **Informações de títulos FIDE** | **Checagem de normas** (IM/GM/WGM...) e certificado de norma | ❌ Não existe |
| **FIDE Arbiter Norm Report** | Relatório de norma de árbitro (IA/FA) | ❌ Não existe |
| Estatísticas de rating nacional (AUT/POL) | Equivalente nacional | 🟡 Relatório de **taxas** de rating (FIDE/CBX/LBX) existe; estatística de variação não |

### 3.5 Menu `Visualizar` (destino da saída)

| Opção | O que faz | Albericus |
|---|---|---|
| Tela / Impressora / Arquivo | Define para onde a lista vai | ✅ Exporta CSV/XLSX/PDF/HTML; impressão via PDF |
| Configuração de impressão | Ajustes por trabalho | 🟡 Via leitor de PDF do sistema |
| Criar listas diferentes de uma vez | Impressora + texto + HTML simultâneos | 🟡 Exporta cada formato; **não em lote único multi-destino** |

### 3.6 Menu `Listas` (motor de relatórios — núcleo do SM)

| Lista do Swiss-Manager | Albericus |
|---|---|
| Alfabética | ✅ |
| Classificação provisória/final (1 e 2 colunas) | ✅ Classificação intermediária e final |
| Emparceiramentos (por rodada) | ✅ Folha de emparceiramento + mural com QR |
| Resultados | ✅ |
| Ranking inicial (1 e 2 colunas) | ✅ |
| Cross table por ranking inicial | ✅ Tabela cruzada individual |
| Cross table por classificação | ✅ |
| Cartões de emparceiramento (Excel) | ✅ Cartões de mesa em PDF (intervalo configurável, QR) |
| **Prêmios por categorias** | 🟡 Categorias existem; **lista de prêmios em dinheiro não** |
| Emparceiramentos por mesas | ✅ |
| Fichas individuais (FIDE) | 🟡 Há fichas; layout FIDE específico não |
| Lista de equipes / ordem de força | ✅ Tabela cruzada por equipes + detalhe de tabuleiros |
| Lista de participantes (por rating) | ✅ |
| Lista de performance de jogadores | ✅ Performance estimada na classificação |
| Classificações por tabuleiros (prêmio de tabuleiro) | 🟡 Detalhe por tabuleiro existe; **prêmio por tabuleiro não** |
| Lista de normas FIDE (não-oficial) | ❌ |
| Configuração fina de colunas/HTML/texto (larguras %, bordas, quebra de página) | 🟡 HTML/CSS gerado é fixo; **sem editor de colunas** |

### 3.7 Menu `Especiais`

| Opção | O que faz | Albericus |
|---|---|---|
| Arquivos PGN | Exporta/ajusta PGN das partidas | ✅ Exportação PGN |
| Selecionar idioma e diretórios | Idioma do programa e pastas | 🟡 Idioma único (PT); pastas configuráveis em `Config. app` |
| Exportar FIDE Krause **TRF16** | Arquivo oficial para FIDE/Chess-Results | ✅ TRF16 com validação de pendências |
| Mudar tipo de torneio (RR ⇄ Suíço) | Converte o sistema | ❌ |
| Dividir torneio (domínios A/B/C) | Subtorneios num mesmo arquivo | 🟡 Torneios separados/duplicáveis; não "split" num só |
| Ata/Verificação de mesas em Excel | Saídas Excel específicas | ✅ Exporta XLSX |
| Regra dos 100 pontos / arquivos de rating nacionais (CAN/GER/CZE/RSA/BEL/RUS) | Utilidades de federações estrangeiras | ⛔ Fora de escopo (Brasil) |
| Salvar em Access | Banco MDB | ⛔ Fora de escopo |
| Listagens especiais para Olimpíada | Saídas FIDE de Olimpíada | ❌ (nicho) |

### 3.8 Menu `Lista de rating`

| Opção | O que faz | Albericus |
|---|---|---|
| Importar listas de rating | Carrega lista oficial local | ✅ Importa FIDE/CBX em CSV/XLS/XLSX + snapshots |
| Atualizar lista FIDE / FIDE-Blitz | Baixa lista FIDE | ✅ `import_fide_list_from_url` |
| Atualizar listas nacionais (AUT/GER/CZE/POL/POR/RUS/SLO/CRO/RSA/URU...) | Dezenas de federações | ⛔ Albericus mira **FIDE + CBX + LBX** (correto para o Brasil); demais fora de escopo |
| Ordenar/excluir listas de rating | Gerência das listas | 🟡 Snapshots versionados; gerência manual menor |
| Listas de normas | Tabelas de norma | ❌ |
| Parâmetros de desempate | **Configura quais desempates e em que ordem** | ❌ **No SM é configurável; no Albericus a ordem é fixa** |

### 3.9 Menu `Internet`

| Opção | Albericus |
|---|---|
| Upload/registro automático no Chess-Results.com | ⛔ Offline-first por decisão; gera TRF16 para upload manual |
| Importar inscrições online (Chess-Results) | 🟡 Importa Google Forms/Sheets (CSV publicado) |
| Login / personalizar listas / restringir upload | ⛔ Fora de escopo |
| Upload de fotos/álbuns via FTP | ❌ (nicho) |

### 3.10 Menus `Janela` e `?`

| Opção | Albericus |
|---|---|
| Janela: cascata/lado a lado/minimizar | n/a (Albericus é single-window com telas) |
| Ajuda / O que há de novo | 🟡 Manual operacional em PDF; sem "what's new" no app |

### 3.11 Diálogo de dados do torneio (campos)

O diálogo "Dados do torneio" do SM concentra muita configuração. Mapa de campos:

| Campo do SM | Albericus |
|---|---|
| Nome, local, datas, ritmo de jogo | ✅ |
| Diretor, Árbitro Principal, árbitros auxiliares | ✅ `director`, `chief_arbiter`, `arbiters` |
| Federação organizadora, estado | ✅ |
| FIDE Event-ID, organizador, site, e-mail | ✅ |
| Categorias, data de corte, comentários, prêmios (texto) | ✅ (prêmios só como texto livre) |
| Avaliação de rating (Nac./FIDE/maior), cor de mando | ✅ `initial_order` (rating/nac/int/maior/manual) |
| Pontos do bye, pontos de adesão tardia | ✅ `late_entry_points`, bye configurável |
| **Fator K / avaliação de Elo FIDE** | ❌ Não há K nem avaliação de Elo |
| Nº mínimo de partidas (art. 1.44) p/ título | ❌ |
| **Desempates (até ~5, ordem + parâmetros)** | ❌ Ordem fixa |
| Sistema acelerado | ✅ `accelerated_system` / `acceleration_method` (inclui detecção Baku) |
| Flags de interface/publicação (ocultar classificação, mostrar adversários, ocultar cores, arquivar) | ✅ |

---

## 4. O que o Albericus tem **a mais** que o Swiss-Manager

Para registro — não é só déficit; o Albericus já passou o SM em várias frentes
de operação e de gestão de clube:

- Gestão de clube/escola/turmas, membros, responsáveis, financeiro, aulas,
  exercícios, inventário, ranking interno, diplomas/certificados com verificação.
- Painel do árbitro com pendências, relógio local e fila de aprovação.
- **QR local por mesa** com aprovação do árbitro (o SM 2018 não tem).
- **Portal live** local/público com ocultação de dados sensíveis.
- Pré-visualização de rodada com alertas (cor/float/bye/repetição).
- Auditoria append-only, snapshots de emparceiramento/classificação, backups
  guiados e perfis operacionais locais.
- Sincronização multi-dispositivo opcional (fila local) e eventos de relógio.
- TRF25 já esboçado (exportador versionado), além do TRF16 estável.

---

## 5. Mapa de lacunas priorizado

Ordenado por valor para arbitragem oficial no Brasil x esforço.

| # | Lacuna | Status | Impacto | Esforço | Prioridade |
|---|---|---|---|---|---|
| 1 | **Desempates configuráveis** (escolha + ordem + parâmetros por torneio) | ❌ | Alto | Médio | **P0** |
| 2 | **Desempates adicionais** (Buchholz Cut-1, progressivo, Koya, ARO, nº de pretas) | 🟡 | Alto | Médio | **P0** |
| 3 | **Relatório de variação de Elo FIDE** (We, K, Rc, ΔElo) | ❌ | Alto | Médio | **P1** |
| 4 | **Prêmios em dinheiro** (por colocação/categoria/tabuleiro, Hort, divisão, imposto) | 🟡 | Médio-Alto | Médio | **P1** |
| 5 | **Normas e títulos FIDE** (checagem de norma de jogador, IA/FA) | ❌ | Médio | Alto | **P2** |
| 6 | **Fichas/lista FIDE e estatísticas** (federações, partidas, fichas individuais layout FIDE) | 🟡 | Médio | Baixo | **P2** |
| 7 | **Editor de listas/colunas** (HTML/texto com larguras, bordas, lote multi-destino) | 🟡 | Médio | Médio | **P3** |
| 8 | **Sistema Scheveningen** | ❌ | Baixo-Médio | Médio | **P3** |
| 9 | **Importar XML nativo do Swiss-Manager** (migração de quem usa SM) | 🟡 | Médio | Médio | **P3** |
| 10 | **Mudar tipo de torneio / dividir torneio** | ❌ | Baixo | Baixo | **P4** |
| 11 | Listagens de Olimpíada / álbuns de fotos / Access / listas de rating estrangeiras | ❌/⛔ | Baixo | — | **Fora** |
| 12 | Integração Chess-Results.com (upload/online) | ⛔ | — | — | **Fora** (decisão offline-first) |

Detalhe de implementação de cada item em
[`ESPEC_PARIDADE_SWISSMANAGER.md`](../ESPEC_PARIDADE_SWISSMANAGER.md) e a ordem de
execução em [`ROADMAP_PARIDADE_SWISSMANAGER.md`](../ROADMAP_PARIDADE_SWISSMANAGER.md).

---

## 6. Conclusão do relatório

O Albericus **já cobre o núcleo operacional** de um torneio suíço/equipes e vai
além do SM 2018 em gestão de clube, painel do árbitro, QR, portal e auditoria.
As lacunas reais para **paridade arbitral oficial** se concentram em quatro
frentes: (1) **desempates configuráveis e completos**, (2) **cálculo oficial de
variação de Elo FIDE**, (3) **distribuição de prêmios** e (4) **normas/títulos
FIDE**. As três primeiras têm alto valor e esforço médio — são o foco do
roadmap. Integração com Chess-Results.com e listas de rating estrangeiras
permanecem **fora de escopo** por decisão de produto (offline-first, foco Brasil).
