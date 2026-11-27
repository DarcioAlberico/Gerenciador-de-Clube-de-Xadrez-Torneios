# Roadmap de Implementação - Arbitragem e Gestão de Torneios

Documento derivado de `sistema_arbitragem_xadrez_v2_revisado.md`, adaptado ao
estado atual do Albericus.

Para o backlog operacional detalhado do painel, documentos impressos,
classificação cruzada e próximas sprints, usar `ESPEC_PAINEL_ARBITRO.md` como
fonte executiva. Este arquivo permanece como roadmap macro da arbitragem.

## Estado atual resumido

Já existe no Albericus:

- Aplicativo desktop offline-first em Python, CustomTkinter e SQLite.
- Cadastro de torneios, jogadores, membros, clubes/escolas, turmas e equipes.
- Torneios individuais e por equipes.
- Geração de rodadas por sistema suíço simplificado.
- Chamada inicial com presentes/ausentes antes da primeira rodada.
- Lançamento rápido de resultados por botões e atalhos.
- Bloqueio de alterações perigosas em rodadas fechadas.
- Backups, auditoria operacional básica e perfis locais.
- Exportações CSV, XLSX, PDF, HTML, PGN e TRF/FIDE/Chess-Results.
- Validação TRF com avisos de dados oficiais incompletos.
- Site HTML estático do torneio.
- Empacotamento Windows por PyInstaller.

As fases 0 a 9 já possuem implementação substancial: auditoria, snapshots,
prévia, painel do árbitro, QR local, portal live, equipes, exportadores
versionados, sincronização e eventos de relógio. As fases 10 (manual
operacional) e 11 (inscrições flexíveis) foram concluídas, assim como os
documentos impressos, a tabela cruzada e os refinos de agilidade do painel
(ver `ESPEC_PAINEL_ARBITRO.md`, secoes 4 e 5, EPICs A a E).

Além do previsto nas fases, o projeto adotou o motor Gacrux (Otto Milvang,
homologado FIDE) como padrão de emparceiramento (`gacrux_swiss`) e de
desempates (`tiebreak_engine = gacrux`, com adversário virtual e regras FIDE
por data de vigência), mantendo o motor próprio como fallback.

### Fase 12 CONCLUÍDA (2026-08-04)

A auditoria arbitral de 2026-07-29 virou seis sprints (7 a 12), todas
entregues. Schema atual: **v55**. Suite: **1792 testes**.

O que mudou de natureza — e não só de funcionalidade — nestas sprints: o que
antes era **código** virou **dado**, e o que era **silêncio** virou **aviso**.

- **Regulamento como dado.** Os limiares de norma do Handbook B.01
  (`services/norms`), o regulamento de rating por base e ritmo
  (`services/rating`) e as categorias do edital (`services/categories`) são
  registros, não `if`s. Trocar um limiar deixou de ser reescrever o cálculo.
- **Nada mais some calado.** Reduzir rodadas com agenda pede confirmação e
  audita; mudança estrutural depois da rodada 1 exige motivo e audita; falta de
  rating do ritmo cai no standard AVISANDO; motor de desempate que cai avisa.
- **Configuração honesta.** Seis flags que não faziam nada saíram da tela, e um
  teste varre `src/` para reprovar a próxima.
- **Erros de conformidade corrigidos**, cada um com fonte citada: titulados por
  nível e piso de rating ajustado nas normas (B.01 1.4), K de novato e sub-18
  até o fim do ano no rating (B.02), e o "Sistema Hort" da premiação — que
  combinava geral com categoria e **não era** o Sistema Hort (o Hort reparte
  entre empatados).

O detalhamento executivo, item a item e com as armadilhas anotadas, está nos
EPICs F a J de `ESPEC_PAINEL_ARBITRO.md`.

### O que resta

Não há item de conformidade pendente por decisão própria. O que sobrou depende
de **fonte externa** e está listado em "Baixa prioridade inicial" e na seção
"Fora de Escopo" da `ESPEC_PAINEL_ARBITRO.md`:

- **regulamento de rating da CBX** — não publicado em formato legível; o perfil
  já é editável na tela e sai marcado como NÃO conferido;
- **arquivo de submissão da CBX** — formato não publicado;
- ~~**aceleração de Baku** — formula não publicada pela FIDE~~ **corrigido
  (RGS-30):** a fórmula **está** publicada no FIDE Handbook — Baku Acceleration
  Method, C.04.5.1 até 2025, renumerado para C.04.7 a partir de 01/02/2026.
  Não é bloqueio externo: foi implementado em 2026-11-26 (detalhe em
  "Bloqueado por fonte externa" abaixo);
- relógio de hardware, app nativo e submissão automática a federação.

A próxima entrega deve partir de um **teste piloto presencial** ou de um
requisito novo trazido por torneio real.

## Princípios de implementação

1. O desktop e o banco SQLite local continuam sendo a autoridade do torneio.
2. QR Code, portal, mobile e sincronização não alteram tabelas criticas
   diretamente; tudo passa por serviços de aplicação.
3. Toda ação crítica deve gerar auditoria e, quando aplicável, backup.
4. A conformidade FIDE deve ser apresentada como assistência ao árbitro, não
   como homologação automática.
5. Cada fase precisa entregar algo testavel em torneio real ou simulado.

## Fase 0 - Endurecimento do núcleo

Objetivo: tornar geração de rodada, fechamento, correção e exportação mais
auditaveis antes de adicionar web/QR.

Entregas:

