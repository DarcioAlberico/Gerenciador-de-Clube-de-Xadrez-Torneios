# ESPEC_UI_UX — Especificação de UI/UX do Albericus

> **Status:** v2 (auditoria de campos e adoção) · **Data:** 2026-07-29 · v1: 2026-06-25 · **Escopo:** Camada de interface (`src/ui/`)
> **Documento irmão:** [ROADMAP_UI_UX.md](ROADMAP_UI_UX.md) — sequenciamento, esforço e critérios de aceite.
> **Aplicação:** Albericus — Emparceiramento de Xadrez (desktop, CustomTkinter, Windows/PyInstaller).
> **v2:** revalidação de métricas (§2.3), especificação dos campos de entrada (§4.6) e DoD de adoção (§10). Achados P3-* e Fase 5 no roadmap.

Este documento define o **estado-alvo** da interface: princípios, arquitetura de UI,
design system e padrões de interação. Ele consolida duas análises independentes
(uma focada em arquitetura/débito estrutural, outra em design system/consistência
visual) reconciliadas e **validadas contra o código** em 2026-06-25.

---

## 1. Contexto e objetivo

O Albericus já tem uma base de UI **acima da média para um app desktop**: design
system tokenizado, 6 temas curados com preview, command palette (`Ctrl+K`), toasts
de 4 níveis, campo de data próprio com calendário e editores visuais de configuração.
O problema não é falta de capacidade — é **dívida de costura**: a UI cresceu por
acúmulo (~19,7 mil linhas em 28 arquivos) e hoje paga em três frentes:

1. **Arquitetura** — uma _god class_ com 14 mixins, telas de até 1.920 linhas que
   misturam view + lógica + estado, e um mecanismo de tema que reescreve `sys.modules`
   e destrói a UI inteira a cada troca.
2. **Consistência** — desvios mensuráveis do próprio design system (cores e fontes
   hardcoded, diálogos nativos do SO).
3. **Navegação e feedback** — navegação 100% por menu nativo, ausência de tooltips,
   estados vazios/carregando fracos e confirmações destrutivas sem desfazer.

**Objetivo da spec:** estabelecer a fundação arquitetural e os padrões de componente
que (a) destravam a evolução, (b) elevam a percepção de profissionalismo no uso diário
e (c) respeitam a diretriz permanente de **modularização rígida** (puro separado de
I/O, módulos pequenos, sem _wildcard imports_).

### 1.1 Princípios de design (o norte)

| # | Princípio | Implicação prática |
|---|-----------|--------------------|
| P1 | **Uma fonte de verdade visual** | Toda cor/fonte/espaçamento vem de um token. Zero literais em telas. |
| P2 | **Hierarquia antes de densidade** | Ações primárias preenchidas; secundárias recolhidas; destrutivas isoladas. |
| P3 | **View burra, lógica testável** | Widget não conhece `db`/serviços. Controlador orquestra; estado é explícito. |
| P4 | **Feedback não-bloqueante por padrão** | Toast/inline; modal só quando exige decisão. Toda ação longa mostra progresso. |
| P5 | **O usuário nunca fica perdido** | Navegação persistente visível, tela ativa destacada, dashboard contextual. |
| P6 | **Reversibilidade** | Ações destrutivas oferecem desfazer ou confirmação proporcional ao risco. |
| P7 | **Acessível e localizável desde já** | Contraste WCAG AA, ordem de foco previsível, strings prontas para i18n. |

---

## 2. Estado atual — snapshot validado

Números medidos no código em 2026-06-25 (corrigem estimativas das análises de origem):

