# Sistema de Arbitragem e Gestão de Torneios de Xadrez - Versão Técnica Revisada 2.0

**Data da revisão:** 26/05/2026  
**Documento base:** `Sistema de Arbitragem e Gestão de Torneios de Xadrez.md`  
**Objetivo:** transformar a visão inicial em um plano técnico implementável, auditável e compatível com torneios presenciais, equipes, exportação federativa e operação offline-first.

---

## 1. Resumo executivo

O documento original tem uma direção correta: o sistema não deve competir apenas pelo algoritmo de emparceiramento, mas pela experiência completa de arbitragem. As melhores ideias são: entrada rápida de resultados por QR Code, painel de arbitragem, portal público, explicação de critérios de desempate, suporte a equipes e exportação para formatos oficiais.

A revisão abaixo mantém essas ideias, mas muda a abordagem em três pontos fundamentais:

1. **Sai o discurso de promessa e entra engenharia de produto.** Números como "reduz erros em 90%" ou "fecha rodadas 70% mais rápido" devem ser tratados como metas de validação, não como fatos. O sistema deve medir esses indicadores depois de usado em torneios reais.
2. **Conformidade FIDE não pode ser vendida como automática.** O correto é criar um módulo de pré-validação, trilha de auditoria, exportadores e relatórios que ajudem o árbitro. A decisão final continua sendo do árbitro e da federação.
3. **O núcleo de emparceiramento deve ser protegido.** A camada web, QR Code, notificações e portal público não devem modificar diretamente o motor Swiss. Elas devem entrar por serviços controlados, transações, eventos e validações.

A estratégia recomendada é uma arquitetura **desktop-first, offline-first e web-assisted**: o programa desktop continua sendo a autoridade local do torneio; um backend local ou opcional na nuvem expõe APIs para celular, portal público e sincronização; todas as alterações críticas ficam em log de auditoria.

---

## 2. Diagnóstico do documento original

### 2.1 Pontos fortes

O documento original acerta ao identificar que o projeto já parece ter quatro pilares: `pairings.py`, `teams.py`, `tournaments.py` e `ui_pairings.py`. Essa separação é boa porque evita colocar regra de torneio, interface e banco de dados no mesmo lugar.

Os principais acertos são:

- reconhecer o valor de um motor Swiss próprio;
- separar torneios individuais e por equipes;
- incluir critérios de desempate como recurso central, não como detalhe;
- prever interface de resultados rápida;
- pensar em experiência do jogador, não apenas na mesa do árbitro;
- considerar exportação oficial e relatórios.

### 2.2 Fragilidades

As fragilidades do texto original não estão nas ideias, mas na falta de limites técnicos. Algumas propostas são boas, porém precisam ser rebaixadas para fases posteriores ou redesenhadas.

| Tema | Problema no documento original | Correção recomendada |
|---|---|---|
| QR Code | Parece permitir registro direto do resultado sem detalhar autenticação. | Usar token assinado, escopo por mesa/rodada, expiração, confirmação e aprovação. |
| Relógios DGT/Chronos | Integração tratada como nativa e genérica. | Transformar em plugin opcional. Primeiro registrar eventos manualmente; depois integrar hardware específico. |
| Reservas de equipe | "Auto-promoção" pode violar regulamento específico da competição. | Usar fluxo de substituição com aprovação, bloqueio por prazo e regras configuráveis de escalação. |
| Conformidade FIDE | Texto sugere conformidade automática. | Criar checklist, exportadores e validação; não prometer homologação automática. |
| Tiebreaks | Boa ideia de explicação, mas sem modelo de dados. | Salvar componentes de desempate por jogador/rodada em `tiebreak_components`. |
| Sincronização | CRDT citado sem plano. | Começar com outbox transacional e servidor autoritativo; CRDT só se houver edição concorrente real. |
| Segurança | JWT citado de forma genérica. | Definir perfis, tokens curtos, chaves por torneio, log imutável e política LGPD. |
| Roadmap | Fases amplas demais. | Dividir em MVPs testáveis com critérios de aceite. |

---

## 3. Premissas técnicas

Esta revisão assume que o projeto atual é Python desktop, com interface CustomTkinter e banco local. O plano evita uma reescrita completa. A recomendação é evoluir por camadas:

