# Roadmap de Implementacao - Arbitragem e Gestao de Torneios

Documento derivado de `sistema_arbitragem_xadrez_v2_revisado.md`, adaptado ao
estado atual do Albericus.

Para o backlog operacional detalhado do painel, documentos impressos,
classificacao cruzada e proximas sprints, usar `ESPEC_PAINEL_ARBITRO.md` como
fonte executiva. Este arquivo permanece como roadmap macro da arbitragem.

## Estado atual resumido

Ja existe no Albericus:

- Aplicativo desktop offline-first em Python, CustomTkinter e SQLite.
- Cadastro de torneios, jogadores, membros, clubes/escolas, turmas e equipes.
- Torneios individuais e por equipes.
- Geracao de rodadas por sistema suico simplificado.
- Chamada inicial com presentes/ausentes antes da primeira rodada.
- Lancamento rapido de resultados por botoes e atalhos.
- Bloqueio de alteracoes perigosas em rodadas fechadas.
- Backups, auditoria operacional basica e perfis locais.
- Exportacoes CSV, XLSX, PDF, HTML, PGN e TRF/FIDE/Chess-Results.
- Validacao TRF com avisos de dados oficiais incompletos.
- Site HTML estatico do torneio.
- Empacotamento Windows por PyInstaller.

As fases 0 a 9 ja possuem implementacao substancial: auditoria, snapshots,
previa, painel do arbitro, QR local, portal live, equipes, exportadores
versionados, sincronizacao e eventos de relogio. As fases 10 (manual
operacional) e 11 (inscricoes flexiveis) foram concluidas, assim como os
documentos impressos, a tabela cruzada e os refinos de agilidade do painel
(ver `ESPEC_PAINEL_ARBITRO.md`, secoes 4 e 5, EPICs A a E).

Alem do previsto nas fases, o projeto adotou o motor Gacrux (Otto Milvang,
homologado FIDE) como padrao de emparceiramento (`gacrux_swiss`) e de
desempates (`tiebreak_engine = gacrux`, com adversario virtual e regras FIDE
por data de vigencia), mantendo o motor proprio como fallback.

O backlog prioritario atual vem da auditoria arbitral de 2026-07-29 (Fase 12
abaixo): conformidade de desempates e classificacao, fluxo arbitral de salao,
correcoes nos motores secundarios e submissao federativa. O detalhamento
executivo esta nos EPICs F a J de `ESPEC_PAINEL_ARBITRO.md`.

## Principios de implementacao

1. O desktop e o banco SQLite local continuam sendo a autoridade do torneio.
2. QR Code, portal, mobile e sincronizacao nao alteram tabelas criticas
   diretamente; tudo passa por servicos de aplicacao.
3. Toda acao critica deve gerar auditoria e, quando aplicavel, backup.
4. A conformidade FIDE deve ser apresentada como assistencia ao arbitro, nao
   como homologacao automatica.
5. Cada fase precisa entregar algo testavel em torneio real ou simulado.

## Fase 0 - Endurecimento do nucleo

Objetivo: tornar geracao de rodada, fechamento, correcao e exportacao mais
auditaveis antes de adicionar web/QR.

Entregas:

- Criar `audit_events` append-only para acoes criticas do torneio.
- Criar `pairing_snapshots` com entrada e saida de cada geracao de rodada.
- Criar `standings_snapshots` ao fechar rodadas.
- Registrar `pairing_engine_version` e `ruleset_version` por rodada.
- Adicionar `pairing_system` e `acceleration_method` nas configuracoes.
- Criar helper `backup_before(action, tournament_id, round_id=None)`.
- Bloquear exclusoes destrutivas em rodadas fechadas, exigindo evento de
  correcao/reabertura com motivo.
- Adicionar relatorio basico de auditoria do torneio.

Criterios de aceite:

- Gerar, fechar, corrigir e exportar um torneio individual sem alteracao direta
  no banco fora dos servicos.
- Rodada gerada tem snapshot de entrada e saida.
- Correcao de resultado em rodada fechada exige permissao, motivo e auditoria.
- Testes cobrem snapshot, auditoria e backup por rodada.

## Fase 1 - Previa e explicacao de emparceiramento

Objetivo: dar ao arbitro visibilidade antes de publicar a proxima rodada.

