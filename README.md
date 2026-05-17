# Albericus

Aplicativo desktop em Python para emparceiramento de torneios de xadrez.

## Funcionalidades implementadas

- Cadastro de torneios avulsos, por clube/escola ou por turma.
- Cadastro dos dados do clube.
- Cadastro de membros/socios/alunos/convidados do clube.
- Cadastro de responsaveis, com vinculo a um ou mais membros.
- Listagem de alunos menores de idade sem responsavel cadastrado.
- Cadastro de aulas, treinos e eventos do clube por turma.
- Registro de presenca, falta e falta justificada por membro.
- Cadastro de planos financeiros e lancamentos por membro.
- Controle de pagamentos pagos, pendentes, atrasados, isentos e cancelados.
- Calendario de eventos do clube, com eventos avulsos e torneios vinculados.
- Indicador de proximos eventos no painel do clube.
- Ranking interno geral e por categoria com rating, aproveitamento e historico de variacao.
- Painel inicial com proximos eventos, resumo financeiro, lideres do ranking
  interno e torneios recentes.
- Pacote administrativo consolidado reunindo clube, presencas, financeiro,
  calendario, torneios e ranking interno.
- Cadastro e importacao CSV de jogadores, incluindo FIDE ID, CBX ID,
  titulos e ratings nacional/internacional.
- Importacao de listas oficiais FIDE/CBX em CSV para uma base local de ratings.
- Atualizacao dos jogadores inscritos a partir da base oficial por FIDE ID/CBX ID.
- Inscricao de membros em torneios integrados, filtrando por escopo do torneio.
- Inscricao em massa de membros ativos no torneio selecionado.
- Filtros de membros por tipo de vinculo, status e categoria.
- Historico de torneios e resultados por membro.
- Relatorios de membro e clube com contatos de responsaveis vinculados,
  frequencia, presencas, financeiro, eventos por periodo, ranking interno e
  pacote administrativo.
- Banco SQLite local na pasta de dados do usuario.
- Geracao de primeira rodada por rating.
- Geracao de rodadas seguintes por sistema suico simplificado.
- Controle de bye e tentativa de equilibrio de cores.
- Opcao real para desativar bye, exigindo numero par de jogadores ativos.
- Pontos de entrada tardia aplicados automaticamente a novos jogadores depois
  de rodadas fechadas.
- Status de jogador no torneio: ativo, desistente, ausente e nao emparceirado.
- Registro de resultados.
- Fechamento de rodada.
- Bloqueio de alteracao em rodada fechada, liberado apenas com a flag
  `Permitir mudancas perigosas`.
- Ajuste manual de jogadores em uma mesa antes do fechamento da rodada.
- Busca de jogadores e filtro de classificacao por categoria.
- Configuracao avancada de torneios com dados oficiais, regras basicas,
  flags de interface/publicacao e agenda de datas/horarios por rodada.
- Classificacao com pontos, Buchholz, Buchholz mediano, Sonneborn-Berger,
  vitorias e performance estimada do jogador.
- Exportacao de jogadores, classificacao, rodada especifica, todas as rodadas e relatorio completo em CSV, XLSX e PDF.
- Exportacao de site estatico em HTML/CSS com dados do torneio, jogadores,
  agenda, rodadas e classificacao.
- Geracao de diplomas/certificados de torneios em PDF, com modelos
  personalizaveis, logo, cores e tamanhos de fonte por modelo.
- Logs, exportacoes e backups ficam na pasta de dados do usuario por padrao.

## Instalar com uv

Requer Python 3.11 ou superior.

```bash
uv sync
```

## Rodar

```bash
uv run python app.py
```

Se preferir ativar o ambiente manualmente no PowerShell:

```bash
.venv\Scripts\Activate.ps1
python app.py
```

## Dados locais

Por padrao, o Albericus grava banco, logs, backups e exportacoes na pasta de
dados do usuario:

- Windows: `%LOCALAPPDATA%\Albericus`
- macOS: `~/Library/Application Support/Albericus`
- Linux: `$XDG_DATA_HOME/Albericus` ou `~/.local/share/Albericus`

Para usar uma pasta especifica, defina `ALBERICUS_DATA_DIR` antes de iniciar o
programa. Se existir um banco legado em `data/albericus.db` e a nova pasta ainda
nao tiver banco, ele sera copiado automaticamente na primeira abertura; backups
legados tambem sao copiados quando a nova pasta de backups ainda estiver vazia.

## Testes

```bash
python -m unittest discover -s tests
```

## Checagens de qualidade

As dependencias de desenvolvimento ficam no extra `dev`.

```bash
uv sync --extra dev
.\scripts\check_quality.ps1
```

O script compila os modulos, roda `ruff`, `mypy` e a suite de testes.

## Limpeza de artefatos

Use este script para remover caches Python, caches das ferramentas e saidas de
build. Ele preserva `.venv`, `data/`, `backups/`, `logs/` e `exports/` locais.

```bash
.\scripts\clean_artifacts.ps1
```

## Plano de evolucao: gerenciador de clube de xadrez

O objetivo da proxima fase e transformar o Albericus de um aplicativo focado em
torneios para um gerenciador completo de clube de xadrez, mantendo o modulo de
torneios integrado ao cadastro do clube.

### Visao do produto

O sistema deve passar a gerenciar:

