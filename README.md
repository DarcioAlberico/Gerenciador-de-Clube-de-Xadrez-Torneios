# Gerenciador-de-Clube-de-Xadrez-Torneios
Gerenciador de clube de xadrez com gerenciador de torneios embutidos. Gerencia Clube, Membros, Alunos, Alulas, Torneios, Certificados/Diplomas, etc. Como não sei progromar foi tudo feito por IA.

# Albericus

Aplicativo desktop em Python para Gerenciar Clube/Escolas_Turmas e Torneios de Xadrez.

## Estado atual

Atualizado em **2026-08-04**. Schema do banco **v55**; suite com **1792 testes**
(gate completo: compilação, ruff, mypy, convenções e acentuação de UI, pytest).

O roadmap de arbitragem esta **concluído**: as fases 0 a 12 do
[`ROADMAP_ARBITRAGEM_XADREZ.md`](ROADMAP_ARBITRAGEM_XADREZ.md) e os EPICs A a J
da [`ESPEC_PAINEL_ARBITRO.md`](ESPEC_PAINEL_ARBITRO.md) foram entregues, incluindo
a auditoria arbitral de 2026-07-29 inteira. O roadmap de paridade com o
Swiss-Manager ([`ROADMAP_PARIDADE_SWISSMANAGER.md`](ROADMAP_PARIDADE_SWISSMANAGER.md))
também está fechado.

As entregas mais recentes mudaram a NATUREZA de três partes do sistema: o que era
código passou a ser dado, e o que era silêncio passou a ser aviso.

- **Regulamento como dado.** Limiares de norma (FIDE Handbook B.01), regulamento
  de rating por base e ritmo (B.02) e categorias do edital são registros
  editáveis, não `if`s no meio do cálculo.
- **Nada some calado.** Reduzir rodadas com agenda pede confirmação e audita;
  mudança estrutural depois da rodada 1 exige motivo; rating de ritmo ausente cai
  no standard AVISANDO; motor de desempate que cai avisa.
- **Configuração honesta.** Opção visível que não fazia nada foi removida — e um
  teste varre o código para reprovar a próxima.

**O que falta depende de fonte externa**, não de decisão do projeto: o
regulamento de rating e o formato do arquivo de submissão da CBX (não
publicados), relógio de hardware e app nativo. A aceleração de Baku saiu desta
lista: a regra está no FIDE Handbook (C.04.7) e foi implementada (RGS-30). A próxima entrega deve sair de um **teste piloto
presencial** ou de um requisito trazido por torneio real.

## Funcionalidades implementadas

- Cadastro de torneios avulsos, por clube/escola ou por turma.
- Cadastro dos dados do clube.
- Cadastro de membros/socios/alunos/convidados do clube.
- Cadastro de responsáveis, com vínculo a um ou mais membros.
- Listagem de alunos menores de idade sem responsável cadastrado.
- Cadastro de aulas, treinos e eventos do clube por turma.
- Registro de presença, falta e falta justificada por membro.
- Cadastro de planos financeiros e lançamentos por membro.
- Controle de pagamentos pagos, pendentes, atrasados, isentos e cancelados.
- Calendário de eventos do clube, com eventos avulsos e torneios vinculados.
- Indicador de próximos eventos no painel do clube.
- Ranking interno geral e por categoria com rating, aproveitamento e histórico de variação.
- Painel inicial com próximos eventos, resumo financeiro, lideres do ranking
  interno e torneios recentes.
- Pacote administrativo consolidado reunindo clube, presenças, financeiro,
  calendário, torneios e ranking interno.
- Ajuste de tamanho da interface/fonte pela tela `Config. app`.
- Torneios podem ser selecionados, duplicados, excluídos e salvos como novo
  modelo a partir das configurações atuais.
- Cadastro e importação CSV/XLS/XLSX de jogadores, incluindo FIDE ID, CBX ID, LBX ID,
  títulos e ratings nacional/internacional.
- Importação de inscrições por arquivo CSV/XLS/XLSX ou link publicado do
  Google Forms/Sheets em formato CSV.
- Importação de listas oficiais FIDE/CBX em CSV e das listas online LBX para uma base local de ratings.
- Atualização dos jogadores inscritos a partir da base oficial por FIDE ID/CBX ID/LBX ID.
- Inscrição de membros em torneios integrados, filtrando por escopo do torneio.
- Inscrição em massa de membros ativos no torneio selecionado.
- Filtros de membros por tipo de vínculo, status e categoria.
- Histórico de torneios e resultados por membro.
- Relatórios de membro e clube com contatos de responsáveis vinculados,
  frequência, presenças, financeiro, eventos por período, ranking interno e
  pacote administrativo.
- Banco SQLite local na pasta de dados do usuário.
- Geração de primeira rodada por rating.
- Geração de rodadas seguintes por sistema suíço simplificado.
- Controle de bye e tentativa de equilíbrio de cores.
- Opção real para desativar bye, exigindo número par de jogadores ativos.
- Pontos de entrada tardia aplicados automaticamente a novos jogadores depois
  de rodadas fechadas.
- Status de jogador no torneio: ativo, desistente, ausente e não emparceirado.
- Chamada inicial antes da primeira rodada, com marcação de presentes e
  ausentes antes de gerar o emparceiramento.
- Registro de resultados.
- Lançamento rápido de resultados por botões e atalhos de teclado.
- Fechamento de rodada.
- Aviso de número mínimo recomendado de rodadas antes de gerar uma rodada curta
  para a quantidade de jogadores.
- Bloqueio de alteração em rodada fechada, liberado apenas com a flag
  `Permitir mudancas perigosas`.
- Ajuste manual de jogadores em uma mesa antes do fechamento da rodada.
- Ajustes manuais em torneios por equipes, incluindo troca de cores e troca de
  jogador por tabuleiro dentro da equipe.
- Busca de jogadores e filtro de classificação por categoria.
- Configuração avançada de torneios com dados oficiais, regras básicas,
  flags de interface/publicacao (apenas as que fazem alguma coisa: seis opções
  inertes foram removidas) e agenda por rodada com data, hora, **local,
  ritmo e dia de folga**. Reduzir o total de rodadas com agenda preenchida pede
  confirmação e registra auditoria — antes as datas eram apagadas em silêncio.
- Ritmo de jogo entendido também na grafia do edital (`90'+30"`, `90+30`,
  `40/90+30`), pelo mesmo interpretador que alimenta o registro 222 do TRF25 e a
  classificação standard/rapido/blitz do relatório de rating.
- Tolerância de atraso configurável por torneio, exibida no painel do árbitro e
  impressa na súmula de mesa (`0` = perde a hora marcada, o padrão da FIDE).
- Classificação com pontos, Buchholz, Buchholz mediano, Sonneborn-Berger,
  vitórias e performance estimada do jogador.
- Desempates configuráveis por torneio: escolha e ordene os critérios na tela
  `Config. torneio`. Além dos históricos, há Buchholz Cut-1/Cut-2, progressivo,
  progressivo dos adversários, Koya, rating médio dos adversários (ARO/ARO
  cortado), partidas/vitorias com pretas e partidas jogadas. Pontos são sempre o
  critério primário; rating/nome os técnicos finais. Sem configuração, mantém a
  ordem histórica (pontos, Buchholz, Buchholz mediano, Sonneborn-Berger,
  vitórias).
- Exportação de jogadores, classificação, rodada especifica, todas as rodadas e relatório completo em CSV, XLSX e PDF.
- Exportação de site estático em HTML/CSS com dados do torneio, jogadores,
  agenda, rodadas e classificação.
- Súmulas de mesa em PDF para impressão, com grade de lances, dados oficiais,
  resultado e assinaturas.
- Lista de chamada em PDF para impressão, ordenada pelo ranking inicial e com
  coluna de assinatura.
- Folha de emparceiramento de mural em PDF, com QR de envio de resultado para
  cada mesa enquanto a rodada estiver aberta.
- Cartões de mesa em PDF por intervalo configurável, com número em destaque,
  identificação da rodada e QR opcional.
- Tabela cruzada individual por rodada, com adversário, cor, resultado, pontos
  e desempates, exportável em CSV, XLSX, PDF e HTML.
- Tabela cruzada por equipes com adversário, resultado, match points, game
  points e detalhe dos tabuleiros, exportável em CSV, XLSX, PDF e HTML.
- Exportação e validação TRF/FIDE/Chess-Results, com avisos para dados
  oficiais incompletos antes da geração do arquivo `.trf`.
