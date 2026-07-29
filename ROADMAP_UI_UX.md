# ROADMAP_UI_UX — Plano de implementação de UI/UX do Albericus

> **Status:** v2 · **Data:** 2026-07-29 (v1: 2026-06-25) · **Spec:** [ESPEC_UI_UX.md](ESPEC_UI_UX.md)
> **Fases 0–3 encerradas; Fase 4 com B-6 em execução.** A v2 adiciona o catálogo
> **P3** (auditoria de campos de entrada e adoção, 2026-07-29) e a **Fase 5**.
> **MVP de percepção v2:** F5.1 → F5.2 → F5.5 → F5.6 → F5.7 (~1,5 semana).

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

### P3 — Campos de entrada e adoção (auditoria 2026-07-29)

Origem: auditoria de design de 2026-07-29 (código + screenshots de
`docs/manual_screenshots/`), motivada pela insatisfação com o visual dos campos de
entrada. Detalhes e estado-alvo em [ESPEC_UI_UX.md §2.3 e §4.6](ESPEC_UI_UX.md).

| ID | Achado | Evidência | Impacto |
|----|--------|-----------|---------|
| P3-1 | Campos fora do sistema de tema: `CTkEntry`/`CTkTextbox` nunca são patchados; do `CTkOptionMenu` só a setinha muda — corpo azul de fábrica em **141 widgets** com qualquer accent | [theme.py:382-393](src/ui/theme.py:382) | Alto |
| P3-2 | Contraste reprovado nos campos (medido com o próprio `contrast.py`): borda 2,74:1 / 2,13:1; rótulo do OptionMenu 2,74:1; placeholder 3,51:1; campo invisível nos presets sépia/floresta (1,04–1,12:1); Alto Contraste não alcança campos | [contrast.py](src/ui/contrast.py) | Alto |
| P3-3 | Anarquia dimensional: **67 larguras distintas** (33 Entry + 34 OptionMenu), altura 28px ao lado de botões de 36px, 5 raios de canto, `width=` inútil em 114 casos com `sticky="ew"`, campo de 1.250px na Config. do torneio | grep validado | Alto |
| P3-4 | Sem foco visível (0 bindings), estado de erro em só ~5 de 150 campos (3 implementações locais duplicadas), desabilitado indistinguível do habilitado | [support.py:528](src/ui/support.py:528), [settings.py:252](src/ui/screens/settings.py:252), [tournament_settings_ui.py:586](src/ui/screens/tournament_settings_ui.py:586) | Alto |
| P3-5 | OptionMenu tem anatomia de botão (bloco de cor sólida); `CTkComboBox` (anatomia de campo) nunca usado; calendário do date field com 3ª linguagem visual e tinta cravada | [club_members_ui.py:69](src/ui/screens/club_members_ui.py:69), [support.py:617](src/ui/support.py:617) | Médio |
| P3-6 | Placeholder em só 56/150 campos; nenhuma `font=` em campo; 3 famílias tipográficas coexistem (Roboto/Segoe UI/Inter); 286/332 labels sem cor tokenizada | grep validado | Médio |
| P3-7 | Muro de **25 botões idênticos** na tela Jogadores via `_grid_form_buttons` (15 call-sites); adoção das factories de botão em 17% (35 vs 170 crus) | [tournament_players/view.py:198](src/ui/screens/tournament_players/view.py:198), [app.py:1018](src/ui/app.py:1018) | Alto |
| P3-8 | `_show_info` (77×) manda para toast efêmero (320px/3,5s) conteúdo que precisa ser lido/copiado — URL do servidor QR, caminho do backup, narrativa de desempate — e validações de erro (pintadas de verde) | [support.py:349](src/ui/support.py:349), [pairing_results_ui.py:1262](src/ui/screens/pairing_results_ui.py:1262) | Alto |
| P3-9 | 57 tabelas sem zebra (tokens `THEME_TREE_EVEN/ODD` existem e não são aplicados), sem ordenação por cabeçalho, sem empty state, com scrollbar horizontal permanente (`stretch=False`) | [app.py:720-750](src/ui/app.py:720) | Alto |
| P3-10 | 21 diálogos ad-hoc fora de `components/dialogs.py`: ~16 sem Esc, 22 `geometry()` fixos que ignoram `ui_scale_percent` (120% padrão), ordem/cor de botões contraditória (Cancelar à direita, saída segura verde, diálogo sem botão de saída) | [pairing_results_ui.py:1210](src/ui/screens/pairing_results_ui.py:1210), [settings_users_ui.py:37](src/ui/screens/settings_users_ui.py:37) | Alto |
| P3-11 | Loading só na statusbar (barra de 6px longe da ação); `busy_widget` opcional em `_run_background` → duplo clique dispara a operação 2× | [components/busy.py](src/ui/components/busy.py), [pairings.py:394](src/ui/screens/pairings.py:394) | Médio |
| P3-12 | Três padrões de formulário (grid com aritmética manual de linhas, `_settings_stack`, `pack`); formulários de 14–25 campos sem nenhuma seção; larguras de painel divergentes (272/280/292) | [tournaments/view.py:111](src/ui/screens/tournaments/view.py:111) | Médio |
| P3-13 | Ordem de Tab = ordem de criação (0 `takefocus` no app); `Return` não submete formulários; foco de botão invisível — ESPEC §6 descumprida | grep validado | Médio |
| P3-14 | `tk.Menu` com 31 itens hardcoded paralelo ao registro (rótulos divergem da sidebar); sidebar **some** abaixo de 1.040px em vez de virar rail — notebook 1366px perde a navegação | [app.py:413-486](src/ui/app.py:413), [shell.py:396](src/ui/shell.py:396) | Médio |
| P3-15 | Regressão de acentuação: ~26 rótulos visíveis sem acento, a começar pela tela Início ("Inicio", "acao", "pendencia") — F3.5 corrigiu 93 e não deixou lint | [screens/home.py:56](src/ui/screens/home.py:56) | Médio |
| P3-16 | Defeitos pontuais visíveis nos screenshots: botões com texto cortado no Painel do árbitro ("justes de pontos (TRF25"), "None" literal em coluna de tabela, valor de data corrompido na Config. do torneio ("2026-05-182026-06-07") | `docs/manual_screenshots/` | Médio |

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