Entregas:

- Criar modo "Pre-visualizar proxima rodada" sem gravar definitivamente.
- Separar plano de emparceiramento de persistencia no banco.
- Registrar alertas por mesa: confronto repetido, bye, float, cor, scoregroup.
- Criar explicacao simples por mesa.
- Mostrar painel de alertas antes de confirmar/publicar rodada.
- Persistir motivo de alteracao manual de mesa ou cor.

Criterios de aceite:

- Mesmo snapshot de entrada gera sempre a mesma previa.
- Arbitro ve alertas antes de confirmar a rodada.
- Alteracao manual fica vinculada ao autor, horario e motivo.
- Testes cobrem torneios com 20, 51, 121 e casos-limite.

## Fase 2 - Painel do arbitro

Objetivo: transformar a tela de operacao em painel de excecoes.

Entregas:

- Criar tela ou aba `Painel arbitro`.
- Indicadores: mesas pendentes, resultados corrigidos, ausentes, byes,
  alertas de cor/float e rodada pronta para fechar.
- Acoes rapidas: imprimir rodada, publicar HTML, validar TRF, fechar rodada,
  exportar relatorio da rodada.
- Relatorio de correcoes e intervencoes.
- Estado visual dos resultados: vazio, submetido, aprovado, rejeitado,
  corrigido, bloqueado.

Criterios de aceite:

- Arbitro consegue acompanhar a rodada sem procurar manualmente pendencias.
- Rodada so fecha quando o painel nao aponta pendencias bloqueantes.
- Testes cobrem os contadores principais.

## Fase 3 - Desempates explicaveis

Objetivo: explicar a classificacao final e reduzir conferencia manual.

Entregas:

- Criar `tiebreak_components`.
- Salvar componentes de Buchholz, Buchholz mediano, Sonneborn-Berger,
  confronto direto, vitorias e performance.
- Tornar criterios clicaveis na classificacao.
- Criar relatorio de desempates por jogador.
- Incluir componentes no HTML estatico quando permitido.

Criterios de aceite:

- Cada valor de desempate exibido pode ser explicado a partir dos componentes.
- Relatorio mostra adversarios usados, cortes e totais.
- Testes com torneios pequenos validam empates conhecidos.

## Fase 4 - QR Code local para resultados

Objetivo: permitir envio de resultado pelo celular sem dar autoridade direta ao
participante.

Entregas:

- Criar servidor local opcional FastAPI em `localhost`/rede local.
- Criar `public_tokens` com token assinado por mesa/rodada e expiracao.
- Gerar QR por mesa nas folhas de emparceiramento.
- Criar pagina mobile simples de envio de resultado.
- Gravar envio como `submitted`.
- Criar fila de aprovacao no desktop.
- Aprovar/rejeitar resultado com auditoria.

Criterios de aceite:

- Celular na rede local envia resultado de uma mesa por QR.
- Resultado submetido nao entra na classificacao antes da aprovacao.
- Token nao funciona para outra mesa, outra rodada ou rodada fechada.
- Testes cobrem token, expiracao, aprovacao e rejeicao.

## Fase 5 - Publicacao live e portal publico

Objetivo: publicar informacoes do torneio sem expor dados sensiveis.

Entregas:

- Portal local responsivo com:
  - emparceiramento da rodada atual;
  - classificacao;
  - historico de rodadas;
  - ficha do jogador/equipe;
  - avisos do arbitro.
- Modos `privado`, `clube` e `publico`.
- Exportacao JSON publica.
- Ocultacao de telefone, e-mail, documento, nascimento completo e observacoes.
- Botao de publicar/republicar a partir do desktop.

Criterios de aceite:

- Publico acompanha emparceiramentos e classificacao em rede local.
- Dados sensiveis nao aparecem no portal publico.
- Site estatico atual continua funcionando mesmo sem servidor live.

## Fase 6 - Equipes avancadas

Objetivo: tratar equipes como fluxo arbitral completo, nao apenas cadastro.

Entregas:

- Criar politica de elenco por torneio: ordem de forca, reservas, prazo,
  limite de trocas e regra de tabuleiro.