- Auditoria operacional do torneio com snapshots de emparceiramento,
  classificação e correções de resultado.
- Mudança estrutural (ordem inicial, aceleração, sequencia de desempates) com o
  torneio em andamento exige motivo e gera evento de auditoria — antes dava para
  trocar no meio do torneio e a classificação publicada mudava sozinha.
- Torneio marcado como `Arquivado` sai da lista padrão e reaparece com filtro.
- Pré-visualização da próxima rodada antes de gravar o emparceiramento.
- Painel do árbitro com pendências, correções e ações rápidas.
- Lançamento inline de resultados no painel do árbitro, com botões, atalhos e
  seleção automática da próxima mesa pendente.
- Busca direta por número da mesa no painel, inclusive fora do recorte inline.
- Preferências persistidas do painel do árbitro para auto-refresh, intervalo
  entre atualizações e quantidade de mesas exibidas inline.
- Relógio local no painel do árbitro com início, tempo decorrido e duração final
  congelada quando a rodada e fechada.
- Relatório de taxas de rating por torneio, separado por FIDE, CBX e LBX, com
  configuração de valores unitários e exportação XLSX/PDF.
- Relatório de variação de rating FIDE (estimativa de apoio): tabela oficial de
  expectativa com regra dos 400, fator K, Ro, We, ΔElo, Rc e performance (Rp)
  por jogador. Disponível na tela `Relatorios` como `Rating FIDE`, exportável em
  CSV/XLSX/PDF e com snapshot persistido para reimpressão. Não substitui a
  homologação oficial da federação.
  - **Ritmo**: o torneio e classificado em standard, rápido ou blitz pela
    formula da FIDE (tempo + 60 vezes o incremento), e cada ritmo usa a SUA
    lista de rating. Da para declarar o ritmo em `Config. torneio -> Oficial`
    quando o campo de ritmo de jogo não descrever o evento. Faltando o rating do
    ritmo, o relatório usa o standard e AVISA — não troca de lista calado.
  - **Fator K conforme o B.02**: 40 para jogador novo (até 30 partidas, pelo
    campo `Partidas ja ratadas` do jogador), 40 para sub-18 até o fim do ano do
    aniversario com rating abaixo de 2300, 10 a partir de 2400 e 20 no resto,
    com teto de K x n. O relatório mostra o MOTIVO de cada K.
  - **Piso e rating inicial**: Rc abaixo do piso do regulamento sai no piso, com
    aviso; quem ainda não tem rating recebe a estimativa de rating INICIAL do
    B.02 8.2 (dois adversários fictícios de 1800 empatados, teto de 2200, mínimo
    de 5 partidas), com o motivo quando não da para estimar.
  - **Regulamento editável**: as faixas de K, o piso e as regras de estreia são
    DADO, não código. O perfil FIDE vem conferido contra o B.02; o da CBX vem
    com a forma certa e marcado como NÃO conferido — edite os valores em
    `Config. torneio -> Oficial -> Regulamento CBX` conforme o texto vigente, e
    o relatório dirá que os números vieram dali.
- Categorias configuráveis por torneio, na aba `Premiacao` de `Config. torneio`:
  cada linha e uma categoria do edital (nome, tipo idade/rating/sexo/marca,
  faixa e se ela premia). Sem nenhuma linha valem as faixas padrão (Sub-08 a
  Sub-20, S50+/S65+, cortes 1400/1800/2200 e Feminino), e o botão `Usar faixas
  padrão` preenche a lista para voce mexer no que precisar. Em idade o `Ate` e
  INCLUSIVO (Sub-12 aceita quem completa 12) e em rating e EXCLUSIVO (Sub-1400
  recusa 1400), que e como o edital escreve. A idade e a que o jogador COMPLETA
  no ano de referência — configurável em `Data de referencia da idade`. O
  jogador pertence a varias categorias ao mesmo tempo (Sub-10, Sub-1400,
  Feminino), e a classificação por categoria da ata e do pódio sai para todas —
  e assim que a classificação feminina aparece sozinha.
- Distribuição de prêmios em dinheiro: cadastro de prêmios por colocação (geral),
  por categoria, especiais e de tabuleiro na tela `Config. torneio`, com desconto
  de imposto do organizador. A lista sai na tela `Relatorios` como `Premiacao`,
  exportável em CSV/XLSX/PDF.
  - **Prêmio de categoria vale para TODAS as categorias do jogador**: quem e
    Sub-12, Sub-1800 e Feminino concorre aos três. E assim que o prêmio Feminino
    passa a ser alocado sozinho.
  - **Combinação geral × categoria**: `apenas o maior` ou `acumular`. Além
    disso, cada prêmio pode ser marcado como `Soma` e acumular mesmo quando a
    política do torneio e "apenas o maior" — e o caso do prêmio Feminino em
    quase todo edital brasileiro.
  - **Entre empatados**: `dividir por igual` (padrão) ou **Sistema Hort**, em
    que cada empatado recebe 50% do prêmio da própria posição no desempate mais
    50% do bolo dividido por igual. Atenção: até a ORG-02 o rotulo "Sistema
    Hort" nomeava uma combinação geral×categoria que NÃO e o Sistema Hort;
    torneios que o usavam foram convertidos para o rateio de verdade.
  - **Excluir desistentes** da premiação, opcional (o padrão mantém o
    comportamento anterior).
- Estatísticas e fichas no padrão FIDE, na tela `Relatorios`: `Estatistica de
  federações` (jogadores, % e pontos por federacao), `Estatística de partidas`
  (vitórias de brancas/empates/pretas, WO e byes) e `Fichas individuais` (resumo
  por jogador com V/E/D, cores e performance, mais os resultados rodada a
  rodada). Tudo exportável em CSV/XLSX/PDF.
- Assistente de normas/titulos FIDE (estimativa de apoio), na tela `Relatorios`
  como `Normas FIDE`: por jogador, performance, media dos adversários, número de
  federações e de titulados enfrentados, e o veredito por título (GM/IM e, para
  jogadoras, WGM/WIM) com o que falta para atingir. Os indicadores seguem o FIDE
  Handbook B.01, seção 1.4: titulados por nível (a norma de GM exige GMs, não
  titulados quaisquer; CM e WCM não contam), piso de rating ajustado por norma,
  mínimo de duas federações ALÉM da do candidato, teto de 3/5 da federação do
  candidato, 2/3 de uma mesma federação e 20% sem rating. Não concede norma nem
  título (isso é exclusivo da FIDE).
- Certificado `IT3` preenchido, na tela `Relatorios` como `Certificado IT3
  (norma)`: gera em PDF o formulário da FIDE para cada norma detectada, com os
  dados do torneio, do candidato e a tabela de adversários rodada a rodada
  (título, federação, rating usado e resultado), fechando com Ra, Rp e as
  contagens do B.01. Sem norma atingida o programa avisa, em vez de gerar papel
  em branco.
- Formulário de norma de árbitro (IA/FA), na tela `Relatorios`: reúne os dados do
  torneio e os árbitros designados (nome, função, FIDE ID, categoria) como base
  para preencher o formulário oficial FIDE. Documento de apoio, não oficial.
- Editor de colunas da classificação na tela `Config. torneio`: escolha, ordene e
  ajuste a largura das colunas do relatório de classificação (vazio = colunas
  padrão; largura vazia = automática), aplicado a CSV/XLSX/PDF.
- Sistema Scheveningen: cada jogador de um grupo enfrenta todos do outro.
  Selecione `Scheveningen` no método de pareamento em `Config. torneio`. Os
  grupos podem ser atribuídos manualmente (campo `Grupo Scheveningen` na tela de
  jogadores) ou, sem atribuição, caem nas metades por ranking inicial.
- Importação de torneio do Swiss-Manager por arquivo TRF (FIDE/Krause): botão
  `Importar TRF (Swiss-Manager)` na tela de torneios cria um novo torneio com o
  cabeçalho, todos os jogadores (nome, rating, federação, FIDE ID, nascimento) e
  reconstroi as rodadas jogadas (pareamentos e resultados), deixando o torneio
  importado pronto para classificação, tabela cruzada e exportações.
- Desempates por equipes também configuráveis na tela `Config. torneio` (mesma
  edição ordenável dos desempates individuais).
- Mudar método de pareamento e dividir torneio: a troca de pareamento fica
  bloqueada após a primeira rodada; o botão `Dividir` reparte os jogadores em N
  torneios-filho por ranking inicial (A = mais fortes), vinculados ao torneio de
  origem.