| ID | Tarefa | Esforço | Impacto | Risco | Depende | Aceite |
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
  **Continuação:** 20 telas seguem com texto literal — migram junto com a B-6,
  quando cada uma for aberta de qualquer forma. **Jogadores** já migrou (198
  chaves, catálogo em 271).
- ✅ **B-4** `Treeview` grande (P2-13) — medida e adiada; ver o status abaixo.
- ✅ **B-5** Cache de figuras matplotlib quando dados não mudam (P2-14).
- 🔄 **B-6** Migrar telas-monstro para 3 camadas (continuação de F1.5) — **em
  execução**: Torneios, **Jogadores** e **Arbitragem** migradas; a fila está no
  status abaixo, em ordem.
- ✅ **B-7** Acentuar cabeçalhos/títulos de `src/services/export_*` (F3.5) — a
  decisão de compatibilidade foi tomada: acentuar **inclusive CSV/XLSX**, com
  fronteira ASCII no pacote Access, TRF e PGN. Ver o status abaixo.
- ✅ **B-8** Estreitar o layout da tela **Exportar** — feito; o gargalo mudou de
  dono (ver o status abaixo). **Continuação CONCLUÍDA:** as cinco telas
  administrativas densas (Ranking interno, Financeiro, Calendário, Exercícios,
  Relatórios) deixaram de definir o limiar — a faixa de filtros agora quebra em
  linhas. **Segunda continuação CONCLUÍDA:** o Painel de Arbitragem saiu do
  caminho junto com a B-6, e a faixa que quebra linha ganhou o conserto que
  faltava (ver o status de 2026-07-27). O próximo dono é a tela de **Rodadas**,
  que já é a próxima da fila da B-6.

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

