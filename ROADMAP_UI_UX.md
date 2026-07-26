# ROADMAP_UI_UX — Plano de implementação de UI/UX do Albericus

> **Status:** Proposta (v1) · **Data:** 2026-06-25 · **Spec:** [ESPEC_UI_UX.md](ESPEC_UI_UX.md)
> **Estimativa total:** ~6–7 semanas de um dev solo focado · **MVP de percepção:** ~10 dias úteis.

Roadmap derivado da spec. Mescla duas análises (arquitetural + visual), reconciliadas e
validadas no código. Esforço em dias úteis de um dev solo; impacto e risco em Alto/Médio/Baixo.

---

## 1. Catálogo unificado de achados

IDs estáveis (referenciados pelas tarefas). Prioridade: **P0** destrava evolução ·
**P1** impacto diário · **P2** polish/escala.

### P0 — Débito estrutural

| ID | Achado | Evidência | Impacto |
|----|--------|-----------|---------|
| P0-1 | _God class_: `AlbericusApp` herda 14 mixins de tela | [app.py:29](src/ui/app.py:29) | Alto |
| P0-2 | Telas-monstro (até 1.920 linhas) misturam view+lógica+estado | `pairing_results_ui.py` etc. | Alto |
| P0-3 | Estado via `{"value": None}` (22×/12 arquivos) | grep validado | Médio |
| P0-4 | `from ..support import *` (22 arquivos) | grep validado | Médio |
| P0-5 | Tema reescreve `sys.modules` (`_propagate_theme_globals`) | [support.py:264](src/ui/support.py:264) | Médio |
| P0-6 | Troca de tema **destrói/recria** a UI inteira | [app.py:165](src/ui/app.py:165) | Alto |

### P1 — UX e feedback

| ID | Achado | Evidência | Impacto |
|----|--------|-----------|---------|
| P1-1 | "Wall of buttons": ~18 botões sem hierarquia na tela de Rodadas | [pairing_results_ui.py:30](src/ui/screens/pairing_results_ui.py:30) | Alto |
| P1-2 | Tooltips inexistentes em 100% do app (`CTkToolTip` **não** instalado) | — | Alto |
| P1-3 | Ações longas sem loading (gerar rodada trava UI sem feedback) | `_generate_round` | Alto |
| P1-4 | `messagebox` nativo em todo erro/confirmação (26×) | grep validado | Alto |
| P1-5 | 4 `threading.Thread` crus em vez do helper `_run_background` | communication/settings/club_members | Médio |
| P1-6 | Exclusões destrutivas sem desfazer | `delete_*` | Alto |
| P1-7 | Navegação só por menu nativo (7 menus, 30+ itens) | [app.py:345](src/ui/app.py:345) | Alto |
| P1-8 | Pós-login abre "Clube", não dashboard contextual | [app.py:285](src/ui/app.py:285) | Alto |
| P1-9 | Empty states fracos (label "Nenhum registro") | telas de lista | Médio |
| P1-10 | KPI cards clicáveis sem hover visual | [app.py:905](src/ui/app.py:905) | Médio |
| P1-11 | Modal do Modo Livre reabre sempre (sem "não mostrar de novo") | [free_tournament.py:12](src/ui/screens/free_tournament.py:12) | Baixo |
| P1-12 | Itens de menu desabilitados (Aulas/Exercícios) — **deliberado**, mas confunde | [app.py:367](src/ui/app.py:367) | Baixo |

### P2 — Polish e profissionalização

| ID | Achado | Evidência | Impacto |
|----|--------|-----------|---------|
| P2-1 | 58 cores hex hardcoded em telas (ignoram o accent) | grep validado | Médio |
| P2-2 | 23 `CTkFont(size=)` soltos fora dos tokens | grep validado | Baixo |
| P2-3 | Botões "✕" com `#a3423c` em vez de `THEME_DANGER` | [tournament_widgets.py:85](src/ui/screens/tournament_widgets.py:85) | Médio |
| P2-4 | Espaçamento mágico (sem tokens `SPACE_*`) | telas | Baixo |
| P2-5 | Danger button sem destaque/separação em formulários | telas com Excluir | Médio |
| P2-6 | Login 420×400 apertado (sem split/branding) | [app.py:56](src/ui/app.py:56) | Baixo |
| P2-7 | 4 temas JSON órfãos em `assets/themes/` | validado | Baixo |
| P2-8 | Labels visíveis sem acento ("Configuracoes", "Aparencia") | telas/menu | Médio |
| P2-9 | Persistência de layout de colunas por usuário/sessão | `widths={...}` fixos | Baixo |
| P2-10 | Modal de doação aninhado no `_build_menu` | [app.py:414](src/ui/app.py:414) | Baixo |
| P2-11 | Contraste WCAG AA não auditado (dark/presets quentes) | tokens | Médio |
| P2-12 | i18n: strings PT-BR espalhadas (sem catálogo) | global | Baixo |
| P2-13 | Tabelas `ttk.Treeview` sem virtualização (lento em 1.000+ linhas) | trees | Baixo |
| P2-14 | Charts matplotlib recriados a cada refresh | [dashboard.py](src/ui/screens/dashboard.py) | Baixo |

---

## 2. Fases de implementação

Cada tarefa: **esforço** · **impacto** · **risco** · **depende de** · **aceite**.

### Fase 0 — Fundação de tokens e componentes (baixo risco) · ~5 dias

> **Status (2026-06-25): fundação CONCLUÍDA e validada** — app sobe sem crash, imports
> OK. A _criação_ dos componentes/tokens está pronta; a _adoção ampla_ nas telas
> (tooltip em todas as ações, danger nos formulários, empty states nas listagens) segue
> como trabalho contínuo, entrelaçado com as Fases 2–3.