- Ponte com o Chess-Results.com (o site não tem API pública de upload): na tela
  de Jogadores, `Publicar no Chess-Results` gera o pacote TRF16 + passos e abre a
  página de registro para envio manual, e `Importar inscricoes Chess-Results` lê
  start lists/inscricoes publicadas em CSV. O link publicado e guardado por torneio.
- Listas de rating estrangeiras: `Importar lista estrangeira` (tela de Jogadores)
  importa federações além de FIDE/CBX/LBX por mapeamento genérico de colunas, com
  registro de federações semeado e extensível pela própria interface.
- Álbum de fotos por FTP: aba `Album/FTP` em Integrações publica uma pasta de
  fotos (com galeria `index.html`) em servidor FTP/FTPS; a senha fica protegida
  (DPAPI) e nunca é exibida.
- Exportação para Access: opção `Access (banco)` no hub de Relatórios gera um
  pacote importável (CSV por tabela + `schema.ini`) e, quando há driver ACE
  instalado, também um `.accdb` real.
- Geração em lote multi-destino: botão `Geracao em lote` no hub de Relatórios
  gera vários relatórios x formatos numa pasta de uma vez, com site HTML e
  impressão opcionais.
- Pré-visualização da atualização oficial dos inscritos com comparação
  antes/depois, lista separada de jogadores sem correspondência e confirmação
  explicita das divergências selecionadas.
- Central de pendências com filtros por decisão, QR, relógio, desempate e correção,
  busca por mesa ou detalhe e contador atualizado.
- Painel do árbitro com **alertas clicáveis** (cada alerta leva direto ao
  contexto: pendências bloqueantes, fechar rodada, aprovar QR, ausentes) e
  **barra de progresso da rodada** (mesas resolvidas / total).
- Pacote da rodada em um clique: gera mural + súmulas + cartões numa pasta de
  uma vez pelo Painel do árbitro (também para torneios por equipes).
- Boletim/press-release da rodada em PDF: resultados da rodada, classificação
  (top 10) e destaques (líder, partidas decididas/empates e maior zebra). Pelo
  Painel do árbitro (rodada atual) ou pelo hub de Relatórios (escolhendo a rodada).
- Poster/diploma do pódio em PDF (A4): top 3 (jogadores ou equipes) e campeões
  por categoria, no Painel do árbitro e no hub de Relatórios.
- Checklist de fechamento da rodada: dialogo com itens OK/pendente e ação por
  item; o botão Fechar rodada só habilita quando tudo está resolvido. Em torneios
  por equipes inclui a checagem de escalacoes/ordem de tabuleiro.
- Ata final do torneio em PDF/XLSX/CSV: documento único de encerramento com
  dados do torneio, classificação final, **vencedores por categoria**, premiação,
  taxas de rating, árbitros e assinaturas (no Painel do árbitro e no hub de
  Relatórios).
- Explicacao/exportacao de desempates com componentes persistidos.
- QR local opcional para submissão de resultado por mesa, sempre com aprovação
  do árbitro antes de alterar a partida.
- Portal live local/publico com dados filtrados para não expor informações
  sensíveis.
- Torneios por equipes com escalações por rodada, reservas e histórico de
  substituições.
- Registro opcional de eventos de relógio, tempo e ausência como alertas para
  o árbitro, sem aplicar resultado automaticamente.
- Geração de diplomas/certificados de torneios em PDF, com modelos
  personalizáveis, logo, cores e tamanhos de fonte por modelo.
- Logs, exportações e backups ficam na pasta de dados do usuário por padrão.

## Manual operacional de arbitragem

O Albericus usa uma regra simples de autoridade: o desktop com o banco SQLite
local e sempre a fonte oficial do torneio. QR, portal live, relógios e
notificações são camadas auxiliares. Elas podem sugerir
ou registrar eventos, mas resultado fechado e alteração crítica dependem do
fluxo normal do árbitro.

Para uso presencial, imprima o
[`Manual Operacional de Arbitragem`](docs/Manual_Operacional_Arbitragem.pdf).
A fonte editável com checklist por rodada e registro de incidentes fica em
[`docs/Manual_Operacional_Arbitragem.md`](docs/Manual_Operacional_Arbitragem.md).

Antes de um piloto presencial ou depois de alterar o painel, rode a simulação
operacional reproduzível:

```powershell
.\.venv\Scripts\python.exe scripts\run_referee_operational_pilot.py --strict
```

O comando gera
[`docs/PILOTO_OPERACIONAL_BASELINE.md`](docs/PILOTO_OPERACIONAL_BASELINE.md) e
o equivalente estruturado em JSON. O ensaio automatizado cobre 121 e 801
jogadores, incluindo criação de backup final e restauração em uma segunda
instalação temporária. Ele também bloqueia a rede em uma instalação isolada e
confirma painel, lançamentos, fechamento, classificação, exportações e backup
locais. Uma rajada concorrente de 20 envios QR também e recebida e aprovada
pela fila do árbitro. O cadastro de última hora também e medido depois de uma
rodada fechada, incluindo atualização da lista, classificação e prévia seguinte.
A conferência oficial antes da rodada 1 valida importação local, comparação sem
persistência e confirmação seletiva. O checklist presencial continua necessário
para avaliar impressora, rede local, legibilidade, quantidade de cliques e o
computador físico reserva.

### Antes do torneio

1. Crie ou carregue o torneio e confira nome, local, datas, ritmo, quantidade
   de rodadas, perfil FIDE e dados do árbitro.
2. Importe jogadores por CSV/XLS/XLSX, Google Forms/Sheets publicado em CSV,
   base local de membros ou cadastro manual.
3. Compare e confirme os ratings oficiais quando houver lista FIDE/CBX/LBX importada.
4. Use a chamada inicial na tela de rodadas antes da primeira rodada para
   marcar presentes e ausentes.
5. Gere um backup manual ou confirme que a pasta de backups está configurada em
   `Config. app`.
6. Para torneios oficiais, rode `Validar TRF FIDE` antes da primeira rodada para
   identificar dados ausentes com antecedência.

### Durante o torneio

1. Use `Pre-visualizar proxima rodada` quando quiser revisar alertas de bye,
   cor, repetição ou float antes de gravar.
2. Depois de gerar a rodada, imprima/exporte a rodada ou publique o portal live
   quando necessário.
3. Registre resultados pelo desktop. O QR por mesa pode receber submissão, mas
   o resultado só entra na partida depois de aprovado.
4. Feche a rodada apenas quando não houver pendências. O fechamento grava
   snapshot de classificação e auditoria.
5. Se precisar corrigir resultado de rodada fechada, habilite explicitamente
   mudanças perigosas e registre o motivo.
6. Eventos de relógio, ausência e plugins de hardware entram como alerta. Eles
   não definem WO, queda de seta ou resultado sem decisão do árbitro.

### Depois do torneio

1. Confira classificação, desempates e relatório de auditoria.
2. Exporte classificação, rodadas, PGN, site HTML ou pacote completo conforme
   a necessidade.
3. Gere `Pendencias TRF` e depois o arquivo `Chess-Results (TRF16)` quando o
   torneio precisar de envio federativo.
4. Gere diplomas/certificados se aplicável.
5. Mantenha o backup final junto dos arquivos exportados do torneio.

### Recursos opcionais

- **Portal live:** publica dados do torneio em modo público ou restrito; dados
  sensíveis ficam fora do modo público.
- **QR local:** facilita coleta de resultados, mas toda submissão exige revisão.
- **Dispositivos/relogios:** registram `clock_events` e alertas de anomalia; o
  árbitro continua responsável pela decisão.
- **Notificações:** são opcionais e auditadas. Sem configuração ativa, são
  registradas como ignoradas.

### Checklist de segurança operacional

Cobre as áreas críticas: backup, jogadores, rodadas, auditoria, TRF e
publicação.

- **Backup:** pasta de backups configurada e testada; backup manual antes da
  primeira rodada e backup final arquivado junto das exportações.
- **Jogadores:** presentes conferidos na chamada inicial antes da primeira
  rodada.
- **Rodadas:** rodada anterior fechada antes de gerar a próxima; pendências e
  alertas revisados no painel do árbitro.
- **Auditoria:** relatório de auditoria do torneio conferido; correções em
  rodada fechada feitas com motivo registrado.
- **TRF:** configurações oficiais revisadas e `Pendencias TRF` sem bloqueios
  antes de gerar o `Chess-Results (TRF16)`, quando aplicável.