> **Status (2026-07-26): B-8 (continuação) CONCLUÍDA — as cinco telas densas
> saíram do caminho, e a conta de quebrar linha virou componente.**
> A B-8 tinha deixado o próximo dono do gargalo com nome e número. Medido tela a
> tela, com a barra **completa** forçada e a janela encolhendo de 20 em 20
> pixels (largura real; o CTk multiplica a geometria por 1,2):
>
> | tela | antes | depois |
> |---|---|---|
> | Ranking interno | 1.416px | **768px** |
> | Painel de Arbitragem | 1.416px | 1.200px |
> | Financeiro | 1.368px | **768px** |
> | Calendário | 1.368px | **768px** |
> | Relatórios | 1.296px | **768px** |
> | Exercícios | 1.272px | 984px |
> | Inventário | 1.200px | 1.104px |
> | Treinos | 1.200px | 936px |
>
> (768px é o **piso da varredura**, não o mínimo real: abaixo disso não medi.
> E a medição precisou ser refeita: a primeira não *forçava* o modo da barra, e
> como o app esconde a sidebar em janela estreita, ela media com a barra
> escondida — números 170px otimistas demais, comparando maçã com laranja.)
>
> O defeito era o mesmo em todas: uma **faixa de filtros numa linha rígida**.
> Agora ela quebra em quantas linhas couberem — a ideia que a B-8 provou na
> barra do torneio, agora em [`components/wrap_row.py`](src/ui/components/wrap_row.py),
> com a aritmética isolada e sem Tk em [`layout.py`](src/ui/layout.py). A barra
> do torneio passou a usar a mesma conta, em vez da cópia dela.
>
> **Três achados de medição. O primeiro explica por que a versão ingênua não
> funcionava, e o segundo é o que faz a conta fechar:**
> 1. **`CTkEntry(width=190)` não ocupa 190px.** O customtkinter multiplica pela
>    escala de UI (120% por padrão) e o widget desenha 228. Comparar largura
>    pedida (lógica) com espaço disponível (real) faz a conta concluir que cabe
>    — e era também por isso que a barra do torneio quebrava tarde demais.
> 2. **O `grid` não empilha linhas independentes.** A coluna 1 tem uma largura
>    só, e é a do item mais largo que caiu nela *em qualquer linha*. Somando
>    linha a linha, a tela Relatórios "cabia"; na tela, o último campo ficava
>    **1px** fora da janela, esticado pelo vizinho de baixo. A conta agora mede
>    pelas colunas do grid, e escolhe o maior número de itens por linha que
>    ainda cabe.
> 3. **Item ocupa ~3px a mais do que pede** (borda do frame). Três pixels não
>    parecem nada; com sete itens viram vinte. A faixa erra para o lado da
>    quebra, que custa altura — e altura sobra.
>
> **Um vazamento que o próprio desenho criou, e que o teste pegou.** A faixa
> precisa medir o `content` (largura própria, vinda da janela): medir a si mesma
> não funciona, porque no grid um container fica tão largo quanto o que ele
> pede, e uma faixa em linha única *empurra* o painel para a largura dela — daí
> nunca "ver" largura menor para justificar a quebra. Mas o `content` **não**
> morre com a tela (F1.2), então cada visita deixava mais um ouvinte de
> `<Configure>` falando com widget destruído. A faixa se desliga sozinha no
> `<Destroy>`; para conseguir, escuta o canvas interno do `CTkFrame`, porque
> `CTkFrame.bind` **não devolve** o funcid e `CTkFrame.unbind` recusa receber um
> — só sabe apagar todas as ligações da sequência, levando junto as internas do
> customtkinter. Há teste contando ouvintes depois de sete visitas.
>
> | modo da sidebar | antes | depois |
> |---|---|---|
> | completa | 1.416px | **1.200px** |
> | rail (só ícones) | 1.260px | **1.040px** |
>
> Os dois limiares não ficam só no comentário: o smoke de layout passou a
> exercitar **exatamente** essas duas larguras, tela por tela. Limiar que
> envelhece reprova antes de o usuário descobrir.
>
> **Próximo dono do gargalo:** o **Painel de Arbitragem** (1.200px, no botão
> "Atualizar agora") — e ele já está na fila da **B-6**, então será atacado lá,
> com a tela aberta de qualquer forma. Depois dele vêm Inventário (1.104px) e
> Configurações do torneio (1.080px).

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
>    alguma outra pagar o aprendizado, porque é a que mais dói se quebrar. É
>    também o **dono atual do gargalo de largura** (1.220px, no "Limpar");
> 2. ✅ `tournament_players_ui` (1.613) — **migrada** (ver o status abaixo);
> 3. ✅ `pairing_arbitration_ui` (1.527) — **migrada** (ver o status de 2026-07-27);
> 4. `admin_training_finance` (1.226), `admin_exercises_inventory` (1.126),
>    `club_members_ui` (1.073), `settings_certificates_ui` (1.062);
> 5. as três telas restantes de `tournaments/pages.py` (Central, Equipes,
>    árbitros do torneio) — já isoladas, é o passo mais barato.
>
> Cada uma vale um PR próprio, e o texto delas migra para o catálogo da **B-3**
> no mesmo passo: a tela vai ser aberta de qualquer forma.