- Criar `audit_events` append-only para ações criticas do torneio.
- Criar `pairing_snapshots` com entrada e saída de cada geração de rodada.
- Criar `standings_snapshots` ao fechar rodadas.
- Registrar `pairing_engine_version` e `ruleset_version` por rodada.
- Adicionar `pairing_system` e `acceleration_method` nas configurações.
- Criar helper `backup_before(action, tournament_id, round_id=None)`.
- Bloquear exclusões destrutivas em rodadas fechadas, exigindo evento de
  correcao/reabertura com motivo.
- Adicionar relatório básico de auditoria do torneio.

Critérios de aceite:

- Gerar, fechar, corrigir e exportar um torneio individual sem alteração direta
  no banco fora dos serviços.
- Rodada gerada tem snapshot de entrada e saída.
- Correção de resultado em rodada fechada exige permissão, motivo e auditoria.
- Testes cobrem snapshot, auditoria e backup por rodada.

## Fase 1 - Prévia e explicação de emparceiramento

Objetivo: dar ao árbitro visibilidade antes de publicar a próxima rodada.

Entregas:

- Criar modo "Pré-visualizar próxima rodada" sem gravar definitivamente.
- Separar plano de emparceiramento de persistência no banco.
- Registrar alertas por mesa: confronto repetido, bye, float, cor, scoregroup.
- Criar explicação simples por mesa.
- Mostrar painel de alertas antes de confirmar/publicar rodada.
- Persistir motivo de alteração manual de mesa ou cor.

Critérios de aceite:

- Mesmo snapshot de entrada gera sempre a mesma prévia.
- Árbitro vê alertas antes de confirmar a rodada.
- Alteração manual fica vinculada ao autor, horário e motivo.
- Testes cobrem torneios com 20, 51, 121 e casos-limite.

## Fase 2 - Painel do árbitro

Objetivo: transformar a tela de operação em painel de exceções.

Entregas:

- Criar tela ou aba `Painel arbitro`.
- Indicadores: mesas pendentes, resultados corrigidos, ausentes, byes,
  alertas de cor/float e rodada pronta para fechar.
- Ações rápidas: imprimir rodada, publicar HTML, validar TRF, fechar rodada,
  exportar relatório da rodada.
- Relatório de correções e intervenções.
- Estado visual dos resultados: vazio, submetido, aprovado, rejeitado,
  corrigido, bloqueado.

Critérios de aceite:

- Árbitro consegue acompanhar a rodada sem procurar manualmente pendências.
- Rodada só fecha quando o painel não aponta pendências bloqueantes.
- Testes cobrem os contadores principais.

## Fase 3 - Desempates explicáveis

Objetivo: explicar a classificação final e reduzir conferência manual.

Entregas:

- Criar `tiebreak_components`.
- Salvar componentes de Buchholz, Buchholz mediano, Sonneborn-Berger,
  confronto direto, vitórias e performance.
- Tornar critérios clicáveis na classificação.
- Criar relatório de desempates por jogador.
- Incluir componentes no HTML estático quando permitido.

Critérios de aceite:

- Cada valor de desempate exibido pode ser explicado a partir dos componentes.
- Relatório mostra adversários usados, cortes e totais.
- Testes com torneios pequenos validam empates conhecidos.

## Fase 4 - QR Code local para resultados

Objetivo: permitir envio de resultado pelo celular sem dar autoridade direta ao
participante.

Entregas:

- Criar servidor local opcional FastAPI em `localhost`/rede local.
- Criar `public_tokens` com token assinado por mesa/rodada e expiração.
- Gerar QR por mesa nas folhas de emparceiramento.
- Criar página mobile simples de envio de resultado.
- Gravar envio como `submitted`.
- Criar fila de aprovação no desktop.
- Aprovar/rejeitar resultado com auditoria.

Critérios de aceite:

- Celular na rede local envia resultado de uma mesa por QR.
- Resultado submetido não entra na classificação antes da aprovação.
- Token não funciona para outra mesa, outra rodada ou rodada fechada.
- Testes cobrem token, expiração, aprovação e rejeição.

## Fase 5 - Publicação live e portal público

Objetivo: publicar informações do torneio sem expor dados sensíveis.

Entregas:

- Portal local responsivo com:
  - emparceiramento da rodada atual;
  - classificação;
  - histórico de rodadas;
  - ficha do jogador/equipe;
  - avisos do árbitro.
- Modos `privado`, `clube` e `publico`.
- Exportação JSON publica.
- Ocultação de telefone, e-mail, documento, nascimento completo e observações.
- Botão de publicar/republicar a partir do desktop.

Critérios de aceite:

- Público acompanha emparceiramentos e classificação em rede local.
- Dados sensíveis não aparecem no portal público.
- Site estático atual continua funcionando mesmo sem servidor live.

## Fase 6 - Equipes avançadas

Objetivo: tratar equipes como fluxo arbitral completo, não apenas cadastro.

Entregas:

- Criar política de elenco por torneio: ordem de forca, reservas, prazo,
  limite de trocas e regra de tabuleiro.
- Criar `team_lineup`, `team_lineup_board` e `team_substitution_event`.
- Escalação por rodada.
- Substituição controlada com motivo, validação e auditoria.
- Relatório de escalações e substituições.
- Exportação preparada para evoluir para TRF25/TRF2026.

Critérios de aceite:

- Torneio por equipes com 4 tabuleiros e reservas roda sem perder histórico.
- Resultado aprovado preserva quem jogou em cada tabuleiro.
- Substituição depois de resultado aprovado exige correção formal.

