# Manual Operacional de Arbitragem

Guia de campo do Albericus para torneios presenciais.

Versao: 2026-05-31

## 1. Regra de autoridade

O desktop com o banco SQLite local e a fonte oficial do torneio.

QR, portal live, sincronizacao, relogios e notificacoes sao auxiliares. Eles
podem receber envios ou registrar alertas, mas nao fecham rodada, nao definem
WO e nao alteram resultado automaticamente.

## 2. Preparacao antes do torneio

### 2.1 Configuracao

- [ ] Abrir `Torneios` e selecionar o torneio correto.
- [ ] Conferir nome, local, datas, ritmo, numero de rodadas e formato.
- [ ] Abrir `Config. Torneio` e revisar perfil, ordenacao inicial e dados
      oficiais.
- [ ] Em torneios por equipes, revisar numero de tabuleiros, criterios MP/GP e
      ordem fixa quando aplicavel.
- [ ] Abrir `Config. app` e confirmar a pasta de backups.
- [ ] Clicar em `Criar backup agora`.

### 2.2 Inscritos

- [ ] Abrir `Jogadores`.
- [ ] Importar inscritos por CSV/XLS/XLSX, link Forms/Sheets, membros locais ou
      cadastro manual.
- [ ] Importar listas oficiais FIDE, CBX ou LBX quando aplicavel.
- [ ] Clicar em `Comparar ratings oficiais`.
- [ ] Conferir divergencias e jogadores sem correspondencia.
- [ ] Remover da selecao divergencias que exigem tratamento manual.
- [ ] Clicar em `Confirmar alteracoes` somente depois da revisao.
- [ ] Exportar a lista de chamada em PDF como contingencia.

O piloto automatizado importa uma base FIDE local, compara 801 inscritos sem
persistir dados e confirma seletivamente 700 divergencias antes da rodada 1.
Repita a revisao visual com o operador responsavel antes do evento.

### 2.3 Validacao federativa

- [ ] Abrir `Exportar`.
- [ ] Clicar em `Validar TRF FIDE`.
- [ ] Corrigir bloqueios estruturais antes da primeira rodada.
- [ ] Revisar avisos de dados oficiais incompletos.
- [ ] Gerar `Pendencias TRF` quando precisar distribuir a conferencia.

### 2.4 Contingencia

- [ ] Confirmar carregador e energia do computador principal.
- [ ] Manter um segundo computador apto a restaurar backup.
- [ ] Repetir a restauracao no computador fisico reserva antes do evento.
- [ ] Desligar a internet e confirmar painel, lancamentos e fechamento locais.
- [ ] Separar impressora, papel e acesso aos PDFs exportados.
- [ ] Definir quem pode operar resultados, correcoes e publicacao.
- [ ] Testar QR e portal live na rede local antes de divulgar links.

O piloto automatizado bloqueia conexoes externas e valida a continuidade local
em instalacao isolada. Ele tambem simula 20 envios QR concorrentes e a
aprovacao pela fila do arbitro. Repita o ensaio fisico porque energia,
impressora e rede local do evento nao sao reproduzidas pelo simulador.

## 3. Inicio do evento

- [ ] Abrir `Rodadas`.
- [ ] Realizar a chamada inicial.
- [ ] Marcar ausentes antes de gerar a primeira rodada.
- [ ] Conferir o resumo de presentes e ausentes.
- [ ] Usar `Pre-visualizar proxima rodada`.
- [ ] Revisar alertas de bye, repeticao, cor e float.
- [ ] Confirmar a geracao da rodada.
- [ ] Exportar ou imprimir o mural PDF.
- [ ] Exportar sumulas e cartoes de mesa quando utilizados.
- [ ] Publicar portal live ou site HTML quando utilizado.

## 4. Operacao durante cada rodada

### 4.1 Painel do arbitro