> **Status (2026-07-26): B-6 — Jogadores migrada, e o molde precisou crescer.**
> A tela de Torneios cabia em três arquivos. A de Jogadores (1.613 linhas) não:
> ela **é quatro telas** empilhadas — cadastrar jogador, importar de fora, cuidar
> de rating oficial e publicar no Chess-Results —, e foi justamente empilhá-las
> que produziu o arquivo. Então o pacote
> [`screens/tournament_players/`](src/ui/screens/tournament_players/) tem as três
> camadas do molde (`state`/`controller`/`view`) **mais** um módulo por domínio
> de ação (`imports`, `forms`, `ratings`, `chess_results`) e dois de apoio
> (`dialogs`, `file_types`). Onze arquivos, o maior com **433 linhas**
> (comentário incluso); o import externo não mudou.
>
> **O achado mais sério não estava na tela, e sim na casca.** `_clear_content`
> descobre qual tela está aberta olhando o **quadro anterior da pilha**
> (`inspect.currentframe().f_back`) e anotando o nome se começar com `show_`.
> Isso valia enquanto toda tela chamava `_clear_content` de dentro do próprio
> `show_*`. Tela migrada delega para o `build()` de uma view: o quadro anterior
> passa a se chamar **"build"**, nada é anotado, e o registro continua apontando
> para a tela anterior — **sidebar destacando o item errado e F5 recarregando
> outra tela**. A tela de Torneios já tinha embarcado com esse defeito no PR
> anterior; foi um teste de tema que o denunciou aqui, ao ver `show_club` onde
> devia estar `show_players`. A correção sobe a pilha até achar o `show_*`, o
> que cobre os dois formatos sem pedir nada de quem escreve tela — e há teste
> cobrando as duas migradas **e** uma legada.
>
> **Três achados na própria tela**, todos com teste agora:
> 1. **Botões por cima dos seletores.** `_grid_form_buttons` começava na linha
>    `control_row + 7` — exatamente onde já estavam os três widgets do grupo
>    Scheveningen. Os três primeiros botões nasciam empilhados na mesma célula do
>    grid. Passou despercebido porque o painel rola: quem não desce até lá não vê.
> 2. **"Erro inesperado" para erro de digitação.** Rating "abc" virava
>    `int("abc")` → `ValueError` → modal com código de log, como se fosse falha
>    do programa. Agora `parse_rating` é puro e devolve `None`, e a validação diz
>    qual dos **três** campos de rating recusou o valor.
> 3. **Contagem em duas varreduras.** O resumo ("Total / Visíveis / Presentes")
>    era montado num laço e o filtro em outro; `rows()` devolve linhas e resumo
>    juntos, porque dois números que precisam concordar não podem ter duas fontes.
>
> **A parte de i18n (B-3) mudou uma decisão de desenho.** A primeira versão
> guardava as colunas num dicionário de *chaves* (`("players.column.id", 60)`) e
> resolvia com `t(chave)` na hora de montar. Funciona na tela e **fura o teste**:
> o `test_ui_i18n` varre chamadas `t("literal")`, então toda chave indireta
> viraria "órfã no catálogo" — ou pior, uma chave ausente só apareceria para o
> usuário. As colunas viraram **funções** que chamam `t()` literalmente e
> devolvem o título pronto. Ganho de brinde: o título passa a ser resolvido a
> cada montagem, então trocar o catálogo troca a tabela.
>
> 198 chaves novas (catálogo de 73 → 271), 34 testes sem janela, e o
> `neutral_button` — o par `THEME_NEUTRAL`/`THEME_NEUTRAL_HOVER` repetido à mão
> em cinco telas — virou factory em `components/buttons.py`.