- **Publicação:** portal live / site HTML revisado para não expor dados
  sensíveis no modo público.

### Próximos incrementos

Backlog restante do roadmap de arbitragem (detalhes em
`ROADMAP_ARBITRAGEM_XADREZ.md`). Nenhum deles altera as regras de
emparceiramento ou os resultados já existentes:

- **Notificações em massa/agendadas:** disparo de avisos de rodada e cobrança a
  partir do `MessageService` (hoje o envio e manual, um a um).
- **Plugin de relógio de hardware real:** a interface de plugins já existe (só o
  registro manual está implementado); um plugin especifico entra sob demanda.
- **Aceleração de Baku por equipes:** o Baku individual (FIDE C.04.7) esta
  implementado no pareamento e no TRF (registro 250 e sufixo `_BAKU`); o
  pareamento por equipes ainda não aplica aceleração.
- **Submissão automática a federação:** fora de escopo enquanto não houver API
  publica utilizável; o fluxo atual gera o arquivo TRF para upload manual.

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

Por padrão, o Albericus grava banco, logs, backups e exportações na pasta de
dados do usuário:

- Windows: `%LOCALAPPDATA%\Albericus`
- macOS: `~/Library/Application Support/Albericus`
- Linux: `$XDG_DATA_HOME/Albericus` ou `~/.local/share/Albericus`

Para usar uma pasta especifica, defina `ALBERICUS_DATA_DIR` antes de iniciar o
programa. Se existir um banco legado em `data/albericus.db` e a nova pasta ainda
não tiver banco, ele será copiado automaticamente na primeira abertura; backups
legados também são copiados quando a nova pasta de backups ainda estiver vazia.

## Testes

```bash
python -m unittest discover -s tests
```

## Checagens de qualidade

As dependências de desenvolvimento ficam no extra `dev`.

```bash
uv sync --extra dev
.\scripts\check_quality.ps1
```

O script compila os módulos, roda `ruff`, `mypy` e a suite de testes.

Ferramentas de qualidade do código (ub-mode):

```bash
uv run --extra dev coverage run -m pytest tests/test_x.py
uv run --extra dev coverage json -o coverage.json
uv run --extra dev python scripts/crap.py coverage.json src/services/x.py   # CRAP por função; meta < 10
uv run --extra dev python scripts/dry.py src/services/x.py                  # funções duplicadas; meta < 0,8
uv run --extra dev python scripts/mutate.py src/services/x.py -- tests/test_x.py  # teste de mutação
```

## Limpeza de artefatos

Use este script para remover caches Python, caches das ferramentas e saídas de
build. Ele preserva `.venv`, `data/`, `backups/`, `logs/` e `exports/` locais.

```bash
.\scripts\clean_artifacts.ps1
```

## Plano de evolução: gerenciador de clube de xadrez

O objetivo da próxima fase é transformar o Albericus de um aplicativo focado em
torneios para um gerenciador completo de clube de xadrez, mantendo o módulo de
torneios integrado ao cadastro do clube.

### Visão do produto

O sistema deve passar a gerenciar:

- Cadastro e configurações do clube.
- Jogadores, sócios, alunos e convidados.
- Responsáveis por jogadores menores de idade.
- Mensalidades e pagamentos simples.
- Aulas, treinos e controle de presença.
- Calendário de eventos do clube.
- Ranking interno e histórico de partidas.
- Torneios com inscrição a partir do cadastro do clube.
- Relatórios administrativos, esportivos e financeiros.
- Torneios sem limite fixo de jogadores ou quantidade de eventos, limitado apenas pela maquina e pelo banco local.
- Publicação web simples de emparceiramentos, resultados, informações do torneio e classificação final.
- Banco de dados de jogadores com busca por IDs FIDE/CBX e atualização de ratings oficiais quando houver fonte disponível.
- Cálculo de desempenho do jogador e uso de ratings gerados em torneios anteriores para inscrições futuras.

### Módulos planejados

#### Clube

- Nome, cidade, endereço, telefone, e-mail e observações.
- Configurações padrão do clube.
- Categorias usadas pelo clube.
- Tipos de vínculo: sócio, aluno, convidado, visitante e inativo.
- Futuramente, suporte a logo e identidade visual nos relatórios.

#### Jogadores, sócios e alunos

- Expandir o cadastro atual de jogadores.
- Campos novos: telefone, e-mail, documento, data de nascimento, responsável,
  status de matricula e observações.
- Campos esportivos: sobrenome, nome, título, sexo, FIDE ID, CBX ID, rating
  nacional, rating internacional, federação, clube, escola/turma e categoria.
- Busca por jogador usando nome, FIDE ID ou CBX ID.
- Importação e atualização de dados oficiais de jogadores, quando houver arquivo
  ou fonte confiável da FIDE/CBX.
- Separar o conceito de membro do clube do conceito de participante de torneio.
- Permitir que um membro seja inscrito em vários torneios.
- Permitir convidados externos em torneios sem transforma-los em sócios.
- Exibir histórico do jogador com torneios, presenças, pagamentos e ranking.

#### Escolas e turmas

- Avaliar cadastro de escolas, turmas e professores/instrutores.
- Vincular alunos a escola e turma.
- Usar escola/turma como filtro em membros, inscrições, presenças e relatórios.
- Manter o módulo opcional para não complicar clubes que não trabalham com turmas.

#### Torneios avançados

- Campos de configuração inspirados em Swiss-Manager e SwissSystem:
  denominação, FIDE Event-ID, organizador, página web, e-mail, ritmo,
  diretor do torneio, árbitro principal, árbitros auxiliares, federação,
  estado, local, comentários, premiação, categorias, data de corte e tipo de
  torneio real/teste.
- Agenda de rodadas com data e horário por rodada.
- Configuração de ordenação inicial: rating nacional, rating internacional,
  rating internacional depois nacional, maior rating entre nacional e
  internacional, ou ordem manual.
- Configuração de cor inicial e política de emparceiramento quando aplicável.
- Pontos de bye configuráveis e controle de tchau/bye.
- Regras para adesão tardia, incluindo pontos por entrada depois da primeira
  rodada quando o regulamento permitir.
- Suporte futuro a sistema acelerado.
- Classificação intermediaria e final com critérios de desempate configuráveis.
- Desempates planejados: confronto direto, Buchholz variável, Buchholz mediano,
  Sonneborn-Berger, número de vitórias, número de partidas de pretas,
  progressivo, media de rating dos adversários, Koya e performance.
- Cálculo de desempenho/performance do jogador no torneio para acompanhar a
  evolução dos alunos.
- Copiar configurações de um torneio anterior para criar novo evento.
- Flags de publicação e interface: ocultar classificação temporariamente,
  mostrar adversários na classificação, ocultar nomes de cores e arquivar
  torneio.
- Controles de edição: permitir ou bloquear inscrição publica de jogadores,
  alteração de resultados pelos jogadores e mudanças perigosas.
- Emparceiramento manual completo antes de confirmar a rodada.
- Exclusão de rodadas geradas antes do fechamento e bloqueio de exclusão de
  rodadas fechadas sem ação administrativa explicita.
- Jogador desistente durante o torneio deve continuar na lista de inscritos,
  aparecer como não emparceirado e deixar de ser pareado nas rodadas seguintes,
  mantendo histórico e resultados anteriores.
- Resultados de WO devem continuar disponíveis para vitória por ausência,
  derrota por ausência e dupla ausência.
- Lista de classificação final obrigatória em relatórios e exportações.

#### Publicação web e exportações

- Exportar emparceiramentos, resultados, classificação e informações do torneio
  em HTML/CSS para publicar em uma página simples.
- Gerar pacote estático local pronto para hospedagem.
- Exportar `Chess-Results (TRF16)` para o fluxo FIDE/Swiss-Manager/Chess-Results,
  com cabeçalho do torneio, jogadores, equipes quando aplicável, dados oficiais,
  pontos, classificação e resultados por rodada.
- Validar a exportação TRF16 antes de gravar, bloqueando dados estruturais
  ausentes e exibindo avisos para FIDE ID, federação, rating, nascimento,
  árbitro-chefe, ritmo e datas de rodadas incompletas.
- Manter `PGN (Partidas)` como exportação complementar para partidas/resultados.
- Manter exportações em CSV, XLSX e PDF.
- Futuramente, permitir configuração de página publica do clube ou torneio.

#### Responsáveis