| ID | Tarefa | Status | Entregue |
|----|--------|--------|----------|
| F0.1 | Tokens `SPACE_*` na camada de tema (P2-4) | ✅ Criado | `SPACE_XS..XL` em [support.py](src/ui/support.py) |
| F0.2 | _Factories_ `primary/secondary/danger_button` (P2-5) | ✅ Criado · adoção ⏳ | [components/buttons.py](src/ui/components/buttons.py) |
| F0.3 | Componente `Tooltip` próprio (P1-2) | ✅ Criado · adoção ⏳ | [components/tooltip.py](src/ui/components/tooltip.py) |
| F0.4 | `EmptyState` + CTA (P1-9) | ✅ Criado · 1 adoção | [components/empty_state.py](src/ui/components/empty_state.py); piloto em `_require_tournament` |
| F0.5 | Remover temas órfãos + extrair modal (P2-7, P2-10) | ✅ Feito | 4 JSON removidos; [components/donation.py](src/ui/components/donation.py) |

**Adoção concluída (2026-06-25):**
- `danger_button` em **9 ações destrutivas / 6 telas** (tournaments, admin_calendar,
  admin_training, settings_users, club_members, pairing_results "Excluir rodada") —
  **eliminou todos os literais de cor** `#a3423c`/`#822f2a`/`"red"` (P2-3 e P2-1 parcial:
  0 ocorrências restantes em `src/ui`). Confirmado visualmente: "Excluir rodada" destacado.
- `Tooltip` (helper `_tip_btn`) nos botões crípticos da toolbar de Rodadas (QR, súmulas,
  cartões). Cobertura total dos tooltips da toolbar converge com **F2.1**.
- `EmptyState` (com CTA navegável) no Dashboard (avisos/eventos) e em `_require_tournament`
  (~8 telas de torneio). Bônus: `text_color` do erro de login tokenizado (`THEME_DANGER`).

A camada `src/ui/components/` é a fundação para as telas migradas.

### Fase 1 — Refatoração estrutural (incremental) · ~10–12 dias

> **Sem _big-bang_.** Extrai serviços de tema/navegação, depois migra **uma tela-piloto**
> e valida o padrão antes de propagar.

> **Status (2026-07-25): F1.1 CONCLUÍDA.** Nova camada
> [`src/ui/theme.py`](src/ui/theme.py): tokens de cor/tipografia/espaçamento,
> presets, temas curados e um registro de listeners (`on_theme_change` /
> `notify_theme_change`). O `_propagate_theme_globals` **morreu** — não há mais
> reescrita de `sys.modules`. A troca de preset alcança quem já importou o token
> porque `ColorToken` é uma lista de dois elementos **mutada no lugar**: quem fez
> `from ..support import *` guarda a referência ao mesmo objeto. O customtkinter
> aceita lista de cores nativamente (é como os temas JSON dele já vêm), então não
> houve adaptação nas telas. `support.py` re-exporta os nomes só enquanto as telas
> usam `import *` (some na F1.6); `components/` e `app.py` já importam de `theme`.
> Cobertura em [tests/test_ui_theme.py](tests/test_ui_theme.py), incluindo a
> garantia de que o hack não volta.

> **Status (2026-07-25): F1.2 CONCLUÍDA.** Aplicar tema deixou de **destruir e
> recriar** `statusbar` e `content` (P0-6): agora é `configure()` widget a
> widget, em [`restyle.py`](src/ui/restyle.py). Como nada é recriado, foco,
> scroll e seleção continuam onde estavam — por construção, não por esforço.
> O ponto delicado eram as duas origens de cor: **token** (já mutado pela F1.1,
> bastava repintar) e **padrão do `ThemeManager`** (copiado para dentro do widget
> quando ele nasceu). Para o segundo, `snapshot_defaults()` tira um retrato
> **antes** da troca e só acompanha quem ainda seguia o padrão antigo — um botão
> de perigo mantém o vermelho, em vez de virar accent. Verificado medindo a cor
> **desenhada** no canvas, não a pedida via `cget`.
>
> **Gap adjacente, agora mais visível:** a cor de seleção da `ttk.Treeview` é
> `#334155` fixo e não acompanha o tema — a linha selecionada fica azul-ardósia
> sobre um tema verde. É dívida pré-existente (P2-1) e cabe na **F3.3**.

> **Status (2026-07-25): F1.3 e F1.4 CONCLUÍDAS.** [`navigation.py`](src/ui/navigation.py)
> passa a ser o **registro único** de destinos (`Destination` como dado puro,
> antes duplicado entre o `tk.Menu` e o command palette) mais o `Navigator`
> (`go` / `refresh_current` / `record`). O F5 virou `refresh_current()`; a paleta
> deriva do registro; `_current_view_method` continua legível pelas telas legadas
> como propriedade. O módulo **não importa Tk**, então navegação e busca (que
> ignora acento e caixa) são testáveis sem abrir janela.
> [`shell.py`](src/ui/shell.py) recebeu a casca — conteúdo, statusbar, toasts,
> progresso, atalhos, command palette e a ligação com o `Navigator` —, e
> `AlbericusApp` herda dela **coexistindo com os 14 mixins**, sem _big-bang_.
> `app.py` caiu de ~1.200 para ~800 linhas. Um teste garante o arranjo: a casca é
> dona da cromagem, não conhece nenhuma tela e não importa `screens/`.

| ID | Tarefa | Esforço | Impacto | Risco | Depende | Aceite |
|----|--------|---------|---------|-------|---------|--------|
| ✅ F1.1 | `theme.py` (tokens + `on_change` listener); matar `_propagate_theme_globals` (P0-5) | 2d | A | M | — | Tokens importados de `theme`; sem `sys.modules` hack |
| ✅ F1.2 | Tema sem destroy/rebuild: `restyle()` por `configure()` (P0-6) | 3d | A | **M-A** | F1.1 | Trocar tema preserva foco/scroll/seleção |
| ✅ F1.3 | `Navigator` + registro único de destinos (de `_command_palette_actions`) (P0-1) | 2d | A | M | — | Navegação central; F5 via `refresh_current()` |
| ✅ F1.4 | `AppShell` (casca fina) coexistindo com mixins legados (P0-1) | 2d | A | M | F1.3 | App sobe via shell; mixins ainda funcionam |
| ✅ F1.5 | **Piloto**: migrar 1 tela para View/Controller/State + `dataclass` (P0-2, P0-3) | 3d | A | M | F1.4 | Tela testável sem subir app; zero `{"value":None}` |
| ✅ F1.6 | Imports explícitos na tela-piloto + 2 telas; lint anti-wildcard no CI (P0-4) | 1,5d | M | B | F1.5 | CI falha em novo `import *` |