> **Status (2026-07-27): B-6 — Arbitragem migrada, e a B-8 fechou junto.**
> `pairing_arbitration_ui.py` (1.527 linhas) era **cinco** telas: painel do
> árbitro, Central de pendências e os três cadastros TRF25 (ajustes de pontos,
> byes solicitados, proibições de pareamento). Virou o pacote
> [`screens/pairing_arbitration/`](src/ui/screens/pairing_arbitration/) com 14
> arquivos, o maior com **392 linhas**; o import externo não mudou.
>
> **Os três cadastros TRF25 eram a mesma tela escrita três vezes** — formulário
> estreito à esquerda, tabela à direita, rodapé com Atualizar/Remover/Voltar e
> exclusão com Desfazer. Agora a casca é uma só ([`registry.py`](src/ui/screens/pairing_arbitration/registry.py))
> e cada cadastro declara só o que tem de próprio. A prova de que triplicar
> custa: **só um dos três rodapés** tinha o botão destrutivo destacado, e a
> confirmação de exclusão não pedia `danger=` em nenhum — agora os três pedem.
>
> **Três achados, e os dois primeiros são de infraestrutura de teste:**
>
> 1. **`cancel_pending_callbacks` apagava comando Tcl dos outros.** O
>    `after_cancel` do tkinter não só cancela: apaga o comando do callback
>    usando a lista de comandos de **quem chamou**. Chamado na janela para um
>    `after` agendado por um widget lá dentro, o comando some do interpretador e
>    continua anotado no widget — e o `destroy()` do `tearDown` morre com
>    `can't delete Tcl command`. Onze testes reprovaram em cascata a partir daí.
>    Agora o cancelamento vai direto pelo Tcl (`after cancel`), sem apagar
>    comando de ninguém.
> 2. **A faixa que quebra linha media antes de existir na tela.** A `WrapRow`
>    só sabe onde começa depois de **mapeada**; a única remedição vinha de um
>    `after_idle` que às vezes rodava antes disso, lia deslocamento zero e
>    concluía que tinha a largura inteira do `content`. Agora ela também escuta
>    o próprio `<Map>` e declara a largura como *desconhecida* enquanto não está
>    na tela. Isso não era teoria: **Exercícios caiu de 1.180 para 1.000px e
>    Treinos de 1.140 para 940px** só com esse conserto — telas que a
>    continuação anterior da B-8 dava por resolvidas.
> 3. **O layout antigo escondia o transbordo truncando o botão.** No rodapé dos
>    cadastros, o `pack` desenhava "Voltar ao painel" com **115px** em vez dos
>    168 que ele pede: o rótulo saía cortado e a medição — que olha a largura
>    desenhada — dizia que cabia. Trocar por faixa que quebra linha tornou o
>    problema visível antes de torná-lo resolvido.
>
> **A faixa não serve em toda parte, e a medição é que disse.** No painel do
> árbitro as preferências de atualização vivem numa coluna estreita **cuja
> largura depende da própria faixa**: a conta gira em círculo e lê a posição de
> antes de a coluna assentar, deixando "Atualizar agora" a 1px da borda.
> Ali a resposta é empilhar, que dispensa medição. A faixa ficou onde a coluna é
> larga e a posição dela não depende do resultado (busca de mesas, ações inline,
> rodapé da Central, rodapé dos cadastros).
>
> **Limiares remedidos com dados na base** (torneio com jogadores e rodada
> gerada — a medição anterior usava base vazia e era otimista), com a barra
> **completa** forçada:
>
> | tela | antes | depois |
> |---|---|---|
> | Rodadas (`pairing_results_ui`) | 1.220px | 1.220px (não mexida) |
> | Exercícios | 1.180px | **1.000px** |
> | Painel de Arbitragem | 1.160px | **1.020px** |
> | Treinos | 1.140px | **940px** |
> | Ajustes / Byes / Proibições | 1.020px (com botão cortado) | **1.020px** (inteiro) |
>
> O Painel de Arbitragem deixou de ser o dono do gargalo: o que o limita agora é
> a barra do torneio, igual a nove outras telas. Com a barra em **rail** ele cai
> para o piso da varredura (700px), junto com as outras quinze.
>
> **Os dois limiares continuam onde estavam — 1.200px e 1.040px — e agora se
> sabe por quê.** Com o rail, a exigência máxima medida é exatamente **1.040px**,
> e o dono é a tela de **Rodadas**; com a barra completa ela pede **1.220px**,
> 20px acima do limiar configurado. O smoke roda com base vazia e passa em
> 1.200, então o número não reprova hoje — mas está **otimista** para quem tem
> torneio em andamento. Fica registrado aqui em vez de virar um número corrigido
> no escuro: Rodadas é a próxima da fila da B-6, e o acerto do limiar cabe lá,
> junto com a tela que o define.
>
> **Cobertura:** 42 testes sem janela em
> [tests/test_ui_arbitration.py](tests/test_ui_arbitration.py) (estado puro,
> controlador com banco de mentira, as três páginas de cadastro) mais o smoke,
> que passou a exercitar **as quatro telas de arbitragem que ficavam de fora** —
> eram justamente elas que definiam o limiar. Dois testes guardam os achados: um
> exige que o rodapé dos cadastros quebre em janela estreita, e outro varre o
> `pairing_service` procurando **toda ação de alerta emitida** e cobra que ela
> tenha destino no painel. Esse último precisou de parser de parênteses
> balanceados: a regex ingênua perdia três das nove ações, porque metade dos
> alertas é montada com f-string que contém `)` — `"resultado(s)"`.
>
> **B-3 no mesmo passo:** 205 chaves novas (catálogo de 271 → 476) e a
> acentuação que a F3.5 tinha deixado para trás nesta tela ("Painel do árbitro",
> "Central de pendências", "Ações rápidas", "Proibições"). Sete asserções de
> teste mudaram junto — é o que muda quando o texto visível muda.

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

### Fase 5 — Campos de entrada e adoção do design system (auditoria 2026-07-29) · ~21 dias

> **Motivação:** a auditoria de 2026-07-29 mostrou que a fundação (Fases 0–3) foi
> **criada** mas não **adotada** — e que os campos de entrada nunca entraram no
> design system (catálogo P3 acima; estado-alvo em
> [ESPEC_UI_UX.md §4.6](ESPEC_UI_UX.md)). Esta fase é o que o usuário vê: é aqui
> que o visual dos campos, tabelas e diálogos muda de fato. Ordem interna pensada
> para percepção imediata: F5.1 sozinha corrige a cor de 141 OptionMenus e liga os
> campos aos 13 presets.