- Criar `team_lineup`, `team_lineup_board` e `team_substitution_event`.
- Escalacao por rodada.
- Substituicao controlada com motivo, validacao e auditoria.
- Relatorio de escalacoes e substituicoes.
- Exportacao preparada para evoluir para TRF25/TRF2026.

Criterios de aceite:

- Torneio por equipes com 4 tabuleiros e reservas roda sem perder historico.
- Resultado aprovado preserva quem jogou em cada tabuleiro.
- Substituicao depois de resultado aprovado exige correcao formal.

## Fase 7 - Exportacao federativa avancada

Objetivo: manter TRF16 estavel e preparar evolucao para novos formatos.

Entregas:

- Isolar exportadores em arquitetura versionada.
- Fortalecer relatorio de pendencias antes do TRF.
- Diferenciar partida jogada, bye, WO, dupla ausencia e nao emparceirado.
- Adicionar testes de encoding e fixtures reais/sinteticas.
- Estudar implementacao incremental de TRF25/TRF2026 sem quebrar TRF16.

Criterios de aceite:

- TRF16 continua gerando para torneios individuais e por equipes quando
  aplicavel.
- Pendencias oficiais aparecem antes da exportacao.
- Exportador novo pode ser adicionado sem alterar o fluxo atual.

## Fase 8 - Sincronizacao e multi-dispositivo

Objetivo: permitir operacao assistida por varios dispositivos sem corromper o
torneio.

Entregas:

- Criar `sync_outbox` para eventos locais.
- Registrar dispositivos autorizados em `devices`.
- Sincronizacao opcional com servidor autoritativo.
- Permissoes por perfil para desktop e API.
- Politica de conflito: desktop/servidor autoritativo vence, eventos rejeitados
  ficam auditados.

Criterios de aceite:

- Perda de rede nao interrompe o torneio local.
- Eventos pendentes sincronizam quando a rede volta.
- Conflitos nao alteram resultado fechado sem aprovacao do arbitro.

## Fase 9 - Integracoes avancadas

Objetivo: adicionar recursos opcionais sem colocar o nucleo em risco.

Entregas:

- Tabela `clock_events`.
- Registro manual de eventos de tempo e ausencia.
- Interface de plugins para relogios/dispositivos.
- Primeiro plugin para hardware especifico, se houver demanda real.
- Notificacoes por e-mail/WhatsApp/SMS como camada opcional.
- Assistente de anomalias apenas como alerta, nunca como decisor.

Criterios de aceite:

- Integracoes podem ser desligadas sem afetar torneios locais.
- Hardware nunca altera resultado automaticamente sem aprovacao.

## Fase 10 - Operacionalizacao e manual de arbitragem

Status: concluido em 2026-05-31.

Objetivo: consolidar o que foi implementado em um fluxo operacional claro para
uso em torneio real.

Entregas:

- Documentar o fluxo recomendado antes, durante e depois do torneio.
- Criar checklist de seguranca operacional: backup, auditoria, TRF, publicacao
  e sincronizacao opcional.
- Explicar limites das camadas opcionais: QR, portal live, dispositivos,
  notificacoes e sincronizacao nao substituem a decisao do arbitro.
- Registrar proximos incrementos a partir do backlog restante.

Criterios de aceite:

- [x] O operador consegue preparar um torneio usando apenas o README/manual.
- [x] O manual deixa claro quais recursos sao autoritativos e quais sao apenas
  auxiliares.
- [x] A Fase 10 nao altera regras de emparceiramento nem resultados existentes.

Implementacao:

- guia de campo em `docs/Manual_Operacional_Arbitragem.md`;
- PDF imprimivel em `docs/Manual_Operacional_Arbitragem.pdf`;
- checklist rapido para ate 12 rodadas;
- tabela para registro manual de incidentes;
- gerador reproduzivel em `scripts/generate_referee_operations_manual.py`;
- simulador reproduzivel em `scripts/run_referee_operational_pilot.py`;
- baseline automatizada em `docs/PILOTO_OPERACIONAL_BASELINE.md` para 121 e
  801 jogadores;
- README aponta para o artefato operacional.

Piloto automatizado inicial:

- todos os limiares locais passaram;
- com 801 jogadores, o painel carregou em 23,0215 ms;
- lancamento de resultado com recarga do painel ficou em 49,4234 ms medios;
- tokens QR de documentos passaram a ser persistidos em lote transacional;
- mural PDF com QR para 400 mesas caiu de 20,3793 s para 3,7016 s;
- backup final de 4.890.624 bytes foi criado em 19,6087 ms;
- restauracao em segunda instalacao temporaria validou 1 rodada e 401 mesas em
  699,9135 ms;
- continuidade offline foi validada com sockets e acessos HTTP bloqueados:
  painel, lancamentos, fechamento, classificacao, exportacoes e backup locais
  completaram em 860,8958 ms;
- a fila QR recebeu e aprovou 20 envios concorrentes em 2.846,3054 ms;
- uma inscricao de ultima hora apos rodada fechada atualizou lista,
  classificacao e previa seguinte em 117,0289 ms, preservando o historico;
- a conferencia oficial antes da rodada 1 importou 700 registros em
  146,0958 ms, comparou sem persistir em 882,3479 ms e confirmou seletivamente
  700 alteracoes em 4.325,6951 ms;
- a busca direta do painel localizou e lancou a mesa 400, fora das primeiras
  50 mesas inline, em 73,5168 ms;
- o piloto presencial continua necessario para avaliar rede, impressora,
  legibilidade, cliques do operador e restauracao no computador fisico reserva.

## Fase 11 - Inscricoes e importacao flexivel

Status: concluido em 2026-06-03.

Objetivo: padronizar a coleta de inscricoes na origem e aceitar planilhas e
formularios antigos sem edicao manual previa. Detalhamento executivo em
`ESPEC_PAINEL_ARBITRO.md` (EPIC E, itens `REG-01` e `REG-02`, Sprint 6).

Entregas:

- Gerador de formulario de inscricao padronizado (Google Forms), com tres
  caminhos: (1) criacao **ao vivo** na conta do arbitro via API do Google Forms
  (OAuth de app desktop), devolvendo o link para os jogadores se inscreverem
  sozinhos; (2) **script Apps Script** + definicao `.json` (cria o formulario 1x
  sem digitar perguntas); (3) **link pre-preenchido** (sem OAuth) a partir de um
  formulario existente, com o nome do torneio ja preenchido para compartilhar.
  Respostas importam direto pelo fluxo de inscricoes online. Guia em
  `docs/GUIA_GOOGLE_FORMS.md`.
- Assistente de importacao com mapeamento de colunas: `inspect_source` le
  CSV/XLS/XLSX e URL CSV publicada, devolve cabecalhos, amostra das primeiras
  linhas e palpite por heuristica; tela de de-para por campo canonico com
  pre-visualizacao; transformacoes minimas (idade->nascimento, normalizacao de
  data, "Sobrenome, Nome"); reuso do preview de status sem persistir antes da
  confirmacao.
- Perfis de mapeamento reutilizaveis (`import_mappings`) por origem/formato.

Criterios de aceite:

- Respostas do formulario gerado importam sem mapeamento manual.
- Planilha com colunas fora de ordem e nomes divergentes importa apos o
  mapeamento, sem editar o arquivo de origem.
- Nenhuma linha e persistida antes da confirmacao no preview.
- Servico puro de inspecao/normalizacao coberto por testes.

Fora de escopo: importacao de formularios em PDF/imagem digitalizada (somente
formatos tabulares: CSV/XLS/XLSX e URL CSV publicada). OCR nao sera
implementado.

## Fase 12 - Conformidade arbitral e federativa

Status: em execucao (auditoria arbitral de 2026-07-29). Sprint 7 iniciada em
2026-07-30:

- `TBK-01` entregue — os ajustes de pontos do arbitro deixaram de ser um registro
  que so o TRF25 via e passaram a somar na classificacao, com marcador na tabela,
  motivo por extenso na ata e trilha de auditoria;
- `TBK-02` entregue — a troca do motor FIDE pelo motor proprio deixou de ser um
  warning no log: faixa permanente com o motor que assinou a tabela, evento de
  auditoria, pendencia no painel e modo estrito ("falhar em vez de degradar")
  para torneios FIDE-rated. No caminho, um bug do proprio Gacrux (registro 299
  derrubava o calculo) foi corrigido;