## Fase 7 - Exportação federativa avançada

Objetivo: manter TRF16 estável e preparar evolução para novos formatos.

Entregas:

- Isolar exportadores em arquitetura versionada.
- Fortalecer relatório de pendências antes do TRF.
- Diferenciar partida jogada, bye, WO, dupla ausência e não emparceirado.
- Adicionar testes de encoding e fixtures reais/sinteticas.
- Estudar implementação incremental de TRF25/TRF2026 sem quebrar TRF16.

Critérios de aceite:

- TRF16 continua gerando para torneios individuais e por equipes quando
  aplicável.
- Pendências oficiais aparecem antes da exportação.
- Exportador novo pode ser adicionado sem alterar o fluxo atual.

## Fase 8 - Sincronização e multi-dispositivo

Objetivo: permitir operação assistida por vários dispositivos sem corromper o
torneio.

Entregas:

- Criar `sync_outbox` para eventos locais.
- Registrar dispositivos autorizados em `devices`.
- Sincronização opcional com servidor autoritativo.
- Permissões por perfil para desktop e API.
- Política de conflito: desktop/servidor autoritativo vence, eventos rejeitados
  ficam auditados.

Critérios de aceite:

- Perda de rede não interrompe o torneio local.
- Eventos pendentes sincronizam quando a rede volta.
- Conflitos não alteram resultado fechado sem aprovação do árbitro.

## Fase 9 - Integrações avançadas

Objetivo: adicionar recursos opcionais sem colocar o núcleo em risco.

Entregas:

- Tabela `clock_events`.
- Registro manual de eventos de tempo e ausência.
- Interface de plugins para relogios/dispositivos.
- Primeiro plugin para hardware especifico, se houver demanda real.
- Notificações por e-mail/WhatsApp/SMS como camada opcional.
- Assistente de anomalias apenas como alerta, nunca como decisor.

Critérios de aceite:

- Integrações podem ser desligadas sem afetar torneios locais.
- Hardware nunca altera resultado automaticamente sem aprovação.

## Fase 10 - Operacionalização e manual de arbitragem

Status: concluído em 2026-05-31.

Objetivo: consolidar o que foi implementado em um fluxo operacional claro para
uso em torneio real.

Entregas:

- Documentar o fluxo recomendado antes, durante e depois do torneio.
- Criar checklist de segurança operacional: backup, auditoria, TRF, publicação
  e sincronização opcional.
- Explicar limites das camadas opcionais: QR, portal live, dispositivos,
  notificações e sincronização não substituem a decisão do árbitro.
- Registrar próximos incrementos a partir do backlog restante.

Critérios de aceite:

- [x] O operador consegue preparar um torneio usando apenas o README/manual.
- [x] O manual deixa claro quais recursos são autoritativos e quais são apenas
  auxiliares.
- [x] A Fase 10 não altera regras de emparceiramento nem resultados existentes.

Implementação:

- guia de campo em `docs/Manual_Operacional_Arbitragem.md`;
- PDF imprimível em `docs/Manual_Operacional_Arbitragem.pdf`;
- checklist rápido para até 12 rodadas;
- tabela para registro manual de incidentes;
- gerador reproduzível em `scripts/generate_referee_operations_manual.py`;
- simulador reproduzível em `scripts/run_referee_operational_pilot.py`;
- baseline automatizada em `docs/PILOTO_OPERACIONAL_BASELINE.md` para 121 e
  801 jogadores;
- README aponta para o artefato operacional.

Piloto automatizado inicial:

- todos os limiares locais passaram;
- com 801 jogadores, o painel carregou em 23,0215 ms;
- lançamento de resultado com recarga do painel ficou em 49,4234 ms médios;
- tokens QR de documentos passaram a ser persistidos em lote transacional;
- mural PDF com QR para 400 mesas caiu de 20,3793 s para 3,7016 s;
- backup final de 4.890.624 bytes foi criado em 19,6087 ms;
- restauração em segunda instalação temporária validou 1 rodada e 401 mesas em
  699,9135 ms;
- continuidade offline foi validada com sockets e acessos HTTP bloqueados:
  painel, lançamentos, fechamento, classificação, exportações e backup locais
  completaram em 860,8958 ms;
- a fila QR recebeu e aprovou 20 envios concorrentes em 2.846,3054 ms;
- uma inscrição de última hora após rodada fechada atualizou lista,
  classificação e prévia seguinte em 117,0289 ms, preservando o histórico;
- a conferência oficial antes da rodada 1 importou 700 registros em
  146,0958 ms, comparou sem persistir em 882,3479 ms e confirmou seletivamente
  700 alterações em 4.325,6951 ms;
- a busca direta do painel localizou e lançou a mesa 400, fora das primeiras
  50 mesas inline, em 73,5168 ms;
- o piloto presencial continua necessário para avaliar rede, impressora,
  legibilidade, cliques do operador e restauração no computador físico reserva.

## Fase 11 - Inscrições e importação flexível

Status: concluído em 2026-06-03.

Objetivo: padronizar a coleta de inscrições na origem e aceitar planilhas e
formulários antigos sem edição manual prévia. Detalhamento executivo em
`ESPEC_PAINEL_ARBITRO.md` (EPIC E, itens `REG-01` e `REG-02`, Sprint 6).

Entregas:

- Gerador de formulário de inscrição padronizado (Google Forms), com três
  caminhos: (1) criação **ao vivo** na conta do árbitro via API do Google Forms
  (OAuth de app desktop), devolvendo o link para os jogadores se inscreverem
  sozinhos; (2) **script Apps Script** + definição `.json` (cria o formulário 1x
  sem digitar perguntas); (3) **link pré-preenchido** (sem OAuth) a partir de um
  formulário existente, com o nome do torneio já preenchido para compartilhar.
  Respostas importam direto pelo fluxo de inscrições online. Guia em
  `docs/GUIA_GOOGLE_FORMS.md`.
- Assistente de importação com mapeamento de colunas: `inspect_source` lê
  CSV/XLS/XLSX e URL CSV publicada, devolve cabeçalhos, amostra das primeiras
  linhas e palpite por heurística; tela de de-para por campo canônico com
  pré-visualização; transformações mínimas (idade->nascimento, normalização de
  data, "Sobrenome, Nome"); reuso do preview de status sem persistir antes da
  confirmação.
- Perfis de mapeamento reutilizáveis (`import_mappings`) por origem/formato.

Critérios de aceite:

- Respostas do formulário gerado importam sem mapeamento manual.
- Planilha com colunas fora de ordem e nomes divergentes importa após o
  mapeamento, sem editar o arquivo de origem.
- Nenhuma linha e persistida antes da confirmação no preview.
- Serviço puro de inspecao/normalizacao coberto por testes.

Fora de escopo: importação de formulários em PDF/imagem digitalizada (somente
formatos tabulares: CSV/XLS/XLSX e URL CSV publicada). OCR não será
implementado.

## Fase 12 - Conformidade arbitral e federativa

Status: em execução (auditoria arbitral de 2026-07-29). Sprint 7 iniciada em
2026-07-30:

- `TBK-01` entregue — os ajustes de pontos do árbitro deixaram de ser um registro
  que só o TRF25 via e passaram a somar na classificação, com marcador na tabela,
  motivo por extenso na ata e trilha de auditoria;
- `TBK-02` entregue — a troca do motor FIDE pelo motor próprio deixou de ser um
  warning no log: faixa permanente com o motor que assinou a tabela, evento de
  auditoria, pendência no painel e modo estrito ("falhar em vez de degradar")
  para torneios FIDE-rated. No caminho, um bug do próprio Gacrux (registro 299
  derrubava o cálculo) foi corrigido;
- `ARB-01` entregue — correção em rodada fechada passou a exigir motivo do
  árbitro (era constante no código), a permissão virou desbloqueio POR RODADA com
  justificativa e prazo de 15 min (no lugar de deixar `allow_dangerous_changes`
  ligado no torneio), correção com rodada posterior pareada gera alerta de
  cascata, e os retratos de classificação afetados são arquivados e regravados
  com a classificação **da época de cada rodada**.

- `PAR-04` (parte pontual) entregue — `TEAM_PAIRING_METHODS` estava definido duas
  vezes e a segunda apagava o round-robin por equipes; ele voltou a ser
  selecionável E passou a de fato parear (a geração de rodada nunca lia
  `team_pairing_method`). A troca de cores no individual saiu do `db` cru para o
  serviço, com auditoria nos dois modos. Mais o `pending` acumulado no fechamento
  por equipes e o `KeyError` cru do sumario. Achado no caminho: o dialogo "Trocar
  jogador" não abria (pai errado, `Dialog(self, ...)`).

**SPRINT 7 CONCLUÍDA (2026-07-30).**

Sprint 8 em andamento:

- `TBK-03` entregue (2026-07-30) pela SEGUNDA saída do escopo: o motor próprio foi
  formalmente rebaixado a **legado, não homologavel**, em vez de ganhar uma
  segunda implementação do adversário virtual da FIDE. As regras de desempate são
  versionadas por data e o Gacrux já as acompanha; duas implementações da mesma
  norma divergiriam com o tempo, que e o problema que a TBK-02 existe para
  impedir. O aviso sai na faixa da classificação, no relatório de desempates e na
  hora de escolher o motor. Junto, os dois defeitos que estavam errados em
  qualquer caminho: `wins` contava W.O. (o `WON` da FIDE e vitória no tabuleiro) e
  o confronto direto era aplicado sem todos os empatados terem se enfrentado.
  **Um item da auditoria não se confirmou** — o limiar do Koya já bate com o
  Gacrux; a mudança pedida afastaria os motores, e um teste guarda a equivalência.
- `TBK-04` entregue (2026-07-30): os parâmetros de critério passaram a viver no
  REGISTRO (`TiebreakParam`), validados na porta de entrada e lidos pelos dois
  motores — no Gacrux viram modificador (`BH/C2`, `KS/L60`), cuja sintaxe saiu do
  próprio `gacrux/tiebreak.py`. O registro 212 do TRF25 era uma lista fixa e
  declarava a federação critérios diferentes dos usados; agora sai da
  `tiebreak_sequence` configurada, com os parâmetros junto, e o `WIN` virou `WON`
  (o motor sempre contou vitórias no tabuleiro).
- `TBK-05` entregue (2026-07-31): os quatro desempates de equipes que faltavam —
  Sonneborn-Berger olímpico (`EMGSB`: match points do adversário x game points
  feitos contra ele, que NÃO e o SB de match points), confronto direto, Buchholz
  de game points e board count (Berlin, o único critério em que o menor
  classifica melhor, agora declarado no registro). O board count trouxe o
  resultado POR TABULEIRO até a classificação, com a equipe saindo do elenco do
  jogador e não da paridade do tabuleiro. Junto, uma divida da TBK-04: o corte
  configurado chegava ao arquivo FIDE mas não ao motor em execução. E a tabela
  publicada passou a mostrar o critério que decidiu — ele existia só na ordem.