1. **Camada de domínio:** regras de torneio, jogadores, equipes, rodadas, resultados, emparceiramento e desempates.
2. **Camada de aplicação:** casos de uso como "gerar rodada", "registrar resultado", "fechar rodada", "corrigir resultado", "exportar TRF".
3. **Camada de persistência:** SQLite inicialmente, com migrações e modo WAL; PostgreSQL como opção futura.
4. **Camada de interface:** CustomTkinter para o árbitro e PWA/web para celular, jogador e público.
5. **Camada de integração:** QR Code, notificações, exportações, relógios e publicação live.

O ponto mais importante: **nenhuma interface deve alterar diretamente tabelas críticas**. Toda alteração deve passar por um serviço de aplicação que valide regra, registre auditoria e gere evento.

---

## 4. Conformidade FIDE e atualização normativa

Como a data desta revisão é 26/05/2026, o sistema deve mirar as regras FIDE atuais de Swiss publicadas para 2026, principalmente C.04.1, C.04.2, C.04.3 e C.04.6. As regras gerais de torneios Swiss vigentes desde 01/02/2026 reforçam que o sistema usado em torneio FIDE rated deve ser um sistema FIDE publicado ou autorizado, com regras documentadas, reprodutibilidade e impossibilidade de alterar emparceiramentos corretos em favor de participantes.

Recomendações práticas:

- Criar campo obrigatório `pairing_system` por torneio: `fide_dutch`, `dubov`, `burstein`, `lim`, `team_swiss`, `custom_authorized`.
- Criar campo `acceleration_method`, mesmo que inicialmente seja `none`.
- Criar campo `pairing_engine_version` e `ruleset_version` em cada rodada.
- Salvar `pairing_input_snapshot` antes de gerar a rodada.
- Salvar `pairing_output_snapshot` depois de gerar a rodada.
- Permitir alteração manual de emparceiramento apenas com motivo, perfil autorizado e marca de auditoria.
- Criar relatório "Explicação do emparceiramento" para o árbitro.

Para torneios por equipes, as regras FIDE de Swiss Team Pairing System vigentes desde 01/02/2026 tratam equipes como participantes em muitos pontos, mas observam que cores têm peso diferente em competições por equipes porque jogadores podem ser substituídos ou trocados entre tabuleiros. Portanto, o sistema deve separar:

- cor da equipe;
- cor de cada tabuleiro;
- escalação da equipe;
- regra da competição sobre ordem de tabuleiro;
- permissão ou não de substituições.

Para rating FIDE, as FIDE Rating Regulations vigentes desde 01/03/2024 exigem pré-registro do torneio pela federação responsável, definem prazos de registro e estabelecem que o Chief Arbiter deve fornecer o arquivo de relatório do torneio ao Rating Officer. Logo, o sistema deve priorizar exportação correta e validação antes de exportar, não apenas gerar um arquivo no fim.

Sobre TRF, o caminho mais seguro é implementar **TRF16 como base estável** e desenhar o exportador com arquitetura extensível para TRF25/TRF2026. A Comissão Técnica da FIDE publicou rascunhos/final drafts de TRF25 com extensões para equipes, desempates e troca de dados entre Tournament Handler Programs. Isso é relevante, mas não deve quebrar compatibilidade com fluxos atuais de rating.

---

## 5. Decisão arquitetural recomendada

### 5.1 Arquitetura alvo

```text
+--------------------------------------------------------------+
|                        Interface Desktop                     |
| CustomTkinter/PySide: árbitro principal, operação offline     |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
|                    Camada de Aplicação                       |
| gerar_rodada, registrar_resultado, fechar_rodada, exportar   |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
|                       Núcleo de Domínio                      |
| Swiss, equipes, desempates, validações, standings            |
+-----------------------------+--------------------------------+
                              |
            +-----------------+------------------+
            |                                    |
            v                                    v
+----------------------------+       +---------------------------+
| SQLite local com WAL       |       | API local FastAPI opcional |
| migrações, snapshots, log  |       | QR, portal, PWA, sync      |
+----------------------------+       +---------------------------+
                                             |
                                             v
                                  +---------------------------+
                                  | Celular/tablet/portal     |
                                  | resultados, público, PWA  |
                                  +---------------------------+
```

### 5.2 Autoridade dos dados

No MVP, a autoridade deve ser o **banco local do árbitro principal**. O celular não decide o torneio; ele apenas envia uma solicitação de resultado. O desktop valida, registra, publica e sincroniza.

Depois, se houver necessidade de vários árbitros trabalhando ao mesmo tempo, a autoridade pode ser movida para um servidor PostgreSQL. Essa migração deve ser planejada, mas não precisa acontecer no início.