- Cadastro de responsáveis para crianças e adolescentes.
- Nome, telefone, e-mail e relação com o jogador.
- Observações administrativas.
- Vínculo de um responsável a um ou mais jogadores.

#### Financeiro simples

- Cadastro de planos: mensal, avulso, bolsista, isento ou personalizado.
- Registro de pagamentos por membro.
- Status financeiro: em dia, pendente, atrasado ou isento.
- Relatório por período.
- Resumo mensal de recebimentos e pendências.
- Geração em lote de mensalidades por plano, competência e vencimento.
- Exportação de recibos simples para lançamentos pagos ou isentos.

#### Aulas e treinos

- Cadastro de sessões de aula ou treino.
- Data, horário, professor/instrutor e observações.
- Lista de presença.
- Histórico de frequência por aluno.
- Relatório de presenças por período.

#### Calendário de eventos

- Eventos do clube: aulas, torneios, reuniões, simultâneas, viagens e encontros.
- Status: planejado, confirmado, concluído ou cancelado.
- Integração com torneios cadastrados.
- Visão de próximos eventos.

#### Ranking interno

- Rating interno do clube.
- Histórico de partidas e resultados.
- Aproveitamento por jogador.
- Integração opcional com resultados dos torneios internos.
- Atualização do rating interno com base nos ratings gerados por torneios
  anteriores, para sugerir rating na inscrição do próximo torneio.
- Relatório de evolução do jogador.

#### Torneios integrados

- Manter o módulo atual de torneios.
- Inscrever jogadores a partir do cadastro de membros.
- Permitir jogadores convidados externos.
- Salvar histórico do torneio no perfil do jogador.
- Usar resultados de torneios internos no ranking do clube, quando configurado.
- Continuar exportando jogadores, rodadas, classificação e relatório completo.
- Importar membros ativos em lote e manter convidados externos separados do
  cadastro completo do clube.
- Integrar ratings oficiais e rating interno na inscrição de torneios.
- Publicar emparceiramentos e classificação em página HTML/CSS.

### Mudanças técnicas planejadas

#### Organização do código

Reorganizar gradualmente o projeto por domínios:

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

Essa reorganização deve ser incremental para evitar quebrar o módulo de torneios
já implementado.

#### Banco de dados

Novas tabelas propostas:

- `clubs`: dados do clube.
- `members`: sócios, alunos, jogadores e convidados.
- `guardians`: responsáveis.
- `member_guardians`: vínculo entre membros e responsáveis.
- `membership_plans`: planos de mensalidade.
- `payments`: pagamentos e mensalidades.
- `training_sessions`: aulas e treinos.
- `attendance`: presenças.
- `club_events`: calendário de eventos.
- `exercise_library`: biblioteca de exercícios e posições.
- `training_lists`: listas de treino por clube/turma.
- `training_list_exercises`: exercícios vinculados a listas.
- `exercise_attempts`: tentativas e histórico de estudos por aluno.
- `inventory_items`: materiais, livros e equipamentos.
- `inventory_loans`: empréstimos de materiais para membros.
- `inventory_maintenance`: manutenções e reparos dos materiais.
- `audit_log`: auditoria local de operações sensíveis.
- `tournament_registrations`: inscrições em torneios.
- `internal_rating_history`: histórico de rating interno.
- `schools`: escolas parceiras ou locais de aula.
- `classes`: turmas/aulas vinculadas a escolas ou ao clube.
- `member_class_enrollments`: vínculo entre alunos e turmas.
- `player_external_ids`: IDs oficiais do jogador, como FIDE e CBX.
- `official_rating_snapshots`: listas importadas de rating FIDE/CBX por data.
- `tournament_settings`: configurações avançadas do torneio.
- `round_schedule`: data e horário de cada rodada.
- `tournament_publications`: histórico de exportações HTML/CSS publicadas.
- `player_performances`: desempenho calculado por jogador em cada torneio.

Tabelas atuais que devem ser preservadas:

- `tournaments`
- `players`
- `rounds`
- `pairings`

O caminho recomendado e ligar `players` a `members` por meio de uma coluna
opcional `member_id`, mantendo compatibilidade com torneios antigos.

#### Migrações

- Criar um controle simples de versão do banco.
- Aplicar migrações automaticamente ao abrir o aplicativo.
- Preservar dados existentes em `data/albericus.db` ao migrar para a pasta de dados do usuário.
- Fazer backup antes de migrações estruturais.

### Roadmap de implementação

#### Etapa 1: Base de clube

1. Criar tabela `clubs`.
2. Criar tela de configurações do clube.
3. Criar menu inicial com visão geral do clube.
4. Mostrar indicadores básicos: membros ativos, torneios recentes e próximos eventos.
5. Manter acesso ao módulo de torneios atual.

#### Etapa 2: Membros do clube

1. Criar tabela `members`.
2. Criar tela de cadastro completo de membros.
3. Adicionar busca e filtros por status, categoria e tipo de vínculo.
4. Criar status: ativo, inativo, visitante, convidado e desistente.
5. Criar ação para inscrever membro em torneio.
6. Manter cadastro rápido de convidado externo para torneios.

#### Etapa 3: Integração com torneios

1. Adicionar `member_id` opcional aos jogadores de torneio.
2. Permitir importar jogadores de um torneio a partir dos membros ativos.
3. Permitir convidado externo sem cadastro completo.
4. Registrar torneios jogados no histórico do membro.
5. Exibir resultados de torneios no perfil do jogador.

#### Etapa 4: Responsáveis

1. Criar tabela `guardians`.
2. Criar vínculo entre responsáveis e membros.
3. Exibir contatos do responsável no perfil do aluno.
4. Permitir filtro de alunos menores de idade.

#### Etapa 5: Aulas, treinos e presença

1. Criar cadastro de sessões de treino.
2. Criar tela de chamada.
3. Registrar presença, falta e justificativa.
4. Exibir frequência por aluno.
5. Exportar relatório de presença.

#### Etapa 6: Financeiro simples

1. Criar planos de mensalidade.
2. Registrar pagamentos.
3. Calcular status financeiro por membro.
4. Exibir pendências do mês.
5. Exportar relatório financeiro em CSV, XLSX e PDF.

#### Etapa 7: Calendário

1. Criar tabela de eventos.
2. Criar tela de calendario/listagem.
3. Integrar torneios ao calendário.
4. Mostrar próximos eventos no painel inicial.

#### Etapa 8: Ranking interno

1. Criar modelo de rating interno.
2. Definir se torneios internos afetam o ranking.
3. Registrar histórico de alterações.
4. Exibir ranking geral e por categoria.
5. Exibir evolução individual.

#### Etapa 9: Relatórios

1. Relatório geral do clube.
2. Relatório individual de membro.
3. Relatório de presenças.
4. Relatório financeiro.
5. Relatório de torneios por período.

#### Etapa 10: Acabamento e distribuição

1. Melhorar dashboard inicial.
2. Criar configurações do aplicativo.
3. Melhorar backups e restauração.
4. Criar ícone do aplicativo.
5. Empacotar com PyInstaller.

### Roadmap adicional a partir da conversa do PDF

#### Configuração avançada de torneio

1. Criar tela de configuração completa do torneio com abas semelhantes a:
   geral, desempates, listagens/publicacao, tabuleiros, FIDE e árbitros.
2. Adicionar campos de evento: FIDE Event-ID, organizador, site, e-mail,
   diretor, árbitro principal, árbitros auxiliares, federação, estado, local,
   comentários, premiação, categorias e data de corte.
3. Criar agenda de rodadas com data e horário por rodada.
4. Permitir copiar dados e configurações de um torneio anterior.
5. Separar torneio real de torneio de teste.

#### Cadastro e dados oficiais de jogadores

1. Ampliar cadastro com sobrenome, nome, título, sexo, data de nascimento,
   FIDE ID, CBX ID, rating nacional, rating internacional, federação,
   clube, escola e turma.
2. Criar banco único de jogadores para reaproveitar inscrições entre clubes,
   eventos e torneios.
3. Implementar busca por FIDE ID e CBX ID.
4. Importar listas oficiais FIDE/CBX a partir de arquivo local quando a busca
   direta não estiver disponível.
5. Atualizar rating de jogadores inscritos usando a lista oficial mais recente.

#### Operação de torneio

1. Completar emparceiramento manual, com troca de jogadores, troca de cores e
   ajuste de mesa antes da confirmação.