**SPRINT 8 CONCLUÍDA (2026-07-31).**

Sprint 9 em andamento:

- `ARB-02` entregue (2026-07-31): W.O. lançável no painel (com confirmação e
  atalho), estado de partida ADIADA (schema v47) com recado próprio no
  fechamento, e os códigos `W`/`D`/`L` do TRF — partida DISPUTADA e não ratavel,
  que faltavam e obrigavam o árbitro a mentir no rating ou no Buchholz. Junto
  nasceu o `results_registry.py`: o que um resultado e estava espalhado por seis
  lugares, e a família nova se distingue por uma propriedade que nenhum deles
  expressava.
- `ARB-04` entregue (2026-07-31): o bye solicitado era gravado direto da tela no
  banco, sem serviço — por isso pedido para rodada já gerada era aceito e nunca
  aplicado, pedido de jogador inativo sumia na geração e não havia limite nenhum.
  Nasceu `bye_policy.py` (puro) + `request_bye()` no serviço, com limite por
  jogador e última rodada permitida (schema v48, padrão SEM limite). O `Z` não
  conta para o limite: limita-lo puniria quem avisou que faltaria.
- `ARB-05` entregue (2026-07-31): `player_status` e um campo único que apaga o
  anterior, então "saiu na rodada 3, voltou na 5" não ficava em lugar nenhum.
  Nasceu a tabela `player_status_events` (schema v49, append-only) + o módulo
  puro `participation.py` + seção própria na ata. A mudança vale da PRÓXIMA
  rodada (a atual já foi pareada), e a reentrada de quem DESISTIU exige motivo.
  O TRF não tem código para separar desistência de ausência — o que ele
  distingue e `Z` (não pareado) de `-` (forfeit), e isso já funcionava.
- `ARB-03` entregue (2026-07-31): registro disciplinar com catálogo de infrações
  FIDE (schema v50), que era papel — a tabela do manual operacional. A dedução
  cria o `point_adjustment` vinculado e chega na classificação; partida perdida
  lança W.O. na mesa (e não o `1U-0U` da ARB-02: quem perde por regulamento não
  jogou); queda de seta e ausência passaram a BLOQUEAR o fechamento até a decisão
  ser registrada; e a ata ganhou anexo disciplinar com reincidência marcada.

**SPRINT 9 CONCLUÍDA (2026-07-31).**

Objetivo: fechar as lacunas encontradas na auditoria completa dos módulos de
gestão de torneio feita sob ótica de árbitro FIDE. Detalhamento executivo em
`ESPEC_PAINEL_ARBITRO.md` (EPICs F a J, Sprints 7 a 12).

Entregas, em ordem de prioridade:

1. **Classificação correta (bloqueante, Sprint 7)**: ajustes de pontos do
   árbitro aplicados na classificação (`TBK-01` — ENTREGUE em 2026-07-30),
   fallback do motor Gacrux de desempates com aviso e auditoria (`TBK-02` —
   ENTREGUE em 2026-07-30), correção de resultado com motivo obrigatório,
   desbloqueio pontual e alerta de cascata (`ARB-01` — ENTREGUE em 2026-07-30),
   troca de cores com auditoria e round-robin por equipes destravado
   (`PAR-04` parcial — ENTREGUE em 2026-07-30; a parte de motor — topscorers
   C.3, flutuação em jogo não disputado e float repetido por equipes — ENTREGUE
   em 2026-08-03, na Sprint 10).
2. **Desempates conformes (Sprint 8)**: adversário virtual FIDE no motor
   próprio ou rebaixamento formal a modo legado (`TBK-03` — ENTREGUE em
   2026-07-30), parâmetros de critérios editáveis e registro 212 fiel a
   sequencia configurada (`TBK-04` — ENTREGUE em 2026-07-30), desempates
   olímpicos de equipes (`TBK-05` — ENTREGUE em 2026-07-31). SPRINT CONCLUÍDA.
3. **Fluxo arbitral de salão (Sprint 9)**: W.O. e partida adiada no painel
   inline (`ARB-02` — ENTREGUE em 2026-07-31), política de byes solicitados com
   limites (`ARB-04` — ENTREGUE em 2026-07-31),
   retirada/reentrada com histórico por rodada (`ARB-05` — ENTREGUE em 2026-07-31), registro
   disciplinar de incidentes (`ARB-03` — ENTREGUE em 2026-07-31). SPRINT CONCLUÍDA.
4. **Motores secundários (Sprint 10)**: aceleração e entrada tardia no caminho
   Gacrux sem divergência silenciosa (`PAR-02` — ENTREGUE em 2026-07-31),
   round-robin com tabela persistida e returno (`PAR-01` — ENTREGUE em
   2026-08-01), knockout com desempate registrado e Scheveningen robusto
   (`PAR-03` — ENTREGUE em 2026-08-01).
5. **Submissão federativa (Sprint 11)**: correção do `birth_date` da lista
   FIDE (`FED-05` — ENTREGUE em 2026-08-03), TRF16 com `XXR`/`XXC`/`XXA`,
   Event-ID e modo submissão
   (`FED-03` — ENTREGUE em 2026-08-03), round-trip TRF fiel (`FED-04` — ENTREGUE em 2026-08-03), normas
   FIDE corretas com
   certificado IT3 (`FED-06` — ENTREGUE em 2026-08-04), rating com K/piso/ritmo
   corretos e regulamento modelado (`FED-07` — ENTREGUE em 2026-08-04; o arquivo
   de submissão CBX aguarda o formato publicado).
