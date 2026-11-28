# Albericus — hotfix da Revisão Geral 2 (Fase 0)

> Rascunho para revisão do árbitro (F0.9). Datado de 2026-11-27.

## O que muda na mesa de arbitragem

- **Enter lança o resultado em uma mesa só.** Na tela Rodadas, Enter lançava o resultado na mesa selecionada **e** na seguinte; com W.O., a confirmação aparecia duas vezes (RG2-02).
- **O painel do árbitro não troca mais a mesa por baixo de você.** A atualização automática (a cada 15 s) voltava a seleção para a primeira mesa e levava o cursor para a tabela: o "1" seguinte lançava 1-0 na mesa errada, até se você estivesse digitando na busca. Agora a mesa selecionada, o texto da busca e o cursor ficam onde estavam, e a atualização espera enquanto houver uma janela aberta ou o cursor estiver num campo (RG2-03).
- **O entrante tardio não aparece mais em 1º lugar.** Quem entra depois ficava na frente de todos na classificação ao vivo, impressa e publicada. Agora ele fica depois dos jogadores com a mesma pontuação e, até a rodada dele começar, aparece na tela numa seção à parte: "Entram na rodada N" (RG2-06).
- **Resposta incompleta do motor FIDE vira aviso.** Se o desempate do Gacrux vier incompleto, a classificação é calculada pelo motor próprio e a faixa da classificação avisa, como em qualquer falha do motor (RG2-06).
- **Suíço por equipes: nenhuma rodada com confronto repetido ou segundo bye é gravada.** O motor de equipes às vezes repetia um confronto que podia ser evitado. Agora a geração para, diz qual confronto se repetiria e registra o caso na auditoria. A prévia continua mostrando o alerta "Confronto repetido" (RG2-07a).
- **Bye solicitado já aplicado não pode mais ser apagado.** Excluir o bye depois de gerar a rodada zerava o saldo do jogador, sem rastro. Agora o programa recusa e explica o que fazer. Antes de a rodada ser gerada, a exclusão pede o motivo e fica na auditoria (RG2-05).

## O que muda nos backups e nos arquivos

- **A limpeza de backups só apaga backups do Albericus.** Com a pasta de backups igual à pasta do banco, fechar o programa podia apagar o próprio banco de trabalho. Agora a limpeza nunca toca no banco nem em arquivos com outro nome, e a tela de Configurações recusa essa pasta (RG2-01).
- **O retrato de antes de uma atualização do programa não some mais.** Os backups de segurança (antes de atualizar o banco, de restaurar ou de corrigir datas) têm uma cota própria de 3 e não entram na contagem de "manter últimos backups" (RG2-01).
- **Fechar o programa como árbitro também faz backup.** Antes, o backup de fechamento exigia permissão de administrador (RG2-44).
- **Importar a lista FIDE substitui a anterior.** Cada importação somava uma cópia inteira da lista ao banco; o banco e cada backup cresciam cerca de 90 MB a cada importação da lista FIDE. Agora fica só a lista mais recente de cada fonte (FIDE, CBX, LBX), e o banco é compactado depois da troca. A compactação pode levar alguns segundos (RG2-31).
- **Planilhas exportadas não executam fórmula.** Um nome vindo do formulário como `=HYPERLINK(...)` virava fórmula no Excel. Agora, no Excel, a célula fica como texto, sem mudar o que está escrito; no CSV, o texto ganha um `'` na frente, que o Albericus retira ao importar de volta. Telefones como `+55 11 …` continuam iguais (RG2-20).

## O que ainda não muda

- O motor de equipes ainda não encontra sozinho a alternativa sem repetição: ele recusa a rodada, mas o redesenho do motor vem numa versão seguinte (RG2-07b).
- A contagem regressiva "atualiza em N s" no painel do árbitro fica para a Fase 5 (RG2-36).

## Pedido ao árbitro

1. Confira, numa rodada de teste, o Enter na tela Rodadas e o painel do árbitro aberto por mais de 15 segundos com uma mesa do meio selecionada.
2. Se usar torneio por equipes, avise se aparecer a mensagem de confronto repetido: o caso fica na auditoria, e ele ajuda a calibrar o redesenho do motor.
