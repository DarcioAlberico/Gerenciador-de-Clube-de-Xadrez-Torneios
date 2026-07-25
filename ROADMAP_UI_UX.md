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
| F1.2 | Tema sem destroy/rebuild: `restyle()` por `configure()` (P0-6) | 3d | A | **M-A** | F1.1 | Trocar tema preserva foco/scroll/seleção |
| ✅ F1.3 | `Navigator` + registro único de destinos (de `_command_palette_actions`) (P0-1) | 2d | A | M | — | Navegação central; F5 via `refresh_current()` |
| ✅ F1.4 | `AppShell` (casca fina) coexistindo com mixins legados (P0-1) | 2d | A | M | F1.3 | App sobe via shell; mixins ainda funcionam |
| F1.5 | **Piloto**: migrar 1 tela para View/Controller/State + `dataclass` (P0-2, P0-3) | 3d | A | M | F1.4 | Tela testável sem subir app; zero `{"value":None}` |
| F1.6 | Imports explícitos na tela-piloto + 2 telas; lint anti-wildcard no CI (P0-4) | 1,5d | M | B | F1.5 | CI falha em novo `import *` |

> Após o piloto, cada tela-monstro migrada vira um épico próprio no backlog
> (`pairing_results_ui` → `screens/pairings/{view,controller,state}.py`, etc.).

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

| ID | Tarefa | Esforço | Impacto | Risco | Depende | Aceite |
|----|--------|---------|---------|-------|---------|--------|
| F3.1 | Sidebar persistente com grupos + item ativo (P1-7) | 4d | A | M | F1.3 | Navegação primária visual; menu vira fallback |
| F3.2 | Dashboard contextual pós-login (pendências acionáveis) (P1-8) | 3d | A | M | F1.3 | Abre em pendências com deep-link |
| F3.3 | Tokenizar cores/fonts: 58 hex + 23 fonts + `#a3423c` (P2-1,2,3) + lint CI | 2d | M | B | F1.1 | CI barra novos literais em `screens/` |
| ✅ F3.4 | Modo Livre "não mostrar de novo" (P1-11); Aulas/Exercícios → "(em breve)" (P1-12) | 0,5d | M | B | — | Sem fricção repetida; rótulo claro |
| ✅ F3.5 | Corrigir acentuação das labels visíveis (P2-8) | 0,5d | M | B | — | "Configurações/Aparência/Segurança" |
| F3.6 | Login com split layout + branding + versão (P2-6) | 1d | B | B | — | Layout dividido; espaço p/ "primeiro acesso" |

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

### Backlog (não priorizar agora)

- **B-1** Persistência de layout de colunas por usuário (P2-9) — reaproveitar `ColumnLayoutEditor`.
- **B-2** Auditoria de contraste WCAG AA + preset alto contraste (P2-11).
- **B-3** i18n: extrair strings para `i18n/pt_BR.json`, manter só PT-BR (P2-12).
- **B-4** Virtualização/paginação de `Treeview` (P2-13) — antes da base crescer.
- **B-5** Cache de figuras matplotlib quando dados não mudam (P2-14).
- **B-6** Migrar telas-monstro restantes para 3 camadas (continuação de F1.5).
- **B-7** Acentuar cabeçalhos/títulos de `src/services/export_*` para casar com a UI
  (F3.5). Fica fora da F3.5 porque altera **arquivo entregue** (PDF/CSV/HTML) e
  formato que terceiros consomem — precisa de decisão sobre compatibilidade.

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