- Cadastro e configuracoes do clube.
- Jogadores, socios, alunos e convidados.
- Responsaveis por jogadores menores de idade.
- Mensalidades e pagamentos simples.
- Aulas, treinos e controle de presenca.
- Calendario de eventos do clube.
- Ranking interno e historico de partidas.
- Torneios com inscricao a partir do cadastro do clube.
- Relatorios administrativos, esportivos e financeiros.
- Torneios sem limite fixo de jogadores ou quantidade de eventos, limitado apenas pela maquina e pelo banco local.
- Publicacao web simples de emparceiramentos, resultados, informacoes do torneio e classificacao final.
- Banco de dados de jogadores com busca por IDs FIDE/CBX e atualizacao de ratings oficiais quando houver fonte disponivel.
- Calculo de desempenho do jogador e uso de ratings gerados em torneios anteriores para inscricoes futuras.

### Modulos planejados

#### Clube

- Nome, cidade, endereco, telefone, e-mail e observacoes.
- Configuracoes padrao do clube.
- Categorias usadas pelo clube.
- Tipos de vinculo: socio, aluno, convidado, visitante e inativo.
- Futuramente, suporte a logo e identidade visual nos relatorios.

#### Jogadores, socios e alunos

- Expandir o cadastro atual de jogadores.
- Campos novos: telefone, e-mail, documento, data de nascimento, responsavel,
  status de matricula e observacoes.
- Campos esportivos: sobrenome, nome, titulo, sexo, FIDE ID, CBX ID, rating
  nacional, rating internacional, federacao, clube, escola/turma e categoria.
- Busca por jogador usando nome, FIDE ID ou CBX ID.
- Importacao e atualizacao de dados oficiais de jogadores, quando houver arquivo
  ou fonte confiavel da FIDE/CBX.
- Separar o conceito de membro do clube do conceito de participante de torneio.
- Permitir que um membro seja inscrito em varios torneios.
- Permitir convidados externos em torneios sem transforma-los em socios.
- Exibir historico do jogador com torneios, presencas, pagamentos e ranking.

#### Escolas e turmas

- Avaliar cadastro de escolas, turmas e professores/instrutores.
- Vincular alunos a escola e turma.
- Usar escola/turma como filtro em membros, inscricoes, presencas e relatorios.
- Manter o modulo opcional para nao complicar clubes que nao trabalham com turmas.

#### Torneios avancados

- Campos de configuracao inspirados em Swiss-Manager e SwissSystem:
  denominacao, FIDE Event-ID, organizador, pagina web, e-mail, ritmo,
  diretor do torneio, arbitro principal, arbitros auxiliares, federacao,
  estado, local, comentarios, premiacao, categorias, data de corte e tipo de
  torneio real/teste.
- Agenda de rodadas com data e horario por rodada.
- Configuracao de ordenacao inicial: rating nacional, rating internacional,
  rating internacional depois nacional, maior rating entre nacional e
  internacional, ou ordem manual.
- Configuracao de cor inicial e politica de emparceiramento quando aplicavel.
- Pontos de bye configuraveis e controle de tchau/bye.
- Regras para adesao tardia, incluindo pontos por entrada depois da primeira
  rodada quando o regulamento permitir.
- Suporte futuro a sistema acelerado.
- Classificacao intermediaria e final com criterios de desempate configuraveis.
- Desempates planejados: confronto direto, Buchholz variavel, Buchholz mediano,
  Sonneborn-Berger, numero de vitorias, numero de partidas de pretas,
  progressivo, media de rating dos adversarios, Koya e performance.
- Calculo de desempenho/performance do jogador no torneio para acompanhar a
  evolucao dos alunos.
- Copiar configuracoes de um torneio anterior para criar novo evento.
- Flags de publicacao e interface: ocultar classificacao temporariamente,
  mostrar adversarios na classificacao, ocultar nomes de cores e arquivar
  torneio.
- Controles de edicao: permitir ou bloquear inscricao publica de jogadores,
  alteracao de resultados pelos jogadores e mudancas perigosas.
- Emparceiramento manual completo antes de confirmar a rodada.
- Exclusao de rodadas geradas antes do fechamento e bloqueio de exclusao de
  rodadas fechadas sem acao administrativa explicita.
- Jogador desistente durante o torneio deve continuar na lista de inscritos,
  aparecer como nao emparceirado e deixar de ser pareado nas rodadas seguintes,
  mantendo historico e resultados anteriores.
- Resultados de WO devem continuar disponiveis para vitoria por ausencia,
  derrota por ausencia e dupla ausencia.
- Lista de classificacao final obrigatoria em relatorios e exportacoes.

#### Publicacao web e exportacoes

- Exportar emparceiramentos, resultados, classificacao e informacoes do torneio
  em HTML/CSS para publicar em uma pagina simples.
- Gerar pacote estatico local pronto para hospedagem.
- Futuramente, permitir configuracao de pagina publica do clube ou torneio.
- Manter exportacoes em CSV, XLSX e PDF.

#### Responsaveis

- Cadastro de responsaveis para criancas e adolescentes.
- Nome, telefone, e-mail e relacao com o jogador.
- Observacoes administrativas.
- Vinculo de um responsavel a um ou mais jogadores.

#### Financeiro simples

- Cadastro de planos: mensal, avulso, bolsista, isento ou personalizado.
- Registro de pagamentos por membro.
- Status financeiro: em dia, pendente, atrasado ou isento.
- Relatorio por periodo.
- Resumo mensal de recebimentos e pendencias.
- Geracao em lote de mensalidades por plano, competencia e vencimento.
- Exportacao de recibos simples para lancamentos pagos ou isentos.

