# Passo a passo detalhado: programa de emparceiramento de xadrez

## Atualizacao do roadmap do Albericus

O escopo do Albericus foi ampliado alem do emparceiramento inicial. O programa
agora tambem funciona como gerenciador de clube, escola ou turma de xadrez,
com cadastro de membros/alunos, unidades, turmas, aulas, exercicios,
inventario, eventos, relatorios, ranking interno, backups e gerador de
diplomas/certificados.

As proximas melhorias devem seguir este roteiro incremental:

1. Consulta local/publica de diplomas: exportar uma pagina HTML com busca por
   codigo, nome, origem e status ativo/revogado.
2. Area pedagogica: planos de aula, metas por turma, evolucao por nivel e
   observacoes do professor.
3. Mensalidades e financeiro: planos recorrentes, vencimentos, pagamentos,
   pendencias e recibos simples.
4. Ranking interno avancado: temporadas, categorias configuraveis, historico de
   campeoes e filtros por clube/turma.
5. Comunicacao e portal: pagina HTML do clube/turma, avisos, calendario e
   comunicados para responsaveis.
6. Biblioteca de exercicios: temas taticos, niveis, listas de treino e
   desempenho por aluno.
7. Inventario: pecas, tabuleiros, relogios, livros, emprestimos e manutencoes.
8. Seguranca operacional: perfis de acesso, auditoria de alteracoes e politicas
   de backup.

Status da primeira etapa: implementada a exportacao de um verificador HTML
local de diplomas/certificados a partir do historico de codigos emitidos.

Status da segunda etapa: implementados campos pedagogicos nas aulas/treinos
para nivel alvo, objetivo, conteudo e tarefa, com migracao automatica dos
bancos antigos e inclusao desses dados no relatorio de presencas.

Status da terceira etapa: implementada geracao em lote de mensalidades por
plano, referencia e vencimento, com prevencao de duplicidade, alem de recibos
simples para lancamentos pagos ou isentos.

Status da quarta etapa: o ranking interno ganhou filtros por clube/escola,
turma e periodo de temporada, com relatorios que respeitam esses filtros e
mantem lideres por categoria.

Status da quinta etapa: implementado portal HTML estatico para clube/escola ou
turma, reunindo comunicados, calendario, aulas futuras, ranking interno e
torneios recentes.

Status da sexta etapa: implementada biblioteca de exercicios com cadastro por
tema, nivel e dificuldade, listas de treino por clube/turma, vinculo da lista
com aulas e base de tentativas por aluno para historico de estudos.

Status da setima etapa: implementado inventario com cadastro de materiais,
emprestimos para membros, devolucao, manutencoes e calculo automatico de
disponibilidade.

Status da oitava etapa: implementada seguranca operacional inicial com perfil
local de operador, auditoria de backups/configuracoes/restauracoes, retencao
configuravel de backups e visualizacao da auditoria recente.

Este documento descreve como construir um programa desktop para gerenciar torneios de xadrez, fazer emparceiramentos, registrar resultados, calcular classificação e exportar dados. A proposta usa Python, CustomTkinter para a interface gráfica, SQLite como banco de dados local e módulos de exportação para CSV, Excel e PDF.

## 1. Objetivo do sistema

Criar um aplicativo que permita:

- Cadastrar torneios.
- Cadastrar jogadores.
- Importar lista de jogadores.
- Gerar emparceiramentos por rodada.
- Registrar resultados.
- Controlar cores, byes, confrontos repetidos e pontuação.
- Exibir classificação atualizada.
- Exportar emparceiramentos, resultados e classificação.
- Salvar tudo em banco de dados local.

O formato principal recomendado para começar é o Sistema Suíço, pois é o mais comum em torneios escolares, clubes, eventos rápidos e torneios abertos.

## 2. Tecnologias recomendadas

### 2.1 Linguagem

- Python 3.11 ou superior.