### 5.3 Stack recomendada

| Área | Recomendação | Observação |
|---|---|---|
| Desktop | CustomTkinter existente ou PySide6 futuramente | Não reescrever agora se a interface já funciona. |
| Backend local | FastAPI + Uvicorn | Pode rodar junto do desktop em `localhost`. |
| Banco | SQLite WAL + Alembic/migrações próprias | Suficiente para torneios de clube e operação offline. |
| ORM | SQLAlchemy ou camada própria com repository pattern | O importante é padronizar transações. |
| QR Code | `qrcode` ou biblioteca equivalente | QR deve apontar para rota assinada. |
| PWA | HTML/HTMX ou React | HTMX é mais simples para MVP; React para dashboard complexo. |
| Exportação | Serviço separado `exports/` | TRF, CSV, JSON, PGN e HTML. |
| Testes | pytest + fixtures de torneios reais/sintéticos | Essencial para emparceiramento e desempates. |
| Empacotamento | PyInstaller | Instalação simples para árbitros. |

---

## 6. Redesenho dos módulos existentes

### 6.1 `pairings.py`

Este é o módulo mais sensível. A prioridade é torná-lo determinístico, testável e explicável.

Melhorias recomendadas:

- separar cálculo de pareamento de acesso ao banco;
- criar função pura `generate_pairings(input_snapshot) -> pairing_plan`;
- salvar todos os parâmetros usados no emparceiramento;
- registrar penalidades aplicadas: repetição de confronto, cor, float, bye, score group;
- gerar explicação por mesa;
- criar bateria de testes com torneios pequenos, médios e casos-limite;
- impedir modificação silenciosa de rodada já publicada.

Estrutura sugerida:

```text
pairings/
  __init__.py
  models.py              # dataclasses de entrada/saída
  fide_dutch.py           # algoritmo principal
  team_swiss.py           # pareamento por equipes
  constraints.py          # restrições absolutas e preferências
  explain.py              # explicações de decisão
  validators.py           # checagens antes/depois
  snapshots.py            # serialização do input/output
```

Critérios de aceite:

- mesmo input gera exatamente o mesmo output;
- nenhum jogador enfrenta o mesmo adversário duas vezes, exceto cenário explicitamente permitido;
- jogador com bye prévio não recebe novo bye alocado se a regra impedir;
- histórico de cor respeita restrições absolutas quando aplicável;
- rodada publicada não é alterada sem evento de auditoria.

### 6.2 `teams.py`

O módulo de equipes precisa evoluir de cadastro para motor de escalação.

Substituir a ideia de "auto-promoção de reserva" por **workflow de substituição controlada**:

1. Capitão ou árbitro informa ausência.
2. Sistema mostra reservas elegíveis.
3. Sistema valida ordem de tabuleiro, rating, regra de escalação e prazo.
4. Árbitro confirma.
5. Sistema registra evento de substituição.
6. Resultado e exportação preservam quem efetivamente jogou.

Novas entidades:

- `team_roster_policy`: define se ordem de força é obrigatória, se reservas podem entrar, prazo de escalação e limite de trocas;
- `team_lineup`: escalação de uma rodada;
- `team_lineup_board`: jogador escalado por tabuleiro;
- `team_substitution_event`: substituição com motivo e autor.

Critérios de aceite:

- não excluir equipe depois de rodada iniciada;
- não alterar escalação de partida com resultado aprovado sem correção formal;
- permitir escalação por rodada;
- preservar histórico de titular/reserva;
- exportar corretamente tabuleiros e jogadores.

### 6.3 `tournaments.py`

Este módulo deve virar o centro de configuração normativa do torneio.

Campos recomendados:

```text
tournament_id
name
organizer
federation
city
country
start_date
end_date
rated_fide: bool
fide_event_code
pairing_system
acceleration_method
rounds_count
time_control
scoring_profile_id
team_mode: none | teams_match_points | teams_game_points
board_count
registration_deadline
result_correction_deadline_minutes
publication_mode: private | club | public
ruleset_version
```

Melhorias:

- checklist pré-torneio;
- assistente de configuração por tipo de torneio;
- alerta de incompatibilidade: número de rodadas, jogadores, sistema, pontuação, desempates;
- bloqueio progressivo de campos depois do início;
- agenda com tolerância a atrasos e mudança de horário.

### 6.4 `ui_pairings.py`