#### Aulas e treinos

- Cadastro de sessoes de aula ou treino.
- Data, horario, professor/instrutor e observacoes.
- Lista de presenca.
- Historico de frequencia por aluno.
- Relatorio de presencas por periodo.

#### Calendario de eventos

- Eventos do clube: aulas, torneios, reunioes, simultaneas, viagens e encontros.
- Status: planejado, confirmado, concluido ou cancelado.
- Integracao com torneios cadastrados.
- Visao de proximos eventos.

#### Ranking interno

- Rating interno do clube.
- Historico de partidas e resultados.
- Aproveitamento por jogador.
- Integracao opcional com resultados dos torneios internos.
- Atualizacao do rating interno com base nos ratings gerados por torneios
  anteriores, para sugerir rating na inscricao do proximo torneio.
- Relatorio de evolucao do jogador.

#### Torneios integrados

- Manter o modulo atual de torneios.
- Inscrever jogadores a partir do cadastro de membros.
- Permitir jogadores convidados externos.
- Salvar historico do torneio no perfil do jogador.
- Usar resultados de torneios internos no ranking do clube, quando configurado.
- Continuar exportando jogadores, rodadas, classificacao e relatorio completo.
- Importar membros ativos em lote e manter convidados externos separados do
  cadastro completo do clube.
- Integrar ratings oficiais e rating interno na inscricao de torneios.
- Publicar emparceiramentos e classificacao em pagina HTML/CSS.

### Mudancas tecnicas planejadas

#### Organizacao do codigo

Reorganizar gradualmente o projeto por dominios:

```txt
src/
  core/
    database.py
    logging_config.py
  club/
  members/
  finance/
  sessions/
  events/
  tournaments/
  reports/
  ui/
```

Essa reorganizacao deve ser incremental para evitar quebrar o modulo de torneios
ja implementado.

#### Banco de dados

Novas tabelas propostas:

- `clubs`: dados do clube.
- `members`: socios, alunos, jogadores e convidados.
- `guardians`: responsaveis.
- `member_guardians`: vinculo entre membros e responsaveis.
- `membership_plans`: planos de mensalidade.
- `payments`: pagamentos e mensalidades.
- `training_sessions`: aulas e treinos.
- `attendance`: presencas.
- `club_events`: calendario de eventos.
- `exercise_library`: biblioteca de exercicios e posicoes.
- `training_lists`: listas de treino por clube/turma.
- `training_list_exercises`: exercicios vinculados a listas.
- `exercise_attempts`: tentativas e historico de estudos por aluno.
- `inventory_items`: materiais, livros e equipamentos.
- `inventory_loans`: emprestimos de materiais para membros.
- `inventory_maintenance`: manutencoes e reparos dos materiais.
- `audit_log`: auditoria local de operacoes sensiveis.
- `tournament_registrations`: inscricoes em torneios.
- `internal_rating_history`: historico de rating interno.
- `schools`: escolas parceiras ou locais de aula.
- `classes`: turmas/aulas vinculadas a escolas ou ao clube.
- `member_class_enrollments`: vinculo entre alunos e turmas.
- `player_external_ids`: IDs oficiais do jogador, como FIDE e CBX.
- `official_rating_snapshots`: listas importadas de rating FIDE/CBX por data.
- `tournament_settings`: configuracoes avancadas do torneio.
- `round_schedule`: data e horario de cada rodada.
- `tournament_publications`: historico de exportacoes HTML/CSS publicadas.
- `player_performances`: desempenho calculado por jogador em cada torneio.

Tabelas atuais que devem ser preservadas:

- `tournaments`
- `players`
- `rounds`
- `pairings`

O caminho recomendado e ligar `players` a `members` por meio de uma coluna
opcional `member_id`, mantendo compatibilidade com torneios antigos.

#### Migracoes

- Criar um controle simples de versao do banco.
- Aplicar migracoes automaticamente ao abrir o aplicativo.
- Preservar dados existentes em `data/albericus.db` ao migrar para a pasta de dados do usuario.
- Fazer backup antes de migracoes estruturais.

### Roadmap de implementacao

#### Etapa 1: Base de clube

1. Criar tabela `clubs`.
2. Criar tela de configuracoes do clube.
3. Criar menu inicial com visao geral do clube.
4. Mostrar indicadores basicos: membros ativos, torneios recentes e proximos eventos.
5. Manter acesso ao modulo de torneios atual.

#### Etapa 2: Membros do clube

1. Criar tabela `members`.
2. Criar tela de cadastro completo de membros.
3. Adicionar busca e filtros por status, categoria e tipo de vinculo.
4. Criar status: ativo, inativo, visitante, convidado e desistente.
5. Criar acao para inscrever membro em torneio.
6. Manter cadastro rapido de convidado externo para torneios.

#### Etapa 3: Integracao com torneios

1. Adicionar `member_id` opcional aos jogadores de torneio.
2. Permitir importar jogadores de um torneio a partir dos membros ativos.
3. Permitir convidado externo sem cadastro completo.
4. Registrar torneios jogados no historico do membro.
5. Exibir resultados de torneios no perfil do jogador.

#### Etapa 4: Responsaveis