### 2.2 Interface gráfica

- `customtkinter`: interface moderna baseada em Tkinter.
- `tkinter.filedialog`: seleção de arquivos para importar/exportar.
- `tkinter.messagebox`: mensagens de confirmação e erro.

### 2.3 Banco de dados

- SQLite no MVP.
- Pode usar `sqlite3` nativo do Python.
- Se o projeto crescer, pode migrar para SQLAlchemy.

### 2.4 Exportação

- CSV: módulo nativo `csv`.
- Excel: `openpyxl`.
- PDF: `reportlab`.

### 2.5 Bibliotecas opcionais

- `pandas`: útil para importar/exportar planilhas.
- `python-chess`: útil se o sistema futuramente registrar partidas em PGN, tabuleiros ou validação de lances.

## 3. Instalação inicial

Crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente no Windows:

```bash
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install customtkinter openpyxl reportlab pandas
```

Crie um arquivo `requirements.txt`:

```txt
customtkinter
openpyxl
reportlab
pandas
```

## 4. Estrutura sugerida do projeto

```txt
albericus/
  app.py
  requirements.txt
  README.md
  data/
    albericus.db
  src/
    database/
      connection.py
      schema.py
      repositories.py
    models/
      tournament.py
      player.py
      round.py
      pairing.py
      result.py
    services/
      pairing_service.py
      standings_service.py
      export_service.py
      import_service.py
    ui/
      main_window.py
      tournament_screen.py
      players_screen.py
      pairings_screen.py
      standings_screen.py
      settings_screen.py
    utils/
      validators.py
      constants.py
      paths.py
```

## 5. Funcionalidades do MVP

O MVP deve entregar o fluxo completo de um torneio simples.

### 5.1 Cadastro de torneio

Campos sugeridos:

- Nome do torneio.
- Local.
- Data inicial.
- Data final.
- Sistema de disputa: Suíço.
- Número de rodadas.
- Ritmo de jogo.
- Critérios de desempate.
- Observações.

### 5.2 Cadastro de jogadores

Campos sugeridos:

- Nome completo.
- Clube ou cidade.
- Federação, se houver.
- ID nacional/FIDE, se houver.
- Rating.
- Categoria.
- Data de nascimento.
- Status: ativo, desistente, ausente.

### 5.3 Emparceiramento

O sistema deve:

- Gerar a primeira rodada.
- Gerar rodadas seguintes com base na pontuação.
- Evitar repetição de adversários.
- Alternar cores sempre que possível.
- Controlar bye.
- Permitir ajustes manuais antes de confirmar a rodada.

### 5.4 Resultados

Resultados básicos:

- 1-0
- 0-1
- 1/2-1/2
- 1F-0F por WO
- 0F-1F por WO
- 0F-0F dupla ausência
- Bye

### 5.5 Classificação

Exibir:

- Posição.
- Jogador.
- Pontos.
- Rating.
- Clube.
- Vitórias.
- Buchholz.
- Sonneborn-Berger.
- Confronto direto, se implementado.
- Número de pretas, se usado como desempate.

### 5.6 Exportação

Exportar:

- Lista de jogadores.
- Emparceiramento da rodada.
- Resultados da rodada.
- Classificação geral.
- Relatório completo do torneio.

Formatos:

- `.csv`
- `.xlsx`
- `.pdf`

## 6. Modelo de banco de dados

Use SQLite para manter o sistema simples, portátil e fácil de empacotar.

### 6.1 Tabela `tournaments`

| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Identificador do torneio |
| name | TEXT | Nome do torneio |
| location | TEXT | Local |
| start_date | TEXT | Data inicial |
| end_date | TEXT | Data final |
| system | TEXT | Sistema de disputa |
| rounds_count | INTEGER | Número de rodadas |
| time_control | TEXT | Ritmo de jogo |
| status | TEXT | draft, running, finished |
| created_at | TEXT | Data de criação |

