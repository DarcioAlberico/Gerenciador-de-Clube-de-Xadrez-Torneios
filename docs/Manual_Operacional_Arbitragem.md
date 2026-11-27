# Manual Operacional de Arbitragem

Guia de campo do Albericus para torneios presenciais.

Versão: 2026-05-31

## 1. Regra de autoridade

O desktop com o banco SQLite local e a fonte oficial do torneio.

QR, portal live, sincronização, relógios e notificações são auxiliares. Eles
podem receber envios ou registrar alertas, mas não fecham rodada, não definem
WO e não alteram resultado automaticamente.

## 2. Preparação antes do torneio

### 2.1 Configuração

- [ ] Abrir `Torneios` e selecionar o torneio correto.
- [ ] Conferir nome, local, datas, ritmo, número de rodadas e formato.
- [ ] Abrir `Config. Torneio` e revisar perfil, ordenação inicial e dados
      oficiais.
- [ ] Em torneios por equipes, revisar número de tabuleiros, critérios MP/GP e
      ordem fixa quando aplicável.
- [ ] Abrir `Config. app` e confirmar a pasta de backups.
- [ ] Clicar em `Criar backup agora`.

### 2.2 Inscritos

- [ ] Abrir `Jogadores`.
- [ ] Importar inscritos por CSV/XLS/XLSX, link Forms/Sheets, membros locais ou
      cadastro manual.
- [ ] Importar listas oficiais FIDE, CBX ou LBX quando aplicável.
- [ ] Clicar em `Comparar ratings oficiais`.
- [ ] Conferir divergências e jogadores sem correspondência.
- [ ] Remover da seleção divergências que exigem tratamento manual.
- [ ] Clicar em `Confirmar alteracoes` somente depois da revisão.
- [ ] Exportar a lista de chamada em PDF como contingência.

O piloto automatizado importa uma base FIDE local, compara 801 inscritos sem
persistir dados e confirma seletivamente 700 divergências antes da rodada 1.
Repita a revisão visual com o operador responsável antes do evento.

### 2.3 Validação federativa

- [ ] Abrir `Exportar`.
- [ ] Clicar em `Validar TRF FIDE`.
- [ ] Corrigir bloqueios estruturais antes da primeira rodada.
- [ ] Revisar avisos de dados oficiais incompletos.
- [ ] Gerar `Pendencias TRF` quando precisar distribuir a conferência.

### 2.4 Contingência

- [ ] Confirmar carregador e energia do computador principal.
- [ ] Manter um segundo computador apto a restaurar backup.
- [ ] Repetir a restauração no computador físico reserva antes do evento.
- [ ] Desligar a internet e confirmar painel, lançamentos e fechamento locais.
- [ ] Separar impressora, papel e acesso aos PDFs exportados.
- [ ] Definir quem pode operar resultados, correções e publicação.
- [ ] Testar QR e portal live na rede local antes de divulgar links.

O piloto automatizado bloqueia conexões externas e valida a continuidade local
em instalação isolada. Ele também simula 20 envios QR concorrentes e a
aprovação pela fila do árbitro. Repita o ensaio físico porque energia,
impressora e rede local do evento não são reproduzidas pelo simulador.

## 3. Início do evento

- [ ] Abrir `Rodadas`.
- [ ] Realizar a chamada inicial.
- [ ] Marcar ausentes antes de gerar a primeira rodada.
- [ ] Conferir o resumo de presentes e ausentes.
- [ ] Usar `Pre-visualizar proxima rodada`.
- [ ] Revisar alertas de bye, repetição, cor e float.
- [ ] Confirmar a geração da rodada.
- [ ] Exportar ou imprimir o mural PDF.
- [ ] Exportar súmulas e cartões de mesa quando utilizados.
- [ ] Publicar portal live ou site HTML quando utilizado.

## 4. Operação durante cada rodada

### 4.1 Painel do árbitro