- `ARB-01` entregue — correcao em rodada fechada passou a exigir motivo do
  arbitro (era constante no codigo), a permissao virou desbloqueio POR RODADA com
  justificativa e prazo de 15 min (no lugar de deixar `allow_dangerous_changes`
  ligado no torneio), correcao com rodada posterior pareada gera alerta de
  cascata, e os retratos de classificacao afetados sao arquivados e regravados
  com a classificacao **da epoca de cada rodada**.

- `PAR-04` (parte pontual) entregue — `TEAM_PAIRING_METHODS` estava definido duas
  vezes e a segunda apagava o round-robin por equipes; ele voltou a ser
  selecionavel E passou a de fato parear (a geracao de rodada nunca lia
  `team_pairing_method`). A troca de cores no individual saiu do `db` cru para o
  servico, com auditoria nos dois modos. Mais o `pending` acumulado no fechamento
  por equipes e o `KeyError` cru do sumario. Achado no caminho: o dialogo "Trocar
  jogador" nao abria (pai errado, `Dialog(self, ...)`).

**SPRINT 7 CONCLUIDA (2026-07-30).**

Sprint 8 em andamento:

- `TBK-03` entregue (2026-07-30) pela SEGUNDA saida do escopo: o motor proprio foi
  formalmente rebaixado a **legado, nao homologavel**, em vez de ganhar uma
  segunda implementacao do adversario virtual da FIDE. As regras de desempate sao
  versionadas por data e o Gacrux ja as acompanha; duas implementacoes da mesma
  norma divergiriam com o tempo, que e o problema que a TBK-02 existe para
  impedir. O aviso sai na faixa da classificacao, no relatorio de desempates e na
  hora de escolher o motor. Junto, os dois defeitos que estavam errados em
  qualquer caminho: `wins` contava W.O. (o `WON` da FIDE e vitoria no tabuleiro) e
  o confronto direto era aplicado sem todos os empatados terem se enfrentado.
  **Um item da auditoria nao se confirmou** — o limiar do Koya ja bate com o
  Gacrux; a mudanca pedida afastaria os motores, e um teste guarda a equivalencia.
- `TBK-04` entregue (2026-07-30): os parametros de criterio passaram a viver no
  REGISTRO (`TiebreakParam`), validados na porta de entrada e lidos pelos dois
  motores — no Gacrux viram modificador (`BH/C2`, `KS/L60`), cuja sintaxe saiu do
  proprio `gacrux/tiebreak.py`. O registro 212 do TRF25 era uma lista fixa e
  declarava a federacao criterios diferentes dos usados; agora sai da
  `tiebreak_sequence` configurada, com os parametros junto, e o `WIN` virou `WON`
  (o motor sempre contou vitorias no tabuleiro).
- `TBK-05` entregue (2026-07-31): os quatro desempates de equipes que faltavam —
  Sonneborn-Berger olimpico (`EMGSB`: match points do adversario x game points
  feitos contra ele, que NAO e o SB de match points), confronto direto, Buchholz
  de game points e board count (Berlin, o unico criterio em que o menor
  classifica melhor, agora declarado no registro). O board count trouxe o
  resultado POR TABULEIRO ate a classificacao, com a equipe saindo do elenco do
  jogador e nao da paridade do tabuleiro. Junto, uma divida da TBK-04: o corte
  configurado chegava ao arquivo FIDE mas nao ao motor em execucao. E a tabela
  publicada passou a mostrar o criterio que decidiu — ele existia so na ordem.

**SPRINT 8 CONCLUIDA (2026-07-31).**

Sprint 9 em andamento:

- `ARB-02` entregue (2026-07-31): W.O. lancavel no painel (com confirmacao e
  atalho), estado de partida ADIADA (schema v47) com recado proprio no
  fechamento, e os codigos `W`/`D`/`L` do TRF — partida DISPUTADA e nao ratavel,
  que faltavam e obrigavam o arbitro a mentir no rating ou no Buchholz. Junto
  nasceu o `results_registry.py`: o que um resultado e estava espalhado por seis
  lugares, e a familia nova se distingue por uma propriedade que nenhum deles
  expressava.

Objetivo: fechar as lacunas encontradas na auditoria completa dos modulos de
gestao de torneio feita sob otica de arbitro FIDE. Detalhamento executivo em
`ESPEC_PAINEL_ARBITRO.md` (EPICs F a J, Sprints 7 a 12).