### 6.2 Tabela `players`

| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Identificador do jogador |
| tournament_id | INTEGER FK | Torneio |
| name | TEXT | Nome |
| club | TEXT | Clube/cidade |
| federation_id | TEXT | ID da federação |
| fide_id | TEXT | ID FIDE |
| rating | INTEGER | Rating |
| category | TEXT | Categoria |
| birth_date | TEXT | Data de nascimento |
| active | INTEGER | 1 ativo, 0 inativo |

### 6.3 Tabela `rounds`

| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Identificador da rodada |
| tournament_id | INTEGER FK | Torneio |
| number | INTEGER | Número da rodada |
| status | TEXT | generated, confirmed, closed |
| created_at | TEXT | Data de geração |

### 6.4 Tabela `pairings`

| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Identificador do emparceiramento |
| round_id | INTEGER FK | Rodada |
| board_number | INTEGER | Mesa |
| white_player_id | INTEGER FK | Jogador das brancas |
| black_player_id | INTEGER FK | Jogador das pretas |
| result | TEXT | Resultado |
| is_bye | INTEGER | 1 se for bye |

### 6.5 Tabela `player_round_stats`

| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Identificador |
| tournament_id | INTEGER FK | Torneio |
| round_number | INTEGER | Rodada |
| player_id | INTEGER FK | Jogador |
| opponent_id | INTEGER FK | Adversário |
| color | TEXT | W, B, BYE |
| points | REAL | Pontos na rodada |
| result | TEXT | Resultado |

Essa tabela facilita cálculo de classificação, histórico de cores, adversários e desempates.

## 7. Regras de pontuação

Pontuação padrão:

| Resultado | Brancas | Pretas |
|---|---:|---:|
| 1-0 | 1.0 | 0.0 |
| 0-1 | 0.0 | 1.0 |
| 1/2-1/2 | 0.5 | 0.5 |
| 1F-0F | 1.0 | 0.0 |
| 0F-1F | 0.0 | 1.0 |
| 0F-0F | 0.0 | 0.0 |
| BYE | 1.0 | - |

O sistema deve permitir configurar se o bye vale 1.0, 0.5 ou 0.0 ponto, dependendo do regulamento.

## 8. Lógica de emparceiramento suíço simplificado

O emparceiramento suíço completo da FIDE é complexo. Para um MVP robusto, implemente uma versão simplificada com regras claras.

### 8.1 Primeira rodada

Passos:

1. Ordenar jogadores por rating decrescente.
2. Se não houver rating, ordenar por nome ou número de inscrição.
3. Dividir a lista ao meio.
4. Emparceirar o primeiro da metade superior contra o primeiro da metade inferior.
5. Repetir para os demais.
6. Alternar cores por mesa.
7. Se houver número ímpar de jogadores, dar bye ao jogador de menor rating que ainda não tenha recebido bye.

Exemplo com 8 jogadores:

```txt
Lista ordenada:
1. Jogador A
2. Jogador B
3. Jogador C
4. Jogador D
5. Jogador E
6. Jogador F
7. Jogador G
8. Jogador H

Metade superior: A, B, C, D
Metade inferior: E, F, G, H

Mesa 1: A x E
Mesa 2: F x B
Mesa 3: C x G
Mesa 4: H x D
```

### 8.2 Rodadas seguintes

Passos:

1. Calcular a pontuação atual de todos os jogadores ativos.
2. Agrupar jogadores por pontuação.
3. Ordenar cada grupo por rating e número de inscrição.
4. Dentro de cada grupo, tentar emparceirar jogadores que ainda não se enfrentaram.
5. Se um jogador não encontrar adversário no grupo, ele desce para o próximo grupo.
6. Repetir até todos estarem emparceirados.
7. Se sobrar um jogador, atribuir bye conforme regra.
8. Definir cores equilibrando histórico.
9. Salvar a rodada como `generated`.
10. Permitir que o operador revise e confirme.