> Após o piloto, cada tela-monstro migrada vira um épico próprio no backlog
> (`pairing_results_ui` → `screens/pairings/{view,controller,state}.py`, etc.).

> **Status (2026-07-25): F1.6 e F3.3 CONCLUÍDAS — com o gate de pé antes.**
> O `ruff check .` acusava **193 erros** e não havia CI: as duas tarefas pediam
> "lint no CI" que não existia. Primeiro o gate ficou verde (motor Gacrux
> vendorizado excluído do lint — é código de terceiro; bench de stress com
> per-file-ignore justificado; o resto corrigido de fato), depois veio
> [`.github/workflows/quality.yml`](.github/workflows/quality.yml): compilação,
> ruff, mypy, convenções de UI e os **644 testes sem janela** a cada push. As 108
> asserções que abrem janela ganharam o marcador `gui` e seguem rodando no
> Windows, onde o app é entregue.
>
> **F1.6:** `audit.py`, `home.py` e `reports.py` migradas para imports
> explícitos; as demais 21 ficam numa **linha de base que só encolhe** — um
> `import *` novo reprova, e uma tela migrada que sair da lista também reprova
> (a base não envelhece sozinha).
>
> **F3.3:** zero cor ou fonte cravada em `src/ui/screens`. A regra adotada é
> **nomear é permitido, embutir não**: as cores do Modo Projetor viraram uma
> paleta nomeada (contraste fixo, alheio ao tema — quem vê é a sala), o verde do
> WhatsApp virou constante de marca, e as cores-padrão do diploma viraram
> constante de **dado**. O resto virou token. Junto veio o gap que a F1.2 tinha
> exposto: as tabelas eram pintadas com valores fixos de modo escuro — agora há
> tokens de `Treeview` e `RESULT_STATE_COLORS`, resolvidos por `pick()`, e a
> tabela finalmente acompanha o tema claro.
>
> O lint tem [testes próprios](tests/test_ui_conventions_lint.py) que o fazem
> **reprovar de propósito**: um lint que nunca falha é decoração.

> **Status (2026-07-25): F1.5 CONCLUÍDA — o padrão está provado.**
> A tela de **Árbitros** virou pacote
> [`screens/referees/`](src/ui/screens/referees/): `state.py` (dado puro),
> `controller.py` (decide e fala com o serviço) e `view.py` (monta widgets e faz
> a ponte). Nem o estado nem o controlador importam Tk — os **18 testes** da
> tela rodam em milissegundos, sem abrir janela, que é o aceite da tarefa.
> O `{"value": None}` sumiu: o formulário é um `dataclass` congelado, e a view
> guarda a versão corrente por `nonlocal`. Detalhe que o próprio teste pegou: na
> primeira tentativa eu havia trocado o dicionário de estado por **outro
> dicionário** — a asserção reprovou e o `nonlocal` entrou no lugar.
> Ganhos que a fatia expôs de graça: campo nulo virava a palavra "None" no
> formulário, e o payload agora manda `active` como 0/1 (o banco guarda inteiro).
> Import externo intacto: `from .screens.referees import RefereePagesMixin`.
>
> **Próximo passo é o B-6**: cada tela-monstro migra seguindo este molde.

### Fase 2 — UX e feedback (salto de percepção) · ~7 dias

> O que mais muda a sensação de "profissional" no uso diário. Boa parte independe da Fase 1.
>
> **Status (2026-06-25): F2.1 CONCLUÍDA.** Toolbar de Rodadas hierarquizada — 1
> ação primária preenchida (`Gerar próxima rodada`), `Exportar ▾`/`Mais ▾`
> recolhem as 11 secundárias (exportar/imprimir/súmulas/cartões e
> pré-visualizar/fechar/trocar cores·jogador/QR), `Excluir rodada` isolado à
> direita e `Modo Projetor` com destaque próprio; tooltips em todas as ações
> visíveis. Aceite atendido (≤6 ações visíveis; destrutivo separado). Novo
> componente reutilizável [`menu_button`](src/ui/components/menu_button.py) +
> `tip=` nas factories de botão. Restam F2.3–F2.5.
>
> **Status (2026-06-25): F2.2 CONCLUÍDA.** Eliminados os 26 `messagebox` nativos de
> `src/ui` (0 chamadas restantes). Novo [`dialogs`](src/ui/components/dialogs.py)
> temático: `confirm_dialog` (Sim/Não, `danger=` recolore), `tri_state_dialog`
> (Sim/Não/Cancelar) e `alert_dialog` (OK) — bloqueantes, com `grab` salvo/restaurado
> p/ abrir sobre outro modal. Helpers de feedback unificados em `ErrorCatchingMixin`:
> info/aviso/erro recuperável viram **toast** (ou alerta bloqueante quando há modal
> aberto, senão o toast ficaria escondido); erro inesperado vira modal com código+log.
> `_show_error` agora é único (removidas as cópias de `app.py` e a antiga do mixin),
> aceita `str|Exceção` via `_classify_error` puro — corrige bug latente em que
> `_show_error("texto")` exibia "Erro inesperado". `_confirm_action` ganhou `danger=`.
> **Revisão pós-implementação:** `Enter` ficou **inerte** em diálogo destrutivo (só
> confirma no clique — evita exclusão por Enter reflexo, ESPEC §6); rótulos padrão
> acentuados ("Não") já nascendo em conformidade com **F3.5**; novo token
> `THEME_WARNING`/`THEME_WARNING_TEXT` eliminou as duas cores de aviso divergentes e
> hardcoded (toast × diálogo — adianta parte de **P2-1**); cobertura em
> [tests/test_ui_dialogs.py](tests/test_ui_dialogs.py) (11 testes: retorno de cada
> botão, Esc/Enter, Enter inerte em destrutivo, modal-sobre-modal com `grab`
> restaurado). Pendências conhecidas: `_show_toast` ainda vive em `app.py` e é
> chamado por `hasattr` a partir do mixin (mover p/ `components/toast.py` destrava
> **F2.4**); `support ↔ components` só não cicla por imports dentro de função —
> resolve em **F1.1** (`theme.py`).