2. Permitir exclusão de rodadas geradas ainda não fechadas.
3. Tratar desistências sem remover o jogador da inscrição: manter na lista,
   marcar como desistente/nao emparceirado e preservar histórico anterior.
4. Continuar aceitando resultados de WO: 1F-0F, 0F-1F e 0F-0F.
5. Exibir classificação intermediaria e classificação final obrigatória.
6. Adicionar configurações para inscrição tardia, pontos por entrada tardia,
   bye/tchau, sistema acelerado e mudanças perigosas.

#### Desempenho, rating e evolução

1. Calcular performance/desempenho do jogador por torneio.
2. Salvar desempenho no histórico do membro.
3. Atualizar o rating interno do clube a partir dos resultados dos torneios.
4. Usar o rating atualizado de torneios anteriores como sugestão automática na
   inscrição de torneios novos.
5. Gerar relatório de evolução por aluno com rating, performance e resultados.

#### Publicação web

1. Exportar site estático em HTML/CSS com dados do torneio.
2. Publicar emparceiramentos por rodada.
3. Publicar resultados, lista de inscritos, jogadores não emparceirados e
   classificação final.
4. Prever uma opção futura de página publica do clube ou do torneio.

#### Escolas e turmas

1. Avaliar se o cadastro de escolas e turmas deve entrar antes ou depois do
   financeiro.
2. Criar escolas e turmas como módulo opcional.
3. Usar escola/turma para filtro de alunos, inscrições, presenças e relatórios.

### Prioridade recomendada

A prioridade inicial deve ser:

1. Criar `clubs`.
2. Criar `members`.
3. Integrar `members` com torneios.
4. Completar configuração avançada de torneio e agenda de rodadas.
5. Ampliar cadastro/busca de jogadores com FIDE ID, CBX ID e ratings oficiais.
6. Implementar publicação HTML/CSS de emparceiramentos e classificação.
7. Calcular desempenho do jogador e atualizar rating interno entre torneios.

As três primeiras entregas criam a base do gerenciador de clube sem comprometer
o emparceiramento que já funciona. As demais incorporam as melhorias pedidas na
conversa do PDF.

### Primeira fatia implementada

- Tabela `clubs` criada.
- Tabela `members` criada.
- Coluna opcional `players.member_id` criada por migração automática.
- Tela `Clube` adicionada com dados cadastrais e indicadores básicos.
- Tela `Membros` adicionada com cadastro, edição, busca e ativacao/inativacao.
- Tela `Jogadores` atualizada para inscrever membros ativos no torneio selecionado.
- Cadastro manual de jogadores continua disponível para convidados externos.
- Testes automatizados cobrem criação de membro, inscrição no torneio e migração de banco antigo.

### Segunda etapa implementada

- Status de membros ampliados para: ativo, inativo, visitante, convidado e desistente.
- Tela `Membros` agora possui filtros por tipo de vínculo, status e categoria.
- As categorias do filtro são carregadas automaticamente a partir dos membros cadastrados.
- Apenas membros com status ativo aparecem na inscrição automática de torneios.
- Visitantes, convidados e desistentes ficam fora da inscrição automática, mas convidados externos ainda podem ser adicionados manualmente na tela `Jogadores`.
- Botão de cadastro manual na tela `Jogadores` foi renomeado para `Adicionar convidado`.
- Testes automatizados cobrem os novos status e a elegibilidade para inscrição em torneios.

### Terceira etapa implementada

- Tela `Jogadores` permite inscrever todos os membros ativos ainda não inscritos no torneio selecionado.
- Convidados externos continuam sendo cadastrados diretamente no torneio, sem cadastro completo como membro.
- Tela `Membros` exibe histórico de torneios do membro selecionado com pontos, posição, rodadas jogadas e resumo V/E/D/B.
- Duplo clique no histórico do membro mostra os resultados rodada a rodada daquele torneio.
- O histórico e derivado da coluna `players.member_id`, preservando compatibilidade com torneios antigos.
- Testes automatizados cobrem inscrição em massa e resumo de resultados por membro.

### Quarta etapa implementada

- Tabelas `tournament_settings` e `round_schedule` criadas com migração automática.
- Tela `Config. torneio` adicionada para editar dados gerais, dados oficiais, flags de regras/interface e agenda das rodadas.
- Cadastro de jogadores ampliado com sobrenome, nome próprio, título, sexo, FIDE ID, CBX ID, rating nacional, rating internacional e nascimento.
- Importação CSV aceita colunas oficiais como `fide`, `cbx`, `rating_nacional`, `rating_internacional`, `titulo`, `sexo` e `sobrenome`.
- Classificação calcula uma performance estimada do jogador com base nos ratings dos adversários e no resultado obtido.
- Exportação `Site HTML` gera `index.html` e `styles.css` com informações do torneio, agenda, lista de jogadores, rodadas e classificação.
- Exportações de relatório passam a incluir dados oficiais do torneio, agenda e campos oficiais dos jogadores.
- Testes automatizados cobrem configurações de torneio, agenda, campos oficiais, importação CSV ampliada, migração e exportação HTML.

### Quinta etapa implementada

- Colunas `players.player_status` e `players.starting_points` criadas com migração automática.
- Jogador desistente, ausente ou não emparceirado permanece na lista de inscritos e na classificação, mas não entra nas próximas rodadas.
- Pontos por adesão tardia configurados no torneio são aplicados automaticamente quando um jogador entra após rodadas fechadas.
- Flag `Desativar bye/tchau` agora impede gerar rodada com número ímpar de jogadores ativos.
- Alterar resultado de rodada fechada agora exige a flag `Permitir mudancas perigosas`.
- Jogador cadastrado por engano pode ser excluído enquanto ainda não apareceu em nenhuma rodada.
- Exclusão e bloqueada quando o jogador já tem emparceiramento; nesses casos deve-se usar `Desistente` ou `Nao emparceirado`.
- Exportação HTML e relatórios passam a mostrar status real do jogador no torneio.
- Testes automatizados cobrem desistência, entrada tardia, bye desativado e bloqueio de alteração perigosa.

### Sexta etapa implementada

- Tabelas `official_rating_snapshots` e `official_players` criadas com migração automática.
- Tela `Jogadores` recebeu ações para importar listas `FIDE` e `CBX` em CSV.
- Cada importação oficial salva um snapshot com fonte, arquivo, data da lista e quantidade importada.
- Atualização de ratings oficiais usa FIDE ID e CBX ID para localizar o jogador na base importada.
- Quando há dados FIDE e CBX para o mesmo jogador, o sistema combina os campos: título, sexo, federação e rating internacional da FIDE; clube e rating nacional da CBX.
- O rating principal do jogador e recalculado conforme a ordem inicial configurada no torneio.
- Jogadores sem correspondência oficial são reportados ao usuário sem bloquear os demais.
- Testes automatizados cobrem importação oficial, atualização combinada FIDE/CBX, ordem inicial de rating e migração das novas tabelas.

### Sétima etapa implementada

- Tabela `internal_rating_history` criada com migração automática e backup antes de alterar bancos antigos.
- Tela `Classificacao` recebeu a ação `Atualizar rating interno`, que usa a performance calculada no torneio para atualizar o rating do membro.
- A atualização e idempotente por membro, torneio e jogador, evitando aplicar o mesmo torneio duas vezes por acidente.
- O novo rating interno fica salvo em `members.rating` e passa a ser usado automaticamente ao inscrever o membro em torneios seguintes.
- Tela `Membros` recebeu consulta de histórico de rating interno para o membro selecionado.
- Testes automatizados cobrem criação do histórico, atualização do membro, idempotência, uso do rating no torneio seguinte e migração da nova tabela.

### Oitava etapa implementada

- Relatório de evolução por membro/aluno criado com dados cadastrais, resumo por torneio, histórico de rating interno e resultados rodada a rodada.
- Exportação disponível na tela `Membros` pelo botão `Exportar evolucao`.
- O relatório pode ser gerado em CSV, XLSX ou PDF usando a mesma infraestrutura de exportação do módulo de torneios.
- O resumo por torneio mostra rating de inscrição, pontos, posição, performance, variação de rating interno e placar V/E/D/B.
- Testes automatizados cobrem a geração do relatório com rating, performance e resultados.

### Nona etapa implementada