| ID | Tarefa | Esforço | Impacto | Risco | Depende | Aceite |
|----|--------|---------|---------|-------|---------|--------|
| ✅ F5.1 | Tokens de campo (`THEME_FIELD_*`, `THEME_PLACEHOLDER`) + patch do `ThemeManager` p/ `CTkEntry`/`CTkTextbox`/`CTkOptionMenu` (corpo + tinta via `best_ink`) + bloco de pares de campo no `theme_audit` (P3-1, P3-2) | 2d | A | M | F1.1 | 141 selects e 162 campos seguem o preset; auditor reprova par de campo abaixo de AA; Alto Contraste alcança campos |
| ✅ F5.2 | `components/fields.py`: `text_field`/`select_field`/`text_area`/`date_field`/`labeled_field` — altura única 36px, raio único, escala `FIELD_SM/MD/LG/FULL`, placeholder obrigatório, `font_field()` (P3-3, P3-5, P3-6) | 2d | A | B | F5.1 | Campo e botão alinhados na mesma linha; escala de larguras fechada |
| F5.3 | Estados de campo: anel de foco (borda accent no `FocusIn`), `set_field_error(widget, msg)`/`clear_field_error` únicos com mensagem sob o campo, desabilitado distinto (P3-4) | 1,5d | A | B | F5.2 | Foco visível em navegação por Tab; 3 implementações locais de erro removidas |
| F5.4 | Migrar formulários p/ `fields.py` + `components/form.py` (promover `_settings_stack`, com seções) — ordem: Config. torneio, Jogadores, Torneios, Arbitragem, Config. app (P3-12) | 3d | A | M | F5.2 | 5 telas com seções visuais e largura de painel unificada |
| ✅ F5.5 | `_make_tree`: zebra (tokens já existentes), ordenação por clique no cabeçalho, `stretch=True` na coluna principal, `EmptyState` embutido, nulos renderizados vazios (P3-9, "None") | 1,5d | A | B | — | 57 tabelas ganham zebra+sort+vazio sem tocar call-sites |
| ✅ F5.6 | Quebrar o muro de Jogadores (25 → ~5: primárias + `Importar ▾`/`Bases oficiais ▾`/`Publicar ▾` + danger isolada) e aplicar o molde F2.1 aos 15 call-sites de `_grid_form_buttons` (P3-7) | 2d | A | M | — | Nenhuma tela com >8 ações visíveis no mesmo nível |
| F5.7 | Separar `_show_info`: toast só p/ confirmação curta; `_show_report(title, body)` rolável com botão **Copiar** p/ relatórios; validações → `_show_warning` (~35 call-sites reclassificados) (P3-8) | 1,5d | A | B | — | URL do QR e narrativa de desempate legíveis e copiáveis |
| F5.8 | Migrar os 21 diálogos ad-hoc p/ `Dialog` canônico (Esc, centralização, tamanho × `ui_scale_percent`, ordem [secundário][primário]); corrigir o aviso de BYE e o diálogo sem saída de Usuários (P3-10) | 2,5d | M | M | — | Todo diálogo fecha com Esc e cabe na tela em 160% |
| F5.9 | `ProgressOverlay` local sobre o painel em ação + `busy_widget` obrigatório por convenção de lint (P3-11) | 1,5d | M | B | — | Duplo clique não duplica operação; espera visível no local |
| F5.10 | Teclado: ordem de Tab explícita nos formulários, `Return` → ação primária, `takefocus=False` em botões secundários (P3-13) | 1,5d | M | B | F5.4 | Lançar 20 resultados usando só o teclado |
| F5.11 | `tk.Menu` gerado do registro `DESTINATIONS`; sidebar vira **rail** (não some) abaixo de 1.040px (P3-14) | 1d | M | B | F1.3 | Menu e sidebar com os mesmos destinos e rótulos |
| F5.12 | Lint de acentuação em `text=`/`t()` + correção dos ~26 rótulos; caça aos defeitos pontuais: truncamento dos botões do painel, data corrompida na Config. do torneio (P3-15, P3-16) | 1d | M | B | — | Grep de palavras-alvo zerado no CI; screenshots do manual re-tirados |