> **Status (2026-07-25): F2.3 CONCLUÍDA.** Zero `threading.Thread` cru em `src/ui` —
> os 4 restantes (sync de ratings online, envio simples e disparo em massa de e-mail,
> download da lista FIDE) passaram pelo helper único `_run_background`, junto com a
> importação CBX, que era **síncrona** e travava a janela. `_generate_round` e
> `_preview_next_round` também saíram da thread da UI: permissão e confirmações
> continuam no laço principal (abrem modal), só o emparceiramento vai para o
> background — era o congelamento mais visível do dia a dia (P1-3). Novo
> [`BusyIndicator`](src/ui/components/busy.py): barra indeterminada na statusbar,
> **com contagem de tarefas** (N ações simultâneas → uma barra; só o fim da última
> a esconde), ligada/desligada dentro do próprio `_run_background` — nenhuma tela
> precisa saber que ela existe. Erro em background já cai no `_show_error`
> unificado da F2.2, ou seja, vira toast. Cobertura em
> [tests/test_ui_busy.py](tests/test_ui_busy.py).

> **Status (2026-07-25): F2.4 e F2.5 CONCLUÍDAS — Fase 2 fechada.** O toast saiu de
> `app.py` para [`components/toast.py`](src/ui/components/toast.py) (`ToastStack`) e
> ganhou **botão de ação**; `_show_toast` virou delegador fino, então os 60+
> call-sites e os stubs de teste seguem intactos. Isso resolve também a inversão de
> camada apontada na revisão da F2.2. Novo helper `_delete_with_undo` no mixin:
> exclui, oferece "Desfazer" e recria o registro a partir de um retrato tirado
> **antes** da exclusão. Aplicado nas três exclusões sem dependentes do painel de
> arbitragem (ajuste de pontos, bye solicitado, proibição de emparceiramento),
> individual e equipes. **Exclusão com cascata continua sem undo**, por decisão da
> ESPEC §5.1 — passar `restore=None` mantém só a confirmação explícita; o id
> recriado difere do original, então o retrato só serve para registros folha.
> F2.5: KPI clicável ganhou realce de borda no hover, com a borda sempre presente
> (na cor do painel) para o realce não deslocar o layout em 1px, e uma checagem de
> `winfo_containing` para o realce não piscar ao passar do card para os rótulos.
>
> **Achado de infraestrutura de teste.** Ao rodar os arquivos de UI juntos, a suíte
> de toast era **inteiramente pulada** (7 `skipTest` silenciosos): `after` órfãos de
> uma raiz Tk destruída atrapalham a criação da raiz do arquivo seguinte, que falha
> com `couldn't read init.tcl`. `cancel_pending_callbacks` foi extraído de
> `test_ui_layout` para [tests/support/ctk_cleanup.py](tests/support/ctk_cleanup.py)
> e agora é usado por todos os arquivos de UI antes do `destroy()` — era por ter
> esse cancelamento que `test_ui_layout` nunca falhava. **Resolvido o pulo em
> massa**; restam ~2 skips intermitentes (de ~640 testes) na criação da raiz
> dentro do próprio `test_ui_layout`, que já existiam antes. Uma "âncora" de raiz
> Tk na sessão foi testada e **não** serve: ela vira o `_default_root` do tkinter
> e os menus da `AlbericusApp` passam para o interpretador errado, quebrando ~6
> testes (registrado em `tests/conftest.py` para ninguém repetir a tentativa).

| ID | Tarefa | Esforço | Impacto | Risco | Depende | Aceite |
|----|--------|---------|---------|-------|---------|--------|
| ✅ F2.1 | Hierarquizar a toolbar de Rodadas: primárias/`Exportar▾`/`Mais▾`/danger isolado (P1-1) | 2d | A | B | F0.2 | ≤6 ações visíveis; destrutivo separado |
| ✅ F2.2 | Confirmação CTk + toast de erro; remover `messagebox` (P1-4); unificar `_show_error` | 1,5d | A | B | F0.2 | Zero `messagebox` em telas migradas |
| ✅ F2.3 | Progresso em ações longas + migrar 4 threads crus p/ `_run_background` (P1-3, P1-5) | 2d | A | M | — | Botão desabilita + spinner; erro vira toast |
| ✅ F2.4 | Undo em exclusões via toast com ação (P1-6) | 1,5d | A | M | F2.2 | "Excluído · Desfazer" onde aplicável |
| ✅ F2.5 | Hover visual em KPI cards clicáveis (P1-10) | 0,5d | M | B | — | Cursor + realce no hover |

### Fase 3 — Navegação e polish (diferenciação) · ~8 dias

