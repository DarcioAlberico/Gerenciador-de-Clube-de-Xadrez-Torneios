# Albericus — Revisão Geral Suíço, Fases 1 a 4

> Rascunho para revisão do árbitro. Datado de 2026-11-26. Substitui o "contorno" da `NOTA_RELEASE_RGS_FASE0.md`.

## Datas e gravações seguras (Fase 1)

- **Nenhuma data muda sem ser digitada.** Uma data inválida é recusada no campo, com a explicação, e o formulário não salva (RGS-06, RGS-33, RGS-07).
- **Datas antigas estranhas** aparecem na tela inicial como "N datas a revisar". As que dão para converter são normalizadas, depois de um backup (RGS-06).
- **Salvar as Configurações, fechar a rodada, corrigir um resultado e importar TRF gravam tudo ou nada.** Uma falha no meio não deixa o torneio pela metade (RGS-08, RGS-09, RGS-11).
- **Corrigir um resultado de rodada fechada recalcula os retratos de classificação** das rodadas seguintes (RGS-10).
- **O calendário não trava a tela** (abre com F4, Alt+↓ ou ▾). O jogador **ausente volta a concorrer a prêmio**; só desistente e expulso ficam de fora (RGS-12, RGS-35).

## Árbitro prático (Fase 2)

- **Erro de regra aparece numa faixa fixa**, com a ação sugerida (RGS-26).
- **"Corrigir resultado…"**: clique direito, Shift+F10 ou Ctrl+E na mesa. Pede um motivo e mostra a cascata nas rodadas seguintes, com "Reparear" e "Reverter esta correção…". As "mudanças perigosas" foram para a aba **Avançado** (RGS-20).
- **Excluir rodada com resultados** exige motivo e guarda os resultados na auditoria (RGS-34).
- **Lançamento mais rápido:** "Desfazer (Ctrl+Z)", o contador "N/M lançadas" e W.O. pelas teclas `w`, `p` e `a`. O botão principal acompanha a rodada: Lançar → Fechar → Gerar a próxima (RGS-21, RGS-25).
- **Menu na linha do jogador** (clique direito ou Shift+F10): "Faltar só à rodada N…", "Bye na próxima rodada…" com o saldo de byes, "Retirar do torneio…" e "Reintegrar…" (RGS-22, RGS-23).
- **Seletores de jogador com busca** em byes, ajustes e proibições: digite parte do nome e tecle Enter (RGS-23).

## Conformidade FIDE (Fase 3)

- **Bye de 0 ou 0,5 ponto e ajuste manual de pontos agora saem pelo motor FIDE (Gacrux).** O motor reserva não é mais necessário nesses casos (RGS-03).
- **Desempate de seeding** por rating, depois título, depois ordem alfabética (C.04.2) (RGS-13).
- **Proibições de confronto continuam no Gacrux** (RGS-15). A saída do motor é conferida, e cada rodada gerada passa por uma verificação independente (RGS-19, RGS-16).
- **Ajuste manual de emparceiramento exige motivo** e fica na auditoria (RGS-16).
- **Fim do falso aviso de "bye repetido"** (RGS-17).
- **Motor reserva:** só com confirmação, com o rótulo "motor reserva — não homologado FIDE". Ele não dá bye a quem venceu por W.O. e segue as regras de cor (RGS-18).
- **Cor inicial** da mesa 1 sorteada e gravada ao criar o torneio. Dá para mudar nas Configurações (RGS-14).
- **Entrada tardia** com assistente: ID FIDE/CBX, pontos por rodada perdida (0, ½ ou 1) e "entra na rodada N" (RGS-24).

## Polimento (Fase 4)

- **Textos com acento correto** e status da rodada em português ("Rodada 3 - encerrada") (RGS-27).
- **As Configurações do painel voltam a carregar depois de mudar a escala da tela** (RGS-28).
- **Atualizar o programa não deixa o banco pela metade:** cada versão do banco é migrada numa transação (RGS-29).
- **A atualização automática do painel não para mais sozinha** (RGS-31).
- **Falhas que antes sumiam caladas agora ficam no log** (RGS-32).

## Depois das fases

- **Aceleração de Baku** conforme o FIDE Handbook (C.04.7): o grupo de cima recebe pontos virtuais só para o emparceiramento, nunca na classificação. Vale para torneio individual com pontuação padrão (RGS-30).
- **Aceleração clássica corrigida:** o motor FIDE passou a receber os pontos virtuais das rodadas aceleradas anteriores, e não só da rodada que está sendo pareada.
- **Suíço por equipes:**
  - a ordem das equipes fica fixa durante o torneio;
  - uma equipe sem um titular entra com a reserva, e o tabuleiro vazio vira W.O.;
  - equipe sem ninguém presente: o programa pergunta se confirma o W.O. do confronto;
  - confronto perdido por W.O. não conta como jogado;
  - quem venceu por W.O. não recebe o bye.
  - bye solicitado de meio ponto ou zero não impede mais a equipe de receber o bye alocado;
  - equipe inscrita depois da R1 num todos-contra-todos fica fora do calendário, com aviso;
  - "Trocar TPN" na tela de Equipes, com motivo, só entre rodadas;
  - aceleração de Baku por equipes, com match points (2 por vitória), declarada também no TRF25. A aceleração clássica em equipes avisa que não se aplica.
- **Trocar as cores de uma mesa** pede motivo e fica na auditoria.
- **Ctrl+Z** funciona em qualquer lugar da tela de Rodadas. Digitar numa caixa de texto não lança nem apaga resultado.
- **"Fechar rodada" no painel** pede a mesma confirmação da tela de Rodadas. Pelo **Checklist** do painel, é um passo só: ele diz o que fechar faz e não pergunta de novo.
- **O TRF** traz a cor inicial antes da R1. No retrato de uma rodada antiga, deixa de fora quem entrou depois e mostra os pontos e a posição daquela rodada.
- **Mais textos com acento:** avisos do TRF, mensagens do motor FIDE, do registro de incidentes e das fórmulas de desempate. Os níveis de aprendizado ("Básico", "Intermediário", "Avançado") e os modelos de certificado padrão também, inclusive num banco antigo, desde que o texto não tenha sido editado (o editado fica como está).

## Ainda depende do árbitro

1. Os arquivos do incidente de 11/11 (`app.log`, o `.db` e a versão do executável) para o replay e para conferir as datas antigas (F0.6).
2. Uma sessão de teste das tarefas da Fase 2, sem instrução (F2.8).
3. Confirmar se o regulamento usual deixa o jogador **ausente** na última rodada concorrer a prêmio (D5).