A interface atual deve ser preservada, mas reorganizada em telas orientadas a fluxo.

Telas recomendadas:

1. **Preparação:** jogadores, equipes, configuração, validação pré-torneio.
2. **Rodada atual:** mesas, resultados pendentes, alertas, impressão/QR.
3. **Classificação:** individual/equipes, desempates e explicações.
4. **Auditoria:** alterações, correções, exclusões, substituições.
5. **Exportações:** TRF, HTML, PDF, CSV, PGN.
6. **Portal/Sync:** status do servidor local, links públicos, QR codes.

A interface de resultado deve ter estados claros:

```text
sem_resultado -> submetido -> aprovado -> publicado -> fechado
                              \-> rejeitado
publicado -> corrigido -> republicado
fechado -> reaberto_com_motivo
```

---

## 7. Modelo de dados recomendado

O modelo abaixo é suficiente para evoluir sem quebrar o projeto atual. Não é necessário implementar tudo de uma vez; a primeira etapa é criar as tabelas de auditoria, snapshots e resultados.

### 7.1 Tabelas centrais

| Tabela | Função |
|---|---|
| `tournaments` | Configuração principal do torneio. |
| `sections` | Categoria/seção: absoluto, sub-18, feminino, equipes, etc. |
| `players` | Cadastro de jogador. |
| `teams` | Cadastro de equipe. |
| `team_members` | Relação jogador-equipe, papel e ordem. |
| `rounds` | Rodadas, status e timestamps. |
| `pairings` | Mesas geradas. |
| `games` | Partidas individuais por mesa/tabuleiro. |
| `results` | Resultado submetido/aprovado/corrigido. |
| `standings_snapshots` | Classificação congelada por rodada. |
| `tiebreak_components` | Componentes calculados dos critérios. |
| `audit_events` | Log imutável de ações críticas. |
| `pairing_snapshots` | Entrada e saída do motor de emparceiramento. |
| `public_tokens` | Tokens de QR e portal. |
| `sync_outbox` | Eventos pendentes de sincronização. |
| `devices` | Celulares/tablets autorizados. |

### 7.2 Estados de rodada

```text
draft
published
in_progress
results_pending
ready_to_close
closed
reopened
cancelled
```

### 7.3 Estados de resultado

```text
empty
submitted
approved
rejected
published
corrected
locked
```

### 7.4 Auditoria mínima

Cada ação crítica deve gerar evento:

```json
{
  "event_id": "uuid",
  "tournament_id": 1,
  "round_id": 3,
  "entity_type": "result",
  "entity_id": 155,
  "action": "result_corrected",
  "actor_id": "arbiter:main",
  "reason": "Resultado digitado invertido na mesa 12",
  "before_hash": "...",
  "after_hash": "...",
  "created_at": "2026-05-26T19:30:00-03:00"
}
```

O log deve ser append-only. Em vez de apagar, cria-se um evento de correção. Isso protege o árbitro e torna o sistema confiável.

---

## 8. Fluxo de QR Code para resultados

O QR Code é uma das melhores ideias do documento original, mas precisa ser implementado com segurança.

### 8.1 Fluxo seguro

1. Ao publicar a rodada, o sistema gera um token por mesa.
2. O QR aponta para `/r/{round_id}/b/{board_id}?token=...`.
3. O token tem escopo limitado: torneio, rodada, mesa e prazo.
4. A tela mostra nomes, cores, mesa e botões de resultado.
5. O usuário confirma o resultado em duas etapas.
6. O backend grava como `submitted`.
7. O árbitro aprova ou rejeita no painel.
8. Depois de aprovado, o resultado entra na classificação.

### 8.2 Segurança mínima

- token assinado com HMAC;
- expiração por rodada;
- limite de tentativas;
- registro de IP/dispositivo quando disponível;
- confirmação visual com nomes e cores;
- bloqueio se rodada fechada;
- trilha de auditoria.

### 8.3 Modo offline

Se não houver internet, o QR pode apontar para um servidor local no notebook do árbitro, por exemplo:

```text
http://192.168.0.10:8765/t/abc123/r/3/b/12
```

Isso permite uso em rede Wi-Fi local sem depender de nuvem. Para clubes pequenos, o desktop pode abrir um hotspot ou usar a rede local existente.

### 8.4 MVP

O primeiro MVP não precisa ter login de jogador. Basta:

- QR por mesa;
- tela web local;
- envio de resultado;
- fila de aprovação;
- painel com pendentes;
- impressão de folha de emparceiramento com QR.