Entregas, em ordem de prioridade:

1. **Classificacao correta (bloqueante, Sprint 7)**: ajustes de pontos do
   arbitro aplicados na classificacao (`TBK-01` — ENTREGUE em 2026-07-30),
   fallback do motor Gacrux de desempates com aviso e auditoria (`TBK-02` —
   ENTREGUE em 2026-07-30), correcao de resultado com motivo obrigatorio,
   desbloqueio pontual e alerta de cascata (`ARB-01` — ENTREGUE em 2026-07-30),
   troca de cores com auditoria e round-robin por equipes destravado
   (`PAR-04` parcial — ENTREGUE em 2026-07-30).
2. **Desempates conformes (Sprint 8)**: adversario virtual FIDE no motor
   proprio ou rebaixamento formal a modo legado (`TBK-03` — ENTREGUE em
   2026-07-30), parametros de criterios editaveis e registro 212 fiel a
   sequencia configurada (`TBK-04` — ENTREGUE em 2026-07-30), desempates
   olimpicos de equipes (`TBK-05` — ENTREGUE em 2026-07-31). SPRINT CONCLUIDA.
3. **Fluxo arbitral de salao (Sprint 9)**: W.O. e partida adiada no painel
   inline (`ARB-02` — ENTREGUE em 2026-07-31), politica de byes solicitados com
   limites (`ARB-04`),
   retirada/reentrada com historico por rodada (`ARB-05`), registro
   disciplinar de incidentes (`ARB-03`).
4. **Motores secundarios (Sprint 10)**: aceleracao e entrada tardia no caminho
   Gacrux sem divergencia silenciosa (`PAR-02`), round-robin com tabela
   persistida e returno (`PAR-01`), knockout com desempate registrado e
   Scheveningen robusto (`PAR-03`).
5. **Submissao federativa (Sprint 11)**: correcao do `birth_date` da lista
   FIDE (`FED-05`), TRF16 com `XXR`/`XXC`/`XXA`, Event-ID e modo submissao
   (`FED-03`), round-trip TRF fiel (`FED-04`), normas FIDE corretas com
   certificado IT3 (`FED-06`), rating com K/piso/ritmo corretos e relatorio
   CBX real (`FED-07`).
6. **Organizacao (Sprint 12)**: categorias configuraveis por torneio
   (`ORG-01`), premiacao conforme edital, inclusive Feminino automatico
   (`ORG-02`), agenda e controle de tempo estruturados (`ORG-03`), remocao ou
   implementacao das flags mortas de configuracao (`ORG-04`).

Criterios de aceite:

- Nenhuma decisao arbitral registrada no sistema fica invisivel na
  classificacao publicada.
- Nenhuma troca de motor, descarte de configuracao ou perda de dado acontece
  em silencio: tudo gera aviso ao arbitro e evento de auditoria.
- TRF16 gerado passa no validador Gacrux e abre no Swiss-Manager sem ajuste
  manual.
- Cada item entregue segue a definicao de pronto geral deste roadmap.

## Backlog priorizado

Atualizado em 2026-07-29. Os itens do backlog original (previa, painel,
snapshots, componentes de desempate, QR, portal, Google Forms, mapeamento de
colunas, TRF25) foram entregues nas fases 0 a 11 e nos EPICs A a E da
`ESPEC_PAINEL_ARBITRO.md`. O backlog atual deriva da Fase 12.

### Muito alto impacto / baixa complexidade

- ~~Aplicar `point_adjustments` na classificacao (`TBK-01`).~~ FEITO 2026-07-30.
- ~~Aviso e auditoria no fallback do motor de desempates (`TBK-02`).~~ FEITO
  2026-07-30.
- ~~Motivo obrigatorio na correcao de rodada fechada (`ARB-01`).~~ FEITO
  2026-07-30 (com desbloqueio pontual, cascata e retratos reconciliados).
- ~~Troca de cores via servico com auditoria (`PAR-04`, parte).~~ FEITO 2026-07-30.
- ~~Destravar round-robin por equipes (constante duplicada) (`PAR-04`, parte).~~
  FEITO 2026-07-30 — e o metodo passou a de fato parear, nao so a ser aceito.