### 8.3 Restrições importantes

O algoritmo deve evitar:

- Jogadores se enfrentarem mais de uma vez.
- Jogador receber dois byes no mesmo torneio.
- Três brancas ou três pretas seguidas, sempre que possível.
- Diferença exagerada entre número de brancas e pretas.
- Jogador inativo ou desistente ser emparceirado.

### 8.4 Prioridade na escolha de adversário

Ao escolher adversários, use uma pontuação de penalidade:

| Situação | Penalidade |
|---|---:|
| Já se enfrentaram | Infinita |
| Mesma pontuação | 0 |
| Diferença de 0.5 ponto | 10 |
| Diferença de 1.0 ponto | 25 |
| Cores ruins para ambos | 15 |
| Um jogador ficaria com três cores iguais seguidas | 100 |
| Jogador já recebeu bye | Infinita para novo bye |

O par escolhido deve ser o de menor penalidade.

### 8.5 Pseudocódigo do emparceiramento

```txt
função gerar_emparceiramento(torneio, rodada):
    jogadores = buscar_jogadores_ativos(torneio)
    historico = buscar_historico(torneio)

    se quantidade_de_jogadores for ímpar:
        jogador_bye = escolher_bye(jogadores, historico)
        remover jogador_bye da lista
        criar emparceiramento de bye

    ordenar jogadores por:
        pontuação desc
        rating desc
        nome asc

    lista_pendente = jogadores
    mesas = []

    enquanto lista_pendente não estiver vazia:
        jogador = primeiro jogador pendente
        candidatos = demais jogadores pendentes

        melhor_adversario = candidato com menor penalidade

        se não existir adversário válido:
            aplicar troca com mesa anterior
            ou mover jogador para grupo inferior

        definir cores usando histórico
        criar mesa
        remover os dois jogadores da lista pendente

    salvar mesas no banco
```

## 9. Definição de cores

Para cada jogador, mantenha:

- Quantas vezes jogou de brancas.
- Quantas vezes jogou de pretas.
- Sequência recente de cores.
- Cor da última rodada.

Regra prática:

1. Se um jogador tem mais brancas que o outro, ele deve receber pretas.
2. Se um jogador jogou a última rodada de brancas, preferir pretas.
3. Evitar três cores iguais seguidas.
4. Na primeira rodada, alternar por mesa.
5. Se houver conflito, priorizar o jogador com pior desequilíbrio de cores.

## 10. Cálculo de classificação

### 10.1 Pontos

Somar os pontos de cada jogador em todas as rodadas fechadas.

### 10.2 Buchholz

Somar a pontuação final ou atual dos adversários enfrentados.

Exemplo:

```txt
Jogador A enfrentou B, C e D.
B tem 2.0 pontos.
C tem 1.5 ponto.
D tem 1.0 ponto.
Buchholz de A = 4.5
```

### 10.3 Buchholz mediano

Somar a pontuação dos adversários, removendo o melhor e o pior resultado quando houver rodadas suficientes.

### 10.4 Sonneborn-Berger

Somar:

- Pontuação total do adversário derrotado.
- Metade da pontuação total do adversário empatado.
- Zero contra adversário que venceu o jogador.

### 10.5 Ordem recomendada

Classificação sugerida:

1. Pontos.
2. Buchholz.
3. Buchholz mediano.
4. Sonneborn-Berger.
5. Vitórias.
6. Confronto direto.
7. Rating.
8. Nome.

## 11. Interface com CustomTkinter

### 11.1 Janela principal

Componentes:

- Menu lateral.
- Área central.
- Barra superior com nome do torneio ativo.
- Rodapé com status do banco e última ação.

Menu lateral:

- Torneios.
- Jogadores.
- Rodadas.
- Emparceiramento.
- Resultados.
- Classificação.
- Exportar.
- Configurações.

### 11.2 Tela de torneios