---

## 9. Painel do árbitro

O painel deve ser orientado a exceções. O árbitro não precisa clicar em tudo; precisa ver o que exige ação.

### 9.1 Indicadores principais

- mesas sem resultado;
- resultados submetidos aguardando aprovação;
- resultados corrigidos;
- partidas com tempo excedido de acordo com horário planejado;
- jogadores/equipes ausentes;
- problemas de escalação;
- conflitos de cor;
- jogadores com float repetido;
- alertas antes de gerar próxima rodada.

### 9.2 Ações rápidas

- aprovar todos os resultados conferidos;
- imprimir emparceiramentos;
- publicar no portal;
- gerar próxima rodada em modo prévia;
- reabrir rodada com justificativa;
- exportar relatório da rodada;
- bloquear/ocultar dados pessoais no portal.

### 9.3 Prévia da rodada

Antes de publicar, o sistema deve mostrar:

- confrontos repetidos detectados;
- jogadores sem adversário;
- byes;
- cor de cada jogador;
- alertas de três cores seguidas;
- floats;
- pares de scoregroup;
- mudanças manuais feitas pelo árbitro.

---

## 10. Explicador de desempates

O explicador visual de tiebreaks é uma das funções mais valiosas para reduzir reclamações.

### 10.1 O que salvar

Em vez de calcular apenas o número final, salve os componentes:

```text
player_id
round_id
tiebreak_code
raw_value
display_value
components_json
calculated_at
algorithm_version
```

Exemplo de `components_json` para Buchholz:

```json
{
  "opponents": [
    {"player": "Carlos", "score": 4.5, "included": true},
    {"player": "João", "score": 3.0, "included": true},
    {"player": "Pedro", "score": 2.0, "included": false, "reason": "cut1"}
  ],
  "total": 7.5
}
```

### 10.2 Interface

Na classificação, cada critério deve ser clicável:

```text
3º - Maria - 5.0 pts - Buchholz 21.5
Por que está em 3º?
- Pontos: empatada com Ana e Beatriz.
- 1º desempate: Buchholz.
- Soma dos pontos dos adversários: 21.5.
- Ana tem 20.0 e Beatriz tem 19.5.
```

### 10.3 Benefício real

O benefício não é apenas transparência. Ele também funciona como teste de qualidade do sistema: se o software não consegue explicar o desempate, provavelmente o cálculo está acoplado demais ou pouco auditável.

---

## 11. Exportações e relatórios

### 11.1 Exportadores prioritários

| Prioridade | Exportação | Motivo |
|---|---|---|
| Alta | PDF de emparceiramento por rodada | Uso imediato em torneios presenciais. |
| Alta | PDF/HTML de classificação | Divulgação e impressão. |
| Alta | CSV/Excel | Conferência manual e integração com clubes. |
| Alta | TRF16 | Base para rating FIDE e compatibilidade ampla. |
| Média | TRF25/TRF2026 | Preparação para evolução técnica da FIDE. |
| Média | JSON público | Portal, bots e integrações. |
| Média | PGN em lote | Útil quando há partidas registradas. |
| Baixa | API de submissão automática | Só depois de entender fluxo da federação. |

### 11.2 Validação antes da exportação

Antes de gerar TRF, o sistema deve checar:

- dados do torneio completos;
- datas coerentes;
- árbitro informado;
- cidade/país/federação;
- FIDE ID quando aplicável;
- rating e título dos jogadores;
- resultados válidos;
- ausências e forfeits diferenciados de jogos jogados;
- byes e partidas não jogadas classificados corretamente;
- sistema de emparceiramento declarado;
- rodadas fechadas;
- encoding do arquivo.

### 11.3 Relatórios úteis

- relatório oficial do torneio;
- relatório de correções;
- relatório de reclamações/intervenções;
- relatório de escalações por equipe;
- relatório de critérios de desempate;
- relatório de auditoria.

---

## 12. Portal público e experiência do jogador

O portal deve começar simples. Não é necessário criar uma rede social do torneio. O primeiro objetivo é reduzir fila na mesa do árbitro.

### 12.1 Páginas do MVP

- `/pairings`: emparceiramento da rodada atual;
- `/standings`: classificação;
- `/rounds`: histórico de rodadas;
- `/player/{id}`: ficha do jogador;
- `/team/{id}`: ficha da equipe;
- `/announcements`: avisos do árbitro.

