"""``AppShell``: a casca da janela — tudo que não é tela.

Conteúdo, statusbar, toasts, indicador de progresso, atalhos globais, command
palette e a ligação com o :class:`~src.ui.navigation.Navigator`. **Não conhece
nenhuma tela**: quem monta tela são os mixins de ``screens/``, que continuam
funcionando como antes (ESPEC_UI_UX §3.1 / achado P0-1).

Casca fina de propósito: a ``AlbericusApp`` herda daqui e segue herdando os
mixins legados. Isso permite migrar tela a tela sem um *big-bang* — o oposto do
que aconteceria se a casca fosse reescrita junto com as telas.

O host precisa ser uma janela CTk e expor ``db`` e ``security_service``.
"""
from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk

from src.core.database import default_backup_dir

from .components import BusyIndicator
from .components.sidebar import (
    MODE_FULL as SIDEBAR_FULL,
)
from .components.sidebar import (
    MODE_HIDDEN as SIDEBAR_HIDDEN,
)
from .components.sidebar import (
    MODE_RAIL as SIDEBAR_RAIL,
)
from .components.sidebar import (
    Sidebar,
)
from .components.toast import ToastAction, ToastStack
from .i18n import t
from .navigation import DESTINATIONS, Navigator
from .theme import (
    SIZE_BODY,
    THEME_ACCENT,
    THEME_APP_BG,
    THEME_ON_ACCENT,
    THEME_PANEL_BG,
    THEME_STATUSBAR_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
)