- Tela `Relatorios` adicionada para gerar relatórios administrativos sem depender de um torneio selecionado.
- Relatório geral do clube exporta perfil, indicadores, membros por status/tipo/categoria, ranking interno e torneios cadastrados.
- Relatório individual de membro reutiliza a evolução do aluno com dados cadastrais, torneios, rating interno e resultados rodada a rodada.
- Relatório de torneios por período permite filtrar por data inicial/final e inclui resumo operacional e top 10 de cada torneio.
- Todos os novos relatórios usam CSV, XLSX ou PDF.
- Testes automatizados cobrem o relatório geral do clube e o filtro de torneios por período.

### Décima etapa implementada

- Dashboard inicial do clube ampliado com cards de backup, atalhos operacionais e lista dos últimos torneios.
- Tabela `app_settings` criada para salvar preferências locais do aplicativo.
- Tela `Config. app` adicionada para alterar aparência, pasta padrão de exportação e pasta de backups.
- Backups agora podem ser listados, criados manualmente e restaurados pela interface, com copia de segurança antes da restauração.
- Ícone do aplicativo criado em `assets/app_icon.svg` e `assets/app_icon.ico`.
- Arquivo `albericus.spec` e script `scripts/build_windows.ps1` adicionados para empacotar o aplicativo com PyInstaller.
- Testes automatizados cobrem preferências do aplicativo, backup/restauracao e migração da nova tabela.

### Melhoria: clubes, escolas e turmas

- O cadastro de `clubs` deixa de representar apenas um clube fixo e passa a aceitar varias unidades.
- Cada unidade pode ser classificada como clube, escola, projeto ou parceiro.
- Escolas e clubes podem ter varias turmas vinculadas por meio da tabela `classes`.
- Alunos/membros podem ser vinculados a uma turma ativa por meio de `member_class_enrollments`, preservando histórico de troca de turma.
- A tela `Clube` passa a permitir criar, editar, ativar/inativar unidades e cadastrar turmas da unidade selecionada.
- A tela `Membros` passa a salvar e filtrar por clube/escola e turma.
- Torneios podem ser avulsos, vinculados a uma unidade ou vinculados a uma turma.
- A inscrição automática usa todos os membros ativos no torneio avulso, os membros da unidade no torneio de clube/escola e apenas os alunos da turma no torneio de turma.
- Relatórios passam a incluir clube/escola e turma, permitindo acompanhar alunos por unidade.
- A migração preserva os dados existentes vinculando registros antigos ao clube padrão `id = 1`.

### Modo Amistoso (escolar)

O "Modo Amistoso" é o que o app chama de **Modo Livre** (menu "Torneio | Livre"). É para eventos casuais, escolares ou treinos. Revisão completa em `ROADMAP_REVISAO_MODO_AMISTOSO.md` e `ESPEC_REVISAO_MODO_AMISTOSO.md`.

O que o modo faz:

- **Cria o torneio em um passo.** O professor informa nome, rodadas e, se quiser, a turma: os alunos ativos dela já entram. O preset grava 0,5 ponto por rodada perdida.
- **Aceita aluno que chega depois.** Ele pode jogar já na rodada em andamento (ela é refeita com ele) ou esperar a próxima. Começa com 0,5 ou zero por rodada perdida, pelo mesmo plano do assistente "Entrada tardia…".
- **Refaz a rodada aberta com quem está presente** ("Re-emparceirar"). Apagar e gerar de novo é um passo só: se a geração falha, a rodada original continua lá. Com resultado anotado ou envio por QR pendente, o professor diz o motivo, e tudo fica na auditoria.
- **Oferece mais uma rodada** quando as rodadas acabaram e sobrou tempo.
- **Imprime súmula sem W.O. automático por atraso**, quando o torneio não tem tolerância configurada.
- **Liga e desliga em Configurações → Avançado**, com auditoria.

O que o modo não faz:

- Não troca o motor: o emparceiramento continua o holandês (Gacrux).
- Não vale rating FIDE nem CBX. O perfil FIDE-rated é recusado, e o TRF16 em modo submissão também. O arquivo de trabalho sai com aviso.
- Rating interno do clube: antes de o torneio amistoso contar, o app pergunta ("Contar no rating" ou "Não contar").
- O rating interno do clube continua contando, com aviso (decisão pendente D2).

### Gerador de diplomas - Etapa 1 implementada

- Tela `Diplomas` adicionada para torneios individuais.
- Modelos fixos disponíveis: participação, premiação geral e premiação por categoria.
- Destinatários podem ser todos os jogadores, top N geral, top N por categoria
  ou jogadores selecionados na lista.
- Cada diploma e gerado como uma página em PDF paisagem, dentro de um único arquivo.
- Os dados são preenchidos automaticamente com nome do jogador, torneio, local,
  período, pontos, posição geral e posição na categoria.
- Torneios por equipes ficam preparados para uma etapa futura do gerador.

### Gerador de diplomas - Etapa 2 implementada

- Tabela `certificate_templates` criada com migração automática.
- Modelos padrão de participação, premiação geral e premiação por categoria
  são cadastrados automaticamente.
- A tela `Diplomas` permite editar e salvar nome do modelo, tipo, orientação,
  título, texto principal, rodapé e assinaturas.
- Também é possível salvar um modelo existente como novo modelo personalizado.
- A geração do PDF usa o texto do modelo editado, com variáveis como
  `{nome}`, `{torneio}`, `{local}`, `{periodo}`, `{posicao}`, `{categoria}`,
  `{posicao_categoria}`, `{pontos}`, `{rating}` e `{clube}`.
- Orientação paisagem e retrato são suportadas na emissão do PDF.
- A tela exibe um preview simples do título renderizado para o primeiro
  destinatário encontrado.

### Gerador de diplomas - Etapa 3 implementada

- Modelos de diploma passaram a salvar identidade visual própria.
- Cada modelo pode definir logo, cor principal, cor de destaque e tamanhos de
  fonte para título, texto principal e rodapé.
- A tela `Diplomas` recebeu campos para editar esses dados visuais e escolher
  um arquivo de logo local.
- A geração do PDF aplica as cores do modelo na moldura, linha de destaque,
  título e assinaturas.
- O logo e desenhado no topo do diploma quando informado e validado.
- Os modelos antigos são migrados automaticamente com valores visuais padrão.

### Gerador de diplomas - Etapa 4 implementada

- A tela `Diplomas` passa a escolher o contexto da emissão: torneio,
  membros/alunos, aula/turma, evento ou ranking interno.
- Novos modelos padrão são cadastrados para membro/aluno, aula/turma, evento
  e ranking interno.
- A geração em PDF agora aceita destinatários vindos do cadastro de membros,
  da lista de presença de aulas, de eventos vinculados a uma unidade e do
  ranking interno.
- A lista da tela muda automaticamente conforme o contexto e permite gerar
  diplomas para todos, top N quando aplicável ou destinatários selecionados.
- Novas variáveis de modelo incluem `{turma}`, `{aula}`, `{evento}`,
  `{instrutor}`, `{professor}`, `{tipo}`, `{status}`, `{nivel}`, `{delta}`,
  `{jogos}`, `{desempenho}`, `{aproveitamento}`, `{vitorias}`, `{empates}`,
  `{derrotas}` e `{ultimo_torneio}`.

### Gerador de diplomas - Etapa 5 implementada

- Cada diploma emitido passa a receber um código único de verificação.
- O código e impresso no PDF e fica disponível nas variáveis `{codigo}`,
  `{codigo_verificacao}`, `{emissao}` e `{emitido_em}`.
- A tabela `certificate_issuances` registra histórico de emissão com contexto,
  origem, destinatário, modelo usado, arquivo gerado e status.
- A tela `Diplomas` exibe as emissões recentes e permite consultar um diploma
  pelo código de verificação.
- A migração para a versão 7 cria o histórico automaticamente e preserva os
  modelos existentes.

### Gerador de diplomas - fundos e identidade visual

- Modelos de diploma aceitam imagem de fundo, opacidade do fundo, logo
  principal e logo secundário.
- A tela `Diplomas` permite selecionar arquivos `.png`, `.jpg` ou `.jpeg`
  para esses elementos visuais.
- Fundos padrão de xadrez ficam em `assets/certificates/backgrounds/`:
  `tabuleiro_sutil.png`, `xadrez_classico.png`, `xadrez_escolar.png`,
  `xadrez_premium.png` e `pecas_marca_dagua.png`.
- Logos padrão em PNG transparente ficam em `assets/certificates/logos/`:
  `albericus_knight.png`, `clube_rook.png`, `escola_pawn.png`,
  `torneio_trophy.png` e `selo_queen.png`.
