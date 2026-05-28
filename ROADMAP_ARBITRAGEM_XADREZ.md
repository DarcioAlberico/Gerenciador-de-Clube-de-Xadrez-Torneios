# Roadmap de Implementacao - Arbitragem e Gestao de Torneios

Documento derivado de `sistema_arbitragem_xadrez_v2_revisado.md`, adaptado ao
estado atual do Albericus.

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

Ainda falta transformar o Albericus em um sistema de arbitragem auditavel com
explicacao completa de pareamentos, resultados submetidos por QR, snapshots,
portal live e workflow mais forte para equipes.

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

- O operador consegue preparar um torneio usando apenas o README/manual.
- O manual deixa claro quais recursos sao autoritativos e quais sao apenas
  auxiliares.
- A Fase 10 nao altera regras de emparceiramento nem resultados existentes.

## Backlog priorizado

### Muito alto impacto / baixa complexidade

- Pre-visualizar proxima rodada.
- Relatorio de auditoria do torneio.
- Log de correcoes com motivo.
- Status visual de resultados pendentes.
- PDF de emparceiramento com layout limpo e, depois, QR.
- CSV/Excel de classificacao com desempates detalhados.

### Alto impacto / media complexidade

- Snapshots de emparceiramento.
- Componentes de desempate.
- Painel do arbitro.
- QR Code de resultado com fila de aprovacao.
- API local FastAPI.
- Portal local responsivo.

### Alto impacto / alta complexidade

- Motor de explicacao de pareamento.
- Equipes com reservas e escalacao por rodada.
- Sincronizacao multi-dispositivo.
- Permissoes completas por perfil.
- TRF25/TRF2026.

### Baixa prioridade inicial

- Integracao com relogios.
- App nativo Android/iOS.
- Submissao automatica para federacao.
- CRDT completo.
- IA para arbitragem.

## Primeiras sprints recomendadas

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