class AppShell:
    """Casca da janela. Ver o módulo para o contrato esperado do host."""

    def _build_shell_navigation(self) -> Navigator:
        """Cria o Navigator da janela. Chamado uma vez, na construção do app."""
        self.navigator = Navigator(self)
        return self.navigator

    def _configure_grid(self) -> None:
        self.grid_columnconfigure(0, weight=0)  # sidebar: largura fixa
        self.grid_columnconfigure(1, weight=1)  # conteudo: ocupa o resto
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

    def _register_shortcuts(self) -> None:
        """Atalhos globais. Disponíveis depois do login."""
        bindings: list[tuple[str, Callable[[Any], None]]] = [
            ("<F5>", lambda _e: self._refresh_current_view()),
            ("<Control-Key-1>", lambda _e: self._navigate("show_visual_dashboard")),
            ("<Control-Key-2>", lambda _e: self._navigate("show_tournaments")),
            ("<Control-Key-3>", lambda _e: self._navigate("show_tournament_dashboard")),
            ("<Control-Key-4>", lambda _e: self._navigate("show_pairings")),
            ("<Control-Key-5>", lambda _e: self._navigate("show_standings")),
            ("<Control-comma>", lambda _e: self._navigate("show_app_settings")),
            ("<Control-k>", lambda _e: self._show_command_palette()),
            ("<Control-K>", lambda _e: self._show_command_palette()),
        ]
        for sequence, handler in bindings:
            self.bind_all(sequence, handler)

    def _navigate(self, key_or_method: str) -> None:
        """Vai para um destino do registro (aceita chave ou nome do metodo)."""
        self.navigator.go(key_or_method)

    @property
    def _current_view_method(self) -> str | None:
        """Tela em exibicao. Mantido como atributo por compatibilidade: telas
        legadas leem isto para decidir se um refresh agendado ainda faz sentido.
        Tolerante a ser lido antes do Navigator existir (login)."""
        navigator = getattr(self, "navigator", None)
        return navigator.current if navigator is not None else None

    def _refresh_current_view(self) -> None:
        if not self.navigator.refresh_current():
            self._show_toast(t("shell.reload.empty"), kind="info", duration_ms=1500)
            return
        self._refresh_statusbar()

    def _command_palette_actions(self) -> list[tuple[str, Callable[[], None], str, str | None]]:
        """Acoes do command palette: destinos do registro unico + acoes soltas.

        O registro (navigation.DESTINATIONS) e a unica lista de destinos do app;
        aqui ela so vira o formato que o palette consome. Destino sem metodo na
        aplicacao e ignorado, em vez de quebrar a paleta inteira."""
        acoes: list[tuple[str, Callable[[], None], str, str | None]] = []
        for destino in DESTINATIONS:
            metodo = getattr(self, destino.method, None)
            if callable(metodo):
                acoes.append((destino.label, metodo, destino.keywords, destino.icon))
        acoes.append(
            (t("shell.action.reload"), self._refresh_current_view, "refresh atualizar", "configuracoes")
        )
        return acoes

    def _show_command_palette(self) -> None:
        if getattr(self, "_palette_open", False):
            return
        self._palette_open = True

        palette = ctk.CTkToplevel(self)
        palette.title(t("shell.palette.title"))
        palette.geometry("560x420")
        palette.transient(self)
        palette.resizable(False, False)
        try:
            palette.grab_set()
        except Exception:
            pass

        # Centraliza próximo ao topo da janela principal
        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 560) // 2
        y = self.winfo_rooty() + 80
        palette.geometry(f"+{max(0, x)}+{max(0, y)}")

        actions = self._command_palette_actions()
        state: dict[str, Any] = {"filtered": list(actions), "selected": 0, "rows": []}

        entry = ctk.CTkEntry(palette, placeholder_text=t("shell.palette.placeholder"))
        entry.pack(fill="x", padx=12, pady=(12, 6))

        list_holder = ctk.CTkScrollableFrame(palette, fg_color=THEME_PANEL_BG)
        list_holder.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        list_holder.grid_columnconfigure(0, weight=1)

        def close() -> None:
            self._palette_open = False
            try:
                palette.grab_release()
            except Exception:
                pass
            palette.destroy()

        def execute(index: int) -> None:
            if not (0 <= index < len(state["filtered"])):
                return
            _, fn, _, _ = state["filtered"][index]
            close()
            try:
                fn()
            except Exception as exc:
                self._show_error(exc)

        def render_rows() -> None:
            for row in state["rows"]:
                row.destroy()
            state["rows"] = []
            for index, (label, _fn, _kw, icon_key) in enumerate(state["filtered"]):
                is_selected = index == state["selected"]
                img = self._ctk_menu_icons.get(icon_key) if hasattr(self, "_ctk_menu_icons") else None
                row = ctk.CTkLabel(
                    list_holder,
                    text=f"  {label}",
                    image=img,
                    compound="left",
                    anchor="w",
                    fg_color=THEME_ACCENT if is_selected else "transparent",
                    text_color=THEME_ON_ACCENT if is_selected else THEME_TEXT_MAIN,
                    corner_radius=4,
                )
                row.grid(row=index, column=0, sticky="ew", padx=4, pady=1, ipadx=8, ipady=4)
                row.bind("<Button-1>", lambda _e, i=index: execute(i))
                state["rows"].append(row)
            if not state["filtered"]:
                ctk.CTkLabel(
                    list_holder, text=t("shell.palette.empty"),
                    text_color=THEME_TEXT_SUB,
                ).grid(row=0, column=0, pady=20)

        def filter_actions(_event: Any = None) -> None:
            query = entry.get().strip().lower()
            if not query:
                state["filtered"] = list(actions)
            else:
                scored: list[tuple[int, tuple[str, Callable, str, str | None]]] = []
                for action in actions:
                    label, _fn, kw, icon_key = action
                    haystack = f"{label} {kw}".lower()
                    if query in haystack:
                        # prefixo do label = melhor pontuação
                        score = 0 if label.lower().startswith(query) else (
                            1 if query in label.lower() else 2
                        )
                        scored.append((score, action))
                scored.sort(key=lambda item: item[0])
                state["filtered"] = [action for _score, action in scored]
            state["selected"] = 0
            render_rows()

        def move(delta: int) -> str:
            if state["filtered"]:
                state["selected"] = (state["selected"] + delta) % len(state["filtered"])
                render_rows()
            return "break"

        entry.bind("<KeyRelease>", filter_actions)
        entry.bind("<Down>", lambda _e: move(1))
        entry.bind("<Up>", lambda _e: move(-1))
        entry.bind("<Return>", lambda _e: execute(state["selected"]))
        palette.bind("<Escape>", lambda _e: close())
        palette.protocol("WM_DELETE_WINDOW", close)

        render_rows()
        entry.focus_set()

    def _build_statusbar(self) -> None:
        self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=THEME_STATUSBAR_BG)
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.statusbar.grid_columnconfigure(0, weight=2)
        self.statusbar.grid_columnconfigure(1, weight=1)
        self.statusbar.grid_columnconfigure(2, weight=2)

        font_status = ctk.CTkFont(size=SIZE_BODY)

        self.tournament_label = ctk.CTkLabel(
            self.statusbar,
            text="Nenhum torneio selecionado",
            text_color=THEME_TEXT_SUB,
            justify="left",
            font=font_status,
        )
        self.tournament_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")

        self.metrics_label = ctk.CTkLabel(
            self.statusbar,
            text="",
            text_color=THEME_TEXT_SUB,
            justify="center",
            font=font_status,
        )
        self.metrics_label.grid(row=0, column=1, padx=10, pady=2, sticky="")

        self.status_label = ctk.CTkLabel(
            self.statusbar,
            text=self._default_status_text(),
            text_color=THEME_TEXT_SUB,
            justify="right",
            font=font_status,
        )
        self.status_label.grid(row=0, column=2, padx=10, pady=2, sticky="e")

        # Progresso de tarefas em background: some quando nao ha nada rodando.
        self.busy_indicator = BusyIndicator(self.statusbar)
        self.busy_indicator.grid_config(row=0, column=3, padx=(0, 12), pady=2, sticky="e")

    def _default_status_text(self) -> str:
        db_name = Path(self.db.db_path).name
        backup = self._last_backup_label()
        return f"Banco: {db_name}" + (f"  ·  Backup: {backup}" if backup else "")

    def _last_backup_label(self) -> str:
        try:
            backup_dir = default_backup_dir()
            if not backup_dir.exists():
                return ""
            entries = [p for p in backup_dir.iterdir() if p.is_file() or p.is_dir()]
            if not entries:
                return ""
            latest = max(entries, key=lambda p: p.stat().st_mtime)
            ts = datetime.fromtimestamp(latest.stat().st_mtime)
            today = datetime.now().date()
            if ts.date() == today:
                return f"hoje {ts.strftime('%H:%M')}"
            return ts.strftime("%d/%m %H:%M")
        except Exception:
            return ""

    def _refresh_statusbar(self) -> None:
        if not hasattr(self, "metrics_label"):
            return
        parts: list[str] = []
        tournament_id = getattr(self, "current_tournament_id", None)
        if tournament_id:
            try:
                dashboard = self.pairing_service.arbitration_dashboard(tournament_id)
                metrics = dashboard.get("metrics", {})
                pending = metrics.get("pending_results", 0)
                closed = metrics.get("closed_rounds", 0)
                total = metrics.get("rounds_count", 0)
                parts.append(f"Rodadas {closed}/{total}")
                if pending:
                    parts.append(f"⚠ {pending} pendente(s)")
                else:
                    parts.append("✓ sem pendências")
            except Exception:
                pass
        self.metrics_label.configure(text="  ·  ".join(parts))
        if hasattr(self, "status_label"):
            self.status_label.configure(text=self._default_status_text())

    @property
    def toasts(self) -> ToastStack:
        """Pilha de toasts da janela (criada sob demanda)."""
        if getattr(self, "_toast_stack", None) is None:
            self._toast_stack = ToastStack(self)
        return self._toast_stack

    def _show_toast(
        self,
        message: str,
        is_error: bool = False,
        *,
        kind: str | None = None,
        duration_ms: int | None = None,
        action: ToastAction | None = None,
    ) -> None:
        """Notificação não-bloqueante no canto inferior-direito.

        kind ∈ {"info", "success", "warning", "error"}.
        is_error=True é mantido para compat e equivale a kind="error".
        `action=("Desfazer", callback)` acrescenta um botão e estende a duração.
        Erros com stack-trace devem continuar usando _show_error (modal).
        """
        if kind is None:
            kind = "error" if is_error else "info"
        self.toasts.show(message, kind=kind, duration_ms=duration_ms, action=action)

    def _build_content(self) -> None:
        """Monta o corpo da janela: sidebar (coluna 0) + área de conteúdo (1).

        A sidebar entra aqui, e não num passo separado, porque é o mesmo ponto
        que o login e a reconstrução por troca de tema já chamam — um caminho só
        para montar o corpo.
        """
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME_APP_BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

    def _build_sidebar(self) -> None:
        """Navegação primária persistente (P1-7). O `tk.Menu` segue como fallback."""
        anterior = getattr(self, "sidebar", None)
        if anterior is not None:
            try:
                anterior.frame.destroy()
            except Exception:
                pass
        # A janela e reconstruida na troca de tema: os inscritos antigos apontam
        # para widgets mortos e precisam sair antes de a nova barra assinar.
        self.navigator.clear_subscribers()
        self.sidebar = Sidebar(
            self,
            navigator=self.navigator,
            icons=getattr(self, "_ctk_menu_icons", None),
        )
        self.sidebar.frame.grid(row=0, column=0, sticky="nsw")
        self.navigator.subscribe(self.sidebar.highlight)
        self.bind("<Configure>", self._sync_sidebar_mode, add="+")
        self._sync_sidebar_mode()

    # Limiares REMEDIDOS na B-8, com as 23 telas do smoke de layout — e o achado
    # foi que o gargalo mudou de dono. Eram 1500/1440 quando a Exportar pedia
    # ~1.375px e a barra do torneio ocupava uma linha unica de ~950px; as duas
    # foram corrigidas, e agora quem manda no limiar sao as telas administrativas
    # densas (Ranking interno, Financeiro, Calendario, Exercicios, Relatorios).
    #
    # Medido: com a barra COMPLETA todas cabem a partir de 1.416px reais; com o
    # RAIL, a partir de 1.260px — antes o rail so aparecia em 1.440px, ou seja,
    # a navegacao agora sobrevive a 180px a menos de janela. Abaixo do menor
    # limiar a barra some e o menu nativo volta a ser a navegacao (P1-7): melhor
    # perder a barra do que empurrar botao para fora da janela.
    #
    # Pixels REAIS: o CTk multiplica a geometria pela escala de UI (120% por
    # padrao), entao uma janela pedida em 1180 mede 1416 na tela.
    #
    # O proximo ganho esta nessas cinco telas administrativas — registrado no
    # ROADMAP como continuacao da B-8, nao como divida esquecida.
    _SIDEBAR_FULL_FROM = 1416
    _SIDEBAR_RAIL_FROM = 1260

    def _sync_sidebar_mode(self, event: Any = None) -> None:
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None:
            return
        if event is not None and getattr(event, "widget", self) is not self:
            return  # <Configure> de widget filho: nao interessa
        # Dentro do <Configure>, winfo_width() ainda devolve a largura ANTIGA:
        # a nova vem no proprio evento.
        largura = getattr(event, "width", 0) or self.winfo_width()
        # A barra do torneio se redistribui na mesma carona: ela ja escuta a
        # largura da janela por tabela interposta, e um segundo <Configure> so
        # para ela seria o dobro de trabalho no mesmo evento.
        relayout = getattr(self, "_layout_tournament_nav", None)
        if callable(relayout):
            relayout()
        if largura >= self._SIDEBAR_FULL_FROM:
            sidebar.set_mode(SIDEBAR_FULL)
        elif largura >= self._SIDEBAR_RAIL_FROM:
            sidebar.set_mode(SIDEBAR_RAIL)
        else:
            sidebar.set_mode(SIDEBAR_HIDDEN)

    def _clear_content(self) -> None:
        self._pairing_shortcuts_enabled = False
        if self._arbitration_refresh_job is not None:
            try:
                self.after_cancel(self._arbitration_refresh_job)
            except Exception:
                pass
            self._arbitration_refresh_job = None
        # Anota o show_* que disparou esta limpeza, para o F5 saber o que
        # recarregar. Fica aqui (e nao so no Navigator.go) porque muita tela e
        # aberta por chamada direta — botao que chama self.show_pairings().
        caller = inspect.currentframe().f_back
        if caller is not None:
            self.navigator.record(caller.f_code.co_name)
        for child in self.content.winfo_children():
            child.destroy()