- [ ] Abrir `Painel do arbitro`.
- [ ] Ajustar auto-refresh, intervalo e quantidade de mesas inline.
- [ ] Conferir mesas pendentes, byes, ausentes, correções e tempo de rodada.
- [ ] Para localizar uma mesa fora da lista inicial, preencher `Buscar mesa`.
- [ ] Lançar resultados inline por botões ou atalhos.
- [ ] Confirmar que a seleção avança para a próxima mesa pendente.

Atalhos inline:

| Tecla | Resultado |
|---|---|
| `1` | `1-0` |
| `-` | `1/2-1/2` |
| `0` | `0-1` |
| `Backspace` ou `Delete` | limpar |

### 4.2 Pendências

- [ ] Abrir `Central de pendencias`.
- [ ] Usar filtros `Todas`, `Decisao`, `QR`, `Sync` e `Relogio`.
- [ ] Pesquisar pela mesa quando a fila estiver extensa.
- [ ] Aprovar ou rejeitar cada envio QR.
- [ ] Tratar eventos de relógio como alertas para decisão humana.
- [ ] Conferir pendências de sincronização quando a camada opcional estiver
      ativa.

### 4.3 Inscrição de última hora

- [ ] Abrir `Jogadores` e cadastrar ou importar o novo inscrito.
- [ ] Conferir status ativo e pontos por adesão tardia quando configurados.
- [ ] Não alterar emparceiramentos de rodadas já fechadas.
- [ ] Confirmar que o jogador aparece na classificação e na prévia seguinte.

### 4.4 Fechamento da rodada

- [ ] Confirmar que não existem mesas pendentes.
- [ ] Resolver envios QR aguardando revisão.
- [ ] Conferir resultados atípicos: WO, dupla ausência e bye.
- [ ] Fechar a rodada.
- [ ] Confirmar o snapshot de classificação e a auditoria.
- [ ] Gerar a próxima rodada somente depois do fechamento.

## 5. Correções

- [ ] Evitar editar diretamente o banco SQLite.
- [ ] Para corrigir rodada aberta, alterar o resultado pela interface normal.
- [ ] Para corrigir rodada fechada, habilitar explicitamente mudanças
      perigosas.
- [ ] Registrar o motivo solicitado pela interface.
- [ ] Conferir auditoria e classificação depois da correção.
- [ ] Republicar mural, portal ou site quando a correção afetar informação
      divulgada.

## 6. Encerramento do torneio

- [ ] Conferir classificação final.
- [ ] Conferir tabela cruzada e desempates.
- [ ] Exportar classificação, tabela cruzada e relatório completo.
- [ ] Exportar `Taxas de rating` em XLSX ou PDF quando aplicável.
- [ ] Gerar `Pendencias TRF`.
- [ ] Corrigir bloqueios federativos.
- [ ] Gerar `Chess-Results (TRF16)` quando aplicável.
- [ ] Exportar site HTML ou JSON público quando aplicável.
- [ ] Conferir o relatório de auditoria.
- [ ] Clicar em `Criar backup agora`.
- [ ] Arquivar backup final e exportações na pasta do evento.

## 7. Checklist rápido por rodada

Use esta seção impressa durante o evento.

| Rodada | Chamada / ausências | Prévia revisada | Mural publicado | Pendências resolvidas | Rodada fechada | Backup extra |
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

| Horário | Rodada / mesa | Tipo | Decisão do árbitro | Operador |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## 9. Limites conhecidos

- Aceleração de Baku (FIDE C.04.7) vale só para torneio individual com
  pontuação padrão; no torneio por equipes ela ainda não é aplicada.
- O envio federativo e manual enquanto não houver API pública utilizável.
- Eventos de relógio não definem resultado automaticamente.
- QR de resultado por tabuleiro de equipes ainda não é tratado.
- Plugins de hardware dependem da definição de equipamento alvo.