Elementos:

- Lista de torneios cadastrados.
- Botão novo torneio.
- Botão abrir torneio.
- Botão editar.
- Botão excluir.
- Filtro por status.

Campos do formulário:

- Nome.
- Local.
- Data inicial.
- Data final.
- Número de rodadas.
- Sistema.
- Ritmo de jogo.

### 11.3 Tela de jogadores

Elementos:

- Tabela com jogadores.
- Busca por nome.
- Filtro por clube/categoria.
- Botão adicionar.
- Botão editar.
- Botão remover.
- Botão importar.
- Botão marcar desistente.

Colunas:

- Nº.
- Nome.
- Rating.
- Clube.
- Categoria.
- Status.

### 11.4 Tela de emparceiramento

Elementos:

- Seleção da rodada.
- Botão gerar rodada.
- Botão confirmar rodada.
- Botão refazer rodada.
- Botão trocar cores.
- Botão trocar jogador.
- Tabela de mesas.

Colunas:

- Mesa.
- Brancas.
- Rating brancas.
- Resultado.
- Pretas.
- Rating pretas.

### 11.5 Tela de resultados

Elementos:

- Lista de mesas da rodada.
- Combobox de resultado por mesa.
- Botão salvar resultados.
- Botão fechar rodada.
- Destaque para resultados pendentes.

Validações:

- Não fechar rodada com resultado pendente.
- Não alterar resultado de rodada fechada sem confirmação.
- Atualizar classificação após fechar rodada.

### 11.6 Tela de classificação

Elementos:

- Tabela geral.
- Botão recalcular.
- Botão exportar.
- Filtro por categoria.

Colunas:

- Posição.
- Nome.
- Pontos.
- Buchholz.
- Buchholz mediano.
- Sonneborn-Berger.
- Vitórias.
- Rating.
- Clube.

### 11.7 Tela de exportação

Elementos:

- Tipo de relatório.
- Formato do arquivo.
- Caminho de destino.
- Botão exportar.

Relatórios:

- Lista de jogadores.
- Emparceiramento da rodada.
- Resultados.
- Classificação.
- Relatório completo.

## 12. Camadas do sistema

### 12.1 Camada de interface

Responsável por:

- Desenhar telas.
- Capturar cliques e entradas.
- Mostrar mensagens.
- Enviar comandos para os serviços.

Não deve conter regra complexa de emparceiramento.

### 12.2 Camada de serviços

Responsável por:

- Gerar emparceiramento.
- Calcular classificação.
- Validar regras de torneio.
- Importar e exportar arquivos.

### 12.3 Camada de banco

Responsável por:

- Criar tabelas.
- Inserir, atualizar, buscar e excluir registros.
- Controlar transações.

## 13. Fluxo completo do torneio

1. Usuário cria um torneio.
2. Usuário cadastra ou importa jogadores.
3. Sistema valida número mínimo de jogadores.
4. Usuário gera a primeira rodada.
5. Sistema cria mesas e salva no banco.
6. Usuário revisa o emparceiramento.
7. Usuário confirma a rodada.
8. Usuário registra os resultados.
9. Sistema valida resultados.
10. Usuário fecha a rodada.
11. Sistema atualiza histórico e classificação.
12. Usuário gera a próxima rodada.
13. Processo se repete até a última rodada.
14. Sistema marca torneio como finalizado.
15. Usuário exporta relatórios finais.

## 14. Importação de jogadores

### 14.1 Formato CSV recomendado

```csv
name,club,federation_id,fide_id,rating,category,birth_date
Ana Silva,Clube A,123,,1850,Sub-18,2008-04-10
Bruno Souza,Clube B,124,,1720,Absoluto,1998-11-03
```

### 14.2 Validações na importação

Verificar:

- Nome obrigatório.
- Rating numérico.
- Data em formato válido.
- Jogadores duplicados.
- Campos ausentes.

Ao encontrar erro:

- Mostrar linha com problema.
- Permitir continuar importação ignorando linhas inválidas.
- Gerar relatório de erros.

## 15. Exportações

### 15.1 CSV

Usar para arquivos simples e integração com outros sistemas.

Exemplos:

- `jogadores.csv`
- `rodada_01.csv`
- `classificacao.csv`

### 15.2 Excel

Usar para relatórios editáveis.

Abas recomendadas:

- Torneio.
- Jogadores.
- Rodadas.
- Resultados.
- Classificação.

### 15.3 PDF

Usar para impressão e divulgação.

Relatórios em PDF:

- Emparceiramento da rodada.
- Classificação final.
- Relatório completo.

Cada PDF deve conter:

- Nome do torneio.
- Local.
- Data.
- Rodada.
- Tabela principal.
- Data/hora de geração.

## 16. Validações essenciais

Antes de gerar rodada:

- Torneio existe.
- Há pelo menos 2 jogadores ativos.
- Rodada anterior está fechada.
- Número máximo de rodadas ainda não foi atingido.

Antes de fechar rodada:

- Todos os resultados foram preenchidos.
- Não há mesa duplicada.
- Não há jogador repetido na mesma rodada.
- Bye está correto.

Antes de exportar:

- Torneio selecionado.
- Há dados para o relatório escolhido.
- Caminho de destino é válido.

## 17. Tratamento de erros

Erros comuns:

- Banco de dados não encontrado.
- Arquivo CSV inválido.
- Tentativa de gerar rodada duplicada.
- Jogador sem nome.
- Resultado inválido.
- Falha ao salvar PDF.

Cada erro deve:

- Mostrar mensagem clara ao usuário.
- Registrar detalhe técnico em log.
- Não fechar o programa inesperadamente.

## 18. Logs

Criar arquivo:

```txt
logs/app.log
```

Registrar:

- Criação de torneio.
- Importações.
- Geração de rodada.
- Alteração manual de emparceiramento.
- Fechamento de rodada.
- Exportações.
- Erros.

## 19. Segurança dos dados

Recomendações:

- Fazer backup automático antes de fechar uma rodada.
- Confirmar exclusões.
- Não permitir excluir torneio em andamento sem confirmação forte.
- Criar cópia do banco em `backups/`.
- Usar transações ao gerar rodada e salvar resultados.

## 20. Testes recomendados

### 20.1 Testes do banco

- Criar torneio.
- Inserir jogador.
- Atualizar jogador.
- Remover jogador.
- Buscar torneio ativo.

### 20.2 Testes do emparceiramento

- Número par de jogadores.
- Número ímpar de jogadores.
- Jogador não recebe dois byes.
- Jogadores não se enfrentam duas vezes.
- Rodada seguinte respeita pontuação.
- Cores são equilibradas.

### 20.3 Testes de classificação

- Pontuação correta.
- Buchholz correto.
- Sonneborn-Berger correto.
- Ordenação correta.

### 20.4 Testes de exportação

- CSV gerado.
- Excel gerado.
- PDF gerado.
- Arquivos abrem sem erro.

## 21. Roadmap de implementação

### Etapa 1: Base do projeto

1. Criar estrutura de pastas.
2. Criar ambiente virtual.
3. Criar `requirements.txt`.
4. Criar tela principal vazia.
5. Configurar tema do CustomTkinter.

### Etapa 2: Banco de dados

1. Criar conexão SQLite.
2. Criar script de criação das tabelas.
3. Criar repositórios para torneios e jogadores.
4. Testar inserção e consulta.

### Etapa 3: Torneios

1. Criar tela de cadastro.
2. Criar listagem de torneios.
3. Permitir abrir torneio ativo.
4. Salvar edição no banco.

### Etapa 4: Jogadores

1. Criar formulário de jogador.
2. Criar tabela/lista de jogadores.
3. Criar busca.
4. Criar importação CSV.
5. Criar validações.