> **Status (2026-07-29): F5.1 CONCLUÍDA.** As cores dos campos deixaram de ser
> escolhidas e passaram a ser **derivadas**: `field_palette(painel)` em
> [`theme.py`](src/ui/theme.py) calcula fundo, borda, texto e placeholder a
> partir da cor do painel em que o campo vive — borda e placeholder são
> *procurados* (`_least_mix`), a menor mistura de tinta que alcança 3:1 sobre o
> painel e 4.5:1 sobre o campo, então **qualquer** preset de painel passa por
> construção, inclusive os que ainda não existem. No painel sépia o campo sai
> branco-quente; no floresta, branco-esverdeado — fim do cinza-azulado de
> fábrica destoando em 12 dos 13 presets.
>
> `apply_frame_bg_preset` muta os tokens novos (`THEME_FIELD_BG/BORDER/TEXT`,
> `THEME_PLACEHOLDER`) e patcha os padrões do `ThemeManager` para `CTkEntry`,
> `CTkTextbox` e `CTkComboBox` — com isso o [`restyle.py`](src/ui/restyle.py),
> que **já sabia** repintar essas classes e rodava a vazio (o padrão nunca
> mudava), passou a propagar a troca de tema aos ~162 campos existentes sem
> nenhuma mudança de código. `THEME_FIELD_BORDER_FOCUS` e
> `THEME_FIELD_BORDER_ERROR` são *aliases vivos* de `THEME_ACCENT` e
> `THEME_DANGER` — trocar o accent move o anel de foco junto (consumo na F5.3).
>
> O corpo do `CTkOptionMenu` agora segue o accent com tinta calculada
> (`best_ink`): morre o azul de fábrica nos 141 seletores (P3-1) e a reprovação
> de 2.74:1 do rótulo (P3-2). A setinha usa o tom de hover para manter a
> distinção. A anatomia de *campo* para selects fica para a F5.2.
>
> O [`theme_audit.py`](src/ui/theme_audit.py) ganhou os três pares de campo
> (borda×painel, texto×campo, placeholder×campo) usando a **mesma** função pura
> do preset — auditor e tema não podem divergir. O placeholder entra na família
> FILL de propósito: exigir AAA dele no alto contraste o tornaria tão escuro
> quanto o texto real. Testes: garantias da paleta nos 13 presets × 2 faces,
> temperatura preservada (sépia sai quente), tokens mutados no lugar, patch do
> `ThemeManager` verificado, e os dois gates existentes (curados AA + 5.070
> combinações) agora cobrem os campos automaticamente.

> **Status (2026-07-29): F5.2 CONCLUÍDA.** Nasce
> [`components/fields.py`](src/ui/components/fields.py) com as cinco factories
> (`text_field`, `select_field`, `text_area`, `date_field`, `labeled_field`) e
> a anatomia fechada: **altura 36px** — a mesma de `buttons._DEFAULT_HEIGHT`,
> com teste que quebra se um dos lados mudar sozinho —, raio único, fonte
> `font_field()` (novo token `SIZE_FIELD=13`; rótulo em `font_field_label()` =
> `SIZE_BODY`), e a escala de larguras `FIELD_SM/MD/LG` (120/240/360; FULL não
> é largura, é `sticky="ew"` com o `width` virando mínimo). `placeholder` é
> **keyword obrigatória** do `text_field` — campo sem dica de formato não
> compila mais (P3-6, eram 94 caixas mudas).
>
> `select_field` encerra o dilema do P3-5: seleção com anatomia de **campo**
> (corpo em `THEME_FIELD_BG`, tinta de campo, chevron na cor da borda, dropdown
> no painel), não o bloco de accent — que desde a F5.1 ficou correto para o
> `CTkOptionMenu` cru, mas continua linguagem de botão. As cores são os tokens
> vivos, então o `restyle` propaga a troca de tema. `text_area` nasce com
> `border_width=1` (o de fábrica é 0 = área invisível) e `wrap="word"`;
> `date_field` embrulha o `MaskedDateEntry` na escala (import tardio — o
> `support` importa `components`, não o contrário); `labeled_field` fecha o
> espaçamento rótulo→campo em `SPACE_XS`.
>
> **Piloto do aceite** na linha de lançamento de Rodadas
> ([`pairing_results_ui.py`](src/ui/screens/pairing_results_ui.py)): os dois
> seletores crus (28px, azul de fábrica) viraram `select_field`, e os botões
> rápidos 1-0/1/2/0-1 subiram para `FIELD_HEIGHT` — a linha inteira (campo,
> campo, primária, rápidos) alinhada nos mesmos 36px, verificado em screenshot
> sobre o tema sépia. A migração ampla dos formulários é a F5.4.
> Testes: contratos puros (paridade de altura com botão, escala fechada,
> placeholder obrigatório) + anatomia real com janela (marcados `gui`).