6. **Organização (Sprint 12 — CONCLUÍDA em 2026-08-04)**: categorias
   configuráveis por torneio (`ORG-01`), premiação conforme edital, inclusive
   Feminino automático (`ORG-02`), agenda e controle de tempo estruturados
   (`ORG-03`), remoção das flags mortas de configuração (`ORG-04`).

Critérios de aceite:

- Nenhuma decisão arbitral registrada no sistema fica invisível na
  classificação publicada.
- Nenhuma troca de motor, descarte de configuração ou perda de dado acontece
  em silêncio: tudo gera aviso ao árbitro e evento de auditoria.
- TRF16 gerado passa no validador Gacrux e abre no Swiss-Manager sem ajuste
  manual.
- Cada item entregue segue a definição de pronto geral deste roadmap.

## Backlog priorizado

Atualizado em 2026-08-04 — **todos os itens da Fase 12 estão entregues**. Os
itens do backlog original (prévia, painel, snapshots, componentes de desempate,
QR, portal, Google Forms, mapeamento de colunas, TRF25) foram entregues nas
fases 0 a 11 e nos EPICs A a E da `ESPEC_PAINEL_ARBITRO.md`. O que segue riscado
abaixo e registro; o que sobra sem risco depende de fonte externa.

### Muito alto impacto / baixa complexidade

- ~~Aplicar `point_adjustments` na classificação (`TBK-01`).~~ FEITO 2026-07-30.
- ~~Aviso e auditoria no fallback do motor de desempates (`TBK-02`).~~ FEITO
  2026-07-30.
- ~~Motivo obrigatório na correção de rodada fechada (`ARB-01`).~~ FEITO
  2026-07-30 (com desbloqueio pontual, cascata e retratos reconciliados).
- ~~Troca de cores via serviço com auditoria (`PAR-04`, parte).~~ FEITO 2026-07-30.
- ~~Destravar round-robin por equipes (constante duplicada) (`PAR-04`, parte).~~
  FEITO 2026-07-30 — e o método passou a de fato parear, não só a ser aceito.
- ~~Corrigir `birth_date` da importação da lista FIDE (`FED-05`).~~ FEITO
  2026-08-03 — o ano da FIDE e data VALIDA no TRF; quem estava errado era a
  validação. Junto: leitor puro com fixture, https e falha de rede com recado.
- ~~W.O. no lançamento inline do painel (`ARB-02`, parte).~~ FEITO 2026-07-31
  — junto com partida adiada e os códigos `W`/`D`/`L`.

### Alto impacto / media complexidade

- ~~Adversário virtual FIDE no motor próprio de desempates (`TBK-03`).~~ FEITO
  2026-07-30 — pela segunda saída: motor próprio rebaixado a legado.
- ~~Parâmetros de critérios editáveis + registro 212 fiel (`TBK-04`).~~ FEITO
  2026-07-30.
- ~~Desempates olímpicos de equipes (`TBK-05`).~~ FEITO 2026-07-31 — SB
  olímpico, confronto direto, Buchholz de game points e board count.
- ~~Política de byes solicitados (`ARB-04`).~~ FEITO 2026-07-31.
- ~~Aceleração e entrada tardia no caminho Gacrux (`PAR-02`).~~ FEITO 2026-07-31
  — aceleração vira registro 250 no TRF e a entrada tardia vira célula de bye;
  o que não cabe no arquivo cai no motor próprio ou avisa, nunca some.
- ~~TRF16 com `XXR`/`XXC`/`XXA`, Event-ID e modo submissão (`FED-03`).~~ FEITO
  2026-08-03 — `XXR`/`XXC` sim; `XXA` NÃO, porque quebra o parser da
  implementação de referência (a aceleração sai no 250). Event-ID como `XXE`,
  modo submissão bloqueante e células iguais as do TRF25.
- ~~Round-trip TRF fiel (`FED-04`).~~ FEITO 2026-08-03 — `U` deixou de ser `F`,
  `Z` preservado, e arbitro/calendario/equipes deixaram de ser descartados.
- ~~Normas FIDE corretas + certificado IT3 (`FED-06`).~~ FEITO 2026-08-04 —
  titulado por nível (CM/WCM fora), piso de rating ajustado que sobe UM
  adversário, tetos de federação e de não ratados, e a tabela do Anexo derivada
  das frações em vez de copiada. IT3 preenchido em PDF por norma detectada.
- ~~Premiação conforme edital (Feminino automático, multi-categoria) (`ORG-02`).~~
  FEITO 2026-08-04 — prêmio de categoria casa com TODAS as categorias do
  jogador, política por prêmio, e o "Sistema Hort" foi para onde ele de
  fato mora: o rateio entre empatados.

### Alto impacto / alta complexidade

- ~~Retirada e reentrada com histórico por rodada (`ARB-05`).~~ FEITO 2026-07-31.
- ~~Registro disciplinar de incidentes (`ARB-03`).~~ FEITO 2026-07-31.
- ~~Round-robin com tabela persistida (Berger) e returno (`PAR-01`).~~ FEITO
  2026-08-01 — números sorteados uma vez e guardados, tabela de Berger da
  referência FIDE, returno com cores invertidas e bye de verdade. A anulação dos
  50% de quem desiste cedo fica DETECTADA e avisada, não automática.