> **Status (2026-07-25): F3.1 CONCLUÍDA.** Sidebar persistente em
> [`components/sidebar.py`](src/ui/components/sidebar.py), espelhando o registro
> da F1.3 — acrescentar destino em `DESTINATIONS` o faz aparecer na barra, sem
> lista paralela. Grupos (Clube · Treinamento · Gestão · Torneio · Ferramentas ·
> Configurações), ícones e **item ativo destacado**, inclusive quando a tela é
> aberta por atalho, pela paleta ou por um botão da própria tela (a barra assina
> `Navigator.subscribe`). O `tk.Menu` permanece como fallback.
>
> **A barra é responsiva, e não por enfeite:** a suíte reprovou a primeira versão
> — com 235px à esquerda, telas densas empurravam botão para fora da janela. A
> medição mostrou que a **Exportar** sozinha pede ~1.375px de conteúdo. Daí os
> três modos: `full` (≥1500px reais), `rail` só com ícones e tooltip (≥1440) e
> `hidden` abaixo disso, quando o menu volta a ser a navegação. Registrado como
> **B-8**: a tela Exportar merece um layout mais estreito — hoje é ela que
> define o limiar.
>
> **Status (2026-07-25): F3.2 CONCLUÍDA.** O app deixa de abrir no cadastro
> "Perfil do Clube" e passa a abrir em **Início**, com as pendências acionáveis
> do momento e um botão que leva direto onde cada uma se resolve (*deep link*
> pelo registro da F1.3). As regras ficam em [`home.py`](src/ui/home.py), **puras
> e sem Tk** — `HomeSnapshot` é dado simples e `build_pendencies` decide o quê e
> em que ordem; a tela ([`screens/home.py`](src/ui/screens/home.py)) só lê o banco
> e desenha. Cobertas: arbitragem bloqueante, QR aguardando aprovação, resultados
> a lançar, torneio sem rodadas (mandando **inscrever** quando nem jogador há —
> gerar rodada não destravaria), torneio concluído → diplomas, mensalidades em
> atraso e próximo evento. Sem nada pendente, a tela diz "Tudo em dia" em vez de
> ficar vazia. Cada leitura do estado é isolada: um serviço com problema vira
> ausência daquele dado, não tela em branco. Um teste garante que **todo destino
> de pendência existe no registro** — deep link quebrado seria pior que pendência
> nenhuma.
|----|--------|---------|---------|-------|---------|--------|
| ✅ F3.1 | Sidebar persistente com grupos + item ativo (P1-7) | 4d | A | M | F1.3 | Navegação primária visual; menu vira fallback |
| ✅ F3.2 | Dashboard contextual pós-login (pendências acionáveis) (P1-8) | 3d | A | M | F1.3 | Abre em pendências com deep-link |
| ✅ F3.3 | Tokenizar cores/fonts: 58 hex + 23 fonts + `#a3423c` (P2-1,2,3) + lint CI | 2d | M | B | F1.1 | CI barra novos literais em `screens/` |
| ✅ F3.4 | Modo Livre "não mostrar de novo" (P1-11); Aulas/Exercícios → "(em breve)" (P1-12) | 0,5d | M | B | — | Sem fricção repetida; rótulo claro |
| ✅ F3.5 | Corrigir acentuação das labels visíveis (P2-8) | 0,5d | M | B | — | "Configurações/Aparência/Segurança" |
| ✅ F3.6 | Login com split layout + branding + versão (P2-6) | 1d | B | B | — | Layout dividido; espaço p/ "primeiro acesso" |

> **Status (2026-07-25): F3.4 e F3.5 CONCLUÍDAS.** O aviso do Modo Livre ganhou
> "Não mostrar novamente" (persistido em `free_mode_notice_hidden`); marcada a
> caixa, o menu passa direto à criação — que **continua pedindo o nome**, então
> nada é criado sem confirmação. A escolha vale nos dois caminhos de saída
> (Iniciar e Cancelar). Aulas/Exercícios viraram "Aulas (em breve)" —
> desabilitado sem explicação lê como quebrado, não como escopo. F3.5 acentuou
> **93 rótulos curtos** em `src/ui` (incluindo Configurações/Aparência/Segurança
> do critério de aceite). Fronteira deliberada: só rótulos, não frases de
> diálogo — reescrever mensagens inteiras é trabalho do catálogo i18n (**B-3**).
> **Divergência conhecida:** cabeçalhos de exportação em `src/services/export_*`
> seguem sem acento (ver **B-7**) — mexer neles altera arquivo entregue e
> formato consumido por terceiros, o que não cabe nesta tarefa.

> **Status (2026-07-25): F3.6 CONCLUÍDA — Fases 0 a 3 encerradas.** O login era
> uma caixa de 420×400 sem espaço para nada. Agora são duas faixas: marca à
> esquerda (logo, nome, propósito) e formulário à direita, com um botão
> **"Primeiro acesso?"** que explica onde se cadastra um operador — **sem
> revelar credencial**, porque senha na tela de login é convite a nunca trocá-la
> (há teste guardando isso). A versão saiu do título cravado e ganhou fonte
> única em [`src/core/version.py`](src/core/version.py); o rodapé mostra
> `v1.0 · banco v43`, e a versão do schema encurta muito o diagnóstico de um
> chamado. Divergência a resolver quando for publicar: o `pyproject.toml` diz
> `0.1.0` (versão de empacotamento) — os dois números precisam contar a mesma
> história.

### Fase 4 — Backlog em execução

- ✅ **B-1** Persistência de layout de colunas por usuário (P2-9).
- ✅ **B-2** Auditoria de contraste WCAG AA + preset alto contraste (P2-11).
- ✅ **B-3** i18n: catálogo `i18n/pt_BR.json` + a cromagem migrada (P2-12).
  **Continuação:** as 21 telas seguem com texto literal — migram junto com a B-6,
  quando cada uma for aberta de qualquer forma.
- ✅ **B-4** `Treeview` grande (P2-13) — medida e adiada; ver o status abaixo.
- ✅ **B-5** Cache de figuras matplotlib quando dados não mudam (P2-14).
- 🔄 **B-6** Migrar telas-monstro para 3 camadas (continuação de F1.5) — **em
  execução**: Torneios migrada; a fila está no status abaixo, em ordem.
- ✅ **B-7** Acentuar cabeçalhos/títulos de `src/services/export_*` (F3.5) — a
  decisão de compatibilidade foi tomada: acentuar **inclusive CSV/XLSX**, com
  fronteira ASCII no pacote Access, TRF e PGN. Ver o status abaixo.
- ✅ **B-8** Estreitar o layout da tela **Exportar** — feito; o gargalo mudou de
  dono (ver o status abaixo). **Continuação:** as cinco telas administrativas
  densas (Ranking interno, Financeiro, Calendário, Exercícios, Relatórios) são
  quem define o limiar agora.