### 12.2 Privacidade

Nem todo dado deve ser público. Permitir:

- ocultar e-mail, telefone e data de nascimento;
- mostrar apenas nome de torneio e rating;
- modo clube privado;
- modo público completo;
- exportação anonimizada para testes.

### 12.3 Notificações

Notificações devem entrar só depois do portal básico. Comece por e-mail ou aviso web. WhatsApp/SMS exigem custo, aprovação de template, provedores externos e cuidado com LGPD.

---

## 13. Integração com relógios e hardware

A integração com relógios deve ser tratada como plugin, não como base do sistema.

### 13.1 Ordem correta de implementação

1. Registrar manualmente eventos de tempo e ausência.
2. Criar tabela genérica `clock_events`.
3. Criar interface de plugins.
4. Integrar primeiro com um hardware bem definido.
5. Só depois sugerir resultados automaticamente.

### 13.2 Regra de ouro

Hardware pode sugerir; o árbitro decide. O sistema nunca deve converter automaticamente uma leitura de relógio em derrota sem confirmação, porque há contexto de arbitragem que o software não enxerga.

---

## 14. Segurança, LGPD e perfis de acesso

### 14.1 Perfis

| Perfil | Permissões |
|---|---|
| Administrador | Configura torneio, usuários, exportações e backups. |
| Árbitro principal | Gera rodadas, aprova resultados, corrige, fecha rodadas. |
| Árbitro auxiliar | Registra/submete resultados e ocorrências. |
| Capitão | Envia escalação e solicita substituição, se permitido. |
| Jogador | Consulta dados próprios e confirma presença. |
| Público | Consulta páginas publicadas. |

### 14.2 Dados sensíveis

Evite publicar:

- e-mail;
- telefone;
- documento;
- data completa de nascimento;
- observações internas;
- justificativas disciplinares;
- anexos de reclamações.

### 14.3 Backup

O sistema deve fazer backup automático em momentos críticos:

- antes de gerar rodada;
- antes de publicar rodada;
- antes de fechar rodada;
- antes de correção em massa;
- antes de exportação final.

Formato recomendado:

```text
backups/
  2026-05-26_rodada-03_antes-publicar.sqlite
  2026-05-26_rodada-03_antes-fechar.sqlite
  2026-05-26_final_exportacao-trf.sqlite
```

---

## 15. Estratégia de testes

Sem testes fortes, um software de emparceiramento vira risco para o árbitro. A prioridade é criar uma suíte de testes antes de ampliar interface.

### 15.1 Testes obrigatórios

| Tipo | Exemplos |
|---|---|
| Unitários | cálculo de pontos, cores, byes, desempates. |
| Propriedade | nenhum confronto repetido em torneios gerados aleatoriamente. |
| Regressão | torneios salvos com resultado esperado. |
| Integração | gerar rodada -> registrar resultados -> fechar -> gerar próxima. |
| Exportação | TRF/CSV/PDF gerados com dados corretos. |
| Auditoria | toda correção gera evento. |
| UI crítica | fluxo de resultado e fechamento de rodada. |

### 15.2 Fixtures recomendadas

Criar pasta:

```text
tests/fixtures/tournaments/
  individual_8_players_3_rounds.json
  individual_9_players_bye.json
  individual_color_conflict.json
  team_6_teams_4_boards.json
  team_substitution_case.json
  late_entry_case.json
  withdrawn_player_case.json
  corrected_result_case.json
```

### 15.3 Métricas de qualidade

- tempo para gerar rodada com 50, 100, 300 e 1000 jogadores;
- número de cliques para registrar resultados;
- número de correções por torneio;
- tempo entre fim da última partida e publicação da próxima rodada;
- divergência entre classificação explicada e classificação final;
- erros de exportação detectados antes do envio.

---

## 16. Roadmap revisado

### Fase 0 - Estabilização do núcleo

Objetivo: impedir que novas funcionalidades quebrem o motor atual.

Entregas:

- migrações de banco;
- logs de auditoria;
- snapshots de emparceiramento;
- testes de regressão;
- backup automático por rodada;
- separação mínima entre UI e serviços.

Critério de aceite:

- gerar, publicar, registrar resultados, fechar e exportar um torneio individual sem manipulação direta no banco.

### Fase 1 - Produtividade imediata do árbitro

Objetivo: reduzir trabalho manual sem depender de internet.

Entregas:

- folha de emparceiramento com QR Code;
- servidor local FastAPI;
- tela mobile de envio de resultado;
- fila de aprovação no desktop;
- dashboard de pendências;
- PDF/HTML de classificação.

Critério de aceite:

- realizar um torneio de teste com celular registrando resultados em rede local.

### Fase 2 - Explicabilidade e exportação oficial

Objetivo: aumentar confiança do árbitro e do jogador.

Entregas:

- explicador de tiebreaks;
- prévia de rodada com alertas;
- exportador TRF16;
- validador pré-exportação;
- relatório de auditoria;
- relatório de correções.

Critério de aceite:

- gerar arquivo de relatório e explicar a classificação final sem cálculo manual externo.

### Fase 3 - Equipes avançadas

Objetivo: transformar `teams.py` em motor operacional.

Entregas:

- escalação por rodada;
- substituição controlada de reservas;
- regras de tabuleiro configuráveis;
- match points/game points;
- classificação por equipes;
- exportação de equipes preparada para TRF25/TRF2026.

Critério de aceite:

- rodar torneio por equipes com 4 tabuleiros, reservas e substituições auditadas.

### Fase 4 - Portal público e sincronização

Objetivo: publicar torneios com baixa fricção.

Entregas:

- portal público responsivo;
- atualização live;
- modo privado/público;
- exportação JSON;
- sync opcional para nuvem;
- permissões por perfil.

Critério de aceite:

- público acompanha classificação e emparceiramentos sem acessar o computador do árbitro.

### Fase 5 - Integrações avançadas

Objetivo: diferenciar o produto sem comprometer o núcleo.

Entregas:

- plugins para relógios/dispositivos;
- notificações por e-mail/WhatsApp/SMS;
- PWA completa;
- assistente de anomalias;
- suporte ampliado a TRF25/TRF2026.

Critério de aceite:

- integrações podem ser desligadas sem afetar torneios locais.

---

## 17. Backlog priorizado

### Muito alto impacto / baixa complexidade

- backup automático antes de fechamento de rodada;
- botão "pré-visualizar próxima rodada";
- PDF de emparceiramento limpo;
- CSV de classificação;
- log de correções;
- status visual de resultados pendentes.

### Alto impacto / média complexidade

- QR Code de resultado;
- API local;
- explicador de tiebreaks;
- snapshots de emparceiramento;
- validador pré-exportação;
- exportador TRF16.

### Alto impacto / alta complexidade

- torneios por equipes com reservas;
- portal live;
- sincronização multi-dispositivo;
- permissões por perfil;
- motor de explicação de pareamento.

### Baixa prioridade inicial

- integração com relógios;
- app nativo Android/iOS;
- submissão automática para federação;
- CRDT completo;
- inteligência artificial para arbitragem.

---

## 18. Especificação curta das APIs

### 18.1 Resultados

```http
POST /api/tournaments/{tournament_id}/rounds/{round_id}/boards/{board_id}/result-submissions
```

Payload:

```json
{
  "token": "signed-token",
  "result": "1-0",
  "submitted_by": "table_qr",
  "device_label": "Mesa 12",
  "confirmation": true
}
```

Resposta:

```json
{
  "status": "submitted",
  "message": "Resultado enviado para aprovação do árbitro."
}
```

### 18.2 Aprovação

```http
POST /api/results/{submission_id}/approve
```

Payload:

```json
{
  "arbiter_id": "arbiter:main",
  "notes": "Conferido com a súmula"
}
```

### 18.3 Publicação

```http
POST /api/rounds/{round_id}/publish
```

Payload:

```json
{
  "publish_pairings": true,
  "publish_standings": true,
  "visibility": "public"
}
```

---

## 19. Estrutura de pastas sugerida

```text
chess_tournament_manager/
  app/
    main.py
    config.py
  domain/
    tournaments.py
    players.py
    teams.py
    pairings/
    tiebreaks/
    scoring.py
  services/
    generate_round.py
    submit_result.py
    approve_result.py
    close_round.py
    export_tournament.py
  persistence/
    db.py
    migrations/
    repositories/
  desktop_ui/
    main_window.py
    screens/
  web_api/
    server.py
    routers/
    templates/
    static/
  exports/
    pdf_exporter.py
    trf16_exporter.py
    trf25_exporter.py
    csv_exporter.py
    html_exporter.py
  audit/
    events.py
    hashes.py
  tests/
    fixtures/
```

---

## 20. Riscos e mitigação

