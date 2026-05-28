from __future__ import annotations

import inspect
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .screens.admin import AdminPagesMixin
from .screens.club import ClubPagesMixin
from .screens.dashboard import DashboardPagesMixin
from .screens.library import LibraryMixin
from .screens.pairings import PairingPagesMixin
from .screens.referees import RefereePagesMixin
from .screens.settings import SettingsPagesMixin
from .support import *
from .screens.tournaments import TournamentPagesMixin
from .screens.reports import ReportPagesMixin
from .screens.audit import AuditPagesMixin
from .screens.communication import CommunicationPagesMixin
from .screens.integrations import IntegrationPagesMixin
from src.services.report_engine import ReportEngine


class AlbericusApp(
    UIBuilderMixin,
    ClubPagesMixin,
    DashboardPagesMixin,
    AdminPagesMixin,
    RefereePagesMixin,
    TournamentPagesMixin,
    PairingPagesMixin,
    SettingsPagesMixin,
    LibraryMixin,
    ReportPagesMixin,
    AuditPagesMixin,
    CommunicationPagesMixin,
    IntegrationPagesMixin,
    ctk.CTk,
):
    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        configure_logging()
        logger.info("Aplicativo iniciado")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Albericus - Emparceiramento de Xadrez v1.0")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.db = db or Database()
        self._apply_app_settings()
        self._set_window_icon()
        self.dashboard_service = DashboardService(self.db)
        self.referee_service = RefereeService(self.db)
        self.club_service = ClubService(self.db)
        self.guardian_service = GuardianService(self.db)
        self.tournament_service = TournamentService(self.db)
        self.team_service = TeamService(self.db)
        self.member_service = MemberService(self.db)
        self.learning_level_service = LearningLevelService(self.db)
        self.training_service = TrainingService(self.db)
        self.exercise_service = ExerciseService(self.db)
        self.finance_service = FinanceService(self.db)
        self.event_service = EventService(self.db)
        self.inventory_service = InventoryService(self.db)
        self.security_service = SecurityService(self.db)
        self.sync_service = SyncService(self.db)
        self.clock_integration_service = ClockIntegrationService(self.db)
        self.pairing_service = PairingService(self.db)
        self.qr_result_service = QRResultService(self.db, self.pairing_service)
        self.import_service = ImportService(self.db)
        self.official_rating_service = OfficialRatingService(self.db)
        self.internal_rating_service = InternalRatingService(self.db)
        self.export_service = ExportService(self.db, self.pairing_service)
        self.certificate_service = CertificateService(self.db, self.pairing_service)
        self.communication_service = CommunicationService(self.db)
        self.calendar_service = CalendarService(self.db)
        self.library_service = LibraryService(self.db)
        self.report_engine = ReportEngine(self.db, self.finance_service, self.member_service, self.tournament_service)

        self.current_tournament_id: int | None = None
        self.current_round_id: int | None = None
        self.round_option_map: dict[str, int] = {}
        self.pairing_row_map: dict[str, int] = {}
        self.pairing_detail_map: dict[str, dict[str, Any]] = {}
        self.local_result_server: LocalResultServer | None = None

        self._configure_grid()
        self._configure_tree_style()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._build_login_screen()

    def _on_closing(self) -> None:
        try:
            self.security_service.create_backup("auto_shutdown")
        except Exception as exc:
            logger.error("Erro ao gerar backup no fechamento: %s", exc)
        if self.local_result_server is not None:
            self.local_result_server.stop()
        self.destroy()

    def _build_login_screen(self) -> None:
        self.login_frame = ctk.CTkFrame(self, corner_radius=10)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self.login_frame, text="Albericus", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(self.login_frame, text="Acesso Restrito", font=ctk.CTkFont(size=14)).pack(pady=(0, 20))

        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Usuário", width=200)
        self.username_entry.pack(pady=10, padx=20)

        self.password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Senha", show="*", width=200)
        self.password_entry.pack(pady=10, padx=20)
        
        self.login_error_label = ctk.CTkLabel(self.login_frame, text="", text_color="red")
        self.login_error_label.pack()

        def try_login(event=None):
            user = self.username_entry.get().strip()
            pwd = self.password_entry.get().strip()
            if not user or not pwd:
                self.login_error_label.configure(text="Preencha usuário e senha.")
                return
            if self.security_service.login(user, pwd):
                self.login_frame.destroy()
                self._build_menu()
                self._build_statusbar()
                self._build_content()
                self._register_shortcuts()
                self.show_club()
                self._refresh_statusbar()
            else:
                self.login_error_label.configure(text="Credenciais inválidas.")

        self.password_entry.bind("<Return>", try_login)
        ctk.CTkButton(self.login_frame, text="Entrar", command=try_login, width=200).pack(pady=(10, 20), padx=20)
        self.username_entry.focus()

    def _configure_grid(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

    def _configure_tree_style(self, register_callback: bool = True) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        scale = getattr(self, "_ui_scale_percent", 120) / 100
        style.configure(
            "Treeview",
            rowheight=max(28, int(28 * scale)),
            font=("Segoe UI", max(10, int(10 * scale))),
        )
        style.configure("Treeview.Heading", font=("Segoe UI", max(10, int(10 * scale)), "bold"))
        self._update_tree_colors(style)
        if register_callback:
            ctk.AppearanceModeTracker.add(self._on_appearance_change, self)

    def _on_appearance_change(self, new_appearance_mode: str) -> None:
        style = ttk.Style(self)
        self._update_tree_colors(style)

    def _update_tree_colors(self, style: ttk.Style) -> None:
        mode = ctk.get_appearance_mode()
        bg = THEME_TREE_BG[0] if mode == "Light" else THEME_TREE_BG[1]
        fg = THEME_TREE_FG[0] if mode == "Light" else THEME_TREE_FG[1]
        style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg)
        style.configure("Treeview.Heading", background=bg, foreground=fg)


    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # 1. Clube
        club_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Clube", menu=club_menu)
        club_menu.add_command(label="Dashboard Visual", command=self.show_visual_dashboard, accelerator="Ctrl+1")
        club_menu.add_command(label="Perfil do Clube", command=self.show_club)
        club_menu.add_command(label="Membros", command=self.show_members)
        club_menu.add_command(label="Níveis", command=self.show_learning_levels)
        club_menu.add_command(label="Responsáveis", command=self.show_guardians)

        # 2. Treinamento
        training_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Treinamento", menu=training_menu)
        training_menu.add_command(label="Aulas", command=self.show_training)
        training_menu.add_command(label="Exercícios", command=self.show_exercises)

        # 3. Gestão
        mgmt_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Gestão", menu=mgmt_menu)
        mgmt_menu.add_command(label="Árbitros", command=self.show_referees)
        mgmt_menu.add_command(label="Inventário", command=self.show_inventory)
        mgmt_menu.add_command(label="Financeiro", command=self.show_finance)
        mgmt_menu.add_command(label="Calendário", command=self.show_calendar)
        mgmt_menu.add_command(label="Ranking Interno", command=self.show_internal_ranking)

        # 4. Torneio
        tourn_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Torneio", menu=tourn_menu)
        tourn_menu.add_command(label="Torneios", command=self.show_tournaments, accelerator="Ctrl+2")
        tourn_menu.add_command(label="Central do Torneio", command=self.show_tournament_dashboard, accelerator="Ctrl+3")
        tourn_menu.add_command(label="Painel do Árbitro", command=self.show_arbitration_panel)
        tourn_menu.add_command(label="Config. Torneio", command=self.show_tournament_settings)
        tourn_menu.add_separator()
        tourn_menu.add_command(label="Jogadores", command=self.show_players)
        tourn_menu.add_command(label="Equipes", command=self.show_teams)
        tourn_menu.add_command(label="Rodadas", command=self.show_pairings, accelerator="Ctrl+4")
        tourn_menu.add_command(label="Classificação", command=self.show_standings, accelerator="Ctrl+5")
        tourn_menu.add_command(label="Diplomas", command=self.show_certificates)

        # 5. Ferramentas
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ferramentas", menu=tools_menu)
        tools_menu.add_command(label="Exportar", command=self.show_export)
        tools_menu.add_command(label="Relatórios Administrativos", command=self.show_administrative_reports)
        tools_menu.add_command(label="DRE Financeiro", command=self.show_financial_reports)
        tools_menu.add_command(label="Comunicação", command=self.show_communication)
        tools_menu.add_command(label="Integrações Operacionais", command=self.show_integrations)

        # 6. Configurações
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configurações", menu=settings_menu)
        settings_menu.add_command(label="Config. App", command=self.show_app_settings, accelerator="Ctrl+,")
        settings_menu.add_command(label="Auditoria Completa", command=self.show_audit_logs)

        # 7. Ajuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        
        def show_donation_modal() -> None:
            modal = ctk.CTkToplevel(self)
            modal.title("Apoie o Projeto")
            modal.geometry("400x350")
            modal.grab_set()
            modal.resizable(False, False)

            ctk.CTkLabel(
                modal, 
                text="❤ Apoie o Desenvolvimento", 
                font=ctk.CTkFont(size=20, weight="bold")
            ).pack(pady=(20, 10))

            ctk.CTkLabel(
                modal, 
                text="O Albericus é um projeto independente.\nSe o software tem ajudado você e o seu clube,\nconsidere pagar um café para o desenvolvedor!",
                justify="center"
            ).pack(pady=(0, 20))
            
            ctk.CTkLabel(modal, text="Chave PIX:", font=ctk.CTkFont(weight="bold")).pack()
            pix_key = "30436841843"
            
            entry = ctk.CTkEntry(modal, width=250, justify="center")
            entry.pack(pady=(5, 15))
            entry.insert(0, pix_key)
            entry.configure(state="readonly")

            def copy_pix():
                self.clipboard_clear()
                self.clipboard_append(pix_key)
                self.update()
                copy_btn.configure(text="Copiado!", fg_color="#25D366")
                self.after(2000, lambda: copy_btn.configure(text="Copiar Chave PIX", fg_color=THEME_ACCENT))

            copy_btn = ctk.CTkButton(modal, text="Copiar Chave PIX", command=copy_pix, fg_color=THEME_ACCENT)
            copy_btn.pack(pady=10)

            def open_livepix():
                import webbrowser
                webbrowser.open("https://livepix.gg/darcioalberico")

            livepix_btn = ctk.CTkButton(modal, text="Cartão / Internacional (LivePix)", command=open_livepix, fg_color="#8a2be2", hover_color="#5c1d96")
            livepix_btn.pack(pady=(0, 10))

        help_menu.add_command(label="❤ Apoie o Projeto", command=show_donation_modal)

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
        ]
        for sequence, handler in bindings:
            self.bind_all(sequence, handler)

    def _navigate(self, method_name: str) -> None:
        method = getattr(self, method_name, None)
        if callable(method):
            method()

    def _refresh_current_view(self) -> None:
        method_name = getattr(self, "_current_view_method", None)
        if not method_name:
            self._show_toast("Nada para recarregar.", kind="info", duration_ms=1500)
            return
        method = getattr(self, method_name, None)
        if callable(method):
            method()
        self._refresh_statusbar()

    def _build_statusbar(self) -> None:
        self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=THEME_STATUSBAR_BG)
        self.statusbar.grid(row=1, column=0, sticky="ew")
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

    def require_permission(self, action: str) -> None:
        self.security_service.require_permission(action)

    def show_administrative_reports(self) -> None:
        SettingsPagesMixin.show_reports(self)

    def show_financial_reports(self) -> None:
        ReportPagesMixin.show_reports(self)

    def show_reports(self) -> None:
        self.show_administrative_reports()

    def _show_toast(
        self,
        message: str,
        is_error: bool = False,
        *,
        kind: str | None = None,
        duration_ms: int = 3500,
    ) -> None:
        """Notificação não-bloqueante no canto inferior-direito.

        kind ∈ {"info", "success", "warning", "error"}.
        is_error=True é mantido para compat e equivale a kind="error".
        Erros com stack-trace devem continuar usando _show_error (modal).
        """
        if kind is None:
            kind = "error" if is_error else "info"
        palette = {
            "info":    (THEME_ACCENT,  ("#FFFFFF", "#0B0F19")),
            "success": (THEME_SUCCESS, ("#FFFFFF", "#FFFFFF")),
            "warning": (("#F59E0B", "#FBBF24"), ("#0B0F19", "#0B0F19")),
            "error":   (THEME_DANGER,  ("#FFFFFF", "#FFFFFF")),
        }
        bg, fg = palette.get(kind, palette["info"])

        if not hasattr(self, "_active_toasts"):
            self._active_toasts: list[ctk.CTkFrame] = []

        toast = ctk.CTkFrame(self, fg_color=bg, corner_radius=8)
        ctk.CTkLabel(
            toast, text=message, text_color=fg,
            font=ctk.CTkFont(size=SIZE_BODY),
            wraplength=320, justify="left",
        ).pack(padx=14, pady=8)

        self._active_toasts.append(toast)
        self._restack_toasts()
        toast.lift()

        def dismiss() -> None:
            if toast in self._active_toasts:
                self._active_toasts.remove(toast)
                try:
                    toast.destroy()
                except Exception:
                    pass
                self._restack_toasts()

        self.after(duration_ms, dismiss)

    def _restack_toasts(self) -> None:
        """Reposiciona os toasts ativos empilhados acima da statusbar."""
        offset = 40
        for toast in reversed(getattr(self, "_active_toasts", [])):
            try:
                toast.update_idletasks()
                height = toast.winfo_reqheight()
                toast.place(relx=1.0, rely=1.0, x=-20, y=-offset, anchor="se")
                offset += height + 8
            except Exception:
                pass

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME_APP_BG)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

    def _clear_content(self) -> None:
        self._pairing_shortcuts_enabled = False
        # Rastreia o show_* que disparou esta limpeza para o F5 saber o que recarregar.
        caller = inspect.currentframe().f_back
        if caller is not None:
            name = caller.f_code.co_name
            if name.startswith("show_"):
                self._current_view_method = name
        for child in self.content.winfo_children():
            child.destroy()

    def _page_title(self, title: str, subtitle: str = "") -> None:
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, padx=22, pady=(22, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self._page_header = header

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=SIZE_PAGE_TITLE, weight="bold"),
            text_color=THEME_TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                text_color=THEME_TEXT_SUB,
                wraplength=760,
                justify="left",
            ).grid(row=1, column=0, pady=(2, 0), sticky="w")

    def _build_tournament_nav(self, active: str) -> None:
        if not getattr(self, "current_tournament_id", None):
            return
        tournament = self.db.get_tournament(self.current_tournament_id)
        if not tournament:
            return
        header = getattr(self, "_page_header", None)
        if header is None:
            return

        is_team_tournament = tournament.get("competition_type") == "team"
        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.grid(row=0, column=1, rowspan=2, padx=(16, 0), sticky="e")

        items: list[tuple[str, str, Callable[[], None], str | None]] = [
            ("central", "Central", self.show_tournament_dashboard, None),
            ("arbiter", "Arbitro", self.show_arbitration_panel, None),
            ("settings", "Config.", self.show_tournament_settings, "tournament_write"),
            ("players", "Jogadores", self.show_players, "tournament_write"),
            ("pairings", "Rodadas", self.show_pairings, "tournament_write"),
            ("standings", "Classificacao", self.show_standings, None),
            ("export", "Exportar", self.show_export, None),
            ("certificates", "Diplomas", self.show_certificates, None),
        ]
        if is_team_tournament:
            items.insert(3, ("teams", "Equipes", self.show_teams, "tournament_write"))

        for index, (key, label, command, permission) in enumerate(items):
            is_active = key == active
            button = ctk.CTkButton(
                nav,
                text=label,
                command=command,
                width=112,
                height=32,
                fg_color=THEME_ACCENT if is_active else "transparent",
                border_width=0 if is_active else 1,
                text_color=("#FFFFFF", "#0B0F19") if is_active else THEME_TEXT_MAIN,
            )
            button.grid(row=0, column=index, padx=(6, 0), pady=(0, 6), sticky="e")
            if permission:
                self._disable_if_unauthorized(button, permission)

    def _make_panel(self, parent: ctk.CTkBaseClass | None = None) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(parent or self.content, fg_color=THEME_PANEL_BG, corner_radius=8)
        return panel

    def _section_title(
        self,
        parent: ctk.CTkBaseClass,
        text: str,
        *,
        subsection: bool = False,
    ) -> ctk.CTkLabel:
        """Rótulo padronizado de seção. Use subsection=True para sub-cabeçalhos."""
        font = font_subsection() if subsection else font_section()
        return ctk.CTkLabel(parent, text=text, font=font, text_color=THEME_TEXT_MAIN)

    def _kpi_card(
        self,
        parent: ctk.CTkBaseClass,
        label: str,
        value: Any,
        *,
        subtitle: str = "",
    ) -> ctk.CTkFrame:
        """Card padrão de KPI: label (sub) / valor grande / subtitle opcional.

        O caller posiciona o card com .grid()/.pack() no parent.
        """
        card = self._make_panel(parent)
        ctk.CTkLabel(card, text=label, text_color=THEME_TEXT_SUB).pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(card, text=str(value), font=font_kpi_value()).pack(
            anchor="w", padx=14, pady=(0, 0 if subtitle else 12)
        )
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, text_color=THEME_TEXT_SUB).pack(
                anchor="w", padx=14, pady=(0, 12)
            )
        return card

    def _make_scrollable_panel(
        self,
        parent: ctk.CTkBaseClass | None = None,
        width: int = 292,
    ) -> ctk.CTkScrollableFrame:
        panel = ctk.CTkScrollableFrame(
            parent or self.content,
            fg_color=THEME_PANEL_BG,
            corner_radius=8,
            width=width,
        )
        panel.grid_columnconfigure(0, weight=1)
        return panel

    def _make_tree(
        self,
        parent: ctk.CTkFrame,
        columns: list[str],
        headings: dict[str, str],
        widths: dict[str, int],
        visible_rows: int = 10,
    ) -> ttk.Treeview:
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            height=visible_rows,
            show="headings",
            selectmode="browse",
        )
        for column in columns:
            tree.heading(column, text=headings.get(column, column))
            tree.column(column, width=widths.get(column, 100), anchor="w", stretch=False)
        y_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        return tree

    @staticmethod
    def _member_display_name(member: dict[str, Any]) -> str:
        name = str(member.get("name") or "").strip()
        surname = str(member.get("surname") or "").strip()
        return f"{surname}, {name}" if surname and name else surname or name

    def _require_tournament(self) -> bool:
        if self.current_tournament_id:
            return True
        self._clear_content()
        self._page_title("Selecione um torneio", "Crie ou abra um torneio antes de usar esta tela.")
        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=18, sticky="nsew")
        ctk.CTkButton(body, text="Ir para Torneios", command=self.show_tournaments).pack(anchor="w")
        return False

    def _set_current_tournament(self, tournament_id: int) -> None:
        self.current_tournament_id = tournament_id
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            self.tournament_label.configure(text="Nenhum torneio selecionado")
            return
        scope = self._tournament_scope_text(tournament)
        self.tournament_label.configure(
            text=f"{tournament['name']} | {scope} | {tournament['rounds_count']} rodadas | {tournament['status']}"
        )
        self._refresh_statusbar()

    @staticmethod
    def _tournament_scope_key(tournament: dict[str, Any]) -> str:
        if tournament.get("class_id"):
            return "class"
        if tournament.get("club_id"):
            return "club"
        return "standalone"

    def _tournament_scope_text(self, tournament: dict[str, Any]) -> str:
        scope = self._tournament_scope_key(tournament)
        if scope == "class":
            return tournament.get("class_name") or TOURNAMENT_SCOPES["class"]
        if scope == "club":
            return tournament.get("club_name") or TOURNAMENT_SCOPES["club"]
        return TOURNAMENT_SCOPES["standalone"]

    def _apply_app_settings(self) -> None:
        try:
            settings = self.db.get_app_settings()
            ctk.set_appearance_mode(str(settings.get("appearance_mode") or "System"))
            color_theme = settings.get("color_theme")
            if color_theme and color_theme in ["blue", "green", "dark-blue"]:
                ctk.set_default_color_theme(color_theme)
            try:
                scale_percent = int(str(settings.get("ui_scale_percent") or "120"))
            except ValueError:
                scale_percent = 100
            scale_percent = min(160, max(80, scale_percent))
            self._ui_scale_percent = scale_percent
            scale = scale_percent / 100
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
        except Exception:
            logger.exception("Falha ao aplicar configuracoes do aplicativo")

    def _set_window_icon(self) -> None:
        icon_path = resource_path("assets/app_icon.ico")
        if not icon_path.exists():
            return
        try:
            self.iconbitmap(str(icon_path))
        except Exception:
            logger.exception("Falha ao carregar icone do aplicativo")

    def _default_export_dir(self) -> Path:
        try:
            settings = self.db.get_app_settings()
            path = Path(str(settings.get("default_export_dir") or default_export_dir()))
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            fallback = default_export_dir()
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    def _show_error(self, error: Exception) -> None:
        error_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        title, message, is_unexpected = self._error_dialog(error, error_id)
        if is_unexpected:
            logger.error(
                "Erro inesperado [%s]",
                error_id,
                exc_info=(type(error), error, error.__traceback__),
            )
        else:
            logger.warning("%s: %s", title, error)
        messagebox.showerror(title, message)

    @staticmethod
    def _error_dialog(
        error: Exception,
        error_id: str,
    ) -> tuple[str, str, bool]:
        if isinstance(error, AppError):
            return "Erro", str(error), False
        if isinstance(error, PermissionError):
            return (
                "Erro de permissao",
                f"Sem permissao para acessar o arquivo ou pasta.\n\n{error}",
                False,
            )
        if isinstance(error, FileNotFoundError):
            return (
                "Arquivo nao encontrado",
                f"O arquivo ou pasta informado nao foi encontrado.\n\n{error}",
                False,
            )
        if isinstance(error, OSError):
            return (
                "Erro de arquivo",
                f"Nao foi possivel acessar o arquivo ou pasta.\n\n{error}",
                False,
            )
        if isinstance(error, ValueError):
            return "Dados invalidos", str(error), False
        return (
            "Erro inesperado",
            "Ocorreu uma falha inesperada.\n\n"
            f"Codigo: {error_id}\n"
            f"Consulte o log em: {current_log_path()}",
            True,
        )

    def _show_info(self, message: str) -> None:
        messagebox.showinfo("Albericus", message)

    def _run_background(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        busy_message: str = "Processando...",
        busy_widget: Any | None = None,
    ) -> None:
        if busy_widget is not None:
            try:
                busy_widget.configure(state="disabled")
            except Exception:
                logger.exception("Falha ao desabilitar widget durante tarefa em background")
        if hasattr(self, "status_label") and busy_message:
            self.status_label.configure(text=busy_message)

        def run() -> None:
            try:
                result = work()
            except Exception as exc:
                self.after(0, lambda error=exc: finish(error=error))
                return
            self.after(0, lambda: finish(result=result))

        def finish(result: Any = None, error: Exception | None = None) -> None:
            if busy_widget is not None:
                try:
                    busy_widget.configure(state="normal")
                except Exception:
                    logger.exception("Falha ao reabilitar widget apos tarefa em background")
            if hasattr(self, "status_label"):
                self.status_label.configure(text=self._default_status_text())
            if error:
                self._show_error(error)
                return
            if on_success:
                try:
                    on_success(result)
                except Exception as exc:
                    self._show_error(exc)

        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def _safe_filename(text: str, fallback: str) -> str:
        value = "".join(
            character.lower() if character.isalnum() else "_"
            for character in text
        ).strip("_")
        return value or fallback

    def _grid_form_buttons(
        self,
        parent: ctk.CTkBaseClass,
        buttons: list[tuple[str, Callable[[], None]]],
        start_row: int,
        padx: int = 16,
        required_action: str = "",
    ) -> None:
        for offset, (label, command) in enumerate(buttons):
            btn = ctk.CTkButton(parent, text=label, command=command)
            btn.grid(
                row=start_row + offset,
                column=0,
                padx=padx,
                pady=(8 if offset == 0 else 4, 0),
                sticky="ew",
            )
            if required_action:
                self._disable_if_unauthorized(btn, required_action)