> **Status (2026-07-29): F5.5 CONCLUÍDA.** Nasce
> [`components/tree.py`](src/ui/components/tree.py) com a `ThemedTreeview`, e o
> `_make_tree` passa a instanciá-la — **nenhum dos ~57 call-sites mudou**, que
> era o aceite. Tudo acontece por dentro de `insert`/`delete`:
>
> - **zebra**: os tokens `THEME_TREE_ODD/EVEN` existiam desde a B-2 e nunca
>   tinham sido aplicados; a tag entra por ÚLTIMO na lista do item (no ttk a
>   primeira tag que define uma opção vence), então as tags semânticas das
>   telas — estado QR com fundo próprio, verde de "registrado" — continuam
>   mandando. Excluir e ordenar reaplicam a alternância; cada instância se
>   inscreve em `on_theme_change` + `AppearanceModeTracker` e se **desinscreve
>   no `<Destroy>`** (testado — sem isso cada tela visitada viraria ouvinte
>   imortal);
> - **ordenação por clique**: numérica quando a coluna inteira é numérica
>   ("1740", "1.5" e "1,5"), texto `casefold` caso contrário, vazios sempre ao
>   fim, segundo clique inverte, indicador ▲/▼ no cabeçalho. Tela que registra
>   o próprio `heading(command=...)` depois (explicação de desempates em
>   `pairings.py`) substitui a ordenação naquela coluna — comportamento certo.
>   O fluxo "próxima mesa" do lançamento rápido não quebra: ele recaptura o
>   índice a cada recarga;
> - **`stretch=True` na coluna mais larga** (nome, em geral): a sobra de
>   largura é absorvida em vez de virar barra horizontal permanente;
> - **nulos viram célula vazia**: `None` e a string `"None"` (nunca é dado
>   legítimo em PT-BR) — era o "None" vazando na coluna Turma de Jogadores;
> - **estado vazio embutido**: `EmptyState` central aparece quando a tabela
>   fica sem linhas e some na primeira inserção; `_make_tree` ganhou
>   `empty_title`/`empty_description` opcionais com default genérico — P1-9
>   sai de 4 para as ~57 tabelas.
>
> 9 testes novos (`tests/test_ui_tree.py`, marcados `gui`) + smoke de layout
> completo verde. Screenshot de Jogadores confirma zebra e "None" eliminado
> sobre o tema sépia.

> **Status (2026-07-29): F5.6 CONCLUÍDA — 25 controles viraram 8.** O muro da
> tela de Jogadores era o pior caso do P3-7, e o mais irônico: a F2.1 tinha
> comemorado a redução de ~18 botões em Rodadas e nunca olhado para os 25 daqui.
>
> O `_grid_form_buttons` ganhou **vocabulário** em vez de mais um caso especial
> ([`components/action_group.py`](src/ui/components/action_group.py), puro, sem
> Tk): além do `(rótulo, comando)` de sempre, aceita `ActionGroup` (vira
> `menu_button` recolhido) e `DangerAction` (vira `danger_button` com respiro
> extra, isolado). **As 16 chamadas existentes seguem idênticas** — quem passa
> lista plana continua desenhando lista plana.
>
> O agrupamento vive em
> [`tournament_players/menu.py`](src/ui/screens/tournament_players/menu.py),
> módulo puro que recebe `chave -> callable` e devolve a estrutura. O critério é
> **de onde o jogador vem**, que é a pergunta que o operador faz: avulso
> (Adicionar/Atualizar/Limpar soltos) · `Inscrever ▾` (membro, todos ativos,
> status, os três caminhos de formulário) · `Importar ▾` (modelos, planilha,
> mapeamento, online, Chess-Results) · `Bases oficiais ▾` (FIDE, CBX, LBX,
> estrangeira, atualizar, comparar) · Publicar solto (é saída, não entrada) ·
> **Excluir jogador** isolado em vermelho no fim.
>
> **Sem permissão, o gatilho do menu continua clicável e os itens nascem
> acinzentados** — desabilitar o gatilho esconderia atrás de um botão morto a
> razão pela qual ele está morto.
>
> Três decisões que os testes guardam: `t()` recebe **string literal**, nunca
> f-string (chave montada em runtime vira órfã no `test_ui_i18n` — mesma
> armadilha da B-3); nenhum menu nasce com um item só (seria hierarquia sem
> ganho); e o teste que sustenta tudo compara o `flatten_actions` contra **todas**
> as chaves `players.action.*` do catálogo — recolher não pode virar sumir.
> O `_click_button` do smoke passou a alcançar itens de menu (via `_menu_items`,
> exposto pelo `menu_button` justamente para automação): as três falhas que ele
> acusou eram honestas — a ação mudou de um clique para dois.
>
> 8 testes novos, sem janela. Gate completo verde.

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

### MVP de percepção v2 (~1,5 semana · Fase 5)

`F5.1` (campos entram no tema — 141 selects deixam de ser azuis de fábrica) →
`F5.2`+`F5.3` (anatomia e estados dos campos) → `F5.5` (zebra/sort/vazio nas 57
tabelas, sem tocar call-sites) → `F5.6` (muro de Jogadores) → `F5.7` (relatório
copiável). É o menor corte que ataca diretamente a reclamação de origem — o visual
dos campos de entrada — e as telas de uso diário.

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