1. Criar tabela `guardians`.
2. Criar vinculo entre responsaveis e membros.
3. Exibir contatos do responsavel no perfil do aluno.
4. Permitir filtro de alunos menores de idade.

#### Etapa 5: Aulas, treinos e presenca

1. Criar cadastro de sessoes de treino.
2. Criar tela de chamada.
3. Registrar presenca, falta e justificativa.
4. Exibir frequencia por aluno.
5. Exportar relatorio de presenca.

#### Etapa 6: Financeiro simples

1. Criar planos de mensalidade.
2. Registrar pagamentos.
3. Calcular status financeiro por membro.
4. Exibir pendencias do mes.
5. Exportar relatorio financeiro em CSV, XLSX e PDF.

#### Etapa 7: Calendario

1. Criar tabela de eventos.
2. Criar tela de calendario/listagem.
3. Integrar torneios ao calendario.
4. Mostrar proximos eventos no painel inicial.

#### Etapa 8: Ranking interno

1. Criar modelo de rating interno.
2. Definir se torneios internos afetam o ranking.
3. Registrar historico de alteracoes.
4. Exibir ranking geral e por categoria.
5. Exibir evolucao individual.

#### Etapa 9: Relatorios

1. Relatorio geral do clube.
2. Relatorio individual de membro.
3. Relatorio de presencas.
4. Relatorio financeiro.
5. Relatorio de torneios por periodo.

#### Etapa 10: Acabamento e distribuicao

1. Melhorar dashboard inicial.
2. Criar configuracoes do aplicativo.
3. Melhorar backups e restauracao.
4. Criar icone do aplicativo.
5. Empacotar com PyInstaller.

### Roadmap adicional a partir da conversa do PDF

#### Configuracao avancada de torneio

1. Criar tela de configuracao completa do torneio com abas semelhantes a:
   geral, desempates, listagens/publicacao, tabuleiros, FIDE e arbitros.
2. Adicionar campos de evento: FIDE Event-ID, organizador, site, e-mail,
   diretor, arbitro principal, arbitros auxiliares, federacao, estado, local,
   comentarios, premiacao, categorias e data de corte.
3. Criar agenda de rodadas com data e horario por rodada.
4. Permitir copiar dados e configuracoes de um torneio anterior.
5. Separar torneio real de torneio de teste.

#### Cadastro e dados oficiais de jogadores

1. Ampliar cadastro com sobrenome, nome, titulo, sexo, data de nascimento,
   FIDE ID, CBX ID, rating nacional, rating internacional, federacao,
   clube, escola e turma.
2. Criar banco unico de jogadores para reaproveitar inscricoes entre clubes,
   eventos e torneios.
3. Implementar busca por FIDE ID e CBX ID.
4. Importar listas oficiais FIDE/CBX a partir de arquivo local quando a busca
   direta nao estiver disponivel.
5. Atualizar rating de jogadores inscritos usando a lista oficial mais recente.

#### Operacao de torneio

1. Completar emparceiramento manual, com troca de jogadores, troca de cores e
   ajuste de mesa antes da confirmacao.
2. Permitir exclusao de rodadas geradas ainda nao fechadas.
3. Tratar desistencias sem remover o jogador da inscricao: manter na lista,
   marcar como desistente/nao emparceirado e preservar historico anterior.
4. Continuar aceitando resultados de WO: 1F-0F, 0F-1F e 0F-0F.
5. Exibir classificacao intermediaria e classificacao final obrigatoria.
6. Adicionar configuracoes para inscricao tardia, pontos por entrada tardia,
   bye/tchau, sistema acelerado e mudancas perigosas.

#### Desempenho, rating e evolucao

1. Calcular performance/desempenho do jogador por torneio.
2. Salvar desempenho no historico do membro.
3. Atualizar o rating interno do clube a partir dos resultados dos torneios.
4. Usar o rating atualizado de torneios anteriores como sugestao automatica na
   inscricao de torneios novos.
5. Gerar relatorio de evolucao por aluno com rating, performance e resultados.

#### Publicacao web

1. Exportar site estatico em HTML/CSS com dados do torneio.
2. Publicar emparceiramentos por rodada.
3. Publicar resultados, lista de inscritos, jogadores nao emparceirados e
   classificacao final.
4. Prever uma opcao futura de pagina publica do clube ou do torneio.

#### Escolas e turmas

1. Avaliar se o cadastro de escolas e turmas deve entrar antes ou depois do
   financeiro.
2. Criar escolas e turmas como modulo opcional.
3. Usar escola/turma para filtro de alunos, inscricoes, presencas e relatorios.

### Prioridade recomendada

A prioridade inicial deve ser:

1. Criar `clubs`.
2. Criar `members`.
3. Integrar `members` com torneios.
4. Completar configuracao avancada de torneio e agenda de rodadas.
5. Ampliar cadastro/busca de jogadores com FIDE ID, CBX ID e ratings oficiais.
6. Implementar publicacao HTML/CSS de emparceiramentos e classificacao.
7. Calcular desempenho do jogador e atualizar rating interno entre torneios.

As tres primeiras entregas criam a base do gerenciador de clube sem comprometer
o emparceiramento que ja funciona. As demais incorporam as melhorias pedidas na
conversa do PDF.

### Primeira fatia implementada