- Novos modelos prontos com esses fundos são cadastrados automaticamente,
  mantendo os modelos antigos como opções simples.
- Os fundos podem ser recriados com
  `uv run python scripts\generate_certificate_backgrounds.py`.
- Os logos podem ser recriados com
  `uv run python scripts\generate_certificate_logos.py`.

### Roadmap do gerenciador de clube

O Albericus já cobre torneios, membros/alunos, turmas, aulas, exercícios,
inventário, eventos, relatórios, backups, ranking interno e diplomas. As
próximas melhorias devem ser implementadas em etapas pequenas para manter o
banco local simples e testavel:

1. Consulta local/publica de diplomas: exportar uma página HTML de verificação
   dos códigos emitidos, com busca por código, nome, origem e status.
2. Área pedagógica: planos de aula, metas por turma, evolução por nível,
   tarefas e observações do professor.
3. Mensalidades e financeiro: planos recorrentes, vencimentos, pagamentos,
   pendências e recibos simples.
4. Ranking interno avançado: temporadas, categorias configuráveis, histórico
   de campeões, critérios por clube/turma e filtros por período.
5. Comunicação e portal: página HTML do clube/turma, avisos, calendário,
   exportação de listas e comunicados para responsáveis.
6. Biblioteca de exercícios: temas táticos, níveis, listas de treino,
   desempenho por aluno e histórico de estudos.
7. Inventário: controle de pecas, tabuleiros, relógios, livros, empréstimos e
   manutenções.
8. Segurança operacional: perfis de acesso, auditoria de alterações, políticas
   de backup e restauração guiada.

### Roadmap do gerenciador de clube - Etapa 1 implementada

- A tela `Diplomas` recebeu a ação `Exportar verificador`.
- O verificador gera um único arquivo HTML local, sem servidor, com busca por
  código, nome, origem ou modelo.
- A página exibe código, status ativo/revogado, destinatário, contexto, origem,
  tipo, modelo e data de emissão.
- O arquivo HTML não publica o caminho local do PDF, evitando expor a estrutura
  de pastas da maquina.

### Roadmap do gerenciador de clube - Etapa 2 implementada

- A tela `Aulas` passa a registrar dados pedagógicos da aula/treino:
  nível alvo, objetivo, conteúdo e tarefa para casa/treino.
- As aulas continuam vinculadas a clube/escola e turma, permitindo montar um
  plano pedagógico por turma sem criar outro fluxo de cadastro.
- O relatório de presenças inclui os novos campos pedagógicos na seção de
  aulas e treinos.
- Bancos antigos são migrados automaticamente para adicionar os novos campos em
  `training_sessions`.

### Roadmap do gerenciador de clube - Etapa 3 implementada

- A tela `Financeiro` passa a gerar mensalidades em lote a partir de um plano,
  referência `AAAA-MM` e vencimento.
- A geração considera socios/alunos ativos e pula automaticamente lançamentos
  já existentes para o mesmo plano e referência.
- Lançamentos pagos ou isentos podem ser exportados como recibo simples em
  PDF, XLSX ou CSV.
- O fluxo manual de lançamentos, status financeiro, resumo e relatórios por
  período continua funcionando no mesmo módulo.

### Roadmap do gerenciador de clube - Etapa 4 implementada

- O `Ranking interno` passa a aceitar filtros por clube/escola, turma e período
  de temporada.
- O aproveitamento, partidas, pontos e variação exibidos podem ser calculados
  apenas dentro do período informado.
- O relatório de ranking interno inclui os filtros aplicados, permitindo
  registrar rankings por temporada, unidade ou turma.
- A exportação também respeita categoria, clube/escola, turma e período,
  mantendo a visão geral e os lideres por categoria.

### Roadmap do gerenciador de clube - Etapa 5 implementada

- A tela `Relatorios` recebeu a opção `Portal do clube/turma`.
- O portal exporta uma pasta HTML estática com `index.html` e `styles.css`,
  pronta para abrir localmente ou hospedar.
- A página inclui comunicados, calendário de eventos, aulas/treinos futuros,
  turmas, ranking interno e torneios recentes.
- A exportação pode ser filtrada por clube/escola e turma, permitindo gerar um
  portal geral da unidade ou uma página especifica para uma turma.

### Roadmap do gerenciador de clube - Etapa 6 implementada

- A tela `Exercicios` permite cadastrar posições e tarefas por tema, nível,
  dificuldade, FEN, PGN, solução, objetivo, tags e fonte.
- Listas de treino podem ser criadas para clube/escola, turma e nível, com
  status de rascunho, pronta, aplicada ou arquivada.
- Exercícios podem ser adicionados e removidos das listas, mantendo uma ordem
  simples para uso em aula.
- A tela `Aulas` recebeu o campo `Lista de treino`, permitindo vincular uma
  lista pronta ao planejamento da aula/treino.
- O banco registra tentativas por aluno, exercício, lista e aula, criando a
  base para acompanhar desempenho e histórico de estudos.
- Bancos antigos são migrados automaticamente para a versão 11, criando
  `exercise_library`, `training_lists`, `training_list_exercises`,
  `exercise_attempts` e `training_sessions.training_list_id`.

### Roadmap do gerenciador de clube - Etapa 7 implementada

- A nova tela `Inventario` permite cadastrar materiais por clube/escola:
  pecas, tabuleiros, relógios, livros, kits, itens digitais e outros.
- Cada item registra código, quantidade total, estado de conservação, local,
  data/valor de aquisição, status ativo e observações.
- Empréstimos vinculam item, membro, quantidade, data prevista e devolução,
  com disponibilidade calculada automaticamente pelos empréstimos em aberto.
- Manutenções registram descrição, custo, fornecedor, status e data de
  conclusão, permitindo acompanhar reparos pendentes.
- Bancos antigos são migrados automaticamente para a versão 12, criando
  `inventory_items`, `inventory_loans` e `inventory_maintenance`.

### Roadmap do gerenciador de clube - Etapa 8 implementada

- A tela `Config. app` ganhou a seção `Seguranca operacional`, com operador
  local, perfil operacional e quantidade de backups a manter.
- Perfis locais disponíveis: administrador, arbitragem, professor, assistente
  e consulta. Nesta etapa eles identificam operações auditadas e preparam a
  base para bloqueios por permissão em uma etapa futura.
- Backups manuais e restaurações passam pelo `SecurityService`, registrando
  auditoria local em `audit_log`.
- A política de retenção remove backups antigos mantendo a quantidade
  configurada, com ação manual `Aplicar retencao`.
- A própria tela de configurações mostra a auditoria recente com data,
  operador, perfil, ação e descrição.
- Bancos antigos são migrados automaticamente para a versão 13, criando
  `audit_log` e índices por data/acao e entidade.

## Importação de jogadores

Cabeçalhos aceitos:

```csv
name,club,rating,category,fide,cbx,rating_nacional,rating_internacional,titulo
Ana Silva,Clube A,1850,Sub-18,123456,7890,1850,1820,WFM
Bruno Souza,Clube B,1720,Absoluto,234567,6789,1720,1690,
```

Também são aceitos nomes de colunas em português, como `nome`, `clube`, `elo`,
`categoria`, `sobrenome`, `sexo`, `id_fide`, `id_cbx`, `elo_nacional` e
`elo_fide`.

Os mesmos cabeçalhos podem ser usados em arquivos `.csv`, `.xls` e `.xlsx`.

## CSV de ratings oficiais

Para importar uma lista FIDE, CBX ou LBX por arquivo na tela `Jogadores`, use CSV com colunas como:

```csv
name,fide,cbx,title,fide_rating,rating_nacional,federation,club,birth_date
Ana Silva,123456,7890,WFM,1820,1850,BRA,Clube A,2008-01-01
```

Também são aceitos nomes como `nome`, `titulo`, `id_fide`, `id_cbx`,
`rating_internacional`, `elo_fide`, `rating_nacional`, `elo_nacional`,
`fed`, `federacao`, `clube`, `sexo` e `data_nascimento`.

Para a LBX, a ação `Atualizar base LBX` baixa e consolida automaticamente as listas
standard, rapid e blitz publicadas pela entidade. Também são aceitos `lbx_id`,
`id_lbx` e o formato Swiss-Manager com `ID_No`, `Rtg_Nat`, `ClubName` e `Birthday`.

## Observação

O algoritmo de emparceiramento e um suíço simplificado para uso inicial. Para torneios oficiais, valide as regras com o regulamento da entidade organizadora e com um árbitro.
