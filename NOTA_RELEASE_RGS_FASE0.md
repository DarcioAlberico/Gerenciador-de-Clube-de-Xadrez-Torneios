# Albericus — correção do executável (Revisão Geral Suíço, Fase 0)

> Rascunho para revisão do árbitro (F0.9). Datado de 2026-11-26.

## O que muda

- **O motor FIDE (Gacrux) agora roda dentro do executável.** No `.exe` de 11/11 ele não era encontrado: o pareamento padrão falhava e o desempate caía no motor próprio (RGS-01).
- **Os textos da tela voltaram.** Barra lateral, cadastro de jogadores e botões como "Cancelar" mostravam códigos (`nav.group.tournament`...) em vez dos rótulos (RGS-02).
- **Erro inesperado agora aparece e fica no log.** Antes, uma falha num clique podia não mostrar nada, e o programa parecia "parar" (RGS-04).
- **Bye de 0 ou 0,5 ponto e ajuste manual de pontos:** o motor FIDE contava esses pontos errado e podia parear com outro placar ou travar a geração. Agora a rodada é recusada com uma mensagem clara, e você pode parear essa rodada com o **motor reserva**, que não é homologado pela FIDE. A escolha fica na auditoria do torneio (RGS-03).
- **O executável se testa antes de ser distribuído:** textos, banco, 3 rodadas e o desempate pelo Gacrux, mais um PDF e um TRF (RGS-05).

## Até a próxima versão (contorno)

- **Para corrigir um resultado errado**, use a tela **Rodadas**: ela libera a rodada na hora, com o motivo. **Evite "mudanças perigosas"** nas Configurações.
- **Se uma data aparecer estranha** (por exemplo `20/26/1113`), digite-a de novo antes de salvar as Configurações.
- **Se o regulamento permitir, use bye de 1 ponto.** Bye de 0 ou 0,5 ponto e ajuste manual de pontos levam ao motor reserva até a versão que corrige o motor FIDE para esses casos.

## Pedido ao árbitro

Para fechar a investigação do incidente de 11/11, envie, se puder:

1. o arquivo `app.log` (em `%LOCALAPPDATA%\Albericus\logs`);
2. o arquivo `.db` do torneio, ou um backup dele;
3. a versão do executável que você usou (aparece no título da janela).