> **Status (2026-07-25): B-4 — a medição desmentiu a premissa; virtualização
> NÃO foi implementada.** O achado P2-13 dizia "lento em 1.000+ linhas". Medido:
>
> | jogadores | abrir a tela | só as linhas | fatia |
> |---|---|---|---|
> | 1.200 | 849 ms | 11 ms | 1,3% |
> | 3.000 | 597 ms | 20 ms | 3,3% |
> | 6.000 | 677 ms | 42 ms | 6,3% |
>
> O custo da tela é **praticamente constante** e não vem da tabela: vem de
> montar os widgets do formulário (14 campos, `CTkOptionMenu`, scrollbars) a
> cada visita — no perfil, quatro `CTkOptionMenu` sozinhos custam 157 ms.
> Virtualizar a tabela atacaria 6% do problema, cobrando complexidade e tirando
> do usuário a rolagem contínua. **Adiada com número, não com opinião**, e com
> um teste que reprova se encher 5.000 linhas passar do orçamento — a hora de
> virtualizar volta à pauta sozinha.
>
> O que a medição mostrou que **de fato** cresce com a base é o caminho por
> tecla: cada `<KeyRelease>` numa busca esvazia a tabela e reinsere tudo. Daí
> [`components/debounce.py`](src/ui/components/debounce.py) — agendamento
> injetado, testável sem janela — aplicado nas **14 caixas de busca e filtro de
> data**. A paleta de comandos ficou de fora de propósito: a lista é curta e
> qualquer atraso ali seria sentido como travamento.
>
> **Achado de infraestrutura de teste, e este é o mais sério.** Ao debouncear a
> busca da arbitragem, o teste que a cobria continuou verde — porque ele nunca
> havia buscado. Três detalhes silenciosos: o `bind` vive no `tk.Entry` **de
> dentro** do `CTkEntry`; evento de tecla **sem `keysym`** o Tk descarta; e sem
> **foco** ele também não é entregue. Nenhum levanta erro. A asserção antiga
> (`"mesa 1"` → 2 linhas) media a tabela **não filtrada**. Agora há
> [`tests/support/ui_input.py`](tests/support/ui_input.py) (`type_into`) e o
> teste exige filtro de verdade (0 de 2) mais o `flush()` do adiamento.
> **Status (2026-07-25): B-2 CONCLUÍDA — 77 reprovações viraram zero.**
> A auditoria foi escrita antes das correções, e o número dizia tudo: **77
> pares abaixo de AA nos 6 temas curados**. O pior deles era o rótulo do botão
> primário com accent âmbar no modo escuro — **1,30:1**, texto que só existia
> no código.
>
> A parte difícil não é a conta (dez linhas de WCAG em
> [`contrast.py`](src/ui/contrast.py)), é o **contrato**: saber que o texto de
> ajuda cai sobre o painel, e que o painel muda com o preset de frames.
> [`theme_audit.py`](src/ui/theme_audit.py) declara os 33 encontros de cor que
> a tela produz; par que existe e não está lá é ponto cego.
>
> Três causas explicaram quase tudo:
> 1. **Tinta cravada.** O branco fixo do toast e o cinza padrão do customtkinter
>    (`#DCE4EE`) não sabem sobre o que estão. Agora a tinta é **calculada**
>    (`best_ink`): botão amarelo nasce com texto escuro, botão índigo com texto
>    claro, sem tabela de exceções para alguém esquecer de atualizar.
> 2. **Accents na faixa errada.** Os tons 500 nascem para fundo escuro; sobre
>    painel claro nenhum dos 15 alcançava os 3:1 de componente — nem o azul
>    padrão (2,99:1). A face clara foi para a faixa 600/700.
> 3. **Cinzas apagados demais.** `#94A3B8` em "bye"/"anulado" dava 2,34:1 sobre
>    linha clara. Discreto continua discreto em `#5C6B80`; o que ele não pode é
>    ser ilegível, porque "anulado" muda o que o árbitro faz com aquela mesa.
>
> Resultado: **0 reprovações** nos temas curados e — efeito colateral do item 2
> — nas **5.070 combinações** que o modo avançado permite montar. O preset
> **Alto Contraste** entrou como tema curado e é o único cobrado em **AAA
> (7:1)** nas superfícies (pior par: 12,77:1); para isso, `apply_bg_preset`
> passou a aceitar override de cor de texto, e a devolvê-la ao sair — senão o
> preto puro grudaria no tema seguinte. 21 testes, nenhum abre janela.

> **Status (2026-07-26): B-7 CONCLUÍDA.** A F3.5 tinha deixado isto de fora
> porque mexe em **arquivo entregue**. A decisão tomada: **acentuar tudo que
> gente lê**, inclusive CSV e XLSX — num app de clube, cabeçalho casado com a
> tela vale mais do que a hipótese de um script de terceiro que faz *match* por
> texto exato.
>
> **A parte que exigiu desenho foi a fronteira.** O pacote **Access** reusa os
> **mesmos** construtores de seção das exportações para humanos, e ali o texto
> vira nome de coluna de CSV lido por driver ODBC com `schema.ini` — acento é
> risco de importação, não polimento. A saída não foi manter duas listas de
> cabeçalhos (que divergem no primeiro descuido): a lista é **uma só**,
> acentuada, e [`text_ascii.py`](src/services/text_ascii.py) dobra para ASCII
> **no ponto de entrega**. A regra fica visível no código — quem exporta para
> máquina chama `to_ascii`; quem exporta para gente, não.
>
> TRF/Chess-Results e PGN não passam pelos construtores de seção (vão pelos
> `federation_exporters`), então continuaram ASCII sem esforço; o **JSON
> público** usa chaves em inglês, e por isso nunca esteve em risco.
>
> 281 literais acentuados em 8 módulos. Onze testes foram atualizados por
> asserirem o texto antigo — é exatamente o que muda quando se muda um arquivo
> entregue. Um deles, o do pacote Access, passou a **exigir ASCII** com um
> comentário dizendo por quê: era o único que poderia regredir em silêncio, já
> que quem descobriria seria o usuário, na hora de importar.
> **Status (2026-07-25): B-8 CONCLUÍDA — e o gargalo mudou de dono.** A tela
> **Exportar** punha os três seletores e as três ações numa linha só e pedia
> **1.360px**; empilhar as ações numa linha própria derrubou a exigência dela
> para **menos de 1.000px**. Mas a medição seguinte mostrou que ela nem era o
> problema inteiro: em **toda** tela de torneio, o único widget fora da janela
> era sempre o mesmo — o último item ("Diplomas") da **barra do torneio**, oito
> botões de 112px numa linha rígida de ~950px. Agora ela quebra em quantas
> linhas couberem, recalculando na mesma carona do `<Configure>` que a sidebar
> já usa. Quebrar custa ~38px de altura, que sobra; insistir numa linha custa um
> botão inacessível, que não tem substituto visível.
>
> **Limiares remedidos com as 23 telas do smoke**, e não só com as de torneio —
> foi aí que apareceu o novo dono do gargalo: as telas **administrativas
> densas** (Ranking interno, Financeiro, Calendário, Exercícios, Relatórios).
>
> | modo da sidebar | antes | depois |
> |---|---|---|
> | completa | 1.500px | **1.416px** |
> | rail (só ícones) | 1.440px | **1.260px** |
>
> Ou seja: **a navegação sobrevive a 180px a menos de janela**. O ganho não é
> maior porque a Exportar deixou de ser o limite e outras cinco telas assumiram
> — registrado como continuação da B-8, com nome e número, em vez de virar
> dívida anônima.
>
> Um detalhe que o teste pegou: medir a largura pelo **cabeçalho** não funciona
> (ele nasce junto com a tela e ainda mede 1px); pelo `content`, que sobrevive à
> troca de tela, funciona.