- Tabela `clubs` criada.
- Tabela `members` criada.
- Coluna opcional `players.member_id` criada por migracao automatica.
- Tela `Clube` adicionada com dados cadastrais e indicadores basicos.
- Tela `Membros` adicionada com cadastro, edicao, busca e ativacao/inativacao.
- Tela `Jogadores` atualizada para inscrever membros ativos no torneio selecionado.
- Cadastro manual de jogadores continua disponivel para convidados externos.
- Testes automatizados cobrem criacao de membro, inscricao no torneio e migracao de banco antigo.

### Segunda etapa implementada

- Status de membros ampliados para: ativo, inativo, visitante, convidado e desistente.
- Tela `Membros` agora possui filtros por tipo de vinculo, status e categoria.
- As categorias do filtro sao carregadas automaticamente a partir dos membros cadastrados.
- Apenas membros com status ativo aparecem na inscricao automatica de torneios.
- Visitantes, convidados e desistentes ficam fora da inscricao automatica, mas convidados externos ainda podem ser adicionados manualmente na tela `Jogadores`.
- Botao de cadastro manual na tela `Jogadores` foi renomeado para `Adicionar convidado`.
- Testes automatizados cobrem os novos status e a elegibilidade para inscricao em torneios.

### Terceira etapa implementada

- Tela `Jogadores` permite inscrever todos os membros ativos ainda nao inscritos no torneio selecionado.
- Convidados externos continuam sendo cadastrados diretamente no torneio, sem cadastro completo como membro.
- Tela `Membros` exibe historico de torneios do membro selecionado com pontos, posicao, rodadas jogadas e resumo V/E/D/B.
- Duplo clique no historico do membro mostra os resultados rodada a rodada daquele torneio.
- O historico e derivado da coluna `players.member_id`, preservando compatibilidade com torneios antigos.
- Testes automatizados cobrem inscricao em massa e resumo de resultados por membro.

### Quarta etapa implementada

- Tabelas `tournament_settings` e `round_schedule` criadas com migracao automatica.
- Tela `Config. torneio` adicionada para editar dados gerais, dados oficiais, flags de regras/interface e agenda das rodadas.
- Cadastro de jogadores ampliado com sobrenome, nome proprio, titulo, sexo, FIDE ID, CBX ID, rating nacional, rating internacional e nascimento.
- Importacao CSV aceita colunas oficiais como `fide`, `cbx`, `rating_nacional`, `rating_internacional`, `titulo`, `sexo` e `sobrenome`.
- Classificacao calcula uma performance estimada do jogador com base nos ratings dos adversarios e no resultado obtido.
- Exportacao `Site HTML` gera `index.html` e `styles.css` com informacoes do torneio, agenda, lista de jogadores, rodadas e classificacao.
- Exportacoes de relatorio passam a incluir dados oficiais do torneio, agenda e campos oficiais dos jogadores.
- Testes automatizados cobrem configuracoes de torneio, agenda, campos oficiais, importacao CSV ampliada, migracao e exportacao HTML.

### Quinta etapa implementada

- Colunas `players.player_status` e `players.starting_points` criadas com migracao automatica.
- Jogador desistente, ausente ou nao emparceirado permanece na lista de inscritos e na classificacao, mas nao entra nas proximas rodadas.
- Pontos por adesao tardia configurados no torneio sao aplicados automaticamente quando um jogador entra apos rodadas fechadas.
- Flag `Desativar bye/tchau` agora impede gerar rodada com numero impar de jogadores ativos.
- Alterar resultado de rodada fechada agora exige a flag `Permitir mudancas perigosas`.
- Jogador cadastrado por engano pode ser excluido enquanto ainda nao apareceu em nenhuma rodada.
- Exclusao e bloqueada quando o jogador ja tem emparceiramento; nesses casos deve-se usar `Desistente` ou `Nao emparceirado`.
- Exportacao HTML e relatorios passam a mostrar status real do jogador no torneio.
- Testes automatizados cobrem desistencia, entrada tardia, bye desativado e bloqueio de alteracao perigosa.

### Sexta etapa implementada

- Tabelas `official_rating_snapshots` e `official_players` criadas com migracao automatica.
- Tela `Jogadores` recebeu acoes para importar listas `FIDE` e `CBX` em CSV.
- Cada importacao oficial salva um snapshot com fonte, arquivo, data da lista e quantidade importada.
- Atualizacao de ratings oficiais usa FIDE ID e CBX ID para localizar o jogador na base importada.
- Quando ha dados FIDE e CBX para o mesmo jogador, o sistema combina os campos: titulo, sexo, federacao e rating internacional da FIDE; clube e rating nacional da CBX.
- O rating principal do jogador e recalculado conforme a ordem inicial configurada no torneio.
- Jogadores sem correspondencia oficial sao reportados ao usuario sem bloquear os demais.
- Testes automatizados cobrem importacao oficial, atualizacao combinada FIDE/CBX, ordem inicial de rating e migracao das novas tabelas.

### Setima etapa implementada

- Tabela `internal_rating_history` criada com migracao automatica e backup antes de alterar bancos antigos.
- Tela `Classificacao` recebeu a acao `Atualizar rating interno`, que usa a performance calculada no torneio para atualizar o rating do membro.
- A atualizacao e idempotente por membro, torneio e jogador, evitando aplicar o mesmo torneio duas vezes por acidente.
- O novo rating interno fica salvo em `members.rating` e passa a ser usado automaticamente ao inscrever o membro em torneios seguintes.
- Tela `Membros` recebeu consulta de historico de rating interno para o membro selecionado.
- Testes automatizados cobrem criacao do historico, atualizacao do membro, idempotencia, uso do rating no torneio seguinte e migracao da nova tabela.