| Risco | Gravidade | Mitigação |
|---|---:|---|
| Erro de emparceiramento | Muito alta | testes de regressão, snapshots e prévia explicável. |
| Correção sem rastro | Alta | audit log append-only. |
| QR Code usado por pessoa errada | Média | token assinado, confirmação e aprovação do árbitro. |
| Falha de internet | Alta | modo local/offline-first. |
| Exportação FIDE inválida | Alta | validador pré-exportação e testes com arquivos exemplo. |
| Interface complexa demais | Média | dashboard por exceção e fluxo guiado. |
| Reescrita grande demais | Alta | evolução por serviços e módulos, sem jogar fora o desktop. |
| Vazamento de dados pessoais | Alta | perfis, ocultação pública e política LGPD. |
| Hardware instável | Média | plugins opcionais e confirmação manual. |

---

## 21. Critérios de aceite gerais

Um lançamento inicial confiável deve cumprir:

- criar torneio individual;
- cadastrar jogadores;
- gerar rodada;
- publicar emparceiramento;
- imprimir/exportar PDF;
- registrar resultados manualmente e por QR;
- aprovar resultados;
- fechar rodada;
- gerar classificação com tiebreaks;
- explicar pelo menos Buchholz, Sonneborn-Berger e confronto direto;
- fazer backup automático;
- registrar correções em auditoria;
- exportar CSV e TRF16;
- operar sem internet.

---

## 22. Plano de implementação imediato

### Sprint 1 - Auditoria e banco

- criar tabela `audit_events`;
- criar tabela `pairing_snapshots`;
- criar tabela `standings_snapshots`;
- criar função `backup_before(action)`;
- impedir exclusões destrutivas em rodada fechada.

### Sprint 2 - Serviços de aplicação

- extrair da UI os casos de uso:
  - `generate_round`;
  - `submit_result`;
  - `approve_result`;
  - `close_round`;
  - `reopen_round`.
- adicionar testes básicos.

### Sprint 3 - QR local

- criar FastAPI local;
- gerar token por mesa;
- criar página mobile simples;
- criar fila de aprovação no desktop;
- gerar PDF de emparceiramento com QR.

### Sprint 4 - Desempates explicáveis

- salvar componentes;
- criar tela "por que esta posição?";
- gerar relatório de tiebreaks;
- testar com torneios pequenos.

### Sprint 5 - Exportação TRF16

- criar exporter isolado;
- criar validador;
- gerar arquivo;
- testar encoding;
- criar relatório de pendências antes de exportar.

---

## 23. Conclusão revisada

O projeto tem potencial real porque parte de um núcleo que já parece resolver o essencial: torneio, jogadores, equipes, rodadas, emparceiramento e classificação. O salto de qualidade não deve vir de uma reescrita completa nem de promessas futuristas; deve vir de três camadas bem implementadas:

1. **Confiabilidade:** testes, snapshots, auditoria, backup e exportação correta.
2. **Produtividade:** QR Code, painel de pendências, aprovação rápida e relatórios.
3. **Transparência:** explicação de emparceiramento, tiebreaks, portal público e histórico de correções.

A melhor primeira entrega é a combinação: **backup automático + auditoria + QR Code local + dashboard de resultados pendentes**. Isso já diferencia o sistema em torneios reais sem arriscar o motor Swiss.

Depois disso, avance para TRF16, tiebreaks explicáveis e equipes avançadas. Integração com relógios, notificações e nuvem devem ficar como plugins, sempre desligáveis, para que o sistema continue funcionando mesmo em clubes sem internet ou com infraestrutura simples.

---

## 24. Fontes consultadas

1. FIDE Handbook - C.04.2 General handling rules for Swiss Tournaments, effective from 1 February 2026: https://handbook.fide.com/chapter/GeneralHandlingRulesForSwissTournaments202602
2. FIDE Handbook - C.04.6 Swiss Team Pairing System, effective from 1 February 2026: https://handbook.fide.com/chapter/SwissTeamPairingSystem202602
3. FIDE Handbook - FIDE Rating Regulations effective from 1 March 2024: https://handbook.fide.com/chapter/B022024
4. FIDE Technical Commission - TRF25 Final Draft: https://tec.fide.com/2025/01/09/trf25-final-draft/
5. FIDE Technical Commission - Draft TRF 2025 extensions for team pairing and tie-breaks: https://tec.fide.com/2024/09/04/draft-trf-2025-extensions-for-team-pairing-and-tie-breaks/