| Métrica | Valor | Observação |
|---------|-------|------------|
| Arquivos de UI | 28 | `src/ui/**/*.py` |
| Linhas de UI | ~19.675 | maiores telas abaixo |
| Bases da `AlbericusApp` | 14 mixins + `ctk.CTk` | [app.py:29](src/ui/app.py:29) |
| `from ..support import *` | **22 arquivos** | exceções corretas: `library.py`, `dashboard.py` |
| Padrão `{"value": None}` p/ estado | **22 ocorrências / 12 arquivos** | _workaround_ de escopo léxico |
| `messagebox.*` nativos | 26 / 8 arquivos | diálogos do SO fora do tema |
| Cores hex hardcoded em telas | 58 (45 em `pairing_results_ui.py`) | ignoram o accent do usuário |
| `CTkFont(size=...)` solto | 23 | contorna tokens `SIZE_*` |
| `_run_background` (helper async) | **existe e usado 50×/12 arquivos** | bom — só faltam 4 _call-sites_ |
| `threading.Thread` cru | 4 _call-sites_ | migrar para o helper |
| Temas JSON órfãos | 4 (`assets/themes/*.json`) | código morto |

**Telas-monstro (linhas):** `pairing_results_ui.py` 1920 · `tournament_players_ui.py`
1614 · `pairing_arbitration_ui.py` 1447 · `admin_training_finance.py` 1225 ·
`tournaments.py` 1168 · `admin_exercises_inventory.py` 1125 · `club_members_ui.py`
1059 · `settings_certificates_ui.py` 1056.

### 2.1 O que já é bom (preservar)

Sistema de tema maduro ([support.py:138-261](src/ui/support.py:138)) · command palette
([app.py:538](src/ui/app.py:538)) · toasts ([app.py:742](src/ui/app.py:742)) ·
`_run_background` ([app.py:1194](src/ui/app.py:1194)) · `MaskedDateEntry`
([support.py:506](src/ui/support.py:506)) · sub-nav contextual de torneio
([app.py:847](src/ui/app.py:847)) · `_disable_if_unauthorized` (permissão na UI).
**Nada disso é descartado** — a spec os promove a cidadãos de primeira classe.

### 2.2 Validação visual (2026-06-25)

O diagnóstico foi confirmado rodando o app sobre uma cópia descartável do banco
(`tools/ui_shot.py`, com bypass de login), em 3 telas representativas:

- **Rodadas** — o _wall of buttons_ é real: 3 fileiras de ~18 botões de cor idêntica,
  com "Excluir rodada" (destrutivo) no meio da grade. Statusbar útil ("Rodadas 4/5 ·
  ✓ sem pendências · Modo Oficial"). Confirma P1-1.
- **Dashboard Visual** — estático, sem faixa de KPIs; o gráfico "Status Financeiro"
  aparece **vazio com eixos de -0.04 a 0.04** quando não há dados (empty state
  quebrado), e os painéis mostram "Nenhum aviso"/"Nenhum evento". Confirma P1-8, P1-9.
- **Configurações do app** — a galeria de temas curados (ponto forte) renderiza bem,
  mas o título "Configuracoes", as abas "Aparencia"/"Seguranca" e a coluna "Descricao"
  aparecem **sem acento** ao usuário. Confirma P2-8.

### 2.3 Revalidação (2026-07-29) — a fundação existe, a adoção não chegou

Auditoria de design completa (código + screenshots de `docs/manual_screenshots/`),
motivada pela insatisfação declarada com o visual dos **campos de entrada**. Números
remedidos:

| Métrica | v1 (06-25) | v2 (07-29) | Leitura |
|---------|-----------:|-----------:|---------|
| Linhas de UI | ~19.675 | **25.969** | cresceu 32% |
| `messagebox.*` nativos | 26 | **0** ✅ | F2.2 cumprida |
| `from ..support import *` | 22 | **20** | quase parado |
| Mixins da `AlbericusApp` | 14 | **14** | DoD §10.3 aberto |
| Telas migradas (3 camadas) | 0 | **4** ✅ | DoD §10.4 cumprido |
| Botões via factory vs. cru | — | **35 vs. 170 (17%)** | DoD §10.6 aberto |
| `EmptyState` em tabelas | — | **4 de 57** | DoD §10.7 aberto |
| `CTkEntry`/`CTkOptionMenu`/`CTkTextbox` | — | **150 / 141 / 12** | nenhum no design system |

Conclusões da revalidação:

1. **Os campos de entrada nunca entraram no design system.** O patch de tema cobre
   botões e frames, mas `CTkEntry`/`CTkTextbox` não são patchados e do `CTkOptionMenu`
   só a setinha muda — o corpo fica azul de fábrica em 141 widgets, com qualquer
   accent ([theme.py:382-393](src/ui/theme.py:382)). Todos os campos usam os defaults
   do CTk: contrastes reprovados pelo próprio [contrast.py](src/ui/contrast.py)
   (borda 2,74:1 sobre painel claro; rótulo do OptionMenu 2,74:1; placeholder 3,51:1;
   campo invisível nos presets sépia/floresta), sem foco visível, sem estado de erro
   em ~145 dos 150, 67 larguras distintas e altura 28px ao lado de botões de 36px.
   **É a causa raiz da insatisfação com o visual dos campos.** Estado-alvo em §4.6.
2. **Criação ≠ adoção.** Os componentes canônicos do §4.4 existem e são bons, mas
   cobrem 17% dos botões, 4 de 57 tabelas e 0 dos 21 diálogos ad-hoc. O usuário sente
   a adoção, não a criação.
3. **Evidência visual (screenshots do manual):** muro de 25 botões idênticos em
   Jogadores; botões com texto cortado no Painel do árbitro ("justes de pontos
   (TRF25"); campos esticados a ~1.250px na Config. do torneio; valor de data
   corrompido ("2026-05-182026-06-07"); "None" literal em coluna de tabela; Treeview
   com visual nativo destoando dos cards.

---

## 3. Arquitetura-alvo de UI

A meta é uma **casca fina** + **telas autocontidas** em 3 camadas, com tema e navegação
como serviços. Migração **incremental, tela a tela** (ver roadmap) — sem _big-bang_.

### 3.1 Camadas por tela: View / Controller / State

Hoje uma tela como `pairing_results_ui.py` mistura criação de widgets, acesso direto a
`self.db`/serviços, callbacks de validação, formatação e estado mutável via
`dict["value"]`. Alvo — três responsabilidades separadas:

```
src/ui/screens/pairings/
├── view.py         # só widgets + binds. Recebe um controller. NÃO importa db/serviços.
├── controller.py   # orquestra serviços, expõe refresh()/save()/on_select(). Testável sem Tk.
└── state.py        # @dataclass ScreenState — seleção, filtros, flags. Sem dict["value"].
```

**Contrato de tela:**

```python
# src/ui/core/screen.py
class Screen(ABC):
    def __init__(self, host: AppShell, services: ServiceRegistry) -> None: ...
    @abstractmethod
    def build(self, parent: ctk.CTkFrame) -> None: ...   # cria a view
    def on_show(self) -> None: ...                        # refresh ao entrar
    def on_hide(self) -> None: ...                        # cancela jobs/after
    def teardown(self) -> None: ...                       # destrói widgets
```

**Estado explícito** (substitui as 22 ocorrências de `{"value": None}`):

```python
# state.py
@dataclass
class PairingsState:
    selected_round_id: int | None = None
    selected_pairing_id: int | None = None
    team_mode: bool = False
```

**Benefícios diretos:** autocomplete da IDE volta a funcionar; cada tela testável sem
instanciar o app inteiro (hoje `tests/test_ui_layout.py` sobe o app completo por
página — lento); refactor de uma tela não exige ler o _god object_.

### 3.2 Casca fina + Navigator + registro de telas

`AlbericusApp` deixa de herdar 14 mixins e vira **`AppShell`** (janela, menu/sidebar,
statusbar, serviços, ciclo de vida). A navegação vira um serviço:

```python
# src/ui/core/navigator.py
class Navigator:
    def register(self, name: str, factory: Callable[[], Screen]) -> None: ...
    def show(self, name: str, **params: Any) -> None:   # hide() atual → build/show novo
    def current(self) -> Screen | None: ...
    def refresh_current(self) -> None: ...               # F5
```

O registro de destinos **já existe de fato** em `_command_palette_actions`
([app.py:493](src/ui/app.py:493)) — vira a fonte única que alimenta menu, sidebar,
command palette e atalhos.

### 3.3 Tema como serviço (`theme.py`) com _listeners_

Dois problemas a eliminar:

- **`_propagate_theme_globals`** ([support.py:264](src/ui/support.py:264)) itera
  `sys.modules` fazendo `setattr` em qualquer módulo que tenha o nome do token —
  frágil, lento e opaco para debug.
- **`_rebuild_ui_after_theme_change`** ([app.py:165](src/ui/app.py:165)) **destrói e
  recria** `content` + `statusbar` a cada troca de tema — perde foco, scroll, seleção
  de tree, e trava segundos em telas pesadas.

Alvo — módulo único + _listener pattern_ + reaplicação por `configure()`:

```python
# src/ui/theme.py  (tokens vivem aqui; telas fazem `from src.ui import theme`)
ACCENT: tuple[str, str] = ("#3B82F6", "#38BDF8")
PANEL_BG: tuple[str, str] = ("#FFFFFF", "#1E293B")
# ...

_listeners: list[Callable[[], None]] = []
def on_change(cb: Callable[[], None]) -> None: _listeners.append(cb)

def apply(accent: str, bg: str, frame: str, appearance: str) -> None:
    # atualiza tokens in-place + ThemeManager do CTk
    for cb in _listeners: cb()        # cada tela reestiliza seus widgets
```

Telas registram um `restyle()` que faz `widget.configure(fg_color=theme.PANEL_BG[face])`
recursivo — **sem destroy/rebuild**. Acesso por `theme.ACCENT` (late binding) elimina o
hack de `sys.modules` e o `import *` que ele exige para funcionar.

### 3.4 Imports explícitos

Eliminar `from ..support import *` (22 arquivos). `library.py` e `dashboard.py` já são
o padrão correto. Wildcard oculta dependências, quebra ferramentas de refactor e é
**incompatível com a diretriz de modularização rígida**.

---

## 4. Design System

### 4.1 Cor — tokens, zero literais

Os tokens `THEME_*` já existem e cobrem o caso geral. A spec **proíbe literais hex em
telas**: as 58 ocorrências migram para token. Casos:

- Botões "✕" em [tournament_widgets.py](src/ui/screens/tournament_widgets.py:85)
  (`#a3423c`) → `THEME_DANGER`.
- "Modo Projetor" e badges de status em `pairing_results_ui.py` → tokens semânticos
  novos (`THEME_PROJECTOR`, `THEME_STATUS_PENDING/OK`) para acompanharem o tema.
- Regra de lint (grep no CI, ver roadmap) barra novos `#RRGGBB` em `src/ui/screens/`.

### 4.2 Tipografia — só tokens `SIZE_*`

Os 23 `CTkFont(size=...)` soltos migram para os helpers existentes (`font_section()`,
`font_kpi_value()`, …) ou novos (`font_body()`, `font_dialog_title()`). Tabela
canônica em [support.py:95](src/ui/support.py:95) é a única fonte.

### 4.3 Espaçamento — novos tokens `SPACE_*`

Padrões mágicos (`pady=(12, 4)`, `(16, 4)`, `(8, 0)`) aparecem centenas de vezes com
variações. Definir e aplicar:

```python
SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL = 4, 8, 12, 16, 24
```

### 4.4 Componentes canônicos (catálogo)

Tudo abaixo vira _factory_/classe em `src/ui/components/` — **uma** implementação,
reusada. Substitui variações ad-hoc espalhadas.

| Componente | Hoje | Alvo |
|------------|------|------|
| **Botões** | `CTkButton` cru, cor por call-site | `primary_button` / `secondary_button` / `danger_button` (cor, peso e posição padronizados) |
| **Diálogo de confirmação** | `messagebox.askyesno` (26×) | `confirm_dialog(title, body, *, danger=False)` CTk temático |
| **Erro** | `messagebox.showerror` | toast de erro + `_show_error` modal só p/ stack-trace |
| **Modal** | `CTkToplevel` montado à mão (doação, Modo Livre, palette) | `Dialog` com header/body/footer + `grab_set`/Esc/centralização |
| **Empty state** | `CTkLabel("Nenhum registro")` | `EmptyState(icon, título, descrição, cta)` |
| **Tooltip** | inexistente | `Tooltip(widget, text)` próprio (~40 linhas; `CTkToolTip` não está instalado) |
| **KPI card** | `_kpi_card` sem hover | + estado hover visível quando `command` presente ([app.py:905](src/ui/app.py:905)) |
| **Tabela** | `ttk.Treeview` cinza | wrapper com zebra, hover, badge de status e densidade temada |
| **Loading** | nada | `Spinner`/`ProgressOverlay` para ações longas |

### 4.5 Navegação — sidebar persistente

Introduzir um **rail/sidebar** CTk à esquerda, agrupado por área (Clube · Torneio ·
Ferramentas · Config), com o destino ativo destacado. Espelha o registro único de
destinos (§3.2). O `tk.Menu` nativo permanece como _fallback_/acessibilidade, mas deixa
de ser a navegação primária. Mockup de referência aprovado nesta sessão (shell com
sidebar + barra de ações hierárquica na tela de Rodadas).

### 4.6 Campos de entrada — anatomia, dimensões e estados (v2, 2026-07-29)

Estado-alvo para os 150 `CTkEntry`, 141 `CTkOptionMenu` e 12 `CTkTextbox`. Hoje
nenhum deles recebe cor, fonte ou altura do design system (§2.3).

**Tokens de campo** (novos em `theme.py`, mutados pelos presets como os demais):

```python
THEME_FIELD_BG            # fundo do campo — derivado do painel, sempre distinguível (Δ mensurável)
THEME_FIELD_BORDER        # ≥ 3:1 contra o painel (AA para componente de UI)
THEME_FIELD_BORDER_FOCUS  # = accent do tema
THEME_FIELD_BORDER_ERROR  # = THEME_DANGER
THEME_FIELD_TEXT          # ≥ 4,5:1 contra THEME_FIELD_BG
THEME_PLACEHOLDER         # ≥ 4,5:1 contra THEME_FIELD_BG
```

Aplicação em duas frentes: (a) patch dos defaults do `ThemeManager` para `CTkEntry`,
`CTkTextbox` e `CTkOptionMenu` — com isso o [restyle.py](src/ui/restyle.py) existente
passa a repintá-los sem mudança de código; (b) tinta do OptionMenu calculada com
[`best_ink`](src/ui/contrast.py:69). O [theme_audit.py](src/ui/theme_audit.py) ganha
o bloco de **pares de campo** (fundo×painel, borda×painel, placeholder×fundo,
texto×fundo, rótulo do select×preenchimento) e trava no gate dos temas curados —
hoje o auditor tem zero pares de entrada, por isso as reprovações nunca apareceram.

**Anatomia** (factories em `components/fields.py` — proibido `CTkEntry` cru em tela):

| Elemento | Regra |
|----------|-------|
| Rótulo | sempre **acima**, `font_field_label()` (SIZE_BODY, `THEME_TEXT_SUB`), `SPACE_XS` até o campo |
| Campo | altura única **36px** (alinhado a `buttons._DEFAULT_HEIGHT`), raio **6**, borda 1px (2px no foco), `font_field()` |
| Placeholder | **obrigatório** em campo de texto livre (formato esperado: "Ex.: 90'+30\"", "dd/mm/aaaa") |
| Ajuda/erro | linha reservada sob o campo, `SIZE_XS`; erro em `THEME_DANGER` com a mensagem, não só borda |
| Largura | escala fechada: `FIELD_SM=120` (números/datas) · `FIELD_MD=240` (padrão) · `FIELD_LG=360` (nomes/caminhos) · `FULL` (só com `sticky="ew"` **e** teto de coluna `max ~560px`) — elimina as 67 larguras distintas e o campo de 1.250px da Config. do torneio |

**Estados** (todos visíveis e distintos): repouso · **foco** (borda 2px accent —
hoje inexistente) · **erro** (`set_field_error(widget, msg)` / `clear_field_error`
únicos, substituindo as 3 implementações locais) · **desabilitado** (fundo do
painel + texto sub — hoje indistinguível) · somente-leitura.

**Seleção (`select_field`)**: aparência de **campo**, não de botão — fundo claro
`THEME_FIELD_BG`, borda, chevron discreto e dropdown temado. Implementação sobre
`CTkComboBox` em `state="readonly"` (que já tem anatomia de campo) ou `CTkOptionMenu`
reestilizado; o bloco de cor sólida atual fica reservado a botões de ação. Fim da
linha de formulário que alterna caixa branca / bloco azul.

**Data (`date_field`)**: [`MaskedDateEntry`](src/ui/support.py:459) é a referência de
comportamento (máscara, clamp, borda de erro) e vira o único campo de data do app —
nada de `DateEntry` nativo. O calendário popup adota os tokens do tema e
`best_ink(THEME_ACCENT)` no dia selecionado (hoje `#FFFFFF` cravado).

**Área de texto (`text_area`)**: borda 1px (hoje `border_width=0` a torna invisível
sobre o painel), mesmo fundo/fonte do campo, `wrap="word"` sempre, altura em passos
(`80/140/200`).

**Tabelas (leitura)**: a Treeview é o "campo de leitura" mais usado (57 instâncias) e
segue as mesmas regras de integração — zebra com os tokens `THEME_TREE_EVEN/ODD`
(existem e nunca foram aplicados), ordenação por clique no cabeçalho, `stretch=True`
na coluna principal (fim da barra horizontal permanente), `EmptyState` embutido no
`_make_tree`, e "None"/valores nulos renderizados como vazio.

---

## 5. Padrões de interação

### 5.1 Feedback

- **Sucesso/info:** toast (já existe). **Erro recuperável:** toast de erro. **Erro
  inesperado:** modal com código + caminho do log. **Implementado (F2.2):** a única
  `_show_error` vive em `ErrorCatchingMixin`
  ([support.py:511](src/ui/support.py:511)) — e não em `app.py`, como esta seção
  previa: o mixin atende as ~25 telas, enquanto a cópia de `app.py` só servia a
  janela principal. A classificação saiu para a função pura
  [`_classify_error`](src/ui/support.py:442) (aceita `str` ou exceção). Quando há
  modal com _grab_ aberto, o feedback vira alerta bloqueante em vez de toast —
  senão ficaria escondido atrás do modal ([support.py:500](src/ui/support.py:500)).
- **Destrutivo:** confirmação proporcional + **undo no toast** quando viável
  ("Torneio X excluído · Desfazer"). Para exclusões em cascata, manter confirmação
  explícita.

### 5.2 Operações longas

Toda ação que toca serviço pesado (gerar rodada, importar TRF/FIDE, exportar lote)
roda via `_run_background` **com**: botão desabilitado durante a execução, indicador de
progresso (spinner/barra) e tratamento de erro → toast. Migrar os 4 `threading.Thread`
crus para o helper. _Não recriar_ o helper — ele já existe e é usado 50×.

### 5.3 Navegação e descoberta

Sidebar (primária) + sub-nav contextual de torneio (já existe) + command palette
(`Ctrl+K`) + atalhos (`Ctrl+1..5`). **Dashboard contextual pós-login** substitui a
abertura em "Perfil do Clube": ao entrar, mostrar pendências acionáveis (rodadas
abertas, byes não resolvidos, resultados faltando, próximos eventos) com _deep-link_
para a tela correspondente.

### 5.4 Estados de tela

Toda listagem/painel implementa os três estados: **vazio** (EmptyState + CTA),
**carregando** (skeleton/spinner) e **erro** (mensagem + ação de retry). Proibido
"tela morta".

---

## 6. Acessibilidade e internacionalização

- **Contraste:** auditar `THEME_TEXT_SUB` em dark mode e presets quentes (amber/yellow)
  contra WCAG AA (4.5:1 texto normal). Ajustar tokens reprovados; considerar preset de
  alto contraste.
- **Foco/teclado:** ordem de tabulação previsível (não dependente da ordem de criação);
  Enter/Esc consistentes em modais; foco visível.
- **Polish PT-BR:** corrigir labels **visíveis** sem acento ("Configuracoes",
  "Aparencia", "Seguranca") — barato, alto efeito de qualidade percebida.
- **i18n (preparação):** extrair strings para `i18n/pt_BR.json` mantendo só PT-BR ativo.
  Exportações FIDE em EN virão; preparar o terreno evita refactor doloroso. **Não**
  implementar EN agora.

---

## 7. Decisões de produto a respeitar (não são bugs)

- **Aulas/Exercícios desativados** ([app.py:367](src/ui/app.py:367)) é **deliberado**
  ("pedagógico pausado"). Telas e métodos permanecem intactos. Ação de UI: trocar o
  item cinza por rótulo **"(em breve)"** ou ocultar por _feature flag_ — **não remover**.
- **Modo Livre** ([free_tournament.py:12](src/ui/screens/free_tournament.py:12)) é um
  modal **funcional** (cria o torneio), não só informativo. Ação: colapsar o bloco
  explicativo de 3 bullets após a 1ª exibição ("não mostrar de novo"), preservando os
  botões de ação.
- **Modo Livre usa marca dedicada `free_mode`**, não o perfil do torneio — qualquer
  UI nova deve ler/escrever essa marca.

---

## 8. Não-objetivos (fora de escopo desta fase)

- Trocar de _framework_ (Qt/web) — fora de escopo; CustomTkinter permanece.
- Implementar idioma inglês completo (só preparar i18n).
- Virtualização de tabelas — backlog, antes que a base cresça muito.
- Animações/transições além de _fades_ sutis de toast.

---

## 9. Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Refactor estrutural sem rede de tipos (mypy só cobre `src/core`) | Migrar **uma tela-piloto** primeiro; ampliar gate de mypy para `src/ui/core` e telas migradas. |
| `test_ui_layout.py` é lento e sobe o app inteiro | Telas testáveis isoladamente (§3.1) reduzem dependência desse teste; manter como _smoke_. |
| Tema sem destroy/rebuild pode introduzir bugs sutis de cor | Fazer por último na fundação; cobrir com checklist visual claro/escuro por componente. |
| _Big-bang_ no god class quebra tudo | **Proibido.** Coexistência: `AppShell` + telas novas convivem com mixins legados durante a migração. |

---

## 10. Definição de pronto (DoD global)

A fase de fundação é considerada concluída quando:

1. Zero `from ..support import *` em `src/ui` (lint no CI).
2. Zero literais hex/`CTkFont(size=)` novos em `src/ui/screens` (lint no CI).
3. `AlbericusApp` não herda mixins de tela; navegação via `Navigator`.
4. Pelo menos a tela-piloto e mais 2 migradas para View/Controller/State.
5. Troca de tema **não** destrói a UI nem perde seleção/scroll.
6. Catálogo de componentes (§4.4) implementado e adotado nas telas migradas.
7. Tooltips, empty states e progresso presentes nas telas de maior uso diário.

**DoD de adoção (v2, 2026-07-29)** — a fase de adoção (Fase 5 do roadmap) é
considerada concluída quando:

8. Todo campo de entrada segue os tokens de campo (§4.6): nenhum widget com cor de
   fábrica do CTk; pares de campo auditados no `theme_audit` e verdes nos temas
   curados.
9. Zero `CTkEntry`/`CTkOptionMenu`/`CTkTextbox` cru em `src/ui/screens` (lint no
   CI); larguras só pela escala `FIELD_*`; foco e erro visíveis em qualquer campo.
10. Toda tabela com zebra, ordenação por cabeçalho e estado vazio; todo diálogo
    fecha com Esc e respeita `ui_scale_percent`.
11. Nenhuma tela com mais de ~8 ações visíveis no mesmo nível de hierarquia
    (agrupamento em menus `▾` conforme o molde da F2.1).
12. Mensagem que precisa ser lida/copiada nunca sai em toast efêmero
    (`_show_report` com Copiar).

---

## Apêndice A — Rastreabilidade dos achados

Catálogo unificado das duas análises de origem, deduplicado e priorizado, consumido
pelo roadmap. Ver [ROADMAP_UI_UX.md §Catálogo](ROADMAP_UI_UX.md).