> **Status (2026-07-26): B-6 EM EXECUÇÃO — Torneios migrada; a fila está aqui.**
> A B-6 é épico por natureza: sete telas de 1.000 a 1.900 linhas. Migrar todas
> num passo seria trocar um diff revisável por um irrevisável, então este passo
> migra **uma tela de verdade** e prova que o molde do piloto escala — o piloto
> de Árbitros tinha 127 linhas; a tela de Torneios tem 315 só na lista.
>
> `screens/tournaments.py` virou pacote: `state.py` (regras do formulário e
> forma da linha), `controller.py` (decide e fala com os serviços, sem Tk),
> `view.py` (monta widgets) e `pages.py` — as **outras** telas do domínio,
> intactas, registradas como as próximas. O import externo não mudou.
>
> **O que a extração expôs**, e que o teste agora guarda: a tela *desabilita*
> clube e turma fora do escopo, mas desabilitar **não esvazia**. Quem escolhesse
> um clube e voltasse para "avulso" criava o torneio carregando o clube junto —
> sem nada na tela denunciando. Agora `payload()` zera o que o escopo não pede, e
> um teste cobra que "o que a tela habilita" e "o que a validação exige" saiam da
> **mesma** função. 26 testes, nenhum abre janela.
>
> **Dois achados de infraestrutura.** O lint anti-`import *` reconhecia `.` e
> `..`, mas não `...` — mover uma tela para subpacote **escapava do lint em
> silêncio**; a regex agora aceita qualquer profundidade. E um teste corrigia
> `filedialog` no módulo errado (`screens.tournaments`), funcionando só porque o
> `import *` re-exportava o nome de lá; agora aponta para quem de fato o usa.
>
> **Fila da B-6**, por ordem de valor sobre risco:
> 1. `pairing_results_ui` (1.922) — a maior e a mais usada; entra depois de
>    alguma outra pagar o aprendizado, porque é a que mais dói se quebrar;
> 2. `tournament_players_ui` (1.613);
> 3. `pairing_arbitration_ui` (1.527);
> 4. `admin_training_finance` (1.226), `admin_exercises_inventory` (1.126),
>    `club_members_ui` (1.073), `settings_certificates_ui` (1.062);
> 5. as três telas restantes de `tournaments/pages.py` (Central, Equipes,
>    árbitros do torneio) — já isoladas, é o passo mais barato.
>
> Cada uma vale um PR próprio, e o texto delas migra para o catálogo da **B-3**
> no mesmo passo: a tela vai ser aberta de qualquer forma.
> **Status (2026-07-26): B-3 CONCLUÍDA — preparação, e só.** A ESPEC §6 e §8 são
> explícitas: extrair strings mantendo **só PT-BR**, sem implementar inglês. O
> valor imediato não é falar inglês; é ter **um lugar** onde o texto mora.
>
> Migrar as ~21 telas de uma vez seria trocar milhares de literais legíveis por
> `t("chave")` num diff que colide de frente com a **B-6** — e as telas vão ser
> abertas na B-6 de qualquer jeito. Então a fatia escolhida foi a **cromagem**:
> o registro de navegação (29 destinos), os diálogos e a casca. É exatamente o
> que uma versão em inglês precisaria primeiro, e é o que quase não muda.
>
> A decisão de desenho está no registro: `Destination` **deixou de guardar** o
> rótulo. Guarda identidade (`key`) e comportamento (`method`); rótulo, palavras
> de busca e grupo viraram **propriedades** que leem o catálogo na hora de
> exibir. Por isso trocar o catálogo troca o idioma **sem reconstruir o
> registro** — há um teste que faz exatamente isso e volta atrás.
>
> **Chave ausente devolve a própria chave**, de propósito: aparece feia na tela,
> impossível de ignorar. O que impede isso de chegar ao usuário é o teste que
> varre as chamadas de `t()` em `src/` e cobra que cada chave exista — e o
> inverso, que o catálogo não acumule chave órfã. Esse segundo **reprovou na
> primeira execução** e pegou uma chave que eu havia adicionado sem usar.
>
> Detalhe de empacotamento que passaria batido: o caminho do catálogo precisa da
> mesma checagem de `sys.frozen` que o `assets/` usa, e o `albericus.spec`
> precisou levar `i18n/` no build — senão o app empacotado abriria mostrando
> `nav.club` no lugar de "Perfil do Clube".