- [ ] Abrir `Painel do arbitro`.
- [ ] Ajustar auto-refresh, intervalo e quantidade de mesas inline.
- [ ] Conferir mesas pendentes, byes, ausentes, correcoes e tempo de rodada.
- [ ] Para localizar uma mesa fora da lista inicial, preencher `Buscar mesa`.
- [ ] Lancar resultados inline por botoes ou atalhos.
- [ ] Confirmar que a selecao avanca para a proxima mesa pendente.

Atalhos inline:

| Tecla | Resultado |
|---|---|
| `1` | `1-0` |
| `-` | `1/2-1/2` |
| `0` | `0-1` |
| `Backspace` ou `Delete` | limpar |

### 4.2 Pendencias

- [ ] Abrir `Central de pendencias`.
- [ ] Usar filtros `Todas`, `Decisao`, `QR`, `Sync` e `Relogio`.
- [ ] Pesquisar pela mesa quando a fila estiver extensa.
- [ ] Aprovar ou rejeitar cada envio QR.
- [ ] Tratar eventos de relogio como alertas para decisao humana.
- [ ] Conferir pendencias de sincronizacao quando a camada opcional estiver
      ativa.

### 4.3 Inscricao de ultima hora

- [ ] Abrir `Jogadores` e cadastrar ou importar o novo inscrito.
- [ ] Conferir status ativo e pontos por adesao tardia quando configurados.
- [ ] Nao alterar emparceiramentos de rodadas ja fechadas.
- [ ] Confirmar que o jogador aparece na classificacao e na previa seguinte.

### 4.4 Fechamento da rodada

- [ ] Confirmar que nao existem mesas pendentes.
- [ ] Resolver envios QR aguardando revisao.
- [ ] Conferir resultados atipicos: WO, dupla ausencia e bye.
- [ ] Fechar a rodada.
- [ ] Confirmar o snapshot de classificacao e a auditoria.
- [ ] Gerar a proxima rodada somente depois do fechamento.

## 5. Correcoes

- [ ] Evitar editar diretamente o banco SQLite.
- [ ] Para corrigir rodada aberta, alterar o resultado pela interface normal.
- [ ] Para corrigir rodada fechada, habilitar explicitamente mudancas
      perigosas.
- [ ] Registrar o motivo solicitado pela interface.
- [ ] Conferir auditoria e classificacao depois da correcao.
- [ ] Republicar mural, portal ou site quando a correcao afetar informacao
      divulgada.

## 6. Encerramento do torneio

- [ ] Conferir classificacao final.
- [ ] Conferir tabela cruzada e desempates.
- [ ] Exportar classificacao, tabela cruzada e relatorio completo.
- [ ] Exportar `Taxas de rating` em XLSX ou PDF quando aplicavel.
- [ ] Gerar `Pendencias TRF`.
- [ ] Corrigir bloqueios federativos.
- [ ] Gerar `Chess-Results (TRF16)` quando aplicavel.
- [ ] Exportar site HTML ou JSON publico quando aplicavel.
- [ ] Conferir o relatorio de auditoria.
- [ ] Clicar em `Criar backup agora`.
- [ ] Arquivar backup final e exportacoes na pasta do evento.

## 7. Checklist rapido por rodada

Use esta secao impressa durante o evento.

| Rodada | Chamada / ausencias | Previa revisada | Mural publicado | Pendencias resolvidas | Rodada fechada | Backup extra |
|---|---|---|---|---|---|---|
| 1 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 2 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 7 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 8 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 9 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 10 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 11 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 12 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

## 8. Registro de incidentes

| Horario | Rodada / mesa | Tipo | Decisao do arbitro | Operador |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## 9. Limites conhecidos

- Aceleracao Baku continua desabilitada enquanto nao houver formula aplicavel
  publicada.
- O envio federativo e manual enquanto nao houver API publica utilizavel.
- Eventos de relogio nao definem resultado automaticamente.
- QR de resultado por tabuleiro de equipes ainda nao e tratado.
- Plugins de hardware dependem da definicao de equipamento alvo.