### Oitava etapa implementada

- Relatorio de evolucao por membro/aluno criado com dados cadastrais, resumo por torneio, historico de rating interno e resultados rodada a rodada.
- Exportacao disponivel na tela `Membros` pelo botao `Exportar evolucao`.
- O relatorio pode ser gerado em CSV, XLSX ou PDF usando a mesma infraestrutura de exportacao do modulo de torneios.
- O resumo por torneio mostra rating de inscricao, pontos, posicao, performance, variacao de rating interno e placar V/E/D/B.
- Testes automatizados cobrem a geracao do relatorio com rating, performance e resultados.

### Nona etapa implementada

- Tela `Relatorios` adicionada para gerar relatorios administrativos sem depender de um torneio selecionado.
- Relatorio geral do clube exporta perfil, indicadores, membros por status/tipo/categoria, ranking interno e torneios cadastrados.
- Relatorio individual de membro reutiliza a evolucao do aluno com dados cadastrais, torneios, rating interno e resultados rodada a rodada.
- Relatorio de torneios por periodo permite filtrar por data inicial/final e inclui resumo operacional e top 10 de cada torneio.
- Todos os novos relatorios usam CSV, XLSX ou PDF.
- Testes automatizados cobrem o relatorio geral do clube e o filtro de torneios por periodo.

### Decima etapa implementada

- Dashboard inicial do clube ampliado com cards de backup, atalhos operacionais e lista dos ultimos torneios.
- Tabela `app_settings` criada para salvar preferencias locais do aplicativo.
- Tela `Config. app` adicionada para alterar aparencia, pasta padrao de exportacao e pasta de backups.
- Backups agora podem ser listados, criados manualmente e restaurados pela interface, com copia de seguranca antes da restauracao.
- Icone do aplicativo criado em `assets/app_icon.svg` e `assets/app_icon.ico`.
- Arquivo `albericus.spec` e script `scripts/build_windows.ps1` adicionados para empacotar o aplicativo com PyInstaller.
- Testes automatizados cobrem preferencias do aplicativo, backup/restauracao e migracao da nova tabela.

### Melhoria: clubes, escolas e turmas

- O cadastro de `clubs` deixa de representar apenas um clube fixo e passa a aceitar varias unidades.
- Cada unidade pode ser classificada como clube, escola, projeto ou parceiro.
- Escolas e clubes podem ter varias turmas vinculadas por meio da tabela `classes`.
- Alunos/membros podem ser vinculados a uma turma ativa por meio de `member_class_enrollments`, preservando historico de troca de turma.
- A tela `Clube` passa a permitir criar, editar, ativar/inativar unidades e cadastrar turmas da unidade selecionada.
- A tela `Membros` passa a salvar e filtrar por clube/escola e turma.
- Torneios podem ser avulsos, vinculados a uma unidade ou vinculados a uma turma.
- A inscricao automatica usa todos os membros ativos no torneio avulso, os membros da unidade no torneio de clube/escola e apenas os alunos da turma no torneio de turma.
- Relatorios passam a incluir clube/escola e turma, permitindo acompanhar alunos por unidade.
- A migracao preserva os dados existentes vinculando registros antigos ao clube padrao `id = 1`.

### Gerador de diplomas - Etapa 1 implementada

- Tela `Diplomas` adicionada para torneios individuais.
- Modelos fixos disponiveis: participacao, premiacao geral e premiacao por categoria.
- Destinatarios podem ser todos os jogadores, top N geral, top N por categoria
  ou jogadores selecionados na lista.
- Cada diploma e gerado como uma pagina em PDF paisagem, dentro de um unico arquivo.
- Os dados sao preenchidos automaticamente com nome do jogador, torneio, local,
  periodo, pontos, posicao geral e posicao na categoria.
- Torneios por equipes ficam preparados para uma etapa futura do gerador.

### Gerador de diplomas - Etapa 2 implementada

- Tabela `certificate_templates` criada com migracao automatica.
- Modelos padrao de participacao, premiacao geral e premiacao por categoria
  sao cadastrados automaticamente.
- A tela `Diplomas` permite editar e salvar nome do modelo, tipo, orientacao,
  titulo, texto principal, rodape e assinaturas.
- Tambem e possivel salvar um modelo existente como novo modelo personalizado.
- A geracao do PDF usa o texto do modelo editado, com variaveis como
  `{nome}`, `{torneio}`, `{local}`, `{periodo}`, `{posicao}`, `{categoria}`,
  `{posicao_categoria}`, `{pontos}`, `{rating}` e `{clube}`.
- Orientacao paisagem e retrato sao suportadas na emissao do PDF.
- A tela exibe um preview simples do titulo renderizado para o primeiro
  destinatario encontrado.

### Gerador de diplomas - Etapa 3 implementada

- Modelos de diploma passaram a salvar identidade visual propria.
- Cada modelo pode definir logo, cor principal, cor de destaque e tamanhos de
  fonte para titulo, texto principal e rodape.
- A tela `Diplomas` recebeu campos para editar esses dados visuais e escolher
  um arquivo de logo local.
- A geracao do PDF aplica as cores do modelo na moldura, linha de destaque,
  titulo e assinaturas.
- O logo e desenhado no topo do diploma quando informado e validado.
- Os modelos antigos sao migrados automaticamente com valores visuais padrao.