- Corrigir `birth_date` da importacao da lista FIDE (`FED-05`).
- ~~W.O. no lancamento inline do painel (`ARB-02`, parte).~~ FEITO 2026-07-31
  — junto com partida adiada e os codigos `W`/`D`/`L`.

### Alto impacto / media complexidade

- ~~Adversario virtual FIDE no motor proprio de desempates (`TBK-03`).~~ FEITO
  2026-07-30 — pela segunda saida: motor proprio rebaixado a legado.
- ~~Parametros de criterios editaveis + registro 212 fiel (`TBK-04`).~~ FEITO
  2026-07-30.
- ~~Desempates olimpicos de equipes (`TBK-05`).~~ FEITO 2026-07-31 — SB
  olimpico, confronto direto, Buchholz de game points e board count.
- Politica de byes solicitados (`ARB-04`).
- Aceleracao e entrada tardia no caminho Gacrux (`PAR-02`).
- TRF16 com `XXR`/`XXC`/`XXA`, Event-ID e modo submissao (`FED-03`).
- Round-trip TRF fiel (`FED-04`).
- Normas FIDE corretas + certificado IT3 (`FED-06`).
- Premiacao conforme edital (Feminino automatico, multi-categoria) (`ORG-02`).

### Alto impacto / alta complexidade

- Retirada e reentrada com historico por rodada (`ARB-05`).
- Registro disciplinar de incidentes (`ARB-03`).
- Round-robin com tabela persistida (Berger) e returno (`PAR-01`).
- Knockout com desempate registrado e Scheveningen robusto (`PAR-03`).
- Rating com K/piso/ritmo e regulamento CBX (`FED-07`).
- Categorias configuraveis por torneio (`ORG-01`).
- Agenda e controle de tempo estruturados (`ORG-03`).

### Baixa prioridade inicial

- Integracao com relogios (hardware).
- App nativo Android/iOS.
- Submissao automatica para federacao.
- CRDT completo.
- IA para arbitragem.
- Aceleracao de Baku (aguardando formula publicada pela FIDE).

## Primeiras sprints recomendadas

Nota (2026-07-29): as sprints 1 a 5 abaixo foram entregues (fases 0 a 5 e
EPICs correspondentes). As proximas sprints (7 a 12, Fase 12) estao detalhadas
em `ESPEC_PAINEL_ARBITRO.md`, secao 7. O historico abaixo fica preservado como
registro.

### Sprint 1 - Auditoria e snapshots

- Criar tabelas `audit_events`, `pairing_snapshots` e `standings_snapshots`.
- Adicionar `pairing_system`, `acceleration_method`, `pairing_engine_version`
  e `ruleset_version`.
- Centralizar `backup_before`.
- Testar geracao/fechamento/correcao com auditoria.

### Sprint 2 - Previa de rodada

- Extrair plano de emparceiramento antes de persistir.
- Criar botao `Pre-visualizar proxima rodada`.
- Mostrar alertas de repeticao, bye, cor e float.
- Confirmar gravacao somente depois da revisao do arbitro.

### Sprint 3 - Painel do arbitro

- Criar indicadores operacionais.
- Exibir pendencias bloqueantes.
- Adicionar relatorio de correcoes/intervencoes.
- Integrar validacao TRF e publicacao HTML como acoes rapidas.

### Sprint 4 - Desempates explicaveis

- Persistir componentes.
- Criar tela/acao "Por que esta posicao?".
- Exportar relatorio de desempates.
- Adicionar fixtures de classificacao conhecida.

### Sprint 5 - QR local

- Criar FastAPI local opcional.
- Gerar tokens por mesa.
- Criar pagina mobile de envio.
- Criar fila de aprovacao no desktop.
- Adicionar QR na folha de emparceiramento.

## Definicao de pronto geral

Uma entrega so deve ser considerada pronta quando:

- tem migracao de banco compativel com bancos antigos;
- tem testes automatizados do servico principal;
- registra auditoria quando altera estado critico;
- nao quebra torneios individuais existentes;
- nao exige internet para o fluxo principal;
- possui mensagem clara para o arbitro quando bloqueia uma acao;
- esta documentada no README ou manual quando afetar a operacao.