- ~~Knockout com desempate registrado e Scheveningen robusto (`PAR-03`).~~ FEITO
  2026-08-01 — empate no mata-mata para a próxima fase até o árbitro registrar
  quem passa e por que; a chave mostra o motivo; a escala do Scheveningen e
  guardada e sobrevive a desistência.
- ~~Rating com K/piso/ritmo e regulamento CBX (`FED-07`).~~ FEITO 2026-08-04
  — regulamento virou DADO (perfil por base e ritmo), um interpretador de
  ritmo só para o TRF25 e para o rating, cada ritmo com a sua lista, K = 40
  de novato disparando, sub-18 até o fim do ano do aniversario, piso e
  rating inicial do 8.2. O ARQUIVO de submissão da CBX aguarda o formato.
- ~~Categorias configuráveis por torneio (`ORG-01`).~~ FEITO 2026-08-04 — a
  categoria virou dado (tabela por torneio), Feminino virou categoria de
  verdade e a classificação passou a agrupar por TODAS as categorias
  premiáveis do jogador. Torneio sem cadastro continua no padrão antigo.
- ~~Agenda e controle de tempo estruturados (`ORG-03`).~~ FEITO 2026-08-04 —
  `90'+30"` e a forma compacta da FIDE entendidas pelo mesmo interpretador do
  TRF25, agenda com local/ritmo/folga por rodada, confirmação ao reduzir
  rodadas e tolerância de atraso no painel e na súmula.
- ~~Configuração honesta: flags mortas e bloqueios pos-R1 (`ORG-04`).~~ FEITO
  2026-08-04 — seis opções inertes fora da tela (com teste que varre `src/` para
  pegar a próxima), mudança estrutural pos-R1 com motivo e auditoria, e
  `archived` finalmente arquivando.

### Bloqueado por fonte externa

Não iniciar sem o documento ou o equipamento; o código já está preparado onde
fazia sentido preparar.

- **Regulamento de rating da CBX** — o site expõe só a busca de rating e o
  Caderno de Regulamento de Torneios não traz a formula. O perfil de rating já e
  editável em `Config. torneio -> Oficial` e sai marcado como NÃO conferido.
- **Arquivo de submissão da CBX** — formato aceito não publicado.
- ~~**Aceleração de Baku** — formula não publicada pela FIDE~~ — **errado,
  corrigido pelo RGS-30 (2026-11-26).** A regra está no FIDE Handbook desde a
  aprovação de 2016 (Baku Acceleration Method; C.04.5.1 nas edições até 2025,
  C.04.7 "FIDE-approved Accelerated Systems" a partir de 01/02/2026). Em resumo:
  - só vale com pontuação padrão (vitória = 2 empates; na redação de 2026 os
    pontos virtuais são "os pontos de uma vitória");
  - antes da R1 a lista ordenada é dividida em **GA** (a primeira metade,
    arredondada para cima até o par mais próximo: `2 × ⌈N/4⌉`) e **GB** (o
    resto); com entrada tardia, o último jogador do GA continua o mesmo (o GA
    pode ficar ímpar);
  - só o GA recebe pontos virtuais (VP), que entram apenas no **score de
    pareamento** (grupos de pontuação), nunca na classificação;
  - redação vigente: são aceleradas a primeira metade das rodadas (arredondada
    para cima); VP = 1 na primeira metade (arredondada para cima) das rodadas
    aceleradas e 0,5 no resto; depois, zero. Exemplo do Handbook: 9 rodadas →
    5 aceleradas, VP 1 nas R1–R3 e 0,5 nas R4–R5. A redação antiga (Manual do
    Árbitro 2022) fixava VP 1 nas R1–R3 e 0,5 nas R4–R5 para qualquer número
    de rodadas — coincide com a nova só em 9 (e 10) rodadas.

  **Redação conferida (2026-11-26)** no texto do Handbook,
  https://handbook.fide.com/chapter/C0407202602 — C.04.7 "FIDE-approved
  Accelerated Systems", aprovado pelo Conselho em 28/10/2025, aplicado desde
  01/02/2026. Confere com o resumo acima: 1.1 vitória = dois empates e
  derrota = zero; 1.2 GA = "the first half of the participants, rounded up to
  the nearest even number" (`2 × ⌈N/4⌉`, que é também o número do último do
  GA); 1.3 com entrada tardia o último do GA continua o mesmo, o GA pode ficar
  ímpar e o número dele pode mudar; 1.4.1 aceleradas = primeira metade das
  rodadas, para cima; 1.4.2–1.4.3 VP = pontos de uma vitória na primeira
  metade das aceleradas e metade disso no resto, GB nunca recebe; 1.4.4
  exemplos de 9 rodadas (VP 1 nas R1–R3, 0,5 nas R4–R5) e de 11 rodadas por
  equipes (VP 2 nas R1–R3, 1 nas R4–R6); 1.5 score de pareamento = pontos +
  VP. O `ts2json.add_accelerated` do Gacrux usa a mesma conta.

  **Estado do código — FEITO (RGS-30, 2026-11-26):**
  - `pairing/acceleration.py`: `baku_virtual_points` (função pura: N inicial,
    total de rodadas, rodada, número de pareamento, entrantes tardios acima do
    último do GA; recusa com `AppError` pontuação fora do 1.1),
    `baku_initial_field`, `baku_accelerated_player_ids` e
    `baku_acceleration_blocks`. `BAKU_NOT_IMPLEMENTED` saiu.
  - Pareamento: `PairingService._baku_acceleration` monta o GA sobre a lista de
    antes da R1 (`standings_cut.players_as_of_round(…, 1)`), e o plano da rodada
    (quem, quanto) vai ao Gacrux pelo registro 250 (VP 1 e 0,5 são
    representáveis) e ao motor próprio por `standings_with_virtual_points`. O
    VP nunca entra na classificação.
  - TRF25: 250 em blocos (VP 1 nas rodadas de VP inteiro, 0,5 nas restantes,
    competidores 1 até o último do GA) e sufixo `_BAKU` no 192 do Suíço
    individual. Rótulo: "Baku (FIDE C.04.7)".
  - Testes: `tests/test_rgs30_baku.py` (exemplo do Handbook, 11 rodadas,
    entrada tardia, recusa de pontuação, 250/192 e o Gacrux real separando GA
    de GB na R1).

  **Comparação com o bbpPairings v6.0.0 (2026-11-26).** Não há `--baku` na
  linha de comando; o bbp liga Baku pelo 192 `FIDE_DUTCH_2025_BAKU`
  (`trf.cpp`, `applyBakuAcceleration`). Duas diferenças:
  - o bbp usa GA = ⌈N/2⌉, não `2 × ⌈N/4⌉`; diverge do Handbook (1.2, "rounded
    up to the nearest even number") quando N deixa resto 1 ou 2 por 4 (N = 9,
    10, 13…). Nesses campos a R1 do Albericus difere da do bbp, e o Albericus
    segue o Handbook;
  - com N múltiplo de 4 ou resto 3, a R1 e as rodadas aceleradas batem até que
    a história conte: a partir da R3/R4 o Gacrux diverge do bbp (15, 16 e 20
    jogadores). **Causa:** `GacruxEngine._adjust_trf_for_pairing` apaga todo
    250 do exportador e escreve só o da rodada pareada, então o Gacrux calcula
    os floats das rodadas passadas sem o VP. Com o 250 de cada rodada já
    acelerada no arquivo (experimento), as três séries ficaram idênticas ao
    bbp em todas as rodadas. O defeito vale também para a clássica (Haley).

  **Corrigido no mesmo dia:** `GacruxEngine._past_acceleration_records` põe
  no arquivo do pareamento e do `check_round` o 250 de cada rodada acelerada
  já disputada (plano de `_round_acceleration`), para Baku e clássica; o
  `test_r3_e_r4_iguais_ao_bbp` (16 jogadores) fixa as R1–R4 do bbp. O TRF16
  emite o 250 de Baku pelos mesmos `baku_acceleration_blocks` (o TRF25 herda).
  README e Manual Operacional atualizados.

  **Pendência:** Baku por equipes não é aplicado pelo pareamento de equipes (o
  192 de equipes fica sem `_BAKU`).