### Gerador de diplomas - Etapa 4 implementada

- A tela `Diplomas` passa a escolher o contexto da emissao: torneio,
  membros/alunos, aula/turma, evento ou ranking interno.
- Novos modelos padrao sao cadastrados para membro/aluno, aula/turma, evento
  e ranking interno.
- A geracao em PDF agora aceita destinatarios vindos do cadastro de membros,
  da lista de presenca de aulas, de eventos vinculados a uma unidade e do
  ranking interno.
- A lista da tela muda automaticamente conforme o contexto e permite gerar
  diplomas para todos, top N quando aplicavel ou destinatarios selecionados.
- Novas variaveis de modelo incluem `{turma}`, `{aula}`, `{evento}`,
  `{instrutor}`, `{professor}`, `{tipo}`, `{status}`, `{nivel}`, `{delta}`,
  `{jogos}`, `{desempenho}`, `{aproveitamento}`, `{vitorias}`, `{empates}`,
  `{derrotas}` e `{ultimo_torneio}`.

### Gerador de diplomas - Etapa 5 implementada

- Cada diploma emitido passa a receber um codigo unico de verificacao.
- O codigo e impresso no PDF e fica disponivel nas variaveis `{codigo}`,
  `{codigo_verificacao}`, `{emissao}` e `{emitido_em}`.
- A tabela `certificate_issuances` registra historico de emissao com contexto,
  origem, destinatario, modelo usado, arquivo gerado e status.
- A tela `Diplomas` exibe as emissoes recentes e permite consultar um diploma
  pelo codigo de verificacao.
- A migracao para a versao 7 cria o historico automaticamente e preserva os
  modelos existentes.

### Gerador de diplomas - fundos e identidade visual

- Modelos de diploma aceitam imagem de fundo, opacidade do fundo, logo
  principal e logo secundario.
- A tela `Diplomas` permite selecionar arquivos `.png`, `.jpg` ou `.jpeg`
  para esses elementos visuais.
- Fundos padrao de xadrez ficam em `assets/certificates/backgrounds/`:
  `tabuleiro_sutil.png`, `xadrez_classico.png`, `xadrez_escolar.png`,
  `xadrez_premium.png` e `pecas_marca_dagua.png`.
- Logos padrao em PNG transparente ficam em `assets/certificates/logos/`:
  `albericus_knight.png`, `clube_rook.png`, `escola_pawn.png`,
  `torneio_trophy.png` e `selo_queen.png`.
- Novos modelos prontos com esses fundos sao cadastrados automaticamente,
  mantendo os modelos antigos como opcoes simples.
- Os fundos podem ser recriados com
  `uv run python scripts\generate_certificate_backgrounds.py`.
- Os logos podem ser recriados com
  `uv run python scripts\generate_certificate_logos.py`.

### Roadmap do gerenciador de clube

O Albericus ja cobre torneios, membros/alunos, turmas, aulas, exercicios,
inventario, eventos, relatorios, backups, ranking interno e diplomas. As
proximas melhorias devem ser implementadas em etapas pequenas para manter o
banco local simples e testavel:

1. Consulta local/publica de diplomas: exportar uma pagina HTML de verificacao
   dos codigos emitidos, com busca por codigo, nome, origem e status.
2. Area pedagogica: planos de aula, metas por turma, evolucao por nivel,
   tarefas e observacoes do professor.
3. Mensalidades e financeiro: planos recorrentes, vencimentos, pagamentos,
   pendencias e recibos simples.
4. Ranking interno avancado: temporadas, categorias configuraveis, historico
   de campeoes, criterios por clube/turma e filtros por periodo.
5. Comunicacao e portal: pagina HTML do clube/turma, avisos, calendario,
   exportacao de listas e comunicados para responsaveis.
6. Biblioteca de exercicios: temas taticos, niveis, listas de treino,
   desempenho por aluno e historico de estudos.
7. Inventario: controle de pecas, tabuleiros, relogios, livros, emprestimos e
   manutencoes.
8. Seguranca operacional: perfis de acesso, auditoria de alteracoes, politicas
   de backup e restauracao guiada.

### Roadmap do gerenciador de clube - Etapa 1 implementada

- A tela `Diplomas` recebeu a acao `Exportar verificador`.
- O verificador gera um unico arquivo HTML local, sem servidor, com busca por
  codigo, nome, origem ou modelo.
- A pagina exibe codigo, status ativo/revogado, destinatario, contexto, origem,
  tipo, modelo e data de emissao.
- O arquivo HTML nao publica o caminho local do PDF, evitando expor a estrutura
  de pastas da maquina.

### Roadmap do gerenciador de clube - Etapa 2 implementada

- A tela `Aulas` passa a registrar dados pedagogicos da aula/treino:
  nivel alvo, objetivo, conteudo e tarefa para casa/treino.
- As aulas continuam vinculadas a clube/escola e turma, permitindo montar um
  plano pedagogico por turma sem criar outro fluxo de cadastro.
- O relatorio de presencas inclui os novos campos pedagogicos na secao de
  aulas e treinos.
- Bancos antigos sao migrados automaticamente para adicionar os novos campos em
  `training_sessions`.

### Roadmap do gerenciador de clube - Etapa 3 implementada

- A tela `Financeiro` passa a gerar mensalidades em lote a partir de um plano,
  referencia `AAAA-MM` e vencimento.