> **Status (2026-07-25): B-1 CONCLUÍDA — com uma divergência deliberada.**
> O backlog dizia "reaproveitar `ColumnLayoutEditor`", e **não foi isso**. Aquele
> editor escolhe *quais* colunas e em que ordem saem no **relatório de
> classificação**, por torneio, e seu registro (`LAYOUT_REGISTRIES`) só conhece
> `standings`. O achado do P2-9 é outro: as ~59 tabelas de tela nascem com
> `widths={...}` cravado e o usuário não consegue guardar um ajuste. Levar o
> editor para lá significaria abrir um diálogo para cada tabela; a interação
> natural é arrastar o separador, que já existe no ttk e ninguém escutava.
>
> Então: arrastou, ficou guardado — por **usuário** (dois operadores na mesma
> máquina não disputam largura), em tabela nova (`ui_column_layouts`, schema
> **v44**) e não em `app_settings`, cuja lista fixa de chaves permitidas não
> comporta um conjunto aberto de tabelas.
>
> Três decisões que o código registra: **a identidade da tabela sai dos dados**
> (hash de colunas + títulos), porque exigir uma chave em 59 chamadas seriam 59
> chances de errar; **guarda-se o desvio, não a largura**, para que mudar um
> padrão amanhã alcance quem nunca arrastou aquela coluna; e **largura tem piso**
> (40px), senão o arrasto consegue esconder dado sem o usuário perceber.
>
> O teste na janela real expôs o furo do primeiro desenho: **três tabelas são
> montadas à mão, fora do `_make_tree`** (frequência e títulos em Sócios, planos
> em Usuários) — o teste pegou justamente uma delas e a largura não voltava.
> Daí `_remember_column_widths(tree)` receber a tabela **pronta** e ler dela
> colunas, títulos e padrões, em vez de depender do helper: as três entraram com
> uma linha cada, sem virar exceção. Saída de emergência em Configurações →
> Aparência ("Restaurar largura das colunas"), porque arrastar não tem desfazer.
> 33 testes sem janela + 4 na janela.

> **Status (2026-07-25): B-5 CONCLUÍDA.** O achado ao medir foi outro: o caro
> não era montar a figura, era o `pyplot`. Por gráfico, no backend TkAgg —
> `plt.subplots` + embutir: **321 ms**; a mesma coisa com `Figure()` direto,
> sem o manager global: **76 ms**; vinda do cache: **55 ms**. Então a tarefa
> virou duas: o Dashboard deixou de passar pelo `pyplot` (o que já resolve 3/4
> do custo e dispensa o `plt.close()` para não vazar) e ganhou um cache de
> figuras. Visita repetida com dois gráficos: ~640 ms → ~110 ms.
>
> A separação segue o molde da F1.5: [`charts.py`](src/ui/charts.py) é puro
> (cache e chaves, sem Tk **nem matplotlib**),
> [`dashboard_figures.py`](src/ui/screens/dashboard_figures.py) monta as figuras
> sem Tk, e a tela ficou só com painéis e embutir.
>
> **O risco de um cache é mostrar número velho**, então o contrato é a chave:
> tudo que entra no desenho entra nela. A paleta virou um `dataclass` congelado
> com as **sete** cores usadas — a tela antes lia três e usava sete, e uma cor
> fora da chave devolveria o gráfico do tema anterior. Coberto em
> [tests/test_ui_charts.py](tests/test_ui_charts.py) (20 casos, nenhum abre
> janela). O que só a janela real prova ganhou dois testes em
> `test_ui_layout`: a figura cacheada **sobrevive à troca de canvas** — cada
> visita destrói o conteúdo e cria um `FigureCanvasTkAgg` novo sobre a mesma
> figura, inclusive entre raízes Tk destruídas (verificado à parte).

---

## 3. Sequenciamento recomendado

```
Semana 1   ██ Fase 0 (tokens, botões, tooltip, empty state)        ← começa já, baixo risco
Semana 2   ██ F1.1 theme.py + F1.3 Navigator        + F2.1 toolbar  ← UX em paralelo
Semana 3   ██ F1.4 AppShell + F1.5 piloto           + F2.2/F2.3
Semana 4   ██ F1.6 imports/lint + F1.2 tema s/ rebuild (mais arriscado, isolado)
Semana 5   ██ F3.1 sidebar
Semana 6   ██ F3.2 dashboard contextual + F3.3 tokenização + polish (F3.4-6)
Semana 7   ██ folga/estabilização + início do backlog B-6 (telas-monstro)
```

**Princípios de ordem:**
1. **Fase 0 primeiro** — fundação reutilizável de baixo risco; tudo depois reusa.
2. **Tema sem rebuild (F1.2) por último na fundação** — é o mais arriscado; isolar.
3. **UX (Fase 2) corre em paralelo** — toca pouco a arquitetura; entrega percepção cedo.
4. **Refactor é incremental** — piloto valida o padrão; nunca _big-bang_.

### MVP de percepção (~10 dias, se for cortar)

`F0.2` + `F0.3` (botões/tooltip) → `F2.1` (toolbar) → `F2.2`+`F2.3` (erro/loading) →
`F3.1` (sidebar). Transforma a cara do app sem depender do refactor estrutural completo.

---

## 4. CI, testes e qualidade

- **Lints novos no CI:** (a) proibir `from ..support import *` em `src/ui`; (b) proibir
  `#RRGGBB` e `CTkFont(size=` novos em `src/ui/screens`. Implementáveis como grep/ruff.
- **Gate de tipos:** ampliar mypy (hoje só `src/core`) para `src/ui/core` e telas
  migradas — controladores são puros e tipáveis.
- **Testes:** controladores testáveis sem Tk (cobertura nova); `test_ui_layout.py`
  permanece como _smoke_ de montagem. Validar troca de tema (F1.2) com checklist
  claro/escuro por componente.
- **Regra de PR:** cada tarefa = 1 PR pequeno, alinhado à modularização rígida.

---

## 5. Rastreabilidade

Todo achado (P0/P1/P2) mapeia para ≥1 tarefa (F*) ou item de backlog (B*). Métricas-alvo
e Definição de Pronto global em [ESPEC_UI_UX.md §10](ESPEC_UI_UX.md).