- **Submissão automática para federação** — sem API pública utilizável.
- **Relógio de hardware** — a interface de plugins existe; falta equipamento
  alvo.

### Baixa prioridade inicial

- App nativo Android/iOS.
- CRDT completo.
- IA para arbitragem.
- Alocação automática de prêmio por tabuleiro em equipes (depende de uma
  classificação por tabuleiro que o programa não calcula).
- `tournaments.system`: legado dessincronizado de `pairing_method`. Aparece em
  relatório, site público e TRF — trocar a fonte desse texto e mudança de
  conteúdo publicado, e merece item próprio.

## Primeiras sprints recomendadas

Nota (2026-07-29): as sprints 1 a 5 abaixo foram entregues (fases 0 a 5 e
EPICs correspondentes). As próximas sprints (7 a 12, Fase 12) estão detalhadas
em `ESPEC_PAINEL_ARBITRO.md`, seção 7. O histórico abaixo fica preservado como
registro.

### Sprint 1 - Auditoria e snapshots

- Criar tabelas `audit_events`, `pairing_snapshots` e `standings_snapshots`.
- Adicionar `pairing_system`, `acceleration_method`, `pairing_engine_version`
  e `ruleset_version`.
- Centralizar `backup_before`.
- Testar geracao/fechamento/correcao com auditoria.

### Sprint 2 - Prévia de rodada

- Extrair plano de emparceiramento antes de persistir.
- Criar botão `Pre-visualizar proxima rodada`.
- Mostrar alertas de repetição, bye, cor e float.
- Confirmar gravação somente depois da revisão do árbitro.

### Sprint 3 - Painel do árbitro

- Criar indicadores operacionais.
- Exibir pendências bloqueantes.
- Adicionar relatório de correcoes/intervencoes.
- Integrar validação TRF e publicação HTML como ações rápidas.

### Sprint 4 - Desempates explicáveis

- Persistir componentes.
- Criar tela/acao "Por que esta posição?".
- Exportar relatório de desempates.
- Adicionar fixtures de classificação conhecida.

### Sprint 5 - QR local

- Criar FastAPI local opcional.
- Gerar tokens por mesa.
- Criar página mobile de envio.
- Criar fila de aprovação no desktop.
- Adicionar QR na folha de emparceiramento.

## Definição de pronto geral

Uma entrega só deve ser considerada pronta quando:

- tem migração de banco compatível com bancos antigos;
- tem testes automatizados do serviço principal;
- registra auditoria quando altera estado crítico;
- não quebra torneios individuais existentes;
- não exige internet para o fluxo principal;
- possui mensagem clara para o árbitro quando bloqueia uma ação;
- está documentada no README ou manual quando afetar a operação.