- A geracao considera socios/alunos ativos e pula automaticamente lancamentos
  ja existentes para o mesmo plano e referencia.
- Lancamentos pagos ou isentos podem ser exportados como recibo simples em
  PDF, XLSX ou CSV.
- O fluxo manual de lancamentos, status financeiro, resumo e relatorios por
  periodo continua funcionando no mesmo modulo.

### Roadmap do gerenciador de clube - Etapa 4 implementada

- O `Ranking interno` passa a aceitar filtros por clube/escola, turma e periodo
  de temporada.
- O aproveitamento, partidas, pontos e variacao exibidos podem ser calculados
  apenas dentro do periodo informado.
- O relatorio de ranking interno inclui os filtros aplicados, permitindo
  registrar rankings por temporada, unidade ou turma.
- A exportacao tambem respeita categoria, clube/escola, turma e periodo,
  mantendo a visao geral e os lideres por categoria.

### Roadmap do gerenciador de clube - Etapa 5 implementada

- A tela `Relatorios` recebeu a opcao `Portal do clube/turma`.
- O portal exporta uma pasta HTML estatica com `index.html` e `styles.css`,
  pronta para abrir localmente ou hospedar.
- A pagina inclui comunicados, calendario de eventos, aulas/treinos futuros,
  turmas, ranking interno e torneios recentes.
- A exportacao pode ser filtrada por clube/escola e turma, permitindo gerar um
  portal geral da unidade ou uma pagina especifica para uma turma.

### Roadmap do gerenciador de clube - Etapa 6 implementada

- A tela `Exercicios` permite cadastrar posicoes e tarefas por tema, nivel,
  dificuldade, FEN, PGN, solucao, objetivo, tags e fonte.
- Listas de treino podem ser criadas para clube/escola, turma e nivel, com
  status de rascunho, pronta, aplicada ou arquivada.
- Exercicios podem ser adicionados e removidos das listas, mantendo uma ordem
  simples para uso em aula.
- A tela `Aulas` recebeu o campo `Lista de treino`, permitindo vincular uma
  lista pronta ao planejamento da aula/treino.
- O banco registra tentativas por aluno, exercicio, lista e aula, criando a
  base para acompanhar desempenho e historico de estudos.
- Bancos antigos sao migrados automaticamente para a versao 11, criando
  `exercise_library`, `training_lists`, `training_list_exercises`,
  `exercise_attempts` e `training_sessions.training_list_id`.

### Roadmap do gerenciador de clube - Etapa 7 implementada

- A nova tela `Inventario` permite cadastrar materiais por clube/escola:
  pecas, tabuleiros, relogios, livros, kits, itens digitais e outros.
- Cada item registra codigo, quantidade total, estado de conservacao, local,
  data/valor de aquisicao, status ativo e observacoes.
- Emprestimos vinculam item, membro, quantidade, data prevista e devolucao,
  com disponibilidade calculada automaticamente pelos emprestimos em aberto.
- Manutencoes registram descricao, custo, fornecedor, status e data de
  conclusao, permitindo acompanhar reparos pendentes.
- Bancos antigos sao migrados automaticamente para a versao 12, criando
  `inventory_items`, `inventory_loans` e `inventory_maintenance`.

### Roadmap do gerenciador de clube - Etapa 8 implementada

- A tela `Config. app` ganhou a secao `Seguranca operacional`, com operador
  local, perfil operacional e quantidade de backups a manter.
- Perfis locais disponiveis: administrador, arbitragem, professor, assistente
  e consulta. Nesta etapa eles identificam operacoes auditadas e preparam a
  base para bloqueios por permissao em uma etapa futura.
- Backups manuais e restauracoes passam pelo `SecurityService`, registrando
  auditoria local em `audit_log`.
- A politica de retencao remove backups antigos mantendo a quantidade
  configurada, com acao manual `Aplicar retencao`.
- A propria tela de configuracoes mostra a auditoria recente com data,
  operador, perfil, acao e descricao.
- Bancos antigos sao migrados automaticamente para a versao 13, criando
  `audit_log` e indices por data/acao e entidade.

## CSV de jogadores

Cabecalhos aceitos:

```csv
name,club,rating,category,fide,cbx,rating_nacional,rating_internacional,titulo
Ana Silva,Clube A,1850,Sub-18,123456,7890,1850,1820,WFM
Bruno Souza,Clube B,1720,Absoluto,234567,6789,1720,1690,
```

Tambem sao aceitos nomes de colunas em portugues, como `nome`, `clube`, `elo`,
`categoria`, `sobrenome`, `sexo`, `id_fide`, `id_cbx`, `elo_nacional` e
`elo_fide`.

## CSV de ratings oficiais

Para importar uma lista FIDE ou CBX na tela `Jogadores`, use CSV com colunas como:

```csv
name,fide,cbx,title,fide_rating,rating_nacional,federation,club,birth_date
Ana Silva,123456,7890,WFM,1820,1850,BRA,Clube A,2008-01-01
```

Tambem sao aceitos nomes como `nome`, `titulo`, `id_fide`, `id_cbx`,
`rating_internacional`, `elo_fide`, `rating_nacional`, `elo_nacional`,
`fed`, `federacao`, `clube`, `sexo` e `data_nascimento`.

## Observacao

O algoritmo de emparceiramento e um suico simplificado para uso inicial. Para torneios oficiais, valide as regras com o regulamento da entidade organizadora e com um arbitro.