### Etapa 5: Primeira rodada

1. Implementar ordenação por rating.
2. Dividir jogadores em duas metades.
3. Criar mesas.
4. Atribuir cores.
5. Salvar rodada no banco.
6. Mostrar na tela.

### Etapa 6: Resultados

1. Criar seleção de resultado por mesa.
2. Salvar resultado no banco.
3. Criar histórico por jogador.
4. Fechar rodada.

### Etapa 7: Classificação

1. Calcular pontos.
2. Calcular vitórias.
3. Calcular Buchholz.
4. Calcular Sonneborn-Berger.
5. Exibir tabela ordenada.

### Etapa 8: Rodadas seguintes

1. Agrupar jogadores por pontuação.
2. Evitar confrontos repetidos.
3. Implementar escolha por menor penalidade.
4. Implementar controle de bye.
5. Implementar controle de cores.
6. Permitir ajuste manual.

### Etapa 9: Exportação

1. Exportar CSV.
2. Exportar Excel.
3. Exportar PDF.
4. Adicionar botões nas telas.
5. Testar impressão.

### Etapa 10: Acabamento

1. Melhorar mensagens.
2. Adicionar logs.
3. Adicionar backups.
4. Criar ícone do aplicativo.
5. Empacotar com PyInstaller.

## 22. Empacotamento

Instale o PyInstaller:

```bash
pip install pyinstaller
```

Gerar executável:

```bash
pyinstaller --onefile --windowed app.py
```

Se houver arquivos extras, como banco inicial, imagens e temas, configurar o `.spec`.

## 23. Melhorias futuras

**Integrações Externas:**
- [x] Atualização Automática de Rating (Importação da lista FIDE/CBX).
- [x] Exportação de arquivos compatíveis com federações e Chess-Results.
- [x] Exportação PGN das partidas do torneio.

**Sistemas de Torneio e Partidas:**
- [x] Sistema Schuring (Round-Robin / Todos contra todos).
- [x] Sistema Mata-mata (Knockout).
- [ ] Sistema suíço mais rigoroso com regras FIDE.

**Gestão e Segurança do Clube:**
### Opção A: Gestão Visual e Arbitragem
- [x] Dashboards Visuais (Gráficos) sobre alunos, despesas e receitas.
- [x] Cadastro de Árbitros (Gestão e Associação a torneios).
- [x] Backup automático ou manual em Nuvem (Google Drive, Dropbox, ou S3).
- [x] Premiação e controle inteligente por faixa de rating e categorias (emissão automática de diplomas do Top N por categoria).

**Interface e Usabilidade:**
- [x] Tema claro/escuro.
- [ ] Impressão direta a partir do aplicativo.

## 24. Ordem prática de desenvolvimento

Se o objetivo é construir rápido sem perder organização, siga esta ordem:

1. Banco de dados.
2. Cadastro de torneio.
3. Cadastro de jogadores.
4. Geração da primeira rodada.
5. Registro de resultados.
6. Classificação por pontos.
7. Rodadas seguintes.
8. Desempates.
9. Exportação.
10. Ajustes manuais e segurança.

## 25. Critério de pronto do MVP

O MVP está pronto quando for possível:

1. Criar um torneio.
2. Cadastrar pelo menos 8 jogadores.
3. Gerar a primeira rodada.
4. Registrar resultados.
5. Fechar a rodada.
6. Gerar uma segunda rodada sem repetir confrontos.
7. Ver a classificação.
8. Exportar a classificação em CSV ou PDF.

## 26. Observação sobre regras oficiais

Este roteiro propõe um sistema suíço simplificado, adequado para desenvolvimento inicial. Para torneios oficiais homologados, as regras de emparceiramento devem seguir o regulamento vigente da entidade responsável pelo evento. Nesse caso, o algoritmo deve ser revisado com base nas regras oficiais e validado por um árbitro.
